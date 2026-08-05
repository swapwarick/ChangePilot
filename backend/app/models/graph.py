from pydantic import BaseModel, Field


class DependencyNode(BaseModel):
    id: str
    label: str
    kind: str
    path: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class DependencyEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str


class DependencyGraph(BaseModel):
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)

