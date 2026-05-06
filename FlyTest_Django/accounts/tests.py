import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.conf import settings
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from accounts.serializers import ContentTypeSerializer
from accounts.models import UserApproval, ensure_user_approval_record, ensure_user_profile, is_user_approved
from accounts.throttles import RegisterRateThrottle
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

        user = User.objects.create_user(
            username="cookie-user",
            email="cookie-user@example.com",
            password="testpass123",
        )
        profile = ensure_user_profile(user)
        profile.phone_number = "13800000090"
        profile.save(update_fields=["phone_number", "updated_at"])
        return user

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_login_sets_http_only_auth_cookies(self):
        response = self.client.post(
            "/api/token/",
            {"username": "13800000090", "password": "testpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.JWT_ACCESS_COOKIE_NAME, response.cookies)
        self.assertIn(settings.JWT_REFRESH_COOKIE_NAME, response.cookies)
        self.assertTrue(response.cookies[settings.JWT_ACCESS_COOKIE_NAME]["httponly"])
        self.assertTrue(response.cookies[settings.JWT_REFRESH_COOKIE_NAME]["httponly"])

    def test_login_with_remember_me_sets_refresh_cookie_for_30_days(self):
        response = self.client.post(
            "/api/token/",
            {
                "username": "13800000090",
                "password": "testpass123",
                "remember_me": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        refresh_cookie = response.cookies[settings.JWT_REFRESH_COOKIE_NAME]
        self.assertEqual(int(refresh_cookie["max-age"]), settings.JWT_REMEMBER_ME_DAYS * 24 * 60 * 60)

    def test_refresh_works_with_refresh_cookie_only(self):
        login_response = self.client.post(
            "/api/token/",
            {"username": "13800000090", "password": "testpass123"},
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
            {"username": "13800000090", "password": "testpass123"},
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
            {"username": "13800000090", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.post("/api/accounts/logout/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[settings.JWT_ACCESS_COOKIE_NAME].value, "")
        self.assertEqual(response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value, "")


class UserRegistrationApprovalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="approval-admin",
            email="approval-admin@example.com",
            password="Admin123456",
            is_staff=True,
        )

    def _rendered_payload(self, response):
        if hasattr(response, "render"):
            response.render()
        return json.loads(response.content.decode("utf-8"))

    def test_register_creates_pending_user_without_staff_privileges(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000000",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(profile__phone_number="13800000000")
        self.assertFalse(user.is_staff)
        self.assertRegex(user.username, r"^(?=.*[A-Za-z])[A-Za-z0-9]{3,}$")
        self.assertFalse(user.username.isdigit())
        self.assertEqual(user.profile.phone_number, "13800000000")
        self.assertEqual(user.profile.real_name, "张三")
        approval = user.approval_record
        self.assertEqual(approval.status, UserApproval.STATUS_PENDING)
        self.assertFalse(is_user_approved(user))

    def test_register_auto_assigns_unique_alphanumeric_username(self):
        first_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000001",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )
        second_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000002",
                "real_name": "李四",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        first_user = User.objects.get(profile__phone_number="13800000001")
        second_user = User.objects.get(profile__phone_number="13800000002")
        self.assertNotEqual(first_user.username, second_user.username)
        self.assertRegex(first_user.username, r"^(?=.*[A-Za-z])[A-Za-z0-9]{3,}$")
        self.assertRegex(second_user.username, r"^(?=.*[A-Za-z])[A-Za-z0-9]{3,}$")

    def test_register_rejects_invalid_phone_number(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "123456",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)
        payload = self._rendered_payload(response)
        self.assertEqual(payload["message"], "请填写真实的手机号。")
        self.assertEqual(payload["errors"]["phone_number"][0], "请填写真实的手机号。")

    def test_register_rejects_duplicate_phone_number(self):
        self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000003",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )

        response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000003",
                "real_name": "李四",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)
        payload = self._rendered_payload(response)
        self.assertEqual(payload["message"], "该手机号已被注册。")
        self.assertEqual(payload["errors"]["phone_number"][0], "该手机号已被注册。")

    def test_register_rejects_non_chinese_real_name(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000004",
                "real_name": "Tom",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("real_name", response.data)
        payload = self._rendered_payload(response)
        self.assertEqual(payload["message"], "姓名仅支持2到20位中文。")
        self.assertEqual(payload["errors"]["real_name"][0], "姓名仅支持2到20位中文。")

    def test_register_rejects_duplicate_real_name(self):
        self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000031",
                "real_name": "寮犱笁",
                "password": "Testpass123!",
            },
            format="json",
        )

        response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000032",
                "real_name": "寮犱笁",
                "password": "Testpass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("real_name", response.data)
        payload = self._rendered_payload(response)
        self.assertEqual(payload["message"], "该姓名已被使用，请更换后重试。")
        self.assertEqual(payload["errors"]["real_name"][0], "该姓名已被使用，请更换后重试。")

    def test_login_supports_phone_number_after_registration(self):
        register_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000005",
                "real_name": "王五",
                "password": "Testpass123!",
            },
            format="json",
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(profile__phone_number="13800000005")
        ensure_user_approval_record(user, status=UserApproval.STATUS_APPROVED)

        response = self.client.post(
            "/api/token/",
            {"username": "13800000005", "password": "Testpass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_supports_system_username(self):
        user = User.objects.create_user(
            username="phone-only-user",
            email="phone-only@example.com",
            password="Testpass123!",
        )
        profile = ensure_user_profile(user)
        profile.phone_number = "13800000006"
        profile.save(update_fields=["phone_number", "updated_at"])
        ensure_user_approval_record(user, status=UserApproval.STATUS_APPROVED)

        response = self.client.post(
            "/api/token/",
            {"username": "phone-only-user", "password": "Testpass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch.dict(RegisterRateThrottle.THROTTLE_RATES, {"register": "1/hour"}, clear=False)
    def test_failed_register_attempts_do_not_consume_throttle_quota(self):
        invalid_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "123456",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

        valid_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000110",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )
        self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)

    @patch.dict(RegisterRateThrottle.THROTTLE_RATES, {"register": "1/hour"}, clear=False)
    def test_only_successful_registers_are_throttled(self):
        first_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000111",
                "real_name": "张三",
                "password": "Testpass123!",
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post(
            "/api/accounts/register/",
            {
                "phone_number": "13800000112",
                "real_name": "李四",
                "password": "Testpass123!",
            },
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_pending_user_permissions_endpoint_returns_empty_list(self):
        user = User.objects.create_user(
            username="pending-perm-user",
            email="pending-perm-user@example.com",
            password="Testpass123!",
        )
        ensure_user_approval_record(user, status=UserApproval.STATUS_PENDING)
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
        ensure_user_approval_record(user, status=UserApproval.STATUS_PENDING)

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
        ensure_user_approval_record(pending_user, status=UserApproval.STATUS_PENDING)
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
        pending_user = User.objects.get(username="summary-pending-user")
        ensure_user_approval_record(
            pending_user,
            status=UserApproval.STATUS_PENDING,
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
        profile = ensure_user_profile(self.user)
        profile.phone_number = "13800000091"
        profile.save(update_fields=["phone_number", "updated_at"])
        self.client.force_authenticate(user=self.user)

    def _payload(self, response):
        if isinstance(response.data, dict) and "data" in response.data:
            return response.data["data"]
        return response.data

    def test_can_update_current_user_profile(self):
        response = self.client.put(
            "/api/accounts/profile/",
            {
                "username": "profileuser01",
                "email": "updated-profile@example.com",
                "phone_number": "13800000000",
                "real_name": "张三",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "profileuser01")
        self.assertEqual(self.user.email, "updated-profile@example.com")
        self.assertEqual(self.user.profile.phone_number, "13800000000")
        self.assertEqual(self.user.profile.real_name, "张三")
        self.assertIsNotNone(self.user.profile.username_changed_at)

    def test_updated_profile_is_visible_in_user_management_list(self):
        admin = User.objects.create_user(
            username="profile-admin",
            email="profile-admin@example.com",
            password="Admin123456",
            is_staff=True,
        )

        self.client.put(
            "/api/accounts/profile/",
            {
                "email": "updated-profile@example.com",
                "phone_number": "13800000000",
                "real_name": "张三",
            },
            format="json",
        )

        self.client.force_authenticate(user=admin)
        response = self.client.get("/api/accounts/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile_row = next(item for item in response.data if item["username"] == "profile-user")
        self.assertEqual(profile_row["real_name"], "张三")
        self.assertEqual(profile_row["phone_number"], "13800000000")

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

    def test_profile_partial_update_allows_phone_only(self):
        response = self.client.put(
            "/api/accounts/profile/",
            {
                "phone_number": "13900000000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.phone_number, "13900000000")

    def test_profile_rejects_duplicate_username(self):
        User.objects.create_user(
            username="profileuser88",
            email="another@example.com",
            password="Testpass123!",
        )

        response = self.client.put(
            "/api/accounts/profile/",
            {
                "username": "profileuser88",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_profile_rejects_duplicate_real_name(self):
        other_user = User.objects.create_user(
            username="profileuser66",
            email="realname@example.com",
            password="Testpass123!",
        )
        other_profile = ensure_user_profile(other_user)
        other_profile.real_name = "鏉庡洓"
        other_profile.save(update_fields=["real_name", "updated_at"])

        response = self.client.put(
            "/api/accounts/profile/",
            {
                "real_name": "鏉庡洓",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("real_name", response.data)

    def test_profile_rejects_second_username_change_within_30_days(self):
        profile = ensure_user_profile(self.user)
        profile.username_changed_at = timezone.now()
        profile.save(update_fields=["username_changed_at", "updated_at"])

        response = self.client.put(
            "/api/accounts/profile/",
            {
                "username": "profileuser99",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_change_password_invalidates_existing_access_and_refresh_tokens(self):
        self.client.force_authenticate(user=None)
        token_response = self.client.post(
            "/api/token/",
            {"username": "13800000091", "password": "Testpass123!"},
            format="json",
        )
        payload = self._payload(token_response)
        access_token = payload["access"]
        refresh_token = payload["refresh"]

        response = self.client.post(
            "/api/accounts/change-password/",
            {
                "current_password": "Testpass123!",
                "new_password": "Newpass123!",
                "confirm_password": "Newpass123!",
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[settings.JWT_ACCESS_COOKIE_NAME].value, "")
        self.assertEqual(response.cookies[settings.JWT_REFRESH_COOKIE_NAME].value, "")

        old_access_response = self.client.get(
            "/api/accounts/me/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        self.assertEqual(old_access_response.status_code, status.HTTP_401_UNAUTHORIZED)

        refresh_response = self.client.post(
            "/api/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)
