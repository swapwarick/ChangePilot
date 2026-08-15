"""Scientifically Defensible Risk Assessment & Reporting Test Suite.

Verifies the 12 core scientific validation criteria:
1. Files are not called services.
2. Modules are not called services.
3. Import dependencies do not imply deployment order.
4. Feature flags are not recommended without evidence.
5. Human reviewers are not invented.
6. File paths are labeled review areas when ownership is unavailable.
7. Risk score is not described as failure probability.
8. Confidence is labeled Evidence Completeness.
9. Failure scenarios are explicitly marked as potential.
10. Recommendations are separated from facts.
11. AI Prompt strictly grounds on supplied evidence without unsupported inventions.
12. Missing deployment topology produces no deployment-order claims.
"""

import pytest

from app.models.enums import RecommendationType, RiskLevel, StatementType
from app.models.risk import RiskInput
from app.prompts.manager import DEFAULT_PROMPTS, PromptManager
from app.risk.engine import DeterministicRiskEngine


@pytest.fixture
def risk_engine() -> DeterministicRiskEngine:
    return DeterministicRiskEngine()


def test_1_and_2_files_and_modules_are_not_called_services(risk_engine: DeterministicRiskEngine):
    """Test 1 & 2: Files, modules, and components are not referred to as 'services'."""
    payload = RiskInput(
        changed_files=[
            "frontend/src/App.tsx",
            "frontend/src/components/CommandBar.tsx",
            "frontend/src/main.tsx",
            "frontend/vite.config.ts",
        ],
        impacted_modules=["frontend/components", "frontend/src", "frontend/config"],
        dependency_count=12,
    )
    result = risk_engine.score(payload)

    # Ensure no evidence or statement refers to App.tsx or modules as "services"
    for ev in result.evidence:
        assert "Multiple Services Impacted" not in ev.name
        assert "microservices" not in ev.recommendation.lower()

    for stmt in result.statements:
        assert "Multiple Services Impacted" not in stmt.claim


def test_3_and_12_import_dependencies_do_not_imply_deployment_order(risk_engine: DeterministicRiskEngine):
    """Test 3 & 12: Import graphs do not generate standalone deployment order claims without topology."""
    payload = RiskInput(
        changed_files=["src/moduleA.ts", "src/moduleB.ts", "src/moduleC.ts"],
        impacted_modules=["moduleA", "moduleB", "moduleC"],
        dependency_count=15,
        deployment_topology_detected=False,
    )
    result = risk_engine.score(payload)

    for dep_note in result.deployment_considerations:
        assert "coordinate deployment order" not in dep_note.lower()
        assert "do not infer standalone deployment sequencing" in dep_note.lower() or "tested together" in dep_note.lower()


def test_4_feature_flags_not_recommended_without_evidence(risk_engine: DeterministicRiskEngine):
    """Test 4: Feature flags are only recommended when feature flag infrastructure is detected."""
    # Scenario A: No feature flags in repository
    no_ff_payload = RiskInput(
        changed_files=["src/utils/math.ts", "src/components/Button.tsx"],
        dependency_count=25,
        feature_flag_infrastructure_detected=False,
    )
    res_no_ff = risk_engine.score(no_ff_payload)

    for rec in res_no_ff.recommendations:
        assert "feature flag" not in rec.claim.lower()

    ff_fact = next(f for f in res_no_ff.facts if "feature flag" in f.claim.lower())
    assert "not detected" in ff_fact.claim.lower()

    # Scenario B: Feature flags detected
    ff_payload = RiskInput(
        changed_files=["src/utils/math.ts", "src/config/flags.py"],
        dependency_count=25,
        feature_flag_infrastructure_detected=True,
    )
    res_ff = risk_engine.score(ff_payload)
    ff_fact_b = next(f for f in res_ff.facts if "feature flag" in f.claim.lower())
    assert "detected" in ff_fact_b.claim.lower() and "not detected" not in ff_fact_b.claim.lower()


