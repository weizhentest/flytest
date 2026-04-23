from __future__ import annotations

from datetime import datetime, timedelta

import requests as http_requests
from asgiref.sync import sync_to_async
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def _actor(user_id: int):
    user = get_django_user(user_id)
    if not user:
        raise AppError("User not found", status_code=404)
    return user


def _accessible_projects(user_id: int):
    ensure_django_setup()
    from projects.models import Project

    user = _actor(user_id)
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(members__user=user).distinct()


def _chat_project(user_id: int, project_id: int | str):
    if project_id in (None, ""):
        raise AppError("project_id is required", status_code=400)

    project = _accessible_projects(user_id).filter(id=project_id).first()
    if not project:
        raise AppError(
            "You don't have permission to access this project or project doesn't exist.",
            status_code=403,
        )
    return project


def _project_for_rag(user_id: int, project_id: int | str):
    ensure_django_setup()
    from projects.models import Project

    if project_id in (None, ""):
        return None

    project = Project.objects.filter(id=project_id).first()
    if not project:
        raise AppError("Project not found", status_code=404)

    user = _actor(user_id)
    if not user.is_superuser and not project.members.filter(user=user).exists():
        raise AppError("You don't have permission to access this project.", status_code=403)

    return project


def _llm_queryset():
    ensure_django_setup()
    from langgraph_integration.models import LLMConfig

    return LLMConfig.objects.all().order_by("-created_at")


def _tool_approval_queryset(user_id: int):
    ensure_django_setup()
    from langgraph_integration.models import UserToolApproval

    return UserToolApproval.objects.filter(user=_actor(user_id)).order_by("-updated_at")


def provider_choices() -> dict:
    ensure_django_setup()
    from langgraph_integration.models import LLMConfig

    return {
        "choices": [{"value": value, "label": label} for value, label in LLMConfig.PROVIDER_CHOICES]
    }


def list_llm_configs() -> list[dict]:
    ensure_django_setup()
    from langgraph_integration.serializers import LLMConfigSerializer

    return LLMConfigSerializer(_llm_queryset(), many=True).data


def create_llm_config(payload: dict) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import LLMConfigSerializer

    serializer = LLMConfigSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Create LLM config failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return LLMConfigSerializer(instance).data


def get_llm_config(config_id: int) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import LLMConfigSerializer

    instance = _llm_queryset().filter(id=config_id).first()
    if not instance:
        raise AppError("LLM config not found", status_code=404)
    return LLMConfigSerializer(instance).data


def update_llm_config(config_id: int, payload: dict, partial: bool = True) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import LLMConfigSerializer

    instance = _llm_queryset().filter(id=config_id).first()
    if not instance:
        raise AppError("LLM config not found", status_code=404)
    serializer = LLMConfigSerializer(instance, data=payload, partial=partial)
    if not serializer.is_valid():
        raise AppError("Update LLM config failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return LLMConfigSerializer(instance).data


def delete_llm_config(config_id: int) -> None:
    instance = _llm_queryset().filter(id=config_id).first()
    if not instance:
        raise AppError("LLM config not found", status_code=404)
    instance.delete()


def test_llm_connection(config_id: int) -> dict:
    ensure_django_setup()
    from langgraph_integration.views import create_llm_instance

    config = _llm_queryset().filter(id=config_id).first()
    if not config:
        raise AppError("LLM config not found", status_code=404)

    try:
        llm = create_llm_instance(config, temperature=0.1)
        response = llm.invoke("Hi")
        if getattr(response, "content", None):
            return {"status": "success", "message": "连接测试成功"}
        return {"status": "warning", "message": "响应格式异常"}
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"连接失败: {exc}", status_code=400)


def fetch_models(payload: dict) -> dict:
    ensure_django_setup()
    from langgraph_integration.models import LLMConfig

    api_url = str(payload.get("api_url") or "").rstrip("/")
    api_key = str(payload.get("api_key") or "")
    config_id = payload.get("config_id")

    if config_id:
        config = LLMConfig.objects.filter(pk=config_id).first()
        if not config:
            raise AppError("配置不存在", status_code=404)
        if not api_url:
            api_url = str(config.api_url or "").rstrip("/")
        if not api_key:
            api_key = config.api_key or ""

    if not api_url:
        raise AppError("请提供 API URL", status_code=400)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = http_requests.get(f"{api_url}/models", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = [model.get("id") for model in data.get("data", []) if model.get("id")]
        return {"status": "success", "models": models}
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"获取模型列表失败: {exc}", status_code=400)


