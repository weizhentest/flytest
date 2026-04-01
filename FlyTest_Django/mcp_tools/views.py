from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Q
from asgiref.sync import sync_to_async

from projects.models import Project  # 假设 Project 模型位于 'projects' 应用
from .serializers import MCPProjectListSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication  # 导入 JWT 认证
from .models import RemoteMCPConfig
from .serializers import RemoteMCPConfigSerializer

# import urllib.request # 不再需要
# import urllib.parse # 不再需要
# import urllib.error # 不再需要
import json
import asyncio  # 确保导入 asyncio
import logging  # 导入 logging 模块

# from fastmcp import Client # 此处不再直接使用
# from fastmcp.client.transports import StreamableHttpTransport # 此处不再直接使用
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
)  # 导入 LangGraph 的 MCP 客户端
from flytest_django.permissions import HasModelPermission

logger = logging.getLogger(__name__)  # 获取日志实例


# --- 工具实现函数 ---
def _get_project_list_tool(request_user, arguments: dict):
    """
    实现 'get_project_list' 工具的核心逻辑。
    当前 'arguments' 暂未使用，保留给后续筛选/分页等参数。
    """
    # 确保 request_user 已认证（理论上应由视图 permission_classes 兜底）。
    if not request_user or not request_user.is_authenticated:
        # 若权限配置正确，通常不会走到这里。
        raise PermissionError("User is not authenticated.")

    accessible_projects = (
        Project.objects.filter(Q(creator=request_user) | Q(members=request_user))
        .distinct()
        .order_by("-created_at")
    )

    serializer = MCPProjectListSerializer(accessible_projects, many=True)
    return serializer.data


# --- 工具注册表 ---
# 将工具名映射到对应实现函数。
# 每个函数都应接收 'request_user' 与 'arguments'（dict）。
TOOL_REGISTRY = {
    "get_project_list": _get_project_list_tool,
    # 后续工具可在此扩展。
}


# --- MCP 工具执行入口视图 ---
class MCPToolRunnerView(APIView):
    """
    通用 MCP 工具执行视图：
    根据传入的工具名与参数执行对应工具。
    该视图是本 Django 应用处理 MCP 工具调用的统一入口。
    """


    authentication_classes = [JWTAuthentication]  # 使用 JWT 认证
    permission_classes = [
        permissions.IsAuthenticated
    ]  # 仅做基础认证，细粒度权限在 post 中处理

    def post(self, request, *args, **kwargs):
        # 检查MCP工具执行权限 (这里可以定义具体需要的权限)
        if not request.user.has_perm("mcp_tools.add_remotemcpconfig"):
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You do not have permission to execute MCP tools.",
                    "data": {},
                    "errors": {
                        "permission": ["mcp_tools.add_remotemcpconfig required"]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        tool_name = request.data.get("name")
        tool_arguments = request.data.get("arguments", {})  # 未提供时默认为空字典

        if not tool_name:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Tool name ('name') is required in the request body.",
                    "data": {},
                    "errors": {"name": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tool_function = TOOL_REGISTRY.get(tool_name)

        if not tool_function:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": f"Tool '{tool_name}' not found.",
                    "data": {},
                    "errors": {"name": [f"Tool '{tool_name}' is not registered."]},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # 将认证用户（request.user）与参数传入工具函数
            result_data = tool_function(request.user, tool_arguments)

            # MCP CallToolResponseSchema 期望返回 content item 列表。
            # 为简化处理，这里直接返回工具结果数据。
            # 但在已知解析规则的 LangGraph 内部场景下，
            # 直接放在统一响应的 data 字段通常更实用。
            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": f"Tool '{tool_name}' executed successfully.",
                    "data": result_data,
                },
                status=status.HTTP_200_OK,
            )

        except PermissionError as pe:  # 捕获工具函数抛出的权限异常
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": f"Permission denied while executing tool '{tool_name}': {str(pe)}",
                    "data": {},
                    "errors": {tool_name: [str(pe)]},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except Exception as e:
            # 生产环境建议完整记录此异常日志。
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": f"An unexpected error occurred while executing tool '{tool_name}'.",
                    "data": {},
                    "errors": {tool_name: [str(e)]},  # 生产环境应避免暴露过多内部细节
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


