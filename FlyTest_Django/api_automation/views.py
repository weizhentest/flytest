from collections import OrderedDict
import os
import tempfile
import threading
import time
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from django.db.models import Q
from django.db.models import Avg, Count, Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models.functions import TruncDate
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from projects.models import Project
from flytest_django.viewsets import BaseModelViewSet

from .ai_failure_analyzer import analyze_execution_failure
from .ai_case_generator import (
    GeneratedCaseDraft,
    _coerce_bool,
    _normalize_extractors,
    _normalize_request_overrides,
    create_test_cases_from_drafts,
    generate_test_case_drafts_with_ai,
    summarize_persisted_test_cases,
)
from .ai_report_summarizer import summarize_execution_report
from .execution import ExecutionRunContext, execute_api_request
from .import_service import process_document_import
from .models import (
    ApiCaseGenerationJob,
    ApiCollection,
    ApiEnvironment,
    ApiExecutionRecord,
    ApiImportJob,
    ApiRequest,
    ApiTestCase,
)
from .serializers import (
    ApiCaseGenerationJobSerializer,
    ApiCollectionSerializer,
    ApiEnvironmentSerializer,
    ApiExecutionRecordSerializer,
    ApiImportJobSerializer,
    ApiRequestSerializer,
    ApiTestCaseSerializer,
)
from .services import (
    build_request_url,
    find_missing_variables,
    collect_placeholders,
    extract_json_path,
)
from .specs import (
    backfill_request_specs_from_legacy,
    backfill_test_case_specs_from_legacy,
    serialize_assertion_specs,
    serialize_extractor_specs,
    serialize_request_spec,
    serialize_test_case_override,
)


TOKEN_VARIABLE_NAMES = {"token", "access_token", "refresh_token", "refreshToken", "authorization"}
AUTH_RESPONSE_KEY_MAP = {
    "token": "token",
    "access_token": "token",
    "accessToken": "token",
    "jwt": "token",
    "authorization": "token",
    "refresh_token": "refresh_token",
    "refreshToken": "refresh_token",
    "uid": "uid",
    "userId": "uid",
    "user_id": "uid",
}
BOOTSTRAP_OPTIONAL_EMPTY_VARIABLES = {
    "device",
    "registrationId",
    "pushId",
    "deviceId",
    "deviceType",
    "nickname",
    "name",
}

WORKFLOW_FAILURE_STATUSES = {"failed", "error"}
WORKFLOW_STAGE_LABELS = {
    "prepare": "Prepare",
    "request": "Request",
    "teardown": "Teardown",
}


class ImportJobCancelled(Exception):
    pass


class CaseGenerationJobCancelled(Exception):
    pass


def get_accessible_projects(user):
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(Q(members__user=user) | Q(creator=user)).distinct()


def collect_collection_ids(root_collection: ApiCollection) -> list[int]:
    collection_ids = [root_collection.id]
    child_ids = list(root_collection.children.values_list("id", flat=True))
    for child_id in child_ids:
        child = root_collection.children.model.objects.get(id=child_id)
        collection_ids.extend(collect_collection_ids(child))
    return collection_ids


def _save_job(job_id: int, *, force: bool = False, **fields):
    job = ApiImportJob.objects.get(pk=job_id)
    if not force and job.status == "canceled" and fields.get("status") != "canceled":
        return job
    for key, value in fields.items():
        setattr(job, key, value)
    job.updated_at = timezone.now()
    job.save()
    return job


def _is_job_cancelled(job_id: int) -> bool:
    return ApiImportJob.objects.filter(pk=job_id).filter(Q(cancel_requested=True) | Q(status="canceled")).exists()


def _resolve_import_job_source_path(job: ApiImportJob) -> str:
    if not getattr(job, "source_file", None):
        raise ValueError("未找到可重启的源文档，请重新上传接口文档后再试。")
    try:
        file_path = job.source_file.path
    except (ValueError, NotImplementedError) as exc:
        raise ValueError("源文档暂不可访问，请重新上传接口文档后再试。") from exc
    if not file_path or not os.path.exists(file_path):
        raise ValueError("源文档已不存在，请重新上传接口文档后再试。")
    return file_path


def _delete_import_job_source_file(job: ApiImportJob):
    if not getattr(job, "source_file", None):
        return
    try:
        job.source_file.delete(save=False)
    except FileNotFoundError:
        pass


def _clear_import_job_source_file(job_id: int):
    job = ApiImportJob.objects.filter(pk=job_id).first()
    if not job or not getattr(job, "source_file", None):
        return
    _delete_import_job_source_file(job)
    ApiImportJob.objects.filter(pk=job_id).update(source_file="", updated_at=timezone.now())


def _save_case_generation_job(job_id: int, *, force: bool = False, **fields):
    job = ApiCaseGenerationJob.objects.get(pk=job_id)
    terminal_statuses = {"success", "failed", "canceled"}
    if not force and job.status in terminal_statuses and fields.get("status") not in terminal_statuses:
        return job
    for key, value in fields.items():
        setattr(job, key, value)
    job.updated_at = timezone.now()
    job.save()
    return job


def _is_case_generation_job_cancelled(job_id: int) -> bool:
    return ApiCaseGenerationJob.objects.filter(pk=job_id).filter(
        Q(cancel_requested=True) | Q(status="canceled")
    ).exists()


def _run_import_job(job_id: int):
    try:
        job = ApiImportJob.objects.select_related("collection", "project", "creator").get(pk=job_id)
        if job.cancel_requested or job.status == "canceled":
            _save_job(
                job_id,
                force=True,
                status="canceled",
                progress_stage="canceled",
                progress_message="文档解析任务已暂停。",
                completed_at=timezone.now(),
            )
            return
        file_path = _resolve_import_job_source_path(job)
        _save_job(
            job_id,
            status="running",
            progress_percent=8,
            progress_stage="queued",
            progress_message="任务已开始，正在准备解析接口文档。",
            error_message="",
        )

        def progress(percent: int, stage: str, message: str):
            if _is_job_cancelled(job_id):
                raise ImportJobCancelled("文档解析已手动停止")
            _save_job(
                job_id,
                status="running",
                progress_percent=max(0, min(percent, 100)),
                progress_stage=stage,
                progress_message=message,
            )

        payload = process_document_import(
            collection=job.collection,
            user=job.creator,
            file_path=file_path,
            generate_test_cases=job.generate_test_cases,
            enable_ai_parse=job.enable_ai_parse,
            progress_callback=progress,
            cancel_callback=lambda: _is_job_cancelled(job_id),
        )
        if _is_job_cancelled(job_id):
            raise ImportJobCancelled("文档解析已手动停止")
        _save_job(
            job_id,
            status="success",
            progress_percent=100,
            progress_stage="completed",
            progress_message="接口文档解析完成。",
            result_payload=payload,
            error_message="",
            completed_at=timezone.now(),
        )
        _clear_import_job_source_file(job_id)
    except ImportJobCancelled as exc:
        _save_job(
            job_id,
            force=True,
            status="canceled",
            progress_stage="canceled",
            progress_message="文档解析任务已暂停。",
            error_message=str(exc),
            completed_at=timezone.now(),
            cancel_requested=True,
        )
    except Exception as exc:  # noqa: BLE001
        _save_job(
            job_id,
            status="failed",
            progress_stage="failed",
            progress_message="接口文档解析失败。",
            error_message=str(exc),
            completed_at=timezone.now(),
        )


def _start_import_job(job_id: int):
    worker = threading.Thread(target=_run_import_job, args=(job_id,), daemon=True)
    worker.start()


def _load_requests_by_ids(request_ids: list[int]) -> list[ApiRequest]:
    if not request_ids:
        return []
    request_map = {
        item.id: item
        for item in ApiRequest.objects.select_related("collection", "collection__project", "created_by").filter(
            id__in=request_ids
        )
    }
    return [request_map[item_id] for item_id in request_ids if item_id in request_map]


def _run_case_generation_job(job_id: int):
    try:
        job = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").get(pk=job_id)
        if job.cancel_requested or job.status == "canceled":
            _save_case_generation_job(
                job_id,
                force=True,
                status="canceled",
                progress_stage="canceled",
                progress_message="AI 用例生成任务已取消。",
                completed_at=timezone.now(),
            )
            return

        _save_case_generation_job(
            job_id,
            status="running",
            progress_percent=8,
            progress_stage="prepare",
            progress_message="任务已开始，正在准备生成测试用例。",
            error_message="",
        )

        request_ids = [int(item) for item in (job.request_ids or []) if str(item).strip().isdigit()]
        api_requests = _load_requests_by_ids(request_ids)
        if not api_requests:
            raise ValueError("未找到可生成测试用例的接口。")

        public_items: list[dict[str, object]] = []
        draft_items: list[dict[str, object]] = []
        total_requests = len(api_requests)

        for index, api_request in enumerate(api_requests, start=1):
            if _is_case_generation_job_cancelled(job_id):
                raise CaseGenerationJobCancelled("AI 用例生成已手动停止")

            percent = 10 + int((index - 1) / max(total_requests, 1) * 72)
            _save_case_generation_job(
                job_id,
                status="running",
                progress_percent=min(percent, 88),
                progress_stage="generate",
                progress_message=f"正在为接口“{api_request.name}”生成测试用例（{index}/{total_requests}）。",
            )

            prepared = _prepare_request_test_case_generation(
                api_request=api_request,
                user=job.creator,
                mode=job.mode,
                count_per_request=job.count_per_request,
            )
            public_items.append(dict(prepared["public_item"]))
            draft_items.append(dict(prepared["draft_item"]))

        summary = _build_case_generation_summary(scope=job.scope, mode=job.mode, items=public_items)
        if job.mode == "regenerate":
            _save_case_generation_job(
                job_id,
                status="preview_ready",
                progress_percent=100,
                progress_stage="preview",
                progress_message="AI 重生成预览已准备完成，等待确认应用。",
                result_payload=summary,
                draft_payload={
                    "scope": job.scope,
                    "mode": job.mode,
                    "count_per_request": job.count_per_request,
                    "items": draft_items,
                },
                error_message="",
                completed_at=timezone.now(),
            )
            return

        _save_case_generation_job(
            job_id,
            status="success",
            progress_percent=100,
            progress_stage="completed",
            progress_message="AI 用例生成完成。",
            result_payload=summary,
            draft_payload={
                "scope": job.scope,
                "mode": job.mode,
                "count_per_request": job.count_per_request,
                "items": draft_items,
            },
            error_message="",
            completed_at=timezone.now(),
        )
    except CaseGenerationJobCancelled as exc:
        _save_case_generation_job(
            job_id,
            force=True,
            status="canceled",
            progress_stage="canceled",
            progress_message="AI 用例生成任务已取消。",
            error_message=str(exc),
            completed_at=timezone.now(),
            cancel_requested=True,
        )
    except Exception as exc:  # noqa: BLE001
        _save_case_generation_job(
            job_id,
            force=True,
            status="failed",
            progress_stage="failed",
            progress_message="AI 用例生成失败。",
            error_message=str(exc),
            completed_at=timezone.now(),
        )


