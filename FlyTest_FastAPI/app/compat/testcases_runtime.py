from __future__ import annotations

import json
import io
from types import SimpleNamespace
from typing import Any

from fastapi.concurrency import run_in_threadpool
from django.core.files.uploadedfile import SimpleUploadedFile

from app.compat.django_bridge import ensure_django_setup, get_django_user
from app.core.errors import AppError


def _get_project(*, user_id: int, project_id: int):
    ensure_django_setup()
    from projects.models import Project

    user = get_django_user(user_id)
    queryset = Project.objects.all() if user and user.is_superuser else Project.objects.filter(members__user=user).distinct()
    project = queryset.filter(id=project_id).first()
    if not project:
        raise AppError("Project not found", status_code=404)
    return project


def _module_queryset(*, user_id: int, project_id: int):
    ensure_django_setup()
    from testcases.models import TestCaseModule

    return TestCaseModule.objects.filter(project=_get_project(user_id=user_id, project_id=project_id)).select_related("creator", "parent")


def _testcase_queryset(*, user_id: int, project_id: int):
    ensure_django_setup()
    from testcases.models import TestCase

    return (
        TestCase.objects.filter(project=_get_project(user_id=user_id, project_id=project_id))
        .select_related("creator", "module")
        .prefetch_related("steps", "screenshots")
    )


def _suite_queryset(*, user_id: int, project_id: int):
    ensure_django_setup()
    from testcases.models import TestSuite

    return TestSuite.objects.filter(project=_get_project(user_id=user_id, project_id=project_id)).prefetch_related("testcases", "creator")


def _execution_queryset(*, user_id: int, project_id: int):
    ensure_django_setup()
    from testcases.models import TestExecution

    return (
        TestExecution.objects.filter(suite__project=_get_project(user_id=user_id, project_id=project_id))
        .select_related("suite", "executor")
        .prefetch_related("results", "results__testcase")
    )


def _normalize_media_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    normalized = url.replace("\\", "/")
    if normalized.startswith("/media/"):
        return normalized
    normalized = normalized.lstrip("/")
    return f"/media/{normalized}"


def _screenshot_queryset(*, user_id: int, project_id: int, testcase_id: int):
    ensure_django_setup()
    from testcases.models import TestCaseScreenshot

    testcase = _testcase_queryset(user_id=user_id, project_id=project_id).filter(id=testcase_id).first()
    if not testcase:
        raise AppError("Test case not found", status_code=404)
    return testcase, TestCaseScreenshot.objects.filter(test_case=testcase).select_related("uploader")


