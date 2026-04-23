from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.errors import AppError
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.skills.service import (
    delete_skill,
    get_skill_content,
    get_skill_detail,
    import_skill_from_git,
    list_skills,
    toggle_skill,
    upload_skill,
)


router = APIRouter(prefix="/projects/{project_id}/skills", tags=["skills"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/")
def skill_list(project_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_skills(db=db, project_id=project_id), message="鑾峰彇鎴愬姛", code=200)


@router.get("/{skill_id}/")
def skill_detail(project_id: int, skill_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(
        get_skill_detail(db=db, project_id=project_id, skill_id=skill_id),
        message="鑾峰彇鎴愬姛",
        code=200,
    )


@router.patch("/{skill_id}/")
def skill_patch(project_id: int, skill_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "is_active" not in payload:
        raise AppError("缂哄皯 is_active 瀛楁", status_code=400)
    return success_response(
        toggle_skill(db=db, project_id=project_id, skill_id=skill_id, is_active=bool(payload.get("is_active"))),
        message="鏇存柊鎴愬姛",
        code=200,
    )


@router.delete("/{skill_id}/")
def skill_delete(project_id: int, skill_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    name = delete_skill(db=db, project_id=project_id, skill_id=skill_id)
    return success_response(None, message=f"Skill '{name}' 宸插垹闄?", code=200)


@router.post("/upload/", status_code=201)
async def skill_upload(project_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    payload = await run_in_threadpool(
        upload_skill,
        db=db,
        project_id=project_id,
        creator=user,
        filename=file.filename or "",
        content=await file.read(),
    )
    return success_response(payload, message=f"Skill '{payload['name']}' 涓婁紶鎴愬姛", code=201)


@router.post("/import-git/", status_code=201)
def skill_import_git(
    project_id: int,
    git_url: str = Form(...),
    branch: str = Form("main"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = import_skill_from_git(db=db, project_id=project_id, creator=user, git_url=git_url, branch=branch)
    return success_response(payload, message=f"鎴愬姛瀵煎叆 {len(payload)} 涓?Skill", code=201)


@router.get("/{skill_id}/content/")
def skill_content(project_id: int, skill_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(
        get_skill_content(db=db, project_id=project_id, skill_id=skill_id),
        message="鑾峰彇鎴愬姛",
        code=200,
    )