def _apply_case_generation_job(job_id: int):
    try:
        job = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator").get(pk=job_id)
        if job.cancel_requested or job.status == "canceled":
            _save_case_generation_job(
                job_id,
                force=True,
                status="canceled",
                progress_stage="canceled",
                progress_message="AI 用例生成任务已取消。",
                completed_at=timezone.now(),
            )
            return

        if job.status not in {"applying", "preview_ready"}:
            raise ValueError("当前任务状态不支持应用预览结果。")

        draft_items = [item for item in ((job.draft_payload or {}).get("items") or []) if isinstance(item, dict)]
        if not draft_items:
            raise ValueError("当前任务没有可应用的预览草稿。")

        _save_case_generation_job(
            job_id,
            status="applying",
            progress_percent=6,
            progress_stage="apply",
            progress_message="正在应用 AI 重生成预览结果。",
            error_message="",
            completed_at=None,
        )

        public_items: list[dict[str, object]] = []
        total_items = len(draft_items)

        for index, draft_item in enumerate(draft_items, start=1):
            if _is_case_generation_job_cancelled(job_id):
                raise CaseGenerationJobCancelled("AI 用例生成已手动停止")

            if draft_item.get("skipped"):
                public_items.append(
                    {
                        "request_id": draft_item.get("request_id"),
                        "request_name": draft_item.get("request_name"),
                        "request_method": draft_item.get("request_method"),
                        "request_url": draft_item.get("request_url"),
                        "mode": job.mode,
                        "skipped": True,
                        "created_count": 0,
                        "ai_used": False,
                        "ai_cache_hit": False,
                        "items": [],
                    }
                )
                continue

            request_id = draft_item.get("request_id")
            api_request = ApiRequest.objects.select_related("collection", "collection__project", "created_by").filter(
                pk=request_id,
                collection__project=job.project,
            ).first()
            if not api_request:
                raise ValueError(f"接口已不存在，无法应用预览结果: request_id={request_id}")

            percent = 10 + int((index - 1) / max(total_items, 1) * 76)
            _save_case_generation_job(
                job_id,
                status="applying",
                progress_percent=min(percent, 92),
                progress_stage="apply",
                progress_message=f"正在应用接口“{api_request.name}”的预览结果（{index}/{total_items}）。",
            )
            public_items.append(
                _apply_request_test_case_generation_from_drafts(
                    api_request=api_request,
                    creator=job.creator,
                    mode=job.mode,
                    draft_item=draft_item,
                )
            )

        summary = _build_case_generation_summary(scope=job.scope, mode=job.mode, items=public_items)
        _save_case_generation_job(
            job_id,
            status="success",
            progress_percent=100,
            progress_stage="completed",
            progress_message="AI 用例生成结果已应用。",
            result_payload=summary,
            error_message="",
            completed_at=timezone.now(),
        )
    except CaseGenerationJobCancelled as exc:
        _save_case_generation_job(
            job_id,
            force=True,
            status="canceled",
            progress_stage="canceled",
            progress_message="AI 用例生成任务已取消。",
            error_message=str(exc),
            completed_at=timezone.now(),
            cancel_requested=True,
        )
    except Exception as exc:  # noqa: BLE001
        _save_case_generation_job(
            job_id,
            force=True,
            status="failed",
            progress_stage="failed",
            progress_message="应用 AI 预览结果失败。",
            error_message=str(exc),
            completed_at=timezone.now(),
        )


def _start_case_generation_job(job_id: int):
    worker = threading.Thread(target=_run_case_generation_job, args=(job_id,), daemon=True)
    worker.start()


def _start_case_generation_apply(job_id: int):
    worker = threading.Thread(target=_apply_case_generation_job, args=(job_id,), daemon=True)
    worker.start()


def _resolve_execution_environment(project: Project, environment_id=None):
    environment = None
    if environment_id:
        environment = ApiEnvironment.objects.filter(project=project, pk=environment_id).first()
    return environment or ApiEnvironment.objects.filter(project=project, is_default=True).first()


def _get_env_setting(variables: dict, *keys: str):
    for key in keys:
        value = variables.get(key)
        if value not in (None, ""):
            return value
    return None


def _is_auth_candidate(api_request: ApiRequest, variables: dict) -> bool:
    combined = f"{api_request.name} {api_request.url}".lower()
    if "refresh" in combined or "logout" in combined or "退出" in combined:
        return False

    placeholders = collect_placeholders(
        {
            "url": api_request.url,
            "headers": api_request.headers,
            "params": api_request.params,
            "body": api_request.body,
        }
    )
    token_placeholders = placeholders & TOKEN_VARIABLE_NAMES
    if token_placeholders:
        return False

    if "login" in combined or "登录" in combined or "applogin" in combined:
        return True
    if "token" in combined and api_request.method.upper() == "POST":
        return True
    return False


def _get_auth_requests(project: Project, variables: dict) -> list[ApiRequest]:
    auth_request_id = _get_env_setting(variables, "__auth_request_id", "auth_request_id")
    if auth_request_id not in (None, ""):
        request = ApiRequest.objects.filter(collection__project=project, id=auth_request_id).first()
        return [request] if request else []

    auth_request_name = str(_get_env_setting(variables, "__auth_request_name", "auth_request_name") or "").strip().lower()
    requests = list(
        ApiRequest.objects.select_related("collection", "collection__project")
        .filter(collection__project=project)
        .order_by("id")
    )

    if auth_request_name:
        matched = []
        for item in requests:
            combined = f"{item.name} {item.url}".lower()
            if auth_request_name in combined:
                matched.append(item)
        if matched:
            return matched

    def score(item: ApiRequest) -> int:
        combined = f"{item.name} {item.url}".lower()
        total = 0
        if not _is_auth_candidate(item, variables):
            return -999
        if "登录" in item.name or "login" in combined:
            total += 40
        if "applogin" in combined:
            total += 30
        if "pclogin" in combined:
            total += 20
        if item.method.upper() == "POST":
            total += 10
        return total

    return [item for item in sorted(requests, key=score, reverse=True) if score(item) > 0]


def _get_auth_request(project: Project, variables: dict) -> ApiRequest | None:
    requests = _get_auth_requests(project, variables)
    return requests[0] if requests else None


def _extract_auth_variables(response_payload, variables: dict) -> dict:
    if not isinstance(response_payload, dict):
        return {}

    explicit_token_path = _get_env_setting(variables, "__auth_token_path", "auth_token_path")
    token_paths = []
    if explicit_token_path:
        token_paths.extend([part.strip() for part in str(explicit_token_path).split(",") if part.strip()])
    token_paths.extend(
        [
            "data.token",
            "data.accessToken",
            "data.access_token",
            "data.jwt",
            "data.authorization",
            "token",
            "accessToken",
            "access_token",
            "authorization",
        ]
    )

    resolved: dict[str, str] = {}
    for path in token_paths:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["token"] = str(value)
            break

    for path in ["data.refresh_token", "data.refreshToken", "refresh_token", "refreshToken"]:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["refresh_token"] = str(value)
            break

    for path in ["data.uid", "data.userId", "data.user_id", "uid", "userId", "user_id"]:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["uid"] = str(value)
            break

    return resolved


def _extract_auth_error_message(record: ApiExecutionRecord) -> str:
    if record.error_message:
        return record.error_message
    payload = (record.response_snapshot or {}).get("body")
    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "msg"):
            value = payload.get(key)
            if value not in (None, ""):
                return str(value)
    return "登录接口未返回可用 token"


def _missing_variables_for_bootstrap(variables: dict, auth_request: ApiRequest) -> list[str]:
    missing = find_missing_variables(
        variables,
        auth_request.url,
        auth_request.headers,
        auth_request.params,
        auth_request.body,
    )
    return [item for item in missing if item not in BOOTSTRAP_OPTIONAL_EMPTY_VARIABLES]


def _serialize_execution_batch(records):
    serializer = ApiExecutionRecordSerializer(records, many=True)
    run_types = {"test_case" if record.test_case_id else "request" for record in records}
    execution_mode = "sync"
    if records:
        execution_mode = str((records[0].request_snapshot or {}).get("execution_mode") or "sync")
    return {
        "run_id": records[0].run_id if records else None,
        "run_name": records[0].run_name if records else None,
        "run_type": next(iter(run_types)) if len(run_types) == 1 else "mixed",
        "execution_mode": execution_mode,
        "total_count": len(records),
        "success_count": sum(1 for record in records if record.status == "success"),
        "failed_count": sum(1 for record in records if record.status == "failed"),
        "error_count": sum(1 for record in records if record.status == "error"),
        "items": serializer.data,
    }


def _build_run_name(execution_kind: str, scope: str = "single", target_name: str | None = None) -> str:
    labels = {
        ("request", "single"): "接口执行",
        ("request", "selected"): "接口批量执行",
        ("request", "collection"): "接口目录执行",
        ("request", "project"): "项目接口执行",
        ("test_case", "single"): "测试用例执行",
        ("test_case", "selected"): "测试用例批量执行",
        ("test_case", "collection"): "目录测试用例执行",
        ("test_case", "project"): "项目测试用例执行",
    }
    label = labels.get((execution_kind, scope), "接口执行")
    if target_name and scope == "single":
        return f"{label} - {target_name}"
    return label


def _resolve_execution_mode(payload) -> str:
    explicit_mode = str(payload.get("execution_mode") or "").strip().lower()
    if explicit_mode in {"sync", "async"}:
        return explicit_mode

    for key in ("use_async", "async_mode"):
        if key not in payload:
            continue
        return "async" if str(payload.get(key) or "").lower() in {"1", "true", "yes", "on"} else "sync"
    return "sync"


def _increment_execution_counts(target: dict, record: ApiExecutionRecord):
    target["total_count"] += 1
    if record.passed:
        target["passed_count"] += 1
    if record.status == "failed":
        target["failed_count"] += 1
    if record.status == "error":
        target["error_count"] += 1


def _finalize_execution_counts(target: dict):
    total_count = target.get("total_count", 0)
    target["pass_rate"] = round((target.get("passed_count", 0) / total_count) * 100, 2) if total_count else 0
    return target


def _resolve_record_case_name(record_payload: dict) -> str:
    interface_name = record_payload.get("interface_name")
    test_case_name = record_payload.get("test_case_name")
    request_name = record_payload.get("request_name")
    if test_case_name:
        return test_case_name
    if request_name and request_name != interface_name:
        return request_name
    return "接口直接执行"


