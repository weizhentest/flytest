from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.projects.service import (
    add_project_member,
    create_project,
    delete_project,
    get_project_detail,
    get_project_statistics,
    list_project_members,
    list_projects,
    remove_project_member,
    update_project,
    update_project_member_role,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/")
def project_list(
    search: str | None = Query(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_projects(db, user=user, search=search))


@router.post("/", status_code=201)
def project_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_project(db, user=user, payload=payload), message="项目创建成功", code=201)


@router.get("/{project_id}/")
def project_detail(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_project_detail(db, user=user, project_id=project_id))


@router.patch("/{project_id}/")
def project_patch(project_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_project(db, user=user, project_id=project_id, payload=payload), message="项目更新成功")


@router.delete("/{project_id}/")
def project_delete(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_project(db, user=user, project_id=project_id)
    return success_response(None, message="项目删除成功")


@router.get("/{project_id}/members/")
def project_members(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_project_members(db, user=user, project_id=project_id))


@router.get("/{project_id}/statistics/")
def project_statistics(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_project_statistics(db=db, user=user, project_id=project_id))


@router.post("/{project_id}/add_member/", status_code=201)
def project_add_member(project_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(
        add_project_member(db, user=user, project_id=project_id, payload=payload),
        message="成员添加成功",
        code=201,
    )


@router.delete("/{project_id}/remove_member/")
def project_remove_member(project_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    remove_project_member(db, user=user, project_id=project_id, target_user_id=int(payload.get("user_id") or 0))
    return success_response({"message": "成员已成功移除"}, message="成员已成功移除")


@router.patch("/{project_id}/update_member_role/")
def project_update_member_role(project_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(
        update_project_member_role(db, user=user, project_id=project_id, payload=payload),
        message="成员角色更新成功",
    )
