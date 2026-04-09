from django.contrib.auth.models import Group, User
from rest_framework import serializers
from .models import LLMConfig, UserToolApproval, get_user_active_llm_config


class LLMConfigSerializer(serializers.ModelSerializer):
    """
    LLM配置序列化器，用于创建和更新LLM配置
    注意：为了安全，在读取时不返回 api_key 字段
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
            "api_key": {"write_only": True}  # API密钥只允许写入，不允许读取
        }

    def to_representation(self, instance):
        """
        自定义序列化输出，隐藏敏感字段
        """
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_sensitive_visible = instance.can_view_sensitive(user) if request else True

        if "api_key" in data:
            del data["api_key"]

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
        """验证配置名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("配置名称不能为空")
        return value.strip()

    def validate_name(self, value):
        """验证模型名称（原name字段）"""
        if not value or not value.strip():
            raise serializers.ValidationError("模型名称不能为空")
        return value.strip()

    def validate_api_key(self, value):
        """验证API密钥"""
        if value and len(value.strip()) < 1:
            raise serializers.ValidationError("API密钥长度至少需要1个字符")
        return value.strip() if value else ""

    def validate_api_url(self, value):
        """验证API地址"""
        if not value:
            raise serializers.ValidationError("API地址不能为空")

        # 简单的URL格式验证
        if not (value.startswith("http://") or value.startswith("https://")):
            raise serializers.ValidationError("API地址必须以http://或https://开头")

        return value

    def validate(self, attrs):
        """全局验证"""
        request = self.context.get("request")
        owner = getattr(self.instance, "owner", None)
        if owner is None and request is not None:
            owner = getattr(request, "user", None)

        # 检查是否存在同名配置（排除当前实例）
        config_name = attrs.get("config_name")
        if config_name:
            queryset = LLMConfig.objects.filter(config_name=config_name, owner=owner)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"config_name": "当前用户下已存在同名配置"})

        if request and request.user and not request.user.is_superuser and not request.user.is_staff:
            shared_groups = attrs.get("shared_groups")
            shared_users = attrs.get("shared_users")
            if shared_groups or shared_users:
                raise serializers.ValidationError("只有管理员可以将 AI 大模型配置共享给组织或其他成员。")

        return attrs

    def create(self, validated_data):
        """创建LLM配置"""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """更新LLM配置"""
        return super().update(instance, validated_data)


class UserToolApprovalSerializer(serializers.ModelSerializer):
    """用户工具审批偏好序列化器"""

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
        """验证工具名称"""
        if not value or not value.strip():
            raise serializers.ValidationError("工具名称不能为空")
        return value.strip()

    def validate(self, attrs):
        """全局验证"""
        scope = attrs.get("scope", "permanent")
        session_id = attrs.get("session_id")

        # 如果是会话级别偏好，必须提供 session_id
        if scope == "session" and not session_id:
            raise serializers.ValidationError(
                {"session_id": "会话级别偏好必须提供 session_id"}
            )

        return attrs


class UserToolApprovalBatchSerializer(serializers.Serializer):
    """批量更新用户工具审批偏好"""

    tool_name = serializers.CharField(max_length=100)
    policy = serializers.ChoiceField(choices=UserToolApproval.POLICY_CHOICES)
    scope = serializers.ChoiceField(
        choices=UserToolApproval.SCOPE_CHOICES, default="permanent"
    )
    session_id = serializers.CharField(max_length=255, required=False, allow_null=True)
