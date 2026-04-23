from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.api_automation.service import (
    apply_case_generation_job,
    analyze_execution_record_failure,
    cancel_case_generation_job,
    cancel_import_job,
    create_case_generation_job,
    collection_tree,
    create_collection,
    create_environment,
    create_request,
    create_test_case,
    delete_collection,
    delete_environment,
    delete_request,
    delete_test_case,
    execute_request,
    execute_request_batch,
    execute_test_case,
    execute_test_case_batch,
    get_case_generation_job,
    get_execution_record,
    get_execution_report,
    get_execution_report_summary,
    get_import_job,
    get_test_case,
    import_document,
    list_case_generation_jobs,
    list_collections,
    list_environments,
    list_execution_records,
    list_import_jobs,
    list_requests,
    list_test_cases,
    generate_test_cases_legacy,
    update_collection,
    update_environment,
    update_request,
    update_test_case,
)
from app.services.auth.service import get_current_user_from_token


router = APIRouter(prefix="/api-automation", tags=["api-automation"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.get("/collections/")
def api_collection_list(
    project: int | None = Query(default=None),
    parent: int | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_collections(user_id=user.id, project_id=project, parent_id=parent))


@router.get("/collections/tree/")
def api_collection_tree(project: int, user=Depends(get_current_user)) -> dict:
    return success_response(collection_tree(user_id=user.id, project_id=project))


@router.post("/collections/", status_code=201)
def api_collection_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_collection(user_id=user.id, payload=payload), code=201)


@router.patch("/collections/{collection_id}/")
def api_collection_patch(collection_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_collection(user_id=user.id, collection_id=collection_id, payload=payload))


@router.delete("/collections/{collection_id}/")
def api_collection_delete(collection_id: int, user=Depends(get_current_user)) -> dict:
    delete_collection(user_id=user.id, collection_id=collection_id)
    return success_response(None)


@router.get("/environments/")
def api_environment_list(project: int | None = Query(default=None), user=Depends(get_current_user)) -> dict:
    return success_response(list_environments(user_id=user.id, project_id=project))


@router.post("/environments/", status_code=201)
def api_environment_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_environment(user_id=user.id, payload=payload), code=201)


@router.patch("/environments/{environment_id}/")
def api_environment_patch(environment_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_environment(user_id=user.id, environment_id=environment_id, payload=payload))


@router.delete("/environments/{environment_id}/")
def api_environment_delete(environment_id: int, user=Depends(get_current_user)) -> dict:
    delete_environment(user_id=user.id, environment_id=environment_id)
    return success_response(None)


@router.get("/requests/")
def api_request_list(
    project: int | None = Query(default=None),
    collection: int | None = Query(default=None),
    method: str | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_requests(user_id=user.id, project_id=project, collection_id=collection, method=method))


@router.post("/requests/", status_code=201)
def api_request_create(payload: dict, user=Depends(get_current_user)) -> dict:
    result = create_request(user_id=user.id, payload=payload)
    return success_response(result, code=201)


@router.patch("/requests/{request_id}/")
def api_request_patch(request_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_request(user_id=user.id, request_id=request_id, payload=payload))


@router.delete("/requests/{request_id}/")
def api_request_delete(request_id: int, user=Depends(get_current_user)) -> dict:
    delete_request(user_id=user.id, request_id=request_id)
    return success_response(None)


@router.post("/requests/import-document/")
async def api_request_import_document(
    response: Response,
    collection_id: int = Form(...),
    file: UploadFile = File(...),
    generate_test_cases: bool = Form(True),
    enable_ai_parse: bool = Form(True),
    async_mode: bool = Form(True),
    user=Depends(get_current_user),
) -> dict:
    payload, status_code = await run_in_threadpool(
        import_document,
        user_id=user.id,
        collection_id=collection_id,
        filename=file.filename or "",
        file_bytes=await file.read(),
        generate_test_cases=generate_test_cases,
        enable_ai_parse=enable_ai_parse,
        async_mode=async_mode,
    )
    response.status_code = status_code
    return success_response(payload, code=status_code)


@router.post("/requests/{request_id}/execute/")
def api_request_execute(request_id: int, payload: dict | None = None, user=Depends(get_current_user)) -> dict:
    payload = payload or {}
    return success_response(
        execute_request(
            user_id=user.id,
            request_id=request_id,
            environment_id=payload.get("environment_id"),
            execution_mode=str(payload.get("execution_mode") or "sync"),
        )
    )


@router.post("/requests/execute-batch/")
def api_request_execute_batch(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        execute_request_batch(
            user_id=user.id,
            scope=str(payload.get("scope") or "selected"),
            ids=payload.get("ids") or [],
            project_id=payload.get("project_id"),
            collection_id=payload.get("collection_id"),
            environment_id=payload.get("environment_id"),
            execution_mode=str(payload.get("execution_mode") or "sync"),
        )
    )


