import httpx

from src.config import Settings, get_settings

JINA_API_URL = "https://api.jina.ai/v1/embeddings"

import asyncio


class JinaEmbeddingsClient:
    """Client for generating text embeddings via Jina AI's embeddings API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    import asyncio

    async def embed_texts(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
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

        max_retries = 5
        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(JINA_API_URL, headers=headers, json=payload)

            if response.status_code == 429:
                wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                print(f"Rate limited, waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

        raise RuntimeError(f"Jina API rate limit exceeded after {max_retries} retries")