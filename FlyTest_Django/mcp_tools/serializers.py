from rest_framework import serializers
from projects.models import Project  # 假设 Project 模型位于 'projects' 应用
from .models import RemoteMCPConfig, MCPTool  # 导入 RemoteMCPConfig
import re
from urllib.parse import urlparse


class MCPProjectListSerializer(serializers.ModelSerializer):
    """
    用于 MCP 工具的项目列表序列化器。
    仅提供最小必要字段。
    """

    class Meta:
        model = Project
        fields = ["id", "name", "description"]  # 增加 description 以提供更多上下文
        # 在更复杂场景下，可添加 read_only_fields，
        # 防止字段被其他 MCP 工具端点更新。
        # 如需启用，请在此显式补充只读字段配置。


class RemoteMCPConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemoteMCPConfig
        fields = [
            "id",
            "name",
            "url",
            "transport",
            "headers",
            "is_active",
            "require_hitl",
            "hitl_tools",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_url(self, value):
        """
        自定义 URL 验证，支持：
        - 标准域名 (example.com)
        - IP 地址 (192.168.1.1)
        - Docker 容器名 (flytest-mcp, mcp)
        - localhost
        """
        if not value:
            raise serializers.ValidationError("URL 不能为空")

        # 解析 URL
        try:
            parsed = urlparse(value)
        except Exception:
            raise serializers.ValidationError("无效的 URL 格式")

        # 检查协议
        if parsed.scheme not in ["http", "https"]:
            raise serializers.ValidationError("URL 必须使用 http 或 https 协议")

        # 检查主机名
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        if not hostname:
            raise serializers.ValidationError("URL 必须包含主机名或 IP 地址")

        # 验证主机名格式（支持多种格式）
        # 1. localhost（本机）
        if hostname == "localhost":
            return value

        # 2. IP 地址 (IPv4)
        ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
        if re.match(ip_pattern, hostname):
            # 验证 IP 地址范围
            parts = hostname.split(".")
            if all(0 <= int(part) <= 255 for part in parts):
                return value
            raise serializers.ValidationError("无效的 IP 地址")

        # 3. 域名或 Docker 容器名
        # 允许字母、数字、连字符、下划线和点
        hostname_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-_\.]*[a-zA-Z0-9])?$"
        if re.match(hostname_pattern, hostname):
            return value

        raise serializers.ValidationError("无效的主机名格式")


class MCPToolSerializer(serializers.ModelSerializer):
    """MCP 工具序列化器"""



    mcp_name = serializers.CharField(source="mcp_config.name", read_only=True)
    effective_require_hitl = serializers.BooleanField(read_only=True)

    class Meta:
        model = MCPTool
        fields = [
            "id",
            "name",
            "description",
            "input_schema",
            "mcp_name",
            "require_hitl",
            "effective_require_hitl",
            "synced_at",
        ]
        read_only_fields = ["synced_at"]
