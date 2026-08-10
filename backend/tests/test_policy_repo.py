import pytest
from app.database.tables import RiskPolicyRow
from app.models.policy import PolicyRuleConfig, RiskPolicy
from app.repositories.policy_repo import RiskPolicyRepository


@pytest.mark.asyncio
async def test_seed_default_policy(async_session):
    repo = RiskPolicyRepository(async_session)
    active = await repo.get_active()
    assert active is not None
    assert active.version == "1.0.0"
    assert len(active.rules) >= 20
    assert active.is_active is True


@pytest.mark.asyncio
async def test_clone_and_activate_policy(async_session):
    repo = RiskPolicyRepository(async_session)
    active = await repo.get_active()

    cloned = RiskPolicy(
        id="policy-v2-test",
        name="Enterprise Policy v2.0.0",
        version="2.0.0",
        description="Cloned test policy",
        is_active=False,
        rules=active.rules,
    )
    saved = await repo.save(cloned)
    assert saved.id == "policy-v2-test"
    assert saved.version == "2.0.0"

    activated = await repo.set_active("policy-v2-test")
    assert activated is not None
    assert activated.is_active is True

    updated_active = await repo.get_active()
    assert updated_active.id == "policy-v2-test"
