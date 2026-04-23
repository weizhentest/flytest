from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_bearer_token
from app.core.dependencies import get_db
from app.core.responses import success_response
from app.services.auth.service import get_current_user_from_token
from app.services.ui_automation.service import (
    actuator_status,
    batch_delete_testcases,
    batch_update_case_steps,
    batch_update_page_steps_detailed,
    create_batch_record,
    create_case_step,
    create_element,
    create_env_config,
    create_execution_record,
    create_module,
    create_page,
    create_page_steps,
    create_page_steps_detailed,
    create_public_data,
    create_testcase,
    delete_batch_record,
    delete_case_step,
    delete_element,
    delete_env_config,
    delete_execution_record,
    delete_module,
    delete_page,
    delete_page_steps,
    delete_page_steps_detailed,
    delete_public_data,
    delete_testcase,
    execution_trace,
    get_batch_record,
    get_case_step,
    get_element,
    get_env_config,
    get_execution_record,
    get_module,
    get_page,
    get_page_steps,
    get_page_steps_detailed,
    get_public_data,
    get_testcase,
    list_actuators,
    list_batch_records,
    list_case_steps,
    list_elements,
    list_env_configs,
    list_execution_records,
    list_modules,
    list_page_steps,
    list_page_steps_detailed,
    list_pages,
    list_public_data,
    list_testcases,
    module_tree,
    page_steps_execute_data,
    public_data_by_project,
    save_upload_file,
    testcase_execute_data,
    update_case_step,
    update_element,
    update_env_config,
    update_module,
    update_page,
    update_page_steps,
    update_page_steps_detailed,
    update_public_data,
    update_testcase,
)


router = APIRouter(prefix="/ui-automation", tags=["ui-automation"])


def get_current_user(token: str = Depends(get_bearer_token), db: Session = Depends(get_db)):
    return get_current_user_from_token(db, token)


@router.post("/screenshots/upload/", status_code=201)
async def ui_screenshot_upload(file: UploadFile = File(...), user=Depends(get_current_user)) -> dict:
    content = await file.read()
    return save_upload_file(category="ui_screenshots", filename=file.filename or "screenshot.png", content=content, default_extension=".png")


@router.post("/traces/upload/", status_code=201)
async def ui_trace_upload(file: UploadFile = File(...), user=Depends(get_current_user)) -> dict:
    content = await file.read()
    return save_upload_file(category="ui_traces", filename=file.filename or "trace.zip", content=content, default_extension=".zip")


@router.get("/modules/")
def ui_modules(project: int | None = None, parent: int | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_modules(user_id=user.id, project=project, parent=parent))


@router.post("/modules/", status_code=201)
def ui_module_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_module(user_id=user.id, payload=payload), code=201)


@router.get("/modules/tree/")
def ui_modules_tree(project: int, user=Depends(get_current_user)) -> dict:
    return success_response(module_tree(user_id=user.id, project_id=project))


@router.get("/modules/{module_id}/")
def ui_module_detail(module_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_module(user_id=user.id, module_id=module_id))


@router.patch("/modules/{module_id}/")
def ui_module_patch(module_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_module(user_id=user.id, module_id=module_id, payload=payload))


@router.put("/modules/{module_id}/")
def ui_module_put(module_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_module(user_id=user.id, module_id=module_id, payload=payload))


@router.delete("/modules/{module_id}/")
def ui_module_delete(module_id: int, user=Depends(get_current_user)) -> dict:
    delete_module(user_id=user.id, module_id=module_id)
    return success_response(None)


@router.get("/pages/")
def ui_pages(project: int | None = None, module: int | None = None, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_pages(user_id=user.id, project=project, module=module, search=search))


@router.post("/pages/", status_code=201)
def ui_page_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_page(user_id=user.id, payload=payload), code=201)


@router.get("/pages/{page_id}/")
def ui_page_detail(page_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_page(user_id=user.id, page_id=page_id))


