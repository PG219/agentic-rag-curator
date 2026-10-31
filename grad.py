import gradio as gr
import httpx

API_URL = "http://localhost:8001/api/v1/ask"


def ask(question: str) -> tuple[str, str]:
    if not question.strip():
        return "", ""
    try:
        r = httpx.post(API_URL, params={"q": question}, timeout=120)
        r.raise_for_status()
    except Exception as e:
        return f"Request failed: {e}", ""
    data = r.json()
    sources = "\n".join(
        f"- [{s['title']}](https://arxiv.org/abs/{s['arxiv_id']})"
        for s in data.get("sources", [])
    )
    return data["answer"], sources or "_No sources: the papers don't cover this._"


with gr.Blocks(title="Agentic RAG Curator") as demo:
    gr.Markdown("# Agentic RAG Curator\nAsk questions about arXiv ML papers. Answers cite their sources.")
    q = gr.Textbox(label="Question", placeholder="What is RAFT?")
    btn = gr.Button("Ask", variant="primary")
    answer = gr.Markdown(label="Answer")
    gr.Markdown("### Sources")
    sources = gr.Markdown()
    btn.click(ask, q, [answer, sources])
    q.submit(ask, q, [answer, sources])

demo.launch(server_port=7861)