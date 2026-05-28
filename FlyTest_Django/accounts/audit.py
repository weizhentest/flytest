import ipaddress
import logging
from typing import Any

from django.contrib.auth.models import AnonymousUser

from .models import UserOperationLog

logger = logging.getLogger(__name__)


def _normalize_ip(raw_ip: str | None) -> str | None:
    ip_value = (raw_ip or "").strip()
    if not ip_value:
        return None

    if ip_value.startswith("[") and "]" in ip_value:
        ip_value = ip_value[1 : ip_value.index("]")]
    elif ip_value.count(":") == 1 and "." in ip_value:
        ip_value = ip_value.rsplit(":", 1)[0]

    try:
        return str(ipaddress.ip_address(ip_value))
    except ValueError:
        return None


def get_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        for candidate in forwarded_for.split(","):
            ip_value = _normalize_ip(candidate)
            if ip_value:
                return ip_value

    return (
        _normalize_ip(request.META.get("HTTP_X_REAL_IP"))
        or _normalize_ip(request.META.get("REMOTE_ADDR"))
    )


def record_user_operation(
    *,
    user,
    action: str,
    label: str = "",
    request=None,
    path: str = "",
    method: str = "",
    metadata: dict[str, Any] | None = None,
) -> UserOperationLog | None:
    if not user or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
        return None

    try:
        request_path = request.get_full_path() if request is not None else ""
        request_method = request.method if request is not None else ""
        user_agent = request.META.get("HTTP_USER_AGENT", "") if request is not None else ""

        return UserOperationLog.objects.create(
            user=user,
            username_snapshot=getattr(user, "username", "") or "",
            action=action,
            label=(label or "")[:120],
            path=(path or request_path or "")[:500],
            method=(method or request_method or "")[:12],
            ip_address=get_client_ip(request) if request is not None else None,
            user_agent=user_agent,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("记录用户操作日志失败: user=%s action=%s", getattr(user, "id", None), action)
        return None