@router.patch("/pages/{page_id}/")
def ui_page_patch(page_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page(user_id=user.id, page_id=page_id, payload=payload))


@router.put("/pages/{page_id}/")
def ui_page_put(page_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page(user_id=user.id, page_id=page_id, payload=payload))


@router.delete("/pages/{page_id}/")
def ui_page_delete(page_id: int, user=Depends(get_current_user)) -> dict:
    delete_page(user_id=user.id, page_id=page_id)
    return success_response(None)


@router.get("/elements/")
def ui_elements(page: int | None = None, locator_type: str | None = None, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_elements(user_id=user.id, page=page, locator_type=locator_type, search=search))


@router.post("/elements/", status_code=201)
def ui_element_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_element(user_id=user.id, payload=payload), code=201)


@router.get("/elements/{element_id}/")
def ui_element_detail(element_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_element(user_id=user.id, element_id=element_id))


@router.patch("/elements/{element_id}/")
def ui_element_patch(element_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_element(user_id=user.id, element_id=element_id, payload=payload))


@router.put("/elements/{element_id}/")
def ui_element_put(element_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_element(user_id=user.id, element_id=element_id, payload=payload))


@router.delete("/elements/{element_id}/")
def ui_element_delete(element_id: int, user=Depends(get_current_user)) -> dict:
    delete_element(user_id=user.id, element_id=element_id)
    return success_response(None)


@router.get("/page-steps/")
def ui_page_steps(project: int | None = None, page: int | None = None, module: int | None = None, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_page_steps(user_id=user.id, project=project, page=page, module=module, search=search))


@router.post("/page-steps/", status_code=201)
def ui_page_steps_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_page_steps(user_id=user.id, payload=payload), code=201)


@router.get("/page-steps/{page_steps_id}/execute-data/")
def ui_page_steps_execute(page_steps_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(page_steps_execute_data(user_id=user.id, page_steps_id=page_steps_id))


@router.get("/page-steps/{page_steps_id}/")
def ui_page_steps_detail(page_steps_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_page_steps(user_id=user.id, page_steps_id=page_steps_id))


@router.patch("/page-steps/{page_steps_id}/")
def ui_page_steps_patch(page_steps_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page_steps(user_id=user.id, page_steps_id=page_steps_id, payload=payload))


@router.put("/page-steps/{page_steps_id}/")
def ui_page_steps_put(page_steps_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page_steps(user_id=user.id, page_steps_id=page_steps_id, payload=payload))


@router.delete("/page-steps/{page_steps_id}/")
def ui_page_steps_delete(page_steps_id: int, user=Depends(get_current_user)) -> dict:
    delete_page_steps(user_id=user.id, page_steps_id=page_steps_id)
    return success_response(None)


@router.post("/page-steps-detailed/batch_update/")
def ui_page_steps_detailed_batch_update(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        batch_update_page_steps_detailed(
            user_id=user.id,
            page_step_id=payload.get("page_step"),
            steps=payload.get("steps", []),
        )
    )


@router.get("/page-steps-detailed/")
def ui_page_steps_detailed(page_step: int | None = None, step_type: int | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_page_steps_detailed(user_id=user.id, page_step=page_step, step_type=step_type))


@router.post("/page-steps-detailed/", status_code=201)
def ui_page_steps_detailed_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_page_steps_detailed(user_id=user.id, payload=payload), code=201)


@router.get("/page-steps-detailed/{step_detail_id}/")
def ui_page_steps_detailed_detail(step_detail_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_page_steps_detailed(user_id=user.id, step_detail_id=step_detail_id))


@router.patch("/page-steps-detailed/{step_detail_id}/")
def ui_page_steps_detailed_patch(step_detail_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page_steps_detailed(user_id=user.id, step_detail_id=step_detail_id, payload=payload))


