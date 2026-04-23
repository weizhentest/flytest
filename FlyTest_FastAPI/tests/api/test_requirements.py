import os
from pathlib import Path
import sys
from uuid import uuid4

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
            "name": f"Requirements Project {uuid4().hex[:8]}",
            "description": "requirements fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_requirements_core_flow() -> None:
    from requirements.models import RequirementDocument

    headers = _auth_headers()
    project_id = _create_project(headers)

    created = client.post(
        "/api/requirements/documents/",
        headers=headers,
        data={
            "project": str(project_id),
            "title": f"Requirement Doc {uuid4().hex[:6]}",
            "description": "fastapi migration document",
            "document_type": "md",
            "content": "# Overview\n## Login\nThe user can login.\n## Billing\nSupport invoices.",
        },
    )
    assert created.status_code == 201
    document = created.json()["data"]
    document_id = document["id"]

    listing = client.get(f"/api/requirements/documents/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == document_id for item in listing.json()["data"])

    structure = client.get(f"/api/requirements/documents/{document_id}/analyze-structure/", headers=headers)
    assert structure.status_code == 200
    assert structure.json()["data"]["structure_analysis"]["h1_titles"]

    detail = client.get(f"/api/requirements/documents/{document_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["latest_review"] is None

    created_module = client.post(
        "/api/requirements/modules/",
        headers=headers,
        json={
            "document": document_id,
            "title": "Login module",
            "content": "Support login and logout",
            "order": 0,
            "is_auto_generated": False,
        },
    )
    assert created_module.status_code == 201
    module = created_module.json()["data"]
    module_id = module["id"]

    modules = client.get(f"/api/requirements/modules/?document={document_id}", headers=headers)
    assert modules.status_code == 200
    assert any(item["id"] == module_id for item in modules.json()["data"])

    db_document = RequirementDocument.objects.get(id=document_id)
    db_document.status = "user_reviewing"
    db_document.save(update_fields=["status"])

    adjusted = client.put(
        f"/api/requirements/documents/{document_id}/adjust-modules/",
        headers=headers,
        json={
            "modules": [
                {
                    "title": "Login module refined",
                    "content": "Support login, logout and password recovery",
                    "order": 0,
                    "is_auto_generated": False,
                }
            ]
        },
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["status"] == "ready_for_review"
    module_id = adjusted.json()["data"]["modules"][0]["id"]

    report_created = client.post(
        "/api/requirements/reports/",
        headers=headers,
        json={
            "document": document_id,
            "status": "pending",
            "overall_rating": "average",
            "completion_score": 72,
            "summary": "Initial review summary",
            "recommendations": "Add more business rules",
            "progress": 0.25,
            "current_step": "initializing",
            "completed_steps": ["collect_document"],
        },
    )
    assert report_created.status_code == 201
    report = report_created.json()["data"]
    report_id = report["id"]

    issue_created = client.post(
        "/api/requirements/issues/",
        headers=headers,
        json={
            "report": report_id,
            "module": module_id,
            "issue_type": "clarity",
            "priority": "medium",
            "title": "Clarify invoice rules",
            "description": "Billing module lacks invoice edge cases",
            "suggestion": "Add invalid invoice examples",
        },
    )
    assert issue_created.status_code == 201
    issue = issue_created.json()["data"]
    issue_id = issue["id"]

    issue_updated = client.patch(
        f"/api/requirements/issues/{issue_id}/",
        headers=headers,
        json={"is_resolved": True, "resolution_note": "Handled in v2"},
    )
    assert issue_updated.status_code == 200
    assert issue_updated.json()["data"]["is_resolved"] is True

    result_created = client.post(
        "/api/requirements/module-results/",
        headers=headers,
        json={
            "report": report_id,
            "module": module_id,
            "module_rating": "good",
            "issues_count": 1,
            "severity_score": 40,
            "analysis_content": "Module is mostly clear",
            "strengths": "Small scope",
            "weaknesses": "Few examples",
            "recommendations": "Expand examples",
        },
    )
    assert result_created.status_code == 201
    result = result_created.json()["data"]
    result_id = result["id"]

    report_detail = client.get(f"/api/requirements/reports/{report_id}/", headers=headers)
    assert report_detail.status_code == 200
    report_payload = report_detail.json()["data"]
    assert any(item["id"] == issue_id for item in report_payload["issues"])
    assert any(item["id"] == result_id for item in report_payload["module_results"])

    progress = client.get(f"/api/requirements/documents/{document_id}/review-progress/", headers=headers)
    assert progress.status_code == 200
    assert "task_id" in progress.json()["data"]

    deleted_result = client.delete(f"/api/requirements/module-results/{result_id}/", headers=headers)
    assert deleted_result.status_code == 200

    deleted_issue = client.delete(f"/api/requirements/issues/{issue_id}/", headers=headers)
    assert deleted_issue.status_code == 200

    deleted_report = client.delete(f"/api/requirements/reports/{report_id}/", headers=headers)
    assert deleted_report.status_code == 200

    deleted_module = client.delete(f"/api/requirements/modules/{module_id}/", headers=headers)
    assert deleted_module.status_code == 200

    deleted_document = client.delete(f"/api/requirements/documents/{document_id}/", headers=headers)
    assert deleted_document.status_code == 200
