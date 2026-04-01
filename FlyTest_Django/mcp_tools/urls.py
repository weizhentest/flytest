from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views  # 导入整个 views 模块

router = DefaultRouter()
router.register(
    r"remote-configs", views.RemoteMCPConfigViewSet, basename="remote-mcp-config"
)

app_name = "mcp_tools"  # 可选：如后续需要可用于 URL 命名空间

urlpatterns = [
    # 新增用于探测远程 MCP 配置连通性的 URL（需放在 router.urls 前避免冲突）
    path(
        "remote-configs/ping/",
        views.RemoteMCPConfigPingView.as_view(),
        name="remote-mcp-config-ping",
    ),
    # 直接引入 RemoteMCPConfigViewSet 的 router 路由
    path("", include(router.urls)),
    # 新增通用端点：调用任意已注册 MCP 工具
    path("call/", views.MCPToolRunnerView.as_view(), name="mcp_call_tool"),
]