def _build_run_payload(records: list[ApiExecutionRecord], *, run_id: str, run_name: str, latest_executed_at):
    if not records:
        return None

    ordered_records = sorted(records, key=lambda item: item.created_at, reverse=True)
    serializer = ApiExecutionRecordSerializer(ordered_records, many=True)
    payload_by_id = {item["id"]: item for item in serializer.data}
    interface_map: OrderedDict[str, dict] = OrderedDict()
    environment_names: OrderedDict[str, None] = OrderedDict()
    run_types = {"test_case" if record.test_case_id else "request" for record in ordered_records}

    for record in ordered_records:
        record_payload = payload_by_id[record.id]
        environment_name = record_payload.get("environment_name")
        if environment_name:
            environment_names.setdefault(environment_name, None)

        interface_name = record_payload.get("interface_name") or record_payload.get("request_name") or "未命名接口"
        interface_key = f"{record.request_id or interface_name}:{record_payload.get('collection_id') or ''}"
        interface_entry = interface_map.setdefault(
            interface_key,
            {
                "request_id": record.request_id,
                "interface_name": interface_name,
                "collection_id": record_payload.get("collection_id"),
                "collection_name": record_payload.get("collection_name"),
                "method": record_payload.get("method"),
                "url": record_payload.get("url"),
                "total_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "error_count": 0,
                "latest_executed_at": record_payload.get("created_at"),
                "latest_status_code": record_payload.get("status_code"),
                "failed_test_case_count": 0,
                "test_cases": [],
                "failed_test_cases": [],
                "_case_map": OrderedDict(),
            },
        )
        _increment_execution_counts(interface_entry, record)

        case_name = _resolve_record_case_name(record_payload)
        case_key = f"test-case:{record.test_case_id}" if record.test_case_id else f"direct:{record.request_id or interface_name}"
        case_entry = interface_entry["_case_map"].setdefault(
            case_key,
            {
                "test_case_id": record.test_case_id,
                "test_case_name": case_name,
                "is_direct_request": not bool(record.test_case_id),
                "total_count": 0,
                "passed_count": 0,
                "failed_count": 0,
                "error_count": 0,
                "latest_executed_at": record_payload.get("created_at"),
                "latest_status_code": record_payload.get("status_code"),
                "latest_error_message": record_payload.get("error_message"),
                "records": [],
                "failed_records": [],
            },
        )
        _increment_execution_counts(case_entry, record)
        case_entry["records"].append(record_payload)
        if not record.passed:
            case_entry["failed_records"].append(record_payload)
            if not case_entry.get("latest_error_message"):
                case_entry["latest_error_message"] = record_payload.get("error_message")

    interfaces = []
    for interface_entry in interface_map.values():
        case_entries = []
        failed_case_entries = []
        for case_entry in interface_entry.pop("_case_map").values():
            _finalize_execution_counts(case_entry)
            case_entries.append(case_entry)
            if case_entry["failed_count"] or case_entry["error_count"]:
                failed_case_entries.append(case_entry)

        interface_entry["test_cases"] = case_entries
        interface_entry["failed_test_cases"] = failed_case_entries
        interface_entry["failed_test_case_count"] = len(failed_case_entries)
        _finalize_execution_counts(interface_entry)
        interfaces.append(interface_entry)

    run_payload = {
        "run_id": run_id,
        "run_name": run_name or ordered_records[0].run_name or "单次执行",
        "run_type": next(iter(run_types)) if len(run_types) == 1 else "mixed",
        "total_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "error_count": 0,
        "latest_executed_at": latest_executed_at or ordered_records[0].created_at,
        "environment_names": list(environment_names.keys()),
        "interface_count": len(interfaces),
        "failed_interface_count": sum(1 for item in interfaces if item["failed_count"] or item["error_count"]),
        "test_case_count": sum(len(item["test_cases"]) for item in interfaces),
        "failed_test_case_count": sum(item["failed_test_case_count"] for item in interfaces),
        "interfaces": interfaces,
    }
    for record in ordered_records:
        _increment_execution_counts(run_payload, record)
    _finalize_execution_counts(run_payload)
    return run_payload


def _build_report_run_groups(queryset, limit: int = 12):
    run_rows = list(
        queryset.exclude(run_id="")
        .values("run_id", "run_name")
        .annotate(latest_executed_at=Max("created_at"))
        .order_by("-latest_executed_at")[:limit]
    )
    legacy_records = list(
        queryset.filter(run_id="")
        .select_related("request", "request__collection", "test_case", "environment", "executor")
        .order_by("-created_at")[:limit]
    )

    selected_runs = [
        {
            "key": row["run_id"],
            "run_id": row["run_id"],
            "run_name": row["run_name"] or "",
            "latest_executed_at": row["latest_executed_at"],
            "legacy_record_id": None,
        }
        for row in run_rows
    ]
    selected_runs.extend(
        {
            "key": f"legacy-{record.id}",
            "run_id": f"legacy-{record.id}",
            "run_name": record.run_name or "",
            "latest_executed_at": record.created_at,
            "legacy_record_id": record.id,
        }
        for record in legacy_records
    )
    fallback_time = datetime.min.replace(tzinfo=timezone.now().tzinfo)
    selected_runs.sort(
        key=lambda item: item["latest_executed_at"] or fallback_time,
        reverse=True,
    )
    selected_runs = selected_runs[:limit]

    if not selected_runs:
        return [], {
            "run_count": 0,
            "interface_count": 0,
            "failed_interface_count": 0,
            "test_case_count": 0,
            "failed_test_case_count": 0,
        }

    selected_run_ids = [item["run_id"] for item in selected_runs if item["legacy_record_id"] is None]
    selected_legacy_ids = [item["legacy_record_id"] for item in selected_runs if item["legacy_record_id"] is not None]
    records = list(
        queryset.filter(Q(run_id__in=selected_run_ids) | Q(id__in=selected_legacy_ids))
        .select_related("request", "request__collection", "test_case", "environment", "executor")
        .order_by("-created_at")
    )

    grouped_records: OrderedDict[str, list[ApiExecutionRecord]] = OrderedDict()
    for record in records:
        grouped_records.setdefault(record.run_id or f"legacy-{record.id}", []).append(record)

    run_groups = []
    for selected_run in selected_runs:
        run_payload = _build_run_payload(
            grouped_records.get(selected_run["key"], []),
            run_id=selected_run["run_id"],
            run_name=selected_run["run_name"],
            latest_executed_at=selected_run["latest_executed_at"],
        )
        if run_payload:
            run_groups.append(run_payload)

    hierarchy_summary = {
        "run_count": len(run_groups),
        "interface_count": sum(item["interface_count"] for item in run_groups),
        "failed_interface_count": sum(item["failed_interface_count"] for item in run_groups),
        "test_case_count": sum(item["test_case_count"] for item in run_groups),
        "failed_test_case_count": sum(item["failed_test_case_count"] for item in run_groups),
    }
    return run_groups, hierarchy_summary


def _apply_report_days_filter(queryset, days_value_raw):
    if not days_value_raw:
        return queryset, None
    try:
        days_value = max(1, min(int(days_value_raw), 90))
        since = timezone.now() - timedelta(days=days_value)
        return queryset.filter(created_at__gte=since), None
    except ValueError:
        return queryset, {"error": "days 参数必须是 1-90 之间的整数"}


def _build_execution_report_payload(queryset):
    total_count = queryset.count()
    aggregate = queryset.aggregate(
        success_count=Count("id", filter=Q(status="success")),
        failed_count=Count("id", filter=Q(status="failed")),
        error_count=Count("id", filter=Q(status="error")),
        passed_count=Count("id", filter=Q(passed=True)),
        avg_response_time=Avg("response_time"),
        latest_executed_at=Max("created_at"),
    )

    method_breakdown = list(
        queryset.values("method")
        .annotate(
            total=Count("id"),
            passed=Count("id", filter=Q(passed=True)),
            failed=Count("id", filter=Q(status="failed")),
            error=Count("id", filter=Q(status="error")),
            avg_response_time=Avg("response_time"),
        )
        .order_by("method")
    )

    collection_breakdown = list(
        queryset.values("request__collection__name")
        .annotate(
            total=Count("id"),
            passed=Count("id", filter=Q(passed=True)),
            failed=Count("id", filter=Q(status="failed")),
            error=Count("id", filter=Q(status="error")),
        )
        .order_by("-total", "request__collection__name")
    )

    failing_requests = list(
        queryset.filter(passed=False)
        .values("request_id", "request__name", "request__collection__name")
        .annotate(
            total=Count("id"),
            latest_executed_at=Max("created_at"),
            latest_status_code=Max("status_code"),
        )
        .order_by("-total", "request__name")[:10]
    )

    trend = list(
        queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total=Count("id"),
            passed=Count("id", filter=Q(passed=True)),
            failed=Count("id", filter=Q(status="failed")),
            error=Count("id", filter=Q(status="error")),
        )
        .order_by("day")
    )

    recent_records = queryset.order_by("-created_at")[:10]
    recent_records_payload = ApiExecutionRecordSerializer(recent_records, many=True).data
    run_groups, hierarchy_summary = _build_report_run_groups(queryset)
    pass_rate = round(((aggregate["passed_count"] or 0) / total_count) * 100, 2) if total_count else 0

    return {
        "summary": {
            "total_count": total_count,
            "success_count": aggregate["success_count"] or 0,
            "failed_count": aggregate["failed_count"] or 0,
            "error_count": aggregate["error_count"] or 0,
            "passed_count": aggregate["passed_count"] or 0,
            "pass_rate": pass_rate,
            "avg_response_time": round(float(aggregate["avg_response_time"] or 0), 2) if aggregate["avg_response_time"] else None,
            "latest_executed_at": aggregate["latest_executed_at"],
        },
        "method_breakdown": method_breakdown,
        "collection_breakdown": collection_breakdown,
        "failing_requests": [
            {
                "request_id": item["request_id"],
                "request_name": item["request__name"] or "未命名接口",
                "request__collection__name": item["request__collection__name"],
                "total": item["total"],
                "latest_executed_at": item["latest_executed_at"],
                "latest_status_code": item["latest_status_code"],
            }
            for item in failing_requests
        ],
        "trend": trend,
        "recent_records": recent_records_payload,
        "run_groups": run_groups,
        "hierarchy_summary": hierarchy_summary,
    }


def _collect_request_scope(user, scope: str, *, project_id=None, collection_id=None, ids=None):
    queryset = ApiRequest.objects.select_related("collection", "collection__project", "created_by").filter(
        collection__project__in=get_accessible_projects(user)
    )

    if scope == "selected":
        if not ids:
            return []
        return list(queryset.filter(id__in=ids).order_by("collection_id", "order", "created_at"))

    if scope == "collection":
        if not collection_id:
            return []
        root_collection = ApiCollection.objects.filter(
            pk=collection_id,
            project__in=get_accessible_projects(user),
        ).first()
        if not root_collection:
            return []
        return list(queryset.filter(collection_id__in=collect_collection_ids(root_collection)).order_by("order", "created_at"))

    if scope == "project":
        if not project_id:
            return []
        return list(queryset.filter(collection__project_id=project_id).order_by("collection_id", "order", "created_at"))

    return []


