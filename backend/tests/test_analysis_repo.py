"""Tests for AnalysisRepository CRUD."""

import pytest

from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger, RiskLevel
from app.models.graph import DependencyGraph
from app.models.risk import RiskEvidence, RiskResult
from app.repositories.analysis_repo import AnalysisRepository


def _make_result(analysis_id: str = "a-1", repository_id: str = "repo-1") -> ChangeAnalysisResult:
    return ChangeAnalysisResult(
        id=analysis_id,
        repository_id=repository_id,
        trigger=AnalysisTrigger.PULL_REQUEST,
        changed_files=["src/auth.py", "src/db.py"],
        impacted_modules=["auth", "database"],
        dependency_graph=DependencyGraph(nodes=[], edges=[]),
        risk=RiskResult(
            score=65,
            level=RiskLevel.HIGH,
            confidence=0.85,
            evidence=[
                RiskEvidence(
                    signal="authentication_change",
                    description="Auth files changed.",
                    weight=0.2,
                    score=0.33,
                    file_paths=["src/auth.py"],
                )
            ],
            reasons=["authentication_change: Auth files changed."],
        ),
    )


@pytest.mark.asyncio
async def test_save_and_get_analysis(async_session) -> None:
    repo = AnalysisRepository(async_session)
    original = _make_result()

    saved = await repo.save(original)
    assert saved.id == "a-1"
    assert saved.risk.score == 65
    assert saved.risk.level == RiskLevel.HIGH
    assert len(saved.risk.evidence) == 1

    fetched = await repo.get("a-1")
    assert fetched is not None
    assert fetched.changed_files == ["src/auth.py", "src/db.py"]


@pytest.mark.asyncio
async def test_list_by_repository(async_session) -> None:
    repo = AnalysisRepository(async_session)
    await repo.save(_make_result("a-1", "repo-1"))
    await repo.save(_make_result("a-2", "repo-1"))
    await repo.save(_make_result("a-3", "repo-2"))

    results = await repo.list_by_repository("repo-1")
    assert len(results) == 2
    assert all(result.repository_id == "repo-1" for result in results)


@pytest.mark.asyncio
async def test_get_missing_analysis_returns_none(async_session) -> None:
    repo = AnalysisRepository(async_session)
    assert await repo.get("nonexistent") is None