def list_modules(*, user_id: int, project_id: int, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestCaseModuleSerializer

    queryset = _module_queryset(user_id=user_id, project_id=project_id)
    if search:
        queryset = queryset.filter(name__icontains=search)
    return TestCaseModuleSerializer(queryset.order_by("level", "name"), many=True).data


def create_module(*, user_id: int, project_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseModuleSerializer

    project = _get_project(user_id=user_id, project_id=project_id)
    serializer = TestCaseModuleSerializer(data=payload, context={"project": project})
    if not serializer.is_valid():
        raise AppError("Test case module creation failed", status_code=400, errors=serializer.errors)
    module = serializer.save(creator=get_django_user(user_id), project=project)
    return TestCaseModuleSerializer(module).data


def get_module(*, user_id: int, project_id: int, module_id: int) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseModuleSerializer

    module = _module_queryset(user_id=user_id, project_id=project_id).filter(id=module_id).first()
    if not module:
        raise AppError("Test case module not found", status_code=404)
    return TestCaseModuleSerializer(module).data


def update_module(*, user_id: int, project_id: int, module_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseModuleSerializer

    project = _get_project(user_id=user_id, project_id=project_id)
    module = _module_queryset(user_id=user_id, project_id=project_id).filter(id=module_id).first()
    if not module:
        raise AppError("Test case module not found", status_code=404)
    serializer = TestCaseModuleSerializer(module, data=payload, partial=True, context={"project": project})
    if not serializer.is_valid():
        raise AppError("Test case module update failed", status_code=400, errors=serializer.errors)
    module = serializer.save()
    return TestCaseModuleSerializer(module).data


def delete_module(*, user_id: int, project_id: int, module_id: int) -> None:
    module = _module_queryset(user_id=user_id, project_id=project_id).filter(id=module_id).first()
    if not module:
        raise AppError("Test case module not found", status_code=404)
    if module.testcases.exists():
        raise AppError(
            f"Cannot delete module '{module.name}' while it still has test cases",
            status_code=400,
        )
    module.delete()


def list_testcases(
    *,
    user_id: int,
    project_id: int,
    search: str | None = None,
    module_id: int | None = None,
    level: str | None = None,
    review_status: str | None = None,
    review_status_in: str | None = None,
    test_type: str | None = None,
    test_type_in: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestCaseSerializer

    queryset = _testcase_queryset(user_id=user_id, project_id=project_id)
    if search:
        queryset = queryset.filter(name__icontains=search) | queryset.filter(precondition__icontains=search)
    if module_id:
        module = _module_queryset(user_id=user_id, project_id=project_id).filter(id=module_id).first()
        queryset = queryset.filter(module_id__in=module.get_all_descendant_ids()) if module else queryset.none()
    if level:
        queryset = queryset.filter(level=level)
    if review_status:
        queryset = queryset.filter(review_status=review_status)
    if review_status_in:
        values = [item.strip() for item in review_status_in.split(",") if item.strip()]
        if values:
            queryset = queryset.filter(review_status__in=values)
    if test_type:
        queryset = queryset.filter(test_type=test_type)
    if test_type_in:
        values = [item.strip() for item in test_type_in.split(",") if item.strip()]
        if values:
            queryset = queryset.filter(test_type__in=values)
    return TestCaseSerializer(queryset.order_by("-created_at"), many=True).data


def create_testcase(*, user_id: int, project_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseSerializer

    serializer = TestCaseSerializer(data=payload, context={"request": None})
    if not serializer.is_valid():
        raise AppError("Test case creation failed", status_code=400, errors=serializer.errors)
    testcase = serializer.save(creator=get_django_user(user_id), project=_get_project(user_id=user_id, project_id=project_id))
    return TestCaseSerializer(testcase).data


def get_testcase(*, user_id: int, project_id: int, testcase_id: int) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseSerializer

    testcase = _testcase_queryset(user_id=user_id, project_id=project_id).filter(id=testcase_id).first()
    if not testcase:
        raise AppError("Test case not found", status_code=404)
    return TestCaseSerializer(testcase).data


def update_testcase(*, user_id: int, project_id: int, testcase_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestCaseSerializer

    testcase = _testcase_queryset(user_id=user_id, project_id=project_id).filter(id=testcase_id).first()
    if not testcase:
        raise AppError("Test case not found", status_code=404)
    serializer = TestCaseSerializer(testcase, data=payload, partial=True, context={"request": None})
    if not serializer.is_valid():
        raise AppError("Test case update failed", status_code=400, errors=serializer.errors)
    testcase = serializer.save()
    return TestCaseSerializer(testcase).data


def delete_testcase(*, user_id: int, project_id: int, testcase_id: int) -> None:
    testcase = _testcase_queryset(user_id=user_id, project_id=project_id).filter(id=testcase_id).first()
    if not testcase:
        raise AppError("Test case not found", status_code=404)
    testcase.delete()


def batch_delete_testcases(*, user_id: int, project_id: int, ids: list[int]) -> dict:
    if not ids:
        raise AppError("ids is required", status_code=400)
    queryset = _testcase_queryset(user_id=user_id, project_id=project_id).filter(id__in=ids)
    found_ids = list(queryset.values_list("id", flat=True))
    deleted_count, _ = queryset.delete()
    return {"deleted_count": deleted_count, "deleted_ids": found_ids}


def upload_testcase_screenshots(
    *,
    user_id: int,
    project_id: int,
    testcase_id: int,
    files: list[tuple[str, bytes, str]],
    title: str = "",
    description: str = "",
    step_number: int | None = None,
    mcp_session_id: str = "",
    page_url: str = "",
) -> dict:
    ensure_django_setup()
    from django.core.files.uploadedfile import SimpleUploadedFile
    from testcases.serializers import TestCaseScreenshotSerializer

    user = get_django_user(user_id)
    testcase, _ = _screenshot_queryset(user_id=user_id, project_id=project_id, testcase_id=testcase_id)
    if not files:
        raise AppError("Please provide screenshot files.", status_code=400)
    if len(files) > 10:
        raise AppError("You can upload at most 10 screenshots at a time.", status_code=400)

    allowed_types = {"image/jpeg", "image/jpg", "image/png", "image/gif"}
    max_size = 5 * 1024 * 1024
    created = []
    request_context = SimpleNamespace(user=user)

    for index, (filename, content, content_type) in enumerate(files, start=1):
        if content_type not in allowed_types:
            raise AppError(
                f"File {filename} has unsupported format.",
                status_code=400,
            )
        if len(content) > max_size:
            raise AppError(f"File {filename} exceeds 5MB limit.", status_code=400)

        upload = SimpleUploadedFile(name=filename, content=content, content_type=content_type)
        payload = {
            "test_case": testcase.id,
            "screenshot": upload,
            "title": f"{title} ({index})" if title and len(files) > 1 else title,
            "description": description,
            "step_number": step_number,
            "mcp_session_id": mcp_session_id,
            "page_url": page_url,
        }
        serializer = TestCaseScreenshotSerializer(data=payload, context={"request": request_context})
        if not serializer.is_valid():
            raise AppError("Screenshot upload failed.", status_code=400, errors=serializer.errors)
        created.append(serializer.save())

    return {
        "message": f"Successfully uploaded {len(created)} screenshots.",
        "screenshots": TestCaseScreenshotSerializer(created, many=True).data,
    }


def list_testcase_screenshots(*, user_id: int, project_id: int, testcase_id: int) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestCaseScreenshotSerializer

    _, queryset = _screenshot_queryset(user_id=user_id, project_id=project_id, testcase_id=testcase_id)
    return TestCaseScreenshotSerializer(queryset.order_by("step_number", "created_at"), many=True).data


def delete_testcase_screenshot(*, user_id: int, project_id: int, testcase_id: int, screenshot_id: int) -> dict:
    testcase, queryset = _screenshot_queryset(user_id=user_id, project_id=project_id, testcase_id=testcase_id)
    screenshot = queryset.filter(id=screenshot_id).first()
    if not screenshot:
        raise AppError("Screenshot not found.", status_code=404)
    screenshot.delete()
    return {"message": "Screenshot deleted successfully", "testcase_id": testcase.id}


def batch_delete_testcase_screenshots(*, user_id: int, project_id: int, testcase_id: int, ids: list[int]) -> dict:
    if not ids:
        raise AppError("ids is required", status_code=400)
    _, queryset = _screenshot_queryset(user_id=user_id, project_id=project_id, testcase_id=testcase_id)
    screenshots = queryset.filter(id__in=ids)
    found_ids = list(screenshots.values_list("id", flat=True))
    missing = [item for item in ids if item not in found_ids]
    if missing:
        raise AppError(
            f"Screenshots not found or not in current testcase: {missing}",
            status_code=400,
            errors={"not_found_ids": missing},
        )
    deleted_info = [
        {
            "id": screenshot.id,
            "title": screenshot.title or "untitled",
            "step_number": screenshot.step_number,
        }
        for screenshot in screenshots
    ]
    screenshots.delete()
    return {
        "message": f"Successfully deleted {len(deleted_info)} screenshots.",
        "deleted_count": len(deleted_info),
        "deleted_screenshots": deleted_info,
    }


def list_suites(*, user_id: int, project_id: int, search: str | None = None) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestSuiteSerializer

    queryset = _suite_queryset(user_id=user_id, project_id=project_id)
    if search:
        queryset = queryset.filter(name__icontains=search) | queryset.filter(description__icontains=search)
    return TestSuiteSerializer(queryset.order_by("-created_at"), many=True).data


def create_suite(*, user_id: int, project_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestSuiteSerializer

    serializer = TestSuiteSerializer(data=payload, context={"project_id": project_id})
    if not serializer.is_valid():
        raise AppError("Test suite creation failed", status_code=400, errors=serializer.errors)
    suite = serializer.save(creator=get_django_user(user_id), project=_get_project(user_id=user_id, project_id=project_id))
    return TestSuiteSerializer(suite).data


def get_suite(*, user_id: int, project_id: int, suite_id: int) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestSuiteSerializer

    suite = _suite_queryset(user_id=user_id, project_id=project_id).filter(id=suite_id).first()
    if not suite:
        raise AppError("Test suite not found", status_code=404)
    return TestSuiteSerializer(suite).data


def update_suite(*, user_id: int, project_id: int, suite_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestSuiteSerializer

    suite = _suite_queryset(user_id=user_id, project_id=project_id).filter(id=suite_id).first()
    if not suite:
        raise AppError("Test suite not found", status_code=404)
    serializer = TestSuiteSerializer(suite, data=payload, partial=True, context={"project_id": project_id})
    if not serializer.is_valid():
        raise AppError("Test suite update failed", status_code=400, errors=serializer.errors)
    suite = serializer.save()
    return TestSuiteSerializer(suite).data


def delete_suite(*, user_id: int, project_id: int, suite_id: int) -> None:
    suite = _suite_queryset(user_id=user_id, project_id=project_id).filter(id=suite_id).first()
    if not suite:
        raise AppError("Test suite not found", status_code=404)
    suite.delete()


def list_executions(
    *,
    user_id: int,
    project_id: int,
    search: str | None = None,
    ordering: str | None = None,
) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestExecutionSerializer

    queryset = _execution_queryset(user_id=user_id, project_id=project_id)
    if search:
        queryset = queryset.filter(suite__name__icontains=search)
    allowed_ordering = {"created_at", "-created_at", "started_at", "-started_at", "completed_at", "-completed_at", "status", "-status"}
    order_by = ordering if ordering in allowed_ordering else "-created_at"
    return TestExecutionSerializer(queryset.order_by(order_by), many=True).data


def create_execution(*, user_id: int, project_id: int, payload: dict[str, Any]) -> dict:
    ensure_django_setup()
    from testcases.models import TestExecution
    from testcases.serializers import TestExecutionCreateSerializer, TestExecutionSerializer

    serializer = TestExecutionCreateSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("Test execution creation failed", status_code=400, errors=serializer.errors)

    suite_id = serializer.validated_data["suite_id"]
    generate_playwright_script = serializer.validated_data.get("generate_playwright_script", False)
    suite = _suite_queryset(user_id=user_id, project_id=project_id).filter(id=suite_id).first()
    if not suite:
        raise AppError("Test suite not found", status_code=404)

    execution = TestExecution.objects.create(
        suite=suite,
        executor=get_django_user(user_id),
        status="pending",
        generate_playwright_script=generate_playwright_script,
    )

    try:
        from testcases.tasks import execute_test_suite

        task = execute_test_suite.delay(execution.id)
        execution.celery_task_id = getattr(task, "id", None)
        execution.save(update_fields=["celery_task_id", "updated_at"])
    except Exception:
        # Keep the execution record even when Celery/Redis is unavailable.
        pass

    return TestExecutionSerializer(execution).data


def get_execution(*, user_id: int, project_id: int, execution_id: int) -> dict:
    ensure_django_setup()
    from testcases.serializers import TestExecutionSerializer

    execution = _execution_queryset(user_id=user_id, project_id=project_id).filter(id=execution_id).first()
    if not execution:
        raise AppError("Test execution not found", status_code=404)
    return TestExecutionSerializer(execution).data


def cancel_execution(*, user_id: int, project_id: int, execution_id: int) -> dict:
    ensure_django_setup()
    from django.utils import timezone

    execution = _execution_queryset(user_id=user_id, project_id=project_id).filter(id=execution_id).first()
    if not execution:
        raise AppError("Test execution not found", status_code=404)
    if execution.status not in {"pending", "running"}:
        raise AppError(f"Cannot cancel execution in status {execution.status}", status_code=400)

    try:
        if execution.celery_task_id:
            from celery import current_app

            current_app.control.revoke(execution.celery_task_id, terminate=True)
    except Exception:
        pass

    execution.status = "cancelled"
    execution.completed_at = timezone.now()
    execution.save(update_fields=["status", "completed_at", "updated_at"])
    execution.results.filter(status__in=["pending", "running"]).update(status="skip")
    return {"message": "Test execution cancellation requested"}


def list_execution_results(*, user_id: int, project_id: int, execution_id: int) -> list[dict]:
    ensure_django_setup()
    from testcases.serializers import TestCaseResultSerializer

    execution = _execution_queryset(user_id=user_id, project_id=project_id).filter(id=execution_id).first()
    if not execution:
        raise AppError("Test execution not found", status_code=404)
    results = execution.results.all().select_related("testcase")
    return TestCaseResultSerializer(results, many=True).data


def execution_report(*, user_id: int, project_id: int, execution_id: int) -> dict:
    execution = _execution_queryset(user_id=user_id, project_id=project_id).filter(id=execution_id).first()
    if not execution:
        raise AppError("Test execution not found", status_code=404)

    data = {
        "execution_id": execution.id,
        "suite": {
            "id": execution.suite.id,
            "name": execution.suite.name,
            "description": execution.suite.description,
        },
        "executor": {
            "id": execution.executor.id,
            "username": execution.executor.username,
        }
        if execution.executor
        else None,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration": execution.duration,
        "statistics": {
            "total": execution.total_count,
            "passed": execution.passed_count,
            "failed": execution.failed_count,
            "skipped": execution.skipped_count,
            "error": execution.error_count,
            "pass_rate": execution.pass_rate,
        },
        "results": [],
        "script_results": [],
    }

    for result in execution.results.all().select_related("testcase"):
        data["results"].append(
            {
                "testcase_id": result.testcase.id,
                "testcase_name": result.testcase.name,
                "status": result.status,
                "error_message": result.error_message,
                "execution_time": result.execution_time,
                "screenshots": [_normalize_media_url(path) for path in (result.screenshots or [])],
                "testcase_detail": {
                    "id": result.testcase.id,
                    "name": result.testcase.name,
                    "level": result.testcase.level,
                },
            }
        )

    script_results_manager = getattr(execution, "script_results", None)
    if script_results_manager is not None:
        for script_result in script_results_manager.all().select_related("script"):
            data["script_results"].append(
                {
                    "script_id": script_result.script.id,
                    "script_name": script_result.script.name,
                    "status": script_result.status,
                    "error_message": script_result.error_message,
                    "execution_time": script_result.execution_time,
                    "screenshots": [_normalize_media_url(path) for path in (script_result.screenshots or [])],
                    "videos": [_normalize_media_url(path) for path in (script_result.videos or [])],
                    "output": script_result.output,
                }
            )

    return data


def delete_execution(*, user_id: int, project_id: int, execution_id: int) -> dict:
    execution = _execution_queryset(user_id=user_id, project_id=project_id).filter(id=execution_id).first()
    if not execution:
        raise AppError("Test execution not found", status_code=404)
    if execution.status in {"pending", "running"}:
        raise AppError("Cannot delete a pending or running execution", status_code=400)

    deleted_execution = {
        "id": execution.id,
        "suite_name": execution.suite.name,
        "status": execution.status,
        "created_at": execution.created_at,
    }
    execution.delete()
    return {"message": "Test execution deleted", "deleted_execution": deleted_execution}


def export_testcases_excel(
    *,
    user_id: int,
    project_id: int,
    method: str,
    payload: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
):
    ensure_django_setup()
    from testcase_templates.export_service import TestCaseExportService
    from testcase_templates.models import ImportExportTemplate

    project = _get_project(user_id=user_id, project_id=project_id)
    queryset = _testcase_queryset(user_id=user_id, project_id=project_id)
    source = query_params if method.upper() == "GET" else (payload or {})

    testcase_ids = source.get("ids")
    if isinstance(testcase_ids, str):
        testcase_ids = [int(item.strip()) for item in testcase_ids.split(",") if item.strip()]
    elif testcase_ids is None:
        testcase_ids = []

    module_ids = source.get("module_ids")
    if isinstance(module_ids, str):
        module_ids = [int(item.strip()) for item in module_ids.split(",") if item.strip()]
    elif module_ids is None:
        module_ids = []

    template_id = source.get("template_id")
    template = None
    if template_id:
        template = ImportExportTemplate.objects.filter(
            pk=int(template_id), is_active=True, template_type__in=["export", "both"]
        ).first()
        if not template:
            raise AppError("Export template not found or inactive", status_code=400)

    if testcase_ids:
        queryset = queryset.filter(id__in=testcase_ids)
    elif module_ids:
        all_module_ids: set[int] = set()
        for module_id in module_ids:
            module = _module_queryset(user_id=user_id, project_id=project_id).filter(id=module_id).first()
            if module:
                all_module_ids.update(module.get_all_descendant_ids())
        queryset = queryset.filter(module_id__in=all_module_ids) if all_module_ids else queryset.none()

    export_service = TestCaseExportService(template)
    excel_bytes, filename = export_service.export(queryset, project.name)
    return excel_bytes, filename


def import_testcases_excel(
    *,
    user_id: int,
    project_id: int,
    filename: str,
    file_bytes: bytes,
    template_id: int,
):
    ensure_django_setup()
    from testcase_templates.import_service import TestCaseImportService
    from testcase_templates.models import ImportExportTemplate

    if not file_bytes:
        raise AppError("Please upload an Excel file", status_code=400)

    template = ImportExportTemplate.objects.filter(id=template_id, is_active=True).first()
    if not template:
        raise AppError("Import template not found or inactive", status_code=404)

    project = _get_project(user_id=user_id, project_id=project_id)
    user = get_django_user(user_id)
    upload = SimpleUploadedFile(
        name=filename or "import.xlsx",
        content=file_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    result = TestCaseImportService(template, project, user).import_from_file(upload)
    return {
        "success": result.success,
        "total_rows": result.total_rows,
        "imported_count": result.imported_count,
        "skipped_count": result.skipped_count,
        "error_count": result.error_count,
        "duplicate_names": result.duplicate_names,
        "errors": result.errors[:20],
        "created_testcase_ids": result.created_testcases,
    }