def _collect_test_case_scope(user, scope: str, *, project_id=None, collection_id=None, ids=None):
    queryset = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator").filter(
        project__in=get_accessible_projects(user)
    )

    if scope == "selected":
        if not ids:
            return []
        return list(queryset.filter(id__in=ids).order_by("created_at"))

    if scope == "collection":
        if not collection_id:
            return []
        root_collection = ApiCollection.objects.filter(
            pk=collection_id,
            project__in=get_accessible_projects(user),
        ).first()
        if not root_collection:
            return []
        return list(
            queryset.filter(request__collection_id__in=collect_collection_ids(root_collection)).order_by("created_at")
        )

    if scope == "project":
        if not project_id:
            return []
        return list(queryset.filter(project_id=project_id).order_by("created_at"))

    return []


def _execute_api_request(
    *,
    api_request: ApiRequest,
    executor,
    environment: ApiEnvironment | None = None,
    test_case: ApiTestCase | None = None,
    run_id: str | None = None,
    run_name: str | None = None,
    request_name: str | None = None,
    override_payload: dict | None = None,
    snapshot_extra: dict | None = None,
    assertions_override=None,
    extractors_override=None,
    runtime_context: dict | None = None,
    allow_auth_bootstrap: bool = True,
    execution_mode: str = "sync",
):
    shared_runtime_context = runtime_context is not None
    runtime_context = runtime_context if runtime_context is not None else {}
    created_local_context = False
    run_execution_context = runtime_context.get("_execution_run_context")

    if not getattr(api_request, "request_spec", None):
        backfill_request_specs_from_legacy(api_request)
    if test_case and not getattr(test_case, "override_spec", None):
        backfill_test_case_specs_from_legacy(test_case)

    if not run_execution_context:
        run_execution_context = ExecutionRunContext(
            run_id=run_id or uuid4().hex,
            run_name=run_name or "",
            environment=environment,
            execution_mode=execution_mode,
        )
        run_execution_context.variables.update(runtime_context.get("variables", {}))
        runtime_context["_execution_run_context"] = run_execution_context
        created_local_context = True
    else:
        if run_id:
            run_execution_context.run_id = run_id
        if run_name:
            run_execution_context.run_name = run_name
        if environment and run_execution_context.environment is None:
            run_execution_context.environment = environment
        run_execution_context.execution_mode = execution_mode or run_execution_context.execution_mode
        run_execution_context.variables.update(runtime_context.get("variables", {}))

    try:
        record = execute_api_request(
            api_request=api_request,
            executor=executor,
            environment=environment,
            test_case=test_case,
            run_context=run_execution_context,
            request_name=request_name,
            allow_bootstrap=allow_auth_bootstrap,
            request_override=override_payload,
            assertion_specs_override=assertions_override,
            extractor_specs_override=extractors_override,
        )
        if snapshot_extra:
            request_snapshot = dict(record.request_snapshot or {})
            request_snapshot.update(snapshot_extra)
            record.request_snapshot = request_snapshot
            record.save(update_fields=["request_snapshot"])
        runtime_context["variables"] = dict(run_execution_context.variables)
        return record
    finally:
        if created_local_context and not shared_runtime_context:
            run_execution_context.close()
            runtime_context.pop("_execution_run_context", None)


def _coerce_workflow_number(value):
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError):
        return value
    return int(numeric) if numeric.is_integer() else numeric


def _normalize_workflow_schema_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return ""


def _normalize_workflow_assertions(assertions):
    if assertions is None:
        return None
    if not isinstance(assertions, list):
        return []

    normalized = []
    for index, item in enumerate(assertions):
        if not isinstance(item, dict):
            continue
        assertion_type = str(item.get("assertion_type") or item.get("type") or "").strip()
        if not assertion_type:
            continue

        normalized_item = {
            "assertion_type": assertion_type,
            "target": item.get("target") or ("json" if assertion_type == "json_path" else "body"),
            "selector": item.get("selector") or item.get("path") or "",
            "operator": item.get("operator") or "equals",
            "expected_text": str(item.get("expected_text") or ""),
            "expected_number": _coerce_workflow_number(item.get("expected_number")),
            "expected_json": item.get("expected_json") if isinstance(item.get("expected_json"), (dict, list, bool)) else {},
            "min_value": _coerce_workflow_number(item.get("min_value", item.get("min"))),
            "max_value": _coerce_workflow_number(item.get("max_value", item.get("max"))),
            "schema_text": _normalize_workflow_schema_text(item.get("schema_text")),
            "enabled": bool(item.get("enabled", True)),
            "order": int(item.get("order", index)),
        }
        expected_value = item.get("expected")
        if expected_value not in (None, "") and normalized_item["expected_number"] is None:
            if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
                normalized_item["expected_number"] = _coerce_workflow_number(expected_value)
            elif isinstance(expected_value, (dict, list, bool)):
                normalized_item["expected_json"] = expected_value
            else:
                normalized_item["expected_text"] = str(expected_value)
        normalized.append(normalized_item)
    return normalized


def _resolve_workflow_request(test_case: ApiTestCase, raw_step: dict):
    request_queryset = ApiRequest.objects.select_related("collection").filter(collection__project=test_case.project)
    request_id = raw_step.get("request_id")
    request_name = str(raw_step.get("request_name") or "").strip()

    if request_id not in (None, ""):
        request_obj = request_queryset.filter(pk=request_id).first()
        if request_obj:
            return request_obj, ""
        return None, f"Workflow step request not found: request_id={request_id}"

    if request_name:
        request_obj = request_queryset.filter(name__iexact=request_name).order_by("collection_id", "order", "created_at").first()
        if request_obj:
            return request_obj, ""
        request_obj = request_queryset.filter(name__icontains=request_name).order_by("collection_id", "order", "created_at").first()
        if request_obj:
            return request_obj, ""
        return None, f"Workflow step request not found: request_name={request_name}"

    return test_case.request, ""


def _parse_test_case_workflow_steps(test_case: ApiTestCase):
    script = test_case.script if isinstance(test_case.script, dict) else {}
    raw_steps = script.get("workflow_steps")
    if not isinstance(raw_steps, list):
        return []

    steps = []
    for index, raw_step in enumerate(raw_steps):
        if not isinstance(raw_step, dict):
            continue
        if not bool(raw_step.get("enabled", True)):
            continue

        stage = str(raw_step.get("stage") or "prepare").strip().lower()
        if stage not in {"prepare", "request", "teardown"}:
            stage = "prepare"

        request_obj, lookup_error = _resolve_workflow_request(test_case, raw_step)
        raw_assertions = raw_step.get("assertion_specs")
        if raw_assertions is None:
            raw_assertions = raw_step.get("assertions")
        raw_extractors = raw_step.get("extractor_specs")
        if raw_extractors is None:
            raw_extractors = raw_step.get("extractors")
        raw_request_overrides = raw_step.get("request_overrides")
        steps.append(
            {
                "index": len(steps) + 1,
                "stage": stage,
                "name": str(raw_step.get("name") or (request_obj.name if request_obj else f"workflow_step_{index + 1}")).strip()[:160],
                "continue_on_failure": bool(_coerce_bool(raw_step.get("continue_on_failure"), False)),
                "request": request_obj,
                "request_id": request_obj.id if request_obj else raw_step.get("request_id"),
                "request_name": request_obj.name if request_obj else str(raw_step.get("request_name") or ""),
                "lookup_error": lookup_error,
                "request_overrides": (
                    _normalize_request_overrides(request_obj or test_case.request, raw_request_overrides)
                    if isinstance(raw_request_overrides, dict)
                    else None
                ),
                "assertions_override": _normalize_workflow_assertions(raw_assertions),
                "extractors_override": _normalize_extractors(raw_extractors, []) if raw_extractors is not None else None,
            }
        )
    return steps


def _serialize_workflow_step_result(step: dict, record: ApiExecutionRecord | None = None, *, status=None, error_message=""):
    result_status = status or (record.status if record else "error")
    if record:
        passed = record.passed
    elif result_status == "success":
        passed = True
    elif result_status in WORKFLOW_FAILURE_STATUSES:
        passed = False
    else:
        passed = None
    payload = {
        "kind": step.get("kind") or "workflow_step",
        "index": step.get("index"),
        "name": step.get("name"),
        "stage": step.get("stage"),
        "continue_on_failure": bool(step.get("continue_on_failure", False)),
        "request_id": step.get("request_id"),
        "request_name": step.get("request_name"),
        "status": result_status,
        "passed": passed,
        "status_code": record.status_code if record else None,
        "response_time": record.response_time if record else None,
        "error_message": error_message or (record.error_message if record else ""),
        "record_id": record.id if record else None,
        "record_request_name": record.request_name if record else "",
        "response_snapshot": dict(record.response_snapshot or {}) if record else {},
        "assertions_results": list(record.assertions_results or []) if record else [],
    }
    if record and step.get("kind") != "main_request":
        payload["request_snapshot"] = dict(record.request_snapshot or {})
    else:
        payload["request_snapshot"] = {}
    return payload


def _is_workflow_failure(step_result: dict) -> bool:
    return str(step_result.get("status") or "") in WORKFLOW_FAILURE_STATUSES


def _build_workflow_step_failure_assertions(step_results: list[dict], start_index: int) -> list[dict]:
    assertions = []
    next_index = start_index
    for item in step_results:
        if item.get("kind") == "main_request" or not _is_workflow_failure(item):
            continue
        assertions.append(
            {
                "index": next_index,
                "type": "workflow_step",
                "stage": item.get("stage"),
                "name": item.get("name"),
                "expected": "success",
                "actual": item.get("status"),
                "passed": False,
                "message": item.get("error_message") or f"{item.get('name')} failed",
            }
        )
        next_index += 1
    return assertions


def _format_workflow_failure_message(step_result: dict) -> str:
    step_name = step_result.get("name") or "unnamed_step"
    step_stage = str(step_result.get("stage") or "prepare")
    detail = step_result.get("error_message") or f"status={step_result.get('status')}"
    return f"Workflow step failed: {step_name} [{step_stage}], {detail}"


