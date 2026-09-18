import hashlib
import math


class DeterministicEmbedder:
    """Offline embedder for tests and local plumbing validation.

    It is intentionally not a semantic model. Production deployments should
    inject a real embedding provider implementing the same interface.
    """

    def __init__(self, dimensions: int = 32):
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        values = []
        for index in range(self.dimensions):
            digest = hashlib.sha256(f"{index}:{text}".encode()).digest()
            values.append((int.from_bytes(digest[:4], "big") / 2**32) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
