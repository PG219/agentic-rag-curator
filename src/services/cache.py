import hashlib
import json

import redis.asyncio as redis

from src.config import get_settings


def make_cache_key(question: str, n: int, category: str | None) -> str:
    question = " ".join(question.lower().split())
    raw_key = f"q:{question}|n:{n}|c:{category}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"ask:v1:{digest}"


class CacheService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._r = redis.Redis(
            host=self._settings.redis_host,
            port=self._settings.redis_port,
            decode_responses=True,
        )

    async def get(self, key: str) -> dict | None:
        try:
            raw = await self._r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None  # cache down: behave as a miss, never break /ask

    async def set(self, key: str, value: dict) -> None:
        try:
            await self._r.set(
                key, json.dumps(value), ex=self._settings.redis_ttl_seconds
            )
        except Exception:
            pass


cache_service = CacheService()