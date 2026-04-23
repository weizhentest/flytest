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
            "name": f"API Job Project {uuid4().hex[:8]}",
            "description": "api automation job migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def _create_collection(headers: dict[str, str], project_id: int) -> int:
    response = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"Job CMS {uuid4().hex[:6]}", "parent": None},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_api_automation_import_document_sync_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    collection_id = _create_collection(headers, project_id)

    content = b"## Login\nPOST /api/login\n```json\n{\"phone\": \"{{phone}}\", \"password\": \"{{password}}\"}\n```"
    response = client.post(
        "/api/api-automation/requests/import-document/",
        headers=headers,
        data={
            "collection_id": str(collection_id),
            "generate_test_cases": "true",
            "enable_ai_parse": "false",
            "async_mode": "false",
        },
        files={"file": ("api.md", content, "text/markdown")},
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["created_count"] >= 1
    assert "environment_suggestions" in payload


@patch("api_automation.views._start_import_job")
def test_api_automation_import_job_async_and_cancel(mock_start_job) -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    collection_id = _create_collection(headers, project_id)

    response = client.post(
        "/api/api-automation/requests/import-document/",
        headers=headers,
        data={
            "collection_id": str(collection_id),
            "generate_test_cases": "true",
            "enable_ai_parse": "false",
            "async_mode": "true",
        },
        files={"file": ("api.md", b"## Login\nPOST /api/login", "text/markdown")},
    )
    assert response.status_code == 202
    job = response.json()["data"]
    job_id = job["id"]

    detail = client.get(f"/api/api-automation/import-jobs/{job_id}/", headers=headers)
    assert detail.status_code == 200

    listing = client.get(f"/api/api-automation/import-jobs/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == job_id for item in listing.json()["data"])

    cancelled = client.post(f"/api/api-automation/import-jobs/{job_id}/cancel/", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["cancel_requested"] is True
    mock_start_job.assert_called_once()


@patch("api_automation.views._start_case_generation_job")
def test_api_automation_case_generation_job_flow(mock_start_job) -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    collection_id = _create_collection(headers, project_id)
    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Generate User {uuid4().hex[:6]}",
            "description": "request for generation job",
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
        "/api/api-automation/case-generation-jobs/",
        headers=headers,
        json={
            "scope": "selected",
            "ids": [request_id],
            "mode": "regenerate",
            "count_per_request": 1,
        },
    )
    assert created.status_code == 202
    job = created.json()["data"]
    job_id = job["id"]

    detail = client.get(f"/api/api-automation/case-generation-jobs/{job_id}/", headers=headers)
    assert detail.status_code == 200

    listing = client.get(f"/api/api-automation/case-generation-jobs/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == job_id for item in listing.json()["data"])

    cancelled = client.post(f"/api/api-automation/case-generation-jobs/{job_id}/cancel/", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["cancel_requested"] is True
    mock_start_job.assert_called_once()


@patch("api_automation.views._start_case_generation_apply")
@patch("api_automation.views._start_case_generation_job")
@patch("api_automation.views.generate_test_case_drafts_with_ai")
def test_api_automation_case_generation_job_apply_flow(mock_generate, mock_start_job, mock_start_apply) -> None:
    from api_automation.ai_case_generator import AITestCaseGenerationResult, GeneratedCaseDraft
    from api_automation.views import _apply_case_generation_job, _run_case_generation_job

    mock_generate.return_value = AITestCaseGenerationResult(
        used_ai=True,
        note="AI generated preview candidate",
        prompt_name="API自动化用例生成",
        prompt_source="builtin_fallback",
        model_name="demo-model",
        case_summaries=[
            {
                "name": "Create order - regenerated",
                "status": "ready",
                "tags": ["ai-generated"],
                "assertion_count": 1,
                "extractor_count": 0,
                "assertion_types": ["status_code"],
                "extractor_variables": [],
                "override_sections": [],
                "body_mode": "none",
            }
        ],
        cases=[
            GeneratedCaseDraft(
                name="Create order - regenerated",
                description="Preview replacement",
                status="ready",
                tags=["ai-generated"],
                assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                extractors=[],
                request_overrides={},
            )
        ],
    )

    headers = _auth_headers()
    project_id = _create_project(headers)
    collection_id = _create_collection(headers, project_id)
    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Generate Apply User {uuid4().hex[:6]}",
            "description": "request for generation apply job",
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
        "/api/api-automation/case-generation-jobs/",
        headers=headers,
        json={"scope": "selected", "ids": [request_id], "mode": "regenerate", "count_per_request": 1},
    )
    assert created.status_code == 202
    job_id = created.json()["data"]["id"]
    _run_case_generation_job(job_id)

    applied = client.post(f"/api/api-automation/case-generation-jobs/{job_id}/apply/", headers=headers)
    assert applied.status_code == 202
    _apply_case_generation_job(job_id)

    detail = client.get(f"/api/api-automation/case-generation-jobs/{job_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "success"
    mock_start_job.assert_called_once()
    mock_start_apply.assert_called_once()


@patch("api_automation.views.generate_test_case_drafts_with_ai")
def test_api_automation_generate_test_cases_legacy_endpoint(mock_generate) -> None:
    from api_automation.ai_case_generator import AITestCaseGenerationResult, GeneratedCaseDraft

    mock_generate.return_value = AITestCaseGenerationResult(
        used_ai=True,
        note="AI generated cases",
        prompt_name="API自动化用例生成",
        prompt_source="builtin_fallback",
        model_name="demo-model",
        case_summaries=[
            {
                "name": "Create order - generated",
                "status": "ready",
                "tags": ["ai-generated"],
                "assertion_count": 1,
                "extractor_count": 0,
                "assertion_types": ["status_code"],
                "extractor_variables": [],
                "override_sections": [],
                "body_mode": "none",
            }
        ],
        cases=[
            GeneratedCaseDraft(
                name="Create order - generated",
                description="Generated case",
                status="ready",
                tags=["ai-generated"],
                assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                extractors=[],
                request_overrides={},
            )
        ],
    )

    headers = _auth_headers()
    project_id = _create_project(headers)
    collection_id = _create_collection(headers, project_id)
    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Generate Legacy User {uuid4().hex[:6]}",
            "description": "request for legacy generation endpoint",
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

    generated = client.post(
        "/api/api-automation/requests/generate-test-cases/",
        headers=headers,
        json={"scope": "selected", "ids": [request_id], "mode": "generate", "count_per_request": 1},
    )
    assert generated.status_code == 200
    payload = generated.json()["data"]
    assert payload["total_requests"] == 1
    assert payload["created_testcase_count"] == 1
