"""Comprehensive tests for the Canonical Export Model and ExportService.

Tests cover:
  - Canonical AnalysisExportModel construction & validation
  - PDF generation (multi-page ReportLab, NumberedCanvas, pypdf text extraction)
  - Critical Acceptance Test (anl-8426f2cf / agent-diaries-core: no false empty phrases)
  - JSON schema completeness (all canonical fields preserved)
  - CSV generation (ZIP containing 6 rich CSV datasets)
  - Markdown generation (complete PR report with FACT/INF/REC labels)
  - Repository & analysis isolation
  - Score preservation (exact score preserved across DB round-trip and export formats)
  - Unicode repository and special character filenames
  - Large analysis sets (500+ files)
"""

from __future__ import annotations

import io
import json
import zipfile

import pypdf
import pytest

from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger, RecommendationType, RiskLevel, StatementType
from app.models.export import AnalysisExportModel
from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode, GraphHealth
from app.models.repository import RepositorySummary
from app.models.risk import (
    EvidenceStatement,
    RiskBreakdownItem,
    RiskEvidence,
    RiskResult,
)
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.repository_repo import RepositoryRepository
from app.services.export_service import ExportService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ID = "repo-export-001"
ANALYSIS_ID = "anl-export-001"


def _make_repo(
    repo_id: str = REPO_ID,
    name: str = "agent-diaries-core",
    owner: str = "swapwarick",
) -> RepositorySummary:
    return RepositorySummary(
        id=repo_id,
        name=name,
        owner=owner,
        full_name=f"{owner}/{name}",
        source="github",
        url=f"https://github.com/{owner}/{name}",
        default_branch="main",
        language="TypeScript",
    )


def _make_analysis(
    analysis_id: str = ANALYSIS_ID,
    repository_id: str = REPO_ID,
    score: int = 31,
    changed_files: list[str] | None = None,
) -> ChangeAnalysisResult:
    if changed_files is None:
        changed_files = [
            "GPTverdict.txt",
            "package-lock.json",
            "package.json",
            "tests/fixtures/claim-worker.cjs",
        ]

    evidence = [
        RiskEvidence(
            signal="dependency_upgrades",
            name="Package Dependencies Upgraded",
            category="architecture",
            description="Package manager dependency files modified. (2 matching file(s))",
            weight=0.14,
            score=1.0,
            file_paths=["package-lock.json", "package.json"],
            recommendation="Audit updated dependencies for breaking changes and vulnerability advisories.",
            recommendation_type=RecommendationType.POLICY_BASED,
            threshold="1 file",
            rule="dependency_upgrades",
        ),
        RiskEvidence(
            signal="large_blast_radius",
            name="Large Downstream Blast Radius",
            category="architecture",
            description="5 downstream component dependencies are impacted by this change.",
            weight=0.18,
            score=0.25,
            file_paths=[],
            recommendation="Add regression tests covering downstream consumers and validate in a staging environment.",
            recommendation_type=RecommendationType.POLICY_BASED,
            threshold="> 10 dependencies",
            rule="large_blast_radius",
        ),
    ]

    breakdown = [
        RiskBreakdownItem(
            rule="dependency_upgrades",
            name="Package Dependencies Upgraded",
            category="architecture",
            points=14,
            evidence="Package manager dependency files modified. (2 matching file(s))",
            affected_files=["package-lock.json", "package.json"],
            threshold="1 file",
            recommendation="Audit updated dependencies for breaking changes.",
        ),
        RiskBreakdownItem(
            rule="large_blast_radius",
            name="Large Downstream Blast Radius",
            category="architecture",
            points=5,
            evidence="5 downstream component dependencies are impacted.",
            affected_files=[],
        ),
    ]

    facts = [
        EvidenceStatement(
            id="FACT-001",
            statement_type=StatementType.FACT,
            claim="4 files modified in this change set.",
            source_evidence="Git commit diff analysis",
            affected_files=changed_files,
        ),
        EvidenceStatement(
            id="FACT-002",
            statement_type=StatementType.FACT,
            claim="Package Dependencies Upgraded: Package manager dependency files modified.",
            source_evidence="package.json in changed_files",
            affected_files=["package.json", "package-lock.json"],
        ),
    ]

    inferences = [
        EvidenceStatement(
            id="INF-001",
            statement_type=StatementType.INFERENCE,
            claim="Downstream regression risk: 5 downstream component dependencies are impacted.",
            source_evidence="Derived from dependency graph traversal",
            traceability_ref="large_blast_radius",
        )
    ]

    recs = [
        EvidenceStatement(
            id="REC-001",
            statement_type=StatementType.RECOMMENDATION,
            claim="Audit updated dependencies for breaking changes and vulnerability advisories.",
            recommendation_type=RecommendationType.POLICY_BASED,
            affected_files=["package.json", "package-lock.json"],
        )
    ]

    graph = DependencyGraph(
        nodes=[
            DependencyNode(id="n1", label="package.json", kind="file", path="package.json"),
            DependencyNode(id="n2", label="tests", kind="module", path="tests/fixtures/claim-worker.cjs"),
        ],
        edges=[
            DependencyEdge(id="e1", source="n2", target="n1", relationship="IMPORTS"),
        ],
        graph_health=GraphHealth(
            node_count=193,
            edge_count=420,
            circular_dependency_count=0,
            orphan_candidates=34,
            unresolved_imports=23,
        ),
    )

    risk = RiskResult(
        score=score,
        level=RiskLevel.MEDIUM if score >= 30 else RiskLevel.LOW,
        confidence=0.98,
        evidence_completeness=0.98,
        is_calibrated=False,
        calibration_status="Not statistically calibrated against historical production failure outcomes.",
        score_description="Deterministic change-risk index based on repository evidence.",
        evidence=evidence,
        facts=facts,
        inferences=inferences,
        recommendations=recs,
        risk_breakdown=breakdown,
        reasons=["Package Dependencies Upgraded", "Large Downstream Blast Radius"],
    )

    return ChangeAnalysisResult(
        id=analysis_id,
        repository_id=repository_id,
        trigger=AnalysisTrigger.COMMIT_COMPARISON,
        changed_files=changed_files,
        impacted_modules=["tests"],
        dependency_graph=graph,
        risk=risk,
        ai_report="AI generated report text.",
        parser_version="1.0.0-treesitter",
        graph_version="1.0.0",
        risk_engine_version="1.0.0-deterministic",
        analysis_timestamp="2026-08-18T10:00:00+00:00",
    )


