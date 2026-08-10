from pydantic import BaseModel, Field


class DependencyNode(BaseModel):
    id: str
    label: str
    kind: str  # repository, module, folder, file, class, function, api, database, package
    path: str | None = None
    module: str | None = None
    language: str | None = None
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


class DependencyGraph(BaseModel):
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)

