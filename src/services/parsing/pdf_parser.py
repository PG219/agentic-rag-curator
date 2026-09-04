import tempfile
from pathlib import Path

import httpx
import pymupdf4llm


class PDFParser:
    """Downloads a PDF from a URL and extracts clean Markdown text for RAG chunking."""

    async def parse_from_url(self, pdf_url: str) -> str:
        """Download the PDF at pdf_url and return its content as Markdown."""
        pdf_bytes = await self._download(pdf_url)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)

        try:
            markdown_text = pymupdf4llm.to_markdown(str(tmp_path))
            return markdown_text
        finally:
            tmp_path.unlink(missing_ok=True)

    async def _download(self, pdf_url: str) -> bytes:
        """Fetch raw PDF bytes from a URL."""
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()
            return response.content