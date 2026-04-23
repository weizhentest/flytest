import os
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch
from types import SimpleNamespace

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "FlyTest_FastAPI"))
sys.path.insert(0, str(REPO_ROOT / "FlyTest_Django"))

os.environ["DATABASE_URL"] = f"sqlite:///{(REPO_ROOT / 'FlyTest_Django' / 'db.sqlite3').as_posix()}"
os.environ["SECRET_KEY"] = "change-me-fastapi-local"
os.environ["APP_ENV"] = "test"
os.environ["API_PREFIX"] = "/api"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

from app.config import get_settings

get_settings.cache_clear()

import django  # noqa: E402

django.setup()

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
            "description": "knowledge fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


@patch("knowledge.services.VectorStoreManager.__init__", return_value=None)
@patch("knowledge.services.KnowledgeBaseService.query")
@patch("knowledge.services.KnowledgeBaseService.process_document")
@patch("knowledge.services.KnowledgeBaseService.delete_document")
@patch("requests.post")
def test_knowledge_core_flow(mock_requests_post, mock_delete_document, mock_process_document, mock_query, _mock_vector_manager_init) -> None:
    from knowledge.models import Document, DocumentChunk, QueryLog

    mock_requests_post.return_value = SimpleNamespace(
        ok=True,
        status_code=200,
        text="ok",
        json=lambda: {"data": [{"embedding": [0.1, 0.2]}], "results": [{"index": 0, "relevance_score": 0.9}]},
    )

    mock_query.return_value = {
        "query": "what is this",
        "answer": "demo answer",
        "sources": [],
        "retrieval_time": 0.01,
        "generation_time": 0.02,
        "total_time": 0.03,
    }
    mock_delete_document.side_effect = lambda document: document.delete()

    headers = _auth_headers()
    project_id = _create_project(headers)

    config = client.get("/api/knowledge/global-config/", headers=headers)
    assert config.status_code == 200

    services = client.get("/api/knowledge/embedding-services/", headers=headers)
    assert services.status_code == 200
    assert services.json()["data"]["services"]

    created = client.post(
        "/api/knowledge/knowledge-bases/",
        headers=headers,
        json={
            "name": f"KB {uuid4().hex[:8]}",
            "description": "knowledge base",
            "project": project_id,
            "chunk_size": 500,
            "chunk_overlap": 50,
            "is_active": True,
        },
    )
    assert created.status_code == 201
    kb = created.json()["data"]
    kb_id = kb["id"]

    listing = client.get(f"/api/knowledge/knowledge-bases/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == kb_id for item in listing.json()["data"])

    detail = client.get(f"/api/knowledge/knowledge-bases/{kb_id}/", headers=headers)
    assert detail.status_code == 200

    stats = client.get(f"/api/knowledge/knowledge-bases/{kb_id}/statistics/", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["data"]["document_count"] >= 0

    queried = client.post(
        f"/api/knowledge/knowledge-bases/{kb_id}/query/",
        headers=headers,
        json={"query": "what is this", "top_k": 3, "similarity_threshold": 0.1},
    )
    assert queried.status_code == 200
    assert queried.json()["data"]["answer"] == "demo answer"

    uploaded = client.post(
        "/api/knowledge/documents/",
        headers=headers,
        data={
            "knowledge_base": kb_id,
            "title": "Doc A",
            "document_type": "txt",
            "content": "hello knowledge",
        },
    )
    assert uploaded.status_code == 201
    document = uploaded.json()["data"]
    document_id = document["id"]

    db_doc = Document.objects.get(id=document_id)
    db_doc.status = "completed"
    db_doc.content = "hello knowledge"
    db_doc.save(update_fields=["status", "content"])

    chunk = DocumentChunk.objects.create(
        document=db_doc,
        chunk_index=0,
        content="hello knowledge",
        vector_id="vec-1",
        embedding_hash="hash-1",
        start_index=0,
        end_index=15,
        page_number=1,
    )

    query_log = QueryLog.objects.create(
        knowledge_base_id=kb_id,
        user_id=1,
        query="what is this",
        response="demo answer",
        retrieved_chunks=[{"chunk_id": str(chunk.id)}],
        similarity_scores=[0.9],
        retrieval_time=0.01,
        generation_time=0.02,
        total_time=0.03,
    )

    documents = client.get(f"/api/knowledge/documents/?knowledge_base={kb_id}", headers=headers)
    assert documents.status_code == 200
    assert any(item["id"] == document_id for item in documents.json()["data"])

    document_detail = client.get(f"/api/knowledge/documents/{document_id}/", headers=headers)
    assert document_detail.status_code == 200

    document_status = client.get(f"/api/knowledge/documents/{document_id}/status/", headers=headers)
    assert document_status.status_code == 200
    assert document_status.json()["data"]["status"] == "completed"

    content = client.get(f"/api/knowledge/documents/{document_id}/content/", headers=headers)
    assert content.status_code == 200
    assert content.json()["data"]["content"] == "hello knowledge"

    knowledge_content = client.get(f"/api/knowledge/knowledge-bases/{kb_id}/content/", headers=headers)
    assert knowledge_content.status_code == 200
    assert knowledge_content.json()["data"]["knowledge_base"]["id"] == kb_id

    chunks = client.get(f"/api/knowledge/chunks/?document={document_id}", headers=headers)
    assert chunks.status_code == 200
    assert any(item["id"] == str(chunk.id) for item in chunks.json()["data"])

    chunk_detail = client.get(f"/api/knowledge/chunks/{chunk.id}/", headers=headers)
    assert chunk_detail.status_code == 200

    query_logs = client.get(f"/api/knowledge/query-logs/?knowledge_base={kb_id}", headers=headers)
    assert query_logs.status_code == 200
    assert any(item["id"] == str(query_log.id) for item in query_logs.json()["data"])

    query_log_detail = client.get(f"/api/knowledge/query-logs/{query_log.id}/", headers=headers)
    assert query_log_detail.status_code == 200

    embedding_test = client.post(
        "/api/knowledge/test-embedding-connection/",
        headers=headers,
        json={
            "embedding_service": "custom",
            "api_base_url": "https://example.test/embeddings",
            "model_name": "embed-demo",
            "api_key": "",
        },
    )
    assert embedding_test.status_code == 200

    reranker_test = client.post(
        "/api/knowledge/test-reranker-connection/",
        headers=headers,
        json={
            "reranker_service": "custom",
            "reranker_api_url": "https://example.test/rerank",
            "reranker_model_name": "rerank-demo",
            "reranker_api_key": "",
        },
    )
    assert reranker_test.status_code == 200

    reprocess = client.post(f"/api/knowledge/documents/{document_id}/reprocess/", headers=headers)
    assert reprocess.status_code == 200

    system_status = client.get("/api/knowledge/knowledge-bases/system_status/", headers=headers)
    assert system_status.status_code == 200
    assert "overall_status" in system_status.json()["data"]

    deleted_doc = client.delete(f"/api/knowledge/documents/{document_id}/", headers=headers)
    assert deleted_doc.status_code == 200

    deleted_kb = client.delete(f"/api/knowledge/knowledge-bases/{kb_id}/", headers=headers)
    assert deleted_kb.status_code == 200
