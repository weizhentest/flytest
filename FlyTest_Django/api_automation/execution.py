from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any

import httpx

from data_factory.reference import build_reference_tree

from .generation import build_request_script, build_parameterized_test_case_script
from .models import ApiEnvironment, ApiExecutionRecord, ApiRequest, ApiTestCase
from .services import VariableResolver, build_request_url, extract_json_path, find_missing_variables
from .specs import (
    serialize_assertion_specs,
    serialize_environment_specs,
    serialize_extractor_specs,
    serialize_request_spec,
    serialize_test_case_override,
)


DEFAULT_TOKEN_PATHS = [
    "data.token",
    "data.accessToken",
    "data.access_token",
    "data.jwt",
    "data.authorization",
    "token",
    "accessToken",
    "access_token",
    "authorization",
]
TOKEN_VARIABLE_NAMES = {"token", "access_token", "authorization", "refresh_token", "refreshToken"}


@dataclass
class StageResult:
    name: str
    stage_type: str
    status: str
    started_at: float
    ended_at: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.stage_type,
            "status": self.status,
            "duration_ms": round((self.ended_at - self.started_at) * 1000, 2),
            "detail": self.detail,
        }


@dataclass
class EffectiveRequestSpec:
    method: str
    url: str
    body_mode: str
    body_json: dict[str, Any] | list[Any] | None
    raw_text: str
    xml_text: str
    binary_base64: str
    graphql_query: str
    graphql_operation_name: str
    graphql_variables: dict[str, Any]
    timeout_ms: int
    headers: list[dict[str, Any]]
    query: list[dict[str, Any]]
    cookies: list[dict[str, Any]]
    form_fields: list[dict[str, Any]]
    multipart_parts: list[dict[str, Any]]
    files: list[dict[str, Any]]
    auth: dict[str, Any]
    transport: dict[str, Any]
    assertions: list[dict[str, Any]]
    extractors: list[dict[str, Any]]


