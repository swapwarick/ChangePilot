from fastapi import APIRouter, HTTPException

from app.analysis.change_analyzer import ChangeAnalyzer
from app.core.auth import OptionalUser
from app.database.session import DbSession
from app.models.analysis import ChangeAnalysisRequest, ChangeAnalysisResult
from app.repositories.analysis_repo import AnalysisRepository

router = APIRouter()
analyzer = ChangeAnalyzer()


@router.post("/changes", response_model=ChangeAnalysisResult)
async def analyze_changes(
    payload: ChangeAnalysisRequest, db: DbSession, current_user: OptionalUser = None
) -> ChangeAnalysisResult:
    user_id = current_user.id if current_user else None
    is_ephemeral = current_user.tier == "guest" if current_user else False
    result = analyzer.analyze(payload)
    return await AnalysisRepository(db).save(result, user_id=user_id, is_ephemeral=is_ephemeral)


@router.get("/{analysis_id}", response_model=ChangeAnalysisResult)
async def get_analysis(analysis_id: str, db: DbSession) -> ChangeAnalysisResult:
    result = await AnalysisRepository(db).get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@router.get("", response_model=list[ChangeAnalysisResult])
async def list_analyses(repository_id: str, db: DbSession, limit: int = 50) -> list[ChangeAnalysisResult]:
    return await AnalysisRepository(db).list_by_repository(repository_id, limit=limit)


@router.delete("/{analysis_id}", status_code=204)
async def delete_analysis(
    analysis_id: str, db: DbSession, current_user: OptionalUser = None
) -> None:
    user_id = current_user.id if current_user else None
    deleted = await AnalysisRepository(db).delete(analysis_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis not found or access denied")
