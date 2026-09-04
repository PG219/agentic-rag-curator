from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Paper(Base):
    """Represents a single arXiv paper and its parsed content."""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # arXiv identifiers
    arxiv_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)  # comma-separated for now
    categories: Mapped[str] = mapped_column(String(200))  # comma-separated arXiv categories
    pdf_url: Mapped[str] = mapped_column(Text)

    # Parsed content (filled in after Docling parsing)
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<Paper arxiv_id={self.arxiv_id!r} title={self.title[:40]!r}>"

