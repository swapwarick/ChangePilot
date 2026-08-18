"""Blast radius traversal for the repository dependency graph.

Given a set of directly changed graph nodes, this module performs a
breadth-first traversal of ``IMPORTS``, ``CALLS``, and ``DEPENDS_ON`` edges
to compute the full *transitive* impact set — every node that could be
affected by the change, grouped by traversal depth.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class BlastRadiusNode:
    """A single node in the transitive impact set."""
    node_id: str
    label: str
    kind: str
    path: str | None
    depth: int          # 0 = directly changed; 1 = direct dependent; etc.
    is_critical: bool = False


@dataclass
class BlastRadiusResult:
    """Full transitive impact result for a set of changed nodes."""
    # Nodes that were directly changed (depth 0)
    changed_nodes: list[BlastRadiusNode] = field(default_factory=list)
    # All transitively impacted nodes (depth >= 1)
    impacted_nodes: list[BlastRadiusNode] = field(default_factory=list)
    # File paths of all impacted nodes (deduplicated)
    impacted_file_paths: list[str] = field(default_factory=list)
    # Maximum traversal depth reached
    max_depth_reached: int = 0
    # Total number of nodes in the impact set (changed + impacted)
    total_impact_size: int = 0
    # Detailed traversal paths explaining why nodes are impacted
    dependency_paths: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Edge relationship categories
# ---------------------------------------------------------------------------

_FORWARD_IMPACT_RELATIONSHIPS = frozenset({
    "IMPORTS",
    "CALLS",
    "DEPENDS_ON",
    "USES",
    "INHERITS",
    "IMPLEMENTS",
})


def _build_reverse_adjacency(
    edges: list[DependencyEdge],
) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if getattr(edge, "edge_type", None) in ("CONFIG_REFERENCE", "BUILD_DEPENDENCY"):
            continue
        if edge.relationship in _FORWARD_IMPACT_RELATIONSHIPS:
            adj.setdefault(edge.target, []).append(edge.source)
    return adj


# ---------------------------------------------------------------------------
# Main traversal
# ---------------------------------------------------------------------------

def compute_blast_radius(
    graph: DependencyGraph,
    changed_node_ids: list[str],
    max_depth: int = 3,
) -> BlastRadiusResult:
    node_by_id: dict[str, DependencyNode] = {n.id: n for n in graph.nodes}
    reverse_adj = _build_reverse_adjacency(graph.edges)

    _EXCLUDED_KINDS = frozenset({"package", "repository", "folder"})

    result = BlastRadiusResult()
    visited: set[str] = set()

    # Queue contains: (current_id, depth, path_string)
    queue: deque[tuple[str, int, str]] = deque()
    for nid in changed_node_ids:
        if nid in node_by_id:
            queue.append((nid, 0, nid))
            visited.add(nid)
            node = node_by_id[nid]
            result.changed_nodes.append(
                BlastRadiusNode(
                    node_id=nid,
                    label=node.label,
                    kind=node.kind,
                    path=node.path,
                    depth=0,
                    is_critical=node.is_critical,
                )
            )

    max_depth_reached = 0

    while queue:
        current_id, depth, path_so_far = queue.popleft()
        max_depth_reached = max(max_depth_reached, depth)

        if depth >= max_depth:
            continue

        for dependent_id in reverse_adj.get(current_id, []):
            if dependent_id in visited:
                continue
            visited.add(dependent_id)

            node = node_by_id.get(dependent_id)
            if node is None or node.kind in _EXCLUDED_KINDS:
                continue

            new_path = f"{path_so_far} -> {dependent_id}"
            result.dependency_paths.append(new_path)

            blast_node = BlastRadiusNode(
                node_id=dependent_id,
                label=node.label,
                kind=node.kind,
                path=node.path,
                depth=depth + 1,
                is_critical=node.is_critical,
            )
            result.impacted_nodes.append(blast_node)
            queue.append((dependent_id, depth + 1, new_path))

    seen_paths: set[str] = set()
    for n in result.impacted_nodes:
        if n.path and n.kind in ("file", "function", "class", "api", "database"):
            if n.path not in seen_paths:
                seen_paths.add(n.path)
                result.impacted_file_paths.append(n.path)

    result.max_depth_reached = max_depth_reached
    result.total_impact_size = len(result.changed_nodes) + len(result.impacted_nodes)
    return result


def enrich_graph_nodes_with_blast_radius(
    graph: DependencyGraph,
    changed_node_ids: list[str],
    max_depth: int = 3,
) -> DependencyGraph:
    """Return a copy of *graph* with ``blast_radius`` counts populated.

    Sets ``node.blast_radius`` on each node in the graph to the count of nodes
    it transitively impacts — a useful metric for prioritising review effort.

    Args:
        graph:            The repository dependency graph.
        changed_node_ids: IDs of directly changed nodes.
        max_depth:        BFS depth limit (default: 3).

    Returns:
        The same *graph* object with ``blast_radius`` fields mutated in-place.
    """
    reverse_adj = _build_reverse_adjacency(graph.edges)
    node_by_id: dict[str, DependencyNode] = {n.id: n for n in graph.nodes}

    for start_id in changed_node_ids:
        visited: set[str] = set([start_id])
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        count = 0

        while queue:
            nid, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for dep_id in reverse_adj.get(nid, []):
                if dep_id not in visited:
                    visited.add(dep_id)
                    count += 1
                    queue.append((dep_id, depth + 1))

        if start_id in node_by_id:
            node_by_id[start_id].blast_radius = count

    return graph
