"""Persistence and retrieval for Enterprise Risk Policies."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import RiskPolicyRow
from app.models.policy import PolicyRuleConfig, RiskPolicy
from app.risk.rules import RULES


class RiskPolicyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seed_default_if_empty(self) -> RiskPolicy:
        stmt = select(RiskPolicyRow).limit(1)
        res = await self._session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return self._to_schema(existing)

        # Seed default v1.0.0 policy with built-in 25 rules
        default_rules = [
            PolicyRuleConfig(
                signal=rule.signal,
                name=rule.name,
                category=rule.category,
                description=rule.description,
                weight=rule.weight,
                enabled=True,
                threshold=rule.threshold,
                recommendation=rule.recommendation,
                path_markers=list(rule.path_markers),
                extensions=list(rule.extensions),
                custom=False,
            )
            for rule in RULES
        ]

        row = RiskPolicyRow(
            id=str(uuid.uuid4()),
            name="Enterprise Default Policy",
            organization_id="default-org",
            version="1.0.0",
            description="Standard enterprise static analysis risk rules and weight thresholds.",
            is_active=True,
            rules=[r.model_dump() for r in default_rules],
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_schema(row)

    async def list_all(self) -> list[RiskPolicy]:
        await self.seed_default_if_empty()
        stmt = select(RiskPolicyRow).order_by(RiskPolicyRow.created_at.desc())
        res = await self._session.execute(stmt)
        return [self._to_schema(row) for row in res.scalars()]

    async def get(self, policy_id: str) -> RiskPolicy | None:
        row = await self._session.get(RiskPolicyRow, policy_id)
        return self._to_schema(row) if row else None

    async def get_active(self) -> RiskPolicy:
        await self.seed_default_if_empty()
        stmt = select(RiskPolicyRow).where(RiskPolicyRow.is_active).limit(1)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row:
            return self._to_schema(row)
        # Fallback to newest
        all_policies = await self.list_all()
        return all_policies[0]

    async def save(self, policy: RiskPolicy) -> RiskPolicy:
        row = RiskPolicyRow(
            id=policy.id,
            name=policy.name,
            organization_id=policy.organization_id,
            version=policy.version,
            description=policy.description,
            is_active=policy.is_active,
            rules=[r.model_dump() if isinstance(r, PolicyRuleConfig) else r for r in policy.rules],
        )
        merged = await self._session.merge(row)
        await self._session.commit()
        await self._session.refresh(merged)
        return self._to_schema(merged)

    async def set_active(self, policy_id: str) -> RiskPolicy | None:
        target = await self._session.get(RiskPolicyRow, policy_id)
        if not target:
            return None

        # Deactivate all
        await self._session.execute(update(RiskPolicyRow).values(is_active=False))
        target.is_active = True
        await self._session.commit()
        await self._session.refresh(target)
        return self._to_schema(target)

    @staticmethod
    def _to_schema(row: RiskPolicyRow) -> RiskPolicy:
        return RiskPolicy(
            id=row.id,
            name=row.name,
            organization_id=row.organization_id,
            version=row.version,
            description=row.description or "",
            is_active=row.is_active,
            rules=[PolicyRuleConfig(**r) for r in row.rules],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
