# 导入 Django 模型基类。
from django.db import models

# 导入项目认证用户模型配置。
from django.conf import settings

# 导入安全随机字符串生成器。
import secrets

# 导入时区工具用于过期时间判断。
from django.utils import timezone


class APIKey(models.Model):
    """
    表示用于平台请求鉴权的 API Key。
    每个 API Key 关联一个 Django 用户，并继承该用户权限。
    """


    # API Key 原文（供外部 MCP 客户端直接使用）；生产高安全场景可改为哈希存储策略。
    key = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name="API Key"
    )

    # Key 的业务名称，便于界面区分用途。
    name = models.CharField(max_length=100, unique=True, verbose_name="Key Name")

    # 关联用户；使用该 Key 的请求将继承该用户权限。
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name="Associated User",
    )

    # Key 创建时间。
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    # 可选过期时间；为空表示长期有效。
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Expires At",
        help_text="Optional. If set, the key will expire at this date/time.",
    )

    # 开关状态；关闭后即使未过期也不可用。
    is_active = models.BooleanField(default=True, verbose_name="Is Active")

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
        ordering = ["-created_at"]

    def __str__(self):
        return f"API Key: {self.name} (User: {self.user.username})"

    def save(self, *args, **kwargs):
        # 条件：未显式传入 key；动作：自动生成；结果：避免创建出空 Key 记录。
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    def generate_key(self):
        """生成安全且 URL 友好的 API Key。"""
        # 生成 32 字节随机内容对应的 URL-safe 字符串，兼顾安全性与可传输性。
        return secrets.token_urlsafe(32)

    def is_valid(self):
        """检查 API Key 是否启用且未过期。"""
        # 条件：被禁用；动作：直接判定无效；结果：可立即吊销已发放 Key。
        if not self.is_active:
            return False
        # 条件：设置了过期时间且已过期；动作：判定无效；结果：防止过期 Key 继续访问。
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True
