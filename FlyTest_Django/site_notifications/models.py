from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteNotification(models.Model):
    SCOPE_ALL = "all"
    SCOPE_PROJECT = "project_members"
    SCOPE_USERS = "users"

    SCOPE_CHOICES = [
        (SCOPE_ALL, "通知所有人"),
        (SCOPE_PROJECT, "通知项目内成员"),
        (SCOPE_USERS, "指定用户通知"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_site_notifications",
        verbose_name="发送人",
    )
    title = models.CharField(max_length=200, verbose_name="通知标题")
    content = models.TextField(verbose_name="通知内容")
    scope = models.CharField(max_length=32, choices=SCOPE_CHOICES, verbose_name="通知范围")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_notifications",
        verbose_name="关联项目",
    )
    recipient_count = models.PositiveIntegerField(default=0, verbose_name="接收人数")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "站内通知"
        verbose_name_plural = "站内通知"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class SiteNotificationRecipient(models.Model):
    notification = models.ForeignKey(
        SiteNotification,
        on_delete=models.CASCADE,
        related_name="recipients",
        verbose_name="通知",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="site_notification_receipts",
        verbose_name="接收人",
    )
    is_read = models.BooleanField(default=False, verbose_name="是否已读")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="已读时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "站内通知接收记录"
        verbose_name_plural = "站内通知接收记录"
        ordering = ["is_read", "-notification__created_at", "-id"]
        unique_together = [("notification", "user")]

    def __str__(self):
        return f"{self.user_id}-{self.notification_id}"

    def mark_as_read(self):
        if self.is_read:
            return False
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at", "updated_at"])
        return True


class SiteNotificationReply(models.Model):
    notification = models.ForeignKey(
        SiteNotification,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name="通知",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="site_notification_replies",
        verbose_name="回复人",
    )
    content = models.TextField(verbose_name="回复内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "站内通知回复"
        verbose_name_plural = "站内通知回复"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.notification_id}-{self.sender_id}"
