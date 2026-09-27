from opensearchpy import OpenSearch

from src.config import Settings, get_settings


def get_opensearch_client(settings: Settings | None = None) -> OpenSearch:
    """Create an OpenSearch client configured from application settings."""
    settings = settings or get_settings()
    return OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_auth=None,
        use_ssl=settings.opensearch_use_ssl,
        verify_certs=settings.opensearch_verify_certs,
    )