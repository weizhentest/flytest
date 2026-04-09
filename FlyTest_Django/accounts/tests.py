from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from accounts.serializers import ContentTypeSerializer
from accounts.views import MyTokenObtainPairView, PermissionViewSet


class MyTokenObtainPairViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_returns_503_when_database_not_ready(self):
        request = self.factory.post(
            "/api/token/",
            {"username": "tester", "password": "secret"},
            format="json",
        )

        with patch(
            "accounts.views.BaseTokenObtainPairView.post",
            side_effect=OperationalError("database is not ready"),
        ):
            response = MyTokenObtainPairView.as_view()(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["detail"], "认证服务正在启动，请稍后重试。")


class PermissionMenuMappingTests(TestCase):
    def test_app_automation_permissions_are_created(self):
        self.assertTrue(
            Permission.objects.filter(content_type__app_label="app_automation").exists()
        )

    def test_api_automation_permissions_map_to_api_menu(self):
        content_type = ContentType.objects.get(
            app_label="api_automation", model="apirequest"
        )
        serializer = ContentTypeSerializer()

        self.assertEqual(serializer.get_app_label_cn(content_type), "API自动化")
        self.assertEqual(serializer.get_app_label_subcategory(content_type), "请求管理")

    def test_ui_automation_permissions_map_to_ui_submenus(self):
        content_type = ContentType.objects.get(
            app_label="ui_automation", model="uiactuator"
        )
        serializer = ContentTypeSerializer()

        self.assertEqual(serializer.get_app_label_cn(content_type), "UI自动化")
        self.assertEqual(serializer.get_app_label_subcategory(content_type), "执行器")

    def test_ui_elements_are_grouped_under_page_management(self):
        content_type = ContentType.objects.get(
            app_label="ui_automation", model="uielement"
        )
        serializer = ContentTypeSerializer()

        self.assertEqual(serializer.get_app_label_cn(content_type), "UI自动化")
        self.assertEqual(serializer.get_app_label_subcategory(content_type), "页面管理")

    def test_data_factory_permissions_map_to_visible_sections(self):
        tag_content_type = ContentType.objects.get(
            app_label="data_factory", model="datafactorytag"
        )
        record_content_type = ContentType.objects.get(
            app_label="data_factory", model="datafactoryrecord"
        )
        serializer = ContentTypeSerializer()

        self.assertEqual(serializer.get_app_label_cn(tag_content_type), "数据工厂")
        self.assertEqual(serializer.get_app_label_subcategory(tag_content_type), "标签管理")
        self.assertEqual(serializer.get_app_label_cn(record_content_type), "数据工厂")
        self.assertEqual(serializer.get_app_label_subcategory(record_content_type), "使用记录")

    def test_app_automation_model_sort_matches_menu_order(self):
        overview_content_type = ContentType.objects.get(
            app_label="app_automation", model="appautomationoverview"
        )
        report_content_type = ContentType.objects.get(
            app_label="app_automation", model="appautomationreport"
        )
        serializer = ContentTypeSerializer()

        self.assertLess(
            serializer.get_model_sort(overview_content_type),
            serializer.get_model_sort(report_content_type),
        )

    def test_permission_viewset_excludes_removed_smart_diagram_permissions(self):
        queryset = PermissionViewSet.queryset
        self.assertFalse(
            queryset.filter(content_type__app_label="orchestrator_integration").exists()
        )
        self.assertFalse(
            queryset.filter(content_type__app_label="testcase_templates").exists()
        )


class AuthCookieFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = self._create_user()

    def _create_user(self):
        from django.contrib.auth.models import User

        return User.objects.create_user(
            username="cookie-user",
            email="cookie-user@example.com",
            password="testpass123",
        )

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_login_sets_http_only_auth_cookies(self):
        response = self.client.post(
            "/api/token/",
            {"username": "cookie-user", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.JWT_ACCESS_COOKIE_NAME, response.cookies)
        self.assertIn(settings.JWT_REFRESH_COOKIE_NAME, response.cookies)
        self.assertTrue(response.cookies[settings.JWT_ACCESS_COOKIE_NAME]["httponly"])
        self.assertTrue(response.cookies[settings.JWT_REFRESH_COOKIE_NAME]["httponly"])

    def test_refresh_works_with_refresh_cookie_only(self):
        login_response = self.client.post(
            "/api/token/",
            {"username": "cookie-user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.post("/api/token/refresh/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertTrue(payload.get("access"))
        self.assertIn(settings.JWT_ACCESS_COOKIE_NAME, response.cookies)

    def test_current_user_endpoint_accepts_cookie_auth(self):
        login_response = self.client.post(
            "/api/token/",
            {"username": "cookie-user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.get("/api/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(payload["username"], "cookie-user")

    def test_logout_clears_auth_cookies(self):
        login_response = self.client.post(
            "/api/token/",
            {"username": "cookie-user", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.post("/api/accounts/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[settings.JWT_ACCESS_COOKIE_NAME].value, "")
        self.assertEqual(response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value, "")
