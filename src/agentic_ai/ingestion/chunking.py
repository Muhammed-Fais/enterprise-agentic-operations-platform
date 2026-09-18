import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    content_hash: str


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_text(text: str, *, max_characters: int = 1200, overlap: int = 150) -> list[TextChunk]:
    """Create deterministic paragraph-aware chunks for reproducible ingestion.

    This first implementation favors predictable boundaries and testability. A
    token-aware splitter can be added later behind the same function contract.
    """
    if max_characters <= 0 or overlap < 0 or overlap >= max_characters:
        raise ValueError("max_characters must be positive and overlap must be smaller")

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[TextChunk] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current and len(candidate) > max_characters:
            chunks.append(TextChunk(len(chunks), current, _hash(current)))
            prefix = current[-overlap:] if overlap else ""
            current = f"{prefix}\n\n{paragraph}".strip()
        else:
            current = candidate

        while len(current) > max_characters:
            split_at = current.rfind(" ", 0, max_characters + 1)
            split_at = split_at if split_at > 0 else max_characters
            piece = current[:split_at].strip()
            chunks.append(TextChunk(len(chunks), piece, _hash(piece)))
            current = current[max(0, split_at - overlap):].strip()

    if current:
        chunks.append(TextChunk(len(chunks), current, _hash(current)))
    return chunks
