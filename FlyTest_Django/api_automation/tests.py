import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from knowledge.models import Document as KnowledgeDocument
from knowledge.models import DocumentChunk, KnowledgeBase
from requirements.models import RequirementDocument, RequirementModule
from rest_framework import status
from rest_framework.test import APIClient

from data_factory.models import DataFactoryRecord
from data_factory.reference import build_reference_tree
from projects.models import Project

from .ai_parser import (
    AIEnhancementResult,
    _build_ai_failure_note,
    _get_chunk_max_workers,
    _extract_request_centered_chunks,
    _invoke_ai_for_chunk_with_timeout_fallback,
    _probe_openai_compatible_text_response,
    create_llm_instance,
    enhance_import_result_with_ai,
    safe_llm_invoke,
)
from .ai_case_generator import (
    AITestCaseGenerationResult,
    GeneratedCaseDraft,
    create_test_cases_from_drafts,
    generate_test_case_drafts_with_ai,
)
from .ai_failure_analyzer import analyze_execution_failure
from .document_import import ParsedRequestData, extract_requests_from_curl, parse_openapi_document, parse_postman_collection
from .execution import build_effective_request_spec, evaluate_structured_assertions
from .ai_report_summarizer import _get_report_summary_prompt
from .import_service import _build_environment_suggestions
from .models import ApiCaseGenerationJob, ApiCollection, ApiEnvironment, ApiExecutionRecord, ApiImportJob, ApiRequest, ApiTestCase
from .services import VariableResolver, build_request_url, find_missing_variables
from .specs import apply_request_spec_payload, apply_test_case_override_payload, serialize_assertion_specs, serialize_extractor_specs, serialize_test_case_override
from .views import _apply_case_generation_job, _recover_stale_import_job, _run_case_generation_job


