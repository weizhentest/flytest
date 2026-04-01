# 导入 DRF 默认路由器。
from rest_framework.routers import DefaultRouter

# 导入 API Key 视图集。
from .views import APIKeyViewSet

# 创建 API Key 模块路由器。
router = DefaultRouter()
router.register(r'api-keys', APIKeyViewSet, basename='api-key')  # API Key CRUD 路由。

# 导出路由列表供主路由 include。
urlpatterns = router.urls
