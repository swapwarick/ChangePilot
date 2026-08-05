from fastapi import APIRouter

from app.database.session import DbSession
from app.models.repository import RepositoryCreate, RepositorySummary
from app.repositories.repository_repo import RepositoryRepository

router = APIRouter()


@router.get("", response_model=list[RepositorySummary])
async def list_repositories(db: DbSession) -> list[RepositorySummary]:
    return await RepositoryRepository(db).list_all()


@router.post("", response_model=RepositorySummary)
async def create_repository(payload: RepositoryCreate, db: DbSession) -> RepositorySummary:
    return await RepositoryRepository(db).create(payload)


@router.delete("/{repository_id}", status_code=204)
async def delete_repository(repository_id: str, db: DbSession) -> None:
    await RepositoryRepository(db).delete(repository_id)
