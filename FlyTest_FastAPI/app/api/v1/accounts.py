from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.errors import AppError
from app.core.responses import success_response
from app.services.accounts.service import (
    assign_permission_to_group,
    assign_permission_to_user,
    batch_assign_group_permissions,
    batch_assign_user_permissions,
    batch_remove_group_permissions,
    batch_remove_user_permissions,
    create_group,
    create_user_admin,
    delete_group,
    delete_user_detail,
    get_content_type_detail,
    get_current_user_detail,
    get_group_detail,
    get_permission_detail,
    get_user_detail,
    group_add_users,
    group_permissions,
    group_remove_users,
    list_content_types,
    list_groups,
    list_group_users,
    list_permissions,
    list_users,
    register_user,
    remove_permission_from_group,
    remove_permission_from_user,
    update_group,
    update_group_permissions,
    update_user_detail,
    update_user_permissions,
    user_permissions,
)
from app.services.auth.service import get_current_user_from_token
from app.core.auth import get_bearer_token


router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.post("/register/")
def accounts_register(payload: dict, db: Session = Depends(get_db)):
    return success_response(register_user(db, payload), code=201)


@router.get("/me/")
def accounts_me(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(get_current_user_detail(db=db, user=user))


@router.get("/users/")
def accounts_users(search: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(list_users(db=db, search=search))


@router.post("/users/")
def accounts_users_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(create_user_admin(db=db, payload=payload), code=201)


@router.get("/users/{user_id}/")
def accounts_user_detail(user_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(get_user_detail(db=db, actor=user, target_user_id=user_id))


@router.patch("/users/{user_id}/")
def accounts_user_patch(user_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_user_detail(db=db, actor=user, target_user_id=user_id, payload=payload))


@router.put("/users/{user_id}/")
def accounts_user_put(user_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_user_detail(db=db, actor=user, target_user_id=user_id, payload=payload))


@router.delete("/users/{user_id}/")
def accounts_user_delete(user_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    delete_user_detail(db=db, actor=user, target_user_id=user_id)
    return success_response(None)


@router.get("/users/{user_id}/permissions/")
def accounts_user_permissions(user_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(user_permissions(db=db, actor=user, target_user_id=user_id))


@router.post("/users/{user_id}/batch-assign-permissions/")
def accounts_user_batch_assign_permissions(user_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(batch_assign_user_permissions(db=db, actor=user, target_user_id=user_id, payload=payload))


@router.post("/users/{user_id}/batch-remove-permissions/")
def accounts_user_batch_remove_permissions(user_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(batch_remove_user_permissions(db=db, actor=user, target_user_id=user_id, payload=payload))


@router.put("/users/{user_id}/update-permissions/")
def accounts_user_update_permissions(user_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_user_permissions(db=db, actor=user, target_user_id=user_id, payload=payload))


@router.get("/groups/")
def accounts_groups(search: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(list_groups(db=db, search=search))


@router.post("/groups/")
def accounts_groups_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(create_group(db=db, payload=payload), code=201)


@router.get("/groups/{group_id}/")
def accounts_group_detail(group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(get_group_detail(db=db, group_id=group_id))


@router.patch("/groups/{group_id}/")
def accounts_group_patch(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_group(db=db, group_id=group_id, payload=payload))


@router.put("/groups/{group_id}/")
def accounts_group_put(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_group(db=db, group_id=group_id, payload=payload))


@router.delete("/groups/{group_id}/")
def accounts_group_delete(group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    delete_group(db=db, group_id=group_id)
    return success_response(None)


@router.get("/groups/{group_id}/users/")
def accounts_group_users(group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(list_group_users(db=db, group_id=group_id))


@router.post("/groups/{group_id}/add_users/")
def accounts_group_add_users(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(group_add_users(db=db, group_id=group_id, payload=payload))


@router.post("/groups/{group_id}/remove_users/")
def accounts_group_remove_users(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(group_remove_users(db=db, group_id=group_id, payload=payload))


@router.get("/groups/{group_id}/permissions/")
def accounts_group_permissions(group_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(group_permissions(db=db, group_id=group_id))


@router.post("/groups/{group_id}/batch-assign-permissions/")
def accounts_group_batch_assign_permissions(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(batch_assign_group_permissions(db=db, group_id=group_id, payload=payload))


@router.post("/groups/{group_id}/batch-remove-permissions/")
def accounts_group_batch_remove_permissions(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(batch_remove_group_permissions(db=db, group_id=group_id, payload=payload))


@router.put("/groups/{group_id}/update-permissions/")
def accounts_group_update_permissions(group_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(update_group_permissions(db=db, group_id=group_id, payload=payload))


@router.get("/permissions/")
def accounts_permissions(
    content_type: int | None = None,
    content_type__app_label: str | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(list_permissions(db=db, content_type=content_type, app_label=content_type__app_label, search=search))


@router.get("/permissions/{permission_id}/")
def accounts_permission_detail(permission_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(get_permission_detail(db=db, permission_id=permission_id))


@router.post("/permissions/{permission_id}/assign_to_user/")
def accounts_permission_assign_to_user(permission_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(assign_permission_to_user(db=db, actor=user, permission_id=permission_id, payload=payload))


@router.post("/permissions/{permission_id}/remove_from_user/")
def accounts_permission_remove_from_user(permission_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(remove_permission_from_user(db=db, actor=user, permission_id=permission_id, payload=payload))


@router.post("/permissions/{permission_id}/assign_to_group/")
def accounts_permission_assign_to_group(permission_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(assign_permission_to_group(db=db, permission_id=permission_id, payload=payload))


@router.post("/permissions/{permission_id}/remove_from_group/")
def accounts_permission_remove_from_group(permission_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(remove_permission_from_group(db=db, permission_id=permission_id, payload=payload))


@router.get("/content-types/")
def accounts_content_types(
    app_label: str | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response(list_content_types(db=db, app_label=app_label, search=search))


@router.get("/content-types/{content_type_id}/")
def accounts_content_type_detail(content_type_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(get_content_type_detail(db=db, content_type_id=content_type_id))
