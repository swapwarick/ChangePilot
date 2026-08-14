"""Persistent Repository Knowledge Graph & Health Analyzer.

Constructs full repository graph snapshots, detects circular imports, potential orphan candidates,
dependency fan-out metrics, potential test gaps, and architectural policy violations.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field

from app.analysis.tree_sitter_parser import ParsedFileAST, PathNormalizer, is_config_file, is_generated_or_vendor
from app.models.enums import EdgeType, FileClassification
from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode, GraphHealth


@dataclass
class HealthCategoryDetail:
    category: str
    score: int
    evidence: list[str] = field(default_factory=list)
    deductions: int = 0
    recommendations: list[str] = field(default_factory=list)


@dataclass
class RepoHealthMetrics:
    health_score: int = 100  # 0 to 100 integer score
    total_files: int = 0
    total_classes: int = 0
    total_functions: int = 0
    total_dependencies: int = 0
    circular_dependencies: list[list[str]] = field(default_factory=list)
    potential_orphan_candidates: list[str] = field(default_factory=list)
    dead_code_symbols: list[str] = field(default_factory=list)
    god_classes: list[str] = field(default_factory=list)
    high_fan_out_files: list[dict[str, any]] = field(default_factory=list)
    high_fan_in_files: list[dict[str, any]] = field(default_factory=list)
    potential_test_gaps: list[str] = field(default_factory=list)
    architectural_violations: list[dict[str, str]] = field(default_factory=list)
    module_coupling_ratio: float = 0.0
    coverage_notice: str = "Coverage data unavailable; test gap inferred from repository structure."
    categories: dict[str, HealthCategoryDetail] = field(default_factory=dict)

    @property
    def orphan_modules(self) -> list[str]:
        return self.potential_orphan_candidates

    @property
    def test_coverage_gaps(self) -> list[str]:
        return self.potential_test_gaps


def classify_file(file_path: str) -> str:
    norm = file_path.replace("\\", "/").lower()
    filename = norm.split("/")[-1]

    if is_config_file(file_path):
        return FileClassification.CONFIGURATION

    if any(t in norm for t in ("test", "spec", "__tests__")):
        return FileClassification.TEST

    if filename in (
        "main.py", "app.py", "server.py", "index.py", "cli.py", "worker.py",
        "main.ts", "main.tsx", "server.ts", "server.tsx", "index.ts", "index.tsx",
        "app.tsx", "app.ts", "page.tsx", "page.jsx", "layout.tsx", "layout.jsx",
        "route.ts", "route.js", "main.js", "server.js", "index.js"
    ):
        if filename.startswith("page.") or filename.startswith("route.") or filename.startswith("layout."):
            return FileClassification.ROUTE
        return FileClassification.ENTRYPOINT

    if any(norm.startswith(p) or f"/{p}" in norm for p in ("pages/", "app/", "routes/", "controllers/", "api/")):
        return FileClassification.ROUTE

    return FileClassification.SOURCE_MODULE


class KnowledgeGraphBuilder:
    """Constructs persistent knowledge graphs and analyzes architectural repository health."""

    def build_graph_from_parsed_files(self, parsed_files: list[ParsedFileAST]) -> tuple[DependencyGraph, str, RepoHealthMetrics]:
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []
        file_paths = {pf.file_path for pf in parsed_files}

        # Filter vendor/generated files
        valid_parsed_files = [pf for pf in parsed_files if not is_generated_or_vendor(pf.file_path)]

        # 1. Repository Root Node
        repo_node_id = "repo:root"
        nodes[repo_node_id] = DependencyNode(
            id=repo_node_id,
            label="Repository Root",
            kind="repository",
            path=".",
            file_classification=FileClassification.CONFIGURATION,
        )

        # Lookup maps for functions and classes
        func_map: dict[str, str] = {}
        cls_map: dict[str, str] = {}
        for pf in valid_parsed_files:
            for fn in pf.function_symbols:
                func_map.setdefault(fn.name, f"function:{pf.file_path}:{fn.name}")
            for cls in pf.class_symbols:
                cls_map.setdefault(cls.name, f"class:{pf.file_path}:{cls.name}")

        outgoing_degree: dict[str, int] = defaultdict(int)
        incoming_degree: dict[str, int] = defaultdict(int)
        import_adj: dict[str, set[str]] = defaultdict(set)

        self_edge_count = 0
        duplicate_edge_count = 0
        unresolved_imports_count = 0
        seen_edge_triplets = set()

        for pf in valid_parsed_files:
            file_id = f"file:{pf.file_path}"
            parts = pf.file_path.split("/")
            module_name = parts[0] if len(parts) > 1 else "root"
            module_id = f"module:{module_name}"
            folder_path = "/".join(parts[:-1]) if len(parts) > 1 else "."
            folder_id = f"folder:{folder_path}"
            file_cls = classify_file(pf.file_path)

            nodes.setdefault(
                module_id,
                DependencyNode(
                    id=module_id,
                    label=module_name,
                    kind="module",
                    path=module_name,
                    module=module_name,
                    file_classification=FileClassification.CONFIGURATION,
                ),
            )
            if folder_path != ".":
                nodes.setdefault(
                    folder_id,
                    DependencyNode(
                        id=folder_id,
                        label=folder_path.split("/")[-1],
                        kind="folder",
                        path=folder_path,
                        module=module_name,
                        file_classification=FileClassification.CONFIGURATION,
                    ),
                )
                e_id = f"{module_id}->{folder_id}"
                edges.append(
                    DependencyEdge(
                        id=e_id,
                        source=module_id,
                        target=folder_id,
                        relationship="DEPENDS_ON",
                        edge_type=EdgeType.BUILD_DEPENDENCY,
                    )
                )

            is_critical_file = any(kw in pf.file_path.lower() for kw in ("auth", "security", "payment", "db", "session", "alembic"))
            nodes[file_id] = DependencyNode(
                id=file_id,
                label=parts[-1],
                kind="file",
                path=pf.file_path,
                module=module_name,
                language=pf.language,
                file_classification=file_cls,
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
                    edge_type=EdgeType.BUILD_DEPENDENCY,
                )
            )

            # Class Nodes
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
                    file_classification=file_cls,
                    is_critical=is_db,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{cls_id}",
                        source=file_id,
                        target=cls_id,
                        relationship="DEFINES_MODEL" if is_db else "EXPORTS",
                        edge_type=EdgeType.SOURCE_IMPORT,
                    )
                )
                for base in cls.base_classes:
                    target_cls_id = cls_map.get(base, f"base:{base}")
                    if target_cls_id == f"base:{base}":
                        nodes.setdefault(
                            target_cls_id,
                            DependencyNode(
                                id=target_cls_id,
                                label=base,
                                kind="class",
                                path=pf.file_path,
                                module=module_name,
                                file_classification=FileClassification.SOURCE_MODULE,
                            ),
                        )
                    edges.append(
                        DependencyEdge(
                            id=f"{cls_id}->{target_cls_id}",
                            source=cls_id,
                            target=target_cls_id,
                            relationship="INHERITS",
                            edge_type=EdgeType.SOURCE_IMPORT,
                        )
                    )

            # Function Nodes
            for fn in pf.function_symbols:
                fn_id = f"function:{pf.file_path}:{fn.name}"
                nodes[fn_id] = DependencyNode(
                    id=fn_id,
                    label=fn.name,
                    kind="function",
                    path=pf.file_path,
                    module=module_name,
                    language=pf.language,
                    file_classification=file_cls,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{fn_id}",
                        source=file_id,
                        target=fn_id,
                        relationship="EXPORTS",
                        edge_type=EdgeType.SOURCE_IMPORT,
                    )
                )
                for call in fn.calls[:5]:
                    target_fn_id = func_map.get(call, f"call:{call}")
                    if target_fn_id == f"call:{call}":
                        nodes.setdefault(
                            target_fn_id,
                            DependencyNode(
                                id=target_fn_id,
                                label=call,
                                kind="function",
                                path=pf.file_path,
                                module=module_name,
                                file_classification=FileClassification.SOURCE_MODULE,
                            ),
                        )
                    edges.append(
                        DependencyEdge(
                            id=f"{fn_id}->{target_fn_id}",
                            source=fn_id,
                            target=target_fn_id,
                            relationship="CALLS",
                            edge_type=EdgeType.SOURCE_IMPORT,
                        )
                    )

            # API Route Nodes
            for route in pf.api_routes:
                api_id = f"api:{route}"
                nodes[api_id] = DependencyNode(
                    id=api_id,
                    label=route,
                    kind="api",
                    path=pf.file_path,
                    module=module_name,
                    language=pf.language,
                    file_classification=FileClassification.ROUTE,
                    is_critical=True,
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{api_id}",
                        source=file_id,
                        target=api_id,
                        relationship="DEFINES_ROUTE",
                        edge_type=EdgeType.ROUTE_REFERENCE,
                    )
                )

            # Package Dependencies
            for pkg in pf.package_deps:
                pkg_id = f"package:{pkg}"
                nodes.setdefault(
                    pkg_id,
                    DependencyNode(
                        id=pkg_id,
                        label=pkg,
                        kind="package",
                        path="package.json",
                        file_classification=FileClassification.CONFIGURATION,
                    ),
                )
                edges.append(
                    DependencyEdge(
                        id=f"{file_id}->{pkg_id}",
                        source=file_id,
                        target=pkg_id,
                        relationship="IMPORTS",
                        edge_type=EdgeType.PACKAGE_DEPENDENCY,
                    )
                )

            # File IMPORTS with canonical normalization
            for imp in pf.imports:
                target_path = PathNormalizer.resolve_import_path(pf.file_path, imp.source_module, file_paths)
                if target_path:
                    tgt_id = f"file:{target_path}"
                    triplet = (file_id, tgt_id, imp.import_type)
                    if triplet in seen_edge_triplets:
                        duplicate_edge_count += 1
                        continue
                    seen_edge_triplets.add(triplet)

                    if pf.file_path == target_path:
                        self_edge_count += 1
                        edges.append(
                            DependencyEdge(
                                id=f"{file_id}->{tgt_id}",
                                source=file_id,
                                target=tgt_id,
                                relationship="IMPORTS",
                                edge_type=EdgeType.SELF_IMPORT,
                            )
                        )
                    else:
                        e_type = (
                            EdgeType.CONFIG_REFERENCE
                            if is_config_file(target_path) or is_config_file(pf.file_path)
                            else imp.import_type
                        )
                        edges.append(
                            DependencyEdge(
                                id=f"{file_id}->{tgt_id}",
                                source=file_id,
                                target=tgt_id,
                                relationship="IMPORTS",
                                edge_type=e_type,
                            )
                        )
                        if e_type in (EdgeType.SOURCE_IMPORT, EdgeType.DYNAMIC_IMPORT):
                            import_adj[pf.file_path].add(target_path)
                            outgoing_degree[pf.file_path] += 1
                            incoming_degree[target_path] += 1
                else:
                    if not imp.source_module.startswith(".") and not imp.is_relative:
                        # Third-party package import
                        pass
                    else:
                        unresolved_imports_count += 1

        # Calculate Fan-In & Fan-Out based purely on SOURCE_IMPORT / DYNAMIC_IMPORT
        for n in nodes.values():
            if n.kind == "file" and n.path:
                n.fan_out = outgoing_degree[n.path]
                n.fan_in = incoming_degree[n.path]

        # Analyze Repository Health & Quality
        health_metrics = self._analyze_health(
            valid_parsed_files, import_adj, incoming_degree, outgoing_degree, nodes
        )

        graph_health = GraphHealth(
            node_count=len(nodes),
            edge_count=len(edges),
            self_edge_count=self_edge_count,
            duplicate_edge_count=duplicate_edge_count,
            unresolved_imports=unresolved_imports_count,
            circular_dependency_count=len(health_metrics.circular_dependencies),
            orphan_candidates=len(health_metrics.potential_orphan_candidates),
            invalid_paths=0,
            warnings=[
                f"Detected {self_edge_count} self-import statement(s).",
                f"Found {len(health_metrics.circular_dependencies)} circular dependency cycle(s).",
            ] if self_edge_count > 0 or len(health_metrics.circular_dependencies) > 0 else [],
        )

        graph = DependencyGraph(nodes=list(nodes.values()), edges=edges, graph_health=graph_health)
        graph_hash = self._hash_graph(graph)

        return graph, graph_hash, health_metrics

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
        nodes: dict[str, DependencyNode],
    ) -> RepoHealthMetrics:
        health = RepoHealthMetrics(
            total_files=len(parsed_files),
            total_classes=sum(len(pf.defined_classes) for pf in parsed_files),
            total_functions=sum(len(pf.defined_functions) for pf in parsed_files),
            total_dependencies=sum(outgoing_degree.values()),
        )

        # 1. Circular Dependencies (DFS on distinct file source imports)
        visited = set()
        rec_stack = set()
        cycles = []

        def find_cycles(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in import_adj.get(node, []):
                if neighbor == node:
                    continue  # Ignore self loops
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

        # 2. Potential Orphan Candidates (only SOURCE_MODULE with 0 incoming source imports)
        for pf in parsed_files:
            classification = classify_file(pf.file_path)
            if classification == FileClassification.SOURCE_MODULE:
                if incoming_degree[pf.file_path] == 0:
                    health.potential_orphan_candidates.append(pf.file_path)
                    node_id = f"file:{pf.file_path}"
                    if node_id in nodes:
                        nodes[node_id].file_classification = FileClassification.ORPHAN_CANDIDATE
            else:
                node_id = f"file:{pf.file_path}"
                if node_id in nodes:
                    nodes[node_id].file_classification = classification

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

        # 4. God Classes (Classes with >= 8 methods)
        for pf in parsed_files:
            for cls in pf.class_symbols:
                if len(cls.methods) >= 8:
                    health.god_classes.append(f"{pf.file_path}:{cls.name} ({len(cls.methods)} methods)")

        # 5. Dead Code Symbols
        all_imported_names = {imp.imported_name for pf in parsed_files for imp in pf.imports if imp.imported_name != "*"}
        for pf in parsed_files:
            for exp in pf.exports:
                if exp not in all_imported_names and not any(k in exp.lower() for k in ("main", "app", "handler", "route")):
                    health.dead_code_symbols.append(f"{pf.file_path}:{exp}")
        health.dead_code_symbols = health.dead_code_symbols[:15]

        # 6. Potential Test Gaps
        source_files = [
            pf.file_path for pf in parsed_files
            if classify_file(pf.file_path) in (FileClassification.SOURCE_MODULE, FileClassification.ROUTE)
        ]
        test_files = [pf.file_path for pf in parsed_files if classify_file(pf.file_path) == FileClassification.TEST]

        for src in source_files[:25]:
            src_stem = src.split("/")[-1].split(".")[0].lower()
            if not any(src_stem in t.lower() for t in test_files):
                health.potential_test_gaps.append(src)

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

        # 8. 5-Category Health Breakdown Calculation
        arch_score = max(100 - len(health.circular_dependencies) * 8 - len(health.architectural_violations) * 10 - len(health.god_classes) * 4, 10)
        dep_score = max(100 - len(health.high_fan_out_files) * 3 - int(health.module_coupling_ratio * 20), 10)
        test_score = max(100 - len(health.potential_test_gaps) * 4, 10)
        sec_score = max(100 - len(health.architectural_violations) * 12, 10)
        maint_score = max(100 - len(health.potential_orphan_candidates) * 2 - len(health.dead_code_symbols) * 2, 10)

        health.categories = {
            "Architecture": HealthCategoryDetail(
                category="Architecture",
                score=arch_score,
                evidence=[f"{len(health.circular_dependencies)} circular cycles", f"{len(health.architectural_violations)} layering violations"],
                deductions=100 - arch_score,
                recommendations=["Eliminate circular dependencies using dependency inversion.", "Isolate database logic from UI components."]
            ),
            "Dependencies": HealthCategoryDetail(
                category="Dependencies",
                score=dep_score,
                evidence=[f"{len(health.high_fan_out_files)} high fan-out modules"],
                deductions=100 - dep_score,
                recommendations=["Decouple high fan-out modules into sub-modules."]
            ),
            "Testing": HealthCategoryDetail(
                category="Testing",
                score=test_score,
                evidence=[f"{len(health.potential_test_gaps)} potential test gaps", health.coverage_notice],
                deductions=100 - test_score,
                recommendations=["Add unit tests for un-tested source modules."]
            ),
            "Security": HealthCategoryDetail(
                category="Security",
                score=sec_score,
                evidence=[f"{len(health.architectural_violations)} security boundary risks"],
                deductions=100 - sec_score,
                recommendations=["Enforce strict input validation on public API routes."]
            ),
            "Maintainability": HealthCategoryDetail(
                category="Maintainability",
                score=maint_score,
                evidence=[f"{len(health.potential_orphan_candidates)} potential orphan candidates"],
                deductions=100 - maint_score,
                recommendations=["Clean up unreferenced orphan source modules."]
            ),
        }

        overall = int(round(arch_score * 0.25 + dep_score * 0.20 + test_score * 0.20 + sec_score * 0.20 + maint_score * 0.15))
        health.health_score = max(min(overall, 100), 10)
        return health
