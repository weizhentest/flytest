import re

from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .models import LLMConfig, UserToolApproval, get_user_active_llm_config


class LLMConfigSerializer(serializers.ModelSerializer):
    """
    LLM 配置序列化器。
    读取时隐藏 api_key，并按当前请求用户控制敏感字段可见性。
    """

    has_api_key = serializers.SerializerMethodField()
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    owner_name = serializers.SerializerMethodField()
    shared_group_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        source="shared_groups",
        required=False,
        write_only=True,
    )
    shared_user_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.filter(is_active=True),
        source="shared_users",
        required=False,
        write_only=True,
    )
    shared_groups = serializers.SerializerMethodField()
    shared_users = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_view_sensitive = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    sharing_summary = serializers.SerializerMethodField()
    sensitive_fields_hidden = serializers.SerializerMethodField()

    class Meta:
        model = LLMConfig
        fields = [
            "id",
            "owner_id",
            "owner_name",
            "config_name",
            "provider",
            "wire_api",
            "name",
            "api_url",
            "api_key",
            "has_api_key",
            "system_prompt",
            "supports_vision",
            "context_limit",
            "enable_summarization",
            "enable_hitl",
            "enable_streaming",
            "is_active",
            "shared_group_ids",
            "shared_user_ids",
            "shared_groups",
            "shared_users",
            "can_edit",
            "can_view_sensitive",
            "is_shared",
            "sharing_summary",
            "sensitive_fields_hidden",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "api_key": {"write_only": True},
        }

    @staticmethod
    def _normalize_api_url(value: str) -> str:
        normalized = value.strip().rstrip("/")
        suffixes = (
            "/chat/completions",
            "/responses",
            "/messages",
            "/messages/count_tokens",
        )
        lowered = normalized.lower()
        for suffix in suffixes:
            if lowered.endswith(suffix):
                normalized = normalized[: -len(suffix)]
                break
        normalized = re.sub(r"(?<!:)/{2,}", "/", normalized)
        return normalized

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_sensitive_visible = instance.can_view_sensitive(user) if request else True

        data.pop("api_key", None)

        active_config = get_user_active_llm_config(user) if user and user.is_authenticated else None
        data["is_active"] = bool(active_config and active_config.pk == instance.pk)

        if not is_sensitive_visible:
            data["api_url"] = ""
            data["system_prompt"] = ""

        return data

    def get_has_api_key(self, obj):
        return bool(obj.api_key)

    def get_owner_name(self, obj):
        return obj.owner.username if obj.owner else "系统共享"

    def get_shared_groups(self, obj):
        return [{"id": group.id, "name": group.name} for group in obj.shared_groups.all().order_by("name")]

    def get_shared_users(self, obj):
        return [
            {"id": user.id, "username": user.username, "email": user.email}
            for user in obj.shared_users.all().order_by("username")
        ]

    def get_can_edit(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return obj.can_manage(user) if request else True

    def get_can_view_sensitive(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return obj.can_view_sensitive(user) if request else True

    def get_is_shared(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return obj.is_shared_with(user) if request else False

    def get_sharing_summary(self, obj):
        groups = obj.shared_groups.count()
        users = obj.shared_users.count()
        if not groups and not users:
            return "仅自己可用"
        parts = []
        if groups:
            parts.append(f"共享给 {groups} 个组织")
        if users:
            parts.append(f"共享给 {users} 名成员")
        return "，".join(parts)

    def get_sensitive_fields_hidden(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return not obj.can_view_sensitive(user) if request else False

    def validate_config_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("配置名称不能为空")
        return value.strip()

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("模型名称不能为空")
        return value.strip()

    def validate_api_key(self, value):
        if value and len(value.strip()) < 1:
            raise serializers.ValidationError("API 密钥长度至少需要 1 个字符")
        return value.strip() if value else ""

    def validate_api_url(self, value):
        if not value:
            raise serializers.ValidationError("API 地址不能为空")
        value = self._normalize_api_url(value)
        if not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError("API 地址必须以 http:// 或 https:// 开头")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        owner = getattr(self.instance, "owner", None)
        if owner is None and request is not None:
            owner = getattr(request, "user", None)

        provider = attrs.get("provider", getattr(self.instance, "provider", None))
        wire_api = attrs.get("wire_api", getattr(self.instance, "wire_api", "chat_completions"))

        config_name = attrs.get("config_name")
        if config_name:
            queryset = LLMConfig.objects.filter(config_name=config_name, owner=owner)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"config_name": "当前用户下已存在同名配置"})

        if provider == "qwen" and wire_api == "messages":
            raise serializers.ValidationError({"wire_api": "当前供应商不支持 Claude Messages 协议。"})

        if request and request.user and not request.user.is_superuser and not request.user.is_staff:
            shared_groups = attrs.get("shared_groups")
            shared_users = attrs.get("shared_users")
            if shared_groups or shared_users:
                raise serializers.ValidationError("只有管理员可以将 AI 大模型配置共享给组织或其他成员。")

        return attrs


class UserToolApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserToolApproval
        fields = [
            "id",
            "tool_name",
            "policy",
            "scope",
            "session_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_tool_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("工具名称不能为空")
        return value.strip()

    def validate(self, attrs):
        scope = attrs.get("scope", "permanent")
        session_id = attrs.get("session_id")

        if scope == "session" and not session_id:
            raise serializers.ValidationError({"session_id": "会话级别偏好必须提供 session_id"})

        return attrs


class UserToolApprovalBatchSerializer(serializers.Serializer):
    tool_name = serializers.CharField(max_length=100)
    policy = serializers.ChoiceField(choices=UserToolApproval.POLICY_CHOICES)
    scope = serializers.ChoiceField(
        choices=UserToolApproval.SCOPE_CHOICES, default="permanent"
    )
    session_id = serializers.CharField(max_length=255, required=False, allow_null=True)
