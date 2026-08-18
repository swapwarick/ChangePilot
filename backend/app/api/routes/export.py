"""Analysis Export API Endpoints.

All endpoints enforce repository isolation:
  - Fetch analysis by analysis_id
  - Verify analysis.repository_id matches the provided repository_id query param (if given)
  - Fetch the Repository record for metadata
  - Stream the export as the appropriate MIME type

Risk scores and findings are NEVER re-computed during export.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database.session import DbSession
from app.database.tables import AnalysisRow, RepositoryRow
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.repository_repo import RepositoryRepository
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter()
_export_service = ExportService()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _resolve_export_context(
    analysis_id: str,
    repository_id: str | None,
    db: DbSession,
):
    """Fetch and validate analysis + repository. Raises 404/403 on failure."""
    result = await AnalysisRepository(db).get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")

    # Repository isolation check
    if repository_id is not None and result.repository_id != repository_id:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Analysis '{analysis_id}' does not belong to repository '{repository_id}'. "
                "Export rejected: repository isolation violation."
            ),
        )

    repo = await RepositoryRepository(db).get(result.repository_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail=f"Repository '{result.repository_id}' not found.",
        )

    return result, repo


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
    analysis, repo = await _resolve_export_context(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_json(analysis, repo)
    except Exception as exc:
        logger.exception("JSON export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    safe_name = _safe_filename(f"{repo.name}-{analysis_id}")
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
    analysis, repo = await _resolve_export_context(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_csv(analysis, repo)
    except Exception as exc:
        logger.exception("CSV export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    safe_name = _safe_filename(f"{repo.name}-{analysis_id}")
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
    analysis, repo = await _resolve_export_context(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_markdown(analysis, repo)
    except Exception as exc:
        logger.exception("Markdown export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    safe_name = _safe_filename(f"{repo.name}-{analysis_id}")
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
    analysis, repo = await _resolve_export_context(analysis_id, repository_id, db)
    try:
        payload = _export_service.export_pdf(analysis, repo)
    except Exception as exc:
        logger.exception("PDF export failed for analysis %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    safe_name = _safe_filename(f"{repo.name}-{analysis_id}")
    return StreamingResponse(
        iter([payload]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}-analysis.pdf"'},
    )
