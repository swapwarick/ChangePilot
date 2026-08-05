from pydantic import BaseModel, Field

from app.models.enums import RiskLevel


class RiskEvidence(BaseModel):
    signal: str
    description: str
    weight: float = Field(ge=0, le=1)
    score: float = Field(ge=0, le=1)
    file_paths: list[str] = Field(default_factory=list)


class RiskInput(BaseModel):
    changed_files: list[str]
    impacted_modules: list[str] = Field(default_factory=list)
    dependency_count: int = Field(default=0, ge=0)
    missing_tests: bool = False
    large_refactor: bool = False
    critical_modules: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    score: float = Field(ge=0, le=1)
    level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    evidence: list[RiskEvidence]
    reasons: list[str]

