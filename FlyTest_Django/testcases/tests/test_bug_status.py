from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from testcases.models import TestBug, TestSuite


class TestBugStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="bugadmin",
            email="bugadmin@example.com",
            password="password",
        )
        self.project = Project.objects.create(
            name="Bug Project",
            description="Bug status tests",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=self.user, role="admin")
        self.suite = TestSuite.objects.create(
            project=self.project,
            name="Bug Suite",
            creator=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_bug(self, **overrides):
        payload = {
            "project": self.project,
            "suite": self.suite,
            "title": "截止时间状态测试",
            "opened_by": self.user,
            "assigned_to": self.user,
            "status": TestBug.STATUS_ASSIGNED,
            "deadline": timezone.localdate() - timedelta(days=1),
        }
        payload.update(overrides)
        bug = TestBug.objects.create(**payload)
        bug.assigned_users.set([self.user])
        return bug

    def test_effective_status_recovers_after_deadline_moved_to_future(self):
        bug = self._create_bug()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_EXPIRED)

        response = self.client.patch(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/",
            {"deadline": (timezone.localdate() + timedelta(days=7)).isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.status, TestBug.STATUS_ASSIGNED)
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)
        self.assertEqual(response.data["status"], TestBug.STATUS_ASSIGNED)

    def test_legacy_expired_status_is_treated_as_dynamic_overlay_only(self):
        bug = self._create_bug(deadline=timezone.localdate() + timedelta(days=3))
        TestBug.objects.filter(id=bug.id).update(status=TestBug.STATUS_EXPIRED)

        bug.refresh_from_db()
        self.assertEqual(bug.status, TestBug.STATUS_EXPIRED)
        self.assertEqual(bug.get_workflow_status(), TestBug.STATUS_ASSIGNED)
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)

        response = self.client.get(f"/api/projects/{self.project.id}/test-bugs/{bug.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], TestBug.STATUS_ASSIGNED)
