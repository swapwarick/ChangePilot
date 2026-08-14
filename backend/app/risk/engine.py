from collections import defaultdict

from app.models.enums import RiskLevel
from app.models.risk import RiskBreakdownItem, RiskEvidence, RiskInput, RiskResult
from app.risk.rules import RULES, RiskRule


class DeterministicRiskEngine:
    """Scores risk from reproducible evidence only, normalized to a 0-100 scale."""

    def score(self, risk_input: RiskInput, custom_rules: list | None = None) -> RiskResult:
        evidence = self._collect_rule_evidence(risk_input.changed_files, custom_rules=custom_rules)

        # Dynamic graph-based evidence metrics
        if risk_input.dependency_count > 0:
            dep_score = min(risk_input.dependency_count / 20.0, 1.0)
            evidence.append(
                RiskEvidence(
                    signal="large_blast_radius",
                    name="Large Downstream Blast Radius",
                    category="architecture",
                    description=f"{risk_input.dependency_count} downstream dependencies are impacted by this change.",
                    weight=0.18,
                    score=dep_score,
                    recommendation="Deploy change behind a feature flag and monitor staging logs.",
                    threshold="> 10 dependencies",
                    rule="large_blast_radius",
                    evidence_type="graph_metric",
                    evidence_value=str(risk_input.dependency_count),
                )
            )

        if risk_input.missing_tests:
            evidence.append(
                RiskEvidence(
                    signal="missing_tests",
                    name="Missing Related Test Changes",
                    category="testing",
                    description="No related unit test or test spec changes were detected alongside source modifications.",
                    weight=0.14,
                    score=1.0,
                    recommendation="Add unit tests covering modified business logic.",
                    threshold="0 test changes",
                    rule="missing_tests",
                    evidence_type="repo_structure",
                    evidence_value="0_tests",
                )
            )

        if risk_input.large_refactor:
            evidence.append(
                RiskEvidence(
                    signal="large_refactor",
                    name="Large Refactor Change",
                    category="architecture",
                    description=f"The change set touches {len(risk_input.changed_files)} files, qualifying as a large refactor.",
                    weight=0.16,
                    score=1.0,
                    file_paths=risk_input.changed_files[:15],
                    recommendation="Break pull request into smaller, isolated sub-PRs for safer code review.",
                    threshold=">= 15 files",
                    rule="large_refactor",
                    evidence_type="diff_metric",
                    evidence_value=str(len(risk_input.changed_files)),
                )
            )

        if risk_input.critical_modules:
            evidence.append(
                RiskEvidence(
                    signal="critical_service_modified",
                    name="Critical Business Service Modified",
                    category="architecture",
                    description=f"Critical modules are directly changed or impacted: {', '.join(risk_input.critical_modules[:3])}",
                    weight=0.20,
                    score=min(len(risk_input.critical_modules) / 3.0, 1.0),
                    file_paths=risk_input.critical_modules,
                    recommendation="Run end-to-end integration tests for critical business workflows.",
                    threshold="1 critical module",
                    rule="critical_service_modified",
                    evidence_type="path_keyword",
                    evidence_value=",".join(risk_input.critical_modules[:3]),
                )
            )

        if len(risk_input.impacted_modules) >= 3:
            evidence.append(
                RiskEvidence(
                    signal="multi_service_affected",
                    name="Multiple Services Impacted",
                    category="architecture",
                    description=f"Change impact spans across {len(risk_input.impacted_modules)} distinct modules: {', '.join(risk_input.impacted_modules[:4])}",
                    weight=0.18,
                    score=min(len(risk_input.impacted_modules) / 4.0, 1.0),
                    recommendation="Coordinate deployment order across affected microservices.",
                    threshold=">= 3 modules",
                    rule="multi_service_affected",
                    evidence_type="graph_metric",
                    evidence_value=str(len(risk_input.impacted_modules)),
                )
            )

        if risk_input.affected_functions:
            fn_count = len(risk_input.affected_functions)
            evidence.append(
                RiskEvidence(
                    signal="function_level_impact",
                    name="Specific Functions Modified",
                    category="architecture",
                    description=(
                        f"{fn_count} function(s) directly modified: "
                        f"{', '.join(risk_input.affected_functions[:5])}"
                        + (f" and {fn_count - 5} more" if fn_count > 5 else "")
                    ),
                    weight=0.10,
                    score=min(fn_count / 10.0, 1.0),
                    recommendation="Review all call sites of the modified functions for argument and return-type compatibility.",
                    threshold="1 function",
                    rule="function_level_impact",
                    evidence_type="diff_ast",
                    evidence_value=",".join(risk_input.affected_functions[:5]),
                )
            )

        if risk_input.hub_nodes_affected:
            hub_count = len(risk_input.hub_nodes_affected)
            evidence.append(
                RiskEvidence(
                    signal="hub_node_affected",
                    name="High-Degree Hub Node in Impact Set",
                    category="architecture",
                    description=(
                        f"{hub_count} heavily-connected hub node(s) are directly changed or transitively impacted: "
                        f"{', '.join(risk_input.hub_nodes_affected[:3])}"
                    ),
                    weight=0.16,
                    score=min(hub_count / 3.0, 1.0),
                    recommendation="Run the full test suite — hub nodes have many consumers and failures propagate widely.",
                    threshold="1 hub node",
                    rule="hub_node_affected",
                    evidence_type="graph_topology",
                    evidence_value=",".join(risk_input.hub_nodes_affected[:3]),
                )
            )

        if risk_input.bridge_nodes_affected:
            bridge_count = len(risk_input.bridge_nodes_affected)
            evidence.append(
                RiskEvidence(
                    signal="bridge_node_affected",
                    name="Architectural Bridge Node Modified",
                    category="architecture",
                    description=(
                        f"{bridge_count} architectural bridge/chokepoint node(s) are in the impact set: "
                        f"{', '.join(risk_input.bridge_nodes_affected[:3])}. "
                        "These nodes connect otherwise separate subsystems."
                    ),
                    weight=0.18,
                    score=min(bridge_count / 2.0, 1.0),
                    recommendation="Validate integration points between all subsystems connected through these nodes.",
                    threshold="1 bridge node",
                    rule="bridge_node_affected",
                    evidence_type="graph_topology",
                    evidence_value=",".join(risk_input.bridge_nodes_affected[:3]),
                )
            )

        # Anti-Double Counting & Deduplication Audit
        seen_categories: set[str] = set()
        raw_rule_score = 0.0
        risk_breakdown: list[RiskBreakdownItem] = []

        for item in sorted(evidence, key=lambda i: i.weight * i.score, reverse=True):
            points = int(round(item.weight * item.score * 100))
            raw_rule_score += points

            risk_breakdown.append(
                RiskBreakdownItem(
                    rule=item.rule or item.signal,
                    category=item.category,
                    points=points,
                    evidence=item.description,
                    affected_files=item.file_paths,
                    recommendation=item.recommendation,
                )
            )

        # Apply diminishing returns scaling to prevent double counting overflow
        normalized_score = raw_rule_score
        if raw_rule_score > 60:
            normalized_score = 60 + (raw_rule_score - 60) * 0.5

        capped_score = int(round(max(min(normalized_score, 100), 0)))
        level = self._level(capped_score)
        confidence = self._confidence(risk_input, evidence)

        reasons = [
            f"{item.name or item.signal}: {item.description}"
            for item in sorted(evidence, key=lambda item: item.weight * item.score, reverse=True)
        ]

        audit = {
            "raw_rule_score": round(raw_rule_score, 2),
            "normalized_score": round(normalized_score, 2),
            "capped_score": capped_score,
        }

        return RiskResult(
            score=capped_score,
            level=level,
            confidence=confidence,
            evidence=evidence,
            reasons=reasons,
            risk_breakdown=risk_breakdown,
            audit=audit,
        )

    def _collect_rule_evidence(self, changed_files: list[str], custom_rules: list | None = None) -> list[RiskEvidence]:
        matches: dict[str, list[str]] = defaultdict(list)
        rule_meta: dict[str, dict] = {}

        if custom_rules:
            for c_rule in custom_rules:
                rule_dict = c_rule.model_dump() if hasattr(c_rule, "model_dump") else c_rule
                if not rule_dict.get("enabled", True):
                    continue

                sig = rule_dict["signal"]
                rule_meta[sig] = rule_dict
                p_markers = tuple(rule_dict.get("path_markers") or [])
                exts = tuple(rule_dict.get("extensions") or [])

                for file_path in changed_files:
                    path_lower = file_path.lower()
                    m_path = any(m.lower() in path_lower for m in p_markers) if p_markers else False
                    m_ext = any(path_lower.endswith(e.lower()) for e in exts) if exts else False
                    if m_path or m_ext:
                        matches[sig].append(file_path)
        else:
            rule_by_signal = {rule.signal: rule for rule in RULES}
            for file_path in changed_files:
                for rule in RULES:
                    if rule.matches(file_path):
                        matches[rule.signal].append(file_path)
                        rule_meta[rule.signal] = {
                            "signal": rule.signal,
                            "name": rule.name,
                            "category": rule.category,
                            "description": rule.description,
                            "weight": rule.weight,
                            "recommendation": rule.recommendation,
                            "threshold": rule.threshold,
                        }

        evidence: list[RiskEvidence] = []
        for signal, paths in matches.items():
            meta = rule_meta[signal]
            evidence.append(
                RiskEvidence(
                    signal=signal,
                    name=meta.get("name", signal),
                    category=meta.get("category", "general"),
                    description=f"{meta.get('description', '')} ({len(paths)} matching files)",
                    weight=meta.get("weight", 0.15),
                    score=min(len(paths) / 2.0, 1.0),
                    file_paths=sorted(set(paths)),
                    recommendation=meta.get("recommendation", ""),
                    enabled=True,
                    threshold=meta.get("threshold", "1 file"),
                    rule=signal,
                    evidence_type="path_match",
                    evidence_value=",".join(sorted(set(paths))[:5]),
                )
            )
        return evidence

    def _level(self, score: int) -> RiskLevel:
        if score >= 75:
            return RiskLevel.CRITICAL
        if score >= 55:
            return RiskLevel.HIGH
        if score >= 25:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _confidence(self, risk_input: RiskInput, evidence: list[RiskEvidence]) -> float:
        confidence = 0.60
        if risk_input.changed_files:
            confidence += 0.15
        if risk_input.impacted_modules:
            confidence += 0.10
        if evidence:
            confidence += 0.10
        if risk_input.dependency_count:
            confidence += 0.05
        return round(min(confidence, 0.98), 3)
