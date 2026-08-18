import asyncio
import json
import logging

from app.models.ai_provider import AIMessage, AIRequest
from app.models.analysis import ChangeAnalysisResult
from app.prompts.manager import DEFAULT_PROMPTS, PromptManager
from app.providers.registry import AIProviderRegistry

logger = logging.getLogger(__name__)


class AIReportService:
    def __init__(
        self,
        provider_registry: AIProviderRegistry,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self._provider_registry = provider_registry
        self._prompt_manager = prompt_manager or PromptManager(DEFAULT_PROMPTS)

    def generate_deterministic_summary(self, analysis: ChangeAnalysisResult) -> str:
        """Generates a grounded, evidence-backed architectural synthesis when no external LLM is configured."""
        completeness_pct = int(round(analysis.risk.evidence_completeness * 100))
        lines = [
            "# Executive Architectural & Risk Synthesis",
            f"**Repository**: `{analysis.repository_id}`",
            f"**Deterministic Risk Score**: `{analysis.risk.score}/100` ({analysis.risk.level.value.upper()})",
            f"**Evidence Completeness**: `{completeness_pct}%`",
            "",
            "## 1. Executive Summary",
            f"ChangePilot analyzed {len(analysis.changed_files)} changed file(s) across impacted module(s): **{', '.join(analysis.impacted_modules) if analysis.impacted_modules else 'root'}**.",
            f"The Knowledge Graph topology contains {len(analysis.dependency_graph.nodes)} AST nodes and {len(analysis.dependency_graph.edges)} dependency edges.",
            "",
            "## 2. Active Risk Findings & Evidence Breakdown",
        ]

        if analysis.risk.risk_breakdown:
            for item in analysis.risk.risk_breakdown:
                name = item.name or item.rule.replace("_", " ").title()
                files_str = f" ({len(item.affected_files)} file(s))" if item.affected_files else ""
                lines.append(f"- **{name}** (+{item.points} pts) [{item.category.upper()}]{files_str}: {item.evidence}")
                if item.recommendation:
                    lines.append(f"  - *Actionable Guidance*: {item.recommendation}")
        else:
            lines.append("- No high-risk policy violations detected in the changed files.")

        if analysis.risk.facts:
            lines.append("")
            lines.append("## 3. Verified Codebase Facts")
            for fact in analysis.risk.facts:
                lines.append(f"- {fact.claim}")

        if analysis.risk.recommendations:
            lines.append("")
            lines.append("## 4. Architectural Guidance & Review Focus")
            for rec in analysis.risk.recommendations:
                lines.append(f"- {rec.claim}")

        if analysis.risk.deployment_considerations:
            lines.append("")
            lines.append("## 5. Deployment & Rollback Considerations")
            for dep in analysis.risk.deployment_considerations:
                lines.append(f"- {dep}")

        return "\n".join(lines)

    async def generate_report(self, analysis: ChangeAnalysisResult) -> str:
        # Check if any active provider is available
        active_providers = getattr(self._provider_registry, "_providers", {})
        if not active_providers:
            return self.generate_deterministic_summary(analysis)

        facts_data = [stmt.model_dump() for stmt in analysis.risk.facts]
        inferences_data = [stmt.model_dump() for stmt in analysis.risk.inferences]
        recommendations_data = [stmt.model_dump() for stmt in analysis.risk.recommendations]
        review_areas_data = analysis.risk.recommended_review_areas
        deployment_evidence_data = analysis.risk.deployment_considerations
        risk_breakdown_data = [item.model_dump() for item in analysis.risk.risk_breakdown]

        prompt = self._prompt_manager.render(
            "risk_report",
            {
                "risk_json": analysis.risk.model_dump_json(indent=2),
                "graph_summary": json.dumps(
                    {
                        "nodes": len(analysis.dependency_graph.nodes),
                        "edges": len(analysis.dependency_graph.edges),
                        "impacted_modules": analysis.impacted_modules,
                    },
                    indent=2,
                ),
                "facts_json": json.dumps(facts_data, indent=2),
                "inferences_json": json.dumps(inferences_data, indent=2),
                "recommendations_json": json.dumps(recommendations_data, indent=2),
                "review_areas_json": json.dumps(review_areas_data, indent=2),
                "deployment_evidence_json": json.dumps(deployment_evidence_data, indent=2),
                "risk_breakdown_json": json.dumps(risk_breakdown_data, indent=2),
            },
        )

        try:
            response = await asyncio.wait_for(
                self._provider_registry.generate_with_fallback(
                    AIRequest(
                        task_category="report",
                        messages=[
                            AIMessage(
                                role="system",
                                content=(
                                    "You are a Principal Software Architect synthesizing a scientifically defensible change risk assessment. "
                                    "Ground all statements strictly in the supplied structured evidence. "
                                    "Never invent unreferenced files, false dependencies, or speculative facts. "
                                    "Never call files, folders, or modules 'services'. "
                                    "Never recalculate or override risk scores or evidence completeness metrics."
                                ),
                            ),
                            AIMessage(role="user", content=prompt),
                        ],
                    )
                ),
                timeout=25.0,
            )
            return response.content
        except Exception as exc:
            logger.warning("LLM generation unavailable (%s). Using deterministic architectural synthesis.", exc)
            return self.generate_deterministic_summary(analysis)
