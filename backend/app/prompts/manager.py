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
        id="risk-report-v2",
        category="risk_report",
        version=2,
        variables=["risk_json", "graph_summary", "facts_json", "inferences_json", "recommendations_json", "review_areas_json", "deployment_evidence_json"],
        template=(
            "You are a Principal Software Architect and Risk Analysis Engineer synthesizing a change risk assessment.\n\n"
            "CRITICAL GROUNDING RULES:\n"
            "1. Ground every sentence strictly in the supplied structured evidence below. Do not invent unreferenced files, false dependencies, or speculative facts.\n"
            "2. Never call files, folders, or modules 'services'. Use precise architectural terms: 'Affected Files', 'Affected Modules', 'Affected Components', 'Affected Packages'. Only use 'Services' if a deployable runtime service manifest is explicitly present in deployment evidence.\n"
            "3. Do NOT infer deployment ordering solely from source code imports. Import dependencies indicate shared coupling, not deployment sequence.\n"
            "4. Do NOT recommend feature flags unless feature flag infrastructure is confirmed in the evidence.\n"
            "5. Do NOT invent human reviewers. Label file paths as 'Recommended review area'. Only cite usernames if Git ownership evidence is present.\n"
            "6. Failure scenarios MUST be labeled as 'Potential Scenario' using probabilistic language ('May introduce regression risk', 'Could affect'). Never claim a failure WILL occur.\n"
            "7. Clearly distinguish FACTS (directly measured), INFERENCES (deterministic conclusions), and RECOMMENDATIONS (suggested actions).\n"
            "8. Do not recalculate or override the deterministic risk score or completeness metric.\n\n"
            "STRUCTURED EVIDENCE PAYLOAD:\n"
            "- Risk Summary & Metrics:\n{{ risk_json }}\n\n"
            "- Observed Facts:\n{{ facts_json }}\n\n"
            "- Deterministic Inferences:\n{{ inferences_json }}\n\n"
            "- Classified Recommendations:\n{{ recommendations_json }}\n\n"
            "- Review Areas & Ownership Evidence:\n{{ review_areas_json }}\n\n"
            "- Deployment Topology Evidence:\n{{ deployment_evidence_json }}\n\n"
            "- Graph Topology Summary:\n{{ graph_summary }}\n\n"
            "Generate the report using EXACTLY these 9 markdown sections:\n"
            "# Change Risk Assessment\n\n"
            "## Risk Summary\n"
            "(State Risk Score, Risk Level, Evidence Completeness, and Calibration Status. Include: 'Deterministic change-risk index based on repository evidence. This score is not a statistical probability of production failure.')\n\n"
            "## Facts\n"
            "(List only directly observed facts citing [FACT-xxx] IDs.)\n\n"
            "## Impact Analysis\n"
            "(List deterministic inferences derived from graph/diff evidence citing [INF-xxx] IDs.)\n\n"
            "## Risk Factors\n"
            "(Table or breakdown of triggered rules with points, category, and evidence.)\n\n"
            "## Failure Scenarios\n"
            "(List potential scenarios labeled 'Potential Scenario: ...' citing specific affected files/dependencies.)\n\n"
            "## Recommended Actions\n"
            "(Group recommendations by Evidence-backed, Policy-based, and Generic best practice, citing [REC-xxx] IDs.)\n\n"
            "## Reviewer / Ownership Analysis\n"
            "(List recommended review areas with ownership details if available, or 'Reviewer ownership could not be determined from available repository evidence.')\n\n"
            "## Deployment Considerations\n"
            "(Deployment advice if topology exists, otherwise state 'These components share dependency relationships and should be tested together. Deployment topology evidence was not detected.')\n"
        ),
    ),
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
    ),
]
