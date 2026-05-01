from io import StringIO
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
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
        self.assertEqual(bug.status, TestBug.STATUS_UNASSIGNED)
        self.assertEqual(response.data["status"], TestBug.STATUS_UNASSIGNED)
        self.assertEqual(response.data["status_display"], "未指派")

    def test_can_create_suite_bug_with_multiple_related_testcases(self):
        admin_user = User.objects.create_superuser(
            username="bugmultiadmin",
            email="bugmultiadmin@example.com",
            password="password",
        )
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 2",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase, second_testcase)
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/",
            {
                "suite": self.suite.id,
                "testcase_ids": [self.testcase.id, second_testcase.id],
                "title": "登录流程多用例关联",
                "steps": "1. 打开页面\n2. 输入错误密码",
                "expected_result": "提示密码错误",
                "actual_result": "页面白屏",
                "bug_type": "codeerror",
                "severity": "2",
                "priority": "1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        bug = TestBug.objects.get()
        self.assertEqual(bug.testcase_id, self.testcase.id)
        self.assertEqual(
            list(bug.related_testcases.order_by("id").values_list("id", flat=True)),
            [self.testcase.id, second_testcase.id],
        )
        self.assertEqual(response.data["testcase_ids"], [self.testcase.id, second_testcase.id])
        self.assertEqual(response.data["testcase_names"], ["Test Case 1", "Test Case 2"])

    def test_can_update_bug_related_testcases(self):
        admin_user = User.objects.create_superuser(
            username="bugupdateadmin",
            email="bugupdateadmin@example.com",
            password="password",
        )
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 2",
            creator=self.user,
        )
        third_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 3",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase, second_testcase, third_testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="待更新的BUG",
            opened_by=admin_user,
        )
        bug.related_testcases.set([self.testcase, second_testcase])
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/",
            {
                "testcase_ids": [third_testcase.id, second_testcase.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.testcase_id, third_testcase.id)
        self.assertEqual(
            list(bug.related_testcases.order_by("id").values_list("id", flat=True)),
            [second_testcase.id, third_testcase.id],
        )
        self.assertEqual(response.data["testcase_ids"], [third_testcase.id, second_testcase.id])
        self.assertEqual(response.data["testcase_names"], ["Test Case 3", "Test Case 2"])

    def test_create_bug_rejects_related_testcases_outside_suite(self):
        admin_user = User.objects.create_superuser(
            username="buginvalidadmin",
            email="buginvalidadmin@example.com",
            password="password",
        )
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 2",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/",
            {
                "suite": self.suite.id,
                "testcase_ids": [self.testcase.id, second_testcase.id],
                "title": "非法关联用例",
                "bug_type": "codeerror",
                "severity": "2",
                "priority": "1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("testcase_ids", response.data)
        self.assertEqual(TestBug.objects.count(), 0)

    def test_update_bug_can_clear_related_testcases(self):
        admin_user = User.objects.create_superuser(
            username="bugclearadmin",
            email="bugclearadmin@example.com",
            password="password",
        )
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Test Case 2",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase, second_testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="清空关联用例",
            opened_by=admin_user,
        )
        bug.related_testcases.set([self.testcase, second_testcase])
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/",
            {
                "testcase_ids": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertIsNone(bug.testcase_id)
        self.assertEqual(list(bug.related_testcases.values_list("id", flat=True)), [])
        self.assertEqual(response.data["testcase_ids"], [])
        self.assertEqual(response.data["testcase_names"], [])

    def test_can_resolve_suite_bug(self):
        admin_user = User.objects.create_superuser(
            username="bugresolveadmin",
            email="bugresolveadmin@example.com",
            password="password",
        )
        assignee = User.objects.create_user(username="bugresolver", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="测试Bug",
            opened_by=admin_user,
            assigned_to=assignee,
            status=TestBug.STATUS_CONFIRMED,
        )
        bug.assigned_users.set([assignee])
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
        self.assertEqual(bug.status, TestBug.STATUS_PENDING_RETEST)
        self.assertEqual(bug.resolution, "fixed")
        self.assertIsNotNone(bug.resolved_at)
        self.assertEqual(response.data["status"], TestBug.STATUS_PENDING_RETEST)
        self.assertEqual(response.data["status_display"], "待复测")

    def test_bug_workflow_actions_update_status_and_timestamps(self):
        admin_user = User.objects.create_superuser(
            username="bugworkflowadmin",
            email="bugworkflowadmin@example.com",
            password="password",
        )
        assignee = User.objects.create_user(username="bugworkflowmember", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="状态流转测试",
            opened_by=admin_user,
        )
        self.api_client.force_authenticate(user=admin_user)

        assign_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/assign/",
            {"assigned_to_ids": [assignee.id]},
            format="json",
        )
        self.assertEqual(assign_response.status_code, 200, assign_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)
        self.assertEqual(bug.assigned_to_id, assignee.id)
        self.assertIsNotNone(bug.assigned_at)

        confirm_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/confirm/",
            {},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_CONFIRMED)

        fix_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/fix/",
            {"resolution": "fixed", "solution": "已完成修复"},
            format="json",
        )
        self.assertEqual(fix_response.status_code, 200, fix_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_FIXED)
        self.assertEqual(bug.resolution, "fixed")
        self.assertIsNotNone(bug.resolved_at)

        close_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/close/",
            {"solution": "验证通过后关闭"},
            format="json",
        )
        self.assertEqual(close_response.status_code, 200, close_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_CLOSED)
        self.assertIsNotNone(bug.closed_at)

        activate_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/activate/",
            {},
            format="json",
        )
        self.assertEqual(activate_response.status_code, 200, activate_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_CONFIRMED)
        self.assertEqual(bug.activated_count, 1)
        self.assertIsNone(bug.closed_at)
        self.assertIsNone(bug.resolved_at)

    def test_multiple_assignees_can_be_saved_and_secondary_assignee_can_confirm(self):
        admin_user = User.objects.create_superuser(
            username="bugmultiassignadmin",
            email="bugmultiassignadmin@example.com",
            password="password",
        )
        first_assignee = User.objects.create_user(username="bugassignee1", password="password")
        second_assignee = User.objects.create_user(username="bugassignee2", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=first_assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=second_assignee, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="多指派流转",
            opened_by=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        assign_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/assign/",
            {"assigned_to_ids": [first_assignee.id, second_assignee.id]},
            format="json",
        )

        self.assertEqual(assign_response.status_code, 200, assign_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.assigned_to_id, first_assignee.id)
        self.assertEqual(
            list(bug.assigned_users.order_by("id").values_list("id", flat=True)),
            [first_assignee.id, second_assignee.id],
        )
        self.assertEqual(assign_response.data["assigned_to_ids"], [first_assignee.id, second_assignee.id])
        self.assertEqual(assign_response.data["status"], TestBug.STATUS_ASSIGNED)

        self.api_client.force_authenticate(user=second_assignee)
        confirm_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/confirm/",
            {},
            format="json",
        )

        self.assertEqual(confirm_response.status_code, 200, confirm_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_CONFIRMED)

    def test_bug_creator_can_change_status_without_admin_role(self):
        creator = User.objects.create_user(username="bugcreator", password="password")
        assignee = User.objects.create_user(username="bugcreatorassignee", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="创建人可流转",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.set([assignee])

        self.api_client.force_authenticate(user=creator)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/close/",
            {"solution": "创建人验证后关闭"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_CLOSED)
        self.assertIsNotNone(bug.closed_at)

    def test_unrelated_member_cannot_change_bug_status(self):
        creator = User.objects.create_user(username="bugowner", password="password")
        assignee = User.objects.create_user(username="bugworker", password="password")
        outsider = User.objects.create_user(username="bugoutsider", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=outsider, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="无权限流转",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.set([assignee])

        self.api_client.force_authenticate(user=outsider)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/confirm/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)

    def test_batch_assign_bugs_supports_multiple_assignees(self):
        admin_user = User.objects.create_superuser(
            username="bugbatchassignadmin",
            email="bugbatchassignadmin@example.com",
            password="password",
        )
        first_assignee = User.objects.create_user(username="bugbatchuser1", password="password")
        second_assignee = User.objects.create_user(username="bugbatchuser2", password="password")
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Batch Test Case 2",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=first_assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=second_assignee, role="member")
        self.suite.testcases.add(self.testcase, second_testcase)
        bug_one = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="批量指派BUG1",
            opened_by=admin_user,
        )
        bug_two = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=second_testcase,
            title="批量指派BUG2",
            opened_by=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/batch-assign/",
            {
                "ids": [bug_one.id, bug_two.id],
                "assigned_to_ids": [first_assignee.id, second_assignee.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug_one.refresh_from_db()
        bug_two.refresh_from_db()
        self.assertEqual(set(response.data["updated_ids"]), {bug_one.id, bug_two.id})
        for bug in (bug_one, bug_two):
            self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)
            self.assertEqual(bug.assigned_to_id, first_assignee.id)
            self.assertEqual(
                list(bug.assigned_users.order_by("id").values_list("id", flat=True)),
                [first_assignee.id, second_assignee.id],
            )
            self.assertIsNotNone(bug.assigned_at)

    def test_batch_update_resolution_syncs_bug_status(self):
        admin_user = User.objects.create_superuser(
            username="bugbatchresolutionadmin",
            email="bugbatchresolutionadmin@example.com",
            password="password",
        )
        second_testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Resolution Test Case 2",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase, second_testcase)
        bug_one = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="批量解决方案BUG1",
            opened_by=admin_user,
            status=TestBug.STATUS_CONFIRMED,
        )
        bug_two = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=second_testcase,
            title="批量解决方案BUG2",
            opened_by=admin_user,
            status=TestBug.STATUS_ASSIGNED,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/batch-update-resolution/",
            {
                "ids": [bug_one.id, bug_two.id],
                "resolution": "fixed",
                "solution": "批量完成修复",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug_one.refresh_from_db()
        bug_two.refresh_from_db()
        self.assertEqual(set(response.data["updated_ids"]), {bug_one.id, bug_two.id})
        for bug in (bug_one, bug_two):
            self.assertEqual(bug.resolution, "fixed")
            self.assertEqual(bug.solution, "批量完成修复")
            self.assertEqual(bug.get_effective_status(), TestBug.STATUS_FIXED)
            self.assertIsNotNone(bug.resolved_at)

    def test_bug_attachment_upload_and_delete_records_activity(self):
        admin_user = User.objects.create_superuser(
            username="bugattachmentadmin",
            email="bugattachmentadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="附件管理BUG",
            opened_by=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload_response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/upload-attachments/",
                    {
                        "section": "steps",
                        "files": [
                            SimpleUploadedFile(
                                "reproduce.png",
                                b"fake-image-content",
                                content_type="image/png",
                            )
                        ],
                    },
                    format="multipart",
                )

                self.assertEqual(upload_response.status_code, 201, upload_response.data)
                attachments = upload_response.data["data"]
                self.assertEqual(len(attachments), 1)
                attachment_id = attachments[0]["id"]
                self.assertEqual(attachments[0]["original_name"], "reproduce.png")
                self.assertEqual(attachments[0]["file_type"], "image")

                bug.refresh_from_db()
                self.assertEqual(bug.attachments.count(), 1)
                self.assertEqual(bug.activities.first().action, "upload_attachment")

                delete_response = self.api_client.delete(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/attachments/{attachment_id}/"
                )
                self.assertEqual(delete_response.status_code, 200, delete_response.data)

                bug.refresh_from_db()
                self.assertEqual(bug.attachments.count(), 0)
                latest_activity = bug.activities.first()
                self.assertEqual(latest_activity.action, "delete_attachment")
                self.assertIn("reproduce.png", latest_activity.content)

    def test_bug_detail_returns_activity_logs_after_attachment_upload(self):
        admin_user = User.objects.create_superuser(
            username="bugactivityadmin",
            email="bugactivityadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        self.api_client.force_authenticate(user=admin_user)
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                create_response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/",
                    {
                        "suite": self.suite.id,
                        "testcase": self.testcase.id,
                        "title": "活动日志BUG",
                        "bug_type": "codeerror",
                        "severity": "3",
                        "priority": "3",
                    },
                    format="json",
                )
                self.assertEqual(create_response.status_code, 201, create_response.data)
                bug_id = create_response.data["id"]

                upload_response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/{bug_id}/upload-attachments/",
                    {
                        "section": "actual_result",
                        "files": [
                            SimpleUploadedFile(
                                "result.txt",
                                b"actual result attachment",
                                content_type="text/plain",
                            )
                        ],
                    },
                    format="multipart",
                )
                self.assertEqual(upload_response.status_code, 201, upload_response.data)

                detail_response = self.api_client.get(
                    f"/api/projects/{self.project.id}/test-bugs/{bug_id}/"
                )

                self.assertEqual(detail_response.status_code, 200, detail_response.data)
                self.assertEqual(len(detail_response.data["attachments"]), 1)
                self.assertGreaterEqual(len(detail_response.data["activity_logs"]), 2)
                self.assertEqual(detail_response.data["activity_logs"][0]["action"], "upload_attachment")
                self.assertEqual(detail_response.data["activity_logs"][1]["action"], "create")

    def test_repair_test_bug_workflow_command_normalizes_legacy_data(self):
        admin_user = User.objects.create_superuser(
            username="bugcommandadmin",
            email="bugcommandadmin@example.com",
            password="password",
        )
        member = User.objects.create_user(username="bugcommandmember", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=member, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="历史Bug",
            opened_by=admin_user,
            assigned_to=member,
            status="active",
        )
        bug.assigned_users.clear()

        dry_run_output = StringIO()
        call_command("repair_test_bug_workflow", "--dry-run", stdout=dry_run_output)
        bug.refresh_from_db()
        self.assertEqual(bug.status, TestBug.STATUS_ASSIGNED)
        self.assertIn("修复 1 条", dry_run_output.getvalue())

        execute_output = StringIO()
        call_command("repair_test_bug_workflow", stdout=execute_output)
        bug.refresh_from_db()
        self.assertEqual(bug.status, TestBug.STATUS_ASSIGNED)
        self.assertEqual(list(bug.assigned_users.values_list("id", flat=True)), [member.id])
        self.assertIsNotNone(bug.assigned_at)
        self.assertIn("修复 1 条", execute_output.getvalue())
