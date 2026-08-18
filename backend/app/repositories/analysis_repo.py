"""Persistence for change analysis results."""

from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import AnalysisRow
from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger, RecommendationType, RiskLevel, StatementType
from app.models.graph import DependencyGraph
from app.models.risk import (
    EvidenceStatement,
    RiskBreakdownItem,
    RiskEvidence,
    RiskResult,
)


def _safe_json_decode(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


class AnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, result: ChangeAnalysisResult) -> ChangeAnalysisResult:
        row = AnalysisRow(
            id=result.id,
            repository_id=result.repository_id,
            trigger=result.trigger.value,
            changed_files=result.changed_files,
            impacted_modules=result.impacted_modules,
            dependency_graph=result.dependency_graph.model_dump(),
            risk_score=result.risk.score,
            risk_level=result.risk.level.value if hasattr(result.risk.level, "value") else str(result.risk.level),
            risk_confidence=result.risk.confidence,
            evidence_completeness=result.risk.evidence_completeness,
            is_calibrated=result.risk.is_calibrated,
            calibration_status=result.risk.calibration_status,
            risk_evidence=[item.model_dump() for item in result.risk.evidence],
            risk_reasons=result.risk.reasons,
            ai_report=result.ai_report,
            # Persist the full risk result snapshot for lossless export
            risk_full_result=result.risk.model_dump(),
        )
        merged = await self._session.merge(row)
        await self._session.commit()
        await self._session.refresh(merged)
        return self._to_schema(merged)

    async def get(self, analysis_id: str) -> ChangeAnalysisResult | None:
        row = await self._session.get(AnalysisRow, analysis_id)
        return self._to_schema(row) if row else None

    async def list_by_repository(
        self, repository_id: str, *, limit: int = 50
    ) -> list[ChangeAnalysisResult]:
        stmt = (
            select(AnalysisRow)
            .where(AnalysisRow.repository_id == repository_id)
            .order_by(AnalysisRow.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_schema(row) for row in result.scalars()]

    @staticmethod
    def _to_schema(row: AnalysisRow) -> ChangeAnalysisResult:
        full_result_raw = _safe_json_decode(row.risk_full_result)
        dep_graph_raw = _safe_json_decode(row.dependency_graph) or {}
        changed_files_raw = _safe_json_decode(row.changed_files) or []
        impacted_modules_raw = _safe_json_decode(row.impacted_modules) or []

        risk: RiskResult | None = None
        if full_result_raw and isinstance(full_result_raw, dict):
            try:
                risk = RiskResult(**full_result_raw)
            except Exception:
                risk = None

        if risk is None or not risk.risk_breakdown:
            partial_risk = AnalysisRepository._build_partial_risk(row)
            if risk is None:
                risk = partial_risk
            else:
                # Merge missing collections
                if not risk.risk_breakdown:
                    risk.risk_breakdown = partial_risk.risk_breakdown
                if not risk.facts:
                    risk.facts = partial_risk.facts
                if not risk.inferences:
                    risk.inferences = partial_risk.inferences
                if not risk.recommendations:
                    risk.recommendations = partial_risk.recommendations
                if not risk.statements:
                    risk.statements = partial_risk.statements

        return ChangeAnalysisResult(
            id=row.id,
            repository_id=row.repository_id,
            trigger=AnalysisTrigger(row.trigger),
            changed_files=changed_files_raw,
            impacted_modules=impacted_modules_raw,
            dependency_graph=DependencyGraph(**dep_graph_raw),
            risk=risk,
            ai_report=row.ai_report,
            parser_version=getattr(row, "parser_version", "1.0.0"),
            graph_version=getattr(row, "graph_version", "1.0.0"),
            risk_engine_version=getattr(row, "risk_engine_version", "1.0.0"),
            analysis_timestamp=row.created_at.isoformat() if row.created_at else None,
        )

    @staticmethod
    def _build_partial_risk(row: AnalysisRow) -> RiskResult:
        """Reconstruct a complete, evidence-grounded RiskResult from individual columns."""
        evidence_raw = _safe_json_decode(row.risk_evidence) or []
        changed_files_raw = _safe_json_decode(row.changed_files) or []
        impacted_modules_raw = _safe_json_decode(row.impacted_modules) or []
        reasons_raw = _safe_json_decode(row.risk_reasons) or []

        evidence: list[RiskEvidence] = []
        for item in evidence_raw:
            try:
                if isinstance(item, dict):
                    evidence.append(RiskEvidence(**item))
            except Exception:
                pass

        # Synthesize risk breakdown from evidence
        risk_breakdown: list[RiskBreakdownItem] = []
        raw_rule_score = 0.0
        for ev in sorted(evidence, key=lambda x: x.weight * x.score, reverse=True):
            pts = int(round(ev.weight * ev.score * 100))
            raw_rule_score += pts
            risk_breakdown.append(
                RiskBreakdownItem(
                    rule=ev.rule or ev.signal,
                    name=ev.name or ev.rule or ev.signal,
                    category=ev.category,
                    points=pts,
                    evidence=ev.description,
                    affected_files=ev.file_paths or [],
                    threshold=ev.threshold or "",
                    recommendation=ev.recommendation or "",
                    recommendation_type=ev.recommendation_type,
                )
            )

        # Synthesize facts
        facts: list[EvidenceStatement] = []
        fact_idx = 1
        facts.append(
            EvidenceStatement(
                id=f"FACT-{fact_idx:03d}",
                statement_type=StatementType.FACT,
                claim=f"{len(changed_files_raw)} file(s) modified in this change set.",
                source_evidence="Git commit diff analysis",
                affected_files=changed_files_raw[:20],
                traceability_ref="git_diff_stat",
            )
        )
        fact_idx += 1

        if impacted_modules_raw:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim=f"Change impact intersects {len(impacted_modules_raw)} architectural module(s): {', '.join(impacted_modules_raw[:5])}",
                    source_evidence="AST module resolution",
                    traceability_ref="module_resolution",
                )
            )
            fact_idx += 1

        for ev in evidence:
            if ev.signal in (
                "dependency_upgrades", "authentication_change", "env_vars_changed",
                "database_schema", "public_api_changed", "critical_component_modified",
                "large_refactor", "migration_detected"
            ):
                facts.append(
                    EvidenceStatement(
                        id=f"FACT-{fact_idx:03d}",
                        statement_type=StatementType.FACT,
                        claim=f"{ev.name or ev.signal}: {ev.description}",
                        source_evidence=f"Observed in {', '.join(ev.file_paths[:3])}" if ev.file_paths else "Repository AST scan",
                        affected_files=ev.file_paths or [],
                        traceability_ref=ev.rule or ev.signal,
                    )
                )
                fact_idx += 1

        # Synthesize inferences
        inferences: list[EvidenceStatement] = []
        inf_idx = 1
        if len(impacted_modules_raw) >= 3:
            inferences.append(
                EvidenceStatement(
                    id=f"INF-{inf_idx:03d}",
                    statement_type=StatementType.INFERENCE,
                    claim=f"Cross-module architectural coupling: change set spans {len(impacted_modules_raw)} distinct architectural domains.",
                    source_evidence="Derived from module impact analysis",
                    traceability_ref="rule:multi_module_impact",
                )
            )
            inf_idx += 1

        for ev in evidence:
            if ev.signal == "large_blast_radius":
                inferences.append(
                    EvidenceStatement(
                        id=f"INF-{inf_idx:03d}",
                        statement_type=StatementType.INFERENCE,
                        claim=f"Downstream regression risk: {ev.description}",
                        source_evidence="Derived from dependency graph traversal",
                        traceability_ref="rule:large_blast_radius",
                    )
                )
                inf_idx += 1
            elif ev.signal == "missing_tests":
                inferences.append(
                    EvidenceStatement(
                        id=f"INF-{inf_idx:03d}",
                        statement_type=StatementType.INFERENCE,
                        claim="Test coverage gap: production code changes lack accompanying unit test or test specification modifications.",
                        source_evidence="Diff analysis: 0 test files modified",
                        traceability_ref="rule:missing_tests",
                    )
                )
                inf_idx += 1
            elif ev.signal == "critical_component_modified":
                inferences.append(
                    EvidenceStatement(
                        id=f"INF-{inf_idx:03d}",
                        statement_type=StatementType.INFERENCE,
                        claim=f"Critical business workflows may be affected due to modifications in core components: {', '.join(ev.file_paths[:3])}",
                        source_evidence="Sensitive domain path keyword matching",
                        traceability_ref="rule:critical_component_modified",
                        affected_files=ev.file_paths or [],
                    )
                )
                inf_idx += 1

        # Synthesize recommendations
        recommendations: list[EvidenceStatement] = []
        rec_idx = 1
        for ev in evidence:
            if ev.recommendation:
                recommendations.append(
                    EvidenceStatement(
                        id=f"REC-{rec_idx:03d}",
                        statement_type=StatementType.RECOMMENDATION,
                        claim=ev.recommendation,
                        recommendation_type=ev.recommendation_type,
                        source_evidence=f"Triggered by {ev.name or ev.signal}: {ev.description}",
                        traceability_ref=ev.rule or ev.signal,
                        affected_files=ev.file_paths or [],
                    )
                )
                rec_idx += 1

        all_statements = facts + inferences + recommendations

        normalized_score = raw_rule_score
        if raw_rule_score > 60:
            normalized_score = 60 + (raw_rule_score - 60) * 0.5
        capped_score = int(round(row.risk_score))

        audit = {
            "raw_rule_score": round(raw_rule_score, 2),
            "normalized_score": round(normalized_score, 2),
            "capped_score": capped_score,
            "evidence_completeness": getattr(row, "evidence_completeness", row.risk_confidence),
        }

        return RiskResult(
            score=capped_score,
            level=RiskLevel(row.risk_level),
            confidence=row.risk_confidence,
            evidence_completeness=getattr(row, "evidence_completeness", row.risk_confidence),
            is_calibrated=getattr(row, "is_calibrated", False),
            calibration_status=getattr(
                row, "calibration_status",
                "Not statistically calibrated against historical production failure outcomes. Deterministic engineering index only."
            ),
            score_description="Deterministic change-risk index based on repository evidence. This score is not a statistical probability of production failure.",
            evidence=evidence,
            statements=all_statements,
            facts=facts,
            inferences=inferences,
            recommendations=recommendations,
            risk_breakdown=risk_breakdown,
            reasons=reasons_raw or [ev.description for ev in evidence],
            audit=audit,
        )
