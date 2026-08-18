"""Production-grade ExportService for ChangePilot analysis results.

Consumes the canonical AnalysisExportModel.
Never invents data or recalculates risk during export.
Provides PDF (ReportLab multi-page), JSON, CSV (ZIP), and Markdown renderers.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any, Union

from app.models.analysis import ChangeAnalysisResult
from app.models.export import (
    AnalysisExportModel,
    ExportBlastRadius,
    ExportChangedFile,
    ExportDependencyPath,
    ExportEvidenceStatement,
    ExportFinding,
    ExportGraphHealth,
    ExportMetadata,
    ExportRepositoryHealth,
    ExportRepositoryInfo,
    ExportRiskBreakdownItem,
    ExportRiskSummary,
    ExportTestFinding,
)
from app.models.repository import RepositorySummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        return iso.replace("T", " ").replace("+00:00", " UTC")
    except Exception:
        return iso or ""


def _risk_color_hex(level: str) -> str:
    lvl = level.lower()
    if "crit" in lvl:
        return "#dc2626"
    if "high" in lvl:
        return "#ea580c"
    if "med" in lvl:
        return "#d97706"
    return "#16a34a"


def _risk_bg_hex(level: str) -> str:
    lvl = level.lower()
    if "crit" in lvl:
        return "#fef2f2"
    if "high" in lvl:
        return "#fff7ed"
    if "med" in lvl:
        return "#fffbeb"
    return "#f0fdf4"


def _ensure_model(
    analysis_or_model: Union[AnalysisExportModel, ChangeAnalysisResult],
    repository: RepositorySummary | None = None,
    health_metrics: dict[str, Any] | None = None,
    base_commit: str | None = None,
    head_commit: str | None = None,
) -> AnalysisExportModel:
    if isinstance(analysis_or_model, AnalysisExportModel):
        return analysis_or_model
    if repository is None:
        raise ValueError("repository must be provided when passing ChangeAnalysisResult")
    return AnalysisExportModel.from_analysis(
        analysis=analysis_or_model,
        repository=repository,
        health_metrics=health_metrics,
        base_commit=base_commit,
        head_commit=head_commit,
    )


# ---------------------------------------------------------------------------
# ReportLab Canvas with Page Numbers & Running Headers/Footers
# ---------------------------------------------------------------------------


try:
    from reportlab.pdfgen import canvas

    class NumberedCanvas(canvas.Canvas):
        """Two-pass canvas to dynamically compute and draw 'Page X of Y' and running headers."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._saved_page_states: list[dict[str, Any]] = []

        def showPage(self) -> None:
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_decorations(num_pages)
                super().showPage()
            super().save()

        def draw_page_decorations(self, page_count: int) -> None:
            self.saveState()
            self.setFont("Helvetica", 8)
            from reportlab.lib import colors
            self.setFillColor(colors.HexColor("#64748b"))

            # Running Header (pages 2+)
            if self._pageNumber > 1:
                header_text = getattr(self, "_header_text", "ChangePilot Risk Assessment Report")
                self.drawString(45, 800, header_text)
                self.setStrokeColor(colors.HexColor("#e2e8f0"))
                self.setLineWidth(0.5)
                self.line(45, 792, 550, 792)

            # Running Footer (all pages)
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(45, 45, 550, 45)

            footer_left = getattr(
                self, "_footer_text", "ChangePilot Engineering Risk Assessment · Confidential"
            )
            self.drawString(45, 32, footer_left)
            page_str = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(550, 32, page_str)
            self.restoreState()

except ImportError:
    NumberedCanvas = None  # type: ignore


# ---------------------------------------------------------------------------
# ExportService
# ---------------------------------------------------------------------------


