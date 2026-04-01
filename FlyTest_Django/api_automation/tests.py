import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project

from .ai_parser import (
    AIEnhancementResult,
    _build_ai_failure_note,
    _get_chunk_max_workers,
    _invoke_ai_for_chunk_with_timeout_fallback,
    create_llm_instance,
    safe_llm_invoke,
)
from .ai_case_generator import AITestCaseGenerationResult, GeneratedCaseDraft
from .document_import import ParsedRequestData
from .models import ApiCollection, ApiExecutionRecord, ApiImportJob, ApiRequest, ApiTestCase
from .services import build_request_url


class ApiAutomationAIParserTests(SimpleTestCase):
    def test_safe_llm_invoke_retries_after_concurrent_rate_limit(self):
        llm = Mock()
        llm.invoke.side_effect = [
            Exception("Error code: 429 - {'error': {'code': 'concurrent_request_limit_exceeded'}}"),
            SimpleNamespace(content='{"requests": []}'),
        ]

        with patch("api_automation.ai_parser.time.sleep") as mock_sleep:
            response = safe_llm_invoke(llm, [])

        self.assertEqual(response.content, '{"requests": []}')
        self.assertEqual(llm.invoke.call_count, 2)
        mock_sleep.assert_called_once()

    def test_chunk_worker_limit_defaults_to_single_worker(self):
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(_get_chunk_max_workers(5), 1)

    def test_chunk_worker_limit_respects_env_and_chunk_count(self):
        with patch.dict(os.environ, {"API_AUTOMATION_AI_CHUNK_MAX_WORKERS": "4"}, clear=False):
            self.assertEqual(_get_chunk_max_workers(2), 2)

    @patch("api_automation.ai_parser.ChatOpenAI")
    def test_create_llm_instance_disables_provider_retries_by_default(self, mock_chat_openai):
        active_config = SimpleNamespace(
            provider="openai_compatible",
            name="gpt-5.4",
            request_timeout=120,
            max_retries=3,
            api_url="https://example.com/v1",
            api_key="test-key",
        )

        with patch.dict(os.environ, {}, clear=False):
            create_llm_instance(active_config)

        self.assertEqual(mock_chat_openai.call_args.kwargs["max_retries"], 0)

    @patch("api_automation.ai_parser._invoke_ai_for_chunk")
    def test_timeout_fallback_splits_large_chunk_and_recovers(self, mock_invoke_ai_for_chunk):
        def side_effect(*args, **kwargs):
            chunk_content = kwargs["chunk_content"]
            if len(chunk_content) > 3000:
                raise Exception("Request timed out.")
            return {"requests": []}, False, False

        mock_invoke_ai_for_chunk.side_effect = side_effect

        payloads, truncated_chunk, truncated_preparsed, used_timeout_split = _invoke_ai_for_chunk_with_timeout_fallback(
            active_config=SimpleNamespace(),
            prompt_template="demo",
            file_path="demo.md",
            content_source_type="native_document",
            marker_used=False,
            chunk_content=("\n\n".join(["a" * 2500, "b" * 2500, "c" * 2500, "d" * 2500])),
            chunk_index=0,
            chunk_total=1,
            related_requests=[],
            base_requests=[],
        )

        self.assertTrue(used_timeout_split)
        self.assertEqual(len(payloads), 4)
        self.assertFalse(truncated_chunk)
        self.assertFalse(truncated_preparsed)
        self.assertGreater(mock_invoke_ai_for_chunk.call_count, 1)

    def test_build_ai_failure_note_for_concurrent_limit_is_friendly(self):
        note = _build_ai_failure_note(
            Exception("Error code: 429 - {'error': {'code': 'concurrent_request_limit_exceeded'}}")
        )

        self.assertIn("并发限流", note)
        self.assertIn("429", note)
        self.assertIn("回退", note)

    def test_build_ai_failure_note_for_timeout_is_friendly(self):
        note = _build_ai_failure_note(Exception("Request timed out."))

        self.assertIn("请求超时", note)
        self.assertIn("缩小文档分片", note)
        self.assertIn("回退", note)


class ApiAutomationImportDocumentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="apiadmin",
            email="apiadmin@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="API Automation Project",
            description="project for api automation tests",
            creator=self.user,
        )
        self.collection = ApiCollection.objects.create(
            project=self.project,
            name="Imported APIs",
            creator=self.user,
        )
        self.other_user = User.objects.create_user(
            username="outsider",
            email="outsider@example.com",
            password="testpass123",
        )

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_import_document_creates_requests_scripts_and_test_cases(self):
        openapi_document = {
            "openapi": "3.0.1",
            "info": {"title": "Demo", "version": "1.0.0"},
            "servers": [{"url": "https://example.com"}],
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "tags": ["users"],
                        "responses": {"200": {"description": "ok"}},
                    },
                    "post": {
                        "summary": "Create user",
                        "tags": ["users"],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "name": "Alice",
                                        "email": "alice@example.com",
                                    }
                                }
                            }
                        },
                        "responses": {"201": {"description": "created"}},
                    },
                }
            },
        }

        upload = SimpleUploadedFile(
            "openapi.json",
            json.dumps(openapi_document).encode("utf-8"),
            content_type="application/json",
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "async_mode": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)

        self.assertEqual(payload["created_count"], 2)
        self.assertEqual(payload["generated_script_count"], 2)
        self.assertEqual(payload["created_testcase_count"], 2)
        self.assertEqual(len(payload["generated_scripts"]), 2)
        self.assertEqual(len(payload["test_cases"]), 2)
        self.assertTrue(payload["ai_requested"])
        self.assertFalse(payload["ai_used"])
        self.assertIn("回退", payload["ai_note"])
        self.assertIn("generated_script", payload["items"][0])
        self.assertEqual(ApiRequest.objects.count(), 2)
        self.assertEqual(ApiTestCase.objects.count(), 2)

        post_script = next(item["script"] for item in payload["generated_scripts"] if item["request_name"] == "Create user")
        self.assertEqual(post_script["request"]["method"], "POST")
        self.assertEqual(post_script["request"]["url"], "https://example.com/users")

    def test_import_document_can_skip_test_case_generation(self):
        markdown = b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```"
        upload = SimpleUploadedFile("api.md", markdown, content_type="text/markdown")

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "false",
                "async_mode": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)

        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["generated_script_count"], 1)
        self.assertEqual(payload["created_testcase_count"], 0)
        self.assertTrue(payload["ai_requested"])
        self.assertFalse(payload["ai_used"])
        self.assertEqual(ApiRequest.objects.count(), 1)
        self.assertEqual(ApiTestCase.objects.count(), 0)

    @patch("api_automation.import_service.enhance_import_result_with_ai")
    def test_import_document_uses_ai_enhancement_when_available(self, mock_enhance):
        mock_enhance.return_value = AIEnhancementResult(
            requested=True,
            used=True,
            note="AI enhanced import applied",
            prompt_source="user_prompt",
            prompt_name="API自动化解析",
            model_name="gpt-4.1",
            requests=[
                ParsedRequestData(
                    name="AI Login",
                    method="POST",
                    url="/api/login",
                    description="AI enriched login request",
                    headers={"Authorization": "Bearer {{token}}"},
                    params={},
                    body_type="json",
                    body={"username": "demo", "password": "123456"},
                    assertions=[
                        {"type": "status_code", "expected": 200},
                        {"type": "json_path", "path": "code", "operator": "equals", "expected": 0},
                    ],
                    collection_name="auth",
                )
            ],
        )

        upload = SimpleUploadedFile(
            "api.md",
            b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```",
            content_type="text/markdown",
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "enable_ai_parse": "true",
                "async_mode": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)

        self.assertTrue(payload["ai_requested"])
        self.assertTrue(payload["ai_used"])
        self.assertEqual(payload["ai_prompt_source"], "user_prompt")
        self.assertEqual(payload["ai_prompt_name"], "API自动化解析")
        self.assertEqual(payload["ai_model_name"], "gpt-4.1")
        self.assertEqual(payload["items"][0]["name"], "AI Login")
        self.assertEqual(payload["test_cases"][0]["request_name"], "AI Login")
        self.assertEqual(payload["generated_scripts"][0]["script"]["assertions"][1]["type"], "json_path")

    @patch("api_automation.import_service._build_environment_drafts", return_value=[])
    @patch("api_automation.import_service.import_requests_from_document")
    @patch("api_automation.import_service.enhance_import_result_with_ai")
    def test_pdf_import_prefers_ai_before_rule_parse(self, mock_enhance, mock_rule_parse, _mock_env_drafts):
        mock_enhance.return_value = AIEnhancementResult(
            requested=True,
            used=True,
            note="AI parsed PDF directly",
            prompt_source="user_prompt",
            prompt_name="API自动化解析",
            model_name="gpt-5.4",
            requests=[
                ParsedRequestData(
                    name="PDF Login",
                    method="POST",
                    url="/api/login",
                    description="AI parsed from PDF",
                    headers={},
                    params={},
                    body_type="json",
                    body={"username": "demo", "password": "123456"},
                    assertions=[{"type": "status_code", "expected": 200}],
                    collection_name="auth",
                )
            ],
        )

        upload = SimpleUploadedFile(
            "api.pdf",
            b"%PDF-1.4 fake pdf content",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "enable_ai_parse": "true",
                "async_mode": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)
        self.assertEqual(payload["source_type"], "ai_direct_document")
        self.assertTrue(payload["ai_used"])
        self.assertEqual(payload["items"][0]["name"], "PDF Login")
        mock_rule_parse.assert_not_called()

    def test_test_case_list_endpoint_supports_collection_filter(self):
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="List users",
            method="GET",
            url="/api/users",
            created_by=self.user,
        )
        ApiTestCase.objects.create(
            project=self.project,
            request=request,
            name="List users - Ready",
            status="ready",
            script={"request": {"method": "GET", "url": "/api/users"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        response = self.client.get(
            "/api/api-automation/test-cases/",
            {
                "project": self.project.id,
                "collection": self.collection.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["collection_id"], self.collection.id)

    def test_collection_filter_includes_descendant_requests_and_test_cases(self):
        child = ApiCollection.objects.create(
            project=self.project,
            parent=self.collection,
            name="Auth",
            creator=self.user,
        )
        request = ApiRequest.objects.create(
            collection=child,
            name="Nested login",
            method="POST",
            url="/api/token/",
            created_by=self.user,
        )
        ApiTestCase.objects.create(
            project=self.project,
            request=request,
            name="Nested login case",
            status="ready",
            script={"request": {"method": "POST", "url": "/api/token/"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        request_response = self.client.get(
            "/api/api-automation/requests/",
            {
                "project": self.project.id,
                "collection": self.collection.id,
            },
        )
        self.assertEqual(request_response.status_code, status.HTTP_200_OK)
        request_payload = self._payload(request_response)
        self.assertEqual(len(request_payload), 1)
        self.assertEqual(request_payload[0]["name"], "Nested login")

        testcase_response = self.client.get(
            "/api/api-automation/test-cases/",
            {
                "project": self.project.id,
                "collection": self.collection.id,
            },
        )
        self.assertEqual(testcase_response.status_code, status.HTTP_200_OK)
        testcase_payload = self._payload(testcase_response)
        self.assertEqual(len(testcase_payload), 1)
        self.assertEqual(testcase_payload[0]["name"], "Nested login case")

    def test_import_document_returns_400_for_malformed_json(self):
        upload = SimpleUploadedFile(
            "broken.json",
            b'{"openapi": "3.0.1", "paths": ',
            content_type="application/json",
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "async_mode": "false",
                "file": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ApiRequest.objects.count(), 0)
        self.assertEqual(ApiTestCase.objects.count(), 0)

    def test_import_document_is_not_accessible_to_non_member(self):
        outsider_client = APIClient()
        outsider_client.force_authenticate(user=self.other_user)
        upload = SimpleUploadedFile(
            "api.md",
            b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```",
            content_type="text/markdown",
        )

        response = outsider_client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "file": upload,
            },
            format="multipart",
        )

        self.assertIn(response.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})
        self.assertEqual(ApiRequest.objects.count(), 0)

    def test_import_job_can_be_canceled(self):
        job = ApiImportJob.objects.create(
            project=self.project,
            collection=self.collection,
            creator=self.user,
            source_name="demo.pdf",
            status="pending",
            progress_percent=4,
            progress_stage="uploaded",
            progress_message="等待解析",
            generate_test_cases=True,
            enable_ai_parse=True,
        )

        response = self.client.post(f"/api/api-automation/import-jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "canceled")
        self.assertTrue(payload["cancel_requested"])

    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_generate_test_cases_endpoint_creates_cases_for_selected_requests(self, mock_generate):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            headers={},
            params={},
            body_type="json",
            body={"sku": "A100"},
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        mock_generate.return_value = AITestCaseGenerationResult(
            used_ai=True,
            note="AI generated 2 cases",
            prompt_name="API自动化用例生成",
            prompt_source="builtin_fallback",
            model_name="demo-model",
            cases=[
                GeneratedCaseDraft(
                    name="Create order - 成功校验",
                    description="验证下单成功",
                    status="ready",
                    tags=["ai-generated", "positive"],
                    assertions=[{"type": "status_code", "expected": 200}],
                    request_overrides={"headers": {}, "params": {}, "body_type": "json", "body": {"sku": "A100"}, "timeout_ms": 30000},
                ),
                GeneratedCaseDraft(
                    name="Create order - 关键字段校验",
                    description="验证关键响应字段",
                    status="ready",
                    tags=["ai-generated", "regression"],
                    assertions=[{"type": "status_code", "expected": 200}],
                    request_overrides={"headers": {}, "params": {}, "body_type": "json", "body": {"sku": "A100"}, "timeout_ms": 30000},
                ),
            ],
        )

        response = self.client.post(
            "/api/api-automation/requests/generate-test-cases/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "generate",
                "count_per_request": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["total_requests"], 1)
        self.assertEqual(payload["created_testcase_count"], 2)
        self.assertEqual(payload["items"][0]["request_id"], api_request.id)
        self.assertEqual(ApiTestCase.objects.filter(request=api_request).count(), 2)

    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_generate_mode_skips_request_with_existing_cases(self, mock_generate):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="List reports",
            method="GET",
            url="/api/reports",
            created_by=self.user,
        )
        ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="Existing report case",
            status="ready",
            script={"request": {"method": "GET", "url": "/api/reports"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        response = self.client.post(
            "/api/api-automation/requests/generate-test-cases/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "generate",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["skipped_requests"], 1)
        self.assertEqual(payload["created_testcase_count"], 0)
        mock_generate.assert_not_called()


class ApiAutomationExecutionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            username="execadmin",
            email="execadmin@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="API Execution Project",
            description="project for execution tests",
            creator=self.user,
        )
        self.collection = ApiCollection.objects.create(
            project=self.project,
            name="Execution APIs",
            creator=self.user,
        )

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_build_request_url_deduplicates_common_api_prefix(self):
        self.assertEqual(
            build_request_url("https://cms-test.9635.com.cn/api", "api/live/getLiveToken"),
            "https://cms-test.9635.com.cn/api/live/getLiveToken",
        )
        self.assertEqual(
            build_request_url("https://cms-test.9635.com.cn/api", "/api/live/getLiveToken"),
            "https://cms-test.9635.com.cn/api/live/getLiveToken",
        )
        self.assertEqual(
            build_request_url("https://cms-test.9635.com.cn/api", "live/getLiveToken"),
            "https://cms-test.9635.com.cn/api/live/getLiveToken",
        )

    def test_execute_request_reports_missing_environment_variables(self):
        environment = self.project.api_environments.create(
            name="Execution Env",
            base_url="https://cms-test.9635.com.cn/api",
            variables={"token": "", "nkey": "", "auth_request_name": "APP密码登录"},
            creator=self.user,
            is_default=True,
        )
        ApiRequest.objects.create(
            collection=self.collection,
            name="APP密码登录",
            method="POST",
            url="user/appLogin",
            params={"phone": "{{phone}}", "password": "{{password}}"},
            created_by=self.user,
        )
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="Protected endpoint",
            method="GET",
            url="api/live/getLiveToken",
            headers={"Authorization": "{{token}}"},
            params={"nkey": "{{nkey}}", "uid": "{{uid}}"},
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )

        response = self.client.post(
            f"/api/api-automation/requests/{request.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "error")
        self.assertFalse(payload["passed"])
        self.assertIn("自动获取 token 失败", payload["error_message"])
        self.assertIn("phone", payload["error_message"])
        self.assertIn("password", payload["error_message"])
        self.assertEqual(
            payload["request_snapshot"]["url"],
            "https://cms-test.9635.com.cn/api/live/getLiveToken",
        )

    @patch("api_automation.views.httpx.request")
    def test_execute_request_bootstraps_token_from_auth_request(self, mock_request):
        environment = self.project.api_environments.create(
            name="Execution Env",
            base_url="https://cms-test.9635.com.cn/api",
            variables={
                "token": "",
                "phone": "13800138000",
                "password": "secret123",
                "auth_request_name": "APP密码登录",
            },
            creator=self.user,
            is_default=True,
        )
        ApiRequest.objects.create(
            collection=self.collection,
            name="APP密码登录",
            method="POST",
            url="user/appLogin",
            params={"phone": "{{phone}}", "password": "{{password}}"},
            created_by=self.user,
        )
        protected_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Protected endpoint",
            method="GET",
            url="api/live/getLiveToken",
            headers={"Authorization": "{{token}}"},
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )

        class MockResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        def side_effect(**kwargs):
            url = kwargs["url"]
            if url.endswith("/user/appLogin"):
                return MockResponse(200, {"code": 200, "data": {"token": "AUTO_TOKEN_123"}})
            if url.endswith("/api/live/getLiveToken"):
                self.assertEqual(kwargs["headers"]["Authorization"], "AUTO_TOKEN_123")
                return MockResponse(200, {"code": 200, "message": "success"})
            raise AssertionError(f"Unexpected url: {url}")

        mock_request.side_effect = side_effect

        response = self.client.post(
            f"/api/api-automation/requests/{protected_request.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["request_snapshot"]["missing_variables"], [])
        environment.refresh_from_db()
        self.assertEqual(environment.variables["token"], "AUTO_TOKEN_123")

    def test_execution_report_endpoint_returns_summary(self):
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="Report endpoint request",
            method="GET",
            url="/api/reports",
            created_by=self.user,
        )

        ApiExecutionRecord.objects.create(
            project=self.project,
            request=request,
            environment=None,
            run_id="run-report-1",
            run_name="接口批量执行",
            request_name=request.name,
            method=request.method,
            url=request.url,
            status="success",
            passed=True,
            status_code=200,
            response_time=120.5,
            request_snapshot={},
            response_snapshot={},
            assertions_results=[],
            executor=self.user,
        )

        response = self.client.get(
            "/api/api-automation/execution-records/report/",
            {"project": self.project.id, "days": 7},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["summary"]["total_count"], 1)
        self.assertEqual(payload["summary"]["success_count"], 1)
        self.assertEqual(len(payload["recent_records"]), 1)
        self.assertEqual(len(payload["run_groups"]), 1)
        self.assertEqual(payload["run_groups"][0]["interface_count"], 1)

    @patch("api_automation.views.httpx.request")
    def test_execute_test_case_persists_test_case_and_run_metadata(self, mock_request):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="会员登录",
            method="POST",
            url="/api/login",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="会员登录-正确密码",
            status="ready",
            script={"request_overrides": {"body_type": "json", "body": {"username": "demo", "password": "123456"}}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        class MockResponse:
            status_code = 200
            headers = {}
            text = '{"code":200}'
            is_success = True

            def json(self):
                return {"code": 200}

        mock_request.return_value = MockResponse()

        response = self.client.post(
            f"/api/api-automation/test-cases/{test_case.id}/execute/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["test_case"], test_case.id)
        self.assertEqual(payload["test_case_name"], test_case.name)
        self.assertEqual(payload["interface_name"], api_request.name)
        self.assertTrue(payload["run_id"])
        self.assertIn("测试用例执行", payload["run_name"])

        record = ApiExecutionRecord.objects.get(pk=payload["id"])
        self.assertEqual(record.test_case_id, test_case.id)
        self.assertTrue(record.run_id)

    def test_execution_report_includes_run_interface_and_failed_case_hierarchy(self):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="会员登录",
            method="POST",
            url="/api/login",
            created_by=self.user,
        )
        failed_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="会员登录-错误密码",
            status="ready",
            script={"request_overrides": {"body_type": "json", "body": {"username": "demo", "password": "wrong"}}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        ApiExecutionRecord.objects.create(
            project=self.project,
            request=api_request,
            test_case=failed_case,
            environment=None,
            run_id="run-cms-1",
            run_name="CMS 回归执行",
            request_name=failed_case.name,
            method="POST",
            url="/api/login",
            status="failed",
            passed=False,
            status_code=401,
            response_time=188.4,
            request_snapshot={
                "interface_name": api_request.name,
                "collection_id": self.collection.id,
                "collection_name": self.collection.name,
                "test_case_id": failed_case.id,
                "test_case_name": failed_case.name,
            },
            response_snapshot={"body": {"message": "用户名或密码错误"}},
            assertions_results=[{"index": 0, "type": "status_code", "expected": 200, "actual": 401, "passed": False}],
            error_message="用户名或密码错误",
            executor=self.user,
        )

        response = self.client.get(
            "/api/api-automation/execution-records/report/",
            {"project": self.project.id, "days": 7},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["hierarchy_summary"]["run_count"], 1)
        self.assertEqual(payload["hierarchy_summary"]["failed_test_case_count"], 1)
        self.assertEqual(len(payload["run_groups"]), 1)

        run_group = payload["run_groups"][0]
        self.assertEqual(run_group["run_name"], "CMS 回归执行")
        self.assertEqual(run_group["failed_test_case_count"], 1)
        self.assertEqual(run_group["interface_count"], 1)

        interface_group = run_group["interfaces"][0]
        self.assertEqual(interface_group["interface_name"], "会员登录")
        self.assertEqual(interface_group["failed_test_case_count"], 1)
        self.assertEqual(len(interface_group["failed_test_cases"]), 1)

        case_group = interface_group["failed_test_cases"][0]
        self.assertEqual(case_group["test_case_name"], "会员登录-错误密码")
        self.assertEqual(case_group["latest_status_code"], 401)
        self.assertEqual(case_group["latest_error_message"], "用户名或密码错误")
        self.assertEqual(case_group["failed_records"][0]["error_message"], "用户名或密码错误")
