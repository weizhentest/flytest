import importlib
import json
import os
import tempfile
import time
import unittest
import gc
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import jwt

import app.database as database
import app.reporting as reporting
from tests.testing_client import TestClient


class FakeExecutor:
    def __init__(self, **kwargs):
        self.default_package_name = kwargs.get("default_package_name", "")

    def count_total_steps(self, steps):
        return max(len(steps), 1)

    def has_action(self, steps, actions):
        return False

    def launch_default_app(self):
        return "launch default app"

    def run(self, steps, on_step_complete):
        total = max(len(steps), 1)
        for index, step in enumerate(steps, start=1):
            on_step_complete(index, total, step.get("name", f"step-{index}"), "ok")
        return {"passed_steps": len(steps), "total_steps": len(steps)}


class StopExecutor(FakeExecutor):
    def run(self, steps, on_step_complete):
        from app.execution_runtime import StopRequested

        raise StopRequested("stopped by test")


class StepFailureExecutor(FakeExecutor):
    def run(self, steps, on_step_complete):
        from app.execution_runtime import StepExecutionError

        raise StepExecutionError(1, "failing-step", ValueError("boom"))


class CrashExecutor(FakeExecutor):
    def run(self, steps, on_step_complete):
        raise RuntimeError("unexpected crash")


class SlowExecutor(FakeExecutor):
    def run(self, steps, on_step_complete):
        return {"passed_steps": 0, "total_steps": max(len(steps), 1)}


class FakeThread:
    def __init__(self, target=None, args=None, kwargs=None, daemon=None):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.daemon = daemon

    def start(self):
        return None


class InlineThread(FakeThread):
    def start(self):
        if self.target is not None:
            return self.target(*self.args, **self.kwargs)
        return None


class FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class AppApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.env_patcher = patch.dict(os.environ, {"APP_AUTOMATION_AUTH_DISABLED": "1"}, clear=False)
        self.env_patcher.start()
        self.patches = [
            patch.object(database, "DATA_DIR", self.data_dir),
            patch.object(database, "UPLOADS_DIR", self.data_dir / "uploads"),
            patch.object(database, "ELEMENT_UPLOADS_DIR", self.data_dir / "uploads" / "elements"),
            patch.object(database, "REPORTS_DIR", self.data_dir / "reports"),
            patch.object(database, "DB_PATH", self.data_dir / "app_automation.db"),
            patch.object(reporting, "REPORTS_DIR", self.data_dir / "reports"),
        ]
        for patcher in self.patches:
            patcher.start()

        database.init_storage()

        import app.main as main_module

        self.main_module = importlib.reload(main_module)
        self.client_cm = TestClient(self.main_module.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self):
        if hasattr(self, "client_cm"):
            self.client_cm.__exit__(None, None, None)
        if hasattr(self, "client"):
            del self.client
        if hasattr(self, "client_cm"):
            del self.client_cm
        if hasattr(self, "main_module"):
            del self.main_module
        if hasattr(self, "env_patcher"):
            self.env_patcher.stop()
        for patcher in reversed(getattr(self, "patches", [])):
            patcher.stop()
        gc.collect()
        for attempt in range(10):
            try:
                self.temp_dir.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                gc.collect()
                time.sleep(0.3)

    def create_package(self):
        response = self.client.post(
            "/packages/",
            json={
                "project_id": 1001,
                "name": "企业微信",
                "package_name": "com.tencent.wework",
                "activity_name": ".LaunchActivity",
                "platform": "android",
                "description": "smoke package",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create_test_case(self, name: str = "test-case", *, package_id: int | None = None, steps=None):
        if package_id is None:
            with database.connection() as conn:
                existing_package = database.fetch_one(
                    conn,
                    "SELECT id FROM packages WHERE project_id = ? AND package_name = ?",
                    (1001, "com.tencent.wework"),
                )
            package = {"id": existing_package["id"]} if existing_package else self.create_package()
        else:
            package = {"id": package_id}
        response = self.client.post(
            "/test-cases/",
            json={
                "project_id": 1001,
                "name": name,
                "description": "test case fixture",
                "package_id": package["id"],
                "ui_flow": {
                    "steps": steps
                    or [{"name": "save screenshot", "type": "snapshot", "config": {"name": "done"}}]
                },
                "variables": [],
                "tags": ["smoke"],
                "timeout": 60,
                "retry_count": 0,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create_element(self, name: str, element_type: str, selector_value: str, *, description: str = "", tags=None):
        response = self.client.post(
            "/elements/",
            json={
                "project_id": 1001,
                "name": name,
                "element_type": element_type,
                "selector_type": "text",
                "selector_value": selector_value,
                "description": description or name,
                "tags": tags or [],
                "config": {},
                "image_path": "",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def create_device_record(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, android_version, connection_type, ip_address, port,
                    locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("emulator-5554", "Pixel_6", "available", "14", "emulator", "", 5555, "", None, "{}", "", "", now, now, now),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def create_execution_fixture(self, *, case_name: str = "execution-case", steps=None, suite_name: str | None = None):
        flow_steps = steps or [{"name": "save screenshot", "type": "snapshot", "config": {"name": "done"}}]

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "enterprise-wechat", "com.tencent.wework", ".LaunchActivity", "android", "", now, now),
            )
            package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            suite_id = None
            if suite_name:
                conn.execute(
                    """
                    INSERT INTO test_suites (
                        project_id, name, description, execution_status, execution_result, passed_count, failed_count,
                        last_run_at, created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (1001, suite_name, "", "running", "", 0, 0, None, "tester", now, now),
                )
                suite_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO test_cases (
                    project_id, name, description, package_id, ui_flow, variables, tags,
                    timeout, retry_count, last_result, last_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    case_name,
                    "execution fixture",
                    package_id,
                    json.dumps({"steps": flow_steps}, ensure_ascii=False),
                    "[]",
                    "[]",
                    60,
                    0,
                    "",
                    None,
                    now,
                    now,
                ),
            )
            test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, android_version, connection_type, ip_address, port,
                    locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f"emulator-{test_case_id}", f"device-{test_case_id}", "available", "14", "emulator", "", 5555, "", None, "{}", "", "", now, now, now),
            )
            device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO executions (
                    project_id, test_case_id, test_suite_id, device_id, status, result, progress, trigger_mode,
                    triggered_by, logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                    started_at, finished_at, duration, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', '', 0, 'manual', ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
                """,
                (1001, test_case_id, suite_id, device_id, "smoke", now, now),
            )
            execution_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        return {
            "package_id": package_id,
            "suite_id": suite_id,
            "test_case_id": test_case_id,
            "device_id": device_id,
            "execution_id": execution_id,
        }

    def test_app_api_smoke_workflow(self):
        package = self.create_package()
        self.create_element("登录按钮", "button", "登录", description="登录提交按钮", tags=["登录"])
        self.create_element("首页消息入口", "button", "消息", description="首页消息入口", tags=["首页", "消息"])

        scene_response = self.client.post(
            "/ai/scene-plan/",
            json={
                "project_id": 1001,
                "prompt": "启动企业微信，点击登录按钮，校验首页消息入口存在，并截图",
                "package_id": package["id"],
                "current_case_name": "AI 登录",
                "current_description": "",
                "current_steps": [],
                "current_variables": [],
                "llm_config": None,
            },
        )
        self.assertEqual(scene_response.status_code, 200)
        plan = scene_response.json()["data"]
        step_types = [step["type"] for step in plan["steps"]]
        self.assertIn("launch_app", step_types)
        self.assertIn("touch", step_types)
        self.assertIn("assert_exists", step_types)
        self.assertIn("snapshot", step_types)

        step_response = self.client.post(
            "/ai/step-suggestion/",
            json={
                "project_id": 1001,
                "prompt": "输入登录账号",
                "package_id": package["id"],
                "current_case_name": "AI 登录",
                "current_description": "",
                "current_step": {"name": "", "type": "text", "config": {}},
                "current_steps": plan["steps"],
                "current_variables": [],
                "llm_config": None,
            },
        )
        self.assertEqual(step_response.status_code, 200)
        step_payload = step_response.json()["data"]
        self.assertEqual(step_payload["step"]["type"], "text")
        self.assertIn("text", step_payload["step"]["config"])

        case_response = self.client.post(
            "/test-cases/",
            json={
                "project_id": 1001,
                "name": "AI 登录场景",
                "description": "smoke case",
                "package_id": package["id"],
                "ui_flow": {"steps": plan["steps"], "name": plan["name"], "description": plan["description"]},
                "variables": plan["variables"],
                "tags": ["smoke"],
                "timeout": 60,
                "retry_count": 0,
            },
        )
        self.assertEqual(case_response.status_code, 200)
        case_id = case_response.json()["data"]["id"]

        device_id = self.create_device_record()
        with patch.object(self.main_module, "start_execution_thread") as mocked_start:
            execute_response = self.client.post(
                f"/test-cases/{case_id}/execute/",
                json={"device_id": device_id, "trigger_mode": "manual", "triggered_by": "smoke"},
            )
        self.assertEqual(execute_response.status_code, 200)
        self.assertTrue(mocked_start.called)

        manifest = {
            "name": "smoke-pack",
            "version": "1.0.0",
            "description": "smoke import",
            "author": "tester",
            "components": [
                {
                    "name": "点击元素",
                    "type": "touch",
                    "category": "interaction",
                    "description": "点击动作",
                    "schema": {"selector": "string"},
                    "default_config": {"selector_type": "element"},
                    "enabled": True,
                    "sort_order": 1,
                }
            ],
            "custom_components": [
                {
                    "name": "登录流程",
                    "type": "login_flow_component",
                    "description": "公共登录流程",
                    "schema": {},
                    "default_config": {},
                    "steps": [{"name": "点击登录", "type": "touch", "config": {"selector_type": "element", "selector": "登录按钮"}}],
                    "enabled": True,
                    "sort_order": 2,
                }
            ],
        }
        import_response = self.client.post(
            "/component-packages/import/",
            files={"file": ("smoke-pack.json", json.dumps(manifest, ensure_ascii=False).encode("utf-8"), "application/json")},
            data={"overwrite": "1"},
        )
        self.assertEqual(import_response.status_code, 200)
        import_payload = import_response.json()["data"]
        self.assertEqual(import_payload["package"]["name"], "smoke-pack")
        self.assertGreaterEqual(import_payload["counts"]["custom_created"], 1)

        export_response = self.client.get("/component-packages/export/", params={"export_format": "json", "name": "export-pack"})
        self.assertEqual(export_response.status_code, 200)
        export_payload = export_response.json()["data"]
        self.assertEqual(export_payload["filename"], "export-pack.json")
        self.assertGreaterEqual(export_payload["component_count"], 1)
        self.assertGreaterEqual(export_payload["custom_component_count"], 1)

    def test_execute_test_case_rejects_locked_device_before_creating_execution(self):
        test_case = self.create_test_case(name="locked-device-case")
        device_id = self.create_device_record()

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                ("existing-run", now, now, device_id),
            )

        with patch.object(self.main_module, "start_execution_thread") as mocked_start:
            response = self.client.post(
                f"/test-cases/{test_case['id']}/execute/",
                json={"device_id": device_id, "trigger_mode": "manual", "triggered_by": "smoke"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(mocked_start.called)

        with database.connection() as conn:
            executions = database.fetch_all(
                conn,
                "SELECT id FROM executions WHERE test_case_id = ?",
                (test_case["id"],),
            )

        self.assertEqual(executions, [])

    def test_run_test_suite_rejects_locked_device(self):
        test_case = self.create_test_case(name="suite-device-lock-case")
        suite_response = self.client.post(
            "/test-suites/",
            json={
                "project_id": 1001,
                "name": "locked-suite",
                "description": "suite fixture",
                "test_case_ids": [test_case["id"]],
            },
        )
        self.assertEqual(suite_response.status_code, 200)
        suite_id = suite_response.json()["data"]["id"]
        device_id = self.create_device_record()

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                ("existing-run", now, now, device_id),
            )

        response = self.client.post(
            f"/test-suites/{suite_id}/run/",
            json={"device_id": device_id, "triggered_by": "smoke", "package_name": ""},
        )

        self.assertEqual(response.status_code, 409)

        with database.connection() as conn:
            executions = database.fetch_all(
                conn,
                "SELECT id FROM executions WHERE test_suite_id = ?",
                (suite_id,),
            )

        self.assertEqual(executions, [])

    def test_stop_pending_execution_releases_device_and_blocks_late_start(self):
        fixture = self.create_execution_fixture(case_name="pending-stop-case")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                ("smoke", now, now, fixture["device_id"]),
            )

        response = self.client.post(f"/executions/{fixture['execution_id']}/stop/")
        self.assertEqual(response.status_code, 200)

        with patch.object(self.main_module, "AppFlowExecutor") as mocked_executor:
            self.main_module.run_execution(fixture["execution_id"])

        self.assertFalse(mocked_executor.called)

        with database.connection() as conn:
            execution = database.fetch_one(
                conn,
                "SELECT status, result, started_at FROM executions WHERE id = ?",
                (fixture["execution_id"],),
            )
            device = database.fetch_one(
                conn,
                "SELECT status, locked_by FROM devices WHERE id = ?",
                (fixture["device_id"],),
            )

        self.assertEqual(execution["status"], "stopped")
        self.assertEqual(execution["result"], "stopped")
        self.assertIsNone(execution["started_at"])
        self.assertEqual(device["status"], "available")
        self.assertEqual(device["locked_by"], "")

    def test_run_now_failure_reschedules_interval_task_after_lock_conflict(self):
        fixture = self.create_execution_fixture(case_name="scheduled-lock-case")

        create_response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "scheduled-lock-task",
                "description": "scheduled trigger",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": False,
                "notification_type": "",
                "notify_emails": [],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        task_payload = create_response.json()["data"]
        task_id = task_payload["id"]
        original_next_run = task_payload["next_run_time"]

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                ("existing-run", now, now, fixture["device_id"]),
            )

        response = self.client.post(f"/scheduled-tasks/{task_id}/run_now/", params={"triggered_by": "smoke"})
        self.assertEqual(response.status_code, 409)

        task_response = self.client.get(f"/scheduled-tasks/{task_id}/")
        self.assertEqual(task_response.status_code, 200)
        task_payload = task_response.json()["data"]

        self.assertEqual(task_payload["failed_runs"], 1)
        self.assertEqual(task_payload["last_result"]["status"], "failed")
        self.assertEqual(task_payload["status"], "ACTIVE")
        self.assertGreater(
            datetime.fromisoformat(task_payload["next_run_time"]),
            datetime.fromisoformat(original_next_run),
        )

    def test_upload_element_asset_reuses_duplicate_image_within_project(self):
        upload_response = self.client.post(
            "/elements/upload/",
            params={"project_id": 1001, "category": "common"},
            files={"file": ("duplicate.png", b"duplicate-image-content", "image/png")},
        )
        self.assertEqual(upload_response.status_code, 200)
        upload_payload = upload_response.json()["data"]
        self.assertFalse(upload_payload["duplicate"])
        self.assertTrue(upload_payload["image_path"].startswith("elements/common/project-1001/"))

        element_response = self.client.post(
            "/elements/",
            json={
                "project_id": 1001,
                "name": "duplicate-image-element",
                "element_type": "image",
                "selector_type": "image",
                "selector_value": upload_payload["image_path"],
                "description": "duplicate image element",
                "tags": [],
                "config": {
                    "file_hash": upload_payload["file_hash"],
                    "image_category": upload_payload["image_category"],
                    "image_path": upload_payload["image_path"],
                },
                "image_path": upload_payload["image_path"],
                "is_active": True,
            },
        )
        self.assertEqual(element_response.status_code, 200)
        element_payload = element_response.json()["data"]

        duplicate_response = self.client.post(
            "/elements/upload/",
            params={"project_id": 1001, "category": "common"},
            files={"file": ("duplicate.png", b"duplicate-image-content", "image/png")},
        )
        self.assertEqual(duplicate_response.status_code, 200)
        duplicate_payload = duplicate_response.json()["data"]
        self.assertTrue(duplicate_payload["duplicate"])
        self.assertEqual(duplicate_payload["image_path"], upload_payload["image_path"])
        self.assertEqual(duplicate_payload["existing_element"]["id"], element_payload["id"])

    def test_upload_element_asset_recovers_category_from_nested_asset_path(self):
        upload_response = self.client.post(
            "/elements/upload/",
            params={"project_id": 1001, "category": "common"},
            files={"file": ("legacy-duplicate.png", b"legacy-duplicate-image", "image/png")},
        )
        self.assertEqual(upload_response.status_code, 200)
        upload_payload = upload_response.json()["data"]

        element_response = self.client.post(
            "/elements/",
            json={
                "project_id": 1001,
                "name": "legacy-duplicate-image-element",
                "element_type": "image",
                "selector_type": "image",
                "selector_value": upload_payload["image_path"],
                "description": "legacy duplicate image element",
                "tags": [],
                "config": {
                    "file_hash": upload_payload["file_hash"],
                    "image_path": upload_payload["image_path"],
                },
                "image_path": upload_payload["image_path"],
                "is_active": True,
            },
        )
        self.assertEqual(element_response.status_code, 200)

        duplicate_response = self.client.post(
            "/elements/upload/",
            params={"project_id": 1001, "category": "common"},
            files={"file": ("legacy-duplicate.png", b"legacy-duplicate-image", "image/png")},
        )
        self.assertEqual(duplicate_response.status_code, 200)

        duplicate_payload = duplicate_response.json()["data"]
        self.assertTrue(duplicate_payload["duplicate"])
        self.assertEqual(duplicate_payload["image_category"], "common")

    def test_create_test_case_rejects_cross_project_package(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (2002, "cross-project-package", "com.example.cross", "", "android", "", now, now),
            )
            package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.post(
            "/test-cases/",
            json={
                "project_id": 1001,
                "name": "cross-project-case",
                "description": "should fail",
                "package_id": package_id,
                "ui_flow": {"steps": []},
                "variables": [],
                "tags": [],
                "timeout": 60,
                "retry_count": 0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_add_test_case_to_suite_rejects_cross_project_case(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO test_suites (
                    project_id, name, description, execution_status, execution_result, passed_count, failed_count,
                    last_run_at, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "suite-1001", "", "not_run", "", 0, 0, None, "tester", now, now),
            )
            suite_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_cases (
                    project_id, name, description, package_id, ui_flow, variables, tags,
                    timeout, retry_count, last_result, last_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (2002, "other-project-case", "", None, "{}", "[]", "[]", 60, 0, "", None, now, now),
            )
            test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.post(
            f"/test-suites/{suite_id}/add_test_case/",
            params={"test_case_id": test_case_id},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_health_endpoint_reports_scheduler_metadata(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]

        self.assertEqual(payload["service"], "app-automation")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["version"], self.main_module.app.version)
        self.assertTrue(payload["checked_at"])
        self.assertIn("scheduler", payload)
        self.assertIn("running", payload["scheduler"])
        self.assertIn("running_tasks", payload["scheduler"])
        self.assertIn("poll_interval_seconds", payload["scheduler"])

    def test_run_execution_completes_and_writes_report(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "企业微信", "com.tencent.wework", ".LaunchActivity", "android", "", now, now),
            )
            package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_cases (
                    project_id, name, description, package_id, ui_flow, variables, tags,
                    timeout, retry_count, last_result, last_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    "执行回归",
                    "run execution smoke",
                    package_id,
                    json.dumps({"steps": [{"name": "保存截图", "type": "snapshot", "config": {"name": "done"}}]}, ensure_ascii=False),
                    "[]",
                    "[]",
                    60,
                    0,
                    "",
                    None,
                    now,
                    now,
                ),
            )
            test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, android_version, connection_type, ip_address, port,
                    locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("emulator-5556", "Pixel_7", "available", "14", "emulator", "", 5555, "", None, "{}", "", "", now, now, now),
            )
            device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO executions (
                    project_id, test_case_id, test_suite_id, device_id, status, result, progress, trigger_mode,
                    triggered_by, logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                    started_at, finished_at, duration, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, 'pending', '', 0, 'manual', ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
                """,
                (1001, test_case_id, device_id, "smoke", now, now),
            )
            execution_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch.object(self.main_module, "AppFlowExecutor", FakeExecutor):
            self.main_module.run_execution(execution_id)

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (execution_id,))
            device = database.fetch_one(conn, "SELECT * FROM devices WHERE id = ?", (device_id,))
            test_case = database.fetch_one(conn, "SELECT * FROM test_cases WHERE id = ?", (test_case_id,))

        self.assertEqual(execution["status"], "completed")
        self.assertEqual(execution["result"], "passed")
        self.assertEqual(device["status"], "available")
        self.assertEqual(test_case["last_result"], "passed")
        report_index = Path(execution["report_path"]) / "index.html"
        self.assertTrue(report_index.exists())

    def test_run_execution_refreshes_suite_stats_on_success(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "企业微信", "com.tencent.wework", ".LaunchActivity", "android", "", now, now),
            )
            package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_suites (
                    project_id, name, description, execution_status, execution_result, passed_count, failed_count,
                    last_run_at, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "登录套件", "", "running", "", 0, 0, None, "tester", now, now),
            )
            suite_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_cases (
                    project_id, name, description, package_id, ui_flow, variables, tags,
                    timeout, retry_count, last_result, last_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    "套件执行成功",
                    "suite success smoke",
                    package_id,
                    json.dumps({"steps": [{"name": "保存截图", "type": "snapshot", "config": {"name": "done"}}]}, ensure_ascii=False),
                    "[]",
                    "[]",
                    60,
                    0,
                    "",
                    None,
                    now,
                    now,
                ),
            )
            test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, android_version, connection_type, ip_address, port,
                    locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("emulator-5558", "Pixel_8", "available", "14", "emulator", "", 5555, "", None, "{}", "", "", now, now, now),
            )
            device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO executions (
                    project_id, test_case_id, test_suite_id, device_id, status, result, progress, trigger_mode,
                    triggered_by, logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                    started_at, finished_at, duration, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', '', 0, 'manual', ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
                """,
                (1001, test_case_id, suite_id, device_id, "smoke", now, now),
            )
            execution_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch.object(self.main_module, "AppFlowExecutor", FakeExecutor):
            self.main_module.run_execution(execution_id)

        with database.connection() as conn:
            suite = database.fetch_one(conn, "SELECT * FROM test_suites WHERE id = ?", (suite_id,))

        self.assertEqual(suite["execution_status"], "completed")
        self.assertEqual(suite["execution_result"], "passed")
        self.assertEqual(suite["passed_count"], 1)
        self.assertEqual(suite["failed_count"], 0)

    def test_run_execution_refreshes_suite_stats_on_empty_steps_failure(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "企业微信", "com.tencent.wework", ".LaunchActivity", "android", "", now, now),
            )
            package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_suites (
                    project_id, name, description, execution_status, execution_result, passed_count, failed_count,
                    last_run_at, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "空步骤套件", "", "running", "", 0, 0, None, "tester", now, now),
            )
            suite_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO test_cases (
                    project_id, name, description, package_id, ui_flow, variables, tags,
                    timeout, retry_count, last_result, last_run_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    "空步骤失败",
                    "suite failure smoke",
                    package_id,
                    json.dumps({"steps": []}, ensure_ascii=False),
                    "[]",
                    "[]",
                    60,
                    0,
                    "",
                    None,
                    now,
                    now,
                ),
            )
            test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, name, status, android_version, connection_type, ip_address, port,
                    locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("emulator-5559", "Pixel_9", "available", "14", "emulator", "", 5555, "", None, "{}", "", "", now, now, now),
            )
            device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO executions (
                    project_id, test_case_id, test_suite_id, device_id, status, result, progress, trigger_mode,
                    triggered_by, logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                    started_at, finished_at, duration, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', '', 0, 'manual', ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
                """,
                (1001, test_case_id, suite_id, device_id, "smoke", now, now),
            )
            execution_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch.object(self.main_module, "AppFlowExecutor", FakeExecutor):
            self.main_module.run_execution(execution_id)

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (execution_id,))
            suite = database.fetch_one(conn, "SELECT * FROM test_suites WHERE id = ?", (suite_id,))

        self.assertEqual(execution["status"], "failed")
        self.assertEqual(suite["execution_status"], "completed")
        self.assertEqual(suite["execution_result"], "failed")
        self.assertEqual(suite["passed_count"], 0)
        self.assertEqual(suite["failed_count"], 1)

    def test_run_execution_updates_case_status_when_stopped(self):
        fixture = self.create_execution_fixture(case_name="stop-case", suite_name="stop-suite")

        with patch.object(self.main_module, "AppFlowExecutor", StopExecutor):
            self.main_module.run_execution(fixture["execution_id"])

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (fixture["execution_id"],))
            device = database.fetch_one(conn, "SELECT * FROM devices WHERE id = ?", (fixture["device_id"],))
            test_case = database.fetch_one(conn, "SELECT * FROM test_cases WHERE id = ?", (fixture["test_case_id"],))
            suite = database.fetch_one(conn, "SELECT * FROM test_suites WHERE id = ?", (fixture["suite_id"],))

        self.assertEqual(execution["status"], "stopped")
        self.assertEqual(execution["result"], "stopped")
        self.assertEqual(device["status"], "available")
        self.assertEqual(test_case["last_result"], "stopped")
        self.assertIsNotNone(test_case["last_run_at"])
        self.assertEqual(suite["execution_status"], "completed")
        self.assertEqual(suite["execution_result"], "stopped")

        suite_response = self.client.get(f"/test-suites/{fixture['suite_id']}/")
        self.assertEqual(suite_response.status_code, 200)
        self.assertEqual(suite_response.json()["data"]["stopped_count"], 1)

    def test_run_execution_updates_case_status_when_step_fails(self):
        fixture = self.create_execution_fixture(case_name="failed-case")

        with patch.object(self.main_module, "AppFlowExecutor", StepFailureExecutor):
            self.main_module.run_execution(fixture["execution_id"])

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (fixture["execution_id"],))
            device = database.fetch_one(conn, "SELECT * FROM devices WHERE id = ?", (fixture["device_id"],))
            test_case = database.fetch_one(conn, "SELECT * FROM test_cases WHERE id = ?", (fixture["test_case_id"],))

        self.assertEqual(execution["status"], "failed")
        self.assertEqual(execution["result"], "failed")
        self.assertEqual(device["status"], "available")
        self.assertEqual(test_case["last_result"], "failed")
        self.assertIsNotNone(test_case["last_run_at"])

    def test_run_execution_refreshes_suite_stats_on_unexpected_exception(self):
        fixture = self.create_execution_fixture(case_name="crash-case", suite_name="crash-suite")

        with patch.object(self.main_module, "AppFlowExecutor", CrashExecutor):
            self.main_module.run_execution(fixture["execution_id"])

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (fixture["execution_id"],))
            suite = database.fetch_one(conn, "SELECT * FROM test_suites WHERE id = ?", (fixture["suite_id"],))
            test_case = database.fetch_one(conn, "SELECT * FROM test_cases WHERE id = ?", (fixture["test_case_id"],))

        self.assertEqual(execution["status"], "failed")
        self.assertEqual(execution["result"], "failed")
        self.assertEqual(suite["execution_status"], "completed")
        self.assertEqual(suite["execution_result"], "failed")
        self.assertEqual(suite["passed_count"], 0)
        self.assertEqual(suite["failed_count"], 1)
        self.assertEqual(test_case["last_result"], "failed")
        self.assertIsNotNone(test_case["last_run_at"])

    def test_delete_execution_rejects_active_runs(self):
        fixture = self.create_execution_fixture(case_name="active-delete-case")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE executions SET status = 'running', started_at = ?, updated_at = ? WHERE id = ?",
                (now, now, fixture["execution_id"]),
            )
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                ("tester", now, now, fixture["device_id"]),
            )

        response = self.client.delete(f"/executions/{fixture['execution_id']}/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "执行仍在收尾中，请等待完成后再删除")

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT status FROM executions WHERE id = ?", (fixture["execution_id"],))
            device = database.fetch_one(conn, "SELECT status, locked_by FROM devices WHERE id = ?", (fixture["device_id"],))

        self.assertEqual(execution["status"], "running")
        self.assertEqual(device["status"], "locked")
        self.assertEqual(device["locked_by"], "tester")

    def test_delete_execution_allows_stopped_runs(self):
        fixture = self.create_execution_fixture(case_name="stopped-delete-case")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                "UPDATE executions SET status = 'stopped', result = 'stopped', finished_at = ?, updated_at = ? WHERE id = ?",
                (now, now, fixture["execution_id"]),
            )

        response = self.client.delete(f"/executions/{fixture['execution_id']}/")
        self.assertEqual(response.status_code, 200)

        with database.connection() as conn:
            execution = database.fetch_one(conn, "SELECT id FROM executions WHERE id = ?", (fixture["execution_id"],))

        self.assertIsNone(execution)

    def test_delete_test_suite_cleans_related_tasks_and_keeps_execution_history(self):
        fixture = self.create_execution_fixture(case_name="suite-delete-case", suite_name="suite-delete")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    project_id, name, description, task_type, trigger_type, cron_expression, interval_seconds, execute_at,
                    device_id, package_id, test_suite_id, test_case_id, notify_on_success, notify_on_failure,
                    notification_type, notify_emails, status, last_run_time, next_run_time, total_runs, successful_runs,
                    failed_runs, last_result, error_message, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, 0, 0, '{}', '', ?, ?, ?)
                """,
                (
                    1001,
                    "suite-cleanup-task",
                    "cleanup",
                    "TEST_SUITE",
                    "INTERVAL",
                    "",
                    3600,
                    None,
                    fixture["device_id"],
                    fixture["package_id"],
                    fixture["suite_id"],
                    None,
                    0,
                    1,
                    "email",
                    json.dumps(["qa@example.com"], ensure_ascii=False),
                    "ACTIVE",
                    now,
                    "tester",
                    now,
                    now,
                ),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """
                INSERT INTO notification_logs (
                    task_id, task_name, task_type, notification_type, actual_notification_type,
                    sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                    status, error_message, response_info, created_at, sent_at, retry_count, is_retried
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    "suite-cleanup-task",
                    "TEST_SUITE",
                    "task_execution",
                    "email",
                    "FlyTest",
                    "noreply@flytest.local",
                    json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                    "{}",
                    "suite cleanup notification",
                    "failed",
                    "fixture",
                    "{}",
                    now,
                    now,
                    0,
                    0,
                ),
            )
            log_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.delete(f"/test-suites/{fixture['suite_id']}/")
        self.assertEqual(response.status_code, 200)

        with database.connection() as conn:
            suite = database.fetch_one(conn, "SELECT id FROM test_suites WHERE id = ?", (fixture["suite_id"],))
            task = database.fetch_one(conn, "SELECT id FROM scheduled_tasks WHERE id = ?", (task_id,))
            execution = database.fetch_one(
                conn,
                "SELECT id, test_suite_id FROM executions WHERE id = ?",
                (fixture["execution_id"],),
            )
            notification = database.fetch_one(conn, "SELECT task_id FROM notification_logs WHERE id = ?", (log_id,))

        self.assertIsNone(suite)
        self.assertIsNone(task)
        self.assertIsNone(execution["test_suite_id"])
        self.assertIsNone(notification["task_id"])

    def test_run_now_returns_trigger_payload_and_notification_context(self):
        import app.extended_routes as extended_routes

        fixture = self.create_execution_fixture(case_name="scheduled-case")

        create_response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "scheduled-task",
                "description": "scheduled trigger",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": True,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        task_id = create_response.json()["data"]["id"]

        with patch.object(extended_routes, "Thread", FakeThread):
            response = self.client.post(f"/scheduled-tasks/{task_id}/run_now/", params={"triggered_by": "smoke"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["last_result"]["status"], "triggered")
        self.assertEqual(payload["last_result"]["triggered_by"], "smoke")
        self.assertTrue(payload["trigger_payload"]["execution_id"] > 0)
        self.assertEqual(payload["successful_runs"], 0)
        self.assertEqual(payload["failed_runs"], 0)

        with database.connection() as conn:
            execution = database.fetch_one(
                conn,
                "SELECT trigger_mode, package_id FROM executions WHERE id = ?",
                (payload["trigger_payload"]["execution_id"],),
            )

        self.assertEqual(execution["trigger_mode"], "scheduled")
        self.assertEqual(execution["package_id"], fixture["package_id"])

        log_response = self.client.get("/notification-logs/", params={"task_id": task_id})
        self.assertEqual(log_response.status_code, 200)
        logs = log_response.json()["data"]
        self.assertEqual(logs, [])

    def test_run_now_updates_task_statistics_after_execution_result(self):
        import app.extended_routes as extended_routes

        fixture = self.create_execution_fixture(case_name="scheduled-failed-case")

        create_response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "scheduled-result-task",
                "description": "scheduled trigger",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        task_id = create_response.json()["data"]["id"]

        with patch.object(extended_routes, "Thread", FakeThread):
            response = self.client.post(f"/scheduled-tasks/{task_id}/run_now/", params={"triggered_by": "smoke"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        execution_id = payload["trigger_payload"]["execution_id"]

        with patch.object(self.main_module, "AppFlowExecutor", CrashExecutor):
            extended_routes._run_case_task_in_background(
                task_id,
                execution_id,
                triggered_by="smoke",
                triggered_at=payload["last_result"]["triggered_at"],
            )

        task_response = self.client.get(f"/scheduled-tasks/{task_id}/")
        self.assertEqual(task_response.status_code, 200)
        task_payload = task_response.json()["data"]
        self.assertEqual(task_payload["successful_runs"], 0)
        self.assertEqual(task_payload["failed_runs"], 1)
        self.assertEqual(task_payload["last_result"]["status"], "failed")
        self.assertEqual(task_payload["last_result"]["execution_id"], execution_id)

        log_response = self.client.get("/notification-logs/", params={"task_id": task_id})
        self.assertEqual(log_response.status_code, 200)
        logs = log_response.json()["data"]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["status"], "failed")
        self.assertEqual(logs[0]["response_info"]["execution_id"], execution_id)
        self.assertEqual(logs[0]["response_info"]["triggered_by"], "smoke")

    def test_create_scheduled_task_rejects_cross_project_test_case(self):
        fixture = self.create_execution_fixture(case_name="cross-project-case")

        response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 2002,
                "name": "invalid-cross-project-task",
                "description": "",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": None,
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("测试用例", response.json()["detail"])

    def test_create_scheduled_task_rejects_invalid_package_id(self):
        fixture = self.create_execution_fixture(case_name="invalid-package-task")

        response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "invalid-package-task",
                "description": "",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": 999999,
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )

        self.assertEqual(response.status_code, 404)

        with database.connection() as conn:
            task = database.fetch_one(
                conn,
                "SELECT id FROM scheduled_tasks WHERE name = ?",
                ("invalid-package-task",),
            )

        self.assertIsNone(task)

    def test_create_scheduled_task_rejects_invalid_cron_expression(self):
        fixture = self.create_execution_fixture(case_name="invalid-cron-task")

        response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "invalid-cron-task",
                "description": "",
                "task_type": "TEST_CASE",
                "trigger_type": "CRON",
                "cron_expression": "not-a-cron",
                "interval_seconds": None,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "tester",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_update_scheduled_task_preserves_created_by(self):
        fixture = self.create_execution_fixture(case_name="scheduled-update-task")

        create_response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "scheduled-update-task",
                "description": "before edit",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "creator-user",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        task_id = create_response.json()["data"]["id"]

        update_response = self.client.put(
            f"/scheduled-tasks/{task_id}/",
            json={
                "project_id": 1001,
                "name": "scheduled-update-task",
                "description": "after edit",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 7200,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "editor-user",
            },
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["created_by"], "creator-user")

        with database.connection() as conn:
            row = database.fetch_one(conn, "SELECT created_by FROM scheduled_tasks WHERE id = ?", (task_id,))

        self.assertEqual(row["created_by"], "creator-user")

    def test_update_scheduled_task_preserves_current_mutable_status(self):
        fixture = self.create_execution_fixture(case_name="scheduled-status-race-task")

        create_response = self.client.post(
            "/scheduled-tasks/",
            json={
                "project_id": 1001,
                "name": "scheduled-status-race-task",
                "description": "before edit",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "creator-user",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        task_id = create_response.json()["data"]["id"]

        with database.connection() as conn:
            conn.execute(
                "UPDATE scheduled_tasks SET status = 'PAUSED', updated_at = ? WHERE id = ?",
                (database.utc_now(), task_id),
            )

        update_response = self.client.put(
            f"/scheduled-tasks/{task_id}/",
            json={
                "project_id": 1001,
                "name": "scheduled-status-race-task",
                "description": "after edit",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 7200,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "editor-user",
            },
        )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["data"]["status"], "PAUSED")

        with database.connection() as conn:
            row = database.fetch_one(conn, "SELECT status FROM scheduled_tasks WHERE id = ?", (task_id,))

        self.assertEqual(row["status"], "PAUSED")

    def test_update_terminal_scheduled_task_rejects_status_change(self):
        fixture = self.create_execution_fixture(case_name="terminal-status-task")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    project_id, name, description, task_type, trigger_type, cron_expression, interval_seconds, execute_at,
                    device_id, package_id, test_suite_id, test_case_id, notify_on_success, notify_on_failure,
                    notification_type, notify_emails, status, last_run_time, next_run_time, total_runs, successful_runs,
                    failed_runs, last_result, error_message, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    "terminal-status-task",
                    "terminal",
                    "TEST_CASE",
                    "INTERVAL",
                    "",
                    3600,
                    None,
                    fixture["device_id"],
                    fixture["package_id"],
                    None,
                    fixture["test_case_id"],
                    0,
                    1,
                    "email",
                    json.dumps(["qa@example.com"]),
                    "FAILED",
                    now,
                    None,
                    1,
                    0,
                    1,
                    "{}",
                    "boom",
                    "creator-user",
                    now,
                    now,
                ),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.put(
            f"/scheduled-tasks/{task_id}/",
            json={
                "project_id": 1001,
                "name": "terminal-status-task",
                "description": "edited",
                "task_type": "TEST_CASE",
                "trigger_type": "INTERVAL",
                "cron_expression": "",
                "interval_seconds": 3600,
                "execute_at": None,
                "device_id": fixture["device_id"],
                "package_id": fixture["package_id"],
                "test_suite_id": None,
                "test_case_id": fixture["test_case_id"],
                "notify_on_success": False,
                "notify_on_failure": True,
                "notification_type": "email",
                "notify_emails": ["qa@example.com"],
                "status": "ACTIVE",
                "created_by": "editor-user",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_pause_terminal_scheduled_task_rejects_request(self):
        fixture = self.create_execution_fixture(case_name="terminal-pause-task")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    project_id, name, description, task_type, trigger_type, cron_expression, interval_seconds, execute_at,
                    device_id, package_id, test_suite_id, test_case_id, notify_on_success, notify_on_failure,
                    notification_type, notify_emails, status, last_run_time, next_run_time, total_runs, successful_runs,
                    failed_runs, last_result, error_message, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1001,
                    "terminal-pause-task",
                    "terminal",
                    "TEST_CASE",
                    "ONCE",
                    "",
                    None,
                    now,
                    fixture["device_id"],
                    fixture["package_id"],
                    None,
                    fixture["test_case_id"],
                    0,
                    1,
                    "email",
                    json.dumps(["qa@example.com"]),
                    "COMPLETED",
                    now,
                    None,
                    1,
                    1,
                    0,
                    "{}",
                    "",
                    "creator-user",
                    now,
                    now,
                ),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.post(f"/scheduled-tasks/{task_id}/pause/")

        self.assertEqual(response.status_code, 409)
        self.assertIn("detail", response.json())

        with database.connection() as conn:
            row = database.fetch_one(conn, "SELECT status FROM scheduled_tasks WHERE id = ?", (task_id,))

        self.assertEqual(row["status"], "COMPLETED")

    def test_retry_notification_updates_response_info(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO notification_logs (
                    task_id, task_name, task_type, notification_type, actual_notification_type,
                    sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                    status, error_message, response_info, created_at, sent_at, retry_count, is_retried
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    "retry-task",
                    "TEST_CASE",
                    "task_execution",
                    "email",
                    "FlyTest",
                    "noreply@flytest.local",
                    json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                    "{}",
                    "failed notification",
                    "failed",
                    "network timeout",
                    "{}",
                    now,
                    None,
                    0,
                    0,
                ),
            )
            log_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.post(f"/notification-logs/{log_id}/retry/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["error_message"], "")
        self.assertTrue(payload["is_retried"])
        self.assertEqual(payload["retry_count"], 1)
        self.assertEqual(payload["response_info"]["retry_status"], "success")
        self.assertEqual(payload["response_info"]["retry_count"], 1)
        self.assertTrue(payload["response_info"]["retried_at"])

    def test_notification_logs_support_date_range_filter(self):
        with database.connection() as conn:
            conn.executemany(
                """
                INSERT INTO notification_logs (
                    task_id, task_name, task_type, notification_type, actual_notification_type,
                    sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                    status, error_message, response_info, created_at, sent_at, retry_count, is_retried
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        None,
                        "early-log",
                        "TEST_CASE",
                        "task_execution",
                        "email",
                        "FlyTest",
                        "noreply@flytest.local",
                        json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                        "{}",
                        "early notification",
                        "success",
                        "",
                        "{}",
                        "2026-04-01T08:00:00+00:00",
                        "2026-04-01T08:01:00+00:00",
                        0,
                        0,
                    ),
                    (
                        None,
                        "target-log",
                        "TEST_CASE",
                        "task_execution",
                        "email",
                        "FlyTest",
                        "noreply@flytest.local",
                        json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                        "{}",
                        "target notification",
                        "failed",
                        "timeout",
                        "{}",
                        "2026-04-03T09:00:00+00:00",
                        None,
                        0,
                        0,
                    ),
                ],
            )

        response = self.client.get(
            "/notification-logs/",
            params={"start_date": "2026-04-03", "end_date": "2026-04-03"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_name"], "target-log")

    def test_notification_logs_support_project_filter(self):
        with database.connection() as conn:
            conn.executemany(
                """
                INSERT INTO notification_logs (
                    project_id, task_id, task_name, task_type, notification_type, actual_notification_type,
                    sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                    status, error_message, response_info, created_at, sent_at, retry_count, is_retried
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        1001,
                        None,
                        "project-1001-log",
                        "TEST_CASE",
                        "task_execution",
                        "email",
                        "FlyTest",
                        "noreply@flytest.local",
                        json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                        "{}",
                        "project 1001 notification",
                        "success",
                        "",
                        "{}",
                        "2026-04-03T09:00:00+00:00",
                        None,
                        0,
                        0,
                    ),
                    (
                        2002,
                        None,
                        "project-2002-log",
                        "TEST_CASE",
                        "task_execution",
                        "email",
                        "FlyTest",
                        "noreply@flytest.local",
                        json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                        "{}",
                        "project 2002 notification",
                        "success",
                        "",
                        "{}",
                        "2026-04-03T10:00:00+00:00",
                        None,
                        0,
                        0,
                    ),
                ],
            )

        response = self.client.get("/notification-logs/", params={"project_id": 1001})
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["task_name"], "project-1001-log")

    def test_init_storage_backfills_notification_log_project_id_from_task(self):
        fixture = self.create_execution_fixture(case_name="backfill-log-case")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    project_id, name, description, task_type, trigger_type, cron_expression, interval_seconds, execute_at,
                    device_id, package_id, test_suite_id, test_case_id, notify_on_success, notify_on_failure,
                    notification_type, notify_emails, status, last_run_time, next_run_time, total_runs, successful_runs,
                    failed_runs, last_result, error_message, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 0, 0, '{}', '', ?, ?, ?)
                """,
                (
                    1001,
                    "legacy-task",
                    "",
                    "TEST_CASE",
                    "ONCE",
                    "",
                    None,
                    None,
                    fixture["device_id"],
                    fixture["package_id"],
                    None,
                    fixture["test_case_id"],
                    0,
                    1,
                    "email",
                    "[]",
                    "ACTIVE",
                    "tester",
                    now,
                    now,
                ),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO notification_logs (
                    project_id, task_id, task_name, task_type, notification_type, actual_notification_type,
                    sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                    status, error_message, response_info, created_at, sent_at, retry_count, is_retried
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    task_id,
                    "legacy-task-log",
                    "TEST_CASE",
                    "task_execution",
                    "email",
                    "FlyTest",
                    "noreply@flytest.local",
                    json.dumps([{"email": "qa@example.com"}], ensure_ascii=False),
                    "{}",
                    "legacy notification",
                    "success",
                    "",
                    "{}",
                    database.utc_now(),
                    None,
                    0,
                    0,
                ),
            )

        database.init_storage()

        with database.connection() as conn:
            log_row = database.fetch_one(
                conn,
                "SELECT project_id FROM notification_logs WHERE task_name = ?",
                ("legacy-task-log",),
            )

        self.assertIsNotNone(log_row)
        self.assertEqual(log_row["project_id"], 1001)

    def test_execution_report_uses_relative_artifact_link(self):
        fixture = self.create_execution_fixture(case_name="artifact-case")

        with database.connection() as conn:
            report_dir = reporting.ensure_reports_root(conn) / f"execution-{fixture['execution_id']}"
            artifact_dir = report_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_dir / "failed-step.png"
            artifact_path.write_bytes(b"fake-image")
            now = database.utc_now()
            conn.execute(
                """
                UPDATE executions
                SET logs = ?, report_summary = ?, status = 'failed', result = 'failed', finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        [
                            {
                                "timestamp": now,
                                "level": "error",
                                "message": "step failed",
                                "artifact": str(artifact_path),
                            }
                        ],
                        ensure_ascii=False,
                    ),
                    "artifact failure",
                    now,
                    now,
                    fixture["execution_id"],
                ),
            )
            report_path = reporting.write_execution_report(conn, fixture["execution_id"])

        index_html = (Path(report_path) / "index.html").read_text(encoding="utf-8")
        self.assertIn("artifacts/failed-step.png", index_html)
        self.assertNotIn(str(artifact_path), index_html)

class AppApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "data"
        self.secret = "app-automation-test-secret"
        self.env_patcher = patch.dict(
            os.environ,
            {
                "APP_AUTOMATION_AUTH_DISABLED": "0",
                "APP_AUTOMATION_JWT_SECRET": self.secret,
                "APP_AUTOMATION_DJANGO_BASE_URL": "http://permissions.local",
            },
            clear=False,
        )
        self.env_patcher.start()
        self.patches = [
            patch.object(database, "DATA_DIR", self.data_dir),
            patch.object(database, "UPLOADS_DIR", self.data_dir / "uploads"),
            patch.object(database, "ELEMENT_UPLOADS_DIR", self.data_dir / "uploads" / "elements"),
            patch.object(database, "REPORTS_DIR", self.data_dir / "reports"),
            patch.object(database, "DB_PATH", self.data_dir / "app_automation.db"),
            patch.object(reporting, "REPORTS_DIR", self.data_dir / "reports"),
        ]
        for patcher in self.patches:
            patcher.start()

        database.init_storage()

        import app.access_control as access_control
        import app.main as main_module

        self.mock_permissions = [
            {"codename": codename, "content_type": {"app_label": "app_automation"}}
            for codename in [
                "view_appautomationoverview",
                "view_appautomationdevice",
                "view_appautomationpackage",
                "view_appautomationelement",
                "view_appautomationscenebuilder",
                "view_appautomationtestcase",
                "view_appautomationsuite",
                "view_appautomationexecution",
                "view_appautomationscheduledtask",
                "view_appautomationnotification",
                "view_appautomationreport",
                "view_appautomationsettings",
            ]
        ]
        self.mock_projects = [{"id": 1001, "name": "project-1001"}]
        self.access_control_module = importlib.reload(access_control)
        self.main_module = importlib.reload(main_module)
        self.urlopen_patcher = patch.object(
            self.access_control_module.urllib_request,
            "urlopen",
            side_effect=self.fake_django_urlopen,
        )
        self.urlopen_patcher.start()
        self.client_cm = TestClient(self.main_module.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self):
        if hasattr(self, "client_cm"):
            self.client_cm.__exit__(None, None, None)
        if hasattr(self, "client"):
            del self.client
        if hasattr(self, "client_cm"):
            del self.client_cm
        if hasattr(self, "main_module"):
            del self.main_module
        if hasattr(self, "access_control_module"):
            del self.access_control_module
        if hasattr(self, "urlopen_patcher"):
            self.urlopen_patcher.stop()
        if hasattr(self, "env_patcher"):
            self.env_patcher.stop()
        for patcher in reversed(getattr(self, "patches", [])):
            patcher.stop()
        gc.collect()
        for attempt in range(10):
            try:
                self.temp_dir.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                gc.collect()
                time.sleep(0.3)

    def build_auth_header(self):
        token = jwt.encode({"user_id": 1, "username": "tester"}, self.secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def fake_django_urlopen(self, request, timeout=5):
        url = getattr(request, "full_url", str(request))
        if "/api/accounts/users/1/permissions/" in url:
            return FakeUrlopenResponse({"data": self.mock_permissions})
        if "/api/projects/" in url:
            return FakeUrlopenResponse({"data": self.mock_projects})
        raise AssertionError(f"Unexpected Django access-control URL: {url}")

    def test_public_health_remains_available(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_mutating_route_requires_authentication(self):
        response = self.client.post(
            "/settings/save/",
            json={
                "adb_path": "adb",
                "default_timeout": 180,
                "workspace_root": "",
                "auto_discover_on_open": True,
                "notes": "blocked",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_mutating_route_accepts_valid_bearer_token(self):
        response = self.client.post(
            "/settings/save/",
            headers=self.build_auth_header(),
            json={
                "adb_path": "adb",
                "default_timeout": 180,
                "workspace_root": "",
                "auto_discover_on_open": True,
                "notes": "authorized",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["default_timeout"], 180)
        self.assertEqual(payload["notes"], "authorized")

    def test_read_route_rejects_query_token(self):
        token = jwt.encode({"user_id": 1, "username": "query-user"}, self.secret, algorithm="HS256")

        response = self.client.get("/settings/current/", params={"token": token})

        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_mutating_route_rejects_query_token(self):
        token = jwt.encode({"user_id": 1, "username": "query-user"}, self.secret, algorithm="HS256")

        response = self.client.post(
            "/settings/save/",
            params={"token": token},
            json={
                "adb_path": "adb",
                "default_timeout": 120,
                "workspace_root": "",
                "auto_discover_on_open": True,
                "notes": "query-token-should-fail",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("detail", response.json())

    def test_project_scoped_list_filters_packages(self):
        with database.connection() as conn:
            now = database.utc_now()
            conn.executemany(
                """
                INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1001, "visible-package", "com.example.visible", "", "android", "", now, now),
                    (2002, "hidden-package", "com.example.hidden", "", "android", "", now, now),
                ],
            )

        response = self.client.get("/packages/", headers=self.build_auth_header())

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["project_id"], 1001)
        self.assertEqual(payload[0]["package_name"], "com.example.visible")

    def test_project_scoped_create_rejects_inaccessible_project(self):
        response = self.client.post(
            "/packages/",
            headers=self.build_auth_header(),
            json={
                "project_id": 2002,
                "name": "forbidden-package",
                "package_name": "com.example.forbidden",
                "activity_name": "",
                "platform": "android",
                "description": "",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

    def test_project_scoped_asset_url_allows_uploaded_asset_preview(self):
        upload_response = self.client.post(
            "/elements/upload/",
            headers=self.build_auth_header(),
            params={"project_id": 1001, "category": "common"},
            files={"file": ("preview.png", b"preview-image", "image/png")},
        )

        self.assertEqual(upload_response.status_code, 200)
        image_path = upload_response.json()["data"]["image_path"]
        self.assertTrue(image_path.startswith("elements/common/project-1001/"))

        asset_response = self.client.get(f"/elements/assets/{image_path}", headers=self.build_auth_header())

        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.content, b"preview-image")

    def test_legacy_asset_url_allows_accessible_element_reference(self):
        asset_path = "elements/common/legacy.png"
        file_path = database.ELEMENT_UPLOADS_DIR / "common" / "legacy.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"legacy-image")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO elements (
                    project_id, name, element_type, selector_type, selector_value, description,
                    tags, config, image_path, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "legacy-image", "image", "image", asset_path, "", "[]", "{}", asset_path, 1, now, now),
            )

        asset_response = self.client.get(f"/elements/assets/{asset_path}", headers=self.build_auth_header())

        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.content, b"legacy-image")

    def test_selector_only_image_element_supports_preview_and_asset_access(self):
        asset_path = "elements/common/selector-only.png"
        file_path = database.ELEMENT_UPLOADS_DIR / "common" / "selector-only.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"selector-only-image")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO elements (
                    project_id, name, element_type, selector_type, selector_value, description,
                    tags, config, image_path, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "selector-only-image", "image", "image", asset_path, "", "[]", "{}", "", 1, now, now),
            )
            element_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        asset_response = self.client.get(f"/elements/assets/{asset_path}", headers=self.build_auth_header())
        preview_response = self.client.get(f"/elements/{element_id}/preview/", headers=self.build_auth_header())

        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(asset_response.content, b"selector-only-image")
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(preview_response.content, b"selector-only-image")

    def test_project_scoped_asset_url_rejects_inaccessible_project_file(self):
        file_path = database.ELEMENT_UPLOADS_DIR / "common" / "project-2002" / "secret.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"secret-image")

        response = self.client.get("/elements/assets/elements/common/project-2002/secret.png", headers=self.build_auth_header())

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

    def test_preview_element_rejects_cross_project_asset_reference(self):
        asset_path = "elements/common/project-2002/secret.png"
        file_path = database.ELEMENT_UPLOADS_DIR / "common" / "project-2002" / "secret.png"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"secret-image")

        with database.connection() as conn:
            now = database.utc_now()
            conn.execute(
                """
                INSERT INTO elements (
                    project_id, name, element_type, selector_type, selector_value, description,
                    tags, config, image_path, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (1001, "cross-project-preview", "image", "image", asset_path, "", "[]", "{}", asset_path, 1, now, now),
            )
            element_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        response = self.client.get(f"/elements/{element_id}/preview/", headers=self.build_auth_header())

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

    def test_create_element_rejects_cross_project_image_path(self):
        asset_path = "elements/common/project-2002/secret.png"

        response = self.client.post(
            "/elements/",
            headers=self.build_auth_header(),
            json={
                "project_id": 1001,
                "name": "cross-project-image",
                "element_type": "image",
                "selector_type": "image",
                "selector_value": asset_path,
                "description": "cross project asset",
                "tags": [],
                "config": {"image_path": asset_path},
                "image_path": asset_path,
                "is_active": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_image_categories_are_scoped_by_project(self):
        self.mock_projects = [
            {"id": 1001, "name": "project-1001"},
            {"id": 2002, "name": "project-2002"},
        ]
        headers = self.build_auth_header()

        create_1001 = self.client.post(
            "/elements/image-categories/create/",
            headers=headers,
            json={"project_id": 1001, "name": "shared"},
        )
        create_2002 = self.client.post(
            "/elements/image-categories/create/",
            headers=headers,
            json={"project_id": 2002, "name": "shared"},
        )
        self.assertEqual(create_1001.status_code, 200)
        self.assertEqual(create_2002.status_code, 200)

        upload_1001 = self.client.post(
            "/elements/upload/",
            headers=headers,
            params={"project_id": 1001, "category": "shared"},
            files={"file": ("shared-1001.png", b"project-1001", "image/png")},
        )
        upload_2002 = self.client.post(
            "/elements/upload/",
            headers=headers,
            params={"project_id": 2002, "category": "shared"},
            files={"file": ("shared-2002.png", b"project-2002", "image/png")},
        )
        self.assertEqual(upload_1001.status_code, 200)
        self.assertEqual(upload_2002.status_code, 200)

        response_1001 = self.client.get(
            "/elements/image-categories/",
            headers=headers,
            params={"project_id": 1001},
        )
        response_2002 = self.client.get(
            "/elements/image-categories/",
            headers=headers,
            params={"project_id": 2002},
        )
        self.assertEqual(response_1001.status_code, 200)
        self.assertEqual(response_2002.status_code, 200)

        categories_1001 = {item["name"]: item["count"] for item in response_1001.json()["data"]}
        categories_2002 = {item["name"]: item["count"] for item in response_2002.json()["data"]}

        self.assertEqual(categories_1001.get("shared"), 1)
        self.assertEqual(categories_2002.get("shared"), 1)
        self.assertIn("common", categories_1001)
        self.assertIn("common", categories_2002)

    def test_delete_image_category_only_removes_current_project_directory(self):
        self.mock_projects = [
            {"id": 1001, "name": "project-1001"},
            {"id": 2002, "name": "project-2002"},
        ]
        headers = self.build_auth_header()

        for project_id in (1001, 2002):
            response = self.client.post(
                "/elements/image-categories/create/",
                headers=headers,
                json={"project_id": project_id, "name": "shared"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.delete(
            "/elements/image-categories/shared/",
            headers=headers,
            params={"project_id": 1001},
        )
        self.assertEqual(response.status_code, 200)

        with database.connection() as conn:
            project_1001_dir = database.ELEMENT_UPLOADS_DIR / "shared" / "project-1001"
            project_2002_dir = database.ELEMENT_UPLOADS_DIR / "shared" / "project-2002"
            self.assertFalse(project_1001_dir.exists())
            self.assertTrue(project_2002_dir.exists())

        response_1001 = self.client.get(
            "/elements/image-categories/",
            headers=headers,
            params={"project_id": 1001},
        )
        response_2002 = self.client.get(
            "/elements/image-categories/",
            headers=headers,
            params={"project_id": 2002},
        )
        categories_1001 = {item["name"]: item["count"] for item in response_1001.json()["data"]}
        categories_2002 = {item["name"]: item["count"] for item in response_2002.json()["data"]}

        self.assertNotIn("shared", categories_1001)
        self.assertEqual(categories_2002.get("shared"), 0)

    def test_mutating_route_accepts_access_cookie(self):
        token = jwt.encode({"user_id": 1, "username": "cookie-user"}, self.secret, algorithm="HS256")
        self.client.cookies.set("flytest_access_token", token)

        response = self.client.post(
            "/settings/save/",
            json={
                "adb_path": "adb",
                "default_timeout": 240,
                "workspace_root": "",
                "auto_discover_on_open": True,
                "notes": "cookie-authorized",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["default_timeout"], 240)
        self.assertEqual(payload["notes"], "cookie-authorized")


if __name__ == "__main__":
    unittest.main()
