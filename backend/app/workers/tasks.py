from app.analysis.change_analyzer import ChangeAnalyzer
from app.models.analysis import ChangeAnalysisRequest, ChangeAnalysisResult


def analyze_repository_change(payload: ChangeAnalysisRequest) -> ChangeAnalysisResult:
    return ChangeAnalyzer().analyze(payload)

