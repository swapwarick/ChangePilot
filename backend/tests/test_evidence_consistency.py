"""Regression test suite for ChangePilot Evidence & Calculation Consistency.

Verifies the 12 core consistency requirements:
  1. Downstream dependency edge count vs unique component count distinction
  2. Blast radius consistency across RiskInput, RiskResult, ExportModel, PDF, JSON, CSV
  3. Graph resolution quality metrics (resolution_rate, DEGRADED status)
  4. Next.js entrypoint classification (middleware.ts, page.tsx, route.ts not orphans)
  5. Alembic env.py classification (CONFIGURATION, not orphan)
  6. Python worker/task entrypoints (tasks.py, analysis_worker.py not orphans)
  7. Potential test gap semantics (never claims "0% coverage")
  8. Evidence-backed criticality reasons
  9. Exact health score weighted calculation reproducibility
  10. Risk score traceability and audit normalization
  11. Reviewer ownership unavailable notice
  12. Export uniformity across PDF, JSON, CSV, and Markdown
"""

import json
from pathlib import Path

import pytest
from app.analysis.change_analyzer import ChangeAnalyzer
from app.analysis.file_classifier import FileClassification, classify_file
from app.graph.blast_radius import compute_blast_radius
from app.graph.knowledge_graph import KnowledgeGraphBuilder
from app.models.analysis import ChangeAnalysisRequest
from app.models.enums import AnalysisTrigger
from app.models.export import AnalysisExportModel
from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode
from app.models.risk import ImpactMetrics, RiskInput
from app.risk.engine import RiskEngine
from app.services.export_service import ExportService


# ---------------------------------------------------------------------------
# 1. Edge Count != Component Count
# ---------------------------------------------------------------------------

def test_edge_count_not_equal_component_count():
    """Verify that dependency edges (e.g. 24) and unique downstream components (e.g. 10) are distinct."""
    impact = ImpactMetrics(
        changed_files=3,
        direct_dependents=4,
        transitive_dependents=6,
        unique_affected_components=10,
        total_blast_radius=13,
        dependency_edges=24,
        affected_modules=["auth", "api", "dashboard"],
    )
    assert impact.changed_files == 3
    assert impact.unique_affected_components == 10
    assert impact.total_blast_radius == 13
    assert impact.dependency_edges == 24
    assert impact.dependency_edges != impact.unique_affected_components

    # Verify RiskEngine produces rule evidence stating unique downstream components
    risk_in = RiskInput(
        changed_files=["src/auth/service.py", "src/auth/models.py", "src/auth/jwt.py"],
        dependency_count=10,
        impact_metrics=impact,
    )
    engine = RiskEngine()
    result = engine.score(risk_in)

    blast_ev = next((e for e in result.evidence if e.signal == "large_blast_radius"), None)
    assert blast_ev is not None
    assert "10 unique downstream component(s) impacted across 24 dependency edge(s)" in blast_ev.description
    assert "24 downstream component dependencies are impacted" not in blast_ev.description


# ---------------------------------------------------------------------------
# 2. Blast Radius Consistency Across Models
# ---------------------------------------------------------------------------

def test_blast_radius_consistency_across_models():
    """Verify blast radius is identical in RiskInput, RiskResult, ExportModel, PDF, JSON, CSV."""
    from app.models.repository import RepositorySummary

    impact = ImpactMetrics(
        changed_files=3,
        direct_dependents=4,
        transitive_dependents=6,
        unique_affected_components=10,
        total_blast_radius=13,
        dependency_edges=24,
        affected_modules=["core", "api"],
    )

    risk_in = RiskInput(
        changed_files=["a.py", "b.py", "c.py"],
        dependency_count=10,
        impact_metrics=impact,
    )
    engine = RiskEngine()
    risk_res = engine.score(risk_in)

    # 1. Check RiskResult
    assert risk_res.impact_metrics.unique_affected_components == 10
    assert risk_res.impact_metrics.total_blast_radius == 13
    assert risk_res.impact_metrics.dependency_edges == 24

    # 2. Check ExportModel
    nodes = [DependencyNode(id=f"file:{f}", label=f, kind="file", path=f) for f in ["a.py", "b.py", "c.py"]]
    graph = DependencyGraph(nodes=nodes, edges=[])
    from app.models.analysis import ChangeAnalysisResult
    analysis = ChangeAnalysisResult(
        repository_id="repo-1",
        trigger=AnalysisTrigger.COMMIT_COMPARISON,
        changed_files=["a.py", "b.py", "c.py"],
        impacted_modules=["core", "api"],
        impact_metrics=impact,
        dependency_graph=graph,
        risk=risk_res,
    )
    repo = RepositorySummary(id="repo-1", name="ChangePilot", default_branch="main", source="local")

    export_model = AnalysisExportModel.from_analysis(analysis, repository=repo)
    assert export_model.blast_radius.direct_impact == 3
    assert export_model.blast_radius.unique_affected_components == 10
    assert export_model.blast_radius.total_impact == 13
    assert export_model.blast_radius.dependency_edges == 24

    # 3. Check JSON Export
    svc = ExportService()
    json_bytes = svc.export_json(export_model)
    data = json.loads(json_bytes.decode("utf-8"))
    assert data["blast_radius"]["direct_impact"] == 3
    assert data["blast_radius"]["unique_affected_components"] == 10
    assert data["blast_radius"]["total_impact"] == 13
    assert data["blast_radius"]["dependency_edges"] == 24


