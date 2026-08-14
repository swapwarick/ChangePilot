"""Storage quota enforcement and ephemeral data cleanup.

- ``check_storage_quota``: raises HTTP 413 if adding file_size bytes would exceed the user's quota.
- ``account_storage``: atomically increments or decrements the user's storage counter.
- ``purge_ephemeral_data``: deletes all data rows owned by a guest user on logout.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import AnalysisJobRow, AnalysisRow, RepoKnowledgeGraphRow, RepositoryRow, UserRow

logger = logging.getLogger(__name__)

_30_MB = 31_457_280  # bytes


def check_storage_quota(user: UserRow, file_size_bytes: int) -> None:
    """Raise HTTP 413 if the user would exceed their quota after adding ``file_size_bytes``."""
    if user.tier == "guest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest accounts cannot store data. Please register for a free 30 MB account.",
        )
    if user.storage_quota_bytes <= 0:
        return  # No quota limit configured — allow
    projected = user.storage_used_bytes + file_size_bytes
    if projected > user.storage_quota_bytes:
        used_mb = round(user.storage_used_bytes / 1_048_576, 1)
        quota_mb = round(user.storage_quota_bytes / 1_048_576, 1)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Storage quota exceeded ({used_mb} MB used of {quota_mb} MB). Delete some data to free space.",
        )


async def account_storage(user_id: str, delta_bytes: int, db: AsyncSession) -> None:
    """Add (or subtract) ``delta_bytes`` to the user's ``storage_used_bytes`` counter."""
    user = await db.get(UserRow, user_id)
    if user is None:
        return
    user.storage_used_bytes = max(0, user.storage_used_bytes + delta_bytes)
    await db.commit()


async def purge_ephemeral_data(user_id: str, db: AsyncSession) -> None:
    """Delete all ephemeral rows owned by ``user_id``.

    Called when a guest user logs out so no data is left on the server.
    """
    logger.info("Purging ephemeral data for guest user %s", user_id)

    # Collect repository IDs owned by this user so we can cascade
    repo_ids_result = await db.execute(
        select(RepositoryRow.id).where(
            RepositoryRow.user_id == user_id,
            RepositoryRow.is_ephemeral.is_(True),
        )
    )
    repo_ids = [r for (r,) in repo_ids_result.all()]

    if repo_ids:
        await db.execute(
            delete(AnalysisRow).where(
                AnalysisRow.repository_id.in_(repo_ids),
                AnalysisRow.is_ephemeral.is_(True),
            )
        )
        await db.execute(
            delete(AnalysisJobRow).where(
                AnalysisJobRow.repository_id.in_(repo_ids),
                AnalysisJobRow.is_ephemeral.is_(True),
            )
        )
        await db.execute(
            delete(RepoKnowledgeGraphRow).where(
                RepoKnowledgeGraphRow.repository_id.in_(repo_ids),
                RepoKnowledgeGraphRow.is_ephemeral.is_(True),
            )
        )
        await db.execute(
            delete(RepositoryRow).where(
                RepositoryRow.user_id == user_id,
                RepositoryRow.is_ephemeral.is_(True),
            )
        )

    # Delete the guest user account itself
    await db.execute(delete(UserRow).where(UserRow.id == user_id, UserRow.tier == "guest"))
    await db.commit()
    logger.info("Ephemeral data purge complete for user %s", user_id)
