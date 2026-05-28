from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project, ProjectMember


class ProjectStaffAdminAccessTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="staff_owner", password="pass123456")
        self.member = User.objects.create_user(username="staff_member", password="pass123456")
        self.staff_admin = User.objects.create_user(
            username="platform_admin",
            password="pass123456",
            is_staff=True,
        )

        project_content_type = ContentType.objects.get_for_model(Project)
        view_project_permission = Permission.objects.get(
            codename="view_project",
            content_type=project_content_type,
        )
        self.staff_admin.user_permissions.add(view_project_permission)

        self.project = Project.objects.create(
            name="Staff Access Project",
            description="verify staff admin project access",
            creator=self.owner,
        )
        ProjectMember.objects.create(project=self.project, user=self.owner, role="owner")
        ProjectMember.objects.create(project=self.project, user=self.member, role="member")

    def test_staff_admin_can_view_project_members_without_membership(self):
        self.client.force_authenticate(self.staff_admin)

        response = self.client.get(f"/api/projects/{self.project.id}/members/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_staff_admin_can_remove_project_member_without_membership(self):
        self.client.force_authenticate(self.staff_admin)

        response = self.client.delete(
            f"/api/projects/{self.project.id}/remove_member/",
            {"user_id": self.member.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.project, user=self.member).exists()
        )


class ProjectPermissionAdminAccessTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="perm_owner", password="pass123456")
        self.member = User.objects.create_user(username="perm_member", password="pass123456")
        self.permission_admin = User.objects.create_user(username="perm_admin", password="pass123456")

        project_content_type = ContentType.objects.get_for_model(Project)
        project_member_content_type = ContentType.objects.get_for_model(ProjectMember)
        for content_type, codename in [
            (project_content_type, "view_project"),
            (project_content_type, "change_project"),
            (project_member_content_type, "view_projectmember"),
            (project_member_content_type, "delete_projectmember"),
        ]:
            permission = Permission.objects.get(codename=codename, content_type=content_type)
            self.permission_admin.user_permissions.add(permission)

        self.project = Project.objects.create(
            name="Permission Admin Project",
            description="verify direct permission admin access",
            creator=self.owner,
        )
        ProjectMember.objects.create(project=self.project, user=self.owner, role="owner")
        ProjectMember.objects.create(project=self.project, user=self.member, role="member")
        ProjectMember.objects.create(project=self.project, user=self.permission_admin, role="member")

    def test_permission_admin_can_list_projects(self):
        self.client.force_authenticate(self.permission_admin)

        response = self.client.get("/api/projects/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project.id, [item["id"] for item in response.data])

    def test_permission_admin_can_remove_project_member(self):
        self.client.force_authenticate(self.permission_admin)

        response = self.client.delete(
            f"/api/projects/{self.project.id}/remove_member/",
            {"user_id": self.member.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ProjectMember.objects.filter(project=self.project, user=self.member).exists()
        )

    def test_removed_permission_admin_cannot_list_or_retrieve_project(self):
        ProjectMember.objects.filter(project=self.project, user=self.permission_admin).delete()
        self.client.force_authenticate(self.permission_admin)

        list_response = self.client.get("/api/projects/")
        retrieve_response = self.client.get(f"/api/projects/{self.project.id}/")

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.project.id, [item["id"] for item in list_response.data])
        self.assertEqual(retrieve_response.status_code, status.HTTP_403_FORBIDDEN)