def list_tool_approvals(user_id: int) -> list[dict]:
    ensure_django_setup()
    from langgraph_integration.serializers import UserToolApprovalSerializer

    return UserToolApprovalSerializer(_tool_approval_queryset(user_id), many=True).data


def create_tool_approval(user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import UserToolApprovalSerializer

    serializer = UserToolApprovalSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Create tool approval failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(user=_actor(user_id))
    return UserToolApprovalSerializer(instance).data


def get_tool_approval(user_id: int, approval_id: int) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import UserToolApprovalSerializer

    instance = _tool_approval_queryset(user_id).filter(id=approval_id).first()
    if not instance:
        raise AppError("Tool approval not found", status_code=404)
    return UserToolApprovalSerializer(instance).data


def update_tool_approval(user_id: int, approval_id: int, payload: dict, partial: bool = True) -> dict:
    ensure_django_setup()
    from langgraph_integration.serializers import UserToolApprovalSerializer

    instance = _tool_approval_queryset(user_id).filter(id=approval_id).first()
    if not instance:
        raise AppError("Tool approval not found", status_code=404)
    serializer = UserToolApprovalSerializer(instance, data=payload, partial=partial)
    if not serializer.is_valid():
        raise AppError("Update tool approval failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return UserToolApprovalSerializer(instance).data


def delete_tool_approval(user_id: int, approval_id: int) -> None:
    instance = _tool_approval_queryset(user_id).filter(id=approval_id).first()
    if not instance:
        raise AppError("Tool approval not found", status_code=404)
    instance.delete()


def available_tools(user_id: int, session_id: str | None = None) -> dict:
    ensure_django_setup()
    from langgraph_integration.models import UserToolApproval
    from mcp_tools.models import RemoteMCPConfig

    user = _actor(user_id)
    approvals = UserToolApproval.objects.filter(user=user)
    if session_id:
        approvals = approvals.filter(Q(scope="permanent") | Q(scope="session", session_id=session_id))
    else:
        approvals = approvals.filter(scope="permanent")

    approval_map = {
        approval.tool_name: {"policy": approval.policy, "scope": approval.scope}
        for approval in approvals
    }

    tool_groups = []

    skill_builtin_tools = [
        {"tool_name": "read_skill_content", "description": "读取 Skill 的 SKILL.md 内容"},
        {"tool_name": "execute_skill_script", "description": "执行 Skill 脚本命令，支持单个或批量并发执行（需审批）"},
    ]
    tool_groups.append(
        {
            "group_name": "Skill 工具",
            "group_id": "builtin_skill",
            "tools": [
                {
                    "tool_name": item["tool_name"],
                    "description": item["description"],
                    "allowed_decisions": ["approve", "reject"],
                    "current_policy": approval_map.get(item["tool_name"], {}).get("policy", "ask_every_time"),
                    "current_scope": approval_map.get(item["tool_name"], {}).get("scope", "permanent"),
                }
                for item in skill_builtin_tools
            ],
        }
    )

    mcp_configs = RemoteMCPConfig.objects.filter(is_active=True).prefetch_related("tools")
    for config in mcp_configs:
        tools = []
        for tool in config.tools.all():
            tools.append(
                {
                    "tool_name": tool.name,
                    "description": tool.description or f"[{config.name}] {tool.name}",
                    "allowed_decisions": ["approve", "reject"],
                    "current_policy": approval_map.get(tool.name, {}).get("policy", "ask_every_time"),
                    "current_scope": approval_map.get(tool.name, {}).get("scope", "permanent"),
                    "require_hitl": tool.effective_require_hitl,
                }
            )
        if tools:
            tool_groups.append(
                {
                    "group_name": config.name,
                    "group_id": f"mcp_{config.id}",
                    "tools": tools,
                }
            )

    all_tools = [tool for group in tool_groups for tool in group["tools"]]
    return {
        "tools": all_tools,
        "tool_groups": tool_groups,
        "policy_choices": [
            {"value": "always_allow", "label": "始终允许"},
            {"value": "always_reject", "label": "始终拒绝"},
            {"value": "ask_every_time", "label": "每次询问"},
        ],
        "scope_choices": [
            {"value": "session", "label": "仅本次会话"},
            {"value": "permanent", "label": "永久生效"},
        ],
    }


def batch_update_tool_approvals(user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from langgraph_integration.models import UserToolApproval
    from langgraph_integration.serializers import UserToolApprovalBatchSerializer

    approvals_data = payload.get("approvals", [])
    if not approvals_data:
        raise AppError("请提供要更新的审批偏好", status_code=400)

    user = _actor(user_id)
    updated = []
    errors = []
    for item in approvals_data:
        serializer = UserToolApprovalBatchSerializer(data=item)
        if not serializer.is_valid():
            errors.append({"tool_name": item.get("tool_name", "unknown"), "errors": serializer.errors})
            continue
        data = serializer.validated_data
        if data.get("scope", "permanent") == "permanent":
            approval, created = UserToolApproval.objects.update_or_create(
                user=user,
                tool_name=data["tool_name"],
                scope="permanent",
                defaults={"policy": data["policy"], "session_id": None},
            )
        else:
            approval, created = UserToolApproval.objects.update_or_create(
                user=user,
                tool_name=data["tool_name"],
                scope="session",
                session_id=data.get("session_id"),
                defaults={"policy": data["policy"]},
            )
        updated.append(
            {
                "tool_name": approval.tool_name,
                "policy": approval.policy,
                "scope": approval.scope,
                "created": created,
            }
        )

    return {"updated": updated, "errors": errors or None}


def reset_tool_approvals(user_id: int, payload: dict | None = None) -> dict:
    ensure_django_setup()
    from langgraph_integration.models import UserToolApproval

    payload = payload or {}
    queryset = UserToolApproval.objects.filter(user=_actor(user_id))
    if payload.get("tool_name"):
        queryset = queryset.filter(tool_name=payload["tool_name"])
    if payload.get("scope"):
        queryset = queryset.filter(scope=payload["scope"])
    if payload.get("session_id"):
        queryset = queryset.filter(session_id=payload["session_id"])
    count = queryset.count()
    queryset.delete()
    return {"message": f"已重置 {count} 条审批偏好", "deleted_count": count}


def token_usage_stats(user_id: int, query: dict) -> dict:
    ensure_django_setup()
    from django.utils import timezone as tz
    from langgraph_integration.models import ChatSession

    actor = _actor(user_id)
    start_date_str = query.get("start_date")
    end_date_str = query.get("end_date")
    group_by = query.get("group_by", "day")
    target_user_id = query.get("user_id")

    if target_user_id and not actor.is_superuser:
        raise AppError("无权查看其他用户的统计信息", status_code=403)

    local_now = tz.localtime(tz.now())
    today = local_now.date()
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        if group_by == "day":
            start_date = today
        elif group_by == "week":
            start_date = today - timedelta(days=today.weekday())
        elif group_by == "month":
            start_date = today.replace(day=1)
        else:
            start_date = (local_now - timedelta(days=30)).date()

    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else today

    queryset = ChatSession.objects.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    personal_queryset = queryset.filter(user_id=target_user_id) if target_user_id else queryset.filter(user=actor)
    all_users_queryset = queryset

    trunc_func = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}.get(group_by, TruncDate)
    user_stats = (
        all_users_queryset.values("user__username", "user_id")
        .annotate(
            total_input=Sum("total_input_tokens"),
            total_output=Sum("total_output_tokens"),
            total_tokens=Sum("total_tokens"),
            total_requests=Sum("request_count"),
            session_count=Count("id"),
        )
        .order_by("-total_tokens")
    )
    time_stats = (
        personal_queryset.annotate(period=trunc_func("created_at"))
        .values("period")
        .annotate(
            total_input=Sum("total_input_tokens"),
            total_output=Sum("total_output_tokens"),
            total_tokens=Sum("total_tokens"),
            total_requests=Sum("request_count"),
            session_count=Count("id"),
        )
        .order_by("period")
    )
    total_stats = personal_queryset.aggregate(
        total_input=Sum("total_input_tokens"),
        total_output=Sum("total_output_tokens"),
        total_tokens=Sum("total_tokens"),
        total_requests=Sum("request_count"),
        session_count=Count("id"),
    )
    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "group_by": group_by,
        },
        "total": {
            "input_tokens": total_stats["total_input"] or 0,
            "output_tokens": total_stats["total_output"] or 0,
            "total_tokens": total_stats["total_tokens"] or 0,
            "request_count": total_stats["total_requests"] or 0,
            "session_count": total_stats["session_count"] or 0,
        },
        "by_user": [
            {
                "user_id": item["user_id"],
                "username": item["user__username"],
                "input_tokens": item["total_input"] or 0,
                "output_tokens": item["total_output"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "request_count": item["total_requests"] or 0,
                "session_count": item["session_count"] or 0,
            }
            for item in user_stats
        ],
        "by_time": [
            {
                "period": item["period"].isoformat() if item["period"] else None,
                "input_tokens": item["total_input"] or 0,
                "output_tokens": item["total_output"] or 0,
                "total_tokens": item["total_tokens"] or 0,
                "request_count": item["total_requests"] or 0,
                "session_count": item["session_count"] or 0,
            }
            for item in time_stats
        ],
    }


def list_chat_sessions(user_id: int, project_id: int | str) -> dict:
    ensure_django_setup()
    from flytest_django.checkpointer import check_history_exists, get_thread_ids_by_prefix
    from langgraph_integration.models import ChatSession

    project = _chat_project(user_id, project_id)
    user = _actor(user_id)

    django_sessions = (
        ChatSession.objects.filter(user=user, project_id=project.id)
        .order_by("-updated_at")
        .values("session_id", "title", "updated_at", "created_at")
    )

    sessions_list: list[dict] = []
    django_session_ids: set[str] = set()

    for item in django_sessions:
        session_id = str(item["session_id"])
        django_session_ids.add(session_id)
        sessions_list.append(
            {
                "id": session_id,
                "title": item["title"] or "New Chat",
                "updated_at": item["updated_at"].isoformat() if item["updated_at"] else None,
                "created_at": item["created_at"].isoformat() if item["created_at"] else None,
            }
        )

    if check_history_exists():
        try:
            thread_id_prefix = f"{user_id}_{project.id}_"
            thread_ids = get_thread_ids_by_prefix(thread_id_prefix)
            for thread_id in thread_ids:
                if not str(thread_id).startswith(thread_id_prefix):
                    continue
                session_id = str(thread_id)[len(thread_id_prefix) :]
                if session_id and session_id not in django_session_ids:
                    sessions_list.append(
                        {
                            "id": session_id,
                            "title": f"Session {session_id[:8]}...",
                            "updated_at": None,
                            "created_at": None,
                        }
                    )
        except Exception:  # noqa: BLE001
            # Match Django behavior: failure to inspect checkpoints should not break the session list endpoint.
            pass

    return {
        "user_id": str(user_id),
        "project_id": str(project.id),
        "project_name": project.name,
        "sessions": [item["id"] for item in sessions_list],
        "sessions_detail": sessions_list,
    }


def get_chat_history(user_id: int, session_id: str, project_id: int | str) -> dict:
    ensure_django_setup()
    from flytest_django.checkpointer import check_history_exists, get_sync_checkpointer
    from langgraph_integration.models import ChatSession

    if not session_id:
        raise AppError(
            "session_id query parameter is required.",
            status_code=400,
            errors={"session_id": ["This field is required."]},
        )

    project = _chat_project(user_id, project_id)
    user = _actor(user_id)

    prompt_id = None
    prompt_name = None
    try:
        chat_session = ChatSession.objects.select_related("prompt").get(
            session_id=session_id,
            user=user,
            project_id=project.id,
        )
        if chat_session.prompt:
            prompt_id = chat_session.prompt.id
            prompt_name = chat_session.prompt.name
    except ChatSession.DoesNotExist:
        pass

    thread_id = f"{user_id}_{project.id}_{session_id}"
    history_messages: list[dict] = []
    messages = []

    if check_history_exists():
        try:
            with get_sync_checkpointer() as memory:
                checkpoint_tuples = list(memory.list(config={"configurable": {"thread_id": thread_id}}))

            if checkpoint_tuples:
                message_timestamps: dict[int, str] = {}
                processed_message_count = 0

                for checkpoint_tuple in reversed(checkpoint_tuples):
                    checkpoint_data = getattr(checkpoint_tuple, "checkpoint", None)
                    if not checkpoint_data:
                        continue
                    checkpoint_messages = checkpoint_data.get("channel_values", {}).get("messages", [])
                    current_message_count = len(checkpoint_messages)
                    if current_message_count > processed_message_count:
                        checkpoint_timestamp = checkpoint_data.get("ts")
                        if checkpoint_timestamp:
                            for index in range(processed_message_count, current_message_count):
                                message_timestamps[index] = checkpoint_timestamp
                        processed_message_count = current_message_count

                latest_checkpoint = getattr(checkpoint_tuples[0], "checkpoint", None) or {}
                messages = latest_checkpoint.get("channel_values", {}).get("messages", [])

                for index, msg in enumerate(messages):
                    message_data = _serialize_history_message(msg)
                    if not message_data:
                        continue

                    timestamp = message_timestamps.get(index)
                    if timestamp:
                        message_data["timestamp"] = _format_history_timestamp(timestamp)
                    history_messages.append(message_data)
        except FileNotFoundError:
            history_messages = []
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                f"Error retrieving chat history: {exc}",
                status_code=500,
                errors={"history_retrieval": [str(exc)]},
            )

    context_token_count = 0
    context_limit = 128000
    try:
        active_config = _llm_queryset().filter(is_active=True).first()
        if active_config:
            context_limit = active_config.context_limit or 128000
        for msg in reversed(messages):
            usage_metadata = getattr(msg, "usage_metadata", None)
            if usage_metadata:
                context_token_count = usage_metadata.get("input_tokens", 0) + usage_metadata.get("output_tokens", 0)
                break
    except Exception:  # noqa: BLE001
        pass

    return {
        "thread_id": thread_id,
        "session_id": session_id,
        "project_id": str(project.id),
        "project_name": project.name,
        "prompt_id": prompt_id,
        "prompt_name": prompt_name,
        "history": history_messages,
        "context_token_count": context_token_count,
        "context_limit": context_limit,
    }


