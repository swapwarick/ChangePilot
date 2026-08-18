"""Analysis Export API Endpoints.

All endpoints enforce repository isolation:
  - Fetch analysis by analysis_id
  - Verify analysis.repository_id matches the provided repository_id query param (if given)
  - Fetch the Repository record for metadata
  - Fetch knowledge graph snapshot for repository health metrics (if available)
  - Build canonical AnalysisExportModel
  - Stream the export as the appropriate MIME type

Risk scores and findings are NEVER re-computed during export.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.database.session import DbSession
from app.database.tables import AnalysisRow, RepoKnowledgeGraphRow, RepositoryRow
from app.models.export import AnalysisExportModel
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.repository_repo import RepositoryRepository
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter()
_export_service = ExportService()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _resolve_export_model(
    analysis_id: str,
    repository_id: str | None,
    db: DbSession,
) -> tuple[AnalysisExportModel, str]:
    """Fetch and validate analysis + repository + graph, returning canonical AnalysisExportModel."""
    analysis = await AnalysisRepository(db).get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")

    # Repository isolation check
    if repository_id is not None and analysis.repository_id != repository_id:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Analysis '{analysis_id}' does not belong to repository '{repository_id}'. "
                "Export rejected: repository isolation violation."
            ),
        )

    repo = await RepositoryRepository(db).get(analysis.repository_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{analysis.repository_id}' not found.",
        )

    # Fetch knowledge graph health metrics if available
    kg_stmt = (
        select(RepoKnowledgeGraphRow)
        .where(RepoKnowledgeGraphRow.repository_id == analysis.repository_id)
        .order_by(RepoKnowledgeGraphRow.created_at.desc())
        .limit(1)
    )
    kg_res = await db.execute(kg_stmt)
    kg_row = kg_res.scalar_one_or_none()
    health_metrics: dict | None = None
    if kg_row and kg_row.health_metrics:
        hm = kg_row.health_metrics
        if isinstance(hm, str):
            try:
                health_metrics = json.loads(hm)
            except Exception:
                health_metrics = None
        elif isinstance(hm, dict):
            health_metrics = hm

    # Fetch raw row for base_ref / head_ref commit SHAs if present
    row = await db.get(AnalysisRow, analysis_id)
    base_commit = getattr(row, "base_ref", None) if row else None
    head_commit = getattr(row, "head_ref", None) if row else None

    export_model = AnalysisExportModel.from_analysis(
        analysis=analysis,
        repository=repo,
        health_metrics=health_metrics,
        base_commit=base_commit,
        head_commit=head_commit,
    )

    safe_name = _safe_filename(f"{repo.name}-{analysis_id}")
    return export_model, safe_name


def _safe_filename(name: str) -> str:
    """Produce a safe ASCII filename from an arbitrary string."""
    import re
    name = name.encode("ascii", errors="ignore").decode("ascii")
    name = re.sub(r"[^\w\-.]", "_", name)
    return name[:64] or "export"


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}/export/json")
async def export_analysis_json(
    analysis_id: str,
    db: DbSession,
    repository_id: str | None = Query(None, description="Repository isolation guard"),
) -> StreamingResponse:
    """Export the full analysis as a machine-readable JSON document."""
    model, safe_name = await _resolve_export_model(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_json(model)
    except Exception as exc:
        logger.exception("JSON export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([payload]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-analysis.json"'},
    )


# ---------------------------------------------------------------------------
# CSV (ZIP)
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}/export/csv")
async def export_analysis_csv(
    analysis_id: str,
    db: DbSession,
    repository_id: str | None = Query(None, description="Repository isolation guard"),
) -> StreamingResponse:
    """Export the analysis as a ZIP archive containing multiple CSV datasets."""
    model, safe_name = await _resolve_export_model(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_csv(model)
    except Exception as exc:
        logger.exception("CSV export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([payload]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-analysis.zip"'},
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}/export/markdown")
async def export_analysis_markdown(
    analysis_id: str,
    db: DbSession,
    repository_id: str | None = Query(None, description="Repository isolation guard"),
) -> StreamingResponse:
    """Export the analysis as a GitHub/PR-friendly Markdown report."""
    model, safe_name = await _resolve_export_model(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_markdown(model)
    except Exception as exc:
        logger.exception("Markdown export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([payload]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-analysis.md"'},
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}/export/pdf")
async def export_analysis_pdf(
    analysis_id: str,
    db: DbSession,
    repository_id: str | None = Query(None, description="Repository isolation guard"),
) -> StreamingResponse:
    """Export the analysis as a professional enterprise PDF report."""
    model, safe_name = await _resolve_export_model(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_pdf(model)
    except Exception as exc:
        logger.exception("PDF export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return StreamingResponse(
        iter([payload]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-analysis.pdf"'},
    )
