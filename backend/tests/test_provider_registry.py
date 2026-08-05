import pytest

from app.models.ai_provider import AIProviderConfig, AIRequest, AIResponse
from app.models.enums import AIProviderKind
from app.providers.base import AIProvider
from app.providers.registry import AIProviderRegistry


class FailingProvider(AIProvider):
    async def generate(self, request: AIRequest) -> AIResponse:
        raise RuntimeError("provider unavailable")

    async def test_connection(self):
        raise RuntimeError("provider unavailable")

    async def list_models(self):
        return []


class PassingProvider(AIProvider):
    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(provider_id=self.config.id, model=self.config.model, content="ok")

    async def test_connection(self):
        raise RuntimeError("not needed")

    async def list_models(self):
        return [self.config.model]


class FakeFactory:
    def create(self, config: AIProviderConfig) -> AIProvider:
        if config.id == "primary":
            return FailingProvider(config)
        return PassingProvider(config)


@pytest.mark.asyncio
async def test_provider_registry_falls_back_by_priority() -> None:
    registry = AIProviderRegistry(
        configs=[
            AIProviderConfig(
                id="primary",
                name="Primary",
                kind=AIProviderKind.OPENAI_COMPATIBLE,
                base_url="http://localhost:1234/v1",
                model="primary-model",
                priority=1,
                is_default=True,
            ),
            AIProviderConfig(
                id="fallback",
                name="Fallback",
                kind=AIProviderKind.OLLAMA,
                base_url="http://localhost:11434",
                model="fallback-model",
                priority=2,
            ),
        ],
        factory=FakeFactory(),
    )

    response = await registry.generate_with_fallback(AIRequest(messages=[]))

    assert response.provider_id == "fallback"
    assert response.content == "ok"

