from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from projects.models import Project, ProjectDeletionRequest, ProjectMember


class ProjectDeletionFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(username='owner', password='password123')
        self.admin = User.objects.create_user(username='admin', password='password123', is_staff=True)

        content_type = ContentType.objects.get_for_model(Project)
        for codename in ['view_project', 'delete_project']:
            permission = Permission.objects.get(codename=codename, content_type=content_type)
            self.owner.user_permissions.add(permission)

        self.project = Project.objects.create(name='Deletion Project', description='demo', creator=self.owner)
        ProjectMember.objects.create(project=self.project, user=self.owner, role='owner')
        ProjectMember.objects.create(project=self.project, user=self.admin, role='admin')

    def test_delete_project_creates_pending_request(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.delete(f'/api/projects/{self.project.id}/')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        deletion_request = ProjectDeletionRequest.objects.get(project=self.project)
        self.assertEqual(deletion_request.status, ProjectDeletionRequest.STATUS_PENDING)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_deleted)

    def test_admin_can_approve_and_restore_project(self):
        deletion_request = ProjectDeletionRequest.objects.create(
            project=self.project,
            project_name=self.project.name,
            project_display_id=self.project.id,
            requested_by=self.owner,
            requested_by_name='owner',
        )

        self.client.force_authenticate(user=self.admin)
        approve_response = self.client.post(f'/api/projects/deletion-requests/{deletion_request.id}/approve/')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        deletion_request.refresh_from_db()
        self.assertTrue(self.project.is_deleted)
        self.assertEqual(deletion_request.status, ProjectDeletionRequest.STATUS_APPROVED)

        restore_response = self.client.post(f'/api/projects/deletion-requests/{deletion_request.id}/restore/')
        self.assertEqual(restore_response.status_code, status.HTTP_200_OK)

        self.project.refresh_from_db()
        deletion_request.refresh_from_db()
        self.assertFalse(self.project.is_deleted)
        self.assertEqual(deletion_request.status, ProjectDeletionRequest.STATUS_RESTORED)
