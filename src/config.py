from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application runtime settings loaded from environment and .env file."""
        # arXiv Settings
    arxiv_categories: str = Field(
        default="cs.AI,cs.LG,cs.CL",
        description="Comma-separated arXiv categories to fetch",
    )
    arxiv_max_results: int = Field(
        default=50, description="Max papers to fetch per ingestion run"
    )
    arxiv_request_delay_seconds: float = Field(
        default=3.0, description="Delay between arXiv API requests (politeness policy)"
    )

    @property
    def arxiv_categories_list(self) -> list[str]:
        """Parse comma-separated categories into a list."""
        return [c.strip() for c in self.arxiv_categories.split(",") if c.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core App Settings
    app_name: str = Field(default="agentic-rag-curator", description="Application name")
    app_env: str = Field(
        default="development",
        description="Current environment (development, staging, production)",
    )
    debug: bool = Field(default=False, description="Debug mode flag")
    host: str = Field(default="0.0.0.0", description="Bind host for HTTP server")
    port: int = Field(default=8000, description="Bind port for HTTP server")

    # PostgreSQL Settings
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(default="postgres", description="PostgreSQL username")
    postgres_password: str = Field(
        default="postgres", description="PostgreSQL password"
    )
    postgres_db: str = Field(
        default="rag_curator", description="PostgreSQL database name"
    )

    # OpenSearch Settings
    opensearch_host: str = Field(default="localhost", description="OpenSearch host")
    opensearch_port: int = Field(default=9200, description="OpenSearch port")
    opensearch_user: str = Field(default="admin", description="OpenSearch username")
    opensearch_password: str = Field(default="admin", description="OpenSearch password")
    opensearch_use_ssl: bool = Field(
        default=False, description="Whether to use SSL for OpenSearch"
    )
    opensearch_verify_certs: bool = Field(
        default=False, description="Verify OpenSearch SSL certificates"
    )

    @property
    def postgres_dsn(self) -> str:
        """Construct PostgreSQL connection string."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def opensearch_url(self) -> str:
        """Construct OpenSearch URL."""
        scheme = "https" if self.opensearch_use_ssl else "http"
        return f"{scheme}://{self.opensearch_host}:{self.opensearch_port}"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
