from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.api_keys.service import create_api_key, delete_api_key, get_api_key, list_api_keys, update_api_key
from app.services.auth.service import get_current_user_from_token


router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/")
def api_key_list(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_api_keys(db, user=user))


@router.post("/", status_code=201)
def api_key_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_api_key(db, user=user, payload=payload), message="API Key 创建成功", code=201)


@router.get("/{api_key_id}/")
def api_key_detail(api_key_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_api_key(db, user=user, api_key_id=api_key_id))


@router.patch("/{api_key_id}/")
def api_key_patch(api_key_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_api_key(db, user=user, api_key_id=api_key_id, payload=payload), message="API Key 更新成功")


@router.delete("/{api_key_id}/")
def api_key_delete(api_key_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_api_key(db, user=user, api_key_id=api_key_id)
    return success_response(None, message="API Key 删除成功")
