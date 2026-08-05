from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class RiskRule:
    signal: str
    description: str
    weight: float
    path_markers: tuple[str, ...]
    extensions: tuple[str, ...] = ()

    def matches(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/").lower()
        suffix = PurePosixPath(normalized).suffix
        return any(marker in normalized for marker in self.path_markers) or suffix in self.extensions


RULES: tuple[RiskRule, ...] = (
    RiskRule(
        signal="authentication_change",
        description="Authentication-sensitive files changed.",
        weight=0.2,
        path_markers=("auth", "session", "login", "oauth", "better-auth"),
    ),
    RiskRule(
        signal="authorization_change",
        description="Authorization or policy enforcement changed.",
        weight=0.18,
        path_markers=("permission", "rbac", "acl", "policy", "authorize"),
    ),
    RiskRule(
        signal="database_schema_change",
        description="Database schema or migration files changed.",
        weight=0.18,
        path_markers=("migration", "schema", "database", "prisma", "alembic"),
        extensions=(".sql",),
    ),
    RiskRule(
        signal="api_contract_change",
        description="API routes, schemas, or contract files changed.",
        weight=0.14,
        path_markers=("api", "schema", "openapi", "routes", "contract"),
    ),
    RiskRule(
        signal="infrastructure_change",
        description="Infrastructure or deployment configuration changed.",
        weight=0.12,
        path_markers=("docker", "kubernetes", "terraform", ".github/workflows", "helm"),
        extensions=(".tf", ".yaml", ".yml"),
    ),
    RiskRule(
        signal="environment_config_change",
        description="Environment configuration changed.",
        weight=0.1,
        path_markers=(".env", "config", "settings"),
    ),
    RiskRule(
        signal="shared_library_change",
        description="Shared library or common module changed.",
        weight=0.12,
        path_markers=("shared", "common", "lib", "utils", "packages/"),
    ),
)

