from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.prompts.service import (
    clear_default_prompt,
    create_prompt,
    delete_prompt,
    duplicate_prompt,
    get_init_status,
    get_prompt,
    get_prompt_types,
    initialize_prompts,
    list_prompts,
    serialize_prompt,
    set_default_prompt,
    update_prompt,
)


router = APIRouter(prefix="/prompts/user-prompts", tags=["prompts"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/")
def prompt_list(
    search: str | None = Query(default=None),
    is_default: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    prompt_type: str | None = Query(default=None),
    ordering: str | None = Query(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        list_prompts(
            db,
            user=user,
            search=search,
            is_default=is_default,
            is_active=is_active,
            prompt_type=prompt_type,
            ordering=ordering,
        )
    )


@router.post("/", status_code=201)
def prompt_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = create_prompt(db, user=user, payload=payload)
    return success_response(serialize_prompt(prompt), message="User prompt created successfully", code=201)


@router.get("/default/")
def prompt_default(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    from app.repositories.prompts import PromptRepository

    prompt = PromptRepository(db).get_default(user_id=user.id)
    return success_response(serialize_prompt(prompt) if prompt else None)


@router.get("/by_type/")
def prompt_by_type(type: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    from app.repositories.prompts import PromptRepository

    prompt = PromptRepository(db).get_by_type(user_id=user.id, prompt_type=type)
    return success_response(serialize_prompt(prompt) if prompt else None)


@router.get("/types/")
def prompt_types() -> dict:
    return success_response(get_prompt_types())


@router.post("/clear_default/")
def prompt_clear_default(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(clear_default_prompt(db, user=user), message="Default prompt cleared successfully")


@router.post("/initialize/")
def prompt_initialize(payload: dict | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    result = initialize_prompts(db, user=user, force_update=bool((payload or {}).get("force_update", False)))
    return success_response(result, message="初始化完成")


@router.get("/init_status/")
def prompt_init_status(user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_init_status(db, user=user), message="获取状态成功")


@router.get("/{prompt_id}/")
def prompt_detail(prompt_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = get_prompt(db, user=user, prompt_id=prompt_id)
    return success_response(serialize_prompt(prompt))


@router.put("/{prompt_id}/")
def prompt_put(prompt_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = update_prompt(db, user=user, prompt_id=prompt_id, payload=payload)
    return success_response(serialize_prompt(prompt), message="User prompt updated successfully")


@router.patch("/{prompt_id}/")
def prompt_patch(prompt_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = update_prompt(db, user=user, prompt_id=prompt_id, payload=payload)
    return success_response(serialize_prompt(prompt), message="User prompt updated successfully")


@router.delete("/{prompt_id}/")
def prompt_delete(prompt_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_prompt(db, user=user, prompt_id=prompt_id)
    return success_response(None, message="User prompt deleted successfully")


@router.post("/{prompt_id}/set_default/")
def prompt_set_default(prompt_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = set_default_prompt(db, user=user, prompt_id=prompt_id)
    return success_response(serialize_prompt(prompt), message="默认提示词设置成功")


@router.post("/{prompt_id}/duplicate/", status_code=201)
def prompt_duplicate(prompt_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    prompt = duplicate_prompt(db, user=user, prompt_id=prompt_id)
    return success_response(serialize_prompt(prompt), message="提示词复制成功", code=201)
