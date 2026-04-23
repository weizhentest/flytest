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
            "name": f"UI Project {uuid4().hex[:8]}",
            "description": "ui automation fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_ui_automation_core_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    module_created = client.post(
        "/api/ui-automation/modules/",
        headers=headers,
        json={"project": project_id, "name": f"Portal {uuid4().hex[:6]}", "parent": None},
    )
    assert module_created.status_code == 201
    module_id = module_created.json()["data"]["id"]

    tree = client.get(f"/api/ui-automation/modules/tree/?project={project_id}", headers=headers)
    assert tree.status_code == 200
    assert any(item["id"] == module_id for item in tree.json()["data"])

    page_created = client.post(
        "/api/ui-automation/pages/",
        headers=headers,
        json={
            "project": project_id,
            "module": module_id,
            "name": f"Login Page {uuid4().hex[:6]}",
            "url": "https://example.test/login",
            "description": "login page",
        },
    )
    assert page_created.status_code == 201
    page_id = page_created.json()["data"]["id"]

    element_created = client.post(
        "/api/ui-automation/elements/",
        headers=headers,
        json={
            "page": page_id,
            "name": "username input",
            "locator_type": "css",
            "locator_value": "#username",
            "wait_time": 1,
            "is_iframe": False,
        },
    )
    assert element_created.status_code == 201
    element_id = element_created.json()["data"]["id"]

    page_steps_created = client.post(
        "/api/ui-automation/page-steps/",
        headers=headers,
        json={
            "project": project_id,
            "page": page_id,
            "module": module_id,
            "name": f"Login Action {uuid4().hex[:6]}",
            "description": "login page steps",
            "run_flow": "open -> type -> click",
            "flow_data": {},
        },
    )
    assert page_steps_created.status_code == 201
    page_steps_id = page_steps_created.json()["data"]["id"]

    detailed_updated = client.post(
        "/api/ui-automation/page-steps-detailed/batch_update/",
        headers=headers,
        json={
            "page_step": page_steps_id,
            "steps": [
                {
                    "step_type": 0,
                    "element_id": element_id,
                    "ope_key": "fill",
                    "ope_value": {"value": "admin"},
                    "description": "fill username",
                }
            ],
        },
    )
    assert detailed_updated.status_code == 200

    page_steps_execute = client.get(f"/api/ui-automation/page-steps/{page_steps_id}/execute-data/", headers=headers)
    assert page_steps_execute.status_code == 200
    assert len(page_steps_execute.json()["data"]["step_details"]) == 1

    testcase_created = client.post(
        "/api/ui-automation/testcases/",
        headers=headers,
        json={
            "project": project_id,
            "module": module_id,
            "name": f"Login Case {uuid4().hex[:6]}",
            "description": "ui test case",
            "level": "P1",
            "status": 0,
            "front_custom": [],
            "front_sql": [],
            "posterior_sql": [],
            "parametrize": [],
            "case_flow": "",
        },
    )
    assert testcase_created.status_code == 201
    testcase_id = testcase_created.json()["data"]["id"]

    case_steps_updated = client.post(
        "/api/ui-automation/case-steps/batch_update/",
        headers=headers,
        json={
            "test_case": testcase_id,
            "steps": [
                {
                    "page_step": page_steps_id,
                    "case_data": {},
                    "case_cache_data": {},
                    "case_cache_ass": {},
                    "switch_step_open_url": False,
                    "error_retry": 0,
                }
            ],
        },
    )
    assert case_steps_updated.status_code == 200

    testcase_execute = client.get(f"/api/ui-automation/testcases/{testcase_id}/execute-data/", headers=headers)
    assert testcase_execute.status_code == 200
    assert len(testcase_execute.json()["data"]["case_step_details"]) == 1

    execution_created = client.post(
        "/api/ui-automation/execution-records/",
        headers=headers,
        json={
            "test_case": testcase_id,
            "status": 2,
            "trigger_type": "manual",
            "environment": {"browser": "chromium"},
            "step_results": [{"status": "pass"}],
            "screenshots": ["/media/ui/demo.png"],
            "trace_data": {"events": []},
            "log": "ok",
            "start_time": "2026-04-03T10:00:00Z",
            "end_time": "2026-04-03T10:00:01Z",
            "duration": 1.0,
        },
    )
    assert execution_created.status_code == 201
    execution_id = execution_created.json()["data"]["id"]

    execution_trace = client.get(f"/api/ui-automation/execution-records/{execution_id}/trace/", headers=headers)
    assert execution_trace.status_code == 200
    assert execution_trace.json()["data"]["events"] == []

    public_data_created = client.post(
        "/api/ui-automation/public-data/",
        headers=headers,
        json={
            "project": project_id,
            "type": 0,
            "key": f"username_{uuid4().hex[:6]}",
            "value": "admin",
            "description": "shared username",
            "is_enabled": True,
        },
    )
    assert public_data_created.status_code == 201
    public_data_id = public_data_created.json()["data"]["id"]

    by_project = client.get(f"/api/ui-automation/public-data/by-project/{project_id}/", headers=headers)
    assert by_project.status_code == 200
    assert any(item["id"] if "id" in item else True for item in by_project.json()["data"])

    env_created = client.post(
        "/api/ui-automation/env-configs/",
        headers=headers,
        json={
            "project": project_id,
            "name": f"Test Env {uuid4().hex[:6]}",
            "base_url": "https://example.test",
            "browser": "chromium",
            "headless": True,
            "viewport_width": 1280,
            "viewport_height": 720,
            "timeout": 30000,
            "db_c_status": False,
            "db_rud_status": False,
            "mysql_config": {},
            "extra_config": {},
            "is_default": True,
        },
    )
    assert env_created.status_code == 201
    env_config_id = env_created.json()["data"]["id"]

    batch_created = client.post(
        "/api/ui-automation/batch-records/",
        headers=headers,
        json={
            "name": f"Batch {uuid4().hex[:6]}",
            "total_cases": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "status": 2,
            "trigger_type": "manual",
            "duration": 1.0,
        },
    )
    assert batch_created.status_code == 201
    batch_id = batch_created.json()["data"]["id"]

    actuator_list = client.get("/api/ui-automation/actuators/list_actuators/", headers=headers)
    assert actuator_list.status_code == 200
    actuator_status = client.get("/api/ui-automation/actuators/status/", headers=headers)
    assert actuator_status.status_code == 200
    assert "total_actuators" in actuator_status.json()["data"]

    screenshot_upload = client.post(
        "/api/ui-automation/screenshots/upload/",
        headers=headers,
        files={"file": ("shot.png", b"fake-png-bytes", "image/png")},
    )
    assert screenshot_upload.status_code == 201
    assert screenshot_upload.json()["status"] == "success"
    assert screenshot_upload.json()["url"].startswith("/media/ui_screenshots/")

    trace_upload = client.post(
        "/api/ui-automation/traces/upload/",
        headers=headers,
        files={"file": ("trace.zip", b"fake-zip-bytes", "application/zip")},
    )
    assert trace_upload.status_code == 201
    assert trace_upload.json()["status"] == "success"
    assert trace_upload.json()["path"].startswith("ui_traces/")

    client.delete(f"/api/ui-automation/batch-records/{batch_id}/", headers=headers)
    client.delete(f"/api/ui-automation/env-configs/{env_config_id}/", headers=headers)
    client.delete(f"/api/ui-automation/public-data/{public_data_id}/", headers=headers)
    client.delete(f"/api/ui-automation/execution-records/{execution_id}/", headers=headers)
    client.post("/api/ui-automation/testcases/batch-delete/", headers=headers, json={"ids": [testcase_id]})
    client.delete(f"/api/ui-automation/page-steps/{page_steps_id}/", headers=headers)
    client.delete(f"/api/ui-automation/elements/{element_id}/", headers=headers)
    client.delete(f"/api/ui-automation/pages/{page_id}/", headers=headers)
    client.delete(f"/api/ui-automation/modules/{module_id}/", headers=headers)
