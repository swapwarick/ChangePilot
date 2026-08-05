from uuid import uuid4

from app.graph.builder import DependencyGraphBuilder
from app.models.analysis import ChangeAnalysisRequest, ChangeAnalysisResult
from app.models.risk import RiskInput
from app.risk.engine import DeterministicRiskEngine


class ChangeAnalyzer:
    def __init__(
        self,
        risk_engine: DeterministicRiskEngine | None = None,
        graph_builder: DependencyGraphBuilder | None = None,
    ) -> None:
        self._risk_engine = risk_engine or DeterministicRiskEngine()
        self._graph_builder = graph_builder or DependencyGraphBuilder()

    def analyze(self, request: ChangeAnalysisRequest) -> ChangeAnalysisResult:
        graph = self._graph_builder.from_changed_files(request.changed_files)
        impacted_modules = sorted({node.label for node in graph.nodes if node.kind in {"module", "service"}})
        critical_modules = [
            path for path in request.changed_files if any(marker in path.lower() for marker in ("auth", "payment", "db"))
        ]
        risk = self._risk_engine.score(
            RiskInput(
                changed_files=request.changed_files,
                impacted_modules=impacted_modules,
                dependency_count=len(graph.edges),
                missing_tests=not any("test" in path.lower() or "spec" in path.lower() for path in request.changed_files),
                large_refactor=len(request.changed_files) >= 15,
                critical_modules=critical_modules,
            )
        )
        return ChangeAnalysisResult(
            id=str(uuid4()),
            repository_id=request.repository_id,
            trigger=request.trigger,
            changed_files=request.changed_files,
            impacted_modules=impacted_modules,
            dependency_graph=graph,
            risk=risk,
        )

