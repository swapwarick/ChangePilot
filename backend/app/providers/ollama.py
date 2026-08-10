import time

import httpx

from app.models.ai_provider import AIRequest, AIResponse, ProviderHealth
from app.providers.base import AIProvider


class OllamaProvider(AIProvider):
    async def generate(self, request: AIRequest) -> AIResponse:
        if self.config.base_url is None:
            raise ValueError("Ollama providers require a base_url")

        url = f"{str(self.config.base_url).rstrip('/')}/api/chat"
        payload = {
            "model": request.model or self.config.model,
            "messages": [message.model_dump() for message in request.messages],
            "stream": False,
            "options": {
                "temperature": request.temperature if request.temperature is not None else self.config.temperature,
                "num_predict": request.max_tokens or self.config.max_tokens,
            },
        }
        timeout_config = httpx.Timeout(300.0, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
        return AIResponse(
            provider_id=self.config.id,
            model=payload["model"],
            content=body.get("message", {}).get("content", ""),
            usage={
                "prompt_tokens": body.get("prompt_eval_count", 0),
                "completion_tokens": body.get("eval_count", 0),
            },
        )

    async def test_connection(self) -> ProviderHealth:
        start = time.perf_counter()
        try:
            models = await self.list_models()
            return ProviderHealth(
                provider_id=self.config.id,
                healthy=True,
                latency_ms=round((time.perf_counter() - start) * 1000),
                models=models,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as provider health.
            return ProviderHealth(provider_id=self.config.id, healthy=False, error=str(exc))

    async def list_models(self) -> list[str]:
        if self.config.base_url is None:
            return [self.config.model]
        url = f"{str(self.config.base_url).rstrip('/')}/api/tags"
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            body = response.json()
        return [item["name"] for item in body.get("models", [])] or [self.config.model]

