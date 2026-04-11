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
