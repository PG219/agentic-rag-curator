from datetime import datetime

import requests
from airflow.sdk import dag, task


@dag(
    dag_id="ingest_arxiv_papers",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ingestion", "arxiv"],
)
def ingest_arxiv_papers():
    @task
    def trigger_ingestion() -> dict:
        """Call the FastAPI app's ingestion endpoint."""
        response = requests.post("http://app:8000/api/v1/ingest", timeout=600)
        response.raise_for_status()
        return response.json()

    trigger_ingestion()


ingest_arxiv_papers()