def _build_test_case_blocked_record(
    *,
    test_case: ApiTestCase,
    executor,
    environment: ApiEnvironment | None,
    run_id: str,
    run_name: str,
    request_name: str,
    execution_mode: str,
    override_payload: dict,
    assertions_override: list[dict],
    snapshot_extra: dict,
    status_value: str,
    error_message: str,
):
    request_spec = serialize_request_spec(test_case.request)
    body_mode = str(override_payload.get("body_mode") or request_spec.get("body_mode") or "none")
    body_value = override_payload.get("body_json") or request_spec.get("body_json")
    if body_mode == "raw":
        body_value = override_payload.get("raw_text") or request_spec.get("raw_text")
    elif body_mode == "xml":
        body_value = override_payload.get("xml_text") or request_spec.get("xml_text")
    elif body_mode == "graphql":
        body_value = {
            "query": override_payload.get("graphql_query") or request_spec.get("graphql_query") or "",
            "operationName": override_payload.get("graphql_operation_name") or request_spec.get("graphql_operation_name") or "",
            "variables": override_payload.get("graphql_variables") or request_spec.get("graphql_variables") or {},
        }
    elif body_mode == "binary":
        body_value = override_payload.get("binary_base64") or request_spec.get("binary_base64") or ""

    request_snapshot = {
        "request_id": test_case.request_id,
        "interface_name": test_case.request.name,
        "collection_id": test_case.request.collection_id,
        "collection_name": test_case.request.collection.name,
        "test_case_id": test_case.id,
        "test_case_name": test_case.name,
        "test_case_status": test_case.status,
        "test_case_tags": test_case.tags or [],
        "test_case_script": test_case.script if isinstance(test_case.script, dict) else {},
        "method": str(override_payload.get("method") or request_spec.get("method") or test_case.request.method).upper(),
        "url": build_request_url(
            environment.base_url if environment else "",
            str(override_payload.get("url") or request_spec.get("url") or test_case.request.url),
        ),
        "headers": {},
        "params": {},
        "cookies": {},
        "body_mode": body_mode,
        "body": body_value,
        "request_spec": request_spec,
        "request_override_spec": override_payload,
        "assertion_specs": assertions_override,
        "extractor_specs": list(serialize_extractor_specs(test_case.request)) + list(serialize_extractor_specs(test_case)),
        "execution_mode": execution_mode,
        "missing_variables": [],
        "main_request_blocked": True,
        "stage_results": [],
    }
    request_snapshot.update(snapshot_extra)
    return ApiExecutionRecord.objects.create(
        project=test_case.project,
        request=test_case.request,
        test_case=test_case,
        environment=environment,
        run_id=run_id,
        run_name=run_name,
        request_name=request_name,
        method=request_snapshot["method"],
        url=request_snapshot["url"],
        status=status_value,
        passed=False,
        status_code=None,
        response_time=None,
        request_snapshot=request_snapshot,
        response_snapshot={},
        assertions_results=[],
        error_message=error_message,
        executor=executor,
    )


def _execute_workflow_step(
    *,
    step: dict,
    test_case: ApiTestCase,
    executor,
    environment: ApiEnvironment | None,
    run_id: str,
    run_name: str,
    runtime_context: dict,
    execution_mode: str,
):
    if step.get("lookup_error"):
        return _serialize_workflow_step_result(
            step,
            status="error",
            error_message=str(step.get("lookup_error") or ""),
        )

    request_obj = step.get("request")
    if not request_obj:
        return _serialize_workflow_step_result(step, status="error", error_message="Workflow step has no valid request binding")

    record = _execute_api_request(
        api_request=request_obj,
        executor=executor,
        environment=environment,
        run_id=run_id,
        run_name=run_name,
        request_name=f"[Workflow][{WORKFLOW_STAGE_LABELS.get(step['stage'], 'Prepare')}] {step['name']}",
        override_payload=step.get("request_overrides"),
        snapshot_extra={
            "workflow_step": {
                "index": step["index"],
                "name": step["name"],
                "stage": step["stage"],
                "continue_on_failure": step["continue_on_failure"],
                "source_test_case_id": test_case.id,
                "source_test_case_name": test_case.name,
            },
            "workflow_source_test_case_id": test_case.id,
            "workflow_source_test_case_name": test_case.name,
        },
        assertions_override=step.get("assertions_override"),
        extractors_override=step.get("extractors_override"),
        runtime_context=runtime_context,
        execution_mode=execution_mode,
    )
    return _serialize_workflow_step_result(step, record)


def _build_test_case_execution_payload(test_case: ApiTestCase):
    if not getattr(test_case, "override_spec", None):
        backfill_test_case_specs_from_legacy(test_case)

    script = test_case.script if isinstance(test_case.script, dict) else {}
    overrides = serialize_test_case_override(test_case)
    assertions = serialize_assertion_specs(test_case) or serialize_assertion_specs(test_case.request)
    snapshot_extra = {
        "request_id": test_case.request_id,
        "interface_name": test_case.request.name,
        "collection_id": test_case.request.collection_id,
        "collection_name": test_case.request.collection.name,
        "test_case_id": test_case.id,
        "test_case_name": test_case.name,
        "test_case_status": test_case.status,
        "test_case_tags": test_case.tags or [],
        "test_case_script": script,
    }
    return overrides, assertions, snapshot_extra, _parse_test_case_workflow_steps(test_case)


def _execute_test_case(
    *,
    test_case: ApiTestCase,
    executor,
    environment: ApiEnvironment | None = None,
    run_id: str | None = None,
    run_name: str | None = None,
    request_name: str | None = None,
    runtime_context: dict | None = None,
    execution_mode: str = "sync",
):
    shared_runtime_context = runtime_context is not None
    runtime_context = runtime_context if runtime_context is not None else {}
    overrides, assertions, snapshot_extra, workflow_steps = _build_test_case_execution_payload(test_case)

    if not workflow_steps:
        return _execute_api_request(
            api_request=test_case.request,
            executor=executor,
            environment=environment,
            test_case=test_case,
            run_id=run_id,
            run_name=run_name,
            request_name=request_name or test_case.name,
            override_payload=overrides,
            snapshot_extra=snapshot_extra,
            assertions_override=assertions,
            runtime_context=runtime_context,
            execution_mode=execution_mode,
        )

    created_local_context = False
    if "_execution_run_context" not in runtime_context:
        runtime_context["_execution_run_context"] = ExecutionRunContext(
            run_id=run_id or uuid4().hex,
            run_name=run_name or "",
            environment=environment,
            execution_mode=execution_mode,
        )
        runtime_context["_execution_run_context"].variables.update(runtime_context.get("variables", {}))
        created_local_context = True

    run_execution_context = runtime_context["_execution_run_context"]
    if run_id:
        run_execution_context.run_id = run_id
    if run_name:
        run_execution_context.run_name = run_name
    if environment and run_execution_context.environment is None:
        run_execution_context.environment = environment
    run_execution_context.execution_mode = execution_mode or run_execution_context.execution_mode
    runtime_context["variables"] = dict(run_execution_context.variables)

    main_record = None
    workflow_results = []
    blocking_failure = None
    pre_main_steps = [item for item in workflow_steps if item["stage"] in {"prepare", "request"}]
    teardown_steps = [item for item in workflow_steps if item["stage"] == "teardown"]

    try:
        for step in pre_main_steps:
            step_result = _execute_workflow_step(
                step=step,
                test_case=test_case,
                executor=executor,
                environment=environment,
                run_id=run_execution_context.run_id or run_id or "",
                run_name=run_execution_context.run_name or run_name or "",
                runtime_context=runtime_context,
                execution_mode=execution_mode,
            )
            workflow_results.append(step_result)
            if _is_workflow_failure(step_result) and not step["continue_on_failure"]:
                blocking_failure = step_result
                break

        if blocking_failure is None:
            main_record = _execute_api_request(
                api_request=test_case.request,
                executor=executor,
                environment=environment,
                test_case=test_case,
                run_id=run_execution_context.run_id or run_id,
                run_name=run_execution_context.run_name or run_name,
                request_name=request_name or test_case.name,
                override_payload=overrides,
                snapshot_extra=snapshot_extra,
                assertions_override=assertions,
                runtime_context=runtime_context,
                execution_mode=execution_mode,
            )
        else:
            blocked_status = "error" if blocking_failure["status"] == "error" else "failed"
            blocked_message = _format_workflow_failure_message(blocking_failure)
            main_record = _build_test_case_blocked_record(
                test_case=test_case,
                executor=executor,
                environment=environment,
                run_id=run_execution_context.run_id or run_id or "",
                run_name=run_execution_context.run_name or run_name or "",
                request_name=request_name or test_case.name,
                execution_mode=execution_mode,
                override_payload=overrides,
                assertions_override=assertions,
                snapshot_extra=snapshot_extra,
                status_value=blocked_status,
                error_message=blocked_message,
            )

        workflow_results.append(
            _serialize_workflow_step_result(
                {
                    "kind": "main_request",
                    "index": len(workflow_results) + 1,
                    "name": test_case.name,
                    "stage": "request",
                    "request_id": test_case.request_id,
                    "request_name": test_case.request.name,
                    "continue_on_failure": False,
                },
                main_record,
            )
        )

        for step in teardown_steps:
            step_result = _execute_workflow_step(
                step=step,
                test_case=test_case,
                executor=executor,
                environment=environment,
                run_id=run_execution_context.run_id or run_id or "",
                run_name=run_execution_context.run_name or run_name or "",
                runtime_context=runtime_context,
                execution_mode=execution_mode,
            )
            workflow_results.append(step_result)
            if _is_workflow_failure(step_result) and not step["continue_on_failure"]:
                break

        all_failures = [item for item in workflow_results if _is_workflow_failure(item)]
        auxiliary_failures = [item for item in all_failures if item.get("kind") != "main_request"]
        final_status = main_record.status
        if any(item["status"] == "error" for item in all_failures):
            final_status = "error"
        elif any(item["status"] == "failed" for item in all_failures):
            final_status = "failed"
        final_passed = final_status == "success" and bool(main_record.passed)

        final_error_message = main_record.error_message or ""
        if auxiliary_failures and (main_record.status == "success" or not final_error_message or final_status == "error"):
            final_error_message = _format_workflow_failure_message(auxiliary_failures[0])

        request_snapshot = dict(main_record.request_snapshot or {})
        request_snapshot["workflow_steps"] = workflow_results
        request_snapshot["workflow_summary"] = {
            "enabled": True,
            "configured_step_count": len(workflow_steps),
            "executed_step_count": len(workflow_results),
            "failure_count": len(all_failures),
            "has_failure": bool(all_failures),
            "main_request_executed": not bool(request_snapshot.get("main_request_blocked")),
            "main_record_id": main_record.id,
        }

        updated_assertions_results = list(main_record.assertions_results or [])
        updated_assertions_results.extend(
            _build_workflow_step_failure_assertions(workflow_results, len(updated_assertions_results) + 1)
        )

        update_fields = ["request_snapshot", "assertions_results", "status", "passed", "error_message"]
        main_record.request_snapshot = request_snapshot
        main_record.assertions_results = updated_assertions_results
        main_record.status = final_status
        main_record.passed = final_passed
        main_record.error_message = final_error_message
        main_record.save(update_fields=update_fields)
        runtime_context["variables"] = dict(run_execution_context.variables)
        return main_record
    finally:
        if created_local_context and not shared_runtime_context:
            run_execution_context.close()
            runtime_context.pop("_execution_run_context", None)


