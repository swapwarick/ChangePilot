"""Unit tests for graph metric correctness:

Covers:
- File fan-in / fan-out precision
- Folder aggregated metrics (fan-in, fan-out, internal/external deps)
- Module aggregated metrics (via folder path prefix)
- Duplicate edge deduplication
- Self-edge exclusion
- Internal vs external dependency classification
"""


from app.analysis.tree_sitter_parser import ImportSymbol, ParsedFileAST
from app.graph.knowledge_graph import KnowledgeGraphBuilder


def _make_parsed(path: str, imports: list[str], *, lang="typescript") -> ParsedFileAST:
    return ParsedFileAST(
        file_path=path,
        file_hash=f"hash-{path}",
        language=lang,
        imports=[
            ImportSymbol(source_module=src, imported_name="*", is_relative=True)
            for src in imports
        ],
    )


# ---------------------------------------------------------------------------
# File metric tests
# ---------------------------------------------------------------------------

def test_file_fan_in_counts_distinct_importers():
    """Fan-In = distinct source files importing this file."""
    pf_utils = _make_parsed("src/utils.ts", [])
    pf_a = _make_parsed("src/a.ts", ["./utils.ts"])
    pf_b = _make_parsed("src/b.ts", ["./utils.ts"])
    pf_c = _make_parsed("src/c.ts", ["./utils.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_utils, pf_a, pf_b, pf_c])

    utils_node = next(n for n in graph.nodes if n.id == "file:src/utils.ts")
    assert utils_node.fan_in == 3


def test_file_fan_out_counts_distinct_imports():
    """Fan-Out = distinct internal target files imported by this file."""
    pf_a = _make_parsed("src/a.ts", ["./b.ts", "./c.ts", "./d.ts"])
    pf_b = _make_parsed("src/b.ts", [])
    pf_c = _make_parsed("src/c.ts", [])
    pf_d = _make_parsed("src/d.ts", [])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_a, pf_b, pf_c, pf_d])

    a_node = next(n for n in graph.nodes if n.id == "file:src/a.ts")
    assert a_node.fan_out == 3


def test_duplicate_imports_not_counted_twice():
    """Duplicate import statements from same file to same target count once."""
    pf_a = _make_parsed("src/a.ts", ["./b.ts", "./b.ts", "./b.ts"])
    pf_b = _make_parsed("src/b.ts", [])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_a, pf_b])

    a_node = next(n for n in graph.nodes if n.id == "file:src/a.ts")
    b_node = next(n for n in graph.nodes if n.id == "file:src/b.ts")
    assert a_node.fan_out == 1
    assert b_node.fan_in == 1


