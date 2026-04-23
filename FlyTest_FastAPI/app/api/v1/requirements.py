from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.requirements.service import (
    adjust_modules,
    analyze_document_structure,
    check_context_limit,
    confirm_modules,
    create_document,
    create_issue,
    create_module,
    create_module_result,
    create_report,
    delete_document,
    delete_issue,
    delete_module,
    delete_module_result,
    delete_report,
    get_document,
    get_document_image,
    get_issue,
    get_module,
    get_module_result,
    get_report,
    list_document_images,
    list_documents,
    list_issues,
    list_module_results,
    list_modules,
    list_reports,
    module_operations,
    restart_review,
    review_progress,
    split_modules,
    start_review,
    update_document,
    update_issue,
    update_module,
    update_module_result,
    update_report,
)


router = APIRouter(prefix="/requirements", tags=["requirements"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/documents/")
def requirement_documents(
    project: int | str | None = None,
    status: str | None = None,
    document_type: str | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_documents(db=db, user=user, project=project, status=status, document_type=document_type, search=search))


@router.post("/documents/", status_code=201)
async def requirement_document_create(
    project: str = Form(...),
    title: str = Form(...),
    description: str | None = Form(default=None),
    document_type: str = Form(...),
    file: UploadFile | None = File(default=None),
    content: str | None = Form(default=None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = {
        "project": project,
        "title": title,
        "description": description,
        "document_type": document_type,
        "content": content,
    }
    if file is not None:
        payload["file"] = file.file
        if not getattr(file.file, "name", None):
            file.file.name = file.filename or "upload.bin"
    return success_response(await run_in_threadpool(create_document, db=db, user=user, payload=payload), code=201)


@router.get("/documents/{document_id}/images/{image_id}/")
def requirement_document_image(document_id: str, image_id: str):
    image = get_document_image(document_id=document_id, image_id=image_id)
    return FileResponse(path=image.image_file.path, media_type=image.content_type)


@router.get("/documents/{document_id}/images-list/")
def requirement_document_images_list(document_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(list_document_images(user_id=user.id, document_id=document_id))


@router.post("/documents/{document_id}/split-modules/")
def requirement_document_split_modules(document_id: str, payload: dict | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(split_modules(user_id=user.id, document_id=document_id, payload=payload or {}))


@router.get("/documents/{document_id}/check-context-limit/")
def requirement_document_check_context(document_id: str, model: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(check_context_limit(user_id=user.id, document_id=document_id, model_name=model))


@router.get("/documents/{document_id}/analyze-structure/")
def requirement_document_analyze_structure(document_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(analyze_document_structure(user_id=user.id, document_id=document_id))


@router.post("/documents/{document_id}/confirm-modules/")
def requirement_document_confirm_modules(document_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(confirm_modules(user_id=user.id, document_id=document_id))


@router.put("/documents/{document_id}/adjust-modules/")
def requirement_document_adjust_modules(document_id: str, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(adjust_modules(user_id=user.id, document_id=document_id, payload=payload))


@router.post("/documents/{document_id}/module-operations/")
def requirement_document_module_operations(document_id: str, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(module_operations(user_id=user.id, document_id=document_id, payload=payload))


@router.post("/documents/{document_id}/start-review/")
def requirement_document_start_review(document_id: str, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(start_review(user_id=user.id, document_id=document_id, payload=payload))


@router.post("/documents/{document_id}/restart-review/")
def requirement_document_restart_review(document_id: str, payload: dict | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(restart_review(user_id=user.id, document_id=document_id, payload=payload or {}))


@router.get("/documents/{document_id}/review-progress/")
def requirement_document_review_progress(document_id: str, user=Depends(get_current_user)) -> dict:
    return success_response(review_progress(user_id=user.id, document_id=document_id))


@router.get("/documents/{document_id}/")
def requirement_document_detail(document_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_document(db=db, user=user, document_id=document_id))


@router.put("/documents/{document_id}/")
def requirement_document_put(document_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_document(db=db, user=user, document_id=document_id, payload=payload))


@router.patch("/documents/{document_id}/")
def requirement_document_patch(document_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_document(db=db, user=user, document_id=document_id, payload=payload))


@router.delete("/documents/{document_id}/")
def requirement_document_delete(document_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_document(db=db, user=user, document_id=document_id)
    return success_response(None)


@router.get("/modules/")
def requirement_modules(document: str | None = None, search: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_modules(db=db, user=user, document=document, search=search))


@router.post("/modules/", status_code=201)
def requirement_module_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_module(db=db, user=user, payload=payload), code=201)


@router.get("/modules/{module_id}/")
def requirement_module_detail(module_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_module(db=db, user=user, module_id=module_id))


@router.put("/modules/{module_id}/")
def requirement_module_put(module_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_module(db=db, user=user, module_id=module_id, payload=payload))


@router.patch("/modules/{module_id}/")
def requirement_module_patch(module_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_module(db=db, user=user, module_id=module_id, payload=payload))


@router.delete("/modules/{module_id}/")
def requirement_module_delete(module_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_module(db=db, user=user, module_id=module_id)
    return success_response(None)


@router.get("/reports/")
def requirement_reports(
    document: str | None = None,
    status: str | None = None,
    overall_rating: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_reports(db=db, user=user, document=document, status=status, overall_rating=overall_rating))


@router.post("/reports/", status_code=201)
def requirement_report_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_report(db=db, user=user, payload=payload), code=201)


@router.get("/reports/{report_id}/")
def requirement_report_detail(report_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_report(db=db, user=user, report_id=report_id))


@router.put("/reports/{report_id}/")
def requirement_report_put(report_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_report(db=db, user=user, report_id=report_id, payload=payload))


@router.patch("/reports/{report_id}/")
def requirement_report_patch(report_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_report(db=db, user=user, report_id=report_id, payload=payload))


@router.delete("/reports/{report_id}/")
def requirement_report_delete(report_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_report(db=db, user=user, report_id=report_id)
    return success_response(None)


@router.get("/issues/")
def requirement_issues(
    report: str | None = None,
    module: str | None = None,
    issue_type: str | None = None,
    priority: str | None = None,
    is_resolved: bool | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(list_issues(db=db, user=user, report=report, module=module, issue_type=issue_type, priority=priority, is_resolved=is_resolved))


@router.post("/issues/", status_code=201)
def requirement_issue_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_issue(db=db, user=user, payload=payload), code=201)


@router.get("/issues/{issue_id}/")
def requirement_issue_detail(issue_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_issue(db=db, user=user, issue_id=issue_id))


@router.put("/issues/{issue_id}/")
def requirement_issue_put(issue_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_issue(db=db, user=user, issue_id=issue_id, payload=payload))


@router.patch("/issues/{issue_id}/")
def requirement_issue_patch(issue_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_issue(db=db, user=user, issue_id=issue_id, payload=payload))


@router.delete("/issues/{issue_id}/")
def requirement_issue_delete(issue_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_issue(db=db, user=user, issue_id=issue_id)
    return success_response(None)


@router.get("/module-results/")
def requirement_module_results(report: str | None = None, module: str | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(list_module_results(db=db, user=user, report=report, module=module))


@router.post("/module-results/", status_code=201)
def requirement_module_result_create(payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(create_module_result(db=db, user=user, payload=payload), code=201)


@router.get("/module-results/{result_id}/")
def requirement_module_result_detail(result_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(get_module_result(db=db, user=user, result_id=result_id))


@router.put("/module-results/{result_id}/")
def requirement_module_result_put(result_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_module_result(db=db, user=user, result_id=result_id, payload=payload))


@router.patch("/module-results/{result_id}/")
def requirement_module_result_patch(result_id: str, payload: dict, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return success_response(update_module_result(db=db, user=user, result_id=result_id, payload=payload))


@router.delete("/module-results/{result_id}/")
def requirement_module_result_delete(result_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    delete_module_result(db=db, user=user, result_id=result_id)
    return success_response(None)
