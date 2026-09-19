import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


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
    ndcg_at_k: float


@dataclass(frozen=True)
class RetrievalPrediction:
    case_id: str
    retrieved_chunk_ids: tuple[str, ...]
    latency_ms: float = 0.0


@dataclass(frozen=True)
class RetrievalEvaluation:
    cases_evaluated: int
    recall_at_k: float
    precision_at_k: float
    mean_reciprocal_rank: float
    ndcg_at_k: float
    forbidden_retrieval_rate: float
    p95_latency_ms: float
    passed: bool
    failures: tuple[str, ...]


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
    dcg = sum(
        1 / math.log2(index + 2)
        for index, chunk_id in enumerate(top_k)
        if chunk_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1 / math.log2(index + 2) for index in range(ideal_hits))

    return RetrievalMetrics(
        recall_at_k=len(set(hits)) / len(relevant) if relevant else 0.0,
        precision_at_k=len(hits) / len(top_k) if top_k else 0.0,
        mean_reciprocal_rank=1 / first_relevant_rank if first_relevant_rank else 0.0,
        forbidden_retrieval_rate=forbidden_hits / len(top_k) if top_k else 0.0,
        ndcg_at_k=dcg / ideal_dcg if ideal_dcg else 0.0,
    )


def load_retrieval_cases(path: str | Path) -> list[RetrievalCase]:
    cases: list[RetrievalCase] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            cases.append(
                RetrievalCase(
                    case_id=payload["case_id"],
                    query=payload["query"],
                    relevant_chunk_ids=frozenset(payload["relevant_chunk_ids"]),
                    forbidden_chunk_ids=frozenset(payload.get("forbidden_chunk_ids", [])),
                )
            )
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid retrieval case at line {line_number}") from exc
    return cases


def load_retrieval_predictions(path: str | Path) -> dict[str, RetrievalPrediction]:
    predictions: dict[str, RetrievalPrediction] = {}
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            prediction = RetrievalPrediction(
                case_id=payload["case_id"],
                retrieved_chunk_ids=tuple(payload["retrieved_chunk_ids"]),
                latency_ms=float(payload.get("latency_ms", 0.0)),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid retrieval prediction at line {line_number}") from exc
        if prediction.case_id in predictions:
            raise ValueError(f"duplicate prediction for case {prediction.case_id}")
        predictions[prediction.case_id] = prediction
    return predictions


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def evaluate_dataset(
    cases: Iterable[RetrievalCase],
    predictions: dict[str, RetrievalPrediction],
    *,
    k: int = 5,
    min_recall_at_k: float = 0.0,
    max_forbidden_retrieval_rate: float = 0.0,
    max_p95_latency_ms: float | None = None,
) -> RetrievalEvaluation:
    case_list = list(cases)
    if not case_list:
        raise ValueError("evaluation dataset must not be empty")

    metrics: list[RetrievalMetrics] = []
    latencies: list[float] = []
    missing = []
    for case in case_list:
        prediction = predictions.get(case.case_id)
        if prediction is None:
            missing.append(case.case_id)
            continue
        metrics.append(evaluate_retrieval(case, list(prediction.retrieved_chunk_ids), k=k))
        latencies.append(prediction.latency_ms)

    if missing:
        raise ValueError(f"missing predictions for cases: {', '.join(sorted(missing))}")

    count = len(metrics)
    summary = RetrievalEvaluation(
        cases_evaluated=count,
        recall_at_k=sum(item.recall_at_k for item in metrics) / count,
        precision_at_k=sum(item.precision_at_k for item in metrics) / count,
        mean_reciprocal_rank=sum(item.mean_reciprocal_rank for item in metrics) / count,
        ndcg_at_k=sum(item.ndcg_at_k for item in metrics) / count,
        forbidden_retrieval_rate=sum(item.forbidden_retrieval_rate for item in metrics) / count,
        p95_latency_ms=_p95(latencies),
        passed=True,
        failures=(),
    )
    failures: list[str] = []
    if summary.recall_at_k < min_recall_at_k:
        failures.append(f"recall_at_k {summary.recall_at_k:.4f} < {min_recall_at_k:.4f}")
    if summary.forbidden_retrieval_rate > max_forbidden_retrieval_rate:
        failures.append(
            "forbidden_retrieval_rate "
            f"{summary.forbidden_retrieval_rate:.4f} > {max_forbidden_retrieval_rate:.4f}"
        )
    if max_p95_latency_ms is not None and summary.p95_latency_ms > max_p95_latency_ms:
        failures.append(f"p95_latency_ms {summary.p95_latency_ms:.2f} > {max_p95_latency_ms:.2f}")
    return RetrievalEvaluation(
        **{**summary.__dict__, "passed": not failures, "failures": tuple(failures)}
    )
