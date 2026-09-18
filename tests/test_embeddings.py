import pytest

from agentic_ai.embeddings import DeterministicEmbedder


@pytest.mark.asyncio
async def test_deterministic_embedder_is_repeatable_and_normalized() -> None:
    embedder = DeterministicEmbedder(dimensions=8)
    first = await embedder.embed("incident status")
    second = await embedder.embed("incident status")

    assert first == second
    assert len(first) == 8
    assert sum(value * value for value in first) == pytest.approx(1.0)
