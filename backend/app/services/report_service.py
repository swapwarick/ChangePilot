import json

from app.models.ai_provider import AIMessage, AIRequest
from app.models.analysis import ChangeAnalysisResult
from app.prompts.manager import DEFAULT_PROMPTS, PromptManager
from app.providers.registry import AIProviderRegistry


class AIReportService:
    def __init__(
        self,
        provider_registry: AIProviderRegistry,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self._provider_registry = provider_registry
        self._prompt_manager = prompt_manager or PromptManager(DEFAULT_PROMPTS)

    async def generate_report(self, analysis: ChangeAnalysisResult) -> str:
        facts_data = [stmt.model_dump() for stmt in analysis.risk.facts]
        inferences_data = [stmt.model_dump() for stmt in analysis.risk.inferences]
        recommendations_data = [stmt.model_dump() for stmt in analysis.risk.recommendations]
        review_areas_data = analysis.risk.recommended_review_areas
        deployment_evidence_data = analysis.risk.deployment_considerations

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
            },
        )
        response = await self._provider_registry.generate_with_fallback(
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
        )
        return response.content

