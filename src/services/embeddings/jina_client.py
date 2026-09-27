import httpx

from src.config import Settings, get_settings

JINA_API_URL = "https://api.jina.ai/v1/embeddings"


class JinaEmbeddingsClient:
    """Client for generating text embeddings via Jina AI's embeddings API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def embed_texts(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        task: "retrieval.passage" for documents being indexed,
              "retrieval.query" for search queries.
        """
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self._settings.jina_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.jina_embedding_model,
            "task": task,
            "dimensions": self._settings.jina_embedding_dimensions,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(JINA_API_URL, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        return [item["embedding"] for item in data["data"]]