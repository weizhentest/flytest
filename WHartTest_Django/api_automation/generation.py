from __future__ import annotations

from typing import Any

from .document_import import ParsedRequestData


def build_request_script(
    *,
    method: str,
    url: str,
    headers: dict[str, Any],
    params: dict[str, Any],
    body_type: str,
    body: Any,
    timeout_ms: int = 30000,
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "request": {
            "method": method,
            "url": url,
            "headers": headers or {},
            "params": params or {},
            "body_type": body_type,
            "body": body if body is not None else {},
            "timeout_ms": timeout_ms,
        },
        "assertions": assertions or [],
        "stages": [
            {
                "name": "prepare",
                "type": "prepare",
                "enabled": True,
            },
            {
                "name": "execute",
                "type": "request",
                "enabled": True,
            },
            {
                "name": "assert",
                "type": "assertions",
                "enabled": True,
            },
        ],
    }


def generate_test_case_name(request_name: str, method: str) -> str:
    action_map = {
        "GET": "读取校验",
        "POST": "创建校验",
        "PUT": "更新校验",
        "PATCH": "修改校验",
        "DELETE": "删除校验",
        "HEAD": "响应头校验",
        "OPTIONS": "能力探测校验",
    }
    suffix = action_map.get(method.upper(), "接口校验")
    return f"{request_name} - {suffix}"


def generate_test_case_description(request_name: str, url: str, method: str) -> str:
    return f"根据接口文档自动生成的测试用例，用于验证 {request_name}（{method} {url}）的基础可用性与响应状态。"


def generate_script_and_test_case(parsed_request: ParsedRequestData) -> tuple[dict[str, Any], dict[str, Any]]:
    assertions = parsed_request.assertions or [{"type": "status_code", "expected": 200}]
    script = build_request_script(
        method=parsed_request.method,
        url=parsed_request.url,
        headers=parsed_request.headers,
        params=parsed_request.params,
        body_type=parsed_request.body_type,
        body=parsed_request.body,
        assertions=assertions,
    )

    test_case = {
        "name": generate_test_case_name(parsed_request.name, parsed_request.method),
        "description": generate_test_case_description(parsed_request.name, parsed_request.url, parsed_request.method),
        "status": "ready",
        "tags": list(
            {
                "auto-generated",
                parsed_request.method.lower(),
                (parsed_request.collection_name or "default").lower(),
            }
        ),
        "assertions": assertions,
        "script": script,
    }
    return script, test_case
