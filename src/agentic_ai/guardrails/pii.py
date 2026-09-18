import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MaskingResult:
    text: str
    counts: dict[str, int]


_PATTERNS = {
    "api_key": re.compile(r"\b(?:sk|api|key)[-_][A-Za-z0-9_-]{16,}\b", re.IGNORECASE),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "phone": re.compile(r"(?<!\d)(?:\+?\d[\d .()/-]{7,}\d)(?!\d)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def mask_pii(text: str) -> MaskingResult:
    counts: dict[str, int] = {}
    masked = text
    for kind, pattern in _PATTERNS.items():
        masked, count = pattern.subn(f"[MASKED_{kind.upper()}]", masked)
        if count:
            counts[kind] = count
    return MaskingResult(masked, counts)
