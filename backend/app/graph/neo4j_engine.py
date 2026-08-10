"""Neo4j Dependency Graph Traversal Engine.

Stores temporary graph indexes in Neo4j and runs Cypher variable-length paths
to calculate blast radius and downstream dependency fan-out.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from neo4j import AsyncGraphDatabase

from app.core.config import get_settings
from app.models.graph import DependencyGraph

logger = logging.getLogger(__name__)


@dataclass
class BlastRadiusResult:
    changed_files: list[str]
    direct_impact_files: list[str] = field(default_factory=list)
    indirect_impact_files: list[str] = field(default_factory=list)
    impacted_nodes: list[str] = field(default_factory=list)
    impacted_modules: list[str] = field(default_factory=list)
    impacted_services: list[str] = field(default_factory=list)
    affected_apis: list[str] = field(default_factory=list)
    affected_db_models: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    transitive_dependency_count: int = 0
    max_depth: int = 0


class Neo4jGraphEngine:
    """Async Neo4j query engine for graph indexing and blast radius computation."""

    def __init__(self) -> None:
        settings = get_settings()
        self._uri = settings.neo4j_uri
        self._user = settings.neo4j_user
        self._password = settings.neo4j_password
        self._driver = None

    async def get_driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def sync_graph(self, repo_id: str, graph: DependencyGraph) -> None:
        """Syncs PostgreSQL graph snapshot into Neo4j graph nodes and edges."""
        try:
            driver = await self.get_driver()
            async with driver.session() as session:
                await session.run("MATCH (n {repo_id: $repo_id}) DETACH DELETE n", repo_id=repo_id)

                nodes_payload = [
                    {
                        "id": node.id,
                        "label": node.label,
                        "kind": node.kind,
                        "path": node.path or "",
                        "repo_id": repo_id,
                    }
                    for node in graph.nodes
                ]
                if nodes_payload:
                    query_nodes = """
                    UNWIND $nodes AS n
                    CREATE (item:Node {id: n.id, label: n.label, kind: n.kind, path: n.path, repo_id: n.repo_id})
                    """
                    await session.run(query_nodes, nodes=nodes_payload)

                edges_payload = [
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relationship": edge.relationship,
                        "repo_id": repo_id,
                    }
                    for edge in graph.edges
                ]
                if edges_payload:
                    query_edges = """
                    UNWIND $edges AS e
                    MATCH (src:Node {id: e.source, repo_id: e.repo_id})
                    MATCH (tgt:Node {id: e.target, repo_id: e.repo_id})
                    CREATE (src)-[:REL {type: e.relationship}]->(tgt)
                    """
                    await session.run(query_edges, edges=edges_payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j sync warning (falling back to in-memory graph): %s", exc)

    async def calculate_blast_radius(
        self, repo_id: str, changed_files: list[str], graph: DependencyGraph | None = None
    ) -> BlastRadiusResult:
        """Executes Cypher variable-length path traversal or in-memory graph BFS to compute downstream blast radius."""
        try:
            driver = await self.get_driver()
            async with driver.session() as session:
                query = """
                MATCH (src:Node {repo_id: $repo_id})
                WHERE src.path IN $changed_files OR src.id IN $changed_files
                OPTIONAL MATCH (dependent:Node {repo_id: $repo_id})-[r:REL*1..5]->(src)
                RETURN 
                    collect(distinct dependent.id) as impacted_ids,
                    collect(distinct dependent.label) as impacted_labels,
                    collect(distinct dependent.kind) as impacted_kinds,
                    collect(distinct dependent.path) as impacted_paths
                """
                result = await session.run(query, repo_id=repo_id, changed_files=changed_files)
                record = await result.single()
                if record and record["impacted_ids"]:
                    impacted_ids = record["impacted_ids"] or []
                    impacted_paths = [p for p in record["impacted_paths"] if p]
                    impacted_labels = record["impacted_labels"] or []

                    direct = [p for p in impacted_paths if any(c in p for c in changed_files)]
                    indirect = [p for p in impacted_paths if p not in direct and p not in changed_files]
                    affected_tests = [p for p in impacted_paths if "test" in p.lower() or "spec" in p.lower()]
                    affected_apis = [l for l in impacted_labels if "GET" in l or "POST" in l or "PUT" in l or "DELETE" in l]

                    return BlastRadiusResult(
                        changed_files=changed_files,
                        direct_impact_files=direct,
                        indirect_impact_files=indirect,
                        impacted_nodes=impacted_ids,
                        impacted_modules=sorted(set(impacted_labels)),
                        affected_apis=affected_apis,
                        affected_tests=affected_tests,
                        transitive_dependency_count=len(impacted_ids),
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j blast radius fallback: %s", exc)

        # In-Memory BFS Traversal Fallback
        direct: set[str] = set()
        indirect: set[str] = set()
        impacted_nodes: set[str] = set()
        affected_apis: set[str] = set()
        affected_db_models: set[str] = set()
        affected_tests: set[str] = set()

        if graph:
            # Build reverse lookup: target -> source
            reverse_adj: dict[str, list[tuple[str, str]]] = {}
            node_map = {n.id: n for n in graph.nodes}
            file_id_map = {n.path: n.id for n in graph.nodes if n.kind == "file" and n.path}

            for edge in graph.edges:
                reverse_adj.setdefault(edge.target, []).append((edge.source, edge.relationship))

            # Multi-hop BFS from changed files
            queue: list[tuple[str, int]] = []
            visited: set[str] = set()

            for cf in changed_files:
                target_id = file_id_map.get(cf, f"file:{cf}")
                queue.append((target_id, 0))
                visited.add(target_id)

            while queue:
                curr_id, depth = queue.pop(0)
                curr_node = node_map.get(curr_id)

                if curr_node:
                    impacted_nodes.add(curr_node.id)
                    if curr_node.kind == "api":
                        affected_apis.add(curr_node.label)
                    elif curr_node.kind == "database":
                        affected_db_models.add(curr_node.label)

                    if curr_node.kind == "file" and curr_node.path:
                        if depth == 1:
                            direct.add(curr_node.path)
                        elif depth > 1:
                            indirect.add(curr_node.path)

                        if "test" in curr_node.path.lower() or "spec" in curr_node.path.lower():
                            affected_tests.add(curr_node.path)

                if depth < 4:
                    for src_id, _rel in reverse_adj.get(curr_id, []):
                        if src_id not in visited:
                            visited.add(src_id)
                            queue.append((src_id, depth + 1))

        return BlastRadiusResult(
            changed_files=changed_files,
            direct_impact_files=sorted(direct),
            indirect_impact_files=sorted(indirect),
            impacted_nodes=sorted(impacted_nodes),
            impacted_modules=[f.split("/")[0] for f in changed_files if "/" in f],
            affected_apis=sorted(affected_apis),
            affected_db_models=sorted(affected_db_models),
            affected_tests=sorted(affected_tests),
            transitive_dependency_count=len(impacted_nodes),
        )