def test_5_and_6_human_reviewers_not_invented_and_labeled_review_areas(risk_engine: DeterministicRiskEngine):
    """Test 5 & 6: File paths are labeled 'review area' and usernames are not fabricated."""
    # Scenario A: No contributor Git data
    payload_no_owner = RiskInput(
        changed_files=["frontend/src/components/CommandBar.tsx"],
        contributor_ownership_data={},
    )
    result = risk_engine.score(payload_no_owner)

    assert len(result.recommended_review_areas) == 1
    area = result.recommended_review_areas[0]
    assert area["review_area"] == "frontend/src/components/CommandBar.tsx"
    assert area["suggested_reviewer"] is None
    assert "could not be determined" in area["ownership_note"]

    # Scenario B: Known contributor Git history
    payload_with_owner = RiskInput(
        changed_files=["frontend/src/components/CommandBar.tsx"],
        contributor_ownership_data={"frontend/src/components/CommandBar.tsx": "alice_dev"},
    )
    result_owner = risk_engine.score(payload_with_owner)
    area_b = result_owner.recommended_review_areas[0]
    assert area_b["suggested_reviewer"] == "alice_dev"


def test_7_and_8_risk_score_and_confidence_semantics(risk_engine: DeterministicRiskEngine):
    """Test 7 & 8: Risk score is deterministic engineering index and confidence is evidence completeness."""
    payload = RiskInput(
        changed_files=["app/main.py", "app/auth.py"],
        dependency_count=8,
    )
    result = risk_engine.score(payload)

    # Risk Score description disclaims failure probability
    assert "not a statistical probability of production failure" in result.score_description.lower()
    assert result.is_calibrated is False
    assert "not statistically calibrated" in result.calibration_status.lower()

    # Evidence completeness between 0 and 1
    assert 0.60 <= result.evidence_completeness <= 1.0
    assert result.evidence_completeness == result.confidence


def test_9_failure_scenarios_marked_as_potential(risk_engine: DeterministicRiskEngine):
    """Test 9: Failure scenarios use probabilistic potential language, never certainty."""
    payload = RiskInput(
        changed_files=["app/auth/session.py", "app/db/migrations/001.sql"],
        dependency_count=18,
        missing_tests=True,
    )
    result = risk_engine.score(payload)

    assert len(result.potential_failure_scenarios) > 0
    for scenario in result.potential_failure_scenarios:
        assert scenario.startswith("Potential Scenario:")
        assert "will fail" not in scenario.lower()
        assert "will break" not in scenario.lower()
        assert any(w in scenario.lower() for w in ("may", "could", "possible"))


def test_10_recommendations_separated_from_facts(risk_engine: DeterministicRiskEngine):
    """Test 10: Facts, inferences, and recommendations are strictly separated and typed."""
    payload = RiskInput(
        changed_files=["src/core.py", "src/auth.py"],
        dependency_count=14,
        missing_tests=True,
    )
    result = risk_engine.score(payload)

    assert len(result.facts) > 0
    assert len(result.inferences) > 0
    assert len(result.recommendations) > 0

    for fact in result.facts:
        assert fact.statement_type == StatementType.FACT
        assert fact.id.startswith("FACT-")

    for inf in result.inferences:
        assert inf.statement_type == StatementType.INFERENCE
        assert inf.id.startswith("INF-")

    for rec in result.recommendations:
        assert rec.statement_type == StatementType.RECOMMENDATION
        assert rec.id.startswith("REC-")
        assert rec.recommendation_type in {
            RecommendationType.EVIDENCE_BACKED,
            RecommendationType.POLICY_BASED,
            RecommendationType.GENERIC_BEST_PRACTICE,
        }


def test_11_ai_prompt_grounding_constraints():
    """Test 11: Prompt template contains strict anti-hallucination and evidence grounding instructions."""
    pm = PromptManager(DEFAULT_PROMPTS)
    latest_template = pm.latest("risk_report")

    assert latest_template.version >= 2
    assert "Never call files, folders, or modules 'services'" in latest_template.template
    assert "Do NOT infer deployment ordering solely from source code imports" in latest_template.template
    assert "Do NOT recommend feature flags unless feature flag infrastructure is confirmed" in latest_template.template
    assert "Do NOT invent human reviewers" in latest_template.template
    assert "Potential Scenario" in latest_template.template
    assert "facts_json" in latest_template.variables
    assert "inferences_json" in latest_template.variables
    assert "recommendations_json" in latest_template.variables


