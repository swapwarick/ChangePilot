from pydantic import BaseModel, Field


class GraphHealth(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    self_edge_count: int = 0
    duplicate_edge_count: int = 0
    unresolved_imports: int = 0
    circular_dependency_count: int = 0
    orphan_candidates: int = 0
    invalid_paths: int = 0
    warnings: list[str] = Field(default_factory=list)


class DependencyNode(BaseModel):
    id: str
    label: str
    kind: str  # repository, module, folder, file, class, function, api, database, package
    path: str | None = None
    module: str | None = None
    language: str | None = None
    file_classification: str = "SOURCE_MODULE"
    fan_in: int = 0
    fan_out: int = 0
    blast_radius: int = 0
    is_critical: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


class DependencyEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str  # IMPORTS, EXPORTS, CALLS, DEPENDS_ON, INHERITS, IMPLEMENTS, USES, DEFINES_ROUTE, DEFINES_MODEL
    edge_type: str = "SOURCE_IMPORT"


class DependencyGraph(BaseModel):
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    graph_health: GraphHealth | None = None

