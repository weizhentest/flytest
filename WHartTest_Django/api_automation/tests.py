import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project

from .ai_parser import AIEnhancementResult
from .ai_case_generator import AITestCaseGenerationResult, GeneratedCaseDraft
from .document_import import ParsedRequestData
from .models import ApiCollection, ApiRequest, ApiTestCase


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

    @patch("api_automation.views.enhance_import_result_with_ai")
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
