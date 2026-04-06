from __future__ import annotations

from typing import Any

from django.db.models import Count, Prefetch, Q
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project

from .catalog import get_scenarios, get_tool_catalog, get_tool_definition
from .executor import DataFactoryExecutionError, execute_tool
from .models import DataFactoryRecord, DataFactoryTag
from .reference import build_reference_options, build_reference_placeholder, build_reference_tree
from .serializers import (
    DataFactoryExecuteSerializer,
    DataFactoryRecordSerializer,
    DataFactoryReferenceSerializer,
    DataFactoryTagSerializer,
)


class DataFactoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class DataFactoryTagViewSet(viewsets.ModelViewSet):
    queryset = DataFactoryTag.objects.select_related("project", "creator")
    serializer_class = DataFactoryTagSerializer
    pagination_class = DataFactoryPagination

    def get_queryset(self):
        queryset = super().get_queryset().annotate(record_total=Count("records", distinct=True))
        project_id = self.request.query_params.get("project")
        search = str(self.request.query_params.get("search") or "").strip()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search) | Q(description__icontains=search))
        return queryset.order_by("name", "id")

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)


class DataFactoryRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DataFactoryRecord.objects.select_related("project", "creator").prefetch_related(
        Prefetch("tags", queryset=DataFactoryTag.objects.order_by("name", "id"))
    )
    serializer_class = DataFactoryRecordSerializer
    pagination_class = DataFactoryPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project")
        search = str(self.request.query_params.get("search") or "").strip()
        tool_category = str(self.request.query_params.get("tool_category") or "").strip()
        tool_scenario = str(self.request.query_params.get("tool_scenario") or "").strip()
        tag_code = str(self.request.query_params.get("tag_code") or "").strip()
        tag_id = self.request.query_params.get("tag_id")
        is_saved = self.request.query_params.get("is_saved")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if search:
            queryset = queryset.filter(
                Q(tool_name__icontains=search)
                | Q(tags__name__icontains=search)
                | Q(tags__code__icontains=search)
            )
        if tool_category:
            queryset = queryset.filter(tool_category=tool_category)
        if tool_scenario:
            queryset = queryset.filter(tool_scenario=tool_scenario)
        if tag_code:
            queryset = queryset.filter(tags__code=tag_code)
        if tag_id:
            queryset = queryset.filter(tags__id=tag_id)
        if is_saved in {"true", "false"}:
            queryset = queryset.filter(is_saved=(is_saved == "true"))
        return queryset.distinct().order_by("-created_at", "-id")


class ToolCatalogApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_tool_catalog())


class ToolScenariosApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_scenarios())


class DataFactoryExecuteApiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DataFactoryExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        project = Project.objects.filter(id=validated["project"]).first()
        if project is None:
            return Response({"error": "项目不存在"}, status=status.HTTP_404_NOT_FOUND)

        tool = get_tool_definition(validated["tool_name"])
        if not tool:
            return Response({"error": "工具不存在"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            output_data = execute_tool(tool["name"], validated["input_data"])
        except DataFactoryExecutionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        response_data: dict[str, Any] = {
            "tool": tool,
            "output_data": output_data,
            "saved": False,
        }

        if validated.get("save_record", True):
            record = DataFactoryRecord.objects.create(
                project=project,
                creator=request.user,
                tool_name=tool["name"],
                tool_category=tool["category"],
                tool_scenario=tool["scenario"],
                input_data=validated["input_data"],
                output_data=output_data,
                is_saved=True,
            )
            tags = list(DataFactoryTag.objects.filter(project=project, id__in=validated.get("tag_ids", [])))
            for tag_name in validated.get("tag_names", []):
                clean_name = str(tag_name).strip()
                if not clean_name:
                    continue
                tag = DataFactoryTag.objects.filter(project=project, name=clean_name).first()
                if tag is None:
                    tag_serializer = DataFactoryTagSerializer(data={"project": project.id, "name": clean_name})
                    tag_serializer.is_valid(raise_exception=True)
                    tag = tag_serializer.save(creator=request.user)
                tags.append(tag)
            if tags:
                record.tags.set({tag.id: tag for tag in tags}.values())
            response_data["saved"] = True
            response_data["record"] = DataFactoryRecordSerializer(record, context={"request": request}).data

        return Response(response_data, status=status.HTTP_200_OK)


class DataFactoryStatisticsApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response({"error": "project 参数必填"}, status=status.HTTP_400_BAD_REQUEST)
        queryset = DataFactoryRecord.objects.filter(project_id=project_id)
        total_records = queryset.count()
        saved_records = queryset.filter(is_saved=True).count()
        category_stats = list(
            queryset.values("tool_category").annotate(total=Count("id")).order_by("tool_category")
        )
        scenario_stats = list(
            queryset.values("tool_scenario").annotate(total=Count("id")).order_by("tool_scenario")
        )
        tag_stats = list(
            DataFactoryTag.objects.filter(project_id=project_id)
            .annotate(total=Count("records"))
            .values("id", "name", "code", "color", "total")
            .order_by("-total", "name")
        )
        recent_records = DataFactoryRecordSerializer(
            queryset.select_related("creator").prefetch_related("tags").order_by("-created_at", "-id")[:5],
            many=True,
            context={"request": request},
        ).data
        return Response(
            {
                "total_records": total_records,
                "saved_records": saved_records,
                "category_stats": category_stats,
                "scenario_stats": scenario_stats,
                "tag_stats": tag_stats,
                "recent_records": recent_records,
            }
        )


class DataFactoryReferencesApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response({"error": "project 参数必填"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = DataFactoryReferenceSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data["mode"]
        options = build_reference_options(int(project_id))
        for tag in options["tags"]:
            tag["placeholder"] = build_reference_placeholder("tag", tag["code"], mode=mode)
        for record in options["records"]:
            record["placeholder"] = build_reference_placeholder("record", str(record["id"]), mode=mode)
        return Response(
            {
                "mode": mode,
                "tree": build_reference_tree(int(project_id)),
                "tags": options["tags"],
                "records": options["records"],
            }
        )
