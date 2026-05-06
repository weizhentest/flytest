from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from accounts.models import is_user_approved
from accounts.serializers import UserDetailSerializer
from projects.models import Project, ProjectMember

from .models import SiteNotification, SiteNotificationRecipient, SiteNotificationReply


class ProjectBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name"]


class SiteNotificationRecipientSerializer(serializers.ModelSerializer):
    sender_detail = UserDetailSerializer(source="notification.sender", read_only=True)
    project_detail = ProjectBriefSerializer(source="notification.project", read_only=True)
    title = serializers.CharField(source="notification.title", read_only=True)
    content = serializers.CharField(source="notification.content", read_only=True)
    scope = serializers.CharField(source="notification.scope", read_only=True)
    scope_display = serializers.CharField(source="notification.get_scope_display", read_only=True)
    created_at = serializers.DateTimeField(source="notification.created_at", read_only=True)
    notification_id = serializers.IntegerField(source="notification.id", read_only=True)
    preview = serializers.SerializerMethodField()

    class Meta:
        model = SiteNotificationRecipient
        fields = [
            "id",
            "notification_id",
            "title",
            "content",
            "preview",
            "scope",
            "scope_display",
            "project_detail",
            "sender_detail",
            "is_read",
            "read_at",
            "created_at",
        ]

    def get_preview(self, obj):
        content = (obj.notification.content or "").strip()
        if len(content) <= 90:
            return content
        return f"{content[:90]}..."


class SiteNotificationReplySerializer(serializers.ModelSerializer):
    sender_detail = UserDetailSerializer(source="sender", read_only=True)

    class Meta:
        model = SiteNotificationReply
        fields = [
            "id",
            "content",
            "sender_detail",
            "created_at",
            "updated_at",
        ]


class SiteNotificationDetailSerializer(SiteNotificationRecipientSerializer):
    replies = SiteNotificationReplySerializer(many=True, source="notification.replies", read_only=True)
    reply_count = serializers.SerializerMethodField()

    class Meta(SiteNotificationRecipientSerializer.Meta):
        fields = SiteNotificationRecipientSerializer.Meta.fields + [
            "replies",
            "reply_count",
        ]

    def get_reply_count(self, obj):
        return obj.notification.replies.count()


class SiteNotificationCreateSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=SiteNotification.SCOPE_CHOICES, help_text="通知范围")
    title = serializers.CharField(max_length=200, help_text="通知标题")
    content = serializers.CharField(help_text="通知内容")
    project_id = serializers.IntegerField(required=False, allow_null=True, help_text="项目ID")
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        help_text="接收用户ID列表",
    )

    def validate_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("通知标题不能为空。")
        return value

    def validate_content(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("通知内容不能为空。")
        return value

    def validate(self, attrs):
        scope = attrs["scope"]
        project_id = attrs.get("project_id")
        user_ids = attrs.get("user_ids") or []

        project = None
        recipients = User.objects.none()

        if scope == SiteNotification.SCOPE_ALL:
            recipients = User.objects.filter(is_active=True)
        elif scope == SiteNotification.SCOPE_PROJECT:
            if not project_id:
                raise serializers.ValidationError({"project_id": "请选择项目。"})
            try:
                project = Project.objects.get(pk=project_id, is_deleted=False)
            except Project.DoesNotExist as exc:
                raise serializers.ValidationError({"project_id": "所选项目不存在。"}) from exc
            recipients = User.objects.filter(
                is_active=True,
                project_memberships__project=project,
            ).distinct()
        else:
            if not user_ids:
                raise serializers.ValidationError({"user_ids": "请至少选择一个接收人。"})
            recipients = User.objects.filter(id__in=set(user_ids), is_active=True).distinct()
            if recipients.count() != len(set(user_ids)):
                raise serializers.ValidationError({"user_ids": "存在无效的接收人，请刷新后重试。"})

        approved_recipients = recipients.filter(is_staff=True) | recipients.filter(is_superuser=True) | recipients.filter(approval_record__status="approved") | recipients.filter(approval_record__isnull=True)
        approved_recipients = approved_recipients.distinct()
        if not approved_recipients.exists():
            raise serializers.ValidationError("当前没有可接收通知的用户。")

        attrs["project"] = project
        attrs["recipients"] = list(approved_recipients)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        recipients = validated_data.pop("recipients")
        project = validated_data.pop("project", None)
        validated_data.pop("project_id", None)
        validated_data.pop("user_ids", None)

        notification = SiteNotification.objects.create(
            sender=request.user,
            project=project,
            recipient_count=len(recipients),
            **validated_data,
        )

        SiteNotificationRecipient.objects.bulk_create(
            [
                SiteNotificationRecipient(notification=notification, user=user)
                for user in recipients
            ]
        )
        return notification


class SiteNotificationCreateResponseSerializer(serializers.ModelSerializer):
    sender_detail = UserDetailSerializer(source="sender", read_only=True)
    project_detail = ProjectBriefSerializer(source="project", read_only=True)

    class Meta:
        model = SiteNotification
        fields = [
            "id",
            "title",
            "content",
            "scope",
            "recipient_count",
            "sender_detail",
            "project_detail",
            "created_at",
        ]


class SiteNotificationReplyCreateSerializer(serializers.Serializer):
    content = serializers.CharField(help_text="回复内容")

    def validate_content(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("回复内容不能为空。")
        return value
