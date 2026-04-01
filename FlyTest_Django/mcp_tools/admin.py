from django.contrib import admin

# 在此注册模型。
from .models import RemoteMCPConfig


@admin.register(RemoteMCPConfig)
class RemoteMCPConfigAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "url",
        "transport",
        "is_active",
        "require_hitl",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active", "transport", "require_hitl")
    search_fields = ("name", "url")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "url", "transport", "headers", "is_active")}),
        (
            "人工审批 (HITL)",
            {
                "fields": ("require_hitl", "hitl_tools"),
                "description": "配置该 MCP 的工具是否需要人工审批。hitl_tools 为空时表示所有工具都需要审批。",
            },
        ),
    )
