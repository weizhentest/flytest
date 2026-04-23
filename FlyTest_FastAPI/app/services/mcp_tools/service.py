from __future__ import annotations

from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from langchain_mcp_adapters.client import MultiServerMCPClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.auth import User
from app.db.models.mcp_tools import MCPTool, RemoteMCPConfig
from app.db.models.projects import Project
from app.repositories.mcp_tools import MCPToolsRepository
from app.repositories.projects import ProjectRepository


def _serialize_remote_config(item: RemoteMCPConfig) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "url": item.url,
        "transport": item.transport,
        "headers": item.headers or {},
        "is_active": bool(item.is_active),
        "require_hitl": bool(item.require_hitl),
        "hitl_tools": list(item.hitl_tools or []),
        "created_at": item.created_at.isoformat() if item.created_at else "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else "",
    }


def _serialize_tool(item: MCPTool) -> dict:
    effective_require_hitl = item.require_hitl
    if effective_require_hitl is None:
        if item.mcp_config.require_hitl:
            effective_require_hitl = True if not item.mcp_config.hitl_tools else item.name in (item.mcp_config.hitl_tools or [])
        else:
            effective_require_hitl = False
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "input_schema": item.input_schema or {},
        "mcp_name": item.mcp_config.name if item.mcp_config_id else "",
        "require_hitl": item.require_hitl,
        "effective_require_hitl": bool(effective_require_hitl),
        "synced_at": item.synced_at.isoformat() if item.synced_at else "",
    }


def list_remote_configs(*, db: Session) -> list[dict]:
    return [_serialize_remote_config(item) for item in MCPToolsRepository(db).list_remote_configs()]


def get_remote_config(*, db: Session, config_id: int) -> dict:
    item = MCPToolsRepository(db).get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)
    return _serialize_remote_config(item)


def create_remote_config(*, db: Session, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name:
        raise AppError("Remote MCP config name is required.", status_code=400, errors={"name": ["This field is required."]})
    if not url:
        raise AppError("Remote MCP config url is required.", status_code=400, errors={"url": ["This field is required."]})
    repo = MCPToolsRepository(db)
    if any(item.name == name for item in repo.list_remote_configs()):
        raise AppError("Remote MCP Configuration already exists.", status_code=400, errors={"name": ["This value must be unique."]})

    item = repo.create_remote_config(
        RemoteMCPConfig(
            name=name,
            url=url,
            transport=str(payload.get("transport") or "streamable-http").strip() or "streamable-http",
            headers=dict(payload.get("headers") or {}),
            is_active=bool(payload.get("is_active", True)),
            require_hitl=bool(payload.get("require_hitl", False)),
            hitl_tools=list(payload.get("hitl_tools") or []),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    )
    db.commit()
    item = repo.get_remote_config(config_id=item.id)
    return _serialize_remote_config(item)


def update_remote_config(*, db: Session, config_id: int, payload: dict) -> dict:
    repo = MCPToolsRepository(db)
    item = repo.get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)

    for field in ("name", "url", "transport"):
        if field in payload and payload.get(field) is not None:
            value = str(payload.get(field)).strip()
            if field in {"name", "url"} and not value:
                raise AppError(f"Remote MCP config {field} is required.", status_code=400, errors={field: ["This field is required."]})
            setattr(item, field, value)
    if "headers" in payload and payload.get("headers") is not None:
        item.headers = dict(payload.get("headers") or {})
    if "is_active" in payload and payload.get("is_active") is not None:
        item.is_active = bool(payload.get("is_active"))
    if "require_hitl" in payload and payload.get("require_hitl") is not None:
        item.require_hitl = bool(payload.get("require_hitl"))
    if "hitl_tools" in payload and payload.get("hitl_tools") is not None:
        item.hitl_tools = list(payload.get("hitl_tools") or [])
    item.updated_at = datetime.now()
    db.add(item)
    db.commit()
    item = repo.get_remote_config(config_id=config_id)
    return _serialize_remote_config(item)


def delete_remote_config(*, db: Session, config_id: int) -> None:
    repo = MCPToolsRepository(db)
    item = repo.get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)
    repo.delete_remote_config(item)
    db.commit()


async def ping_remote_config(*, db: Session, config_id: int) -> tuple[dict, int]:
    item = MCPToolsRepository(db).get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)

    server_key = item.name or "target_server"
    transport = (item.transport or "sse").replace("-", "_")
    client_config = {
        server_key: {
            "url": item.url,
            "transport": transport,
        }
    }
    if item.headers and isinstance(item.headers, dict) and item.headers:
        client_config[server_key]["headers"] = item.headers

    try:
        client = MultiServerMCPClient(client_config)
        tools = await client.get_tools()
        tool_names = [tool.name for tool in tools if hasattr(tool, "name")]
        payload = {
            "status": "online",
            "url": item.url,
            "tools_count": len(tool_names),
            "tools": tool_names,
        }
        return payload, 200
    except Exception as exc:  # noqa: BLE001
        payload = {
            "status": "error",
            "url": item.url,
            "error": f"{type(exc).__name__}: {exc}",
        }
        return payload, 500