@router.put("/page-steps-detailed/{step_detail_id}/")
def ui_page_steps_detailed_put(step_detail_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_page_steps_detailed(user_id=user.id, step_detail_id=step_detail_id, payload=payload))


@router.delete("/page-steps-detailed/{step_detail_id}/")
def ui_page_steps_detailed_delete(step_detail_id: int, user=Depends(get_current_user)) -> dict:
    delete_page_steps_detailed(user_id=user.id, step_detail_id=step_detail_id)
    return success_response(None)


@router.get("/testcases/")
def ui_testcases(
    project: int | None = None,
    module: int | None = None,
    level: str | None = None,
    status: int | None = None,
    search: str | None = None,
    user=Depends(get_current_user),
) -> dict:
    return success_response(list_testcases(user_id=user.id, project=project, module=module, level=level, status=status, search=search))


@router.post("/testcases/", status_code=201)
def ui_testcase_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_testcase(user_id=user.id, payload=payload), code=201)


@router.get("/testcases/{testcase_id}/execute-data/")
def ui_testcase_execute_data_route(testcase_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(testcase_execute_data(user_id=user.id, testcase_id=testcase_id))


@router.post("/testcases/batch-delete/")
def ui_testcases_batch_delete(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(batch_delete_testcases(user_id=user.id, ids=payload.get("ids", [])))


@router.get("/testcases/{testcase_id}/")
def ui_testcase_detail(testcase_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_testcase(user_id=user.id, testcase_id=testcase_id))


@router.patch("/testcases/{testcase_id}/")
def ui_testcase_patch(testcase_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_testcase(user_id=user.id, testcase_id=testcase_id, payload=payload))


@router.put("/testcases/{testcase_id}/")
def ui_testcase_put(testcase_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_testcase(user_id=user.id, testcase_id=testcase_id, payload=payload))


@router.delete("/testcases/{testcase_id}/")
def ui_testcase_delete(testcase_id: int, user=Depends(get_current_user)) -> dict:
    delete_testcase(user_id=user.id, testcase_id=testcase_id)
    return success_response(None)


@router.post("/case-steps/batch_update/")
def ui_case_steps_batch_update(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(
        batch_update_case_steps(
            user_id=user.id,
            test_case_id=payload.get("test_case"),
            steps=payload.get("steps", []),
        )
    )


@router.get("/case-steps/")
def ui_case_steps(test_case: int | None = None, status: int | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_case_steps(user_id=user.id, test_case=test_case, status=status))


@router.post("/case-steps/", status_code=201)
def ui_case_step_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_case_step(user_id=user.id, payload=payload), code=201)


@router.get("/case-steps/{case_step_id}/")
def ui_case_step_detail(case_step_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_case_step(user_id=user.id, case_step_id=case_step_id))


@router.patch("/case-steps/{case_step_id}/")
def ui_case_step_patch(case_step_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_case_step(user_id=user.id, case_step_id=case_step_id, payload=payload))


@router.put("/case-steps/{case_step_id}/")
def ui_case_step_put(case_step_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_case_step(user_id=user.id, case_step_id=case_step_id, payload=payload))


@router.delete("/case-steps/{case_step_id}/")
def ui_case_step_delete(case_step_id: int, user=Depends(get_current_user)) -> dict:
    delete_case_step(user_id=user.id, case_step_id=case_step_id)
    return success_response(None)


@router.get("/execution-records/")
def ui_execution_records(project: int | None = None, test_case: int | None = None, status: int | None = None, trigger_type: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_execution_records(user_id=user.id, project=project, test_case=test_case, status=status, trigger_type=trigger_type))


@router.post("/execution-records/", status_code=201)
def ui_execution_record_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_execution_record(user_id=user.id, payload=payload), code=201)


@router.get("/execution-records/{record_id}/trace/")
def ui_execution_record_trace(record_id: int, refresh: bool = False, user=Depends(get_current_user)) -> dict:
    return success_response(execution_trace(user_id=user.id, record_id=record_id, refresh=refresh))


@router.get("/execution-records/{record_id}/")
def ui_execution_record_detail(record_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_execution_record(user_id=user.id, record_id=record_id))


@router.delete("/execution-records/{record_id}/")
def ui_execution_record_delete(record_id: int, user=Depends(get_current_user)) -> dict:
    delete_execution_record(user_id=user.id, record_id=record_id)
    return success_response(None)


@router.get("/public-data/by-project/{project_id}/")
def ui_public_data_by_project_route(project_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(public_data_by_project(user_id=user.id, project_id=project_id))


@router.get("/public-data/")
def ui_public_data(project: int | None = None, type: int | None = None, is_enabled: bool | None = None, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_public_data(user_id=user.id, project=project, type=type, is_enabled=is_enabled, search=search))


@router.post("/public-data/", status_code=201)
def ui_public_data_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_public_data(user_id=user.id, payload=payload), code=201)


@router.get("/public-data/{item_id}/")
def ui_public_data_detail(item_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_public_data(user_id=user.id, item_id=item_id))


@router.patch("/public-data/{item_id}/")
def ui_public_data_patch(item_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_public_data(user_id=user.id, item_id=item_id, payload=payload))


@router.put("/public-data/{item_id}/")
def ui_public_data_put(item_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_public_data(user_id=user.id, item_id=item_id, payload=payload))


@router.delete("/public-data/{item_id}/")
def ui_public_data_delete(item_id: int, user=Depends(get_current_user)) -> dict:
    delete_public_data(user_id=user.id, item_id=item_id)
    return success_response(None)


@router.get("/env-configs/")
def ui_env_configs(project: int | None = None, browser: str | None = None, is_default: bool | None = None, search: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_env_configs(user_id=user.id, project=project, browser=browser, is_default=is_default, search=search))


@router.post("/env-configs/", status_code=201)
def ui_env_config_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_env_config(user_id=user.id, payload=payload), code=201)


