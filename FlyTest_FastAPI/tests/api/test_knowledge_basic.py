import os
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch

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


def _auth_headers() -> dict[str, str]:
    response = client.post("/api/token/", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access']}"}


def _create_project(headers: dict[str, str]) -> int:
    response = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": f"Knowledge Project {uuid4().hex[:8]}",
            "description": "knowledge migration test project",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_knowledge_basic_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    config = client.get("/api/knowledge/global-config/", headers=headers)
    assert config.status_code == 200
    assert "embedding_service" in config.json()["data"]

    knowledge_base = client.post(
        "/api/knowledge/knowledge-bases/",
        headers=headers,
        json={
            "name": f"KnowledgeBase {uuid4().hex[:6]}",
            "description": "knowledge base for fastapi migration",
            "project": project_id,
            "chunk_size": 500,
            "chunk_overlap": 100,
            "is_active": True,
        },
    )
    assert knowledge_base.status_code == 201
    kb_payload = knowledge_base.json()["data"]
    kb_id = kb_payload["id"]

    listing = client.get(f"/api/knowledge/knowledge-bases/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == kb_id for item in listing.json()["data"])

    detail = client.get(f"/api/knowledge/knowledge-bases/{kb_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == kb_id

    stats = client.get(f"/api/knowledge/knowledge-bases/{kb_id}/statistics/", headers=headers)
    assert stats.status_code == 200
    assert "document_count" in stats.json()["data"]

    with patch("knowledge.services.KnowledgeBaseService.process_document"):
        uploaded = client.post(
            "/api/knowledge/documents/",
            headers=headers,
            data={
                "knowledge_base": kb_id,
                "title": "Doc One",
                "document_type": "txt",
                "content": "hello knowledge",
            },
        )
        assert uploaded.status_code == 201
        doc_payload = uploaded.json()["data"]
        doc_id = doc_payload["id"]

    documents = client.get(f"/api/knowledge/documents/?knowledge_base={kb_id}", headers=headers)
    assert documents.status_code == 200
    assert any(item["id"] == doc_id for item in documents.json()["data"])

    doc_detail = client.get(f"/api/knowledge/documents/{doc_id}/", headers=headers)
    assert doc_detail.status_code == 200
    assert doc_detail.json()["data"]["id"] == doc_id

    doc_status = client.get(f"/api/knowledge/documents/{doc_id}/status/", headers=headers)
    assert doc_status.status_code == 200
    assert doc_status.json()["data"]["id"] == doc_id

    deleted_doc = client.delete(f"/api/knowledge/documents/{doc_id}/", headers=headers)
    assert deleted_doc.status_code == 200

    deleted_kb = client.delete(f"/api/knowledge/knowledge-bases/{kb_id}/", headers=headers)
    assert deleted_kb.status_code == 200
