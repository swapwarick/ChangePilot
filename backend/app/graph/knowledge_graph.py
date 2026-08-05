"""Persistent Repository Knowledge Graph & Health Analyzer.

Constructs full repository graph snapshots, detects circular imports, orphan modules,
dependency fan-out metrics, test coverage gaps, and architectural policy violations.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field

from app.analysis.tree_sitter_parser import ParsedFileAST
from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode


@dataclass
class RepoHealthMetrics:
    total_files: int = 0
    total_dependencies: int = 0
    circular_dependencies: list[list[str]] = field(default_factory=list)
    orphan_modules: list[str] = field(default_factory=list)
    max_fan_out: dict[str, int] = field(default_factory=dict)
    test_coverage_gaps: list[str] = field(default_factory=list)
    architectural_violations: list[dict[str, str]] = field(default_factory=list)


class KnowledgeGraphBuilder:
    """Constructs persistent knowledge graphs and analyzes architectural repository health."""

    def build_graph_from_parsed_files(self, parsed_files: list[ParsedFileAST]) -> tuple[DependencyGraph, str, RepoHealthMetrics]:
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []
        file_paths = {pf.file_path for pf in parsed_files}

        # Create File & Module Nodes
        for pf in parsed_files:
            file_id = f"file:{pf.file_path}"
            module_name = pf.file_path.split("/")[0] if "/" in pf.file_path else "root"
            module_id = f"module:{module_name}"

            nodes.setdefault(
                module_id,
                DependencyNode(id=module_id, label=module_name, kind="module", path=module_name),
            )
            nodes[file_id] = DependencyNode(
                id=file_id,
                label=pf.file_path.split("/")[-1],
                kind="file",
                path=pf.file_path,
                metadata={
                    "language": pf.language,
                    "classes": ",".join(pf.defined_classes),
                    "functions": ",".join(pf.defined_functions),
                    "api_routes": ",".join(pf.api_routes),
                },
            )
            edges.append(
                DependencyEdge(
                    id=f"{module_id}->{file_id}",
                    source=module_id,
                    target=file_id,
                    relationship="owns",
                )
            )

        # Create Dependency Edges from AST Imports
        import_adj: dict[str, set[str]] = defaultdict(set)
        incoming_degree: dict[str, int] = defaultdict(int)

        for pf in parsed_files:
            src_id = f"file:{pf.file_path}"
            for imp in pf.imports:
                # Resolve import target to file path if possible
                target_path = self._resolve_import_target(pf.file_path, imp.source_module, file_paths)
                if target_path:
                    tgt_id = f"file:{target_path}"
                    edges.append(
                        DependencyEdge(
                            id=f"{src_id}->{tgt_id}",
                            source=src_id,
                            target=tgt_id,
                            relationship="imports",
                        )
                    )
                    import_adj[pf.file_path].add(target_path)
                    incoming_degree[target_path] += 1

        graph = DependencyGraph(nodes=list(nodes.values()), edges=edges)
        graph_hash = self._hash_graph(graph)
        health_metrics = self._analyze_health(parsed_files, import_adj, incoming_degree)

        return graph, graph_hash, health_metrics

    def _resolve_import_target(self, current_file: str, import_src: str, all_files: set[str]) -> str | None:
        """Resolves relative/absolute import paths to actual repository file paths."""
        if not import_src or import_src.startswith("http") or not import_src.startswith("."):
            # Try fuzzy match against known files
            clean_src = import_src.replace(".", "/").strip("/")
            for file_path in all_files:
                if file_path.startswith(clean_src) or clean_src in file_path:
                    return file_path
            return None

        # Resolve relative import
        current_dir = "/".join(current_file.split("/")[:-1])
        normalized = f"{current_dir}/{import_src}".replace("//", "/")
        parts = []
        for p in normalized.split("/"):
            if p == "..":
                if parts:
                    parts.pop()
            elif p != ".":
                parts.append(p)
        candidate_base = "/".join(parts)

        for ext in ("", ".ts", ".tsx", ".js", ".jsx", ".py", "/index.ts", "/index.js"):
            candidate = f"{candidate_base}{ext}"
            if candidate in all_files:
                return candidate
        return None

    def _hash_graph(self, graph: DependencyGraph) -> str:
        serialized = json.dumps(
            {
                "nodes": sorted([n.id for n in graph.nodes]),
                "edges": sorted([e.id for e in graph.edges]),
            },
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _analyze_health(
        self,
        parsed_files: list[ParsedFileAST],
        import_adj: dict[str, set[str]],
        incoming_degree: dict[str, int],
    ) -> RepoHealthMetrics:
        health = RepoHealthMetrics(total_files=len(parsed_files))

        # 1. Circular Dependencies Detection (Tarjan's / DFS cycle finding)
        visited = set()
        rec_stack = set()
        cycles = []

        def find_cycles(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in import_adj.get(node, []):
                if neighbor not in visited:
                    find_cycles(neighbor, path)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.remove(node)

        for pf in parsed_files:
            if pf.file_path not in visited:
                find_cycles(pf.file_path, [])

        health.circular_dependencies = cycles[:10]  # Cap at top 10

        # 2. Orphan Modules (No incoming or outgoing non-test imports)
        for pf in parsed_files:
            if not pf.file_path.startswith("test") and "spec" not in pf.file_path and incoming_degree[pf.file_path] == 0 and len(import_adj.get(pf.file_path, [])) == 0:
                health.orphan_modules.append(pf.file_path)

        # 3. Test Coverage Gaps
        source_files = [pf.file_path for pf in parsed_files if not ("test" in pf.file_path.lower() or "spec" in pf.file_path.lower())]
        test_files = [pf.file_path for pf in parsed_files if "test" in pf.file_path.lower() or "spec" in pf.file_path.lower()]
        
        for src in source_files[:20]:
            src_stem = src.split("/")[-1].split(".")[0].lower()
            if not any(src_stem in t.lower() for t in test_files):
                health.test_coverage_gaps.append(src)

        # 4. Architectural Layering Violations
        # e.g., UI/Frontend files importing Database/Session files directly
        for pf in parsed_files:
            if any(layer in pf.file_path.lower() for layer in ("components", "ui", "pages", "frontend")):
                for target in import_adj.get(pf.file_path, []):
                    if any(db_marker in target.lower() for db_marker in ("database", "session", "alembic", "prisma")):
                        health.architectural_violations.append(
                            {
                                "rule": "UI layer directly importing Database layer",
                                "source": pf.file_path,
                                "target": target,
                            }
                        )

        return health
