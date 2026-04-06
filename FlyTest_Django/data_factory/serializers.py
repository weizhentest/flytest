from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .catalog import get_tool_definition
from .models import DataFactoryRecord, DataFactoryTag
from .reference import build_reference_placeholder, make_unique_tag_code, preview_reference_value


class DataFactoryTagSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    record_count = serializers.SerializerMethodField()
    latest_preview = serializers.SerializerMethodField()

    class Meta:
        model = DataFactoryTag
        fields = [
            "id",
            "project",
            "name",
            "code",
            "description",
            "color",
            "creator",
            "creator_name",
            "record_count",
            "latest_preview",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "creator", "creator_name", "record_count", "latest_preview", "created_at", "updated_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        project = attrs.get("project") or getattr(self.instance, "project", None)
        name = str(attrs.get("name") or getattr(self.instance, "name", "")).strip()
        if not project:
            raise serializers.ValidationError({"project": "project 为必填项"})
        if not name:
            raise serializers.ValidationError({"name": "标签名称不能为空"})
        attrs["name"] = name
        attrs["code"] = make_unique_tag_code(project.id, name, exclude_id=getattr(self.instance, "id", None))
        return attrs

    def get_record_count(self, obj: DataFactoryTag) -> int:
        return obj.records.filter(is_saved=True).count()

    def get_latest_preview(self, obj: DataFactoryTag) -> str:
        record = obj.records.filter(is_saved=True).order_by("-created_at", "-id").first()
        if not record:
            return ""
        return preview_reference_value(record.output_data.get("result") if isinstance(record.output_data, dict) else record.output_data)


class DataFactoryTagOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataFactoryTag
        fields = ["id", "name", "code", "color", "description"]


class DataFactoryRecordSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    tags = DataFactoryTagOptionSerializer(many=True, read_only=True)
    tool_display_name = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    scenario_display = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    reference_placeholder_api = serializers.SerializerMethodField()
    reference_placeholder_ui = serializers.SerializerMethodField()

    class Meta:
        model = DataFactoryRecord
        fields = [
            "id",
            "project",
            "creator",
            "creator_name",
            "tool_name",
            "tool_display_name",
            "tool_category",
            "category_display",
            "tool_scenario",
            "scenario_display",
            "input_data",
            "output_data",
            "is_saved",
            "tags",
            "preview",
            "reference_placeholder_api",
            "reference_placeholder_ui",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_tool_display_name(self, obj: DataFactoryRecord) -> str:
        tool = get_tool_definition(obj.tool_name)
        return tool["display_name"] if tool else obj.tool_name

    def get_category_display(self, obj: DataFactoryRecord) -> str:
        return obj.get_tool_category_display()

    def get_scenario_display(self, obj: DataFactoryRecord) -> str:
        return obj.get_tool_scenario_display()

    def get_preview(self, obj: DataFactoryRecord) -> str:
        value = obj.output_data.get("result") if isinstance(obj.output_data, dict) else obj.output_data
        return preview_reference_value(value)

    def get_reference_placeholder_api(self, obj: DataFactoryRecord) -> str:
        return build_reference_placeholder("record", str(obj.id), mode="api")

    def get_reference_placeholder_ui(self, obj: DataFactoryRecord) -> str:
        return build_reference_placeholder("record", str(obj.id), mode="ui")


class DataFactoryExecuteSerializer(serializers.Serializer):
    project = serializers.IntegerField(required=True)
    tool_name = serializers.CharField(required=True)
    input_data = serializers.JSONField(required=True)
    save_record = serializers.BooleanField(required=False, default=True)
    tag_names = serializers.ListField(child=serializers.CharField(max_length=80), required=False, default=list)
    tag_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)

    def validate_tool_name(self, value: str) -> str:
        if not get_tool_definition(value):
            raise serializers.ValidationError("工具不存在")
        return value


class DataFactoryReferenceSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["api", "ui"], required=False, default="api")
