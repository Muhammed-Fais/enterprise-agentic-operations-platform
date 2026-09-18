from typing import Protocol


class Embedder(Protocol):
    dimensions: int

    async def embed(self, text: str) -> list[float]: ...
