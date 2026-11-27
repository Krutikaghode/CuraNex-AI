from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=1000)


class CitationOut(BaseModel):
    number: int
    report_id: int
    filename: str
    page: int | None
    excerpt: str
    score: float


class AskResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    provider: str
    chat_model: str
    embed_model: str
    reports_searched: int


class AssistantStatus(BaseModel):
    provider: str
    chat_model: str
    embed_model: str
    reachable: bool
    missing_models: list[str]


class IndexResponse(BaseModel):
    reports_indexed: int
