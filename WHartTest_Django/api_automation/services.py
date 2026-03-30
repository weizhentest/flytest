import json
import random
import re
import time
import uuid
from typing import Any
from urllib.parse import urljoin


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


class VariableResolver:
    def __init__(self, variables: dict[str, Any] | None = None):
        base_variables = variables.copy() if variables else {}
        base_variables.setdefault("timestamp", int(time.time()))
        base_variables.setdefault("timestamp_ms", int(time.time() * 1000))
        base_variables.setdefault("uuid", str(uuid.uuid4()))
        base_variables.setdefault("random_int", random.randint(100000, 999999))
        self.variables = base_variables

    def resolve(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if isinstance(value, str):
            return self.resolve_string(value)
        return value

    def resolve_string(self, value: str) -> Any:
        matched = PLACEHOLDER_PATTERN.fullmatch(value.strip())
        if matched:
            return self.variables.get(matched.group(1), value)

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            replacement = self.variables.get(key, match.group(0))
            if isinstance(replacement, (dict, list)):
                return json.dumps(replacement, ensure_ascii=False)
            return str(replacement)

        return PLACEHOLDER_PATTERN.sub(replace, value)


def build_request_url(base_url: str, request_url: str) -> str:
    if request_url.startswith(("http://", "https://")):
        return request_url
    if not base_url:
        return request_url
    return urljoin(base_url.rstrip("/") + "/", request_url.lstrip("/"))


def extract_json_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def evaluate_assertions(assertions: list[dict[str, Any]], status_code: int, response_text: str, response_json: Any) -> tuple[list[dict[str, Any]], bool]:
    if not assertions:
        return [], True

    results: list[dict[str, Any]] = []
    all_passed = True

    for index, assertion in enumerate(assertions, start=1):
        assertion_type = assertion.get("type")
        expected = assertion.get("expected")
        operator = assertion.get("operator", "equals")
        path = assertion.get("path")
        passed = False
        actual: Any = None
        message = ""

        if assertion_type == "status_code":
            actual = status_code
            passed = actual == int(expected)
            message = f"状态码应为 {expected}"
        elif assertion_type == "body_contains":
            actual = response_text
            passed = str(expected) in response_text
            message = f"响应体包含 {expected}"
        elif assertion_type == "json_path":
            actual = extract_json_path(response_json, str(path)) if response_json is not None and path else None
            if operator == "contains":
                passed = str(expected) in str(actual)
            elif operator == "not_equals":
                passed = actual != expected
            else:
                passed = actual == expected
            message = f"JSONPath {path} {operator} {expected}"
        elif assertion_type == "header":
            header_name = str(path or "")
            actual = None
            passed = False
            message = f"暂不支持 header 断言: {header_name}"
        else:
            actual = None
            passed = False
            message = f"未知断言类型: {assertion_type}"

        results.append(
            {
                "index": index,
                "type": assertion_type,
                "operator": operator,
                "path": path,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "message": message,
            }
        )
        all_passed = all_passed and passed

    return results, all_passed

