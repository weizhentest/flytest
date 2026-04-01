"""
UI自动化 WebSocket 路由配置
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # 前端WebSocket连接
    re_path(r'ws/ui/web/$', consumers.UiAutomationConsumer.as_asgi()),
    # 执行器WebSocket连接
    re_path(r'ws/ui/actuator/$', consumers.UiAutomationConsumer.as_asgi()),
]