def get_remote_config_tools(*, db: Session, config_id: int) -> dict:
    repo = MCPToolsRepository(db)
    item = repo.get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)
    tools = repo.list_remote_tools(config_id=config_id)
    return {
        "mcp_name": item.name,
        "tools_count": len(tools),
        "tools": [_serialize_tool(tool) for tool in tools],
    }


def _user_has_mcp_config_permission(*, db: Session, user: User) -> bool:
    if user.is_superuser:
        return True
    row = db.execute(
        text(
            """
            SELECT 1
            FROM auth_permission p
            JOIN django_content_type ct ON ct.id = p.content_type_id
            WHERE ct.app_label = 'mcp_tools'
              AND p.codename = 'add_remotemcpconfig'
              AND (
                p.id IN (
                  SELECT permission_id
                  FROM auth_user_user_permissions
                  WHERE user_id = :user_id
                )
                OR p.id IN (
                  SELECT gp.permission_id
                  FROM auth_group_permissions gp
                  JOIN auth_user_groups ug ON ug.group_id = gp.group_id
                  WHERE ug.user_id = :user_id
                )
              )
            LIMIT 1
            """
        ),
        {"user_id": user.id},
    ).first()
    return row is not None


async def sync_remote_config_tools(*, db: Session, config_id: int) -> tuple[dict, int]:
    repo = MCPToolsRepository(db)
    item = repo.get_remote_config(config_id=config_id)
    if not item:
        raise AppError("Remote MCP Configuration not found.", status_code=404)

    result = {
        "success": False,
        "tools_count": 0,
        "added": 0,
        "updated": 0,
        "removed": 0,
    }

    server_config = {
        item.name: {
            "transport": item.transport,
            "url": item.url,
        }
    }
    if item.headers:
        server_config[item.name]["headers"] = item.headers

    try:
        client = MultiServerMCPClient(server_config)
        async with client.session(item.name) as session:
            tools_response = await session.list_tools()
            remote_tools = tools_response.tools if hasattr(tools_response, "tools") else []

        existing_tools = {tool.name: tool for tool in repo.list_remote_tools(config_id=item.id)}
        existing_names = set(existing_tools.keys())
        remote_names = set()

        for tool in remote_tools:
            tool_name = tool.name
            remote_names.add(tool_name)
            description = getattr(tool, "description", "") or ""
            input_schema = getattr(tool, "inputSchema", {}) or {}

            if tool_name in existing_tools:
                existing_tool = existing_tools[tool_name]
                updated = False
                if existing_tool.description != description:
                    existing_tool.description = description
                    updated = True
                if existing_tool.input_schema != input_schema:
                    existing_tool.input_schema = input_schema
                    updated = True
                if updated:
                    existing_tool.synced_at = datetime.now()
                    db.add(existing_tool)
                    result["updated"] += 1
            else:
                repo.create_remote_tool(
                    MCPTool(
                        mcp_config_id=item.id,
                        name=tool_name,
                        description=description,
                        input_schema=input_schema,
                        synced_at=datetime.now(),
                    )
                )
                result["added"] += 1

        removed_names = existing_names - remote_names
        for name in removed_names:
            repo.delete_remote_tool(existing_tools[name])
        result["removed"] = len(removed_names)
        db.commit()

        result["success"] = True
        result["tools_count"] = len(remote_tools)
        return result, 200
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        result["error"] = str(exc)
        return result, 500


def call_mcp_tool(*, db: Session, user: User, tool_name: str, arguments: dict | None = None) -> dict:
    if not user or not _user_has_mcp_config_permission(db=db, user=user):
        raise AppError("You do not have permission to execute MCP tools.", status_code=403)

    if not tool_name:
        raise AppError("Tool name is required.", status_code=400, errors={"name": ["This field is required."]})

    if tool_name == "get_project_list":
        projects = ProjectRepository(db).list_accessible_projects(user=user)
        return [
            {
                "id": project.id,
                "name": project.name,
                "description": project.description or "",
            }
            for project in projects
        ]

    raise AppError(
        f"Tool '{tool_name}' not found.",
        status_code=404,
        errors={"name": [f"Tool '{tool_name}' is not registered."]},
    )
