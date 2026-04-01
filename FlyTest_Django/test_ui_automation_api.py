#!/usr/bin/env python
"""
UI自动化模块API测试脚本
测试所有API端点的CRUD操作
"""
import os
import sys
import json
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flytest_django.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from projects.models import Project

User = get_user_model()


class UIAutomationAPITest:
    """UI自动化API测试类"""
    
    def __init__(self):
        self.client = APIClient()
        self.user = None
        self.project = None
        self.base_url = '/api/ui-automation'
        
        # 测试数据ID
        self.module_id = None
        self.page_id = None
        self.element_id = None
        self.page_step_id = None
        self.step_detail_id = None
        self.test_case_id = None
        self.case_step_id = None
        self.public_data_id = None
        self.env_config_id = None
    
    def setup(self):
        """初始化测试数据"""
        print("=" * 60)
        print("初始化测试环境...")
        
        # 创建或获取测试用户
        self.user, created = User.objects.get_or_create(
            username='api_test_user',
            defaults={'email': 'test@example.com', 'is_staff': True}
        )
        if created:
            self.user.set_password('testpass123')
            self.user.save()
            print(f"  创建测试用户: {self.user.username}")
        else:
            print(f"  使用现有用户: {self.user.username}")
        
        # 创建或获取测试项目
        self.project, created = Project.objects.get_or_create(
            name='API测试项目',
            defaults={'description': '用于API测试的项目'}
        )
        if created:
            print(f"  创建测试项目: {self.project.name}")
        else:
            print(f"  使用现有项目: {self.project.name}")
        
        # 认证
        self.client.force_authenticate(user=self.user)
        print("  用户认证完成")
        print("=" * 60)
    
    def test_module_api(self):
        """测试模块API"""
        print("\n[1] 测试模块API (UiModule)")
        print("-" * 40)
        
        # 创建模块 (不包含None值的字段)
        data = {
            'name': '测试模块',
            'project': self.project.id,
            'level': 1
        }
        response = self.client.post(f'{self.base_url}/modules/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.module_id = response.data['id']
            print(f"  ✓ 创建模块成功: ID={self.module_id}")
        else:
            print(f"  ✗ 创建模块失败: {response.status_code} - {response.data}")
            return False
        
        # 获取模块列表
        response = self.client.get(f'{self.base_url}/modules/')
        if response.status_code == status.HTTP_200_OK:
            print(f"  ✓ 获取模块列表成功: 共{len(response.data)}条")
        else:
            print(f"  ✗ 获取模块列表失败: {response.status_code}")
        
        # 更新模块
        response = self.client.patch(
            f'{self.base_url}/modules/{self.module_id}/',
            {'name': '更新后的模块'}
        )
        if response.status_code == status.HTTP_200_OK:
            print(f"  ✓ 更新模块成功")
        else:
            print(f"  ✗ 更新模块失败: {response.status_code}")
        
        return True
    
    def test_page_api(self):
        """测试页面API"""
        print("\n[2] 测试页面API (UiPage)")
        print("-" * 40)
        
        data = {
            'name': '登录页面',
            'url': 'https://example.com/login',
            'project': self.project.id,
            'module': self.module_id
        }
        response = self.client.post(f'{self.base_url}/pages/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.page_id = response.data['id']
            print(f"  ✓ 创建页面成功: ID={self.page_id}")
        else:
            print(f"  ✗ 创建页面失败: {response.status_code} - {response.data}")
            return False
        
        # 获取页面详情
        response = self.client.get(f'{self.base_url}/pages/{self.page_id}/')
        if response.status_code == status.HTTP_200_OK:
            print(f"  ✓ 获取页面详情成功: {response.data['name']}")
        else:
            print(f"  ✗ 获取页面详情失败: {response.status_code}")
        
        return True
    
    def test_element_api(self):
        """测试元素API"""
        print("\n[3] 测试元素API (UiElement)")
        print("-" * 40)
        
        data = {
            'name': '用户名输入框',
            'page': self.page_id,
            'locator_type': 'css',
            'locator_value': '#username',
            'locator_type_2': 'xpath',
            'locator_value_2': '//input[@id="username"]'
        }
        response = self.client.post(f'{self.base_url}/elements/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.element_id = response.data['id']
            print(f"  ✓ 创建元素成功: ID={self.element_id}")
        else:
            print(f"  ✗ 创建元素失败: {response.status_code} - {response.data}")
            return False
        
        # 按页面过滤元素
        response = self.client.get(f'{self.base_url}/elements/?page={self.page_id}')
        if response.status_code == status.HTTP_200_OK:
            print(f"  ✓ 按页面过滤元素成功: 共{len(response.data)}条")
        else:
            print(f"  ✗ 按页面过滤元素失败: {response.status_code}")
        
        return True
    
    def test_page_steps_api(self):
        """测试页面步骤API"""
        print("\n[4] 测试页面步骤API (UiPageSteps)")
        print("-" * 40)
        
        data = {
            'name': '登录操作',
            'project': self.project.id,
            'page': self.page_id,
            'module': self.module_id,
            'flow_data': {'nodes': [], 'edges': []}
        }
        response = self.client.post(f'{self.base_url}/page-steps/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.page_step_id = response.data['id']
            print(f"  ✓ 创建页面步骤成功: ID={self.page_step_id}")
        else:
            print(f"  ✗ 创建页面步骤失败: {response.status_code} - {response.data}")
            return False
        
        return True
    
    def test_step_detail_api(self):
        """测试步骤详情API"""
        print("\n[5] 测试步骤详情API (UiPageStepsDetailed)")
        print("-" * 40)
        
        data = {
            'page_step': self.page_step_id,
            'step_type': 0,  # 元素操作
            'element': self.element_id,
            'ope_key': 'input',
            'ope_value': {'value': 'test_user'},
            'step_sort': 1
        }
        response = self.client.post(f'{self.base_url}/page-steps-detailed/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.step_detail_id = response.data['id']
            print(f"  ✓ 创建步骤详情成功: ID={self.step_detail_id}")
        else:
            print(f"  ✗ 创建步骤详情失败: {response.status_code} - {response.data}")
            return False
        
        # 测试批量更新排序
        response = self.client.post(
            f'{self.base_url}/page-steps-detailed/batch_update/',
            {'items': [{'id': self.step_detail_id, 'step_sort': 2}]},
            format='json'
        )
        if response.status_code == status.HTTP_200_OK:
            print(f"  ✓ 批量更新排序成功")
        else:
            print(f"  ✗ 批量更新排序失败: {response.status_code}")
        
        return True
    
    def test_test_case_api(self):
        """测试用例API"""
        print("\n[6] 测试用例API (UiTestCase)")
        print("-" * 40)
        
        data = {
            'name': '登录测试用例',
            'project': self.project.id,
            'module': self.module_id,
            'level': 'P0',
            'status': 0
        }
        response = self.client.post(f'{self.base_url}/testcases/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.test_case_id = response.data['id']
            print(f"  ✓ 创建测试用例成功: ID={self.test_case_id}")
        else:
            print(f"  ✗ 创建测试用例失败: {response.status_code} - {response.data}")
            return False
        
        return True
    
    def test_case_steps_api(self):
        """测试用例步骤API"""
        print("\n[7] 测试用例步骤API (UiCaseStepsDetailed)")
        print("-" * 40)
        
        data = {
            'test_case': self.test_case_id,
            'page_step': self.page_step_id,
            'case_sort': 1
        }
        response = self.client.post(f'{self.base_url}/case-steps/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.case_step_id = response.data['id']
            print(f"  ✓ 创建用例步骤成功: ID={self.case_step_id}")
        else:
            print(f"  ✗ 创建用例步骤失败: {response.status_code} - {response.data}")
            return False
        
        return True
    
    def test_public_data_api(self):
        """测试公共数据API"""
        print("\n[8] 测试公共数据API (UiPublicData)")
        print("-" * 40)
        
        data = {
            'project': self.project.id,
            'key': 'test_username',
            'value': 'admin',
            'data_type': 'string',
            'description': '测试用户名'
        }
        response = self.client.post(f'{self.base_url}/public-data/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.public_data_id = response.data['id']
            print(f"  ✓ 创建公共数据成功: ID={self.public_data_id}")
        else:
            print(f"  ✗ 创建公共数据失败: {response.status_code} - {response.data}")
            return False
        
        return True
    
    def test_env_config_api(self):
        """测试环境配置API"""
        print("\n[9] 测试环境配置API (UiEnvironmentConfig)")
        print("-" * 40)
        
        data = {
            'project': self.project.id,
            'name': '测试环境',
            'env_type': 'test',
            'base_url': 'https://test.example.com',
            'config': json.dumps({'timeout': 30})
        }
        response = self.client.post(f'{self.base_url}/env-configs/', data, format='json')
        if response.status_code == status.HTTP_201_CREATED:
            self.env_config_id = response.data['id']
            print(f"  ✓ 创建环境配置成功: ID={self.env_config_id}")
        else:
            print(f"  ✗ 创建环境配置失败: {response.status_code} - {response.data}")
            return False
        
        return True
    
    def cleanup(self):
        """清理测试数据"""
        print("\n" + "=" * 60)
        print("清理测试数据...")
        
        # 按依赖顺序反向删除
        endpoints = [
            ('env-configs', self.env_config_id),
            ('public-data', self.public_data_id),
            ('case-steps', self.case_step_id),
            ('testcases', self.test_case_id),
            ('page-steps-detailed', self.step_detail_id),
            ('page-steps', self.page_step_id),
            ('elements', self.element_id),
            ('pages', self.page_id),
            ('modules', self.module_id),
        ]
        
        for endpoint, item_id in endpoints:
            if item_id:
                response = self.client.delete(f'{self.base_url}/{endpoint}/{item_id}/')
                if response.status_code == status.HTTP_204_NO_CONTENT:
                    print(f"  ✓ 删除{endpoint}成功")
                else:
                    print(f"  ✗ 删除{endpoint}失败: {response.status_code}")
        
        print("=" * 60)
    
    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("UI自动化模块API测试")
        print("=" * 60)
        
        self.setup()
        
        tests = [
            self.test_module_api,
            self.test_page_api,
            self.test_element_api,
            self.test_page_steps_api,
            self.test_step_detail_api,
            self.test_test_case_api,
            self.test_case_steps_api,
            self.test_public_data_api,
            self.test_env_config_api,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  ✗ 测试异常: {e}")
                failed += 1
        
        self.cleanup()
        
        print("\n" + "=" * 60)
        print(f"测试完成: 通过 {passed}/{passed + failed}")
        if failed == 0:
            print("✓ 所有API测试通过!")
        else:
            print(f"✗ 有 {failed} 个测试失败")
        print("=" * 60)
        
        return failed == 0


if __name__ == '__main__':
    test = UIAutomationAPITest()
    success = test.run_all_tests()
    sys.exit(0 if success else 1)
