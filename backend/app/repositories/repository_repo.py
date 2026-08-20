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

    async def list_by_user(self, user_id: str) -> list[RepositorySummary]:
        result = await self._session.execute(
            select(RepositoryRow)
            .where(RepositoryRow.user_id == user_id)
            .order_by(RepositoryRow.name)
        )
        return [self._to_schema(row) for row in result.scalars()]

    async def list_anonymous(self) -> list[RepositorySummary]:
        result = await self._session.execute(
            select(RepositoryRow)
            .where(RepositoryRow.user_id.is_(None))
            .order_by(RepositoryRow.name)
        )
        return [self._to_schema(row) for row in result.scalars()]

    async def get(self, repository_id: str) -> RepositorySummary | None:
        row = await self._session.get(RepositoryRow, repository_id)
        return self._to_schema(row) if row else None

    async def create(
        self, payload: RepositoryCreate, *, user_id: str | None = None, is_ephemeral: bool = False
    ) -> RepositorySummary:
        row = RepositoryRow(
            id=payload.name.lower().replace(" ", "-"),
            name=payload.name,
            source=payload.source,
            url=str(payload.url) if payload.url else None,
            user_id=user_id,
            is_ephemeral=is_ephemeral,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return self._to_schema(row)

    async def delete(self, repository_id: str, *, user_id: str | None = None) -> bool:
        stmt = select(RepositoryRow).where(RepositoryRow.id == repository_id)
        if user_id is not None:
            stmt = stmt.where(RepositoryRow.user_id == user_id)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if not row:
            return False

        from sqlalchemy import delete as sql_delete
        from app.database.tables import AnalysisJobRow, AnalysisRow, RepoKnowledgeGraphRow

        # Cascade delete associated records
        await self._session.execute(sql_delete(AnalysisRow).where(AnalysisRow.repository_id == repository_id))
        await self._session.execute(sql_delete(AnalysisJobRow).where(AnalysisJobRow.repository_id == repository_id))
        await self._session.execute(sql_delete(RepoKnowledgeGraphRow).where(RepoKnowledgeGraphRow.repository_id == repository_id))
        await self._session.delete(row)
        await self._session.commit()
        return True

    @staticmethod
    def _to_schema(row: RepositoryRow) -> RepositorySummary:
        return RepositorySummary(
            id=row.id,
            name=row.name,
            owner=row.owner or "",
            full_name=row.full_name or row.name,
            source=row.source,
            url=row.url,
            default_branch=row.default_branch or "main",
            language=row.language,
        )
