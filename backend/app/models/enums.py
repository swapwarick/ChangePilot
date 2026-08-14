from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EdgeType(StrEnum):
    SOURCE_IMPORT = "SOURCE_IMPORT"
    PACKAGE_DEPENDENCY = "PACKAGE_DEPENDENCY"
    CONFIG_REFERENCE = "CONFIG_REFERENCE"
    BUILD_DEPENDENCY = "BUILD_DEPENDENCY"
    ROUTE_REFERENCE = "ROUTE_REFERENCE"
    TEST_REFERENCE = "TEST_REFERENCE"
    DYNAMIC_IMPORT = "DYNAMIC_IMPORT"
    SELF_IMPORT = "SELF_IMPORT"


class FileClassification(StrEnum):
    ENTRYPOINT = "ENTRYPOINT"
    ROUTE = "ROUTE"
    CONFIGURATION = "CONFIGURATION"
    TEST = "TEST"
    SOURCE_MODULE = "SOURCE_MODULE"
    ORPHAN_CANDIDATE = "ORPHAN_CANDIDATE"


class AIProviderKind(StrEnum):
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    CUSTOM_REST = "custom_rest"
    GROQ = "groq"
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"


class AnalysisTrigger(StrEnum):
    COMMIT_COMPARISON = "commit_comparison"
    BRANCH_COMPARISON = "branch_comparison"
    PULL_REQUEST = "pull_request"
    ZIP_UPLOAD = "zip_upload"

