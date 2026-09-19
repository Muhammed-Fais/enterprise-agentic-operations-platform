import json
from dataclasses import dataclass
from pathlib import Path

from agentic_ai.auth import AuthContext
from agentic_ai.guardrails import detect_prompt_injection, mask_pii
from agentic_ai.mcp import ApprovalRequired, ToolAuthorization, ToolCapability, ToolPolicy


@dataclass(frozen=True)
class SecurityCase:
    case_id: str
    category: str
    payload: dict[str, object]


@dataclass(frozen=True)
class SecurityEvaluation:
    cases_evaluated: int
    passed_cases: int
    failed_cases: int
    by_category: dict[str, int]
    passed: bool
    failures: tuple[str, ...]


def load_security_cases(path: str | Path) -> list[SecurityCase]:
    cases: list[SecurityCase] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            cases.append(
                SecurityCase(
                    case_id=payload["case_id"],
                    category=payload["category"],
                    payload=payload,
                )
            )
        except (KeyError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid security case at line {line_number}") from exc
    return cases


def _evaluate_case(case: SecurityCase) -> tuple[bool, str]:
    payload = case.payload
    if case.category == "pii":
        result = mask_pii(str(payload["input"]))
        leaked = [value for value in payload.get("must_not_contain", []) if value in result.text]
        markers = [value for value in payload.get("expected_markers", []) if value not in result.text]
        if leaked or markers:
            return False, f"PII masking failed: leaked={leaked}, missing_markers={markers}"
        return True, ""

    if case.category == "prompt_injection":
        actual = detect_prompt_injection(str(payload["input"])).detected
        expected = bool(payload["expected_detected"])
        return actual == expected, f"expected detected={expected}, got {actual}"

    if case.category == "acl":
        retrieved = set(payload.get("retrieved_chunk_ids", []))
        forbidden = set(payload.get("forbidden_chunk_ids", []))
        leaked = sorted(retrieved & forbidden)
        return not leaked, f"forbidden chunks returned: {leaked}"

    if case.category == "tool_authorization":
        capability = ToolCapability(str(payload["capability"]))
        authorization = ToolAuthorization(
            [
                ToolPolicy(
                    str(payload["tool_name"]),
                    capability,
                    frozenset(payload.get("allowed_roles", [])),
                )
            ]
        )
        context = AuthContext("tenant-a", "security-eval", tuple(payload.get("roles", [])))
        try:
            authorization.authorize(context, str(payload["tool_name"]), {})
            actual = "allowed"
        except ApprovalRequired:
            actual = "approval_required"
        except PermissionError:
            actual = "denied"
        expected = str(payload["expected_outcome"])
        return actual == expected, f"expected outcome={expected}, got {actual}"

    raise ValueError(f"unsupported security case category: {case.category}")


def evaluate_security_dataset(cases: list[SecurityCase]) -> SecurityEvaluation:
    if not cases:
        raise ValueError("security dataset must not be empty")
    failures: list[str] = []
    by_category: dict[str, int] = {}
    passed_cases = 0
    for case in cases:
        by_category[case.category] = by_category.get(case.category, 0) + 1
        passed, reason = _evaluate_case(case)
        if passed:
            passed_cases += 1
        else:
            failures.append(f"{case.case_id}: {reason}")
    return SecurityEvaluation(
        cases_evaluated=len(cases),
        passed_cases=passed_cases,
        failed_cases=len(cases) - passed_cases,
        by_category=by_category,
        passed=not failures,
        failures=tuple(failures),
    )
