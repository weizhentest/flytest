import io
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4
import zipfile
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
    access = response.json()["data"]["access"]
    return {"Authorization": f"Bearer {access}"}


def _create_project(headers: dict[str, str]) -> int:
    response = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": f"Skill Project {uuid4().hex[:8]}",
            "description": "Skill migration test project",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _build_skill_zip(skill_name: str) -> tuple[str, bytes]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        skill_md = (
            "---\n"
            f"name: {skill_name}\n"
            "description: Skill migration smoke test\n"
            "---\n\n"
            "# Usage\n\n"
            "This is a temporary skill for FastAPI smoke tests.\n"
        )
        zf.writestr("SKILL.md", skill_md)
        zf.writestr("runner.py", "def run():\n    return 'ok'\n")
    return f"{skill_name}.zip", buffer.getvalue()


def test_skills_upload_and_manage_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    skill_name = f"FastAPI Skill {uuid4().hex[:8]}"
    filename, payload = _build_skill_zip(skill_name)

    uploaded = client.post(
        f"/api/projects/{project_id}/skills/upload/",
        headers=headers,
        files={"file": (filename, payload, "application/zip")},
    )
    assert uploaded.status_code == 201
    skill = uploaded.json()["data"]
    skill_id = skill["id"]
    assert skill["name"] == skill_name

    listing = client.get(f"/api/projects/{project_id}/skills/", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == skill_id for item in listing.json()["data"])

    detail = client.get(f"/api/projects/{project_id}/skills/{skill_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == skill_id

    content = client.get(f"/api/projects/{project_id}/skills/{skill_id}/content/", headers=headers)
    assert content.status_code == 200
    assert content.json()["data"]["name"] == skill_name

    toggled = client.patch(
        f"/api/projects/{project_id}/skills/{skill_id}/",
        headers=headers,
        json={"is_active": False},
    )
    assert toggled.status_code == 200
    assert toggled.json()["data"]["is_active"] is False

    deleted = client.delete(f"/api/projects/{project_id}/skills/{skill_id}/", headers=headers)
    assert deleted.status_code == 200


def test_skills_import_git_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    skill_name = f"Git Skill {uuid4().hex[:8]}"

    def fake_clone_repo(_git_url: str, _branch: str, dest_dir: str) -> None:
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                f"name: {skill_name}\n"
                "description: Imported from fake git\n"
                "---\n\n"
                "# Usage\n\n"
                "Imported skill.\n"
            )
        with open(os.path.join(dest_dir, "runner.py"), "w", encoding="utf-8") as handle:
            handle.write("def run():\n    return 'ok'\n")

    with patch("app.services.skills.service._clone_repo", side_effect=fake_clone_repo):
        imported = client.post(
            f"/api/projects/{project_id}/skills/import-git/",
            headers=headers,
            data={"git_url": "https://example.com/repo.git", "branch": "main"},
        )
        assert imported.status_code == 201
        payload = imported.json()["data"]
        assert len(payload) == 1
        assert payload[0]["name"] == skill_name