class ApiAutomationAIParserTests(SimpleTestCase):
    def test_report_summary_prompt_uses_prompt_type_defaults(self):
        prompt_content, prompt_source, prompt_name = _get_report_summary_prompt(user=None)
        self.assertEqual(prompt_source, "builtin_default")
        self.assertEqual(prompt_name, "API测试报告摘要")
        self.assertIn("report_context_json", prompt_content)

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

    def test_safe_llm_invoke_retries_after_connection_error(self):
        llm = Mock()
        llm.invoke.side_effect = [
            Exception("Connection error."),
            SimpleNamespace(content='{"requests": []}'),
        ]

        with patch("api_automation.ai_parser.time.sleep") as mock_sleep:
            response = safe_llm_invoke(llm, [])

        self.assertEqual(response.content, '{"requests": []}')
        self.assertEqual(llm.invoke.call_count, 2)
        mock_sleep.assert_called_once()

    def test_safe_llm_invoke_accepts_structured_content_list(self):
        llm = Mock()
        llm.invoke.return_value = SimpleNamespace(
            content=[{"text": '{"requests": []}'}],
            response_metadata={"finish_reason": "stop", "token_usage": {"completion_tokens": 12}},
            usage_metadata={"input_tokens": 8, "output_tokens": 12, "total_tokens": 20},
            additional_kwargs={},
        )

        response = safe_llm_invoke(llm, [])

        self.assertEqual(response.content, '{"requests": []}')
        self.assertEqual(response.response_metadata["finish_reason"], "stop")

    def test_safe_llm_invoke_includes_usage_details_for_empty_response(self):
        llm = Mock()
        llm.invoke.return_value = SimpleNamespace(
            content="",
            response_metadata={"finish_reason": "stop", "token_usage": {"completion_tokens": 5}},
            usage_metadata={"total_tokens": 19},
            additional_kwargs={},
        )

        with self.assertRaises(RuntimeError) as ctx:
            safe_llm_invoke(llm, [], max_retries=1)

        self.assertIn("finish_reason=stop", str(ctx.exception))
        self.assertIn("completion_tokens=5", str(ctx.exception))

    @patch("api_automation.ai_parser.httpx.post")
    def test_messages_wire_api_probe_accepts_text_content(self, mock_post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "content": [{"type": "text", "text": "浣犲ソ"}],
            "usage": {"input_tokens": 8, "output_tokens": 12},
            "stop_reason": "end_turn",
        }
        mock_post.return_value = response

        result = _probe_openai_compatible_text_response(
            SimpleNamespace(
                provider="openai_compatible",
                wire_api="messages",
                api_url="https://example.com/v1",
                api_key="test-key",
                name="gpt-5.4",
            )
        )

        self.assertIsNone(result)

    def test_chunk_worker_limit_defaults_to_single_worker(self):
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(_get_chunk_max_workers(5), 1)

    def test_chunk_worker_limit_respects_env_and_chunk_count(self):
        with patch.dict(os.environ, {"API_AUTOMATION_AI_CHUNK_MAX_WORKERS": "4"}, clear=False):
            self.assertEqual(_get_chunk_max_workers(2), 2)

    def test_chunk_worker_limit_for_siliconflow_forces_serial_mode(self):
        config = SimpleNamespace(provider="siliconflow")
        with patch.dict(os.environ, {"API_AUTOMATION_AI_CHUNK_MAX_WORKERS": "4"}, clear=False):
            self.assertEqual(_get_chunk_max_workers(5, config), 1)

    def test_extract_request_centered_chunks_groups_by_request_context(self):
        document = (
            "接口一\nPOST /api/login\n用于登录获取 token。\n\n"
            "接口二\nGET /api/profile\n用于获取用户详情。\n\n"
            "接口三\nPOST /api/logout\n用于退出登录。"
        )
        requests_payload = [
            ParsedRequestData(name="登录", method="POST", url="/api/login"),
            ParsedRequestData(name="详情", method="GET", url="/api/profile"),
            ParsedRequestData(name="退出", method="POST", url="/api/logout"),
        ]

        chunks = _extract_request_centered_chunks(document, requests_payload, max_chunk_chars=120)

        self.assertGreaterEqual(len(chunks), 2)
        first_chunk_text, first_chunk_requests = chunks[0]
        self.assertIn("/api/login", first_chunk_text)
        self.assertTrue(first_chunk_requests)

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

        payloads, truncated_chunk, truncated_preparsed, used_timeout_split, used_connection_split = _invoke_ai_for_chunk_with_timeout_fallback(
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
        self.assertFalse(used_connection_split)

    @patch("api_automation.ai_parser._invoke_ai_for_chunk")
    def test_connection_error_fallback_splits_large_chunk_and_recovers(self, mock_invoke_ai_for_chunk):
        def side_effect(*args, **kwargs):
            chunk_content = kwargs["chunk_content"]
            if len(chunk_content) > 3000:
                raise Exception("Connection error.")
            return {"requests": []}, False, False

        mock_invoke_ai_for_chunk.side_effect = side_effect

        payloads, truncated_chunk, truncated_preparsed, used_timeout_split, used_connection_split = _invoke_ai_for_chunk_with_timeout_fallback(
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
        self.assertTrue(used_connection_split)
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
        self.assertIn("鍥為€€", note)

    def test_build_ai_failure_note_for_timeout_is_friendly(self):
        note = _build_ai_failure_note(Exception("Request timed out."))

        self.assertIn("请求超时", note)
        self.assertIn("缂╁皬鏂囨。鍒嗙墖", note)
        self.assertIn("鍥為€€", note)


    def test_build_ai_failure_note_for_connection_error_is_friendly(self):
        note = _build_ai_failure_note(Exception("Connection error."))

        self.assertIn("AI 网关连接异常", note)
        self.assertIn("Connection error", note)
        self.assertIn("缂╁皬鏂囨。鍒嗙墖", note)
        self.assertIn("鍥為€€", note)

    @patch("api_automation.ai_parser._invoke_ai_for_chunk_with_timeout_fallback")
    @patch("api_automation.ai_parser.load_document_content_for_ai")
    @patch("api_automation.ai_parser.get_api_automation_prompt")
    @patch("api_automation.ai_parser.LLMConfig.objects.filter")
    def test_enhance_import_result_with_ai_reuses_cached_result(
        self,
        mock_filter,
        mock_get_prompt,
        mock_load_document,
        mock_invoke_chunk,
    ):
        cache.clear()
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_get_prompt.return_value = ("prompt-template", "builtin_default", "API自动化解析")
        mock_load_document.return_value = ("# Demo API\nGET /users", "text_document", False)
        mock_invoke_chunk.return_value = (
            [
                {
                    "requests": [
                        {
                            "name": "List users",
                            "method": "GET",
                            "url": "/users",
                        }
                    ],
                    "summary": "识别到 1 个接口",
                }
            ],
            False,
            False,
            False,
            False,
        )

        result_first = enhance_import_result_with_ai(
            file_path="demo.md",
            user=SimpleNamespace(pk=1001),
            source_type="text_document",
            base_requests=[],
        )
        result_second = enhance_import_result_with_ai(
            file_path="demo.md",
            user=SimpleNamespace(pk=1001),
            source_type="text_document",
            base_requests=[],
        )

        self.assertTrue(result_first.used)
        self.assertFalse(result_first.cache_hit)
        self.assertTrue(result_second.used)
        self.assertTrue(result_second.cache_hit)
        self.assertEqual(mock_invoke_chunk.call_count, 1)
        self.assertEqual(result_second.requests[0].name, "List users")
        cache.clear()

    @patch("api_automation.ai_parser.httpx.post")
    @patch("api_automation.ai_parser.load_document_content_for_ai")
    @patch("api_automation.ai_parser.get_api_automation_prompt")
    @patch("api_automation.ai_parser.LLMConfig.objects.filter")
    def test_enhance_import_result_short_circuits_when_gateway_returns_empty_content(
        self,
        mock_filter,
        mock_get_prompt,
        mock_load_document,
        mock_httpx_post,
    ):
        cache.clear()
        mock_filter.return_value.first.return_value = SimpleNamespace(
            name="gpt-5.4",
            provider="openai_compatible",
            api_url="https://example.com/v1",
            api_key="test-key",
        )
        mock_get_prompt.return_value = ("prompt-template", "builtin_default", "API自动化解析")

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {"role": "assistant"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "completion_tokens": 7,
                "total_tokens": 19,
            },
        }
        mock_httpx_post.return_value = response

        result = enhance_import_result_with_ai(
            file_path="demo.md",
            user=SimpleNamespace(pk=1001),
            source_type="text_document",
            base_requests=[],
        )

        self.assertFalse(result.used)
        self.assertIn("未返回可解析正文", result.note)
        mock_load_document.assert_not_called()
        cache.clear()


class ApiAutomationAICaseGeneratorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="casegen_admin",
            email="casegen_admin@example.com",
            password="testpass123",
        )
        self.project = Project.objects.create(
            name="AI Case Project",
            description="project for ai case generation tests",
            creator=self.user,
        )
        self.collection = ApiCollection.objects.create(
            project=self.project,
            name="Order APIs",
            creator=self.user,
        )
        self.api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            headers={"X-Env": "test"},
            params={},
            body_type="json",
            body={"sku": "A100", "qty": 1},
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )

    def _create_execution_record(
        self,
        *,
        suffix: str,
        status: str,
        passed: bool,
        status_code: int | None,
        test_case_name: str,
        error_message: str = "",
        assertions_results: list[dict] | None = None,
        response_snapshot: dict | None = None,
        request_snapshot: dict | None = None,
    ) -> ApiExecutionRecord:
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=self.api_request,
            name=test_case_name,
            status="ready",
            script={},
            assertions=[],
            creator=self.user,
        )
        return ApiExecutionRecord.objects.create(
            project=self.project,
            request=self.api_request,
            test_case=test_case,
            environment=None,
            run_id=f"run-{suffix}",
            run_name=f"Run {suffix}",
            request_name=test_case_name,
            method=self.api_request.method,
            url=self.api_request.url,
            status=status,
            passed=passed,
            status_code=status_code,
            response_time=128.5,
            request_snapshot=request_snapshot or {},
            response_snapshot=response_snapshot or {},
            assertions_results=assertions_results or [],
            error_message=error_message,
            executor=self.user,
        )

    def _seed_reference_context(self):
        requirement_document = RequirementDocument.objects.create(
            project=self.project,
            title="CMS订单接口需求说明",
            description="覆盖订单创建、鉴权、幂等与库存校验。",
            document_type="md",
            content="创建订单接口需要校验登录态、库存余量、SKU 合法性，并返回订单号。",
            status="review_completed",
            uploader=self.user,
        )
        RequirementModule.objects.create(
            document=requirement_document,
            title="创建订单接口规则",
            content=(
                "接口 /api/orders 必须校验 token 是否有效；成功后返回 data.orderNo。"
                "库存不足时返回 409，并给出明确错误信息。"
            ),
            order=1,
            is_auto_generated=False,
        )
        RequirementModule.objects.create(
            document=requirement_document,
            title="用户资料模块",
            content="这个模块主要描述用户资料查询，与订单创建无关。",
            order=2,
            is_auto_generated=False,
        )

        knowledge_base = KnowledgeBase.objects.create(
            name="CMS接口知识库",
            description="API automation knowledge",
            project=self.project,
            creator=self.user,
            is_active=True,
        )
        knowledge_document = KnowledgeDocument.objects.create(
            knowledge_base=knowledge_base,
            title="订单接口排错手册",
            document_type="txt",
            content=(
                "Create order API troubleshooting: when Authorization token is missing, the service returns 401. "
                "When inventory is insufficient, return 409 and message inventory not enough."
            ),
            status="completed",
            uploader=self.user,
        )
        DocumentChunk.objects.create(
            document=knowledge_document,
            chunk_index=0,
            content="POST /api/orders should assert response code 200 and data.orderNo exists on success.",
        )
        DocumentChunk.objects.create(
            document=knowledge_document,
            chunk_index=1,
            content="Notification webhook troubleshooting for /api/webhooks/notify with event callback retries.",
        )
        return requirement_document, knowledge_document

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_append_generation_deduplicates_by_effective_request_and_assertion_semantics(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        existing_case = ApiTestCase.objects.create(
            project=self.project,
            request=self.api_request,
            name="Create order - Existing baseline",
            status="ready",
            script={"request_overrides": {}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated 3 candidate cases, including semantic duplicates.",
                    "cases": [
                        {
                            "name": "Create order - Explicit baseline copy",
                            "description": "Same as the existing baseline, but repeats default request fields explicitly.",
                            "status": "ready",
                            "tags": ["ai-generated", "positive"],
                            "assertions": [
                                {"assertion_type": "status_code", "expected_number": 200},
                            ],
                            "request_overrides": {
                                "method": "POST",
                                "url": "/api/orders",
                                "headers": [{"name": "X-Env", "value": "test", "enabled": True, "order": 0}],
                                "body_mode": "json",
                                "body_json": {"qty": 1, "sku": "A100"},
                                "timeout_ms": 30000,
                            },
                        },
                        {
                            "name": "Create order - Order number exists",
                            "description": "Checks whether the response contains an order number.",
                            "status": "ready",
                            "tags": ["ai-generated", "regression"],
                            "assertions": [
                                {"assertion_type": "exists", "selector": "data.orderNo"},
                                {"assertion_type": "status_code", "expected_number": 200},
                            ],
                            "request_overrides": {
                                "headers": [
                                    {"name": "X-Trace", "value": "scene-1", "enabled": True, "order": 1},
                                    {"name": "X-Env", "value": "test", "enabled": True, "order": 0},
                                ],
                                "body_mode": "json",
                                "body_json": {"sku": "A100", "qty": 1},
                            },
                        },
                        {
                            "name": "Create order - Order number exists copy",
                            "description": "Semantically the same as the previous case, but with reordered fields and assertions.",
                            "status": "ready",
                            "tags": ["ai-generated", "smoke"],
                            "assertions": [
                                {"assertion_type": "status_code", "expected_number": 200},
                                {"assertion_type": "exists", "selector": "data.orderNo"},
                            ],
                            "request_overrides": {
                                "headers": [
                                    {"name": "X-Env", "value": "test", "enabled": True, "order": 0},
                                    {"name": "X-Trace", "value": "scene-1", "enabled": True, "order": 1},
                                ],
                                "body_mode": "json",
                                "body_json": {"qty": 1, "sku": "A100"},
                                "timeout_ms": 30000,
                            },
                        },
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[existing_case],
            mode="append",
            count=3,
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(len(result.cases), 1)
        self.assertEqual(result.cases[0].name, "Create order - Order number exists")
        self.assertEqual(result.cases[0].assertions[0]["assertion_type"], "exists")

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_reuses_cached_ai_result(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated 1 cached case.",
                    "cases": [
                        {
                            "name": "Create order - Cached smoke",
                            "description": "Ensures cache reuse works.",
                            "status": "ready",
                            "tags": ["ai-generated", "smoke"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "extractors": [{"source": "json_path", "selector": "data.id", "variable_name": "order_id"}],
                            "request_overrides": {
                                "headers": [{"name": "X-Scene", "value": "cache", "enabled": True, "order": 0}],
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        first_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )
        second_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self.assertTrue(first_result.used_ai)
        self.assertFalse(first_result.cache_hit)
        self.assertTrue(second_result.used_ai)
        self.assertTrue(second_result.cache_hit)
        self.assertEqual(mock_safe_invoke.call_count, 1)
        self.assertEqual(second_result.case_summaries[0]["override_sections"], ["headers"])
        self.assertEqual(second_result.case_summaries[0]["extractor_variables"], ["order_id"])
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_ai_generation_normalizes_rich_http_overrides_and_persists_specs(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generate richer HTTP coverage.",
                    "cases": [
                        {
                            "name": "Create order - Cookie auth multipart upload",
                            "description": "Uses multipart payload, cookie auth, transport overrides and richer assertions.",
                            "status": "ready",
                            "tags": ["ai-generated", "multipart"],
                            "assertions": [
                                {"type": "status_range", "min_value": "200", "max_value": "299"},
                                {"type": "header", "path": "Content-Type", "operator": "contains", "expected": "json"},
                                {"type": "response_time", "operator": "lte", "expected_number": "1500"},
                                {
                                    "type": "json_schema",
                                    "schema_text": {
                                        "type": "object",
                                        "properties": {"code": {"type": "integer"}},
                                    },
                                },
                            ],
                            "extractors": [
                                {"type": "header", "path": "X-Trace-Id", "name": "trace_id", "required": "true"},
                            ],
                            "request_overrides": {
                                "body_type": "multipart",
                                "body": {"scene": "avatar"},
                                "cookies": {"locale": "zh-CN"},
                                "files": [
                                    {
                                        "name": "file",
                                        "path": "{{avatar_path}}",
                                        "filename": "avatar.png",
                                        "contentType": "image/png",
                                    }
                                ],
                                "auth": {
                                    "type": "apikey",
                                    "in": "cookie",
                                    "key": "sessionid",
                                    "value": "{{session_cookie}}",
                                    "variable": "session_cookie",
                                },
                                "transport": {
                                    "verify": "false",
                                    "follow_redirect": "false",
                                    "retries": "2",
                                    "retry_interval": "800",
                                    "proxy": "http://127.0.0.1:7890",
                                },
                                "timeout_ms": "45000",
                            },
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(len(result.cases), 1)
        draft = result.cases[0]
        self.assertIn("supported_auth_types", mock_safe_invoke.call_args.args[1][1].content)
        self.assertEqual(draft.request_overrides["body_mode"], "multipart")
        self.assertEqual(draft.request_overrides["multipart_parts"][0]["name"], "scene")
        self.assertEqual(draft.request_overrides["files"][0]["field_name"], "file")
        self.assertEqual(draft.request_overrides["files"][0]["content_type"], "image/png")
        self.assertEqual(draft.request_overrides["auth"]["auth_type"], "api_key")
        self.assertEqual(draft.request_overrides["auth"]["api_key_in"], "cookie")
        self.assertFalse(draft.request_overrides["transport"]["verify_ssl"])
        self.assertFalse(draft.request_overrides["transport"]["follow_redirects"])
        self.assertEqual(draft.request_overrides["transport"]["retry_count"], 2)
        self.assertEqual(draft.request_overrides["transport"]["retry_interval_ms"], 800)
        self.assertEqual(draft.request_overrides["timeout_ms"], 45000)
        self.assertEqual(draft.assertions[0]["min_value"], 200)
        self.assertEqual(draft.assertions[3]["schema_text"], '{"type": "object", "properties": {"code": {"type": "integer"}}}')
        self.assertTrue(draft.extractors[0]["required"])

        created_cases = create_test_cases_from_drafts(
            api_request=self.api_request,
            drafts=result.cases,
            creator=self.user,
        )

        self.assertEqual(len(created_cases), 1)
        stored_override = serialize_test_case_override(created_cases[0])
        stored_assertions = serialize_assertion_specs(created_cases[0])
        stored_extractors = serialize_extractor_specs(created_cases[0])
        self.assertEqual(stored_override["body_mode"], "multipart")
        self.assertEqual(stored_override["cookies"][0]["name"], "locale")
        self.assertEqual(stored_override["files"][0]["field_name"], "file")
        self.assertEqual(stored_override["files"][0]["content_type"], "image/png")
        self.assertEqual(stored_override["auth"]["auth_type"], "api_key")
        self.assertEqual(stored_override["auth"]["api_key_in"], "cookie")
        self.assertEqual(stored_override["transport"]["verify_ssl"], False)
        self.assertEqual(stored_override["transport"]["follow_redirects"], False)
        self.assertEqual(stored_override["transport"]["retry_count"], 2)
        self.assertEqual(stored_assertions[0]["assertion_type"], "status_range")
        self.assertEqual(stored_assertions[0]["min_value"], 200.0)
        self.assertEqual(stored_extractors[0]["source"], "header")
        self.assertEqual(stored_extractors[0]["variable_name"], "trace_id")

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_prompt_includes_recent_execution_history_context(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        self._create_execution_record(
            suffix="history-failed",
            status="failed",
            passed=False,
            status_code=401,
            test_case_name="Create order - expired token",
            error_message="token invalid",
            assertions_results=[
                {"index": 1, "type": "status_code", "expected": 200, "actual": 401, "passed": False},
            ],
            response_snapshot={"body": {"message": "token invalid"}},
            request_snapshot={
                "main_request_blocked": True,
                "workflow_summary": {
                    "enabled": True,
                    "configured_step_count": 1,
                    "executed_step_count": 1,
                    "main_request_executed": False,
                },
                "workflow_steps": [
                    {
                        "index": 0,
                        "name": "Refresh login token",
                        "stage": "prepare",
                        "status": "failed",
                        "status_code": 401,
                        "error_message": "refresh token expired",
                    }
                ],
            },
        )
        self._create_execution_record(
            suffix="history-success",
            status="success",
            passed=True,
            status_code=200,
            test_case_name="Create order - stable baseline",
            assertions_results=[
                {"index": 1, "type": "status_code", "expected": 200, "actual": 200, "passed": True},
                {"index": 2, "type": "exists", "path": "data.orderNo", "passed": True},
            ],
            response_snapshot={"body": {"message": "ok"}},
        )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with history context.",
                    "cases": [
                        {
                            "name": "Create order - auth retry",
                            "description": "Covers auth retry.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertIn("recent_failed_examples", prompt_text)
        self.assertIn("token invalid", prompt_text)
        self.assertIn("auth_or_permission", prompt_text)
        self.assertIn("Create order - stable baseline", prompt_text)
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_cache_key_changes_when_execution_history_changes(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with cache-awareness.",
                    "cases": [
                        {
                            "name": "Create order - cache refresh",
                            "description": "Ensures history digest participates in cache key.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        first_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self._create_execution_record(
            suffix="cache-new-failure",
            status="failed",
            passed=False,
            status_code=500,
            test_case_name="Create order - new failure signal",
            error_message="inventory service unavailable",
            assertions_results=[
                {"index": 1, "type": "status_code", "expected": 200, "actual": 500, "passed": False},
            ],
            response_snapshot={"body": {"message": "inventory service unavailable"}},
        )

        second_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self.assertTrue(first_result.used_ai)
        self.assertFalse(first_result.cache_hit)
        self.assertTrue(second_result.used_ai)
        self.assertFalse(second_result.cache_hit)
        self.assertNotEqual(first_result.cache_key, second_result.cache_key)
        self.assertEqual(mock_safe_invoke.call_count, 2)
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_history_context_uses_recent_bounded_examples(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        for index in range(1, 6):
            self._create_execution_record(
                suffix=f"failed-{index}",
                status="failed",
                passed=False,
                status_code=400 + index,
                test_case_name=f"History failed case {index}",
                error_message=f"failed marker {index}",
                assertions_results=[
                    {"index": 1, "type": "status_code", "expected": 200, "actual": 400 + index, "passed": False},
                ],
                response_snapshot={"body": {"message": f"failed marker {index}"}},
            )
        for index in range(1, 4):
            self._create_execution_record(
                suffix=f"success-{index}",
                status="success",
                passed=True,
                status_code=200,
                test_case_name=f"History success case {index}",
                assertions_results=[
                    {"index": 1, "type": "status_code", "expected": 200, "actual": 200, "passed": True},
                ],
                response_snapshot={"body": {"message": f"success marker {index}"}},
            )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with bounded history.",
                    "cases": [
                        {
                            "name": "Create order - bounded history",
                            "description": "Ensures only recent examples are injected.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertIn("History failed case 5", prompt_text)
        self.assertIn("History failed case 4", prompt_text)
        self.assertIn("History failed case 3", prompt_text)
        self.assertNotIn("History failed case 1", prompt_text)
        self.assertIn("History success case 3", prompt_text)
        self.assertIn("History success case 2", prompt_text)
        self.assertNotIn("History success case 1", prompt_text)
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_prompt_includes_project_requirement_and_knowledge_context(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        self._seed_reference_context()
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with project references.",
                    "cases": [
                        {
                            "name": "Create order - project context",
                            "description": "Uses requirement and knowledge references.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertIn('"reference_available": true', prompt_text)
        self.assertIn("创建订单接口规则", prompt_text)
        self.assertIn("订单接口排错手册", prompt_text)
        self.assertIn("inventory not enough", prompt_text)
        self.assertNotIn("/api/webhooks/notify", prompt_text)
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_cache_key_changes_when_reference_context_changes(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        requirement_document, _knowledge_document = self._seed_reference_context()
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with project reference cache-awareness.",
                    "cases": [
                        {
                            "name": "Create order - doc cache refresh",
                            "description": "Ensures document digest participates in cache key.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        first_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        module = requirement_document.modules.get(title="创建订单接口规则")
        module.content = f"{module.content} 新增规则：重复请求时应返回 409 并提示幂等冲突。"
        module.save(update_fields=["content", "updated_at"])

        second_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self.assertTrue(first_result.used_ai)
        self.assertFalse(first_result.cache_hit)
        self.assertTrue(second_result.used_ai)
        self.assertFalse(second_result.cache_hit)
        self.assertNotEqual(first_result.cache_key, second_result.cache_key)
        self.assertEqual(mock_safe_invoke.call_count, 2)
        cache.clear()

    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_reference_context_is_bounded_per_source(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        requirement_document, knowledge_document = self._seed_reference_context()
        for index in range(2, 6):
            RequirementModule.objects.create(
                document=requirement_document,
                title=f"鍒涘缓璁㈠崟琛ュ厖瑙勫垯 {index}",
                content=f"/api/orders additional rule {index}: verify sku and qty boundary {index}.",
                order=index,
                is_auto_generated=False,
            )
        for index in range(2, 5):
            DocumentChunk.objects.create(
                document=knowledge_document,
                chunk_index=index,
                content=f"/api/orders chunk {index}: response should include orderNo and verify auth token.",
            )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with bounded project references.",
                    "cases": [
                        {
                            "name": "Create order - bounded project references",
                            "description": "Ensures per-source bounds stay stable.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertEqual(prompt_text.count('"source": "requirement_module"'), 2)
        self.assertEqual(prompt_text.count('"source": "knowledge_chunk"'), 2)
        self.assertLessEqual(prompt_text.count('"source": "requirement_document"'), 1)
        self.assertLessEqual(prompt_text.count('"source": "knowledge_document"'), 1)
        cache.clear()

    @patch("api_automation.ai_case_generator._collect_knowledge_references_with_hybrid_search")
    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_prompt_prefers_hybrid_knowledge_retrieval_when_available(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
        mock_hybrid_references,
    ):
        cache.clear()
        self._seed_reference_context()
        mock_hybrid_references.return_value = {
            "references": [
                {
                    "source": "knowledge_chunk",
                    "title": "订单接口语义检索片段",
                    "container_title": "CMS接口知识库",
                    "snippet": "semantic retrieval says inventory not enough should return 409 and provide a clear error message.",
                    "score": 92,
                    "matched_terms": ["orders"],
                    "recency_rank": 3,
                    "similarity_score": 0.92,
                    "retrieval_method": "hybrid",
                }
            ],
            "summary": {
                "query": "POST /api/orders",
                "knowledge_base_count": 1,
                "searched_knowledge_bases": ["CMS接口知识库"],
                "used_hybrid_search": True,
                "fallback_used": False,
                "result_count": 1,
            },
        }
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with hybrid retrieval.",
                    "cases": [
                        {
                            "name": "Create order - hybrid retrieval",
                            "description": "Uses hybrid retrieval knowledge.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertIn('"used_hybrid_search": true', prompt_text)
        self.assertIn("semantic retrieval says inventory not enough should return 409", prompt_text)
        self.assertNotIn("/api/webhooks/notify", prompt_text)
        cache.clear()

    @patch("api_automation.ai_case_generator._collect_knowledge_references_with_hybrid_search")
    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_falls_back_to_keyword_knowledge_context_when_hybrid_retrieval_is_unavailable(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
        mock_hybrid_references,
    ):
        cache.clear()
        self._seed_reference_context()
        mock_hybrid_references.return_value = {
            "references": [],
            "summary": {
                "query": "POST /api/orders",
                "knowledge_base_count": 1,
                "searched_knowledge_bases": ["CMS接口知识库"],
                "used_hybrid_search": False,
                "fallback_used": True,
                "result_count": 0,
                "error": "vector store unavailable",
            },
        }
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with fallback keyword references.",
                    "cases": [
                        {
                            "name": "Create order - fallback retrieval",
                            "description": "Uses fallback keyword references.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        prompt_text = mock_safe_invoke.call_args.args[1][1].content
        self.assertTrue(result.used_ai)
        self.assertIn('"fallback_used": true', prompt_text)
        self.assertIn("订单接口排错手册", prompt_text)
        self.assertIn("inventory not enough", prompt_text)
        cache.clear()

    @patch("api_automation.ai_case_generator._collect_knowledge_references_with_hybrid_search")
    @patch("api_automation.ai_case_generator.create_llm_instance")
    @patch("api_automation.ai_case_generator.LLMConfig.objects.filter")
    @patch("api_automation.ai_case_generator.safe_llm_invoke")
    def test_generation_cache_key_changes_when_hybrid_knowledge_context_changes(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
        mock_hybrid_references,
    ):
        cache.clear()
        mock_hybrid_references.side_effect = [
            {
                "references": [
                    {
                        "source": "knowledge_chunk",
                        "title": "璁㈠崟璇箟鐗囨A",
                        "container_title": "CMS接口知识库",
                        "snippet": "first semantic retrieval context",
                        "score": 88,
                        "matched_terms": ["orders"],
                        "recency_rank": 3,
                        "similarity_score": 0.88,
                        "retrieval_method": "hybrid",
                    }
                ],
                "summary": {
                    "query": "POST /api/orders",
                    "knowledge_base_count": 1,
                    "searched_knowledge_bases": ["CMS接口知识库"],
                    "used_hybrid_search": True,
                    "fallback_used": False,
                    "result_count": 1,
                },
            },
            {
                "references": [
                    {
                        "source": "knowledge_chunk",
                        "title": "璁㈠崟璇箟鐗囨B",
                        "container_title": "CMS接口知识库",
                        "snippet": "second semantic retrieval context",
                        "score": 90,
                        "matched_terms": ["orders"],
                        "recency_rank": 3,
                        "similarity_score": 0.9,
                        "retrieval_method": "hybrid",
                    }
                ],
                "summary": {
                    "query": "POST /api/orders",
                    "knowledge_base_count": 1,
                    "searched_knowledge_bases": ["CMS接口知识库"],
                    "used_hybrid_search": True,
                    "fallback_used": False,
                    "result_count": 1,
                },
            },
        ]
        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "Generated with hybrid retrieval cache-awareness.",
                    "cases": [
                        {
                            "name": "Create order - hybrid cache refresh",
                            "description": "Ensures hybrid retrieval digest participates in cache key.",
                            "status": "ready",
                            "tags": ["ai-generated"],
                            "assertions": [{"assertion_type": "status_code", "expected_number": 200}],
                            "request_overrides": {},
                        }
                    ],
                },
                ensure_ascii=False,
            )
        )

        first_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )
        second_result = generate_test_case_drafts_with_ai(
            api_request=self.api_request,
            user=self.user,
            existing_cases=[],
            mode="append",
            count=1,
        )

        self.assertTrue(first_result.used_ai)
        self.assertFalse(first_result.cache_hit)
        self.assertTrue(second_result.used_ai)
        self.assertFalse(second_result.cache_hit)
        self.assertNotEqual(first_result.cache_key, second_result.cache_key)
        self.assertEqual(mock_safe_invoke.call_count, 2)
        cache.clear()


class ApiAutomationImporterParsingTests(SimpleTestCase):
    def test_environment_suggestions_include_auth_and_variable_recommendations(self):
        parsed_requests = [
            ParsedRequestData(
                name="鐢ㄦ埛鐧诲綍",
                method="POST",
                url="/api/login",
                body_type="json",
                body={"phone": "{{phone}}", "password": "{{password}}"},
            ),
            ParsedRequestData(
                name="鏌ヨ鐢ㄦ埛淇℃伅",
                method="GET",
                url="/api/user/profile",
                headers={"Authorization": "Bearer {{token}}"},
            ),
        ]
        created_requests = [
            SimpleNamespace(id=11, name="鐢ㄦ埛鐧诲綍", method="POST", url="/api/login", collection=SimpleNamespace(name="auth")),
            SimpleNamespace(id=12, name="鏌ヨ鐢ㄦ埛淇℃伅", method="GET", url="/api/user/profile", collection=SimpleNamespace(name="user")),
        ]

        suggestions = _build_environment_suggestions(
            parsed_requests=parsed_requests,
            created_requests=created_requests,
            environment_drafts=[{"name": "娴嬭瘯鐜", "base_url": "https://cms-test.example.com/api"}],
            saved_environments=[],
            primary_environment_draft={"base_url": "https://cms-test.example.com/api"},
            primary_environment=None,
        )

        self.assertEqual(suggestions["base_url_candidates"][0]["base_url"], "https://cms-test.example.com/api")
        self.assertEqual(suggestions["auth_suggestions"][0]["request_name"], "鐢ㄦ埛鐧诲綍")
        self.assertEqual(suggestions["auth_suggestions"][0]["token_path"], "data.token")
        patch_variables = {item["name"]: item["value"] for item in suggestions["environment_patch"]["variables"]}
        self.assertEqual(patch_variables["auth_request_name"], "鐢ㄦ埛鐧诲綍")
        self.assertEqual(patch_variables["auth_token_path"], "data.token")
        self.assertIn("phone", patch_variables)
        self.assertIn("password", patch_variables)
        self.assertIn("token", patch_variables)

    def test_postman_collection_preserves_query_auth_and_multipart_files(self):
        collection = {
            "info": {"name": "Demo"},
            "item": [
                {
                    "name": "Upload avatar",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "https://example.com/api/users/upload?tenant=cms",
                            "query": [{"key": "tenant", "value": "cms"}],
                        },
                        "auth": {
                            "type": "bearer",
                            "bearer": [{"key": "token", "value": "{{token}}"}],
                        },
                        "header": [{"key": "X-Trace-Id", "value": "{{trace_id}}"}],
                        "body": {
                            "mode": "formdata",
                            "formdata": [
                                {"key": "scene", "value": "avatar", "type": "text"},
                                {"key": "file", "type": "file", "src": "/tmp/avatar.png"},
                            ],
                        },
                    },
                }
            ],
        }

        requests = parse_postman_collection(collection)

        self.assertEqual(len(requests), 1)
        parsed = requests[0]
        self.assertEqual(parsed.params["tenant"], "cms")
        self.assertEqual(parsed.body_type, "form")
        self.assertEqual(parsed.request_spec["body_mode"], "multipart")
        self.assertEqual(parsed.request_spec["auth"]["auth_type"], "bearer")
        self.assertEqual(parsed.request_spec["files"][0]["field_name"], "file")
        self.assertEqual(parsed.request_spec["multipart_parts"][0]["name"], "scene")

    def test_postman_collection_inherits_collection_and_folder_auth(self):
        collection = {
            "info": {"name": "Demo"},
            "auth": {
                "type": "bearer",
                "bearer": [{"key": "token", "value": "{{collection_token}}"}],
            },
            "item": [
                {
                    "name": "鐢ㄦ埛妯″潡",
                    "auth": {
                        "type": "basic",
                        "basic": [
                            {"key": "username", "value": "demo"},
                            {"key": "password", "value": "secret"},
                        ],
                    },
                    "item": [
                        {
                            "name": "鐧诲綍鎺ュ彛",
                            "request": {
                                "method": "POST",
                                "url": "https://example.com/api/login",
                            },
                        },
                        {
                            "name": "鍏紑淇℃伅",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "https://example.com/api/public?tenant=cms",
                                    "query": [
                                        {"key": "tenant", "value": "cms"},
                                        {"key": "debug", "value": "1", "disabled": True},
                                    ],
                                },
                                "auth": {"type": "noauth"},
                                "header": [
                                    {"key": "X-Debug", "value": "1", "disabled": True},
                                    {"key": "X-Scene", "value": "public"},
                                ],
                            },
                        },
                    ],
                },
                {
                    "name": "璧勬枡鎺ュ彛",
                    "request": {
                        "method": "GET",
                        "url": "https://example.com/api/profile",
                    },
                },
            ],
        }

        requests = parse_postman_collection(collection)

        login_request = next(item for item in requests if item.name == "鐧诲綍鎺ュ彛")
        public_request = next(item for item in requests if item.name == "鍏紑淇℃伅")
        profile_request = next(item for item in requests if item.name == "璧勬枡鎺ュ彛")

        self.assertEqual(login_request.request_spec["auth"]["auth_type"], "basic")
        self.assertEqual(login_request.request_spec["auth"]["username"], "demo")
        self.assertEqual(public_request.request_spec["auth"]["auth_type"], "none")
        self.assertEqual(public_request.request_spec["query"][0]["name"], "tenant")
        self.assertEqual(public_request.request_spec["headers"][0]["name"], "X-Scene")
        self.assertEqual(profile_request.request_spec["auth"]["auth_type"], "bearer")
        self.assertEqual(profile_request.request_spec["auth"]["token_value"], "{{collection_token}}")

    def test_openapi_document_supports_vendor_json_graphql_and_multipart(self):
        spec = {
            "openapi": "3.0.1",
            "paths": {
                "/graphql": {
                    "post": {
                        "summary": "Run GraphQL",
                        "requestBody": {
                            "content": {
                                "application/graphql": {
                                    "example": {
                                        "query": "query GetUser { user { id } }",
                                        "variables": {"tenant": "cms"},
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/vendor-json": {
                    "post": {
                        "summary": "Vendor JSON",
                        "requestBody": {
                            "content": {
                                "application/vnd.api+json": {
                                    "example": {"title": "hello"}
                                }
                            }
                        },
                        "responses": {"201": {"description": "created"}},
                    }
                },
                "/upload": {
                    "post": {
                        "summary": "Upload file",
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "scene": {"type": "string", "default": "avatar"},
                                            "file": {"type": "string", "format": "binary"},
                                        },
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
        }

        requests = parse_openapi_document(spec)

        graphql_request = next(item for item in requests if item.name == "Run GraphQL")
        vendor_request = next(item for item in requests if item.name == "Vendor JSON")
        upload_request = next(item for item in requests if item.name == "Upload file")

        self.assertEqual(graphql_request.request_spec["body_mode"], "graphql")
        self.assertEqual(graphql_request.request_spec["graphql_variables"]["tenant"], "cms")
        self.assertEqual(vendor_request.request_spec["body_mode"], "json")
        self.assertEqual(vendor_request.body_type, "json")
        self.assertEqual(upload_request.request_spec["body_mode"], "multipart")
        self.assertEqual(upload_request.request_spec["files"][0]["field_name"], "file")
        self.assertEqual(upload_request.request_spec["multipart_parts"][0]["name"], "scene")

    def test_openapi_document_supports_graphql_json_cookie_vendor_xml_and_encoded_multipart(self):
        spec = {
            "openapi": "3.1.0",
            "paths": {
                "/graphql-json": {
                    "post": {
                        "summary": "GraphQL JSON",
                        "parameters": [
                            {
                                "name": "sessionid",
                                "in": "cookie",
                                "schema": {"default": "cookie-1"},
                            }
                        ],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "query": "query GetUser { user { id } }",
                                        "operationName": "GetUser",
                                        "variables": {"tenant": "cms"},
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/vendor-xml": {
                    "post": {
                        "summary": "Vendor XML",
                        "requestBody": {
                            "content": {
                                "application/vnd.cms+xml": {
                                    "example": "<Request><scene>cms</scene></Request>"
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/upload-media": {
                    "post": {
                        "summary": "Upload media",
                        "requestBody": {
                            "content": {
                                "multipart/form-data": {
                                    "encoding": {
                                        "file": {"contentType": "image/png"},
                                        "attachments": {"contentType": "application/pdf"},
                                    },
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "scene": {"type": "string", "default": "avatar"},
                                            "file": {"type": "string", "format": "binary"},
                                            "attachments": {
                                                "type": "array",
                                                "items": {"type": "string", "format": "binary"},
                                            },
                                        },
                                    },
                                }
                            }
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
        }

        requests = parse_openapi_document(spec)

        graphql_request = next(item for item in requests if item.name == "GraphQL JSON")
        vendor_xml_request = next(item for item in requests if item.name == "Vendor XML")
        upload_request = next(item for item in requests if item.name == "Upload media")

        self.assertEqual(graphql_request.request_spec["body_mode"], "graphql")
        self.assertEqual(graphql_request.request_spec["graphql_operation_name"], "GetUser")
        self.assertEqual(graphql_request.request_spec["cookies"][0]["name"], "sessionid")
        self.assertEqual(vendor_xml_request.request_spec["body_mode"], "xml")
        self.assertIn("<Request>", vendor_xml_request.request_spec["xml_text"])
        self.assertEqual(upload_request.request_spec["body_mode"], "multipart")
        self.assertEqual(upload_request.request_spec["files"][0]["content_type"], "image/png")
        self.assertEqual(upload_request.request_spec["files"][1]["field_name"], "attachments")
        self.assertEqual(upload_request.request_spec["files"][1]["content_type"], "application/pdf")
        self.assertEqual(upload_request.request_spec["multipart_parts"][0]["name"], "scene")

    def test_openapi_document_maps_security_schemes_to_structured_auth(self):
        spec = {
            "openapi": "3.0.3",
            "components": {
                "securitySchemes": {
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                    },
                    "BasicAuth": {
                        "type": "http",
                        "scheme": "basic",
                    },
                    "QueryKey": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_key",
                    },
                    "CookieSession": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "sessionid",
                    },
                    "OAuthAuth": {
                        "type": "oauth2",
                        "flows": {
                            "clientCredentials": {
                                "tokenUrl": "https://example.com/oauth/token",
                                "scopes": {},
                            }
                        },
                    },
                }
            },
            "security": [{"BearerAuth": []}],
            "paths": {
                "/profile": {
                    "get": {
                        "summary": "Profile",
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/admin": {
                    "get": {
                        "summary": "Admin",
                        "security": [{"BasicAuth": []}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/search": {
                    "get": {
                        "summary": "Search",
                        "security": [{"QueryKey": []}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/session": {
                    "get": {
                        "summary": "Session",
                        "security": [{"CookieSession": []}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/oauth": {
                    "get": {
                        "summary": "OAuth Profile",
                        "security": [{"OAuthAuth": []}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/public": {
                    "get": {
                        "summary": "Public",
                        "security": [],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
        }

        requests = parse_openapi_document(spec)

        profile_request = next(item for item in requests if item.name == "Profile")
        admin_request = next(item for item in requests if item.name == "Admin")
        search_request = next(item for item in requests if item.name == "Search")
        session_request = next(item for item in requests if item.name == "Session")
        oauth_request = next(item for item in requests if item.name == "OAuth Profile")
        public_request = next(item for item in requests if item.name == "Public")

        self.assertEqual(profile_request.request_spec["auth"]["auth_type"], "bearer")
        self.assertEqual(profile_request.request_spec["auth"]["header_name"], "Authorization")
        self.assertEqual(admin_request.request_spec["auth"]["auth_type"], "basic")
        self.assertEqual(search_request.request_spec["auth"]["auth_type"], "api_key")
        self.assertEqual(search_request.request_spec["auth"]["api_key_in"], "query")
        self.assertEqual(search_request.request_spec["auth"]["api_key_name"], "api_key")
        self.assertEqual(session_request.request_spec["auth"]["auth_type"], "cookie")
        self.assertEqual(session_request.request_spec["auth"]["cookie_name"], "sessionid")
        self.assertEqual(oauth_request.request_spec["auth"]["auth_type"], "bearer")
        self.assertEqual(public_request.request_spec["auth"]["auth_type"], "none")

    def test_swagger_document_maps_security_definitions_and_refs(self):
        spec = {
            "swagger": "2.0",
            "host": "example.com",
            "basePath": "/api",
            "schemes": ["https"],
            "securityDefinitions": {
                "BasicRef": {"$ref": "#/definitions/SecurityBasic"},
                "HeaderKey": {
                    "type": "apiKey",
                    "name": "X-API-Key",
                    "in": "header",
                },
            },
            "security": [{"HeaderKey": []}],
            "definitions": {
                "SecurityBasic": {
                    "type": "basic",
                }
            },
            "parameters": {
                "TraceId": {
                    "name": "X-Trace-Id",
                    "in": "header",
                    "type": "string",
                    "default": "trace-1",
                }
            },
            "paths": {
                "/reports": {
                    "get": {
                        "summary": "Report list",
                        "parameters": [{"$ref": "#/parameters/TraceId"}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/admin/login": {
                    "get": {
                        "summary": "Swagger Basic",
                        "security": [{"BasicRef": []}],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
        }

        requests = parse_openapi_document(spec)

        report_request = next(item for item in requests if item.name == "Report list")
        login_request = next(item for item in requests if item.name == "Swagger Basic")

        self.assertEqual(report_request.url, "https://example.com/api/reports")
        self.assertEqual(report_request.request_spec["auth"]["auth_type"], "api_key")
        self.assertEqual(report_request.request_spec["auth"]["api_key_name"], "X-API-Key")
        self.assertEqual(report_request.request_spec["headers"][0]["name"], "X-Trace-Id")
        self.assertEqual(login_request.request_spec["auth"]["auth_type"], "basic")

    def test_swagger_document_supports_body_and_formdata_parameters(self):
        spec = {
            "swagger": "2.0",
            "host": "example.com",
            "basePath": "/api",
            "schemes": ["https"],
            "paths": {
                "/users": {
                    "post": {
                        "summary": "Create user",
                        "consumes": ["application/json"],
                        "parameters": [
                            {
                                "name": "payload",
                                "in": "body",
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string", "default": "demo"},
                                        "enabled": {"type": "boolean", "default": True},
                                    },
                                },
                            }
                        ],
                        "responses": {"201": {"description": "created"}},
                    }
                },
                "/login": {
                    "post": {
                        "summary": "Login form",
                        "consumes": ["application/x-www-form-urlencoded"],
                        "parameters": [
                            {"name": "username", "in": "formData", "type": "string", "default": "admin"},
                            {"name": "password", "in": "formData", "type": "string", "default": "admin"},
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/upload": {
                    "post": {
                        "summary": "Upload legacy file",
                        "consumes": ["multipart/form-data"],
                        "parameters": [
                            {"name": "scene", "in": "formData", "type": "string", "default": "avatar"},
                            {"name": "file", "in": "formData", "type": "file"},
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
                "/xml": {
                    "post": {
                        "summary": "Legacy XML",
                        "consumes": ["application/xml"],
                        "parameters": [
                            {
                                "name": "xmlBody",
                                "in": "body",
                                "x-example": "<Request><tenant>cms</tenant></Request>",
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                },
            },
        }

        requests = parse_openapi_document(spec)

        create_user_request = next(item for item in requests if item.name == "Create user")
        login_form_request = next(item for item in requests if item.name == "Login form")
        upload_request = next(item for item in requests if item.name == "Upload legacy file")
        xml_request = next(item for item in requests if item.name == "Legacy XML")

        self.assertEqual(create_user_request.url, "https://example.com/api/users")
        self.assertEqual(create_user_request.request_spec["body_mode"], "json")
        self.assertEqual(create_user_request.request_spec["body_json"]["username"], "demo")
        self.assertTrue(create_user_request.request_spec["body_json"]["enabled"])
        self.assertEqual(create_user_request.assertion_specs[0]["expected_number"], 201)

        self.assertEqual(login_form_request.request_spec["body_mode"], "urlencoded")
        self.assertEqual(login_form_request.request_spec["form_fields"][0]["name"], "username")
        self.assertEqual(login_form_request.request_spec["form_fields"][1]["value"], "admin")

        self.assertEqual(upload_request.request_spec["body_mode"], "multipart")
        self.assertEqual(upload_request.request_spec["multipart_parts"][0]["name"], "scene")
        self.assertEqual(upload_request.request_spec["files"][0]["field_name"], "file")
        self.assertEqual(upload_request.request_spec["files"][0]["source_type"], "placeholder")

        self.assertEqual(xml_request.request_spec["body_mode"], "xml")
        self.assertIn("<Request>", xml_request.request_spec["xml_text"])

    def test_curl_import_supports_cookie_basic_auth_and_transport_flags(self):
        markdown = """
        ## Download report
        ```bash
        curl -X POST https://example.com/api/report/export?tenant=cms \\
          -u demo:secret \\
          -b sessionid=abc123;theme=light \\
          -k \\
          --proxy http://127.0.0.1:7890 \\
          -F scene=full \\
          -F file=@/tmp/report.csv
        ```
        """

        requests = extract_requests_from_curl(markdown)

        self.assertEqual(len(requests), 1)
        parsed = requests[0]
        self.assertEqual(parsed.request_spec["auth"]["auth_type"], "basic")
        self.assertFalse(parsed.request_spec["transport"]["verify_ssl"])
        self.assertEqual(parsed.request_spec["transport"]["proxy_url"], "http://127.0.0.1:7890")
        self.assertEqual(parsed.request_spec["cookies"][0]["name"], "sessionid")
        self.assertEqual(parsed.request_spec["body_mode"], "multipart")
        self.assertEqual(parsed.request_spec["files"][0]["field_name"], "file")

    def test_curl_import_supports_get_head_timeout_user_agent_and_file_content_type(self):
        markdown = """
        ## Search users
        ```bash
        curl --get 'https://example.com/api/users?tenant=cms' \\
          -A 'FlyTestBot/1.0' \\
          --max-time 12.5 \\
          -d page=2 \\
          -d keyword=admin
        ```

        ## Check health
        ```bash
        curl -I https://example.com/health
        ```

        ## Upload avatar
        ```bash
        curl https://example.com/api/upload \\
          -F 'scene=avatar' \\
          -F 'file=@/tmp/avatar.png;type=image/png;filename=custom-avatar.png'
        ```
        """

        requests = extract_requests_from_curl(markdown)

        search_request = next(item for item in requests if item.url == "https://example.com/api/users")
        health_request = next(item for item in requests if item.url == "https://example.com/health")
        upload_request = next(item for item in requests if item.url == "https://example.com/api/upload")

        self.assertEqual(search_request.method, "GET")
        self.assertEqual(search_request.params["tenant"], "cms")
        self.assertEqual(search_request.params["page"], "2")
        self.assertEqual(search_request.params["keyword"], "admin")
        self.assertEqual(search_request.request_spec["headers"][0]["name"], "User-Agent")
        self.assertEqual(search_request.request_spec["headers"][0]["value"], "FlyTestBot/1.0")
        self.assertEqual(search_request.request_spec["timeout_ms"], 12500)
        self.assertEqual(search_request.request_spec["body_mode"], "none")

        self.assertEqual(health_request.method, "HEAD")
        self.assertEqual(health_request.request_spec["body_mode"], "none")

        self.assertEqual(upload_request.method, "POST")
        self.assertEqual(upload_request.request_spec["body_mode"], "multipart")
        self.assertEqual(upload_request.request_spec["files"][0]["content_type"], "image/png")
        self.assertEqual(upload_request.request_spec["files"][0]["file_name"], "custom-avatar.png")


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

    @patch("api_automation.views.get_import_ai_compatibility_status")
    def test_ai_import_compatibility_endpoint_returns_structured_status(self, mock_status):
        mock_status.return_value = {
            "compatible": False,
            "issue_code": "gateway_incompatible_empty_content",
            "level": "warning",
            "title": "当前 AI 网关未返回正文",
            "message": "当前激活模型 gpt-5.4 调用成功但未返回可解析正文，API 文档导入会回退到规则解析。",
            "action_hint": "请在“系统设置 > AI大模型配置”中切换到能正常返回正文的模型或网关。",
            "model_name": "gpt-5.4",
            "prompt_source": "user_prompt",
            "prompt_name": "API自动化解析",
        }

        response = self.client.get("/api/api-automation/requests/ai-import-compatibility/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertFalse(payload["compatible"])
        self.assertEqual(payload["issue_code"], "gateway_incompatible_empty_content")
        self.assertIn("未返回正文", payload["title"])

    def test_import_document_rejects_unsupported_extension(self):
        upload = SimpleUploadedFile("shell.exe", b"MZ...", content_type="application/octet-stream")

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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("不受支持", str(response.data["error"]))

    @override_settings(MAX_API_DOCUMENT_UPLOAD_BYTES=32)
    def test_import_document_rejects_oversized_file(self):
        upload = SimpleUploadedFile(
            "openapi.json",
            json.dumps({"openapi": "3.0.0", "paths": {"/ping": {"get": {}}}}).encode("utf-8"),
            content_type="application/json",
        )

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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("不能超过", str(response.data["error"]))

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
        self.assertFalse(payload["ai_requested"])
        self.assertFalse(payload["ai_used"])
        self.assertIn("鍥為€€", payload["ai_note"])
        self.assertEqual(payload["ai_issue_code"], "not_requested")
        self.assertIn("未检测到激活的大模型配置", payload["ai_user_message"])
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
        self.assertEqual(payload["ai_issue_code"], "llm_not_configured")
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
        self.assertEqual(payload["generated_scripts"][0]["script"]["assertions"][1]["assertion_type"], "json_path")

    @patch("api_automation.import_service.enhance_import_result_with_ai")
    def test_import_document_accepts_inline_text_input(self, mock_enhance):
        mock_enhance.return_value = AIEnhancementResult(
            requested=True,
            used=True,
            note="AI parsed inline document",
            prompt_source="user_prompt",
            prompt_name="API自动化解析",
            model_name="gpt-4.1",
            requests=[
                ParsedRequestData(
                    name="Inline Login",
                    method="POST",
                    url="/api/login",
                    description="AI parsed from inline document",
                    headers={"Authorization": "Bearer {{token}}"},
                    params={},
                    body_type="json",
                    body={"username": "demo", "password": "123456"},
                    assertions=[{"type": "status_code", "expected": 200}],
                    collection_name="auth",
                )
            ],
        )

        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "generate_test_cases": "true",
                "enable_ai_parse": "true",
                "async_mode": "false",
                "source_name": "inline-login.md",
                "raw_text": "## Login\nPOST /api/login\nAuthorization: Bearer {{token}}\n```json\n{\"username\":\"demo\"}\n```",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)
        self.assertTrue(payload["ai_requested"])
        self.assertTrue(payload["ai_used"])
        self.assertEqual(payload["created_count"], 1)
        self.assertEqual(payload["items"][0]["name"], "Inline Login")
        self.assertEqual(ApiRequest.objects.count(), 1)

    def test_import_document_rejects_empty_inline_text(self):
        response = self.client.post(
            "/api/api-automation/requests/import-document/",
            {
                "collection_id": str(self.collection.id),
                "async_mode": "false",
                "raw_text": "   \n\t",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ApiRequest.objects.count(), 0)

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

    def test_create_request_reuses_duplicate_from_child_or_parent_collection(self):
        child = ApiCollection.objects.create(
            project=self.project,
            parent=self.collection,
            name="Auth APIs",
            creator=self.user,
        )
        existing = ApiRequest.objects.create(
            collection=self.collection,
            name="Login",
            method="POST",
            url="/api/login",
            created_by=self.user,
        )

        response = self.client.post(
            "/api/api-automation/requests/",
            {
                "collection": child.id,
                "name": "Child Login",
                "method": "POST",
                "url": "/api/login",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["id"], existing.id)
        self.assertEqual(ApiRequest.objects.filter(method="POST", url="/api/login").count(), 1)

    def test_update_request_rejects_duplicate_method_and_url_across_project(self):
        child = ApiCollection.objects.create(
            project=self.project,
            parent=self.collection,
            name="Order APIs",
            creator=self.user,
        )
        ApiRequest.objects.create(
            collection=self.collection,
            name="Login",
            method="POST",
            url="/api/login",
            created_by=self.user,
        )
        editable = ApiRequest.objects.create(
            collection=child,
            name="Profile",
            method="GET",
            url="/api/profile",
            created_by=self.user,
        )

        response = self.client.patch(
            f"/api/api-automation/requests/{editable.id}/",
            {
                "method": "POST",
                "url": "/api/login",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("已存在相同请求方法和路径的接口", str(response.data))

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
            progress_message="绛夊緟瑙ｆ瀽",
            generate_test_cases=True,
            enable_ai_parse=True,
        )

        response = self.client.post(f"/api/api-automation/import-jobs/{job.id}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "canceled")
        self.assertTrue(payload["cancel_requested"])

    @patch("api_automation.views._start_import_job")
    def test_async_import_job_persists_source_file_for_restart(self, mock_start_import_job):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            upload = SimpleUploadedFile(
                "async-api.md",
                b"## Login\nPOST /api/login\n```json\n{\"username\": \"demo\"}\n```",
                content_type="text/markdown",
            )

            response = self.client.post(
                "/api/api-automation/requests/import-document/",
                {
                    "collection_id": str(self.collection.id),
                    "generate_test_cases": "true",
                    "async_mode": "true",
                    "file": upload,
                },
                format="multipart",
            )

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            payload = self._payload(response)
            job = ApiImportJob.objects.get(pk=payload["id"])
            self.assertTrue(bool(job.source_file))
            self.assertTrue(os.path.exists(job.source_file.path))
            mock_start_import_job.assert_called_once_with(job.id)

    @patch("api_automation.views._start_import_job")
    def test_async_import_job_accepts_inline_text_source(self, mock_start_import_job):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            raw_text = "## Login\nPOST /api/login\n```json\n{\"username\":\"demo\"}\n```"

            response = self.client.post(
                "/api/api-automation/requests/import-document/",
                {
                    "collection_id": str(self.collection.id),
                    "generate_test_cases": "true",
                    "async_mode": "true",
                    "source_name": "inline-api.md",
                    "raw_text": raw_text,
                },
                format="multipart",
            )

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            payload = self._payload(response)
            job = ApiImportJob.objects.get(pk=payload["id"])
            self.assertEqual(job.source_name, "inline-api.md")
            self.assertTrue(bool(job.source_file))
            self.assertTrue(os.path.exists(job.source_file.path))
            self.assertEqual(Path(job.source_file.path).read_text(encoding="utf-8"), raw_text)
            mock_start_import_job.assert_called_once_with(job.id)

    @patch("api_automation.views._start_import_job")
    def test_import_job_can_restart_after_being_canceled(self, mock_start_import_job):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            job = ApiImportJob.objects.create(
                project=self.project,
                collection=self.collection,
                creator=self.user,
                source_name="demo.md",
                source_file=SimpleUploadedFile(
                    "demo.md",
                    b"## Login\nPOST /api/login",
                    content_type="text/markdown",
                ),
                status="canceled",
                progress_percent=76,
                progress_stage="canceled",
                progress_message="文档解析任务已暂停。",
                cancel_requested=True,
                generate_test_cases=True,
                enable_ai_parse=True,
            )

            response = self.client.post(f"/api/api-automation/import-jobs/{job.id}/restart/")

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            payload = self._payload(response)
            self.assertEqual(payload["status"], "pending")
            self.assertFalse(payload["cancel_requested"])
            self.assertEqual(payload["progress_stage"], "uploaded")
            self.assertEqual(payload["progress_percent"], 4)
            mock_start_import_job.assert_called_once_with(job.id)

            job.refresh_from_db()
            self.assertEqual(job.status, "pending")
            self.assertFalse(job.cancel_requested)
            self.assertEqual(job.error_message, "")

    def test_import_job_restart_requires_persisted_source_file(self):
        job = ApiImportJob.objects.create(
            project=self.project,
            collection=self.collection,
            creator=self.user,
            source_name="legacy.md",
            status="canceled",
            progress_percent=40,
            progress_stage="canceled",
            progress_message="文档解析任务已暂停。",
            cancel_requested=True,
            generate_test_cases=True,
            enable_ai_parse=True,
        )

        response = self.client.post(f"/api/api-automation/import-jobs/{job.id}/restart/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("源文档", self._payload(response)["error"])

    def test_import_job_can_be_closed_and_removes_source_file(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            job = ApiImportJob.objects.create(
                project=self.project,
                collection=self.collection,
                creator=self.user,
                source_name="demo.md",
                source_file=SimpleUploadedFile(
                    "demo.md",
                    b"## Login\nPOST /api/login",
                    content_type="text/markdown",
                ),
                status="canceled",
                progress_percent=76,
                progress_stage="canceled",
                progress_message="文档解析任务已暂停。",
                cancel_requested=False,
                generate_test_cases=True,
                enable_ai_parse=True,
            )
            source_path = job.source_file.path

            response = self.client.post(f"/api/api-automation/import-jobs/{job.id}/close/")

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            payload = self._payload(response)
            self.assertEqual(payload["id"], job.id)
            self.assertTrue(payload["closed"])
            self.assertFalse(ApiImportJob.objects.filter(pk=job.id).exists())
            self.assertFalse(os.path.exists(source_path))

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
                    name="Create order - 鎴愬姛鏍￠獙",
                    description="楠岃瘉涓嬪崟鎴愬姛",
                    status="ready",
                    tags=["ai-generated", "positive"],
                    assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                    extractors=[],
                    request_overrides={
                        "method": "",
                        "url": "",
                        "headers": [],
                        "query": [],
                        "cookies": [],
                        "form_fields": [],
                        "multipart_parts": [],
                        "files": [],
                        "body_mode": "json",
                        "body_json": {"sku": "A100"},
                        "raw_text": "",
                        "xml_text": "",
                        "binary_base64": "",
                        "graphql_query": "",
                        "graphql_operation_name": "",
                        "graphql_variables": {},
                        "timeout_ms": 30000,
                        "auth": {},
                        "transport": {},
                    },
                ),
                GeneratedCaseDraft(
                    name="Create order - 鍏抽敭瀛楁鏍￠獙",
                    description="楠岃瘉鍏抽敭鍝嶅簲瀛楁",
                    status="ready",
                    tags=["ai-generated", "regression"],
                    assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                    extractors=[],
                    request_overrides={
                        "method": "",
                        "url": "",
                        "headers": [{"name": "X-Scenario", "value": "field-check", "enabled": True, "order": 0}],
                        "query": [],
                        "cookies": [],
                        "form_fields": [],
                        "multipart_parts": [],
                        "files": [],
                        "body_mode": "json",
                        "body_json": {"sku": "A100"},
                        "raw_text": "",
                        "xml_text": "",
                        "binary_base64": "",
                        "graphql_query": "",
                        "graphql_operation_name": "",
                        "graphql_variables": {},
                        "timeout_ms": 30000,
                        "auth": {},
                        "transport": {},
                    },
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

    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_regenerate_mode_returns_preview_without_deleting_existing_cases(self, mock_generate):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            created_by=self.user,
        )
        existing_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="Create order - existing",
            status="ready",
            script={"request": {"method": "POST", "url": "/api/orders"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )
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

        response = self.client.post(
            "/api/api-automation/requests/generate-test-cases/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "regenerate",
                "count_per_request": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertTrue(payload["preview_only"])
        self.assertTrue(payload["requires_confirmation"])
        self.assertEqual(payload["preview_request_count"], 1)
        self.assertEqual(payload["created_testcase_count"], 0)
        self.assertEqual(ApiTestCase.objects.filter(request=api_request).count(), 1)
        item = payload["items"][0]
        self.assertTrue(item["preview_only"])
        self.assertEqual(item["replacement_summary"]["existing_count"], 1)
        self.assertEqual(item["replacement_summary"]["proposed_count"], 1)
        self.assertEqual(item["replacement_summary"]["removed_case_names"], ["Create order - existing"])
        self.assertEqual(item["replacement_summary"]["added_case_names"], ["Create order - regenerated"])
        self.assertTrue(ApiTestCase.objects.filter(id=existing_case.id).exists())

    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_regenerate_mode_applies_replacement_after_confirmation(self, mock_generate):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            created_by=self.user,
        )
        existing_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="Create order - existing",
            status="ready",
            script={"request": {"method": "POST", "url": "/api/orders"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )
        mock_generate.return_value = AITestCaseGenerationResult(
            used_ai=True,
            note="AI applied replacement candidate",
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
                    description="Confirmed replacement",
                    status="ready",
                    tags=["ai-generated"],
                    assertions=[{"assertion_type": "status_code", "expected_number": 200}],
                    extractors=[],
                    request_overrides={},
                )
            ],
        )

        response = self.client.post(
            "/api/api-automation/requests/generate-test-cases/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "regenerate",
                "count_per_request": 1,
                "apply_changes": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertFalse(payload["preview_only"])
        self.assertEqual(payload["created_testcase_count"], 1)
        self.assertFalse(ApiTestCase.objects.filter(id=existing_case.id).exists())
        self.assertEqual(ApiTestCase.objects.filter(request=api_request).count(), 1)
        self.assertEqual(ApiTestCase.objects.get(request=api_request).name, "Create order - regenerated")

    @patch("api_automation.views._start_case_generation_job")
    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_case_generation_job_returns_preview_and_persists_drafts(self, mock_generate, _mock_start_job):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            created_by=self.user,
        )
        existing_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="Create order - existing",
            status="ready",
            script={"request": {"method": "POST", "url": "/api/orders"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )
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

        response = self.client.post(
            "/api/api-automation/case-generation-jobs/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "regenerate",
                "count_per_request": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        job_id = self._payload(response)["id"]
        _run_case_generation_job(job_id)

        job = ApiCaseGenerationJob.objects.get(pk=job_id)
        self.assertEqual(job.status, "preview_ready")
        self.assertTrue(job.result_payload["preview_only"])
        self.assertEqual(job.result_payload["preview_request_count"], 1)
        self.assertEqual(job.draft_payload["items"][0]["drafts"][0]["name"], "Create order - regenerated")
        self.assertTrue(ApiTestCase.objects.filter(id=existing_case.id).exists())

    @patch("api_automation.views._start_case_generation_apply")
    @patch("api_automation.views._start_case_generation_job")
    @patch("api_automation.views.generate_test_case_drafts_with_ai")
    def test_case_generation_job_apply_uses_saved_preview_without_second_ai_call(
        self,
        mock_generate,
        _mock_start_job,
        _mock_start_apply,
    ):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            created_by=self.user,
        )
        existing_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="Create order - existing",
            status="ready",
            script={"request": {"method": "POST", "url": "/api/orders"}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )
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

        create_response = self.client.post(
            "/api/api-automation/case-generation-jobs/",
            {
                "scope": "selected",
                "ids": [api_request.id],
                "mode": "regenerate",
                "count_per_request": 1,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_202_ACCEPTED)
        job_id = self._payload(create_response)["id"]
        _run_case_generation_job(job_id)

        apply_response = self.client.post(
            f"/api/api-automation/case-generation-jobs/{job_id}/apply/",
            {},
            format="json",
        )
        self.assertEqual(apply_response.status_code, status.HTTP_202_ACCEPTED)
        _apply_case_generation_job(job_id)

        job = ApiCaseGenerationJob.objects.get(pk=job_id)
        self.assertEqual(job.status, "success")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertFalse(ApiTestCase.objects.filter(id=existing_case.id).exists())
        self.assertEqual(ApiTestCase.objects.filter(request=api_request).count(), 1)
        self.assertEqual(ApiTestCase.objects.get(request=api_request).name, "Create order - regenerated")


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

    def test_build_effective_request_spec_respects_explicit_empty_override_values(self):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Create order",
            method="POST",
            url="/api/orders",
            headers={"X-Env": "test"},
            body_type="json",
            body={"sku": "A100"},
            created_by=self.user,
        )
        apply_request_spec_payload(
            api_request,
            {
                "method": "POST",
                "url": "/api/orders",
                "body_mode": "json",
                "body_json": {"sku": "A100"},
                "raw_text": "legacy-body",
                "xml_text": "",
                "binary_base64": "",
                "graphql_query": "",
                "graphql_operation_name": "",
                "graphql_variables": {"tenant": "cms"},
                "timeout_ms": 30000,
                "headers": [{"name": "X-Env", "value": "test", "enabled": True, "order": 0}],
                "query": [],
                "cookies": [],
                "form_fields": [],
                "multipart_parts": [],
                "files": [],
                "auth": {"auth_type": "none"},
                "transport": {},
            },
        )

        effective_spec = build_effective_request_spec(
            api_request,
            request_override={
                "replace_fields": ["headers", "body_json", "raw_text", "graphql_variables"],
                "headers": [],
                "body_json": {},
                "raw_text": "",
                "graphql_variables": {},
            },
        )

        self.assertEqual(effective_spec.headers, [])
        self.assertEqual(effective_spec.body_json, {})
        self.assertEqual(effective_spec.raw_text, "")
        self.assertEqual(effective_spec.graphql_variables, {})

    def test_evaluate_structured_assertions_supports_richer_operator_variants(self):
        response = SimpleNamespace(
            status_code=201,
            headers={"Content-Type": "application/json; charset=utf-8"},
            cookies={"sessionid": "cookie-123"},
            text='{"data":{"roles":["editor"],"profile":{}},"trace":"trace-123"}',
            is_success=True,
        )
        response_payload = {"data": {"roles": ["editor"], "profile": {}}, "trace": "trace-123"}

        results, passed = evaluate_structured_assertions(
            [
                {"assertion_type": "status_code", "operator": "gte", "expected_number": 200},
                {"assertion_type": "json_path", "selector": "data.roles", "operator": "contains", "expected_text": "editor"},
                {"assertion_type": "json_path", "selector": "data.profile", "operator": "equals", "expected_json": {}},
                {"assertion_type": "header", "selector": "Content-Type", "operator": "starts_with", "expected_text": "application/json"},
                {"assertion_type": "cookie", "selector": "sessionid", "operator": "ends_with", "expected_text": "123"},
                {"assertion_type": "regex", "selector": "trace-(\\d+)", "operator": "equals", "expected_text": "123"},
                {"assertion_type": "array_length", "selector": "data.roles", "operator": "gt", "expected_number": 0},
                {"assertion_type": "response_time", "operator": "lt", "expected_number": 200},
            ],
            response,
            response_payload,
            128.4,
        )

        self.assertTrue(passed)
        self.assertEqual(len(results), 8)
        self.assertTrue(all(item["passed"] for item in results))

    def test_execute_request_reports_missing_environment_variables(self):
        environment = self.project.api_environments.create(
            name="Execution Env",
            base_url="https://cms-test.9635.com.cn/api",
            variables={"token": "", "nkey": "", "auth_request_name": "APP瀵嗙爜鐧诲綍"},
            creator=self.user,
            is_default=True,
        )
        ApiRequest.objects.create(
            collection=self.collection,
            name="APP瀵嗙爜鐧诲綍",
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

    @patch("api_automation.execution.httpx.Client.request")
    def test_execute_request_bootstraps_token_from_auth_request(self, mock_request):
        environment = self.project.api_environments.create(
            name="Execution Env",
            base_url="https://cms-test.9635.com.cn/api",
            variables={
                "token": "",
                "phone": "13800138000",
                "password": "secret123",
                "auth_request_name": "APP瀵嗙爜鐧诲綍",
            },
            creator=self.user,
            is_default=True,
        )
        ApiRequest.objects.create(
            collection=self.collection,
            name="APP瀵嗙爜鐧诲綍",
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
                self.cookies = {}
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

    def test_environment_api_persists_structured_specs(self):
        response = self.client.post(
            "/api/api-automation/environments/",
            {
                "project": self.project.id,
                "name": "结构化环境",
                "base_url": "https://example.com",
                "timeout_ms": 15000,
                "is_default": True,
                "environment_specs": {
                    "headers": [
                        {"name": "Authorization", "value": "Bearer {{token}}", "enabled": True, "order": 0},
                    ],
                    "variables": [
                        {"name": "token", "value": "TOKEN_123", "enabled": True, "is_secret": True, "order": 0},
                    ],
                    "cookies": [
                        {
                            "name": "sessionid",
                            "value": "cookie-1",
                            "domain": "example.com",
                            "path": "/",
                            "enabled": True,
                            "order": 0,
                        },
                    ],
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = self._payload(response)
        self.assertEqual(payload["environment_specs"]["headers"][0]["name"], "Authorization")
        self.assertEqual(payload["environment_specs"]["variables"][0]["name"], "token")
        self.assertEqual(payload["environment_specs"]["cookies"][0]["name"], "sessionid")

        environment = ApiEnvironment.objects.get(pk=payload["id"])
        self.assertEqual(environment.common_headers["Authorization"], "Bearer {{token}}")
        self.assertEqual(environment.variables["token"], "TOKEN_123")
        self.assertEqual(environment.cookie_specs.count(), 1)
        self.assertTrue(environment.variable_specs.filter(name="token", is_secret=True).exists())

    @patch("api_automation.execution.httpx.Client")
    def test_execute_batch_reuses_run_level_cookie_jar(self, mock_client_cls):
        login_request = ApiRequest.objects.create(
            collection=self.collection,
            name="鐧诲綍鎺ュ彛",
            method="POST",
            url="/api/login",
            assertions=[{"type": "status_code", "expected": 200}],
            order=1,
            created_by=self.user,
        )
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="鑾峰彇璧勬枡",
            method="GET",
            url="/api/profile",
            assertions=[{"type": "status_code", "expected": 200}],
            order=2,
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Cookie Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )

        class MockResponse:
            def __init__(self, status_code, payload, cookies=None):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                for key, value in (cookies or {}).items():
                    self.cookies.set(key, value)
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, **kwargs):
                seed_cookies = kwargs.get("cookies") or httpx.Cookies()
                self.cookies = httpx.Cookies()
                self.session_cookies: dict[str, str] = {}
                for cookie in seed_cookies.jar:
                    self.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
                    self.session_cookies[cookie.name] = cookie.value

            def request(self, **kwargs):
                visible_cookies = dict(self.session_cookies)
                visible_cookies.update(kwargs.get("cookies") or {})
                if kwargs["url"].endswith("/api/login"):
                    self.cookies.set("sessionid", "cookie-123")
                    self.session_cookies["sessionid"] = "cookie-123"
                    return MockResponse(200, {"code": 200, "message": "ok"}, {"sessionid": "cookie-123"})
                if kwargs["url"].endswith("/api/profile"):
                    if visible_cookies.get("sessionid") != "cookie-123":
                        return MockResponse(401, {"message": "missing session"})
                    return MockResponse(200, {"code": 200, "data": {"user": "demo"}})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            def close(self):
                return None

        mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

        response = self.client.post(
            "/api/api-automation/requests/execute-batch/",
            {
                "scope": "selected",
                "ids": [login_request.id, profile_request.id],
                "environment_id": environment.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual(mock_client_cls.call_count, 1, payload)
        self.assertEqual(payload["success_count"], 2, payload)
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["items"][1]["status"], "success")

    @patch("api_automation.execution.httpx.AsyncClient")
    def test_execute_batch_async_mode_reuses_run_level_cookie_jar(self, mock_async_client_cls):
        login_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Async 登录接口",
            method="POST",
            url="/api/login",
            assertions=[{"type": "status_code", "expected": 200}],
            order=1,
            created_by=self.user,
        )
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="Async 閼惧嘲褰囩挧鍕灐",
            method="GET",
            url="/api/profile",
            assertions=[{"type": "status_code", "expected": 200}],
            order=2,
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Async Cookie Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )

        class MockResponse:
            def __init__(self, status_code, payload, cookies=None):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                for key, value in (cookies or {}).items():
                    self.cookies.set(key, value)
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                seed_cookies = kwargs.get("cookies") or httpx.Cookies()
                self.cookies = httpx.Cookies()
                self.session_cookies: dict[str, str] = {}
                for cookie in seed_cookies.jar:
                    self.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
                    self.session_cookies[cookie.name] = cookie.value

            async def request(self, **kwargs):
                visible_cookies = dict(self.session_cookies)
                visible_cookies.update(kwargs.get("cookies") or {})
                if kwargs["url"].endswith("/api/login"):
                    self.cookies.set("sessionid", "async-cookie-123")
                    self.session_cookies["sessionid"] = "async-cookie-123"
                    return MockResponse(200, {"code": 200, "message": "ok"}, {"sessionid": "async-cookie-123"})
                if kwargs["url"].endswith("/api/profile"):
                    if visible_cookies.get("sessionid") != "async-cookie-123":
                        return MockResponse(401, {"message": "missing session"})
                    return MockResponse(200, {"code": 200, "data": {"user": "demo"}})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            async def aclose(self):
                return None

        mock_async_client_cls.side_effect = lambda **kwargs: FakeAsyncClient(**kwargs)

        response = self.client.post(
            "/api/api-automation/requests/execute-batch/",
            {
                "scope": "selected",
                "ids": [login_request.id, profile_request.id],
                "environment_id": environment.id,
                "execution_mode": "async",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["execution_mode"], "async")
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual(mock_async_client_cls.call_count, 1, payload)
        self.assertEqual(payload["success_count"], 2, payload)
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["items"][1]["status"], "success")

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
            run_name="鎺ュ彛鎵归噺鎵ц",
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

    @patch("api_automation.ai_report_summarizer.LLMConfig.objects.filter")
    def test_execution_report_summary_endpoint_returns_rule_fallback_when_no_llm(self, mock_filter):
        mock_filter.return_value.first.return_value = None
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="Report summary request",
            method="GET",
            url="/api/reports/summary",
            created_by=self.user,
        )

        ApiExecutionRecord.objects.create(
            project=self.project,
            request=request,
            environment=None,
            run_id="run-report-summary-1",
            run_name="鎶ュ憡鎽樿鎵规",
            request_name=request.name,
            method=request.method,
            url=request.url,
            status="failed",
            passed=False,
            status_code=401,
            response_time=188.2,
            request_snapshot={},
            response_snapshot={"body": {"message": "unauthorized"}},
            assertions_results=[],
            error_message="unauthorized",
            executor=self.user,
        )

        response = self.client.post(
            "/api/api-automation/execution-records/report-summary/",
            {"project": self.project.id, "days": 7},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertFalse(payload["used_ai"])
        self.assertTrue(payload["summary"])
        self.assertTrue(payload["recommended_actions"])

    @patch("api_automation.ai_report_summarizer.create_llm_instance")
    @patch("api_automation.ai_report_summarizer.LLMConfig.objects.filter")
    @patch("api_automation.ai_report_summarizer.safe_llm_invoke")
    def test_execution_report_summary_endpoint_reuses_cached_ai_result(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        request = ApiRequest.objects.create(
            collection=self.collection,
            name="Report summary cached request",
            method="GET",
            url="/api/reports/cache",
            created_by=self.user,
        )

        ApiExecutionRecord.objects.create(
            project=self.project,
            request=request,
            environment=None,
            run_id="run-report-summary-cache",
            run_name="鎶ュ憡鎽樿缂撳瓨鎵规",
            request_name=request.name,
            method=request.method,
            url=request.url,
            status="failed",
            passed=False,
            status_code=500,
            response_time=320.4,
            request_snapshot={},
            response_snapshot={"body": {"message": "server error"}},
            assertions_results=[],
            error_message="server error",
            executor=self.user,
        )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="gpt-5.4")
        mock_create_llm.return_value = SimpleNamespace()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "最近失败主要集中在接口稳定性和鉴权配置。",
                    "top_risks": [
                        {"title": "鉴权不稳定", "detail": "部分接口返回 401/500，建议检查登录引导配置。"}
                    ],
                    "recommended_actions": [
                        {"title": "检查鉴权链路", "detail": "确认 token 提取路径和环境变量。", "priority": "high"}
                    ],
                    "evidence": [
                        {"label": "失败状态码", "detail": "最近批次存在 500 错误。"}
                    ],
                },
                ensure_ascii=False,
            )
        )

        first_response = self.client.post(
            "/api/api-automation/execution-records/report-summary/",
            {"project": self.project.id, "days": 7},
            format="json",
        )
        second_response = self.client.post(
            "/api/api-automation/execution-records/report-summary/",
            {"project": self.project.id, "days": 7},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        first_payload = self._payload(first_response)
        second_payload = self._payload(second_response)
        self.assertTrue(first_payload["used_ai"])
        self.assertFalse(first_payload["cache_hit"])
        self.assertTrue(second_payload["used_ai"])
        self.assertTrue(second_payload["cache_hit"])
        self.assertEqual(mock_safe_invoke.call_count, 1)
        cache.clear()

    @patch("api_automation.ai_failure_analyzer.create_llm_instance")
    @patch("api_automation.ai_failure_analyzer.LLMConfig.objects.filter")
    @patch("api_automation.ai_failure_analyzer.safe_llm_invoke")
    def test_execution_failure_analysis_endpoint_reuses_cached_ai_result(
        self,
        mock_safe_invoke,
        mock_filter,
        mock_create_llm,
    ):
        cache.clear()
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="会员登录",
            method="POST",
            url="/api/login",
            created_by=self.user,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="会员登录-错误密码",
            status="ready",
            script={"request_overrides": {"body_type": "json", "body": {"username": "demo", "password": "wrong"}}},
            assertions=[{"type": "status_code", "expected": 200}],
            creator=self.user,
        )
        record = ApiExecutionRecord.objects.create(
            project=self.project,
            request=api_request,
            test_case=test_case,
            environment=None,
            run_id="run-ai-analysis-1",
            run_name="鐧诲綍澶辫触澶嶇洏",
            request_name=test_case.name,
            method="POST",
            url="/api/login",
            status="failed",
            passed=False,
            status_code=401,
            response_time=166.2,
            request_snapshot={
                "interface_name": api_request.name,
                "workflow_summary": {"enabled": False, "configured_step_count": 0, "executed_step_count": 0},
            },
            response_snapshot={"body": {"message": "token invalid"}},
            assertions_results=[
                {"index": 0, "type": "status_code", "expected": 200, "actual": 401, "passed": False},
            ],
            error_message="token invalid",
            executor=self.user,
        )

        mock_filter.return_value.first.return_value = SimpleNamespace(name="demo-model")
        mock_create_llm.return_value = object()
        mock_safe_invoke.return_value = SimpleNamespace(
            content=json.dumps(
                {
                    "summary": "认证信息失效，优先检查 token 和登录前置步骤。",
                    "failure_mode": "auth_or_permission",
                    "likely_root_causes": [
                        {"title": "登录态失效", "detail": "当前返回 401，更像 token 失效或未正确传递。", "confidence": 0.93}
                    ],
                    "recommended_actions": [
                        {"title": "检查认证变量", "detail": "确认 token、cookie 和环境变量是否仍有效。", "priority": "high"}
                    ],
                    "evidence": [
                        {"label": "状态码", "detail": "当前响应状态码为 401。"}
                    ],
                },
                ensure_ascii=False,
            )
        )

        response_first = self.client.post(
            f"/api/api-automation/execution-records/{record.id}/analyze-failure/",
            format="json",
        )
        response_second = self.client.post(
            f"/api/api-automation/execution-records/{record.id}/analyze-failure/",
            format="json",
        )

        self.assertEqual(response_first.status_code, status.HTTP_200_OK)
        self.assertEqual(response_second.status_code, status.HTTP_200_OK)
        payload_first = self._payload(response_first)
        payload_second = self._payload(response_second)
        self.assertTrue(payload_first["used_ai"])
        self.assertFalse(payload_first["cache_hit"])
        self.assertTrue(payload_second["cache_hit"])
        self.assertEqual(payload_second["failure_mode"], "auth_or_permission")
        self.assertEqual(payload_second["likely_root_causes"][0]["title"], "登录态失效")
        self.assertEqual(mock_safe_invoke.call_count, 1)
        cache.clear()

    def test_rule_based_failure_analysis_marks_workflow_blocked_record(self):
        api_request = ApiRequest.objects.create(
            collection=self.collection,
            name="璇诲彇鐢ㄦ埛淇℃伅",
            method="GET",
            url="/api/profile",
            created_by=self.user,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=api_request,
            name="鐢ㄦ埛淇℃伅-鍓嶇疆澶辫触闃绘柇",
            status="ready",
            script={
                "workflow_steps": [
                    {"name": "鐧诲綍鑾峰彇 token", "stage": "prepare", "request_id": 9999},
                ]
            },
            assertions=[],
            creator=self.user,
        )
        record = ApiExecutionRecord.objects.create(
            project=self.project,
            request=api_request,
            test_case=test_case,
            environment=None,
            run_id="run-rule-analysis-1",
            run_name="瑙勫垯澶嶇洏",
            request_name=test_case.name,
            method="GET",
            url="/api/profile",
            status="failed",
            passed=False,
            status_code=None,
            response_time=None,
            request_snapshot={
                "main_request_blocked": True,
                "workflow_summary": {
                    "enabled": True,
                    "configured_step_count": 1,
                    "executed_step_count": 1,
                    "failure_count": 1,
                    "has_failure": True,
                    "main_request_executed": False,
                },
                "workflow_steps": [
                    {
                        "index": 0,
                        "name": "鐧诲綍鑾峰彇 token",
                        "stage": "prepare",
                        "status": "failed",
                        "status_code": 401,
                        "error_message": "token missing",
                    }
                ],
            },
            response_snapshot={},
            assertions_results=[
                {"type": "workflow_step", "passed": False, "message": "Workflow step failed: 鐧诲綍鑾峰彇 token"}
            ],
            error_message="Workflow step failed: 鐧诲綍鑾峰彇 token",
            executor=self.user,
        )

        result = analyze_execution_failure(record=record, user=self.user)

        self.assertFalse(result.used_ai)
        self.assertEqual(result.failure_mode, "workflow_blocked")
        self.assertIn("主请求", result.summary)
        self.assertTrue(any("前置步骤" in item["title"] or "prepare" in item["detail"] for item in result.likely_root_causes))
        self.assertTrue(any("变量" in item["detail"] or "步骤" in item["detail"] for item in result.recommended_actions))

    @patch("api_automation.execution.httpx.Client.request")
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
            cookies = {}
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

    @patch("api_automation.execution.httpx.Client")
    def test_execute_test_case_workflow_prepare_step_shares_variables_with_main_request(self, mock_client_cls):
        login_request = ApiRequest.objects.create(
            collection=self.collection,
            name="登录取 Token",
            method="POST",
            url="/api/login",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="读取用户信息",
            method="GET",
            url="/api/profile",
            headers={"Authorization": "Bearer {{auth_token}}"},
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Workflow Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=profile_request,
            name="鐢ㄦ埛淇℃伅-宸ヤ綔娴佸彇 token",
            status="ready",
            script={
                "workflow_steps": [
                    {
                        "name": "Fetch token",
                        "stage": "prepare",
                        "request_id": login_request.id,
                        "extractor_specs": [
                            {
                                "source": "json_path",
                                "selector": "data.token",
                                "variable_name": "auth_token",
                                "required": True,
                            }
                        ],
                    }
                ]
            },
            assertions=[],
            creator=self.user,
        )

        profile_headers = []

        class MockResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, **kwargs):
                self.cookies = kwargs.get("cookies") or httpx.Cookies()

            def request(self, **kwargs):
                if kwargs["url"].endswith("/api/login"):
                    return MockResponse(200, {"data": {"token": "token-xyz"}})
                if kwargs["url"].endswith("/api/profile"):
                    profile_headers.append((kwargs.get("headers") or {}).get("Authorization"))
                    return MockResponse(200, {"code": 200, "message": "ok"})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            def close(self):
                return None

        mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

        response = self.client.post(
            f"/api/api-automation/test-cases/{test_case.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(mock_client_cls.call_count, 1)
        self.assertEqual(profile_headers, ["Bearer token-xyz"])
        self.assertTrue(payload["workflow_summary"]["enabled"])
        self.assertEqual(payload["workflow_summary"]["failure_count"], 0)
        self.assertEqual(payload["workflow_steps"][0]["stage"], "prepare")
        self.assertFalse(payload["main_request_blocked"])

        record = ApiExecutionRecord.objects.get(pk=payload["id"])
        self.assertEqual(record.request_snapshot["headers"]["Authorization"], "Bearer token-xyz")
        self.assertTrue(record.request_snapshot["workflow_summary"]["enabled"])
        self.assertEqual(record.request_snapshot["workflow_summary"]["failure_count"], 0)
        self.assertEqual(record.request_snapshot["workflow_steps"][0]["stage"], "prepare")
        self.assertEqual(record.request_snapshot["workflow_steps"][0]["status"], "success")
        self.assertEqual(record.request_snapshot["workflow_steps"][1]["kind"], "main_request")

    @patch("api_automation.execution.httpx.Client")
    def test_execute_test_case_workflow_teardown_failure_marks_case_failed(self, mock_client_cls):
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="璇诲彇鐢ㄦ埛淇℃伅",
            method="GET",
            url="/api/profile",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        logout_request = ApiRequest.objects.create(
            collection=self.collection,
            name="退出登录",
            method="POST",
            url="/api/logout",
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Teardown Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=profile_request,
            name="用户信息-含清理步骤",
            status="ready",
            script={
                "workflow_steps": [
                    {
                        "name": "Cleanup session",
                        "stage": "teardown",
                        "request_id": logout_request.id,
                    }
                ]
            },
            assertions=[],
            creator=self.user,
        )

        class MockResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, **kwargs):
                self.cookies = kwargs.get("cookies") or httpx.Cookies()

            def request(self, **kwargs):
                if kwargs["url"].endswith("/api/profile"):
                    return MockResponse(200, {"code": 200})
                if kwargs["url"].endswith("/api/logout"):
                    return MockResponse(500, {"message": "logout failed"})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            def close(self):
                return None

        mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

        response = self.client.post(
            f"/api/api-automation/test-cases/{test_case.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "failed")

        record = ApiExecutionRecord.objects.get(pk=payload["id"])
        self.assertFalse(record.passed)
        self.assertIn("Workflow step failed", record.error_message)
        self.assertEqual(record.request_snapshot["workflow_steps"][-1]["stage"], "teardown")
        self.assertEqual(record.request_snapshot["workflow_steps"][-1]["status"], "failed")
        self.assertTrue(any(item.get("type") == "workflow_step" for item in record.assertions_results))

    @patch("api_automation.execution.httpx.Client")
    def test_execute_test_case_workflow_prepare_failure_blocks_main_request_by_default(self, mock_client_cls):
        prepare_request = ApiRequest.objects.create(
            collection=self.collection,
            name="准备登录态",
            method="POST",
            url="/api/setup",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="璇诲彇鐢ㄦ埛淇℃伅",
            method="GET",
            url="/api/profile",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Block Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=profile_request,
            name="鐢ㄦ埛淇℃伅-鍓嶇疆澶辫触闃绘柇",
            status="ready",
            script={
                "workflow_steps": [
                    {
                        "name": "Prepare context",
                        "stage": "prepare",
                        "request_id": prepare_request.id,
                    }
                ]
            },
            assertions=[],
            creator=self.user,
        )

        profile_call_count = 0

        class MockResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, **kwargs):
                self.cookies = kwargs.get("cookies") or httpx.Cookies()

            def request(self, **kwargs):
                nonlocal profile_call_count
                if kwargs["url"].endswith("/api/setup"):
                    return MockResponse(500, {"message": "setup failed"})
                if kwargs["url"].endswith("/api/profile"):
                    profile_call_count += 1
                    return MockResponse(200, {"code": 200})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            def close(self):
                return None

        mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

        response = self.client.post(
            f"/api/api-automation/test-cases/{test_case.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(profile_call_count, 0)
        self.assertTrue(payload["main_request_blocked"])
        self.assertFalse(payload["workflow_summary"]["main_request_executed"])
        self.assertEqual(payload["workflow_steps"][0]["status"], "failed")

        record = ApiExecutionRecord.objects.get(pk=payload["id"])
        self.assertTrue(record.request_snapshot["main_request_blocked"])
        self.assertFalse(record.request_snapshot["workflow_summary"]["main_request_executed"])
        self.assertIn("Workflow step failed", record.error_message)

    @patch("api_automation.execution.httpx.Client")
    def test_execute_test_case_workflow_continue_on_failure_still_runs_main_request(self, mock_client_cls):
        prepare_request = ApiRequest.objects.create(
            collection=self.collection,
            name="准备登录态",
            method="POST",
            url="/api/setup",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        profile_request = ApiRequest.objects.create(
            collection=self.collection,
            name="璇诲彇鐢ㄦ埛淇℃伅",
            method="GET",
            url="/api/profile",
            assertions=[{"type": "status_code", "expected": 200}],
            created_by=self.user,
        )
        environment = self.project.api_environments.create(
            name="Continue Env",
            base_url="https://example.com",
            creator=self.user,
            is_default=True,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            request=profile_request,
            name="鐢ㄦ埛淇℃伅-鍓嶇疆澶辫触缁х画鎵ц",
            status="ready",
            script={
                "workflow_steps": [
                    {
                        "name": "Prepare context",
                        "stage": "prepare",
                        "request_id": prepare_request.id,
                        "continue_on_failure": True,
                    }
                ]
            },
            assertions=[],
            creator=self.user,
        )

        profile_call_count = 0

        class MockResponse:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload
                self.headers = {}
                self.cookies = httpx.Cookies()
                self.text = json.dumps(payload, ensure_ascii=False)
                self.is_success = 200 <= status_code < 300

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, **kwargs):
                self.cookies = kwargs.get("cookies") or httpx.Cookies()

            def request(self, **kwargs):
                nonlocal profile_call_count
                if kwargs["url"].endswith("/api/setup"):
                    return MockResponse(500, {"message": "setup failed"})
                if kwargs["url"].endswith("/api/profile"):
                    profile_call_count += 1
                    return MockResponse(200, {"code": 200})
                raise AssertionError(f"Unexpected url: {kwargs['url']}")

            def close(self):
                return None

        mock_client_cls.side_effect = lambda **kwargs: FakeClient(**kwargs)

        response = self.client.post(
            f"/api/api-automation/test-cases/{test_case.id}/execute/",
            {"environment_id": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(profile_call_count, 1)

        record = ApiExecutionRecord.objects.get(pk=payload["id"])
        self.assertTrue(record.request_snapshot["workflow_summary"]["main_request_executed"])
        self.assertEqual(record.request_snapshot["workflow_steps"][0]["status"], "failed")
        self.assertEqual(record.request_snapshot["workflow_steps"][1]["kind"], "main_request")

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
            run_name="CMS 鍥炲綊鎵ц",
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
            response_snapshot={"body": {"message": "鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒"}},
            assertions_results=[{"index": 0, "type": "status_code", "expected": 200, "actual": 401, "passed": False}],
            error_message="鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒",
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
        self.assertEqual(run_group["run_name"], "CMS 鍥炲綊鎵ц")
        self.assertEqual(run_group["failed_test_case_count"], 1)
        self.assertEqual(run_group["interface_count"], 1)

        interface_group = run_group["interfaces"][0]
        self.assertEqual(interface_group["interface_name"], "会员登录")
        self.assertEqual(interface_group["failed_test_case_count"], 1)
        self.assertEqual(len(interface_group["failed_test_cases"]), 1)

        case_group = interface_group["failed_test_cases"][0]
        self.assertEqual(case_group["test_case_name"], "会员登录-错误密码")
        self.assertEqual(case_group["latest_status_code"], 401)
        self.assertEqual(case_group["latest_error_message"], "鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒")
        self.assertEqual(case_group["failed_records"][0]["error_message"], "鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒")


class ApiAutomationDataFactoryReferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="api_df_admin",
            email="api_df_admin@example.com",
            password="testpass123",
        )
        self.project = Project.objects.create(
            name="API Data Factory Project",
            description="project for api data factory reference tests",
            creator=self.user,
        )

    def test_variable_resolver_resolves_data_factory_tag_and_record_paths(self):
        record = DataFactoryRecord.objects.create(
            project=self.project,
            creator=self.user,
            tool_name="json_format",
            tool_category="json",
            tool_scenario="format_conversion",
            input_data={"text": '{"token":"abc123"}'},
            output_data={
                "success": True,
                "tool_name": "json_format",
                "result": {"text": '{\n  "token": "abc123"\n}', "parsed": {"token": "abc123", "profile": {"name": "FlyTest"}}},
                "summary": "JSON 格式化完成",
                "metadata": {},
            },
            is_saved=True,
        )
        tag = self.project.data_factory_tags.create(name="鐧诲綍鍑瘉", code="login_payload", creator=self.user)
        record.tags.add(tag)

        resolver = VariableResolver({"df": build_reference_tree(self.project.id)})

        self.assertEqual(resolver.resolve("{{df.tag.login_payload.token}}"), "abc123")
        self.assertEqual(resolver.resolve("Bearer {{df.record.%s.token}}" % record.id), "Bearer abc123")
        self.assertEqual(resolver.resolve({"name": "{{df.record.%s.profile.name}}" % record.id}), {"name": "FlyTest"})

    def test_find_missing_variables_ignores_existing_data_factory_references(self):
        record = DataFactoryRecord.objects.create(
            project=self.project,
            creator=self.user,
            tool_name="random_string",
            tool_category="random",
            tool_scenario="data_generation",
            input_data={"length": 8},
            output_data={
                "success": True,
                "tool_name": "random_string",
                "result": "demo-user",
                "summary": "ok",
                "metadata": {},
            },
            is_saved=True,
        )
        tag = self.project.data_factory_tags.create(name="用户名", code="login_name", creator=self.user)
        record.tags.add(tag)
        variables = {"df": build_reference_tree(self.project.id)}

        missing = find_missing_variables(
            variables,
            {"username": "{{df.tag.login_name}}", "missing": "{{df.tag.not_exists}}"},
        )

        self.assertEqual(missing, ["df.tag.not_exists"])


def _patched_test_import_document_creates_requests_scripts_and_test_cases(self):
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
    self.assertFalse(payload["ai_requested"])
    self.assertFalse(payload["ai_used"])
    self.assertEqual(payload["ai_issue_code"], "not_requested")
    self.assertEqual(ApiRequest.objects.count(), 2)
    self.assertEqual(ApiTestCase.objects.count(), 2)


def _patched_test_import_document_can_skip_test_case_generation(self):
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

    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    self.assertIn("AI", str(self._payload(response)["error"]))
    self.assertEqual(ApiRequest.objects.count(), 0)
    self.assertEqual(ApiTestCase.objects.count(), 0)


def _patched_test_pdf_import_prefers_ai_before_rule_parse(self):
    with patch("api_automation.import_service._build_environment_drafts", return_value=[]), patch(
        "api_automation.import_service.import_requests_from_document"
    ) as mock_rule_parse, patch(
        "api_automation.import_service.enhance_import_result_with_ai"
    ) as mock_enhance:
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
    self.assertEqual(payload["source_type"], "ai_document")
    self.assertTrue(payload["ai_used"])
    self.assertEqual(payload["items"][0]["name"], "PDF Login")
    mock_rule_parse.assert_not_called()


def _patched_test_build_ai_failure_note_for_concurrent_limit_is_friendly(self):
    note = _build_ai_failure_note(
        Exception("Error code: 429 - {'error': {'code': 'concurrent_request_limit_exceeded'}}")
    )
    self.assertIn("并发限流", note)
    self.assertIn("429", note)


def _patched_test_build_ai_failure_note_for_timeout_is_friendly(self):
    note = _build_ai_failure_note(Exception("Request timed out."))
    self.assertIn("请求超时", note)
    self.assertIn("缩小文档分片", note)


def _patched_test_build_ai_failure_note_for_connection_error_is_friendly(self):
    note = _build_ai_failure_note(Exception("Connection error."))
    self.assertIn("AI 网关连接异常", note)
    self.assertIn("Connection error", note)
    self.assertIn("缩小文档分片", note)


ApiAutomationImportDocumentTests.test_import_document_creates_requests_scripts_and_test_cases = (
    _patched_test_import_document_creates_requests_scripts_and_test_cases
)
ApiAutomationImportDocumentTests.test_import_document_can_skip_test_case_generation = (
    _patched_test_import_document_can_skip_test_case_generation
)
ApiAutomationImportDocumentTests.test_pdf_import_prefers_ai_before_rule_parse = (
    _patched_test_pdf_import_prefers_ai_before_rule_parse
)
ApiAutomationAIParserTests.test_build_ai_failure_note_for_concurrent_limit_is_friendly = (
    _patched_test_build_ai_failure_note_for_concurrent_limit_is_friendly
)
ApiAutomationAIParserTests.test_build_ai_failure_note_for_timeout_is_friendly = (
    _patched_test_build_ai_failure_note_for_timeout_is_friendly
)
ApiAutomationAIParserTests.test_build_ai_failure_note_for_connection_error_is_friendly = (
    _patched_test_build_ai_failure_note_for_connection_error_is_friendly
)


def _patched_test_request_list_is_lightweight(self):
    api_request = ApiRequest.objects.create(
        collection=self.collection,
        name="List users",
        method="GET",
        url="/api/users",
        headers={"Accept": "application/json"},
        params={"page": 1},
        body_type="json",
        body={"demo": True},
        assertions=[{"type": "status_code", "expected": 200}, {"type": "body_contains", "expected": "ok"}],
        created_by=self.user,
    )
    ApiTestCase.objects.create(
        project=self.project,
        request=api_request,
        name="List users case",
        status="ready",
        script={"request": {"method": "GET", "url": "/api/users"}},
        assertions=[{"type": "status_code", "expected": 200}],
        creator=self.user,
    )

    response = self.client.get(
        "/api/api-automation/requests/",
        {
            "project": self.project.id,
            "collection": self.collection.id,
        },
    )

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    payload = self._payload(response)
    self.assertEqual(len(payload), 1)
    self.assertEqual(payload[0]["test_case_count"], 1)
    self.assertEqual(payload[0]["assertion_count"], 2)
    self.assertNotIn("generated_script", payload[0])
    self.assertNotIn("request_spec", payload[0])
    self.assertNotIn("assertion_specs", payload[0])
    self.assertNotIn("extractor_specs", payload[0])


ApiAutomationImportDocumentTests.test_request_list_is_lightweight = _patched_test_request_list_is_lightweight


def _patched_test_ai_parse_job_is_not_recovered_too_early(self):
    with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
        job = ApiImportJob.objects.create(
            project=self.project,
            collection=self.collection,
            creator=self.user,
            source_name="demo.md",
            source_file=SimpleUploadedFile(
                "demo.md",
                "## Login\n鎺ュ彛鍦板潃: /api/login\n璇锋眰鏂瑰紡: POST\n鍙傛暟: username,password".encode("utf-8"),
                content_type="text/markdown",
            ),
            status="running",
            progress_percent=48,
            progress_stage="ai_parse",
            progress_message="正在使用 AI 解析接口文档正文。",
            generate_test_cases=True,
            enable_ai_parse=True,
        )
        ApiImportJob.objects.filter(pk=job.id).update(updated_at=timezone.now() - timedelta(seconds=310))
        job.refresh_from_db()

        recovered = _recover_stale_import_job(job)

        self.assertEqual(recovered.status, "running")
        self.assertEqual(recovered.progress_stage, "ai_parse")


ApiAutomationImportDocumentTests.test_ai_parse_job_is_not_recovered_too_early = (
    _patched_test_ai_parse_job_is_not_recovered_too_early
)


def _patched_test_test_case_override_body_replaces_request_body(self):
    api_request = ApiRequest.objects.create(
        collection=self.collection,
        name="Update profile",
        method="POST",
        url="/api/profile/update",
        headers={"Content-Type": "application/json"},
        params={},
        body_type="json",
        body={"nickname": "old", "profile": "old profile"},
        assertions=[{"type": "status_code", "expected": 200}],
        created_by=self.user,
    )
    test_case = ApiTestCase.objects.create(
        project=self.project,
        request=api_request,
        name="Update profile case",
        status="ready",
        script={"request": {"method": "POST", "url": "/api/profile/update"}},
        assertions=[{"type": "status_code", "expected": 200}],
        creator=self.user,
    )

    apply_test_case_override_payload(
        test_case,
        {
            "method": "POST",
            "url": "/api/profile/update",
            "body_mode": "json",
            "body_json": {"nickname": "new"},
            "raw_text": "",
            "xml_text": "",
            "binary_base64": "",
            "graphql_query": "",
            "graphql_operation_name": "",
            "graphql_variables": {},
            "timeout_ms": 30000,
            "headers": [],
            "query": [],
            "cookies": [],
            "form_fields": [],
            "multipart_parts": [],
            "files": [],
            "auth": {},
            "transport": {},
            "replace_fields": ["body_mode", "body_json", "raw_text", "xml_text", "binary_base64", "graphql_query", "graphql_operation_name", "graphql_variables"],
        },
    )

    test_case.refresh_from_db()
    override_payload = serialize_test_case_override(test_case)
    self.assertEqual(override_payload["body_json"], {"nickname": "new"})
    self.assertIn("body_json", override_payload.get("replace_fields") or [])
    self.assertEqual(test_case.script["request"]["body"], {"nickname": "new"})


ApiAutomationImportDocumentTests.test_test_case_override_body_replaces_request_body = (
    _patched_test_test_case_override_body_replaces_request_body
)
