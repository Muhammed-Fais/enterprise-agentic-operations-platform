from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    external_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    content: str = Field(min_length=1)
    allowed_subjects: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentIngestResponse(BaseModel):
    document_id: str
    chunks_created: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class SearchResultResponse(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    metadata: dict[str, str]


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]


class AgentRequest(BaseModel):
    query: str = Field(min_length=1)


class AgentResponse(BaseModel):
    answer: str
    citations: list[str]
    live_status: dict[str, str] | None = None
