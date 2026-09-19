import argparse
import json
from dataclasses import asdict

from .retrieval import (
    evaluate_dataset,
    load_retrieval_cases,
    load_retrieval_predictions,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the retrieval quality gate")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--min-recall-at-k", type=float, default=0.0)
    parser.add_argument("--max-forbidden-retrieval-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-latency-ms", type=float)
    args = parser.parse_args()

    report = evaluate_dataset(
        load_retrieval_cases(args.cases),
        load_retrieval_predictions(args.predictions),
        k=args.k,
        min_recall_at_k=args.min_recall_at_k,
        max_forbidden_retrieval_rate=args.max_forbidden_retrieval_rate,
        max_p95_latency_ms=args.max_p95_latency_ms,
    )
    with open(args.output, "w", encoding="utf-8") as report_file:
        json.dump(asdict(report), report_file, indent=2)
        report_file.write("\n")
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
