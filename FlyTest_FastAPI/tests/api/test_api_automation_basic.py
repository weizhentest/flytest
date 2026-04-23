import os
from pathlib import Path
import sys
from uuid import uuid4

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
            "name": f"API Automation Project {uuid4().hex[:8]}",
            "description": "api automation fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_api_automation_basic_crud_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"CMS {uuid4().hex[:6]}", "parent": None},
    )
    assert collection.status_code == 201
    collection_payload = collection.json()["data"]
    collection_id = collection_payload["id"]

    tree = client.get(f"/api/api-automation/collections/tree/?project={project_id}", headers=headers)
    assert tree.status_code == 200
    assert any(item["id"] == collection_id for item in tree.json()["data"])

    environment = client.post(
        "/api/api-automation/environments/",
        headers=headers,
        json={
            "project": project_id,
            "name": f"Test Env {uuid4().hex[:6]}",
            "base_url": "https://example.test/api",
            "common_headers": {},
            "variables": {"token": ""},
            "timeout_ms": 30000,
            "is_default": True,
            "environment_specs": {
                "headers": [],
                "variables": [{"name": "token", "value": "", "enabled": True, "is_secret": True, "order": 0}],
                "cookies": [],
            },
        },
    )
    assert environment.status_code == 201
    environment_payload = environment.json()["data"]
    environment_id = environment_payload["id"]

    environments = client.get(f"/api/api-automation/environments/?project={project_id}", headers=headers)
    assert environments.status_code == 200
    assert any(item["id"] == environment_id for item in environments.json()["data"])

    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Get User {uuid4().hex[:6]}",
            "description": "request migration test",
            "method": "GET",
            "url": "/api/user/profile",
            "headers": {"Authorization": "Bearer {{token}}"},
            "params": {},
            "body_type": "none",
            "body": {},
            "assertions": [{"type": "status_code", "expected": 200}],
            "timeout_ms": 30000,
            "order": 0,
            "request_spec": {
                "method": "GET",
                "url": "/api/user/profile",
                "body_mode": "none",
                "body_json": {},
                "raw_text": "",
                "xml_text": "",
                "binary_base64": "",
                "graphql_query": "",
                "graphql_operation_name": "",
                "graphql_variables": {},
                "timeout_ms": 30000,
                "headers": [{"name": "Authorization", "value": "Bearer {{token}}", "enabled": True, "order": 0}],
                "query": [],
                "cookies": [],
                "form_fields": [],
                "multipart_parts": [],
                "files": [],
                "auth": {
                    "auth_type": "none",
                    "username": "",
                    "password": "",
                    "token_value": "",
                    "token_variable": "token",
                    "header_name": "Authorization",
                    "bearer_prefix": "Bearer",
                    "api_key_name": "",
                    "api_key_in": "header",
                    "api_key_value": "",
                    "cookie_name": "",
                    "bootstrap_request_id": None,
                    "bootstrap_request_name": "",
                    "bootstrap_token_path": "",
                },
                "transport": {
                    "verify_ssl": True,
                    "proxy_url": "",
                    "client_cert": "",
                    "client_key": "",
                    "follow_redirects": True,
                    "retry_count": 0,
                    "retry_interval_ms": 500,
                },
            },
        },
    )
    assert request_response.status_code == 201
    request_payload = request_response.json()["data"]
    request_id = request_payload["id"]

    requests = client.get(
        f"/api/api-automation/requests/?project={project_id}&collection={collection_id}",
        headers=headers,
    )
    assert requests.status_code == 200
    assert any(item["id"] == request_id for item in requests.json()["data"])

    deleted_request = client.delete(f"/api/api-automation/requests/{request_id}/", headers=headers)
    assert deleted_request.status_code == 200

    deleted_environment = client.delete(f"/api/api-automation/environments/{environment_id}/", headers=headers)
    assert deleted_environment.status_code == 200

    deleted_collection = client.delete(f"/api/api-automation/collections/{collection_id}/", headers=headers)
    assert deleted_collection.status_code == 200