def test_self_import_excluded_from_fan_metrics():
    """Self-imports must NOT increment fan-in or fan-out."""
    pf = _make_parsed("src/self.ts", ["./self.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, health = builder.build_graph_from_parsed_files([pf])

    self_node = next(n for n in graph.nodes if n.id == "file:src/self.ts")
    assert self_node.fan_in == 0
    assert self_node.fan_out == 0
    # graph_health is on the DependencyGraph object
    assert graph.graph_health is not None
    assert graph.graph_health.self_edge_count == 1
    assert len(health.circular_dependencies) == 0


# ---------------------------------------------------------------------------
# Folder metric tests (via graph topology, tested from knowledge graph output)
# ---------------------------------------------------------------------------

def test_folder_fan_in_from_external_importers():
    """
    Folder fan-in = distinct external SOURCE_IMPORT files that import any file inside the folder.
    BUILD_DEPENDENCY infrastructure edges (folder→file, module→folder) are excluded.
    """
    # files inside the folder
    pf_service = _make_parsed("runtime/AgentLifecycle.ts", [])
    pf_metrics = _make_parsed("runtime/RuntimeMetrics.ts", [])
    # external importers
    pf_ext1 = _make_parsed("src/orchestrator.ts", ["../runtime/AgentLifecycle.ts"])
    pf_ext2 = _make_parsed("src/monitor.ts", ["../runtime/RuntimeMetrics.ts"])
    # internal importer (between sibling folder files - should NOT count toward fan-in)
    pf_internal = _make_parsed("runtime/AgentRuntime.ts", ["./AgentLifecycle.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_service, pf_metrics, pf_ext1, pf_ext2, pf_internal])

    SOURCE_EDGE_TYPES = {"SOURCE_IMPORT", "DYNAMIC_IMPORT", "IMPORTS"}

    # Only file nodes inside runtime/ (not the folder/module nodes themselves)
    runtime_file_ids = {n.id for n in graph.nodes if n.kind == "file" and n.path and n.path.startswith("runtime/")}
    external_file_importers = set()
    for edge in graph.edges:
        if edge.edge_type not in SOURCE_EDGE_TYPES:
            continue
        if edge.target in runtime_file_ids and edge.source not in runtime_file_ids:
            external_file_importers.add(edge.source)

    assert len(external_file_importers) == 2


def test_folder_internal_dependencies_not_counted_as_external():
    """
    SOURCE_IMPORT edges between files inside the same folder are internal dependencies.
    They must NOT appear as external fan-in or fan-out.
    """
    pf_a = _make_parsed("runtime/a.ts", ["./b.ts"])
    pf_b = _make_parsed("runtime/b.ts", ["./c.ts"])
    pf_c = _make_parsed("runtime/c.ts", [])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_a, pf_b, pf_c])

    # Only count SOURCE_IMPORT edges (real code imports), not BUILD_DEPENDENCY infrastructure
    SOURCE_EDGE_TYPES = {"SOURCE_IMPORT", "DYNAMIC_IMPORT", "IMPORTS"}

    runtime_file_ids = {n.id for n in graph.nodes if n.kind == "file" and n.path and n.path.startswith("runtime/")}
    internal_edges = [
        e for e in graph.edges
        if e.source in runtime_file_ids and e.target in runtime_file_ids
        and e.edge_type in SOURCE_EDGE_TYPES
    ]
    external_fan_in = {
        e.source for e in graph.edges
        if e.target in runtime_file_ids and e.source not in runtime_file_ids
        and e.edge_type in SOURCE_EDGE_TYPES
    }
    external_fan_out = {
        e.target for e in graph.edges
        if e.source in runtime_file_ids and e.target not in runtime_file_ids
        and e.edge_type in SOURCE_EDGE_TYPES
    }

    assert len(internal_edges) == 2        # a→b, b→c
    assert len(external_fan_in) == 0       # nothing external imports into runtime/
    assert len(external_fan_out) == 0      # nothing imports from outside runtime/ime/


def test_folder_fan_out_counts_distinct_external_targets():
    """
    Folder fan-out = distinct external nodes imported by files inside the folder.
    """
    pf_helper = _make_parsed("lib/utils.ts", [])
    pf_types = _make_parsed("lib/types.ts", [])
    pf_a = _make_parsed("runtime/AgentLifecycle.ts", ["../lib/utils.ts"])
    pf_b = _make_parsed("runtime/AgentRuntime.ts", ["../lib/utils.ts", "../lib/types.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf_helper, pf_types, pf_a, pf_b])

    folder_node_ids = {n.id for n in graph.nodes if n.path and n.path.startswith("runtime/")}
    external_targets = {
        e.target for e in graph.edges
        if e.source in folder_node_ids and e.target not in folder_node_ids
    }

    # Both a.ts and b.ts import utils.ts; b.ts also imports types.ts → 2 distinct external targets
    assert len(external_targets) == 2


# ---------------------------------------------------------------------------
# Graph health / edge count tests
# ---------------------------------------------------------------------------

def test_graph_health_counts_self_edges_correctly():
    pf1 = _make_parsed("src/x.ts", ["./x.ts"])  # self import
    pf2 = _make_parsed("src/y.ts", ["./x.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, _ = builder.build_graph_from_parsed_files([pf1, pf2])

    assert graph.graph_health is not None
    assert graph.graph_health.self_edge_count == 1


def test_graph_health_no_circular_count_for_self_imports():
    pf = _make_parsed("src/a.ts", ["./a.ts"])

    builder = KnowledgeGraphBuilder()
    graph, _, health = builder.build_graph_from_parsed_files([pf])

    assert graph.graph_health.circular_dependency_count == 0
    assert len(health.circular_dependencies) == 0
