from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.errors import AppError
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.langgraph.service import (
    available_tools,
    batch_update_tool_approvals,
    batch_delete_chat_history,
    build_chat_response,
    build_chat_resume_stream,
    create_llm_config,
    create_tool_approval,
    delete_chat_history,
    delete_llm_config,
    delete_tool_approval,
    fetch_models,
    get_chat_history,
    get_llm_config,
    get_tool_approval,
    list_llm_configs,
    list_tool_approvals,
    list_chat_sessions,
    provider_choices,
    rag_query,
    rollback_chat_history,
    reset_tool_approvals,
    test_llm_connection,
    token_usage_stats,
    update_llm_config,
    update_tool_approval,
)


router = APIRouter(prefix="/lg", tags=["langgraph"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/providers/")
async def lg_providers(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(provider_choices))


@router.post("/chat/")
async def lg_chat(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    payload, status_code = await build_chat_response(user.id, await request.json())
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/chat/resume/")
async def lg_chat_resume(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    try:
        generator = await build_chat_resume_stream(user.id, await request.json())
        return StreamingResponse(
            generator,
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message, "code": exc.status_code})


@router.get("/chat/history/")
async def lg_chat_history_get(
    session_id: str,
    project_id: int,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    return success_response(
        await run_in_threadpool(get_chat_history, user.id, session_id, project_id),
        message="Chat history retrieved successfully.",
    )


@router.delete("/chat/history/")
async def lg_chat_history_delete(
    session_id: str,
    project_id: int,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    return success_response(
        await run_in_threadpool(delete_chat_history, user.id, session_id, project_id),
        message="Chat history deleted successfully.",
    )


@router.patch("/chat/history/")
async def lg_chat_history_patch(
    request: Request,
    session_id: str,
    project_id: int,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    payload = await request.json()
    return success_response(
        await run_in_threadpool(
            rollback_chat_history,
            user.id,
            session_id,
            project_id,
            payload.get("keep_count"),
        ),
        message="Chat history rolled back successfully.",
    )


@router.get("/chat/sessions/")
async def lg_chat_sessions(
    project_id: int,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    return success_response(
        await run_in_threadpool(list_chat_sessions, user.id, project_id),
        message="User chat sessions retrieved successfully.",
    )


@router.post("/chat/batch-delete/")
async def lg_chat_batch_delete(
    request: Request,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    return success_response(
        await run_in_threadpool(batch_delete_chat_history, user.id, await request.json()),
        message="Batch delete completed successfully.",
    )


@router.get("/token-usage/")
async def lg_token_usage(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(token_usage_stats, user.id, dict(request.query_params)))


@router.post("/knowledge/rag/")
async def lg_knowledge_rag(
    request: Request,
    token: str = Depends(get_bearer_token),
    user=Depends(get_current_user),
):
    return success_response(
        await run_in_threadpool(rag_query, user.id, await request.json()),
        message="RAG query executed successfully.",
    )


@router.get("/llm-configs/")
async def lg_llm_configs(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(list_llm_configs))


@router.post("/llm-configs/", status_code=201)
async def lg_llm_configs_create(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(create_llm_config, await request.json()), code=201)


@router.post("/llm-configs/fetch_models/")
async def lg_llm_configs_fetch_models(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(fetch_models, await request.json()))


@router.get("/llm-configs/{config_id}/")
async def lg_llm_config_detail(config_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(get_llm_config, config_id))


@router.put("/llm-configs/{config_id}/")
async def lg_llm_config_put(config_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(update_llm_config, config_id, await request.json(), False))


@router.patch("/llm-configs/{config_id}/")
async def lg_llm_config_patch(config_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(update_llm_config, config_id, await request.json(), True))


@router.delete("/llm-configs/{config_id}/")
async def lg_llm_config_delete(config_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    await run_in_threadpool(delete_llm_config, config_id)
    return success_response(None)


@router.post("/llm-configs/{config_id}/test_connection/")
async def lg_llm_config_test(config_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(test_llm_connection, config_id))


@router.get("/tool-approvals/")
async def lg_tool_approvals(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(list_tool_approvals, user.id))


@router.post("/tool-approvals/", status_code=201)
async def lg_tool_approvals_create(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(create_tool_approval, user.id, await request.json()), code=201)


@router.get("/tool-approvals/available_tools/")
async def lg_tool_approvals_available(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(available_tools, user.id, request.query_params.get("session_id")))


@router.post("/tool-approvals/batch_update/")
async def lg_tool_approvals_batch_update(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(batch_update_tool_approvals, user.id, await request.json()))


@router.post("/tool-approvals/reset/")
async def lg_tool_approvals_reset(request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(reset_tool_approvals, user.id, await request.json()))


@router.get("/tool-approvals/{approval_id}/")
async def lg_tool_approval_detail(approval_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(get_tool_approval, user.id, approval_id))


@router.put("/tool-approvals/{approval_id}/")
async def lg_tool_approval_put(approval_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(update_tool_approval, user.id, approval_id, await request.json(), False))


@router.patch("/tool-approvals/{approval_id}/")
async def lg_tool_approval_patch(approval_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    return success_response(await run_in_threadpool(update_tool_approval, user.id, approval_id, await request.json(), True))


@router.delete("/tool-approvals/{approval_id}/")
async def lg_tool_approval_delete(approval_id: int, request: Request, token: str = Depends(get_bearer_token), user=Depends(get_current_user)):
    await run_in_threadpool(delete_tool_approval, user.id, approval_id)
    return success_response(None)