@pytest.fixture
def svc() -> ExportService:
    return ExportService()


@pytest.fixture
def repo() -> RepositorySummary:
    return _make_repo()


@pytest.fixture
def analysis() -> ChangeAnalysisResult:
    return _make_analysis()


@pytest.fixture
def health_metrics() -> dict:
    return {
        "health_score": 67,
        "total_files": 128,
        "potential_orphan_candidates": [".prettierrc.cjs", "examples/basic.ts"],
        "potential_test_gaps": ["examples/basic.ts", "src/storage.ts"],
    }


# ---------------------------------------------------------------------------
# Canonical Export Model Tests
# ---------------------------------------------------------------------------


class TestCanonicalExportModel:
    def test_builds_complete_model(self, analysis, repo, health_metrics):
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)
        assert model.analysis_id == ANALYSIS_ID
        assert model.repository.name == "agent-diaries-core"
        assert model.risk.score == 31
        assert model.risk.level == "MEDIUM"
        assert len(model.risk.breakdown) >= 2
        assert len(model.facts) >= 2
        assert len(model.inferences) >= 1
        assert len(model.recommendations) >= 1
        assert len(model.changed_files) == 4
        assert model.repository_health.health_score == 67
        assert model.graph_health.nodes == 193
        assert model.graph_health.edges == 420
        assert model.graph_health.unresolved_imports == 23

    def test_synthesizes_missing_collections_faithfully(self, repo):
        """When facts/inferences/breakdown are empty, from_analysis synthesizes them faithfully."""
        raw_analysis = _make_analysis()
        raw_analysis.risk.facts = []
        raw_analysis.risk.inferences = []
        raw_analysis.risk.recommendations = []
        raw_analysis.risk.risk_breakdown = []

        model = AnalysisExportModel.from_analysis(raw_analysis, repo)
        assert len(model.risk.breakdown) >= 2
        assert len(model.facts) >= 3
        assert len(model.inferences) >= 1
        assert len(model.recommendations) >= 2


