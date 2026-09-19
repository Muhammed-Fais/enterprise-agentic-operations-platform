import pytest

from agentic_ai.evaluation import (
    RetrievalCase,
    RetrievalPrediction,
    evaluate_dataset,
    evaluate_retrieval,
)


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


def test_dataset_evaluation_computes_ndcg_and_latency_gate() -> None:
    cases = [
        RetrievalCase("one", "query", frozenset({"a"})),
        RetrievalCase("two", "query", frozenset({"b"})),
    ]
    predictions = {
        "one": RetrievalPrediction("one", ("a", "noise"), latency_ms=10),
        "two": RetrievalPrediction("two", ("b",), latency_ms=30),
    }

    report = evaluate_dataset(
        cases,
        predictions,
        k=2,
        min_recall_at_k=1.0,
        max_p95_latency_ms=30,
    )

    assert report.passed
    assert report.recall_at_k == pytest.approx(1.0)
    assert report.ndcg_at_k == pytest.approx(1.0)
    assert report.p95_latency_ms == pytest.approx(30)


def test_dataset_evaluation_fails_forbidden_retrieval() -> None:
    case = RetrievalCase("one", "query", frozenset({"a"}), frozenset({"secret"}))
    prediction = {"one": RetrievalPrediction("one", ("secret", "a"))}

    report = evaluate_dataset([case], prediction, k=2)

    assert not report.passed
    assert "forbidden_retrieval_rate" in report.failures[0]