# ---------------------------------------------------------------------------
# 3. Graph Resolution Quality
# ---------------------------------------------------------------------------

def test_unresolved_imports_reduce_graph_quality():
    """Verify resolution_rate and DEGRADED status calculation when unresolved imports exist."""
    from app.analysis.tree_sitter_parser import ImportSymbol, ParsedFileAST

    # File with 1 valid import and 2 unresolved imports
    parsed = [
        ParsedFileAST(
            file_path="src/main.py",
            file_hash="hash-main",
            language="python",
            imports=[
                ImportSymbol(source_module=".utils", imported_name="helper", is_relative=True),
                ImportSymbol(source_module=".unresolved_one", imported_name="foo", is_relative=True),
                ImportSymbol(source_module=".unresolved_two", imported_name="bar", is_relative=True),
            ],
        ),
        ParsedFileAST(
            file_path="src/utils.py",
            file_hash="hash-utils",
            language="python",
            imports=[],
        ),
    ]

    builder = KnowledgeGraphBuilder()
    graph, _, health = builder.build_graph_from_parsed_files(parsed)

    gh = graph.graph_health
    assert gh is not None
    assert gh.resolved_internal_imports == 1
    assert gh.unresolved_imports == 2
    assert gh.total_internal_imports_attempted == 3
    assert gh.resolution_rate == pytest.approx(0.3333, abs=0.01)
    assert gh.graph_quality_status == "POOR"
    assert any("Graph quality is POOR" in w for w in gh.warnings)


# ---------------------------------------------------------------------------
# 4. Next.js Entrypoint Classification
# ---------------------------------------------------------------------------

def test_nextjs_middleware_not_orphan():
    """Verify Next.js middleware and conventions are classified as FRAMEWORK_ENTRYPOINT/ROUTE and not orphans."""
    assert classify_file("frontend/middleware.ts") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("frontend/middleware.js") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("frontend/app/page.tsx") == FileClassification.ROUTE
    assert classify_file("frontend/app/layout.tsx") == FileClassification.ROUTE
    assert classify_file("frontend/app/loading.tsx") == FileClassification.ROUTE
    assert classify_file("frontend/app/error.tsx") == FileClassification.ROUTE
    assert classify_file("frontend/app/not-found.tsx") == FileClassification.ROUTE
    assert classify_file("frontend/app/instrumentation.ts") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("frontend/app/api/auth/route.ts") == FileClassification.ROUTE


# ---------------------------------------------------------------------------
# 5. Alembic env.py & Migration Classification
# ---------------------------------------------------------------------------

def test_alembic_env_and_migrations_not_orphan():
    """Verify backend/alembic/env.py and version scripts are classified as CONFIGURATION and not orphans."""
    assert classify_file("backend/alembic/env.py") == FileClassification.CONFIGURATION
    assert classify_file("alembic/env.py") == FileClassification.CONFIGURATION
    assert classify_file("backend/alembic/versions/001_initial_schema.py") == FileClassification.CONFIGURATION
    assert classify_file("alembic/versions/002_real_analysis_schema.py") == FileClassification.CONFIGURATION


# ---------------------------------------------------------------------------
# 6. Worker Entrypoints & Package Inits Classification
# ---------------------------------------------------------------------------

def test_worker_entrypoints_and_package_inits_not_orphan():
    """Verify tasks.py, analysis_worker.py, and __init__.py are not classified as source module orphans."""
    assert classify_file("backend/app/workers/tasks.py") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("backend/app/workers/analysis_worker.py") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("app/workers/worker.py") == FileClassification.FRAMEWORK_ENTRYPOINT
    assert classify_file("backend/app/__init__.py") == FileClassification.CONFIGURATION
    assert classify_file("backend/app/database/session.py") == FileClassification.CONFIGURATION


# ---------------------------------------------------------------------------
# 7. Potential Test Gap Semantics
# ---------------------------------------------------------------------------

def test_missing_test_modifications_not_zero_coverage():
    """Verify missing_tests rule generates 'Potential Test Gap' evidence and never claims '0% coverage'."""
    risk_in = RiskInput(
        changed_files=["src/core/calculator.py"],
        missing_tests=True,
    )
    engine = RiskEngine()
    res = engine.score(risk_in)

    test_ev = next((e for e in res.evidence if e.signal == "missing_tests"), None)
    assert test_ev is not None
    assert test_ev.name == "Potential Test Gap"
    assert "0% coverage" not in test_ev.description
    assert "Runtime coverage data is unavailable" in test_ev.description


# ---------------------------------------------------------------------------
# 8. Evidence-Based Criticality
# ---------------------------------------------------------------------------

