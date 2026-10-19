import re

from langfuse import get_client

from src.services.llm.client import LLMClient
from src.services.llm.prompts import build_messages
from src.services.search.hybrid import HybridSearchService


def cited_sources(answer: str, context: list[dict]) -> list[dict]:
    """Map [1], [2] style citations in the answer back to papers."""
    if answer.strip().startswith("I could not find"):
        return []
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
        langfuse = get_client()
        with langfuse.start_as_current_observation(
            as_type="span",
            name="rag-ask",
            input={"question": question, "n": n, "category": category},
        ) as root:
            with langfuse.start_as_current_observation(
                as_type="span", name="retrieve"
            ) as step:
                context = await self._hybrid.retrieve_context(
                    question, category=category, n=n
                )
                step.update(
                    output=[
                        {"arxiv_id": c["arxiv_id"], "title": c["title"],
                         "rrf_score": c["rrf_score"]}
                        for c in context
                    ]
                )

            if not context:
                result = {"answer": "I could not find any relevant papers.", "sources": []}
                root.update(output=result)
                return result

            messages = build_messages(question, context)
            with langfuse.start_as_current_observation(
                as_type="generation",
                name="llm-answer",
                model=self._llm.providers[0].model,
                input=messages,
            ) as gen:
                answer = await self._llm.generate(messages)
                used = self._llm.last_provider
                gen.update(
                    output=answer,
                    metadata={
                        "provider": used.name if used else None,
                        "model": used.model if used else None,
                    },
                )

            result = {"answer": answer, "sources": cited_sources(answer, context)}
            root.update(output=result)
            return result

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