from pydantic import BaseModel, HttpUrl


class RepositoryCreate(BaseModel):
    name: str
    source: str
    url: HttpUrl | None = None


class RepositorySummary(BaseModel):
    id: str
    name: str
    source: str
    default_branch: str = "main"
    language: str | None = None

