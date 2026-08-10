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
    health_score: float = 100.0  # 0 to 100
    total_files: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_dependencies: int = 0
    circular_dependencies: list[list[str]] = field(default_factory=list)
    orphan_modules: list[str] = field(default_factory=list)
    dead_code_symbols: list[str] = field(default_factory=list)
    god_classes: list[str] = field(default_factory=list)
    high_fan_out_files: list[dict[str, any]] = field(default_factory=list)
    high_fan_in_files: list[dict[str, any]] = field(default_factory=list)
    test_coverage_gaps: list[str] = field(default_factory=list)
    architectural_violations: list[dict[str, str]] = field(default_factory=list)
    module_coupling_ratio: float = 0.0


class KnowledgeGraphBuilder:
    """Constructs persistent knowledge graphs and analyzes architectural repository health."""

    def build_graph_from_parsed_files(self, parsed_files: list[ParsedFileAST]) -> tuple[DependencyGraph, str, RepoHealthMetrics]:
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []
        file_paths = {pf.file_path for pf in parsed_files}

        # 1. Repository Node
        repo_node_id = "repo:root"
        nodes[repo_node_id] = DependencyNode(
            id=repo_node_id,
            label="Repository Root",
            kind="repository",
            path=".",
        )

        # 2. Module, Folder, File, Class, Function, API, DB, Package Nodes
        outgoing_degree: dict[str, int] = defaultdict(int)
        incoming_degree: dict[str, int] = defaultdict(int)
        import_adj: dict[str, set[str]] = defaultdict(set)

        for pf in parsed_files:
            file_id = f"file:{pf.file_path}"
            parts = pf.file_path.split("/")
            module_name = parts[0] if len(parts) > 1 else "root"
            module_id = f"module:{module_name}"
            folder_path = "/".join(parts[:-1]) if len(parts) > 1 else "."
            folder_id = f"folder:{folder_path}"

            # Module Node
            nodes.setdefault(
                module_id,
                DependencyNode(id=module_id, label=module_name, kind="module", path=module_name, module=module_name),
            )
            # Folder Node
            if folder_path != ".":
                nodes.setdefault(
                    folder_id,
                    DependencyNode(id=folder_id, label=folder_path.split("/")[-1], kind="folder", path=folder_path, module=module_name),
                )
                edges.append(
                    DependencyEdge(
                        id=f"{module_id}->{folder_id}",
                        source=module_id,
                        target=folder_id,
                        relationship="DEPENDS_ON",
                    )
                )

            # File Node
            is_critical_file = any(kw in pf.file_path.lower() for kw in ("auth", "security", "payment", "db", "session", "alembic"))
            nodes[file_id] = DependencyNode(
                id=file_id,
                label=parts[-1],
                kind="file",
                path=pf.file_path,
                module=module_name,
                language=pf.language,
                is_critical=is_critical_file,
                metadata={
                    "language": pf.language,
                    "classes": ",".join(pf.defined_classes),
                    "functions": ",".join(pf.defined_functions),
                    "api_routes": ",".join(pf.api_routes),
                },
            )

            parent_container = folder_id if folder_path != "." else module_id
            edges.append(
                DependencyEdge(
                    id=f"{parent_container}->{file_id}",
                    source=parent_container,
                    target=file_id,
                    relationship="DEPENDS_ON",
                )
            )

            # Class Nodes & Base Inheritance (INHERITS / DEFINES_MODEL)
            for cls in pf.class_symbols:
                cls_id = f"class:{pf.file_path}:{cls.name}"
                is_db = cls.is_db_model or any("base" in b.lower() or "model" in b.lower() for b in cls.base_classes)
                cls_kind = "database" if is_db else "class"

                nodes[cls_id] = DependencyNode(
                    id=cls_id,
                    label=cls.name,
                    kind=cls_kind,
                    path=pf.file_path,
                    module=module_name,
                    language=pf.language,
                    is_critical=is_db,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{cls_id}",
                        source=file_id,
                        target=cls_id,
                        relationship="DEFINES_MODEL" if is_db else "EXPORTS",
                    )
                )
                for base in cls.base_classes:
                    edges.append(
                        DependencyEdge(
                            id=f"{cls_id}->base:{base}",
                            source=cls_id,
                            target=f"base:{base}",
                            relationship="INHERITS",
                        )
                    )

            # Function Nodes & CALLS
            for fn in pf.function_symbols:
                fn_id = f"function:{pf.file_path}:{fn.name}"
                nodes[fn_id] = DependencyNode(
                    id=fn_id,
                    label=fn.name,
                    kind="function",
                    path=pf.file_path,
                    module=module_name,
                    language=pf.language,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{fn_id}",
                        source=file_id,
                        target=fn_id,
                        relationship="EXPORTS",
                    )
                )
                for call in fn.calls[:5]:
                    edges.append(
                        DependencyEdge(
                            id=f"{fn_id}->call:{call}",
                            source=fn_id,
                            target=f"call:{call}",
                            relationship="CALLS",
                        )
                    )

            # API Route Nodes (DEFINES_ROUTE)
            for route in pf.api_routes:
                api_id = f"api:{route}"
                nodes[api_id] = DependencyNode(
                    id=api_id,
                    label=route,
                    kind="api",
                    path=pf.file_path,
                    module=module_name,
                    language=pf.language,
                    is_critical=True,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{api_id}",
                        source=file_id,
                        target=api_id,
                        relationship="DEFINES_ROUTE",
                    )
                )

            # Package Dependencies (IMPORTS)
            for pkg in pf.package_deps:
                pkg_id = f"package:{pkg}"
                nodes.setdefault(
                    pkg_id,
                    DependencyNode(id=pkg_id, label=pkg, kind="package", path="package.json"),
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{pkg_id}",
                        source=file_id,
                        target=pkg_id,
                        relationship="IMPORTS",
                    )
                )

            # Resolve File IMPORTS
            for imp in pf.imports:
                target_path = self._resolve_import_target(pf.file_path, imp.source_module, file_paths)
                if target_path:
                    tgt_id = f"file:{target_path}"
                    edges.append(
                        DependencyEdge(
                            id=f"{file_id}->{tgt_id}",
                            source=file_id,
                            target=tgt_id,
                            relationship="IMPORTS",
                        )
                    )
                    import_adj[pf.file_path].add(target_path)
                    outgoing_degree[pf.file_path] += 1
                    incoming_degree[target_path] += 1

        # Populate Node Fan-In / Fan-Out
        for n in nodes.values():
            if n.kind == "file" and n.path:
                n.fan_out = outgoing_degree[n.path]
                n.fan_in = incoming_degree[n.path]

        graph = DependencyGraph(nodes=list(nodes.values()), edges=edges)
        graph_hash = self._hash_graph(graph)
        health_metrics = self._analyze_health(parsed_files, import_adj, incoming_degree, outgoing_degree)

        return graph, graph_hash, health_metrics

    def _resolve_import_target(self, current_file: str, import_src: str, all_files: set[str]) -> str | None:
        """Resolves relative/absolute import paths to actual repository file paths."""
        if not import_src or import_src.startswith("http") or not import_src.startswith("."):
            clean_src = import_src.replace(".", "/").strip("/")
            for file_path in all_files:
                if file_path.startswith(clean_src) or clean_src in file_path:
                    return file_path
            return None

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
        outgoing_degree: dict[str, int],
    ) -> RepoHealthMetrics:
        health = RepoHealthMetrics(
            total_files=len(parsed_files),
            total_classes=sum(len(pf.defined_classes) for pf in parsed_files),
            total_functions=sum(len(pf.defined_functions) for pf in parsed_files),
            total_dependencies=sum(outgoing_degree.values()),
        )

        # 1. Circular Dependencies (Tarjan's DFS)
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

        health.circular_dependencies = cycles[:15]

        # 2. Orphan Modules (No incoming or outgoing non-test imports)
        for pf in parsed_files:
            if not any(t in pf.file_path.lower() for t in ("test", "spec", "config")) and incoming_degree[pf.file_path] == 0 and outgoing_degree[pf.file_path] == 0:
                health.orphan_modules.append(pf.file_path)

        # 3. High Fan-Out & High Fan-In Files
        sorted_fan_out = sorted(parsed_files, key=lambda f: outgoing_degree[f.file_path], reverse=True)
        health.high_fan_out_files = [
            {"path": f.file_path, "count": outgoing_degree[f.file_path]}
            for f in sorted_fan_out[:10]
            if outgoing_degree[f.file_path] > 0
        ]

        sorted_fan_in = sorted(parsed_files, key=lambda f: incoming_degree[f.file_path], reverse=True)
        health.high_fan_in_files = [
            {"path": f.file_path, "count": incoming_degree[f.file_path]}
            for f in sorted_fan_in[:10]
            if incoming_degree[f.file_path] > 0
        ]

        # 4. God Classes (Classes with > 8 methods)
        for pf in parsed_files:
            for cls in pf.class_symbols:
                if len(cls.methods) >= 8:
                    health.god_classes.append(f"{pf.file_path}:{cls.name} ({len(cls.methods)} methods)")

        # 5. Dead Code Candidates (Exported functions/classes never imported anywhere)
        all_imported_names = {imp.imported_name for pf in parsed_files for imp in pf.imports if imp.imported_name != "*"}
        for pf in parsed_files:
            for exp in pf.exports:
                if exp not in all_imported_names and not any(k in exp.lower() for k in ("main", "app", "handler", "route")):
                    health.dead_code_symbols.append(f"{pf.file_path}:{exp}")

        health.dead_code_symbols = health.dead_code_symbols[:15]

        # 6. Test Coverage Gaps
        source_files = [pf.file_path for pf in parsed_files if not any(t in pf.file_path.lower() for t in ("test", "spec", "__pycache__", "config"))]
        test_files = [pf.file_path for pf in parsed_files if any(t in pf.file_path.lower() for t in ("test", "spec"))]

        for src in source_files[:25]:
            src_stem = src.split("/")[-1].split(".")[0].lower()
            if not any(src_stem in t.lower() for t in test_files):
                health.test_coverage_gaps.append(src)

        # 7. Architectural Layering Violations
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

        # Calculate Overall Health Score (100 - penalties)
        score = 100.0
        score -= len(health.circular_dependencies) * 4.0
        score -= len(health.architectural_violations) * 5.0
        score -= min(len(health.test_coverage_gaps) * 1.5, 25.0)
        score -= min(len(health.god_classes) * 3.0, 15.0)
        score -= min(len(health.orphan_modules) * 1.0, 10.0)

        health.health_score = max(round(score, 1), 10.0)
        return health

