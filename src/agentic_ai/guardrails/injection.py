import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionAssessment:
    detected: bool
    matched_rules: tuple[str, ...]


_RULES = {
    "instruction_override": re.compile(
        r"\b(?:ignore|disregard|override)\b.{0,40}\b(?:previous|prior|system|all)\b.{0,30}\b(?:instructions?|rules?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "prompt_extraction": re.compile(
        r"\b(?:reveal|show|print|repeat| disclose)\b.{0,40}\b(?:system prompt|hidden prompt|secret instructions?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "guardrail_bypass": re.compile(
        r"\b(?:bypass|disable|evade)\b.{0,30}\b(?:guardrails?|safety|policy|approval)\b",
        re.IGNORECASE | re.DOTALL,
    ),
}


def detect_prompt_injection(text: str) -> InjectionAssessment:
    matched = tuple(rule_name for rule_name, pattern in _RULES.items() if pattern.search(text))
    return InjectionAssessment(detected=bool(matched), matched_rules=matched)
