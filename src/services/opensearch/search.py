from opensearchpy import OpenSearch


class SearchService:
    """Performs BM25 keyword search against the papers index."""

    def __init__(self, client: OpenSearch, index_name: str) -> None:
        self._client = client
        self._index_name = index_name

    def search(
        self,
        query: str,
        category: str | None = None,
        size: int = 10,
    ) -> list[dict]:
        """Search papers by keyword relevance, optionally filtered by category."""
        must_clauses = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "abstract^2", "parsed_text"],
                }
            }
        ]
        filter_clauses = []
        if category:
            filter_clauses.append({"term": {"categories": category}})

        body = {
            "query": {"bool": {"must": must_clauses, "filter": filter_clauses}},
            "highlight": {"fields": {"abstract": {}, "parsed_text": {}}},
            "size": size,
        }

        response = self._client.search(index=self._index_name, body=body)
        return [
            {
                "arxiv_id": hit["_source"]["arxiv_id"],
                "title": hit["_source"]["title"],
                "score": hit["_score"],
                "highlights": hit.get("highlight", {}),
            }
            for hit in response["hits"]["hits"]
        ]