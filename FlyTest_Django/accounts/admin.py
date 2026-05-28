# 导入 Django Admin 注册入口。
from django.contrib import admin

from .models import UserOperationLog


@admin.register(UserOperationLog)
class UserOperationLogAdmin(admin.ModelAdmin):
    list_display = ("user", "username_snapshot", "action", "label", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "username_snapshot", "label", "path", "ip_address")
    readonly_fields = (
        "user",
        "username_snapshot",
        "action",
        "label",
        "path",
        "method",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    )
