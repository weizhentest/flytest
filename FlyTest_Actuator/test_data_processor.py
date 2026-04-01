# -*- coding: utf-8 -*-
"""
变量处理器单元测试
"""

import pytest
from data_processor import DataProcessor, get_data_processor, reset_data_processor


class TestDataProcessor:
    """DataProcessor 类测试"""
    
    def setup_method(self):
        """每个测试方法前重置处理器"""
        self.dp = DataProcessor()
    
    def test_set_and_get_cache(self):
        """测试设置和获取缓存变量"""
        self.dp.set_cache('username', 'admin')
        assert self.dp.get_cache('username') == 'admin'
        assert self.dp.get_cache('not_exist') is None
        assert self.dp.get_cache('not_exist', 'default') == 'default'
    
    def test_get_all(self):
        """测试获取所有变量"""
        self.dp.set_cache('key1', 'value1')
        self.dp.set_cache('key2', 'value2')
        all_vars = self.dp.get_all()
        assert all_vars == {'key1': 'value1', 'key2': 'value2'}
    
    def test_clear(self):
        """测试清空缓存"""
        self.dp.set_cache('key1', 'value1')
        self.dp.clear()
        assert self.dp.get_all() == {}
    
    def test_load_public_data(self):
        """测试加载公共数据"""
        public_data = [
            {'key': 'str_var', 'value': 'hello', 'type': 0, 'is_enabled': True},
            {'key': 'int_var', 'value': '123', 'type': 1, 'is_enabled': True},
            {'key': 'list_var', 'value': '[1, 2, 3]', 'type': 2, 'is_enabled': True},
            {'key': 'dict_var', 'value': '{"a": 1}', 'type': 3, 'is_enabled': True},
            {'key': 'disabled_var', 'value': 'skip', 'type': 0, 'is_enabled': False},
        ]
        self.dp.load_public_data(public_data)
        
        assert self.dp.get_cache('str_var') == 'hello'
        assert self.dp.get_cache('int_var') == 123
        assert self.dp.get_cache('list_var') == [1, 2, 3]
        assert self.dp.get_cache('dict_var') == {'a': 1}
        assert self.dp.get_cache('disabled_var') is None
    
    def test_replace_simple_variable(self):
        """测试简单变量替换"""
        self.dp.set_cache('username', 'admin')
        self.dp.set_cache('password', '123456')
        
        # 单个变量
        result = self.dp.replace('${{username}}')
        assert result == 'admin'
        
        # 嵌入字符串中
        result = self.dp.replace('用户名: ${{username}}, 密码: ${{password}}')
        assert result == '用户名: admin, 密码: 123456'
    
    def test_replace_preserves_type(self):
        """测试变量替换保持原始类型"""
        self.dp.set_cache('num', 42)
        self.dp.set_cache('list_data', [1, 2, 3])
        self.dp.set_cache('dict_data', {'key': 'value'})
        
        # 单独变量返回原始类型
        assert self.dp.replace('${{num}}') == 42
        assert self.dp.replace('${{list_data}}') == [1, 2, 3]
        assert self.dp.replace('${{dict_data}}') == {'key': 'value'}
        
        # 嵌入字符串中转为 JSON 字符串
        result = self.dp.replace('数据: ${{list_data}}')
        assert result == '数据: [1, 2, 3]'
    
    def test_replace_nested_dict(self):
        """测试嵌套字典中的变量替换"""
        self.dp.set_cache('token', 'abc123')
        
        data = {
            'headers': {
                'Authorization': 'Bearer ${{token}}'
            },
            'body': {
                'data': '${{token}}'
            }
        }
        result = self.dp.replace(data)
        assert result == {
            'headers': {
                'Authorization': 'Bearer abc123'
            },
            'body': {
                'data': 'abc123'
            }
        }
    
    def test_replace_list(self):
        """测试列表中的变量替换"""
        self.dp.set_cache('item1', 'A')
        self.dp.set_cache('item2', 'B')
        
        data = ['${{item1}}', '${{item2}}', 'fixed']
        result = self.dp.replace(data)
        assert result == ['A', 'B', 'fixed']
    
    def test_replace_undefined_variable(self):
        """测试未定义变量保持原样"""
        result = self.dp.replace('${{undefined_var}}')
        assert result == '${{undefined_var}}'
    
    def test_replace_nested_variable(self):
        """测试嵌套变量替换"""
        self.dp.set_cache('inner', 'world')
        self.dp.set_cache('outer', 'hello ${{inner}}')
        
        result = self.dp.replace('${{outer}}')
        assert result == 'hello world'
    
    def test_has_variable(self):
        """测试检查是否包含变量"""
        assert self.dp.has_variable('${{var}}') is True
        assert self.dp.has_variable('no variable') is False
        assert self.dp.has_variable({'key': '${{var}}'}) is True
        assert self.dp.has_variable(['${{var}}', 'normal']) is True
    
    def test_extract_variables(self):
        """测试提取变量名"""
        text = '用户 ${{username}} 的密码是 ${{password}}'
        variables = self.dp.extract_variables(text)
        assert variables == {'username', 'password'}
        
        # 从嵌套结构提取
        data = {
            'auth': '${{token}}',
            'items': ['${{item1}}', '${{item2}}']
        }
        variables = self.dp.extract_variables(data)
        assert variables == {'token', 'item1', 'item2'}


class TestGlobalInstance:
    """全局实例测试"""
    
    def test_get_data_processor_singleton(self):
        """测试获取全局单例"""
        dp1 = get_data_processor()
        dp2 = get_data_processor()
        assert dp1 is dp2
    
    def test_reset_data_processor(self):
        """测试重置处理器"""
        dp1 = get_data_processor()
        dp1.set_cache('key', 'value')
        
        dp2 = reset_data_processor()
        assert dp2 is not dp1
        assert dp2.get_cache('key') is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
