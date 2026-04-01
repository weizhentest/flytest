# -*- coding: utf-8 -*-
"""
变量处理器 - 实现 ${{变量名}} 语法的变量替换


支持:
- 公共数据变量替换: ${{变量名}}
- 嵌套变量替换: ${{var1}} -> value 包含 ${{var2}}
- JSON 类型自动转换
"""

import json
import re
import logging
from typing import Any, Optional, Union

logger = logging.getLogger('actuator')


class DataProcessor:
    """变量数据处理器"""
    
    # 变量匹配正则: ${{变量名}}
    VARIABLE_PATTERN = re.compile(r'\$\{\{([^}]+)\}\}')
    
    def __init__(self):
        self._cache: dict[str, Any] = {}
    
    def set_cache(self, key: str, value: Any) -> None:
        """设置缓存变量"""
        self._cache[key] = value
        logger.debug(f"设置变量: {key} = {value}")
    
    def get_cache(self, key: str, default: Any = None) -> Any:
        """获取缓存变量"""
        return self._cache.get(key, default)
    
    def get_all(self) -> dict[str, Any]:
        """获取所有缓存变量"""
        return self._cache.copy()
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.debug("已清空所有变量缓存")
    
    def load_public_data(self, public_data_list: list[dict]) -> None:
        """从公共数据列表加载变量到缓存
        
        Args:
            public_data_list: 公共数据列表，格式如:
                [{"key": "username", "value": "admin", "type": 0}, ...]
                type: 0=字符串, 1=整数, 2=列表, 3=字典
        """
        for item in public_data_list:
            if not item.get('is_enabled', True):
                continue
            
            key = item.get('key', '')
            value = item.get('value', '')
            data_type = item.get('type', 0)
            
            if not key:
                continue
            
            # 根据类型转换值
            try:
                if data_type == 1:  # 整数
                    value = int(value)
                elif data_type == 2:  # 列表
                    value = json.loads(value) if isinstance(value, str) else value
                elif data_type == 3:  # 字典
                    value = json.loads(value) if isinstance(value, str) else value
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"变量 {key} 类型转换失败: {e}，使用原始字符串值")
            
            self.set_cache(key, value)
        
        logger.info(f"已加载 {len(self._cache)} 个公共变量")
    
    def replace(self, value: Any, max_depth: int = 10) -> Any:
        """替换值中的变量
        
        Args:
            value: 要处理的值，可以是字符串、字典、列表
            max_depth: 最大递归深度，防止循环引用
        
        Returns:
            替换后的值
        """
        if max_depth <= 0:
            logger.warning("变量替换达到最大递归深度，可能存在循环引用")
            return value
        
        if value is None:
            return value
        
        if isinstance(value, str):
            return self._replace_string(value, max_depth)
        
        if isinstance(value, dict):
            return {k: self.replace(v, max_depth - 1) for k, v in value.items()}
        
        if isinstance(value, list):
            return [self.replace(item, max_depth - 1) for item in value]
        
        # 其他类型直接返回
        return value
    
    def _replace_string(self, text: str, max_depth: int) -> Union[str, Any]:
        """替换字符串中的变量
        
        Args:
            text: 要处理的字符串
            max_depth: 最大递归深度
        
        Returns:
            替换后的值。如果整个字符串就是一个变量且值为非字符串类型，
            则返回该类型的值；否则返回替换后的字符串
        """
        if not text or not isinstance(text, str):
            return text
        
        # 查找所有变量
        matches = list(self.VARIABLE_PATTERN.finditer(text))
        if not matches:
            return text
        
        # 如果整个字符串就是一个变量，返回原始类型的值
        if len(matches) == 1 and matches[0].group(0) == text.strip():
            var_name = matches[0].group(1).strip()
            if var_name in self._cache:
                value = self._cache[var_name]
                # 如果值中还包含变量，继续替换
                if isinstance(value, str) and self.VARIABLE_PATTERN.search(value):
                    return self._replace_string(value, max_depth - 1)
                return value
            else:
                logger.warning(f"变量 {var_name} 未定义，保持原样")
                return text
        
        # 多个变量或变量嵌入在字符串中，全部转为字符串拼接
        result = text
        for match in reversed(matches):  # 从后往前替换，避免索引偏移
            var_name = match.group(1).strip()
            if var_name in self._cache:
                var_value = self._cache[var_name]
                # 转为字符串
                if isinstance(var_value, (dict, list)):
                    replacement = json.dumps(var_value, ensure_ascii=False)
                else:
                    replacement = str(var_value)
                result = result[:match.start()] + replacement + result[match.end():]
            else:
                logger.warning(f"变量 {var_name} 未定义，保持原样")
        
        # 检查替换后是否还有变量
        if self.VARIABLE_PATTERN.search(result) and max_depth > 1:
            return self._replace_string(result, max_depth - 1)
        
        return result
    
    def has_variable(self, value: Any) -> bool:
        """检查值中是否包含变量"""
        if isinstance(value, str):
            return bool(self.VARIABLE_PATTERN.search(value))
        
        if isinstance(value, dict):
            return any(self.has_variable(v) for v in value.values())
        
        if isinstance(value, list):
            return any(self.has_variable(item) for item in value)
        
        return False
    
    def extract_variables(self, value: Any) -> set[str]:
        """提取值中的所有变量名"""
        variables: set[str] = set()
        
        if isinstance(value, str):
            for match in self.VARIABLE_PATTERN.finditer(value):
                variables.add(match.group(1).strip())
        
        elif isinstance(value, dict):
            for v in value.values():
                variables.update(self.extract_variables(v))
        
        elif isinstance(value, list):
            for item in value:
                variables.update(self.extract_variables(item))
        
        return variables


# 全局实例，供执行器使用
_data_processor: Optional[DataProcessor] = None


def get_data_processor() -> DataProcessor:
    """获取全局数据处理器实例"""
    global _data_processor
    if _data_processor is None:
        _data_processor = DataProcessor()
    return _data_processor


def reset_data_processor() -> DataProcessor:
    """重置数据处理器（新用例执行时调用）"""
    global _data_processor
    _data_processor = DataProcessor()
    return _data_processor
