"""REST API Endpoints for Enterprise Risk Policy Management and Versioning."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.session import DbSession
from app.models.policy import PolicyComparisonResult, PolicyRuleConfig, RiskPolicy
from app.repositories.policy_repo import RiskPolicyRepository

router = APIRouter()


class CreatePolicyRequest(BaseModel):
    name: str = "Enterprise Custom Policy"
    version: str = "1.1.0"
    description: str = "Cloned policy configuration."
    clone_from_id: str | None = None


@router.get("", response_model=list[RiskPolicy])
async def list_policies(db: DbSession) -> list[RiskPolicy]:
    return await RiskPolicyRepository(db).list_all()


@router.get("/active", response_model=RiskPolicy)
async def get_active_policy(db: DbSession) -> RiskPolicy:
    return await RiskPolicyRepository(db).get_active()


@router.post("", response_model=RiskPolicy)
async def create_policy(payload: CreatePolicyRequest, db: DbSession) -> RiskPolicy:
    repo = RiskPolicyRepository(db)
    rules: list[PolicyRuleConfig] = []

    if payload.clone_from_id:
        parent = await repo.get(payload.clone_from_id)
        if parent:
            rules = parent.rules
    if not rules:
        active = await repo.get_active()
        rules = active.rules

    new_policy = RiskPolicy(
        id=str(uuid.uuid4()),
        name=payload.name,
        version=payload.version,
        description=payload.description,
        is_active=False,
        rules=rules,
    )
    return await repo.save(new_policy)


@router.put("/{policy_id}", response_model=RiskPolicy)
async def update_policy(policy_id: str, payload: RiskPolicy, db: DbSession) -> RiskPolicy:
    repo = RiskPolicyRepository(db)
    existing = await repo.get(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")

    payload.id = policy_id
    return await repo.save(payload)


@router.put("/{policy_id}/activate", response_model=RiskPolicy)
async def activate_policy(policy_id: str, db: DbSession) -> RiskPolicy:
    repo = RiskPolicyRepository(db)
    activated = await repo.set_active(policy_id)
    if not activated:
        raise HTTPException(status_code=404, detail="Policy not found")
    return activated


@router.post("/import", response_model=RiskPolicy)
async def import_policy(payload: RiskPolicy, db: DbSession) -> RiskPolicy:
    repo = RiskPolicyRepository(db)
    payload.id = str(uuid.uuid4())
    payload.is_active = False
    return await repo.save(payload)


@router.get("/compare", response_model=PolicyComparisonResult)
async def compare_policies(policy_a: str, policy_b: str, db: DbSession) -> PolicyComparisonResult:
    repo = RiskPolicyRepository(db)
    p_a = await repo.get(policy_a)
    p_b = await repo.get(policy_b)

    if not p_a or not p_b:
        raise HTTPException(status_code=404, detail="One or both policy versions not found")

    rules_a = {r.signal: r for r in p_a.rules}
    rules_b = {r.signal: r for r in p_b.rules}

    weight_changes = []
    status_changes = []
    added = []
    removed = []

    for sig, r_b in rules_b.items():
        if sig not in rules_a:
            added.append({"signal": sig, "name": r_b.name, "weight": r_b.weight})
        else:
            r_a = rules_a[sig]
            if abs(r_a.weight - r_b.weight) > 0.001:
                weight_changes.append({
                    "signal": sig,
                    "name": r_b.name,
                    "old_weight": r_a.weight,
                    "new_weight": r_b.weight,
                })
            if r_a.enabled != r_b.enabled:
                status_changes.append({
                    "signal": sig,
                    "name": r_b.name,
                    "old_enabled": r_a.enabled,
                    "new_enabled": r_b.enabled,
                })

    for sig, r_a in rules_a.items():
        if sig not in rules_b:
            removed.append({"signal": sig, "name": r_a.name, "weight": r_a.weight})

    return PolicyComparisonResult(
        policy_a_version=p_a.version,
        policy_b_version=p_b.version,
        weight_changes=weight_changes,
        status_changes=status_changes,
        added_rules=added,
        removed_rules=removed,
    )
