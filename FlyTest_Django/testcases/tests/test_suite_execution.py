from django.test import TestCase
from django.contrib.auth.models import User
from projects.models import Project
from testcases.models import TestSuite, TestCase as TestCaseModel, TestExecution, TestCaseModule
from testcases.serializers import TestSuiteSerializer, TestExecutionCreateSerializer
from rest_framework.exceptions import ValidationError

class TestSuiteExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.project = Project.objects.create(name='Test Project', description='Test Description', creator=self.user)
        self.module = TestCaseModule.objects.create(project=self.project, name='Test Module', creator=self.user)
        
        self.testcase = TestCaseModel.objects.create(
            project=self.project,
            module=self.module,
            name='Test Case 1',
            creator=self.user
        )
        
        self.suite = TestSuite.objects.create(
            project=self.project,
            name='Test Suite 1',
            creator=self.user
        )

    def test_suite_validation_with_testcase(self):
        """测试包含用例的套件验证"""
        self.suite.testcases.add(self.testcase)
        
        serializer = TestExecutionCreateSerializer(data={'suite_id': self.suite.id})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        
    def test_suite_validation_empty(self):
        """测试空套件验证"""
        serializer = TestExecutionCreateSerializer(data={'suite_id': self.suite.id})
        self.assertFalse(serializer.is_valid())
        self.assertIn('suite_id', serializer.errors)
        self.assertEqual(str(serializer.errors['suite_id'][0]), "测试套件中没有测试用例")

    def test_suite_serializer_partial_update(self):
        """测试套件序列化器的部分更新"""
        self.suite.testcases.add(self.testcase)
        
        data = {'name': 'Updated Suite Name'}
        serializer = TestSuiteSerializer(instance=self.suite, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_suite = serializer.save()
        self.assertEqual(updated_suite.name, 'Updated Suite Name')
        self.assertTrue(updated_suite.testcases.exists())

    def test_suite_serializer_validation_empty_create(self):
        """测试创建空套件时的验证"""
        data = {
            'name': 'Empty Suite',
            'project': self.project.id,
            'testcases': [],
        }
        # 需要提供 context
        context = {'project_id': self.project.id, 'request': None}
        serializer = TestSuiteSerializer(data=data, context=context)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)