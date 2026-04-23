from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.testcase_templates.service import (
    create_template,
    delete_template,
    duplicate_template,
    get_field_options,
    get_template_detail,
    list_templates,
    parse_excel_headers,
    upload_template_file,
    update_template,
)


router = APIRouter(prefix="/testcase-templates", tags=["testcase-templates"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/")
def template_list(
    template_type: str | None = None,
    is_active: bool | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_templates(db=db, template_type=template_type, is_active=is_active))


@router.post("/", status_code=201)
def template_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_template(db=db, payload=payload, creator=user), code=201)


@router.post("/parse_headers/")
async def template_parse_headers(
    file: UploadFile = File(...),
    sheet_name: str = Form(""),
    header_row: int = Form(1),
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        await run_in_threadpool(
            parse_excel_headers,
            file_bytes=await file.read(),
            sheet_name=sheet_name,
            header_row=header_row,
        )
    )


@router.get("/field_options/")
def template_field_options(user=Depends(get_current_user)) -> dict:
    return success_response(get_field_options())


@router.get("/{template_id}/")
def template_detail(template_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_template_detail(db=db, template_id=template_id))


@router.patch("/{template_id}/")
def template_patch(template_id: int, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_template(db=db, template_id=template_id, payload=payload))


@router.delete("/{template_id}/")
def template_delete(template_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_template(db=db, template_id=template_id)
    return success_response(None)


@router.post("/{template_id}/duplicate/", status_code=201)
def template_duplicate(template_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(duplicate_template(db=db, template_id=template_id, creator=user), code=201)


@router.post("/{template_id}/upload-template-file/")
async def template_upload_file_route(
    template_id: int,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await run_in_threadpool(
        upload_template_file,
        db=db,
        template_id=template_id,
        filename=file.filename or "template.xlsx",
        file_bytes=await file.read(),
    )
