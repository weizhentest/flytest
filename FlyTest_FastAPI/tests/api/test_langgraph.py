import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


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

from django.http import JsonResponse, StreamingHttpResponse  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from knowledge.models import KnowledgeBase  # noqa: E402
from langgraph_integration.models import ChatSession, LLMConfig  # noqa: E402
from rest_framework.response import Response  # noqa: E402
from app.main import create_app  # noqa: E402


client = TestClient(create_app())


def _unwrap_data(payload):
    if isinstance(payload, dict) and "data" in payload and "status" in payload:
        return payload["data"]
    return payload


def _auth_headers() -> dict[str, str]:
    response = client.post("/api/token/", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access']}"}


def _create_project(headers: dict[str, str]) -> int:
    response = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": f"LangGraph Project {uuid4().hex[:8]}",
            "description": "langgraph fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_langgraph_llm_config_and_tool_approval_flow() -> None:
    headers = _auth_headers()

    providers = client.get("/api/lg/providers/", headers=headers)
    assert providers.status_code == 200

    config_created = client.post(
        "/api/lg/llm-configs/",
        headers=headers,
        json={
            "config_name": f"fastapi-test-{uuid4().hex[:6]}",
            "provider": "openai_compatible",
            "name": "gpt-4o-mini",
            "api_url": "https://example.com/v1",
            "api_key": "secret-key",
            "system_prompt": "You are helpful",
            "supports_vision": False,
            "context_limit": 128000,
            "enable_summarization": True,
            "enable_hitl": True,
            "enable_streaming": True,
            "is_active": False,
        },
    )
    assert config_created.status_code == 201
    config_id = _unwrap_data(config_created.json())["id"]

    config_list = client.get("/api/lg/llm-configs/", headers=headers)
    assert config_list.status_code == 200
    assert any(item["id"] == config_id for item in _unwrap_data(config_list.json()))

    config_detail = client.get(f"/api/lg/llm-configs/{config_id}/", headers=headers)
    assert config_detail.status_code == 200
    assert _unwrap_data(config_detail.json())["id"] == config_id

    config_patch = client.patch(f"/api/lg/llm-configs/{config_id}/", headers=headers, json={"is_active": True})
    assert config_patch.status_code == 200
    assert _unwrap_data(config_patch.json())["is_active"] is True

    approval_created = client.post(
        "/api/lg/tool-approvals/",
        headers=headers,
        json={
            "tool_name": f"demo_tool_{uuid4().hex[:4]}",
            "policy": "ask_every_time",
            "scope": "permanent",
        },
    )
    assert approval_created.status_code in (200, 201)
    approval_payload = _unwrap_data(approval_created.json())
    approval_id = approval_payload["id"]

    approvals = client.get("/api/lg/tool-approvals/", headers=headers)
    assert approvals.status_code == 200
    assert any(item["id"] == approval_id for item in _unwrap_data(approvals.json()))

    batch_updated = client.post(
        "/api/lg/tool-approvals/batch_update/",
        headers=headers,
        json={
            "approvals": [
                {
                    "tool_name": f"batch_tool_{uuid4().hex[:4]}",
                    "policy": "always_allow",
                    "scope": "permanent",
                }
            ]
        },
    )
    assert batch_updated.status_code == 200

    available_tools = client.get("/api/lg/tool-approvals/available_tools/", headers=headers)
    assert available_tools.status_code == 200
    assert "policy_choices" in _unwrap_data(available_tools.json())

    reset = client.post("/api/lg/tool-approvals/reset/", headers=headers, json={"tool_name": approval_payload["tool_name"]})
    assert reset.status_code == 200

    deleted = client.delete(f"/api/lg/llm-configs/{config_id}/", headers=headers)
    assert deleted.status_code in (200, 204)


def test_langgraph_chat_and_resume_routes() -> None:
    headers = _auth_headers()

    async def fake_chat_post(self, request, *args, **kwargs):
        assert request.user.username == "admin"
        assert request.data["message"] == "hello"
        assert request.data["project_id"] == 1
        return Response(
            {
                "status": "success",
                "code": 200,
                "message": "Message processed successfully.",
                "data": {
                    "user_message": "hello",
                    "llm_response": "hi",
                    "session_id": "s1",
                    "project_id": 1,
                },
            },
            status=200,
        )

    async def fake_resume_generator(*args, **kwargs):
        yield 'data: {"type":"message","data":"resumed"}\n\n'
        yield "data: [DONE]\n\n"

    with patch("langgraph_integration.views.ChatAPIView.post", new=fake_chat_post):
        response = client.post(
            "/api/lg/chat/",
            headers=headers,
            json={"message": "hello", "project_id": 1},
        )
        assert response.status_code == 200
        assert response.json()["data"]["llm_response"] == "hi"
        assert response.json()["data"]["session_id"] == "s1"

    with patch(
        "langgraph_integration.views.ChatResumeAPIView._create_resume_generator",
        return_value=fake_resume_generator(),
    ):
        resumed = client.post(
            "/api/lg/chat/resume/",
            headers=headers,
            json={"session_id": "s1", "project_id": 1, "decision": "approve"},
        )
        assert resumed.status_code == 200
        assert 'data: {"type":"message","data":"resumed"}' in resumed.text


def test_langgraph_native_sessions_batch_delete_and_rag_routes() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)
    admin_user = get_user_model().objects.get(username="admin")

    session_id = f"lg-session-{uuid4().hex[:6]}"
    fallback_session_id = f"lg-fallback-{uuid4().hex[:6]}"
    ChatSession.objects.create(
        user=admin_user,
        session_id=session_id,
        title="FastAPI Native Session",
        project_id=project_id,
    )

    with (
        patch("flytest_django.checkpointer.check_history_exists", return_value=True),
        patch(
            "flytest_django.checkpointer.get_thread_ids_by_prefix",
            return_value=[
                f"{admin_user.id}_{project_id}_{session_id}",
                f"{admin_user.id}_{project_id}_{fallback_session_id}",
            ],
        ),
    ):
        sessions = client.get(f"/api/lg/chat/sessions/?project_id={project_id}", headers=headers)
        assert sessions.status_code == 200
        payload = sessions.json()["data"]
        assert payload["project_id"] == str(project_id)
        assert any(item["id"] == session_id for item in payload["sessions_detail"])
        assert fallback_session_id in payload["sessions"]

    checkpoints = [
        SimpleNamespace(
            checkpoint={
                "ts": "2026-04-03T10:00:00+00:00",
                "channel_values": {
                    "messages": [
                        HumanMessage(content="hello"),
                        AIMessage(
                            content="world",
                            additional_kwargs={
                                "metadata": {
                                    "agent": "agent_loop",
                                    "agent_type": "final",
                                    "step": 1,
                                    "max_steps": 5,
                                    "sse_event_type": "message",
                                    "is_thinking_process": True,
                                    }
                                },
                            usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
                        ),
                        ToolMessage(
                            content="tool output",
                            tool_call_id="tool-call-1",
                            additional_kwargs={
                                "metadata": {
                                    "step": 1,
                                    "sse_event_type": "tool_result",
                                }
                            },
                        ),
                    ]
                },
            }
        )
    ]

    class FakeCheckpointer:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def list(self, config):
            assert config["configurable"]["thread_id"] == f"{admin_user.id}_{project_id}_{session_id}"
            return checkpoints

    with (
        patch("flytest_django.checkpointer.check_history_exists", return_value=True),
        patch("flytest_django.checkpointer.get_sync_checkpointer", return_value=FakeCheckpointer()),
    ):
        history = client.get(
            f"/api/lg/chat/history/?session_id={session_id}&project_id={project_id}",
            headers=headers,
        )
        assert history.status_code == 200
        history_payload = history.json()["data"]
        assert history_payload["session_id"] == session_id
        assert history_payload["project_id"] == str(project_id)
        assert history_payload["context_token_count"] == 15
        assert history_payload["history"][0]["type"] == "human"
        assert history_payload["history"][1]["agent"] == "agent_loop"
        assert history_payload["history"][1]["is_thinking_process"] is True
        assert history_payload["history"][2]["type"] == "tool"
        assert history_payload["history"][2]["sse_event_type"] == "tool_result"

    with (
        patch("flytest_django.checkpointer.check_history_exists", return_value=True),
        patch("flytest_django.checkpointer.rollback_checkpoints_to_count", return_value=3),
    ):
        rollback = client.patch(
            f"/api/lg/chat/history/?session_id={session_id}&project_id={project_id}",
            headers=headers,
            json={"keep_count": 2},
        )
        assert rollback.status_code == 200
        rollback_payload = rollback.json()["data"]
        assert rollback_payload["deleted_count"] == 3
        assert rollback_payload["kept_count"] == 2

    with (
        patch("flytest_django.checkpointer.check_history_exists", return_value=True),
        patch("flytest_django.checkpointer.delete_checkpoints_by_thread_id", return_value=1),
    ):
        deleted_single = client.delete(
            f"/api/lg/chat/history/?session_id={session_id}&project_id={project_id}",
            headers=headers,
        )
        assert deleted_single.status_code == 200
        deleted_single_payload = deleted_single.json()["data"]
        assert deleted_single_payload["deleted_count"] == 1
        assert deleted_single_payload["session_deleted_count"] == 1

    with (
        patch("flytest_django.checkpointer.check_history_exists", return_value=True),
        patch("flytest_django.checkpointer.delete_checkpoints_batch", return_value=2),
    ):
        deleted = client.post(
            "/api/lg/chat/batch-delete/",
            headers=headers,
            json={"session_ids": [session_id], "project_id": project_id},
        )
        assert deleted.status_code == 200
        deleted_payload = deleted.json()["data"]
        assert deleted_payload["deleted_count"] == 2
        assert deleted_payload["processed_sessions"] == 1

    assert not ChatSession.objects.filter(session_id=session_id, project_id=project_id).exists()

    knowledge_base = KnowledgeBase.objects.create(
        name=f"KB {uuid4().hex[:6]}",
        description="fastapi native rag test",
        project_id=project_id,
        creator=admin_user,
    )
    LLMConfig.objects.filter(is_active=True).update(is_active=False)
    LLMConfig.objects.create(
        config_name=f"fastapi-rag-{uuid4().hex[:6]}",
        provider="openai_compatible",
        name="gpt-4o-mini",
        api_url="https://example.com/v1",
        api_key="secret-key",
        is_active=True,
    )

    rag_result = {
        "question": "hello",
        "answer": "world",
        "context": [{"content": "ctx", "similarity_score": 0.9, "metadata": {"source": "demo"}}],
        "retrieval_time": 0.1,
        "generation_time": 0.2,
        "total_time": 0.3,
    }

    with (
        patch("langgraph_integration.views.create_llm_instance", return_value=object()),
        patch("knowledge.langgraph_integration.KnowledgeRAGService.query", return_value=rag_result),
    ):
        rag = client.post(
            "/api/lg/knowledge/rag/",
            headers=headers,
            json={
                "query": "hello",
                "knowledge_base_id": str(knowledge_base.id),
                "project_id": project_id,
            },
        )
        assert rag.status_code == 200
        rag_payload = rag.json()["data"]
        assert rag_payload["query"] == "hello"
        assert rag_payload["answer"] == "world"
        assert rag_payload["sources"][0]["content"] == "ctx"
