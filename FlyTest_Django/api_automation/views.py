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

from .ai_case_generator import create_test_cases_from_drafts, generate_test_case_drafts_with_ai
from .import_service import process_document_import
from .models import ApiCollection, ApiEnvironment, ApiExecutionRecord, ApiImportJob, ApiRequest, ApiTestCase
from .serializers import (
    ApiCollectionSerializer,
    ApiEnvironmentSerializer,
    ApiExecutionRecordSerializer,
    ApiImportJobSerializer,
    ApiRequestSerializer,
    ApiTestCaseSerializer,
)
from .generation import build_request_script
from .services import (
    VariableResolver,
    build_request_url,
    evaluate_assertions,
    find_missing_variables,
    collect_placeholders,
    extract_json_path,
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


class ImportJobCancelled(Exception):
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


def _run_import_job(job_id: int, file_path: str):
    try:
        job = ApiImportJob.objects.select_related("collection", "project", "creator").get(pk=job_id)
        if job.cancel_requested or job.status == "canceled":
            _save_job(
                job_id,
                force=True,
                status="canceled",
                progress_stage="canceled",
                progress_message="文档解析任务已取消。",
                completed_at=timezone.now(),
            )
            return
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
    except ImportJobCancelled as exc:
        _save_job(
            job_id,
            force=True,
            status="canceled",
            progress_stage="canceled",
            progress_message="文档解析任务已取消。",
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
    finally:
        if os.path.exists(file_path):
            os.unlink(file_path)


def _start_import_job(job_id: int, file_path: str):
    worker = threading.Thread(target=_run_import_job, args=(job_id, file_path), daemon=True)
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
    return {
        "run_id": records[0].run_id if records else None,
        "run_name": records[0].run_name if records else None,
        "run_type": next(iter(run_types)) if len(run_types) == 1 else "mixed",
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
    runtime_context: dict | None = None,
    allow_auth_bootstrap: bool = True,
):
    project = api_request.collection.project
    override_payload = override_payload or {}
    runtime_context = runtime_context or {}

    variables = {}
    base_url = ""
    common_headers = {}
    timeout_ms = api_request.timeout_ms

    if environment:
        variables.update(environment.variables or {})
        base_url = environment.base_url or ""
        common_headers = environment.common_headers or {}
        timeout_ms = environment.timeout_ms or timeout_ms
    variables.update(runtime_context.get("variables", {}))

    method = str(override_payload.get("method") or api_request.method).upper()
    raw_url = str(override_payload.get("url") or api_request.url)

    merged_headers = dict(api_request.headers or {})
    if isinstance(override_payload.get("headers"), dict):
        merged_headers.update(override_payload["headers"])

    merged_params = dict(api_request.params or {})
    if isinstance(override_payload.get("params"), dict):
        merged_params.update(override_payload["params"])

    body_type = override_payload.get("body_type") or api_request.body_type
    body = override_payload.get("body", api_request.body)
    timeout_ms = override_payload.get("timeout_ms") or timeout_ms
    assertions = assertions_override if assertions_override is not None else (api_request.assertions or [])

    missing_variables = find_missing_variables(variables, raw_url, common_headers, merged_headers, merged_params, body)

    bootstrap_error = None
    if "token" in missing_variables and allow_auth_bootstrap and environment:
        auth_request = _get_auth_request(project, variables)
        if auth_request:
            bootstrap_missing = _missing_variables_for_bootstrap(variables, auth_request)
            if bootstrap_missing:
                bootstrap_error = f"自动获取 token 失败，登录接口缺少环境变量: {', '.join(bootstrap_missing)}"
            else:
                auth_record = _execute_api_request(
                    api_request=auth_request,
                    executor=executor,
                    environment=environment,
                    run_id=run_id,
                    run_name=run_name,
                    request_name=f"[Auth Bootstrap] {auth_request.name}",
                    runtime_context=runtime_context,
                    allow_auth_bootstrap=False,
                )
                auth_payload = (auth_record.response_snapshot or {}).get("body")
                auth_variables = _extract_auth_variables(auth_payload, variables)
                if auth_variables.get("token"):
                    runtime_context.setdefault("variables", {}).update(auth_variables)
                    variables.update(auth_variables)
                    if environment:
                        updated_variables = dict(environment.variables or {})
                        updated_variables.update(auth_variables)
                        environment.variables = updated_variables
                        ApiEnvironment.objects.filter(pk=environment.pk).update(
                            variables=updated_variables,
                            updated_at=timezone.now(),
                        )
                    missing_variables = find_missing_variables(
                        variables,
                        raw_url,
                        common_headers,
                        merged_headers,
                        merged_params,
                        body,
                    )
                else:
                    bootstrap_error = auth_record.error_message or "自动获取 token 失败，登录接口响应中未识别到 token 字段"
        else:
            bootstrap_error = "未找到可用于自动获取 token 的登录接口，请在环境变量中配置 auth_request_id 或 auth_request_name"

    resolver = VariableResolver(variables)
    resolved_url = build_request_url(base_url, str(resolver.resolve(raw_url)))
    resolved_headers = {
        **resolver.resolve(common_headers or {}),
        **resolver.resolve(merged_headers or {}),
    }
    resolved_params = resolver.resolve(merged_params or {})
    resolved_body = resolver.resolve(body)

    request_kwargs = {
        "method": method,
        "url": resolved_url,
        "headers": resolved_headers,
        "params": resolved_params,
        "timeout": max(timeout_ms / 1000, 1),
        "follow_redirects": True,
    }

    if body_type == "json":
        request_kwargs["json"] = resolved_body or {}
    elif body_type == "form":
        request_kwargs["data"] = resolved_body or {}
    elif body_type == "raw":
        request_kwargs["content"] = resolved_body if isinstance(resolved_body, str) else str(resolved_body)

    request_snapshot = {
        "request_id": api_request.id,
        "interface_name": api_request.name,
        "collection_id": api_request.collection_id,
        "collection_name": api_request.collection.name,
        "method": method,
        "url": resolved_url,
        "headers": resolved_headers,
        "params": resolved_params,
        "body_type": body_type,
        "body": resolved_body,
        "generated_script": build_request_script(
            method=method,
            url=raw_url,
            headers=merged_headers,
            params=merged_params,
            body_type=body_type,
            body=body,
            timeout_ms=timeout_ms,
            assertions=assertions,
        ),
        "missing_variables": missing_variables,
    }
    if snapshot_extra:
        request_snapshot.update(snapshot_extra)

    response_snapshot = {}
    status_code = None
    response_time = None
    assertions_results = []
    passed = False
    execute_status = "error"
    error_message = ""

    try:
        if missing_variables:
            message = bootstrap_error if bootstrap_error and "token" in missing_variables else None
            raise ValueError(
                message or ("缺少执行所需环境变量: " + ", ".join(missing_variables))
            )

        started_at = time.perf_counter()
        response = httpx.request(**request_kwargs)
        response_time = round((time.perf_counter() - started_at) * 1000, 2)
        status_code = response.status_code
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = response.text

        response_snapshot = {
            "headers": dict(response.headers),
            "body": response_payload,
        }

        assertions_results, passed = evaluate_assertions(
            assertions,
            response.status_code,
            response.text,
            response_payload if isinstance(response_payload, (dict, list)) else None,
        )
        if not assertions_results:
            passed = response.is_success

        execute_status = "success" if passed else "failed"
        if not passed and not error_message and isinstance(response_payload, dict):
            for key in ("message", "detail", "error", "msg"):
                value = response_payload.get(key)
                if value not in (None, ""):
                    error_message = str(value)
                    break
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        response_snapshot = {"body": None, "error": error_message}
        passed = False
        execute_status = "error"

    return ApiExecutionRecord.objects.create(
        project=project,
        request=api_request,
        test_case=test_case,
        environment=environment,
        run_id=run_id or uuid4().hex,
        run_name=run_name or "",
        request_name=request_name or api_request.name,
        method=method,
        url=resolved_url,
        status=execute_status,
        passed=passed,
        status_code=status_code,
        response_time=response_time,
        request_snapshot=request_snapshot,
        response_snapshot=response_snapshot,
        assertions_results=assertions_results,
        error_message=error_message,
        executor=executor,
    )


def _build_test_case_execution_payload(test_case: ApiTestCase):
    script = test_case.script or {}
    overrides = script.get("request_overrides") if isinstance(script, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}

    assertions = test_case.assertions or test_case.request.assertions or []
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
    return overrides, assertions, snapshot_extra


def _serialize_generation_case_items(test_cases: list[ApiTestCase]):
    serializer = ApiTestCaseSerializer(test_cases, many=True)
    return serializer.data


def _generate_request_test_cases(
    *,
    api_request: ApiRequest,
    user,
    mode: str,
    count_per_request: int,
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
            "note": "已跳过已有测试用例的接口。",
            "items": [],
        }

    generation_result = generate_test_case_drafts_with_ai(
        api_request=api_request,
        user=user,
        existing_cases=existing_cases,
        mode=mode,
        count=count_per_request,
    )

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
        "created_count": len(created_cases),
        "ai_used": generation_result.used_ai,
        "note": generation_result.note,
        "prompt_name": generation_result.prompt_name,
        "prompt_source": generation_result.prompt_source,
        "model_name": generation_result.model_name,
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
        serializer = self.get_serializer(ApiImportJob.objects.get(pk=job.id))
        return Response(serializer.data)


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

        suffix = Path(file.name).suffix or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        if async_mode:
            job = ApiImportJob.objects.create(
                project=collection.project,
                collection=collection,
                creator=request.user,
                source_name=file.name,
                status="pending",
                progress_percent=4,
                progress_stage="uploaded",
                progress_message="文档已上传，正在进入后台解析队列。",
                generate_test_cases=generate_test_cases,
                enable_ai_parse=enable_ai_parse,
            )
            _start_import_job(job.id, temp_path)
            serializer = ApiImportJobSerializer(job)
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

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
        record = _execute_api_request(
            api_request=api_request,
            executor=request.user,
            environment=environment,
            run_id=run_id,
            run_name=run_name,
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
                )
            )
        return Response(_serialize_execution_batch(records))

    @action(detail=False, methods=["post"], url_path="generate-test-cases")
    def generate_test_cases(self, request):
        scope = str(request.data.get("scope") or "selected")
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

        items = []
        created_total = 0
        skipped_count = 0
        ai_used_count = 0
        notes: list[str] = []

        for api_request in api_requests:
            item = _generate_request_test_cases(
                api_request=api_request,
                user=request.user,
                mode=mode,
                count_per_request=count_per_request,
            )
            items.append(item)
            created_total += item["created_count"]
            skipped_count += 1 if item.get("skipped") else 0
            ai_used_count += 1 if item.get("ai_used") else 0
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
        overrides, assertions, snapshot_extra = _build_test_case_execution_payload(test_case)
        run_id = uuid4().hex
        run_name = _build_run_name("test_case", "single", test_case.name)
        record = _execute_api_request(
            api_request=test_case.request,
            executor=request.user,
            environment=environment,
            test_case=test_case,
            run_id=run_id,
            run_name=run_name,
            request_name=test_case.name,
            override_payload=overrides,
            snapshot_extra=snapshot_extra,
            assertions_override=assertions,
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
        for test_case in test_cases:
            environment = _resolve_execution_environment(test_case.project, environment_id)
            overrides, assertions, snapshot_extra = _build_test_case_execution_payload(test_case)
            records.append(
                _execute_api_request(
                    api_request=test_case.request,
                    executor=request.user,
                    environment=environment,
                    test_case=test_case,
                    run_id=run_id,
                    run_name=run_name,
                    request_name=test_case.name,
                    override_payload=overrides,
                    snapshot_extra=snapshot_extra,
                    assertions_override=assertions,
                    runtime_context=runtime_context,
                )
            )
        return Response(_serialize_execution_batch(records))