def _merge_named_items(base_items: list[dict[str, Any]], override_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered: list[str] = []
    for item in base_items + override_items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        if name not in merged:
            ordered.append(name)
            merged[name] = {"name": name}
        merged[name].update(item)
    return [merged[name] for name in ordered]


def _merge_file_items(base_items: list[dict[str, Any]], override_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in base_items + override_items:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "")
        if not field_name:
            continue
        key = f"{field_name}:{item.get('file_name') or item.get('file_path') or item.get('order', 0)}"
        if key not in keyed:
            order.append(key)
            keyed[key] = {"field_name": field_name}
        keyed[key].update(item)
    return [keyed[key] for key in order]


def _merge_auth(base_auth: dict[str, Any], override_auth: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_auth or {})
    for key, value in (override_auth or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def _merge_transport(base_transport: dict[str, Any], override_transport: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_transport or {})
    for key, value in (override_transport or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def _pick_override_scalar(
    override_spec: dict[str, Any],
    key: str,
    fallback: Any,
    *,
    replace_fields: set[str] | None = None,
    allow_blank_string: bool = False,
):
    if key not in override_spec:
        return fallback
    value = override_spec.get(key)
    if value is None:
        return fallback
    if key not in (replace_fields or set()) and value == "":
        return fallback
    if value == "" and not allow_blank_string and key in (replace_fields or set()):
        return fallback
    return value


def _pick_override_json(
    override_spec: dict[str, Any],
    key: str,
    fallback: Any,
    *,
    replace_fields: set[str] | None = None,
):
    if key not in override_spec:
        return fallback
    value = override_spec.get(key)
    if key in (replace_fields or set()) and isinstance(value, (dict, list)):
        return value
    if value:
        return value
    return fallback


def _merge_named_bucket(
    base_items: list[dict[str, Any]],
    override_spec: dict[str, Any],
    key: str,
    *,
    replace_fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    if key not in override_spec:
        return list(base_items)
    override_items = list(override_spec.get(key) or [])
    if key in (replace_fields or set()):
        return override_items
    return _merge_named_items(base_items, override_items)


def _merge_file_bucket(
    base_items: list[dict[str, Any]],
    override_spec: dict[str, Any],
    *,
    replace_fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    if "files" not in override_spec:
        return list(base_items)
    override_items = list(override_spec.get("files") or [])
    if "files" in (replace_fields or set()):
        return override_items
    return _merge_file_items(base_items, override_items)


def _merge_request_spec_payload(
    base_request_spec: dict[str, Any],
    override_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    override_spec = override_spec if isinstance(override_spec, dict) else {}
    replace_fields = {
        str(item).strip()
        for item in (override_spec.get("replace_fields") or [])
        if str(item).strip()
    }
    return {
        **base_request_spec,
        "method": _pick_override_scalar(override_spec, "method", base_request_spec["method"], replace_fields=replace_fields),
        "url": _pick_override_scalar(override_spec, "url", base_request_spec["url"], replace_fields=replace_fields),
        "body_mode": _pick_override_scalar(override_spec, "body_mode", base_request_spec["body_mode"], replace_fields=replace_fields),
        "body_json": _pick_override_json(
            override_spec,
            "body_json",
            base_request_spec["body_json"],
            replace_fields=replace_fields,
        ),
        "raw_text": _pick_override_scalar(
            override_spec,
            "raw_text",
            base_request_spec["raw_text"],
            replace_fields=replace_fields,
            allow_blank_string=True,
        ),
        "xml_text": _pick_override_scalar(
            override_spec,
            "xml_text",
            base_request_spec["xml_text"],
            replace_fields=replace_fields,
            allow_blank_string=True,
        ),
        "binary_base64": _pick_override_scalar(
            override_spec,
            "binary_base64",
            base_request_spec["binary_base64"],
            replace_fields=replace_fields,
            allow_blank_string=True,
        ),
        "graphql_query": _pick_override_scalar(
            override_spec,
            "graphql_query",
            base_request_spec["graphql_query"],
            replace_fields=replace_fields,
            allow_blank_string=True,
        ),
        "graphql_operation_name": _pick_override_scalar(
            override_spec,
            "graphql_operation_name",
            base_request_spec["graphql_operation_name"],
            replace_fields=replace_fields,
            allow_blank_string=True,
        ),
        "graphql_variables": _pick_override_json(
            override_spec,
            "graphql_variables",
            base_request_spec["graphql_variables"],
            replace_fields=replace_fields,
        ),
        "timeout_ms": _pick_override_scalar(
            override_spec,
            "timeout_ms",
            base_request_spec["timeout_ms"],
            replace_fields=replace_fields,
        ),
        "headers": _merge_named_bucket(
            base_request_spec["headers"],
            override_spec,
            "headers",
            replace_fields=replace_fields,
        ),
        "query": _merge_named_bucket(
            base_request_spec["query"],
            override_spec,
            "query",
            replace_fields=replace_fields,
        ),
        "cookies": _merge_named_bucket(
            base_request_spec["cookies"],
            override_spec,
            "cookies",
            replace_fields=replace_fields,
        ),
        "form_fields": _merge_named_bucket(
            base_request_spec["form_fields"],
            override_spec,
            "form_fields",
            replace_fields=replace_fields,
        ),
        "multipart_parts": _merge_named_bucket(
            base_request_spec["multipart_parts"],
            override_spec,
            "multipart_parts",
            replace_fields=replace_fields,
        ),
        "files": _merge_file_bucket(base_request_spec["files"], override_spec, replace_fields=replace_fields),
        "auth": _merge_auth(base_request_spec["auth"], dict(override_spec.get("auth") or {})),
        "transport": _merge_transport(base_request_spec["transport"], dict(override_spec.get("transport") or {})),
    }


def build_effective_request_spec(
    api_request: ApiRequest,
    test_case: ApiTestCase | None = None,
    request_override: dict[str, Any] | None = None,
    assertion_specs_override: list[dict[str, Any]] | None = None,
    extractor_specs_override: list[dict[str, Any]] | None = None,
) -> EffectiveRequestSpec:
    request_spec = serialize_request_spec(api_request)
    assertion_specs = serialize_assertion_specs(test_case) if test_case else serialize_assertion_specs(api_request)
    extractor_specs = serialize_extractor_specs(api_request)
    if test_case:
        if serialize_extractor_specs(test_case):
            extractor_specs = extractor_specs + serialize_extractor_specs(test_case)
        request_spec = _merge_request_spec_payload(request_spec, serialize_test_case_override(test_case))
    if request_override:
        request_spec = _merge_request_spec_payload(request_spec, request_override)
    if assertion_specs_override is not None:
        assertion_specs = list(assertion_specs_override)
    if extractor_specs_override is not None:
        extractor_specs = list(extractor_specs_override)
    return EffectiveRequestSpec(
        method=str(request_spec["method"]).upper(),
        url=str(request_spec["url"]),
        body_mode=str(request_spec["body_mode"] or "none").lower(),
        body_json=request_spec.get("body_json"),
        raw_text=str(request_spec.get("raw_text") or ""),
        xml_text=str(request_spec.get("xml_text") or ""),
        binary_base64=str(request_spec.get("binary_base64") or ""),
        graphql_query=str(request_spec.get("graphql_query") or ""),
        graphql_operation_name=str(request_spec.get("graphql_operation_name") or ""),
        graphql_variables=request_spec.get("graphql_variables") if isinstance(request_spec.get("graphql_variables"), dict) else {},
        timeout_ms=int(request_spec.get("timeout_ms") or api_request.timeout_ms or 30000),
        headers=list(request_spec.get("headers") or []),
        query=list(request_spec.get("query") or []),
        cookies=list(request_spec.get("cookies") or []),
        form_fields=list(request_spec.get("form_fields") or []),
        multipart_parts=list(request_spec.get("multipart_parts") or []),
        files=list(request_spec.get("files") or []),
        auth=dict(request_spec.get("auth") or {}),
        transport=dict(request_spec.get("transport") or {}),
        assertions=assertion_specs,
        extractors=extractor_specs,
    )


@dataclass
class ExecutionRunContext:
    run_id: str | None = None
    run_name: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    environment: ApiEnvironment | None = None
    execution_mode: str = "sync"
    cookies: httpx.Cookies = field(default_factory=httpx.Cookies)
    _client: httpx.Client | None = None
    _transport_signature: tuple[Any, ...] | None = None
    _async_client: httpx.AsyncClient | None = None
    _async_transport_signature: tuple[Any, ...] | None = None
    _async_runner: asyncio.Runner | None = None

    def close(self):
        self._close_sync_client()
        self._close_async_client()
        if self._async_runner is not None:
            self._async_runner.close()
            self._async_runner = None

    def _normalize_execution_mode(self) -> str:
        return "async" if str(self.execution_mode or "sync").lower() == "async" else "sync"

    def _build_transport_signature(self, transport: dict[str, Any]) -> tuple[Any, ...]:
        return (
            transport.get("verify_ssl", True),
            transport.get("proxy_url") or "",
            transport.get("client_cert") or "",
            transport.get("client_key") or "",
        )

    def _build_client_kwargs(self, transport: dict[str, Any]) -> dict[str, Any]:
        client_kwargs: dict[str, Any] = {
            "verify": transport.get("verify_ssl", True),
            "cookies": self.cookies,
        }
        if transport.get("proxy_url"):
            client_kwargs["proxy"] = transport["proxy_url"]
        if transport.get("client_cert") and transport.get("client_key"):
            client_kwargs["cert"] = (transport["client_cert"], transport["client_key"])
        elif transport.get("client_cert"):
            client_kwargs["cert"] = transport["client_cert"]
        return client_kwargs

    def _close_sync_client(self):
        if self._client is not None:
            self.cookies = self._client.cookies
            self._client.close()
            self._client = None
            self._transport_signature = None

    def _close_async_client(self):
        if self._async_client is not None:
            self.cookies = self._async_client.cookies
            self._get_async_runner().run(self._async_client.aclose())
            self._async_client = None
            self._async_transport_signature = None

    def _get_async_runner(self) -> asyncio.Runner:
        if self._async_runner is None:
            self._async_runner = asyncio.Runner()
        return self._async_runner

    def get_client(self, transport: dict[str, Any]) -> httpx.Client:
        signature = self._build_transport_signature(transport)
        if self._client is not None and self._transport_signature == signature:
            return self._client

        self._close_sync_client()
        self._close_async_client()
        self._client = httpx.Client(**self._build_client_kwargs(transport))
        self._transport_signature = signature
        return self._client

    def get_async_client(self, transport: dict[str, Any]) -> httpx.AsyncClient:
        signature = self._build_transport_signature(transport)
        if self._async_client is not None and self._async_transport_signature == signature:
            return self._async_client

        self._close_sync_client()
        self._close_async_client()
        self._async_client = httpx.AsyncClient(**self._build_client_kwargs(transport))
        self._async_transport_signature = signature
        return self._async_client

    @staticmethod
    def _request_sync(
        *,
        client: httpx.Client,
        request_kwargs: dict[str, Any],
        retries: int,
        retry_interval: float,
    ) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                return client.request(**request_kwargs)
            except Exception:
                if attempt >= retries:
                    raise
                time.sleep(retry_interval)
        raise RuntimeError("Request retries exhausted unexpectedly")

    @staticmethod
    async def _request_async(
        *,
        client: httpx.AsyncClient,
        request_kwargs: dict[str, Any],
        retries: int,
        retry_interval: float,
    ) -> httpx.Response:
        for attempt in range(retries + 1):
            try:
                return await client.request(**request_kwargs)
            except Exception:
                if attempt >= retries:
                    raise
                await asyncio.sleep(retry_interval)
        raise RuntimeError("Request retries exhausted unexpectedly")

    def request(
        self,
        *,
        transport: dict[str, Any],
        request_kwargs: dict[str, Any],
        retries: int,
        retry_interval: float,
    ) -> httpx.Response:
        if self._normalize_execution_mode() == "async":
            client = self.get_async_client(transport)
            return self._get_async_runner().run(
                self._request_async(
                    client=client,
                    request_kwargs=request_kwargs,
                    retries=retries,
                    retry_interval=retry_interval,
                )
            )

        client = self.get_client(transport)
        return self._request_sync(
            client=client,
            request_kwargs=request_kwargs,
            retries=retries,
            retry_interval=retry_interval,
        )


def _build_environment_defaults(environment: ApiEnvironment | None) -> tuple[str, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if not environment:
        return "", {}, {}, []
    spec_payload = serialize_environment_specs(environment)
    base_headers = {
        item["name"]: item.get("value", "")
        for item in spec_payload.get("headers", [])
        if item.get("enabled", True)
    }
    variables = {
        item["name"]: item.get("value", "")
        for item in spec_payload.get("variables", [])
        if item.get("enabled", True)
    }
    cookies = [item for item in spec_payload.get("cookies", []) if item.get("enabled", True)]
    return environment.base_url or "", base_headers, variables, cookies


def _resolve_items(items: list[dict[str, Any]], resolver: VariableResolver) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for item in items:
        if not item.get("enabled", True):
            continue
        resolved.append(
            {
                **item,
                "name": resolver.resolve(item.get("name", "")),
                "value": resolver.resolve(item.get("value", "")),
            }
        )
    return resolved


def _items_to_dict(items: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        result[name] = item.get("value", "")
    return result


def _resolve_body(spec: EffectiveRequestSpec, resolver: VariableResolver) -> tuple[str, Any]:
    if spec.body_mode == "json":
        return "json", resolver.resolve(spec.body_json or {})
    if spec.body_mode in {"form", "urlencoded"}:
        return "data", _items_to_dict(_resolve_items(spec.form_fields, resolver))
    if spec.body_mode == "multipart":
        return "multipart", _items_to_dict(_resolve_items(spec.multipart_parts, resolver))
    if spec.body_mode == "graphql":
        return "json", {
            "query": resolver.resolve(spec.graphql_query),
            "operationName": resolver.resolve(spec.graphql_operation_name),
            "variables": resolver.resolve(spec.graphql_variables or {}),
        }
    if spec.body_mode == "xml":
        return "content", resolver.resolve(spec.xml_text)
    if spec.body_mode == "binary":
        return "content", base64.b64decode(resolver.resolve(spec.binary_base64) or "")
    if spec.body_mode == "raw":
        return "content", resolver.resolve(spec.raw_text)
    return "none", None


def _extract_value_from_source(
    source: str,
    selector: str,
    response: httpx.Response,
    response_payload: Any,
    response_time_ms: float | None,
):
    if source == "json_path":
        return extract_json_path(response_payload, selector) if selector and response_payload is not None else None
    if source == "header":
        return response.headers.get(selector)
    if source == "cookie":
        return response.cookies.get(selector)
    if source == "status_code":
        return response.status_code
    if source == "response_time":
        return response_time_ms
    if source == "regex":
        match = re.search(selector, response.text or "")
        if not match:
            return None
        return match.group(1) if match.groups() else match.group(0)
    return None


def _apply_extractors(
    extractor_specs: list[dict[str, Any]],
    response: httpx.Response,
    response_payload: Any,
    response_time_ms: float | None,
    runtime_variables: dict[str, Any],
):
    results: list[dict[str, Any]] = []
    for item in extractor_specs:
        if not item.get("enabled", True):
            continue
        variable_name = str(item.get("variable_name") or "").strip()
        if not variable_name:
            continue
        value = _extract_value_from_source(
            str(item.get("source") or ""),
            str(item.get("selector") or ""),
            response,
            response_payload,
            response_time_ms,
        )
        success = value not in (None, "")
        if success:
            runtime_variables[variable_name] = value
        elif item.get("default_value") not in (None, ""):
            runtime_variables[variable_name] = item.get("default_value")
            success = True
            value = item.get("default_value")
        results.append(
            {
                "variable_name": variable_name,
                "source": item.get("source"),
                "selector": item.get("selector"),
                "value": value,
                "passed": success or not item.get("required", False),
            }
        )
    return results


def _coalesce_expected(spec: dict[str, Any]):
    assertion_type = str(spec.get("assertion_type") or spec.get("type") or "")
    if spec.get("expected_number") is not None:
        value = spec["expected_number"]
        return int(value) if value == int(value) else value
    if spec.get("expected_text"):
        return spec["expected_text"]
    if assertion_type == "json_path" and "expected_json" in spec and spec.get("expected_json") is not None:
        return spec["expected_json"]
    if spec.get("expected_json") not in ({}, [], None):
        return spec["expected_json"]
    return None


def _value_exists(value: Any) -> bool:
    return value not in (None, "")


def _to_comparable_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:  # noqa: BLE001
        return None


def _compare_values(actual: Any, expected: Any, operator: str) -> bool:
    normalized_operator = str(operator or "equals").strip().lower()
    if normalized_operator == "exists":
        return _value_exists(actual)
    if normalized_operator == "not_exists":
        return not _value_exists(actual)
    if normalized_operator in {"gt", "gte", "lt", "lte"}:
        actual_number = _to_comparable_number(actual)
        expected_number = _to_comparable_number(expected)
        if actual_number is None or expected_number is None:
            return False
        if normalized_operator == "gt":
            return actual_number > expected_number
        if normalized_operator == "gte":
            return actual_number >= expected_number
        if normalized_operator == "lt":
            return actual_number < expected_number
        return actual_number <= expected_number
    if normalized_operator == "contains":
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        if isinstance(actual, dict):
            if isinstance(expected, dict):
                return all(actual.get(key) == value for key, value in expected.items())
            return str(expected) in actual
        return str(expected) in str(actual or "")
    if normalized_operator == "not_contains":
        return not _compare_values(actual, expected, "contains")
    if normalized_operator == "starts_with":
        return str(actual or "").startswith(str(expected))
    if normalized_operator == "ends_with":
        return str(actual or "").endswith(str(expected))
    if normalized_operator == "not_equals":
        return actual != expected
    return actual == expected


def _lazy_validate_json_schema(schema_text: str, payload: Any) -> tuple[bool, str]:
    try:
        import jsonschema  # type: ignore
    except Exception:  # noqa: BLE001
        return False, "jsonschema 依赖未安装"

    try:
        schema = json.loads(schema_text)
    except Exception:  # noqa: BLE001
        return False, "Schema 不是合法 JSON"
    try:
        jsonschema.validate(payload, schema)
        return True, "schema 校验通过"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def evaluate_structured_assertions(
    assertion_specs: list[dict[str, Any]],
    response: httpx.Response,
    response_payload: Any,
    response_time_ms: float | None,
) -> tuple[list[dict[str, Any]], bool]:
    if not assertion_specs:
        return [], response.is_success

    results: list[dict[str, Any]] = []
    all_passed = True
    for index, spec in enumerate(assertion_specs, start=1):
        if not spec.get("enabled", True):
            continue
        assertion_type = str(spec.get("assertion_type") or spec.get("type") or "")
        selector = str(spec.get("selector") or spec.get("path") or "")
        operator = str(spec.get("operator") or "equals")
        expected = _coalesce_expected(spec)
        actual = None
        passed = False
        message = ""

        if assertion_type == "status_code":
            actual = response.status_code
            passed = _compare_values(actual, expected, operator)
            message = f"状态码应为 {expected}"
        elif assertion_type == "status_range":
            actual = response.status_code
            min_value = spec.get("min_value")
            max_value = spec.get("max_value")
            passed = True
            if min_value is not None:
                passed = passed and actual >= min_value
            if max_value is not None:
                passed = passed and actual <= max_value
            message = f"状态码范围 {min_value} - {max_value}"
        elif assertion_type == "body_contains":
            actual = response.text
            passed = _compare_values(actual, expected, "contains")
            message = f"响应体包含 {expected}"
        elif assertion_type == "body_not_contains":
            actual = response.text
            passed = _compare_values(actual, expected, "not_contains")
            message = f"响应体不包含 {expected}"
        elif assertion_type == "json_path":
            actual = extract_json_path(response_payload, selector) if selector and response_payload is not None else None
            passed = _compare_values(actual, expected, operator)
            message = f"JSONPath {selector} {operator} {expected}"
        elif assertion_type == "header":
            actual = response.headers.get(selector)
            passed = _compare_values(actual, expected, operator)
            message = f"响应头 {selector} {operator} {expected}"
        elif assertion_type == "cookie":
            actual = response.cookies.get(selector)
            passed = _compare_values(actual, expected, operator)
            message = f"Cookie {selector} {operator} {expected}"
        elif assertion_type == "regex":
            actual = response.text
            match = re.search(selector, response.text or "")
            matched_text = match.group(1) if match and match.groups() else match.group(0) if match else None
            actual = matched_text
            if operator == "exists" or expected in (None, ""):
                passed = match is not None
            else:
                passed = _compare_values(matched_text, expected, operator)
            message = f"正则 {selector}"
        elif assertion_type == "exists":
            actual = extract_json_path(response_payload, selector) if selector and response_payload is not None else None
            passed = _value_exists(actual)
            message = f"{selector} 应存在"
        elif assertion_type == "not_exists":
            actual = extract_json_path(response_payload, selector) if selector and response_payload is not None else None
            passed = not _value_exists(actual)
            message = f"{selector} 不应存在"
        elif assertion_type == "array_length":
            actual = extract_json_path(response_payload, selector) if selector and response_payload is not None else response_payload
            actual = len(actual) if isinstance(actual, (list, tuple, dict, str)) else None
            expected_number = spec.get("expected_number")
            passed = _compare_values(actual, expected_number, operator)
            message = f"{selector} 长度 {operator} {expected_number}"
        elif assertion_type == "response_time":
            actual = response_time_ms
            expected_number = spec.get("expected_number")
            passed = _compare_values(actual, expected_number, operator)
            message = f"响应时间 {operator} {expected_number}ms"
        elif assertion_type in {"json_schema", "openapi_contract"}:
            actual = response_payload
            passed, message = _lazy_validate_json_schema(str(spec.get("schema_text") or ""), response_payload)
        else:
            actual = None
            passed = False
            message = f"未知断言类型: {assertion_type}"

        results.append(
            {
                "index": index,
                "type": assertion_type,
                "operator": operator,
                "path": selector,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "message": message,
            }
        )
        all_passed = all_passed and passed
    return results, all_passed


def _find_bootstrap_request(api_request: ApiRequest, run_context: ExecutionRunContext, auth_config: dict[str, Any]) -> ApiRequest | None:
    project = api_request.collection.project
    bootstrap_request_id = auth_config.get("bootstrap_request_id") or run_context.variables.get("auth_request_id")
    if bootstrap_request_id:
        return ApiRequest.objects.filter(collection__project=project, id=bootstrap_request_id).first()

    bootstrap_request_name = (
        auth_config.get("bootstrap_request_name")
        or run_context.variables.get("auth_request_name")
        or run_context.variables.get("__auth_request_name")
    )
    if bootstrap_request_name:
        lower_name = str(bootstrap_request_name).strip().lower()
        return (
            ApiRequest.objects.filter(collection__project=project)
            .order_by("id")
            .filter(url__icontains=lower_name)
            .first()
            or ApiRequest.objects.filter(collection__project=project, name__icontains=bootstrap_request_name).order_by("id").first()
        )

    candidates = list(ApiRequest.objects.filter(collection__project=project).order_by("id"))
    for candidate in candidates:
        combined = f"{candidate.name} {candidate.url}".lower()
        if candidate.id == api_request.id:
            continue
        if candidate.method.upper() == "POST" and ("login" in combined or "登录" in candidate.name):
            return candidate
    return None


def _extract_bootstrap_variables(auth_config: dict[str, Any], response_payload: Any) -> dict[str, Any]:
    if not isinstance(response_payload, dict):
        return {}
    token_paths: list[str] = []
    explicit_paths = str(auth_config.get("bootstrap_token_path") or "").strip()
    if explicit_paths:
        token_paths.extend([part.strip() for part in explicit_paths.split(",") if part.strip()])
    token_paths.extend(DEFAULT_TOKEN_PATHS)
    resolved: dict[str, Any] = {}
    for path in token_paths:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["token"] = value
            break
    for path in ["data.refresh_token", "data.refreshToken", "refresh_token", "refreshToken"]:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["refresh_token"] = value
            break
    for path in ["data.uid", "data.userId", "data.user_id", "uid", "userId", "user_id"]:
        value = extract_json_path(response_payload, path)
        if value not in (None, ""):
            resolved["uid"] = value
            break
    return resolved


def _build_auth_headers_and_params(auth_config: dict[str, Any], run_variables: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    headers: dict[str, Any] = {}
    params: dict[str, Any] = {}
    cookies: dict[str, Any] = {}
    auth_type = str(auth_config.get("auth_type") or "none")
    if auth_type == "basic":
        username = str(auth_config.get("username") or "")
        password = str(auth_config.get("password") or "")
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
        headers[str(auth_config.get("header_name") or "Authorization")] = f"Basic {token}"
    elif auth_type in {"bearer", "bootstrap_request"}:
        token_variable = str(auth_config.get("token_variable") or "token")
        token_value = auth_config.get("token_value") or run_variables.get(token_variable)
        if token_value not in (None, ""):
            prefix = str(auth_config.get("bearer_prefix") or "Bearer").strip()
            header_name = str(auth_config.get("header_name") or "Authorization")
            headers[header_name] = f"{prefix} {token_value}".strip()
    elif auth_type == "api_key":
        key_name = str(auth_config.get("api_key_name") or "")
        key_value = auth_config.get("api_key_value") or run_variables.get(str(auth_config.get("token_variable") or "token"))
        location = str(auth_config.get("api_key_in") or "header")
        if key_name and key_value not in (None, ""):
            if location == "query":
                params[key_name] = key_value
            elif location == "cookie":
                cookies[key_name] = key_value
            else:
                headers[key_name] = key_value
    elif auth_type == "cookie":
        cookie_name = str(auth_config.get("cookie_name") or "token")
        token_value = auth_config.get("token_value") or run_variables.get(str(auth_config.get("token_variable") or cookie_name))
        if token_value not in (None, ""):
            cookies[cookie_name] = token_value
    return headers, params, cookies


def _request_payload_for_missing_variable_check(spec: EffectiveRequestSpec) -> list[Any]:
    payloads: list[Any] = [spec.url]
    for bucket in (spec.headers, spec.query, spec.cookies, spec.form_fields, spec.multipart_parts):
        payloads.append({item.get("name"): item.get("value") for item in bucket if item.get("name")})
    if spec.body_mode == "json":
        payloads.append(spec.body_json or {})
    elif spec.body_mode == "raw":
        payloads.append(spec.raw_text)
    elif spec.body_mode == "xml":
        payloads.append(spec.xml_text)
    elif spec.body_mode == "graphql":
        payloads.append(spec.graphql_query)
        payloads.append(spec.graphql_variables or {})
    elif spec.body_mode == "binary":
        payloads.append(spec.binary_base64)
    payloads.append(spec.auth or {})
    return payloads


def _find_missing_request_variables(spec: EffectiveRequestSpec, runtime_variables: dict[str, Any]) -> list[str]:
    return find_missing_variables(runtime_variables, *_request_payload_for_missing_variable_check(spec))


def execute_api_request(
    *,
    api_request: ApiRequest,
    executor,
    environment: ApiEnvironment | None = None,
    test_case: ApiTestCase | None = None,
    run_context: ExecutionRunContext | None = None,
    request_name: str | None = None,
    allow_bootstrap: bool = True,
    request_override: dict[str, Any] | None = None,
    assertion_specs_override: list[dict[str, Any]] | None = None,
    extractor_specs_override: list[dict[str, Any]] | None = None,
) -> ApiExecutionRecord:
    run_context = run_context or ExecutionRunContext(environment=environment)
    if environment and run_context.environment is None:
        run_context.environment = environment

    effective_spec = build_effective_request_spec(
        api_request,
        test_case,
        request_override=request_override,
        assertion_specs_override=assertion_specs_override,
        extractor_specs_override=extractor_specs_override,
    )
    base_url, environment_headers, environment_variables, environment_cookies = _build_environment_defaults(environment)
    data_factory_variables = {"df": build_reference_tree(api_request.collection.project_id)}
    runtime_variables = {
        **environment_variables,
        **data_factory_variables,
        **(run_context.variables or {}),
    }
    resolver = VariableResolver(runtime_variables)
    resolved_headers: dict[str, Any] = {}
    resolved_params: dict[str, Any] = {}
    resolved_cookies: dict[str, Any] = {}
    body_channel = "none"
    resolved_body: Any = None
    transport = effective_spec.transport or {}
    follow_redirects = transport.get("follow_redirects", True)
    stage_results: list[dict[str, Any]] = []
    request_snapshot: dict[str, Any] = {}
    response_snapshot: dict[str, Any] = {}
    assertions_results: list[dict[str, Any]] = []
    execute_status = "error"
    error_message = ""
    status_code = None
    response_time_ms = None
    passed = False
    auth_bootstrap_error = ""

    def refresh_resolved_request_state():
        nonlocal resolver, resolved_headers, resolved_params, resolved_cookies, body_channel, resolved_body, resolved_url
        resolver = VariableResolver(runtime_variables)
        resolved_url = build_request_url(base_url, str(resolver.resolve(effective_spec.url)))
        resolved_headers = {
            **resolver.resolve(environment_headers or {}),
            **_items_to_dict(_resolve_items(effective_spec.headers, resolver)),
        }
        resolved_params = _items_to_dict(_resolve_items(effective_spec.query, resolver))
        resolved_cookies = {
            item["name"]: resolver.resolve(item.get("value", ""))
            for item in environment_cookies + _resolve_items(effective_spec.cookies, resolver)
            if item.get("name")
        }
        body_channel, resolved_body = _resolve_body(effective_spec, resolver)

    def stage(name: str, stage_type: str):
        started_at = time.perf_counter()

        def finish(status: str, detail: str = ""):
            ended_at = time.perf_counter()
            stage_results.append(StageResult(name, stage_type, status, started_at, ended_at, detail).to_dict())

        return finish

    finish_prepare = stage("prepare", "prepare")
    resolved_url = ""
    refresh_resolved_request_state()
    effective_auth = dict(effective_spec.auth or {})
    pre_auth_missing_variables = _find_missing_request_variables(effective_spec, runtime_variables)
    inferred_bootstrap_auth = False
    if (
        allow_bootstrap
        and str(effective_auth.get("auth_type") or "none") in {"", "none"}
        and any(name in TOKEN_VARIABLE_NAMES for name in pre_auth_missing_variables)
    ):
        effective_auth["auth_type"] = "bootstrap_request"
        effective_auth["token_variable"] = str(
            effective_auth.get("token_variable")
            or next((name for name in pre_auth_missing_variables if name in TOKEN_VARIABLE_NAMES), "token")
        )
        inferred_bootstrap_auth = True
    if inferred_bootstrap_auth:
        auth_headers, auth_params, auth_cookies = {}, {}, {}
    else:
        auth_headers, auth_params, auth_cookies = _build_auth_headers_and_params(effective_auth, runtime_variables)
    finish_prepare("success", "已完成变量解析")

    finish_auth = stage("auth", "auth")
    auth_type = str(effective_auth.get("auth_type") or "none")
    token_variable = str(effective_auth.get("token_variable") or "token")
    token_missing = auth_type in {"bearer", "bootstrap_request"} and not (
        effective_auth.get("token_value") or runtime_variables.get(token_variable)
    )
    if allow_bootstrap and (auth_type == "bootstrap_request" or token_missing):
        bootstrap_request = _find_bootstrap_request(api_request, run_context, effective_auth)
        if bootstrap_request:
            bootstrap_record = execute_api_request(
                api_request=bootstrap_request,
                executor=executor,
                environment=environment,
                run_context=run_context,
                request_name=f"[Auth Bootstrap] {bootstrap_request.name}",
                allow_bootstrap=False,
            )
            bootstrap_payload = (bootstrap_record.response_snapshot or {}).get("body")
            bootstrap_variables = _extract_bootstrap_variables(effective_auth, bootstrap_payload)
            if bootstrap_record.status == "error" and not bootstrap_variables:
                auth_bootstrap_error = bootstrap_record.error_message or "认证引导失败"
                if "自动获取 token 失败" not in auth_bootstrap_error:
                    auth_bootstrap_error = f"自动获取 token 失败，{auth_bootstrap_error}"
                finish_auth("error", auth_bootstrap_error)
            else:
                runtime_variables.update(bootstrap_variables)
                run_context.variables.update(bootstrap_variables)
                if environment and bootstrap_variables:
                    updated_variables = dict(environment.variables or {})
                    updated_variables.update({key: str(value) for key, value in bootstrap_variables.items()})
                    environment.variables = updated_variables
                    environment.save(update_fields=["variables", "updated_at"])
                refresh_resolved_request_state()
                if inferred_bootstrap_auth:
                    auth_headers, auth_params, auth_cookies = {}, {}, {}
                else:
                    auth_headers, auth_params, auth_cookies = _build_auth_headers_and_params(
                        effective_auth,
                        runtime_variables,
                    )
                finish_auth("success", "已完成认证引导")
        else:
            finish_auth("skipped", "未找到可用认证引导请求")
    else:
        finish_auth("success", "使用静态认证或无需认证")

    resolved_headers.update(auth_headers)
    resolved_params.update(auth_params)
    resolved_cookies.update(auth_cookies)

    request_snapshot = {
        "request_id": api_request.id,
        "interface_name": api_request.name,
        "collection_id": api_request.collection_id,
        "collection_name": api_request.collection.name,
        "method": effective_spec.method,
        "url": resolved_url,
        "headers": resolved_headers,
        "params": resolved_params,
        "cookies": resolved_cookies,
        "body_mode": effective_spec.body_mode,
        "body": resolved_body,
        "request_spec": serialize_request_spec(api_request),
        "request_override_spec": request_override if request_override is not None else (serialize_test_case_override(test_case) if test_case else None),
        "assertion_specs": effective_spec.assertions,
        "extractor_specs": effective_spec.extractors,
        "execution_mode": run_context._normalize_execution_mode(),
        "generated_script": build_request_script(api_request=api_request),
    }
    missing_request_variables = _find_missing_request_variables(effective_spec, runtime_variables)
    request_snapshot["missing_variables"] = missing_request_variables
    if test_case:
        request_snapshot["test_case_id"] = test_case.id
        request_snapshot["test_case_name"] = test_case.name

    finish_request = stage("execute", "request")
    if missing_request_variables:
        token_related_missing = [name for name in missing_request_variables if name in TOKEN_VARIABLE_NAMES]
        if auth_bootstrap_error:
            error_message = auth_bootstrap_error
        elif token_related_missing:
            error_message = f"自动获取 token 失败，仍缺少变量: {', '.join(missing_request_variables)}"
        else:
            error_message = f"存在未解析的环境变量: {', '.join(missing_request_variables)}"
        finish_request("error", error_message)
        execute_status = "error"
        passed = False
    else:
        try:
            request_kwargs: dict[str, Any] = {
                "method": effective_spec.method,
                "url": resolved_url,
                "headers": resolved_headers,
                "params": resolved_params,
                "cookies": resolved_cookies,
                "timeout": max(float(effective_spec.timeout_ms) / 1000, 1),
                "follow_redirects": follow_redirects,
            }
            exit_stack = ExitStack()
            if body_channel == "json":
                request_kwargs["json"] = resolved_body
            elif body_channel == "data":
                request_kwargs["data"] = resolved_body
            elif body_channel == "multipart":
                request_kwargs["data"] = resolved_body
                files_payload = []
                for file_item in effective_spec.files:
                    if not file_item.get("enabled", True):
                        continue
                    field_name = str(file_item.get("field_name") or "").strip()
                    if not field_name:
                        continue
                    source_type = str(file_item.get("source_type") or "path")
                    file_name = str(file_item.get("file_name") or field_name)
                    content_type = str(file_item.get("content_type") or "application/octet-stream")
                    if source_type == "base64":
                        file_bytes = base64.b64decode(str(file_item.get("base64_content") or ""))
                        files_payload.append((field_name, (file_name, file_bytes, content_type)))
                    else:
                        file_path = resolver.resolve(file_item.get("file_path") or "")
                        file_handle = exit_stack.enter_context(open(file_path, "rb"))
                        files_payload.append((field_name, (file_name or file_handle.name, file_handle, content_type)))
                request_kwargs["files"] = files_payload
            elif body_channel == "content":
                request_kwargs["content"] = resolved_body

            started_at = time.perf_counter()
            response = None
            retries = max(int(transport.get("retry_count") or 0), 0)
            retry_interval = max(int(transport.get("retry_interval_ms") or 500), 0) / 1000
            try:
                response = run_context.request(
                    transport=transport,
                    request_kwargs=request_kwargs,
                    retries=retries,
                    retry_interval=retry_interval,
                )
            finally:
                exit_stack.close()

            response_time_ms = round((time.perf_counter() - started_at) * 1000, 2)
            status_code = response.status_code
            finish_request("success", f"HTTP {status_code}")

            try:
                response_payload = response.json()
            except ValueError:
                response_payload = response.text

            finish_extract = stage("extract", "extractors")
            extractor_results = _apply_extractors(
                effective_spec.extractors,
                response,
                response_payload if isinstance(response_payload, (dict, list)) else None,
                response_time_ms,
                run_context.variables,
            )
            finish_extract("success", f"提取 {len(extractor_results)} 个变量")

            finish_assert = stage("assert", "assertions")
            assertions_results, passed = evaluate_structured_assertions(
                effective_spec.assertions,
                response,
                response_payload if isinstance(response_payload, (dict, list)) else None,
                response_time_ms,
            )
            finish_assert("success", f"断言 {len(assertions_results)} 条")
            execute_status = "success" if passed else "failed"

            response_snapshot = {
                "headers": dict(response.headers),
                "cookies": dict(response.cookies),
                "body": response_payload,
                "extractor_results": extractor_results,
            }
            if not passed and isinstance(response_payload, dict):
                for key in ("message", "detail", "error", "msg"):
                    if response_payload.get(key) not in (None, ""):
                        error_message = str(response_payload.get(key))
                        break
        except Exception as exc:  # noqa: BLE001
            finish_request("error", str(exc))
            error_message = str(exc)
            execute_status = "error"
            passed = False

    finish_teardown = stage("teardown", "teardown")
    finish_teardown("success", "执行结束")
    request_snapshot["stage_results"] = stage_results

    if test_case:
        generated_script = build_parameterized_test_case_script(
            request_id=test_case.request_id,
            method=effective_spec.method,
            url=effective_spec.url,
            headers={item["name"]: item.get("value", "") for item in effective_spec.headers if item.get("enabled", True)},
            params={item["name"]: item.get("value", "") for item in effective_spec.query if item.get("enabled", True)},
            body_type=effective_spec.body_mode,
            body=resolved_body,
            timeout_ms=effective_spec.timeout_ms,
            assertions=effective_spec.assertions,
            extractors=effective_spec.extractors,
            request_override_spec=serialize_test_case_override(test_case),
        )
        request_snapshot["generated_script"] = generated_script

    record = ApiExecutionRecord.objects.create(
        project=api_request.collection.project,
        request=api_request,
        test_case=test_case,
        environment=environment,
        run_id=run_context.run_id or "",
        run_name=run_context.run_name or "",
        request_name=request_name or (test_case.name if test_case else api_request.name),
        method=effective_spec.method,
        url=resolved_url,
        status=execute_status,
        passed=passed,
        status_code=status_code,
        response_time=response_time_ms,
        request_snapshot=request_snapshot,
        response_snapshot=response_snapshot,
        assertions_results=assertions_results,
        error_message=error_message,
        executor=executor,
    )
    return record
