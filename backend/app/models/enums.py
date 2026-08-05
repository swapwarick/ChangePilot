from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AIProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    CUSTOM_REST = "custom_rest"


class AnalysisTrigger(StrEnum):
    COMMIT_COMPARISON = "commit_comparison"
    BRANCH_COMPARISON = "branch_comparison"
    PULL_REQUEST = "pull_request"
    ZIP_UPLOAD = "zip_upload"

