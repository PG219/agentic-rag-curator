"""Backfill paper_chunks: chunk + embed + index every paper that has no chunks yet.

Run from the repo root (venv active, Docker services up):
    python -m scripts.backfill_chunks --limit 10
Safe to re-run: papers that already have chunks are skipped.
"""
import argparse
import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.paper import Paper
from src.services.embeddings.jina_client import JinaEmbeddingsClient
from src.services.indexing.embedding_indexing import EmbeddingIndexingService  # adjust path if needed
from src.services.opensearch.client import get_opensearch_client


def already_chunked_ids(client, index: str) -> set[str]:
    resp = client.search(
        index=index,
        body={"size": 0, "aggs": {"ids": {"terms": {"field": "arxiv_id", "size": 1000}}}},
    )
    return {b["key"] for b in resp["aggregations"]["ids"]["buckets"]}


async def main(limit: int | None) -> None:
    settings = get_settings()
    client = get_opensearch_client(settings)
    service = EmbeddingIndexingService(
        client, settings.opensearch_chunks_index, embeddings_client=JinaEmbeddingsClient(settings)
    )

    done = already_chunked_ids(client, settings.opensearch_chunks_index)
    engine = create_engine(settings.postgres_dsn)
    with Session(engine) as session:
        papers = session.scalars(select(Paper).where(Paper.parsed_text.is_not(None))).all()

    todo = [p for p in papers if p.arxiv_id not in done]
    if limit:
        todo = todo[:limit]
    print(f"{len(papers)} papers with text, {len(done)} already chunked, processing {len(todo)}")

    total_chunks = 0
    for i, paper in enumerate(todo, 1):
        try:
            n = await service.index_paper_chunks(paper)
            total_chunks += n
            print(f"[{i}/{len(todo)}] {paper.arxiv_id}: {n} chunks")
        except Exception as e:  # keep going; re-run later picks up failures
            print(f"[{i}/{len(todo)}] {paper.arxiv_id} FAILED: {e}")
            await asyncio.sleep(5)
    print(f"Done. {total_chunks} chunks indexed this run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="max papers this run")
    asyncio.run(main(parser.parse_args().limit))