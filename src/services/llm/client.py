import asyncio

import httpx

from src.config import get_settings


class LLMError(Exception):
    """Raised when the LLM API call fails."""


class LLMClient:
    def __init__(self, max_retries: int = 3, timeout: float = 60.0):
        s = get_settings()
        self.base_url = s.llm_base_url.rstrip("/")
        self.model = s.llm_model
        self.api_key = s.llm_api_key
        self.max_retries = max_retries
        self.timeout = timeout

    async def generate(self, messages: list[dict], temperature: float = 0.2) -> str:
        """Send chat messages, return the assistant's reply text."""
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                if resp.status_code in (429, 500, 502, 503) and attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt * 2)  # 2s, 4s backoff
                    continue
                raise LLMError(f"LLM API {resp.status_code}: {resp.text[:300]}")
        raise LLMError("LLM API failed after retries")