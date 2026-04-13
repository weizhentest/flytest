from __future__ import annotations

import os
from typing import Any

import jwt
from fastapi import HTTPException, Request
from jwt import InvalidTokenError


PUBLIC_PATH_PREFIXES = (
    "/health",
    "/openapi.json",
    "/docs",
    "/redoc",
)


def auth_disabled() -> bool:
    return os.environ.get("APP_AUTOMATION_AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def is_public_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def should_skip_auth(request: Request) -> bool:
    return request.method.upper() == "OPTIONS" or is_public_path(request.url.path)


def get_jwt_secret() -> str:
    return (
        os.environ.get("APP_AUTOMATION_JWT_SECRET")
        or os.environ.get("DJANGO_SECRET_KEY")
        or ""
    ).strip()


def get_jwt_algorithm() -> str:
    return os.environ.get("APP_AUTOMATION_JWT_ALGORITHM", "HS256").strip() or "HS256"


def get_access_cookie_name() -> str:
    return os.environ.get("DJANGO_JWT_ACCESS_COOKIE_NAME", "flytest_access_token").strip() or "flytest_access_token"


def extract_bearer_token(request: Request) -> str:
    query_token = (request.query_params.get("token") or "").strip()
    if query_token:
        return query_token

    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return (request.cookies.get(get_access_cookie_name()) or "").strip()


def validate_request_token(request: Request) -> dict[str, Any]:
    if auth_disabled():
        return {"sub": "local-test", "username": "local-test"}

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="缺少访问令牌")

    secret = get_jwt_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="APP 自动化鉴权密钥未配置")

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[get_jwt_algorithm()],
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="访问令牌无效或已过期") from exc

    return payload if isinstance(payload, dict) else {}
