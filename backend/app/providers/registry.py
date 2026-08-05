import asyncio
import logging

from app.models.ai_provider import AIProviderConfig, AIRequest, AIResponse
from app.providers.factory import AIProviderFactory

logger = logging.getLogger(__name__)


class AIProviderRegistry:
    def __init__(
        self,
        configs: list[AIProviderConfig],
        factory: AIProviderFactory | None = None,
    ) -> None:
        self._configs = {config.id: config for config in configs}
        self._factory = factory or AIProviderFactory()

    def list_configs(self) -> list[AIProviderConfig]:
        return sorted(self._configs.values(), key=lambda config: config.priority)

    def upsert(self, config: AIProviderConfig) -> AIProviderConfig:
        if config.is_default:
            for provider_id, existing in self._configs.items():
                if provider_id != config.id:
                    self._configs[provider_id] = existing.model_copy(update={"is_default": False})
        self._configs[config.id] = config
        return config

    def delete(self, provider_id: str) -> None:
        self._configs.pop(provider_id)

    async def generate_with_fallback(self, request: AIRequest) -> AIResponse:
        errors: list[str] = []
        for config in self._ordered_candidates(request.task_category):
            provider = self._factory.create(config)
            for attempt in range(config.retry_policy.max_attempts):
                try:
                    return await provider.generate(request)
                except Exception as exc:  # noqa: BLE001 - records adapter failure before fallback.
                    errors.append(f"{config.id} attempt {attempt + 1}: {exc}")
                    logger.warning("AI provider failed", extra={"provider_id": config.id, "error": str(exc)})
                    if attempt + 1 < config.retry_policy.max_attempts:
                        await asyncio.sleep(config.retry_policy.backoff_seconds)
        raise RuntimeError("All configured AI providers failed: " + "; ".join(errors))

    def _ordered_candidates(self, task_category: str) -> list[AIProviderConfig]:
        enabled = [
            config
            for config in self._configs.values()
            if config.enabled and task_category in config.task_categories
        ]
        default = [config for config in enabled if config.is_default]
        remaining = [config for config in enabled if not config.is_default]
        return default + sorted(remaining, key=lambda config: config.priority)

