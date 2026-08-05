"""Tests for RepositoryRepository CRUD."""

import pytest

from app.models.repository import RepositoryCreate
from app.repositories.repository_repo import RepositoryRepository


@pytest.mark.asyncio
async def test_create_and_list_repositories(async_session) -> None:
    repo = RepositoryRepository(async_session)

    created = await repo.create(RepositoryCreate(name="My App", source="github"))
    assert created.id == "my-app"
    assert created.name == "My App"
    assert created.source == "github"
    assert created.default_branch == "main"

    all_repos = await repo.list_all()
    assert len(all_repos) == 1
    assert all_repos[0].id == "my-app"


@pytest.mark.asyncio
async def test_get_repository(async_session) -> None:
    repo = RepositoryRepository(async_session)
    await repo.create(RepositoryCreate(name="Backend", source="gitlab"))

    found = await repo.get("backend")
    assert found is not None
    assert found.name == "Backend"

    missing = await repo.get("nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_delete_repository(async_session) -> None:
    repo = RepositoryRepository(async_session)
    await repo.create(RepositoryCreate(name="Temp Repo", source="zip"))

    await repo.delete("temp-repo")
    result = await repo.get("temp-repo")
    assert result is None
