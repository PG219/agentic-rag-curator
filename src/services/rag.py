from src.services.llm.client import LLMClient
from src.services.llm.prompts import build_messages
from src.services.search.hybrid import HybridSearchService


class RAGService:
    def __init__(self, hybrid: HybridSearchService, llm: LLMClient) -> None:
        self._hybrid = hybrid
        self._llm = llm

    async def ask(self, question: str, n: int = 5, category: str | None = None) -> dict:
        context = await self._hybrid.retrieve_context(question, category=category, n=n)
        if not context:
            return {"answer": "I could not find any relevant papers.", "sources": []}

        messages =  build_messages(question, context)
        answer = await self._llm.generate(messages)

        sources = [{"arxiv_id": c["arxiv_id"], "title": c["title"]} for c in context]
        return {"answer": answer, "sources": sources}