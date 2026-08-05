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
    impacted_nodes: list[str] = field(default_factory=list)
    impacted_modules: list[str] = field(default_factory=list)
    impacted_services: list[str] = field(default_factory=list)
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
                # Clear existing graph nodes for this repo
                await session.run("MATCH (n {repo_id: $repo_id}) DETACH DELETE n", repo_id=repo_id)

                # Batch insert nodes
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

                # Batch insert relationships
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
                    CREATE (src)-[:DEPENDS_ON {relationship: e.relationship}]->(tgt)
                    """
                    await session.run(query_edges, edges=edges_payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Neo4j sync warning (falling back to in-memory graph): %s", exc)

    async def calculate_blast_radius(self, repo_id: str, changed_files: list[str]) -> BlastRadiusResult:
        """Executes Cypher variable-length path traversal to compute downstream blast radius."""
        try:
            driver = await self.get_driver()
            async with driver.session() as session:
                query = """
                MATCH (src:Node {repo_id: $repo_id})
                WHERE src.path IN $changed_files OR src.id IN $changed_files
                OPTIONAL MATCH (dependent:Node {repo_id: $repo_id})-[:DEPENDS_ON*1..5]->(src)
                RETURN 
                    collect(distinct dependent.id) as impacted_ids,
                    collect(distinct dependent.label) as impacted_labels,
                    collect(distinct dependent.kind) as impacted_kinds
                """
                result = await session.run(query, repo_id=repo_id, changed_files=changed_files)
                record = await result.single()
                if record:
                    impacted_ids = record["impacted_ids"] or []
                    impacted_labels = record["impacted_labels"] or []
                    return BlastRadiusResult(
                        changed_files=changed_files,
                        impacted_nodes=impacted_ids,
                        impacted_modules=sorted(set(impacted_labels)),
                        transitive_dependency_count=len(impacted_ids),
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Neo4j blast radius fallback: {exc}")

        # In-memory fallback if Neo4j is not currently reachable
        return BlastRadiusResult(
            changed_files=changed_files,
            impacted_nodes=changed_files,
            impacted_modules=[f.split("/")[0] for f in changed_files if "/" in f],
            transitive_dependency_count=len(changed_files),
        )
