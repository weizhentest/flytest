from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.errors import AppError
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.compat.orchestrator_runtime import (
    build_error_stream,
    build_resume_stream,
    execute_agent_loop,
    stop_agent_loop,
)
from app.services.auth.service import get_current_user_from_token
from app.services.orchestrator.service import (
    create_task,
    get_task,
    list_tasks,
)


router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/tasks/")
def orchestrator_tasks(
    project: int | None = None,
    status: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_tasks(db=db, user=user, project=project, status=status))


@router.post("/tasks/", status_code=201)
def orchestrator_task_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_task(db=db, user=user, payload=payload), code=201)


@router.get("/tasks/{task_id}/")
def orchestrator_task_detail(task_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_task(db=db, user=user, task_id=task_id))


@router.post("/agent-loop/")
async def orchestrator_agent_loop(
    request: Request,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    result = await execute_agent_loop(user_id=user.id, payload=await request.json())
    if result["mode"] == "stream":
        return StreamingResponse(
            result["generator"],
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return JSONResponse(status_code=result["status_code"], content=result["content"])


@router.post("/agent-loop/stop/")
async def orchestrator_agent_loop_stop(request: Request, token: str = Depends(get_bearer_token)):
    payload = await request.json()
    return success_response(stop_agent_loop(session_id=str(payload.get("session_id") or "")))


@router.post("/agent-loop/resume/")
async def orchestrator_agent_loop_resume(
    request: Request,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    payload = await request.json()
    try:
        generator = await build_resume_stream(user_id=user.id, payload=payload)
        return StreamingResponse(
            generator,
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except AppError as exc:
        return StreamingResponse(
            build_error_stream(message=exc.message, code=exc.status_code),
            media_type="text/event-stream; charset=utf-8",
            status_code=exc.status_code,
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
