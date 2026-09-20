from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.database import get_db
from src.services.ingestion import IngestionService

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.post("/ingest", summary="Trigger ingestion for all configured arXiv categories")
async def trigger_ingestion(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """Fetch and store new papers for every configured arXiv category."""
    service = IngestionService(db)
    results = {}
    for category in settings.arxiv_categories_list:
        count = await service.ingest_category(category)
        results[category] = count
    return {"ingested": results}