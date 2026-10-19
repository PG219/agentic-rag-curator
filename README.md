# Agentic RAG Curator

<div align="center">
  <h3>A production-style RAG system over arXiv papers</h3>
  <p>Hybrid search (BM25 + vectors), grounded answers with citations, streaming, provider fallback, and observability, built stage by stage.</p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-async-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenSearch-BM25%20%2B%20kNN-orange.svg" alt="OpenSearch">
  <img src="https://img.shields.io/badge/Docker-Compose-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/Status-Stage%205%20in%20progress-yellow.svg" alt="Status">
</p>

---

## About

Agentic RAG Curator fetches arXiv papers, indexes them for keyword and semantic search, and answers research questions **using only the retrieved papers**, with numbered citations mapped back to real sources. If the papers don't contain the answer, it says so instead of guessing.

This is my own build of the arXiv Paper Curator learning project. I followed its stage-by-stage structure but made my own design choices, listed under [What's different in my version](#whats-different-in-my-version).

> **Design principle:** solid search foundations first (BM25), then add vectors for hybrid retrieval, then the LLM, then observability and agents.

---

## Progress

| Stage | What | Status |
|-------|------|--------|
| 1 | Infrastructure: Docker Compose, FastAPI, PostgreSQL, OpenSearch, Airflow | ✅ Done |
| 2 | Ingestion: fetch and parse arXiv papers into the database | ✅ Done |
| 3 | Hybrid search: BM25 + k-NN fused with Reciprocal Rank Fusion | ✅ Done |
| 4 | RAG generation: grounded prompts, citations, `/ask`, SSE streaming, provider fallback | ✅ Done |
| 5 | Observability and caching: Langfuse tracing, Redis cache | 🚧 In progress |
| 6 | Agentic layer: LangGraph (guardrail, grade, rewrite, generate) | 📅 Planned |
| 7 | Interfaces: Telegram bot and Gradio UI | 📅 Planned |

---

## Architecture

```
                    ┌────────────────────────────────────────┐
  arXiv ─► Airflow ─► Parse ─► PostgreSQL (metadata + text)   │
                    │            │                            │
                    │            ▼ chunk + embed (Jina, 1024-d)
                    │     OpenSearch                          │
                    │     ├─ papers        (BM25)             │
                    │     └─ paper_chunks  (k-NN, HNSW)       │
                    └────────────────────────────────────────┘

  Question ─► FastAPI /ask ─► Hybrid retrieval (BM25 + k-NN → RRF)
                              ─► best chunk per paper + abstract
                              ─► numbered prompt ─► LLM (Gemini → Groq fallback)
                              ─► answer + [n] citations → sources
```

*(Add your own architecture diagram under `static/` and link it here.)*

### Retrieval

1. **BM25** over title, abstract and parsed text (`papers` index).
2. **k-NN** over section chunks (`paper_chunks`, 1024-dim Jina embeddings, cosine similarity).
3. **Reciprocal Rank Fusion** merges both rankings, then results are de-duplicated by paper.
4. For each paper the **best chunk plus the abstract** goes to the LLM, so answers have both overview and detail.

### Generation

- The system prompt allows answers **only** from numbered context blocks.
- The model cites with `[1]`, `[2]`. The server maps those numbers back to papers, so sources are never invented by the model.
- When the context doesn't contain the answer, the model replies exactly *"I could not find this in the retrieved papers."* and `sources` is empty.
- **Streaming** over Server-Sent Events with `token`, `sources` and `error` events.
- **Provider fallback:** an OpenAI-compatible client tries Gemini first and falls back to Groq. It retries with backoff on 429 and 5xx responses.

---

## What's different in my version

- **Hosted LLMs instead of local Ollama**, using Gemini with a Groq fallback, because local model pulls were too slow on my machine.
- **Server-side citation mapping** (`[n]` → paper) with refusal handling, added after a weak fallback model hallucinated an acronym and produced a malformed citation.
- **Richer context:** abstract plus best excerpt per paper, after retrieval returned thin answers from short chunks alone.
- **pip + venv** rather than `uv`.
- **Resumable chunk backfill** script for indexing already-ingested papers.

---

## Quick Start

### Prerequisites

- Docker Desktop (with Docker Compose)
- Python 3.12+
- API keys: a Jina key (embeddings), a Gemini key, optionally a Groq key (fallback)
- 8 GB+ RAM recommended

### Run

```bash
# 1. Clone
git clone https://github.com/PG219/agentic-rag-curator.git
cd agentic-rag-curator

# 2. Configure
cp .env.example .env      # then fill in your keys (see Configuration)

# 3. Start services
docker compose up --build -d

# 4. Check
curl http://localhost:8000/docs
```

> The app code is baked into the Docker image. After changing source, rebuild with `docker compose build app && docker compose up -d app`.

### Local development (optional)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -e .
```

### Services

| Service | URL | Purpose |
|---------|-----|---------|
| API docs | http://localhost:8000/docs | Interactive API |
| Airflow | http://localhost:8080 | Ingestion workflows |
| OpenSearch | http://localhost:9200 | Search engine |

---

## Usage

**Ask a question**

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAFT?"}'
```

Returns the answer and the list of cited papers.

**Stream an answer (SSE)**

```bash
curl -N -X POST http://localhost:8000/api/v1/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAFT?"}'
```

Events: `token` (answer text), `sources` (cited papers), `error`.

The BM25 and hybrid search endpoints are listed in the interactive docs at `/docs`.

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Purpose |
|----------|---------|
| `JINA_API_KEY` | Embeddings for hybrid search |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Primary LLM (Gemini via its OpenAI-compatible endpoint) |
| `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL` | Fallback LLM. Use a capable model such as `llama-3.3-70b-versatile` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Tracing (Stage 5) |

**Never commit `.env`.** Check `git status` before pushing.

---

## Project Structure

```
agentic-rag-curator/
├── src/
│   ├── routers/            # API endpoints (ask, search)
│   ├── services/
│   │   ├── opensearch/     # BM25 and vector search
│   │   ├── search/         # Hybrid search + RRF
│   │   ├── llm/            # LLM client (fallback, streaming) and prompts
│   │   └── rag.py          # RAG orchestration and citation mapping
│   ├── config.py           # Settings from environment
│   └── main.py             # FastAPI app
├── scripts/                # Backfill and utilities
├── airflow/                # Ingestion DAGs
├── Dockerfile
├── compose.yml
└── pyproject.toml
```

---

## Lessons Learned

- **Thin context gives thin answers.** Sending only a chunk missed definitions that live in the abstract.
- **A weak fallback model is worse than none.** It invented an acronym expansion. Fallback models must be strong enough to follow the grounding rules.
- **Never trust model-written citations.** Number the context, let the model cite numbers, and map them to papers on the server.
- **Refusals need handling end to end:** no sources on refusal, and no caching of refusals later.
- **Containers bake code in.** A 404 on a new route usually meant a stale image.

---

## Troubleshooting

- **New endpoint returns 404:** rebuild the app image (`docker compose build app`).
- **500 with connection refused to OpenSearch:** check `docker compose ps` and start the `opensearch` container.
- **Gemini returns 503:** the client retries, then falls back to Groq.
- **Docker build fails during `pip install`:** often a slow network. Raise the pip timeout and retries in the Dockerfile.
- **Services slow to start:** wait a couple of minutes and check `docker compose logs <service>`.

---

## Roadmap

- [ ] Langfuse tracing with provider and model visible per request
- [ ] Redis exact-match cache, then semantic cache
- [ ] LangGraph agent: guardrail, document grading, query rewriting
- [ ] Telegram bot and Gradio chat UI
- [ ] Evaluation set covering short and vague queries

---

## Acknowledgements

Based on the structure of the **arXiv Paper Curator** course by [Jam with AI](https://jamwithai.substack.com) (Shirin Khosravi Jam and Shantanu Ladhwe). This repository is my own implementation with the changes described above.

## License

<<<<<<< HEAD
MIT. See [LICENSE](LICENSE).
=======
MIT. See [LICENSE](LICENSE).
>>>>>>> c8a63f0 (Add Langfuse tracing, pin dependencies)
