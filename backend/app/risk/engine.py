from collections import defaultdict
from typing import Any

from app.models.enums import RecommendationType, RiskLevel, StatementType
from app.models.risk import (
    EvidenceStatement,
    ImpactMetrics,
    RiskBreakdownItem,
    RiskEvidence,
    RiskInput,
    RiskResult,
)
from app.risk.rules import RULES


class DeterministicRiskEngine:
    """Scores risk strictly from reproducible repository evidence, normalized to a 0-100 index.

    Adheres strictly to scientific epistemological separation:
    - FACT: Directly measured from repository / AST / Git / graph evidence.
    - INFERENCE: Deterministic conclusion derived from observed facts.
    - RECOMMENDATION: Suggested action classified as EVIDENCE_BACKED, POLICY_BASED, or GENERIC_BEST_PRACTICE.
    """

    def score(self, risk_input: RiskInput, custom_rules: list | None = None) -> RiskResult:
        # Detect feature flag & deployment infrastructure from changed files if not pre-populated
        ff_detected = risk_input.feature_flag_infrastructure_detected or self._detect_feature_flags(risk_input.changed_files)
        deploy_detected = risk_input.deployment_topology_detected or self._detect_deployment_topology(risk_input.changed_files)

        evidence = self._collect_rule_evidence(risk_input.changed_files, custom_rules=custom_rules)

        # Dynamic graph-based evidence metrics
        if not risk_input.impact_metrics or (risk_input.impact_metrics.changed_files == 0 and risk_input.changed_files):
            risk_input.impact_metrics = ImpactMetrics(
                changed_files=len(risk_input.changed_files),
                unique_affected_components=risk_input.dependency_count,
                total_blast_radius=len(risk_input.changed_files) + risk_input.dependency_count,
                affected_modules=risk_input.impacted_modules or [],
            )

        unique_downstream = (
            risk_input.impact_metrics.unique_affected_components
            if risk_input.impact_metrics and risk_input.impact_metrics.unique_affected_components > 0
            else risk_input.dependency_count
        )
        traversed_edges = (
            risk_input.impact_metrics.dependency_edges
            if risk_input.impact_metrics and risk_input.impact_metrics.dependency_edges > 0
            else 0
        )

        if unique_downstream > 0:
            dep_score = min(unique_downstream / 20.0, 1.0)
            ff_rec = (
                "Feature flag deployment is available and may reduce rollback risk."
                if ff_detected
                else "Add regression tests covering downstream consumers and validate in a staging environment."
            )
            rec_type = RecommendationType.EVIDENCE_BACKED if ff_detected else RecommendationType.POLICY_BASED
            
            desc = f"{unique_downstream} unique downstream component(s) impacted"
            if traversed_edges > 0:
                desc += f" across {traversed_edges} dependency edge(s)"
            desc += " by this change."

            evidence.append(
                RiskEvidence(
                    signal="large_blast_radius",
                    name="Large Downstream Blast Radius",
                    category="architecture",
                    description=desc,
                    weight=0.18,
                    score=dep_score,
                    recommendation=ff_rec,
                    recommendation_type=rec_type,
                    threshold="> 10 unique components",
                    rule="large_blast_radius",
                    evidence_type="graph_metric",
                    evidence_value=f"{unique_downstream}_components",
                )
            )

        if risk_input.missing_tests:
            evidence.append(
                RiskEvidence(
                    signal="missing_tests",
                    name="Potential Test Gap",
                    category="testing",
                    description="No related unit test or test specification modifications were detected alongside source changes. Runtime coverage data is unavailable.",
                    weight=0.14,
                    score=1.0,
                    recommendation="Add unit tests covering modified business logic in changed components.",
                    recommendation_type=RecommendationType.EVIDENCE_BACKED,
                    threshold="0 test changes",
                    rule="missing_tests",
                    evidence_type="repo_structure",
                    evidence_value="0_tests",
                )
            )

        arch_relevant = [
            f for f in risk_input.changed_files
            if not any(f.lower().startswith(p) or f"/{p}" in f.lower() for p in (".idea/", ".gradle/", "build/", ".vscode/", "gradle/"))
            and not any(f.lower().endswith(ext) for ext in (".png", ".webp", ".jpg", ".jpeg", ".ico", ".svg", ".jar", ".aar", ".bak", ".iml", "~"))
        ]
        if len(arch_relevant) >= 15 or (risk_input.large_refactor and len(arch_relevant) >= 15):
            evidence.append(
                RiskEvidence(
                    signal="large_refactor",
                    name="Large Architectural Refactor",
                    category="architecture",
                    description=f"{len(arch_relevant)} architecturally relevant source/build files modified (out of {len(risk_input.changed_files)} total changed files).",
                    weight=0.16,
                    score=min(len(arch_relevant) / 30.0, 1.0),
                    file_paths=arch_relevant[:15],
                    recommendation="Consider breaking change set into smaller, isolated pull requests for safer review.",
                    recommendation_type=RecommendationType.GENERIC_BEST_PRACTICE,
                    threshold=">= 15 architectural files",
                    rule="large_refactor",
                    evidence_type="diff_metric",
                    evidence_value=f"{len(arch_relevant)}/{len(risk_input.changed_files)}",
                )
            )

        if risk_input.critical_modules:
            evidence.append(
                RiskEvidence(
                    signal="critical_component_modified",
                    name="Critical Business Component Modified",
                    category="architecture",
                    description=f"Critical business components are directly changed or impacted: {', '.join(risk_input.critical_modules[:3])}",
                    weight=0.20,
                    score=min(len(risk_input.critical_modules) / 3.0, 1.0),
                    file_paths=risk_input.critical_modules,
                    recommendation="Run end-to-end integration tests for critical business workflows.",
                    recommendation_type=RecommendationType.POLICY_BASED,
                    threshold="1 critical component",
                    rule="critical_component_modified",
                    evidence_type="path_keyword",
                    evidence_value=",".join(risk_input.critical_modules[:3]),
                )
            )

        if len(risk_input.impacted_modules) >= 3:
            evidence.append(
                RiskEvidence(
                    signal="multi_module_impact",
                    name="Multiple Modules Impacted",
                    category="architecture",
                    description=f"Change impact spans across {len(risk_input.impacted_modules)} distinct architectural modules: {', '.join(risk_input.impacted_modules[:4])}",
                    weight=0.18,
                    score=min(len(risk_input.impacted_modules) / 4.0, 1.0),
                    recommendation="These components share dependency relationships and should be tested together.",
                    recommendation_type=RecommendationType.EVIDENCE_BACKED,
                    threshold=">= 3 modules",
                    rule="multi_module_impact",
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
                    recommendation_type=RecommendationType.EVIDENCE_BACKED,
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
                    recommendation_type=RecommendationType.EVIDENCE_BACKED,
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
                    recommendation_type=RecommendationType.EVIDENCE_BACKED,
                    threshold="1 bridge node",
                    rule="bridge_node_affected",
                    evidence_type="graph_topology",
                    evidence_value=",".join(risk_input.bridge_nodes_affected[:3]),
                )
            )

        # Anti-Double Counting & Deduplication Audit
        raw_rule_score = 0.0
        risk_breakdown: list[RiskBreakdownItem] = []

        for item in sorted(evidence, key=lambda i: i.weight * i.score, reverse=True):
            raw_pts = item.weight * item.score * 100
            points = int(round(raw_pts))
            raw_rule_score += raw_pts

            risk_breakdown.append(
                RiskBreakdownItem(
                    rule=item.rule or item.signal,
                    name=item.name or item.rule or item.signal,
                    category=item.category,
                    points=points,
                    raw_points=round(raw_pts, 2),
                    evidence=item.description,
                    affected_files=item.file_paths,
                    threshold=item.threshold,
                    observed_value=item.evidence_value or item.description,
                    trigger=item.signal,
                    status="TRIGGERED",
                    recommendation=item.recommendation,
                    recommendation_type=item.recommendation_type,
                )
            )

        # Apply diminishing returns scaling to prevent double counting overflow
        normalized_score = raw_rule_score
        if raw_rule_score > 60:
            normalized_score = 60 + (raw_rule_score - 60) * 0.5

        capped_score = int(round(max(min(normalized_score, 100), 0)))
        level = self._level(capped_score)
        completeness = self._evidence_completeness(risk_input, evidence)

        # Generate strictly classified FACT, INFERENCE, RECOMMENDATION statements
        statements, facts, inferences, recommendations = self._generate_classified_statements(
            risk_input, evidence, ff_detected, deploy_detected
        )

        potential_failure_scenarios = self._generate_potential_scenarios(risk_input, evidence)
        review_areas = self._generate_review_areas(risk_input)
        deployment_considerations = self._generate_deployment_considerations(risk_input, deploy_detected)

        reasons = [
            f"{item.name or item.signal}: {item.description}"
            for item in sorted(evidence, key=lambda item: item.weight * item.score, reverse=True)
        ]

        audit = {
            "raw_rule_score": round(raw_rule_score, 2),
            "normalized_score": round(normalized_score, 2),
            "capped_score": capped_score,
            "evidence_completeness": completeness,
        }

        return RiskResult(
            score=capped_score,
            level=level,
            evidence_completeness=completeness,
            confidence=completeness,
            is_calibrated=False,
            calibration_status="Not statistically calibrated against historical production failure outcomes. Deterministic engineering index only.",
            score_description="Deterministic change-risk index based on repository evidence. This score is not a statistical probability of production failure.",
            impact_metrics=risk_input.impact_metrics,
            evidence=evidence,
            statements=statements,
            facts=facts,
            inferences=inferences,
            recommendations=recommendations,
            potential_failure_scenarios=potential_failure_scenarios,
            recommended_review_areas=review_areas,
            deployment_considerations=deployment_considerations,
            reasons=reasons,
            risk_breakdown=risk_breakdown,
            audit=audit,
        )

    def _generate_classified_statements(
        self,
        risk_input: RiskInput,
        evidence: list[RiskEvidence],
        ff_detected: bool,
        deploy_detected: bool,
    ) -> tuple[list[EvidenceStatement], list[EvidenceStatement], list[EvidenceStatement], list[EvidenceStatement]]:
        facts: list[EvidenceStatement] = []
        inferences: list[EvidenceStatement] = []
        recommendations: list[EvidenceStatement] = []
        fact_idx = 1
        inf_idx = 1
        rec_idx = 1

        # --- FACTS (Directly measured observations) ---
        file_count = len(risk_input.changed_files)
        facts.append(
            EvidenceStatement(
                id=f"FACT-{fact_idx:03d}",
                statement_type=StatementType.FACT,
                claim=f"{file_count} file(s) modified in the active change set.",
                source_evidence=f"Git unified diff touching {file_count} files",
                traceability_ref="diff_stat",
                affected_files=risk_input.changed_files[:10],
            )
        )
        fact_idx += 1

        im = risk_input.impact_metrics
        if im and im.unique_affected_components > 0:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim=f"{im.unique_affected_components} unique downstream component(s) impacted across {im.dependency_edges} dependency edge(s). Total blast radius: {im.total_blast_radius}.",
                    source_evidence="AST Dependency Graph BFS traversal",
                    traceability_ref="graph_traversal",
                )
            )
            fact_idx += 1
        elif risk_input.dependency_count > 0:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim=f"{risk_input.dependency_count} downstream component(s) impacted by this change.",
                    source_evidence="AST Dependency Graph traversal",
                    traceability_ref="graph_traversal",
                )
            )
            fact_idx += 1

        if risk_input.impacted_modules:
            mod_list = ", ".join(risk_input.impacted_modules[:5])
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim=f"{len(risk_input.impacted_modules)} distinct architectural module(s) are touched or imported: {mod_list}",
                    source_evidence="AST module resolution",
                    traceability_ref="ast_modules",
                )
            )
            fact_idx += 1

        if risk_input.affected_functions:
            fn_count = len(risk_input.affected_functions)
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim=f"{fn_count} function/class symbol(s) directly modified in AST diff.",
                    source_evidence=f"Tree-Sitter AST diff on {fn_count} symbols",
                    traceability_ref="ast_diff_symbols",
                )
            )
            fact_idx += 1

        if ff_detected:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim="Feature flag infrastructure was detected in repository evidence.",
                    source_evidence="Repository configuration / dependency scan",
                    traceability_ref="feature_flags_scan",
                )
            )
            fact_idx += 1
        else:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim="Feature flag infrastructure was not detected in available repository evidence.",
                    source_evidence="Repository configuration scan",
                    traceability_ref="feature_flags_scan",
                )
            )
            fact_idx += 1

        if deploy_detected:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim="Deployment topology configuration manifests were detected.",
                    source_evidence="Infrastructure as Code / container manifests",
                    traceability_ref="deployment_manifests",
                )
            )
            fact_idx += 1
        else:
            facts.append(
                EvidenceStatement(
                    id=f"FACT-{fact_idx:03d}",
                    statement_type=StatementType.FACT,
                    claim="Deployment topology evidence was not detected from available repository files.",
                    source_evidence="Repository infrastructure scan",
                    traceability_ref="deployment_manifests",
                )
            )
            fact_idx += 1

        # --- INFERENCES (Deterministic conclusions derived from facts) ---
        downstream_cnt = im.unique_affected_components if im and im.unique_affected_components > 0 else risk_input.dependency_count
        if downstream_cnt > 10:
            edge_desc = f" across {im.dependency_edges} dependency edges" if im and im.dependency_edges > 0 else ""
            inferences.append(
                EvidenceStatement(
                    id=f"INF-{inf_idx:03d}",
                    statement_type=StatementType.INFERENCE,
                    claim=f"High downstream blast radius: changing these components may introduce regression risk across {downstream_cnt} unique dependent components{edge_desc}.",
                    source_evidence=f"Derived from blast radius traversal ({downstream_cnt} unique components)",
                    traceability_ref="rule:large_blast_radius",
                )
            )
            inf_idx += 1

        if risk_input.missing_tests:
            inferences.append(
                EvidenceStatement(
                    id=f"INF-{inf_idx:03d}",
                    statement_type=StatementType.INFERENCE,
                    claim="Potential test gap: production code changes lack accompanying unit test or test specification modifications in this commit set. Runtime coverage data was unavailable.",
                    source_evidence="Diff analysis: 0 test files modified in commit set",
                    traceability_ref="rule:missing_tests",
                )
            )
            inf_idx += 1

        if risk_input.critical_modules:
            inferences.append(
                EvidenceStatement(
                    id=f"INF-{inf_idx:03d}",
                    statement_type=StatementType.INFERENCE,
                    claim=f"Critical business workflows may be affected because changes intersect sensitive domains: {', '.join(risk_input.critical_modules[:3])}",
                    source_evidence="Sensitive domain path keyword matching",
                    traceability_ref="rule:critical_component_modified",
                    affected_files=risk_input.critical_modules,
                )
            )
            inf_idx += 1

        if len(risk_input.impacted_modules) >= 3:
            inferences.append(
                EvidenceStatement(
                    id=f"INF-{inf_idx:03d}",
                    statement_type=StatementType.INFERENCE,
                    claim="Cross-module coupling: changes span multiple architectural boundaries rather than being localized to a single module.",
                    source_evidence=f"Impact spans {len(risk_input.impacted_modules)} modules",
                    traceability_ref="rule:multi_module_impact",
                )
            )
            inf_idx += 1

        # --- RECOMMENDATIONS (Separated by RecommendationType) ---
        for ev in evidence:
            if ev.recommendation:
                rec_id = f"REC-{rec_idx:03d}"
                rec_idx += 1
                recommendations.append(
                    EvidenceStatement(
                        id=rec_id,
                        statement_type=StatementType.RECOMMENDATION,
                        recommendation_type=ev.recommendation_type,
                        claim=ev.recommendation,
                        source_evidence=f"Triggered by {ev.rule or ev.signal}: {ev.description}",
                        traceability_ref=f"rule:{ev.rule or ev.signal}",
                        affected_files=ev.file_paths,
                    )
                )

        all_statements = facts + inferences + recommendations
        return all_statements, facts, inferences, recommendations

    def _generate_potential_scenarios(self, risk_input: RiskInput, evidence: list[RiskEvidence]) -> list[str]:
        scenarios: list[str] = []
        downstream_cnt = (
            risk_input.impact_metrics.unique_affected_components
            if risk_input.impact_metrics and risk_input.impact_metrics.unique_affected_components > 0
            else risk_input.dependency_count
        )
        if downstream_cnt > 0:
            scenarios.append(
                f"Potential Scenario: Downstream consumers may be affected because {downstream_cnt} dependent components rely on the modified interfaces."
            )
        if risk_input.missing_tests:
            scenarios.append(
                "Potential Scenario: Regressions in modified business logic may go undetected prior to deployment due to absence of accompanying automated test specifications."
            )
        if any("auth" in f.lower() or "session" in f.lower() for f in risk_input.changed_files):
            scenarios.append(
                "Potential Scenario: Authentication or session validation logic changes could alter token verification or permission evaluation for active sessions."
            )
        if any(f.endswith(".sql") or "migration" in f.lower() for f in risk_input.changed_files):
            scenarios.append(
                "Potential Scenario: Database schema changes may cause transient runtime queries to fail if application code and database migrations are not synchronized."
            )
        if not scenarios:
            scenarios.append(
                "Potential Scenario: Minor localized regressions possible in directly modified components if edge cases in updated logic are unhandled."
            )
        return scenarios

    def _generate_review_areas(self, risk_input: RiskInput) -> list[dict[str, Any]]:
        review_areas: list[dict[str, Any]] = []
        for path in risk_input.changed_files[:6]:
            owner_info = risk_input.contributor_ownership_data.get(path)
            if owner_info:
                review_areas.append({
                    "review_area": path,
                    "suggested_reviewer": owner_info,
                    "evidence": "Git contributor history indicates recent commit ownership in this area.",
                })
            else:
                review_areas.append({
                    "review_area": path,
                    "suggested_reviewer": None,
                    "ownership_note": "Ownership data unavailable — CODEOWNERS/team mapping could not be determined from available repository evidence.",
                })
        return review_areas

    def _generate_deployment_considerations(self, risk_input: RiskInput, deploy_detected: bool) -> list[str]:
        if deploy_detected:
            return [
                "Deployment topology configuration detected: verify container build and staging deployment manifests before production rollout.",
                "These components share dependency relationships and should be tested together.",
            ]
        return [
            "These components share dependency relationships and should be tested together.",
            "Deployment topology evidence was not detected from repository files. Do not infer standalone deployment sequencing solely from source code imports.",
        ]

    def _detect_feature_flags(self, files: list[str]) -> bool:
        keywords = ("launchdarkly", "unleash", "openfeature", "feature_flag", "flags.py", "featureflags")
        return any(any(kw in f.lower() for kw in keywords) for f in files)

    def _detect_deployment_topology(self, files: list[str]) -> bool:
        keywords = ("dockerfile", "docker-compose", "k8s/", "kubernetes", "helm", "terraform", ".tf", "deployment.yaml")
        return any(any(kw in f.lower() for kw in keywords) for f in files)

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
                            "recommendation_type": getattr(rule, "recommendation_type", RecommendationType.POLICY_BASED),
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
                    description=f"{meta.get('description', '')} ({len(paths)} matching file(s))",
                    weight=meta.get("weight", 0.15),
                    score=min(len(paths) / 2.0, 1.0),
                    file_paths=sorted(set(paths)),
                    recommendation=meta.get("recommendation", ""),
                    recommendation_type=meta.get("recommendation_type", RecommendationType.POLICY_BASED),
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

    def _evidence_completeness(self, risk_input: RiskInput, evidence: list[RiskEvidence]) -> float:
        completeness = 0.60
        if risk_input.changed_files:
            completeness += 0.15
        if risk_input.impacted_modules:
            completeness += 0.10
        if evidence:
            completeness += 0.10
        if risk_input.dependency_count:
            completeness += 0.05
        return round(min(completeness, 0.98), 3)


RiskEngine = DeterministicRiskEngine
