from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AccessContext:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    metadata: dict[str, str]


class Retriever(Protocol):
    async def search(
        self, query: str, access: AccessContext, *, limit: int = 8
    ) -> list[SearchResult]: ...
