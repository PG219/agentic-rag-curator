

SYSTEM_PROMPT = (
    "You are a research assistant that answers questions about arXiv papers. "
    "Answer ONLY using the provided context. "
    "If the context does not contain the answer, say you could not find it in the retrieved papers. "
    "Cite sources inline using the paper id in square brackets, like [2609.1]. "
    "Be concise."
    )


def build_messages(question: str, chunks: list[dict]) -> list[dict]:
    context = "\n\n".join(
        f"[{c['arxiv_id']}] {c['title']}\n{c['text']}" for c in chunks
    )
    user_content = f"Context:\n{context}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]