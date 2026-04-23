import io
import os
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image


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


def _unwrap_data(payload):
    if isinstance(payload, dict) and "status" in payload and "data" in payload:
        return payload["data"]
    return payload


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def _auth_headers() -> dict[str, str]:
    response = client.post("/api/token/", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access']}"}


def _create_project(headers: dict[str, str]) -> int:
    response = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": f"Testcase Project {uuid4().hex[:8]}",
            "description": "testcases fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_testcases_core_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    module_created = client.post(
        f"/api/projects/{project_id}/testcase-modules/",
        headers=headers,
        json={"name": f"Auth {uuid4().hex[:6]}", "parent_id": None},
    )
    assert module_created.status_code == 201
    module = module_created.json()["data"]
    module_id = module["id"]

    testcase_created = client.post(
        f"/api/projects/{project_id}/testcases/",
        headers=headers,
        json={
            "name": f"Login case {uuid4().hex[:6]}",
            "precondition": "User exists",
            "level": "P1",
            "test_type": "functional",
            "module_id": module_id,
            "notes": "FastAPI testcase migration",
            "steps": [
                {"step_number": 1, "description": "Open login page", "expected_result": "Page opens"},
                {"step_number": 2, "description": "Submit credentials", "expected_result": "Login succeeds"},
            ],
        },
    )
    assert testcase_created.status_code == 201
    testcase = testcase_created.json()["data"]
    testcase_id = testcase["id"]

    listing = client.get(
        f"/api/projects/{project_id}/testcases/?module_id={module_id}&level=P1&test_type=functional",
        headers=headers,
    )
    assert listing.status_code == 200
    assert any(item["id"] == testcase_id for item in listing.json()["data"])

    testcase_detail = client.get(f"/api/projects/{project_id}/testcases/{testcase_id}/", headers=headers)
    assert testcase_detail.status_code == 200
    assert len(testcase_detail.json()["data"]["steps"]) == 2

    testcase_updated = client.patch(
        f"/api/projects/{project_id}/testcases/{testcase_id}/",
        headers=headers,
        json={
            "review_status": "approved",
            "steps": [
                {
                    "id": testcase_detail.json()["data"]["steps"][0]["id"],
                    "step_number": 1,
                    "description": "Open login page",
                    "expected_result": "Page opens",
                },
                {
                    "id": testcase_detail.json()["data"]["steps"][1]["id"],
                    "step_number": 2,
                    "description": "Submit credentials",
                    "expected_result": "Dashboard opens",
                },
            ],
        },
    )
    assert testcase_updated.status_code == 200
    assert testcase_updated.json()["data"]["review_status"] == "approved"

    suite_created = client.post(
        f"/api/projects/{project_id}/test-suites/",
        headers=headers,
        json={
            "name": f"Smoke Suite {uuid4().hex[:6]}",
            "description": "Suite for migrated testcase endpoints",
            "testcase_ids": [testcase_id],
            "max_concurrent_tasks": 1,
        },
    )
    assert suite_created.status_code == 201
    suite = suite_created.json()["data"]
    suite_id = suite["id"]

    suite_detail = client.get(f"/api/projects/{project_id}/test-suites/{suite_id}/", headers=headers)
    assert suite_detail.status_code == 200
    assert suite_detail.json()["data"]["testcase_count"] == 1

    suite_updated = client.patch(
        f"/api/projects/{project_id}/test-suites/{suite_id}/",
        headers=headers,
        json={"description": "Updated suite description"},
    )
    assert suite_updated.status_code == 200
    assert suite_updated.json()["data"]["description"] == "Updated suite description"

    suite_deleted = client.delete(f"/api/projects/{project_id}/test-suites/{suite_id}/", headers=headers)
    assert suite_deleted.status_code == 200

    screenshot_upload = client.post(
        f"/api/projects/{project_id}/testcases/{testcase_id}/upload-screenshots/",
        headers=headers,
        files={"screenshot": ("shot.png", _png_bytes(), "image/png")},
        data={"title": "Main shot", "description": "Screenshot for testcase"},
    )
    assert screenshot_upload.status_code == 201
    screenshots_payload = screenshot_upload.json()["data"]["screenshots"]
    assert len(screenshots_payload) == 1
    screenshot_id = screenshots_payload[0]["id"]

    screenshots = client.get(f"/api/projects/{project_id}/testcases/{testcase_id}/screenshots/", headers=headers)
    assert screenshots.status_code == 200
    assert any(item["id"] == screenshot_id for item in screenshots.json()["data"])

    export_excel = client.get(f"/api/projects/{project_id}/testcases/export-excel/", headers=headers)
    assert export_excel.status_code == 200
    assert "spreadsheetml" in (export_excel.headers.get("content-type") or "")

    screenshot_deleted = client.delete(
        f"/api/projects/{project_id}/testcases/{testcase_id}/screenshots/{screenshot_id}/",
        headers=headers,
    )
    assert screenshot_deleted.status_code == 200

    screenshot_upload2 = client.post(
        f"/api/projects/{project_id}/testcases/{testcase_id}/upload-screenshots/",
        headers=headers,
        files={"screenshot": ("shot2.png", _png_bytes(), "image/png")},
    )
    assert screenshot_upload2.status_code == 201
    screenshot_id_2 = screenshot_upload2.json()["data"]["screenshots"][0]["id"]

    screenshots_batch_deleted = client.post(
        f"/api/projects/{project_id}/testcases/{testcase_id}/screenshots/batch-delete/",
        headers=headers,
        json={"ids": [screenshot_id_2]},
    )
    assert screenshots_batch_deleted.status_code == 200
    assert screenshots_batch_deleted.json()["data"]["deleted_count"] == 1

    template_created = client.post(
        "/api/testcase-templates/",
        headers=headers,
        json={
            "name": f"Import Template {uuid4().hex[:6]}",
            "template_type": "import",
            "description": "template for import excel",
            "header_row": 1,
            "data_start_row": 2,
            "field_mappings": {
                "name": "name_col",
                "module": "module_col",
                "level": "level_col",
                "precondition": "precondition_col",
                "notes": "notes_col",
            },
            "value_transformations": {},
            "step_parsing_mode": "single_cell",
            "step_config": {
                "step_column": "steps_col",
                "expected_column": "expected_col",
            },
            "module_path_delimiter": "/",
            "is_active": True,
        },
    )
    assert template_created.status_code == 201
    template_id = template_created.json()["data"]["id"]

    import_excel = client.post(
        f"/api/projects/{project_id}/testcases/import-excel/",
        headers=headers,
        files={
            "file": (
                "import.xlsx",
                _xlsx_bytes(
                    [
                        ["name_col", "module_col", "level_col", "precondition_col", "notes_col", "steps_col", "expected_col"],
                        ["Imported testcase", "Imported/Module", "P2", "ready", "notes", "[1]click", "[1]done"],
                    ]
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"template_id": str(template_id)},
    )
    assert import_excel.status_code == 200
    import_payload = _unwrap_data(import_excel.json())
    assert import_payload["success"] is True
    assert import_payload["imported_count"] >= 1

    batch_deleted = client.post(
        f"/api/projects/{project_id}/testcases/batch-delete/",
        headers=headers,
        json={"ids": [testcase_id]},
    )
    assert batch_deleted.status_code == 200
    assert testcase_id in batch_deleted.json()["data"]["deleted_ids"]

    module_deleted = client.delete(f"/api/projects/{project_id}/testcase-modules/{module_id}/", headers=headers)
    assert module_deleted.status_code == 200


@patch("testcases.tasks.execute_test_suite.delay")
def test_testexecutions_core_flow(mock_delay) -> None:
    from django.utils import timezone
    from testcases.models import TestCaseResult, TestExecution

    mock_delay.return_value = type("TaskResult", (), {"id": "fake-celery-id"})()

    headers = _auth_headers()
    project_id = _create_project(headers)

    module_created = client.post(
        f"/api/projects/{project_id}/testcase-modules/",
        headers=headers,
        json={"name": f"Exec {uuid4().hex[:6]}", "parent_id": None},
    )
    assert module_created.status_code == 201
    module_id = module_created.json()["data"]["id"]

    testcase_created = client.post(
        f"/api/projects/{project_id}/testcases/",
        headers=headers,
        json={
            "name": f"Execution case {uuid4().hex[:6]}",
            "precondition": "Execution setup",
            "level": "P0",
            "test_type": "smoke",
            "module_id": module_id,
            "steps": [
                {"step_number": 1, "description": "Run test", "expected_result": "It passes"},
            ],
        },
    )
    assert testcase_created.status_code == 201
    testcase_id = testcase_created.json()["data"]["id"]

    suite_created = client.post(
        f"/api/projects/{project_id}/test-suites/",
        headers=headers,
        json={
            "name": f"Execution Suite {uuid4().hex[:6]}",
            "description": "Suite for execution endpoints",
            "testcase_ids": [testcase_id],
            "max_concurrent_tasks": 1,
        },
    )
    assert suite_created.status_code == 201
    suite_id = suite_created.json()["data"]["id"]

    execution_created = client.post(
        f"/api/projects/{project_id}/test-executions/",
        headers=headers,
        json={"suite_id": suite_id, "generate_playwright_script": False},
    )
    assert execution_created.status_code == 201
    execution_id = execution_created.json()["data"]["id"]
    assert execution_created.json()["data"]["celery_task_id"] == "fake-celery-id"

    executions = client.get(f"/api/projects/{project_id}/test-executions/", headers=headers)
    assert executions.status_code == 200
    assert any(item["id"] == execution_id for item in executions.json()["data"])

    execution_detail = client.get(f"/api/projects/{project_id}/test-executions/{execution_id}/", headers=headers)
    assert execution_detail.status_code == 200

    execution = TestExecution.objects.get(id=execution_id)
    now = timezone.now()
    execution.status = "completed"
    execution.started_at = now
    execution.completed_at = now
    execution.total_count = 1
    execution.passed_count = 1
    execution.failed_count = 0
    execution.skipped_count = 0
    execution.error_count = 0
    execution.save()

    TestCaseResult.objects.create(
        execution=execution,
        testcase_id=testcase_id,
        status="pass",
        started_at=now,
        completed_at=now,
        execution_time=1.25,
        screenshots=["/media/testcase_screenshots/demo.png"],
        execution_log="Execution completed",
    )

    results = client.get(f"/api/projects/{project_id}/test-executions/{execution_id}/results/", headers=headers)
    assert results.status_code == 200
    assert len(results.json()["data"]) == 1

    report = client.get(f"/api/projects/{project_id}/test-executions/{execution_id}/report/", headers=headers)
    assert report.status_code == 200
    report_payload = report.json()["data"]
    assert report_payload["statistics"]["passed"] == 1
    assert report_payload["results"][0]["status"] == "pass"

    cancel_created = client.post(
        f"/api/projects/{project_id}/test-executions/",
        headers=headers,
        json={"suite_id": suite_id, "generate_playwright_script": False},
    )
    assert cancel_created.status_code == 201
    cancel_execution_id = cancel_created.json()["data"]["id"]

    cancelled = client.post(f"/api/projects/{project_id}/test-executions/{cancel_execution_id}/cancel/", headers=headers)
    assert cancelled.status_code == 200

    deleted_completed = client.delete(f"/api/projects/{project_id}/test-executions/{execution_id}/", headers=headers)
    assert deleted_completed.status_code == 200

    deleted_cancelled = client.delete(f"/api/projects/{project_id}/test-executions/{cancel_execution_id}/", headers=headers)
    assert deleted_cancelled.status_code == 200

    client.delete(f"/api/projects/{project_id}/test-suites/{suite_id}/", headers=headers)
    client.post(f"/api/projects/{project_id}/testcases/batch-delete/", headers=headers, json={"ids": [testcase_id]})
    client.delete(f"/api/projects/{project_id}/testcase-modules/{module_id}/", headers=headers)
