import argparse
import json
from dataclasses import asdict

from .security import evaluate_security_dataset, load_security_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic security evaluations")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = evaluate_security_dataset(load_security_cases(args.cases))
    with open(args.output, "w", encoding="utf-8") as report_file:
        json.dump(asdict(report), report_file, indent=2)
        report_file.write("\n")
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
