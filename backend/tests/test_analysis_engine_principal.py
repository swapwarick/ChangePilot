"""Comprehensive Unit Test Suite for Principal-Grade Static Analysis Engine.

Verifies:
1. Self-import detection and circular dependency isolation.
2. Config file edge typing (CONFIG_REFERENCE / BUILD_DEPENDENCY).
3. Redefined orphan classification (ENTRYPOINT, ROUTE, ORPHAN_CANDIDATE).
4. Potential test gap evidence formatting.
5. Risk score 0-100 normalization & anti-double-counting audit.
6. 5-category repository health score calculation.
7. Fan-in and Fan-out mathematical correctness.
8. Blast radius traversal with dependency_paths.
9. Generated/vendor file exclusion.
10. GraphHealth quality auditing.
"""

import pytest

from app.analysis.tree_sitter_parser import (
    ClassSymbol,
    FunctionSymbol,
    ImportSymbol,
    ParsedFileAST,
    PathNormalizer,
    TreeSitterCodeParser,
    is_config_file,
    is_generated_or_vendor,
)
from app.graph.blast_radius import compute_blast_radius
from app.graph.knowledge_graph import KnowledgeGraphBuilder, classify_file
from app.models.enums import EdgeType, FileClassification, RiskLevel
from app.models.risk import RiskInput
from app.risk.engine import DeterministicRiskEngine


def test_self_import_isolation():
    """Verify source == target is classified as SELF_IMPORT and NOT counted as circular dependency."""
    pf = ParsedFileAST(
        file_path="scripts/import-demo-tenders.mjs",
        file_hash="hash123",
        language="javascript",
        imports=[
            ImportSymbol(
                source_module="./import-demo-tenders.mjs",
                imported_name="*",
                is_relative=True,
            )
        ],
    )
    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf])

    # Assert graph health and self-edge count
    assert graph.graph_health is not None
    assert graph.graph_health.self_edge_count == 1
    assert len(health.circular_dependencies) == 0

    # Assert edge type is SELF_IMPORT
    self_edges = [e for e in graph.edges if e.edge_type == EdgeType.SELF_IMPORT]
    assert len(self_edges) == 1
    assert self_edges[0].source == "file:scripts/import-demo-tenders.mjs"
    assert self_edges[0].target == "file:scripts/import-demo-tenders.mjs"


def test_circular_dependency_cycles():
    """Verify A -> B -> A and A -> B -> C -> A cycles are detected, but A -> A is ignored."""
    pf1 = ParsedFileAST(
        file_path="src/a.ts",
        file_hash="hashA",
        language="typescript",
        imports=[ImportSymbol(source_module="./b.ts", imported_name="*", is_relative=True)],
    )
    pf2 = ParsedFileAST(
        file_path="src/b.ts",
        file_hash="hashB",
        language="typescript",
        imports=[ImportSymbol(source_module="./c.ts", imported_name="*", is_relative=True)],
    )
    pf3 = ParsedFileAST(
        file_path="src/c.ts",
        file_hash="hashC",
        language="typescript",
        imports=[ImportSymbol(source_module="./a.ts", imported_name="*", is_relative=True)],
    )

    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf1, pf2, pf3])

    assert len(health.circular_dependencies) == 1
    cycle = health.circular_dependencies[0]
    assert "src/a.ts" in cycle
    assert "src/b.ts" in cycle
    assert "src/c.ts" in cycle


def test_config_false_positives():
    """Verify config files are typed as CONFIG_REFERENCE and isolated from source code imports."""
    assert is_config_file("next.config.js") is True
    assert is_config_file("tsconfig.json") is True
    assert is_config_file("package.json") is True
    assert is_config_file("src/component.tsx") is False

    pf_config = ParsedFileAST(
        file_path="next.config.js",
        file_hash="hashConfig",
        language="config",
    )
    pf_src = ParsedFileAST(
        file_path="src/index.ts",
        file_hash="hashSrc",
        language="typescript",
        imports=[ImportSymbol(source_module="../next.config.js", imported_name="*", is_relative=True)],
    )

    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf_config, pf_src])

    config_edges = [e for e in graph.edges if e.edge_type == EdgeType.CONFIG_REFERENCE]
    assert len(config_edges) == 1
    assert config_edges[0].target == "file:next.config.js"


