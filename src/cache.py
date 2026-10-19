import hashlib
def make_cache_key(question: str, n: int, category: str | None) -> str:
    