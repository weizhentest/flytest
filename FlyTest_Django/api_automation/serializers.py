from rest_framework import serializers

from .generation import build_request_script
from .models import (
    ApiCaseGenerationJob,
    ApiCollection,
    ApiEnvironment,
    ApiExecutionRecord,
    ApiImportJob,
    ApiRequest,
    ApiTestCase,
)
from .specs import (
    apply_environment_spec_payload,
    apply_request_assertions_and_extractors,
    apply_request_spec_payload,
    apply_test_case_assertions_and_extractors,
    apply_test_case_override_payload,
    backfill_environment_specs_from_legacy,
    backfill_request_specs_from_legacy,
    backfill_test_case_specs_from_legacy,
    serialize_assertion_specs,
    serialize_environment_specs,
    serialize_extractor_specs,
    serialize_request_spec,
    serialize_test_case_override,
)


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
    request_spec = serializers.JSONField(write_only=True, required=False)
    assertion_specs = serializers.JSONField(write_only=True, required=False)
    extractor_specs = serializers.JSONField(write_only=True, required=False)
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
            api_request=obj,
        )

    def get_test_case_count(self, obj) -> int:
        return obj.test_cases.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["request_spec"] = serialize_request_spec(instance)
        data["assertion_specs"] = serialize_assertion_specs(instance)
        data["extractor_specs"] = serialize_extractor_specs(instance)
        return data

    def create(self, validated_data):
        request_spec = validated_data.pop("request_spec", None)
        assertion_specs = validated_data.pop("assertion_specs", None)
        extractor_specs = validated_data.pop("extractor_specs", None)
        instance = super().create(validated_data)
        if request_spec is None and assertion_specs is None and extractor_specs is None:
            backfill_request_specs_from_legacy(instance)
            return instance
        apply_request_spec_payload(instance, request_spec)
        apply_request_assertions_and_extractors(
            instance,
            assertion_payload=assertion_specs,
            extractor_payload=extractor_specs,
        )
        return instance

    def update(self, instance, validated_data):
        request_spec = validated_data.pop("request_spec", None)
        assertion_specs = validated_data.pop("assertion_specs", None)
        extractor_specs = validated_data.pop("extractor_specs", None)
        instance = super().update(instance, validated_data)
        if request_spec is not None:
            apply_request_spec_payload(instance, request_spec)
        elif not getattr(instance, "request_spec", None):
            backfill_request_specs_from_legacy(instance)
        if assertion_specs is not None or extractor_specs is not None:
            apply_request_assertions_and_extractors(
                instance,
                assertion_payload=assertion_specs,
                extractor_payload=extractor_specs,
            )
        return instance


class ApiRequestListSerializer(serializers.ModelSerializer):
    collection_name = serializers.CharField(source="collection.name", read_only=True)
    project_id = serializers.IntegerField(source="collection.project_id", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)
    test_case_count = serializers.IntegerField(source="test_case_count_value", read_only=True, default=0)
    assertion_count = serializers.SerializerMethodField()

    class Meta:
        model = ApiRequest
        fields = (
            "id",
            "collection",
            "collection_name",
            "project_id",
            "name",
            "description",
            "method",
            "url",
            "assertion_count",
            "test_case_count",
            "timeout_ms",
            "order",
            "created_by",
            "creator_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_assertion_count(self, obj) -> int:
        assertions = getattr(obj, "assertions", None)
        return len(assertions) if isinstance(assertions, list) else 0


class ApiEnvironmentSerializer(serializers.ModelSerializer):
    environment_specs = serializers.JSONField(write_only=True, required=False)
    creator_name = serializers.CharField(source="creator.username", read_only=True)

    class Meta:
        model = ApiEnvironment
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["environment_specs"] = serialize_environment_specs(instance)
        return data

    def create(self, validated_data):
        environment_specs = validated_data.pop("environment_specs", None)
        instance = super().create(validated_data)
        if environment_specs is None:
            backfill_environment_specs_from_legacy(instance)
            return instance
        apply_environment_spec_payload(instance, environment_specs)
        return instance

    def update(self, instance, validated_data):
        environment_specs = validated_data.pop("environment_specs", None)
        instance = super().update(instance, validated_data)
        if environment_specs is not None:
            apply_environment_spec_payload(instance, environment_specs)
        elif not instance.variable_specs.exists() and not instance.header_specs.exists():
            backfill_environment_specs_from_legacy(instance)
        return instance


class ApiExecutionRecordSerializer(serializers.ModelSerializer):
    executor_name = serializers.CharField(source="executor.username", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    interface_name = serializers.SerializerMethodField()
    test_case_name = serializers.SerializerMethodField()
    collection_id = serializers.SerializerMethodField()
    collection_name = serializers.SerializerMethodField()
    request_collection_name = serializers.SerializerMethodField()
    workflow_summary = serializers.SerializerMethodField()
    workflow_steps = serializers.SerializerMethodField()
    main_request_blocked = serializers.SerializerMethodField()

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

    def get_workflow_summary(self, obj):
        snapshot = obj.request_snapshot or {}
        summary = snapshot.get("workflow_summary")
        return dict(summary) if isinstance(summary, dict) else None

    def get_workflow_steps(self, obj):
        snapshot = obj.request_snapshot or {}
        steps = snapshot.get("workflow_steps")
        return list(steps) if isinstance(steps, list) else []

    def get_main_request_blocked(self, obj):
        snapshot = obj.request_snapshot or {}
        return bool(snapshot.get("main_request_blocked", False))


class ApiImportJobSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True)

    class Meta:
        model = ApiImportJob
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at", "completed_at")


class ApiCaseGenerationJobSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    collection_name = serializers.CharField(source="collection.name", read_only=True)

    class Meta:
        model = ApiCaseGenerationJob
        fields = "__all__"
        read_only_fields = ("creator", "created_at", "updated_at", "completed_at")


class ApiTestCaseSerializer(serializers.ModelSerializer):
    request_override_spec = serializers.JSONField(write_only=True, required=False)
    assertion_specs = serializers.JSONField(write_only=True, required=False)
    extractor_specs = serializers.JSONField(write_only=True, required=False)
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["request_override_spec"] = serialize_test_case_override(instance)
        data["assertion_specs"] = serialize_assertion_specs(instance)
        data["extractor_specs"] = serialize_extractor_specs(instance)
        return data

    def create(self, validated_data):
        request_override_spec = validated_data.pop("request_override_spec", None)
        assertion_specs = validated_data.pop("assertion_specs", None)
        extractor_specs = validated_data.pop("extractor_specs", None)
        instance = super().create(validated_data)
        if request_override_spec is None and assertion_specs is None and extractor_specs is None:
            backfill_test_case_specs_from_legacy(instance)
            return instance
        apply_test_case_override_payload(instance, request_override_spec)
        apply_test_case_assertions_and_extractors(
            instance,
            assertion_payload=assertion_specs,
            extractor_payload=extractor_specs,
        )
        return instance

    def update(self, instance, validated_data):
        request_override_spec = validated_data.pop("request_override_spec", None)
        assertion_specs = validated_data.pop("assertion_specs", None)
        extractor_specs = validated_data.pop("extractor_specs", None)
        instance = super().update(instance, validated_data)
        if request_override_spec is not None:
            apply_test_case_override_payload(instance, request_override_spec)
        elif not getattr(instance, "override_spec", None):
            backfill_test_case_specs_from_legacy(instance)
        if assertion_specs is not None or extractor_specs is not None:
            apply_test_case_assertions_and_extractors(
                instance,
                assertion_payload=assertion_specs,
                extractor_payload=extractor_specs,
            )
        return instance