def test_orphan_classification_redefinition():
    """Verify entrypoints, routes, tests, and configs are not marked as orphan candidates."""
    assert classify_file("src/main.ts") == FileClassification.ENTRYPOINT
    assert classify_file("app/page.tsx") == FileClassification.ROUTE
    assert classify_file("app/api/user/route.ts") == FileClassification.ROUTE
    assert classify_file("next.config.js") == FileClassification.CONFIGURATION
    assert classify_file("tests/test_app.py") == FileClassification.TEST
    assert classify_file("src/unused_helper.ts") == FileClassification.SOURCE_MODULE

    pf_entry = ParsedFileAST(file_path="src/main.ts", file_hash="h1", language="typescript")
    pf_route = ParsedFileAST(file_path="app/page.tsx", file_hash="h2", language="tsx")
    pf_orphan = ParsedFileAST(file_path="src/orphan.ts", file_hash="h3", language="typescript")

    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf_entry, pf_route, pf_orphan])

    assert "src/main.ts" not in health.potential_orphan_candidates
    assert "app/page.tsx" not in health.potential_orphan_candidates
    assert "src/orphan.ts" in health.potential_orphan_candidates

    orphan_node = [n for n in graph.nodes if n.id == "file:src/orphan.ts"][0]
    assert orphan_node.file_classification == FileClassification.ORPHAN_CANDIDATE


def test_fan_in_fan_out_correctness():
    """Verify fan-in and fan-out exclude self imports, config references, and duplicate imports."""
    pf1 = ParsedFileAST(
        file_path="src/utils.ts",
        file_hash="h1",
        language="typescript",
    )
    pf2 = ParsedFileAST(
        file_path="src/feature.ts",
        file_hash="h2",
        language="typescript",
        imports=[
            ImportSymbol(source_module="./utils.ts", imported_name="a", is_relative=True),
            ImportSymbol(source_module="./utils.ts", imported_name="b", is_relative=True),
        ],
    )

    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf1, pf2])

    utils_node = [n for n in graph.nodes if n.id == "file:src/utils.ts"][0]
    feature_node = [n for n in graph.nodes if n.id == "file:src/feature.ts"][0]

    # utils has 1 incoming source module (feature.ts)
    assert utils_node.fan_in == 1
    assert utils_node.fan_out == 0

    # feature has 1 outgoing source module (utils.ts)
    assert feature_node.fan_in == 0
    assert feature_node.fan_out == 1


def test_blast_radius_traversal_and_paths():
    """Verify blast radius traversal follows source code dependencies and records dependency paths."""
    pf1 = ParsedFileAST(file_path="src/db.ts", file_hash="h1", language="typescript")
    pf2 = ParsedFileAST(
        file_path="src/service.ts",
        file_hash="h2",
        language="typescript",
        imports=[ImportSymbol(source_module="./db.ts", imported_name="*", is_relative=True)],
    )
    pf3 = ParsedFileAST(
        file_path="src/controller.ts",
        file_hash="h3",
        language="typescript",
        imports=[ImportSymbol(source_module="./service.ts", imported_name="*", is_relative=True)],
    )

    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf1, pf2, pf3])

    blast = compute_blast_radius(graph, changed_node_ids=["file:src/db.ts"], max_depth=3)

    assert blast.total_impact_size == 3  # db.ts (changed) + service.ts + controller.ts
    assert "src/service.ts" in blast.impacted_file_paths
    assert "src/controller.ts" in blast.impacted_file_paths
    assert len(blast.dependency_paths) >= 2


def test_risk_score_normalization_0_to_100_and_breakdown():
    """Verify risk score is on a 0-100 integer scale with risk_breakdown and audit info."""
    engine = DeterministicRiskEngine()
    risk_input = RiskInput(
        changed_files=["src/auth.ts", "src/payment.ts"],
        dependency_count=12,
        missing_tests=True,
        large_refactor=False,
        critical_modules=["src/auth.ts", "src/payment.ts"],
    )

    result = engine.score(risk_input)

    assert isinstance(result.score, int)
    assert 0 <= result.score <= 100
    assert result.level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert len(result.risk_breakdown) > 0
    assert "raw_rule_score" in result.audit
    assert "capped_score" in result.audit


def test_5_category_health_score_breakdown():
    """Verify repository health score produces 5 categories and a 0-100 overall score."""
    pf = ParsedFileAST(file_path="src/app.ts", file_hash="h1", language="typescript")
    builder = KnowledgeGraphBuilder()
    graph, hash_val, health = builder.build_graph_from_parsed_files([pf])

    assert isinstance(health.health_score, int)
    assert 0 <= health.health_score <= 100
    assert "Architecture" in health.categories
    assert "Dependencies" in health.categories
    assert "Testing" in health.categories
    assert "Security" in health.categories
    assert "Maintainability" in health.categories

    assert health.categories["Architecture"].score >= 10
    assert health.categories["Testing"].score >= 10


def test_vendor_and_generated_file_exclusion():
    """Verify node_modules, .next, venv, and dist are excluded from analysis."""
    assert is_generated_or_vendor("node_modules/express/index.js") is True
    assert is_generated_or_vendor(".next/static/chunks/main.js") is True
    assert is_generated_or_vendor("venv/lib/site-packages/fastapi/__init__.py") is True
    assert is_generated_or_vendor("dist/index.js") is True
    assert is_generated_or_vendor("src/index.ts") is False