def delete_chat_history(user_id: int, session_id: str, project_id: int | str) -> dict:
    ensure_django_setup()
    from flytest_django.checkpointer import check_history_exists, delete_checkpoints_by_thread_id
    from langgraph_integration.models import ChatSession

    if not session_id:
        raise AppError(
            "session_id query parameter is required.",
            status_code=400,
            errors={"session_id": ["This field is required."]},
        )
    project = _chat_project(user_id, project_id)
    thread_id = f"{user_id}_{project.id}_{session_id}"

    if not check_history_exists():
        return {
            "thread_id": thread_id,
            "session_id": session_id,
            "deleted_count": 0,
            "session_deleted_count": 0,
        }

    deleted_count = delete_checkpoints_by_thread_id(thread_id)
    deleted_result = ChatSession.objects.filter(
        session_id=session_id,
        user_id=user_id,
        project=project,
    ).delete()
    return {
        "thread_id": thread_id,
        "session_id": session_id,
        "deleted_count": deleted_count,
        "session_deleted_count": deleted_result[0],
    }


def rollback_chat_history(user_id: int, session_id: str, project_id: int | str, keep_count: int) -> dict:
    ensure_django_setup()
    from flytest_django.checkpointer import check_history_exists, rollback_checkpoints_to_count

    if not session_id:
        raise AppError(
            "session_id query parameter is required.",
            status_code=400,
            errors={"session_id": ["This field is required."]},
        )
    if keep_count is None or not isinstance(keep_count, int) or keep_count < 0:
        raise AppError(
            "keep_count must be a non-negative integer.",
            status_code=400,
            errors={"keep_count": ["This field must be a non-negative integer."]},
        )

    project = _chat_project(user_id, project_id)
    thread_id = f"{user_id}_{project.id}_{session_id}"

    if not check_history_exists():
        return {
            "thread_id": thread_id,
            "session_id": session_id,
            "deleted_count": 0,
            "kept_count": keep_count,
        }

    deleted_count = rollback_checkpoints_to_count(thread_id, keep_count)
    return {
        "thread_id": thread_id,
        "session_id": session_id,
        "deleted_count": deleted_count,
        "kept_count": keep_count,
    }


