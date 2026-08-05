"""Async Analysis Job Management Routes.

Endpoints for submitting background repository analysis jobs, checking job progress,
and retrieving Knowledge Graph health metrics.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.database.session import DbSession, get_session_factory
from app.database.tables import AnalysisJobRow, RepoKnowledgeGraphRow, RepositoryRow
from app.providers.registry import AIProviderRegistry
from app.repositories.provider_repo import AIProviderConfigRepository
from app.workers.analysis_worker import AnalysisWorkerPipeline

router = APIRouter()


class CreateAnalysisJobRequest(BaseModel):
    repository_url: str
    owner: str
    repo_name: str
    base_ref: str = "main~1"
    head_ref: str = "main"


class AnalysisJobStatusResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    step: str
    progress: int
    error: str | None = None
    analysis_id: str | None = None


@router.post("", response_model=AnalysisJobStatusResponse)
async def submit_analysis_job(
    payload: CreateAnalysisJobRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    token: str = Header(..., alias="Authorization"),
) -> AnalysisJobStatusResponse:
    repo_id = f"{payload.owner}-{payload.repo_name}".lower()

    # Ensure repository row exists in DB
    existing_repo = await db.get(RepositoryRow, repo_id)
    if not existing_repo:
        new_repo = RepositoryRow(
            id=repo_id,
            name=payload.repo_name,
            owner=payload.owner,
            full_name=f"{payload.owner}/{payload.repo_name}",
            source="github",
            url=payload.repository_url,
            default_branch=payload.base_ref,
        )
        db.add(new_repo)
        await db.commit()

    # Load configured AI Providers
    configs = await AIProviderConfigRepository(db).list_all()
    registry = AIProviderRegistry(configs=configs) if configs else None

    # Create Analysis Job record
    job_id = str(uuid.uuid4())
    job_row = AnalysisJobRow(
        id=job_id,
        repository_id=repo_id,
        status="PENDING",
        step="Queued in background pipeline",
        progress=5,
    )
    db.add(job_row)
    await db.commit()

    # Dispatch to background worker
    pipeline = AnalysisWorkerPipeline(session_factory=get_session_factory())
    background_tasks.add_task(
        pipeline.execute_job,
        job_id=job_id,
        repository_id=repo_id,
        token=token,
        owner=payload.owner,
        repo_name=payload.repo_name,
        clone_url=payload.repository_url,
        base_ref=payload.base_ref,
        head_ref=payload.head_ref,
        ai_provider_registry=registry,
    )

    return AnalysisJobStatusResponse(
        id=job_id,
        repository_id=repo_id,
        status="PENDING",
        step="Queued in background pipeline",
        progress=5,
    )


@router.get("/{job_id}", response_model=AnalysisJobStatusResponse)
async def get_job_status(job_id: str, db: DbSession) -> AnalysisJobStatusResponse:
    job = await db.get(AnalysisJobRow, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return AnalysisJobStatusResponse(
        id=job.id,
        repository_id=job.repository_id,
        status=job.status,
        step=job.step,
        progress=job.progress,
        error=job.error,
        analysis_id=job.analysis_id,
    )


@router.get("/repositories/{repository_id}/knowledge-graph")
async def get_repository_knowledge_graph(repository_id: str, db: DbSession):
    stmt = (
        select(RepoKnowledgeGraphRow)
        .where(RepoKnowledgeGraphRow.repository_id == repository_id)
        .order_by(RepoKnowledgeGraphRow.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="No knowledge graph found for repository")

    return {
        "id": row.id,
        "repository_id": row.repository_id,
        "commit_sha": row.commit_sha,
        "graph_hash": row.graph_hash,
        "nodes": row.nodes,
        "edges": row.edges,
        "health_metrics": row.health_metrics,
        "created_at": row.created_at.isoformat(),
    }
