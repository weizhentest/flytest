# 导入路由拼装函数。
from django.urls import include, path

# 导入 DRF 默认路由器。
from rest_framework.routers import DefaultRouter

# 导入项目视图集。
from .views import ProjectViewSet

# 创建路由器并注册视图集
router = DefaultRouter()
router.register(r'', ProjectViewSet, basename='project')  # 项目模块主路由。

# URL模式
urlpatterns = [
    path('', include(router.urls)),  # 挂载项目视图集自动路由。
]
