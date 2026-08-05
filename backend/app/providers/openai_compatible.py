import time

import httpx

from app.models.ai_provider import AIRequest, AIResponse, ProviderHealth
from app.providers.base import AIProvider


class OpenAICompatibleProvider(AIProvider):
    async def generate(self, request: AIRequest) -> AIResponse:
        if self.config.base_url is None:
            raise ValueError("OpenAI-compatible providers require a base_url")

        url = f"{str(self.config.base_url).rstrip('/')}/chat/completions"
        headers = dict(self.config.custom_headers)
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.get_secret_value()}"

        payload = {
            "model": request.model or self.config.model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature if request.temperature is not None else self.config.temperature,
            "max_tokens": request.max_tokens or self.config.max_tokens,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        content = body["choices"][0]["message"]["content"]
        return AIResponse(
            provider_id=self.config.id,
            model=payload["model"],
            content=content,
            usage=body.get("usage", {}),
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
        url = f"{str(self.config.base_url).rstrip('/')}/models"
        headers = dict(self.config.custom_headers)
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key.get_secret_value()}"
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            body = response.json()
        data = body.get("data", [])
        return [item["id"] for item in data if "id" in item] or [self.config.model]




