from fastapi import APIRouter

from app.config import get_settings
from app.core.responses import success_response


router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return success_response(
        {
            "ok": True,
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": settings.api_version,
        }
    )


@router.get("/ready")
def ready() -> dict:
    settings = get_settings()
    return success_response(
        {
            "ok": True,
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": settings.api_version,
        }
    )
