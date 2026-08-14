from dataclasses import dataclass
from pathlib import PurePosixPath

from app.models.enums import RecommendationType


@dataclass(frozen=True)
class RiskRule:
    signal: str
    name: str
    category: str  # security, database, architecture, testing, infrastructure, api
    description: str
    weight: float
    recommendation: str
    recommendation_type: RecommendationType = RecommendationType.POLICY_BASED
    threshold: str = "1 file"
    path_markers: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    file_names: tuple[str, ...] = ()

    def matches(self, file_path: str) -> bool:
        normalized = file_path.replace("\\", "/").lower()
        basename = PurePosixPath(normalized).name
        suffix = PurePosixPath(normalized).suffix
        if self.file_names and basename in self.file_names:
            return True
        return any(marker in normalized for marker in self.path_markers) or (bool(self.extensions) and suffix in self.extensions)


RULES: tuple[RiskRule, ...] = (
    # Security
    RiskRule(
        signal="authentication_change",
        name="Authentication Modified",
        category="security",
        description="Authentication and session management logic was modified.",
        weight=0.22,
        recommendation="Run authentication regression tests and request security review.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("auth", "session", "login", "oauth", "jwt", "better-auth"),
    ),
    RiskRule(
        signal="authorization_change",
        name="Authorization Modified",
        category="security",
        description="Role-based access control or permission enforcement changed.",
        weight=0.20,
        recommendation="Verify permission checks across affected API endpoints.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("permission", "rbac", "acl", "policy", "authorize"),
    ),
    RiskRule(
        signal="secrets_modified",
        name="Secrets / Credentials Modified",
        category="security",
        description="Secrets, credential templates, or key stores were edited.",
        weight=0.25,
        recommendation="Audit secret storage for cleartext leaks and rotate compromised tokens.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("secret", "credential", "private_key", "pem", "keystore"),
        file_names=(".env", ".env.local", "secrets.yaml"),
    ),

    # Database
    RiskRule(
        signal="database_schema_change",
        name="Database Schema Changed",
        category="database",
        description="ORM models, SQL schemas, or database tables were altered.",
        weight=0.20,
        recommendation="Verify backward compatibility and check for destructive column drops.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("schema", "database", "prisma", "models/"),
        extensions=(".sql",),
    ),
    RiskRule(
        signal="migration_detected",
        name="Migration Script Detected",
        category="database",
        description="Database migration scripts were added or modified.",
        weight=0.18,
        recommendation="Test forward and backward migration scripts on staging before deployment.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("alembic", "migration", "migrations/"),
        extensions=(".py", ".sql"),
    ),
    RiskRule(
        signal="no_rollback_plan",
        name="No Rollback Plan / Destructive Schema",
        category="database",
        description="Destructive table or column changes detected without rollback safety.",
        weight=0.18,
        recommendation="Ensure migration scripts include down_revision rollback steps.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("drop_column", "drop_table", "truncate"),
    ),

    # API & Contracts
    RiskRule(
        signal="api_contract_changed",
        name="API Contract Modified",
        category="api",
        description="API route definitions, schemas, or OpenAPI specifications changed.",
        weight=0.16,
        recommendation="Ensure frontend client SDKs and public API consumers remain compatible.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("api/", "routes/", "openapi", "graphql", "proto/"),
    ),
    RiskRule(
        signal="deleted_public_api",
        name="Deleted Public API Endpoint",
        category="api",
        description="Public API endpoints or handler routes were removed.",
        weight=0.22,
        recommendation="Check API gateway routes and notify external API consumers.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("router.delete", "delete_endpoint", "api/"),
    ),

    # Infrastructure
    RiskRule(
        signal="dockerfile_modified",
        name="Dockerfile / Container Build Changed",
        category="infrastructure",
        description="Container build steps or runtime base image changed.",
        weight=0.14,
        recommendation="Rebuild container image locally and verify container startup health.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("dockerfile", "docker-compose"),
        file_names=("dockerfile", "docker-compose.yml", "docker-compose.yaml"),
    ),
    RiskRule(
        signal="github_actions_modified",
        name="CI/CD Workflow Modified",
        category="infrastructure",
        description="GitHub Actions or CI pipeline workflow files modified.",
        weight=0.14,
        recommendation="Test pipeline execution on a pull request branch before merging.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=(".github/workflows", "ci.yml", "pipeline"),
    ),
    RiskRule(
        signal="terraform_changed",
        name="Terraform IaC Changed",
        category="infrastructure",
        description="Infrastructure as Code Terraform manifests modified.",
        weight=0.18,
        recommendation="Execute `terraform plan` to verify cloud resource modifications.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("terraform", "main.tf", "variables.tf"),
        extensions=(".tf",),
    ),
    RiskRule(
        signal="kubernetes_manifests_changed",
        name="Kubernetes Manifests Modified",
        category="infrastructure",
        description="K8s deployment, service, or ingress manifests modified.",
        weight=0.16,
        recommendation="Run `kubectl diff` against staging cluster before applying.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("k8s/", "kubernetes", "helm", "deployment.yaml"),
    ),
    RiskRule(
        signal="env_vars_changed",
        name="Environment Configuration Modified",
        category="infrastructure",
        description="Environment variable configuration or settings files modified.",
        weight=0.12,
        recommendation="Update environment configuration across deployment environments.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=(".env", "config.py", "settings.py", "env.example"),
    ),

    # Architecture & Dependencies
    RiskRule(
        signal="shared_library_modified",
        name="Shared Library / Core Utility Modified",
        category="architecture",
        description="Shared core library or utility module modified.",
        weight=0.16,
        recommendation="Run full repository unit test suite across all dependent modules.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 file",
        path_markers=("shared/", "common/", "core/", "utils/", "lib/"),
    ),
    RiskRule(
        signal="dependency_upgrades",
        name="Package Dependencies Upgraded",
        category="architecture",
        description="Package manager dependency files modified.",
        weight=0.14,
        recommendation="Audit updated dependencies for breaking changes and vulnerability advisories.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        file_names=("package.json", "package-lock.json", "pyproject.toml", "requirements.txt"),
    ),
    RiskRule(
        signal="critical_component_modified",
        name="Critical Business Component Modified",
        category="architecture",
        description="Core payment, billing, or critical domain component modified.",
        weight=0.20,
        recommendation="Run end-to-end integration tests for critical business workflows.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("payment", "billing", "order", "user_service"),
    ),
    RiskRule(
        signal="breaking_exported_interface",
        name="Breaking Exported Interface Change",
        category="architecture",
        description="Exported class or function modified with downstream consumer usage.",
        weight=0.18,
        recommendation="Check call sites across all importing files for parameter mismatches.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 interface",
    ),
    RiskRule(
        signal="circular_dependency",
        name="Circular Import Dependency",
        category="architecture",
        description="Modified files participate in a circular module import loop.",
        weight=0.18,
        recommendation="Refactor circular imports into a separate shared interface or utility.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="1 cycle",
    ),
    RiskRule(
        signal="high_fan_out_module",
        name="High Fan-Out Module (Tight Coupling)",
        category="architecture",
        description="Changed file imports more than 10 downstream modules.",
        weight=0.14,
        recommendation="Apply dependency inversion to decouple high fan-out module.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="> 10 imports",
    ),
    RiskRule(
        signal="high_fan_in_module",
        name="High Fan-In Module (High Centrality)",
        category="architecture",
        description="Changed file is imported by more than 8 downstream modules.",
        weight=0.18,
        recommendation="Ensure thorough test coverage due to extensive downstream consumption.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="> 8 dependents",
    ),
    RiskRule(
        signal="large_refactor",
        name="Large Refactor Change",
        category="architecture",
        description="Change set touches >= 15 files qualifying as a large refactor.",
        weight=0.16,
        recommendation="Break pull request into smaller, isolated sub-PRs for safer review.",
        recommendation_type=RecommendationType.GENERIC_BEST_PRACTICE,
        threshold=">= 15 files",
    ),
    RiskRule(
        signal="large_blast_radius",
        name="Large Downstream Blast Radius",
        category="architecture",
        description="Transitive impact spans more than 20 downstream files.",
        weight=0.20,
        recommendation="Add integration tests for downstream components and validate on staging environment.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="> 20 files",
    ),
    RiskRule(
        signal="multi_module_impact",
        name="Multiple Modules Impacted",
        category="architecture",
        description="Change impact spans across 2 or more distinct architectural modules.",
        weight=0.18,
        recommendation="These components share dependency relationships and should be tested together.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="> 2 modules",
    ),
    RiskRule(
        signal="god_class_modified",
        name="God Class Modified",
        category="architecture",
        description="Modified class contains an unusually high number of methods/responsibilities.",
        weight=0.14,
        recommendation="Break god class down using Single Responsibility Principle.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold=">= 8 methods",
    ),

    # Testing
    RiskRule(
        signal="missing_tests",
        name="Missing Related Test Changes",
        category="testing",
        description="Production code was modified without any corresponding test changes.",
        weight=0.14,
        recommendation="Add unit tests covering modified business logic.",
        recommendation_type=RecommendationType.EVIDENCE_BACKED,
        threshold="0 tests",
    ),
    RiskRule(
        signal="low_test_coverage",
        name="Low Test Coverage Gap",
        category="testing",
        description="Modified files belong to modules with identified test coverage gaps.",
        weight=0.12,
        recommendation="Write automated regression tests for untracked source modules.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="0 test specs",
    ),
)


