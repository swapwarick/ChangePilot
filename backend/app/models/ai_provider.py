from pydantic import BaseModel, Field, HttpUrl, SecretStr

from app.models.enums import AIProviderKind


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=2, ge=1, le=5)
    backoff_seconds: float = Field(default=0.5, ge=0, le=10)


class AIProviderConfig(BaseModel):
    id: str
    name: str
    kind: AIProviderKind
    base_url: HttpUrl | None = None
    api_key: SecretStr | None = None
    model: str
    enabled: bool = True
    is_default: bool = False
    priority: int = Field(default=100, ge=1)
    task_categories: list[str] = Field(default_factory=lambda: ["report"])
    fallback_provider_ids: list[str] = Field(default_factory=list)
    custom_headers: dict[str, str] = Field(default_factory=dict)
    temperature: float = Field(default=0.2, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    seed: int | None = Field(default=None)
    max_tokens: int = Field(default=4096, ge=1, le=131072)
    timeout_seconds: float = Field(default=120, ge=1, le=600)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class AIMessage(BaseModel):
    role: str
    content: str


class AIRequest(BaseModel):
    task_category: str = "report"
    messages: list[AIMessage]
    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None
    max_tokens: int | None = None


class AIResponse(BaseModel):
    provider_id: str
    model: str
    content: str
    usage: dict[str, int] = Field(default_factory=dict)

class ProviderHealth(BaseModel):
    provider_id: str
    healthy: bool
    latency_ms: int | None = None
    models: list[str] = Field(default_factory=list)
    error: str | None = None

