from pydantic import BaseModel

from app.schemas.assistant import AskRequest, CitationOut


class AgentRequest(AskRequest):
    pass


class AgentSection(BaseModel):
    title: str
    text: str


class AgentResponse(BaseModel):
    intent: str
    router: str
    answer: str
    sections: list[AgentSection]
    citations: list[CitationOut]
    steps: list[str]
