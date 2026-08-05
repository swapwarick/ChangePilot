from fastapi import APIRouter, HTTPException

from app.analysis.change_analyzer import ChangeAnalyzer
from app.database.session import DbSession
from app.models.analysis import ChangeAnalysisRequest, ChangeAnalysisResult
from app.repositories.analysis_repo import AnalysisRepository

router = APIRouter()
analyzer = ChangeAnalyzer()


@router.post("/changes", response_model=ChangeAnalysisResult)
async def analyze_changes(payload: ChangeAnalysisRequest, db: DbSession) -> ChangeAnalysisResult:
    result = analyzer.analyze(payload)
    return await AnalysisRepository(db).save(result)


@router.get("/{analysis_id}", response_model=ChangeAnalysisResult)
async def get_analysis(analysis_id: str, db: DbSession) -> ChangeAnalysisResult:
    result = await AnalysisRepository(db).get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@router.get("", response_model=list[ChangeAnalysisResult])
async def list_analyses(repository_id: str, db: DbSession, limit: int = 50) -> list[ChangeAnalysisResult]:
    return await AnalysisRepository(db).list_by_repository(repository_id, limit=limit)
