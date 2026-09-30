from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from src.models.paper import Paper
from src.services.chunking.chunker import TextChunker
from src.services.embeddings.jina_client import JinaEmbeddingsClient


class EmbeddingIndexingService:
    """Chunks papers, embeds each chunk, and indexes them into OpenSearch."""

    def __init__(
        self,
        client: OpenSearch,
        index_name: str,
        chunker: TextChunker | None = None,
        embeddings_client: JinaEmbeddingsClient | None = None,
    ) -> None:
        self._client = client
        self._index_name = index_name
        self._chunker = chunker or TextChunker()
        self._embeddings_client = embeddings_client or JinaEmbeddingsClient()

    async def index_paper_chunks(self, paper: Paper) -> int:
        """Chunk a paper, embed each chunk, and index them. Returns chunk count."""
        if not paper.parsed_text:
            return 0

        chunks = self._chunker.chunk_text(paper.parsed_text)
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        embeddings = await self._embeddings_client.embed_texts(texts, task="retrieval.passage")

        actions = [
            {
                "_index": self._index_name,
                "_id": f"{paper.arxiv_id}_{chunk.chunk_index}",
                "_source": {
                    "arxiv_id": paper.arxiv_id,
                    "chunk_index": chunk.chunk_index,
                    "section_title": chunk.section_title,
                    "text": chunk.text,
                    "categories": paper.categories,
                    "embedding": embedding,
                },
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
        success_count, _ = bulk(self._client, actions)
        return success_count