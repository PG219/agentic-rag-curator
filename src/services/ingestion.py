from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.paper import Paper
from src.services.arxiv.client import ArxivClient, ArxivPaper
from src.services.parsing.pdf_parser import PDFParser


class IngestionService:
    """Orchestrates fetching, parsing, and storing arXiv papers."""

    def __init__(
        self,
        db: Session,
        arxiv_client: ArxivClient | None = None,
        pdf_parser: PDFParser | None = None,
    ) -> None:
        self._db = db
        self._arxiv_client = arxiv_client or ArxivClient()
        self._pdf_parser = pdf_parser or PDFParser()

    async def ingest_category(self, category: str, max_results: int | None = None) -> int:
        """Fetch, parse, and store papers for a single arXiv category.

        Returns the number of new papers ingested (skips already-existing ones).
        """
        arxiv_papers = await self._arxiv_client.fetch_papers(category, max_results)

        ingested_count = 0
        for arxiv_paper in arxiv_papers:
            if self._paper_exists(arxiv_paper.arxiv_id):
                continue

            parsed_text = await self._safe_parse(arxiv_paper.pdf_url)
            paper = self._to_db_model(arxiv_paper, parsed_text)

            self._db.add(paper)
            self._db.commit()
            ingested_count += 1

        return ingested_count

    def _paper_exists(self, arxiv_id: str) -> bool:
        """Check whether a paper with this arxiv_id is already stored."""
        stmt = select(Paper.id).where(Paper.arxiv_id == arxiv_id)
        return self._db.execute(stmt).scalar_one_or_none() is not None

    async def _safe_parse(self, pdf_url: str) -> str | None:
        """Parse a PDF, returning None instead of raising if parsing fails."""
        try:
            return await self._pdf_parser.parse_from_url(pdf_url)
        except Exception:
            return None

    def _to_db_model(self, arxiv_paper: ArxivPaper, parsed_text: str | None) -> Paper:
        """Convert an ArxivPaper (fetched data) into a Paper (DB row)."""
        return Paper(
            arxiv_id=arxiv_paper.arxiv_id,
            title=arxiv_paper.title,
            abstract=arxiv_paper.abstract,
            authors=", ".join(arxiv_paper.authors),
            categories=", ".join(arxiv_paper.categories),
            pdf_url=arxiv_paper.pdf_url,
            parsed_text=parsed_text,
            published_at=arxiv_paper.published_at,
        )