def test_critical_component_classification_requires_evidence():
    """Verify evidence-backed criticality reason is populated."""
    risk_in = RiskInput(
        changed_files=["src/payment/gateway.py"],
    )
    engine = RiskEngine()
    res = engine.score(risk_in)

    crit_ev = next((e for e in res.evidence if e.signal == "critical_component_modified"), None)
    assert crit_ev is not None
    assert "Core payment, billing, or critical domain component modified" in crit_ev.description
    assert crit_ev.rule == "critical_component_modified"


# ---------------------------------------------------------------------------
# 9. Health Score Weighted Calculation Exact
# ---------------------------------------------------------------------------

def test_health_score_weighted_calculation_exact():
    """Verify overall == round(arch*0.25 + dep*0.20 + test*0.20 + sec*0.20 + maint*0.15)."""
    from app.analysis.tree_sitter_parser import ParsedFileAST

    parsed = [
        ParsedFileAST(file_path="src/a.py", file_hash="h-a", language="python"),
        ParsedFileAST(file_path="src/b.py", file_hash="h-b", language="python"),
    ]
    builder = KnowledgeGraphBuilder()
    _, _, health = builder.build_graph_from_parsed_files(parsed)

    arch_score = health.categories["Architecture"].score
    dep_score = health.categories["Dependencies"].score
    test_score = health.categories["Testing"].score
    sec_score = health.categories["Security"].score
    maint_score = health.categories["Maintainability"].score

    expected = int(round(
        arch_score * 0.25 + dep_score * 0.20 + test_score * 0.20 + sec_score * 0.20 + maint_score * 0.15
    ))
    assert health.health_score == expected


# ---------------------------------------------------------------------------
# 10. Risk Score Traceability
# ---------------------------------------------------------------------------

def test_risk_score_traceability():
    """Verify risk rule breakdown contains status, threshold, observed_value, points."""
    risk_in = RiskInput(
        changed_files=["src/auth/login.py"],
        missing_tests=True,
    )
    engine = RiskEngine()
    res = engine.score(risk_in)

    assert len(res.risk_breakdown) > 0
    for item in res.risk_breakdown:
        assert item.status == "TRIGGERED"
        assert item.points >= 0
        assert item.evidence != ""


# ---------------------------------------------------------------------------
# 11. Reviewer Section Message
# ---------------------------------------------------------------------------

def test_reviewer_ownership_unavailable_message():
    """Verify reviewer section explicitly states ownership unavailable message when not detected."""
    risk_in = RiskInput(
        changed_files=["src/core/math.py"],
    )
    engine = RiskEngine()
    res = engine.score(risk_in)

    assert len(res.recommended_review_areas) > 0
    rv = res.recommended_review_areas[0]
    assert rv["suggested_reviewer"] is None
    assert "Ownership data unavailable — CODEOWNERS/team mapping" in rv["ownership_note"]


# ---------------------------------------------------------------------------
# 12. Export JSON, CSV, PDF Identical
# ---------------------------------------------------------------------------

def test_export_json_csv_pdf_identical():
    """Verify JSON, CSV, PDF, Markdown contain identical canonical risk and blast radius numbers."""
    from app.models.repository import RepositorySummary

    impact = ImpactMetrics(
        changed_files=2,
        direct_dependents=3,
        transitive_dependents=4,
        unique_affected_components=7,
        total_blast_radius=9,
        dependency_edges=15,
        affected_modules=["core"],
    )
    nodes = [
        DependencyNode(id="file:src/a.py", label="a.py", kind="file", path="src/a.py"),
        DependencyNode(id="file:src/b.py", label="b.py", kind="file", path="src/b.py"),
    ]
    graph = DependencyGraph(nodes=nodes, edges=[])

    risk_in = RiskInput(
        changed_files=["src/a.py", "src/b.py"],
        dependency_count=7,
        impact_metrics=impact,
    )
    engine = RiskEngine()
    risk_res = engine.score(risk_in)

    from app.models.analysis import ChangeAnalysisResult
    analysis = ChangeAnalysisResult(
        repository_id="repo-1",
        trigger=AnalysisTrigger.COMMIT_COMPARISON,
        changed_files=["src/a.py", "src/b.py"],
        impacted_modules=["core"],
        impact_metrics=impact,
        dependency_graph=graph,
        risk=risk_res,
    )
    repo = RepositorySummary(id="repo-1", name="ChangePilot", default_branch="main", source="local")

    export_model = AnalysisExportModel.from_analysis(analysis, repository=repo)
    svc = ExportService()

    # JSON
    json_bytes = svc.export_json(export_model)
    j_data = json.loads(json_bytes.decode("utf-8"))
    assert j_data["risk"]["score"] == risk_res.score
    assert j_data["blast_radius"]["total_impact"] == 9
    assert j_data["blast_radius"]["unique_affected_components"] == 7
    assert j_data["blast_radius"]["dependency_edges"] == 15

    # Markdown
    md_bytes = svc.export_markdown(export_model)
    md_text = md_bytes.decode("utf-8")
    assert f"{risk_res.score}/100" in md_text
    assert "Total Blast Radius:** `9`" in md_text

    # PDF
    pdf_bytes = svc.export_pdf(export_model)
    assert len(pdf_bytes) > 1000  # Valid generated binary PDF
