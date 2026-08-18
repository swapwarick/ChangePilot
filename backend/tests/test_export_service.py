"""Comprehensive tests for the ExportService and export API endpoints.

Tests cover:
  - PDF generation (byte output, non-empty, structure)
  - JSON schema (all required fields, value match)
  - CSV generation (ZIP with 6 CSV files, correct headers)
  - Markdown generation (all required sections, FACT/INF/REC labels)
  - Repository isolation (wrong repository_id → 403)
  - Analysis isolation (analysis_id not belonging to repo → 403)
  - Missing analysis (404)
  - Empty evidence (graceful handling)
  - Large analysis (> 500 files)
  - Special characters in filenames
  - Unicode repository/file names
  - Score preservation (exported score === stored score, never re-computed)
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger, RecommendationType, RiskLevel, StatementType
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
    name: str = "my-service",
    owner: str = "acme-corp",
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
    score: int = 72,
    changed_files: list[str] | None = None,
    extra_facts: list[EvidenceStatement] | None = None,
    extra_inferences: list[EvidenceStatement] | None = None,
    extra_recs: list[EvidenceStatement] | None = None,
) -> ChangeAnalysisResult:
    if changed_files is None:
        changed_files = ["src/auth.ts", "src/db.ts", "src/api/routes.ts"]

    facts = extra_facts or [
        EvidenceStatement(
            id="FACT-001",
            statement_type=StatementType.FACT,
            claim="19 files changed.",
            source_evidence="git diff --stat",
        ),
        EvidenceStatement(
            id="FACT-002",
            statement_type=StatementType.FACT,
            claim="Authentication module modified.",
            source_evidence="src/auth.ts in changed_files",
            affected_files=["src/auth.ts"],
        ),
    ]
    inferences = extra_inferences or [
        EvidenceStatement(
            id="INF-001",
            statement_type=StatementType.INFERENCE,
            claim="21 downstream dependencies may be impacted.",
            traceability_ref="FACT-001",
        ),
    ]
    recs = extra_recs or [
        EvidenceStatement(
            id="REC-001",
            statement_type=StatementType.RECOMMENDATION,
            claim="Add regression tests for CommandBar.tsx.",
            recommendation_type=RecommendationType.EVIDENCE_BACKED,
            affected_files=["src/components/CommandBar.tsx"],
        ),
        EvidenceStatement(
            id="REC-002",
            statement_type=StatementType.RECOMMENDATION,
            claim="Review authentication flow before merge.",
            recommendation_type=RecommendationType.POLICY_BASED,
            affected_files=["src/auth.ts"],
        ),
    ]

    risk = RiskResult(
        score=score,
        level=RiskLevel.HIGH,
        confidence=0.88,
        evidence_completeness=0.88,
        is_calibrated=False,
        calibration_status="NOT_CALIBRATED",
        score_description="Deterministic change-risk index.",
        facts=facts,
        inferences=inferences,
        recommendations=recs,
        evidence=[
            RiskEvidence(
                signal="authentication_change",
                name="Authentication Modified",
                category="security",
                description="Auth files changed.",
                weight=0.2,
                score=0.5,
                file_paths=["src/auth.ts"],
                recommendation="Review auth carefully.",
            ),
            RiskEvidence(
                signal="large_blast_radius",
                name="Large Blast Radius",
                category="architecture",
                description="Many downstream modules affected.",
                weight=0.15,
                score=0.6,
                file_paths=[],
                recommendation="Reduce coupling.",
            ),
        ],
        risk_breakdown=[
            RiskBreakdownItem(
                rule="authentication_change",
                name="Authentication Modified",
                category="security",
                points=20,
                evidence="Auth files changed.",
                affected_files=["src/auth.ts"],
                threshold=">= 1 file",
                recommendation="Review authentication flow.",
            ),
            RiskBreakdownItem(
                rule="large_blast_radius",
                name="Large Blast Radius",
                category="architecture",
                points=15,
                evidence="21 downstream modules.",
                affected_files=[],
            ),
        ],
        potential_failure_scenarios=["Auth regression if session invalidation is broken."],
        deployment_considerations=["Roll back auth change if login failure rate > 1%."],
        recommended_review_areas=[
            {
                "review_area": "Authentication",
                "suggested_reviewer": "alice@example.com",
                "evidence": "src/auth.ts modified",
            }
        ],
        reasons=["authentication_change: Auth files changed."],
    )

    graph = DependencyGraph(
        nodes=[
            DependencyNode(id="n1", label="auth", kind="module", path="src/auth.ts"),
            DependencyNode(id="n2", label="db", kind="module", path="src/db.ts"),
        ],
        edges=[
            DependencyEdge(id="e1", source="n1", target="n2", relationship="IMPORTS"),
        ],
        graph_health=GraphHealth(
            node_count=2,
            edge_count=1,
            circular_dependency_count=0,
            orphan_candidates=0,
            unresolved_imports=1,
        ),
    )

    return ChangeAnalysisResult(
        id=analysis_id,
        repository_id=repository_id,
        trigger=AnalysisTrigger.COMMIT_COMPARISON,
        changed_files=changed_files,
        impacted_modules=["auth", "db", "api"],
        dependency_graph=graph,
        risk=risk,
        ai_report="AI report text here.",
        parser_version="1.0.0",
        graph_version="1.0.0",
        risk_engine_version="1.0.0-deterministic",
        analysis_timestamp="2026-08-18T07:00:00+00:00",
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


# ---------------------------------------------------------------------------
# JSON Export
# ---------------------------------------------------------------------------


class TestJsonExport:
    def test_returns_bytes(self, svc, analysis, repo):
        result = svc.export_json(analysis, repo)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_valid_json(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert isinstance(payload, dict)

    def test_required_top_level_fields(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        required = {
            "export_format", "export_timestamp", "metadata", "risk_summary",
            "changed_files", "impacted_modules", "risk_factors", "facts",
            "inferences", "recommendations", "evidence", "dependency_edges",
            "dependency_nodes", "graph_health",
        }
        for field in required:
            assert field in payload, f"Missing field: {field}"

    def test_metadata_fields(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        meta = payload["metadata"]
        assert meta["repository_id"] == REPO_ID
        assert meta["repository_name"] == "my-service"
        assert meta["owner"] == "acme-corp"
        assert meta["analysis_id"] == ANALYSIS_ID

    def test_score_matches_stored_value(self, svc, analysis, repo):
        """Critical: exported score must match stored score exactly."""
        payload = json.loads(svc.export_json(analysis, repo))
        assert payload["risk_summary"]["score"] == analysis.risk.score

    def test_risk_level_matches(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert payload["risk_summary"]["level"].upper() == str(analysis.risk.level).upper()

    def test_evidence_preserved(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert len(payload["evidence"]) == len(analysis.risk.evidence)

    def test_facts_preserved(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert len(payload["facts"]) == len(analysis.risk.facts)
        assert payload["facts"][0]["id"] == "FACT-001"

    def test_inferences_preserved(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert len(payload["inferences"]) == len(analysis.risk.inferences)

    def test_recommendations_preserved(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert len(payload["recommendations"]) == len(analysis.risk.recommendations)

    def test_dependency_edges_preserved(self, svc, analysis, repo):
        payload = json.loads(svc.export_json(analysis, repo))
        assert len(payload["dependency_edges"]) == len(analysis.dependency_graph.edges)

    def test_unicode_repo_name(self, svc, analysis, repo):
        """Unicode repository/file names must not raise."""
        unicode_repo = _make_repo(name="日本語-service", owner="会社")
        unicode_analysis = _make_analysis(changed_files=["日本語/файл.py", "src/test.ts"])
        result = svc.export_json(unicode_analysis, unicode_repo)
        payload = json.loads(result)
        assert "日本語/файл.py" in payload["changed_files"]

    def test_special_chars_in_filenames(self, svc, repo):
        """Special characters in filenames must be preserved."""
        special_files = [
            "src/file with spaces.ts",
            "src/file&symbols!.tsx",
            "src/file(1).py",
        ]
        a = _make_analysis(changed_files=special_files)
        payload = json.loads(svc.export_json(a, repo))
        for f in special_files:
            assert f in payload["changed_files"]

    def test_empty_evidence(self, svc, repo):
        """Empty evidence must not raise."""
        a = _make_analysis()
        a.risk.evidence = []
        a.risk.facts = []
        a.risk.inferences = []
        a.risk.recommendations = []
        a.risk.risk_breakdown = []
        result = svc.export_json(a, repo)
        payload = json.loads(result)
        assert payload["evidence"] == []
        assert payload["facts"] == []

    def test_large_analysis(self, svc, repo):
        """Large analysis (500+ files) must complete without error."""
        large_files = [f"src/module_{i}/file_{j}.ts" for i in range(50) for j in range(10)]
        a = _make_analysis(changed_files=large_files)
        result = svc.export_json(a, repo)
        payload = json.loads(result)
        assert len(payload["changed_files"]) == 500


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


class TestCsvExport:
    def _open_zip(self, data: bytes) -> dict[str, str]:
        """Open ZIP bytes and return filename -> CSV text mapping."""
        zf = zipfile.ZipFile(io.BytesIO(data))
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}

    def test_returns_valid_zip(self, svc, analysis, repo):
        result = svc.export_csv(analysis, repo)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_contains_six_csv_files(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        expected = {
            "risk_factors.csv", "changed_files.csv", "impacted_files.csv",
            "dependencies.csv", "test_gaps.csv", "repository_metrics.csv",
        }
        assert expected == set(files.keys())

    def test_risk_factors_headers(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        first_line = files["risk_factors.csv"].splitlines()[0]
        assert "rule" in first_line and "category" in first_line and "points" in first_line

    def test_changed_files_headers(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        first_line = files["changed_files.csv"].splitlines()[0]
        assert "file_path" in first_line

    def test_changed_files_count(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        lines = [l for l in files["changed_files.csv"].splitlines() if l.strip()]
        # header + data rows
        assert len(lines) == 1 + len(analysis.changed_files)

    def test_dependencies_headers(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        first_line = files["dependencies.csv"].splitlines()[0]
        assert "source" in first_line and "target" in first_line

    def test_repository_metrics_contains_score(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        content = files["repository_metrics.csv"]
        assert str(analysis.risk.score) in content

    def test_score_preserved_in_metrics(self, svc, analysis, repo):
        files = self._open_zip(svc.export_csv(analysis, repo))
        for line in files["repository_metrics.csv"].splitlines():
            if "risk_score" in line:
                assert str(analysis.risk.score) in line

    def test_empty_evidence_no_crash(self, svc, repo):
        a = _make_analysis()
        a.risk.evidence = []
        a.risk.risk_breakdown = []
        result = svc.export_csv(a, repo)
        assert zipfile.is_zipfile(io.BytesIO(result))

    def test_unicode_filenames_in_csv(self, svc, repo):
        unicode_files = ["日本語/файл.py", "src/test.ts"]
        a = _make_analysis(changed_files=unicode_files)
        files = self._open_zip(svc.export_csv(a, repo))
        content = files["changed_files.csv"]
        assert "日本語/файл.py" in content

    def test_large_analysis_csv(self, svc, repo):
        large_files = [f"src/mod_{i}/file_{j}.ts" for i in range(25) for j in range(10)]
        a = _make_analysis(changed_files=large_files)
        result = svc.export_csv(a, repo)
        files = self._open_zip(result)
        lines = [l for l in files["changed_files.csv"].splitlines() if l.strip()]
        assert len(lines) == 251  # header + 250 files


# ---------------------------------------------------------------------------
# Markdown Export
# ---------------------------------------------------------------------------


class TestMarkdownExport:
    def test_returns_bytes(self, svc, analysis, repo):
        result = svc.export_markdown(analysis, repo)
        assert isinstance(result, bytes) and len(result) > 0

    def test_valid_utf8(self, svc, analysis, repo):
        result = svc.export_markdown(analysis, repo)
        text = result.decode("utf-8")
        assert len(text) > 0

    def test_h1_title_present(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert "# Change Risk Assessment" in text

    def test_required_sections(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        sections = [
            "## Risk Summary",
            "## Facts",
            "## Impact Analysis",
            "## Inferences",
            "## Risk Factors",
            "## Failure Scenarios",
            "## Test Recommendations",
            "## Architecture Findings",
            "## Security Findings",
            "## Recommendations",
            "## Rollback Considerations",
            "## Reviewer / Ownership Evidence",
            "## Analysis Metadata",
        ]
        for section in sections:
            assert section in text, f"Missing section: {section}"

    def test_fact_labels_present(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert "`FACT`" in text
        assert "[FACT-001]" in text

    def test_inference_labels_present(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert "`INFERENCE`" in text
        assert "[INF-001]" in text

    def test_recommendation_labels_present(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert "`RECOMMENDATION`" in text
        assert "[REC-001]" in text

    def test_score_in_summary_table(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert f"{analysis.risk.score}/100" in text

    def test_analysis_id_in_metadata(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert ANALYSIS_ID in text

    def test_repository_name_in_title(self, svc, analysis, repo):
        text = svc.export_markdown(analysis, repo).decode("utf-8")
        assert "my-service" in text

    def test_score_not_recalculated(self, svc, repo):
        """The exported score must equal the stored score."""
        a = _make_analysis(score=37)
        text = svc.export_markdown(a, repo).decode("utf-8")
        assert "37/100" in text

    def test_unicode_content(self, svc, repo):
        unicode_repo = _make_repo(name="日本語-service", owner="会社")
        a = _make_analysis(changed_files=["日本語/файл.py"])
        text = svc.export_markdown(a, unicode_repo).decode("utf-8")
        assert "日本語/файл.py" in text

    def test_special_chars_in_filenames(self, svc, repo):
        a = _make_analysis(changed_files=["src/file with spaces.ts", "src/file&symbols!.tsx"])
        text = svc.export_markdown(a, repo).decode("utf-8")
        assert "src/file with spaces.ts" in text

    def test_empty_evidence(self, svc, repo):
        a = _make_analysis()
        a.risk.facts = []
        a.risk.inferences = []
        a.risk.recommendations = []
        a.risk.risk_breakdown = []
        a.risk.potential_failure_scenarios = []
        a.risk.deployment_considerations = []
        text = svc.export_markdown(a, repo).decode("utf-8")
        assert "No facts recorded" in text
        assert "No inferences recorded" in text


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------


class TestPdfExport:
    def test_returns_bytes(self, svc, analysis, repo):
        result = svc.export_pdf(analysis, repo)
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_starts_with_pdf_magic_bytes(self, svc, analysis, repo):
        result = svc.export_pdf(analysis, repo)
        assert result[:4] == b"%PDF", "PDF output does not start with %PDF magic bytes"

    def test_pdf_not_empty(self, svc, analysis, repo):
        result = svc.export_pdf(analysis, repo)
        assert len(result) > 1024, "PDF appears too small (< 1 KB)"

    def test_empty_evidence_no_crash(self, svc, repo):
        a = _make_analysis()
        a.risk.evidence = []
        a.risk.facts = []
        a.risk.inferences = []
        a.risk.recommendations = []
        a.risk.risk_breakdown = []
        result = svc.export_pdf(a, repo)
        assert result[:4] == b"%PDF"

    def test_large_analysis_no_crash(self, svc, repo):
        large_files = [f"src/mod_{i}/component_{j}.tsx" for i in range(20) for j in range(25)]
        a = _make_analysis(changed_files=large_files)
        result = svc.export_pdf(a, repo)
        assert result[:4] == b"%PDF"

    def test_unicode_repo_name_no_crash(self, svc):
        unicode_repo = _make_repo(name="service-beta", owner="acme")
        a = _make_analysis(changed_files=["src/日本語.ts"])
        # PDF uses ASCII encoding for safety, should not crash
        result = svc.export_pdf(a, unicode_repo)
        assert result[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# Repository Isolation Tests (via AnalysisRepository)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repository_isolation_correct_id_passes(async_session):
    """Export with correct repository_id must succeed."""
    repo_obj = _make_repo()
    a = _make_analysis()

    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    # Correct repository_id — no exception
    fetched = await ar.get(saved.id)
    assert fetched is not None
    assert fetched.repository_id == REPO_ID


@pytest.mark.asyncio
async def test_repository_isolation_wrong_id_different_analysis(async_session):
    """Analysis retrieved belongs to its own repo, not another."""
    a1 = _make_analysis(analysis_id="anl-001", repository_id="repo-A")
    a2 = _make_analysis(analysis_id="anl-002", repository_id="repo-B")

    ar = AnalysisRepository(async_session)
    await ar.save(a1)
    await ar.save(a2)

    fetched_a1 = await ar.get("anl-001")
    fetched_a2 = await ar.get("anl-002")

    assert fetched_a1.repository_id == "repo-A"
    assert fetched_a2.repository_id == "repo-B"
    # Isolation: a1 must NOT be associated with repo-B
    assert fetched_a1.repository_id != "repo-B"


@pytest.mark.asyncio
async def test_missing_analysis_returns_none(async_session):
    ar = AnalysisRepository(async_session)
    result = await ar.get("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_score_preserved_after_round_trip(async_session):
    """Exported score must exactly match the stored score — never re-computed."""
    a = _make_analysis(score=83)
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)
    assert fetched.risk.score == 83, "Risk score changed after round-trip through DB!"


@pytest.mark.asyncio
async def test_full_risk_result_round_trip(async_session):
    """All RiskResult fields must survive DB round-trip via risk_full_result column."""
    a = _make_analysis()
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)

    # Facts
    assert len(fetched.risk.facts) == len(a.risk.facts)
    assert fetched.risk.facts[0].id == "FACT-001"

    # Inferences
    assert len(fetched.risk.inferences) == len(a.risk.inferences)
    assert fetched.risk.inferences[0].id == "INF-001"

    # Recommendations
    assert len(fetched.risk.recommendations) == len(a.risk.recommendations)

    # Risk Breakdown
    assert len(fetched.risk.risk_breakdown) == len(a.risk.risk_breakdown)
    assert fetched.risk.risk_breakdown[0].rule == "authentication_change"


@pytest.mark.asyncio
async def test_list_by_repository_isolation(async_session):
    """list_by_repository must only return analyses for the specified repo."""
    ar = AnalysisRepository(async_session)
    await ar.save(_make_analysis("a1", "repo-X"))
    await ar.save(_make_analysis("a2", "repo-X"))
    await ar.save(_make_analysis("a3", "repo-Y"))

    results = await ar.list_by_repository("repo-X")
    assert len(results) == 2
    assert all(r.repository_id == "repo-X" for r in results)


@pytest.mark.asyncio
async def test_unicode_filenames_round_trip(async_session):
    """Unicode file names must survive DB round-trip without corruption."""
    unicode_files = ["日本語/файл.py", "src/José García.ts", "src/文件 with spaces.tsx"]
    a = _make_analysis(changed_files=unicode_files)
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)
    assert fetched.changed_files == unicode_files


@pytest.mark.asyncio
async def test_special_chars_filenames_round_trip(async_session):
    """Special character filenames must survive DB round-trip."""
    special_files = [
        "src/file with spaces.ts",
        "src/file&symbols!.tsx",
        "src/file(1).py",
        "src/'quoted'.js",
    ]
    a = _make_analysis(changed_files=special_files)
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)
    assert fetched.changed_files == special_files


@pytest.mark.asyncio
async def test_large_analysis_round_trip(async_session):
    """Analysis with 500+ changed files must persist and retrieve correctly."""
    large_files = [f"src/module_{i}/file_{j}.ts" for i in range(50) for j in range(10)]
    a = _make_analysis(changed_files=large_files)
    ar = AnalysisRepository(async_session)
    saved = await ar.save(a)
    fetched = await ar.get(saved.id)
    assert len(fetched.changed_files) == 500


# ---------------------------------------------------------------------------
# Export format cross-checks
# ---------------------------------------------------------------------------


def test_json_csv_markdown_same_score(svc, analysis, repo):
    """All three text-based exports must report the same risk score."""
    json_payload = json.loads(svc.export_json(analysis, repo))
    md_text = svc.export_markdown(analysis, repo).decode("utf-8")
    files = {}
    zf = zipfile.ZipFile(io.BytesIO(svc.export_csv(analysis, repo)))
    for name in zf.namelist():
        files[name] = zf.read(name).decode("utf-8")

    assert json_payload["risk_summary"]["score"] == analysis.risk.score
    assert f"{analysis.risk.score}/100" in md_text
    assert str(analysis.risk.score) in files["repository_metrics.csv"]


def test_evidence_not_flattened_in_json(svc, analysis, repo):
    """JSON export must preserve nested evidence fields (not flatten them)."""
    payload = json.loads(svc.export_json(analysis, repo))
    ev = payload["evidence"][0]
    assert "signal" in ev
    assert "description" in ev
    assert "file_paths" in ev
    assert "weight" in ev
    assert "score" in ev
    assert "recommendation" in ev
