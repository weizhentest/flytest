from datetime import datetime
import secrets

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.api_keys import APIKey
from app.db.models.auth import User
from app.repositories.api_keys import APIKeyRepository


def _serialize_api_key(item: APIKey) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "key": item.key,
        "user": item.user.username if item.user else "",
        "created_at": item.created_at.isoformat() if item.created_at else "",
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "is_active": bool(item.is_active),
    }


def list_api_keys(db: Session, *, user: User) -> list[dict]:
    return [_serialize_api_key(item) for item in APIKeyRepository(db).list_keys(user=user)]


def get_api_key(db: Session, *, user: User, api_key_id: int) -> dict:
    api_key = APIKeyRepository(db).get_key(user=user, api_key_id=api_key_id)
    if not api_key:
        raise AppError("API Key 不存在", status_code=404)
    return _serialize_api_key(api_key)


def create_api_key(db: Session, *, user: User, payload: dict) -> dict:
    repo = APIKeyRepository(db)
    name = str(payload.get("name") or "").strip()
    if not name:
        raise AppError("Key Name 不能为空", status_code=400, errors={"name": ["Key Name 不能为空"]})
    existing = repo.get_by_name(name=name)
    if existing:
        raise AppError("Key Name 已存在", status_code=400, errors={"name": ["Key Name 已存在"]})
    api_key = APIKey(
        name=name,
        key=secrets.token_urlsafe(32),
        user_id=user.id,
        created_at=datetime.now(),
        expires_at=None,
        is_active=bool(payload.get("is_active", True)),
    )
    repo.create(api_key)
    db.commit()
    db.refresh(api_key)
    return _serialize_api_key(api_key)


def update_api_key(db: Session, *, user: User, api_key_id: int, payload: dict) -> dict:
    repo = APIKeyRepository(db)
    api_key = repo.get_key(user=user, api_key_id=api_key_id)
    if not api_key:
        raise AppError("API Key 不存在", status_code=404)
    if "name" in payload and payload.get("name") is not None:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise AppError("Key Name 不能为空", status_code=400, errors={"name": ["Key Name 不能为空"]})
        existing = repo.get_by_name(name=name)
        if existing and existing.id != api_key.id:
            raise AppError("Key Name 已存在", status_code=400, errors={"name": ["Key Name 已存在"]})
        api_key.name = name
    if "is_active" in payload and payload.get("is_active") is not None:
        api_key.is_active = bool(payload.get("is_active"))
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return _serialize_api_key(api_key)


def delete_api_key(db: Session, *, user: User, api_key_id: int) -> None:
    repo = APIKeyRepository(db)
    api_key = repo.get_key(user=user, api_key_id=api_key_id)
    if not api_key:
        raise AppError("API Key 不存在", status_code=404)
    repo.delete(api_key)
    db.commit()
