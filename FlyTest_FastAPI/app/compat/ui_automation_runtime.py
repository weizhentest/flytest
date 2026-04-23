from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from django.db.models import Q

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def _get_accessible_projects(user_id: int):
    ensure_django_setup()
    from projects.models import Project

    user = get_django_user(user_id)
    if not user:
        return Project.objects.none()
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(members__user=user).distinct()


def _module_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiModule

    return UiModule.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "parent", "creator")


def _page_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiPage

    return UiPage.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "module", "creator").prefetch_related("elements")


def _element_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiElement

    return UiElement.objects.filter(page__project__in=_get_accessible_projects(user_id)).select_related("page", "creator")


def _page_steps_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiPageSteps

    return UiPageSteps.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "page", "module", "creator").prefetch_related("step_details")


def _page_steps_detailed_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiPageStepsDetailed

    return UiPageStepsDetailed.objects.filter(page_step__project__in=_get_accessible_projects(user_id)).select_related("page_step", "element")


def _testcase_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiTestCase

    return UiTestCase.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "module", "creator").prefetch_related("case_steps")


def _case_steps_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiCaseStepsDetailed

    return UiCaseStepsDetailed.objects.filter(test_case__project__in=_get_accessible_projects(user_id)).select_related("test_case", "page_step")


def _execution_record_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiExecutionRecord

    return UiExecutionRecord.objects.filter(test_case__project__in=_get_accessible_projects(user_id)).select_related("test_case", "executor", "batch")


def _public_data_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiPublicData

    return UiPublicData.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "creator")


def _env_config_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiEnvironmentConfig

    return UiEnvironmentConfig.objects.filter(project__in=_get_accessible_projects(user_id)).select_related("project", "creator")


def _batch_record_queryset(user_id: int):
    ensure_django_setup()
    from ui_automation.models import UiBatchExecutionRecord

    user = get_django_user(user_id)
    projects = _get_accessible_projects(user_id)
    return UiBatchExecutionRecord.objects.filter(
        Q(execution_records__test_case__project__in=projects) | Q(executor=user)
    ).distinct().select_related("executor").prefetch_related("execution_records", "execution_records__test_case")


def _serialize(serializer_cls, instance_or_queryset, *, many: bool = False):
    return serializer_cls(instance_or_queryset, many=many).data


