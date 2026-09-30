from opensearchpy import OpenSearch

PAPERS_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "arxiv_id": {"type": "keyword"},
            "title": {"type": "text"},
            "abstract": {"type": "text"},
            "parsed_text": {"type": "text"},
            "authors": {"type": "text"},
            "categories": {"type": "keyword"},
            "pdf_url": {"type": "keyword"},
            "published_at": {"type": "date"},
        }
    },
}


CHUNKS_INDEX_MAPPING = {
    "settings": {
        "index": {"knn": True},
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "arxiv_id": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "section_title": {"type": "keyword"},
            "text": {"type": "text"},
            "categories": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                },
            },
        }
    },
}


def create_chunks_index(client: OpenSearch, index_name: str) -> None:
    """Create the chunks index with k-NN vector support, if it doesn't already exist."""
    if client.indices.exists(index=index_name):
        return
    client.indices.create(index=index_name, body=CHUNKS_INDEX_MAPPING)

def create_papers_index(client: OpenSearch, index_name: str) -> None:
    """Create the papers index with the correct mapping, if it doesn't already exist."""
    if client.indices.exists(index=index_name):
        return
    client.indices.create(index=index_name, body=PAPERS_INDEX_MAPPING)