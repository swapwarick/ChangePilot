from pydantic import BaseModel, HttpUrl


class RepositoryCreate(BaseModel):
    name: str
    source: str
    url: HttpUrl | None = None


class RepositorySummary(BaseModel):
    id: str
    name: str
    owner: str = ""
    full_name: str = ""
    source: str
    url: str | None = None
    default_branch: str = "main"
    language: str | None = None