def _serialize_generation_case_items(test_cases: list[ApiTestCase]):
    serializer = ApiTestCaseSerializer(test_cases, many=True)
    return serializer.data


def _build_case_replacement_summary(
    existing_case_summaries: list[dict],
    proposed_case_summaries: list[dict],
) -> dict[str, object]:
    existing_names = [str(item.get("name") or "").strip() for item in existing_case_summaries if str(item.get("name") or "").strip()]
    proposed_names = [str(item.get("name") or "").strip() for item in proposed_case_summaries if str(item.get("name") or "").strip()]
    existing_name_set = set(existing_names)
    proposed_name_set = set(proposed_names)
    removed_case_names = [name for name in existing_names if name not in proposed_name_set]
    added_case_names = [name for name in proposed_names if name not in existing_name_set]
    unchanged_case_names = [name for name in proposed_names if name in existing_name_set]
    return {
        "existing_count": len(existing_case_summaries),
        "proposed_count": len(proposed_case_summaries),
        "will_remove_count": len(existing_case_summaries),
        "will_create_count": len(proposed_case_summaries),
        "removed_case_names": removed_case_names,
        "added_case_names": added_case_names,
        "unchanged_case_names": unchanged_case_names,
    }


def _serialize_generated_case_draft(draft: GeneratedCaseDraft) -> dict[str, object]:
    return {
        "name": draft.name,
        "description": draft.description,
        "status": draft.status,
        "tags": list(draft.tags),
        "assertions": list(draft.assertions),
        "extractors": list(draft.extractors),
        "request_overrides": dict(draft.request_overrides),
    }


def _deserialize_generated_case_draft(payload: dict) -> GeneratedCaseDraft:
    return GeneratedCaseDraft(
        name=str(payload.get("name") or "").strip(),
        description=str(payload.get("description") or ""),
        status=str(payload.get("status") or "draft"),
        tags=[str(tag).strip() for tag in (payload.get("tags") or []) if str(tag).strip()],
        assertions=list(payload.get("assertions") or []),
        extractors=list(payload.get("extractors") or []),
        request_overrides=dict(payload.get("request_overrides") or {}),
    )


def _build_case_generation_summary(*, scope: str, mode: str, items: list[dict]) -> dict[str, object]:
    skipped_count = sum(1 for item in items if item.get("skipped"))
    created_total = sum(int(item.get("created_count") or 0) for item in items)
    ai_used_count = sum(1 for item in items if item.get("ai_used"))
    ai_cache_hit_count = sum(1 for item in items if item.get("ai_cache_hit"))
    preview_only_count = sum(1 for item in items if item.get("preview_only"))
    notes = [str(item.get("note") or "").strip() for item in items if str(item.get("note") or "").strip()]
    return {
        "scope": scope,
        "mode": mode,
        "total_requests": len(items),
        "processed_requests": len(items) - skipped_count,
        "skipped_requests": skipped_count,
        "created_testcase_count": created_total,
        "ai_used_count": ai_used_count,
        "ai_cache_hit_count": ai_cache_hit_count,
        "preview_only": bool(preview_only_count),
        "requires_confirmation": bool(preview_only_count),
        "preview_request_count": preview_only_count,
        "note": " ".join(notes[:5]),
        "items": items,
    }


def _prepare_request_test_case_generation(
    *,
    api_request: ApiRequest,
    user,
    mode: str,
    count_per_request: int,
) -> dict[str, object]:
    existing_cases = list(api_request.test_cases.order_by("created_at"))
    if mode == "generate" and existing_cases:
        public_item = {
            "request_id": api_request.id,
            "request_name": api_request.name,
            "request_method": api_request.method,
            "request_url": api_request.url,
            "mode": mode,
            "skipped": True,
            "skipped_reason": "当前接口已存在测试用例，请使用重新生成或追加生成。",
            "created_count": 0,
            "ai_used": False,
            "ai_cache_hit": False,
            "ai_cache_key": None,
            "ai_duration_ms": None,
            "ai_lock_wait_ms": None,
            "note": "已跳过已有测试用例的接口。",
            "case_summaries": [],
            "items": [],
        }
        return {
            "public_item": public_item,
            "draft_item": {
                "request_id": api_request.id,
                "skipped": True,
                "mode": mode,
                "drafts": [],
            },
        }

    generation_result = generate_test_case_drafts_with_ai(
        api_request=api_request,
        user=user,
        existing_cases=existing_cases,
        mode=mode,
        count=count_per_request,
    )
    existing_case_summaries = summarize_persisted_test_cases(api_request, existing_cases)
    proposed_case_summaries = generation_result.case_summaries
    replacement_summary = _build_case_replacement_summary(existing_case_summaries, proposed_case_summaries)
    preview_only = mode == "regenerate"
    public_item = {
        "request_id": api_request.id,
        "request_name": api_request.name,
        "request_method": api_request.method,
        "request_url": api_request.url,
        "mode": mode,
        "skipped": False,
        "preview_only": preview_only,
        "requires_confirmation": preview_only,
        "created_count": 0,
        "ai_used": generation_result.used_ai,
        "ai_cache_hit": generation_result.cache_hit,
        "ai_cache_key": generation_result.cache_key,
        "ai_duration_ms": generation_result.duration_ms,
        "ai_lock_wait_ms": generation_result.lock_wait_ms,
        "note": generation_result.note,
        "prompt_name": generation_result.prompt_name,
        "prompt_source": generation_result.prompt_source,
        "model_name": generation_result.model_name,
        "case_summaries": proposed_case_summaries,
        "existing_case_summaries": existing_case_summaries if preview_only else [],
        "proposed_case_summaries": proposed_case_summaries,
        "replacement_summary": replacement_summary if mode == "regenerate" else None,
        "items": [],
    }
    draft_item = {
        "request_id": api_request.id,
        "request_name": api_request.name,
        "request_method": api_request.method,
        "request_url": api_request.url,
        "mode": mode,
        "skipped": False,
        "preview_only": preview_only,
        "ai_used": generation_result.used_ai,
        "ai_cache_hit": generation_result.cache_hit,
        "ai_cache_key": generation_result.cache_key,
        "ai_duration_ms": generation_result.duration_ms,
        "ai_lock_wait_ms": generation_result.lock_wait_ms,
        "note": generation_result.note,
        "prompt_name": generation_result.prompt_name,
        "prompt_source": generation_result.prompt_source,
        "model_name": generation_result.model_name,
        "case_summaries": proposed_case_summaries,
        "existing_case_summaries": existing_case_summaries,
        "proposed_case_summaries": proposed_case_summaries,
        "replacement_summary": replacement_summary if mode == "regenerate" else None,
        "drafts": [_serialize_generated_case_draft(draft) for draft in generation_result.cases],
    }
    return {
        "public_item": public_item,
        "draft_item": draft_item,
    }


def _apply_request_test_case_generation_from_drafts(
    *,
    api_request: ApiRequest,
    creator,
    mode: str,
    draft_item: dict,
) -> dict[str, object]:
    existing_cases = list(api_request.test_cases.order_by("created_at"))
    serialized_drafts = [item for item in (draft_item.get("drafts") or []) if isinstance(item, dict)]
    drafts = [_deserialize_generated_case_draft(item) for item in serialized_drafts]
    if mode == "regenerate" and existing_cases:
        ApiTestCase.objects.filter(id__in=[item.id for item in existing_cases]).delete()
        existing_cases = []

    created_cases = create_test_cases_from_drafts(
        api_request=api_request,
        drafts=drafts,
        creator=creator,
    )
    return {
        "request_id": api_request.id,
        "request_name": api_request.name,
        "request_method": api_request.method,
        "request_url": api_request.url,
        "mode": mode,
        "skipped": False,
        "preview_only": False,
        "requires_confirmation": False,
        "created_count": len(created_cases),
        "ai_used": bool(draft_item.get("ai_used")),
        "ai_cache_hit": bool(draft_item.get("ai_cache_hit")),
        "ai_cache_key": draft_item.get("ai_cache_key"),
        "ai_duration_ms": draft_item.get("ai_duration_ms"),
        "ai_lock_wait_ms": draft_item.get("ai_lock_wait_ms"),
        "note": draft_item.get("note"),
        "prompt_name": draft_item.get("prompt_name"),
        "prompt_source": draft_item.get("prompt_source"),
        "model_name": draft_item.get("model_name"),
        "case_summaries": list(draft_item.get("proposed_case_summaries") or draft_item.get("case_summaries") or []),
        "existing_case_summaries": list(draft_item.get("existing_case_summaries") or []) if mode == "regenerate" else [],
        "proposed_case_summaries": list(draft_item.get("proposed_case_summaries") or draft_item.get("case_summaries") or []),
        "replacement_summary": draft_item.get("replacement_summary") if mode == "regenerate" else None,
        "items": _serialize_generation_case_items(created_cases),
    }


def _generate_request_test_cases(
    *,
    api_request: ApiRequest,
    user,
    mode: str,
    count_per_request: int,
    apply_changes: bool = False,
):
    existing_cases = list(api_request.test_cases.order_by("created_at"))
    if mode == "generate" and existing_cases:
        return {
            "request_id": api_request.id,
            "request_name": api_request.name,
            "request_method": api_request.method,
            "request_url": api_request.url,
            "mode": mode,
            "skipped": True,
            "skipped_reason": "当前接口已存在测试用例，请使用重新生成或追加生成。",
            "created_count": 0,
            "ai_used": False,
            "ai_cache_hit": False,
            "ai_cache_key": None,
            "ai_duration_ms": None,
            "ai_lock_wait_ms": None,
            "note": "已跳过已有测试用例的接口。",
            "case_summaries": [],
            "items": [],
        }

    generation_result = generate_test_case_drafts_with_ai(
        api_request=api_request,
        user=user,
        existing_cases=existing_cases,
        mode=mode,
        count=count_per_request,
    )

    existing_case_summaries = summarize_persisted_test_cases(api_request, existing_cases)
    proposed_case_summaries = generation_result.case_summaries
    replacement_summary = _build_case_replacement_summary(existing_case_summaries, proposed_case_summaries)

    if mode == "regenerate" and not apply_changes:
        return {
            "request_id": api_request.id,
            "request_name": api_request.name,
            "request_method": api_request.method,
            "request_url": api_request.url,
            "mode": mode,
            "skipped": False,
            "preview_only": True,
            "requires_confirmation": True,
            "created_count": 0,
            "ai_used": generation_result.used_ai,
            "ai_cache_hit": generation_result.cache_hit,
            "ai_cache_key": generation_result.cache_key,
            "ai_duration_ms": generation_result.duration_ms,
            "ai_lock_wait_ms": generation_result.lock_wait_ms,
            "note": generation_result.note,
            "prompt_name": generation_result.prompt_name,
            "prompt_source": generation_result.prompt_source,
            "model_name": generation_result.model_name,
            "case_summaries": proposed_case_summaries,
            "existing_case_summaries": existing_case_summaries,
            "proposed_case_summaries": proposed_case_summaries,
            "replacement_summary": replacement_summary,
            "items": [],
        }

    if mode == "regenerate" and existing_cases:
        ApiTestCase.objects.filter(id__in=[item.id for item in existing_cases]).delete()
        existing_cases = []

    created_cases = create_test_cases_from_drafts(
        api_request=api_request,
        drafts=generation_result.cases,
        creator=user,
    )
    return {
        "request_id": api_request.id,
        "request_name": api_request.name,
        "request_method": api_request.method,
        "request_url": api_request.url,
        "mode": mode,
        "skipped": False,
        "preview_only": False,
        "requires_confirmation": False,
        "created_count": len(created_cases),
        "ai_used": generation_result.used_ai,
        "ai_cache_hit": generation_result.cache_hit,
        "ai_cache_key": generation_result.cache_key,
        "ai_duration_ms": generation_result.duration_ms,
        "ai_lock_wait_ms": generation_result.lock_wait_ms,
        "note": generation_result.note,
        "prompt_name": generation_result.prompt_name,
        "prompt_source": generation_result.prompt_source,
        "model_name": generation_result.model_name,
        "case_summaries": proposed_case_summaries,
        "existing_case_summaries": existing_case_summaries if mode == "regenerate" else [],
        "proposed_case_summaries": proposed_case_summaries,
        "replacement_summary": replacement_summary if mode == "regenerate" else None,
        "items": _serialize_generation_case_items(created_cases),
    }


