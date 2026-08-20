from fastapi import APIRouter

from app.core.auth import OptionalUser
from app.database.session import DbSession
from app.models.repository import RepositoryCreate, RepositorySummary
from app.repositories.repository_repo import RepositoryRepository

router = APIRouter()


@router.get("", response_model=list[RepositorySummary])
async def list_repositories(db: DbSession, current_user: OptionalUser = None) -> list[RepositorySummary]:
    if current_user:
        return await RepositoryRepository(db).list_by_user(current_user.id)
    return await RepositoryRepository(db).list_anonymous()


@router.post("", response_model=RepositorySummary)
async def create_repository(
    payload: RepositoryCreate, db: DbSession, current_user: OptionalUser = None
) -> RepositorySummary:
    user_id = current_user.id if current_user else None
    is_ephemeral = current_user.tier == "guest" if current_user else False
    return await RepositoryRepository(db).create(payload, user_id=user_id, is_ephemeral=is_ephemeral)


@router.delete("/{repository_id}", status_code=204)
async def delete_repository(
    repository_id: str, db: DbSession, current_user: OptionalUser = None
) -> None:
    user_id = current_user.id if current_user else None
    await RepositoryRepository(db).delete(repository_id, user_id=user_id)
