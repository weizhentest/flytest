import importlib.util
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from projects.models import Project
from langgraph_integration.models import LLMConfig
from ui_automation.ai_mode_runtime import (
    AI_STOP_SIGNALS,
    ExecutionRuntimeState,
    _build_browser_task_prompt,
    _collect_browser_failure_signals,
    _contains_auth_failure_signal,
    _format_browser_step_log,
    _finalize_tasks_for_terminal_status,
    _is_login_related_task,
    _resolve_max_actions_per_step,
    _resolve_runtime_terminal_status,
    request_stop_ai_execution,
)
from ui_automation.models import UiAICase, UiAIExecutionRecord, UiEnvironmentConfig, UiModule, UiPage


ACTUATOR_PATH = Path(__file__).resolve().parents[2] / "FlyTest_Actuator"
if str(ACTUATOR_PATH) not in sys.path:
    sys.path.insert(0, str(ACTUATOR_PATH))

from data_processor import DataProcessor  # noqa: E402


REPORTLAB_AVAILABLE = importlib.util.find_spec("reportlab") is not None


class UiAutomationDataFactoryReferenceTests(SimpleTestCase):
    def test_data_processor_resolves_nested_data_factory_variables(self):
        processor = DataProcessor()
        processor.set_cache(
            "df",
            {
                "tag": {
                    "login_name": "tester01",
                    "profile": {"name": "FlyTest", "roles": ["admin", "qa"]},
                },
                "record": {
                    "12": {"token": "abc123", "enabled": True},
                },
            },
        )

        resolved = processor.replace(
            {
                "username": "${{df.tag.login_name}}",
                "summary": "当前用户：${{df.tag.profile.name}}",
                "token": "${{df.record.12.token}}",
                "enabled": "${{df.record.12.enabled}}",
            }
        )

        self.assertEqual(resolved["username"], "tester01")
        self.assertEqual(resolved["summary"], "当前用户：FlyTest")
        self.assertEqual(resolved["token"], "abc123")
        self.assertIs(resolved["enabled"], True)

    def test_data_processor_preserves_native_type_for_whole_placeholder(self):
        processor = DataProcessor()
        processor.set_cache(
            "df",
            {
                "record": {
                    "88": {"items": ["A", "B"], "meta": {"count": 2}},
                }
            },
        )

        resolved = processor.replace("${{df.record.88}}")

        self.assertEqual(resolved, {"items": ["A", "B"], "meta": {"count": 2}})


