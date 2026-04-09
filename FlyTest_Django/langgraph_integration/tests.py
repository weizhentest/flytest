from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from langgraph_integration.models import LLMConfig, get_user_active_llm_config
from langgraph_integration.views import (
    LLMConfigViewSet,
    _should_hide_tool_message,
    _diagnose_llm_connection_error,
    _extract_llm_response_text,
)


class LlmConnectionDiagnosticsTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.config = LLMConfig.objects.create(
            config_name="Test Config",
            provider="openai_compatible",
            name="gpt-5.4",
            api_url="https://example.com/v1",
            api_key="test-key",
            is_active=True,
        )
        self.factory = APIRequestFactory()

    def test_extract_llm_response_text_supports_list_content(self) -> None:
        response = Mock()
        response.content = [
            {"type": "text", "text": "OK"},
            {"type": "text", "text": "connected"},
        ]

        text = _extract_llm_response_text(response)

        self.assertEqual(text, "OK\nconnected")

    def test_diagnose_error_gives_v1_hint_for_404(self) -> None:
        self.config.api_url = "https://example.com"

        message = _diagnose_llm_connection_error(
            self.config,
            "Error code: 404 - {'error': {'message': 'Not Found'}}",
        )

        self.assertIn("/v1", message)
        self.assertIn("接口地址不存在", message)

    def test_test_connection_accepts_non_string_content_as_success(self) -> None:
        llm = Mock()
        llm.invoke.return_value = Mock(content=[{"type": "text", "text": "OK"}])
        request = self.factory.post(
            f"/api/lg/llm-configs/{self.config.id}/test_connection/"
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "test_connection"})

        with patch("langgraph_integration.views.create_llm_instance", return_value=llm):
            response = view(request, pk=str(self.config.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "连接正常")
        self.assertEqual(response.data["diagnostics"]["conclusion"], "chat_completion_ok")

    def test_test_connection_treats_empty_content_as_reachable_success(self) -> None:
        llm = Mock()
        llm.invoke.return_value = Mock(
            content="",
            response_metadata={
                "finish_reason": "stop",
                "token_usage": {"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
            },
            usage_metadata={"input_tokens": 8, "output_tokens": 6, "total_tokens": 14},
        )
        request = self.factory.post(
            f"/api/lg/llm-configs/{self.config.id}/test_connection/"
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "test_connection"})

        with patch("langgraph_integration.views.create_llm_instance", return_value=llm):
            response = view(request, pk=str(self.config.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["message"], "连接正常")
        self.assertEqual(response.data["diagnostics"]["conclusion"], "connection_ok_response_text_empty")
        self.assertEqual(response.data["diagnostics"]["completion_tokens"], 6)

    def test_probe_models_returns_batch_summary(self) -> None:
        request = self.factory.post(
            f"/api/lg/llm-configs/{self.config.id}/probe_models/",
            {"models": ["gpt-4o", "gpt-5.4"]},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "probe_models"})

        with patch(
            "langgraph_integration.views._probe_model_compatibility",
            side_effect=[
                {
                    "model": "gpt-4o",
                    "status": "success",
                    "message": "返回正文：OK",
                    "diagnostics": {"conclusion": "chat_completion_ok"},
                },
                {
                    "model": "gpt-5.4",
                    "status": "warning",
                    "message": "接口可连通，但聊天正文为空。",
                    "diagnostics": {"conclusion": "chat_completion_empty"},
                },
            ],
        ):
            response = view(request, pk=str(self.config.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertIn("2 个模型探测", response.data["message"])
        self.assertEqual(len(response.data["results"]), 2)


class LlmConfigSharingTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password123",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password123",
        )
        self.group = Group.objects.create(name="研发一组")
        self.member.groups.add(self.group)
        self.config = LLMConfig.objects.create(
            owner=self.owner,
            config_name="Shared Config",
            provider="openai_compatible",
            name="gpt-5.4",
            api_url="https://example.com/v1",
            api_key="test-key",
            system_prompt="owner only",
            is_active=True,
        )
        self.config.shared_groups.add(self.group)
        self.client = APIClient()

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_shared_member_sees_config_but_sensitive_fields_are_hidden(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/lg/llm-configs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["config_name"], "Shared Config")
        self.assertEqual(payload[0]["api_url"], "")
        self.assertEqual(payload[0]["system_prompt"], "")
        self.assertFalse(payload[0]["can_edit"])
        self.assertTrue(payload[0]["is_shared"])

    def test_shared_member_can_activate_shared_config_for_self(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/lg/llm-configs/{self.config.id}/",
            {"is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_user_active_llm_config(self.member).id, self.config.id)

    def test_shared_member_cannot_edit_sensitive_fields(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f"/api/lg/llm-configs/{self.config.id}/",
            {"config_name": "Hacked"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