@router.get("/env-configs/{config_id}/")
def ui_env_config_detail(config_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_env_config(user_id=user.id, config_id=config_id))


@router.patch("/env-configs/{config_id}/")
def ui_env_config_patch(config_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_env_config(user_id=user.id, config_id=config_id, payload=payload))


@router.put("/env-configs/{config_id}/")
def ui_env_config_put(config_id: int, payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(update_env_config(user_id=user.id, config_id=config_id, payload=payload))


@router.delete("/env-configs/{config_id}/")
def ui_env_config_delete(config_id: int, user=Depends(get_current_user)) -> dict:
    delete_env_config(user_id=user.id, config_id=config_id)
    return success_response(None)


@router.get("/actuators/list_actuators/")
def ui_actuators_list(user=Depends(get_current_user)) -> dict:
    return success_response(list_actuators())


@router.get("/actuators/status/")
def ui_actuators_status(user=Depends(get_current_user)) -> dict:
    return success_response(actuator_status())


@router.get("/batch-records/")
def ui_batch_records(project: int | None = None, status: int | None = None, trigger_type: str | None = None, user=Depends(get_current_user)) -> dict:
    return success_response(list_batch_records(user_id=user.id, project=project, status=status, trigger_type=trigger_type))


@router.post("/batch-records/", status_code=201)
def ui_batch_record_create(payload: dict, user=Depends(get_current_user)) -> dict:
    return success_response(create_batch_record(user_id=user.id, payload=payload), code=201)


@router.get("/batch-records/{record_id}/")
def ui_batch_record_detail(record_id: int, user=Depends(get_current_user)) -> dict:
    return success_response(get_batch_record(user_id=user.id, record_id=record_id))


@router.delete("/batch-records/{record_id}/")
def ui_batch_record_delete(record_id: int, user=Depends(get_current_user)) -> dict:
    delete_batch_record(user_id=user.id, record_id=record_id)
    return success_response(None)
