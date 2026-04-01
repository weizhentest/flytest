# 导入 Django Admin 注册入口。
from django.contrib import admin

# 导入 API Key 模型。
from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "name",  # Key 显示名称。
        "user",  # 关联用户。
        "key_preview",  # 截断密钥预览。
        "created_at",  # 创建时间。
        "expires_at",  # 过期时间。
        "is_active",  # 启用状态。
    )
    list_filter = (
        "is_active",  # 按启用状态筛选。
        "created_at",  # 按创建时间筛选。
        "expires_at",  # 按过期时间筛选。
    )
    search_fields = (
        "name",  # 按 Key 名称搜索。
        "key",  # 按完整 Key 搜索（仅后台可见）。
        "user__username",  # 按用户名搜索。
    )
    raw_id_fields = ("user",)  # 用户量大时使用原始 ID 选择器可提升后台性能。
    readonly_fields = ("key", "created_at")  # 防止后台编辑时篡改密钥值与创建时间。

    fieldsets = (
        (
            None,
            {
                "fields": ("name", "user", "is_active")  # 基本信息分组。
            },
        ),
        (
            "Key Details",
            {
                "fields": ("key", "created_at", "expires_at"),  # 只读与有效期相关字段。
                "classes": ("collapse",),  # 默认折叠，减少页面视觉噪音。
            },
        ),
    )

    def key_preview(self, obj):
        """返回截断后的 Key 预览，提升后台可读性。"""
        # 仅显示前后片段，降低后台误泄漏完整密钥的风险。
        return f"{obj.key[:5]}...{obj.key[-5:]}"

    key_preview.short_description = "API Key (Preview)"

    # 覆盖保存逻辑，保证后台手工创建记录时也会自动生成 key。
    def save_model(self, request, obj, form, change):
        # 仅在新建对象时生成 key，避免编辑历史对象时轮换密钥导致调用中断。
        if not obj.pk:
            obj.key = obj.generate_key()
        super().save_model(request, obj, form, change)
