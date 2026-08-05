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
            },
        )
        response = await self._provider_registry.generate_with_fallback(
            AIRequest(
                task_category="report",
                messages=[
                    AIMessage(
                        role="system",
                        content="Explain deterministic evidence. Never recalculate or override scores.",
                    ),
                    AIMessage(role="user", content=prompt),
                ],
            )
        )
        return response.content

