"""Production-grade ExportService for ChangePilot analysis results.

All four export methods receive pre-fetched, persisted analysis data.
Risk scores and findings are NEVER re-computed during export.
Every export is scoped to a specific repository_id + analysis_id.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from app.models.analysis import ChangeAnalysisResult
from app.models.repository import RepositorySummary
from app.models.risk import EvidenceStatement, RiskBreakdownItem, RiskEvidence


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
    return {
        "low": "#16a34a",
        "medium": "#d97706",
        "high": "#ea580c",
        "critical": "#dc2626",
    }.get(level.lower(), "#6b7280")


def _level_upper(level: str) -> str:
    return level.upper()


# ---------------------------------------------------------------------------
# JSON Export
# ---------------------------------------------------------------------------


class ExportService:
    """Service that generates analysis exports in JSON, CSV, Markdown, and PDF."""

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def export_json(
        self,
        analysis: ChangeAnalysisResult,
        repository: RepositorySummary,
    ) -> bytes:
        """Return a complete, machine-readable JSON export of the analysis.

        All evidence, facts, inferences, recommendations, dependency edges,
        blast radius, and metrics are preserved. Nothing is flattened.
        """
        payload: dict[str, Any] = {
            "export_format": "json",
            "export_timestamp": datetime.now(UTC).isoformat(),
            # Metadata
            "metadata": {
                "repository_id": repository.id,
                "repository_name": repository.name,
                "owner": repository.owner,
                "branch": repository.default_branch,
                "analysis_id": analysis.id,
                "analysis_timestamp": analysis.analysis_timestamp,
                "analysis_version": analysis.parser_version,
                "risk_engine_version": analysis.risk_engine_version,
                "graph_version": analysis.graph_version,
            },
            # Risk summary
            "risk_summary": {
                "score": analysis.risk.score,
                "level": str(analysis.risk.level),
                "evidence_completeness": analysis.risk.evidence_completeness,
                "confidence": analysis.risk.confidence,
                "is_calibrated": analysis.risk.is_calibrated,
                "calibration_status": analysis.risk.calibration_status,
                "score_description": analysis.risk.score_description,
            },
            # Changed files & blast radius
            "changed_files": analysis.changed_files,
            "impacted_modules": analysis.impacted_modules,
            # Full risk result — all fields
            "risk_factors": [item.model_dump() for item in (analysis.risk.risk_breakdown or [])],
            "facts": [s.model_dump() for s in (analysis.risk.facts or [])],
            "inferences": [s.model_dump() for s in (analysis.risk.inferences or [])],
            "recommendations": [s.model_dump() for s in (analysis.risk.recommendations or [])],
            "evidence": [e.model_dump() for e in (analysis.risk.evidence or [])],
            "potential_failure_scenarios": analysis.risk.potential_failure_scenarios or [],
            "deployment_considerations": analysis.risk.deployment_considerations or [],
            "recommended_review_areas": analysis.risk.recommended_review_areas or [],
            "reasons": analysis.risk.reasons or [],
            "audit": analysis.risk.audit or {},
            # Dependency graph
            "dependency_edges": [e.model_dump() for e in (analysis.dependency_graph.edges or [])],
            "dependency_nodes": [n.model_dump() for n in (analysis.dependency_graph.nodes or [])],
            "graph_health": (
                analysis.dependency_graph.graph_health.model_dump()
                if analysis.dependency_graph.graph_health
                else None
            ),
            # AI report (if available)
            "ai_report": analysis.ai_report,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False, default=str).encode("utf-8")

    # ------------------------------------------------------------------
    # CSV (ZIP)
    # ------------------------------------------------------------------

    def export_csv(
        self,
        analysis: ChangeAnalysisResult,
        repository: RepositorySummary,
    ) -> bytes:
        """Return a ZIP archive containing six CSV datasets.

        Files:
          - risk_factors.csv
          - changed_files.csv
          - impacted_files.csv
          - dependencies.csv
          - test_gaps.csv
          - repository_metrics.csv
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("risk_factors.csv", self._csv_risk_factors(analysis))
            zf.writestr("changed_files.csv", self._csv_changed_files(analysis))
            zf.writestr("impacted_files.csv", self._csv_impacted_files(analysis))
            zf.writestr("dependencies.csv", self._csv_dependencies(analysis))
            zf.writestr("test_gaps.csv", self._csv_test_gaps(analysis))
            zf.writestr("repository_metrics.csv", self._csv_repo_metrics(analysis, repository))
        return buf.getvalue()

    def _csv_bytes(self, rows: list[list[str]], headers: list[str]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows(rows)
        return buf.getvalue()

    def _csv_risk_factors(self, analysis: ChangeAnalysisResult) -> str:
        headers = [
            "id", "rule", "name", "category", "points", "evidence",
            "affected_files", "threshold", "recommendation", "recommendation_type",
        ]
        rows: list[list[str]] = []
        for i, item in enumerate(analysis.risk.risk_breakdown or [], start=1):
            rows.append([
                f"RF-{i:03d}",
                item.rule,
                item.name or item.rule,
                item.category,
                str(item.points),
                item.evidence,
                "; ".join(item.affected_files or []),
                item.threshold or "",
                item.recommendation or "",
                str(item.recommendation_type or ""),
            ])
        return self._csv_bytes(rows, headers)

    def _csv_changed_files(self, analysis: ChangeAnalysisResult) -> str:
        headers = ["index", "file_path"]
        rows = [[str(i), f] for i, f in enumerate(analysis.changed_files or [], start=1)]
        return self._csv_bytes(rows, headers)

    def _csv_impacted_files(self, analysis: ChangeAnalysisResult) -> str:
        headers = ["index", "module_or_file", "kind"]
        rows: list[list[str]] = []
        # Include graph nodes that are impacted
        for i, node in enumerate(analysis.dependency_graph.nodes or [], start=1):
            rows.append([str(i), node.label, node.kind])
        if not rows:
            for i, m in enumerate(analysis.impacted_modules or [], start=1):
                rows.append([str(i), m, "module"])
        return self._csv_bytes(rows, headers)

    def _csv_dependencies(self, analysis: ChangeAnalysisResult) -> str:
        headers = ["id", "source", "target", "relationship", "edge_type"]
        rows: list[list[str]] = []
        for edge in analysis.dependency_graph.edges or []:
            rows.append([
                edge.id,
                edge.source,
                edge.target,
                edge.relationship,
                edge.edge_type or "",
            ])
        return self._csv_bytes(rows, headers)

    def _csv_test_gaps(self, analysis: ChangeAnalysisResult) -> str:
        headers = ["index", "type", "id", "file_or_description"]
        rows: list[list[str]] = []
        idx = 1
        # From facts/recommendations referencing test
        for stmt in (analysis.risk.recommendations or []):
            if "test" in stmt.claim.lower():
                for f in (stmt.affected_files or [""]):
                    rows.append([str(idx), "RECOMMENDATION", stmt.id, f or stmt.claim])
                    idx += 1
        # From evidence signals
        for ev in (analysis.risk.evidence or []):
            if "test" in ev.signal.lower() or "coverage" in ev.signal.lower():
                for fp in (ev.file_paths or [""]):
                    rows.append([str(idx), "EVIDENCE", ev.signal, fp or ev.description])
                    idx += 1
        if not rows:
            rows.append(["1", "INFO", "N/A", "No explicit test gaps detected"])
        return self._csv_bytes(rows, headers)

    def _csv_repo_metrics(
        self, analysis: ChangeAnalysisResult, repository: RepositorySummary
    ) -> str:
        headers = ["metric", "value"]
        graph_health = analysis.dependency_graph.graph_health
        rows = [
            ["repository_id", repository.id],
            ["repository_name", repository.name],
            ["owner", repository.owner],
            ["branch", repository.default_branch],
            ["analysis_id", analysis.id],
            ["analysis_timestamp", analysis.analysis_timestamp or ""],
            ["risk_score", str(analysis.risk.score)],
            ["risk_level", str(analysis.risk.level)],
            ["evidence_completeness", f"{(analysis.risk.evidence_completeness or 0):.4f}"],
            ["is_calibrated", str(analysis.risk.is_calibrated)],
            ["changed_files_count", str(len(analysis.changed_files or []))],
            ["impacted_modules_count", str(len(analysis.impacted_modules or []))],
            ["graph_nodes", str(len(analysis.dependency_graph.nodes or []))],
            ["graph_edges", str(len(analysis.dependency_graph.edges or []))],
            ["circular_dependencies", str(graph_health.circular_dependency_count if graph_health else 0)],
            ["orphan_candidates", str(graph_health.orphan_candidates if graph_health else 0)],
            ["risk_engine_version", analysis.risk_engine_version or "1.0.0"],
            ["graph_version", analysis.graph_version or "1.0.0"],
            ["parser_version", analysis.parser_version or "1.0.0"],
        ]
        return self._csv_bytes(rows, headers)

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def export_markdown(
        self,
        analysis: ChangeAnalysisResult,
        repository: RepositorySummary,
    ) -> bytes:
        """Return a GitHub/PR-friendly Markdown report."""
        risk = analysis.risk
        level_str = _level_upper(str(risk.level))
        completeness_pct = int(round((risk.evidence_completeness or 0) * 100))
        lines: list[str] = []

        def h(text: str, level: int = 2) -> None:
            lines.append(f"{'#' * level} {text}")
            lines.append("")

        def p(text: str) -> None:
            lines.append(text)
            lines.append("")

        def rule() -> None:
            lines.append("---")
            lines.append("")

        # Title
        lines.append(f"# Change Risk Assessment — {repository.name}")
        lines.append("")
        lines.append(
            f"> **Analysis ID:** `{analysis.id}`  "
            f"**Repository:** `{repository.owner}/{repository.name}`  "
            f"**Branch:** `{repository.default_branch}`"
        )
        lines.append(f"> **Generated:** {_fmt_dt(analysis.analysis_timestamp)}")
        lines.append("")
        rule()

        # Risk Summary
        h("Risk Summary")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| **Risk Score** | `{risk.score}/100` |")
        lines.append(f"| **Risk Level** | `{level_str}` |")
        lines.append(f"| **Evidence Completeness** | `{completeness_pct}%` |")
        lines.append(f"| **Calibration** | {risk.is_calibrated and '✅ Calibrated' or '⚠️ Deterministic (Not Calibrated)'} |")
        lines.append(f"| **Changed Files** | `{len(analysis.changed_files or [])}` |")
        lines.append(f"| **Impacted Modules** | `{len(analysis.impacted_modules or [])}` |")
        lines.append("")
        if risk.score_description:
            lines.append(f"> *{risk.score_description}*")
            lines.append("")
        rule()

        # Facts
        h("Facts")
        if risk.facts:
            for stmt in risk.facts:
                lines.append(f"**`FACT`** `[{stmt.id}]` {stmt.claim}")
                if stmt.source_evidence:
                    lines.append(f"  - *Source:* {stmt.source_evidence}")
                if stmt.affected_files:
                    lines.append(f"  - *Files:* {', '.join(f'`{f}`' for f in stmt.affected_files[:5])}")
                lines.append("")
        else:
            p("*No facts recorded.*")
        rule()

        # Impact Analysis
        h("Impact Analysis")
        lines.append("**Changed Files:**")
        lines.append("")
        for f in (analysis.changed_files or []):
            lines.append(f"- `{f}`")
        lines.append("")
        lines.append("**Impacted Modules:**")
        lines.append("")
        for m in (analysis.impacted_modules or []):
            lines.append(f"- `{m}`")
        lines.append("")

        # Inferences
        h("Inferences")
        if risk.inferences:
            for stmt in risk.inferences:
                lines.append(f"**`INFERENCE`** `[{stmt.id}]` {stmt.claim}")
                if stmt.source_evidence:
                    lines.append(f"  - *Evidence:* {stmt.source_evidence}")
                if stmt.traceability_ref:
                    lines.append(f"  - *Traces to:* `{stmt.traceability_ref}`")
                lines.append("")
        else:
            p("*No inferences recorded.*")
        rule()

        # Risk Factors
        h("Risk Factors")
        if risk.risk_breakdown:
            lines.append("| Rule | Category | Points | Evidence |")
            lines.append("|------|----------|--------|----------|")
            for item in risk.risk_breakdown:
                lines.append(
                    f"| `{item.rule}` | {item.category} | **{item.points}** | {item.evidence[:80]} |"
                )
            lines.append("")
        else:
            p("*No risk breakdown available.*")
        rule()

        # Failure Scenarios
        h("Failure Scenarios")
        if risk.potential_failure_scenarios:
            for scenario in risk.potential_failure_scenarios:
                lines.append(f"- ⚠️ {scenario}")
            lines.append("")
        else:
            p("*No failure scenarios identified.*")
        rule()

        # Test Recommendations
        h("Test Recommendations")
        test_recs = [s for s in (risk.recommendations or []) if "test" in s.claim.lower()]
        other_recs = [s for s in (risk.recommendations or []) if "test" not in s.claim.lower()]
        if test_recs:
            for stmt in test_recs:
                lines.append(f"**`RECOMMENDATION`** `[{stmt.id}]` {stmt.claim}")
                if stmt.affected_files:
                    lines.append(
                        f"  - *Files:* {', '.join(f'`{f}`' for f in stmt.affected_files[:5])}"
                    )
                lines.append("")
        else:
            p("*No specific test recommendations recorded.*")
        rule()

        # Architecture Findings
        h("Architecture Findings")
        arch_evidence = [
            e for e in (risk.evidence or [])
            if e.category in ("architecture", "infrastructure")
        ]
        if arch_evidence:
            for ev in arch_evidence:
                lines.append(f"- **{ev.name or ev.signal}**: {ev.description}")
                if ev.recommendation:
                    lines.append(f"  - *Recommendation:* {ev.recommendation}")
            lines.append("")
        else:
            p("*No architecture findings.*")
        rule()

        # Security Findings
        h("Security Findings")
        sec_evidence = [
            e for e in (risk.evidence or [])
            if e.category == "security"
        ]
        if sec_evidence:
            for ev in sec_evidence:
                lines.append(f"- 🔒 **{ev.name or ev.signal}**: {ev.description}")
                if ev.recommendation:
                    lines.append(f"  - *Recommendation:* {ev.recommendation}")
            lines.append("")
        else:
            p("*No security findings.*")
        rule()

        # Recommendations
        h("Recommendations")
        if other_recs:
            for stmt in other_recs:
                rec_type = str(stmt.recommendation_type or "").replace("_", " ").title()
                lines.append(f"**`RECOMMENDATION`** `[{stmt.id}]` [{rec_type}] {stmt.claim}")
                if stmt.affected_files:
                    lines.append(
                        f"  - *Files:* {', '.join(f'`{f}`' for f in stmt.affected_files[:5])}"
                    )
                lines.append("")
        elif not test_recs:
            p("*No recommendations recorded.*")
        rule()

        # Rollback Considerations
        h("Rollback Considerations")
        if risk.deployment_considerations:
            for consideration in risk.deployment_considerations:
                lines.append(f"- 🔄 {consideration}")
            lines.append("")
        else:
            p("*No rollback considerations recorded.*")
        rule()

        # Reviewer / Ownership Evidence
        h("Reviewer / Ownership Evidence")
        if risk.recommended_review_areas:
            lines.append("| Review Area | Suggested Reviewer | Evidence |")
            lines.append("|-------------|-------------------|----------|")
            for area in risk.recommended_review_areas:
                rev = area.get("suggested_reviewer") or "—"
                ev = area.get("evidence") or area.get("ownership_note") or ""
                area_name = area.get("review_area") or ""
                lines.append(f"| {area_name} | {rev} | {ev[:80]} |")
            lines.append("")
        else:
            p("*No reviewer/ownership evidence recorded.*")
        rule()

        # Analysis Metadata
        h("Analysis Metadata")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| `repository_id` | `{repository.id}` |")
        lines.append(f"| `repository_name` | `{repository.name}` |")
        lines.append(f"| `owner` | `{repository.owner}` |")
        lines.append(f"| `branch` | `{repository.default_branch}` |")
        lines.append(f"| `analysis_id` | `{analysis.id}` |")
        lines.append(f"| `analysis_timestamp` | `{analysis.analysis_timestamp or ''}` |")
        lines.append(f"| `risk_engine_version` | `{analysis.risk_engine_version or '1.0.0'}` |")
        lines.append(f"| `graph_version` | `{analysis.graph_version or '1.0.0'}` |")
        lines.append(f"| `parser_version` | `{analysis.parser_version or '1.0.0'}` |")
        lines.append("")
        lines.append(
            "*This report was generated from persisted analysis data. "
            "Risk scores were not re-computed during export.*"
        )
        lines.append("")

        return "\n".join(lines).encode("utf-8")

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def export_pdf(
        self,
        analysis: ChangeAnalysisResult,
        repository: RepositorySummary,
    ) -> bytes:
        """Return a professional enterprise PDF report generated from structured data."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm, mm
            from reportlab.platypus import (
                HRFlowable,
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

        buf = io.BytesIO()
        risk = analysis.risk
        level_str = _level_upper(str(risk.level))
        level_hex = _risk_color_hex(str(risk.level))
        completeness_pct = int(round((risk.evidence_completeness or 0) * 100))

        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        # Custom styles
        style_title = ParagraphStyle(
            "CPTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=4,
            leading=28,
        )
        style_subtitle = ParagraphStyle(
            "CPSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=2,
        )
        style_h1 = ParagraphStyle(
            "CPH1",
            parent=styles["Heading1"],
            fontSize=14,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=14,
            spaceAfter=6,
            borderPad=4,
        )
        style_h2 = ParagraphStyle(
            "CPH2",
            parent=styles["Heading2"],
            fontSize=11,
            textColor=colors.HexColor("#334155"),
            spaceBefore=10,
            spaceAfter=4,
        )
        style_body = ParagraphStyle(
            "CPBody",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#374151"),
            spaceAfter=3,
            leading=13,
        )
        style_mono = ParagraphStyle(
            "CPMono",
            parent=styles["Normal"],
            fontSize=8,
            fontName="Courier",
            textColor=colors.HexColor("#1e293b"),
            backColor=colors.HexColor("#f1f5f9"),
            spaceAfter=2,
            leading=12,
        )
        style_caption = ParagraphStyle(
            "CPCaption",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#9ca3af"),
            spaceAfter=2,
            alignment=TA_CENTER,
        )
        style_label_fact = ParagraphStyle(
            "CPFact", parent=style_body,
            textColor=colors.HexColor("#1d4ed8"), fontName="Helvetica-Bold",
        )
        style_label_inf = ParagraphStyle(
            "CPInf", parent=style_body,
            textColor=colors.HexColor("#7c3aed"), fontName="Helvetica-Bold",
        )
        style_label_rec = ParagraphStyle(
            "CPRec", parent=style_body,
            textColor=colors.HexColor("#047857"), fontName="Helvetica-Bold",
        )

        def hr() -> HRFlowable:
            return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=6)

        def table_style(header_bg: str = "#1e293b") -> TableStyle:
            return TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ])

        story: list = []

        # ---- Cover / Header ----
        story.append(Paragraph("ChangePilot", ParagraphStyle(
            "Brand", parent=style_body,
            fontSize=10, textColor=colors.HexColor("#6366f1"), fontName="Helvetica-Bold",
        )))
        story.append(Spacer(1, 4))
        story.append(Paragraph("Change Risk Assessment Report", style_title))
        story.append(Paragraph(f"{repository.owner}/{repository.name}", style_subtitle))
        story.append(Paragraph(
            f"Branch: {repository.default_branch}  |  Analysis ID: {analysis.id}",
            style_subtitle,
        ))
        story.append(Paragraph(
            f"Generated: {_fmt_dt(analysis.analysis_timestamp)}",
            style_subtitle,
        ))
        story.append(Spacer(1, 8))
        story.append(hr())

        # ---- Risk Score Banner ----
        risk_banner_data = [
            ["Risk Score", "Risk Level", "Evidence Completeness", "Calibration"],
            [
                Paragraph(f"<b><font size='18'>{risk.score}/100</font></b>", ParagraphStyle(
                    "Score", parent=style_body, alignment=TA_CENTER,
                    textColor=colors.HexColor(level_hex),
                )),
                Paragraph(f"<b>{level_str}</b>", ParagraphStyle(
                    "Level", parent=style_body, alignment=TA_CENTER,
                    textColor=colors.HexColor(level_hex),
                )),
                Paragraph(f"<b>{completeness_pct}%</b>", ParagraphStyle(
                    "EC", parent=style_body, alignment=TA_CENTER,
                )),
                Paragraph(
                    "✓ Calibrated" if risk.is_calibrated else "Deterministic",
                    ParagraphStyle("Cal", parent=style_body, alignment=TA_CENTER),
                ),
            ],
        ]
        risk_banner_table = Table(risk_banner_data, colWidths=["25%", "25%", "25%", "25%"])
        risk_banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ]))
        story.append(risk_banner_table)
        story.append(Spacer(1, 4))
        if risk.score_description:
            story.append(Paragraph(risk.score_description, style_caption))
        story.append(Spacer(1, 8))

        # ---- Repository Information ----
        story.append(Paragraph("Repository Information", style_h1))
        story.append(hr())
        repo_data = [
            ["Field", "Value"],
            ["Repository ID", repository.id],
            ["Name", repository.name],
            ["Owner", repository.owner or "—"],
            ["Branch", repository.default_branch],
            ["Language", repository.language or "—"],
            ["Source", repository.source],
            ["URL", repository.url or "—"],
        ]
        repo_table = Table(repo_data, colWidths=["35%", "65%"])
        repo_table.setStyle(table_style())
        story.append(repo_table)
        story.append(Spacer(1, 6))

        # ---- Risk Breakdown ----
        story.append(Paragraph("Risk Breakdown", style_h1))
        story.append(hr())
        if risk.risk_breakdown:
            bd_data = [["Rule", "Category", "Pts", "Evidence", "Affected Files"]]
            for item in risk.risk_breakdown:
                bd_data.append([
                    Paragraph(item.rule, style_mono),
                    item.category,
                    str(item.points),
                    Paragraph((item.evidence or "")[:120], style_body),
                    Paragraph(", ".join((item.affected_files or [])[:3]), style_body),
                ])
            bd_table = Table(bd_data, colWidths=["22%", "13%", "7%", "36%", "22%"])
            bd_table.setStyle(table_style())
            story.append(bd_table)
        else:
            story.append(Paragraph("No risk breakdown available.", style_body))
        story.append(Spacer(1, 6))

        # ---- Changed Files ----
        story.append(Paragraph("Changed Files", style_h1))
        story.append(hr())
        if analysis.changed_files:
            cf_data = [["#", "File Path"]]
            for i, f in enumerate(analysis.changed_files, start=1):
                cf_data.append([str(i), Paragraph(f, style_mono)])
            cf_table = Table(cf_data, colWidths=["8%", "92%"])
            cf_table.setStyle(table_style())
            story.append(cf_table)
        else:
            story.append(Paragraph("No changed files recorded.", style_body))
        story.append(Spacer(1, 6))

        # ---- Blast Radius / Dependency Findings ----
        story.append(Paragraph("Blast Radius & Dependency Findings", style_h1))
        story.append(hr())
        graph = analysis.dependency_graph
        gh = graph.graph_health
        br_data = [["Metric", "Value"]]
        br_data.append(["Total Nodes", str(len(graph.nodes or []))])
        br_data.append(["Total Edges", str(len(graph.edges or []))])
        br_data.append(["Impacted Modules", str(len(analysis.impacted_modules or []))])
        if gh:
            br_data.append(["Circular Dependencies", str(gh.circular_dependency_count)])
            br_data.append(["Orphan Candidates", str(gh.orphan_candidates)])
            br_data.append(["Unresolved Imports", str(gh.unresolved_imports)])
        br_table = Table(br_data, colWidths=["40%", "60%"])
        br_table.setStyle(table_style())
        story.append(br_table)
        story.append(Spacer(1, 4))
        # Graph warnings
        if gh and gh.warnings:
            story.append(Paragraph("Graph Warnings:", style_h2))
            for w in gh.warnings[:10]:
                story.append(Paragraph(f"• {w}", style_body))
        story.append(Spacer(1, 6))

        # ---- Architecture Findings ----
        story.append(Paragraph("Architecture Findings", style_h1))
        story.append(hr())
        arch_ev = [e for e in (risk.evidence or []) if e.category in ("architecture", "infrastructure")]
        if arch_ev:
            for ev in arch_ev:
                story.append(Paragraph(f"<b>{ev.name or ev.signal}</b>: {ev.description}", style_body))
                if ev.recommendation:
                    story.append(Paragraph(f"   → {ev.recommendation}", style_body))
        else:
            story.append(Paragraph("No architecture findings.", style_body))
        story.append(Spacer(1, 6))

        # ---- Security Findings ----
        story.append(Paragraph("Security Findings", style_h1))
        story.append(hr())
        sec_ev = [e for e in (risk.evidence or []) if e.category == "security"]
        if sec_ev:
            sec_data = [["Signal", "Description", "Recommendation"]]
            for ev in sec_ev:
                sec_data.append([
                    Paragraph(ev.name or ev.signal, style_mono),
                    Paragraph(ev.description[:120], style_body),
                    Paragraph((ev.recommendation or "")[:80], style_body),
                ])
            sec_table = Table(sec_data, colWidths=["25%", "40%", "35%"])
            sec_table.setStyle(table_style("#7f1d1d"))
            story.append(sec_table)
        else:
            story.append(Paragraph("No security findings.", style_body))
        story.append(Spacer(1, 6))

        # ---- Key Findings: Facts & Inferences ----
        story.append(Paragraph("Key Findings", style_h1))
        story.append(hr())
        story.append(Paragraph("Facts", style_h2))
        if risk.facts:
            for stmt in risk.facts[:20]:
                story.append(Paragraph(
                    f"<b>[{stmt.id}]</b> <font color='#1d4ed8'>[FACT]</font> {stmt.claim}",
                    style_body,
                ))
                if stmt.source_evidence:
                    story.append(Paragraph(f"   Source: {stmt.source_evidence}", style_body))
        else:
            story.append(Paragraph("No facts recorded.", style_body))
        story.append(Spacer(1, 4))

        story.append(Paragraph("Inferences", style_h2))
        if risk.inferences:
            for stmt in risk.inferences[:20]:
                story.append(Paragraph(
                    f"<b>[{stmt.id}]</b> <font color='#7c3aed'>[INFERENCE]</font> {stmt.claim}",
                    style_body,
                ))
                if stmt.traceability_ref:
                    story.append(Paragraph(f"   Traces to: {stmt.traceability_ref}", style_body))
        else:
            story.append(Paragraph("No inferences recorded.", style_body))
        story.append(Spacer(1, 6))

        # ---- Test Gaps ----
        story.append(Paragraph("Potential Test Gaps", style_h1))
        story.append(hr())
        test_items = [s for s in (risk.recommendations or []) if "test" in s.claim.lower()]
        if test_items:
            tg_data = [["ID", "Recommendation", "Files"]]
            for stmt in test_items:
                tg_data.append([
                    stmt.id,
                    Paragraph(stmt.claim[:120], style_body),
                    Paragraph(", ".join((stmt.affected_files or [])[:3]), style_body),
                ])
            tg_table = Table(tg_data, colWidths=["12%", "55%", "33%"])
            tg_table.setStyle(table_style())
            story.append(tg_table)
        else:
            story.append(Paragraph("No explicit test gaps detected.", style_body))
        story.append(Spacer(1, 6))

        # ---- Recommendations ----
        story.append(Paragraph("Recommendations", style_h1))
        story.append(hr())
        non_test_recs = [s for s in (risk.recommendations or []) if "test" not in s.claim.lower()]
        all_recs = non_test_recs or (risk.recommendations or [])
        if all_recs:
            for stmt in all_recs[:30]:
                rec_type = str(stmt.recommendation_type or "").replace("_", " ").title() or "General"
                story.append(Paragraph(
                    f"<b>[{stmt.id}]</b> <font color='#047857'>[RECOMMENDATION]</font> "
                    f"<i>[{rec_type}]</i> {stmt.claim}",
                    style_body,
                ))
                if stmt.affected_files:
                    story.append(Paragraph(
                        f"   → Files: {', '.join(stmt.affected_files[:5])}",
                        style_body,
                    ))
        else:
            story.append(Paragraph("No recommendations recorded.", style_body))
        story.append(Spacer(1, 6))

        # ---- Rollback Considerations ----
        story.append(Paragraph("Rollback Considerations", style_h1))
        story.append(hr())
        if risk.deployment_considerations:
            for c in risk.deployment_considerations:
                story.append(Paragraph(f"• {c}", style_body))
        else:
            story.append(Paragraph("No rollback considerations recorded.", style_body))
        story.append(Spacer(1, 6))

        # ---- Repository Health ----
        if gh:
            story.append(Paragraph("Repository Health", style_h1))
            story.append(hr())
            health_data = [
                ["Metric", "Value"],
                ["Total Graph Nodes", str(gh.node_count)],
                ["Total Graph Edges", str(gh.edge_count)],
                ["Circular Dependencies", str(gh.circular_dependency_count)],
                ["Orphan Candidates", str(gh.orphan_candidates)],
                ["Unresolved Imports", str(gh.unresolved_imports)],
                ["Self Imports", str(gh.self_edge_count)],
                ["Duplicate Edges", str(gh.duplicate_edge_count)],
                ["Invalid Paths", str(gh.invalid_paths)],
            ]
            h_table = Table(health_data, colWidths=["40%", "60%"])
            h_table.setStyle(table_style())
            story.append(h_table)
            story.append(Spacer(1, 6))

        # ---- Failure Scenarios ----
        if risk.potential_failure_scenarios:
            story.append(Paragraph("Failure Scenarios", style_h1))
            story.append(hr())
            for scenario in risk.potential_failure_scenarios:
                story.append(Paragraph(f"⚠ {scenario}", style_body))
            story.append(Spacer(1, 6))

        # ---- Reviewer / Ownership ----
        if risk.recommended_review_areas:
            story.append(Paragraph("Reviewer / Ownership Evidence", style_h1))
            story.append(hr())
            rv_data = [["Review Area", "Suggested Reviewer", "Evidence"]]
            for area in risk.recommended_review_areas:
                rv_data.append([
                    area.get("review_area") or "",
                    area.get("suggested_reviewer") or "—",
                    Paragraph((area.get("evidence") or area.get("ownership_note") or "")[:80], style_body),
                ])
            rv_table = Table(rv_data, colWidths=["30%", "25%", "45%"])
            rv_table.setStyle(table_style())
            story.append(rv_table)
            story.append(Spacer(1, 6))

        # ---- Analysis Metadata ----
        story.append(PageBreak())
        story.append(Paragraph("Analysis Metadata", style_h1))
        story.append(hr())
        meta_data = [
            ["Field", "Value"],
            ["repository_id", repository.id],
            ["repository_name", repository.name],
            ["owner", repository.owner or "—"],
            ["branch", repository.default_branch],
            ["analysis_id", analysis.id],
            ["analysis_timestamp", analysis.analysis_timestamp or "—"],
            ["analysis_version", analysis.parser_version or "1.0.0"],
            ["risk_engine_version", analysis.risk_engine_version or "1.0.0"],
            ["graph_version", analysis.graph_version or "1.0.0"],
            ["parser_version", analysis.parser_version or "1.0.0"],
        ]
        meta_table = Table(meta_data, colWidths=["35%", "65%"])
        meta_table.setStyle(table_style())
        story.append(meta_table)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This report was generated from persisted analysis data. "
            "Risk scores were not re-computed during export. "
            f"Generated by ChangePilot on {_fmt_dt(None)}.",
            style_caption,
        ))

        doc.build(story)
        return buf.getvalue()