class ExportService:
    """Production-grade ExportService consuming canonical AnalysisExportModel."""

    # ------------------------------------------------------------------
    # JSON Export
    # ------------------------------------------------------------------

    def export_json(
        self,
        analysis_or_model: Union[AnalysisExportModel, ChangeAnalysisResult],
        repository: RepositorySummary | None = None,
        health_metrics: dict[str, Any] | None = None,
    ) -> bytes:
        """Return a complete, lossless, canonical JSON export."""
        model = _ensure_model(analysis_or_model, repository, health_metrics)
        payload = model.model_dump()
        payload["export_format"] = "json"
        payload["export_timestamp"] = datetime.now(UTC).isoformat()
        return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")

    # ------------------------------------------------------------------
    # CSV (ZIP) Export
    # ------------------------------------------------------------------

    def export_csv(
        self,
        analysis_or_model: Union[AnalysisExportModel, ChangeAnalysisResult],
        repository: RepositorySummary | None = None,
        health_metrics: dict[str, Any] | None = None,
    ) -> bytes:
        """Return a ZIP archive containing six detailed CSV datasets."""
        model = _ensure_model(analysis_or_model, repository, health_metrics)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("risk_factors.csv", self._csv_risk_factors(model))
            zf.writestr("changed_files.csv", self._csv_changed_files(model))
            zf.writestr("impacted_files.csv", self._csv_impacted_files(model))
            zf.writestr("dependencies.csv", self._csv_dependencies(model))
            zf.writestr("test_gaps.csv", self._csv_test_gaps(model))
            zf.writestr("repository_metrics.csv", self._csv_repo_metrics(model))
        return buf.getvalue()

    def _csv_text(self, rows: list[list[str]], headers: list[str]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(rows)
        return buf.getvalue()

    def _csv_risk_factors(self, model: AnalysisExportModel) -> str:
        headers = [
            "id", "rule", "name", "category", "points", "raw_points",
            "evidence", "affected_files", "threshold", "recommendation", "recommendation_type"
        ]
        rows: list[list[str]] = []
        for i, item in enumerate(model.risk.breakdown, start=1):
            rows.append([
                f"RF-{i:03d}",
                item.rule,
                item.name,
                item.category,
                str(item.points),
                str(item.raw_points),
                item.evidence,
                "; ".join(item.affected_files),
                item.threshold,
                item.recommendation,
                item.recommendation_type,
            ])
        if not rows:
            rows.append(["N/A", "none", "No risk factors", "general", "0", "0.0", "No scoring rule fired", "", "", "", ""])
        return self._csv_text(rows, headers)

    def _csv_changed_files(self, model: AnalysisExportModel) -> str:
        headers = ["index", "file_path", "change_type", "language", "module", "risk_signals", "test_status"]
        rows: list[list[str]] = []
        for i, f in enumerate(model.changed_files, start=1):
            rows.append([
                str(i),
                f.path,
                f.change_type,
                f.language,
                f.module,
                "; ".join(f.risk_signals),
                f.test_status,
            ])
        return self._csv_text(rows, headers)

    def _csv_impacted_files(self, model: AnalysisExportModel) -> str:
        headers = ["index", "module_or_file", "relationship", "reason", "depth"]
        rows: list[list[str]] = []
        for i, p in enumerate(model.blast_radius.dependency_paths, start=1):
            rows.append([
                str(i),
                p.file_or_module,
                p.relationship,
                p.reason,
                str(p.depth),
            ])
        if not rows:
            for i, m in enumerate(model.blast_radius.impacted_modules, start=1):
                rows.append([str(i), m, "MODULE_IMPACT", "Architectural module in blast radius", "1"])
        return self._csv_text(rows, headers)

    def _csv_dependencies(self, model: AnalysisExportModel) -> str:
        headers = ["index", "source", "target", "relationship", "depth", "reason"]
        rows: list[list[str]] = []
        for i, p in enumerate(model.blast_radius.dependency_paths, start=1):
            rows.append([
                str(i),
                p.source,
                p.target or p.file_or_module,
                p.relationship,
                str(p.depth),
                p.reason,
            ])
        return self._csv_text(rows, headers)

    def _csv_test_gaps(self, model: AnalysisExportModel) -> str:
        headers = ["index", "category", "title", "description", "recommendation", "affected_files", "status"]
        rows: list[list[str]] = []
        for i, tf in enumerate(model.test_findings, start=1):
            rows.append([
                str(i),
                tf.category,
                tf.title,
                tf.description,
                tf.recommendation,
                "; ".join(tf.affected_files),
                tf.status,
            ])
        return self._csv_text(rows, headers)

    def _csv_repo_metrics(self, model: AnalysisExportModel) -> str:
        headers = ["metric", "value"]
        rows = [
            ["repository_id", model.repository.id],
            ["repository_name", model.repository.name],
            ["owner", model.repository.owner],
            ["branch", model.branch],
            ["base_commit", model.base_commit or ""],
            ["head_commit", model.head_commit or ""],
            ["analysis_id", model.analysis_id],
            ["analysis_timestamp", model.timestamp or ""],
            ["risk_score", str(model.risk.score)],
            ["risk_level", model.risk.level],
            ["evidence_completeness", f"{model.risk.evidence_completeness:.4f}"],
            ["is_calibrated", str(model.risk.is_calibrated)],
            ["raw_rule_score", str(model.risk.raw_rule_score)],
            ["normalized_score", str(model.risk.normalized_score)],
            ["changed_files_count", str(len(model.changed_files))],
            ["direct_impact_count", str(model.blast_radius.direct_impact)],
            ["indirect_impact_count", str(model.blast_radius.indirect_impact)],
            ["total_impact_count", str(model.blast_radius.total_impact)],
            ["graph_nodes", str(model.graph_health.nodes)],
            ["graph_edges", str(model.graph_health.edges)],
            ["circular_dependencies", str(model.graph_health.circular_dependencies)],
            ["orphan_candidates", str(model.graph_health.orphan_candidates)],
            ["unresolved_imports", str(model.graph_health.unresolved_imports)],
            ["health_score", str(model.repository_health.health_score) if model.repository_health.health_score is not None else "Not Persisted"],
            ["parser_version", model.metadata.parser_version],
            ["graph_version", model.metadata.graph_version],
            ["risk_engine_version", model.metadata.risk_engine_version],
        ]
        return self._csv_text(rows, headers)

    # ------------------------------------------------------------------
    # Markdown Export
    # ------------------------------------------------------------------

    def export_markdown(
        self,
        analysis_or_model: Union[AnalysisExportModel, ChangeAnalysisResult],
        repository: RepositorySummary | None = None,
        health_metrics: dict[str, Any] | None = None,
    ) -> bytes:
        """Return a GitHub / PR Markdown report."""
        model = _ensure_model(analysis_or_model, repository, health_metrics)
        lines: list[str] = []

        def h(text: str, level: int = 2) -> None:
            lines.append(f"{'#' * level} {text}\n")

        def p(text: str) -> None:
            lines.append(f"{text}\n")

        def rule() -> None:
            lines.append("---\n")

        # Title
        lines.append(f"# Change Risk Assessment — {model.repository.owner}/{model.repository.name}\n")
        lines.append(
            f"> **Analysis ID:** `{model.analysis_id}` | "
            f"**Branch:** `{model.branch}` | "
            f"**Generated:** {_fmt_dt(model.timestamp)}\n"
        )
        rule()

        # Executive Summary
        h("Executive Summary", 2)
        lines.append(f"**Risk Rating:** `{model.risk.score}/100 — {model.risk.level}`  ")
        lines.append(f"**Evidence Completeness:** `{int(round(model.risk.evidence_completeness * 100))}%`  ")
        lines.append(f"**Calibration Status:** {model.risk.calibration_status}\n")
        if model.risk.score_description:
            lines.append(f"> *{model.risk.score_description}*\n")

        lines.append("| Metric | Value | Direct Impact | Indirect Impact | Circular Dependencies |")
        lines.append("|---|---|---|---|---|")
        lines.append(
            f"| `{model.risk.score}/100` | `{model.risk.level}` | `{model.blast_radius.direct_impact} files` | "
            f"`{model.blast_radius.indirect_impact} files` | `{model.graph_health.circular_dependencies}` |"
        )
        lines.append("")
        rule()

        # Section: Risk Breakdown
        h("1. Risk Breakdown & Scoring Audit", 2)
        if model.risk.breakdown:
            lines.append("| Rule | Category | Points | Evidence | Affected Files |")
            lines.append("|------|----------|--------|----------|----------------|")
            for item in model.risk.breakdown:
                aff = ", ".join(f"`{f}`" for f in item.affected_files[:3]) or "—"
                lines.append(f"| `{item.rule}` | {item.category} | **+{item.points}** | {item.evidence} | {aff} |")
            lines.append("")
            lines.append(
                f"> **Score Calculation:** Raw Rule Points: `{model.risk.raw_rule_score}` → "
                f"Normalized: `{model.risk.normalized_score}` → Final Capped Risk Score: **`{model.risk.score}/100`**\n"
            )
        else:
            p("*No risk scoring rules fired for this analysis.*")
        rule()

        # Section: Facts
        h("2. Directly Observed Facts", 2)
        if model.facts:
            for f in model.facts:
                lines.append(f"- **`FACT`** `[{f.id}]` {f.claim}")
                if f.source_evidence:
                    lines.append(f"  - *Source:* {f.source_evidence}")
                if f.affected_files:
                    lines.append(f"  - *Files:* {', '.join(f'`{x}`' for x in f.affected_files[:4])}")
            lines.append("")
        else:
            p("*No facts recorded in persisted analysis.*")
        rule()

        # Section: Inferences
        h("3. Deterministic Inferences", 2)
        if model.inferences:
            for inf in model.inferences:
                lines.append(f"- **`INFERENCE`** `[{inf.id}]` {inf.claim}")
                if inf.source_evidence:
                    lines.append(f"  - *Evidence:* {inf.source_evidence}")
                if inf.traceability_ref:
                    lines.append(f"  - *Traceability:* `{inf.traceability_ref}`")
            lines.append("")
        else:
            p("*No inferences recorded in persisted analysis.*")
        rule()

        # Section: Recommendations
        h("4. Recommendations", 2)
        if model.recommendations:
            for rec in model.recommendations:
                rec_type = rec.recommendation_type or "POLICY_BASED"
                lines.append(f"- **`RECOMMENDATION`** `[{rec.id}]` *[{rec_type}]* {rec.claim}")
                if rec.source_evidence:
                    lines.append(f"  - *Evidence:* {rec.source_evidence}")
                if rec.affected_files:
                    lines.append(f"  - *Files:* {', '.join(f'`{x}`' for x in rec.affected_files[:4])}")
            lines.append("")
        else:
            p("*No recommendations recorded in persisted analysis.*")
        rule()

        # Section: Blast Radius
        h("5. Blast Radius & Dependency Paths", 2)
        lines.append(
            f"- **Direct Impact:** `{model.blast_radius.direct_impact}` file(s)\n"
            f"- **Indirect Impact:** `{model.blast_radius.indirect_impact}` dependent component(s)\n"
            f"- **Total Impact:** `{model.blast_radius.total_impact}` component(s)\n"
        )
        if model.blast_radius.dependency_paths:
            lines.append("| Depth | Component / Path | Relationship | Reason |")
            lines.append("|-------|------------------|--------------|--------|")
            for pth in model.blast_radius.dependency_paths[:30]:
                lines.append(f"| `{pth.depth}` | `{pth.file_or_module}` | `{pth.relationship}` | {pth.reason} |")
            lines.append("")
        else:
            p("*No dependency traversal paths recorded.*")
        rule()

        # Section: Changed Files
        h("6. Changed Files Detail", 2)
        if model.changed_files:
            lines.append("| # | File Path | Language | Module | Signals | Classification |")
            lines.append("|---|-----------|----------|--------|---------|----------------|")
            for i, cf in enumerate(model.changed_files, start=1):
                sigs = ", ".join(cf.risk_signals) if cf.risk_signals else "—"
                lines.append(f"| {i} | `{cf.path}` | {cf.language} | `{cf.module}` | {sigs} | {cf.test_status} |")
            lines.append("")
        rule()

        # Section: Graph Structure & Health
        h("7. Graph Structure & Health Diagnostics", 2)
        gh = model.graph_health
        lines.append(f"- **AST Nodes:** `{gh.nodes}`")
        lines.append(f"- **Dependency Edges:** `{gh.edges}`")
        lines.append(f"- **Circular Dependencies:** `{gh.circular_dependencies}`")
        lines.append(f"- **Potential Orphan Candidates:** `{gh.orphan_candidates}` *(Note: Potential Orphan Candidate != confirmed dead code)*")
        lines.append(f"- **Unresolved Imports:** `{gh.unresolved_imports}`")
        lines.append("")

        if gh.orphan_candidate_files:
            lines.append("**Potential Orphan Candidates:**")
            for of in gh.orphan_candidate_files[:15]:
                lines.append(f"- `{of}`")
            lines.append("")

        if gh.unresolved_imports > 0:
            if gh.unresolved_import_details:
                lines.append("**Unresolved Imports Detail:**")
                for u in gh.unresolved_import_details[:10]:
                    lines.append(f"- `{u.get('target', 'unknown')}` in `{u.get('source', 'unknown')}` ({u.get('reason', '')})")
                lines.append("")
            else:
                lines.append(f"> *{gh.unresolved_imports} unresolved imports detected. File-level details were not persisted for this analysis.*\n")
        rule()

        # Section: Architecture & Security Findings
        h("8. Architecture & Security Findings", 2)
        h("Architecture Findings", 3)
        if model.architecture_findings:
            for af in model.architecture_findings:
                lines.append(f"- **[{af.classification}] {af.title}**: {af.description}")
                if af.recommendation:
                    lines.append(f"  - *Recommendation:* {af.recommendation}")
            lines.append("")
        else:
            p("*No architecture findings detected from the available analysis evidence.*")

        h("Security Findings", 3)
        if model.security_findings:
            for sf in model.security_findings:
                lines.append(f"- 🔒 **[{sf.classification}] {sf.title}**: {sf.description}")
                if sf.recommendation:
                    lines.append(f"  - *Recommendation:* {sf.recommendation}")
            lines.append("")
        else:
            p("*No security findings detected from the available analysis evidence.*")
        rule()

        # Section: Repository Health
        h("9. Repository Health", 2)
        if model.repository_health.health_score is not None:
            lines.append(f"**Repository Health Score:** `{model.repository_health.health_score}/100`\n")
            if model.repository_health.category_scores_persisted:
                lines.append(f"- Architecture: `{model.repository_health.architecture}`")
                lines.append(f"- Dependencies: `{model.repository_health.dependencies}`")
                lines.append(f"- Testing: `{model.repository_health.testing}`")
                lines.append(f"- Security: `{model.repository_health.security}`")
                lines.append(f"- Maintainability: `{model.repository_health.maintainability}`")
                lines.append("")
            else:
                lines.append("> *Category health scores were not persisted for this analysis.*\n")
        else:
            lines.append("> *Category health scores were not persisted for this analysis.*\n")
        rule()

        # Section: Rollback & Reviewer Evidence
        h("10. Rollback & Reviewer Evidence", 2)
        if model.rollback_considerations:
            lines.append("**Rollback Considerations:**")
            for rc in model.rollback_considerations:
                lines.append(f"- 🔄 {rc}")
            lines.append("")
        else:
            p("*Rollback analysis was not generated for this analysis.*")

        if model.reviewer_evidence:
            lines.append("| Review Area | Suggested Reviewer | Evidence |")
            lines.append("|-------------|-------------------|----------|")
            for r in model.reviewer_evidence:
                lines.append(f"| {r.get('review_area', '')} | {r.get('suggested_reviewer', '—')} | {r.get('evidence', '')} |")
            lines.append("")
        rule()

        # Section: Metadata
        h("11. Analysis Metadata", 2)
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| `repository_id` | `{model.metadata.repository_id}` |")
        lines.append(f"| `repository_name` | `{model.metadata.repository_name}` |")
        lines.append(f"| `owner` | `{model.metadata.owner}` |")
        lines.append(f"| `branch` | `{model.metadata.branch}` |")
        lines.append(f"| `base_commit` | `{model.metadata.base_commit or 'HEAD~1'}` |")
        lines.append(f"| `head_commit` | `{model.metadata.head_commit or 'HEAD'}` |")
        lines.append(f"| `analysis_id` | `{model.analysis_id}` |")
        lines.append(f"| `analysis_timestamp` | `{model.metadata.analysis_timestamp or ''}` |")
        lines.append(f"| `risk_engine_version` | `{model.metadata.risk_engine_version}` |")
        lines.append(f"| `parser_version` | `{model.metadata.parser_version}` |")
        lines.append(f"| `graph_version` | `{model.metadata.graph_version}` |")
        lines.append("")
        lines.append(
            "> *This report was generated from persisted analysis data. "
            "Risk scores were not re-computed during export. "
            "ChangePilot deterministic analysis is fully auditable and reproducible.*"
        )
        lines.append("")

        return "\n".join(lines).encode("utf-8")

    # ------------------------------------------------------------------
    # PDF Export (ReportLab Multi-Page)
    # ------------------------------------------------------------------

    def export_pdf(
        self,
        analysis_or_model: Union[AnalysisExportModel, ChangeAnalysisResult],
        repository: RepositorySummary | None = None,
        health_metrics: dict[str, Any] | None = None,
    ) -> bytes:
        """Return a professional multi-page ReportLab PDF export."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm, mm
            from reportlab.platypus import (
                HRFlowable,
                KeepTogether,
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:
            raise RuntimeError(
                "reportlab is required for PDF export. Run: pip install reportlab"
            ) from exc

        model = _ensure_model(analysis_or_model, repository, health_metrics)
        buf = io.BytesIO()

        level_color = colors.HexColor(_risk_color_hex(model.risk.level))
        level_bg = colors.HexColor(_risk_bg_hex(model.risk.level))
        primary_color = colors.HexColor("#0f172a")
        accent_blue = colors.HexColor("#2563eb")
        accent_purple = colors.HexColor("#7c3aed")
        accent_emerald = colors.HexColor("#059669")
        slate_700 = colors.HexColor("#334155")
        slate_500 = colors.HexColor("#64748b")
        slate_200 = colors.HexColor("#e2e8f0")
        slate_50 = colors.HexColor("#f8fafc")

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=1.5 * cm,
            rightMargin=1.5 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        styles = getSampleStyleSheet()

        # Styles
        style_title = ParagraphStyle(
            "CPTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            textColor=primary_color,
            alignment=TA_LEFT,
            spaceAfter=2,
            fontName="Helvetica-Bold",
        )
        style_subtitle = ParagraphStyle(
            "CPSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=slate_500,
            spaceAfter=2,
        )
        style_h1 = ParagraphStyle(
            "CPH1",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            textColor=primary_color,
            spaceBefore=14,
            spaceAfter=6,
            fontName="Helvetica-Bold",
            keepWithNext=True,
        )
        style_h2 = ParagraphStyle(
            "CPH2",
            parent=styles["Heading2"],
            fontSize=10.5,
            leading=13,
            textColor=slate_700,
            spaceBefore=8,
            spaceAfter=4,
            fontName="Helvetica-Bold",
            keepWithNext=True,
        )
        style_body = ParagraphStyle(
            "CPBody",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=2,
        )
        style_body_bold = ParagraphStyle(
            "CPBodyBold",
            parent=style_body,
            fontName="Helvetica-Bold",
        )
        style_mono = ParagraphStyle(
            "CPMono",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10.5,
            fontName="Courier",
            textColor=primary_color,
        )
        style_card_val = ParagraphStyle(
            "CPCardVal",
            parent=styles["Normal"],
            fontSize=14,
            leading=16,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            textColor=primary_color,
        )
        style_card_lbl = ParagraphStyle(
            "CPCardLbl",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
            textColor=slate_500,
        )
        style_q = ParagraphStyle(
            "CPQuestion",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold",
        )
        style_ans = ParagraphStyle(
            "CPAnswer",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#475569"),
        )
        style_badge_fact = ParagraphStyle(
            "CPBadgeFact",
            parent=style_mono,
            textColor=accent_blue,
            fontName="Helvetica-Bold",
        )
        style_badge_inf = ParagraphStyle(
            "CPBadgeInf",
            parent=style_mono,
            textColor=accent_purple,
            fontName="Helvetica-Bold",
        )
        style_badge_rec = ParagraphStyle(
            "CPBadgeRec",
            parent=style_mono,
            textColor=accent_emerald,
            fontName="Helvetica-Bold",
        )
        style_caption = ParagraphStyle(
            "CPCaption",
            parent=styles["Normal"],
            fontSize=7.5,
            leading=10,
            textColor=slate_500,
            alignment=TA_CENTER,
        )

        def hr() -> HRFlowable:
            return HRFlowable(width="100%", thickness=0.5, color=slate_200, spaceBefore=4, spaceAfter=8)

        def standard_table_style(header_bg: str = "#0f172a") -> TableStyle:
            return TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate_50]),
                ("GRID", (0, 0), (-1, -1), 0.25, slate_200),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ])

        story: list[Any] = []

        # ==============================================================
        # PAGE 1: EXECUTIVE SUMMARY
        # ==============================================================

        # Brand & Header
        story.append(Paragraph("CHANGEPILOT", ParagraphStyle(
            "Brand", parent=style_body_bold, fontSize=9, textColor=colors.HexColor("#6366f1")
        )))
        story.append(Spacer(1, 2))
        story.append(Paragraph("Change Risk Assessment Report", style_title))
        story.append(Paragraph(
            f"<b>Repository:</b> {model.repository.owner}/{model.repository.name} &nbsp;|&nbsp; "
            f"<b>Branch:</b> {model.branch} &nbsp;|&nbsp; "
            f"<b>Analysis ID:</b> {model.analysis_id}",
            style_subtitle,
        ))
        story.append(Paragraph(
            f"<b>Analysis Timestamp:</b> {_fmt_dt(model.timestamp)} &nbsp;|&nbsp; "
            f"<b>Analysis Engine:</b> {model.metadata.risk_engine_version}",
            style_subtitle,
        ))
        story.append(hr())

        # Executive Q&A Block
        qa_data = [
            [
                Paragraph("What changed?", style_q),
                Paragraph(f"{len(model.changed_files)} file(s) modified in commit diff across {len(model.blast_radius.impacted_modules)} module(s).", style_ans),
            ],
            [
                Paragraph("How risky is it?", style_q),
                Paragraph(
                    f"<b>Score: {model.risk.score}/100 ({model.risk.level})</b> — "
                    f"Evidence Completeness: {int(round(model.risk.evidence_completeness * 100))}% ({model.risk.calibration_status[:55]}...)",
                    style_ans,
                ),
            ],
            [
                Paragraph("Why?", style_q),
                Paragraph(
                    "; ".join([f"{b.name} (+{b.points} pts)" for b in model.risk.breakdown[:3]])
                    if model.risk.breakdown else "No risk scoring factors triggered.",
                    style_ans,
                ),
            ],
            [
                Paragraph("What is affected?", style_q),
                Paragraph(
                    f"{model.blast_radius.direct_impact} directly changed files, "
                    f"{model.blast_radius.indirect_impact} transitive downstream dependents. "
                    f"Total impact size: {model.blast_radius.total_impact} components.",
                    style_ans,
                ),
            ],
            [
                Paragraph("What should engineers do?", style_q),
                Paragraph(
                    model.recommendations[0].claim
                    if model.recommendations else "Review changed files and run test suite before merging.",
                    style_ans,
                ),
            ],
        ]
        qa_table = Table(qa_data, colWidths=["25%", "75%"])
        qa_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(qa_table)
        story.append(Spacer(1, 8))

        # Metric Cards Table
        metric_cards_data = [
            [
                Paragraph(f"<font color='{_risk_color_hex(model.risk.level)}'>{model.risk.score}/100</font>", style_card_val),
                Paragraph(f"{int(round(model.risk.evidence_completeness * 100))}%", style_card_val),
                Paragraph(str(len(model.changed_files)), style_card_val),
                Paragraph(str(model.blast_radius.direct_impact), style_card_val),
                Paragraph(str(model.blast_radius.indirect_impact), style_card_val),
                Paragraph(str(model.graph_health.circular_dependencies), style_card_val),
            ],
            [
                Paragraph(f"Risk Score ({model.risk.level})", style_card_lbl),
                Paragraph("Evidence Completeness", style_card_lbl),
                Paragraph("Changed Files", style_card_lbl),
                Paragraph("Direct Impact", style_card_lbl),
                Paragraph("Transitive Impact", style_card_lbl),
                Paragraph("Circular Dependencies", style_card_lbl),
            ],
        ]
        cards_table = Table(metric_cards_data, colWidths=["16.6%", "16.6%", "16.6%", "16.6%", "16.6%", "16.6%"])
        cards_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), level_bg),
            ("BOX", (0, 0), (-1, -1), 0.5, level_color),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, slate_200),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(cards_table)
        story.append(Spacer(1, 8))

        # Key Risk Drivers & Top Actions Summary
        top_recs = model.recommendations[:3]
        rec_bullets = "".join([f"• <b>[{r.id}]</b> {r.claim}<br/>" for r in top_recs]) if top_recs else "• No action required."
        top_factors = model.risk.breakdown[:3]
        factor_bullets = "".join([f"• <b>{b.name}</b> (+{b.points} pts): {b.evidence}<br/>" for b in top_factors]) if top_factors else "• No risk factors triggered."

        summary_boxes = [
            [
                Paragraph("<b>Primary Risk Drivers</b>", style_h2),
                Paragraph("<b>Key Recommended Actions</b>", style_h2),
            ],
            [
                Paragraph(factor_bullets, style_body),
                Paragraph(rec_bullets, style_body),
            ],
        ]
        sum_table = Table(summary_boxes, colWidths=["50%", "50%"])
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, slate_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, slate_200),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(sum_table)

        # ==============================================================
        # PAGE 2+: DETAILED SECTIONS
        # ==============================================================
        story.append(PageBreak())

        # Section 1: Metadata
        story.append(Paragraph("1. Repository & Analysis Metadata", style_h1))
        story.append(hr())
        meta_table_data = [
            ["Attribute", "Value", "Attribute", "Value"],
            ["Repository ID", model.repository.id, "Branch", model.branch],
            ["Repository Name", model.repository.name, "Language", model.repository.language or "Multi-language"],
            ["Owner", model.repository.owner or "—", "Base Commit", model.base_commit or "HEAD~1"],
            ["Analysis ID", model.analysis_id, "Head Commit", model.head_commit or "HEAD"],
            ["Analysis Timestamp", _fmt_dt(model.timestamp), "Parser Version", model.metadata.parser_version],
            ["Risk Engine Version", model.metadata.risk_engine_version, "Graph Version", model.metadata.graph_version],
        ]
        meta_t = Table(meta_table_data, colWidths=["20%", "30%", "20%", "30%"])
        meta_t.setStyle(standard_table_style())
        story.append(meta_t)
        story.append(Spacer(1, 10))

        # Section 2: Risk Breakdown
        story.append(Paragraph("2. Risk Breakdown & Scoring Formula", style_h1))
        story.append(hr())
        if model.risk.breakdown:
            bd_data = [["Rule ID", "Rule Name", "Category", "Pts", "Evidence", "Affected Files"]]
            for item in model.risk.breakdown:
                aff = ", ".join(item.affected_files[:2]) if item.affected_files else "—"
                bd_data.append([
                    Paragraph(item.rule, style_mono),
                    Paragraph(item.name, style_body_bold),
                    Paragraph(item.category, style_body),
                    Paragraph(f"+{item.points}", ParagraphStyle("Pts", parent=style_body_bold, textColor=colors.HexColor("#ea580c"))),
                    Paragraph(item.evidence[:120], style_body),
                    Paragraph(aff, style_mono),
                ])
            bd_t = Table(bd_data, colWidths=["18%", "20%", "12%", "8%", "24%", "18%"])
            bd_t.setStyle(standard_table_style())
            story.append(bd_t)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>Score Audit:</b> Raw Rule Points: <b>{model.risk.raw_rule_score}</b> &nbsp;|&nbsp; "
                f"Diminishing Scaling Score: <b>{model.risk.normalized_score}</b> &nbsp;|&nbsp; "
                f"Final Risk Score: <b>{model.risk.score}/100</b> ({model.risk.level})",
                style_caption,
            ))
        else:
            story.append(Paragraph("No scoring rules triggered for this change set.", style_body))
        story.append(Spacer(1, 10))

        # Section 3: Traceable Statements
        story.append(Paragraph("3. Structured Evidence Statements", style_h1))
        story.append(hr())

        # 3.1 Facts
        story.append(Paragraph("3.1 Observed Facts (Direct Repository & AST Evidence)", style_h2))
        if model.facts:
            facts_data = [["ID", "Type", "Observed Fact Claim", "Source Evidence"]]
            for f in model.facts:
                facts_data.append([
                    Paragraph(f.id, style_badge_fact),
                    Paragraph("FACT", style_mono),
                    Paragraph(f.claim, style_body),
                    Paragraph(f.source_evidence or "Repository Scan", style_caption),
                ])
            ft_table = Table(facts_data, colWidths=["12%", "10%", "50%", "28%"])
            ft_table.setStyle(standard_table_style("#1d4ed8"))
            story.append(ft_table)
        else:
            story.append(Paragraph("No facts recorded in persisted analysis.", style_body))
        story.append(Spacer(1, 8))

        # 3.2 Inferences
        story.append(Paragraph("3.2 Deterministic Inferences (Derived Architectural Conclusions)", style_h2))
        if model.inferences:
            inf_data = [["ID", "Type", "Inferred Architectural Impact", "Traceability Reference"]]
            for inf in model.inferences:
                inf_data.append([
                    Paragraph(inf.id, style_badge_inf),
                    Paragraph("INFERENCE", style_mono),
                    Paragraph(inf.claim, style_body),
                    Paragraph(inf.traceability_ref or inf.source_evidence or "Graph Traversal", style_caption),
                ])
            inf_table = Table(inf_data, colWidths=["12%", "12%", "48%", "28%"])
            inf_table.setStyle(standard_table_style("#6b21a8"))
            story.append(inf_table)
        else:
            story.append(Paragraph("No inferences recorded in persisted analysis.", style_body))
        story.append(Spacer(1, 8))

        # 3.3 Recommendations
        story.append(Paragraph("3.3 Engineering Recommendations", style_h2))
        if model.recommendations:
            rec_data = [["ID", "Type", "Classification", "Actionable Engineering Recommendation", "Files"]]
            for r in model.recommendations:
                aff = ", ".join(r.affected_files[:2]) if r.affected_files else "—"
                rec_data.append([
                    Paragraph(r.id, style_badge_rec),
                    Paragraph("REC", style_mono),
                    Paragraph(r.recommendation_type or "POLICY_BASED", style_caption),
                    Paragraph(r.claim, style_body),
                    Paragraph(aff, style_mono),
                ])
            rec_table = Table(rec_data, colWidths=["10%", "8%", "18%", "44%", "20%"])
            rec_table.setStyle(standard_table_style("#047857"))
            story.append(rec_table)
        else:
            story.append(Paragraph("No recommendations recorded in persisted analysis.", style_body))
        story.append(Spacer(1, 10))

        # Section 4: Blast Radius
        story.append(PageBreak())
        story.append(Paragraph("4. Blast Radius & Dependency Impact Analysis", style_h1))
        story.append(hr())
        br_summary_data = [
            ["Metric", "Value", "Interpretation"],
            ["Direct Impact", f"{model.blast_radius.direct_impact} files", "Directly modified in commit diff"],
            ["Indirect Impact", f"{model.blast_radius.indirect_impact} components", "Transitive dependents traversing AST graph"],
            ["Total Blast Radius", f"{model.blast_radius.total_impact} components", "Total architectural surface exposed to change"],
            ["Impacted Modules", ", ".join(model.blast_radius.impacted_modules) or "root", "Architectural module boundaries crossed"],
        ]
        br_sum_table = Table(br_summary_data, colWidths=["25%", "25%", "50%"])
        br_sum_table.setStyle(standard_table_style())
        story.append(br_sum_table)
        story.append(Spacer(1, 8))

        story.append(Paragraph("Dependency Impact Traversal Paths", style_h2))
        if model.blast_radius.dependency_paths:
            dp_data = [["Depth", "Component / Path", "Relationship", "Reason / Propagation Path"]]
            for pth in model.blast_radius.dependency_paths[:35]:
                dp_data.append([
                    Paragraph(str(pth.depth), style_mono),
                    Paragraph(pth.file_or_module, style_mono),
                    Paragraph(pth.relationship, style_body),
                    Paragraph(pth.reason, style_body),
                ])
            dp_table = Table(dp_data, colWidths=["8%", "38%", "18%", "36%"])
            dp_table.setStyle(standard_table_style())
            story.append(dp_table)
        else:
            story.append(Paragraph("No transitive downstream dependencies detected beyond direct commit modifications.", style_body))
        story.append(Spacer(1, 10))

        # Section 5: Changed Files
        story.append(Paragraph("5. Changed Files Detail", style_h1))
        story.append(hr())
        if model.changed_files:
            cf_data = [["#", "File Path", "Language", "Module", "Risk Signals", "Classification"]]
            for i, cf in enumerate(model.changed_files, start=1):
                sigs = ", ".join(cf.risk_signals) if cf.risk_signals else "—"
                cf_data.append([
                    str(i),
                    Paragraph(cf.path, style_mono),
                    Paragraph(cf.language, style_body),
                    Paragraph(cf.module, style_body),
                    Paragraph(sigs, style_body),
                    Paragraph(cf.test_status, style_caption),
                ])
            cf_table = Table(cf_data, colWidths=["5%", "35%", "14%", "12%", "20%", "14%"])
            cf_table.setStyle(standard_table_style())
            story.append(cf_table)
        else:
            story.append(Paragraph("No changed files in this analysis.", style_body))
        story.append(Spacer(1, 10))

        # Section 6: Graph Structure & Health
        story.append(PageBreak())
        story.append(Paragraph("6. Graph Structure & Health Diagnostics", style_h1))
        story.append(hr())
        gh = model.graph_health
        gh_data = [
            ["Graph Metric", "Value", "Graph Metric", "Value"],
            ["Total AST Nodes", str(gh.nodes), "Total Dependency Edges", str(gh.edges)],
            ["Circular Dependencies", str(gh.circular_dependencies), "Duplicate Edges", str(gh.duplicate_edges)],
            ["Unresolved Imports", str(gh.unresolved_imports), "Self-Importing Nodes", str(gh.self_imports)],
            ["Potential Orphan Candidates", str(gh.orphan_candidates), "Invalid AST Paths", str(gh.invalid_paths)],
        ]
        gh_table = Table(gh_data, colWidths=["25%", "25%", "25%", "25%"])
        gh_table.setStyle(standard_table_style())
        story.append(gh_table)
        story.append(Spacer(1, 8))

        # 6.1 Unresolved Imports
        story.append(Paragraph("6.1 Unresolved Imports", style_h2))
        if gh.unresolved_imports > 0:
            if gh.unresolved_import_details:
                u_data = [["Source File", "Unresolved Target", "Diagnostic Reason"]]
                for u in gh.unresolved_import_details[:15]:
                    u_data.append([
                        Paragraph(u.get("source", "—"), style_mono),
                        Paragraph(u.get("target", "—"), style_mono),
                        Paragraph(u.get("reason", "Module not found in AST"), style_body),
                    ])
                u_table = Table(u_data, colWidths=["35%", "35%", "30%"])
                u_table.setStyle(standard_table_style("#78350f"))
                story.append(u_table)
            else:
                story.append(Paragraph(
                    f"<b>{gh.unresolved_imports} unresolved import(s) detected.</b> "
                    "File-level details were not persisted for this analysis.",
                    style_body,
                ))
        else:
            story.append(Paragraph("No unresolved imports detected in graph AST.", style_body))
        story.append(Spacer(1, 8))

        # 6.2 Potential Orphan Candidates
        story.append(Paragraph("6.2 Potential Orphan Candidates", style_h2))
        story.append(Paragraph("<i>Note: Potential Orphan Candidate != confirmed dead code. Represents nodes with zero incoming dependency references in workspace AST.</i>", style_caption))
        story.append(Spacer(1, 3))
        if gh.orphan_candidate_files:
            oc_data = [["#", "File Path", "Classification", "Diagnostic Note"]]
            for i, oc in enumerate(gh.orphan_candidate_files[:20], start=1):
                oc_data.append([
                    str(i),
                    Paragraph(oc, style_mono),
                    "ORPHAN_CANDIDATE",
                    "0 incoming dependency references detected in graph",
                ])
            oc_table = Table(oc_data, colWidths=["6%", "46%", "20%", "28%"])
            oc_table.setStyle(standard_table_style("#334155"))
            story.append(oc_table)
        else:
            story.append(Paragraph("No orphan candidate files identified.", style_body))
        story.append(Spacer(1, 10))

        # Section 7: Architecture, Security & Test Findings
        story.append(PageBreak())
        story.append(Paragraph("7. Architecture, Security & Test Findings", style_h1))
        story.append(hr())

        # 7.1 Architecture Findings
        story.append(Paragraph("7.1 Architecture & Infrastructure Findings", style_h2))
        if model.architecture_findings:
            af_data = [["Type", "Finding Title", "Category", "Description", "Recommendation"]]
            for af in model.architecture_findings:
                af_data.append([
                    Paragraph(af.classification, style_mono),
                    Paragraph(af.title, style_body_bold),
                    Paragraph(af.category, style_caption),
                    Paragraph(af.description[:120], style_body),
                    Paragraph(af.recommendation or "—", style_body),
                ])
            af_table = Table(af_data, colWidths=["10%", "22%", "12%", "30%", "26%"])
            af_table.setStyle(standard_table_style("#1e293b"))
            story.append(af_table)
        else:
            story.append(Paragraph("No architecture findings detected from the available analysis evidence.", style_body))
        story.append(Spacer(1, 8))

        # 7.2 Security Findings
        story.append(Paragraph("7.2 Security Findings", style_h2))
        if model.security_findings:
            sf_data = [["Type", "Security Finding", "Category", "Description", "Recommendation"]]
            for sf in model.security_findings:
                sf_data.append([
                    Paragraph(sf.classification, style_mono),
                    Paragraph(sf.title, style_body_bold),
                    Paragraph("SECURITY", style_caption),
                    Paragraph(sf.description[:120], style_body),
                    Paragraph(sf.recommendation or "—", style_body),
                ])
            sf_table = Table(sf_data, colWidths=["10%", "22%", "12%", "30%", "26%"])
            sf_table.setStyle(standard_table_style("#7f1d1d"))
            story.append(sf_table)
        else:
            story.append(Paragraph("No security findings detected from the available analysis evidence.", style_body))
        story.append(Spacer(1, 8))

        # 7.3 Test Findings
        story.append(Paragraph("7.3 Test Findings & Verification Gaps", style_h2))
        if model.test_findings:
            tf_data = [["Category", "Finding Title", "Status", "Description", "Recommendation"]]
            for tf in model.test_findings:
                tf_data.append([
                    Paragraph(tf.category, style_body_bold),
                    Paragraph(tf.title, style_body),
                    Paragraph(tf.status, style_mono),
                    Paragraph(tf.description[:120], style_body),
                    Paragraph(tf.recommendation or "—", style_body),
                ])
            tf_table = Table(tf_data, colWidths=["20%", "20%", "12%", "26%", "22%"])
            tf_table.setStyle(standard_table_style("#0f766e"))
            story.append(tf_table)
        else:
            story.append(Paragraph("No test gap findings recorded.", style_body))
        story.append(Spacer(1, 10))

        # Section 8: Repository Health
        story.append(Paragraph("8. Repository Health Score Breakdown", style_h1))
        story.append(hr())
        if model.repository_health.health_score is not None:
            story.append(Paragraph(
                f"<b>Overall Repository Health Score:</b> <font size='12' color='#059669'><b>{model.repository_health.health_score}/100</b></font>",
                style_body,
            ))
            story.append(Spacer(1, 4))
            if model.repository_health.category_scores_persisted:
                rh_data = [
                    ["Category", "Score", "Evaluation Domain"],
                    ["Architecture", f"{model.repository_health.architecture or 'N/A'}/100", "Modular boundaries, coupling, and hub nodes"],
                    ["Dependencies", f"{model.repository_health.dependencies or 'N/A'}/100", "External package health and manifest maintenance"],
                    ["Testing", f"{model.repository_health.testing or 'N/A'}/100", "Test spec coverage and test association"],
                    ["Security", f"{model.repository_health.security or 'N/A'}/100", "Sensitive file isolation and permissions"],
                    ["Maintainability", f"{model.repository_health.maintainability or 'N/A'}/100", "Orphan candidate ratio and circular imports"],
                ]
                rh_table = Table(rh_data, colWidths=["25%", "20%", "55%"])
                rh_table.setStyle(standard_table_style("#065f46"))
                story.append(rh_table)
            else:
                story.append(Paragraph("Category health scores were not persisted for this analysis.", style_caption))
        else:
            story.append(Paragraph("Category health scores were not persisted for this analysis.", style_body))
        story.append(Spacer(1, 10))

        # Section 9: Rollback & Reviewer Evidence
        story.append(Paragraph("9. Rollback Considerations & Reviewer Evidence", style_h1))
        story.append(hr())
        story.append(Paragraph("9.1 Rollback Considerations", style_h2))
        if model.rollback_considerations:
            for rc in model.rollback_considerations:
                story.append(Paragraph(f"• {rc}", style_body))
        else:
            story.append(Paragraph("Rollback analysis was not generated for this analysis.", style_body))
        story.append(Spacer(1, 6))

        story.append(Paragraph("9.2 Suggested Reviewers & Ownership Evidence", style_h2))
        if model.reviewer_evidence:
            rv_data = [["Review Area", "Suggested Reviewer", "Ownership Evidence"]]
            for r in model.reviewer_evidence:
                rv_data.append([
                    Paragraph(r.get("review_area", "—"), style_body_bold),
                    Paragraph(r.get("suggested_reviewer", "—"), style_mono),
                    Paragraph(r.get("evidence", "—"), style_body),
                ])
            rv_table = Table(rv_data, colWidths=["30%", "30%", "40%"])
            rv_table.setStyle(standard_table_style())
            story.append(rv_table)
        else:
            story.append(Paragraph("No reviewer ownership evidence recorded in persisted analysis.", style_body))
        story.append(Spacer(1, 14))

        # Audit Footer
        story.append(Paragraph(
            "<b>Deterministic Guarantee:</b> This engineering report was compiled from persisted analysis data. "
            "Risk scores, graph relationships, and findings were not re-computed or modified during export. "
            f"Generated by ChangePilot on {_fmt_dt(None)}.",
            style_caption,
        ))

        # Build document with NumberedCanvas
        header_text = f"ChangePilot Risk Assessment | {model.repository.owner}/{model.repository.name} ({model.analysis_id})"
        footer_text = f"ChangePilot Engineering Risk Assessment · {model.repository.name} · Confidential"

        def make_canvas(filename: Any, **kwargs: Any) -> Any:
            canv = NumberedCanvas(filename, **kwargs)
            canv._header_text = header_text
            canv._footer_text = footer_text
            return canv

        doc.build(story, canvasmaker=make_canvas if NumberedCanvas else None)
        return buf.getvalue()
