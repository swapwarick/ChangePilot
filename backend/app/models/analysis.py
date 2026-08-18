import uuid

from pydantic import BaseModel, Field

from app.models.enums import AnalysisTrigger
from app.models.graph import DependencyGraph
from app.models.risk import RiskResult


class ChangeAnalysisRequest(BaseModel):
    repository_id: str
    trigger: AnalysisTrigger
    base_ref: str | None = None
    head_ref: str | None = None
    changed_files: list[str] = Field(default_factory=list)


class ChangeAnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repository_id: str
    trigger: AnalysisTrigger
    changed_files: list[str]
    impacted_modules: list[str]
    dependency_graph: DependencyGraph
    risk: RiskResult
    ai_report: str | None = None
    parser_version: str = "1.0.0"
    graph_version: str = "1.0.0"
    risk_engine_version: str = "1.0.0"
    analysis_timestamp: str | None = None

