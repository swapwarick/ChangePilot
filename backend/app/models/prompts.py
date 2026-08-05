from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    id: str
    category: str
    version: int = Field(ge=1)
    template: str
    variables: list[str] = Field(default_factory=list)

