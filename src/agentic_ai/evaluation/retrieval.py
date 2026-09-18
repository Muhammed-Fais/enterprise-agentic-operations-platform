from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalCase:
    case_id: str
    query: str
    relevant_chunk_ids: frozenset[str]
    forbidden_chunk_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    precision_at_k: float
    mean_reciprocal_rank: float
    forbidden_retrieval_rate: float


def evaluate_retrieval(
    case: RetrievalCase, retrieved_chunk_ids: list[str], *, k: int = 5
) -> RetrievalMetrics:
    if k <= 0:
        raise ValueError("k must be positive")

    top_k = retrieved_chunk_ids[:k]
    relevant = case.relevant_chunk_ids
    hits = [chunk_id for chunk_id in top_k if chunk_id in relevant]
    first_relevant_rank = next(
        (index + 1 for index, chunk_id in enumerate(top_k) if chunk_id in relevant), None
    )
    forbidden_hits = sum(chunk_id in case.forbidden_chunk_ids for chunk_id in top_k)

    return RetrievalMetrics(
        recall_at_k=len(set(hits)) / len(relevant) if relevant else 0.0,
        precision_at_k=len(hits) / len(top_k) if top_k else 0.0,
        mean_reciprocal_rank=1 / first_relevant_rank if first_relevant_rank else 0.0,
        forbidden_retrieval_rate=forbidden_hits / len(top_k) if top_k else 0.0,
    )
