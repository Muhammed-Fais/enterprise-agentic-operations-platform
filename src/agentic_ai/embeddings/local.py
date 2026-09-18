import asyncio

from sentence_transformers import SentenceTransformer


class LocalSentenceTransformerEmbedder:
    """Free local semantic embedder backed by Sentence Transformers."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self.dimensions = int(self._model.get_embedding_dimension())

    async def embed(self, text: str) -> list[float]:
        vector = await asyncio.to_thread(
            self._model.encode,
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return vector.tolist()
