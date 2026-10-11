import asyncio

from src.database import SessionLocal
from src.models.paper import Paper
from src.services.opensearch.client import get_opensearch_client
from src.services.embeddings.embedding_indexer import EmbeddingIndexingService
from src.config import get_settings


async def run():
    settings = get_settings()
    db = SessionLocal()
    papers = db.query(Paper).all()
    print(f"Found {len(papers)} papers total")

    client = get_opensearch_client()
    service = EmbeddingIndexingService(client, settings.opensearch_chunks_index)

    total = 0
    for i, paper in enumerate(papers, 1):
        try:
            count = await service.index_paper_chunks(paper)
            total += count
            if i % 10 == 0:
                print(f"[{i}/{len(papers)}] processed, {total} chunks so far")
        except Exception as e:
            print(f"[{i}/{len(papers)}] {paper.arxiv_id} FAILED: {e}")
        await asyncio.sleep(1)  # be polite to Jina's rate limit

    print(f"Done. Total: {total} chunks indexed")
    db.close()


if __name__ == "__main__":
    asyncio.run(run())