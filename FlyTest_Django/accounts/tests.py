from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from accounts.serializers import ContentTypeSerializer
from accounts.models import UserApproval, ensure_user_approval_record, is_user_approved
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


class UserRegistrationApprovalTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="approval-admin",
            email="approval-admin@example.com",
            password="Admin123456",
            is_staff=True,
        )

    def test_register_creates_pending_user_without_staff_privileges(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "username": "pending-user",
                "email": "pending-user@example.com",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="pending-user")
        self.assertFalse(user.is_staff)
        approval = user.approval_record
        self.assertEqual(approval.status, UserApproval.STATUS_PENDING)
        self.assertFalse(is_user_approved(user))

    def test_pending_user_permissions_endpoint_returns_empty_list(self):
        user = User.objects.create_user(
            username="pending-perm-user",
            email="pending-perm-user@example.com",
            password="Testpass123!",
        )
        user.user_permissions.add(Permission.objects.first())

        self.client.force_authenticate(user=user)
        response = self.client.get(f"/api/accounts/users/{user.id}/permissions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    def test_pending_user_cannot_access_model_permission_protected_endpoint(self):
        user = User.objects.create_user(
            username="pending-deny-user",
            email="pending-deny-user@example.com",
            password="Testpass123!",
        )

        self.client.force_authenticate(user=user)
        response = self.client.get("/api/accounts/content-types/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_approve_user(self):
        user = User.objects.create_user(
            username="approve-me",
            email="approve-me@example.com",
            password="Testpass123!",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/accounts/users/{user.id}/approve/",
            {"review_note": "审核通过"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        approval = user.approval_record
        self.assertEqual(approval.status, UserApproval.STATUS_APPROVED)
        self.assertEqual(approval.review_note, "审核通过")
        self.assertEqual(approval.reviewed_by, self.admin)

    def test_admin_can_reject_user_and_clear_permissions(self):
        user = User.objects.create_user(
            username="reject-me",
            email="reject-me@example.com",
            password="Testpass123!",
        )
        user.user_permissions.add(Permission.objects.first())

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f"/api/accounts/users/{user.id}/reject/",
            {"review_note": "资料不完整"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        approval = user.approval_record
        self.assertEqual(approval.status, UserApproval.STATUS_REJECTED)
        self.assertEqual(approval.review_note, "资料不完整")
        self.assertEqual(user.user_permissions.count(), 0)
        self.assertEqual(user.groups.count(), 0)

    def test_admin_can_filter_pending_users(self):
        pending_user = User.objects.create_user(
            username="pending-filter-user",
            email="pending-filter-user@example.com",
            password="Testpass123!",
        )
        approved_user = User.objects.create_user(
            username="approved-filter-user",
            email="approved-filter-user@example.com",
            password="Testpass123!",
            is_staff=True,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/accounts/users/?approval_status=pending")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data}
        self.assertIn(pending_user.username, usernames)
        self.assertNotIn(approved_user.username, usernames)

    def test_admin_can_fetch_approval_summary(self):
        User.objects.create_user(
            username="summary-pending-user",
            email="summary-pending-user@example.com",
            password="Testpass123!",
        )
        rejected_user = User.objects.create_user(
            username="summary-rejected-user",
            email="summary-rejected-user@example.com",
            password="Testpass123!",
        )
        ensure_user_approval_record(
            rejected_user,
            status=UserApproval.STATUS_REJECTED,
            reviewed_by=self.admin,
            review_note="驳回",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/accounts/users/approval-summary/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertGreaterEqual(response.data["data"]["pending"], 1)
        self.assertGreaterEqual(response.data["data"]["approved"], 1)
        self.assertGreaterEqual(response.data["data"]["rejected"], 1)


class CurrentUserProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="profile-user",
            email="profile-user@example.com",
            password="Testpass123!",
        )
        self.client.force_authenticate(user=self.user)

    def test_can_update_current_user_profile(self):
        response = self.client.put(
            "/api/accounts/profile/",
            {
                "email": "updated-profile@example.com",
                "phone_number": "13800000000",
                "real_name": "张三",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "updated-profile@example.com")
        self.assertEqual(self.user.profile.phone_number, "13800000000")
        self.assertEqual(self.user.profile.real_name, "张三")

    def test_can_change_current_user_password(self):
        response = self.client.post(
            "/api/accounts/change-password/",
            {
                "current_password": "Testpass123!",
                "new_password": "Newpass123!",
                "confirm_password": "Newpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Newpass123!"))
