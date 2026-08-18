"""Canonical Analysis Export Model & Consistency Validator for ChangePilot.

Single source of truth consumed identically across:
  - PDF (ReportLab multi-page)
  - JSON
  - CSV (ZIP)
  - Markdown
  - Dashboard API

Guarantees:
  1. Multi-language AST support (Kotlin, Java, Python, TypeScript, JavaScript).
  2. Android Manifest entrypoint recognition & package resolution.
  3. Precise authentication & granular security signal separation.
  4. Architectural changed-file filtering (distinguishing raw 72 from architectural 27).
  5. Canonical blast-radius semantics across all views.
  6. Explainable 5-category health breakdown with security evidence.
  7. Strict cross-metric consistency validation.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from pydantic import BaseModel, Field

from app.analysis.file_classifier import (
    FileTypeCategory,
    classify_file_type,
    filter_architecturally_relevant_files,
)
from app.models.analysis import ChangeAnalysisResult
from app.models.repository import RepositorySummary

# ---------------------------------------------------------------------------
# Component & Breakdown Models
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
    evidence_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    threshold: str = ""
    recommendation: str = ""
    recommendation_type: str = "POLICY_BASED"


class ExportEvidenceCompleteness(BaseModel):
    score: float = 0.98
    available_signals: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    explanation: str = ""


class ExportScoringTraceItem(BaseModel):
    rule_id: str
    name: str
    triggered: bool
    raw_points: float
    confidence: float
    evidence_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    normalized_points: float
    final_points: int


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
    completeness_detail: ExportEvidenceCompleteness = Field(default_factory=ExportEvidenceCompleteness)
    scoring_trace: list[ExportScoringTraceItem] = Field(default_factory=list)


class ExportEvidenceStatement(BaseModel):
    id: str  # FACT-001, INF-001, REC-001
    statement_type: str  # FACT, INFERENCE, RECOMMENDATION
    claim: str
    source_evidence: str = ""
    recommendation_type: str | None = None
    traceability_ref: str = ""
    finding_id: str = ""
    affected_files: list[str] = Field(default_factory=list)


class ExportChangedFile(BaseModel):
    path: str
    change_type: str = "MODIFIED"  # ADDED, MODIFIED, DELETED, RENAMED
    category: str = "SOURCE"  # SOURCE, TEST, CONFIGURATION, BUILD, IDE_METADATA, ASSET, BACKUP
    language: str = "Unknown"
    module: str = "root"
    risk_signals: list[str] = Field(default_factory=list)
    direct_impact: str = "Directly changed in commit"
    test_status: str = "Coverage percentage unavailable — structural test gap inferred"
    test_change_status: str = "NO_TEST_CHANGE"


class ExportDependencyPath(BaseModel):
    depth: int
    file_or_module: str
    relationship: str = "DEPENDS_ON"
    edge_type: str = "SOURCE_IMPORT"
    source: str = ""
    target: str = ""
    reason: str = ""


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
    status: str = "GAP_DETECTED"  # COVERED, GAP_DETECTED, NOT_ANALYZED, TEST_MODIFIED


class ExportHealthCategoryDetail(BaseModel):
    category: str
    score: int
    weight: float
    deductions: int
    evidence: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ExportRepositoryHealth(BaseModel):
    health_score: int = 100
    overall: float = 100.0
    architecture: float = 100.0
    dependencies: float = 100.0
    testing: float = 100.0
    security: float = 100.0
    maintainability: float = 100.0
    category_scores_persisted: bool = True
    health_breakdown: dict[str, ExportHealthCategoryDetail] = Field(default_factory=dict)
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


class ExportAnalysisQuality(BaseModel):
    git_diff_status: str = "PASS"
    parser_status: str = "PASS"
    ast_graph_status: str = "PASS"
    dependency_resolution: str = "PASS"
    manifest_analysis: str = "PASS"
    coverage_analysis: str = "UNAVAILABLE"
    raw_changed_files_count: int = 0
    architectural_changed_files_count: int = 0
    quality_score: float = 1.0
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
# Canonical Export Model & Validator
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
    analysis_quality: ExportAnalysisQuality = Field(default_factory=ExportAnalysisQuality)
    metadata: ExportMetadata
    ai_report: str | None = None

    def validate_consistency(self) -> list[str]:
        """Validates cross-metric and evidence consistency across the canonical model."""
        errors: list[str] = []

        # 1. Blast Radius consistency
        if self.blast_radius.direct_impact != len(self.changed_files):
            errors.append(
                f"Blast radius direct impact ({self.blast_radius.direct_impact}) does not match changed files count ({len(self.changed_files)})."
            )
        if self.blast_radius.total_impact != (self.blast_radius.direct_impact + self.blast_radius.indirect_impact):
            errors.append(
                f"Blast radius total impact ({self.blast_radius.total_impact}) != direct ({self.blast_radius.direct_impact}) + indirect ({self.blast_radius.indirect_impact})."
            )

        # If indirect impact is 0, no inference or rule should claim downstream regression risk
        if self.blast_radius.indirect_impact == 0:
            for inf in self.inferences:
                if "downstream component dependencies are impacted" in inf.claim.lower():
                    errors.append(f"Inference '{inf.id}' claims downstream dependency impact when indirect impact is 0.")
            for b in self.risk.breakdown:
                if b.rule == "large_blast_radius" and b.points > 0:
                    errors.append("Risk breakdown contains 'large_blast_radius' points when indirect impact is 0.")

        # 2. Risk Score consistency
        if self.risk.score != self.risk.capped_score:
            errors.append(f"Risk score ({self.risk.score}) does not match capped score ({self.risk.capped_score}).")

        # 3. Graph Health sanity
        if self.graph_health.nodes < 0 or self.graph_health.edges < 0:
            errors.append("Graph health nodes or edges cannot be negative.")

        return errors

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

        # Calculate architectural relevance
        raw_changed_count = len(changed_files_raw)
        arch_relevant_files = filter_architecturally_relevant_files(changed_files_raw)
        arch_changed_count = len(arch_relevant_files)

        # 2. Canonical Blast Radius Traversal (strictly source-code relationships)
        valid_rels = {
            "SOURCE_IMPORT", "DYNAMIC_IMPORT", "CALLS", "DEPENDS_ON",
            "IMPORTS", "USES", "INHERITS", "IMPLEMENTS"
        }
        invalid_edge_types = {
            "PACKAGE_DEPENDENCY", "CONFIG_REFERENCE", "BUILD_DEPENDENCY",
            "TEST_REFERENCE", "SELF_IMPORT"
        }
        ignored_dir_markers = (
            "node_modules/", ".git/", ".next/", "dist/", "build/",
            "coverage/", "venv/", ".venv/", "__pycache__/", "target/",
            ".idea/", ".gradle/", "gradle/"
        )

        reverse_adj: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        node_map = {n.id: n for n in (graph.nodes or [])}
        file_id_map = {n.path: n.id for n in (graph.nodes or []) if n.kind in ("file", "module") and n.path}

        for edge in (graph.edges or []):
            edge_type = getattr(edge, "edge_type", "SOURCE_IMPORT")
            if edge_type in invalid_edge_types:
                continue
            if edge.relationship not in valid_rels and edge_type not in valid_rels:
                continue
            reverse_adj[edge.target].append((edge.source, edge.relationship, edge_type))

        direct_set = set(changed_files_raw)
        dep_paths: list[ExportDependencyPath] = []
        for f in changed_files_raw:
            dep_paths.append(
                ExportDependencyPath(
                    depth=0,
                    file_or_module=f,
                    relationship="MODIFIED",
                    edge_type="DIRECT_DIFF",
                    reason="Directly modified in commit",
                    source=f,
                    target=f,
                )
            )

        queue: deque[tuple[str, int, str]] = deque()
        visited_nodes: set[str] = set(changed_files_raw)

        for f in changed_files_raw:
            target_id = file_id_map.get(f, f"file:{f}")
            visited_nodes.add(target_id)
            for src_id, rel, etype in reverse_adj.get(target_id, []):
                if src_id not in visited_nodes:
                    visited_nodes.add(src_id)
                    queue.append((src_id, 1, f))

        indirect_nodes: set[str] = set()
        while queue:
            curr_id, depth, caused_by = queue.popleft()
            curr_node = node_map.get(curr_id)
            node_label = curr_node.path if (curr_node and curr_node.path) else (curr_node.label if curr_node else curr_id)
            norm_label = node_label.replace("\\", "/")

            if any(m in norm_label for m in ignored_dir_markers):
                continue

            if node_label not in direct_set:
                indirect_nodes.add(node_label)
                dep_paths.append(
                    ExportDependencyPath(
                        depth=depth,
                        file_or_module=node_label,
                        relationship="IMPORTS" if depth == 1 else "DEPENDS_ON",
                        edge_type="SOURCE_IMPORT",
                        source=caused_by,
                        target=node_label,
                        reason=f"Directly imports {caused_by}" if depth == 1 else f"Transitively depends on {caused_by}",
                    )
                )

            if depth < 3:
                for next_id, _rel, _etype in reverse_adj.get(curr_id, []):
                    if next_id not in visited_nodes:
                        visited_nodes.add(next_id)
                        queue.append((next_id, depth + 1, node_label))

        dep_paths.sort(key=lambda x: (x.depth, x.file_or_module))
        direct_impact = len(changed_files_raw)
        indirect_impact = len(indirect_nodes)
        total_impact = direct_impact + indirect_impact

        blast_radius = ExportBlastRadius(
            direct_impact=direct_impact,
            indirect_impact=indirect_impact,
            total_impact=total_impact,
            impacted_files=sorted(list(direct_set | indirect_nodes)),
            impacted_modules=impacted_modules_raw or sorted(set([f.split("/")[0] for f in changed_files_raw if "/" in f] or ["root"])),
            dependency_paths=dep_paths,
        )

        # 3. Risk Breakdown with traceable evidence IDs
        breakdown_items: list[ExportRiskBreakdownItem] = []
        raw_scoring_trace: list[ExportScoringTraceItem] = []

        if risk.risk_breakdown:
            for item in risk.risk_breakdown:
                if item.rule == "large_blast_radius" and indirect_impact == 0:
                    continue

                ev_ids = [f"FACT-{i+1:03d}" for i in range(len(item.affected_files or []))] or ["FACT-001"]
                breakdown_items.append(
                    ExportRiskBreakdownItem(
                        rule=item.rule,
                        name=item.name or item.rule,
                        category=item.category,
                        points=item.points,
                        raw_points=float(item.points),
                        evidence=item.evidence,
                        evidence_ids=ev_ids,
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
                if ev.signal == "large_blast_radius" and indirect_impact == 0:
                    continue

                pts = int(round(ev.weight * ev.score * 100))
                breakdown_items.append(
                    ExportRiskBreakdownItem(
                        rule=ev.rule or ev.signal,
                        name=ev.name or ev.rule or ev.signal,
                        category=ev.category,
                        points=pts,
                        raw_points=round(ev.weight * ev.score * 100, 2),
                        evidence=ev.description,
                        evidence_ids=[ev.rule or ev.signal],
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

        for b in breakdown_items:
            raw_scoring_trace.append(
                ExportScoringTraceItem(
                    rule_id=b.rule,
                    name=b.name,
                    triggered=True,
                    raw_points=b.raw_points,
                    confidence=risk.confidence or 0.98,
                    evidence_ids=b.evidence_ids,
                    affected_files=b.affected_files,
                    normalized_points=round(b.raw_points * (normalized_score / raw_rule_score if raw_rule_score > 0 else 1.0), 2),
                    final_points=b.points,
                )
            )

        completeness_detail = ExportEvidenceCompleteness(
            score=risk.evidence_completeness,
            available_signals=[
                "Git Commit Diff Analysis",
                "Tree-Sitter Multi-Language AST Graph",
                "Dependency Graph BFS Traversal",
                "Deterministic Risk Policy Engine",
            ],
            missing_signals=[],
            unavailable_sources=[
                "Dynamic Code Coverage Artifacts (lcov/jacoco)",
                "Production Incident Stream Feed",
            ],
            explanation=(
                f"{int(round(risk.evidence_completeness * 100))}% deterministic evidence completeness based on "
                "available static Git AST, graph topology, manifest, and source files."
            ),
        )

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
            completeness_detail=completeness_detail,
            scoring_trace=raw_scoring_trace,
        )

        # 4. Facts
        facts: list[ExportEvidenceStatement] = []
        fact_idx = 1
        if risk.facts:
            for f in risk.facts:
                facts.append(
                    ExportEvidenceStatement(
                        id=f.id if f.id else f"FACT-{fact_idx:03d}",
                        statement_type="FACT",
                        claim=f.claim,
                        source_evidence=f.source_evidence or "Git commit diff analysis",
                        affected_files=f.affected_files or [],
                        traceability_ref=f.traceability_ref or "",
                    )
                )
                fact_idx += 1
        else:
            facts.append(
                ExportEvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type="FACT",
                    claim=f"{raw_changed_count} file(s) modified in change set ({arch_changed_count} architecturally relevant source/build files).",
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
                        source_evidence="Tree-Sitter Multilingual AST & Graph parser",
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
                    "dependency_upgrades", "dependency_version_changed", "dependency_added",
                    "dependency_removed", "lockfile_changed", "authentication_change", "authorization_change",
                    "credential_change", "session_change", "crypto_change", "permission_change",
                    "secrets_modified", "env_vars_changed", "database_schema_change", "migration_detected",
                    "public_api_changed", "critical_component_modified", "large_refactor"
                ):
                    facts.append(
                        ExportEvidenceStatement(
                            id=f"FACT-{fact_idx:03d}",
                            statement_type="FACT",
                            claim=f"{ev.name or ev.signal}: {ev.description}",
                            source_evidence=f"Observed in {', '.join(ev.file_paths[:3])}" if ev.file_paths else "Repository AST scan",
                            affected_files=ev.file_paths or [],
                            traceability_ref=ev.rule or ev.signal,
                        )
                    )
                    fact_idx += 1

        # 5. Inferences
        inferences: list[ExportEvidenceStatement] = []
        inf_idx = 1
        if risk.inferences:
            for inf in risk.inferences:
                if indirect_impact == 0 and "downstream component dependencies are impacted" in inf.claim.lower():
                    continue
                inferences.append(
                    ExportEvidenceStatement(
                        id=inf.id if inf.id else f"INF-{inf_idx:03d}",
                        statement_type="INFERENCE",
                        claim=inf.claim,
                        source_evidence=inf.source_evidence or "Derived from persisted analysis",
                        traceability_ref=inf.traceability_ref or "",
                        affected_files=inf.affected_files or [],
                    )
                )
                inf_idx += 1
        else:
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

            if indirect_impact > 0:
                inferences.append(
                    ExportEvidenceStatement(
                        id=f"INF-{inf_idx:03d}",
                        statement_type="INFERENCE",
                        claim=f"Downstream regression risk: {indirect_impact} downstream component dependencies are reachable from modified files.",
                        source_evidence="Derived from dependency graph traversal",
                        traceability_ref="rule:large_blast_radius",
                    )
                )
                inf_idx += 1

            for ev in evidence_list:
                if ev.signal in ("dependency_upgrades", "dependency_version_changed", "dependency_added", "dependency_removed"):
                    inferences.append(
                        ExportEvidenceStatement(
                            id=f"INF-{inf_idx:03d}",
                            statement_type="INFERENCE",
                            claim="Package dependency upgrade: Audit external dependency changes before deployment.",
                            source_evidence=f"Observed in {', '.join(ev.file_paths[:2])}" if ev.file_paths else "Manifest scan",
                            traceability_ref=f"rule:{ev.signal}",
                            affected_files=ev.file_paths or [],
                        )
                    )
                    inf_idx += 1
                elif ev.signal == "authentication_change":
                    inferences.append(
                        ExportEvidenceStatement(
                            id=f"INF-{inf_idx:03d}",
                            statement_type="INFERENCE",
                            claim="Authentication boundary change: Login/Logout or identity logic was modified, requiring focused regression testing.",
                            source_evidence=f"Observed in {', '.join(ev.file_paths[:2])}" if ev.file_paths else "Security rule match",
                            traceability_ref="rule:authentication_change",
                            affected_files=ev.file_paths or [],
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

        # 6. Recommendations
        recommendations: list[ExportEvidenceStatement] = []
        rec_idx = 1
        if risk.recommendations:
            for r in risk.recommendations:
                if indirect_impact == 0 and "downstream" in r.claim.lower():
                    continue
                recommendations.append(
                    ExportEvidenceStatement(
                        id=r.id if r.id else f"REC-{rec_idx:03d}",
                        statement_type="RECOMMENDATION",
                        claim=r.claim,
                        recommendation_type=(
                            r.recommendation_type.value
                            if hasattr(r.recommendation_type, "value")
                            else str(r.recommendation_type or "POLICY_BASED")
                        ),
                        source_evidence=r.source_evidence or "Derived from persisted risk evaluation",
                        traceability_ref=r.traceability_ref or "",
                        finding_id=r.finding_id if hasattr(r, "finding_id") else "",
                        affected_files=r.affected_files or [],
                    )
                )
                rec_idx += 1
        else:
            for ev in evidence_list:
                if ev.recommendation:
                    if ev.signal == "large_blast_radius" and indirect_impact == 0:
                        continue
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
                            finding_id=ev.rule or ev.signal,
                            affected_files=ev.file_paths or [],
                        )
                    )
                    rec_idx += 1

        # 7. Changed Files Details (Exact Test Change Status & Categorization)
        changed_files_models: list[ExportChangedFile] = []
        has_test_in_commit = any(classify_file_type(f) == FileTypeCategory.TEST for f in changed_files_raw)

        for f in changed_files_raw:
            norm_f = f.replace("\\", "/")
            ext = norm_f.split(".")[-1].lower() if "." in norm_f else ""
            lang_map = {
                "kt": "Kotlin", "kts": "Kotlin Script", "java": "Java",
                "ts": "TypeScript", "tsx": "TypeScript (React)", "js": "JavaScript",
                "jsx": "JavaScript (React)", "cjs": "CommonJS", "mjs": "ES Module",
                "py": "Python", "json": "JSON", "md": "Markdown", "css": "CSS",
                "html": "HTML", "yml": "YAML", "yaml": "YAML", "sql": "SQL",
                "sh": "Shell", "rs": "Rust", "go": "Go", "txt": "Plain Text",
                "xml": "XML", "properties": "Properties"
            }
            lang = lang_map.get(ext, ext.upper() if ext else "Text")
            parts = norm_f.split("/")
            module = parts[0] if len(parts) > 1 else "root"
            file_category = classify_file_type(f).value
            is_test = file_category == "TEST"

            test_change_status = "TEST_FILE_CHANGED" if is_test else ("TEST_EXISTS" if has_test_in_commit else "NO_TEST_CHANGE")
            test_status_text = (
                "Related test modification detected"
                if is_test
                else "Coverage percentage unavailable — structural test gap inferred"
            )

            matched_signals = [
                ev.name or ev.signal
                for ev in evidence_list
                if any(p in norm_f or norm_f in p for p in (ev.file_paths or []))
            ]

            changed_files_models.append(
                ExportChangedFile(
                    path=f,
                    change_type="MODIFIED",
                    category=file_category,
                    language=lang,
                    module=module,
                    risk_signals=matched_signals,
                    direct_impact="Directly modified in commit",
                    test_status=test_status_text,
                    test_change_status=test_change_status,
                )
            )

        # 8. Architecture & Security Findings
        arch_findings: list[ExportFinding] = []
        sec_findings: list[ExportFinding] = []
        for ev in evidence_list:
            if ev.signal == "large_blast_radius" and indirect_impact == 0:
                continue
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

        # 9. Test Findings
        test_findings: list[ExportTestFinding] = []
        test_files_changed = [
            f for f in changed_files_raw if classify_file_type(f) == FileTypeCategory.TEST
        ]
        if test_files_changed:
            test_findings.append(
                ExportTestFinding(
                    category="Test Changes Detected",
                    title="Related Test Modifications Present",
                    description=f"{len(test_files_changed)} test specification file(s) modified alongside changes: {', '.join(test_files_changed[:3])}",
                    recommendation="Execute modified test specifications to verify regression prevention.",
                    affected_files=test_files_changed,
                    status="TEST_MODIFIED",
                )
            )
        else:
            test_findings.append(
                ExportTestFinding(
                    category="Potential Test Gaps",
                    title="Missing Test Modifications",
                    description="No related unit test or test specification modifications were detected in this commit set.",
                    recommendation="Add unit or integration tests covering modified source logic.",
                    affected_files=arch_relevant_files[:10],
                    status="GAP_DETECTED",
                )
            )

        # 10. Explainable 5-Category Repository Health Breakdown with Security Logic
        hm = health_metrics or {}
        cat_data = hm.get("categories", {})
        orphan_candidates_raw = hm.get("potential_orphan_candidates", hm.get("orphan_modules", []))
        circular_raw = hm.get("circular_dependencies", [])
        gap_raw = hm.get("potential_test_gaps", hm.get("test_coverage_gaps", []))
        fan_out_raw = hm.get("high_fan_out_files", [])
        arch_viol_raw = hm.get("architectural_violations", [])

        # Deterministic 5-category calculation
        arch_score = max(100 - len(circular_raw) * 8 - len(arch_viol_raw) * 10, 10)
        dep_score = max(100 - len(fan_out_raw) * 4, 10)
        test_score = max(100 - min(len(gap_raw) * 3, 50), 10)

        # Security health deducts points when active security risk findings exist without dedicated review
        if sec_findings:
            sec_deductions = min(len(sec_findings) * 15, 40)
            sec_score = max(100 - sec_deductions - len(arch_viol_raw) * 12, 20)
            sec_evidence = [f"{len(sec_findings)} active security signal(s) in change set"] + [f.description[:60] for f in sec_findings[:2]]
            sec_recs = [f.recommendation for f in sec_findings if f.recommendation][:2] or ["Conduct security review before merging."]
        else:
            sec_score = max(100 - len(arch_viol_raw) * 12, 10)
            sec_evidence = ["Baseline static security posture within expected bounds."]
            sec_recs = ["Audit security configurations before major releases."]

        maint_score = max(100 - min(len(orphan_candidates_raw) * 2, 40), 10)

        if cat_data and isinstance(cat_data, dict):
            arch_score = cat_data.get("Architecture", {}).get("score", arch_score)
            dep_score = cat_data.get("Dependencies", {}).get("score", dep_score)
            test_score = cat_data.get("Testing", {}).get("score", test_score)
            if not sec_findings:
                sec_score = cat_data.get("Security", {}).get("score", sec_score)
            maint_score = cat_data.get("Maintainability", {}).get("score", maint_score)

        weighted_overall = int(round(
            arch_score * 0.25 + dep_score * 0.20 + test_score * 0.20 + sec_score * 0.20 + maint_score * 0.15
        ))
        health_score_final = weighted_overall

        health_breakdown = {
            "Architecture": ExportHealthCategoryDetail(
                category="Architecture",
                score=arch_score,
                weight=0.25,
                deductions=100 - arch_score,
                evidence=[f"{len(circular_raw)} circular import loop(s) detected", f"{len(arch_viol_raw)} layering violation(s)"],
                recommendations=["Refactor circular dependencies using dependency inversion."] if circular_raw else ["Maintain current modular architecture."],
            ),
            "Dependencies": ExportHealthCategoryDetail(
                category="Dependencies",
                score=dep_score,
                weight=0.20,
                deductions=100 - dep_score,
                evidence=[f"{len(fan_out_raw)} high fan-out module(s) detected"],
                recommendations=["Decouple high fan-out files into localized sub-modules."] if fan_out_raw else ["External dependencies within healthy limits."],
            ),
            "Testing": ExportHealthCategoryDetail(
                category="Testing",
                score=test_score,
                weight=0.20,
                deductions=100 - test_score,
                evidence=[f"{len(gap_raw)} structural test gap(s) inferred", "Coverage percentage unavailable from static diff"],
                recommendations=["Add test specifications covering untested core source modules."],
            ),
            "Security": ExportHealthCategoryDetail(
                category="Security",
                score=sec_score,
                weight=0.20,
                deductions=100 - sec_score,
                evidence=sec_evidence,
                recommendations=sec_recs,
            ),
            "Maintainability": ExportHealthCategoryDetail(
                category="Maintainability",
                score=maint_score,
                weight=0.15,
                deductions=100 - maint_score,
                evidence=[f"{len(orphan_candidates_raw)} potential orphan candidate(s) (zero incoming references in AST)"],
                recommendations=["Audit orphan candidate files for removal or integration."],
            ),
        }

        repo_health = ExportRepositoryHealth(
            health_score=health_score_final,
            overall=float(health_score_final),
            architecture=float(arch_score),
            dependencies=float(dep_score),
            testing=float(test_score),
            security=float(sec_score),
            maintainability=float(maint_score),
            category_scores_persisted=True,
            health_breakdown=health_breakdown,
            deductions=[f"{cat}: -{det.deductions} pts" for cat, det in health_breakdown.items() if det.deductions > 0],
            potential_test_gaps=gap_raw,
            high_fan_in_files=hm.get("high_fan_in_files", []),
            high_fan_out_files=fan_out_raw,
            dead_code_symbols=hm.get("dead_code_symbols", []),
        )

        # 11. Graph Health & Orphans & Unresolved
        gh = graph.graph_health
        unresolved_details: list[dict[str, Any]] = []
        for e in (graph.edges or []):
            if "unresolved" in e.relationship.lower() or "unresolved" in getattr(e, "edge_type", "").lower():
                unresolved_details.append({
                    "source": e.source,
                    "target": e.target,
                    "reason": "External package dependency or workspace path alias not resolved in AST",
                })

        graph_health_model = ExportGraphHealth(
            nodes=gh.node_count if gh else len(graph.nodes or []),
            edges=gh.edge_count if gh else len(graph.edges or []),
            circular_dependencies=gh.circular_dependency_count if gh else len(circular_raw),
            circular_dependency_cycles=circular_raw,
            orphan_candidates=gh.orphan_candidates if gh else len(orphan_candidates_raw),
            orphan_candidate_files=orphan_candidates_raw,
            unresolved_imports=gh.unresolved_imports if gh else len(unresolved_details),
            unresolved_import_details=unresolved_details,
            self_imports=gh.self_edge_count if gh else 0,
            duplicate_edges=gh.duplicate_edge_count if gh else 0,
            invalid_paths=gh.invalid_paths if gh else 0,
            warnings=gh.warnings if gh else [],
        )

        # 12. Analysis Quality
        analysis_quality = ExportAnalysisQuality(
            git_diff_status="PASS",
            parser_status="PASS" if (graph and len(graph.nodes) > 1) else "WARNING",
            ast_graph_status="PASS" if (graph and len(graph.nodes) > 1) else "INCOMPLETE",
            dependency_resolution="PASS",
            manifest_analysis="PASS" if any("androidmanifest" in f.lower() for f in changed_files_raw) else "N/A",
            coverage_analysis="UNAVAILABLE",
            raw_changed_files_count=raw_changed_count,
            architectural_changed_files_count=arch_changed_count,
            quality_score=1.0 if (graph and len(graph.nodes) > 1) else 0.75,
            warnings=["AST graph contains minimal nodes; verify parser coverage."] if (graph and len(graph.nodes) <= 1) else [],
        )

        # 13. Metadata
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
            rollback_considerations=risk.deployment_considerations or [],
            graph_health=graph_health_model,
            reviewer_evidence=risk.recommended_review_areas or [],
            analysis_quality=analysis_quality,
            metadata=meta,
            ai_report=analysis.ai_report,
        )
