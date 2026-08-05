from app.models.enums import RiskLevel
from app.models.risk import RiskInput
from app.risk.engine import DeterministicRiskEngine


def test_risk_engine_scores_auth_database_and_missing_tests_deterministically() -> None:
    engine = DeterministicRiskEngine()
    payload = RiskInput(
        changed_files=[
            "backend/app/auth/session.py",
            "backend/migrations/20260805_add_user_flags.sql",
            "frontend/app/api/users/route.ts",
        ],
        impacted_modules=["backend", "frontend"],
        dependency_count=8,
        missing_tests=True,
    )

    first = engine.score(payload)
    second = engine.score(payload)

    assert first == second
    assert first.level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert any(item.signal == "authentication_change" for item in first.evidence)
    assert any(item.signal == "database_schema_change" for item in first.evidence)
    assert any(item.signal == "missing_tests" for item in first.evidence)


def test_low_risk_documentation_change_stays_low() -> None:
    engine = DeterministicRiskEngine()
    result = engine.score(RiskInput(changed_files=["docs/readme.md"]))

    assert result.score < 0.3
    assert result.level == RiskLevel.LOW