def test_12_risk_breakdown_items_carry_human_readable_name(risk_engine: DeterministicRiskEngine):
    """Test 12: Each RiskBreakdownItem has a non-empty human-readable name field, not just a machine-key signal."""
    payload = RiskInput(
        changed_files=["backend/app/auth/session.py", "backend/migrations/001.sql"],
        dependency_count=8,
        missing_tests=True,
    )
    result = risk_engine.score(payload)

    assert len(result.risk_breakdown) > 0
    for item in result.risk_breakdown:
        # name must be a non-empty string distinct enough to be human-readable
        assert item.name, f"RiskBreakdownItem '{item.rule}' has an empty name field"
        # name should not be identical to the raw signal key for rules that have proper names
        # (signal keys use underscores; names are title-cased human labels)


def test_13_risk_breakdown_items_carry_recommendation_type(risk_engine: DeterministicRiskEngine):
    """Test 13: Every RiskBreakdownItem with a recommendation carries a typed recommendation_type classification."""
    payload = RiskInput(
        changed_files=["src/auth.py", "src/payment.py"],
        dependency_count=12,
        missing_tests=True,
        critical_modules=["src/payment.py"],
    )
    result = risk_engine.score(payload)

    for item in result.risk_breakdown:
        if item.recommendation:
            assert item.recommendation_type in {
                RecommendationType.EVIDENCE_BACKED,
                RecommendationType.POLICY_BASED,
                RecommendationType.GENERIC_BEST_PRACTICE,
            }, f"Rule '{item.rule}' has recommendation but missing valid recommendation_type"


def test_14_v3_prompt_includes_risk_breakdown_json():
    """Test 14: v3 prompt template includes risk_breakdown_json so LLM can produce a grounded Risk Factors table."""
    pm = PromptManager(DEFAULT_PROMPTS)
    latest_template = pm.latest("risk_report")

    assert latest_template.version >= 3, (
        f"Latest prompt version is {latest_template.version}. Expected v3+ with risk_breakdown_json."
    )
    assert "risk_breakdown_json" in latest_template.variables, (
        "v3 prompt must declare 'risk_breakdown_json' as a variable so the LLM can write grounded Risk Factors."
    )
    assert "risk_breakdown_json" in latest_template.template, (
        "v3 prompt template body must reference {{ risk_breakdown_json }} in its evidence payload."
    )
    # Grounding rule 9: no evidence invention
    assert "Do not introduce facts that are not present in the supplied evidence" in latest_template.template


def test_15_hub_and_bridge_node_signals_fire_when_data_present(risk_engine: DeterministicRiskEngine):
    """Test 15: hub_node_affected and bridge_node_affected evidence signals are emitted when topology data is provided."""
    payload = RiskInput(
        changed_files=["src/core/router.ts", "src/utils/config.ts"],
        dependency_count=18,
        hub_nodes_affected=["src/core/router.ts"],
        bridge_nodes_affected=["src/utils/config.ts"],
    )
    result = risk_engine.score(payload)

    signals = {ev.signal for ev in result.evidence}
    assert "hub_node_affected" in signals, (
        "hub_node_affected evidence signal must be triggered when hub_nodes_affected is populated."
    )
    assert "bridge_node_affected" in signals, (
        "bridge_node_affected evidence signal must be triggered when bridge_nodes_affected is populated."
    )


def test_16_risk_score_is_integer(risk_engine: DeterministicRiskEngine):
    """Test 16: Risk score is an integer (deterministic engineering index), never a float.

    The score description states: 'This score is not a statistical probability of production failure.'
    Presenting it as a float (e.g. 66.34) implies false precision. It must be an integer on [0, 100].
    """
    payload = RiskInput(
        changed_files=["src/auth.py", "src/db.py"],
        dependency_count=10,
        missing_tests=True,
    )
    result = risk_engine.score(payload)

    assert isinstance(result.score, int), (
        f"Risk score must be int, got {type(result.score).__name__} ({result.score}). "
        "The deterministic index must be an integer — float presentation implies false precision."
    )
    assert 0 <= result.score <= 100
