from fastapi import Header

from app.core.errors import AppError


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise AppError("缺少认证信息", status_code=401)
    prefix, _, token = authorization.partition(" ")
    if prefix.lower() != "bearer" or not token:
        raise AppError("无效的认证头", status_code=401)
    return token
