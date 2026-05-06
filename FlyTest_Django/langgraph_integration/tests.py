from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from accounts.models import UserProfile
from langgraph_integration.models import LLMConfig, LLMTokenUsage, get_user_active_llm_config
from langgraph_integration.views import (
    LLMConfigViewSet,
    create_llm_instance,
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

        self.assertIn("接口地址不存在", message)
        self.assertIn("https://example.com", message)

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

    @patch("langgraph_integration.views.ClaudeMessagesCompatibleChatModel")
    def test_create_llm_instance_uses_messages_adapter(self, mock_messages_model) -> None:
        self.config.wire_api = "messages"

        create_llm_instance(self.config, temperature=0.2)

        self.assertTrue(mock_messages_model.called)
        self.assertEqual(mock_messages_model.call_args.kwargs["wire_api"], "messages")

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

    def test_provider_choices_include_siliconflow(self) -> None:
        from langgraph_integration.views import ProviderChoicesAPIView

        request = self.factory.get("/api/lg/providers/")
        force_authenticate(request, user=self.user)
        response = ProviderChoicesAPIView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        choices = response.data["data"]["choices"]
        self.assertTrue(any(item["value"] == "siliconflow" for item in choices))

    @patch("langgraph_integration.views.ChatOpenAI")
    def test_create_llm_instance_uses_siliconflow_default_base_url(self, mock_chat_openai) -> None:
        self.config.provider = "siliconflow"
        self.config.api_url = ""
        self.config.wire_api = "chat_completions"

        create_llm_instance(self.config, temperature=0.2)

        self.assertEqual(
            mock_chat_openai.call_args.kwargs["base_url"],
            "https://api.siliconflow.cn/v1",
        )

    @patch("langgraph_integration.views.http_requests.post")
    @patch("langgraph_integration.views.http_requests.get")
    def test_fetch_models_augments_local_proxy_with_gpt_5_5(self, mock_get, mock_post) -> None:
        self.config.api_url = "http://127.0.0.1:8327/v1"
        self.config.save(update_fields=["api_url"])

        models_response = Mock()
        models_response.raise_for_status.return_value = None
        models_response.json.return_value = {
            "data": [
                {"id": "gpt-5"},
                {"id": "gpt-5.4"},
            ]
        }
        mock_get.return_value = models_response

        probe_response = Mock()
        probe_response.raise_for_status.return_value = None
        probe_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_post.return_value = probe_response

        request = self.factory.post(
            "/api/lg/llm-configs/fetch_models/",
            {"config_id": self.config.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "fetch_models"})

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["models"], ["gpt-5", "gpt-5.4", "gpt-5.5"])
        mock_post.assert_called_once()
        self.assertEqual(
            mock_post.call_args.args[0],
            "http://127.0.0.1:8327/v1/chat/completions",
        )
        self.assertEqual(mock_post.call_args.kwargs["json"]["model"], "gpt-5.5")

    @patch("langgraph_integration.views.http_requests.post")
    @patch("langgraph_integration.views.http_requests.get")
    def test_fetch_models_keeps_original_models_when_probe_fails(self, mock_get, mock_post) -> None:
        self.config.api_url = "http://127.0.0.1:8327/v1"
        self.config.save(update_fields=["api_url"])

        models_response = Mock()
        models_response.raise_for_status.return_value = None
        models_response.json.return_value = {
            "data": [
                {"id": "gpt-5"},
                {"id": "gpt-5.4"},
            ]
        }
        mock_get.return_value = models_response
        mock_post.side_effect = Exception("probe failed")

        request = self.factory.post(
            "/api/lg/llm-configs/fetch_models/",
            {"config_id": self.config.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "fetch_models"})

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["models"], ["gpt-5", "gpt-5.4"])

    @patch("langgraph_integration.views.http_requests.post")
    @patch("langgraph_integration.views.http_requests.get")
    def test_fetch_models_does_not_probe_non_local_proxy_endpoint(self, mock_get, mock_post) -> None:
        models_response = Mock()
        models_response.raise_for_status.return_value = None
        models_response.json.return_value = {
            "data": [
                {"id": "gpt-5"},
                {"id": "gpt-5.4"},
            ]
        }
        mock_get.return_value = models_response

        request = self.factory.post(
            "/api/lg/llm-configs/fetch_models/",
            {"config_id": self.config.id},
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = LLMConfigViewSet.as_view({"post": "fetch_models"})

        response = view(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(response.data["models"], ["gpt-5", "gpt-5.4"])
        mock_post.assert_not_called()


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


class TokenUsageDashboardTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            username="dashboard_admin",
            email="dashboard_admin@example.com",
            password="password123",
        )
        self.user_a = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password123",
        )
        self.user_b = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="password123",
        )
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={"real_name": "管理员"},
        )
        UserProfile.objects.update_or_create(
            user=self.user_a,
            defaults={"real_name": "张三"},
        )
        UserProfile.objects.update_or_create(
            user=self.user_b,
            defaults={"real_name": "李四"},
        )
        self.config_a = LLMConfig.objects.create(
            owner=self.admin,
            config_name="GLM",
            provider="siliconflow",
            name="Pro/zai-org/GLM-5.1",
            api_url="https://api.siliconflow.cn/v1",
            api_key="sk-test",
        )
        self.config_b = LLMConfig.objects.create(
            owner=self.admin,
            config_name="GPT",
            provider="openai_compatible",
            name="gpt-5.4",
            api_url="https://example.com/v1",
            api_key="sk-test",
        )
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=6)

        LLMTokenUsage.objects.create(
            user=self.user_a,
            llm_config=self.config_a,
            config_name=self.config_a.config_name,
            provider=self.config_a.provider,
            model_name=self.config_a.name,
            source="api_automation",
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            request_count=2,
            usage_date=today,
        )
        LLMTokenUsage.objects.create(
            user=self.user_b,
            llm_config=self.config_b,
            config_name=self.config_b.config_name,
            provider=self.config_b.provider,
            model_name=self.config_b.name,
            source="requirements_review",
            prompt_tokens=300,
            completion_tokens=100,
            total_tokens=400,
            request_count=1,
            usage_date=yesterday,
        )
        LLMTokenUsage.objects.create(
            user=self.user_a,
            llm_config=self.config_b,
            config_name=self.config_b.config_name,
            provider=self.config_b.provider,
            model_name=self.config_b.name,
            source="langgraph_chat",
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            request_count=1,
            usage_date=week_ago,
        )
        self.client = APIClient()

    def test_token_usage_dashboard_returns_by_model_and_by_user(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/lg/token-usage/", {"preset": "7d"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"]["total_tokens"], 675)
        self.assertEqual(response.data["permissions"]["is_admin"], True)
        self.assertEqual(len(response.data["by_model"]), 2)
        self.assertEqual(response.data["by_model"][0]["model_name"], "gpt-5.4")
        self.assertEqual(response.data["by_user"][0]["username"], "bob")
        self.assertEqual(response.data["by_user"][0]["real_name"], "李四")

    def test_token_usage_dashboard_for_regular_user_only_returns_self(self):
        self.client.force_authenticate(self.user_a)

        response = self.client.get("/api/lg/token-usage/", {"preset": "7d"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"]["total_tokens"], 275)
        self.assertEqual(response.data["permissions"]["can_view_all_users"], False)
        self.assertEqual(len(response.data["by_user"]), 1)
        self.assertEqual(response.data["by_user"][0]["username"], "alice")
        self.assertEqual(response.data["by_user"][0]["real_name"], "张三")
