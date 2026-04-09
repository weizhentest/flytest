"""
flytest_django 项目的 URL 路由配置。

更多说明见：
https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedSimpleRouter
from accounts.views import CookieTokenRefreshView, MyTokenObtainPairView
from projects.views import ProjectViewSet
from testcases.views import (
    TestCaseViewSet,
    TestCaseModuleViewSet,
    TestSuiteViewSet,
    TestExecutionViewSet,
)

from skills.views import SkillViewSet
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from flytest_django.spa_views import serve_spa_asset, serve_spa_index

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
projects_router = NestedSimpleRouter(router, r"projects", lookup="project")
projects_router.register(r"testcases", TestCaseViewSet, basename="project-testcases")
projects_router.register(
    r"testcase-modules",
    TestCaseModuleViewSet,
    basename="project-testcase-modules",
)
projects_router.register(
    r"test-suites", TestSuiteViewSet, basename="project-test-suites"
)
projects_router.register(
    r"test-executions",
    TestExecutionViewSet,
    basename="project-test-executions",
)
projects_router.register(r"skills", SkillViewSet, basename="project-skills")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("api/accounts/", include("accounts.urls")),
    path("api/", include(router.urls)),
    path("api/", include(projects_router.urls)),
    path("api/lg/", include("langgraph_integration.urls")),
    path("api/mcp_tools/", include("mcp_tools.urls")),
    path("api/", include("api_keys.urls")),
    path("api/knowledge/", include("knowledge.urls")),
    path("api/prompts/", include("prompts.urls")),
    path("api/requirements/", include("requirements.urls")),
    path("api/data-factory/", include("data_factory.urls")),
    path("api/orchestrator/", include("orchestrator_integration.urls")),
    path("api/", include("testcase_templates.urls")),
    path("api/ui-automation/", include("ui_automation.urls")),
    path("api/api-automation/", include("api_automation.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

urlpatterns += [
    re_path(
        r"^(?P<asset_path>(assets/.*|favicon\.svg|logo\.svg|app-icon\.svg|manifest\.json|FlyTest\.png|login-fingerprint\.svg|vite\.svg|\.htaccess))$",
        serve_spa_asset,
    ),
    re_path(r"^(?!api/|admin/|media/|static/).*$", serve_spa_index),
]

# 开发环境下提供媒体文件访问路由
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# 开发环境下提供静态文件访问路由
urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT if hasattr(settings, "STATIC_ROOT") else None,
)
