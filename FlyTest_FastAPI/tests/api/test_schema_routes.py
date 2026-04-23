import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "FlyTest_FastAPI"))

os.environ["DATABASE_URL"] = f"sqlite:///{(REPO_ROOT / 'FlyTest_Django' / 'db.sqlite3').as_posix()}"
os.environ["SECRET_KEY"] = "change-me-fastapi-local"
os.environ["APP_ENV"] = "test"
os.environ["API_PREFIX"] = "/api"

from app.config import get_settings

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


client = TestClient(create_app())


def test_schema_routes_are_available() -> None:
    schema = client.get("/api/schema/")
    assert schema.status_code == 200
    assert "openapi" in schema.json()

    swagger = client.get("/api/schema/swagger-ui/")
    assert swagger.status_code == 200
    assert "Swagger UI" in swagger.text

    redoc = client.get("/api/schema/redoc/")
    assert redoc.status_code == 200
    assert "ReDoc" in redoc.text
