import asyncio
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx

from src.config import Settings, get_settings

ARXIV_API_BASE = "https://export.arxiv.org/api/query"


@dataclass
class ArxivPaper:
    """Structured representation of a single arXiv search result."""

    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    pdf_url: str
    published_at: datetime


class ArxivClient:
    """Client for querying the arXiv API, respecting arXiv's rate-limit policy."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._last_request_time: float = 0.0

    async def _respect_rate_limit(self) -> None:
        """Sleep if needed so requests are spaced by the configured delay."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        wait = self._settings.arxiv_request_delay_seconds - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_time = asyncio.get_event_loop().time()

    async def fetch_papers(
        self, category: str, max_results: int | None = None
    ) -> list[ArxivPaper]:
        """Fetch recent papers for a single arXiv category, newest first."""
        await self._respect_rate_limit()

        params = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results or self._settings.arxiv_max_results,
        }
        headers = {"User-Agent": "agentic-rag-curator/0.1 (research assistant project)", "Accept": "application/atom+xml"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(ARXIV_API_BASE, params=params, headers=headers)
            response.raise_for_status()

        return self._parse_feed(response.text)

    def _parse_feed(self, raw_xml: str) -> list[ArxivPaper]:
        """Parse arXiv's Atom feed response into structured ArxivPaper objects."""
        feed = feedparser.parse(raw_xml)
        papers: list[ArxivPaper] = []

        for entry in feed.entries:
            arxiv_id = entry.id.split("/abs/")[-1]
            pdf_url = next(
                (link.href for link in entry.links if link.get("title") == "pdf"),
                entry.id.replace("/abs/", "/pdf/"),
            )
            papers.append(
                ArxivPaper(
                    arxiv_id=arxiv_id,
                    title=entry.title.replace("\n", " ").strip(),
                    abstract=entry.summary.replace("\n", " ").strip(),
                    authors=[author.name for author in entry.authors],
                    categories=[tag.term for tag in entry.tags],
                    pdf_url=pdf_url,
                    published_at=datetime(*entry.published_parsed[:6]),
                )
            )
        return papers