import pytest

from agentic_ai.ingestion import chunk_text


def test_chunking_is_deterministic_and_hashes_content() -> None:
    chunks = chunk_text("First paragraph.\n\nSecond paragraph.", max_characters=40, overlap=5)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.content_hash for chunk in chunks)
    assert chunks == chunk_text("First paragraph.\n\nSecond paragraph.", max_characters=40, overlap=5)


def test_chunking_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("text", max_characters=10, overlap=10)
