"""Change analysis orchestrator.

Coordinates diff parsing, dependency graph construction, blast radius traversal,
execution flow tracing, centrality analysis, and risk scoring into a single
coherent analysis pipeline.

Supports three *detail levels* that trade off depth against speed:

* ``"minimal"``  — risk level + impacted file/module counts; no graph traversal.
* ``"standard"`` — full graph + blast radius + risk evidence (default).
* ``"deep"``     — standard + execution flow tracing + centrality analysis.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from app.analysis.blast_radius_helper import enrich_risk_input_with_graph_analysis
from app.graph.builder import DependencyGraphBuilder
from app.models.analysis import ChangeAnalysisRequest, ChangeAnalysisResult
from app.models.risk import RiskInput
from app.risk.engine import DeterministicRiskEngine

logger = logging.getLogger(__name__)

# Valid analysis detail levels
DETAIL_LEVELS = frozenset({"minimal", "standard", "deep"})


class ChangeAnalyzer:
    """Orchestrates the full change-impact analysis pipeline.

    Args:
        risk_engine:   Risk scoring engine.  Defaults to :class:`DeterministicRiskEngine`.
        graph_builder: Dependency graph builder.  Defaults to :class:`DependencyGraphBuilder`.
    """

    def __init__(
        self,
        risk_engine: DeterministicRiskEngine | None = None,
        graph_builder: DependencyGraphBuilder | None = None,
    ) -> None:
        self._risk_engine = risk_engine or DeterministicRiskEngine()
        self._graph_builder = graph_builder or DependencyGraphBuilder()

    def analyze(
        self,
        request: ChangeAnalysisRequest,
        detail_level: str = "standard",
        custom_rules: list | None = None,
    ) -> ChangeAnalysisResult:
        """Run the change-impact analysis pipeline.

        Args:
            request:      The analysis request (changed files, repository context, etc.).
            detail_level: Analysis depth — ``"minimal"``, ``"standard"``, or ``"deep"``.
            custom_rules: Optional list of custom risk rules to apply alongside built-in rules.

        Returns:
            :class:`ChangeAnalysisResult` with risk scores, impacted modules,
            and (depending on *detail_level*) blast radius and flow data.
        """
        if detail_level not in DETAIL_LEVELS:
            logger.warning("Unknown detail_level %r; falling back to 'standard'.", detail_level)
            detail_level = "standard"

        # --- 1. Build dependency graph -----------------------------------------------
        graph = self._graph_builder.from_changed_files(request.changed_files)

        # --- 2. Identify directly impacted modules ------------------------------------
        from app.analysis.module_detector import ModuleDetector
        impacted_modules = ModuleDetector.extract_impacted_modules(request.changed_files)
        if not impacted_modules:
            impacted_modules = sorted(
                {node.label for node in graph.nodes if node.kind in {"module", "service"} and node.label not in {".idea", "gradle", ".vscode"}}
            ) or ["root"]
        critical_modules = [
            path
            for path in request.changed_files
            if any(marker in path.lower() for marker in ("auth", "payment", "db"))
        ]

        # --- 3. Base risk input (always populated) ------------------------------------
        risk_input = RiskInput(
            changed_files=request.changed_files,
            impacted_modules=impacted_modules,
            dependency_count=len(graph.edges),
            missing_tests=not any(
                "test" in path.lower() or "spec" in path.lower()
                for path in request.changed_files
            ),
            large_refactor=len(request.changed_files) >= 15,
            critical_modules=critical_modules,
        )

        # --- 4. Graph-enriched analysis (standard + deep) -----------------------------
        blast_radius_result = None

        if detail_level in ("standard", "deep"):
            risk_input, blast_radius_result = enrich_risk_input_with_graph_analysis(
                graph=graph,
                risk_input=risk_input,
                changed_files=request.changed_files,
                run_flows=(detail_level == "deep"),
            )
            if detail_level == "deep":
                getattr(blast_radius_result, "_flow_result", None)

        # --- 5. Risk scoring ----------------------------------------------------------
        risk = self._risk_engine.score(risk_input, custom_rules=custom_rules)

        # --- 6. Assemble result -------------------------------------------------------
        return ChangeAnalysisResult(
            id=str(uuid4()),
            repository_id=request.repository_id,
            trigger=request.trigger,
            changed_files=request.changed_files,
            impacted_modules=impacted_modules,
            dependency_graph=graph,
            risk=risk,
        )
