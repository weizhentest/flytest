import os
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch

import httpx
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
            "name": f"API Test Case Project {uuid4().hex[:8]}",
            "description": "api automation test case migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


class MockResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.cookies = httpx.Cookies()
        self.text = str(payload)
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, **kwargs):
        self.cookies = kwargs.get("cookies") or httpx.Cookies()

    def request(self, **kwargs):
        return MockResponse(200, {"code": 200, "message": "ok", "data": {"user": "demo"}})

    def close(self):
        return None


@patch("api_automation.execution.httpx.Client")
def test_api_automation_test_case_flow(mock_client_cls) -> None:
    mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"Case CMS {uuid4().hex[:6]}", "parent": None},
    )
    collection_id = collection.json()["data"]["id"]

    environment = client.post(
        "/api/api-automation/environments/",
        headers=headers,
        json={
            "project": project_id,
            "name": f"Case Env {uuid4().hex[:6]}",
            "base_url": "https://example.test",
            "common_headers": {},
            "variables": {"token": "TOKEN_123"},
            "timeout_ms": 30000,
            "is_default": True,
            "environment_specs": {
                "headers": [],
                "variables": [{"name": "token", "value": "TOKEN_123", "enabled": True, "is_secret": True, "order": 0}],
                "cookies": [],
            },
        },
    )
    environment_id = environment.json()["data"]["id"]

    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Get Case User {uuid4().hex[:6]}",
            "description": "request for case test",
            "method": "GET",
            "url": "/api/profile",
            "headers": {},
            "params": {},
            "body_type": "none",
            "body": {},
            "assertions": [{"type": "status_code", "expected": 200}],
            "timeout_ms": 30000,
            "order": 0,
        },
    )
    request_id = request_response.json()["data"]["id"]

    created = client.post(
        "/api/api-automation/test-cases/",
        headers=headers,
        json={
            "project": project_id,
            "request": request_id,
            "name": f"Case {uuid4().hex[:6]}",
            "description": "test case description",
            "status": "ready",
            "tags": ["smoke"],
            "script": {},
            "assertions": [],
        },
    )
    assert created.status_code == 201
    test_case_id = created.json()["data"]["id"]

    listing = client.get(
        f"/api/api-automation/test-cases/?project={project_id}&collection={collection_id}",
        headers=headers,
    )
    assert listing.status_code == 200
    assert any(item["id"] == test_case_id for item in listing.json()["data"])

    detail = client.get(f"/api/api-automation/test-cases/{test_case_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == test_case_id

    updated = client.patch(
        f"/api/api-automation/test-cases/{test_case_id}/",
        headers=headers,
        json={"description": "updated description", "tags": ["smoke", "regression"]},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["description"] == "updated description"

    executed = client.post(
        f"/api/api-automation/test-cases/{test_case_id}/execute/",
        headers=headers,
        json={"environment_id": environment_id},
    )
    assert executed.status_code == 200

    batch = client.post(
        "/api/api-automation/test-cases/execute-batch/",
        headers=headers,
        json={"scope": "selected", "ids": [test_case_id], "environment_id": environment_id},
    )
    assert batch.status_code == 200
    assert batch.json()["data"]["total_count"] == 1

    deleted = client.delete(f"/api/api-automation/test-cases/{test_case_id}/", headers=headers)
    assert deleted.status_code == 200
