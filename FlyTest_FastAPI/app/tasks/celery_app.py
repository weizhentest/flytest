from celery import Celery

from app.config import get_settings


settings = get_settings()
celery_app = Celery("flytest_fastapi")
celery_app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
