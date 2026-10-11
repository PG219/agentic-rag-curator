from fastapi import APIRouter, Depends, HTTPException, Query

from src.config import Settings, get_settings
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.llm.client import LLMClient, LLMError
from src.services.opensearch.client import get_opensearch_client
from src.services.opensearch.search import SearchService
from src.services.rag import RAGService
from src.services.search.hybrid import HybridSearchService

router = APIRouter(prefix="/api/v1", tags=["rag"])


@router.post("/ask", summary="Answer a question from retrieved arXiv papers (RAG)")
async def ask(
    q: str = Query(..., description="Your question"),
    category: str | None = Query(None, description="Filter by arXiv category"),
    n: int = Query(5, ge=1, le=10, description="Number of papers to use as context"),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Retrieve relevant papers with hybrid search, then generate a cited answer."""
    client = get_opensearch_client(settings)
    search_service = SearchService(
        client, settings.opensearch_papers_index, settings.opensearch_chunks_index
    )
    embeddings_client = JinaEmbeddingsClient(settings)
    hybrid = HybridSearchService(search_service, embeddings_client, client)
    rag = RAGService(hybrid, LLMClient())

    try:
        result = await rag.ask(q, n=n, category=category)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")
    return {"question": q, **result}