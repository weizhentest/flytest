from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from testcases.models import TestBug, TestCase as TestCaseModel
from testcases.models import TestCaseAssignment, TestCaseModule, TestSuite
from testcases.serializers import TestExecutionCreateSerializer, TestSuiteSerializer


class TestSuiteExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.project = Project.objects.create(
            name="Test Project",
            description="Test Description",
            creator=self.user,
        )
        self.module = TestCaseModule.objects.create(
            project=self.project,
            name="Test Module",
            creator=self.user,
        )

        self.testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 1",
            creator=self.user,
        )

        self.suite = TestSuite.objects.create(
            project=self.project,
            name="Test Suite 1",
            creator=self.user,
        )
        self.api_client = APIClient()

    def test_suite_validation_with_testcase(self):
        self.suite.testcases.add(self.testcase)

        serializer = TestExecutionCreateSerializer(data={"suite_id": self.suite.id})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_suite_validation_empty(self):
        serializer = TestExecutionCreateSerializer(data={"suite_id": self.suite.id})
        self.assertFalse(serializer.is_valid())
        self.assertIn("suite_id", serializer.errors)

    def test_suite_serializer_partial_update_keeps_assignments(self):
        self.suite.testcases.add(self.testcase)

        serializer = TestSuiteSerializer(
            instance=self.suite,
            data={"name": "Updated Suite Name"},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        updated_suite = serializer.save()
        self.assertEqual(updated_suite.name, "Updated Suite Name")
        self.assertTrue(updated_suite.testcases.exists())

    def test_suite_serializer_allows_empty_create(self):
        serializer = TestSuiteSerializer(
            data={
                "name": "Empty Suite",
                "description": "Suite without assigned cases yet",
                "max_concurrent_tasks": 1,
            },
            context={"project_id": self.project.id, "request": None},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_suite_serializer_supports_child_suite(self):
        serializer = TestSuiteSerializer(
            data={
                "name": "Child Suite",
                "description": "Nested suite",
                "parent_id": self.suite.id,
                "max_concurrent_tasks": 1,
            },
            context={"project_id": self.project.id, "request": None},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        child_suite = serializer.save(project=self.project, creator=self.user)
        self.assertEqual(child_suite.parent_id, self.suite.id)
        self.assertEqual(child_suite.level, 2)

    def test_testcase_ids_start_from_one(self):
        self.assertEqual(self.testcase.id, 1)

    def test_deleted_testcase_id_is_reused(self):
        second_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 2",
            creator=self.user,
        )
        third_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 3",
            creator=self.user,
        )

        self.assertEqual(second_case.id, 2)
        self.assertEqual(third_case.id, 3)

        second_case.delete()

        replacement_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Replacement Test Case",
            creator=self.user,
        )

        self.assertEqual(replacement_case.id, 2)

    def test_batch_assign_assigns_testcase_to_suite(self):
        admin_user = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="password",
        )
        assignee = User.objects.create_user(
            username="memberuser",
            password="password",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=admin_user,
            role="admin",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=assignee,
            role="member",
        )
        self.testcase.review_status = "approved"
        self.testcase.save(update_fields=["review_status"])

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/testcases/batch-assign/",
            {
                "ids": [self.testcase.id],
                "suite_id": self.suite.id,
                "assignee_id": assignee.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.suite.testcases.filter(id=self.testcase.id).exists())

        assignment = TestCaseAssignment.objects.get(testcase=self.testcase)
        self.assertEqual(assignment.suite_id, self.suite.id)
        self.assertEqual(assignment.assignee_id, assignee.id)
        self.assertEqual(assignment.assigned_by_id, admin_user.id)

    def test_batch_assign_rejects_unapproved_testcase(self):
        admin_user = User.objects.create_superuser(
            username="reviewadmin",
            email="reviewadmin@example.com",
            password="password",
        )
        assignee = User.objects.create_user(
            username="reviewmember",
            password="password",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=admin_user,
            role="admin",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=assignee,
            role="member",
        )
        self.testcase.review_status = "pending_review"
        self.testcase.save(update_fields=["review_status"])

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/testcases/batch-assign/",
            {
                "ids": [self.testcase.id],
                "suite_id": self.suite.id,
                "assignee_id": assignee.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["error"], "只有审核状态为“通过”的测试用例才能分配")
        self.assertFalse(TestCaseAssignment.objects.filter(testcase=self.testcase).exists())

    def test_suite_list_can_filter_by_selected_module_tree(self):
        admin_user = User.objects.create_superuser(
            username="suiteadmin",
            email="suiteadmin@example.com",
            password="password",
        )
        child_module = TestCaseModule.objects.create(
            project=self.project,
            name="Child Module",
            parent=self.module,
            creator=self.user,
        )
        child_case = TestCaseModel.objects.create(
            project=self.project,
            module=child_module,
            name="Child Case",
            creator=self.user,
        )
        sibling_module = TestCaseModule.objects.create(
            project=self.project,
            name="Sibling Module",
            creator=self.user,
        )
        sibling_case = TestCaseModel.objects.create(
            project=self.project,
            module=sibling_module,
            name="Sibling Case",
            creator=self.user,
        )
        sibling_suite = TestSuite.objects.create(
            project=self.project,
            name="Sibling Suite",
            creator=self.user,
        )

        self.suite.testcases.add(child_case)
        sibling_suite.testcases.add(sibling_case)

        ProjectMember.objects.create(
            project=self.project,
            user=admin_user,
            role="admin",
        )
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(
            f"/api/projects/{self.project.id}/test-suites/",
            {"module_id": self.module.id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"] if isinstance(response.data, dict) else response.data
        result_names = [item["name"] for item in payload]
        self.assertIn(self.suite.name, result_names)
        self.assertNotIn(sibling_suite.name, result_names)

    def test_testcase_list_can_filter_by_selected_suite_tree(self):
        admin_user = User.objects.create_superuser(
            username="suitecaseadmin",
            email="suitecaseadmin@example.com",
            password="password",
        )
        child_suite = TestSuite.objects.create(
            project=self.project,
            name="Child Suite",
            parent=self.suite,
            creator=self.user,
        )
        sibling_suite = TestSuite.objects.create(
            project=self.project,
            name="Sibling Suite",
            creator=self.user,
        )
        child_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Child Suite Case",
            creator=self.user,
        )
        sibling_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Sibling Suite Case",
            creator=self.user,
        )

        child_suite.testcases.add(child_case)
        sibling_suite.testcases.add(sibling_case)
        TestCaseAssignment.objects.create(
            testcase=child_case,
            suite=child_suite,
            assignee=admin_user,
            assigned_by=admin_user,
        )

        ProjectMember.objects.create(
            project=self.project,
            user=admin_user,
            role="admin",
        )
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(
            f"/api/projects/{self.project.id}/testcases/",
            {"suite_id": self.suite.id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"] if isinstance(response.data, dict) else response.data
        result_names = [item["name"] for item in payload]
        self.assertIn(child_case.name, result_names)
        self.assertNotIn(sibling_case.name, result_names)
        child_case_payload = next(item for item in payload if item["name"] == child_case.name)
        self.assertIsNotNone(child_case_payload.get("assignment_created_at"))

    def test_suite_can_move_testcases_to_another_suite(self):
        admin_user = User.objects.create_superuser(
            username="moveadmin",
            email="moveadmin@example.com",
            password="password",
        )
        target_suite = TestSuite.objects.create(
            project=self.project,
            name="Target Suite",
            creator=self.user,
        )
        assignee = User.objects.create_user(username="moveassignee", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        self.suite.testcases.add(self.testcase)
        TestCaseAssignment.objects.create(
            testcase=self.testcase,
            suite=self.suite,
            assignee=assignee,
            assigned_by=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-suites/{self.suite.id}/move-testcases/",
            {
                "ids": [self.testcase.id],
                "target_suite_id": target_suite.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(self.suite.testcases.filter(id=self.testcase.id).exists())
        self.assertTrue(target_suite.testcases.filter(id=self.testcase.id).exists())
        assignment = TestCaseAssignment.objects.get(testcase=self.testcase)
        self.assertEqual(assignment.suite_id, target_suite.id)

    def test_suite_can_copy_testcases_to_another_suite(self):
        admin_user = User.objects.create_superuser(
            username="copyadmin",
            email="copyadmin@example.com",
            password="password",
        )
        target_suite = TestSuite.objects.create(
            project=self.project,
            name="Copy Target Suite",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-suites/{self.suite.id}/copy-testcases/",
            {
                "ids": [self.testcase.id],
                "target_suite_id": target_suite.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(self.suite.testcases.filter(id=self.testcase.id).exists())
        self.assertTrue(target_suite.testcases.filter(id=self.testcase.id).exists())

    def test_testcase_list_includes_default_execution_status(self):
        admin_user = User.objects.create_superuser(
            username="executionadmin",
            email="executionadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(f"/api/projects/{self.project.id}/testcases/")

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"] if isinstance(response.data, dict) else response.data
        testcase_payload = next(item for item in payload if item["id"] == self.testcase.id)
        self.assertEqual(testcase_payload["execution_status"], "not_executed")
        self.assertIsNone(testcase_payload["executed_at"])

    def test_batch_update_execution_status(self):
        admin_user = User.objects.create_superuser(
            username="batchexecutionadmin",
            email="batchexecutionadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/testcases/batch-update-execution-status/",
            {
                "ids": [self.testcase.id],
                "execution_status": "passed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.testcase.refresh_from_db()
        self.assertEqual(self.testcase.execution_status, "passed")
        self.assertIsNotNone(self.testcase.executed_at)

    def test_single_update_execution_status_sets_executed_at(self):
        admin_user = User.objects.create_superuser(
            username="singleexecutionadmin",
            email="singleexecutionadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.patch(
            f"/api/projects/{self.project.id}/testcases/{self.testcase.id}/",
            {
                "execution_status": "failed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.testcase.refresh_from_db()
        self.assertEqual(self.testcase.execution_status, "failed")
        self.assertIsNotNone(self.testcase.executed_at)

    def test_not_applicable_does_not_set_executed_at(self):
        admin_user = User.objects.create_superuser(
            username="notapplicableadmin",
            email="notapplicableadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/testcases/batch-update-execution-status/",
            {
                "ids": [self.testcase.id],
                "execution_status": "not_applicable",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.testcase.refresh_from_db()
        self.assertEqual(self.testcase.execution_status, "not_applicable")
        self.assertIsNone(self.testcase.executed_at)

    def test_can_create_suite_bug(self):
        admin_user = User.objects.create_superuser(
            username="bugadmin",
            email="bugadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/",
            {
                "suite": self.suite.id,
                "testcase": self.testcase.id,
                "title": "登录按钮点击后报错",
                "steps": "1. 打开页面\n2. 点击登录",
                "expected_result": "登录成功",
                "actual_result": "出现500错误",
                "bug_type": "codeerror",
                "severity": "2",
                "priority": "1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(TestBug.objects.count(), 1)
        bug = TestBug.objects.first()
        self.assertEqual(bug.title, "登录按钮点击后报错")
        self.assertEqual(bug.status, "active")

    def test_can_resolve_suite_bug(self):
        admin_user = User.objects.create_superuser(
            username="bugresolveadmin",
            email="bugresolveadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="测试Bug",
            opened_by=admin_user,
        )
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/resolve/",
            {
                "resolution": "fixed",
                "solution": "已修复空指针",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.status, "resolved")
        self.assertEqual(bug.resolution, "fixed")
        self.assertIsNotNone(bug.resolved_at)
