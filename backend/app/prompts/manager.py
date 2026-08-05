import re

from app.models.prompts import PromptTemplate

VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptManager:
    def __init__(self, templates: list[PromptTemplate] | None = None) -> None:
        self._templates = {(template.category, template.version): template for template in templates or []}

    def add_template(self, template: PromptTemplate) -> None:
        self._templates[(template.category, template.version)] = template

    def latest(self, category: str) -> PromptTemplate:
        matches = [template for (template_category, _), template in self._templates.items() if template_category == category]
        if not matches:
            raise KeyError(f"No prompt template for category: {category}")
        return max(matches, key=lambda template: template.version)

    def render(self, category: str, variables: dict[str, str], version: int | None = None) -> str:
        template = self._templates[(category, version)] if version else self.latest(category)
        missing = [name for name in template.variables if name not in variables]
        if missing:
            raise ValueError(f"Missing prompt variables: {', '.join(missing)}")

        def replace(match: re.Match[str]) -> str:
            return variables.get(match.group(1), "")

        return VARIABLE_PATTERN.sub(replace, template.template)


DEFAULT_PROMPTS = [
    PromptTemplate(
        id="risk-report-v1",
        category="risk_report",
        version=1,
        variables=["risk_json", "graph_summary"],
        template=(
            "You are explaining a deterministic software change risk analysis. "
            "Do not invent evidence and do not calculate a new score. "
            "Reference only the deterministic evidence below.\n\n"
            "Risk evidence JSON:\n{{ risk_json }}\n\n"
            "Dependency graph summary:\n{{ graph_summary }}\n\n"
            "Produce: executive summary, blast radius explanation, failure scenarios, "
            "suggested reviewers, rollback checklist, testing recommendations, deployment advice."
        ),
    )
]


