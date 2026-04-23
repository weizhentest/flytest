from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.config import get_settings
from app.logging import configure_logging


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    try:
        yield
    finally:
        logger.info("Stopping %s", settings.app_name)
