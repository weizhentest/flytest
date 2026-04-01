from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserPromptViewSet

# 创建路由器并注册 ViewSet。
router = DefaultRouter()
router.register(r"user-prompts", UserPromptViewSet, basename="userprompt")

urlpatterns = [
    path("", include(router.urls)),
]
