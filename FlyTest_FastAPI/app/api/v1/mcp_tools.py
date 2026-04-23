from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.mcp_tools.service import (
    call_mcp_tool,
    create_remote_config,
    delete_remote_config,
    get_remote_config,
    get_remote_config_tools,
    list_remote_configs,
    ping_remote_config,
    sync_remote_config_tools,
    update_remote_config,
)


router = APIRouter(prefix="/mcp_tools", tags=["mcp-tools"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.post("/call/")
def mcp_tool_call(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(
        call_mcp_tool(
            db=db,
            user=user,
            tool_name=str(payload.get("name") or ""),
            arguments=dict(payload.get("arguments") or {}),
        )
    )


@router.get("/remote-configs/")
def mcp_config_list(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_remote_configs(db=db))


@router.post("/remote-configs/", status_code=201)
def mcp_config_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_remote_config(db=db, payload=payload), code=201)


@router.get("/remote-configs/{config_id}/")
def mcp_config_detail(config_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_remote_config(db=db, config_id=config_id))


@router.patch("/remote-configs/{config_id}/")
def mcp_config_patch(config_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_remote_config(db=db, config_id=config_id, payload=payload))


@router.post("/remote-configs/{config_id}/sync_tools/")
async def mcp_config_sync_tools(config_id: int, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    result, status_code = await sync_remote_config_tools(db=db, config_id=config_id)
    response.status_code = status_code
    return success_response(result, code=status_code)


@router.get("/remote-configs/{config_id}/tools/")
def mcp_config_tools(config_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_remote_config_tools(db=db, config_id=config_id))


@router.delete("/remote-configs/{config_id}/")
def mcp_config_delete(config_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_remote_config(db=db, config_id=config_id)
    return success_response(None)


@router.post("/remote-configs/ping/")
async def mcp_config_ping(
    payload: dict,
    response: Response,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result, status_code = await ping_remote_config(db=db, config_id=int(payload.get("config_id") or 0))
    response.status_code = status_code
    return success_response(result, code=status_code)
