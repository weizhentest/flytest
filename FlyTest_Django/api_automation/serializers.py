from rest_framework import serializers

from .generation import build_request_script
from .models import ApiCollection, ApiEnvironment, ApiExecutionRecord, ApiImportJob, ApiRequest, ApiTestCase


class ApiCollectionSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    request_count = serializers.SerializerMethodField()

    class Meta:
        model = ApiCollection
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at")

    def get_children(self, obj):
        children = obj.children.all().order_by("order", "created_at")
        return ApiCollectionSerializer(children, many=True).data if children else []

    def get_request_count(self, obj) -> int:
        return obj.requests.count()


class ApiRequestSerializer(serializers.ModelSerializer):
    collection_name = serializers.CharField(source="collection.name", read_only=True)
    project_id = serializers.IntegerField(source="collection.project_id", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)
    generated_script = serializers.SerializerMethodField()
    test_case_count = serializers.SerializerMethodField()

    class Meta:
        model = ApiRequest
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def get_generated_script(self, obj):
        return build_request_script(
            method=obj.method,
            url=obj.url,
            headers=obj.headers,
            params=obj.params,
            body_type=obj.body_type,
            body=obj.body,
            timeout_ms=obj.timeout_ms,
            assertions=obj.assertions,
        )

    def get_test_case_count(self, obj) -> int:
        return obj.test_cases.count()


class ApiEnvironmentSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)

    class Meta:
        model = ApiEnvironment
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at")


class ApiExecutionRecordSerializer(serializers.ModelSerializer):
    executor_name = serializers.CharField(source="executor.username", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    interface_name = serializers.SerializerMethodField()
    test_case_name = serializers.SerializerMethodField()
    collection_id = serializers.SerializerMethodField()
    collection_name = serializers.SerializerMethodField()
    request_collection_name = serializers.SerializerMethodField()

    class Meta:
        model = ApiExecutionRecord
        fields = "__all__"
        read_only_fields = ("created_at",)

    def get_interface_name(self, obj):
        if obj.request_id and obj.request:
            return obj.request.name
        snapshot = obj.request_snapshot or {}
        return snapshot.get("interface_name") or obj.request_name or None

    def get_test_case_name(self, obj):
        if getattr(obj, "test_case_id", None) and getattr(obj, "test_case", None):
            return obj.test_case.name
        snapshot = obj.request_snapshot or {}
        return snapshot.get("test_case_name")

    def get_collection_id(self, obj):
        if obj.request_id and obj.request:
            return obj.request.collection_id
        snapshot = obj.request_snapshot or {}
        return snapshot.get("collection_id")

    def get_collection_name(self, obj):
        if obj.request_id and obj.request and obj.request.collection:
            return obj.request.collection.name
        snapshot = obj.request_snapshot or {}
        return snapshot.get("collection_name")

    def get_request_collection_name(self, obj):
        return self.get_collection_name(obj)


class ApiImportJobSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True)

    class Meta:
        model = ApiImportJob
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at", "completed_at")


class ApiTestCaseSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    request_name = serializers.CharField(source="request.name", read_only=True)
    request_method = serializers.CharField(source="request.method", read_only=True)
    request_url = serializers.CharField(source="request.url", read_only=True)
    collection_id = serializers.IntegerField(source="request.collection_id", read_only=True)
    collection_name = serializers.CharField(source="request.collection.name", read_only=True)

    class Meta:
        model = ApiTestCase
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at")
