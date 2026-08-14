from app.models.ai_provider import AIProviderConfig
from app.models.enums import AIProviderKind
from app.providers.base import AIProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


class AIProviderFactory:
    def create(self, config: AIProviderConfig) -> AIProvider:
        if config.kind == AIProviderKind.OLLAMA:
            return OllamaProvider(config)
        if config.kind in {
            AIProviderKind.OPENAI_COMPATIBLE,
            AIProviderKind.CUSTOM_REST,
            AIProviderKind.GROQ,
            AIProviderKind.NVIDIA,
            AIProviderKind.OPENROUTER,
        }:
            return OpenAICompatibleProvider(config)
        raise ValueError(f"Unsupported AI provider kind: {config.kind}")

