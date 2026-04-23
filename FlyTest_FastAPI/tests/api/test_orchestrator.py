import os
from pathlib import Path
import sys
from unittest.mock import patch
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

from django.http import JsonResponse, StreamingHttpResponse  # noqa: E402
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
            "name": f"Orchestrator Project {uuid4().hex[:8]}",
            "description": "orchestrator fastapi migration test",
            "credentials": [],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_orchestrator_task_flow() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    created = client.post(
        "/api/orchestrator/tasks/",
        headers=headers,
        json={
            "project": project_id,
            "requirement": f"Generate plan for {uuid4().hex[:6]}",
            "user_notes": "fastapi migration task test",
        },
    )
    assert created.status_code == 201
    task = created.json()["data"]
    task_id = task["id"]
    assert task["status"] == "pending"

    listing = client.get(f"/api/orchestrator/tasks/?project={project_id}", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == task_id for item in listing.json()["data"])

    detail = client.get(f"/api/orchestrator/tasks/{task_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["project"] == project_id


def test_orchestrator_agent_loop_proxy_routes() -> None:
    headers = _auth_headers()
    project_id = _create_project(headers)

    async def fake_stream_generator(*args, **kwargs):
        yield 'data: {"type":"start","session_id":"s1"}\n\n'
        yield "data: [DONE]\n\n"

    async def fake_non_stream_handler(*args, **kwargs):
        return JsonResponse(
            {
                "status": "success",
                "code": 200,
                "message": "Chat completed",
                "data": {"session_id": "s2", "content": "done", "total_steps": 1},
            }
        )

    async def fake_resume_generator(*args, **kwargs):
        yield 'data: {"type":"resume_start","session_id":"s1","decision":"approve"}\n\n'
        yield 'data: {"type":"complete","total_steps":1}\n\n'
        yield "data: [DONE]\n\n"

    with patch(
        "orchestrator_integration.agent_loop_view.AgentLoopStreamAPIView._create_stream_generator",
        return_value=fake_stream_generator(),
    ):
        response = client.post(
            "/api/orchestrator/agent-loop/",
            headers={**headers, "Accept": "text/event-stream"},
            json={"message": "hello", "project_id": project_id, "stream": True},
        )
        assert response.status_code == 200
        assert 'data: {"type":"start","session_id":"s1"}' in response.text
        assert "data: [DONE]" in response.text

    with patch(
        "orchestrator_integration.agent_loop_view.AgentLoopStreamAPIView._handle_non_stream_request",
        new=fake_non_stream_handler,
    ):
        response = client.post(
            "/api/orchestrator/agent-loop/",
            headers=headers,
            json={"message": "hello", "project_id": project_id, "stream": False},
        )
        assert response.status_code == 200
        assert response.json()["data"]["session_id"] == "s2"
        assert response.json()["data"]["content"] == "done"

    response = client.post("/api/orchestrator/agent-loop/stop/", headers=headers, json={"session_id": "s1"})
    assert response.status_code == 200
    assert response.json()["data"]["success"] is True
    assert response.json()["data"]["session_id"] == "s1"

    with patch(
        "orchestrator_integration.agent_loop_view.AgentLoopResumeAPIView._create_resume_stream_generator",
        return_value=fake_resume_generator(),
    ):
        response = client.post(
            "/api/orchestrator/agent-loop/resume/",
            headers=headers,
            json={"session_id": "s1", "resume": {"i1": {"decisions": [{"type": "approve"}], "action_count": 1}}},
        )
        assert response.status_code == 200
        assert '"type":"resume_start"' in response.text
        assert '"type":"complete"' in response.text
