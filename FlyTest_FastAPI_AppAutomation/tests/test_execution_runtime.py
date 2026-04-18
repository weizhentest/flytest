import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.execution_runtime import AppFlowExecutor


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200, headers=None):
        self._payload = json.dumps(payload).encode("utf-8")
        self._status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self._status_code

    def read(self):
        return self._payload


class ExecutionRuntimeTests(unittest.TestCase):
    def create_executor(self):
        temp_dir = tempfile.TemporaryDirectory()
        report_dir = Path(temp_dir.name) / "report"
        artifact_dir = report_dir / "artifacts"
        executor = AppFlowExecutor(
            adb_path="adb",
            device_serial="emulator-5554",
            project_id=1001,
            report_dir=report_dir,
            artifact_dir=artifact_dir,
        )
        return temp_dir, executor

    def test_flow_control_and_variable_outputs_work_together(self):
        temp_dir, executor = self.create_executor()
        try:
            steps = [
                {
                    "name": "Set user",
                    "type": "set_variable",
                    "variable_name": "user",
                    "value": {"name": "FlyTest", "token": "token-123"},
                    "scope": "global",
                },
                {
                    "name": "Extract token",
                    "type": "extract_output",
                    "source": "user",
                    "path": "token",
                    "variable_name": "token",
                    "scope": "local",
                },
                {
                    "name": "Loop envs",
                    "type": "loop",
                    "mode": "foreach",
                    "items": ["dev", "test"],
                    "item_var": "env",
                    "steps": [
                        {
                            "name": "Remember env",
                            "type": "set_variable",
                            "variable_name": "current_env",
                            "value": "{{ env }}",
                            "scope": "global",
                        }
                    ],
                },
                {
                    "name": "If token exists",
                    "type": "if",
                    "left": "{{ token }}",
                    "operator": "truthy",
                    "then_steps": [
                        {
                            "name": "Mark ready",
                            "type": "set_variable",
                            "variable_name": "ready",
                            "value": True,
                            "scope": "global",
                        }
                    ],
                },
                {
                    "name": "Try catch finalize",
                    "type": "try",
                    "try_steps": [
                        {
                            "name": "Missing source",
                            "type": "extract_output",
                            "source": "missing_source",
                            "variable_name": "should_fail",
                        }
                    ],
                    "catch_steps": [
                        {
                            "name": "Capture error",
                            "type": "set_variable",
                            "variable_name": "handled",
                            "value": "{{ error }}",
                            "scope": "global",
                        }
                    ],
                    "finally_steps": [
                        {
                            "name": "Finalize",
                            "type": "set_variable",
                            "variable_name": "finalized",
                            "value": True,
                            "scope": "global",
                        }
                    ],
                },
            ]

            result = executor.run(steps)

            self.assertEqual(result["total_steps"], 8)
            self.assertEqual(result["passed_steps"], 7)
            self.assertEqual(result["failed_steps"], 0)
            self.assertEqual(result["outputs"]["token"], "token-123")
            self.assertEqual(executor.global_context["current_env"], "test")
            self.assertTrue(executor.global_context["ready"])
            self.assertTrue(executor.global_context["finalized"])
            self.assertIn("missing_source", executor.global_context["handled"])
        finally:
            temp_dir.cleanup()

    def test_api_request_can_save_and_extract_response_fields(self):
        temp_dir, executor = self.create_executor()
        try:
            steps = [
                {
                    "name": "Fetch auth info",
                    "type": "api_request",
                    "method": "POST",
                    "url": "https://example.com/token",
                    "json": {"user": "flytest"},
                    "expected_status": 200,
                    "save_as": "auth_response",
                    "scope": "local",
                    "extracts": [
                        {"name": "token", "path": "body.data.token"},
                        {"name": "user_id", "path": "body.data.user.id", "scope": "global"},
                    ],
                }
            ]

            with patch(
                "app.execution_runtime.urlopen",
                return_value=DummyResponse({"data": {"token": "abc-123", "user": {"id": 7}}}),
            ):
                result = executor.run(steps)

            self.assertEqual(result["passed_steps"], 1)
            self.assertEqual(result["outputs"]["token"], "abc-123")
            self.assertEqual(result["outputs"]["user_id"], 7)
            self.assertEqual(result["outputs"]["auth_response"]["status_code"], 200)
            self.assertEqual(executor.global_context["user_id"], 7)
        finally:
            temp_dir.cleanup()

    def test_resolve_asset_path_allows_current_project_asset(self):
        temp_dir, executor = self.create_executor()
        try:
            asset_path = Path(temp_dir.name) / "uploads" / "elements" / "common" / "project-1001" / "ok.png"
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(b"ok")

            with patch("app.execution_runtime.resolve_upload_asset_path", return_value=asset_path):
                resolved = executor._resolve_asset_path("elements/common/project-1001/ok.png")

            self.assertEqual(resolved, asset_path)
        finally:
            temp_dir.cleanup()

    def test_resolve_asset_path_rejects_other_project_asset(self):
        temp_dir, executor = self.create_executor()
        try:
            asset_path = Path(temp_dir.name) / "uploads" / "elements" / "common" / "project-2002" / "secret.png"
            asset_path.parent.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(b"secret")

            with patch("app.execution_runtime.resolve_upload_asset_path", return_value=asset_path):
                resolved = executor._resolve_asset_path("elements/common/project-2002/secret.png")

            self.assertIsNone(resolved)
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
