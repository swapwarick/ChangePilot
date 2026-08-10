"""Persistence for AI provider configurations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import AIProviderConfigRow
from app.models.ai_provider import AIProviderConfig, RetryPolicy
from app.models.enums import AIProviderKind


class AIProviderConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, auto_seed: bool = True) -> list[AIProviderConfig]:
        result = await self._session.execute(
            select(AIProviderConfigRow).order_by(AIProviderConfigRow.priority)
        )
        rows = list(result.scalars())
        if not rows and auto_seed:
            default_ollama = AIProviderConfig(
                id="ollama-local",
                name="Ollama Local (qwen3:4b)",
                kind=AIProviderKind.OLLAMA,
                base_url="http://localhost:11434",
                model="qwen3:4b",
                enabled=True,
                is_default=True,
                priority=1,
                timeout_seconds=120.0,
                task_categories=["report", "explain", "general"],
            )
            return [await self.upsert(default_ollama)]
        return [self._to_schema(row) for row in rows]

    async def upsert(self, config: AIProviderConfig) -> AIProviderConfig:
        # If this one is being set as default, clear the flag on others.
        if config.is_default:
            existing = await self._session.execute(
                select(AIProviderConfigRow).where(
                    AIProviderConfigRow.is_default.is_(True),
                    AIProviderConfigRow.id != config.id,
                )
            )
            for row in existing.scalars():
                row.is_default = False

        row = AIProviderConfigRow(
            id=config.id,
            name=config.name,
            kind=config.kind.value,
            base_url=str(config.base_url) if config.base_url else None,
            api_key=config.api_key.get_secret_value() if config.api_key else None,
            model=config.model,
            enabled=config.enabled,
            is_default=config.is_default,
            priority=config.priority,
            task_categories=config.task_categories,
            fallback_provider_ids=config.fallback_provider_ids,
            custom_headers=config.custom_headers,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
            retry_max_attempts=config.retry_policy.max_attempts,
            retry_backoff=config.retry_policy.backoff_seconds,
        )
        merged = await self._session.merge(row)
        await self._session.commit()
        await self._session.refresh(merged)
        return self._to_schema(merged)

    async def delete(self, provider_id: str) -> None:
        row = await self._session.get(AIProviderConfigRow, provider_id)
        if row:
            await self._session.delete(row)
            await self._session.commit()

    @staticmethod
    def _to_schema(row: AIProviderConfigRow) -> AIProviderConfig:
        return AIProviderConfig(
            id=row.id,
            name=row.name,
            kind=AIProviderKind(row.kind),
            base_url=row.base_url,
            api_key=row.api_key,
            model=row.model,
            enabled=row.enabled,
            is_default=row.is_default,
            priority=row.priority,
            task_categories=row.task_categories,
            fallback_provider_ids=row.fallback_provider_ids,
            custom_headers=row.custom_headers,
            temperature=row.temperature,
            max_tokens=row.max_tokens,
            timeout_seconds=row.timeout_seconds,
            retry_policy=RetryPolicy(
                max_attempts=row.retry_max_attempts,
                backoff_seconds=row.retry_backoff,
            ),
        )