@router.post("/requests/generate-test-cases/")
def api_request_generate_test_cases(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(generate_test_cases_legacy(user_id=user.id, payload=payload))


@router.get("/execution-records/")
def api_execution_record_list(
    project: int | None = Query(default=None),
    request: int | None = Query(default=None),
    collection: int | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        list_execution_records(
            user_id=user.id,
            project_id=project,
            request_id=request,
            collection_id=collection,
        )
    )


@router.get("/execution-records/report/")
def api_execution_report(
    project: int | None = Query(default=None),
    request: int | None = Query(default=None),
    collection: int | None = Query(default=None),
    days: int | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        get_execution_report(
            user_id=user.id,
            project_id=project,
            request_id=request,
            collection_id=collection,
            days=days,
        )
    )


@router.post("/execution-records/report-summary/")
def api_execution_report_summary(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        get_execution_report_summary(
            user_id=user.id,
            project_id=payload.get("project"),
            request_id=payload.get("request"),
            collection_id=payload.get("collection"),
            days=payload.get("days"),
        )
    )


@router.get("/execution-records/{record_id}/")
def api_execution_record_detail(record_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_execution_record(user_id=user.id, record_id=record_id))


@router.post("/execution-records/{record_id}/analyze-failure/")
def api_execution_record_analyze_failure(record_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(analyze_execution_record_failure(user_id=user.id, record_id=record_id))


@router.get("/test-cases/")
def api_test_case_list(
    project: int | None = Query(default=None),
    request: int | None = Query(default=None),
    collection: int | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(
        list_test_cases(
            user_id=user.id,
            project_id=project,
            request_id=request,
            collection_id=collection,
        )
    )


@router.post("/test-cases/", status_code=201)
def api_test_case_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_test_case(user_id=user.id, payload=payload), code=201)


@router.get("/test-cases/{test_case_id}/")
def api_test_case_detail(test_case_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_test_case(user_id=user.id, test_case_id=test_case_id))


@router.patch("/test-cases/{test_case_id}/")
def api_test_case_patch(test_case_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_test_case(user_id=user.id, test_case_id=test_case_id, payload=payload))


@router.delete("/test-cases/{test_case_id}/")
def api_test_case_delete(test_case_id: int, user=Depends(get_current_user)) -> dict:
    delete_test_case(user_id=user.id, test_case_id=test_case_id)
    return success_response(None)


@router.post("/test-cases/{test_case_id}/execute/")
def api_test_case_execute(test_case_id: int, payload: dict | None = None, user=Depends(get_current_user)) -> dict:
    payload = payload or {}
    return success_response(
        execute_test_case(
            user_id=user.id,
            test_case_id=test_case_id,
            environment_id=payload.get("environment_id"),
            execution_mode=str(payload.get("execution_mode") or "sync"),
        )
    )


@router.post("/test-cases/execute-batch/")
def api_test_case_execute_batch(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        execute_test_case_batch(
            user_id=user.id,
            scope=str(payload.get("scope") or "selected"),
            ids=payload.get("ids") or [],
            project_id=payload.get("project_id"),
            collection_id=payload.get("collection_id"),
            environment_id=payload.get("environment_id"),
            execution_mode=str(payload.get("execution_mode") or "sync"),
        )
    )


@router.get("/import-jobs/")
def api_import_job_list(
    project: int | None = Query(default=None),
    status: str | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_import_jobs(user_id=user.id, project_id=project, status_value=status))


@router.get("/import-jobs/{job_id}/")
def api_import_job_detail(job_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_import_job(user_id=user.id, job_id=job_id))


@router.post("/import-jobs/{job_id}/cancel/")
def api_import_job_cancel(job_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(cancel_import_job(user_id=user.id, job_id=job_id))


@router.get("/case-generation-jobs/")
def api_case_generation_job_list(
    project: int | None = Query(default=None),
    status: str | None = Query(default=None),
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_case_generation_jobs(user_id=user.id, project_id=project, status_value=status))


@router.get("/case-generation-jobs/{job_id}/")
def api_case_generation_job_detail(job_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_case_generation_job(user_id=user.id, job_id=job_id))


@router.post("/case-generation-jobs/")
def api_case_generation_job_create(payload: dict, response: Response, user=Depends(get_current_user)) -> dict:
    result, status_code = create_case_generation_job(user_id=user.id, payload=payload)
    response.status_code = status_code
    return success_response(result, code=status_code)


@router.post("/case-generation-jobs/{job_id}/cancel/")
def api_case_generation_job_cancel(job_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(cancel_case_generation_job(user_id=user.id, job_id=job_id))


@router.post("/case-generation-jobs/{job_id}/apply/")
def api_case_generation_job_apply(job_id: int, response: Response, user=Depends(get_current_user)) -> dict:
    result, status_code = apply_case_generation_job(user_id=user.id, job_id=job_id)
    response.status_code = status_code
    return success_response(result, code=status_code)
