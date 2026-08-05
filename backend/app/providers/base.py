from abc import ABC, abstractmethod

from app.models.ai_provider import AIProviderConfig, AIRequest, AIResponse, ProviderHealth


class AIProvider(ABC):
    def __init__(self, config: AIProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    @abstractmethod
    async def test_connection(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[str]:
        raise NotImplementedError

