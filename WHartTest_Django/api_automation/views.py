import os
import tempfile
import time
from pathlib import Path

import httpx
from django.db.models import Q
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from projects.models import Project
from wharttest_django.viewsets import BaseModelViewSet

from .generation import generate_script_and_test_case
from .models import ApiCollection, ApiEnvironment, ApiExecutionRecord, ApiRequest, ApiTestCase
from .serializers import (
    ApiCollectionSerializer,
    ApiEnvironmentSerializer,
    ApiExecutionRecordSerializer,
    ApiRequestSerializer,
    ApiTestCaseSerializer,
)
from .document_import import ParsedRequestData, import_requests_from_document
from .services import VariableResolver, build_request_url, evaluate_assertions


def get_accessible_projects(user):
    if user.is_superuser:
        return Project.objects.all()
    return Project.objects.filter(Q(members__user=user) | Q(creator=user)).distinct()


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
            queryset = queryset.filter(collection_id=collection_id)
        if method:
            queryset = queryset.filter(method=method.upper())
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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

        suffix = Path(file.name).suffix or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        try:
            import_result = import_requests_from_document(temp_path)
            created_requests = self._create_imported_requests(collection, request.user, import_result.requests)
            created_test_cases = self._create_generated_test_cases(
                collection.project,
                request.user,
                created_requests,
                import_result.requests,
                enabled=generate_test_cases,
            )
            serializer = self.get_serializer(created_requests, many=True)
            serialized_requests = serializer.data
            generated_scripts = [
                {
                    "request_id": item["id"],
                    "request_name": item["name"],
                    "collection_name": item.get("collection_name"),
                    "script": item["generated_script"],
                }
                for item in serialized_requests
            ]
            testcase_serializer = ApiTestCaseSerializer(created_test_cases, many=True)
            return Response(
                {
                    "created_count": len(created_requests),
                    "generated_script_count": len(generated_scripts),
                    "created_testcase_count": len(created_test_cases),
                    "source_type": import_result.source_type,
                    "marker_used": import_result.marker_used,
                    "note": import_result.note,
                    "items": serialized_requests,
                    "generated_scripts": generated_scripts,
                    "test_cases": testcase_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        api_request = self.get_object()
        project = api_request.collection.project

        environment = None
        environment_id = request.data.get("environment_id")
        if environment_id:
            environment = ApiEnvironment.objects.filter(project=project, pk=environment_id).first()
        if environment is None:
            environment = ApiEnvironment.objects.filter(project=project, is_default=True).first()

        variables = {}
        base_url = ""
        common_headers = {}
        timeout_ms = api_request.timeout_ms

        if environment:
            variables.update(environment.variables or {})
            base_url = environment.base_url or ""
            common_headers = environment.common_headers or {}
            timeout_ms = environment.timeout_ms or timeout_ms

        resolver = VariableResolver(variables)

        resolved_url = build_request_url(base_url, str(resolver.resolve(api_request.url)))
        resolved_headers = {
            **resolver.resolve(common_headers or {}),
            **resolver.resolve(api_request.headers or {}),
        }
        resolved_params = resolver.resolve(api_request.params or {})
        resolved_body = resolver.resolve(api_request.body)

        request_kwargs = {
            "method": api_request.method,
            "url": resolved_url,
            "headers": resolved_headers,
            "params": resolved_params,
            "timeout": max(timeout_ms / 1000, 1),
            "follow_redirects": True,
        }

        if api_request.body_type == "json":
            request_kwargs["json"] = resolved_body or {}
        elif api_request.body_type == "form":
            request_kwargs["data"] = resolved_body or {}
        elif api_request.body_type == "raw":
            request_kwargs["content"] = resolved_body if isinstance(resolved_body, str) else str(resolved_body)

        request_snapshot = {
            "method": api_request.method,
            "url": resolved_url,
            "headers": resolved_headers,
            "params": resolved_params,
            "body_type": api_request.body_type,
            "body": resolved_body,
        }

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
                api_request.assertions or [],
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

        record = ApiExecutionRecord.objects.create(
            project=project,
            request=api_request,
            environment=environment,
            request_name=api_request.name,
            method=api_request.method,
            url=resolved_url,
            status=execute_status,
            passed=passed,
            status_code=status_code,
            response_time=response_time,
            request_snapshot=request_snapshot,
            response_snapshot=response_snapshot,
            assertions_results=assertions_results,
            error_message=error_message,
            executor=request.user,
        )

        serializer = ApiExecutionRecordSerializer(record)
        return Response(serializer.data)

    def _create_imported_requests(
        self,
        root_collection: ApiCollection,
        user,
        parsed_requests: list[ParsedRequestData],
    ) -> list[ApiRequest]:
        created_requests: list[ApiRequest] = []
        child_collections: dict[str, ApiCollection] = {}

        for parsed in parsed_requests:
            target_collection = root_collection
            if parsed.collection_name and parsed.collection_name.strip():
                normalized_name = parsed.collection_name.strip()[:100]
                if normalized_name and normalized_name != root_collection.name:
                    if normalized_name not in child_collections:
                        child_collection, _ = ApiCollection.objects.get_or_create(
                            project=root_collection.project,
                            parent=root_collection,
                            name=normalized_name,
                            defaults={
                                "creator": user,
                                "order": 0,
                            },
                        )
                        child_collections[normalized_name] = child_collection
                    target_collection = child_collections[normalized_name]

            created_requests.append(
                ApiRequest.objects.create(
                    collection=target_collection,
                    name=parsed.name[:120],
                    description=parsed.description[:5000],
                    method=parsed.method,
                    url=parsed.url,
                    headers=parsed.headers,
                    params=parsed.params,
                    body_type=parsed.body_type,
                    body=parsed.body,
                    assertions=parsed.assertions,
                    timeout_ms=30000,
                    order=0,
                    created_by=user,
                )
            )

        return created_requests

    def _create_generated_test_cases(
        self,
        project: Project,
        user,
        created_requests: list[ApiRequest],
        parsed_requests: list[ParsedRequestData],
        *,
        enabled: bool,
    ) -> list[ApiTestCase]:
        if not enabled:
            return []

        generated_cases: list[ApiTestCase] = []
        for request, parsed in zip(created_requests, parsed_requests, strict=False):
            script, testcase_payload = generate_script_and_test_case(parsed)
            generated_cases.append(
                ApiTestCase.objects.create(
                    project=project,
                    request=request,
                    name=testcase_payload["name"][:160],
                    description=testcase_payload["description"],
                    status=testcase_payload["status"],
                    tags=testcase_payload["tags"],
                    script=script,
                    assertions=testcase_payload["assertions"],
                    creator=user,
                )
            )
        return generated_cases


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
            queryset = queryset.filter(request__collection_id=collection_id)
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
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if request_id:
            queryset = queryset.filter(request_id=request_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)
