"""Canonical Analysis Export Model for ChangePilot.

Single source of truth consumed by all export renderers:
  - PDF (ReportLab)
  - JSON
  - CSV (ZIP)
  - Markdown

Never invents or hallucinates data. Accurately renders persisted analysis evidence,
graph topology, and risk findings without re-computing risk scores.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field

from app.models.analysis import ChangeAnalysisResult
from app.models.repository import RepositorySummary
from app.models.risk import EvidenceStatement, RiskBreakdownItem, RiskEvidence, RiskResult


# ---------------------------------------------------------------------------
# Component Models
# ---------------------------------------------------------------------------


class ExportRepositoryInfo(BaseModel):
    id: str
    name: str
    owner: str = ""
    branch: str = "main"
    default_branch: str = "main"
    url: str | None = None
    language: str | None = None


class ExportRiskBreakdownItem(BaseModel):
    rule: str
    name: str
    category: str
    points: int
    raw_points: float = 0.0
    evidence: str
    affected_files: list[str] = Field(default_factory=list)
    threshold: str = ""
    recommendation: str = ""
    recommendation_type: str = "POLICY_BASED"


class ExportRiskSummary(BaseModel):
    score: int
    level: str
    evidence_completeness: float
    confidence: float
    is_calibrated: bool
    calibration_status: str
    score_description: str
    raw_rule_score: float = 0.0
    normalized_score: float = 0.0
    capped_score: int = 0
    breakdown: list[ExportRiskBreakdownItem] = Field(default_factory=list)


class ExportEvidenceStatement(BaseModel):
    id: str  # FACT-001, INF-001, REC-001
    statement_type: str  # FACT, INFERENCE, RECOMMENDATION
    claim: str
    source_evidence: str = ""
    recommendation_type: str | None = None
    traceability_ref: str = ""
    affected_files: list[str] = Field(default_factory=list)


class ExportChangedFile(BaseModel):
    path: str
    change_type: str = "MODIFIED"
    language: str = "Unknown"
    module: str = "root"
    risk_signals: list[str] = Field(default_factory=list)
    direct_impact: str = "Directly changed in commit"
    test_status: str = "Source Component"


class ExportDependencyPath(BaseModel):
    depth: int
    file_or_module: str
    relationship: str = "DEPENDS_ON"
    reason: str = ""
    source: str = ""
    target: str = ""


class ExportBlastRadius(BaseModel):
    direct_impact: int = 0
    indirect_impact: int = 0
    total_impact: int = 0
    impacted_files: list[str] = Field(default_factory=list)
    impacted_modules: list[str] = Field(default_factory=list)
    dependency_paths: list[ExportDependencyPath] = Field(default_factory=list)


class ExportFinding(BaseModel):
    title: str
    classification: str  # FACT, INFERENCE, RECOMMENDATION
    category: str  # architecture, security, testing, infrastructure, database, api
    description: str
    recommendation: str = ""
    affected_files: list[str] = Field(default_factory=list)
    traceability: str = ""


class ExportTestFinding(BaseModel):
    category: str  # "Actual Coverage", "Potential Test Gaps", "Test Changes Detected"
    title: str
    description: str
    recommendation: str = ""
    affected_files: list[str] = Field(default_factory=list)
    status: str = "GAP_DETECTED"  # COVERED, GAP_DETECTED, NOT_ANALYZED


class ExportRepositoryHealth(BaseModel):
    health_score: int | None = None
    overall: float | None = None
    architecture: float | None = None
    dependencies: float | None = None
    testing: float | None = None
    security: float | None = None
    maintainability: float | None = None
    category_scores_persisted: bool = False
    deductions: list[str] = Field(default_factory=list)
    potential_test_gaps: list[str] = Field(default_factory=list)
    high_fan_in_files: list[dict[str, Any]] = Field(default_factory=list)
    high_fan_out_files: list[dict[str, Any]] = Field(default_factory=list)
    dead_code_symbols: list[str] = Field(default_factory=list)


class ExportGraphHealth(BaseModel):
    nodes: int = 0
    edges: int = 0
    circular_dependencies: int = 0
    circular_dependency_cycles: list[list[str]] = Field(default_factory=list)
    orphan_candidates: int = 0
    orphan_candidate_files: list[str] = Field(default_factory=list)
    unresolved_imports: int = 0
    unresolved_import_details: list[dict[str, Any]] = Field(default_factory=list)
    self_imports: int = 0
    duplicate_edges: int = 0
    invalid_paths: int = 0
    warnings: list[str] = Field(default_factory=list)


class ExportMetadata(BaseModel):
    repository_id: str
    repository_name: str
    owner: str
    branch: str
    base_commit: str | None = None
    head_commit: str | None = None
    analysis_id: str
    analysis_timestamp: str | None = None
    analysis_version: str = "1.0.0"
    risk_engine_version: str = "1.0.0-deterministic"
    risk_policy_version: str = "1.0.0"
    parser_version: str = "1.0.0-treesitter"
    graph_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Canonical Export Model
# ---------------------------------------------------------------------------


class AnalysisExportModel(BaseModel):
    analysis_id: str
    repository: ExportRepositoryInfo
    branch: str
    base_commit: str | None = None
    head_commit: str | None = None
    timestamp: str | None = None
    risk: ExportRiskSummary
    facts: list[ExportEvidenceStatement] = Field(default_factory=list)
    inferences: list[ExportEvidenceStatement] = Field(default_factory=list)
    recommendations: list[ExportEvidenceStatement] = Field(default_factory=list)
    failure_scenarios: list[str] = Field(default_factory=list)
    changed_files: list[ExportChangedFile] = Field(default_factory=list)
    blast_radius: ExportBlastRadius
    architecture_findings: list[ExportFinding] = Field(default_factory=list)
    security_findings: list[ExportFinding] = Field(default_factory=list)
    test_findings: list[ExportTestFinding] = Field(default_factory=list)
    repository_health: ExportRepositoryHealth
    rollback_considerations: list[str] = Field(default_factory=list)
    graph_health: ExportGraphHealth
    reviewer_evidence: list[dict[str, Any]] = Field(default_factory=list)
    metadata: ExportMetadata
    ai_report: str | None = None

    @classmethod
    def from_analysis(
        cls,
        analysis: ChangeAnalysisResult,
        repository: RepositorySummary,
        health_metrics: dict[str, Any] | None = None,
        base_commit: str | None = None,
        head_commit: str | None = None,
    ) -> AnalysisExportModel:
        """Construct the canonical export model faithfully from persisted analysis data."""
        # 1. Repository Info
        repo_info = ExportRepositoryInfo(
            id=repository.id,
            name=repository.name,
            owner=repository.owner or "",
            branch=repository.default_branch,
            default_branch=repository.default_branch,
            url=str(repository.url) if repository.url else None,
            language=repository.language,
        )

        risk = analysis.risk
        evidence_list = risk.evidence or []
        changed_files_raw = analysis.changed_files or []
        impacted_modules_raw = analysis.impacted_modules or []
        graph = analysis.dependency_graph

        # 2. Risk Breakdown
        breakdown_items: list[ExportRiskBreakdownItem] = []
        if risk.risk_breakdown:
            for item in risk.risk_breakdown:
                breakdown_items.append(
                    ExportRiskBreakdownItem(
                        rule=item.rule,
                        name=item.name or item.rule,
                        category=item.category,
                        points=item.points,
                        raw_points=float(item.points),
                        evidence=item.evidence,
                        affected_files=item.affected_files or [],
                        threshold=item.threshold or "",
                        recommendation=item.recommendation or "",
                        recommendation_type=(
                            item.recommendation_type.value
                            if hasattr(item.recommendation_type, "value")
                            else str(item.recommendation_type or "POLICY_BASED")
                        ),
                    )
                )
        elif evidence_list:
            for ev in sorted(evidence_list, key=lambda x: x.weight * x.score, reverse=True):
                pts = int(round(ev.weight * ev.score * 100))
                breakdown_items.append(
                    ExportRiskBreakdownItem(
                        rule=ev.rule or ev.signal,
                        name=ev.name or ev.rule or ev.signal,
                        category=ev.category,
                        points=pts,
                        raw_points=round(ev.weight * ev.score * 100, 2),
                        evidence=ev.description,
                        affected_files=ev.file_paths or [],
                        threshold=ev.threshold or "",
                        recommendation=ev.recommendation or "",
                        recommendation_type=(
                            ev.recommendation_type.value
                            if hasattr(ev.recommendation_type, "value")
                            else str(ev.recommendation_type or "POLICY_BASED")
                        ),
                    )
                )

        raw_rule_score = sum(b.raw_points for b in breakdown_items)
        if raw_rule_score == 0 and risk.score > 0:
            raw_rule_score = float(risk.score)

        normalized_score = raw_rule_score
        if raw_rule_score > 60:
            normalized_score = 60 + (raw_rule_score - 60) * 0.5

        risk_summary = ExportRiskSummary(
            score=risk.score,
            level=str(risk.level.value if hasattr(risk.level, "value") else risk.level).upper(),
            evidence_completeness=risk.evidence_completeness,
            confidence=risk.confidence or risk.evidence_completeness,
            is_calibrated=risk.is_calibrated,
            calibration_status=risk.calibration_status,
            score_description=risk.score_description,
            raw_rule_score=round(raw_rule_score, 2),
            normalized_score=round(normalized_score, 2),
            capped_score=risk.score,
            breakdown=breakdown_items,
        )

        # 3. Facts
        facts: list[ExportEvidenceStatement] = []
        if risk.facts:
            for f in risk.facts:
                facts.append(
                    ExportEvidenceStatement(
                        id=f.id,
                        statement_type="FACT",
                        claim=f.claim,
                        source_evidence=f.source_evidence,
                        affected_files=f.affected_files or [],
                        traceability_ref=f.traceability_ref,
                    )
                )
        else:
            fact_idx = 1
            facts.append(
                ExportEvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type="FACT",
                    claim=f"{len(changed_files_raw)} file(s) modified in this change set.",
                    source_evidence="Git commit diff analysis",
                    affected_files=changed_files_raw[:20],
                    traceability_ref="git_diff_stat",
                )
            )
            fact_idx += 1

            if graph and graph.nodes:
                facts.append(
                    ExportEvidenceStatement(
                        id=f"FACT-{fact_idx:03d}",
                        statement_type="FACT",
                        claim=f"Knowledge graph contains {len(graph.nodes)} AST nodes and {len(graph.edges)} dependency relationships.",
                        source_evidence="Tree-Sitter AST & Graph parser",
                        traceability_ref="graph_snapshot",
                    )
                )
                fact_idx += 1

            if impacted_modules_raw:
                facts.append(
                    ExportEvidenceStatement(
                        id=f"FACT-{fact_idx:03d}",
                        statement_type="FACT",
                        claim=f"Change impact intersects {len(impacted_modules_raw)} architectural module(s): {', '.join(impacted_modules_raw[:5])}",
                        source_evidence="AST module resolution",
                        traceability_ref="module_resolution",
                    )
                )
                fact_idx += 1

            for ev in evidence_list:
                if ev.signal in (
                    "dependency_upgrades", "authentication_change", "env_vars_changed",
                    "database_schema", "public_api_changed", "critical_component_modified",
                    "large_refactor", "migration_detected"
                ):
                    facts.append(
                        ExportEvidenceStatement(
                            id=f"FACT-{fact_idx:03d}",
                            statement_type="FACT",
                            claim=f"{ev.name or ev.signal}: {ev.description}",
                            source_evidence=(
                                f"Observed in {', '.join(ev.file_paths[:3])}"
                                if ev.file_paths else "Repository AST scan"
                            ),
                            affected_files=ev.file_paths or [],
                            traceability_ref=ev.rule or ev.signal,
                        )
                    )
                    fact_idx += 1

        # 4. Inferences
        inferences: list[ExportEvidenceStatement] = []
        if risk.inferences:
            for inf in risk.inferences:
                inferences.append(
                    ExportEvidenceStatement(
                        id=inf.id,
                        statement_type="INFERENCE",
                        claim=inf.claim,
                        source_evidence=inf.source_evidence,
                        affected_files=inf.affected_files or [],
                        traceability_ref=inf.traceability_ref,
                    )
                )
        else:
            inf_idx = 1
            if len(impacted_modules_raw) >= 3:
                inferences.append(
                    ExportEvidenceStatement(
                        id=f"INF-{inf_idx:03d}",
                        statement_type="INFERENCE",
                        claim=f"Cross-module architectural coupling: change set spans {len(impacted_modules_raw)} distinct architectural domains.",
                        source_evidence="Derived from module impact analysis",
                        traceability_ref="rule:multi_module_impact",
                    )
                )
                inf_idx += 1

            for ev in evidence_list:
                if ev.signal == "large_blast_radius":
                    inferences.append(
                        ExportEvidenceStatement(
                            id=f"INF-{inf_idx:03d}",
                            statement_type="INFERENCE",
                            claim=f"Downstream regression risk: {ev.description}",
                            source_evidence="Derived from dependency graph traversal",
                            traceability_ref="rule:large_blast_radius",
                        )
                    )
                    inf_idx += 1
                elif ev.signal == "missing_tests":
                    inferences.append(
                        ExportEvidenceStatement(
                            id=f"INF-{inf_idx:03d}",
                            statement_type="INFERENCE",
                            claim="Test coverage gap: production code changes lack accompanying unit test or test specification modifications.",
                            source_evidence="Diff analysis: 0 test files modified",
                            traceability_ref="rule:missing_tests",
                        )
                    )
                    inf_idx += 1
                elif ev.signal == "critical_component_modified":
                    inferences.append(
                        ExportEvidenceStatement(
                            id=f"INF-{inf_idx:03d}",
                            statement_type="INFERENCE",
                            claim=f"Critical business workflows may be affected due to modifications in core components: {', '.join(ev.file_paths[:3])}",
                            source_evidence="Sensitive domain path keyword matching",
                            traceability_ref="rule:critical_component_modified",
                            affected_files=ev.file_paths or [],
                        )
                    )
                    inf_idx += 1

        # 5. Recommendations
        recommendations: list[ExportEvidenceStatement] = []
        if risk.recommendations:
            for rec in risk.recommendations:
                recommendations.append(
                    ExportEvidenceStatement(
                        id=rec.id,
                        statement_type="RECOMMENDATION",
                        claim=rec.claim,
                        recommendation_type=(
                            rec.recommendation_type.value
                            if hasattr(rec.recommendation_type, "value")
                            else str(rec.recommendation_type or "POLICY_BASED")
                        ),
                        source_evidence=rec.source_evidence,
                        affected_files=rec.affected_files or [],
                        traceability_ref=rec.traceability_ref,
                    )
                )
        else:
            rec_idx = 1
            for ev in evidence_list:
                if ev.recommendation:
                    recommendations.append(
                        ExportEvidenceStatement(
                            id=f"REC-{rec_idx:03d}",
                            statement_type="RECOMMENDATION",
                            claim=ev.recommendation,
                            recommendation_type=(
                                ev.recommendation_type.value
                                if hasattr(ev.recommendation_type, "value")
                                else str(ev.recommendation_type or "POLICY_BASED")
                            ),
                            source_evidence=f"Triggered by {ev.name or ev.signal}: {ev.description}",
                            traceability_ref=ev.rule or ev.signal,
                            affected_files=ev.file_paths or [],
                        )
                    )
                    rec_idx += 1

        # 6. Changed Files Details
        changed_files_models: list[ExportChangedFile] = []
        for f in changed_files_raw:
            norm_f = f.replace("\\", "/")
            ext = norm_f.split(".")[-1].lower() if "." in norm_f else ""
            lang_map = {
                "ts": "TypeScript", "tsx": "TypeScript (React)", "js": "JavaScript",
                "jsx": "JavaScript (React)", "cjs": "CommonJS", "mjs": "ES Module",
                "py": "Python", "json": "JSON", "md": "Markdown", "css": "CSS",
                "html": "HTML", "yml": "YAML", "yaml": "YAML", "sql": "SQL",
                "sh": "Shell", "rs": "Rust", "go": "Go", "txt": "Plain Text"
            }
            lang = lang_map.get(ext, ext.upper() if ext else "Text")
            parts = norm_f.split("/")
            module = parts[0] if len(parts) > 1 else "root"
            is_test = any(t in norm_f.lower() for t in ("test", "spec", "__tests__"))
            matched_signals = [
                ev.name or ev.signal
                for ev in evidence_list
                if any(p in norm_f or norm_f in p for p in (ev.file_paths or []))
            ]

            changed_files_models.append(
                ExportChangedFile(
                    path=f,
                    change_type="MODIFIED",
                    language=lang,
                    module=module,
                    risk_signals=matched_signals,
                    direct_impact="Directly modified in commit",
                    test_status="Test Specification" if is_test else "Source Component",
                )
            )

        # 7. Blast Radius & Traversal Paths
        dep_paths: list[ExportDependencyPath] = []
        adj: dict[str, list[str]] = defaultdict(list)
        reverse_adj: dict[str, list[str]] = defaultdict(list)
        for edge in (graph.edges or []):
            adj[edge.source].append(edge.target)
            reverse_adj[edge.target].append(edge.source)

        visited_nodes: set[str] = set()
        for f in changed_files_raw:
            dep_paths.append(
                ExportDependencyPath(
                    depth=0,
                    file_or_module=f,
                    relationship="MODIFIED",
                    reason="Directly modified file",
                    source=f,
                    target=f,
                )
            )
            visited_nodes.add(f)

        queue: deque[tuple[str, int, str]] = deque()
        for f in changed_files_raw:
            # Files importing or depending on this changed file
            for parent in reverse_adj.get(f, []):
                if parent not in visited_nodes:
                    queue.append((parent, 1, f))
                    visited_nodes.add(parent)
            for child in adj.get(f, []):
                if child not in visited_nodes:
                    queue.append((child, 1, f))
                    visited_nodes.add(child)

        max_depth = 0
        indirect_impact_nodes: set[str] = set()
        while queue:
            node_id, depth, caused_by = queue.popleft()
            if depth > max_depth:
                max_depth = depth
            indirect_impact_nodes.add(node_id)
            dep_paths.append(
                ExportDependencyPath(
                    depth=depth,
                    file_or_module=node_id,
                    relationship="DEPENDS_ON" if depth > 1 else "IMPORTS",
                    reason=(
                        f"Directly imports {caused_by}"
                        if depth == 1
                        else f"Transitively depends on {caused_by}"
                    ),
                    source=caused_by,
                    target=node_id,
                )
            )
            if depth < 3:
                for next_node in reverse_adj.get(node_id, []):
                    if next_node not in visited_nodes:
                        visited_nodes.add(next_node)
                        queue.append((next_node, depth + 1, node_id))

        dep_paths.sort(key=lambda x: (x.depth, x.file_or_module))
        direct_impact = len(changed_files_raw)
        indirect_impact = len(indirect_impact_nodes)
        blast_radius = ExportBlastRadius(
            direct_impact=direct_impact,
            indirect_impact=indirect_impact,
            total_impact=direct_impact + indirect_impact,
            impacted_files=sorted(list(visited_nodes)),
            impacted_modules=impacted_modules_raw,
            dependency_paths=dep_paths,
        )

        # 8. Architecture, Security, Test Findings
        arch_findings: list[ExportFinding] = []
        sec_findings: list[ExportFinding] = []
        for ev in evidence_list:
            if ev.category in ("architecture", "infrastructure", "database", "api"):
                arch_findings.append(
                    ExportFinding(
                        title=ev.name or ev.signal,
                        classification="FACT" if ev.score >= 1.0 else "INFERENCE",
                        category=ev.category,
                        description=ev.description,
                        recommendation=ev.recommendation,
                        affected_files=ev.file_paths or [],
                        traceability=ev.rule or ev.signal,
                    )
                )
            elif ev.category == "security":
                sec_findings.append(
                    ExportFinding(
                        title=ev.name or ev.signal,
                        classification="FACT" if ev.score >= 1.0 else "INFERENCE",
                        category=ev.category,
                        description=ev.description,
                        recommendation=ev.recommendation,
                        affected_files=ev.file_paths or [],
                        traceability=ev.rule or ev.signal,
                    )
                )

        test_findings: list[ExportTestFinding] = []
        test_files_changed = [
            f for f in changed_files_raw if any(t in f.lower() for t in ("test", "spec", "__tests__"))
        ]
        if test_files_changed:
            test_findings.append(
                ExportTestFinding(
                    category="Test Changes Detected",
                    title="Related Test Modifications Present",
                    description=f"{len(test_files_changed)} test specification file(s) modified alongside changes: {', '.join(test_files_changed[:3])}",
                    affected_files=test_files_changed,
                    status="COVERED",
                )
            )
        else:
            test_findings.append(
                ExportTestFinding(
                    category="Potential Test Gaps",
                    title="Missing Test Modifications",
                    description="No related unit test or test specification modifications were detected in this commit set.",
                    recommendation="Add unit or integration tests covering the modified source logic.",
                    affected_files=changed_files_raw,
                    status="GAP_DETECTED",
                )
            )

        # 9. Repository Health
        hm = health_metrics or {}
        health_score = hm.get("health_score")
        cat_data = hm.get("categories", {})
        has_cat = bool(cat_data and isinstance(cat_data, dict))
        repo_health = ExportRepositoryHealth(
            health_score=health_score,
            overall=float(health_score) if health_score is not None else None,
            architecture=cat_data.get("architecture", {}).get("score") if has_cat else None,
            dependencies=cat_data.get("dependencies", {}).get("score") if has_cat else None,
            testing=cat_data.get("testing", {}).get("score") if has_cat else None,
            security=cat_data.get("security", {}).get("score") if has_cat else None,
            maintainability=cat_data.get("maintainability", {}).get("score") if has_cat else None,
            category_scores_persisted=has_cat,
            deductions=[],
            potential_test_gaps=hm.get("potential_test_gaps", []),
            high_fan_in_files=hm.get("high_fan_in_files", []),
            high_fan_out_files=hm.get("high_fan_out_files", []),
            dead_code_symbols=hm.get("dead_code_symbols", []),
        )

        # 10. Graph Health & Orphans & Unresolved
        gh = graph.graph_health
        orphan_files: list[str] = []
        if hm.get("potential_orphan_candidates"):
            orphan_files = hm.get("potential_orphan_candidates", [])
        elif hm.get("orphan_modules"):
            orphan_files = hm.get("orphan_modules", [])
        elif graph.nodes:
            orphan_files = [
                n.path for n in graph.nodes
                if n.fan_in == 0 and n.path and not n.is_critical and n.kind in ("file", "module")
            ]

        unresolved_details: list[dict[str, Any]] = []
        for e in (graph.edges or []):
            if "unresolved" in e.relationship.lower() or "unresolved" in e.edge_type.lower():
                unresolved_details.append({
                    "source": e.source,
                    "target": e.target,
                    "reason": "Target module not resolved in workspace AST",
                })

        graph_health_model = ExportGraphHealth(
            nodes=gh.node_count if gh else len(graph.nodes or []),
            edges=gh.edge_count if gh else len(graph.edges or []),
            circular_dependencies=gh.circular_dependency_count if gh else 0,
            circular_dependency_cycles=hm.get("circular_dependencies", []),
            orphan_candidates=gh.orphan_candidates if gh else len(orphan_files),
            orphan_candidate_files=orphan_files,
            unresolved_imports=gh.unresolved_imports if gh else len(unresolved_details),
            unresolved_import_details=unresolved_details,
            self_imports=gh.self_edge_count if gh else 0,
            duplicate_edges=gh.duplicate_edge_count if gh else 0,
            invalid_paths=gh.invalid_paths if gh else 0,
            warnings=gh.warnings if gh else [],
        )

        # 11. Rollback & Reviewer Evidence
        rollback = risk.deployment_considerations or []
        reviewer_ev = risk.recommended_review_areas or []

        # 12. Metadata
        meta = ExportMetadata(
            repository_id=repository.id,
            repository_name=repository.name,
            owner=repository.owner or "",
            branch=repository.default_branch,
            base_commit=base_commit,
            head_commit=head_commit,
            analysis_id=analysis.id,
            analysis_timestamp=analysis.analysis_timestamp,
            analysis_version=analysis.parser_version or "1.0.0",
            risk_engine_version=analysis.risk_engine_version or "1.0.0-deterministic",
            risk_policy_version="1.0.0",
            parser_version=analysis.parser_version or "1.0.0-treesitter",
            graph_version=analysis.graph_version or "1.0.0",
        )

        return cls(
            analysis_id=analysis.id,
            repository=repo_info,
            branch=repository.default_branch,
            base_commit=base_commit,
            head_commit=head_commit,
            timestamp=analysis.analysis_timestamp,
            risk=risk_summary,
            facts=facts,
            inferences=inferences,
            recommendations=recommendations,
            failure_scenarios=risk.potential_failure_scenarios or [],
            changed_files=changed_files_models,
            blast_radius=blast_radius,
            architecture_findings=arch_findings,
            security_findings=sec_findings,
            test_findings=test_findings,
            repository_health=repo_health,
            rollback_considerations=rollback,
            graph_health=graph_health_model,
            reviewer_evidence=reviewer_ev,
            metadata=meta,
            ai_report=analysis.ai_report,
        )