def batch_delete_chat_history(user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from flytest_django.checkpointer import check_history_exists, delete_checkpoints_batch
    from langgraph_integration.models import ChatSession

    session_ids = payload.get("session_ids", [])
    project_id = payload.get("project_id")

    if not session_ids or not isinstance(session_ids, list):
        raise AppError(
            "session_ids must be a non-empty list.",
            status_code=400,
            errors={"session_ids": ["This field is required and must be a list."]},
        )
    if not project_id:
        raise AppError(
            "project_id is required.",
            status_code=400,
            errors={"project_id": ["This field is required."]},
        )

    project = _chat_project(user_id, project_id)
    if not check_history_exists():
        return {
            "deleted_count": 0,
            "processed_sessions": 0,
            "failed_sessions": [],
        }

    thread_ids = [f"{user_id}_{project.id}_{session_id}" for session_id in session_ids]
    total_deleted = delete_checkpoints_batch(thread_ids)
    failed_sessions: list[dict] = []

    for session_id in session_ids:
        try:
            ChatSession.objects.filter(
                session_id=session_id,
                user_id=user_id,
                project=project,
            ).delete()
        except Exception as exc:  # noqa: BLE001
            failed_sessions.append({"session_id": session_id, "reason": str(exc)})

    return {
        "deleted_count": total_deleted,
        "processed_sessions": len(session_ids),
        "failed_sessions": failed_sessions,
    }


def rag_query(user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from knowledge.langgraph_integration import KnowledgeRAGService
    from knowledge.models import KnowledgeBase
    from langgraph_integration.views import create_llm_instance

    query = str(payload.get("query") or "").strip()
    knowledge_base_id = payload.get("knowledge_base_id")
    project_id = payload.get("project_id")

    if not query:
        raise AppError("query is required", status_code=400)
    if not knowledge_base_id:
        raise AppError("knowledge_base_id is required", status_code=400)

    user = _actor(user_id)
    project = _project_for_rag(user_id, project_id)

    knowledge_base = KnowledgeBase.objects.select_related("project").filter(id=knowledge_base_id).first()
    if not knowledge_base:
        raise AppError("Knowledge base not found", status_code=404)
    if not user.is_superuser and not knowledge_base.project.members.filter(user=user).exists():
        raise AppError("You don't have permission to access this knowledge base.", status_code=403)

    active_config = _llm_queryset().filter(is_active=True).first()
    if not active_config:
        raise AppError("No active LLM configuration found", status_code=500)

    try:
        llm = create_llm_instance(active_config, temperature=0.7)
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"LLM configuration error: {exc}", status_code=500)

    result = KnowledgeRAGService(llm).query(
        question=query,
        knowledge_base_id=str(knowledge_base.id),
        user=user,
        project_id=str(project.id) if project else None,
    )

    return {
        "query": result["question"],
        "answer": result["answer"],
        "sources": result["context"],
        "retrieval_time": result["retrieval_time"],
        "generation_time": result["generation_time"],
        "total_time": result["total_time"],
    }


async def build_chat_response(user_id: int, payload: dict) -> tuple[dict, int]:
    ensure_django_setup()
    from langgraph_integration.views import ChatAPIView

    user = await sync_to_async(_actor)(user_id)
    request = type("FastAPICompatRequest", (), {"data": payload, "user": user})()
    response = await ChatAPIView().post(request)
    return dict(response.data), response.status_code


async def build_chat_resume_stream(user_id: int, payload: dict):
    ensure_django_setup()
    from langgraph_integration.views import ChatResumeAPIView, check_project_permission

    session_id = str(payload.get("session_id") or "").strip()
    project_id = payload.get("project_id")
    decision_type = str(payload.get("decision") or "approve")

    if not project_id:
        raise AppError("project_id is required", status_code=400)
    if not session_id:
        raise AppError("session_id is required", status_code=400)

    user = await sync_to_async(get_django_user)(user_id)
    if not user:
        raise AppError("User not found", status_code=404)

    project = await sync_to_async(check_project_permission)(user, project_id)
    if not project:
        raise AppError("Project access denied", status_code=403)

    thread_id = f"{user.id}_{project_id}_{session_id}"
    request = type("FastAPICompatRequest", (), {"user": user})()
    view = ChatResumeAPIView()
    return view._create_resume_generator(
        request,
        thread_id,
        decision_type,
        session_id,
        project_id,
    )


def _format_history_timestamp(timestamp_str: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:  # noqa: BLE001
        return timestamp_str


def _serialize_history_message(msg) -> dict | None:
    message_data: dict | None = None
    image_data = None
    step = None
    max_steps = None
    sse_event_type = None
    agent_info = None
    agent_type = None

    if isinstance(msg, SystemMessage):
        content = msg.content if hasattr(msg, "content") else str(msg)
        message_data = {"type": "system", "content": content}
    elif isinstance(msg, HumanMessage):
        raw_content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(raw_content, list):
            text_parts = []
            image_urls = []
            for item in raw_content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    image_url = item.get("image_url", {})
                    if isinstance(image_url, dict):
                        url = image_url.get("url", "")
                        if isinstance(url, str) and url.startswith("data:image/"):
                            image_urls.append(url)
            content = "".join(text_parts) if text_parts else "[Image message]"
            has_requirement_doc_images = isinstance(content, str) and (
                "docimg://" in content or "/api/requirements/documents/" in content
            )
            if image_urls and len(image_urls) == 1 and not has_requirement_doc_images:
                image_data = image_urls[0]
        else:
            content = raw_content
        if content and (not isinstance(content, str) or content.strip()):
            message_data = {"type": "human", "content": content}
            if image_data:
                message_data["image"] = image_data
    elif isinstance(msg, AIMessage):
        raw_content = msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(raw_content, list):
            text_parts = [
                item.get("text", "")
                for item in raw_content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            content = " ".join(text_parts) if text_parts else ""
        else:
            content = raw_content
        if not content or (isinstance(content, str) and not content.strip()):
            return None

        additional_kwargs = getattr(msg, "additional_kwargs", None) or {}
        agent_info = additional_kwargs.get("agent")
        agent_type = additional_kwargs.get("agent_type")
        metadata = additional_kwargs.get("metadata", {}) or {}
        if metadata:
            agent_info = agent_info or metadata.get("agent")
            agent_type = agent_type or metadata.get("agent_type")
            step = metadata.get("step")
            max_steps = metadata.get("max_steps")
            sse_event_type = metadata.get("sse_event_type")

        message_data = {"type": "ai", "content": content}
        if agent_info:
            message_data["agent"] = agent_info
        if agent_type:
            message_data["agent_type"] = agent_type
        if step is not None:
            message_data["step"] = step
        if max_steps is not None:
            message_data["max_steps"] = max_steps
        if sse_event_type:
            message_data["sse_event_type"] = sse_event_type
        if metadata.get("is_thinking_process"):
            message_data["is_thinking_process"] = True
    elif isinstance(msg, ToolMessage):
        content = msg.content if hasattr(msg, "content") else str(msg)
        additional_kwargs = getattr(msg, "additional_kwargs", None) or {}
        metadata = additional_kwargs.get("metadata", {}) or {}
        step = metadata.get("step")
        sse_event_type = metadata.get("sse_event_type")
        if content and (not isinstance(content, str) or content.strip()):
            message_data = {"type": "tool", "content": content}
            if step is not None:
                message_data["step"] = step
            if sse_event_type:
                message_data["sse_event_type"] = sse_event_type
    else:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content and (not isinstance(content, str) or content.strip()):
            message_data = {
                "type": "tool" if str(content).strip().startswith(("[", "{")) else "unknown",
                "content": content,
            }

    return message_data
