from __future__ import annotations

import json
import uuid
from typing import Any

from asgiref.sync import sync_to_async

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def stop_agent_loop(*, session_id: str) -> dict:
    ensure_django_setup()
    from orchestrator_integration.stop_signal import set_stop_signal

    if not session_id:
        raise AppError("session_id is required", status_code=400)

    success = set_stop_signal(session_id)
    return {"session_id": session_id, "success": success}


async def build_resume_stream(*, user_id: int, payload: dict[str, Any]):
    ensure_django_setup()
    from orchestrator_integration.agent_loop_view import AgentLoopResumeAPIView

    session_id = str(payload.get("session_id") or "").strip()
    resume_data = payload.get("resume") or {}
    project_id = payload.get("project_id")
    knowledge_base_id = payload.get("knowledge_base_id")
    use_knowledge_base = bool(payload.get("use_knowledge_base", False))

    if not session_id:
        raise AppError("session_id is required", status_code=400)
    if not isinstance(resume_data, dict) or not resume_data:
        raise AppError("resume data is required", status_code=400)

    view = AgentLoopResumeAPIView()
    user = await sync_to_async(get_django_user)(user_id)
    if not user:
        raise AppError("User not found", status_code=404)

    return view._create_resume_stream_generator(
        user,
        session_id,
        project_id,
        resume_data,
        knowledge_base_id,
        use_knowledge_base,
    )


async def build_error_stream(*, message: str, code: int):
    payload = {"type": "error", "message": message, "code": code}
    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def execute_agent_loop(*, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_django_setup()
    from orchestrator_integration.agent_loop_view import AgentLoopStreamAPIView, check_project_permission
    from orchestrator_integration.stop_signal import clear_stop_signal

    user = await sync_to_async(get_django_user)(user_id)
    if not user:
        raise AppError("User not found", status_code=404)

    user_message = str(payload.get("message") or "").strip()
    session_id = str(payload.get("session_id") or "").strip() or uuid.uuid4().hex
    project_id = payload.get("project_id")
    knowledge_base_id = payload.get("knowledge_base_id")
    use_knowledge_base = bool(payload.get("use_knowledge_base", True))
    prompt_id = payload.get("prompt_id")
    image_base64 = payload.get("image")
    generate_playwright_script = bool(payload.get("generate_playwright_script", False))
    test_case_id = payload.get("test_case_id")
    use_pytest = bool(payload.get("use_pytest", True))
    stream_mode = payload.get("stream", True)
    if isinstance(stream_mode, str):
        stream_mode = stream_mode.lower() in ("true", "1", "yes")

    if not project_id:
        raise AppError("project_id is required", status_code=400)
    if not user_message:
        raise AppError("message is required", status_code=400)

    project = await sync_to_async(check_project_permission)(user, project_id)
    if not project:
        raise AppError("Project access denied", status_code=403)

    await sync_to_async(clear_stop_signal)(session_id)

    request = type("FastAPICompatRequest", (), {"user": user})()
    view = AgentLoopStreamAPIView()

    if stream_mode:
        generator = view._create_stream_generator(
            request,
            user_message,
            session_id,
            project_id,
            project,
            knowledge_base_id,
            use_knowledge_base,
            prompt_id,
            image_base64,
            generate_playwright_script,
            test_case_id,
            use_pytest,
        )
        return {"mode": "stream", "generator": generator}

    response = await view._handle_non_stream_request(
        request,
        user_message,
        session_id,
        project_id,
        project,
        knowledge_base_id,
        use_knowledge_base,
        prompt_id,
        image_base64,
        generate_playwright_script,
        test_case_id,
        use_pytest,
    )
    return {
        "mode": "json",
        "content": json.loads(response.content.decode("utf-8")),
        "status_code": response.status_code,
    }
