from fastapi import APIRouter

from app.config import get_settings
from app.core.responses import success_response


router = APIRouter(prefix="/_meta", tags=["meta"])


@router.get("/version")
def version() -> dict:
    settings = get_settings()
    return success_response(
        {
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": settings.api_version,
        }
    )
