# -*- coding: utf-8 -*-
"""
变量处理器，支持执行器中的 ${{variable}} 语法替换。

特性：
- 公共数据变量替换
- 嵌套对象点路径读取，例如 ${{df.tag.login_name}}
- 字符串、字典、列表递归替换
- 当整段文本就是一个变量时，保留原始数据类型
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Union

logger = logging.getLogger("actuator")
_MISSING = object()


class DataProcessor:
    """变量数据处理器。"""

    VARIABLE_PATTERN = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def set_cache(self, key: str, value: Any) -> None:
        self._cache[key] = value
        logger.debug("设置变量: %s = %s", key, value)

    def _lookup_value(self, key: str) -> Any:
        if key in self._cache:
            return self._cache[key]

        current: Any = self._cache
        for part in key.split("."):
            if isinstance(current, list):
                if not part.isdigit():
                    return _MISSING
                index = int(part)
                if index >= len(current):
                    return _MISSING
                current = current[index]
            elif isinstance(current, dict):
                if part not in current:
                    return _MISSING
                current = current[part]
            else:
                return _MISSING
        return current

    def get_cache(self, key: str, default: Any = None) -> Any:
        value = self._lookup_value(key)
        return default if value is _MISSING else value

    def get_all(self) -> dict[str, Any]:
        return self._cache.copy()

    def clear(self) -> None:
        self._cache.clear()
        logger.debug("已清空所有变量缓存")

    def load_public_data(self, public_data_list: list[dict]) -> None:
        """
        从公共数据接口加载变量。

        type:
        - 0: 字符串
        - 1: 整数
        - 2: 列表
        - 3: 字典
        """
        for item in public_data_list:
            if not item.get("is_enabled", True):
                continue

            key = item.get("key", "")
            value = item.get("value", "")
            data_type = item.get("type", 0)

            if not key:
                continue

            try:
                if data_type == 1:
                    value = int(value)
                elif data_type in {2, 3}:
                    value = json.loads(value) if isinstance(value, str) else value
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("变量 %s 类型转换失败: %s，使用原始字符串值", key, exc)

            self.set_cache(key, value)

        logger.info("已加载 %s 个公共变量", len(self._cache))

    def replace(self, value: Any, max_depth: int = 10) -> Any:
        if max_depth <= 0:
            logger.warning("变量替换达到最大递归深度，可能存在循环引用")
            return value

        if value is None:
            return value
        if isinstance(value, str):
            return self._replace_string(value, max_depth)
        if isinstance(value, dict):
            return {key: self.replace(item, max_depth - 1) for key, item in value.items()}
        if isinstance(value, list):
            return [self.replace(item, max_depth - 1) for item in value]
        return value

    def _replace_string(self, text: str, max_depth: int) -> Union[str, Any]:
        if not text:
            return text

        matches = list(self.VARIABLE_PATTERN.finditer(text))
        if not matches:
            return text

        stripped = text.strip()
        if len(matches) == 1 and matches[0].group(0) == stripped:
            var_name = matches[0].group(1).strip()
            value = self._lookup_value(var_name)
            if value is _MISSING:
                logger.warning("变量 %s 未定义，保持原样", var_name)
                return text
            if isinstance(value, str) and self.VARIABLE_PATTERN.search(value) and max_depth > 1:
                return self._replace_string(value, max_depth - 1)
            return value

        result = text
        for match in reversed(matches):
            var_name = match.group(1).strip()
            value = self._lookup_value(var_name)
            if value is _MISSING:
                logger.warning("变量 %s 未定义，保持原样", var_name)
                continue
            if isinstance(value, (dict, list)):
                replacement = json.dumps(value, ensure_ascii=False)
            else:
                replacement = str(value)
            result = result[: match.start()] + replacement + result[match.end() :]

        if self.VARIABLE_PATTERN.search(result) and max_depth > 1:
            return self._replace_string(result, max_depth - 1)
        return result

    def has_variable(self, value: Any) -> bool:
        if isinstance(value, str):
            return bool(self.VARIABLE_PATTERN.search(value))
        if isinstance(value, dict):
            return any(self.has_variable(item) for item in value.values())
        if isinstance(value, list):
            return any(self.has_variable(item) for item in value)
        return False

    def extract_variables(self, value: Any) -> set[str]:
        variables: set[str] = set()

        if isinstance(value, str):
            for match in self.VARIABLE_PATTERN.finditer(value):
                variables.add(match.group(1).strip())
        elif isinstance(value, dict):
            for item in value.values():
                variables.update(self.extract_variables(item))
        elif isinstance(value, list):
            for item in value:
                variables.update(self.extract_variables(item))

        return variables


_data_processor: Optional[DataProcessor] = None


def get_data_processor() -> DataProcessor:
    global _data_processor
    if _data_processor is None:
        _data_processor = DataProcessor()
    return _data_processor


def reset_data_processor() -> DataProcessor:
    global _data_processor
    _data_processor = DataProcessor()
    return _data_processor
