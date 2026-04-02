from __future__ import annotations

import json
from typing import Any

from django.db import transaction

from .models import (
    ApiAssertionSpec,
    ApiEnvironment,
    ApiEnvironmentCookieSpec,
    ApiEnvironmentHeaderSpec,
    ApiEnvironmentVariableSpec,
    ApiExtractorSpec,
    ApiRequest,
    ApiRequestAuthSpec,
    ApiRequestFieldSpec,
    ApiRequestFileSpec,
    ApiRequestSpec,
    ApiRequestTransportSpec,
    ApiTestCase,
    ApiTestCaseAuthSpec,
    ApiTestCaseFieldSpec,
    ApiTestCaseFileSpec,
    ApiTestCaseOverrideSpec,
    ApiTestCaseTransportSpec,
)


FIELD_BUCKET_MAP = {
    "header": "headers",
    "query": "query",
    "cookie": "cookies",
    "form": "form_fields",
    "multipart_text": "multipart_parts",
}

BODY_MODE_TO_LEGACY = {
    "none": "none",
    "json": "json",
    "form": "form",
    "urlencoded": "form",
    "multipart": "form",
    "raw": "raw",
    "xml": "raw",
    "graphql": "json",
    "binary": "raw",
}

LEGACY_TO_BODY_MODE = {
    "none": "none",
    "json": "json",
    "form": "form",
    "raw": "raw",
}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _to_field_items(data: dict[str, Any], field_kind: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, (name, value) in enumerate((data or {}).items()):
        items.append(
            {
                "name": str(name),
                "value": _to_text(value),
                "enabled": True,
                "order": index,
                "field_kind": field_kind,
            }
        )
    return items


def _group_items(items: list[Any]) -> dict[str, list[dict[str, Any]]]:
    grouped = {bucket: [] for bucket in FIELD_BUCKET_MAP.values()}
    for item in items:
        field_kind = getattr(item, "field_kind", None)
        if field_kind is None and isinstance(item, dict):
            field_kind = item.get("field_kind")
        bucket = FIELD_BUCKET_MAP.get(field_kind or "")
        if not bucket:
            continue
        grouped[bucket].append(
            {
                "id": getattr(item, "id", item.get("id") if isinstance(item, dict) else None),
                "name": getattr(item, "name", item.get("name", "") if isinstance(item, dict) else ""),
                "value": getattr(item, "value", item.get("value", "") if isinstance(item, dict) else ""),
                "enabled": getattr(item, "enabled", item.get("enabled", True) if isinstance(item, dict) else True),
                "order": getattr(item, "order", item.get("order", 0) if isinstance(item, dict) else 0),
            }
        )
    for bucket in grouped.values():
        bucket.sort(key=lambda entry: (entry.get("order", 0), entry.get("id") or 0))
    return grouped


def _serialize_files(items: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "field_name": item.field_name,
            "source_type": item.source_type,
            "file_path": item.file_path,
            "file_name": item.file_name,
            "content_type": item.content_type,
            "base64_content": item.base64_content,
            "enabled": item.enabled,
            "order": item.order,
        }
        for item in items
    ]


def _serialize_auth(spec) -> dict[str, Any]:
    if not spec:
        return {
            "auth_type": "none",
            "username": "",
            "password": "",
            "token_value": "",
            "token_variable": "token",
            "header_name": "Authorization",
            "bearer_prefix": "Bearer",
            "api_key_name": "",
            "api_key_in": "header",
            "api_key_value": "",
            "cookie_name": "",
            "bootstrap_request_id": None,
            "bootstrap_request_name": "",
            "bootstrap_token_path": "",
        }
    return {
        "auth_type": spec.auth_type or "none",
        "username": spec.username,
        "password": spec.password,
        "token_value": spec.token_value,
        "token_variable": spec.token_variable or "token",
        "header_name": spec.header_name or "Authorization",
        "bearer_prefix": spec.bearer_prefix or "Bearer",
        "api_key_name": spec.api_key_name,
        "api_key_in": spec.api_key_in or "header",
        "api_key_value": spec.api_key_value,
        "cookie_name": spec.cookie_name,
        "bootstrap_request_id": spec.bootstrap_request_id,
        "bootstrap_request_name": spec.bootstrap_request_name,
        "bootstrap_token_path": spec.bootstrap_token_path,
    }


def _serialize_blank_override_auth() -> dict[str, Any]:
    return {
        "auth_type": "",
        "username": "",
        "password": "",
        "token_value": "",
        "token_variable": "",
        "header_name": "",
        "bearer_prefix": "",
        "api_key_name": "",
        "api_key_in": "",
        "api_key_value": "",
        "cookie_name": "",
        "bootstrap_request_id": None,
        "bootstrap_request_name": "",
        "bootstrap_token_path": "",
    }


def _serialize_transport(spec) -> dict[str, Any]:
    if not spec:
        return {
            "verify_ssl": True,
            "proxy_url": "",
            "client_cert": "",
            "client_key": "",
            "follow_redirects": True,
            "retry_count": 0,
            "retry_interval_ms": 500,
        }
    return {
        "verify_ssl": spec.verify_ssl,
        "proxy_url": spec.proxy_url,
        "client_cert": spec.client_cert,
        "client_key": spec.client_key,
        "follow_redirects": spec.follow_redirects,
        "retry_count": spec.retry_count,
        "retry_interval_ms": spec.retry_interval_ms,
    }


