from concurrent.futures import ThreadPoolExecutor

from opensearchpy import OpenSearch

from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.opensearch.search import SearchService
from src.services.search.rrf import reciprocal_rank_fusion


def dedupe_ids(results: list[dict]) -> list[str]:
    """Extract arxiv_ids from results, keeping only the first (best-ranked) occurrence."""
    seen = set()
    ids = []
    for item in results:
        aid = item["arxiv_id"]
        if aid not in seen:
            seen.add(aid)
            ids.append(aid)
    return ids


class HybridSearchService:
    """Combines BM25 and vector search results using Reciprocal Rank Fusion."""

    def __init__(
        self,
        search_service: SearchService,
        embeddings_client: JinaEmbeddingsClient,
        opensearch_client: OpenSearch,
        rrf_k: int = 60,
    ) -> None:
        self._search_service = search_service
        self._embeddings_client = embeddings_client
        self._os_client = opensearch_client
        self._rrf_k = rrf_k

    async def search(
        self, query: str, category: str | None = None, size: int = 10, candidates: int = 50
    ) -> list[dict]:
        """Run BM25 and vector search, fuse with RRF, return top results."""
        bm25_results = self._search_service.search(query, category=category, size=candidates)

        query_embedding = (
            await self._embeddings_client.embed_texts([query], task="retrieval.query")
        )[0]
        vector_results = self._search_service.vector_search(
            query_embedding, category=category, size=candidates
        )

        bm25_ids = dedupe_ids(bm25_results)
        vector_ids = dedupe_ids(vector_results)

        fused = reciprocal_rank_fusion([bm25_ids, vector_ids], k=self._rrf_k)
        top_results = fused[:size]

        titles = {r["arxiv_id"]: r["title"] for r in bm25_results}
        return [
            {
                "arxiv_id": arxiv_id,
                "rrf_score": score,
                "title": titles.get(arxiv_id),
                "in_bm25": arxiv_id in bm25_ids,
                "in_vector": arxiv_id in vector_ids,
            }
            for arxiv_id, score in top_results
        ]


    async def retrieve_context(
        self, query: str, category: str | None = None, n: int = 5, candidates: int = 50
    ) -> list[dict]:
        """Hybrid-retrieve the top n papers, with chunk text for the LLM prompt."""
        from src.config import get_settings

        bm25_results = self._search_service.search(query, category=category, size=candidates)
        query_embedding = (
            await self._embeddings_client.embed_texts([query], task="retrieval.query")
        )[0]
        vector_results = self._search_service.vector_search(
            query_embedding, category=category, size=candidates
        )

        fused = reciprocal_rank_fusion(
            [dedupe_ids(bm25_results), dedupe_ids(vector_results)], k=self._rrf_k
        )[:n]
        if not fused:
            return []

        # best-ranked chunk per paper (vector_results are ordered best-first)
        best_chunk: dict[str, str] = {}
        for r in vector_results:
            if r.get("text"):
                best_chunk.setdefault(r["arxiv_id"], r["text"])

        # title + abstract (fallback text) from the papers index, doc id = arxiv_id
        docs = self._os_client.mget(
            index=get_settings().opensearch_papers_index,
            body={"docs": [{"_id": aid, "_source": ["title", "abstract"]} for aid, _ in fused]},
        )
        meta = {d["_id"]: d["_source"] for d in docs["docs"] if d.get("found")}

        context = []
        for aid, score in fused:
            m = meta.get(aid, {})
            abstract = m.get("abstract", "")
            chunk = best_chunk.get(aid, "")
            text = f"Abstract: {abstract}\n\nExcerpt: {chunk}" if chunk else abstract
            if text:
                context.append(
                    {"arxiv_id": aid, "title": m.get("title", ""), "text": text, "rrf_score": score}
                )
        return context
    