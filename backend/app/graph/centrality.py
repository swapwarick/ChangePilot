"""Graph centrality analysis: hub detection and architectural chokepoint identification.

Provides two complementary metrics for understanding which nodes in the
dependency graph carry the most structural risk:

* **Hub nodes** — ranked by total degree (in + out).  The most heavily
  connected nodes are likely shared utilities or core services; changes to
  them affect many consumers simultaneously.

* **Bridge nodes** — ranked by betweenness centrality.  Nodes that sit on
  the shortest path between many other node pairs act as architectural
  chokepoints.  If a bridge node is broken, large portions of the graph
  lose transitive connectivity.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class HubNode:
    """A highly-connected node in the dependency graph."""
    node_id: str
    label: str
    kind: str
    path: str | None
    in_degree: int
    out_degree: int
    total_degree: int
    is_critical: bool = False


@dataclass
class BridgeNode:
    """An architectural chokepoint identified by betweenness centrality."""
    node_id: str
    label: str
    kind: str
    path: str | None
    betweenness: float   # normalised betweenness centrality score (0 – 1)
    is_critical: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_adjacency(edges: list[DependencyEdge]) -> dict[str, list[str]]:
    """Forward adjacency: source → list of targets."""
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adj[edge.source].append(edge.target)
    return adj


# ---------------------------------------------------------------------------
# Hub node detection
# ---------------------------------------------------------------------------

def find_hub_nodes(
    graph: DependencyGraph,
    top_n: int = 10,
    exclude_kinds: frozenset[str] | None = None,
) -> list[HubNode]:
    """Find the most connected nodes by total degree (in + out).

    File, folder, package, and repository nodes are excluded by default because
    their degree counts are dominated by structural containment edges rather than
    meaningful code-level coupling.  Pass a custom *exclude_kinds* set to
    override this behaviour.

    Args:
        graph:         The repository dependency graph.
        top_n:         Maximum number of hub nodes to return.
        exclude_kinds: Node kinds to omit from results.

    Returns:
        Up to *top_n* :class:`HubNode` instances ordered by total degree
        descending.
    """
    if exclude_kinds is None:
        exclude_kinds = frozenset({"file", "folder", "package", "repository"})

    in_deg: Counter[str] = Counter()
    out_deg: Counter[str] = Counter()

    for edge in graph.edges:
        out_deg[edge.source] += 1
        in_deg[edge.target] += 1

    candidates: list[HubNode] = []
    for node in graph.nodes:
        if node.kind in exclude_kinds:
            continue
        ind = in_deg.get(node.id, 0)
        outd = out_deg.get(node.id, 0)
        total = ind + outd
        if total == 0:
            continue
        candidates.append(
            HubNode(
                node_id=node.id,
                label=node.label,
                kind=node.kind,
                path=node.path,
                in_degree=ind,
                out_degree=outd,
                total_degree=total,
                is_critical=node.is_critical,
            )
        )

    candidates.sort(key=lambda h: h.total_degree, reverse=True)
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Bridge node detection — approximate betweenness centrality
# ---------------------------------------------------------------------------

def _brandes_betweenness(
    adj: dict[str, list[str]],
    node_ids: list[str],
) -> dict[str, float]:
    """Compute normalised betweenness centrality using Brandes' algorithm.

    This is an O(V * E) implementation suitable for graphs up to ~3,000 nodes.
    For larger graphs callers should use the sampling path in
    :func:`find_bridge_nodes`.

    Args:
        adj:      Forward adjacency map.
        node_ids: All node IDs to iterate over as BFS sources.

    Returns:
        Mapping of node_id → normalised betweenness score.
    """
    bc: dict[str, float] = {nid: 0.0 for nid in node_ids}
    n = len(node_ids)
    if n <= 2:
        return bc

    norm = (n - 1) * (n - 2)  # normalisation denominator

    for source in node_ids:
        # BFS to find shortest paths from source
        stack: list[str] = []
        predecessors: dict[str, list[str]] = {nid: [] for nid in node_ids}
        sigma: dict[str, float] = dict.fromkeys(node_ids, 0.0)
        dist: dict[str, int] = dict.fromkeys(node_ids, -1)
        sigma[source] = 1.0
        dist[source] = 0
        queue: list[str] = [source]
        head = 0

        while head < len(queue):
            v = queue[head]
            head += 1
            stack.append(v)
            for w in adj.get(v, []):
                if w not in dist:
                    continue
                if dist[w] < 0:
                    queue.append(w)
                    dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)

        # Accumulate dependencies
        delta: dict[str, float] = dict.fromkeys(node_ids, 0.0)
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != source:
                bc[w] += delta[w]

    if norm > 0:
        for nid in bc:
            bc[nid] /= norm

    return bc


def find_bridge_nodes(
    graph: DependencyGraph,
    top_n: int = 10,
    sample_size: int | None = None,
    exclude_kinds: frozenset[str] | None = None,
) -> list[BridgeNode]:
    """Find architectural chokepoints using betweenness centrality.

    A *bridge node* sits on the shortest path between many other node pairs.
    Breaking or significantly changing a bridge node disconnects large portions
    of the codebase and carries disproportionate risk.

    For graphs with fewer than 3,000 nodes, exact Brandes centrality is used.
    For larger graphs a random sample of *sample_size* source nodes is used to
    approximate the scores (sampled nodes still yield reliable top-k rankings).

    Args:
        graph:        The repository dependency graph.
        top_n:        Maximum number of bridge nodes to return.
        sample_size:  Number of source nodes to sample for large graphs.
                      Auto-set to ``min(500, n_nodes)`` if *None* and the graph
                      is large.
        exclude_kinds: Node kinds to exclude from results.

    Returns:
        Up to *top_n* :class:`BridgeNode` instances ordered by betweenness
        centrality descending.
    """
    if exclude_kinds is None:
        exclude_kinds = frozenset({"file", "folder", "package", "repository"})

    node_by_id: dict[str, DependencyNode] = {n.id: n for n in graph.nodes}
    candidate_ids = [
        n.id for n in graph.nodes if n.kind not in exclude_kinds
    ]

    if len(candidate_ids) < 3:
        return []

    adj = _build_adjacency(graph.edges)

    # Decide whether to run exact or sampled betweenness
    if len(candidate_ids) > 3_000:
        import random
        k = sample_size if sample_size is not None else min(500, len(candidate_ids))
        sources = random.sample(candidate_ids, k)
        logger.debug(
            "Large graph (%d nodes): computing approximate betweenness from %d sampled sources.",
            len(candidate_ids),
            k,
        )
        bc = _brandes_betweenness(adj, sources)
    else:
        bc = _brandes_betweenness(adj, candidate_ids)

    results: list[BridgeNode] = []
    for nid, score in bc.items():
        if score <= 0:
            continue
        node = node_by_id.get(nid)
        if node is None or node.kind in exclude_kinds:
            continue
        results.append(
            BridgeNode(
                node_id=nid,
                label=node.label,
                kind=node.kind,
                path=node.path,
                betweenness=round(score, 6),
                is_critical=node.is_critical,
            )
        )

    results.sort(key=lambda b: b.betweenness, reverse=True)
    return results[:top_n]


# ---------------------------------------------------------------------------
# Convenience: combined centrality summary
# ---------------------------------------------------------------------------

@dataclass
class CentralitySummary:
    """Combined hub + bridge centrality analysis results."""
    hub_nodes: list[HubNode]
    bridge_nodes: list[BridgeNode]


def analyse_centrality(
    graph: DependencyGraph,
    top_n: int = 10,
) -> CentralitySummary:
    """Run both hub and bridge detection and return a combined summary.

    Args:
        graph:  The repository dependency graph.
        top_n:  How many nodes to return for each metric.

    Returns:
        :class:`CentralitySummary` with ``hub_nodes`` and ``bridge_nodes``.
    """
    return CentralitySummary(
        hub_nodes=find_hub_nodes(graph, top_n=top_n),
        bridge_nodes=find_bridge_nodes(graph, top_n=top_n),
    )
