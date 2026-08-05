from fastapi import APIRouter, HTTPException

from app.database.session import DbSession
from app.models.ai_provider import AIProviderConfig
from app.repositories.provider_repo import AIProviderConfigRepository

router = APIRouter()


@router.get("", response_model=list[AIProviderConfig])
async def list_providers(db: DbSession) -> list[AIProviderConfig]:
    return await AIProviderConfigRepository(db).list_all()


@router.put("/{provider_id}", response_model=AIProviderConfig)
async def upsert_provider(provider_id: str, payload: AIProviderConfig, db: DbSession) -> AIProviderConfig:
    if provider_id != payload.id:
        raise HTTPException(status_code=400, detail="Provider id mismatch")
    return await AIProviderConfigRepository(db).upsert(payload)


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: str, db: DbSession) -> None:
    await AIProviderConfigRepository(db).delete(provider_id)
