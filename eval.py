"""
Stage 3 / RAG1-18: 15-query evaluation comparing BM25, vector, and hybrid search.

Run from the repo root:
    python eval_hybrid_search.py
"""
import asyncio

from src.config import get_settings
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.opensearch.client import get_opensearch_client
from src.services.opensearch.search import SearchService
from src.services.search.hybrid import HybridSearchService, dedupe_ids

# Each query has one or more "relevant" arxiv_ids, drawn from the real 125-paper set.
# Queries deliberately mix exact-title phrasing (favors BM25) and paraphrased/semantic
# phrasing (favors vector search), to see where each method actually wins.
EVAL_QUERIES = [
    {"query": "safe robot manipulation with coding agents", "relevant": ["2609.20822v1"]},
    {"query": "harness design for coding agents", "relevant": ["2609.20804v1", "2609.20519v1", "2609.20474v1", "2609.20050v1"]},
    {"query": "compressing the KV cache in large language models", "relevant": ["2609.19969v1", "2609.19880v1", "2609.20068v1"]},
    {"query": "speculative decoding control", "relevant": ["2609.20186v1"]},
    {"query": "reranking documents using LLM reasoning", "relevant": ["2609.20131v1"]},
    {"query": "diffusion-based language models", "relevant": ["2609.20751v1", "2609.19868v1", "2609.20539v1"]},
    {"query": "federated learning across distributed data sources", "relevant": ["2609.20359v1", "2609.20650v1", "2609.20501v1"]},
    {"query": "recognizing emotion from speech", "relevant": ["2609.20081v1"]},
    {"query": "noise robust quantum state measurement", "relevant": ["2609.20523v1"]},
    {"query": "reinforcement learning for self-driving cars", "relevant": ["2609.20747v1", "2609.20756v1"]},
    {"query": "translating legal rules into formal logic", "relevant": ["2609.20334v1"]},
    {"query": "gender bias in GPT model outputs", "relevant": ["2609.20779v1"]},
    {"query": "routing for low earth orbit satellite networks", "relevant": ["2609.20347v1"]},
    {"query": "evaluation benchmark for Korean language understanding", "relevant": ["2609.19916v1"]},
    {"query": "fingerprinting attacks against ML models", "relevant": ["2609.20614v1", "2609.20457v1"]},
]


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    hits = len(top_k & relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


async def run_eval():
    settings = get_settings()
    client = get_opensearch_client()
    search_service = SearchService(
        client, settings.opensearch_papers_index, settings.opensearch_chunks_index
    )
    embeddings_client = JinaEmbeddingsClient()
    hybrid_service = HybridSearchService(search_service, embeddings_client, client)

    methods = {"bm25": [], "vector": [], "hybrid": []}

    for case in EVAL_QUERIES:
        query = case["query"]
        relevant = set(case["relevant"])

        bm25_results = search_service.search(query, size=10)
        bm25_ids = dedupe_ids(bm25_results)

        query_embedding = (
            await embeddings_client.embed_texts([query], task="retrieval.query")
        )[0]
        vector_results = search_service.vector_search(query_embedding, size=20)
        vector_ids = dedupe_ids(vector_results)

        hybrid_results = await hybrid_service.search(query, size=10, candidates=20)
        hybrid_ids = [r["arxiv_id"] for r in hybrid_results]

        for name, ids in [("bm25", bm25_ids), ("vector", vector_ids), ("hybrid", hybrid_ids)]:
            methods[name].append(
                {
                    "query": query,
                    "p@5": precision_at_k(ids, relevant, 5),
                    "r@10": recall_at_k(ids, relevant, 10),
                    "rr": reciprocal_rank(ids, relevant),
                }
            )

    print(f"\n{'Query':<55} {'BM25 P@5':>9} {'Vec P@5':>9} {'Hyb P@5':>9}")
    print("-" * 85)
    for i, case in enumerate(EVAL_QUERIES):
        q = case["query"][:52] + "..." if len(case["query"]) > 52 else case["query"]
        print(
            f"{q:<55} {methods['bm25'][i]['p@5']:>9.2f} "
            f"{methods['vector'][i]['p@5']:>9.2f} {methods['hybrid'][i]['p@5']:>9.2f}"
        )

    print("\n=== Aggregate metrics (mean across 15 queries) ===")
    print(f"{'Method':<10} {'P@5':>8} {'R@10':>8} {'MRR':>8}")
    for name in ("bm25", "vector", "hybrid"):
        rows = methods[name]
        n = len(rows)
        mean_p5 = sum(r["p@5"] for r in rows) / n
        mean_r10 = sum(r["r@10"] for r in rows) / n
        mean_mrr = sum(r["rr"] for r in rows) / n
        print(f"{name:<10} {mean_p5:>8.3f} {mean_r10:>8.3f} {mean_mrr:>8.3f}")


if __name__ == "__main__":
    asyncio.run(run_eval())