from rest_framework import viewsets
from rest_framework.decorators import action
from asgiref.sync import async_to_sync


class RemoteMCPConfigPingView(APIView):
    """
    用于检查远程 MCP 配置连通状态的 API 端点。
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated
    ]  # 仅做基础认证，细粒度权限在 post 中处理

    async def dispatch(self, request, *args, **kwargs):
        self.request = request
        self.args = args
        self.kwargs = kwargs
        request = await sync_to_async(self.initialize_request)(request, *args, **kwargs)
        self.request = request
        self.headers = await sync_to_async(lambda: self.default_response_headers)()

        try:
            await sync_to_async(self.initial)(request, *args, **kwargs)

            if request.method.lower() in self.http_method_names:
                handler = getattr(
                    self, request.method.lower(), self.http_method_not_allowed
                )
            else:
                handler = self.http_method_not_allowed

            response = await handler(request, *args, **kwargs)

        except Exception as exc:
            response = await sync_to_async(self.handle_exception)(exc)

        self.response = await sync_to_async(self.finalize_response)(
            request, response, *args, **kwargs
        )
        return self.response

    async def post(self, request, *args, **kwargs):
        # 检查MCP配置管理权限 (异步)
        has_permission = await sync_to_async(request.user.has_perm)(
            "mcp_tools.view_remotemcpconfig"
        )
        if not has_permission:
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_403_FORBIDDEN,
                    "message": "You do not have permission to ping MCP configurations.",
                    "data": {},
                    "errors": {
                        "permission": ["mcp_tools.view_remotemcpconfig required"]
                    },
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        logger.info("Entering RemoteMCPConfigPingView.post method.")
        config_id = request.data.get("config_id")
        logger.info(f"Received config_id: {config_id}")

        if not config_id:
            logger.warning("Config ID not provided in the request.")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_400_BAD_REQUEST,
                    "message": "Config ID ('config_id') is required in the request body.",
                    "data": {},
                    "errors": {"config_id": ["This field is required."]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logger.info(f"Attempting to retrieve RemoteMCPConfig with ID: {config_id}")
            config = await sync_to_async(RemoteMCPConfig.objects.get)(id=config_id)
            logger.info(
                f"Successfully retrieved RemoteMCPConfig: {config.name} (ID: {config.id})"
            )
        except RemoteMCPConfig.DoesNotExist:
            logger.error(f"Remote MCP Configuration with ID {config_id} not found.")
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_404_NOT_FOUND,
                    "message": "Remote MCP Configuration not found.",
                    "data": {},
                    "errors": {"config_id": ["Configuration not found."]},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 直接使用配置中的 URL。
        # MultiServerMCPClient 与底层 FastMCP 会根据 transport 在需要时自动补齐 /mcp。
        target_mcp_url = config.url
        logger.info(f"Using MCP server URL from config: {target_mcp_url}")

        try:
            # 准备 MultiServerMCPClient 配置
            server_config_key = (
                config.name or "target_server"
            )  # 使用配置名；为空时使用默认键名

            client_config = {
                server_config_key: {
                    "url": target_mcp_url,  # 直接使用配置中的 URL
                    # 若 transport 使用连字符写法，这里统一转换
                    "transport": (config.transport or "sse").replace("-", "_"),
                }
            }

            # 若 headers 存在且为字典，则附加到客户端配置
            if config.headers and isinstance(config.headers, dict) and config.headers:
                client_config[server_config_key]["headers"] = config.headers
                logger.info(
                    f"Using custom headers for MultiServerMCPClient: {config.headers}"
                )
            else:
                logger.info(
                    "No custom headers provided or headers are not a valid dictionary for MultiServerMCPClient."
                )

            logger.info(
                f"Attempting to connect to MCP server using MultiServerMCPClient with config: {client_config}"
            )

            # 实例化 MultiServerMCPClient
            # 注意：MultiServerMCPClient 本身不是异步上下文管理器，
            # 但其 get_tools 等方法是异步调用。
            mcp_client = MultiServerMCPClient(client_config)

            # 通过 get_tools() 作为“探活”手段，检查连通性与基础可用性。
            # 该调用会尝试连接并从 /mcp/tools 拉取工具列表。
            tools_list = await mcp_client.get_tools()  # This is an async call
            tools_count = len(tools_list)
            logger.info(
                f"Successfully connected to MCP server at {target_mcp_url} and retrieved {tools_count} tools."
            )

            return Response(
                {
                    "status": "success",
                    "code": status.HTTP_200_OK,
                    "message": f"MCP server at {target_mcp_url} is online and accessible (retrieved {tools_count} tools).",
                    "data": {
                        "status": "online",
                        "url": target_mcp_url,
                        "tools_count": tools_count,
                        "tools": [
                            tool.name for tool in tools_list if hasattr(tool, "name")
                        ],  # Include names of the tools
                    },
                },
                status=status.HTTP_200_OK,
            )

        except ImportError:
            logger.error(
                "langchain-mcp-adapters library is not installed. Please install it to use this feature.",
                exc_info=True,
            )
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": "Server configuration error: langchain-mcp-adapters library not found.",
                    "data": {"status": "error", "url": target_mcp_url},
                    "errors": {
                        "mcp_check": ["langchain-mcp-adapters library not installed."]
                    },
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            logger.error(
                f"Error connecting to MCP server {target_mcp_url} using MultiServerMCPClient: {e}",
                exc_info=True,
            )
            error_message = f"Failed to connect or communicate with MCP server at {target_mcp_url}: {type(e).__name__} - {str(e)}"
            return Response(
                {
                    "status": "error",
                    "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "message": error_message,
                    "data": {"status": "error", "url": target_mcp_url},
                    "errors": {"mcp_check": [f"{type(e).__name__}: {str(e)}"]},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RemoteMCPConfigViewSet(viewsets.ModelViewSet):
    """
    远程 MCP 配置管理接口，支持查看与编辑。
    全局共享，所有用户都可以访问。
    """

    queryset = RemoteMCPConfig.objects.all()
    serializer_class = RemoteMCPConfigSerializer
    permission_classes = [permissions.IsAuthenticated, HasModelPermission]

    def get_queryset(self):
        return RemoteMCPConfig.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        """创建后自动同步工具（仅激活状态）"""
        instance = serializer.save()
        if instance.is_active:
            self._sync_tools_async(instance)

    def perform_update(self, serializer):
        """更新后自动同步工具（仅激活状态）"""
        instance = serializer.save()
        if instance.is_active:
            self._sync_tools_async(instance)

    def _sync_tools_async(self, instance):
        """异步同步工具（不阻塞请求）"""
        from .services import sync_mcp_tools
        import threading

        def sync_in_background():
            try:
                asyncio.run(sync_mcp_tools(instance))
            except Exception as e:
                logger.error(f"后台同步 MCP {instance.name} 工具失败: {e}")

        thread = threading.Thread(target=sync_in_background, daemon=True)
        thread.start()

    @action(detail=True, methods=["post"])
    def sync_tools(self, request, pk=None):
        """
        手动同步指定 MCP 配置的工具列表

        POST /api/mcp/configs/{id}/sync_tools/
        """
        from .services import sync_mcp_tools

        instance = self.get_object()

        try:
            result = async_to_sync(sync_mcp_tools)(instance)

            if result["success"]:
                return Response(
                    {
                        "status": "success",
                        "message": f"工具同步成功: 共 {result['tools_count']} 个工具",
                        "data": result,
                    }
                )
            else:
                return Response(
                    {
                        "status": "error",
                        "message": f"工具同步失败: {result.get('error', '未知错误')}",
                        "data": result,
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except Exception as e:
            logger.error(f"同步 MCP {instance.name} 工具失败: {e}", exc_info=True)
            return Response(
                {
                    "status": "error",
                    "message": f"同步失败: {str(e)}",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def tools(self, request, pk=None):
        """
        获取指定 MCP 配置的工具列表

        GET /api/mcp/configs/{id}/tools/
        """
        from .models import MCPTool
        from .serializers import MCPToolSerializer

        instance = self.get_object()
        tools = instance.tools.all()

        return Response(
            {
                "status": "success",
                "data": {
                    "mcp_name": instance.name,
                    "tools_count": tools.count(),
                    "tools": MCPToolSerializer(tools, many=True).data,
                },
            }
        )
