from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserApproval(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "待审核"),
        (STATUS_APPROVED, "已通过"),
        (STATUS_REJECTED, "已驳回"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_record",
        verbose_name="用户",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="审核状态",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_user_approvals",
        verbose_name="审核人",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="审核时间",
    )
    review_note = models.TextField(
        blank=True,
        default="",
        verbose_name="审核备注",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户注册审核"
        verbose_name_plural = "用户注册审核"
        ordering = ["-updated_at", "-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"


def user_avatar_upload_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"accounts/avatars/user_{instance.user_id}/avatar.{extension}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    phone_number = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="手机号",
    )
    real_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="真实姓名",
    )
    avatar = models.ImageField(
        upload_to=user_avatar_upload_path,
        blank=True,
        default="",
        verbose_name="头像",
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="密码修改时间",
    )
    username_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="系统用户名最近修改时间",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = "用户资料"

    def __str__(self):
        return f"{self.user.username} profile"


def get_user_approval_record(user: User | None) -> UserApproval | None:
    if user is None:
        return None
    try:
        return user.approval_record
    except UserApproval.DoesNotExist:
        return None


def get_user_approval_status(user: User | None) -> str:
    if user is None:
        return UserApproval.STATUS_REJECTED
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return UserApproval.STATUS_APPROVED

    approval_record = get_user_approval_record(user)
    if approval_record:
        return approval_record.status
    return UserApproval.STATUS_APPROVED


def is_user_approved(user: User | None) -> bool:
    return get_user_approval_status(user) == UserApproval.STATUS_APPROVED


def ensure_user_approval_record(
    user: User,
    *,
    status: str = UserApproval.STATUS_PENDING,
    reviewed_by: User | None = None,
    review_note: str = "",
) -> UserApproval:
    defaults = {
        "status": status,
        "reviewed_by": reviewed_by if status != UserApproval.STATUS_PENDING else None,
        "reviewed_at": timezone.now() if status != UserApproval.STATUS_PENDING else None,
        "review_note": review_note or "",
    }
    record, _ = UserApproval.objects.update_or_create(user=user, defaults=defaults)
    return record


def get_user_profile(user: User | None) -> UserProfile | None:
    if user is None:
        return None
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


def ensure_user_profile(user: User) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


class UserOperationLog(models.Model):
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_MENU = "menu"

    ACTION_CHOICES = [
        (ACTION_LOGIN, "登录"),
        (ACTION_LOGOUT, "退出"),
        (ACTION_MENU, "菜单访问"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operation_logs",
        verbose_name="用户",
    )
    username_snapshot = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name="用户名快照",
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        db_index=True,
        verbose_name="操作类型",
    )
    label = models.CharField(
        max_length=120,
        blank=True,
        default="",
        verbose_name="操作内容",
    )
    path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="页面路径",
    )
    method = models.CharField(
        max_length=12,
        blank=True,
        default="",
        verbose_name="请求方式",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP 地址",
    )
    user_agent = models.TextField(
        blank=True,
        default="",
        verbose_name="浏览器信息",
    )
    metadata = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="扩展信息",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="操作时间")

    class Meta:
        verbose_name = "用户操作日志"
        verbose_name_plural = "用户操作日志"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="acct_oplog_user_time_idx"),
            models.Index(fields=["action", "-created_at"], name="acct_oplog_action_time_idx"),
        ]

    def __str__(self):
        username = self.username_snapshot or getattr(self.user, "username", "")
        created_at = self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        return f"{username} - {self.get_action_display()} - {created_at}"
