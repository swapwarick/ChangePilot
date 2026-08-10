"""Execution flow tracing for change impact analysis.

Traces call-chain paths starting from directly changed functions and follows
``CALLS`` relationships through the dependency graph to identify downstream
functions that could be affected.  The result provides reviewers with concrete
execution flows like::

    changed_fn → caller_a → caller_b → entry_point

rather than a flat list of impacted files.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

from app.models.graph import DependencyEdge, DependencyGraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FlowStep:
    """A single node in an execution flow chain."""
    node_id: str
    label: str
    kind: str           # 'function' | 'class' | 'api' | …
    file_path: str | None
    depth: int          # 0 = root (the changed function)
    is_critical: bool = False


@dataclass
class ExecutionFlow:
    """A single root-to-leaf execution call chain starting from a changed node."""
    root_function: str          # Name of the changed function (entry point)
    root_file: str | None       # File containing the root function
    steps: list[FlowStep] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """Longest call chain depth from root to leaf."""
        return max((s.depth for s in self.steps), default=0)

    def as_path(self) -> list[str]:
        """Return a human-readable call path: ``[fn_a, fn_b, fn_c]``."""
        return [s.label for s in sorted(self.steps, key=lambda s: s.depth)]


@dataclass
class FlowTraceResult:
    """Aggregated execution flow tracing result."""
    flows: list[ExecutionFlow] = field(default_factory=list)
    # Flat list of all unique function nodes reached across all flows
    all_reached_functions: list[str] = field(default_factory=list)
    # File paths of all uniquely reached nodes
    reached_file_paths: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_call_adjacency(edges: list[DependencyEdge]) -> dict[str, list[str]]:
    """Build a forward call graph: caller_id → list of callee_ids.

    Only ``CALLS`` edges are included.  ``IMPORTS`` and structural edges are
    excluded because they model structural dependencies, not runtime call chains.
    """
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relationship == "CALLS":
            adj.setdefault(edge.source, []).append(edge.target)
    return adj


def _build_caller_adjacency(edges: list[DependencyEdge]) -> dict[str, list[str]]:
    """Build a reverse call graph: callee_id → list of caller_ids.

    This lets us answer "who calls *this* function?" — essential for tracing
    upstream impact when a function is changed.
    """
    adj: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relationship == "CALLS":
            adj.setdefault(edge.target, []).append(edge.source)
    return adj


# ---------------------------------------------------------------------------
# Main flow tracer
# ---------------------------------------------------------------------------

def trace_execution_flows(
    graph: DependencyGraph,
    changed_function_ids: list[str],
    max_depth: int = 4,
    max_flows: int = 20,
) -> FlowTraceResult:
    """Trace upstream call chains from a set of changed function nodes.

    For each changed function, BFS traversal climbs the reverse call graph to
    find all callers at each depth level.  This answers the question:
    "If *this* function changes, which upstream callers will be affected?"

    The traversal is bounded by *max_depth* to keep results focused.  A single
    shared visited set prevents the same node from appearing in multiple flows.

    Args:
        graph:                  The repository dependency graph.
        changed_function_ids:   IDs of directly changed function/class nodes.
        max_depth:              Maximum caller-chain depth to trace.
        max_flows:              Maximum number of root flows to return.

    Returns:
        :class:`FlowTraceResult` with per-root :class:`ExecutionFlow` objects
        and aggregated summary lists.
    """
    node_by_id = {n.id: n for n in graph.nodes}
    caller_adj = _build_caller_adjacency(graph.edges)

    result = FlowTraceResult()
    all_reached: set[str] = set()
    all_paths: set[str] = set()

    for root_id in changed_function_ids[:max_flows]:
        root_node = node_by_id.get(root_id)
        if root_node is None:
            continue

        flow = ExecutionFlow(
            root_function=root_node.label,
            root_file=root_node.path,
        )

        # BFS from the root function climbing the call graph upward
        visited: set[str] = {root_id}
        queue: deque[tuple[str, int]] = deque([(root_id, 0)])

        # Add root step
        flow.steps.append(
            FlowStep(
                node_id=root_id,
                label=root_node.label,
                kind=root_node.kind,
                file_path=root_node.path,
                depth=0,
                is_critical=root_node.is_critical,
            )
        )

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for caller_id in caller_adj.get(current_id, []):
                if caller_id in visited:
                    continue
                visited.add(caller_id)

                caller_node = node_by_id.get(caller_id)
                if caller_node is None:
                    continue

                flow.steps.append(
                    FlowStep(
                        node_id=caller_id,
                        label=caller_node.label,
                        kind=caller_node.kind,
                        file_path=caller_node.path,
                        depth=depth + 1,
                        is_critical=caller_node.is_critical,
                    )
                )
                all_reached.add(caller_node.label)
                if caller_node.path:
                    all_paths.add(caller_node.path)

                queue.append((caller_id, depth + 1))

        if len(flow.steps) > 1:
            result.flows.append(flow)

    result.all_reached_functions = sorted(all_reached)
    result.reached_file_paths = sorted(all_paths)
    return result


def find_function_node_ids(
    graph: DependencyGraph,
    function_names: list[str],
) -> list[str]:
    """Resolve a list of function names to their graph node IDs.

    Matches by node label (case-sensitive) and restricts to nodes of kind
    ``function`` or ``class``.

    Args:
        graph:          The repository dependency graph.
        function_names: List of function/method names to look up.

    Returns:
        List of matching node IDs.  If a name matches multiple nodes, all
        matching IDs are returned.
    """
    name_set = set(function_names)
    return [
        n.id
        for n in graph.nodes
        if n.kind in ("function", "class") and n.label in name_set
    ]
