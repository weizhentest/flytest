from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import json


User = get_user_model()


class RemoteMCPConfig(models.Model):
    """
    用于存储远程 MCP 服务器配置的模型。
    全局共享，所有用户都可以使用。
    """


    name = models.CharField(
        max_length=255, unique=True, help_text="远程 MCP 服务器的名称"
    )
    url = models.CharField(max_length=2048, help_text="远程 MCP 服务器的 URL")
    transport = models.CharField(
        max_length=50,
        default="streamable-http",
        help_text="MCP 服务器的传输协议，例如 'streamable-http'",
    )
    headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="可选的认证头，例如 {'Authorization': 'Bearer YOUR_TOKEN'}",
    )
    is_active = models.BooleanField(default=True, help_text="是否启用此远程 MCP 服务器")

    # HITL 配置
    require_hitl = models.BooleanField(
        default=False, help_text="是否对该 MCP 的所有工具启用人工审批"
    )
    hitl_tools = models.JSONField(
        default=list,
        blank=True,
        help_text="需要人工审批的工具列表（为空时表示所有工具），例如 ['playwright_click', 'playwright_fill']",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "远程 MCP 配置"
        verbose_name_plural = "远程 MCP 配置"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """
        对 headers 字段执行自定义校验。
        确保 headers 为合法的 JSON 对象。
        """
        if not isinstance(self.headers, dict):
            raise ValidationError({"headers": "Headers must be a valid JSON object."})
        # 如有需要，可在此增加对请求头键值的更细粒度校验
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()  # 调用 full_clean，执行包括 clean 在内的全部校验
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # 删除 MCP 时，级联删除关联的工具记录
        self.tools.all().delete()
        super().delete(*args, **kwargs)


class MCPTool(models.Model):
    """
    存储 MCP 服务器的工具信息

    当 MCP 配置激活或手动同步时，从远程服务器获取工具列表并存入此表。
    支持工具级别的 HITL 审批配置。
    """

    mcp_config = models.ForeignKey(
        RemoteMCPConfig,
        on_delete=models.CASCADE,
        related_name="tools",
        help_text="关联的 MCP 配置",
    )
    name = models.CharField(max_length=255, help_text="工具名称")
    description = models.TextField(blank=True, default="", help_text="工具描述")
    input_schema = models.JSONField(
        default=dict, blank=True, help_text="工具的输入参数 JSON Schema"
    )

    # 工具级别的 HITL 配置（优先级高于 MCP 级别）
    require_hitl = models.BooleanField(
        default=None,
        null=True,
        blank=True,
        help_text="是否需要人工审批（None 表示继承 MCP 配置）",
    )

    synced_at = models.DateTimeField(auto_now=True, help_text="上次同步时间")

    class Meta:
        verbose_name = "MCP 工具"
        verbose_name_plural = "MCP 工具"
        unique_together = ["mcp_config", "name"]
        ordering = ["mcp_config", "name"]

    def __str__(self):
        return f"{self.mcp_config.name}:{self.name}"

    @property
    def effective_require_hitl(self) -> bool:
        """获取有效的 HITL 配置（工具级别优先，否则继承 MCP 级别）"""
        if self.require_hitl is not None:
            return self.require_hitl
        # 检查是否在 MCP 的 hitl_tools 列表中
        if self.mcp_config.require_hitl:
            if not self.mcp_config.hitl_tools:
                # 空列表表示所有工具都需要审批
                return True
            return self.name in self.mcp_config.hitl_tools
        return False
