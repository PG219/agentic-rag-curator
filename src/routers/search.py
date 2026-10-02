from fastapi import APIRouter, Depends, Query

from src.config import Settings, get_settings
from src.services.opensearch.client import get_opensearch_client
from src.services.opensearch.search import SearchService

router = APIRouter(prefix="/api/v1", tags=["search"])
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.search.hybrid import HybridSearchService


@router.post("/hybrid-search", summary="Hybrid BM25 + vector search fused with RRF")
async def hybrid_search_papers(
    q: str = Query(..., description="Search query"),
    category: str | None = Query(None, description="Filter by arXiv category"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Search papers using both keyword and semantic search, fused with RRF."""
    client = get_opensearch_client(settings)
    search_service = SearchService(
        client, settings.opensearch_papers_index, settings.opensearch_chunks_index
    )
    embeddings_client = JinaEmbeddingsClient(settings)
    hybrid_service = HybridSearchService(search_service, embeddings_client, client)
    results = await hybrid_service.search(query=q, category=category)
    return {"query": q, "results": results}

@router.post("/search", summary="Keyword search papers using BM25")
async def search_papers(
    q: str = Query(..., description="Search query"),
    category: str | None = Query(None, description="Filter by arXiv category"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Search papers by keyword relevance."""
    client = get_opensearch_client(settings)
    service = SearchService(
        client, settings.opensearch_papers_index, settings.opensearch_chunks_index
    )
    results = service.search(query=q, category=category)
    return {"query": q, "results": results}