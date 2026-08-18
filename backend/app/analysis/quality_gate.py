"""Analysis Quality Gate & Epistemological Health Evaluator for ChangePilot.

Enforces the Fail-Closed Principle:
  MISSING EVIDENCE != ZERO FINDINGS
  UNKNOWN != 0
  UNAVAILABLE != 0
  PARSER FAILURE != HEALTHY
  EMPTY GRAPH != HEALTHY GRAPH

Calculates deterministic evidence completeness and controls metric availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QualityGateResult:
    analysis_quality: str  # FULL, DEGRADED, FAILED
    graph_status: str  # VALID, DEGRADED, FAILED, UNAVAILABLE
    evidence_completeness: float  # 0.0 to 1.0
    health_status: str  # AVAILABLE, DEGRADED, UNAVAILABLE
    parser_health: str  # PASS, PARTIAL, FAIL, UNAVAILABLE
    diff_status: str = "PASS"
    inventory_status: str = "PASS"
    blast_radius_status: str = "PASS"  # PASS, UNAVAILABLE
    test_analysis_status: str = "PASS"
    coverage_status: str = "UNAVAILABLE"
    warnings: list[str] = field(default_factory=list)
    explanation: str = ""


class AnalysisQualityGate:
    """Evaluates the structural integrity of repository code parsing and graph construction."""

    @staticmethod
    def evaluate(
        files_discovered: int,
        supported_source_files: int,
        files_parsed: int,
        files_failed: int,
        ast_nodes: int,
        dependency_edges: int,
        has_git_diff: bool = True,
        has_test_analysis: bool = True,
    ) -> QualityGateResult:
        warnings: list[str] = []

        # 1. Pipeline Stage Scores
        s_diff = 1.0 if has_git_diff else 0.0
        s_inv = 1.0 if files_discovered > 0 else 0.0

        # Parser Health
        if supported_source_files == 0:
            s_ast = 1.0 if files_discovered > 0 else 0.0
            parser_health = "N/A" if files_discovered > 0 else "FAIL"
        else:
            parse_ratio = files_parsed / float(supported_source_files)
            if parse_ratio >= 0.8 and files_failed == 0:
                s_ast = 1.0
                parser_health = "PASS"
            elif parse_ratio >= 0.3:
                s_ast = 0.5
                parser_health = "PARTIAL"
                warnings.append(f"Parser parsed {files_parsed} of {supported_source_files} source files ({files_failed} failed).")
            else:
                s_ast = 0.0
                parser_health = "FAIL"
                warnings.append(f"Language parser failed to extract AST for {supported_source_files} source files.")

        # Graph Health
        if supported_source_files > 0 and (ast_nodes <= 1 or s_ast == 0.0):
            s_graph = 0.0
            s_blast = 0.0
            graph_status = "FAILED"
            blast_status = "UNAVAILABLE"
            health_status = "UNAVAILABLE"
            warnings.append("Dependency graph incomplete — language AST extraction failed.")
        elif supported_source_files > 0 and files_failed > 0:
            s_graph = 0.6
            s_blast = 0.6
            graph_status = "DEGRADED"
            blast_status = "PASS"
            health_status = "DEGRADED"
        else:
            s_graph = 1.0
            s_blast = 1.0
            graph_status = "VALID"
            blast_status = "PASS"
            health_status = "AVAILABLE"

        s_test = 1.0 if has_test_analysis else 0.0

        # 2. Epistemological Evidence Completeness Formula
        completeness = (
            0.20 * s_diff
            + 0.10 * s_inv
            + 0.25 * s_ast
            + 0.20 * s_graph
            + 0.15 * s_blast
            + 0.10 * s_test
        )
        completeness = round(max(min(completeness, 0.98), 0.10), 2)

        # 3. Overall Analysis Quality Rating
        if completeness >= 0.90 and graph_status == "VALID":
            analysis_quality = "FULL"
            explanation = "Complete deterministic evidence from Git diff, multi-language AST, and dependency graph topology."
        elif completeness >= 0.45:
            analysis_quality = "DEGRADED"
            explanation = "Analysis quality is degraded: AST parsing or graph topology is partial; risk score derived from Git diff."
        else:
            analysis_quality = "FAILED"
            explanation = "Core language parsing failed. Source dependency analysis and health scoring are unavailable."

        return QualityGateResult(
            analysis_quality=analysis_quality,
            graph_status=graph_status,
            evidence_completeness=completeness,
            health_status=health_status,
            parser_health=parser_health,
            diff_status="PASS" if has_git_diff else "FAIL",
            inventory_status="PASS" if files_discovered > 0 else "FAIL",
            blast_radius_status=blast_status,
            test_analysis_status="PASS" if has_test_analysis else "FAIL",
            coverage_status="UNAVAILABLE",
            warnings=warnings,
            explanation=explanation,
        )
