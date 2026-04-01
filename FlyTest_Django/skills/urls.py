# 导入路由拼装函数。
from django.urls import include, path

# 导入 DRF 默认路由器。
from rest_framework.routers import DefaultRouter

# 导入 Skill 视图集。
from .views import SkillViewSet

# 创建 Skill 模块路由器。
router = DefaultRouter()
router.register(r'', SkillViewSet, basename='skill')  # Skill CRUD/动作路由。

urlpatterns = [
    path('', include(router.urls)),  # 挂载 Skill 视图集自动路由。
]
