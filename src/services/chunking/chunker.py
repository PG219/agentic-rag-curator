from dataclasses import dataclass

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


@dataclass
class Chunk:
    """A single chunk of a paper's text, with its section heading if known."""

    text: str
    chunk_index: int
    section_title: str | None


class TextChunker:
    """Splits a paper's markdown text into semantically coherent chunks."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
            strip_headers=False,
        )
        self._size_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_text(self, text: str) -> list[Chunk]:
        """Split markdown text into chunks, preferring header boundaries."""
        if not text or not text.strip():
            return []

        sections = self._header_splitter.split_text(text)

        chunks: list[Chunk] = []
        index = 0
        for section in sections:
            section_title = (
                section.metadata.get("h3")
                or section.metadata.get("h2")
                or section.metadata.get("h1")
            )
            sub_chunks = self._size_splitter.split_text(section.page_content)
            for sub_chunk in sub_chunks:
                chunks.append(
                    Chunk(text=sub_chunk, chunk_index=index, section_title=section_title)
                )
                index += 1

        return chunks