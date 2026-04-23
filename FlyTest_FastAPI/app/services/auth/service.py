from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.compat.django_bridge import check_password_with_django
from app.config import get_settings
from app.core.errors import AppError
from app.db.models.auth import User
from app.repositories.auth import AuthRepository
from app.schemas.auth import UserPublic


def serialize_user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        is_staff=bool(user.is_staff),
        is_active=bool(user.is_active),
        groups=[group.name for group in user.groups],
    )


def authenticate_user(db: Session, username: str, password: str) -> User:
    repo = AuthRepository(db)
    user = repo.get_user_by_username(username)
    if not user or not user.is_active:
        raise AppError("账号或密码错误", status_code=401)
    if not check_password_with_django(password, user.password):
        raise AppError("账号或密码错误", status_code=401)
    return user


def _encode_token(*, user_id: int, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload = {
        "token_type": token_type,
        "exp": int((now + expires_delta).timestamp()),
        "iat": int(now.timestamp()),
        "jti": uuid4().hex,
        "user_id": user_id,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def build_token_pair(user: User) -> dict:
    return {
        "refresh": _encode_token(user_id=user.id, token_type="refresh", expires_delta=timedelta(days=7)),
        "access": _encode_token(user_id=user.id, token_type="access", expires_delta=timedelta(hours=12)),
        "user": serialize_user_public(user).model_dump(),
    }


def refresh_access_token(refresh_token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise AppError("无效的刷新令牌", status_code=401, errors={"detail": str(exc)})
    if payload.get("token_type") != "refresh":
        raise AppError("无效的刷新令牌", status_code=401)
    user_id = int(payload.get("user_id") or 0)
    if not user_id:
        raise AppError("无效的刷新令牌", status_code=401)
    return {
        "access": _encode_token(user_id=user_id, token_type="access", expires_delta=timedelta(hours=12)),
    }


def get_current_user_from_token(db: Session, token: str) -> User:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise AppError("无效的访问令牌", status_code=401, errors={"detail": str(exc)})
    if payload.get("token_type") != "access":
        raise AppError("无效的访问令牌", status_code=401)
    user_id = int(payload.get("user_id") or 0)
    repo = AuthRepository(db)
    user = repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise AppError("用户不存在或已停用", status_code=401)
    return user
