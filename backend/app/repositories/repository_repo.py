"""Repository persistence for tracked repositories."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import RepositoryRow
from app.models.repository import RepositoryCreate, RepositorySummary


class RepositoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[RepositorySummary]:
        result = await self._session.execute(select(RepositoryRow).order_by(RepositoryRow.name))
        return [self._to_schema(row) for row in result.scalars()]

    async def get(self, repository_id: str) -> RepositorySummary | None:
        row = await self._session.get(RepositoryRow, repository_id)
        return self._to_schema(row) if row else None

    async def create(self, payload: RepositoryCreate) -> RepositorySummary:
        row = RepositoryRow(
            id=payload.name.lower().replace(" ", "-"),
            name=payload.name,
            source=payload.source,
            url=str(payload.url) if payload.url else None,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_schema(row)

    async def delete(self, repository_id: str) -> None:
        row = await self._session.get(RepositoryRow, repository_id)
        if row:
            await self._session.delete(row)
            await self._session.commit()

    @staticmethod
    def _to_schema(row: RepositoryRow) -> RepositorySummary:
        return RepositorySummary(
            id=row.id,
            name=row.name,
            source=row.source,
            default_branch=row.default_branch,
            language=row.language,
        )
