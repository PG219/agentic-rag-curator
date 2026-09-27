from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

from src.models.paper import Paper


def paper_to_document(paper: Paper) -> dict:
    """Convert a Paper ORM row into an OpenSearch document."""
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "parsed_text": paper.parsed_text or "",
        "authors": paper.authors,
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "published_at": paper.published_at.isoformat(),
    }


class IndexingService:
    """Indexes Paper rows from Postgres into OpenSearch."""

    def __init__(self, client: OpenSearch, index_name: str) -> None:
        self._client = client
        self._index_name = index_name

    def index_paper(self, paper: Paper) -> None:
        """Index a single paper, using its arxiv_id as the document id."""
        self._client.index(
            index=self._index_name,
            id=paper.arxiv_id,
            body=paper_to_document(paper),
        )

    def bulk_index_papers(self, papers: list[Paper]) -> int:
        """Index multiple papers efficiently using OpenSearch's bulk API."""
        actions = [
            {
                "_index": self._index_name,
                "_id": paper.arxiv_id,
                "_source": paper_to_document(paper),
            }
            for paper in papers
        ]
        success_count, _ = bulk(self._client, actions)
        return success_count


        