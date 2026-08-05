"""Tests for AIProviderConfigRepository CRUD."""

import pytest

from app.models.ai_provider import AIProviderConfig
from app.models.enums import AIProviderKind
from app.repositories.provider_repo import AIProviderConfigRepository


def _make_config(
    provider_id: str = "ollama-local",
    is_default: bool = False,
    priority: int = 100,
) -> AIProviderConfig:
    return AIProviderConfig(
        id=provider_id,
        name=f"Provider {provider_id}",
        kind=AIProviderKind.OLLAMA,
        base_url="http://localhost:11434",
        model="llama3",
        is_default=is_default,
        priority=priority,
    )


@pytest.mark.asyncio
async def test_upsert_and_list_providers(async_session) -> None:
    repo = AIProviderConfigRepository(async_session)

    config = await repo.upsert(_make_config("ollama-local", priority=1))
    assert config.id == "ollama-local"
    assert config.kind == AIProviderKind.OLLAMA

    all_configs = await repo.list_all()
    assert len(all_configs) == 1


@pytest.mark.asyncio
async def test_is_default_mutual_exclusivity(async_session) -> None:
    repo = AIProviderConfigRepository(async_session)

    await repo.upsert(_make_config("provider-a", is_default=True, priority=1))
    await repo.upsert(_make_config("provider-b", is_default=True, priority=2))

    all_configs = await repo.list_all()
    defaults = [config for config in all_configs if config.is_default]
    assert len(defaults) == 1
    assert defaults[0].id == "provider-b"


@pytest.mark.asyncio
async def test_delete_provider(async_session) -> None:
    repo = AIProviderConfigRepository(async_session)
    await repo.upsert(_make_config("to-delete"))

    await repo.delete("to-delete")
    all_configs = await repo.list_all()
    assert len(all_configs) == 0


@pytest.mark.asyncio
async def test_upsert_updates_existing(async_session) -> None:
    repo = AIProviderConfigRepository(async_session)

    await repo.upsert(_make_config("updatable", priority=50))
    updated_config = _make_config("updatable", priority=10)
    result = await repo.upsert(updated_config)

    assert result.priority == 10
    all_configs = await repo.list_all()
    assert len(all_configs) == 1
