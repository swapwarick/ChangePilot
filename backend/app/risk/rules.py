"""Deterministic Risk Engine Rules & Signal Registry.

Includes:
  - Granular security rules (authentication_change, authorization_change, credential_change, session_change, crypto_change, permission_change, secrets_modified)
  - Database schema & migration detection
  - Architectural blast radius & coupling rules
  - Boundary-aware path & symbol matching
"""

from __future__ import annotations

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
        basename = PurePosixPath(normalized).name.lower()
        stem = PurePosixPath(normalized).stem.lower()
        suffix = PurePosixPath(normalized).suffix.lower()

        if self.file_names and basename in [f.lower() for f in self.file_names]:
            return True

        if self.extensions and suffix in [e.lower() for e in self.extensions]:
            return True

        for marker in self.path_markers:
            m = marker.lower()
            if m.endswith("/"):
                if f"/{m}" in f"/{normalized}":
                    return True
            else:
                # Word or boundary matching
                stem_words = stem.replace("_", "-").split("-")
                if m in stem_words or stem.startswith(m) or stem.endswith(m):
                    return True
                if f"/{m}/" in f"/{normalized}":
                    return True

        return False


RULES: tuple[RiskRule, ...] = (
    # Security: Granular Signals
    RiskRule(
        signal="authentication_change",
        name="Authentication Modified",
        category="security",
        description="Authentication, login, logout, or user identity verification logic was modified.",
        weight=0.22,
        recommendation="Run authentication regression tests and request security review before merging.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("auth/", "authentication/", "login/", "logout/", "login", "logout", "authmanager", "authenticator", "biometric", "mfa", "2fa"),
    ),
    RiskRule(
        signal="authorization_change",
        name="Authorization Modified",
        category="security",
        description="Role-based access control, user roles, or permission enforcement policies changed.",
        weight=0.20,
        recommendation="Verify access control checks across all protected endpoints and user actions.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("permission/", "rbac/", "acl/", "policy/", "permissionmanager", "authorizer"),
    ),
    RiskRule(
        signal="credential_change",
        name="Credentials & Password Handling Modified",
        category="security",
        description="Password hashing, keystore, keychain, or credential storage modified.",
        weight=0.24,
        recommendation="Verify credentials are encrypted at rest and never logged in cleartext.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("password", "keystore", "keychain", "credential", "credentialmanager"),
    ),
    RiskRule(
        signal="session_change",
        name="Session Management Modified",
        category="security",
        description="User session lifecycle, session tokens, or session timeout handling modified.",
        weight=0.20,
        recommendation="Verify session invalidation on logout and ensure token expiration is enforced.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("session/", "sessionmanager", "session_manager", "usersession", "tokenmanager", "jwt"),
    ),
    RiskRule(
        signal="crypto_change",
        name="Cryptography / Encryption Modified",
        category="security",
        description="Cryptographic cipher, key generation, or hashing algorithms altered.",
        weight=0.24,
        recommendation="Ensure industry-standard algorithms (AES-256, RSA-4096, SHA-256) are utilized.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        path_markers=("crypto/", "cipher", "encryption", "aes", "rsa", "hash"),
    ),
    RiskRule(
        signal="permission_change",
        name="System Permissions Modified",
        category="security",
        description="Application system permissions or runtime permission requests modified.",
        weight=0.18,
        recommendation="Review requested permissions for principle of least privilege.",
        recommendation_type=RecommendationType.POLICY_BASED,
        threshold="1 file",
        file_names=("androidmanifest.xml",),
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
        path_markers=("secret", "private_key", "pem"),
        file_names=(".env", ".env.local", ".env.production", "secrets.yaml", "secrets.json", "secrets.xml"),
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
        path_markers=("schema/", "models/", "entities/", "prisma/"),
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
        path_markers=("alembic/", "migration/", "migrations/"),
        extensions=(".sql",),
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
        path_markers=("router.delete", "delete_endpoint"),
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
        path_markers=(".github/workflows/", "ci.yml", "pipeline.yml"),
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
        path_markers=("k8s/", "kubernetes/", "helm/", "deployment.yaml"),
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
        file_names=("package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "build.gradle", "build.gradle.kts", "pom.xml"),
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
        path_markers=("payment/", "billing/", "order/", "checkout/"),
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
)