class ApiCollectionViewSet(BaseModelViewSet):
    queryset = ApiCollection.objects.select_related("project", "parent", "creator")
    serializer_class = ApiCollectionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["order", "created_at", "name"]
    ordering = ["order", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        project_id = self.request.query_params.get("project")
        parent_id = self.request.query_params.get("parent")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if parent_id is not None:
            queryset = queryset.filter(parent_id=parent_id or None)
        return queryset

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response({"error": "project 参数必填"}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(project_id=project_id, parent__isnull=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ApiImportJobViewSet(BaseModelViewSet):
    queryset = ApiImportJob.objects.select_related("project", "collection", "creator")
    serializer_class = ApiImportJobSerializer
    http_method_names = ["get", "post", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["source_name", "progress_message", "error_message"]
    ordering_fields = ["created_at", "updated_at", "completed_at", "progress_percent"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        if not self.request.user.is_superuser:
            queryset = queryset.filter(creator=self.request.user)

        project_id = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.status in {"success", "failed", "canceled"}:
            serializer = self.get_serializer(job)
            return Response(serializer.data)

        update_fields = {
            "cancel_requested": True,
            "progress_message": "已收到暂停解析请求，正在终止任务。",
        }
        if job.status == "pending":
            update_fields.update(
                {
                    "status": "canceled",
                    "progress_stage": "canceled",
                    "progress_percent": min(job.progress_percent or 0, 100),
                    "progress_message": "文档解析任务已暂停。",
                    "completed_at": timezone.now(),
                }
            )

        _save_job(job.id, force=True, **update_fields)
        serializer = self.get_serializer(ApiImportJob.objects.get(pk=job.id))
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def restart(self, request, pk=None):
        job = self.get_object()
        if job.status not in {"failed", "canceled"}:
            return Response({"error": "仅已暂停或失败的解析任务支持重启"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            _resolve_import_job_source_path(job)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        _save_job(
            job.id,
            force=True,
            status="pending",
            progress_percent=4,
            progress_stage="uploaded",
            progress_message="文档已重新入队，正在准备再次解析。",
            cancel_requested=False,
            result_payload={},
            error_message="",
            completed_at=None,
        )
        _start_import_job(job.id)
        serializer = self.get_serializer(ApiImportJob.objects.get(pk=job.id))
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        job = self.get_object()
        if job.status in {"pending", "running"} or job.cancel_requested:
            return Response({"error": "任务仍在执行中，请先暂停并等待任务停止后再关闭"}, status=status.HTTP_400_BAD_REQUEST)

        job_id = job.id
        _delete_import_job_source_file(job)
        job.delete()
        return Response({"id": job_id, "closed": True})


class ApiCaseGenerationJobViewSet(BaseModelViewSet):
    queryset = ApiCaseGenerationJob.objects.select_related("project", "collection", "creator")
    serializer_class = ApiCaseGenerationJobSerializer
    http_method_names = ["get", "post", "head", "options"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["progress_message", "error_message"]
    ordering_fields = ["created_at", "updated_at", "completed_at", "progress_percent"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        if not self.request.user.is_superuser:
            queryset = queryset.filter(creator=self.request.user)

        project_id = self.request.query_params.get("project")
        status_value = self.request.query_params.get("status")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset

    def create(self, request, *args, **kwargs):
        scope = str(request.data.get("scope") or "selected").strip().lower()
        ids = request.data.get("ids") or []
        project_id = request.data.get("project_id")
        collection_id = request.data.get("collection_id")
        mode = str(request.data.get("mode") or "generate").strip().lower()
        count_per_request = max(1, min(int(request.data.get("count_per_request") or 3), 10))

        if mode not in {"generate", "append", "regenerate"}:
            return Response({"error": "mode 仅支持 generate、append、regenerate"}, status=status.HTTP_400_BAD_REQUEST)

        api_requests = _collect_request_scope(
            request.user,
            scope,
            project_id=project_id,
            collection_id=collection_id,
            ids=ids,
        )
        if not api_requests:
            return Response({"error": "未找到可生成测试用例的接口"}, status=status.HTTP_400_BAD_REQUEST)

        project_ids = {item.collection.project_id for item in api_requests}
        if len(project_ids) != 1:
            return Response({"error": "一次仅支持在同一个项目内生成测试用例"}, status=status.HTTP_400_BAD_REQUEST)

        selected_collection = None
        if collection_id:
            selected_collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(request.user),
            ).first()

        job = ApiCaseGenerationJob.objects.create(
            project=api_requests[0].collection.project,
            collection=selected_collection,
            creator=request.user,
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
        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.status in {"success", "failed", "canceled"}:
            serializer = self.get_serializer(job)
            return Response(serializer.data)

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
        serializer = self.get_serializer(ApiCaseGenerationJob.objects.get(pk=job.id))
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        job = self.get_object()
        if job.status != "preview_ready":
            return Response({"error": "当前任务没有可应用的预览结果"}, status=status.HTTP_400_BAD_REQUEST)

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
        serializer = self.get_serializer(ApiCaseGenerationJob.objects.get(pk=job.id))
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class ApiRequestViewSet(BaseModelViewSet):
    queryset = ApiRequest.objects.select_related("collection", "collection__project", "created_by")
    serializer_class = ApiRequestSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "url", "description"]
    ordering_fields = ["order", "created_at", "updated_at", "name"]
    ordering = ["order", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(collection__project__in=get_accessible_projects(self.request.user))
        project_id = self.request.query_params.get("project")
        collection_id = self.request.query_params.get("collection")
        method = self.request.query_params.get("method")
        if project_id:
            queryset = queryset.filter(collection__project_id=project_id)
        if collection_id:
            root_collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(self.request.user),
            ).first()
            if root_collection:
                queryset = queryset.filter(collection_id__in=collect_collection_ids(root_collection))
            else:
                queryset = queryset.none()
        if method:
            queryset = queryset.filter(method=method.upper())
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        collection_id = request.data.get("collection")
        method = str(request.data.get("method") or "").upper().strip()
        url = str(request.data.get("url") or "").strip()
        if collection_id and method and url:
            collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(request.user),
            ).first()
            if collection:
                existing = (
                    ApiRequest.objects.filter(
                        collection__project=collection.project,
                        method=method,
                        url=url,
                    )
                    .select_related("collection", "collection__project", "created_by")
                    .first()
                )
                if existing:
                    serializer = self.get_serializer(existing)
                    return Response(serializer.data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser], url_path="import-document")
    def import_document(self, request):
        file = request.FILES.get("file")
        collection_id = request.data.get("collection_id")

        if not file:
            return Response({"error": "请上传接口文档文件"}, status=status.HTTP_400_BAD_REQUEST)
        if not collection_id:
            return Response({"error": "collection_id 参数必填"}, status=status.HTTP_400_BAD_REQUEST)

        collection = get_object_or_404(
            ApiCollection.objects.filter(project__in=get_accessible_projects(request.user)),
            pk=collection_id,
        )
        generate_test_cases = str(request.data.get("generate_test_cases", "true")).lower() in {"1", "true", "yes", "on"}
        enable_ai_parse = str(request.data.get("enable_ai_parse", "true")).lower() in {"1", "true", "yes", "on"}
        async_mode = str(request.data.get("async_mode", "true")).lower() in {"1", "true", "yes", "on"}

        if async_mode:
            job = ApiImportJob.objects.create(
                project=collection.project,
                collection=collection,
                creator=request.user,
                source_name=file.name,
                source_file=file,
                status="pending",
                progress_percent=4,
                progress_stage="uploaded",
                progress_message="文档已上传，正在进入后台解析队列。",
                generate_test_cases=generate_test_cases,
                enable_ai_parse=enable_ai_parse,
            )
            _start_import_job(job.id)
            serializer = ApiImportJobSerializer(job)
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

        suffix = Path(file.name).suffix or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            payload = process_document_import(
                collection=collection,
                user=request.user,
                file_path=temp_path,
                generate_test_cases=generate_test_cases,
                enable_ai_parse=enable_ai_parse,
            )
            return Response(payload, status=status.HTTP_201_CREATED)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        api_request = self.get_object()
        environment = _resolve_execution_environment(api_request.collection.project, request.data.get("environment_id"))
        run_id = uuid4().hex
        run_name = _build_run_name("request", "single", api_request.name)
        execution_mode = _resolve_execution_mode(request.data)
        record = _execute_api_request(
            api_request=api_request,
            executor=request.user,
            environment=environment,
            run_id=run_id,
            run_name=run_name,
            execution_mode=execution_mode,
        )
        serializer = ApiExecutionRecordSerializer(record)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="execute-batch")
    def execute_batch(self, request):
        scope = str(request.data.get("scope") or "selected")
        ids = request.data.get("ids") or []
        project_id = request.data.get("project_id")
        collection_id = request.data.get("collection_id")
        environment_id = request.data.get("environment_id")
        execution_mode = _resolve_execution_mode(request.data)

        api_requests = _collect_request_scope(
            request.user,
            scope,
            project_id=project_id,
            collection_id=collection_id,
            ids=ids,
        )
        if not api_requests:
            return Response({"error": "未找到可执行的接口脚本"}, status=status.HTTP_400_BAD_REQUEST)

        records = []
        runtime_context = {}
        run_id = uuid4().hex
        run_name = _build_run_name("request", scope)
        try:
            for api_request in api_requests:
                environment = _resolve_execution_environment(api_request.collection.project, environment_id)
                records.append(
                    _execute_api_request(
                        api_request=api_request,
                        executor=request.user,
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
        return Response(_serialize_execution_batch(records))

    @action(detail=False, methods=["post"], url_path="generate-test-cases")
    def generate_test_cases(self, request):
        scope = str(request.data.get("scope") or "selected")
        ids = request.data.get("ids") or []
        project_id = request.data.get("project_id")
        collection_id = request.data.get("collection_id")
        mode = str(request.data.get("mode") or "generate").strip().lower()
        count_per_request = max(1, min(int(request.data.get("count_per_request") or 3), 10))
        apply_changes = bool(_coerce_bool(request.data.get("apply_changes"), False))

        if mode not in {"generate", "append", "regenerate"}:
            return Response({"error": "mode 仅支持 generate、append、regenerate"}, status=status.HTTP_400_BAD_REQUEST)

        api_requests = _collect_request_scope(
            request.user,
            scope,
            project_id=project_id,
            collection_id=collection_id,
            ids=ids,
        )
        if not api_requests:
            return Response({"error": "未找到可生成测试用例的接口"}, status=status.HTTP_400_BAD_REQUEST)

        items = []
        created_total = 0
        skipped_count = 0
        ai_used_count = 0
        ai_cache_hit_count = 0
        preview_only_count = 0
        notes: list[str] = []

        for api_request in api_requests:
            item = _generate_request_test_cases(
                api_request=api_request,
                user=request.user,
                mode=mode,
                count_per_request=count_per_request,
                apply_changes=apply_changes,
            )
            items.append(item)
            created_total += item["created_count"]
            skipped_count += 1 if item.get("skipped") else 0
            ai_used_count += 1 if item.get("ai_used") else 0
            ai_cache_hit_count += 1 if item.get("ai_cache_hit") else 0
            preview_only_count += 1 if item.get("preview_only") else 0
            if item.get("note"):
                notes.append(str(item["note"]))

        return Response(
            {
                "scope": scope,
                "mode": mode,
                "total_requests": len(api_requests),
                "processed_requests": len(api_requests) - skipped_count,
                "skipped_requests": skipped_count,
                "created_testcase_count": created_total,
                "ai_used_count": ai_used_count,
                "ai_cache_hit_count": ai_cache_hit_count,
                "preview_only": bool(preview_only_count),
                "requires_confirmation": bool(preview_only_count),
                "preview_request_count": preview_only_count,
                "note": " ".join(notes[:5]),
                "items": items,
            }
        )


class ApiEnvironmentViewSet(BaseModelViewSet):
    queryset = ApiEnvironment.objects.select_related("project", "creator")
    serializer_class = ApiEnvironmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "base_url"]
    ordering_fields = ["created_at", "updated_at", "name"]
    ordering = ["-is_default", "name"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class ApiExecutionRecordViewSet(BaseModelViewSet):
    queryset = ApiExecutionRecord.objects.select_related(
        "project",
        "request",
        "request__collection",
        "test_case",
        "environment",
        "executor",
    )
    serializer_class = ApiExecutionRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["request_name", "url", "error_message"]
    ordering_fields = ["created_at", "response_time", "status_code"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        project_id = self.request.query_params.get("project")
        request_id = self.request.query_params.get("request")
        collection_id = self.request.query_params.get("collection")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        if collection_id:
            root_collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(self.request.user),
            ).first()
            if root_collection:
                queryset = queryset.filter(request__collection_id__in=collect_collection_ids(root_collection))
            else:
                queryset = queryset.none()
        return queryset

    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request):
        queryset = self.get_queryset()
        days = request.query_params.get("days")
        if days:
            try:
                days_value = max(1, min(int(days), 90))
                since = timezone.now() - timedelta(days=days_value)
                queryset = queryset.filter(created_at__gte=since)
            except ValueError:
                return Response({"error": "days 参数必须是 1-90 之间的整数"}, status=status.HTTP_400_BAD_REQUEST)

        total_count = queryset.count()
        aggregate = queryset.aggregate(
            success_count=Count("id", filter=Q(status="success")),
            failed_count=Count("id", filter=Q(status="failed")),
            error_count=Count("id", filter=Q(status="error")),
            passed_count=Count("id", filter=Q(passed=True)),
            avg_response_time=Avg("response_time"),
            latest_executed_at=Max("created_at"),
        )

        method_breakdown = list(
            queryset.values("method")
            .annotate(
                total=Count("id"),
                passed=Count("id", filter=Q(passed=True)),
                failed=Count("id", filter=Q(status="failed")),
                error=Count("id", filter=Q(status="error")),
                avg_response_time=Avg("response_time"),
            )
            .order_by("method")
        )

        collection_breakdown = list(
            queryset.values("request__collection__name")
            .annotate(
                total=Count("id"),
                passed=Count("id", filter=Q(passed=True)),
                failed=Count("id", filter=Q(status="failed")),
                error=Count("id", filter=Q(status="error")),
            )
            .order_by("-total", "request__collection__name")
        )

        failing_requests = list(
            queryset.filter(passed=False)
            .values("request_id", "request__name", "request__collection__name")
            .annotate(
                total=Count("id"),
                latest_executed_at=Max("created_at"),
                latest_status_code=Max("status_code"),
            )
            .order_by("-total", "request__name")[:10]
        )

        trend = list(
            queryset.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                total=Count("id"),
                passed=Count("id", filter=Q(passed=True)),
                failed=Count("id", filter=Q(status="failed")),
                error=Count("id", filter=Q(status="error")),
            )
            .order_by("day")
        )

        recent_records = queryset.order_by("-created_at")[:10]
        recent_records_payload = ApiExecutionRecordSerializer(recent_records, many=True).data
        run_groups, hierarchy_summary = _build_report_run_groups(queryset)

        pass_rate = round(((aggregate["passed_count"] or 0) / total_count) * 100, 2) if total_count else 0

        return Response(
            {
                "summary": {
                    "total_count": total_count,
                    "success_count": aggregate["success_count"] or 0,
                    "failed_count": aggregate["failed_count"] or 0,
                    "error_count": aggregate["error_count"] or 0,
                    "passed_count": aggregate["passed_count"] or 0,
                    "pass_rate": pass_rate,
                    "avg_response_time": round(float(aggregate["avg_response_time"] or 0), 2) if aggregate["avg_response_time"] else None,
                    "latest_executed_at": aggregate["latest_executed_at"],
                },
                "method_breakdown": method_breakdown,
                "collection_breakdown": collection_breakdown,
                "failing_requests": [
                    {
                        "request_id": item["request_id"],
                        "request_name": item["request__name"] or "未命名接口",
                        "request__collection__name": item["request__collection__name"],
                        "total": item["total"],
                        "latest_executed_at": item["latest_executed_at"],
                        "latest_status_code": item["latest_status_code"],
                    }
                    for item in failing_requests
                ],
                "trend": trend,
                "recent_records": recent_records_payload,
                "run_groups": run_groups,
                "hierarchy_summary": hierarchy_summary,
            }
        )

    @action(detail=False, methods=["post"], url_path="report-summary")
    def report_summary(self, request):
        queryset = self.get_queryset()
        project_id = request.data.get("project")
        request_id = request.data.get("request")
        collection_id = request.data.get("collection")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        if collection_id:
            root_collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(request.user),
            ).first()
            if root_collection:
                queryset = queryset.filter(request__collection_id__in=collect_collection_ids(root_collection))
            else:
                queryset = queryset.none()

        queryset, error_payload = _apply_report_days_filter(queryset, request.data.get("days"))
        if error_payload:
            return Response(error_payload, status=status.HTTP_400_BAD_REQUEST)

        report_payload = _build_execution_report_payload(queryset)
        result = summarize_execution_report(report_payload=report_payload, user=request.user)
        return Response(
            {
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
        )

    @action(detail=True, methods=["post"], url_path="analyze-failure")
    def analyze_failure(self, request, pk=None):
        record = self.get_object()
        result = analyze_execution_failure(record=record, user=request.user)
        return Response(
            {
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
        )


class ApiTestCaseViewSet(BaseModelViewSet):
    queryset = ApiTestCase.objects.select_related("project", "request", "request__collection", "creator")
    serializer_class = ApiTestCaseSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(project__in=get_accessible_projects(self.request.user))
        project_id = self.request.query_params.get("project")
        request_id = self.request.query_params.get("request")
        collection_id = self.request.query_params.get("collection")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        if collection_id:
            root_collection = ApiCollection.objects.filter(
                pk=collection_id,
                project__in=get_accessible_projects(self.request.user),
            ).first()
            if root_collection:
                queryset = queryset.filter(request__collection_id__in=collect_collection_ids(root_collection))
            else:
                queryset = queryset.none()
        return queryset

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        test_case = self.get_object()
        environment = _resolve_execution_environment(test_case.project, request.data.get("environment_id"))
        run_id = uuid4().hex
        run_name = _build_run_name("test_case", "single", test_case.name)
        execution_mode = _resolve_execution_mode(request.data)
        record = _execute_test_case(
            test_case=test_case,
            executor=request.user,
            environment=environment,
            run_id=run_id,
            run_name=run_name,
            request_name=test_case.name,
            execution_mode=execution_mode,
        )
        serializer = ApiExecutionRecordSerializer(record)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="execute-batch")
    def execute_batch(self, request):
        scope = str(request.data.get("scope") or "selected")
        ids = request.data.get("ids") or []
        project_id = request.data.get("project_id")
        collection_id = request.data.get("collection_id")
        environment_id = request.data.get("environment_id")
        execution_mode = _resolve_execution_mode(request.data)

        test_cases = _collect_test_case_scope(
            request.user,
            scope,
            project_id=project_id,
            collection_id=collection_id,
            ids=ids,
        )
        if not test_cases:
            return Response({"error": "未找到可执行的测试用例"}, status=status.HTTP_400_BAD_REQUEST)

        records = []
        runtime_context = {}
        run_id = uuid4().hex
        run_name = _build_run_name("test_case", scope)
        try:
            for test_case in test_cases:
                environment = _resolve_execution_environment(test_case.project, environment_id)
                records.append(
                    _execute_test_case(
                        test_case=test_case,
                        executor=request.user,
                        environment=environment,
                        run_id=run_id,
                        run_name=run_name,
                        request_name=test_case.name,
                        runtime_context=runtime_context,
                        execution_mode=execution_mode,
                    )
                )
        finally:
            run_execution_context = runtime_context.get("_execution_run_context")
            if run_execution_context:
                run_execution_context.close()
                runtime_context.pop("_execution_run_context", None)
        return Response(_serialize_execution_batch(records))
