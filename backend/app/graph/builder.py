from pathlib import PurePosixPath

from app.models.graph import DependencyEdge, DependencyGraph, DependencyNode


class DependencyGraphBuilder:
    def from_changed_files(self, changed_files: list[str]) -> DependencyGraph:
        nodes: dict[str, DependencyNode] = {}
        edges: list[DependencyEdge] = []

        for file_path in changed_files:
            normalized = file_path.replace("\\", "/")
            path = PurePosixPath(normalized)
            module_name = path.parts[0] if path.parts else "root"
            module_id = f"module:{module_name}"
            file_id = f"file:{normalized}"
            nodes.setdefault(
                module_id,
                DependencyNode(id=module_id, label=module_name, kind="module", path=module_name),
            )
            nodes[file_id] = DependencyNode(
                id=file_id,
                label=path.name,
                kind="file",
                path=normalized,
            )
            edges.append(
                DependencyEdge(
                    id=f"{module_id}->{file_id}",
                    source=module_id,
                    target=file_id,
                    relationship="owns",
                )
            )

        return DependencyGraph(nodes=list(nodes.values()), edges=edges)

