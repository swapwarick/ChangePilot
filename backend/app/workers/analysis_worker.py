"""Async Background Analysis Worker Pipeline.

Executes analysis tasks out of the HTTP request loop:
1. PENDING -> Updates job status
2. CLONING -> Clones/fetches repo via GitCLIManager
3. PARSING -> Parses source code with TreeSitterCodeParser & checks content hash cache
4. BUILDING_GRAPH -> Constructs Knowledge Graph, stores Postgres snapshot, syncs Neo4j
5. SCORING -> Calculates deterministic risk score & blast radius from Neo4j/AST evidence
6. AI_REPORT -> Asynchronously generates AI explanation report
7. COMPLETED -> Saves final result to PostgreSQL
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.tree_sitter_parser import ImportSymbol, ParsedFileAST, TreeSitterCodeParser, is_generated_or_vendor
from app.database.tables import AnalysisJobRow, AnalysisRow, FileASTCacheRow, RepoKnowledgeGraphRow
from app.graph.knowledge_graph import KnowledgeGraphBuilder
from app.graph.neo4j_engine import Neo4jGraphEngine
from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger
from app.models.risk import RiskInput
from app.providers.registry import AIProviderRegistry
from app.repositories.provider_repo import AIProviderConfigRepository
from app.risk.engine import DeterministicRiskEngine
from app.services.git_cli import GitCLIManager
from app.services.report_service import AIReportService

logger = logging.getLogger(__name__)


class AnalysisWorkerPipeline:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._git_cli = GitCLIManager()
        self._parser = TreeSitterCodeParser()
        self._graph_builder = KnowledgeGraphBuilder()
        self._neo4j = Neo4jGraphEngine()
        self._risk_engine = DeterministicRiskEngine()

    async def update_job(
        self, job_id: str, status: str, step: str, progress: int, error: str | None = None, analysis_id: str | None = None
    ) -> None:
        async with self._session_factory() as session:
            job = await session.get(AnalysisJobRow, job_id)
            if job:
                job.status = status
                job.step = step
                job.progress = progress
                if error:
                    job.error = error
                if analysis_id:
                    job.analysis_id = analysis_id
                await session.commit()

    async def execute_job(
        self,
        job_id: str,
        repository_id: str,
        token: str,
        owner: str,
        repo_name: str,
        clone_url: str,
        base_ref: str,
        head_ref: str,
        ai_provider_registry: Any = None,
    ) -> None:
        try:
            # Step 1: CLONING
            await self.update_job(job_id, "CLONING", "Fetching repository via Git CLI...", 15)
            await self._git_cli.ensure_bare_repo(owner, repo_name, clone_url, token)
            worktree_dir = await self._git_cli.checkout_worktree(owner, repo_name, head_ref, clone_url, token)

            # Step 2: DIFF
            diff_result = await self._git_cli.get_commit_diff(owner, repo_name, base_ref, head_ref, clone_url, token)
            changed_files = diff_result.changed_files or ["README.md"]

            # Step 3: PARSING (with content hash caching)
            await self.update_job(job_id, "PARSING", "Parsing source AST with Tree-Sitter...", 40)
            parsed_files = []

            async with self._session_factory() as session:
                for file_path in worktree_dir.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(worktree_dir).as_posix()
                        if not is_generated_or_vendor(rel_path) and self._parser.detect_language(rel_path):
                            try:
                                content = file_path.read_bytes()
                                file_hash = self._parser.compute_file_hash(content)

                                # Check cache
                                cached = await session.get(FileASTCacheRow, file_hash)
                                if not cached:
                                    parsed = self._parser.parse_file(rel_path, content)
                                    parsed_files.append(parsed)
                                    # Save to cache
                                    cache_row = FileASTCacheRow(
                                        file_hash=file_hash,
                                        file_path=rel_path,
                                        language=parsed.language,
                                        parsed_ast={
                                            "file_path": parsed.file_path,
                                            "file_hash": parsed.file_hash,
                                            "language": parsed.language,
                                            "defined_classes": parsed.defined_classes,
                                            "defined_functions": parsed.defined_functions,
                                            "api_routes": parsed.api_routes,
                                            "imports": [
                                                {
                                                    "source_module": imp.source_module,
                                                    "imported_name": imp.imported_name,
                                                    "alias": imp.alias,
                                                    "is_relative": imp.is_relative,
                                                }
                                                for imp in parsed.imports
                                            ],
                                        },
                                    )
                                    await session.merge(cache_row)
                                else:
                                    ast_data = cached.parsed_ast or {}
                                    imports = [
                                        ImportSymbol(
                                            source_module=imp.get("source_module", ""),
                                            imported_name=imp.get("imported_name", "*"),
                                            alias=imp.get("alias"),
                                            is_relative=imp.get("is_relative", False),
                                        )
                                        for imp in ast_data.get("imports", [])
                                    ]
                                    parsed = ParsedFileAST(
                                        file_path=rel_path,
                                        file_hash=file_hash,
                                        language=cached.language,
                                        imports=imports,
                                        defined_classes=ast_data.get("defined_classes", []),
                                        defined_functions=ast_data.get("defined_functions", []),
                                        api_routes=ast_data.get("api_routes", []),
                                    )
                                    parsed_files.append(parsed)
                            except Exception as exc:  # noqa: BLE001
                                logger.warning("Error parsing %s: %s", rel_path, exc)

                await session.commit()

            # Step 4: BUILDING_GRAPH
            await self.update_job(job_id, "BUILDING_GRAPH", "Building Repository Knowledge Graph...", 65)
            graph, graph_hash, health_metrics = self._graph_builder.build_graph_from_parsed_files(parsed_files)

            # Store Knowledge Graph in DB
            async with self._session_factory() as session:
                existing_kg_stmt = (
                    select(RepoKnowledgeGraphRow)
                    .where(RepoKnowledgeGraphRow.repository_id == repository_id)
                    .order_by(RepoKnowledgeGraphRow.created_at.desc())
                    .limit(1)
                )
                existing_kg = (await session.execute(existing_kg_stmt)).scalar_one_or_none()

                orphan_list = getattr(health_metrics, "potential_orphan_candidates", getattr(health_metrics, "orphan_modules", []))
                gap_list = getattr(health_metrics, "potential_test_gaps", getattr(health_metrics, "test_coverage_gaps", []))

                health_dict = {
                    "health_score": health_metrics.health_score,
                    "total_files": health_metrics.total_files,
                    "total_classes": health_metrics.total_classes,
                    "total_functions": health_metrics.total_functions,
                    "total_dependencies": health_metrics.total_dependencies,
                    "circular_dependencies": health_metrics.circular_dependencies,
                    "orphan_modules": orphan_list,
                    "potential_orphan_candidates": orphan_list,
                    "dead_code_symbols": health_metrics.dead_code_symbols,
                    "god_classes": health_metrics.god_classes,
                    "high_fan_out_files": health_metrics.high_fan_out_files,
                    "high_fan_in_files": health_metrics.high_fan_in_files,
                    "test_coverage_gaps": gap_list,
                    "potential_test_gaps": gap_list,
                    "architectural_violations": health_metrics.architectural_violations,
                    "coverage_notice": getattr(health_metrics, "coverage_notice", "Coverage data unavailable; test gap inferred from repository structure."),
                }

                if existing_kg:
                    existing_kg.commit_sha = head_ref
                    existing_kg.graph_hash = graph_hash
                    existing_kg.nodes = [n.model_dump() for n in graph.nodes]
                    existing_kg.edges = [e.model_dump() for e in graph.edges]
                    existing_kg.health_metrics = health_dict
                else:
                    kg_row = RepoKnowledgeGraphRow(
                        repository_id=repository_id,
                        commit_sha=head_ref,
                        graph_hash=graph_hash,
                        nodes=[n.model_dump() for n in graph.nodes],
                        edges=[e.model_dump() for e in graph.edges],
                        health_metrics=health_dict,
                    )
                    session.add(kg_row)
                await session.commit()

            # Sync Neo4j index & calculate Blast Radius
            await self._neo4j.sync_graph(repository_id, graph)
            blast_radius = await self._neo4j.calculate_blast_radius(repository_id, changed_files, graph=graph)

            # Step 5: SCORING (Deterministic Phase)
            await self.update_job(job_id, "SCORING", "Computing deterministic risk score...", 85)
            impacted_modules = blast_radius.impacted_modules or [f.split("/")[0] for f in changed_files if "/" in f]
            critical_modules = [f for f in changed_files if any(m in f.lower() for m in ("auth", "db", "session", "payment", "security"))]

            risk_result = self._risk_engine.score(
                RiskInput(
                    changed_files=changed_files,
                    impacted_modules=impacted_modules,
                    dependency_count=blast_radius.transitive_dependency_count,
                    missing_tests=not any("test" in f.lower() or "spec" in f.lower() for f in changed_files),
                    large_refactor=len(changed_files) >= 15,
                    critical_modules=critical_modules,
                )
            )

            # Create Analysis Record
            analysis_id = f"anl-{job_id[:8]}"
            analysis = ChangeAnalysisResult(
                id=analysis_id,
                repository_id=repository_id,
                trigger=AnalysisTrigger.COMMIT_COMPARISON,
                changed_files=changed_files,
                impacted_modules=impacted_modules,
                dependency_graph=graph,
                risk=risk_result,
                ai_report="AI report is generating asynchronously...",
            )

            async with self._session_factory() as session:
                analysis_row = AnalysisRow(
                    id=analysis_id,
                    repository_id=repository_id,
                    trigger="commit_comparison",
                    base_ref=base_ref,
                    head_ref=head_ref,
                    changed_files=changed_files,
                    impacted_modules=impacted_modules,
                    dependency_graph=graph.model_dump(),
                    risk_score=risk_result.score,
                    risk_level=risk_result.level.value,
                    risk_confidence=risk_result.confidence,
                    risk_evidence=[e.model_dump() for e in risk_result.evidence],
                    risk_reasons=risk_result.reasons,
                    ai_report=analysis.ai_report,
                    parser_version="1.0.0-treesitter",
                    graph_version="1.0.0",
                    risk_engine_version="1.0.0-deterministic",
                    ai_prompt_version="1.0.0",
                )
                await session.merge(analysis_row)
                await session.commit()

            # Step 6: AI_REPORT (Async AI Explanation)
            await self.update_job(job_id, "AI_REPORT", "Generating AI explanation report...", 90, analysis_id=analysis_id)

            try:
                if not ai_provider_registry:
                    async with self._session_factory() as session:
                        configs = await AIProviderConfigRepository(session).list_all()
                        enabled_configs = [c for c in configs if c.enabled]
                        if enabled_configs:
                            ai_provider_registry = AIProviderRegistry(configs=enabled_configs)

                if ai_provider_registry:
                    report_service = AIReportService(provider_registry=ai_provider_registry)
                    ai_report_text = await report_service.generate_report(analysis)
                    async with self._session_factory() as session:
                        row = await session.get(AnalysisRow, analysis_id)
                        if row:
                            row.ai_report = ai_report_text
                            await session.commit()
                else:
                    async with self._session_factory() as session:
                        row = await session.get(AnalysisRow, analysis_id)
                        if row:
                            row.ai_report = self._build_fallback_report(analysis, "No active AI provider configured.")
                            await session.commit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Async AI Report generation warning (non-fatal): %s", exc)
                async with self._session_factory() as session:
                    row = await session.get(AnalysisRow, analysis_id)
                    if row:
                        row.ai_report = self._build_fallback_report(analysis, f"LLM connection unavailable ({exc}).")
                        await session.commit()

            await self.update_job(job_id, "COMPLETED", "Analysis Completed", 100, analysis_id=analysis_id)

        except Exception as exc:
            logger.exception("Analysis job failed: %s", job_id)
            await self.update_job(job_id, "FAILED", f"Error: {exc}", 0, error=str(exc))
        finally:
            # Clean up worktree
            await self._git_cli.cleanup_worktree(owner, repo_name, head_ref)

    @staticmethod
    def _build_fallback_report(analysis: ChangeAnalysisResult, reason: str) -> str:
        level_str = str(analysis.risk.level.value if hasattr(analysis.risk.level, "value") else analysis.risk.level).upper()
        lines = [
            f"### Change Analysis Summary ({level_str} RISK)",
            f"*{reason} Showing deterministic structural analysis.*",
            "",
            f"**Risk Score**: {analysis.risk.score:.2f} / 1.00 (Confidence: {int(analysis.risk.confidence * 100)}%)",
            f"**Changed Files**: {len(analysis.changed_files)} file(s)",
            f"**Impacted Modules**: {', '.join(analysis.impacted_modules) if analysis.impacted_modules else 'None'}",
            "",
            "#### Deterministic Risk Factors",
        ]
        for item in sorted(analysis.risk.evidence, key=lambda x: x.weight * x.score, reverse=True):
            lines.append(f"- **{item.name or item.signal}** ({item.category.title()}): {item.description}")
            if item.recommendation:
                lines.append(f"  *Recommendation*: {item.recommendation}")
        return "\n".join(lines)