def list_modules(*, user_id: int, project: int | None = None, parent: int | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiModuleSerializer

    queryset = _module_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if parent is not None:
        queryset = queryset.filter(parent_id=parent if parent else None)
    return _serialize(UiModuleSerializer, queryset.order_by("level", "name"), many=True)


def module_tree(*, user_id: int, project_id: int) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiModuleSerializer

    queryset = _module_queryset(user_id).filter(project_id=project_id, parent__isnull=True).order_by("level", "name")
    return _serialize(UiModuleSerializer, queryset, many=True)


def create_module(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiModuleSerializer

    serializer = UiModuleSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI module creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiModuleSerializer, instance)


def get_module(*, user_id: int, module_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiModuleSerializer

    instance = _module_queryset(user_id).filter(id=module_id).first()
    if not instance:
        raise AppError("UI module not found", status_code=404)
    return _serialize(UiModuleSerializer, instance)


def update_module(*, user_id: int, module_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiModuleSerializer

    instance = _module_queryset(user_id).filter(id=module_id).first()
    if not instance:
        raise AppError("UI module not found", status_code=404)
    serializer = UiModuleSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI module update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiModuleSerializer, instance)


def delete_module(*, user_id: int, module_id: int) -> None:
    instance = _module_queryset(user_id).filter(id=module_id).first()
    if not instance:
        raise AppError("UI module not found", status_code=404)
    try:
        instance.delete()
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Failed to delete UI module: {exc}", status_code=400)


def list_pages(*, user_id: int, project: int | None = None, module: int | None = None, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiPageSerializer

    queryset = _page_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if module:
        queryset = queryset.filter(module_id=module)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(url__icontains=search))
    return _serialize(UiPageSerializer, queryset.order_by("-id"), many=True)


def create_page(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageSerializer

    serializer = UiPageSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI page creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiPageSerializer, instance)


def get_page(*, user_id: int, page_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageDetailSerializer

    instance = _page_queryset(user_id).filter(id=page_id).first()
    if not instance:
        raise AppError("UI page not found", status_code=404)
    return _serialize(UiPageDetailSerializer, instance)


def update_page(*, user_id: int, page_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageSerializer

    instance = _page_queryset(user_id).filter(id=page_id).first()
    if not instance:
        raise AppError("UI page not found", status_code=404)
    serializer = UiPageSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI page update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiPageSerializer, instance)


def delete_page(*, user_id: int, page_id: int) -> None:
    instance = _page_queryset(user_id).filter(id=page_id).first()
    if not instance:
        raise AppError("UI page not found", status_code=404)
    try:
        instance.delete()
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Failed to delete UI page: {exc}", status_code=400)


def list_elements(*, user_id: int, page: int | None = None, locator_type: str | None = None, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiElementSerializer

    queryset = _element_queryset(user_id)
    if page:
        queryset = queryset.filter(page_id=page)
    if locator_type:
        queryset = queryset.filter(locator_type=locator_type)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(locator_value__icontains=search))
    return _serialize(UiElementSerializer, queryset.order_by("-id"), many=True)


def create_element(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiElementSerializer

    serializer = UiElementSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI element creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiElementSerializer, instance)


def get_element(*, user_id: int, element_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiElementSerializer

    instance = _element_queryset(user_id).filter(id=element_id).first()
    if not instance:
        raise AppError("UI element not found", status_code=404)
    return _serialize(UiElementSerializer, instance)


def update_element(*, user_id: int, element_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiElementSerializer

    instance = _element_queryset(user_id).filter(id=element_id).first()
    if not instance:
        raise AppError("UI element not found", status_code=404)
    serializer = UiElementSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI element update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiElementSerializer, instance)


def delete_element(*, user_id: int, element_id: int) -> None:
    instance = _element_queryset(user_id).filter(id=element_id).first()
    if not instance:
        raise AppError("UI element not found", status_code=404)
    instance.delete()


def list_page_steps(*, user_id: int, project: int | None = None, page: int | None = None, module: int | None = None, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsListSerializer

    queryset = _page_steps_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if page:
        queryset = queryset.filter(page_id=page)
    if module:
        queryset = queryset.filter(module_id=module)
    if search:
        queryset = queryset.filter(name__icontains=search)
    return _serialize(UiPageStepsListSerializer, queryset.order_by("-id"), many=True)


def create_page_steps(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsSerializer

    serializer = UiPageStepsSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI page steps creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiPageStepsSerializer, instance)


def get_page_steps(*, user_id: int, page_steps_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsDetailSerializer

    instance = _page_steps_queryset(user_id).filter(id=page_steps_id).first()
    if not instance:
        raise AppError("UI page steps not found", status_code=404)
    return _serialize(UiPageStepsDetailSerializer, instance)


def update_page_steps(*, user_id: int, page_steps_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsSerializer

    instance = _page_steps_queryset(user_id).filter(id=page_steps_id).first()
    if not instance:
        raise AppError("UI page steps not found", status_code=404)
    serializer = UiPageStepsSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI page steps update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiPageStepsSerializer, instance)


def delete_page_steps(*, user_id: int, page_steps_id: int) -> None:
    instance = _page_steps_queryset(user_id).filter(id=page_steps_id).first()
    if not instance:
        raise AppError("UI page steps not found", status_code=404)
    try:
        instance.delete()
    except Exception as exc:  # noqa: BLE001
        raise AppError(f"Failed to delete UI page steps: {exc}", status_code=400)


def page_steps_execute_data(*, user_id: int, page_steps_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsExecuteSerializer

    instance = _page_steps_queryset(user_id).filter(id=page_steps_id).first()
    if not instance:
        raise AppError("UI page steps not found", status_code=404)
    return _serialize(UiPageStepsExecuteSerializer, instance)


def list_page_steps_detailed(*, user_id: int, page_step: int | None = None, step_type: int | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsDetailedSerializer

    queryset = _page_steps_detailed_queryset(user_id)
    if page_step:
        queryset = queryset.filter(page_step_id=page_step)
    if step_type is not None:
        queryset = queryset.filter(step_type=step_type)
    return _serialize(UiPageStepsDetailedSerializer, queryset.order_by("page_step", "step_sort"), many=True)


def create_page_steps_detailed(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsDetailedSerializer

    serializer = UiPageStepsDetailedSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI page step detail creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiPageStepsDetailedSerializer, instance)


def get_page_steps_detailed(*, user_id: int, step_detail_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsDetailedSerializer

    instance = _page_steps_detailed_queryset(user_id).filter(id=step_detail_id).first()
    if not instance:
        raise AppError("UI page step detail not found", status_code=404)
    return _serialize(UiPageStepsDetailedSerializer, instance)


def update_page_steps_detailed(*, user_id: int, step_detail_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPageStepsDetailedSerializer

    instance = _page_steps_detailed_queryset(user_id).filter(id=step_detail_id).first()
    if not instance:
        raise AppError("UI page step detail not found", status_code=404)
    serializer = UiPageStepsDetailedSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI page step detail update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiPageStepsDetailedSerializer, instance)


def delete_page_steps_detailed(*, user_id: int, step_detail_id: int) -> None:
    instance = _page_steps_detailed_queryset(user_id).filter(id=step_detail_id).first()
    if not instance:
        raise AppError("UI page step detail not found", status_code=404)
    instance.delete()


def batch_update_page_steps_detailed(*, user_id: int, page_step_id: int, steps: list[dict[str, Any]]) -> dict:
    ensure_django_setup()
    from ui_automation.models import UiPageStepsDetailed
    from ui_automation.serializers import UiPageStepsDetailedSerializer

    page_step = _page_steps_queryset(user_id).filter(id=page_step_id).first()
    if not page_step:
        raise AppError("UI page steps not found", status_code=404)

    UiPageStepsDetailed.objects.filter(page_step_id=page_step_id).delete()
    for idx, step_data in enumerate(steps):
        item = dict(step_data)
        item["page_step"] = page_step_id
        item["step_sort"] = idx
        if "element_id" in item and "element" not in item:
            item["element"] = item.pop("element_id")
        serializer = UiPageStepsDetailedSerializer(data=item)
        if not serializer.is_valid():
            raise AppError("UI page step detail batch update failed", status_code=400, errors=serializer.errors)
        serializer.save()
    return {"message": "Batch update completed"}


def list_testcases(
    *,
    user_id: int,
    project: int | None = None,
    module: int | None = None,
    level: str | None = None,
    status: int | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiTestCaseListSerializer

    queryset = _testcase_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if module:
        queryset = queryset.filter(module_id=module)
    if level:
        queryset = queryset.filter(level=level)
    if status is not None:
        queryset = queryset.filter(status=status)
    if search:
        queryset = queryset.filter(name__icontains=search)
    return _serialize(UiTestCaseListSerializer, queryset.order_by("-created_at"), many=True)


def create_testcase(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiTestCaseSerializer

    serializer = UiTestCaseSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI testcase creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiTestCaseSerializer, instance)


def get_testcase(*, user_id: int, testcase_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiTestCaseDetailSerializer

    instance = _testcase_queryset(user_id).filter(id=testcase_id).first()
    if not instance:
        raise AppError("UI testcase not found", status_code=404)
    return _serialize(UiTestCaseDetailSerializer, instance)


def update_testcase(*, user_id: int, testcase_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiTestCaseSerializer

    instance = _testcase_queryset(user_id).filter(id=testcase_id).first()
    if not instance:
        raise AppError("UI testcase not found", status_code=404)
    serializer = UiTestCaseSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI testcase update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiTestCaseSerializer, instance)


def delete_testcase(*, user_id: int, testcase_id: int) -> None:
    instance = _testcase_queryset(user_id).filter(id=testcase_id).first()
    if not instance:
        raise AppError("UI testcase not found", status_code=404)
    instance.delete()


def testcase_execute_data(*, user_id: int, testcase_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiTestCaseExecuteSerializer

    instance = _testcase_queryset(user_id).filter(id=testcase_id).first()
    if not instance:
        raise AppError("UI testcase not found", status_code=404)
    return _serialize(UiTestCaseExecuteSerializer, instance)


def batch_delete_testcases(*, user_id: int, ids: list[int]) -> dict:
    if not ids:
        raise AppError("ids is required", status_code=400)
    queryset = _testcase_queryset(user_id).filter(id__in=ids)
    found_ids = list(queryset.values_list("id", flat=True))
    if len(found_ids) != len(ids):
        missing = [item for item in ids if item not in found_ids]
        raise AppError(f"UI testcases not found: {missing}", status_code=400)
    deleted_testcases = [{"id": item.id, "name": item.name, "module": item.module.name if item.module else None} for item in queryset]
    deleted_count, deleted_details = queryset.delete()
    return {
        "message": f"Deleted {len(deleted_testcases)} UI testcases",
        "deleted_count": len(deleted_testcases),
        "deleted_testcases": deleted_testcases,
        "deletion_details": deleted_details,
        "raw_deleted_count": deleted_count,
    }


def list_case_steps(*, user_id: int, test_case: int | None = None, status: int | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiCaseStepsDetailedSerializer

    queryset = _case_steps_queryset(user_id)
    if test_case:
        queryset = queryset.filter(test_case_id=test_case)
    if status is not None:
        queryset = queryset.filter(status=status)
    return _serialize(UiCaseStepsDetailedSerializer, queryset.order_by("test_case", "case_sort"), many=True)


def create_case_step(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiCaseStepsDetailedSerializer

    serializer = UiCaseStepsDetailedSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI case step creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiCaseStepsDetailedSerializer, instance)


def get_case_step(*, user_id: int, case_step_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiCaseStepsDetailedSerializer

    instance = _case_steps_queryset(user_id).filter(id=case_step_id).first()
    if not instance:
        raise AppError("UI case step not found", status_code=404)
    return _serialize(UiCaseStepsDetailedSerializer, instance)


def update_case_step(*, user_id: int, case_step_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiCaseStepsDetailedSerializer

    instance = _case_steps_queryset(user_id).filter(id=case_step_id).first()
    if not instance:
        raise AppError("UI case step not found", status_code=404)
    serializer = UiCaseStepsDetailedSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI case step update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiCaseStepsDetailedSerializer, instance)


def delete_case_step(*, user_id: int, case_step_id: int) -> None:
    instance = _case_steps_queryset(user_id).filter(id=case_step_id).first()
    if not instance:
        raise AppError("UI case step not found", status_code=404)
    instance.delete()


def batch_update_case_steps(*, user_id: int, test_case_id: int, steps: list[dict[str, Any]]) -> dict:
    ensure_django_setup()
    from ui_automation.models import UiCaseStepsDetailed
    from ui_automation.serializers import UiCaseStepsDetailedSerializer

    testcase = _testcase_queryset(user_id).filter(id=test_case_id).first()
    if not testcase:
        raise AppError("UI testcase not found", status_code=404)

    UiCaseStepsDetailed.objects.filter(test_case_id=test_case_id).delete()
    for idx, step_data in enumerate(steps):
        item = dict(step_data)
        item["test_case"] = test_case_id
        item["case_sort"] = idx
        serializer = UiCaseStepsDetailedSerializer(data=item)
        if not serializer.is_valid():
            raise AppError("UI case step batch update failed", status_code=400, errors=serializer.errors)
        serializer.save()
    return {"message": "Batch update completed"}


def list_execution_records(
    *,
    user_id: int,
    project: int | None = None,
    test_case: int | None = None,
    status: int | None = None,
    trigger_type: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiExecutionRecordListSerializer

    queryset = _execution_record_queryset(user_id)
    if project:
        queryset = queryset.filter(test_case__project_id=project)
    if test_case:
        queryset = queryset.filter(test_case_id=test_case)
    if status is not None:
        queryset = queryset.filter(status=status)
    if trigger_type:
        queryset = queryset.filter(trigger_type=trigger_type)
    return _serialize(UiExecutionRecordListSerializer, queryset.order_by("-created_at"), many=True)


def create_execution_record(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiExecutionRecordSerializer

    serializer = UiExecutionRecordSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI execution record creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(executor=get_django_user(user_id))
    return _serialize(UiExecutionRecordSerializer, instance)


def get_execution_record(*, user_id: int, record_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiExecutionRecordSerializer

    instance = _execution_record_queryset(user_id).filter(id=record_id).first()
    if not instance:
        raise AppError("UI execution record not found", status_code=404)
    return _serialize(UiExecutionRecordSerializer, instance)


def delete_execution_record(*, user_id: int, record_id: int) -> None:
    instance = _execution_record_queryset(user_id).filter(id=record_id).first()
    if not instance:
        raise AppError("UI execution record not found", status_code=404)

    media_root = Path("D:/360MoveData/Users/66674/Desktop/AI/flytest/FlyTest_Django/media")
    for screenshot in instance.screenshots or []:
        if isinstance(screenshot, str):
            screenshot_path = screenshot.replace("/media/", "").lstrip("/")
            candidate = media_root / screenshot_path
            if candidate.exists():
                candidate.unlink()

    for relative_path in [instance.video_path, instance.trace_path]:
        if relative_path:
            candidate = media_root / str(relative_path).lstrip("/")
            if candidate.exists():
                candidate.unlink()

    instance.delete()


def execution_trace(*, user_id: int, record_id: int, refresh: bool = False) -> dict:
    ensure_django_setup()
    from ui_automation.trace_parser import parse_trace_file

    instance = _execution_record_queryset(user_id).filter(id=record_id).first()
    if not instance:
        raise AppError("UI execution record not found", status_code=404)
    if instance.trace_data and not refresh:
        return instance.trace_data
    if not instance.trace_path:
        raise AppError("Trace data is not available", status_code=404)

    trace_path = Path(instance.trace_path)
    if not trace_path.is_absolute():
        trace_path = Path("D:/360MoveData/Users/66674/Desktop/AI/flytest/FlyTest_Django/media") / str(instance.trace_path).lstrip("/")
    trace_data = parse_trace_file(str(trace_path))
    if not trace_data:
        raise AppError("Trace parsing failed", status_code=500)
    instance.trace_data = trace_data
    instance.save(update_fields=["trace_data"])
    return trace_data


def list_public_data(
    *,
    user_id: int,
    project: int | None = None,
    type: int | None = None,
    is_enabled: bool | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiPublicDataSerializer

    queryset = _public_data_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if type is not None:
        queryset = queryset.filter(type=type)
    if is_enabled is not None:
        queryset = queryset.filter(is_enabled=is_enabled)
    if search:
        queryset = queryset.filter(key__icontains=search)
    return _serialize(UiPublicDataSerializer, queryset.order_by("project", "key"), many=True)


def create_public_data(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPublicDataSerializer

    serializer = UiPublicDataSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI public data creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiPublicDataSerializer, instance)


def get_public_data(*, user_id: int, item_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPublicDataSerializer

    instance = _public_data_queryset(user_id).filter(id=item_id).first()
    if not instance:
        raise AppError("UI public data not found", status_code=404)
    return _serialize(UiPublicDataSerializer, instance)


def update_public_data(*, user_id: int, item_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiPublicDataSerializer

    instance = _public_data_queryset(user_id).filter(id=item_id).first()
    if not instance:
        raise AppError("UI public data not found", status_code=404)
    serializer = UiPublicDataSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI public data update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiPublicDataSerializer, instance)


def delete_public_data(*, user_id: int, item_id: int) -> None:
    instance = _public_data_queryset(user_id).filter(id=item_id).first()
    if not instance:
        raise AppError("UI public data not found", status_code=404)
    instance.delete()


def public_data_by_project(*, user_id: int, project_id: int) -> list[dict]:
    queryset = _public_data_queryset(user_id).filter(project_id=project_id, is_enabled=True).values("key", "value", "type")
    return list(queryset)


def list_env_configs(
    *,
    user_id: int,
    project: int | None = None,
    browser: str | None = None,
    is_default: bool | None = None,
    search: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiEnvironmentConfigSerializer

    queryset = _env_config_queryset(user_id)
    if project:
        queryset = queryset.filter(project_id=project)
    if browser:
        queryset = queryset.filter(browser=browser)
    if is_default is not None:
        queryset = queryset.filter(is_default=is_default)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(base_url__icontains=search))
    return _serialize(UiEnvironmentConfigSerializer, queryset.order_by("project", "name"), many=True)


def create_env_config(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiEnvironmentConfigSerializer

    serializer = UiEnvironmentConfigSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI environment config creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=get_django_user(user_id))
    return _serialize(UiEnvironmentConfigSerializer, instance)


def get_env_config(*, user_id: int, config_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiEnvironmentConfigSerializer

    instance = _env_config_queryset(user_id).filter(id=config_id).first()
    if not instance:
        raise AppError("UI environment config not found", status_code=404)
    return _serialize(UiEnvironmentConfigSerializer, instance)


def update_env_config(*, user_id: int, config_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiEnvironmentConfigSerializer

    instance = _env_config_queryset(user_id).filter(id=config_id).first()
    if not instance:
        raise AppError("UI environment config not found", status_code=404)
    serializer = UiEnvironmentConfigSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("UI environment config update failed", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return _serialize(UiEnvironmentConfigSerializer, instance)


def delete_env_config(*, user_id: int, config_id: int) -> None:
    instance = _env_config_queryset(user_id).filter(id=config_id).first()
    if not instance:
        raise AppError("UI environment config not found", status_code=404)
    instance.delete()


def list_actuators() -> dict:
    ensure_django_setup()
    from ui_automation.consumers import SocketUserManager

    items = []
    for actuator_id, consumer in SocketUserManager._actuator_users.items():
        info = getattr(consumer, "actuator_info", {})
        items.append(
            {
                "id": actuator_id,
                "name": info.get("name", actuator_id),
                "ip": info.get("ip", "unknown"),
                "type": info.get("type", "web_ui"),
                "is_open": info.get("is_open", True),
                "debug": info.get("debug", False),
                "browser_type": info.get("browser_type", "chromium"),
                "headless": info.get("headless", False),
                "connected_at": info.get("connected_at"),
            }
        )
    return {"count": len(items), "items": items}


def actuator_status() -> dict:
    ensure_django_setup()
    from ui_automation.consumers import SocketUserManager

    return {
        "total_actuators": SocketUserManager.get_actuator_count(),
        "has_available": SocketUserManager.has_actuator(),
        "web_users": len(SocketUserManager._web_users),
    }


def list_batch_records(*, user_id: int, project: int | None = None, status: int | None = None, trigger_type: str | None = None) -> list[dict]:
    ensure_django_setup()
    from ui_automation.serializers import UiBatchExecutionRecordSerializer

    queryset = _batch_record_queryset(user_id)
    if project:
        queryset = queryset.filter(execution_records__test_case__project_id=project).distinct()
    if status is not None:
        queryset = queryset.filter(status=status)
    if trigger_type:
        queryset = queryset.filter(trigger_type=trigger_type)
    return _serialize(UiBatchExecutionRecordSerializer, queryset.order_by("-created_at"), many=True)


def create_batch_record(*, user_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiBatchExecutionRecordSerializer

    serializer = UiBatchExecutionRecordSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("UI batch record creation failed", status_code=400, errors=serializer.errors)
    instance = serializer.save(executor=get_django_user(user_id))
    return _serialize(UiBatchExecutionRecordSerializer, instance)


def get_batch_record(*, user_id: int, record_id: int) -> dict:
    ensure_django_setup()
    from ui_automation.serializers import UiBatchExecutionRecordDetailSerializer

    instance = _batch_record_queryset(user_id).filter(id=record_id).first()
    if not instance:
        raise AppError("UI batch record not found", status_code=404)
    return _serialize(UiBatchExecutionRecordDetailSerializer, instance)


def delete_batch_record(*, user_id: int, record_id: int) -> None:
    instance = _batch_record_queryset(user_id).filter(id=record_id).first()
    if not instance:
        raise AppError("UI batch record not found", status_code=404)
    instance.execution_records.all().delete()
    instance.delete()


def save_upload_file(*, category: str, filename: str, content: bytes, default_extension: str) -> dict:
    date_dir = datetime.now().strftime("%Y%m%d")
    media_root = Path("D:/360MoveData/Users/66674/Desktop/AI/flytest/FlyTest_Django/media")
    upload_dir = media_root / category / date_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(filename or "").suffix or default_extension
    unique_name = f"{Path(filename or 'upload').stem[:32] or 'upload'}_{datetime.now().strftime('%H%M%S%f')}{extension}"
    file_path = upload_dir / unique_name
    file_path.write_bytes(content)

    relative_path = f"{category}/{date_dir}/{unique_name}"
    return {
        "status": "success",
        "url": f"/media/{relative_path}",
        "path": relative_path,
    }