# ---------------------------------------------------------------------------
# Critical Acceptance Test (anl-8426f2cf / agent-diaries-core)
# ---------------------------------------------------------------------------


class TestCriticalAcceptanceAnalysis:
    def test_no_false_empty_statements_in_pdf(self, svc, repo, health_metrics):
        """For agent-diaries-core analysis with score 31, PDF must NOT produce false empty phrases."""
        analysis = _make_analysis(analysis_id="anl-8426f2cf", score=31)
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)

        pdf_bytes = svc.export_pdf(model)
        assert pdf_bytes[:4] == b"%PDF"

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 5, f"Expected multi-page report, got {len(reader.pages)} pages"

        full_text = "\n".join(page.extract_text() for page in reader.pages)

        # 1. Verify absence of all forbidden phrases
        forbidden_phrases = [
            "No risk breakdown available.",
            "No facts recorded.",
            "No inferences recorded.",
            "No recommendations recorded.",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in full_text, f"Forbidden phrase found in generated PDF: '{phrase}'"

        # 2. Verify presence of required analysis evidence
        assert "31/100" in full_text
        assert "MEDIUM" in full_text
        assert "agent-diaries-core" in full_text
        assert "Package Dependencies Upgraded" in full_text
        assert "FACT-001" in full_text
        assert "INF-001" in full_text
        assert "REC-001" in full_text
        assert "package.json" in full_text
        assert "193" in full_text  # graph nodes
        assert "420" in full_text  # graph edges


# ---------------------------------------------------------------------------
# PDF Generation Tests
# ---------------------------------------------------------------------------


class TestPdfExport:
    def test_starts_with_pdf_magic_bytes(self, svc, analysis, repo):
        model = AnalysisExportModel.from_analysis(analysis, repo)
        pdf_bytes = svc.export_pdf(model)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 5000

    def test_multi_page_numbered_canvas(self, svc, analysis, repo, health_metrics):
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)
        pdf_bytes = svc.export_pdf(model)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        assert num_pages >= 5

        # Check running header and footer text
        first_page_text = reader.pages[0].extract_text()
        assert "Page 1 of" in first_page_text or "Page 1" in first_page_text
        assert "Executive Summary" in first_page_text or "What changed?" in first_page_text

    def test_unicode_repo_and_filenames_in_pdf(self, svc):
        unicode_repo = _make_repo(name="日本語-service", owner="会社")
        unicode_analysis = _make_analysis(changed_files=["日本語/файл.py", "src/auth.ts"])
        model = AnalysisExportModel.from_analysis(unicode_analysis, unicode_repo)
        pdf_bytes = svc.export_pdf(model)
        assert pdf_bytes[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# JSON Export Tests
# ---------------------------------------------------------------------------


class TestJsonExport:
    def test_all_canonical_fields_present(self, svc, analysis, repo, health_metrics):
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)
        payload = json.loads(svc.export_json(model))

        required_keys = {
            "analysis_id", "repository", "branch", "risk", "facts", "inferences",
            "recommendations", "failure_scenarios", "changed_files", "blast_radius",
            "architecture_findings", "security_findings", "test_findings",
            "repository_health", "rollback_considerations", "graph_health",
            "reviewer_evidence", "metadata", "export_format", "export_timestamp"
        }
        for k in required_keys:
            assert k in payload, f"Missing key in JSON export: {k}"

        assert payload["risk"]["score"] == 31
        assert payload["risk"]["level"] == "MEDIUM"
        assert len(payload["risk"]["breakdown"]) >= 2
        assert len(payload["facts"]) >= 2
        assert len(payload["inferences"]) >= 1
        assert len(payload["recommendations"]) >= 1


# ---------------------------------------------------------------------------
# CSV Export Tests
# ---------------------------------------------------------------------------


