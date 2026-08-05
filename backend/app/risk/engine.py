from collections import defaultdict

from app.models.enums import RiskLevel
from app.models.risk import RiskEvidence, RiskInput, RiskResult
from app.risk.rules import RULES


class DeterministicRiskEngine:
    """Scores risk from reproducible evidence only."""

    def score(self, risk_input: RiskInput) -> RiskResult:
        evidence = self._collect_rule_evidence(risk_input.changed_files)

        if risk_input.dependency_count:
            dependency_score = min(risk_input.dependency_count / 25, 1)
            evidence.append(
                RiskEvidence(
                    signal="high_dependency_count",
                    description=f"{risk_input.dependency_count} downstream dependencies are impacted.",
                    weight=0.12,
                    score=dependency_score,
                )
            )

        if risk_input.missing_tests:
            evidence.append(
                RiskEvidence(
                    signal="missing_tests",
                    description="No related test changes were detected.",
                    weight=0.1,
                    score=1,
                )
            )

        if risk_input.large_refactor:
            evidence.append(
                RiskEvidence(
                    signal="large_refactor",
                    description="The change touches enough files to qualify as a large refactor.",
                    weight=0.12,
                    score=1,
                )
            )

        if risk_input.critical_modules:
            evidence.append(
                RiskEvidence(
                    signal="critical_module_change",
                    description="Critical modules are directly changed or impacted.",
                    weight=0.18,
                    score=min(len(risk_input.critical_modules) / 3, 1),
                    file_paths=risk_input.critical_modules,
                )
            )

        raw_score = sum(item.weight * item.score for item in evidence)
        score = round(min(raw_score, 1), 4)
        level = self._level(score)
        confidence = self._confidence(risk_input, evidence)
        reasons = [
            f"{item.signal}: {item.description}"
            for item in sorted(evidence, key=lambda item: item.weight * item.score, reverse=True)
        ]
        return RiskResult(
            score=score,
            level=level,
            confidence=confidence,
            evidence=evidence,
            reasons=reasons,
        )

    def _collect_rule_evidence(self, changed_files: list[str]) -> list[RiskEvidence]:
        matches: dict[str, list[str]] = defaultdict(list)
        rule_by_signal = {rule.signal: rule for rule in RULES}

        for file_path in changed_files:
            for rule in RULES:
                if rule.matches(file_path):
                    matches[rule.signal].append(file_path)

        evidence: list[RiskEvidence] = []
        for signal, paths in matches.items():
            rule = rule_by_signal[signal]
            evidence.append(
                RiskEvidence(
                    signal=rule.signal,
                    description=rule.description,
                    weight=rule.weight,
                    score=min(len(paths) / 3, 1),
                    file_paths=sorted(set(paths)),
                )
            )
        return evidence

    def _level(self, score: float) -> RiskLevel:
        if score >= 0.8:
            return RiskLevel.CRITICAL
        if score >= 0.6:
            return RiskLevel.HIGH
        if score >= 0.3:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _confidence(self, risk_input: RiskInput, evidence: list[RiskEvidence]) -> float:
        confidence = 0.55
        if risk_input.changed_files:
            confidence += 0.15
        if risk_input.impacted_modules:
            confidence += 0.15
        if evidence:
            confidence += 0.1
        if risk_input.dependency_count:
            confidence += 0.05
        return round(min(confidence, 0.95), 3)

