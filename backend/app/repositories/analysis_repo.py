"""Persistence for change analysis results."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.tables import AnalysisRow
from app.models.analysis import ChangeAnalysisResult
from app.models.enums import AnalysisTrigger, RiskLevel
from app.models.graph import DependencyGraph
from app.models.risk import (
    EvidenceStatement,
    RiskBreakdownItem,
    RiskEvidence,
    RiskResult,
)


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
            risk_level=result.risk.level.value,
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
        # Prefer the full risk result snapshot (lossless), fall back to partial reconstruction
        if row.risk_full_result:
            try:
                risk = RiskResult(**row.risk_full_result)
            except Exception:
                risk = AnalysisRepository._build_partial_risk(row)
        else:
            risk = AnalysisRepository._build_partial_risk(row)

        return ChangeAnalysisResult(
            id=row.id,
            repository_id=row.repository_id,
            trigger=AnalysisTrigger(row.trigger),
            changed_files=row.changed_files,
            impacted_modules=row.impacted_modules,
            dependency_graph=DependencyGraph(**row.dependency_graph),
            risk=risk,
            ai_report=row.ai_report,
            parser_version=getattr(row, "parser_version", "1.0.0"),
            graph_version=getattr(row, "graph_version", "1.0.0"),
            risk_engine_version=getattr(row, "risk_engine_version", "1.0.0"),
            analysis_timestamp=row.created_at.isoformat() if row.created_at else None,
        )

    @staticmethod
    def _build_partial_risk(row: AnalysisRow) -> RiskResult:
        """Reconstruct a partial RiskResult from individual columns (legacy rows)."""
        evidence: list[RiskEvidence] = []
        for item in (row.risk_evidence or []):
            try:
                evidence.append(RiskEvidence(**item))
            except Exception:
                pass

        return RiskResult(
            score=row.risk_score,
            level=RiskLevel(row.risk_level),
            confidence=row.risk_confidence,
            evidence_completeness=getattr(row, "evidence_completeness", row.risk_confidence),
            is_calibrated=getattr(row, "is_calibrated", False),
            calibration_status=getattr(row, "calibration_status", "NOT_CALIBRATED"),
            evidence=evidence,
            reasons=row.risk_reasons or [],
        )

    @staticmethod
    def _safe_statements(raw: list[dict]) -> list[EvidenceStatement]:
        result: list[EvidenceStatement] = []
        for item in (raw or []):
            try:
                result.append(EvidenceStatement(**item))
            except Exception:
                pass
        return result

    @staticmethod
    def _safe_breakdown(raw: list[dict]) -> list[RiskBreakdownItem]:
        result: list[RiskBreakdownItem] = []
        for item in (raw or []):
            try:
                result.append(RiskBreakdownItem(**item))
            except Exception:
                pass
        return result
