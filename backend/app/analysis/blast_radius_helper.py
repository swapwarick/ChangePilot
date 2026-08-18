"""Graph analysis helper that enriches a RiskInput with blast radius and centrality data.

This module bridges the dependency graph representation used by the knowledge
graph builder with the blast radius and centrality modules.  It is intentionally
kept as a thin orchestration layer so that each constituent module remains
independently testable.
"""

from __future__ import annotations

import logging

from app.analysis.flow_tracer import find_function_node_ids, trace_execution_flows
from app.graph.blast_radius import BlastRadiusResult, compute_blast_radius
from app.graph.centrality import find_bridge_nodes, find_hub_nodes
from app.models.graph import DependencyGraph
from app.models.risk import RiskInput

logger = logging.getLogger(__name__)


def enrich_risk_input_with_graph_analysis(
    graph: DependencyGraph,
    risk_input: RiskInput,
    changed_files: list[str],
    run_flows: bool = False,
    blast_depth: int = 3,
    centrality_top_n: int = 10,
) -> tuple[RiskInput, BlastRadiusResult | None]:
    """Compute blast radius and centrality metrics and populate *risk_input*.

    Finds the graph node IDs for each changed file, runs blast radius BFS
    traversal, identifies hub and bridge nodes in the impact set, and
    optionally runs execution flow tracing when *run_flows* is True.

    Args:
        graph:            The built dependency graph.
        risk_input:       Base :class:`RiskInput` to enrich (treated as immutable;
                          a copy is returned with new fields populated).
        changed_files:    List of changed file paths used to locate graph nodes.
        run_flows:        If True, also trace upstream call chains from changed
                          function nodes.  Slightly more expensive.
        blast_depth:      Maximum BFS depth for blast radius traversal.
        centrality_top_n: How many hub / bridge nodes to compute.

    Returns:
        Tuple of (enriched :class:`RiskInput`, :class:`BlastRadiusResult` or None).
    """
    # Resolve changed files → graph node IDs
    changed_node_ids: list[str] = []
    for node in graph.nodes:
        if node.kind == "file" and node.path and node.path in changed_files:
            changed_node_ids.append(node.id)

    if not changed_node_ids:
        logger.debug("No graph nodes matched the changed file list; skipping graph enrichment.")
        return risk_input, None

    # --- Blast radius traversal ---------------------------------------------------
    blast_result = compute_blast_radius(
        graph=graph,
        changed_node_ids=changed_node_ids,
        max_depth=blast_depth,
    )

    # --- Hub node detection -------------------------------------------------------
    hub_nodes = find_hub_nodes(graph, top_n=centrality_top_n)
    hub_labels_in_blast: list[str] = []
    blast_node_ids = {n.node_id for n in blast_result.impacted_nodes} | {n.node_id for n in blast_result.changed_nodes}
    for hub in hub_nodes:
        if hub.node_id in blast_node_ids:
            hub_labels_in_blast.append(hub.label)

    # --- Bridge node detection ----------------------------------------------------
    bridge_nodes = find_bridge_nodes(graph, top_n=centrality_top_n)
    bridge_labels_in_blast: list[str] = []
    for bridge in bridge_nodes:
        if bridge.node_id in blast_node_ids:
            bridge_labels_in_blast.append(bridge.label)

    # --- Execution flow tracing (deep mode only) ----------------------------------
    if run_flows:
        fn_ids = find_function_node_ids(graph, function_names=[
            n.label for n in graph.nodes
            if n.kind == "function" and n.id in blast_node_ids
        ])
        flow_result = trace_execution_flows(
            graph=graph,
            changed_function_ids=fn_ids,
            max_depth=4,
        )
        # Attach to blast_result as a side-channel for the caller
        blast_result._flow_result = flow_result  # type: ignore[attr-defined]

    # --- Enrich risk input --------------------------------------------------------
    enriched = risk_input.model_copy(
        update={
            "blast_radius_depth": blast_result.max_depth_reached,
            "blast_radius_size": blast_result.total_impact_size,
            "hub_nodes_affected": hub_labels_in_blast[:5],
            "bridge_nodes_affected": bridge_labels_in_blast[:5],
        }
    )

    return enriched, blast_result
