"""Async Background Analysis Worker Pipeline for ChangePilot.

Executes analysis tasks out of the HTTP request loop:
1. PENDING -> Updates job status
2. CLONING -> Clones/fetches repo via GitCLIManager
3. PARSING -> Multi-Language AST Code Parser with fail-closed error detection
4. BUILDING_GRAPH -> Constructs Knowledge Graph, Android manifest entrypoints, stores DB snapshot
5. SCORING -> Evaluates deterministic risk score, fail-closed quality gate & blast radius
6. AI_REPORT -> Asynchronously generates AI explanation report
7. COMPLETED -> Saves final validated result to PostgreSQL
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analysis.module_detector import ModuleDetector
from app.analysis.quality_gate import AnalysisQualityGate
from app.analysis.tree_sitter_parser import (
    ImportSymbol,
    ParsedFileAST,
    TreeSitterCodeParser,
    is_generated_or_vendor,
)
from app.database.tables import AnalysisJobRow, AnalysisRow, FileASTCacheRow, RepoKnowledgeGraphRow
from app.graph.knowledge_graph import KnowledgeGraphBuilder
from app.graph.neo4j_engine import Neo4jGraphEngine
from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger
from app.models.risk import RiskInput
from app.providers.registry import AIProviderRegistry
from app.repositories.analysis_repo import AnalysisRepository
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
                job.step = (step or "")[:250]
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
        user_id: str | None = None,
        is_ephemeral: bool = False,
    ) -> None:
        try:
            # Step 1: CLONING
            await self.update_job(job_id, "CLONING", "Fetching repository via Git CLI...", 15)
            await self._git_cli.ensure_bare_repo(owner, repo_name, clone_url, token)
            worktree_dir = await self._git_cli.checkout_worktree(owner, repo_name, head_ref, clone_url, token)

            # Step 2: DIFF
            diff_result = await self._git_cli.get_commit_diff(owner, repo_name, base_ref, head_ref, clone_url, token)
            changed_files = diff_result.changed_files or ["README.md"]

            # Step 3: INVENTORY & PARSING (with fail-closed quality tracking)
            await self.update_job(job_id, "PARSING", "Parsing multi-language source AST with Tree-Sitter...", 40)
            parsed_files: list[ParsedFileAST] = []
            files_discovered = 0
            supported_source_files = 0
            files_parsed = 0
            files_failed = 0
            detected_languages: set[str] = set()

            manifest_content: bytes | None = None
            settings_gradle_content = ""

            SUPPORTED_SOURCE_EXTS = {
                ".kt", ".kts", ".java", ".ts", ".tsx", ".js", ".jsx",
                ".py", ".rs", ".go", ".c", ".cpp", ".cs"
            }

            async with self._session_factory() as session:
                for file_path in worktree_dir.rglob("*"):
                    if not file_path.is_file():
                        continue

                    files_discovered += 1
                    rel_path = file_path.relative_to(worktree_dir).as_posix()
                    ext = Path(rel_path).suffix.lower()
                    basename = Path(rel_path).name.lower()

                    if basename == "androidmanifest.xml" and not manifest_content:
                        try:
                            manifest_content = file_path.read_bytes()
                        except Exception:
                            pass

                    if basename in ("settings.gradle", "settings.gradle.kts") and not settings_gradle_content:
                        try:
                            settings_gradle_content = file_path.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass

                    if is_generated_or_vendor(rel_path):
                        continue

                    if ext in SUPPORTED_SOURCE_EXTS:
                        supported_source_files += 1

                    lang = self._parser.detect_language(rel_path)
                    if lang and lang not in ("config", "text"):
                        detected_languages.add(lang)

                    if lang:
                        try:
                            content = file_path.read_bytes()
                            file_hash = self._parser.compute_file_hash(content)

                            # Check AST cache (ensure cached language matches expected parser)
                            cached = await session.get(FileASTCacheRow, file_hash)
                            if cached and cached.language not in ("text", "generic") and cached.parsed_ast:
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
                            else:
                                parsed = self._parser.parse_file(rel_path, content)
                                if parsed.parse_status == "FAILED":
                                    files_failed += 1
                                    logger.error("[PARSER-FAIL] file=%s lang=%s errors=%s", rel_path, parsed.language, parsed.parse_errors)
                                else:
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

                            if parsed.defined_classes or parsed.defined_functions or parsed.imports or len(content.strip()) <= 20:
                                files_parsed += 1
                            parsed_files.append(parsed)

                        except Exception as exc:
                            files_failed += 1
                            logger.error("[PARSER-EXCEPTION] file=%s error=%s", rel_path, exc)

                await session.commit()

            # Step 4: BUILDING_GRAPH
            await self.update_job(job_id, "BUILDING_GRAPH", "Building Repository Knowledge Graph...", 65)
            graph, graph_hash, health_metrics = self._graph_builder.build_graph_from_parsed_files(
                parsed_files, manifest_content=manifest_content
            )

            # Step 5: ANALYSIS QUALITY GATE (Fail-Closed Enforcement)
            quality_gate = AnalysisQualityGate.evaluate(
                files_discovered=files_discovered,
                supported_source_files=supported_source_files,
                files_parsed=files_parsed,
                files_failed=files_failed,
                ast_nodes=len(graph.nodes),
                dependency_edges=len(graph.edges),
                has_git_diff=True,
                has_test_analysis=True,
            )

            # Extract genuine application modules (excluding .idea, gradle, assets)
            gradle_modules = ModuleDetector.detect_gradle_modules(settings_gradle_content) if settings_gradle_content else []
            impacted_modules = ModuleDetector.extract_impacted_modules(changed_files, declared_modules=gradle_modules)
            if not impacted_modules:
                impacted_modules = ["root"]

            # Store Knowledge Graph in DB with fail-closed semantics
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

                categories_dict = {}
                if hasattr(health_metrics, "categories") and health_metrics.categories:
                    for cat_name, cat_obj in health_metrics.categories.items():
                        if hasattr(cat_obj, "__dict__"):
                            categories_dict[cat_name] = {
                                "category": getattr(cat_obj, "category", cat_name),
                                "score": getattr(cat_obj, "score", 100) if quality_gate.health_status != "UNAVAILABLE" else None,
                                "deductions": getattr(cat_obj, "deductions", 0),
                                "evidence": getattr(cat_obj, "evidence", []),
                                "recommendations": getattr(cat_obj, "recommendations", []),
                            }
                        elif isinstance(cat_obj, dict):
                            categories_dict[cat_name] = cat_obj

                # Fail-closed health dictionary: do NOT substitute 0 findings when parsing failed
                health_dict = {
                    "status": quality_gate.health_status,
                    "health_score": health_metrics.health_score if quality_gate.health_status != "UNAVAILABLE" else None,
                    "total_files": health_metrics.total_files,
                    "total_classes": health_metrics.total_classes,
                    "total_functions": health_metrics.total_functions,
                    "total_dependencies": health_metrics.total_dependencies,
                    "circular_dependencies": health_metrics.circular_dependencies if quality_gate.health_status != "UNAVAILABLE" else None,
                    "orphan_modules": orphan_list if quality_gate.health_status != "UNAVAILABLE" else None,
                    "potential_orphan_candidates": orphan_list if quality_gate.health_status != "UNAVAILABLE" else None,
                    "total_source_modules": getattr(health_metrics, "total_source_modules", len(orphan_list)),
                    "orphan_candidate_details": getattr(health_metrics, "orphan_candidate_details", []),
                    "dead_code_symbols": health_metrics.dead_code_symbols if quality_gate.health_status != "UNAVAILABLE" else None,
                    "god_classes": health_metrics.god_classes if quality_gate.health_status != "UNAVAILABLE" else None,
                    "high_fan_out_files": health_metrics.high_fan_out_files,
                    "high_fan_in_files": health_metrics.high_fan_in_files,
                    "test_coverage_gaps": gap_list,
                    "potential_test_gaps": gap_list,
                    "architectural_violations": health_metrics.architectural_violations,
                    "categories": categories_dict,
                    "coverage_notice": getattr(health_metrics, "coverage_notice", "Coverage data unavailable; test gap inferred from repository structure."),
                    "analysis_quality": quality_gate.analysis_quality,
                    "quality_gate": {
                        "analysis_quality": quality_gate.analysis_quality,
                        "graph_status": quality_gate.graph_status,
                        "evidence_completeness": quality_gate.evidence_completeness,
                        "health_status": quality_gate.health_status,
                        "parser_health": quality_gate.parser_health,
                        "diff_status": quality_gate.diff_status,
                        "inventory_status": quality_gate.inventory_status,
                        "blast_radius_status": quality_gate.blast_radius_status,
                        "test_analysis_status": quality_gate.test_analysis_status,
                        "coverage_status": quality_gate.coverage_status,
                        "warnings": quality_gate.warnings,
                        "explanation": quality_gate.explanation,
                    },
                }

                if existing_kg:
                    existing_kg.commit_sha = head_ref
                    existing_kg.graph_hash = graph_hash
                    existing_kg.nodes = [n.model_dump() for n in graph.nodes]
                    existing_kg.edges = [e.model_dump() for e in graph.edges]
                    existing_kg.health_metrics = health_dict
                    if user_id:
                        existing_kg.user_id = user_id
                        existing_kg.is_ephemeral = is_ephemeral
                else:
                    kg_row = RepoKnowledgeGraphRow(
                        repository_id=repository_id,
                        commit_sha=head_ref,
                        graph_hash=graph_hash,
                        nodes=[n.model_dump() for n in graph.nodes],
                        edges=[e.model_dump() for e in graph.edges],
                        health_metrics=health_dict,
                        user_id=user_id,
                        is_ephemeral=is_ephemeral,
                    )
                    session.add(kg_row)
                await session.commit()

            # Sync Neo4j index & calculate Blast Radius
            await self._neo4j.sync_graph(repository_id, graph)
            blast_radius = await self._neo4j.calculate_blast_radius(repository_id, changed_files, graph=graph)

            # Step 6: SCORING (Deterministic Phase)
            await self.update_job(job_id, "SCORING", "Computing deterministic risk score...", 85)
            critical_modules = [
                f for f in changed_files
                if any(m in f.lower() for m in ("auth", "db", "session", "payment", "security"))
            ]

            risk_result = self._risk_engine.score(
                RiskInput(
                    changed_files=changed_files,
                    impacted_modules=impacted_modules,
                    dependency_count=blast_radius.transitive_dependency_count,
                    missing_tests=not any("test" in f.lower() or "spec" in f.lower() for f in changed_files),
                    large_refactor=len(changed_files) >= 15,
                    critical_modules=critical_modules,
                    hub_nodes_affected=getattr(blast_radius, "hub_nodes", []),
                    bridge_nodes_affected=getattr(blast_radius, "bridge_nodes", []),
                    affected_functions=getattr(blast_radius, "affected_functions", []),
                    blast_radius_size=getattr(blast_radius, "total_impact_size", 0),
                    blast_radius_depth=getattr(blast_radius, "max_depth_reached", 0),
                )
            )

            # Apply Quality Gate Completeness & Confidence
            risk_result.evidence_completeness = quality_gate.evidence_completeness
            risk_result.confidence = quality_gate.evidence_completeness
            if quality_gate.analysis_quality != "FULL":
                risk_result.score_description = (
                    f"Risk score: {risk_result.score}/100 ({risk_result.level.value.upper()}) · "
                    f"Analysis Quality: {quality_gate.analysis_quality} ({int(round(quality_gate.evidence_completeness * 100))}% evidence completeness) — {quality_gate.explanation}"
                )

            # Create Analysis Record
            analysis_result_obj = ChangeAnalysisResult(
                id=str(uuid.uuid4()),
                repository_id=repository_id,
                trigger=AnalysisTrigger.COMMIT_COMPARISON,
                risk=risk_result,
                changed_files=changed_files,
                impacted_modules=impacted_modules,
                dependency_graph=graph,
            )

            async with self._session_factory() as session:
                analysis_repo = AnalysisRepository(session)
                saved_analysis = await analysis_repo.save(
                    analysis_result_obj, user_id=user_id, is_ephemeral=is_ephemeral
                )
                analysis_id = saved_analysis.id

            # Step 7: AI REPORT GENERATION (Asynchronous & Resilient)
            ai_report_text = None
            try:
                if ai_provider_registry is None:
                    async with self._session_factory() as session:
                        config_repo = AIProviderConfigRepository(session)
                        ai_provider_registry = AIProviderRegistry()
                        configs = await config_repo.list_active()
                        for cfg in configs:
                            ai_provider_registry.register_config(cfg)

                report_service = AIReportService(ai_provider_registry)
                analysis_result_obj.id = analysis_id
                ai_report_text = await report_service.generate_report(analysis_result_obj)

                if ai_report_text:
                    async with self._session_factory() as session:
                        a_row = await session.get(AnalysisRow, analysis_id)
                        if a_row:
                            a_row.ai_report = ai_report_text
                            await session.commit()
            except Exception as report_err:
                logger.warning("AI Report generation notice: %s", report_err)

            # Step 8: COMPLETE JOB
            await self.update_job(job_id, "COMPLETED", "Analysis completed successfully.", 100, analysis_id=analysis_id)

            # Pipeline Telemetry Log
            logger.info(
                "[PIPELINE-TRACE] repo=%s analysis=%s langs=%s files_discovered=%d supported_source=%d parsed=%d failed=%d ast_nodes=%d edges=%d graph_status=%s quality=%s completeness=%.2f health_status=%s impacted_modules=%s",
                repository_id,
                analysis_id,
                list(detected_languages),
                files_discovered,
                supported_source_files,
                files_parsed,
                files_failed,
                len(graph.nodes),
                len(graph.edges),
                quality_gate.graph_status,
                quality_gate.analysis_quality,
                quality_gate.evidence_completeness,
                quality_gate.health_status,
                impacted_modules,
            )

        except Exception as exc:
            logger.exception("Analysis worker failed for job %s: %s", job_id, exc)
            await self.update_job(job_id, "FAILED", f"Pipeline failure: {exc}", 100, error=str(exc))
            raise
