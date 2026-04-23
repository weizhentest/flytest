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
    access = response.json()["data"]["access"]
    return {"Authorization": f"Bearer {access}"}


def test_auth_and_prompts_and_projects_flow() -> None:
    headers = _auth_headers()
    project_name = f"FastAPI Scaffold Project {uuid4().hex[:8]}"

    me = client.get("/api/accounts/me/", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"

    prompt_types = client.get("/api/prompts/user-prompts/types/", headers=headers)
    assert prompt_types.status_code == 200
    assert any(item["value"] == "api_automation_report_summary" for item in prompt_types.json()["data"])

    prompt_list = client.get("/api/prompts/user-prompts/", headers=headers)
    assert prompt_list.status_code == 200
    assert isinstance(prompt_list.json()["data"]["results"], list)

    create_project = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": project_name,
            "description": "FastAPI migration smoke test project",
            "credentials": [
                {
                    "system_url": "https://example.test",
                    "username": "tester",
                    "password": "secret",
                    "user_role": "admin",
                }
            ],
        },
    )
    assert create_project.status_code == 201
    project_payload = create_project.json()["data"]
    project_id = project_payload["id"]
    assert project_payload["name"] == project_name
    assert project_payload["members"]

    projects = client.get("/api/projects/", headers=headers)
    assert projects.status_code == 200
    assert any(item["id"] == project_id for item in projects.json()["data"])

    members = client.get(f"/api/projects/{project_id}/members/", headers=headers)
    assert members.status_code == 200
    assert len(members.json()["data"]) >= 1

    detail = client.get(f"/api/projects/{project_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == project_id

    statistics = client.get(f"/api/projects/{project_id}/statistics/", headers=headers)
    assert statistics.status_code == 200
    statistics_payload = statistics.json()["data"]
    assert statistics_payload["project"]["id"] == project_id
    assert "testcases" in statistics_payload
    assert "executions" in statistics_payload
    assert "skills" in statistics_payload

    remove = client.delete(f"/api/projects/{project_id}/", headers=headers)
    assert remove.status_code == 200


def test_api_keys_flow() -> None:
    headers = _auth_headers()

    created = client.post(
        "/api/api-keys/",
        headers=headers,
        json={
            "name": f"FastAPI Key {uuid4().hex[:8]}",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    key_payload = created.json()["data"]
    key_id = key_payload["id"]
    assert key_payload["key"]

    listing = client.get("/api/api-keys/", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == key_id for item in listing.json()["data"])

    detail = client.get(f"/api/api-keys/{key_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == key_id

    updated = client.patch(
        f"/api/api-keys/{key_id}/",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["is_active"] is False

    deleted = client.delete(f"/api/api-keys/{key_id}/", headers=headers)
    assert deleted.status_code == 200
