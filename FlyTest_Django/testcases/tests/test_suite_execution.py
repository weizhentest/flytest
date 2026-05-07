from io import StringIO
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from requirements.models import RequirementDocument, RequirementModule
from testcases.ai_test_report_generator import generate_iteration_test_report
from testcases.models import TestBug, TestBugActivity, TestCase as TestCaseModel
from testcases.models import TestCaseAssignment, TestCaseModule, TestReportSnapshot, TestSuite
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

    def test_ai_report_returns_rule_based_report_for_selected_suite_tree(self):
        admin_user = User.objects.create_superuser(
            username="reportadmin",
            email="reportadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        child_suite = TestSuite.objects.create(
            project=self.project,
            name="Child Suite",
            parent=self.suite,
            creator=self.user,
        )
        child_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Child Report Case",
            creator=self.user,
            review_status="approved",
            execution_status="failed",
            notes="来源需求文档ID: {document_id}\n来源需求模块ID: {module_id}",
        )
        requirement_document = RequirementDocument.objects.create(
            project=self.project,
            title="登录需求",
            document_type="md",
            status="review_completed",
            version="V1.2",
            is_latest=True,
            uploader=admin_user,
            content="登录、退出和会话记忆功能需求",
        )
        requirement_module = RequirementModule.objects.create(
            document=requirement_document,
            title="记住我与登录失败提示",
            content="需要验证错误凭据不会建立登录态，且记住我状态符合预期。",
            order=1,
        )
        child_case.notes = (
            f"来源需求文档ID: {requirement_document.id}\n"
            f"来源需求模块ID: {requirement_module.id}"
        )
        child_case.save(update_fields=["notes"])
        self.suite.testcases.add(self.testcase)
        child_suite.testcases.add(child_case)
        bug = TestBug.objects.create(
            project=self.project,
            suite=child_suite,
            testcase=child_case,
            title="Report Bug",
            status=TestBug.STATUS_PENDING_RETEST,
            opened_by=admin_user,
        )
        bug.related_testcases.add(child_case)
        TestBugActivity.objects.create(
            bug=bug,
            action=TestBugActivity.ACTION_FIX,
            content="修复完成",
            operator=admin_user,
        )
        TestBugActivity.objects.create(
            bug=bug,
            action=TestBugActivity.ACTION_RESOLVE,
            content="提交复测",
            operator=admin_user,
        )
        TestBugActivity.objects.create(
            bug=bug,
            action=TestBugActivity.ACTION_ACTIVATE,
            content="复测失败，重新激活",
            operator=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        self.assertFalse(payload["used_ai"])
        self.assertEqual(payload["generation_source"], "rule")
        self.assertEqual(payload["generation_status"], "completed")
        self.assertGreaterEqual(payload["generation_duration_ms"], 0)
        self.assertEqual(payload["fallback_reason"], "")
        self.assertEqual(payload["selected_suite_count"], 1)
        self.assertEqual(payload["suite_count"], 2)
        self.assertEqual(payload["testcase_count"], 2)
        self.assertEqual(payload["bug_count"], 1)
        self.assertTrue(payload["summary"])
        self.assertTrue(payload["suite_breakdown"])
        self.assertIn("requirement_summary", payload)
        standard = payload["report_standard"]
        self.assertEqual(standard["basic_info"]["report_version"], "V1.2")
        self.assertEqual(standard["test_overview"]["target_version"], "V1.2")
        self.assertIn("本次直接选择 1 个套件", standard["test_overview"]["scope_included"])
        self.assertIn("当前项目全部套件均已纳入本次测试报告", standard["test_overview"]["scope_excluded"])
        self.assertEqual(standard["result_details"]["case_execution"]["pass_rate"], 0)
        self.assertEqual(standard["quality_conclusion"]["rating"], "不合格")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "不建议发布")
        self.assertIn("失败 1 条", standard["quality_conclusion"]["conclusion"])
        self.assertTrue(
            any(item["name"] == "测试用例已完成需求追踪" for item in standard["quality_conclusion"]["criteria"])
        )
        self.assertEqual(standard["defect_summary"]["legacy_defects"][0]["status"], "待复测")
        self.assertIn("bug_workflow_summary", payload)
        self.assertEqual(payload["requirement_summary"]["linked_document_count"], 1)
        self.assertEqual(payload["requirement_summary"]["linked_module_count"], 1)

    def test_ai_report_blocks_release_when_cases_are_unreviewed_and_not_executed(self):
        admin_user = User.objects.create_superuser(
            username="reportblockadmin",
            email="reportblockadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        second_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Pending Case 2",
            creator=self.user,
            review_status="optimization_pending_review",
            execution_status="not_executed",
        )
        self.testcase.review_status = "pending_review"
        self.testcase.execution_status = "not_executed"
        self.testcase.save(update_fields=["review_status", "execution_status"])
        self.suite.testcases.add(self.testcase, second_case)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        standard = payload["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "不合格")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "不建议发布")
        self.assertIn("均未审核通过", standard["quality_conclusion"]["conclusion"])
        self.assertIn("尚未执行", standard["quality_conclusion"]["conclusion"])
        review_criteria = next(
            item for item in standard["quality_conclusion"]["criteria"] if item["name"] == "测试用例均已审核通过"
        )
        self.assertFalse(review_criteria["passed"])
        self.assertEqual(standard["result_details"]["case_execution"]["not_executed"], 2)
        self.assertEqual(payload["requirement_summary"]["traceable_testcase_count"], 0)
        self.assertEqual(payload["bug_workflow_summary"]["retest_failed_total_count"], 0)
        self.assertEqual(payload["bug_workflow_summary"]["reactivated_bug_count"], 0)

    def test_ai_report_marks_release_as_conditional_when_only_residual_risks_remain(self):
        admin_user = User.objects.create_superuser(
            username="reportconditionaladmin",
            email="reportconditionaladmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        requirement_document = RequirementDocument.objects.create(
            project=self.project,
            title="登录需求",
            document_type="md",
            status="review_completed",
            version="V2.0",
            is_latest=True,
            uploader=admin_user,
            content="验证登录与账号安全相关流程。",
        )
        requirement_module = RequirementModule.objects.create(
            document=requirement_document,
            title="登录主流程",
            content="登录成功、登录失败、会话验证。",
            order=1,
        )
        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.notes = (
            f"来源需求文档ID: {requirement_document.id}\n"
            f"来源需求模块ID: {requirement_module.id}"
        )
        self.testcase.save(update_fields=["review_status", "execution_status", "notes"])
        self.suite.testcases.add(self.testcase)

        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Residual Bug",
            status=TestBug.STATUS_PENDING_RETEST,
            severity="3",
            opened_by=admin_user,
        )
        bug.related_testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        standard = response.data["data"]["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "良")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "有条件发布")
        self.assertIn("有条件发布", standard["quality_conclusion"]["conclusion"])

    def test_ai_report_blocks_release_when_all_cases_are_approved_but_not_executed(self):
        admin_user = User.objects.create_superuser(
            username="reportapprovednotexecuted",
            email="reportapprovednotexecuted@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        self.testcase.review_status = "approved"
        self.testcase.execution_status = "not_executed"
        self.testcase.save(update_fields=["review_status", "execution_status"])
        self.suite.testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        standard = response.data["data"]["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "不合格")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "不建议发布")
        self.assertIn("尚未执行", standard["quality_conclusion"]["conclusion"])
        execution_criteria = next(
            item for item in standard["quality_conclusion"]["criteria"] if item["name"] == "测试范围内用例已全部执行"
        )
        self.assertFalse(execution_criteria["passed"])
        self.assertEqual(standard["result_details"]["case_execution"]["total"], 1)
        self.assertEqual(standard["result_details"]["case_execution"]["passed"], 0)
        self.assertEqual(standard["result_details"]["case_execution"]["failed"], 0)
        self.assertEqual(standard["result_details"]["case_execution"]["not_executed"], 1)

    def test_ai_report_marks_release_as_conditional_when_traceability_is_incomplete(self):
        admin_user = User.objects.create_superuser(
            username="reporttraceabilityadmin",
            email="reporttraceabilityadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.save(update_fields=["review_status", "execution_status"])
        self.suite.testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        standard = payload["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "良")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "有条件发布")
        self.assertEqual(payload["requirement_summary"]["unlinked_testcase_count"], 1)
        self.assertTrue(
            any("未完成需求追踪映射" in item for item in standard["risk_and_suggestions"]["residual_risks"])
        )

    def test_ai_report_marks_release_as_conditional_when_retest_failures_still_exist(self):
        admin_user = User.objects.create_superuser(
            username="reportretestadmin",
            email="reportretestadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        requirement_document = RequirementDocument.objects.create(
            project=self.project,
            title="回归需求",
            document_type="md",
            status="review_completed",
            version="V2.1",
            is_latest=True,
            uploader=admin_user,
            content="回归验证和缺陷闭环追踪要求。",
        )
        requirement_module = RequirementModule.objects.create(
            document=requirement_document,
            title="回归主流程",
            content="验证缺陷修复后的再次执行结果。",
            order=1,
        )
        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.notes = (
            f"来源需求文档ID: {requirement_document.id}\n"
            f"来源需求模块ID: {requirement_module.id}"
        )
        self.testcase.save(update_fields=["review_status", "execution_status", "notes"])
        self.suite.testcases.add(self.testcase)

        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Retest Failed Bug",
            status=TestBug.STATUS_CLOSED,
            severity="3",
            opened_by=admin_user,
        )
        bug.related_testcases.add(self.testcase)
        TestBugActivity.objects.create(
            bug=bug,
            action=TestBugActivity.ACTION_ACTIVATE,
            content="复测失败",
            operator=admin_user,
        )
        TestBugActivity.objects.create(
            bug=bug,
            action=TestBugActivity.ACTION_CLOSE,
            content="最终验证通过后关闭",
            operator=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        standard = payload["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "良")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "有条件发布")
        self.assertEqual(payload["bug_workflow_summary"]["retest_failed_total_count"], 1)
        self.assertTrue(
            any("复测失败累计 1 次" in item for item in standard["risk_and_suggestions"]["residual_risks"])
        )
        self.assertIn("复测失败累计 1 次", standard["quality_conclusion"]["conclusion"])

    def test_ai_report_recommends_release_only_when_all_criteria_pass(self):
        admin_user = User.objects.create_superuser(
            username="reportreadyadmin",
            email="reportreadyadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        requirement_document = RequirementDocument.objects.create(
            project=self.project,
            title="支付需求",
            document_type="md",
            status="review_completed",
            version="V3.0",
            is_latest=True,
            uploader=admin_user,
            content="支付闭环功能验证。",
        )
        requirement_module = RequirementModule.objects.create(
            document=requirement_document,
            title="支付核心流程",
            content="支付发起、结果确认、异常回退。",
            order=1,
        )
        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.notes = (
            f"来源需求文档ID: {requirement_document.id}\n"
            f"来源需求模块ID: {requirement_module.id}"
        )
        self.testcase.save(update_fields=["review_status", "execution_status", "notes"])
        self.suite.testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        standard = response.data["data"]["report_standard"]
        self.assertEqual(standard["quality_conclusion"]["rating"], "优")
        self.assertEqual(standard["quality_conclusion"]["release_recommendation"], "建议发布")
        self.assertTrue(all(item["passed"] for item in standard["quality_conclusion"]["criteria"]))
        self.assertIn("支持进入发布", standard["quality_conclusion"]["conclusion"])

    def test_ai_report_payload_contains_complete_standard_sections(self):
        admin_user = User.objects.create_superuser(
            username="reportcontractadmin",
            email="reportcontractadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")

        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.test_type = "functional"
        self.testcase.save(update_fields=["review_status", "execution_status", "test_type"])
        self.suite.testcases.add(self.testcase)

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        standard = payload["report_standard"]

        self.assertIn("requirement_summary", payload)
        self.assertIn("bug_workflow_summary", payload)
        self.assertIsInstance(payload["requirement_summary"]["documents"], list)
        self.assertIsInstance(payload["requirement_summary"]["modules"], list)
        self.assertIsInstance(payload["bug_workflow_summary"]["bugs_with_failed_retest"], list)
        self.assertIsInstance(payload["bug_workflow_summary"]["top_retest_failed_bugs"], list)

        self.assertIsInstance(standard["test_overview"]["objectives"], list)
        self.assertIsInstance(standard["environment"]["test_tools"], list)
        self.assertGreater(len(standard["environment"]["test_tools"]), 0)
        self.assertIsInstance(standard["activity_summary"]["test_types"], list)
        self.assertGreater(len(standard["activity_summary"]["test_types"]), 0)
        self.assertIsInstance(standard["result_details"]["execution_breakdown"], list)
        self.assertIsInstance(standard["defect_summary"]["by_severity"], list)
        self.assertIsInstance(standard["defect_summary"]["by_status"], list)
        self.assertIsInstance(standard["defect_summary"]["by_module"], list)
        self.assertIsInstance(standard["defect_summary"]["legacy_defects"], list)
        self.assertIsInstance(standard["quality_conclusion"]["criteria"], list)
        self.assertIsInstance(standard["risk_and_suggestions"]["process_risks"], list)
        self.assertIsInstance(standard["risk_and_suggestions"]["residual_risks"], list)
        self.assertIsInstance(standard["risk_and_suggestions"]["follow_up_actions"], list)
        self.assertIsInstance(standard["appendices"]["defect_list_summary"]["items"], list)
        self.assertIsInstance(standard["appendices"]["key_testcases"], list)
        self.assertIsInstance(standard["appendices"]["requirement_documents"], list)
        self.assertTrue(standard["appendices"]["test_data_note"])

    def test_ai_report_requires_suite_selection(self):
        admin_user = User.objects.create_superuser(
            username="reportemptyadmin",
            email="reportemptyadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["error"], "请至少选择一个测试套件")

    @patch("testcases.views.generate_iteration_test_report")
    def test_ai_report_context_keeps_suite_scoped_assignment_details(self, mock_generate_iteration_test_report):
        admin_user = User.objects.create_superuser(
            username="reportscopeadmin",
            email="reportscopeadmin@example.com",
            password="password",
        )
        assignee = User.objects.create_user(username="scopeassignee", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")

        sibling_suite = TestSuite.objects.create(
            project=self.project,
            name="Sibling Suite",
            creator=self.user,
        )
        shared_case = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name="Shared Report Case",
            creator=self.user,
            review_status="approved",
            execution_status="passed",
        )
        self.suite.testcases.add(shared_case)
        sibling_suite.testcases.add(shared_case)
        TestCaseAssignment.objects.create(
            testcase=shared_case,
            suite=self.suite,
            assignee=assignee,
            assigned_by=admin_user,
        )

        mock_generate_iteration_test_report.return_value = SimpleNamespace(
            used_ai=False,
            note="",
            model_name=None,
            generation_source="rule",
            generation_status="completed",
            generation_duration_ms=12,
            fallback_reason="",
            summary="summary",
            quality_overview="quality",
            risk_overview="risk",
            findings=[],
            recommendations=[],
            evidence=[],
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id, sibling_suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        report_context = mock_generate_iteration_test_report.call_args.kwargs["report_context"]
        testcase_payload = next(item for item in report_context["testcases"] if item["id"] == shared_case.id)
        self.assertEqual(testcase_payload["assignee"], assignee.username)
        self.assertEqual(len(testcase_payload["assignments"]), 1)
        self.assertEqual(testcase_payload["assignments"][0]["suite_id"], self.suite.id)
        self.assertEqual(testcase_payload["assignments"][0]["assignee"], assignee.username)

    @patch("testcases.views.generate_iteration_test_report")
    def test_ai_report_response_sanitizes_invalid_report_items(self, mock_generate_iteration_test_report):
        admin_user = User.objects.create_superuser(
            username="reportsanitizeadmin",
            email="reportsanitizeadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.testcase.review_status = "approved"
        self.testcase.execution_status = "passed"
        self.testcase.save(update_fields=["review_status", "execution_status"])
        self.suite.testcases.add(self.testcase)

        mock_generate_iteration_test_report.return_value = SimpleNamespace(
            used_ai=True,
            note="ok",
            model_name="proxy-key",
            generation_source="ai",
            generation_status="completed",
            generation_duration_ms=23,
            fallback_reason="",
            summary="  summary text  ",
            quality_overview="  quality text  ",
            risk_overview="  risk text  ",
            findings=[
                {"title": "  有效发现  ", "detail": "  有效说明  ", "severity": "HIGH"},
                {"title": "无详情", "detail": "   ", "severity": "low"},
                "invalid",
            ],
            recommendations=[
                {"title": "  有效建议  ", "detail": "  有效动作  ", "priority": "HIGH"},
                {"title": "", "detail": "缺标题", "priority": "low"},
            ],
            evidence=[
                {"label": "  有效证据  ", "detail": "  证据说明  "},
                {"label": "", "detail": "无标签"},
            ],
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/ai-report/",
            {"suite_ids": [self.suite.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload = response.data["data"]
        self.assertEqual(payload["summary"], "summary text")
        self.assertEqual(payload["quality_overview"], "quality text")
        self.assertEqual(payload["risk_overview"], "risk text")
        self.assertEqual(payload["findings"], [{"title": "有效发现", "detail": "有效说明", "severity": "high"}])
        self.assertEqual(payload["recommendations"], [{"title": "有效建议", "detail": "有效动作", "priority": "high"}])
        self.assertEqual(payload["evidence"], [{"label": "有效证据", "detail": "证据说明"}])

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm")
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_uses_ai_when_llm_config_exists(self, mock_get_config, mock_invoke_plain_text_llm):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")
        mock_invoke_plain_text_llm.return_value = """
        {
          "summary": "AI总结",
          "quality_overview": "AI质量概览",
          "risk_overview": "AI风险概览",
          "findings": [{"title": "发现1", "detail": "说明1", "severity": "high"}],
          "recommendations": [{"title": "建议1", "detail": "动作1", "priority": "medium"}],
          "evidence": [{"label": "证据1", "detail": "证据详情"}]
        }
        """

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 1,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"passed": 1},
                "review_status_distribution": {"approved": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(result.model_name, "proxy-key")
        self.assertEqual(result.generation_source, "ai")
        self.assertEqual(result.generation_status, "completed")
        self.assertGreaterEqual(result.generation_duration_ms, 0)
        self.assertEqual(result.fallback_reason, "")
        self.assertEqual(result.summary, "AI总结")
        self.assertEqual(result.findings[0]["title"], "发现1")
        mock_invoke_plain_text_llm.assert_called_once()

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm")
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_falls_back_to_rule_content_when_ai_payload_is_incomplete(
        self, mock_get_config, mock_invoke_plain_text_llm
    ):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")
        mock_invoke_plain_text_llm.return_value = """
        {
          "summary": "",
          "quality_overview": "",
          "risk_overview": "",
          "findings": [{"title": "", "detail": "缺少标题", "severity": "unknown"}],
          "recommendations": [{"title": "   ", "detail": "", "priority": "bad"}],
          "evidence": ["invalid"]
        }
        """

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 0,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"not_executed": 1},
                "review_status_distribution": {"pending_review": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(result.generation_source, "ai")
        self.assertTrue(result.summary)
        self.assertTrue(result.quality_overview)
        self.assertTrue(result.risk_overview)
        self.assertGreater(len(result.findings), 0)
        self.assertGreater(len(result.recommendations), 0)
        self.assertGreater(len(result.evidence), 0)
        self.assertNotEqual(result.summary, "")
        self.assertNotEqual(result.findings, [])

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm")
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_accepts_ai_response_wrapped_in_code_block(
        self, mock_get_config, mock_invoke_plain_text_llm
    ):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")
        mock_invoke_plain_text_llm.return_value = """
分析结果如下：
```json
{
  "summary": "AI 总结",
  "quality_overview": "AI 质量概览",
  "risk_overview": "AI 风险概览",
  "findings": [{"title": "发现1", "detail": "说明1", "severity": "high"}],
  "recommendations": [{"title": "建议1", "detail": "动作1", "priority": "medium"}],
  "evidence": [{"label": "证据1", "detail": "证据详情"}]
}
```
"""

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 1,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"passed": 1},
                "review_status_distribution": {"approved": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(result.generation_source, "ai")
        self.assertEqual(result.summary, "AI 总结")
        self.assertEqual(result.evidence[0]["label"], "证据1")

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm")
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_repairs_non_strict_json_from_ai(self, mock_get_config, mock_invoke_plain_text_llm):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")
        mock_invoke_plain_text_llm.return_value = """
{
  summary: 'AI 总结',
  quality_overview: 'AI 质量概览',
  risk_overview: 'AI 风险概览',
  findings: [{title: '发现1', detail: '说明1', severity: high}],
  recommendations: [{title: '建议1', detail: '动作1', priority: medium}],
  evidence: [{label: '证据1', detail: '证据详情'}],
}
"""

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 1,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"passed": 1},
                "review_status_distribution": {"approved": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(result.generation_source, "ai")
        self.assertEqual(result.summary, "AI 总结")
        self.assertEqual(result.findings[0]["severity"], "high")
        self.assertEqual(result.recommendations[0]["priority"], "medium")

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm")
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_accepts_list_wrapped_ai_payload(self, mock_get_config, mock_invoke_plain_text_llm):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")
        mock_invoke_plain_text_llm.return_value = """
[
  {
    "summary": "AI 总结",
    "quality_overview": "AI 质量概览",
    "risk_overview": "AI 风险概览",
    "findings": [{"title": "发现1", "detail": "说明1", "severity": "high"}],
    "recommendations": [{"title": "建议1", "detail": "动作1", "priority": "medium"}],
    "evidence": [{"label": "证据1", "detail": "证据详情"}]
  }
]
"""

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 1,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"passed": 1},
                "review_status_distribution": {"approved": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertTrue(result.used_ai)
        self.assertEqual(result.generation_source, "ai")
        self.assertEqual(result.summary, "AI 总结")
        self.assertEqual(result.evidence[0]["label"], "证据1")

    @patch("testcases.ai_test_report_generator.invoke_plain_text_llm", side_effect=RuntimeError("Service error"))
    @patch("testcases.ai_test_report_generator.get_user_active_llm_config")
    def test_iteration_report_falls_back_when_ai_call_fails(self, mock_get_config, _mock_invoke_plain_text_llm):
        mock_get_config.return_value = SimpleNamespace(name="proxy-key")

        result = generate_iteration_test_report(
            user=self.user,
            report_context={
                "project": {"id": self.project.id, "name": self.project.name},
                "selected_suite_ids": [self.suite.id],
                "selected_suite_names": [self.suite.name],
                "generated_at": "2026-05-02T12:00:00+08:00",
                "totals": {
                    "suite_count": 1,
                    "selected_suite_count": 1,
                    "testcase_count": 1,
                    "approved_testcase_count": 0,
                    "bug_count": 0,
                },
                "execution_status_distribution": {"not_executed": 1},
                "review_status_distribution": {"pending_review": 1},
                "bug_status_distribution": {},
                "requirement_summary": {},
                "bug_workflow_summary": {},
                "suite_breakdown": [],
            },
        )

        self.assertFalse(result.used_ai)
        self.assertEqual(result.model_name, "proxy-key")
        self.assertEqual(result.generation_source, "fallback")
        self.assertEqual(result.generation_status, "fallback")
        self.assertGreaterEqual(result.generation_duration_ms, 0)
        self.assertEqual(result.fallback_reason, "Service error")
        self.assertIn("AI 分析接口调用失败", result.note)
        self.assertIn("45 秒", result.note)

    def test_report_snapshot_can_be_created_and_listed(self):
        admin_user = User.objects.create_superuser(
            username="snapshotadmin",
            email="snapshotadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        payload = {
            "title": "测试报告 2026-05-01 13:00:00",
            "suite_ids": [self.suite.id],
            "report_data": {
                "generated_at": "2026-05-01T13:00:00+08:00",
                "summary": "报告摘要",
                "suite_count": 1,
                "selected_suite_count": 1,
                "testcase_count": 1,
                "bug_count": 0,
                "used_ai": False,
            },
        }
        create_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/",
            payload,
            format="json",
        )

        self.assertEqual(create_response.status_code, 201, create_response.data)
        self.assertTrue(TestReportSnapshot.objects.filter(project=self.project, title=payload["title"]).exists())

        list_response = self.api_client.get(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/"
        )
        self.assertEqual(list_response.status_code, 200, list_response.data)
        self.assertTrue(list_response.data["success"])
        self.assertEqual(len(list_response.data["data"]), 1)
        self.assertEqual(list_response.data["data"][0]["title"], payload["title"])

    def test_report_snapshot_rejects_invalid_suite_ids_on_create(self):
        admin_user = User.objects.create_superuser(
            username="snapshotinvalidcreate",
            email="snapshotinvalidcreate@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        create_response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/",
            {
                "title": "Invalid Snapshot",
                "suite_ids": [self.suite.id, 999999],
                "report_data": {"summary": "invalid"},
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 400, create_response.data)
        self.assertIn("不存在或不属于当前项目", create_response.data["error"])

    def test_report_snapshot_can_be_renamed_and_pinned(self):
        admin_user = User.objects.create_superuser(
            username="snapshoteditor",
            email="snapshoteditor@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        first_snapshot = TestReportSnapshot.objects.create(
            project=self.project,
            title="First Snapshot",
            suite_ids=[self.suite.id],
            report_data={"summary": "first"},
            creator=admin_user,
        )
        second_snapshot = TestReportSnapshot.objects.create(
            project=self.project,
            title="Second Snapshot",
            suite_ids=[self.suite.id],
            report_data={"summary": "second"},
            creator=admin_user,
        )

        update_response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/{first_snapshot.id}/update/",
            {"title": "Pinned Snapshot", "is_pinned": True},
            format="json",
        )

        self.assertEqual(update_response.status_code, 200, update_response.data)
        self.assertTrue(update_response.data["success"])
        self.assertEqual(update_response.data["data"]["title"], "Pinned Snapshot")
        self.assertTrue(update_response.data["data"]["is_pinned"])

        first_snapshot.refresh_from_db()
        second_snapshot.refresh_from_db()
        self.assertEqual(first_snapshot.title, "Pinned Snapshot")
        self.assertTrue(first_snapshot.is_pinned)
        self.assertFalse(second_snapshot.is_pinned)

        list_response = self.api_client.get(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/"
        )
        self.assertEqual(list_response.status_code, 200, list_response.data)
        self.assertEqual(len(list_response.data["data"]), 2)
        self.assertEqual(list_response.data["data"][0]["id"], first_snapshot.id)
        self.assertTrue(list_response.data["data"][0]["is_pinned"])
        self.assertEqual(list_response.data["data"][1]["id"], second_snapshot.id)

    def test_report_snapshot_rejects_invalid_suite_ids_on_update(self):
        admin_user = User.objects.create_superuser(
            username="snapshotinvalidupdate",
            email="snapshotinvalidupdate@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        snapshot = TestReportSnapshot.objects.create(
            project=self.project,
            title="Snapshot To Update",
            suite_ids=[self.suite.id],
            report_data={"summary": "before"},
            creator=admin_user,
        )

        update_response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/{snapshot.id}/update/",
            {"suite_ids": [self.suite.id, 999999]},
            format="json",
        )

        self.assertEqual(update_response.status_code, 400, update_response.data)
        self.assertIn("不存在或不属于当前项目", update_response.data["error"])

    def test_report_snapshot_can_be_overwritten_with_new_report_content(self):
        admin_user = User.objects.create_superuser(
            username="snapshotwriter",
            email="snapshotwriter@example.com",
            password="password",
        )
        second_suite = TestSuite.objects.create(
            project=self.project,
            name="Second Snapshot Suite",
            creator=self.user,
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.api_client.force_authenticate(user=admin_user)

        snapshot = TestReportSnapshot.objects.create(
            project=self.project,
            title="Iteration Report",
            suite_ids=[self.suite.id],
            report_data={
                "generated_at": "2026-05-01T13:00:00+08:00",
                "summary": "old summary",
                "suite_count": 1,
            },
            creator=admin_user,
        )

        update_response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-executions/report-snapshots/{snapshot.id}/update/",
            {
                "suite_ids": [self.suite.id, second_suite.id],
                "report_data": {
                    "generated_at": "2026-05-01T14:00:00+08:00",
                    "summary": "new summary",
                    "suite_count": 2,
                    "selected_suite_count": 2,
                    "testcase_count": 3,
                    "bug_count": 1,
                    "used_ai": False,
                },
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 200, update_response.data)
        self.assertTrue(update_response.data["success"])
        self.assertEqual(update_response.data["data"]["suite_ids"], [self.suite.id, second_suite.id])
        self.assertEqual(update_response.data["data"]["report_data"]["summary"], "new summary")

        snapshot.refresh_from_db()
        self.assertEqual(snapshot.suite_ids, [self.suite.id, second_suite.id])
        self.assertEqual(snapshot.report_data["summary"], "new summary")
        self.assertEqual(snapshot.report_data["suite_count"], 2)

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

    def test_bug_list_can_filter_by_related_testcase(self):
        admin_user = User.objects.create_superuser(
            username="bugfilteradmin",
            email="bugfilteradmin@example.com",
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
        matched_bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Bug linked to multiple cases",
            opened_by=admin_user,
        )
        matched_bug.related_testcases.set([self.testcase, second_testcase])
        unmatched_bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=third_testcase,
            title="Bug linked elsewhere",
            opened_by=admin_user,
        )
        unmatched_bug.related_testcases.set([third_testcase])
        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(
            f"/api/projects/{self.project.id}/test-bugs/",
            {"testcase_id": second_testcase.id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload_items = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        returned_ids = [item["id"] for item in payload_items]
        self.assertEqual(returned_ids, [matched_bug.id])

    def test_bug_list_can_filter_by_primary_assignee(self):
        admin_user = User.objects.create_superuser(
            username="bugassigneefilteradmin",
            email="bugassigneefilteradmin@example.com",
            password="password",
        )
        primary_assignee = User.objects.create_user(
            username="primaryassignee",
            email="primaryassignee@example.com",
            password="password",
        )
        other_assignee = User.objects.create_user(
            username="otherassignee",
            email="otherassignee@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=primary_assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=other_assignee, role="member")
        self.suite.testcases.add(self.testcase)

        matched_bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Bug assigned via primary field only",
            opened_by=admin_user,
            assigned_to=primary_assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        matched_bug.assigned_users.clear()

        unmatched_bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Bug assigned to someone else",
            opened_by=admin_user,
            assigned_to=other_assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        unmatched_bug.assigned_users.set([other_assignee])

        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(
            f"/api/projects/{self.project.id}/test-bugs/",
            {"assigned_to": primary_assignee.id},
        )

        self.assertEqual(response.status_code, 200, response.data)
        payload_items = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        returned_ids = [item["id"] for item in payload_items]
        self.assertEqual(returned_ids, [matched_bug.id])

    def test_bug_detail_includes_primary_assignee_in_assignee_fields(self):
        admin_user = User.objects.create_superuser(
            username="bugdetailassigneeadmin",
            email="bugdetailassigneeadmin@example.com",
            password="password",
        )
        primary_assignee = User.objects.create_user(
            username="detailprimaryassignee",
            email="detailprimaryassignee@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=primary_assignee, role="member")
        self.suite.testcases.add(self.testcase)

        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Bug detail keeps primary assignee",
            opened_by=admin_user,
            assigned_to=primary_assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.clear()

        self.api_client.force_authenticate(user=admin_user)

        response = self.api_client.get(f"/api/projects/{self.project.id}/test-bugs/{bug.id}/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["assigned_to"], primary_assignee.id)
        self.assertEqual(response.data["assigned_to_ids"], [primary_assignee.id])
        self.assertEqual(response.data["assigned_to_names"], [primary_assignee.username])
        self.assertEqual(
            [item["id"] for item in response.data["assigned_to_details"]],
            [primary_assignee.id],
        )

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

    def test_bug_detail_patch_assigns_users_and_updates_status_and_timestamp(self):
        admin_user = User.objects.create_superuser(
            username="bugdetailpatchadmin",
            email="bugdetailpatchadmin@example.com",
            password="password",
        )
        first_assignee = User.objects.create_user(username="bugdetailpatch1", password="password")
        second_assignee = User.objects.create_user(username="bugdetailpatch2", password="password")
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        ProjectMember.objects.create(project=self.project, user=first_assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=second_assignee, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="detail patch assignment",
            opened_by=admin_user,
            status=TestBug.STATUS_UNASSIGNED,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/",
            {"assigned_to_ids": [first_assignee.id, second_assignee.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.assigned_to_id, first_assignee.id)
        self.assertEqual(
            list(bug.assigned_users.order_by("id").values_list("id", flat=True)),
            [first_assignee.id, second_assignee.id],
        )
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_ASSIGNED)
        self.assertEqual(response.data["status"], TestBug.STATUS_ASSIGNED)
        self.assertEqual(response.data["status_display"], "未确认")
        self.assertIsNotNone(bug.assigned_at)

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

    def test_unrelated_member_cannot_patch_bug_detail(self):
        creator = User.objects.create_user(username="bugpatchowner", password="password")
        assignee = User.objects.create_user(username="bugpatchworker", password="password")
        outsider = User.objects.create_user(username="bugpatchoutsider", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=outsider, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Patch Permission Bug",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
            severity="3",
        )
        bug.assigned_users.set([assignee])

        self.api_client.force_authenticate(user=outsider)
        response = self.api_client.patch(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/",
            {"severity": "1"},
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.severity, "3")

    def test_unrelated_member_cannot_delete_bug(self):
        creator = User.objects.create_user(username="bugdeleteowner", password="password")
        assignee = User.objects.create_user(username="bugdeleteworker", password="password")
        outsider = User.objects.create_user(username="bugdeleteoutsider", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=outsider, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Delete Permission Bug",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.set([assignee])

        self.api_client.force_authenticate(user=outsider)
        response = self.api_client.delete(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/"
        )

        self.assertEqual(response.status_code, 403, response.data)
        self.assertTrue(TestBug.objects.filter(id=bug.id).exists())

    def test_unrelated_member_cannot_manage_bug_attachments(self):
        creator = User.objects.create_user(username="bugattachmentowner", password="password")
        assignee = User.objects.create_user(username="bugattachmentworker", password="password")
        outsider = User.objects.create_user(username="bugattachmentoutsider", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=outsider, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Attachment Permission Bug",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.set([assignee])

        self.api_client.force_authenticate(user=outsider)
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload_response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/upload-attachments/",
                    {
                        "section": "steps",
                        "files": [
                            SimpleUploadedFile(
                                "forbidden.txt",
                                b"forbidden attachment",
                                content_type="text/plain",
                            )
                        ],
                    },
                    format="multipart",
                )

        self.assertEqual(upload_response.status_code, 403, upload_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.attachments.count(), 0)

    def test_unrelated_member_cannot_delete_bug_attachment(self):
        creator = User.objects.create_user(username="bugdeleteattachmentowner", password="password")
        assignee = User.objects.create_user(username="bugdeleteattachmentworker", password="password")
        outsider = User.objects.create_user(username="bugdeleteattachmentoutsider", password="password")
        ProjectMember.objects.create(project=self.project, user=creator, role="member")
        ProjectMember.objects.create(project=self.project, user=assignee, role="member")
        ProjectMember.objects.create(project=self.project, user=outsider, role="member")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="Attachment Delete Permission Bug",
            opened_by=creator,
            assigned_to=assignee,
            status=TestBug.STATUS_ASSIGNED,
        )
        bug.assigned_users.set([assignee])

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.api_client.force_authenticate(user=creator)
                upload_response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/upload-attachments/",
                    {
                        "section": "steps",
                        "files": [
                            SimpleUploadedFile(
                                "owner.txt",
                                b"owner attachment",
                                content_type="text/plain",
                            )
                        ],
                    },
                    format="multipart",
                )
                self.assertEqual(upload_response.status_code, 201, upload_response.data)
                attachment_id = upload_response.data["data"][0]["id"]

                self.api_client.force_authenticate(user=outsider)
                delete_response = self.api_client.delete(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/attachments/{attachment_id}/"
                )

        self.assertEqual(delete_response.status_code, 403, delete_response.data)
        bug.refresh_from_db()
        self.assertEqual(bug.attachments.count(), 1)

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

    def test_bug_attachment_upload_rejects_invalid_section(self):
        admin_user = User.objects.create_superuser(
            username="buginvalidsectionadmin",
            email="buginvalidsectionadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="非法附件区域BUG",
            opened_by=admin_user,
        )

        self.api_client.force_authenticate(user=admin_user)
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.api_client.post(
                    f"/api/projects/{self.project.id}/test-bugs/{bug.id}/upload-attachments/",
                    {
                        "section": "invalid_section",
                        "files": [
                            SimpleUploadedFile(
                                "bad.txt",
                                b"bad attachment",
                                content_type="text/plain",
                            )
                        ],
                    },
                    format="multipart",
                )

                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("请选择有效的附件区域", str(response.data))
                bug.refresh_from_db()
                self.assertEqual(bug.attachments.count(), 0)

    def test_change_status_rejects_manual_expired_status(self):
        admin_user = User.objects.create_superuser(
            username="bugexpiredadmin",
            email="bugexpiredadmin@example.com",
            password="password",
        )
        ProjectMember.objects.create(project=self.project, user=admin_user, role="admin")
        self.suite.testcases.add(self.testcase)
        bug = TestBug.objects.create(
            project=self.project,
            suite=self.suite,
            testcase=self.testcase,
            title="禁止手动过期BUG",
            opened_by=admin_user,
            status=TestBug.STATUS_UNASSIGNED,
        )

        self.api_client.force_authenticate(user=admin_user)
        response = self.api_client.post(
            f"/api/projects/{self.project.id}/test-bugs/{bug.id}/change-status/",
            {"status": TestBug.STATUS_EXPIRED},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("已过期状态由系统自动判断", str(response.data))
        bug.refresh_from_db()
        self.assertEqual(bug.get_effective_status(), TestBug.STATUS_UNASSIGNED)

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
