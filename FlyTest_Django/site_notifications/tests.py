from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import ensure_user_approval_record, ensure_user_profile
from projects.models import Project, ProjectMember
from site_notifications.models import SiteNotificationRecipient


class SiteNotificationApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="adminuser", password="Pass123456", is_staff=True)
        ensure_user_profile(self.admin)

        self.member = User.objects.create_user(username="memberuser", password="Pass123456")
        ensure_user_profile(self.member)
        ensure_user_approval_record(self.member, status="approved")

        self.project = Project.objects.create(name="通知项目", description="测试", creator=self.admin)
        ProjectMember.objects.create(project=self.project, user=self.admin, role="owner")
        ProjectMember.objects.create(project=self.project, user=self.member, role="member")

    def test_admin_can_send_project_notification(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse("site-notification-create"),
            {
                "scope": "project_members",
                "title": "项目通知",
                "content": "项目成员请注意。",
                "project_id": self.project.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SiteNotificationRecipient.objects.count(), 2)

    def test_user_can_mark_notification_read(self):
        self.client.force_authenticate(self.admin)
        self.client.post(
            reverse("site-notification-create"),
            {
                "scope": "users",
                "title": "单独通知",
                "content": "请处理消息。",
                "user_ids": [self.member.id],
            },
            format="json",
        )

        self.client.force_authenticate(self.member)
        inbox_response = self.client.get(reverse("site-notification-inbox"))
        self.assertEqual(inbox_response.status_code, status.HTTP_200_OK)
        item_id = inbox_response.data["items"][0]["id"]

        mark_read_response = self.client.post(reverse("site-notification-mark-read", kwargs={"pk": item_id}))
        self.assertEqual(mark_read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mark_read_response.data["data"]["unread_count"], 0)

    def test_replies_are_visible_to_all_recipients(self):
        self.client.force_authenticate(self.admin)
        create_response = self.client.post(
            reverse("site-notification-create"),
            {
                "scope": "project_members",
                "title": "协作通知",
                "content": "请大家确认收到。",
                "project_id": self.project.id,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.member)
        inbox_response = self.client.get(reverse("site-notification-inbox"))
        recipient_id = inbox_response.data["items"][0]["id"]

        reply_response = self.client.post(
            reverse("site-notification-replies", kwargs={"pk": recipient_id}),
            {"content": "收到，我会跟进处理。"},
            format="json",
        )
        self.assertEqual(reply_response.status_code, status.HTTP_201_CREATED)

        detail_response = self.client.get(reverse("site-notification-detail", kwargs={"pk": recipient_id}))
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["reply_count"], 1)
        self.assertEqual(detail_response.data["replies"][0]["content"], "收到，我会跟进处理。")
