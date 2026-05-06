from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMember


class ProjectMemberVisibilityTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner_case", password="pass123456")
        self.member = User.objects.create_user(username="member_case", password="pass123456")
        self.project = Project.objects.create(
            name="成员可见项目",
            description="验证项目成员无需额外全局查看权限也能看到项目",
            creator=self.owner,
        )
        ProjectMember.objects.create(project=self.project, user=self.owner, role="owner")
        ProjectMember.objects.create(project=self.project, user=self.member, role="member")

    def test_member_can_list_joined_projects_without_global_view_permission(self):
        self.client.force_authenticate(self.member)

        response = self.client.get("/api/projects/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project.id, [item["id"] for item in response.data])

    def test_member_can_retrieve_joined_project_without_global_view_permission(self):
        self.client.force_authenticate(self.member)

        response = self.client.get(f"/api/projects/{self.project.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("id"), self.project.id)
