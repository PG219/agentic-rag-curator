from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.config import Settings, get_settings

router = APIRouter(prefix="", tags=["health"])


@router.get("/health", summary="Service health check")
async def get_health(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Return health and status information for the service."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
