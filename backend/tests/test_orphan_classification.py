"""Regression tests for file classification hierarchy and orphan candidate isolation.

Guarantees:
1. Every file is classified first into its architectural role (ENTRYPOINT, CLI_SCRIPT, EXAMPLE, TEST, CONFIGURATION, DOCUMENTATION, GENERATED, SOURCE_MODULE).
2. Examples, CLI scripts, tests, entrypoints, documentation, and configs are NEVER classified as ORPHAN_CANDIDATE even with zero incoming imports.
3. Only genuine SOURCE_MODULE files with zero incoming imports become ORPHAN_CANDIDATE.
4. Total source modules count and diagnostic orphan candidate details are populated accurately.
"""

from app.analysis.file_classifier import (
    FileTypeCategory,
    classify_file,
    classify_file_type,
    extract_package_json_entrypoints,
    filter_architecturally_relevant_files,
)
from app.analysis.tree_sitter_parser import ImportSymbol, ParsedFileAST
from app.graph.knowledge_graph import KnowledgeGraphBuilder
from app.models.enums import FileClassification


def test_file_classification_hierarchy():
    """Verify primary classification of various file roles."""
    # 1. Entrypoints
    assert classify_file("src/index.ts") == FileClassification.ENTRYPOINT
    assert classify_file("src/main.ts") == FileClassification.ENTRYPOINT
    assert classify_file("src/app.tsx") == FileClassification.ENTRYPOINT
    assert classify_file("server.js") == FileClassification.ENTRYPOINT
    assert classify_file("src/diary/client.ts") == FileClassification.ENTRYPOINT
    assert classify_file("app/src/main/java/com/example/MainActivity.kt") == FileClassification.ENTRYPOINT

    # 2. CLI Scripts
    assert classify_file("script.js") == FileClassification.CLI_SCRIPT
    assert classify_file("scripts/deploy.ts") == FileClassification.CLI_SCRIPT
    assert classify_file("bin/run.sh") == FileClassification.CLI_SCRIPT
    assert classify_file("manage.py") == FileClassification.CLI_SCRIPT

    # 3. Examples
    assert classify_file("examples/basic.ts") == FileClassification.EXAMPLE
    assert classify_file("examples/client_demo.js") == FileClassification.EXAMPLE
    assert classify_file("samples/quickstart.py") == FileClassification.EXAMPLE
    assert classify_file("demo/app.tsx") == FileClassification.EXAMPLE

    # 4. Tests
    assert classify_file("tests/test_auth.py") == FileClassification.TEST
    assert classify_file("src/lib/calc.test.ts") == FileClassification.TEST
    assert classify_file("app/features/user.spec.tsx") == FileClassification.TEST
    assert classify_file("app/src/test/java/com/example/UserTest.kt") == FileClassification.TEST

    # 5. Documentation
    assert classify_file("docs/script.js") == FileClassification.DOCUMENTATION
    assert classify_file("docs/index.html") == FileClassification.DOCUMENTATION
    assert classify_file("README.md") == FileClassification.DOCUMENTATION
    assert classify_file("LICENSE") == FileClassification.DOCUMENTATION

    # 6. Configuration & Build
    assert classify_file("package.json") == FileClassification.CONFIGURATION
    assert classify_file("tsconfig.json") == FileClassification.CONFIGURATION
    assert classify_file("build.gradle.kts") == FileClassification.CONFIGURATION
    assert classify_file("Dockerfile") == FileClassification.CONFIGURATION

    # 7. Generated / Vendor
    assert classify_file("dist/bundle.min.js") == FileClassification.GENERATED
    assert classify_file(".next/server/pages/index.js") == FileClassification.GENERATED
    assert classify_file("node_modules/express/index.js") == FileClassification.GENERATED

    # 8. Genuine Source Modules
    assert classify_file("src/lib/calculator.ts") == FileClassification.SOURCE_MODULE
    assert classify_file("app/services/token_generator.py") == FileClassification.SOURCE_MODULE
    assert classify_file("app/src/main/java/com/example/data/UserRepository.kt") == FileClassification.SOURCE_MODULE


