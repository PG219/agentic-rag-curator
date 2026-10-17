import asyncio
import json
from dataclasses import dataclass

import httpx

from src.config import get_settings


class LLMError(Exception):
    """Raised when the LLM API call fails."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class _Provider:
    name: str
    base_url: str
    model: str
    api_key: str


class LLMClient:
    def __init__(self, max_retries: int = 3, timeout: float = 60.0):
        s = get_settings()
        self.providers = []
        if s.llm_api_key:
            self.providers.append(
                _Provider(
                    "Gemini", s.llm_base_url.rstrip("/"), s.llm_model, s.llm_api_key
                )
            )
        if s.groq_api_key:
            self.providers.append(
                _Provider(
                    "Groq", s.groq_base_url.rstrip("/"), s.groq_model, s.groq_api_key
                )
            )
        self.max_retries = max_retries
        self.timeout = timeout

        if not self.providers:
            raise LLMError("No LLM providers are configured")

    async def generate(self, messages: list[dict], temperature: float = 0.2) -> str:
        """Send chat messages, return the assistant's reply text."""
        errors: list[str] = []
        for provider in self.providers:
            try:
                return await self._generate_with_provider(
                    provider, messages, temperature
                )
            except LLMError as exc:
                errors.append(f"{provider.name}: {exc}")
                if not exc.retryable:
                    raise
        

        raise LLMError("All LLM providers failed: " + "; ".join(errors))

    async def _generate_with_provider(
        self, provider: _Provider, messages: list[dict], temperature: float
    ) -> str:
        payload = {
            "model": provider.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        retryable_statuses = {429, 500, 502, 503, 504}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.post(
                        f"{provider.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                except httpx.RequestError as exc:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt * 2)
                        continue
                    raise LLMError(
                        f"{provider.name} request failed: {exc}", retryable=True
                    ) from exc

                if resp.status_code == 200:
                    try:
                        return resp.json()["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError, ValueError) as exc:
                        raise LLMError(
                            f"{provider.name} returned an invalid response"
                        ) from exc

                if resp.status_code in retryable_statuses:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt * 2)
                        continue
                    raise LLMError(
                        f"{provider.name} API {resp.status_code}: {resp.text[:300]}",
                        retryable=True,
                    )

                raise LLMError(
                    f"{provider.name} API {resp.status_code}: {resp.text[:300]}"
                )

        raise LLMError(f"{provider.name} API failed after retries", retryable=True)

    async def stream(self, messages: list[dict], temperature: float = 0.2):
        """Yield the reply text piece by piece (SSE streaming)."""
        errors: list[str] = []
        for provider in self.providers:
            yielded = False
            try:
                async for piece in self._stream_with_provider(
                    provider, messages, temperature
                ):
                    yielded = True
                    yield piece
                return
            except LLMError as exc:
                errors.append(f"{provider.name}: {exc}")
                # Once tokens have reached the client, retrying another model
                # would produce a duplicated or incomplete answer.
                if not exc.retryable or yielded:
                    raise

        raise LLMError("All LLM providers failed: " + "; ".join(errors))

    async def _stream_with_provider(
        self, provider: _Provider, messages: list[dict], temperature: float
    ):
        payload = {
            "model": provider.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {provider.api_key}"}
        retryable_statuses = {429, 500, 502, 503, 504}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    async with client.stream(
                        "POST",
                        f"{provider.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            if resp.status_code in retryable_statuses:
                                if attempt < self.max_retries - 1:
                                    await asyncio.sleep(2**attempt * 2)
                                    continue
                                raise LLMError(
                                    f"{provider.name} API {resp.status_code}: "
                                    f"{body.decode()[:300]}",
                                    retryable=True,
                                )
                            raise LLMError(
                                f"{provider.name} API {resp.status_code}: "
                                f"{body.decode()[:300]}"
                            )

                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data = line.removeprefix("data: ").strip()
                            if data == "[DONE]":
                                return
                            try:
                                choices = json.loads(data).get("choices") or []
                            except json.JSONDecodeError as exc:
                                raise LLMError(
                                    f"{provider.name} returned invalid stream data"
                                ) from exc
                            if choices:
                                piece = choices[0].get("delta", {}).get("content")
                                if piece:
                                    yield piece
                        return
                except httpx.RequestError as exc:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2**attempt * 2)
                        continue
                    raise LLMError(
                        f"{provider.name} stream request failed: {exc}",
                        retryable=True,
                    ) from exc

        raise LLMError(f"{provider.name} stream failed after retries", retryable=True)