class UiAutomationAiRuntimeTests(SimpleTestCase):
    def tearDown(self):
        AI_STOP_SIGNALS.clear()

    def test_build_browser_task_prompt_adds_guardrails_and_sanitizes_urls(self):
        prompt = _build_browser_task_prompt(
            full_task="打开 https://demo.flytest.local/login，完成登录并校验首页卡片。",
            current_task={
                "id": 2,
                "title": "填写登录表单",
                "description": "输入账号密码并点击登录按钮，若弹出校验错误则补全必填项。",
                "expected_result": "成功进入首页。",
            },
            task_index=1,
            planned_tasks=[
                {"id": 1, "title": "进入登录页", "description": "打开登录页", "status": "completed"},
                {"id": 2, "title": "填写登录表单", "description": "填写并提交", "status": "pending"},
                {"id": 3, "title": "校验首页", "description": "检查 Executive Overview 卡片", "status": "pending"},
            ],
            project_context={
                "pages": [{"name": "登录页", "url": "https://demo.flytest.local/login"}],
                "elements": [{"name": "登录按钮", "locator_type": "text"}],
            },
            env_config=SimpleNamespace(base_url="https://demo.flytest.local/login，", name="Default"),
            execution_mode="text",
            model_name="deepseek-chat",
        )

        self.assertIn("Before save or submit, inspect the page for validation errors", prompt)
        self.assertIn("Use browser-use native action parameters: use 'index'", prompt)
        self.assertIn("Never invent, replace, or guess credentials", prompt)
        self.assertIn("Already completed sub-tasks", prompt)
        self.assertIn("Future sub-tasks (do not execute yet)", prompt)
        self.assertIn("Minimize output tokens", prompt)
        self.assertIn("https://demo.flytest.local/login ", prompt)
        self.assertNotIn("https://demo.flytest.local/login，", prompt)

    def test_resolve_max_actions_per_step_prefers_higher_throughput_for_text_mode(self):
        short_task = {"description": "打开页面并完成快速验证"}
        long_task = {"description": "填写复杂表单、处理下拉框、校验弹窗提示并提交保存，完成后返回列表页确认新增数据可见。"}

        self.assertEqual(_resolve_max_actions_per_step(short_task, "text"), 5)
        self.assertEqual(_resolve_max_actions_per_step(short_task, "vision"), 4)
        self.assertEqual(_resolve_max_actions_per_step(long_task, "text"), 5)

    def test_auth_failure_signal_helpers_detect_login_failures(self):
        task = {
            "title": "执行登录",
            "description": "输入账号密码并登录后台",
            "expected_result": "成功登录首页",
        }
        browser_state = SimpleNamespace(
            recent_events="toast: 登录失败，请检查用户名或密码",
            browser_errors=["401 Unauthorized"],
            closed_popup_messages=["invalid credentials"],
        )
        model_output = SimpleNamespace(
            thinking="login failed",
            evaluation_previous_goal="authentication failed again",
            memory="用户名或密码错误",
            next_goal="retry login after checking credentials",
        )

        signal_text = _collect_browser_failure_signals(browser_state, model_output)

        self.assertTrue(_is_login_related_task(task))
        self.assertTrue(_contains_auth_failure_signal(signal_text))
        self.assertIn("401 Unauthorized", signal_text)

    def test_auth_failure_signal_helpers_ignore_non_login_tasks(self):
        task = {
            "title": "校验首页卡片",
            "description": "检查 Executive Overview 卡片内容",
            "expected_result": "卡片显示正常",
        }

        self.assertFalse(_is_login_related_task(task))
        self.assertFalse(_contains_auth_failure_signal("page loaded successfully"))

    def test_format_browser_step_log_includes_recent_events_and_errors(self):
        browser_state = SimpleNamespace(
            title="登录页",
            url="https://demo.flytest.local/login",
            recent_events="toast: 登录失败",
            browser_errors=["401 Unauthorized"],
            closed_popup_messages=["用户名或密码错误"],
        )
        model_output = SimpleNamespace(
            action=[{"input_text": {"index": 3, "text": "admin"}}],
            next_goal="重新检查账号密码",
            evaluation_previous_goal="登录失败",
        )

        log_message = _format_browser_step_log("执行登录", 2, browser_state, model_output)

        self.assertIn("最近事件：toast: 登录失败", log_message)
        self.assertIn("浏览器错误：401 Unauthorized", log_message)
        self.assertIn("弹窗信息：用户名或密码错误", log_message)

    def test_finalize_tasks_for_stopped_marks_running_and_pending_tasks(self):
        runtime_state = ExecutionRuntimeState(
            record_id=1,
            case_name="Stopped task",
            planned_tasks=[
                {"id": 1, "title": "已完成任务", "status": "completed"},
                {"id": 2, "title": "进行中任务", "status": "running"},
                {"id": 3, "title": "待执行任务", "status": "pending"},
            ],
        )

        _finalize_tasks_for_terminal_status(runtime_state, "stopped", "任务已由用户停止")

        self.assertEqual(runtime_state.planned_tasks[0]["status"], "completed")
        self.assertEqual(runtime_state.planned_tasks[1]["status"], "stopped")
        self.assertEqual(runtime_state.planned_tasks[2]["status"], "stopped")
        self.assertEqual(runtime_state.planned_tasks[1]["error_message"], "任务已由用户停止")
        self.assertEqual(runtime_state.planned_tasks[2]["result"], "任务已由用户停止")

    def test_finalize_tasks_for_failed_marks_future_tasks_as_skipped(self):
        runtime_state = ExecutionRuntimeState(
            record_id=2,
            case_name="Failed task",
            planned_tasks=[
                {"id": 1, "title": "已完成任务", "status": "completed"},
                {"id": 2, "title": "进行中任务", "status": "running"},
                {"id": 3, "title": "待执行任务", "status": "pending"},
            ],
        )

        _finalize_tasks_for_terminal_status(runtime_state, "failed", "元素定位失败")

        self.assertEqual(runtime_state.planned_tasks[0]["status"], "completed")
        self.assertEqual(runtime_state.planned_tasks[1]["status"], "failed")
        self.assertEqual(runtime_state.planned_tasks[2]["status"], "skipped")
        self.assertEqual(runtime_state.planned_tasks[1]["error_message"], "元素定位失败")
        self.assertEqual(runtime_state.planned_tasks[2]["result"], "因前置任务失败，后续任务已跳过")

    def test_resolve_runtime_terminal_status_prefers_failed_and_stopped_states(self):
        runtime_state = ExecutionRuntimeState(
            record_id=3,
            case_name="Mixed terminal task",
            planned_tasks=[
                {"id": 1, "title": "成功任务", "status": "completed"},
                {"id": 2, "title": "失败任务", "status": "failed"},
                {"id": 3, "title": "停止任务", "status": "stopped"},
            ],
            steps_completed=[
                {"step": 1, "title": "成功步骤", "status": "passed"},
                {"step": 2, "title": "失败步骤", "status": "failed"},
            ],
        )

        self.assertEqual(_resolve_runtime_terminal_status(runtime_state), "failed")


class UiAutomationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="uiadmin",
            email="uiadmin@example.com",
            password="Password123!",
        )
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(
            name="FlyTest UI Project",
            description="UI automation test project",
            creator=self.user,
        )
        self.module = UiModule.objects.create(
            project=self.project,
            name="Core",
            parent=None,
            level=0,
            creator=self.user,
        )

    def test_pages_list_supports_optional_server_side_pagination(self):
        for index in range(15):
            UiPage.objects.create(
                project=self.project,
                module=self.module,
                name=f"Page {index + 1}",
                url=f"https://example.com/{index + 1}",
                creator=self.user,
            )

        paged_response = self.client.get(
            f"/api/ui-automation/pages/?project={self.project.id}&page_number=2&page_size=10"
        )
        self.assertEqual(paged_response.status_code, 200)
        paged_payload = paged_response.json()["data"]
        self.assertEqual(paged_payload["count"], 15)
        self.assertEqual(len(paged_payload["results"]), 5)

        full_response = self.client.get(f"/api/ui-automation/pages/?project={self.project.id}")
        self.assertEqual(full_response.status_code, 200)
        full_payload = full_response.json()["data"]
        self.assertIsInstance(full_payload, list)
        self.assertEqual(len(full_payload), 15)

    @patch("ui_automation.views._validate_ai_execution_request", return_value=None)
    @patch("ui_automation.views.start_ai_execution")
    def test_run_ai_case_creates_execution_record(
        self,
        mocked_start_ai_execution,
        mocked_validate_ai_execution_request,
    ):
        ai_case = UiAICase.objects.create(
            project=self.project,
            name="Login smoke",
            description="Verify login flow",
            task_description="Open login page and confirm dashboard card is visible.",
            default_execution_mode="text",
            enable_gif=False,
            creator=self.user,
        )

        response = self.client.post(
            f"/api/ui-automation/ai-cases/{ai_case.id}/run/",
            {"execution_mode": "vision"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["case_name"], ai_case.name)
        self.assertEqual(payload["execution_mode"], "vision")
        self.assertEqual(payload["status"], "running")
        self.assertFalse(payload["enable_gif"])
        mocked_start_ai_execution.assert_called_once()
        mocked_validate_ai_execution_request.assert_called_once_with(self.project.id, "vision")
        self.assertEqual(UiAIExecutionRecord.objects.count(), 1)

    @patch("ui_automation.views._validate_ai_execution_request", return_value=None)
    @patch("ui_automation.views.start_ai_execution")
    def test_run_adhoc_ai_task_supports_enable_gif_flag(
        self,
        mocked_start_ai_execution,
        mocked_validate_ai_execution_request,
    ):
        response = self.client.post(
            "/api/ui-automation/ai-execution-records/run-adhoc/",
            {
                "project": self.project.id,
                "case_name": "Adhoc task",
                "task_description": "Open the dashboard and inspect AI smart mode.",
                "execution_mode": "text",
                "enable_gif": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertFalse(payload["enable_gif"])
        mocked_start_ai_execution.assert_called_once()
        mocked_validate_ai_execution_request.assert_called_once_with(self.project.id, "text")

    @patch("ui_automation.views.get_ai_runtime_capabilities")
    def test_run_ai_case_rejects_vision_mode_when_model_lacks_vision_support(self, mocked_capabilities):
        mocked_capabilities.return_value = {
            "llm_configured": True,
            "supports_vision": False,
            "vision_mode_ready": False,
            "text_mode_ready": True,
        }

        ai_case = UiAICase.objects.create(
            project=self.project,
            name="Vision smoke",
            description="Verify login flow",
            task_description="Open login page and confirm dashboard card is visible.",
            default_execution_mode="vision",
            enable_gif=True,
            creator=self.user,
        )

        response = self.client.post(
            f"/api/ui-automation/ai-cases/{ai_case.id}/run/",
            {"execution_mode": "vision"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("LLM", payload["errors"]["error"])
        self.assertFalse(payload["errors"]["runtime_capabilities"]["supports_vision"])
        self.assertEqual(UiAIExecutionRecord.objects.count(), 0)

    @patch("ui_automation.views.get_ai_runtime_capabilities")
    def test_run_adhoc_rejects_vision_mode_when_runtime_not_ready(self, mocked_capabilities):
        mocked_capabilities.return_value = {
            "llm_configured": True,
            "supports_vision": True,
            "vision_mode_ready": False,
            "text_mode_ready": True,
        }

        response = self.client.post(
            "/api/ui-automation/ai-execution-records/run-adhoc/",
            {
                "project": self.project.id,
                "case_name": "Vision adhoc task",
                "task_description": "Inspect the dashboard in visual mode.",
                "execution_mode": "vision",
                "enable_gif": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertIn("browser-use / Playwright", payload["errors"]["error"])
        self.assertFalse(payload["errors"]["runtime_capabilities"]["vision_mode_ready"])
        self.assertEqual(UiAIExecutionRecord.objects.count(), 0)

    @patch("ui_automation.ai_mode_runtime.importlib.util.find_spec")
    @patch("ui_automation.ai_mode_runtime._find_browser_executable")
    def test_ai_runtime_capabilities_reports_backend_model_and_environment(
        self,
        mocked_find_browser_executable,
        mocked_find_spec,
    ):
        mocked_find_browser_executable.return_value = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"

        def find_spec_side_effect(module_name):
            return object() if module_name in {"browser_use", "playwright"} else None

        mocked_find_spec.side_effect = find_spec_side_effect

        UiEnvironmentConfig.objects.create(
            project=self.project,
            name="Default env",
            base_url="https://example.com",
            browser="chromium",
            headless=True,
            viewport_width=1440,
            viewport_height=900,
            timeout=30000,
            is_default=True,
            creator=self.user,
        )
        LLMConfig.objects.create(
            config_name="Vision Model",
            provider="openai_compatible",
            name="gpt-4.1",
            api_url="https://llm.example.com/v1",
            api_key="secret-key",
            supports_vision=True,
            is_active=True,
        )

        response = self.client.get(
            f"/api/ui-automation/ai-execution-records/capabilities/?project={self.project.id}"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["execution_backend"], "browser_use")
        self.assertTrue(payload["llm_configured"])
        self.assertTrue(payload["text_mode_ready"])
        self.assertTrue(payload["vision_mode_ready"])
        self.assertEqual(payload["model_config_name"], "Vision Model")
        self.assertEqual(payload["default_environment"]["name"], "Default env")
        self.assertEqual(payload["default_environment"]["base_url"], "https://example.com")

    def test_ai_cases_batch_delete_clears_related_execution_records(self):
        case_one = UiAICase.objects.create(
            project=self.project,
            name="Case one",
            description="First AI case",
            task_description="Open page one",
            default_execution_mode="text",
            enable_gif=True,
            creator=self.user,
        )
        case_two = UiAICase.objects.create(
            project=self.project,
            name="Case two",
            description="Second AI case",
            task_description="Open page two",
            default_execution_mode="vision",
            enable_gif=False,
            creator=self.user,
        )
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            ai_case=case_one,
            case_name=case_one.name,
            task_description=case_one.task_description,
            execution_mode="text",
            status="passed",
            executed_by=self.user,
        )

        response = self.client.post(
            "/api/ui-automation/ai-cases/batch-delete/",
            {"ids": [case_one.id, case_two.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["deleted_count"], 2)
        self.assertFalse(UiAICase.objects.filter(id=case_one.id).exists())
        self.assertFalse(UiAICase.objects.filter(id=case_two.id).exists())
        record.refresh_from_db()
        self.assertIsNone(record.ai_case)

    def test_ai_execution_report_includes_media_and_summary_counts(self):
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Adhoc browser task",
            task_description="Validate the settings page layout.",
            execution_mode="vision",
            execution_backend="browser_use",
            status="passed",
            logs="execution logs",
            planned_tasks=[
                {"id": 1, "title": "Open page", "status": "completed"},
                {"id": 2, "title": "Verify content", "status": "failed"},
            ],
            steps_completed=[
                {"step": 1, "title": "Open page", "status": "passed"},
                {"step": 2, "title": "Verify content", "status": "failed"},
            ],
            screenshots_sequence=["/media/ui_ai/step-1.png"],
            gif_path="/media/ui_ai/run.gif",
            error_message="One visual assertion failed.",
            model_config_name="gpt-4.1-vision",
            executed_by=self.user,
        )

        response = self.client.get(f"/api/ui-automation/ai-execution-records/{record.id}/report/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["planned_task_count"], 2)
        self.assertEqual(payload["completed_task_count"], 1)
        self.assertEqual(payload["failed_task_count"], 1)
        self.assertEqual(payload["step_count"], 2)
        self.assertEqual(payload["passed_step_count"], 1)
        self.assertEqual(payload["failed_step_count"], 1)
        self.assertEqual(payload["screenshots_sequence"], ["/media/ui_ai/step-1.png"])
        self.assertEqual(payload["gif_path"], "/media/ui_ai/run.gif")

    def test_ai_execution_report_supports_detailed_and_performance_types(self):
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Settings regression",
            task_description="Open settings page and verify card layout.",
            execution_mode="text",
            execution_backend="planning",
            status="failed",
            logs="step execution logs",
            planned_tasks=[
                {"id": 1, "title": "Open settings", "description": "Navigate to settings", "status": "completed"},
                {"id": 2, "title": "Verify executive card", "description": "Check dashboard card", "status": "failed", "message": "Card not found"},
            ],
            steps_completed=[
                {"step": 1, "title": "Open settings", "description": "Navigate to settings", "status": "passed", "duration": 1.5},
                {"step": 2, "title": "Verify executive card", "description": "Check dashboard card", "status": "failed", "message": "Card not found", "duration": 4.2},
            ],
            error_message="Dashboard card not found.",
            executed_by=self.user,
        )

        detailed_response = self.client.get(
            f"/api/ui-automation/ai-execution-records/{record.id}/report/?report_type=detailed"
        )
        self.assertEqual(detailed_response.status_code, 200)
        detailed_payload = detailed_response.json()["data"]
        self.assertEqual(detailed_payload["report_type"], "detailed")
        self.assertEqual(len(detailed_payload["detailed_steps"]), 2)
        self.assertGreaterEqual(len(detailed_payload["errors"]), 1)

        performance_response = self.client.get(
            f"/api/ui-automation/ai-execution-records/{record.id}/report/?report_type=performance"
        )
        self.assertEqual(performance_response.status_code, 200)
        performance_payload = performance_response.json()["data"]
        self.assertEqual(performance_payload["report_type"], "performance")
        self.assertEqual(performance_payload["metrics"]["total_steps"], 2)
        self.assertGreaterEqual(len(performance_payload["bottlenecks"]), 1)
        self.assertGreaterEqual(len(performance_payload["recommendations"]), 1)

    def test_ai_execution_report_detailed_steps_include_browser_metadata(self):
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Browser metadata task",
            task_description="Open detail page and capture screenshots.",
            execution_mode="vision",
            execution_backend="browser_use",
            status="passed",
            steps_completed=[
                {
                    "step": 1,
                    "title": "打开详情页",
                    "description": "进入详情页并检查关键区域",
                    "expected_result": "详情页加载完成",
                    "status": "passed",
                    "message": "详情页已打开",
                    "duration": 2.3,
                    "browser_step_count": 4,
                    "screenshots": [
                        "ui_ai_execution/15/task-1/screenshots/step-1.png",
                        "ui_ai_execution/15/task-1/screenshots/step-2.png",
                    ],
                }
            ],
            executed_by=self.user,
        )

        response = self.client.get(
            f"/api/ui-automation/ai-execution-records/{record.id}/report/?report_type=detailed"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["report_type"], "detailed")
        self.assertEqual(payload["detailed_steps"][0]["expected_result"], "详情页加载完成")
        self.assertEqual(payload["detailed_steps"][0]["browser_step_count"], 4)
        self.assertEqual(
            payload["detailed_steps"][0]["screenshots"],
            [
                "ui_ai_execution/15/task-1/screenshots/step-1.png",
                "ui_ai_execution/15/task-1/screenshots/step-2.png",
            ],
        )

    def test_ai_execution_records_batch_delete_rejects_running_records(self):
        record_passed = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Completed task",
            task_description="Completed task description",
            execution_mode="text",
            status="passed",
            executed_by=self.user,
        )
        record_failed = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Failed task",
            task_description="Failed task description",
            execution_mode="vision",
            status="failed",
            executed_by=self.user,
        )
        record_running = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Running task",
            task_description="Running task description",
            execution_mode="text",
            status="running",
            executed_by=self.user,
        )

        response = self.client.post(
            "/api/ui-automation/ai-execution-records/batch-delete/",
            {"ids": [record_passed.id, record_failed.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["deleted_count"], 2)
        self.assertFalse(UiAIExecutionRecord.objects.filter(id=record_passed.id).exists())
        self.assertFalse(UiAIExecutionRecord.objects.filter(id=record_failed.id).exists())

        running_delete_response = self.client.post(
            "/api/ui-automation/ai-execution-records/batch-delete/",
            {"ids": [record_running.id]},
            format="json",
        )
        self.assertEqual(running_delete_response.status_code, 400)
        self.assertTrue(UiAIExecutionRecord.objects.filter(id=record_running.id).exists())

    def test_ai_execution_records_batch_stop_updates_running_records(self):
        started_at = timezone.now() - timedelta(seconds=15)
        record_running = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Running task",
            task_description="Running task description",
            execution_mode="text",
            status="running",
            start_time=started_at,
            executed_by=self.user,
        )
        record_pending = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Pending task",
            task_description="Pending task description",
            execution_mode="vision",
            status="pending",
            start_time=started_at,
            executed_by=self.user,
        )
        record_passed = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Passed task",
            task_description="Passed task description",
            execution_mode="text",
            status="passed",
            start_time=started_at,
            end_time=timezone.now(),
            duration=12.4,
            executed_by=self.user,
        )

        response = self.client.post(
            "/api/ui-automation/ai-execution-records/batch-stop/",
            {"ids": [record_running.id, record_pending.id, record_passed.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["stopped_count"], 2)
        self.assertEqual(len(payload["skipped_records"]), 1)

        record_running.refresh_from_db()
        record_pending.refresh_from_db()
        record_passed.refresh_from_db()

        self.assertEqual(record_running.status, "stopped")
        self.assertEqual(record_pending.status, "stopped")
        self.assertEqual(record_passed.status, "passed")
        self.assertIsNotNone(record_running.end_time)
        self.assertIsNotNone(record_pending.end_time)
        self.assertIsNotNone(record_running.duration)
        self.assertIsNotNone(record_pending.duration)

    def test_request_stop_ai_execution_appends_system_log(self):
        started_at = timezone.now() - timedelta(seconds=8)
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Stop me",
            task_description="Stop task description",
            execution_mode="text",
            status="running",
            start_time=started_at,
            logs="已有日志",
            executed_by=self.user,
        )

        result = request_stop_ai_execution(record.id)

        self.assertTrue(result)
        record.refresh_from_db()
        self.assertEqual(record.status, "stopped")
        self.assertIsNotNone(record.end_time)
        self.assertIsNotNone(record.duration)
        self.assertIn("已发送停止信号", record.logs or "")

    def test_ai_execution_record_destroy_rejects_running_record(self):
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Running task",
            task_description="Running task description",
            execution_mode="text",
            status="running",
            executed_by=self.user,
        )

        response = self.client.delete(f"/api/ui-automation/ai-execution-records/{record.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(UiAIExecutionRecord.objects.filter(id=record.id).exists())

    @unittest.skipUnless(REPORTLAB_AVAILABLE, "reportlab is required for PDF export test")
    def test_ai_execution_report_can_export_pdf(self):
        record = UiAIExecutionRecord.objects.create(
            project=self.project,
            case_name="Export report",
            task_description="Export summary report.",
            execution_mode="text",
            execution_backend="planning",
            status="passed",
            planned_tasks=[{"id": 1, "title": "Open page", "description": "Go to dashboard", "status": "completed"}],
            steps_completed=[{"step": 1, "title": "Open page", "description": "Go to dashboard", "status": "passed", "duration": 1.2}],
            executed_by=self.user,
        )

        response = self.client.get(
            f"/api/ui-automation/ai-execution-records/{record.id}/export-pdf/?report_type=summary"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])
        self.assertTrue(bytes(response.content).startswith(b"%PDF"))
