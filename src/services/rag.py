import re

from src.services.llm.client import LLMClient
from src.services.llm.prompts import build_messages
from src.services.search.hybrid import HybridSearchService


def cited_sources(answer: str, context: list[dict]) -> list[dict]:
    """Map [1], [2] style citations in the answer back to papers."""
    nums = {
        int(n)
        for group in re.findall(r"\[([\d,\s]+)\]", answer)
        for n in re.findall(r"\d+", group)
    }
    all_sources = [{"arxiv_id": c["arxiv_id"], "title": c["title"]} for c in context]
    cited = [s for i, s in enumerate(all_sources, 1) if i in nums]
    return cited or all_sources


class RAGService:
    def __init__(self, hybrid: HybridSearchService, llm: LLMClient) -> None:
        self._hybrid = hybrid
        self._llm = llm

    async def ask(self, question: str, n: int = 5, category: str | None = None) -> dict:
        context = await self._hybrid.retrieve_context(question, category=category, n=n)
        if not context:
            return {"answer": "I could not find any relevant papers.", "sources": []}

        messages = build_messages(question, context)
        answer = await self._llm.generate(messages)
        return {"answer": answer, "sources": cited_sources(answer, context)}

    async def ask_stream(self, question: str, n: int = 5, category: str | None = None):
        context = await self._hybrid.retrieve_context(question, category=category, n=n)
        if not context:
            yield {"type": "token", "text": "I could not find any relevant papers."}
            yield {"type": "sources", "sources": []}
            return

        messages = build_messages(question, context)
        answer = ""
        async for piece in self._llm.stream(messages):
            answer += piece
            yield {"type": "token", "text": piece}

        yield {"type": "sources", "sources": cited_sources(answer, context)}