def test_package_json_entrypoints_extraction():
    """Verify extraction of entrypoints from package.json main, bin, and exports."""
    pkg_json = {
        "name": "agent-diaries",
        "main": "./dist/index.js",
        "module": "./dist/index.mjs",
        "bin": {
            "agent-cli": "./bin/cli.js"
        },
        "exports": {
            ".": "./dist/index.js",
            "./diary": "./dist/diary/client.js"
        },
        "scripts": {
            "start": "node script.js"
        }
    }
    entrypoints = extract_package_json_entrypoints(pkg_json)
    assert "dist/index.js" in entrypoints or "index.js" in entrypoints
    assert "bin/cli.js" in entrypoints or "cli.js" in entrypoints
    assert "dist/diary/client.js" in entrypoints or "client.js" in entrypoints


def test_orphan_candidate_strict_isolation():
    """Verify that ONLY SOURCE_MODULE files with 0 incoming imports become ORPHAN_CANDIDATE."""
    pf_entry = ParsedFileAST(
        file_path="src/index.ts",
        file_hash="h_entry",
        language="typescript",
        imports=[
            ImportSymbol(source_module="./lib/used_math", imported_name="*", is_relative=True)
        ],
    )
    pf_used = ParsedFileAST(
        file_path="src/lib/used_math.ts",
        file_hash="h_used",
        language="typescript",
    )
    pf_orphan = ParsedFileAST(
        file_path="src/lib/orphaned_calc.ts",
        file_hash="h_orphan",
        language="typescript",
    )
    pf_script = ParsedFileAST(
        file_path="script.js",
        file_hash="h_script",
        language="javascript",
    )
    pf_example = ParsedFileAST(
        file_path="examples/demo.ts",
        file_hash="h_example",
        language="typescript",
    )
    pf_docs_script = ParsedFileAST(
        file_path="docs/script.js",
        file_hash="h_docs",
        language="javascript",
    )
    pf_client = ParsedFileAST(
        file_path="src/diary/client.ts",
        file_hash="h_client",
        language="typescript",
    )
    pf_test = ParsedFileAST(
        file_path="tests/test_math.py",
        file_hash="h_test",
        language="python",
    )

    all_files = [
        pf_entry, pf_used, pf_orphan, pf_script,
        pf_example, pf_docs_script, pf_client, pf_test
    ]

    builder = KnowledgeGraphBuilder()
    graph, _, health = builder.build_graph_from_parsed_files(all_files)

    # 1. Non-source files and entrypoints must NOT be orphan candidates
    assert "script.js" not in health.potential_orphan_candidates
    assert "examples/demo.ts" not in health.potential_orphan_candidates
    assert "docs/script.js" not in health.potential_orphan_candidates
    assert "src/diary/client.ts" not in health.potential_orphan_candidates
    assert "src/index.ts" not in health.potential_orphan_candidates
    assert "tests/test_math.py" not in health.potential_orphan_candidates

    # 2. Used source file must NOT be an orphan candidate
    assert "src/lib/used_math.ts" not in health.potential_orphan_candidates

    # 3. ONLY the genuine unused source module is an orphan candidate
    assert "src/lib/orphaned_calc.ts" in health.potential_orphan_candidates
    assert len(health.potential_orphan_candidates) == 1

    # 4. Total source modules count must be 2 (used_math.ts and orphaned_calc.ts)
    assert health.total_source_modules == 2
    assert graph.graph_health.orphan_candidates == 1
    assert graph.graph_health.total_source_modules == 2

    # 5. Diagnostic orphan candidate details structure
    assert len(health.orphan_candidate_details) == 1
    detail = health.orphan_candidate_details[0]
    assert detail["path"] == "src/lib/orphaned_calc.ts"
    assert detail["classification"] == "SOURCE_MODULE"
    assert detail["incoming_imports"] == 0
    assert "0 incoming source imports" in detail["reason"]
