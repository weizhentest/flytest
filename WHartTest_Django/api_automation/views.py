import os
import tempfile
import threading
import time
from pathlib import Path

import httpx
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from projects.models import Project
from wharttest_django.viewsets import BaseModelViewSet

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
from .services import VariableResolver, build_request_url, evaluate_assertions


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


def _save_job(job_id: int, **fields):
    job = ApiImportJob.objects.get(pk=job_id)
    for key, value in fields.items():
        setattr(job, key, value)
    job.updated_at = timezone.now()
    job.save()


def _run_import_job(job_id: int, file_path: str):
    try:
        job = ApiImportJob.objects.select_related("collection", "project", "creator").get(pk=job_id)
        _save_job(
            job_id,
            status="running",
            progress_percent=8,
            progress_stage="queued",
            progress_message="任务已开始，正在准备解析接口文档。",
            error_message="",
        )

        def progress(percent: int, stage: str, message: str):
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
        )
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


def _serialize_execution_batch(records):
    serializer = ApiExecutionRecordSerializer(records, many=True)
    return {
        "total_count": len(records),
        "success_count": sum(1 for record in records if record.status == "success"),
        "failed_count": sum(1 for record in records if record.status == "failed"),
        "error_count": sum(1 for record in records if record.status == "error"),
        "items": serializer.data,
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
    request_name: str | None = None,
    override_payload: dict | None = None,
    snapshot_extra: dict | None = None,
    assertions_override=None,
):
    project = api_request.collection.project
    override_payload = override_payload or {}

    variables = {}
    base_url = ""
    common_headers = {}
    timeout_ms = api_request.timeout_ms

    if environment:
        variables.update(environment.variables or {})
        base_url = environment.base_url or ""
        common_headers = environment.common_headers or {}
        timeout_ms = environment.timeout_ms or timeout_ms

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
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        response_snapshot = {"body": None}
        passed = False
        execute_status = "error"

    return ApiExecutionRecord.objects.create(
        project=project,
        request=api_request,
        environment=environment,
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
    http_method_names = ["get", "head", "options"]
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
        record = _execute_api_request(
            api_request=api_request,
            executor=request.user,
            environment=environment,
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
        for api_request in api_requests:
            environment = _resolve_execution_environment(api_request.collection.project, environment_id)
            records.append(
                _execute_api_request(
                    api_request=api_request,
                    executor=request.user,
                    environment=environment,
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
    queryset = ApiExecutionRecord.objects.select_related("project", "request", "environment", "executor")
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


class ApiTestCaseViewSet(BaseModelViewSet):
    queryset = ApiTestCase.objects.select_related("project", "request", "creator")
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
        record = _execute_api_request(
            api_request=test_case.request,
            executor=request.user,
            environment=environment,
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
        for test_case in test_cases:
            environment = _resolve_execution_environment(test_case.project, environment_id)
            overrides, assertions, snapshot_extra = _build_test_case_execution_payload(test_case)
            records.append(
                _execute_api_request(
                    api_request=test_case.request,
                    executor=request.user,
                    environment=environment,
                    request_name=test_case.name,
                    override_payload=overrides,
                    snapshot_extra=snapshot_extra,
                    assertions_override=assertions,
                )
            )
        return Response(_serialize_execution_batch(records))
