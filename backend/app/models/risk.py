from typing import Any
from pydantic import BaseModel, Field

from app.models.enums import RecommendationType, RiskLevel, StatementType


class EvidenceStatement(BaseModel):
    id: str  # e.g., FACT-001, INF-001, REC-001
    statement_type: StatementType  # FACT, INFERENCE, RECOMMENDATION
    claim: str
    source_evidence: str = ""
    recommendation_type: RecommendationType | None = None  # EVIDENCE_BACKED, POLICY_BASED, GENERIC_BEST_PRACTICE
    traceability_ref: str = ""
    affected_files: list[str] = Field(default_factory=list)


class RiskEvidence(BaseModel):
    signal: str
    name: str = ""
    category: str = "general"  # security, database, architecture, testing, infrastructure, api
    description: str
    weight: float = Field(default=0.1, ge=0, le=1)
    score: float = Field(default=0.5, ge=0, le=1)
    file_paths: list[str] = Field(default_factory=list)
    recommendation: str = ""
    recommendation_type: RecommendationType = RecommendationType.POLICY_BASED
    enabled: bool = True
    threshold: str = ""
    # Machine-readable evidence fields
    rule: str = ""
    source_file: str | None = None
    target_file: str | None = None
    line_number: int | None = None
    evidence_type: str = "signal"
    evidence_value: str = ""
    confidence: float = 1.0


class RiskBreakdownItem(BaseModel):
    rule: str
    name: str = ""  # Human-readable rule name (e.g. "Authentication Modified")
    category: str
    points: int
    evidence: str
    affected_files: list[str] = Field(default_factory=list)
    threshold: str = ""
    recommendation: str = ""
    recommendation_type: RecommendationType = RecommendationType.POLICY_BASED


class RiskInput(BaseModel):
    changed_files: list[str]
    impacted_modules: list[str] = Field(default_factory=list)
    dependency_count: int = Field(default=0, ge=0)
    missing_tests: bool = False
    large_refactor: bool = False
    critical_modules: list[str] = Field(default_factory=list)
    added_files: list[str] = Field(default_factory=list)
    deleted_files: list[str] = Field(default_factory=list)
    renamed_files: list[str] = Field(default_factory=list)
    # Environment & Infrastructure detections
    feature_flag_infrastructure_detected: bool = False
    feature_flag_details: list[str] = Field(default_factory=list)
    deployment_topology_detected: bool = False
    deployment_manifest_paths: list[str] = Field(default_factory=list)
    contributor_ownership_data: dict[str, str] = Field(default_factory=dict)
    # Function-level precision fields (populated when diff parsing is available)
    affected_functions: list[str] = Field(
        default_factory=list,
        description="Names of specific functions/classes that were changed, derived from diff line ranges.",
    )
    line_ranges: dict[str, list[tuple[int, int]]] = Field(
        default_factory=dict,
        description="Mapping of file path → list of (start, end) changed line ranges from unified diff.",
    )
    # Blast radius metadata (populated when graph traversal is available)
    blast_radius_depth: int = Field(
        default=0,
        ge=0,
        description="Maximum transitive depth reached during blast radius traversal.",
    )
    blast_radius_size: int = Field(
        default=0,
        ge=0,
        description="Total number of nodes (changed + transitively impacted) in the blast radius.",
    )
    hub_nodes_affected: list[str] = Field(
        default_factory=list,
        description="Labels of high-degree hub nodes that are directly changed or in the blast radius.",
    )
    bridge_nodes_affected: list[str] = Field(
        default_factory=list,
        description="Labels of architectural bridge/chokepoint nodes in the impact set.",
    )


class RiskResult(BaseModel):
    score: int = Field(ge=0, le=100)  # 0-100 integer deterministic risk index
    level: RiskLevel
    evidence_completeness: float = Field(default=1.0, ge=0, le=1)
    confidence: float = Field(default=1.0, ge=0, le=1)  # alias for evidence_completeness
    is_calibrated: bool = False
    calibration_status: str = "Not statistically calibrated against historical production failure outcomes. Deterministic engineering index only."
    score_description: str = "Deterministic change-risk index based on repository evidence. This score is not a statistical probability of production failure."
    evidence: list[RiskEvidence] = Field(default_factory=list)
    statements: list[EvidenceStatement] = Field(default_factory=list)
    facts: list[EvidenceStatement] = Field(default_factory=list)
    inferences: list[EvidenceStatement] = Field(default_factory=list)
    recommendations: list[EvidenceStatement] = Field(default_factory=list)
    potential_failure_scenarios: list[str] = Field(default_factory=list)
    recommended_review_areas: list[dict[str, Any]] = Field(default_factory=list)
    deployment_considerations: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    risk_breakdown: list[RiskBreakdownItem] = Field(default_factory=list)
    audit: dict[str, float | int] = Field(default_factory=dict)

