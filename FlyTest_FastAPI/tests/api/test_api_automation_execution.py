import os
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch
import json

import httpx
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "FlyTest_FastAPI"))
sys.path.insert(0, str(REPO_ROOT / "FlyTest_Django"))

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
            "name": f"API Execution Project {uuid4().hex[:8]}",
            "description": "api automation execution fastapi migration test",
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
def test_api_automation_execution_and_report_flow(mock_client_cls) -> None:
    mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"CMS {uuid4().hex[:6]}", "parent": None},
    )
    assert collection.status_code == 201
    collection_id = collection.json()["data"]["id"]

    environment = client.post(
        "/api/api-automation/environments/",
        headers=headers,
        json={
            "project": project_id,
            "name": f"Exec Env {uuid4().hex[:6]}",
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
    assert environment.status_code == 201
    environment_id = environment.json()["data"]["id"]

    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Get Profile {uuid4().hex[:6]}",
            "description": "execution request",
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
    assert request_response.status_code == 201
    request_id = request_response.json()["data"]["id"]

    executed = client.post(
        f"/api/api-automation/requests/{request_id}/execute/",
        headers=headers,
        json={"environment_id": environment_id},
    )
    assert executed.status_code == 200
    record = executed.json()["data"]
    record_id = record["id"]
    assert record["status"] in {"success", "failed", "error"}

    records = client.get(
        f"/api/api-automation/execution-records/?project={project_id}&collection={collection_id}",
        headers=headers,
    )
    assert records.status_code == 200
    assert any(item["id"] == record_id for item in records.json()["data"])

    detail = client.get(f"/api/api-automation/execution-records/{record_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == record_id

    report = client.get(
        f"/api/api-automation/execution-records/report/?project={project_id}&collection={collection_id}&days=30",
        headers=headers,
    )
    assert report.status_code == 200
    report_payload = report.json()["data"]
    assert report_payload["summary"]["total_count"] >= 1

    report_summary = client.post(
        "/api/api-automation/execution-records/report-summary/",
        headers=headers,
        json={"project": project_id, "collection": collection_id, "days": 30},
    )
    assert report_summary.status_code == 200
    assert report_summary.json()["data"]["summary"]


@patch("api_automation.execution.httpx.Client")
def test_api_automation_test_case_crud_and_execute_flow(mock_client_cls) -> None:
    mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"TC {uuid4().hex[:6]}", "parent": None},
    )
    collection_id = collection.json()["data"]["id"]

    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Request {uuid4().hex[:6]}",
            "description": "test case request",
            "method": "GET",
            "url": "/api/testcase/profile",
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
            "description": "fastapi test case",
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

    updated = client.patch(
        f"/api/api-automation/test-cases/{test_case_id}/",
        headers=headers,
        json={"status": "disabled"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "disabled"

    executed = client.post(
        f"/api/api-automation/test-cases/{test_case_id}/execute/",
        headers=headers,
        json={},
    )
    assert executed.status_code == 200
    assert executed.json()["data"]["test_case"] == test_case_id

    deleted = client.delete(f"/api/api-automation/test-cases/{test_case_id}/", headers=headers)
    assert deleted.status_code == 200


@patch("api_automation.views._start_import_job")
def test_api_automation_import_document_and_import_jobs_flow(_mock_start_import_job) -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"Import {uuid4().hex[:6]}", "parent": None},
    )
    collection_id = collection.json()["data"]["id"]

    markdown = b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```"

    sync_import = client.post(
        "/api/api-automation/requests/import-document/",
        headers=headers,
        data={
            "collection_id": str(collection_id),
            "generate_test_cases": "false",
            "enable_ai_parse": "false",
            "async_mode": "false",
        },
        files={"file": ("api.md", markdown, "text/markdown")},
    )
    assert sync_import.status_code == 201
    assert sync_import.json()["data"]["created_count"] == 1

    async_import = client.post(
        "/api/api-automation/requests/import-document/",
        headers=headers,
        data={
            "collection_id": str(collection_id),
            "generate_test_cases": "false",
            "enable_ai_parse": "false",
            "async_mode": "true",
        },
        files={"file": ("api.md", markdown, "text/markdown")},
    )
    assert async_import.status_code == 202
    job_id = async_import.json()["data"]["id"]

    jobs = client.get(f"/api/api-automation/import-jobs/?project={project_id}", headers=headers)
    assert jobs.status_code == 200
    assert any(item["id"] == job_id for item in jobs.json()["data"])

    detail = client.get(f"/api/api-automation/import-jobs/{job_id}/", headers=headers)
    assert detail.status_code == 200

    canceled = client.post(f"/api/api-automation/import-jobs/{job_id}/cancel/", headers=headers)
    assert canceled.status_code == 200
    assert canceled.json()["data"]["cancel_requested"] is True


@patch("api_automation.views._start_case_generation_apply")
@patch("api_automation.views._start_case_generation_job")
@patch("api_automation.views.generate_test_case_drafts_with_ai")
def test_api_automation_case_generation_job_and_legacy_generation_flow(
    mock_generate,
    _mock_start_case_generation_job,
    _mock_start_case_generation_apply,
) -> None:
    from api_automation.ai_case_generator import AITestCaseGenerationResult, GeneratedCaseDraft
    from api_automation.models import ApiCaseGenerationJob

    headers = _auth_headers()
    project_id = _create_project(headers)

    collection = client.post(
        "/api/api-automation/collections/",
        headers=headers,
        json={"project": project_id, "name": f"Gen {uuid4().hex[:6]}", "parent": None},
    )
    collection_id = collection.json()["data"]["id"]

    request_response = client.post(
        "/api/api-automation/requests/",
        headers=headers,
        json={
            "collection": collection_id,
            "name": f"Generate {uuid4().hex[:6]}",
            "description": "generation request",
            "method": "POST",
            "url": "/api/orders",
            "headers": {},
            "params": {},
            "body_type": "json",
            "body": {"sku": "A100"},
            "assertions": [{"type": "status_code", "expected": 200}],
            "timeout_ms": 30000,
            "order": 0,
        },
    )
    request_id = request_response.json()["data"]["id"]

    mock_generate.return_value = AITestCaseGenerationResult(
        used_ai=True,
        note="AI generated preview candidate",
        prompt_name="API自动化用例生成",
        prompt_source="builtin_fallback",
        model_name="demo-model",
        case_summaries=[
            {
                "name": "Generated case",
                "status": "ready",
                "tags": ["ai-generated"],
                "assertion_count": 1,
                "extractor_count": 0,
                "assertion_types": ["status_code"],
                "extractor_variables": [],
                "override_sections": [],
                "body_mode": "json",
            }
        ],
        cases=[
            GeneratedCaseDraft(
                name="Generated case",
                description="preview",
                status="ready",
                tags=["ai-generated"],
                assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                extractors=[],
                request_overrides={},
            )
        ],
    )

    legacy = client.post(
        "/api/api-automation/requests/generate-test-cases/",
        headers=headers,
        json={"scope": "selected", "ids": [request_id], "mode": "generate", "count_per_request": 1},
    )
    assert legacy.status_code == 200
    assert legacy.json()["data"]["created_testcase_count"] == 1

    job_create = client.post(
        "/api/api-automation/case-generation-jobs/",
        headers=headers,
        json={"scope": "selected", "ids": [request_id], "mode": "regenerate", "count_per_request": 1},
    )
    assert job_create.status_code == 202
    job_id = job_create.json()["data"]["id"]

    jobs = client.get(f"/api/api-automation/case-generation-jobs/?project={project_id}", headers=headers)
    assert jobs.status_code == 200
    assert any(item["id"] == job_id for item in jobs.json()["data"])

    detail = client.get(f"/api/api-automation/case-generation-jobs/{job_id}/", headers=headers)
    assert detail.status_code == 200

    canceled = client.post(f"/api/api-automation/case-generation-jobs/{job_id}/cancel/", headers=headers)
    assert canceled.status_code == 200

    preview_job = ApiCaseGenerationJob.objects.get(pk=job_id)
    preview_job.status = "preview_ready"
    preview_job.save(update_fields=["status"])
    applied = client.post(f"/api/api-automation/case-generation-jobs/{job_id}/apply/", headers=headers)
    assert applied.status_code == 202
