

SYSTEM_PROMPT = (
    "You are a research assistant that answers questions about arXiv papers. "
    "Answer ONLY using the provided context. Never use outside knowledge. "
    "Never guess what an acronym or term means. "
    "If the context does not explicitly state the answer, reply only with: "
    "\"I could not find this in the retrieved papers.\" and nothing else. "
    "Cite sources inline using the number of the context block in square brackets, "
    "like [1] or [2]. Be concise. Never use any other citation format. "
)


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    context = "\n\n".join(
        f"[{i}] {c['title']}\n{c['text']}" for i, c in enumerate(chunks, 1)
    )
    user_content = f"Context:\n{context}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]