def _serialize_blank_override_transport() -> dict[str, Any]:
    return {
        "verify_ssl": None,
        "proxy_url": "",
        "client_cert": "",
        "client_key": "",
        "follow_redirects": None,
        "retry_count": None,
        "retry_interval_ms": None,
    }


def legacy_assertions_to_specs(assertions: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(assertions or []):
        if not isinstance(item, dict):
            continue
        assertion_type = str(item.get("type") or "").strip()
        if not assertion_type:
            continue
        expected = item.get("expected")
        payload = {
            "enabled": True,
            "order": index,
            "assertion_type": assertion_type,
            "target": "body",
            "selector": str(item.get("path") or item.get("selector") or ""),
            "operator": str(item.get("operator") or "equals"),
            "expected_text": expected if isinstance(expected, str) else "",
            "expected_number": float(expected) if isinstance(expected, (int, float)) else None,
            "expected_json": expected if isinstance(expected, (dict, list, bool)) else {},
            "min_value": None,
            "max_value": None,
            "schema_text": "",
        }
        if assertion_type == "header":
            payload["target"] = "header"
        elif assertion_type == "cookie":
            payload["target"] = "cookie"
        elif assertion_type == "json_path":
            payload["target"] = "json"
        result.append(payload)
    return result


def serialize_assertion_specs(owner) -> list[dict[str, Any]]:
    related = list(owner.assertion_specs.all()) if hasattr(owner, "assertion_specs") else []
    if not related:
        legacy = getattr(owner, "assertions", None)
        return legacy_assertions_to_specs(legacy if isinstance(legacy, list) else [])
    return [
        {
            "id": spec.id,
            "enabled": spec.enabled,
            "order": spec.order,
            "assertion_type": spec.assertion_type,
            "target": spec.target,
            "selector": spec.selector,
            "operator": spec.operator,
            "expected_text": spec.expected_text,
            "expected_number": spec.expected_number,
            "expected_json": spec.expected_json,
            "min_value": spec.min_value,
            "max_value": spec.max_value,
            "schema_text": spec.schema_text,
        }
        for spec in related
    ]


def serialize_extractor_specs(owner) -> list[dict[str, Any]]:
    related = list(owner.extractor_specs.all()) if hasattr(owner, "extractor_specs") else []
    return [
        {
            "id": spec.id,
            "enabled": spec.enabled,
            "order": spec.order,
            "source": spec.source,
            "selector": spec.selector,
            "variable_name": spec.variable_name,
            "default_value": spec.default_value,
            "required": spec.required,
        }
        for spec in related
    ]


def assertion_specs_to_legacy(owner) -> list[dict[str, Any]]:
    legacy: list[dict[str, Any]] = []
    for spec in serialize_assertion_specs(owner):
        item = {
            "type": spec["assertion_type"],
            "operator": spec.get("operator") or "equals",
        }
        if spec.get("selector"):
            item["path"] = spec["selector"]
        if spec.get("expected_number") is not None:
            expected: Any = spec["expected_number"]
            if expected == int(expected):
                expected = int(expected)
            item["expected"] = expected
        elif spec.get("expected_text"):
            item["expected"] = spec["expected_text"]
        elif spec.get("expected_json") not in ({}, [], None):
            item["expected"] = spec["expected_json"]
        if spec["assertion_type"] == "status_range":
            item["min"] = spec.get("min_value")
            item["max"] = spec.get("max_value")
        legacy.append(item)
    return legacy


def _legacy_request_spec_payload(api_request: ApiRequest) -> dict[str, Any]:
    body_mode = LEGACY_TO_BODY_MODE.get(api_request.body_type or "none", "raw")
    return {
        "method": api_request.method,
        "url": api_request.url,
        "body_mode": body_mode,
        "body_json": api_request.body if body_mode == "json" and isinstance(api_request.body, (dict, list)) else {},
        "raw_text": api_request.body if body_mode == "raw" and isinstance(api_request.body, str) else "",
        "xml_text": "",
        "binary_base64": "",
        "graphql_query": "",
        "graphql_operation_name": "",
        "graphql_variables": {},
        "timeout_ms": api_request.timeout_ms,
        "headers": _to_field_items(api_request.headers or {}, "header"),
        "query": _to_field_items(api_request.params or {}, "query"),
        "cookies": [],
        "form_fields": _to_field_items(api_request.body or {}, "form") if body_mode == "form" and isinstance(api_request.body, dict) else [],
        "multipart_parts": [],
        "files": [],
        "auth": _serialize_auth(None),
        "transport": _serialize_transport(None),
    }


def serialize_request_spec(api_request: ApiRequest) -> dict[str, Any]:
    request_spec = getattr(api_request, "request_spec", None)
    if not request_spec:
        return _legacy_request_spec_payload(api_request)

    grouped = _group_items(list(request_spec.field_specs.all()))
    return {
        "id": request_spec.id,
        "method": request_spec.method,
        "url": request_spec.url,
        "body_mode": request_spec.body_mode,
        "body_json": request_spec.body_json,
        "raw_text": request_spec.raw_text,
        "xml_text": request_spec.xml_text,
        "binary_base64": request_spec.binary_base64,
        "graphql_query": request_spec.graphql_query,
        "graphql_operation_name": request_spec.graphql_operation_name,
        "graphql_variables": request_spec.graphql_variables,
        "timeout_ms": request_spec.timeout_ms,
        "headers": grouped["headers"],
        "query": grouped["query"],
        "cookies": grouped["cookies"],
        "form_fields": grouped["form_fields"],
        "multipart_parts": grouped["multipart_parts"],
        "files": _serialize_files(list(request_spec.file_specs.all())),
        "auth": _serialize_auth(getattr(request_spec, "auth_spec", None)),
        "transport": _serialize_transport(getattr(request_spec, "transport_spec", None)),
    }


def _legacy_test_case_override_payload(test_case: ApiTestCase) -> dict[str, Any]:
    script = test_case.script or {}
    overrides = script.get("request_overrides") if isinstance(script, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}
    body_mode = LEGACY_TO_BODY_MODE.get(str(overrides.get("body_type") or ""), "")
    body = overrides.get("body")
    return {
        "method": str(overrides.get("method") or ""),
        "url": str(overrides.get("url") or ""),
        "body_mode": body_mode,
        "body_json": body if body_mode == "json" and isinstance(body, (dict, list)) else {},
        "raw_text": body if body_mode == "raw" and isinstance(body, str) else "",
        "xml_text": "",
        "binary_base64": "",
        "graphql_query": "",
        "graphql_operation_name": "",
        "graphql_variables": {},
        "timeout_ms": overrides.get("timeout_ms"),
        "headers": _to_field_items(overrides.get("headers") or {}, "header"),
        "query": _to_field_items(overrides.get("params") or {}, "query"),
        "cookies": [],
        "form_fields": _to_field_items(body or {}, "form") if body_mode == "form" and isinstance(body, dict) else [],
        "multipart_parts": [],
        "files": [],
        "auth": _serialize_blank_override_auth(),
        "transport": _serialize_blank_override_transport(),
    }


def serialize_test_case_override(test_case: ApiTestCase) -> dict[str, Any]:
    override_spec = getattr(test_case, "override_spec", None)
    if not override_spec:
        return _legacy_test_case_override_payload(test_case)

    grouped = _group_items(list(override_spec.field_specs.all()))
    return {
        "id": override_spec.id,
        "method": override_spec.method,
        "url": override_spec.url,
        "body_mode": override_spec.body_mode,
        "body_json": override_spec.body_json,
        "raw_text": override_spec.raw_text,
        "xml_text": override_spec.xml_text,
        "binary_base64": override_spec.binary_base64,
        "graphql_query": override_spec.graphql_query,
        "graphql_operation_name": override_spec.graphql_operation_name,
        "graphql_variables": override_spec.graphql_variables,
        "timeout_ms": override_spec.timeout_ms,
        "headers": grouped["headers"],
        "query": grouped["query"],
        "cookies": grouped["cookies"],
        "form_fields": grouped["form_fields"],
        "multipart_parts": grouped["multipart_parts"],
        "files": _serialize_files(list(override_spec.file_specs.all())),
        "auth": (
            {
                "auth_type": override_spec.auth_spec.auth_type,
                "username": override_spec.auth_spec.username,
                "password": override_spec.auth_spec.password,
                "token_value": override_spec.auth_spec.token_value,
                "token_variable": override_spec.auth_spec.token_variable,
                "header_name": override_spec.auth_spec.header_name,
                "bearer_prefix": override_spec.auth_spec.bearer_prefix,
                "api_key_name": override_spec.auth_spec.api_key_name,
                "api_key_in": override_spec.auth_spec.api_key_in,
                "api_key_value": override_spec.auth_spec.api_key_value,
                "cookie_name": override_spec.auth_spec.cookie_name,
                "bootstrap_request_id": override_spec.auth_spec.bootstrap_request_id,
                "bootstrap_request_name": override_spec.auth_spec.bootstrap_request_name,
                "bootstrap_token_path": override_spec.auth_spec.bootstrap_token_path,
            }
            if hasattr(override_spec, "auth_spec")
            else _serialize_blank_override_auth()
        ),
        "transport": (
            {
                "verify_ssl": override_spec.transport_spec.verify_ssl,
                "proxy_url": override_spec.transport_spec.proxy_url,
                "client_cert": override_spec.transport_spec.client_cert,
                "client_key": override_spec.transport_spec.client_key,
                "follow_redirects": override_spec.transport_spec.follow_redirects,
                "retry_count": override_spec.transport_spec.retry_count,
                "retry_interval_ms": override_spec.transport_spec.retry_interval_ms,
            }
            if hasattr(override_spec, "transport_spec")
            else _serialize_blank_override_transport()
        ),
    }


def serialize_environment_specs(environment: ApiEnvironment) -> dict[str, Any]:
    variable_specs = list(environment.variable_specs.all())
    if not variable_specs and environment.variables:
        variable_items = [
            {
                "name": key,
                "value": _to_text(value),
                "enabled": True,
                "is_secret": False,
                "order": index,
            }
            for index, (key, value) in enumerate((environment.variables or {}).items())
        ]
    else:
        variable_items = [
            {
                "id": item.id,
                "name": item.name,
                "value": item.value,
                "enabled": item.enabled,
                "is_secret": item.is_secret,
                "order": item.order,
            }
            for item in variable_specs
        ]

    header_specs = list(environment.header_specs.all())
    if not header_specs and environment.common_headers:
        header_items = [
            {
                "name": key,
                "value": _to_text(value),
                "enabled": True,
                "order": index,
            }
            for index, (key, value) in enumerate((environment.common_headers or {}).items())
        ]
    else:
        header_items = [
            {
                "id": item.id,
                "name": item.name,
                "value": item.value,
                "enabled": item.enabled,
                "order": item.order,
            }
            for item in header_specs
        ]

    return {
        "variables": variable_items,
        "headers": header_items,
        "cookies": [
            {
                "id": item.id,
                "name": item.name,
                "value": item.value,
                "domain": item.domain,
                "path": item.path,
                "enabled": item.enabled,
                "order": item.order,
            }
            for item in environment.cookie_specs.all()
        ],
    }


def _replace_request_field_specs(request_spec: ApiRequestSpec, payload: dict[str, Any]):
    request_spec.field_specs.all().delete()
    items: list[ApiRequestFieldSpec] = []
    for field_kind, bucket in FIELD_BUCKET_MAP.items():
        for index, item in enumerate(payload.get(bucket, []) or []):
            if not isinstance(item, dict):
                continue
            items.append(
                ApiRequestFieldSpec(
                    request_spec=request_spec,
                    field_kind=field_kind,
                    name=str(item.get("name") or "").strip(),
                    value=_to_text(item.get("value")),
                    enabled=bool(item.get("enabled", True)),
                    order=int(item.get("order", index)),
                )
            )
    ApiRequestFieldSpec.objects.bulk_create([item for item in items if item.name])


def _replace_test_case_field_specs(override_spec: ApiTestCaseOverrideSpec, payload: dict[str, Any]):
    override_spec.field_specs.all().delete()
    items: list[ApiTestCaseFieldSpec] = []
    for field_kind, bucket in FIELD_BUCKET_MAP.items():
        for index, item in enumerate(payload.get(bucket, []) or []):
            if not isinstance(item, dict):
                continue
            items.append(
                ApiTestCaseFieldSpec(
                    override_spec=override_spec,
                    field_kind=field_kind,
                    name=str(item.get("name") or "").strip(),
                    value=_to_text(item.get("value")),
                    enabled=bool(item.get("enabled", True)),
                    order=int(item.get("order", index)),
                )
            )
    ApiTestCaseFieldSpec.objects.bulk_create([item for item in items if item.name])


def _replace_request_file_specs(request_spec: ApiRequestSpec, payload: dict[str, Any]):
    request_spec.file_specs.all().delete()
    items: list[ApiRequestFileSpec] = []
    for index, item in enumerate(payload.get("files", []) or []):
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        items.append(
            ApiRequestFileSpec(
                request_spec=request_spec,
                field_name=field_name,
                source_type=str(item.get("source_type") or "path"),
                file_path=str(item.get("file_path") or ""),
                file_name=str(item.get("file_name") or ""),
                content_type=str(item.get("content_type") or ""),
                base64_content=str(item.get("base64_content") or ""),
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
            )
        )
    ApiRequestFileSpec.objects.bulk_create(items)


def _replace_test_case_file_specs(override_spec: ApiTestCaseOverrideSpec, payload: dict[str, Any]):
    override_spec.file_specs.all().delete()
    items: list[ApiTestCaseFileSpec] = []
    for index, item in enumerate(payload.get("files", []) or []):
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        items.append(
            ApiTestCaseFileSpec(
                override_spec=override_spec,
                field_name=field_name,
                source_type=str(item.get("source_type") or "path"),
                file_path=str(item.get("file_path") or ""),
                file_name=str(item.get("file_name") or ""),
                content_type=str(item.get("content_type") or ""),
                base64_content=str(item.get("base64_content") or ""),
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
            )
        )
    ApiTestCaseFileSpec.objects.bulk_create(items)


def _upsert_request_auth_spec(request_spec: ApiRequestSpec, payload: dict[str, Any] | None):
    payload = payload or {}
    auth_spec, _ = ApiRequestAuthSpec.objects.get_or_create(request_spec=request_spec)
    auth_spec.auth_type = str(payload.get("auth_type") or "none")
    auth_spec.username = str(payload.get("username") or "")
    auth_spec.password = str(payload.get("password") or "")
    auth_spec.token_value = str(payload.get("token_value") or "")
    auth_spec.token_variable = str(payload.get("token_variable") or "token")
    auth_spec.header_name = str(payload.get("header_name") or "Authorization")
    auth_spec.bearer_prefix = str(payload.get("bearer_prefix") or "Bearer")
    auth_spec.api_key_name = str(payload.get("api_key_name") or "")
    auth_spec.api_key_in = str(payload.get("api_key_in") or "header")
    auth_spec.api_key_value = str(payload.get("api_key_value") or "")
    auth_spec.cookie_name = str(payload.get("cookie_name") or "")
    auth_spec.bootstrap_request_id = payload.get("bootstrap_request_id")
    auth_spec.bootstrap_request_name = str(payload.get("bootstrap_request_name") or "")
    auth_spec.bootstrap_token_path = str(payload.get("bootstrap_token_path") or "")
    auth_spec.save()


def _upsert_test_case_auth_spec(override_spec: ApiTestCaseOverrideSpec, payload: dict[str, Any] | None):
    payload = payload or {}
    meaningful_keys = [
        "auth_type",
        "username",
        "password",
        "token_value",
        "token_variable",
        "header_name",
        "bearer_prefix",
        "api_key_name",
        "api_key_in",
        "api_key_value",
        "cookie_name",
        "bootstrap_request_id",
        "bootstrap_request_name",
        "bootstrap_token_path",
    ]
    if not any(payload.get(key) not in (None, "") for key in meaningful_keys):
        ApiTestCaseAuthSpec.objects.filter(override_spec=override_spec).delete()
        return
    auth_spec, _ = ApiTestCaseAuthSpec.objects.get_or_create(override_spec=override_spec)
    auth_spec.auth_type = str(payload.get("auth_type") or "")
    auth_spec.username = str(payload.get("username") or "")
    auth_spec.password = str(payload.get("password") or "")
    auth_spec.token_value = str(payload.get("token_value") or "")
    auth_spec.token_variable = str(payload.get("token_variable") or "")
    auth_spec.header_name = str(payload.get("header_name") or "")
    auth_spec.bearer_prefix = str(payload.get("bearer_prefix") or "")
    auth_spec.api_key_name = str(payload.get("api_key_name") or "")
    auth_spec.api_key_in = str(payload.get("api_key_in") or "header")
    auth_spec.api_key_value = str(payload.get("api_key_value") or "")
    auth_spec.cookie_name = str(payload.get("cookie_name") or "")
    auth_spec.bootstrap_request_id = payload.get("bootstrap_request_id")
    auth_spec.bootstrap_request_name = str(payload.get("bootstrap_request_name") or "")
    auth_spec.bootstrap_token_path = str(payload.get("bootstrap_token_path") or "")
    auth_spec.save()


def _upsert_request_transport_spec(request_spec: ApiRequestSpec, payload: dict[str, Any] | None):
    payload = payload or {}
    transport_spec, _ = ApiRequestTransportSpec.objects.get_or_create(request_spec=request_spec)
    transport_spec.verify_ssl = bool(payload.get("verify_ssl", True))
    transport_spec.proxy_url = str(payload.get("proxy_url") or "")
    transport_spec.client_cert = str(payload.get("client_cert") or "")
    transport_spec.client_key = str(payload.get("client_key") or "")
    transport_spec.follow_redirects = bool(payload.get("follow_redirects", True))
    transport_spec.retry_count = int(payload.get("retry_count") or 0)
    transport_spec.retry_interval_ms = int(payload.get("retry_interval_ms") or 500)
    transport_spec.save()


def _upsert_test_case_transport_spec(override_spec: ApiTestCaseOverrideSpec, payload: dict[str, Any] | None):
    payload = payload or {}
    meaningful_keys = [
        "verify_ssl",
        "proxy_url",
        "client_cert",
        "client_key",
        "follow_redirects",
        "retry_count",
        "retry_interval_ms",
    ]
    if not any(payload.get(key) not in (None, "") for key in meaningful_keys):
        ApiTestCaseTransportSpec.objects.filter(override_spec=override_spec).delete()
        return
    transport_spec, _ = ApiTestCaseTransportSpec.objects.get_or_create(override_spec=override_spec)
    transport_spec.verify_ssl = payload.get("verify_ssl")
    transport_spec.proxy_url = str(payload.get("proxy_url") or "")
    transport_spec.client_cert = str(payload.get("client_cert") or "")
    transport_spec.client_key = str(payload.get("client_key") or "")
    transport_spec.follow_redirects = payload.get("follow_redirects")
    transport_spec.retry_count = int(payload["retry_count"]) if payload.get("retry_count") not in (None, "") else None
    transport_spec.retry_interval_ms = (
        int(payload["retry_interval_ms"]) if payload.get("retry_interval_ms") not in (None, "") else None
    )
    transport_spec.save()


@transaction.atomic
def apply_request_spec_payload(api_request: ApiRequest, payload: dict[str, Any] | None):
    payload = payload or _legacy_request_spec_payload(api_request)
    request_spec, _ = ApiRequestSpec.objects.get_or_create(request=api_request)
    request_spec.method = str(payload.get("method") or api_request.method or "GET").upper()
    request_spec.url = str(payload.get("url") or api_request.url or "")
    request_spec.body_mode = str(payload.get("body_mode") or "none").lower()
    request_spec.body_json = payload.get("body_json") if isinstance(payload.get("body_json"), (dict, list)) else {}
    request_spec.raw_text = str(payload.get("raw_text") or "")
    request_spec.xml_text = str(payload.get("xml_text") or "")
    request_spec.binary_base64 = str(payload.get("binary_base64") or "")
    request_spec.graphql_query = str(payload.get("graphql_query") or "")
    request_spec.graphql_operation_name = str(payload.get("graphql_operation_name") or "")
    request_spec.graphql_variables = (
        payload.get("graphql_variables") if isinstance(payload.get("graphql_variables"), dict) else {}
    )
    request_spec.timeout_ms = int(payload.get("timeout_ms") or api_request.timeout_ms or 30000)
    request_spec.save()
    _replace_request_field_specs(request_spec, payload)
    _replace_request_file_specs(request_spec, payload)
    _upsert_request_auth_spec(request_spec, payload.get("auth"))
    _upsert_request_transport_spec(request_spec, payload.get("transport"))
    sync_legacy_request_from_specs(api_request)
    return request_spec


@transaction.atomic
def apply_test_case_override_payload(test_case: ApiTestCase, payload: dict[str, Any] | None):
    payload = payload or _legacy_test_case_override_payload(test_case)
    override_spec, _ = ApiTestCaseOverrideSpec.objects.get_or_create(test_case=test_case)
    override_spec.method = str(payload.get("method") or "")
    override_spec.url = str(payload.get("url") or "")
    override_spec.body_mode = str(payload.get("body_mode") or "")
    override_spec.body_json = payload.get("body_json") if isinstance(payload.get("body_json"), (dict, list)) else {}
    override_spec.raw_text = str(payload.get("raw_text") or "")
    override_spec.xml_text = str(payload.get("xml_text") or "")
    override_spec.binary_base64 = str(payload.get("binary_base64") or "")
    override_spec.graphql_query = str(payload.get("graphql_query") or "")
    override_spec.graphql_operation_name = str(payload.get("graphql_operation_name") or "")
    override_spec.graphql_variables = (
        payload.get("graphql_variables") if isinstance(payload.get("graphql_variables"), dict) else {}
    )
    override_spec.timeout_ms = int(payload["timeout_ms"]) if payload.get("timeout_ms") not in (None, "") else None
    override_spec.save()
    _replace_test_case_field_specs(override_spec, payload)
    _replace_test_case_file_specs(override_spec, payload)
    _upsert_test_case_auth_spec(override_spec, payload.get("auth"))
    _upsert_test_case_transport_spec(override_spec, payload.get("transport"))
    sync_legacy_test_case_from_specs(test_case)
    return override_spec


def _replace_assertion_specs_for_request(api_request: ApiRequest, payload: list[dict[str, Any]] | None):
    api_request.assertion_specs.all().delete()
    items: list[ApiAssertionSpec] = []
    for index, item in enumerate(payload or []):
        if not isinstance(item, dict):
            continue
        assertion_type = str(item.get("assertion_type") or item.get("type") or "").strip()
        if not assertion_type:
            continue
        items.append(
            ApiAssertionSpec(
                request=api_request,
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
                assertion_type=assertion_type,
                target=str(item.get("target") or "body"),
                selector=str(item.get("selector") or item.get("path") or ""),
                operator=str(item.get("operator") or "equals"),
                expected_text=str(item.get("expected_text") or ""),
                expected_number=float(item["expected_number"]) if item.get("expected_number") not in (None, "") else None,
                expected_json=item.get("expected_json") if isinstance(item.get("expected_json"), (dict, list, bool)) else {},
                min_value=float(item["min_value"]) if item.get("min_value") not in (None, "") else None,
                max_value=float(item["max_value"]) if item.get("max_value") not in (None, "") else None,
                schema_text=str(item.get("schema_text") or ""),
            )
        )
    ApiAssertionSpec.objects.bulk_create(items)


def _replace_assertion_specs_for_test_case(test_case: ApiTestCase, payload: list[dict[str, Any]] | None):
    test_case.assertion_specs.all().delete()
    items: list[ApiAssertionSpec] = []
    for index, item in enumerate(payload or []):
        if not isinstance(item, dict):
            continue
        assertion_type = str(item.get("assertion_type") or item.get("type") or "").strip()
        if not assertion_type:
            continue
        items.append(
            ApiAssertionSpec(
                test_case=test_case,
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
                assertion_type=assertion_type,
                target=str(item.get("target") or "body"),
                selector=str(item.get("selector") or item.get("path") or ""),
                operator=str(item.get("operator") or "equals"),
                expected_text=str(item.get("expected_text") or ""),
                expected_number=float(item["expected_number"]) if item.get("expected_number") not in (None, "") else None,
                expected_json=item.get("expected_json") if isinstance(item.get("expected_json"), (dict, list, bool)) else {},
                min_value=float(item["min_value"]) if item.get("min_value") not in (None, "") else None,
                max_value=float(item["max_value"]) if item.get("max_value") not in (None, "") else None,
                schema_text=str(item.get("schema_text") or ""),
            )
        )
    ApiAssertionSpec.objects.bulk_create(items)


def _replace_extractor_specs_for_request(api_request: ApiRequest, payload: list[dict[str, Any]] | None):
    api_request.extractor_specs.all().delete()
    items: list[ApiExtractorSpec] = []
    for index, item in enumerate(payload or []):
        if not isinstance(item, dict):
            continue
        variable_name = str(item.get("variable_name") or "").strip()
        source = str(item.get("source") or "").strip()
        if not variable_name or not source:
            continue
        items.append(
            ApiExtractorSpec(
                request=api_request,
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
                source=source,
                selector=str(item.get("selector") or ""),
                variable_name=variable_name,
                default_value=str(item.get("default_value") or ""),
                required=bool(item.get("required", False)),
            )
        )
    ApiExtractorSpec.objects.bulk_create(items)


def _replace_extractor_specs_for_test_case(test_case: ApiTestCase, payload: list[dict[str, Any]] | None):
    test_case.extractor_specs.all().delete()
    items: list[ApiExtractorSpec] = []
    for index, item in enumerate(payload or []):
        if not isinstance(item, dict):
            continue
        variable_name = str(item.get("variable_name") or "").strip()
        source = str(item.get("source") or "").strip()
        if not variable_name or not source:
            continue
        items.append(
            ApiExtractorSpec(
                test_case=test_case,
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
                source=source,
                selector=str(item.get("selector") or ""),
                variable_name=variable_name,
                default_value=str(item.get("default_value") or ""),
                required=bool(item.get("required", False)),
            )
        )
    ApiExtractorSpec.objects.bulk_create(items)


@transaction.atomic
def apply_request_assertions_and_extractors(
    api_request: ApiRequest,
    assertion_payload: list[dict[str, Any]] | None = None,
    extractor_payload: list[dict[str, Any]] | None = None,
):
    if assertion_payload is not None:
        _replace_assertion_specs_for_request(api_request, assertion_payload)
    if extractor_payload is not None:
        _replace_extractor_specs_for_request(api_request, extractor_payload)
    sync_legacy_request_from_specs(api_request)


@transaction.atomic
def apply_test_case_assertions_and_extractors(
    test_case: ApiTestCase,
    assertion_payload: list[dict[str, Any]] | None = None,
    extractor_payload: list[dict[str, Any]] | None = None,
):
    if assertion_payload is not None:
        _replace_assertion_specs_for_test_case(test_case, assertion_payload)
    if extractor_payload is not None:
        _replace_extractor_specs_for_test_case(test_case, extractor_payload)
    sync_legacy_test_case_from_specs(test_case)


def _body_from_request_spec_payload(spec_payload: dict[str, Any]) -> tuple[str, Any]:
    body_mode = str(spec_payload.get("body_mode") or "none").lower()
    if body_mode == "json":
        return BODY_MODE_TO_LEGACY.get(body_mode, "json"), spec_payload.get("body_json") or {}
    if body_mode in {"form", "urlencoded", "multipart"}:
        bucket = "multipart_parts" if body_mode == "multipart" else "form_fields"
        body = {}
        for item in spec_payload.get(bucket, []) or []:
            if not isinstance(item, dict) or not item.get("name") or item.get("enabled", True) is False:
                continue
            body[str(item["name"])] = item.get("value", "")
        return BODY_MODE_TO_LEGACY.get(body_mode, "form"), body
    if body_mode == "raw":
        return "raw", str(spec_payload.get("raw_text") or "")
    if body_mode == "xml":
        return "raw", str(spec_payload.get("xml_text") or "")
    if body_mode == "graphql":
        return "json", {
            "query": str(spec_payload.get("graphql_query") or ""),
            "operationName": str(spec_payload.get("graphql_operation_name") or ""),
            "variables": spec_payload.get("graphql_variables") if isinstance(spec_payload.get("graphql_variables"), dict) else {},
        }
    if body_mode == "binary":
        return "raw", str(spec_payload.get("binary_base64") or "")
    return "none", {}


def sync_legacy_request_from_specs(api_request: ApiRequest):
    spec_payload = serialize_request_spec(api_request)
    headers = {item["name"]: item.get("value", "") for item in spec_payload["headers"] if item.get("enabled", True)}
    params = {item["name"]: item.get("value", "") for item in spec_payload["query"] if item.get("enabled", True)}
    body_type, body = _body_from_request_spec_payload(spec_payload)
    api_request.method = str(spec_payload.get("method") or api_request.method or "GET").upper()
    api_request.url = str(spec_payload.get("url") or api_request.url or "")
    api_request.headers = headers
    api_request.params = params
    api_request.body_type = body_type
    api_request.body = body
    api_request.timeout_ms = int(spec_payload.get("timeout_ms") or api_request.timeout_ms or 30000)
    api_request.assertions = assertion_specs_to_legacy(api_request)
    api_request.save(
        update_fields=[
            "method",
            "url",
            "headers",
            "params",
            "body_type",
            "body",
            "timeout_ms",
            "assertions",
            "updated_at",
        ]
    )


def sync_legacy_test_case_from_specs(test_case: ApiTestCase):
    from .generation import build_parameterized_test_case_script

    legacy_script = test_case.script if isinstance(test_case.script, dict) else {}
    override_payload = serialize_test_case_override(test_case)
    request_payload = serialize_request_spec(test_case.request)
    effective_method = str(override_payload.get("method") or request_payload.get("method") or test_case.request.method).upper()
    effective_url = str(override_payload.get("url") or request_payload.get("url") or test_case.request.url)

    headers = {}
    for item in request_payload["headers"]:
        if item.get("enabled", True):
            headers[item["name"]] = item.get("value", "")
    for item in override_payload["headers"]:
        if item.get("enabled", True):
            headers[item["name"]] = item.get("value", "")

    params = {}
    for item in request_payload["query"]:
        if item.get("enabled", True):
            params[item["name"]] = item.get("value", "")
    for item in override_payload["query"]:
        if item.get("enabled", True):
            params[item["name"]] = item.get("value", "")

    merged_spec_payload = dict(request_payload)
    for key, value in override_payload.items():
        if key in {"headers", "query", "cookies", "form_fields", "multipart_parts", "files", "auth", "transport"}:
            continue
        if value not in (None, "", [], {}):
            merged_spec_payload[key] = value
    if override_payload.get("form_fields"):
        merged_spec_payload["form_fields"] = override_payload["form_fields"]
    if override_payload.get("multipart_parts"):
        merged_spec_payload["multipart_parts"] = override_payload["multipart_parts"]
    body_type, body = _body_from_request_spec_payload(merged_spec_payload)
    timeout_ms = override_payload.get("timeout_ms") or request_payload.get("timeout_ms") or test_case.request.timeout_ms or 30000
    assertions = assertion_specs_to_legacy(test_case) or test_case.request.assertions or []
    script = build_parameterized_test_case_script(
        request_id=test_case.request_id,
        method=effective_method,
        url=effective_url,
        headers=headers,
        params=params,
        body_type=body_type,
        body=body,
        timeout_ms=int(timeout_ms),
        assertions=assertions,
    )
    script["extractors"] = serialize_extractor_specs(test_case)
    script["request_override_spec"] = override_payload
    if isinstance(legacy_script.get("workflow_steps"), list):
        script["workflow_steps"] = legacy_script["workflow_steps"]
    test_case.script = script
    test_case.assertions = assertions
    test_case.save(update_fields=["script", "assertions", "updated_at"])


@transaction.atomic
def apply_environment_spec_payload(environment: ApiEnvironment, payload: dict[str, Any] | None = None):
    payload = payload or serialize_environment_specs(environment)
    environment.variable_specs.all().delete()
    ApiEnvironmentVariableSpec.objects.bulk_create(
        [
            ApiEnvironmentVariableSpec(
                environment=environment,
                name=str(item.get("name") or "").strip(),
                value=str(item.get("value") or ""),
                enabled=bool(item.get("enabled", True)),
                is_secret=bool(item.get("is_secret", False)),
                order=int(item.get("order", index)),
            )
            for index, item in enumerate(payload.get("variables", []) or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
    )

    environment.header_specs.all().delete()
    ApiEnvironmentHeaderSpec.objects.bulk_create(
        [
            ApiEnvironmentHeaderSpec(
                environment=environment,
                name=str(item.get("name") or "").strip(),
                value=str(item.get("value") or ""),
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
            )
            for index, item in enumerate(payload.get("headers", []) or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
    )

    environment.cookie_specs.all().delete()
    ApiEnvironmentCookieSpec.objects.bulk_create(
        [
            ApiEnvironmentCookieSpec(
                environment=environment,
                name=str(item.get("name") or "").strip(),
                value=str(item.get("value") or ""),
                domain=str(item.get("domain") or ""),
                path=str(item.get("path") or "/"),
                enabled=bool(item.get("enabled", True)),
                order=int(item.get("order", index)),
            )
            for index, item in enumerate(payload.get("cookies", []) or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
    )
    sync_environment_from_specs(environment)


def sync_environment_from_specs(environment: ApiEnvironment):
    headers = {
        item.name: item.value
        for item in environment.header_specs.filter(enabled=True).order_by("order", "id")
    }
    variables = {
        item.name: item.value
        for item in environment.variable_specs.filter(enabled=True).order_by("order", "id")
    }
    environment.common_headers = headers
    environment.variables = variables
    environment.save(update_fields=["common_headers", "variables", "updated_at"])


@transaction.atomic
def backfill_request_specs_from_legacy(api_request: ApiRequest):
    apply_request_spec_payload(api_request, _legacy_request_spec_payload(api_request))
    if api_request.assertions:
        apply_request_assertions_and_extractors(api_request, legacy_assertions_to_specs(api_request.assertions), [])


@transaction.atomic
def backfill_test_case_specs_from_legacy(test_case: ApiTestCase):
    apply_test_case_override_payload(test_case, _legacy_test_case_override_payload(test_case))
    if test_case.assertions:
        apply_test_case_assertions_and_extractors(test_case, legacy_assertions_to_specs(test_case.assertions), [])


@transaction.atomic
def backfill_environment_specs_from_legacy(environment: ApiEnvironment):
    apply_environment_spec_payload(environment, serialize_environment_specs(environment))