class TestCsvExport:
    def _read_zip(self, data: bytes) -> dict[str, str]:
        zf = zipfile.ZipFile(io.BytesIO(data))
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}

    def test_contains_six_csv_files_with_headers(self, svc, analysis, repo, health_metrics):
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)
        files = self._read_zip(svc.export_csv(model))

        expected = {
            "risk_factors.csv", "changed_files.csv", "impacted_files.csv",
            "dependencies.csv", "test_gaps.csv", "repository_metrics.csv",
        }
        assert expected == set(files.keys())

        # Check risk_factors
        rf = files["risk_factors.csv"]
        assert "rule" in rf and "points" in rf and "evidence" in rf
        assert "dependency_upgrades" in rf

        # Check repository_metrics
        rm = files["repository_metrics.csv"]
        assert "risk_score,31" in rm or "31" in rm
        assert "agent-diaries-core" in rm


# ---------------------------------------------------------------------------
# Markdown Export Tests
# ---------------------------------------------------------------------------


class TestMarkdownExport:
    def test_contains_all_eleven_sections(self, svc, analysis, repo, health_metrics):
        model = AnalysisExportModel.from_analysis(analysis, repo, health_metrics=health_metrics)
        text = svc.export_markdown(model).decode("utf-8")

        expected_sections = [
            "## Executive Summary",
            "## 1. Risk Breakdown",
            "## 2. Directly Observed Facts",
            "## 3. Deterministic Inferences",
            "## 4. Recommendations",
            "## 5. Blast Radius",
            "## 6. Changed Files Detail",
            "## 7. Graph Structure & Health Diagnostics",
            "## 8. Architecture & Security Findings",
            "## 9. Repository Health",
            "## 10. Rollback & Reviewer Evidence",
            "## 11. Analysis Metadata",
        ]
        for sec in expected_sections:
            assert sec in text, f"Missing section in Markdown export: {sec}"

        assert "`FACT`" in text
        assert "`INFERENCE`" in text
        assert "`RECOMMENDATION`" in text
        assert "31/100" in text


# ---------------------------------------------------------------------------
# DB Persistence & Isolation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_round_trip_preserves_complete_evidence(async_session):
    """Analysis saved to DB must preserve complete RiskResult when retrieved."""
    a = _make_analysis(score=42)
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)

    assert fetched is not None
    assert fetched.risk.score == 42
    assert len(fetched.risk.risk_breakdown) >= 2
    assert len(fetched.risk.facts) >= 2
    assert len(fetched.risk.inferences) >= 1
    assert len(fetched.risk.recommendations) >= 1


@pytest.mark.asyncio
async def test_repository_isolation_guard(async_session):
    """RepositoryRepository and AnalysisRepository enforce repository boundaries."""
    a1 = _make_analysis(analysis_id="anl-A", repository_id="repo-Alpha")
    a2 = _make_analysis(analysis_id="anl-B", repository_id="repo-Beta")

    ar = AnalysisRepository(async_session)
    await ar.save(a1)
    await ar.save(a2)

    res_alpha = await ar.list_by_repository("repo-Alpha")
    assert len(res_alpha) == 1
    assert res_alpha[0].id == "anl-A"

    res_beta = await ar.list_by_repository("repo-Beta")
    assert len(res_beta) == 1
    assert res_beta[0].id == "anl-B"


# ---------------------------------------------------------------------------
# Large Analysis & Edge Cases
# ---------------------------------------------------------------------------


def test_large_analysis_export(svc, repo):
    """Exporting an analysis with 500+ files must succeed across all 4 formats."""
    large_files = [f"src/module_{i}/file_{j}.ts" for i in range(50) for j in range(10)]
    a = _make_analysis(changed_files=large_files)
    model = AnalysisExportModel.from_analysis(a, repo)

    json_bytes = svc.export_json(model)
    assert len(json_bytes) > 1000

    csv_bytes = svc.export_csv(model)
    assert zipfile.is_zipfile(io.BytesIO(csv_bytes))

    md_bytes = svc.export_markdown(model)
    assert len(md_bytes) > 1000

    pdf_bytes = svc.export_pdf(model)
    assert pdf_bytes[:4] == b"%PDF"
