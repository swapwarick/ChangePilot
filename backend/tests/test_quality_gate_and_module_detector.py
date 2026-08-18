"""Regression test suite for AnalysisQualityGate and ModuleDetector.

Validates fail-closed semantics, evidence completeness formula,
and genuine architectural module extraction.
"""

from app.analysis.module_detector import ModuleDetector
from app.analysis.quality_gate import AnalysisQualityGate


def test_module_detector_excludes_ide_and_gradle():
    changed_files = [
        ".idea/workspace.xml",
        ".idea/modules.xml",
        ".idea/runConfigurations.xml",
        "gradle/wrapper/gradle-wrapper.jar",
        "gradle/wrapper/gradle-wrapper.properties",
        ".vscode/settings.json",
        "app/src/main/java/com/swapwarick/loginlogout/LoginActivity.kt",
        "app/src/main/res/drawable/logo.webp",
        "app/build.gradle.kts",
    ]
    modules = ModuleDetector.extract_impacted_modules(changed_files)
    assert ".idea" not in modules
    assert "gradle" not in modules
    assert ".vscode" not in modules
    assert "app" in modules


def test_module_detector_gradle_settings_modules():
    settings_content = """
    rootProject.name = "ChangePilot"
    include(":app")
    include(":core:network")
    include(":feature:login")
    """
    declared = ModuleDetector.detect_gradle_modules(settings_content)
    assert "app" in declared
    assert "core/network" in declared
    assert "feature/login" in declared

    changed = [
        "feature/login/src/main/java/LoginScreen.kt",
        ".idea/misc.xml",
        "app/src/main/AndroidManifest.xml",
    ]
    impacted = ModuleDetector.extract_impacted_modules(changed, declared_modules=declared)
    assert ":feature:login" in impacted
    assert ":app" in impacted
    assert ".idea" not in impacted


def test_quality_gate_full_success():
    gate = AnalysisQualityGate.evaluate(
        files_discovered=72,
        supported_source_files=25,
        files_parsed=25,
        files_failed=0,
        ast_nodes=35,
        dependency_edges=18,
        has_git_diff=True,
        has_test_analysis=True,
    )
    assert gate.analysis_quality == "FULL"
    assert gate.graph_status == "VALID"
    assert gate.health_status == "AVAILABLE"
    assert gate.parser_health == "PASS"
    assert gate.evidence_completeness >= 0.90


def test_quality_gate_fail_closed_on_parser_failure():
    # If 25 Kotlin files exist but parser extracts 0 AST nodes
    gate = AnalysisQualityGate.evaluate(
        files_discovered=72,
        supported_source_files=25,
        files_parsed=0,
        files_failed=25,
        ast_nodes=1,
        dependency_edges=0,
        has_git_diff=True,
        has_test_analysis=True,
    )
    assert gate.analysis_quality in ("DEGRADED", "FAILED")
    assert gate.graph_status == "FAILED"
    assert gate.health_status == "UNAVAILABLE"
    assert gate.parser_health == "FAIL"
    # Evidence completeness must NOT be 95%!
    assert gate.evidence_completeness < 0.60
    assert len(gate.warnings) > 0


def test_quality_gate_degraded_partial_parses():
    gate = AnalysisQualityGate.evaluate(
        files_discovered=50,
        supported_source_files=20,
        files_parsed=10,
        files_failed=10,
        ast_nodes=15,
        dependency_edges=5,
        has_git_diff=True,
        has_test_analysis=True,
    )
    assert gate.analysis_quality == "DEGRADED"
    assert gate.graph_status == "DEGRADED"
    assert gate.health_status == "DEGRADED"
    assert gate.parser_health == "PARTIAL"
    assert 0.40 <= gate.evidence_completeness < 0.90
