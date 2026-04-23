from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

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


def _collect_collection_ids(root_collection) -> list[int]:
    if root_collection is None:
        return []
    ids = [root_collection.id]
    for child in root_collection.children.all():
        ids.extend(_collect_collection_ids(child))
    return ids


def list_collections(*, user_id: int, project_id: int | None = None, parent_id: int | None = None):
    ensure_django_setup()
    from api_automation.models import ApiCollection
    from api_automation.serializers import ApiCollectionSerializer

    queryset = ApiCollection.objects.filter(project__in=_get_accessible_projects(user_id))
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if parent_id is not None:
        queryset = queryset.filter(parent_id=parent_id or None)
    return ApiCollectionSerializer(queryset.order_by("order", "created_at"), many=True).data


def collection_tree(*, user_id: int, project_id: int):
    ensure_django_setup()
    from api_automation.models import ApiCollection
    from api_automation.serializers import ApiCollectionSerializer

    if not project_id:
        raise AppError("project 参数必填", status_code=400)
    queryset = ApiCollection.objects.filter(
        project_id=project_id,
        project__in=_get_accessible_projects(user_id),
        parent__isnull=True,
    ).order_by("order", "created_at")
    return ApiCollectionSerializer(queryset, many=True).data


def create_collection(*, user_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.serializers import ApiCollectionSerializer

    user = get_django_user(user_id)
    serializer = ApiCollectionSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("集合创建失败", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=user)
    return ApiCollectionSerializer(instance).data


def update_collection(*, user_id: int, collection_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.models import ApiCollection
    from api_automation.serializers import ApiCollectionSerializer

    instance = ApiCollection.objects.filter(id=collection_id, project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("集合不存在", status_code=404)
    serializer = ApiCollectionSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("集合更新失败", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return ApiCollectionSerializer(instance).data


def delete_collection(*, user_id: int, collection_id: int) -> None:
    ensure_django_setup()
    from api_automation.models import ApiCollection

    instance = ApiCollection.objects.filter(id=collection_id, project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("集合不存在", status_code=404)
    instance.delete()


def list_environments(*, user_id: int, project_id: int | None = None):
    ensure_django_setup()
    from api_automation.models import ApiEnvironment
    from api_automation.serializers import ApiEnvironmentSerializer

    queryset = ApiEnvironment.objects.filter(project__in=_get_accessible_projects(user_id))
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    return ApiEnvironmentSerializer(queryset.order_by("-is_default", "name"), many=True).data


def create_environment(*, user_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.serializers import ApiEnvironmentSerializer

    user = get_django_user(user_id)
    serializer = ApiEnvironmentSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("环境创建失败", status_code=400, errors=serializer.errors)
    instance = serializer.save(creator=user)
    return ApiEnvironmentSerializer(instance).data


def update_environment(*, user_id: int, environment_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.models import ApiEnvironment
    from api_automation.serializers import ApiEnvironmentSerializer

    instance = ApiEnvironment.objects.filter(id=environment_id, project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("环境不存在", status_code=404)
    serializer = ApiEnvironmentSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("环境更新失败", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return ApiEnvironmentSerializer(instance).data


def delete_environment(*, user_id: int, environment_id: int) -> None:
    ensure_django_setup()
    from api_automation.models import ApiEnvironment

    instance = ApiEnvironment.objects.filter(id=environment_id, project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("环境不存在", status_code=404)
    instance.delete()


def list_requests(
    *,
    user_id: int,
    project_id: int | None = None,
    collection_id: int | None = None,
    method: str | None = None,
):
    ensure_django_setup()
    from api_automation.models import ApiCollection, ApiRequest
    from api_automation.serializers import ApiRequestSerializer

    queryset = ApiRequest.objects.select_related("collection", "collection__project", "created_by").filter(
        collection__project__in=_get_accessible_projects(user_id)
    )
    if project_id:
        queryset = queryset.filter(collection__project_id=project_id)
    if collection_id:
        root = ApiCollection.objects.filter(pk=collection_id, project__in=_get_accessible_projects(user_id)).first()
        queryset = queryset.filter(collection_id__in=_collect_collection_ids(root)) if root else queryset.none()
    if method:
        queryset = queryset.filter(method=method.upper())
    return ApiRequestSerializer(queryset.order_by("order", "created_at"), many=True).data


def create_request(*, user_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.models import ApiCollection, ApiRequest
    from api_automation.serializers import ApiRequestSerializer

    user = get_django_user(user_id)
    collection_id = payload.get("collection")
    method = str(payload.get("method") or "").upper().strip()
    url = str(payload.get("url") or "").strip()
    if collection_id and method and url:
        collection = ApiCollection.objects.filter(pk=collection_id, project__in=_get_accessible_projects(user_id)).first()
        if collection:
            existing = ApiRequest.objects.filter(collection__project=collection.project, method=method, url=url).first()
            if existing:
                return ApiRequestSerializer(existing).data
    serializer = ApiRequestSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("接口创建失败", status_code=400, errors=serializer.errors)
    instance = serializer.save(created_by=user)
    return ApiRequestSerializer(instance).data


def update_request(*, user_id: int, request_id: int, payload: dict):
    ensure_django_setup()
    from api_automation.models import ApiRequest
    from api_automation.serializers import ApiRequestSerializer

    instance = ApiRequest.objects.filter(id=request_id, collection__project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("接口不存在", status_code=404)
    serializer = ApiRequestSerializer(instance, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("接口更新失败", status_code=400, errors=serializer.errors)
    instance = serializer.save()
    return ApiRequestSerializer(instance).data


def delete_request(*, user_id: int, request_id: int) -> None:
    ensure_django_setup()
    from api_automation.models import ApiRequest

    instance = ApiRequest.objects.filter(id=request_id, collection__project__in=_get_accessible_projects(user_id)).first()
    if not instance:
        raise AppError("接口不存在", status_code=404)
    instance.delete()


def _execution_record_queryset(*, user_id: int, project_id: int | None = None, request_id: int | None = None, collection_id: int | None = None):
    ensure_django_setup()
    from api_automation.models import ApiCollection, ApiExecutionRecord

    queryset = ApiExecutionRecord.objects.select_related(
        "project",
        "request",
        "request__collection",
        "test_case",
        "environment",
        "executor",
    ).filter(project__in=_get_accessible_projects(user_id))
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if request_id:
        queryset = queryset.filter(request_id=request_id)
    if collection_id:
        root = ApiCollection.objects.filter(pk=collection_id, project__in=_get_accessible_projects(user_id)).first()
        queryset = queryset.filter(request__collection_id__in=_collect_collection_ids(root)) if root else queryset.none()
    return queryset


def list_execution_records(
    *,
    user_id: int,
    project_id: int | None = None,
    request_id: int | None = None,
    collection_id: int | None = None,
) -> list[dict]:
    ensure_django_setup()
    from api_automation.serializers import ApiExecutionRecordSerializer

    queryset = _execution_record_queryset(
        user_id=user_id,
        project_id=project_id,
        request_id=request_id,
        collection_id=collection_id,
    )
    return ApiExecutionRecordSerializer(queryset.order_by("-created_at"), many=True).data


def get_execution_record(*, user_id: int, record_id: int) -> dict:
    ensure_django_setup()
    from api_automation.serializers import ApiExecutionRecordSerializer

    record = _execution_record_queryset(user_id=user_id).filter(id=record_id).first()
    if not record:
        raise AppError("执行记录不存在", status_code=404)
    return ApiExecutionRecordSerializer(record).data


def execute_request(*, user_id: int, request_id: int, environment_id: int | None = None, execution_mode: str = "sync") -> dict:
    ensure_django_setup()
    from api_automation.models import ApiRequest
    from api_automation.serializers import ApiExecutionRecordSerializer
    from api_automation.views import _build_run_name, _execute_api_request, _resolve_execution_environment

    user = get_django_user(user_id)
    api_request = ApiRequest.objects.filter(id=request_id, collection__project__in=_get_accessible_projects(user_id)).first()
    if not api_request:
        raise AppError("接口不存在", status_code=404)
    environment = _resolve_execution_environment(api_request.collection.project, environment_id)
    record = _execute_api_request(
        api_request=api_request,
        executor=user,
        environment=environment,
        run_id=uuid4().hex,
        run_name=_build_run_name("request", "single", api_request.name),
        request_name=api_request.name,
        execution_mode=execution_mode,
    )
    return ApiExecutionRecordSerializer(record).data


def execute_request_batch(
    *,
    user_id: int,
    scope: str,
    ids=None,
    project_id: int | None = None,
    collection_id: int | None = None,
    environment_id: int | None = None,
    execution_mode: str = "sync",
) -> dict:
    ensure_django_setup()
    from api_automation.views import (
        _build_run_name,
        _collect_request_scope,
        _execute_api_request,
        _resolve_execution_environment,
        _serialize_execution_batch,
    )

    user = get_django_user(user_id)
    api_requests = _collect_request_scope(
        user,
        scope,
        project_id=project_id,
        collection_id=collection_id,
        ids=ids or [],
    )
    if not api_requests:
        raise AppError("未找到可执行的接口脚本", status_code=400)

    runtime_context = {}
    records = []
    run_id = uuid4().hex
    run_name = _build_run_name("request", scope)
    try:
        for api_request in api_requests:
            environment = _resolve_execution_environment(api_request.collection.project, environment_id)
            records.append(
                _execute_api_request(
                    api_request=api_request,
                    executor=user,
                    environment=environment,
                    run_id=run_id,
                    run_name=run_name,
                    runtime_context=runtime_context,
                    execution_mode=execution_mode,
                )
            )
    finally:
        run_execution_context = runtime_context.get("_execution_run_context")
        if run_execution_context:
            run_execution_context.close()
            runtime_context.pop("_execution_run_context", None)
    return _serialize_execution_batch(records)


def get_execution_report(
    *,
    user_id: int,
    project_id: int | None = None,
    request_id: int | None = None,
    collection_id: int | None = None,
    days: int | None = None,
) -> dict:
    ensure_django_setup()
    from api_automation.views import _apply_report_days_filter, _build_execution_report_payload

    queryset = _execution_record_queryset(
        user_id=user_id,
        project_id=project_id,
        request_id=request_id,
        collection_id=collection_id,
    )
    queryset, error_payload = _apply_report_days_filter(queryset, days)
    if error_payload:
        raise AppError(error_payload.get("error") or "days 参数无效", status_code=400)
    return _build_execution_report_payload(queryset)


def get_execution_report_summary(
    *,
    user_id: int,
    project_id: int | None = None,
    request_id: int | None = None,
    collection_id: int | None = None,
    days: int | None = None,
) -> dict:
    ensure_django_setup()
    from api_automation.ai_report_summarizer import summarize_execution_report

    report_payload = get_execution_report(
        user_id=user_id,
        project_id=project_id,
        request_id=request_id,
        collection_id=collection_id,
        days=days,
    )
    result = summarize_execution_report(report_payload=report_payload, user=get_django_user(user_id))
    return {
        "used_ai": result.used_ai,
        "note": result.note,
        "summary": result.summary,
        "top_risks": result.top_risks,
        "recommended_actions": result.recommended_actions,
        "evidence": result.evidence,
        "prompt_name": result.prompt_name,
        "prompt_source": result.prompt_source,
        "model_name": result.model_name,
        "cache_hit": result.cache_hit,
        "cache_key": result.cache_key,
        "duration_ms": result.duration_ms,
        "lock_wait_ms": result.lock_wait_ms,
    }


def analyze_execution_record_failure(*, user_id: int, record_id: int) -> dict:
    ensure_django_setup()
    from api_automation.ai_failure_analyzer import analyze_execution_failure

    user = get_django_user(user_id)
    record = _execution_record_queryset(user_id=user_id).filter(id=record_id).first()
    if not record:
        raise AppError("执行记录不存在", status_code=404)
    result = analyze_execution_failure(record=record, user=user)
    return {
        "used_ai": result.used_ai,
        "note": result.note,
        "summary": result.summary,
        "failure_mode": result.failure_mode,
        "likely_root_causes": result.likely_root_causes,
        "recommended_actions": result.recommended_actions,
        "evidence": result.evidence,
        "recent_failures": result.recent_failures,
        "prompt_name": result.prompt_name,
        "prompt_source": result.prompt_source,
        "model_name": result.model_name,
        "cache_hit": result.cache_hit,
        "cache_key": result.cache_key,
        "duration_ms": result.duration_ms,
        "lock_wait_ms": result.lock_wait_ms,
    }


def list_test_cases(*, user_id: int, project_id: int | None = None, request_id: int | None = None, collection_id: int | None = None) -> list[dict]:
    ensure_django_setup()
    from api_automation.models import ApiCollection, ApiTestCase
    from api_automation.serializers import ApiTestCaseSerializer

    queryset = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator").filter(
        project__in=_get_accessible_projects(user_id)
    )
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if request_id:
        queryset = queryset.filter(request_id=request_id)
    if collection_id:
        root = ApiCollection.objects.filter(pk=collection_id, project__in=_get_accessible_projects(user_id)).first()
        queryset = queryset.filter(request__collection_id__in=_collect_collection_ids(root)) if root else queryset.none()
    return ApiTestCaseSerializer(queryset.order_by("-created_at"), many=True).data


def get_test_case(*, user_id: int, test_case_id: int) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiTestCase
    from api_automation.serializers import ApiTestCaseSerializer

    item = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator").filter(
        id=test_case_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    if not item:
        raise AppError("测试用例不存在", status_code=404)
    return ApiTestCaseSerializer(item).data


def create_test_case(*, user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from api_automation.serializers import ApiTestCaseSerializer

    user = get_django_user(user_id)
    serializer = ApiTestCaseSerializer(data=payload)
    if not serializer.is_valid():
        raise AppError("测试用例创建失败", status_code=400, errors=serializer.errors)
    item = serializer.save(creator=user)
    return ApiTestCaseSerializer(item).data


def update_test_case(*, user_id: int, test_case_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiTestCase
    from api_automation.serializers import ApiTestCaseSerializer

    item = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator").filter(
        id=test_case_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    if not item:
        raise AppError("测试用例不存在", status_code=404)
    serializer = ApiTestCaseSerializer(item, data=payload, partial=True)
    if not serializer.is_valid():
        raise AppError("测试用例更新失败", status_code=400, errors=serializer.errors)
    item = serializer.save()
    return ApiTestCaseSerializer(item).data


def delete_test_case(*, user_id: int, test_case_id: int) -> None:
    ensure_django_setup()
    from api_automation.models import ApiTestCase

    item = ApiTestCase.objects.filter(id=test_case_id, project__in=_get_accessible_projects(user_id)).first()
    if not item:
        raise AppError("测试用例不存在", status_code=404)
    item.delete()


def execute_test_case(*, user_id: int, test_case_id: int, environment_id: int | None = None, execution_mode: str = "sync") -> dict:
    ensure_django_setup()
    from api_automation.models import ApiTestCase
    from api_automation.serializers import ApiExecutionRecordSerializer
    from api_automation.views import _build_run_name, _execute_test_case, _resolve_execution_environment

    user = get_django_user(user_id)
    item = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator").filter(
        id=test_case_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    if not item:
        raise AppError("测试用例不存在", status_code=404)
    environment = _resolve_execution_environment(item.project, environment_id)
    record = _execute_test_case(
        test_case=item,
        executor=user,
        environment=environment,
        run_id=uuid4().hex,
        run_name=_build_run_name("test_case", "single", item.name),
        request_name=item.name,
        execution_mode=execution_mode,
    )
    return ApiExecutionRecordSerializer(record).data


def execute_test_case_batch(
    *,
    user_id: int,
    scope: str,
    ids=None,
    project_id: int | None = None,
    collection_id: int | None = None,
    environment_id: int | None = None,
    execution_mode: str = "sync",
) -> dict:
    ensure_django_setup()
    from api_automation.views import (
        _build_run_name,
        _collect_test_case_scope,
        _execute_test_case,
        _resolve_execution_environment,
        _serialize_execution_batch,
    )

    user = get_django_user(user_id)
    test_cases = _collect_test_case_scope(
        user,
        scope,
        project_id=project_id,
        collection_id=collection_id,
        ids=ids or [],
    )
    if not test_cases:
        raise AppError("未找到可执行的测试用例", status_code=400)

    runtime_context = {}
    records = []
    run_id = uuid4().hex
    run_name = _build_run_name("test_case", scope)
    try:
        for item in test_cases:
            environment = _resolve_execution_environment(item.project, environment_id)
            records.append(
                _execute_test_case(
                    test_case=item,
                    executor=user,
                    environment=environment,
                    run_id=run_id,
                    run_name=run_name,
                    request_name=item.name,
                    runtime_context=runtime_context,
                    execution_mode=execution_mode,
                )
            )
    finally:
        run_execution_context = runtime_context.get("_execution_run_context")
        if run_execution_context:
            run_execution_context.close()
            runtime_context.pop("_execution_run_context", None)
    return _serialize_execution_batch(records)


def list_import_jobs(*, user_id: int, project_id: int | None = None, status_value: str | None = None) -> list[dict]:
    ensure_django_setup()
    from api_automation.models import ApiImportJob
    from api_automation.serializers import ApiImportJobSerializer

    queryset = ApiImportJob.objects.select_related("project", "collection", "creator").filter(
        project__in=_get_accessible_projects(user_id)
    )
    user = get_django_user(user_id)
    if user and not user.is_superuser:
        queryset = queryset.filter(creator=user)
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if status_value:
        queryset = queryset.filter(status=status_value)
    return ApiImportJobSerializer(queryset.order_by("-created_at"), many=True).data


def get_import_job(*, user_id: int, job_id: int) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiImportJob
    from api_automation.serializers import ApiImportJobSerializer

    job = ApiImportJob.objects.select_related("project", "collection", "creator").filter(
        id=job_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    user = get_django_user(user_id)
    if job and user and not user.is_superuser and job.creator_id != user.id:
        job = None
    if not job:
        raise AppError("导入任务不存在", status_code=404)
    return ApiImportJobSerializer(job).data


def cancel_import_job(*, user_id: int, job_id: int) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiImportJob
    from api_automation.serializers import ApiImportJobSerializer
    from api_automation.views import _save_job
    from django.utils import timezone

    job = ApiImportJob.objects.select_related("project", "collection", "creator").filter(
        id=job_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    user = get_django_user(user_id)
    if job and user and not user.is_superuser and job.creator_id != user.id:
        job = None
    if not job:
        raise AppError("导入任务不存在", status_code=404)

    if job.status not in {"success", "failed", "canceled"}:
        update_fields = {
            "cancel_requested": True,
            "progress_message": "已收到停止解析请求，正在终止任务。",
        }
        if job.status == "pending":
            update_fields.update(
                {
                    "status": "canceled",
                    "progress_stage": "canceled",
                    "progress_percent": min(job.progress_percent or 0, 100),
                    "completed_at": timezone.now(),
                }
            )
        _save_job(job.id, force=True, **update_fields)
        job.refresh_from_db()
    return ApiImportJobSerializer(job).data


def import_document(
    *,
    user_id: int,
    collection_id: int,
    filename: str,
    file_bytes: bytes,
    generate_test_cases: bool,
    enable_ai_parse: bool,
    async_mode: bool,
) -> tuple[dict, int]:
    ensure_django_setup()
    from api_automation.import_service import process_document_import
    from api_automation.models import ApiCollection, ApiImportJob
    from api_automation.serializers import ApiImportJobSerializer
    from api_automation.views import _start_import_job

    user = get_django_user(user_id)
    collection = ApiCollection.objects.filter(
        id=collection_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    if not collection:
        raise AppError("目标接口集合不存在", status_code=404)

    suffix = Path(filename).suffix or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    if async_mode:
        job = ApiImportJob.objects.create(
            project=collection.project,
            collection=collection,
            creator=user,
            source_name=filename,
            status="pending",
            progress_percent=4,
            progress_stage="uploaded",
            progress_message="文档已上传，正在进入后台解析队列。",
            generate_test_cases=generate_test_cases,
            enable_ai_parse=enable_ai_parse,
        )
        _start_import_job(job.id, temp_path)
        return ApiImportJobSerializer(job).data, 202

    try:
        payload = process_document_import(
            collection=collection,
            user=user,
            file_path=temp_path,
            generate_test_cases=generate_test_cases,
            enable_ai_parse=enable_ai_parse,
        )
        return payload, 201
    except ValueError as exc:
        raise AppError(str(exc), status_code=400)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def list_case_generation_jobs(*, user_id: int, project_id: int | None = None, status_value: str | None = None) -> list[dict]:
    ensure_django_setup()
    from api_automation.models import ApiCaseGenerationJob
    from api_automation.serializers import ApiCaseGenerationJobSerializer

    queryset = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").filter(
        project__in=_get_accessible_projects(user_id)
    )
    user = get_django_user(user_id)
    if user and not user.is_superuser:
        queryset = queryset.filter(creator=user)
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    if status_value:
        queryset = queryset.filter(status=status_value)
    return ApiCaseGenerationJobSerializer(queryset.order_by("-created_at"), many=True).data


def get_case_generation_job(*, user_id: int, job_id: int) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiCaseGenerationJob
    from api_automation.serializers import ApiCaseGenerationJobSerializer

    job = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").filter(
        id=job_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    user = get_django_user(user_id)
    if job and user and not user.is_superuser and job.creator_id != user.id:
        job = None
    if not job:
        raise AppError("用例生成任务不存在", status_code=404)
    return ApiCaseGenerationJobSerializer(job).data


def create_case_generation_job(*, user_id: int, payload: dict) -> tuple[dict, int]:
    ensure_django_setup()
    from api_automation.models import ApiCaseGenerationJob, ApiCollection
    from api_automation.serializers import ApiCaseGenerationJobSerializer
    from api_automation.views import _collect_request_scope, _start_case_generation_job

    user = get_django_user(user_id)
    scope = str(payload.get("scope") or "selected").strip().lower()
    ids = payload.get("ids") or []
    project_id = payload.get("project_id")
    collection_id = payload.get("collection_id")
    mode = str(payload.get("mode") or "generate").strip().lower()
    count_per_request = max(1, min(int(payload.get("count_per_request") or 3), 10))
    api_requests = _collect_request_scope(
        user,
        scope,
        project_id=project_id,
        collection_id=collection_id,
        ids=ids,
    )
    if not api_requests:
        raise AppError("未找到可生成测试用例的接口", status_code=400)
    project_ids = {item.collection.project_id for item in api_requests}
    if len(project_ids) != 1:
        raise AppError("一次仅支持在同一个项目内生成测试用例", status_code=400)
    selected_collection = None
    if collection_id:
        selected_collection = ApiCollection.objects.filter(
            pk=collection_id,
            project__in=_get_accessible_projects(user_id),
        ).first()
    job = ApiCaseGenerationJob.objects.create(
        project=api_requests[0].collection.project,
        collection=selected_collection,
        creator=user,
        scope=scope,
        mode=mode,
        status="pending",
        count_per_request=count_per_request,
        request_ids=[item.id for item in api_requests],
        progress_percent=3,
        progress_stage="queued",
        progress_message="任务已提交，正在进入 AI 用例生成队列。",
    )
    _start_case_generation_job(job.id)
    return ApiCaseGenerationJobSerializer(job).data, 202


def cancel_case_generation_job(*, user_id: int, job_id: int) -> dict:
    ensure_django_setup()
    from api_automation.models import ApiCaseGenerationJob
    from api_automation.serializers import ApiCaseGenerationJobSerializer
    from api_automation.views import _save_case_generation_job
    from django.utils import timezone

    job = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").filter(
        id=job_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    user = get_django_user(user_id)
    if job and user and not user.is_superuser and job.creator_id != user.id:
        job = None
    if not job:
        raise AppError("用例生成任务不存在", status_code=404)

    if job.status not in {"success", "failed", "canceled"}:
        update_fields = {
            "cancel_requested": True,
            "progress_message": "已收到停止请求，正在终止 AI 用例生成任务。",
        }
        if job.status in {"pending", "preview_ready"}:
            update_fields.update(
                {
                    "status": "canceled",
                    "progress_stage": "canceled",
                    "progress_percent": min(job.progress_percent or 0, 100),
                    "completed_at": timezone.now(),
                }
            )
        _save_case_generation_job(job.id, force=True, **update_fields)
        job.refresh_from_db()
    return ApiCaseGenerationJobSerializer(job).data


def apply_case_generation_job(*, user_id: int, job_id: int) -> tuple[dict, int]:
    ensure_django_setup()
    from api_automation.models import ApiCaseGenerationJob
    from api_automation.serializers import ApiCaseGenerationJobSerializer
    from api_automation.views import _save_case_generation_job, _start_case_generation_apply

    job = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").filter(
        id=job_id,
        project__in=_get_accessible_projects(user_id),
    ).first()
    user = get_django_user(user_id)
    if job and user and not user.is_superuser and job.creator_id != user.id:
        job = None
    if not job:
        raise AppError("用例生成任务不存在", status_code=404)
    if job.status != "preview_ready":
        raise AppError("当前任务没有可应用的预览结果", status_code=400)

    _save_case_generation_job(
        job.id,
        force=True,
        status="applying",
        progress_percent=2,
        progress_stage="apply",
        progress_message="正在应用 AI 重生成预览结果。",
        error_message="",
        cancel_requested=False,
        completed_at=None,
    )
    _start_case_generation_apply(job.id)
    job.refresh_from_db()
    return ApiCaseGenerationJobSerializer(job).data, 202


def generate_test_cases_legacy(*, user_id: int, payload: dict) -> dict:
    ensure_django_setup()
    from api_automation.views import _collect_request_scope, _generate_request_test_cases

    user = get_django_user(user_id)
    scope = str(payload.get("scope") or "selected")
    ids = payload.get("ids") or []
    project_id = payload.get("project_id")
    collection_id = payload.get("collection_id")
    mode = str(payload.get("mode") or "generate").strip().lower()
    count_per_request = max(1, min(int(payload.get("count_per_request") or 3), 10))
    apply_changes = bool(payload.get("apply_changes", False))
    api_requests = _collect_request_scope(
        user,
        scope,
        project_id=project_id,
        collection_id=collection_id,
        ids=ids,
    )
    if not api_requests:
        raise AppError("未找到可生成测试用例的接口", status_code=400)
    items = [
        _generate_request_test_cases(
            api_request=item,
            user=user,
            mode=mode,
            count_per_request=count_per_request,
            apply_changes=apply_changes,
        )
        for item in api_requests
    ]
    skipped_count = sum(1 for item in items if item.get("skipped"))
    return {
        "scope": scope,
        "mode": mode,
        "total_requests": len(api_requests),
        "processed_requests": len(api_requests) - skipped_count,
        "skipped_requests": skipped_count,
        "created_testcase_count": sum(int(item.get("created_count") or 0) for item in items),
        "ai_used_count": sum(1 for item in items if item.get("ai_used")),
        "ai_cache_hit_count": sum(1 for item in items if item.get("ai_cache_hit")),
        "preview_only": any(bool(item.get("preview_only")) for item in items),
        "requires_confirmation": any(bool(item.get("preview_only")) for item in items),
        "preview_request_count": sum(1 for item in items if item.get("preview_only")),
        "note": " ".join(str(item.get("note") or "") for item in items if item.get("note")),
        "items": items,
    }
