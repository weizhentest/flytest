from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.testcases.service import (
    batch_delete_testcases,
    batch_delete_testcase_screenshots,
    cancel_execution,
    create_module,
    create_execution,
    create_suite,
    create_testcase,
    delete_execution,
    delete_module,
    delete_testcase_screenshot,
    delete_suite,
    delete_testcase,
    execution_report,
    export_testcases_excel,
    import_testcases_excel,
    get_execution,
    get_module,
    get_suite,
    get_testcase,
    list_execution_results,
    list_executions,
    list_modules,
    list_suites,
    list_testcase_screenshots,
    list_testcases,
    upload_testcase_screenshots,
    update_module,
    update_suite,
    update_testcase,
)


router = APIRouter(prefix="/projects/{project_id}", tags=["testcases"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/testcase-modules/")
def testcase_modules(project_id: int, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_modules(user_id=user.id, project_id=project_id, search=search))


@router.post("/testcase-modules/", status_code=201)
def testcase_module_create(project_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_module(user_id=user.id, project_id=project_id, payload=payload), code=201)


@router.get("/testcase-modules/{module_id}/")
def testcase_module_detail(project_id: int, module_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_module(user_id=user.id, project_id=project_id, module_id=module_id))


@router.put("/testcase-modules/{module_id}/")
def testcase_module_put(project_id: int, module_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_module(user_id=user.id, project_id=project_id, module_id=module_id, payload=payload))


@router.patch("/testcase-modules/{module_id}/")
def testcase_module_patch(project_id: int, module_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_module(user_id=user.id, project_id=project_id, module_id=module_id, payload=payload))


@router.delete("/testcase-modules/{module_id}/")
def testcase_module_delete(project_id: int, module_id: int, user=Depends(get_current_user)) -> dict:
    delete_module(user_id=user.id, project_id=project_id, module_id=module_id)
    return success_response(None)


@router.get("/testcases/")
def project_testcases(
    project_id: int,
    search: str | None = None,
    module_id: int | None = None,
    level: str | None = None,
    review_status: str | None = None,
    review_status_in: str | None = None,
    test_type: str | None = None,
    test_type_in: str | None = None,
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        list_testcases(
            user_id=user.id,
            project_id=project_id,
            search=search,
            module_id=module_id,
            level=level,
            review_status=review_status,
            review_status_in=review_status_in,
            test_type=test_type,
            test_type_in=test_type_in,
        )
    )


@router.post("/testcases/", status_code=201)
def project_testcase_create(project_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_testcase(user_id=user.id, project_id=project_id, payload=payload), code=201)


@router.get("/testcases/export-excel/")
async def project_testcases_export_excel_get(project_id: int, request: Request, user=Depends(get_current_user)):
    excel_bytes, filename = await run_in_threadpool(
        export_testcases_excel,
        user_id=user.id,
        project_id=project_id,
        method="GET",
        query_params=dict(request.query_params),
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/testcases/export-excel/")
async def project_testcases_export_excel_post(project_id: int, payload: dict, user=Depends(get_current_user)):
    excel_bytes, filename = await run_in_threadpool(
        export_testcases_excel,
        user_id=user.id,
        project_id=project_id,
        method="POST",
        payload=payload,
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/testcases/import-excel/")
async def project_testcases_import_excel(
    project_id: int,
    file: UploadFile = File(...),
    template_id: int = Form(...),
    user=Depends(get_current_user),
):
    result = await run_in_threadpool(
        import_testcases_excel,
        user_id=user.id,
        project_id=project_id,
        filename=file.filename or "import.xlsx",
        file_bytes=await file.read(),
        template_id=template_id,
    )
    return result


@router.post("/testcases/batch-delete/")
def project_testcases_batch_delete(project_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(batch_delete_testcases(user_id=user.id, project_id=project_id, ids=payload.get("ids", [])))


@router.get("/testcases/{testcase_id}/")
def project_testcase_detail(project_id: int, testcase_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_testcase(user_id=user.id, project_id=project_id, testcase_id=testcase_id))


@router.put("/testcases/{testcase_id}/")
def project_testcase_put(project_id: int, testcase_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_testcase(user_id=user.id, project_id=project_id, testcase_id=testcase_id, payload=payload))


@router.patch("/testcases/{testcase_id}/")
def project_testcase_patch(project_id: int, testcase_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_testcase(user_id=user.id, project_id=project_id, testcase_id=testcase_id, payload=payload))


@router.delete("/testcases/{testcase_id}/")
def project_testcase_delete(project_id: int, testcase_id: int, user=Depends(get_current_user)) -> dict:
    delete_testcase(user_id=user.id, project_id=project_id, testcase_id=testcase_id)
    return success_response(None)


@router.post("/testcases/{testcase_id}/upload-screenshots/", status_code=201)
async def project_testcase_upload_screenshots(
    project_id: int,
    testcase_id: int,
    screenshots: list[UploadFile] | None = File(default=None),
    screenshot: UploadFile | None = File(default=None),
    title: str | None = Form(default=""),
    description: str | None = Form(default=""),
    step_number: int | None = Form(default=None),
    mcp_session_id: str | None = Form(default=""),
    page_url: str | None = Form(default=""),
    user=Depends(get_current_user),
) -> dict:
    files = []
    for item in screenshots or []:
        files.append((item.filename or "screenshot.png", await item.read(), item.content_type or "image/png"))
    if screenshot is not None:
        files.append((screenshot.filename or "screenshot.png", await screenshot.read(), screenshot.content_type or "image/png"))
    result = await run_in_threadpool(
        upload_testcase_screenshots,
        user_id=user.id,
        project_id=project_id,
        testcase_id=testcase_id,
        files=files,
        title=title or "",
        description=description or "",
        step_number=step_number,
        mcp_session_id=mcp_session_id or "",
        page_url=page_url or "",
    )
    return success_response(
        result,
        code=201,
    )


@router.get("/testcases/{testcase_id}/screenshots/")
def project_testcase_screenshots(project_id: int, testcase_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(list_testcase_screenshots(user_id=user.id, project_id=project_id, testcase_id=testcase_id))


@router.delete("/testcases/{testcase_id}/screenshots/{screenshot_id}/")
def project_testcase_screenshot_delete(project_id: int, testcase_id: int, screenshot_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(
        delete_testcase_screenshot(
            user_id=user.id,
            project_id=project_id,
            testcase_id=testcase_id,
            screenshot_id=screenshot_id,
        )
    )


@router.post("/testcases/{testcase_id}/screenshots/batch-delete/")
def project_testcase_screenshots_batch_delete(project_id: int, testcase_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        batch_delete_testcase_screenshots(
            user_id=user.id,
            project_id=project_id,
            testcase_id=testcase_id,
            ids=payload.get("ids", []),
        )
    )


@router.get("/test-suites/")
def project_test_suites(project_id: int, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_suites(user_id=user.id, project_id=project_id, search=search))


@router.post("/test-suites/", status_code=201)
def project_test_suite_create(project_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_suite(user_id=user.id, project_id=project_id, payload=payload), code=201)


@router.get("/test-suites/{suite_id}/")
def project_test_suite_detail(project_id: int, suite_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_suite(user_id=user.id, project_id=project_id, suite_id=suite_id))


@router.put("/test-suites/{suite_id}/")
def project_test_suite_put(project_id: int, suite_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_suite(user_id=user.id, project_id=project_id, suite_id=suite_id, payload=payload))


@router.patch("/test-suites/{suite_id}/")
def project_test_suite_patch(project_id: int, suite_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_suite(user_id=user.id, project_id=project_id, suite_id=suite_id, payload=payload))


@router.delete("/test-suites/{suite_id}/")
def project_test_suite_delete(project_id: int, suite_id: int, user=Depends(get_current_user)) -> dict:
    delete_suite(user_id=user.id, project_id=project_id, suite_id=suite_id)
    return success_response(None)


@router.get("/test-executions/")
def project_test_executions(
    project_id: int,
    search: str | None = None,
    ordering: str | None = None,
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_executions(user_id=user.id, project_id=project_id, search=search, ordering=ordering))


@router.post("/test-executions/", status_code=201)
def project_test_execution_create(project_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_execution(user_id=user.id, project_id=project_id, payload=payload), code=201)


@router.get("/test-executions/{execution_id}/")
def project_test_execution_detail(project_id: int, execution_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_execution(user_id=user.id, project_id=project_id, execution_id=execution_id))


@router.post("/test-executions/{execution_id}/cancel/")
def project_test_execution_cancel(project_id: int, execution_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(cancel_execution(user_id=user.id, project_id=project_id, execution_id=execution_id))


@router.get("/test-executions/{execution_id}/results/")
def project_test_execution_results(project_id: int, execution_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(list_execution_results(user_id=user.id, project_id=project_id, execution_id=execution_id))


@router.get("/test-executions/{execution_id}/report/")
def project_test_execution_report(project_id: int, execution_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(execution_report(user_id=user.id, project_id=project_id, execution_id=execution_id))


@router.delete("/test-executions/{execution_id}/")
def project_test_execution_delete(project_id: int, execution_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(delete_execution(user_id=user.id, project_id=project_id, execution_id=execution_id))
