import pytest

from agentic_ai.evaluation import RetrievalCase, evaluate_retrieval


def test_retrieval_metrics_reward_relevant_ranked_results() -> None:
    case = RetrievalCase(
        case_id="case-1",
        query="database latency",
        relevant_chunk_ids=frozenset({"chunk-a", "chunk-b"}),
    )

    metrics = evaluate_retrieval(case, ["chunk-a", "noise", "chunk-b"], k=3)

    assert metrics.recall_at_k == pytest.approx(1.0)
    assert metrics.precision_at_k == pytest.approx(2 / 3)
    assert metrics.mean_reciprocal_rank == pytest.approx(1.0)


def test_forbidden_results_are_measured() -> None:
    case = RetrievalCase(
        case_id="case-2",
        query="policy",
        relevant_chunk_ids=frozenset({"allowed"}),
        forbidden_chunk_ids=frozenset({"secret"}),
    )

    metrics = evaluate_retrieval(case, ["secret", "allowed"], k=2)

    assert metrics.forbidden_retrieval_rate == pytest.approx(0.5)


def test_k_must_be_positive() -> None:
    case = RetrievalCase("case-3", "query", frozenset({"chunk"}))

    with pytest.raises(ValueError):
        evaluate_retrieval(case, ["chunk"], k=0)
