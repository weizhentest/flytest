from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
import json
import logging
import os
import re
from string import Template
from typing import Any

from django.db.models import Q
from langchain_core.messages import HumanMessage, SystemMessage

from knowledge.models import Document as KnowledgeDocument
from knowledge.models import DocumentChunk
from langgraph_integration.models import LLMConfig
from prompts.models import UserPrompt
from requirements.models import RequirementDocument, RequirementModule

from .ai_runtime import build_ai_cache_key, run_ai_operation
from .ai_parser import create_llm_instance, extract_json_from_response, safe_llm_invoke
from .document_import import HTTP_METHODS
from .generation import build_parameterized_test_case_script
from .models import ApiExecutionRecord, ApiRequest, ApiTestCase
from .specs import (
    apply_test_case_assertions_and_extractors,
    apply_test_case_override_payload,
    serialize_assertion_specs,
    serialize_extractor_specs,
    serialize_request_spec,
    serialize_test_case_override,
)

logger = logging.getLogger(__name__)

DEFAULT_AI_CASE_GENERATION_CACHE_TTL_SECONDS = 1800
DEFAULT_AI_CASE_GENERATION_LOCK_TIMEOUT_SECONDS = 30
DEFAULT_AI_CASE_GENERATION_HISTORY_FAILURE_LIMIT = 3
DEFAULT_AI_CASE_GENERATION_HISTORY_SUCCESS_LIMIT = 2
DEFAULT_AI_CASE_GENERATION_HISTORY_ASSERTION_LIMIT = 2
DEFAULT_AI_CASE_GENERATION_HISTORY_WORKFLOW_STEP_LIMIT = 2
DEFAULT_AI_CASE_GENERATION_HISTORY_TEXT_LIMIT = 160
DEFAULT_AI_CASE_GENERATION_REFERENCE_MODULE_LIMIT = 2
DEFAULT_AI_CASE_GENERATION_REFERENCE_DOCUMENT_LIMIT = 1
DEFAULT_AI_CASE_GENERATION_REFERENCE_CHUNK_LIMIT = 2
DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT = 24
DEFAULT_AI_CASE_GENERATION_REFERENCE_TEXT_LIMIT = 220
DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_BASE_LIMIT = 3
DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_RETRIEVAL_LIMIT = 3
DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_RETRIEVAL_THRESHOLD = 0.15

SUPPORTED_BODY_TYPES = {"none", "json", "form", "urlencoded", "multipart", "raw", "xml", "graphql", "binary"}
SUPPORTED_CASE_STATUSES = {"draft", "ready", "disabled"}
SUPPORTED_ASSERTIONS = {
    "status_code",
    "status_range",
    "body_contains",
    "body_not_contains",
    "json_path",
    "header",
    "cookie",
    "regex",
    "exists",
    "not_exists",
    "array_length",
    "response_time",
    "json_schema",
    "openapi_contract",
}
SUPPORTED_EXTRACTORS = {
    "json_path",
    "header",
    "cookie",
    "regex",
    "status_code",
    "response_time",
}
SUPPORTED_AUTH_TYPES = {"none", "basic", "bearer", "api_key", "cookie", "bootstrap_request"}
AUTH_TYPE_ALIASES = {
    "": "",
    "none": "none",
    "noauth": "none",
    "basic": "basic",
    "basicauth": "basic",
    "bearer": "bearer",
    "bearertoken": "bearer",
    "oauth2": "bearer",
    "openidconnect": "bearer",
    "apikey": "api_key",
    "api-key": "api_key",
    "api_key": "api_key",
    "cookie": "cookie",
    "bootstrap": "bootstrap_request",
    "bootstrap_request": "bootstrap_request",
    "login": "bootstrap_request",
}

DEFAULT_CASE_PROMPT = """你是 FlyTest 的资深 API 自动化测试设计专家。
请围绕给定接口生成结构化测试用例，要求如下：

1. 每个测试用例必须严格绑定当前接口，不能跨接口。
2. 优先覆盖：基础成功场景、核心业务校验、关键边界场景、常见异常场景。
3. 如果已有测试用例，请避免和现有名称、意图完全重复；在追加生成模式下尤其如此。
4. 断言优先使用结构化规格，可使用：
   - status_code / status_range
   - body_contains / body_not_contains
   - json_path / exists / not_exists / array_length
   - header / cookie / regex
   - response_time / json_schema / openapi_contract
5. 如需依赖响应上下文，请使用 extractors 提取变量，可使用：
   - json_path / header / cookie / regex / status_code / response_time
6. request_overrides 只返回相对当前接口需要覆盖的字段，可包含：
   - method / url / timeout_ms
   - headers / query / cookies
   - body_mode / body_json / raw_text / xml_text / graphql_query / graphql_operation_name / graphql_variables / binary_base64
   - form_fields / multipart_parts / files
   - auth / transport
7. 结果必须只返回 JSON，不要输出 Markdown，不要解释。

输出 JSON 结构如下：
{
  "summary": "一句话总结本次生成策略",
  "cases": [
    {
      "name": "测试用例名称",
      "description": "测试目标说明",
      "status": "ready",
      "tags": ["ai-generated", "positive"],
      "assertions": [
        {"assertion_type": "status_code", "expected_number": 200},
        {"assertion_type": "json_path", "selector": "code", "operator": "equals", "expected_number": 0}
      ],
      "extractors": [
        {"source": "json_path", "selector": "data.id", "variable_name": "created_id"}
      ],
      "request_overrides": {
        "headers": [],
        "query": [],
        "cookies": [],
        "body_mode": "json",
        "body_json": {},
        "timeout_ms": 30000
      }
    }
  ]
}

当前模式: ${mode}
期望生成数量: ${count}
接口信息:
${request_json}

已有测试用例:
${existing_cases_json}

Strict output contract:
${generation_contract_json}
"""


@dataclass
class GeneratedCaseDraft:
    name: str
    description: str
    status: str
    tags: list[str]
    assertions: list[dict[str, Any]]
    extractors: list[dict[str, Any]]
    request_overrides: dict[str, Any]


@dataclass
class AITestCaseGenerationResult:
    used_ai: bool
    note: str
    cases: list[GeneratedCaseDraft]
    prompt_name: str | None = None
    prompt_source: str | None = None
    model_name: str | None = None
    case_summaries: list[dict[str, Any]] = field(default_factory=list)
    cache_hit: bool = False
    cache_key: str | None = None
    duration_ms: float | None = None
    lock_wait_ms: float | None = None


def _format_prompt(template: str, **kwargs) -> str:
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", str(value))
    try:
        result = Template(result).safe_substitute(**kwargs)
    except Exception:  # noqa: BLE001
        pass
    return result


def _get_generation_prompt(user) -> tuple[str, str, str]:
    user_prompt = (
        UserPrompt.objects.filter(user=user, is_active=True, name__icontains="API自动化用例生成")
        .order_by("-updated_at")
        .first()
    )
    if user_prompt:
        return user_prompt.content, "user_prompt", user_prompt.name
    return DEFAULT_CASE_PROMPT, "builtin_fallback", "API自动化用例生成"


def _serialize_request(api_request: ApiRequest) -> str:
    payload = {
        "id": api_request.id,
        "name": api_request.name,
        "description": api_request.description or "",
        "request_spec": serialize_request_spec(api_request),
        "assertion_specs": serialize_assertion_specs(api_request),
        "extractor_specs": serialize_extractor_specs(api_request),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _serialize_generation_contract() -> str:
    payload = {
        "supported_case_statuses": sorted(SUPPORTED_CASE_STATUSES),
        "supported_body_modes": sorted(SUPPORTED_BODY_TYPES),
        "supported_auth_types": sorted(SUPPORTED_AUTH_TYPES),
        "supported_assertions": sorted(SUPPORTED_ASSERTIONS),
        "supported_extractors": sorted(SUPPORTED_EXTRACTORS),
        "dedup_hint": "append mode deduplicates by effective request coverage plus assertion semantics, not only by case name",
        "request_override_rules": [
            "only return fields that need override",
            "headers/query/cookies/form_fields/multipart_parts may be objects or named-item arrays",
            "files may use field_name/name, file_path/path/src, file_name/filename, content_type/contentType, base64_content/base64",
            "auth may use auth_type/type/mode and aliases like apikey, bearer, oauth2, noauth",
            "transport may use verify_ssl/verify, proxy_url/proxy, retry_count/retries, retry_interval_ms/retry_interval",
        ],
        "examples": {
            "auth": {
                "auth_type": "api_key",
                "api_key_name": "X-API-Key",
                "api_key_in": "header",
                "token_variable": "api_key",
            },
            "file": {
                "field_name": "file",
                "source_type": "path",
                "file_path": "{{avatar_path}}",
                "file_name": "avatar.png",
                "content_type": "image/png",
            },
            "transport": {
                "verify_ssl": False,
                "follow_redirects": False,
                "retry_count": 2,
                "retry_interval_ms": 800,
                "proxy_url": "http://127.0.0.1:7890",
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _serialize_existing_cases(existing_cases: list[ApiTestCase]) -> str:
    payload = [
        {
            "id": case.id,
            "name": case.name,
            "description": case.description or "",
            "status": case.status,
            "tags": case.tags or [],
            "assertion_specs": serialize_assertion_specs(case),
            "extractor_specs": serialize_extractor_specs(case),
            "request_override_spec": serialize_test_case_override(case),
        }
        for case in existing_cases
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _read_int_env(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    raw_value = (os.environ.get(name) or "").strip()
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        logger.warning("Invalid integer env %s=%r, fallback to %s", name, raw_value, default)
        return default
    if parsed < minimum:
        return minimum
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def _get_case_generation_cache_ttl() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_CASE_GENERATION_CACHE_TTL_SECONDS",
        DEFAULT_AI_CASE_GENERATION_CACHE_TTL_SECONDS,
        minimum=0,
        maximum=24 * 60 * 60,
    )


def _get_case_generation_lock_timeout() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_CASE_GENERATION_LOCK_TIMEOUT_SECONDS",
        DEFAULT_AI_CASE_GENERATION_LOCK_TIMEOUT_SECONDS,
        minimum=1,
        maximum=300,
    )


def _get_case_generation_history_failure_limit() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_CASE_GENERATION_HISTORY_FAILURE_LIMIT",
        DEFAULT_AI_CASE_GENERATION_HISTORY_FAILURE_LIMIT,
        minimum=0,
        maximum=10,
    )


def _get_case_generation_history_success_limit() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_CASE_GENERATION_HISTORY_SUCCESS_LIMIT",
        DEFAULT_AI_CASE_GENERATION_HISTORY_SUCCESS_LIMIT,
        minimum=0,
        maximum=10,
    )


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _build_case_generation_cache_key(
    *,
    api_request: ApiRequest,
    existing_cases: list[ApiTestCase],
    mode: str,
    count: int,
    prompt_template: str,
    prompt_source: str,
    prompt_name: str,
    generation_contract_json: str,
    reference_context_json: str,
    historical_context_json: str,
    model_name: str,
) -> str:
    return build_ai_cache_key(
        "test_case_generation",
        {
            "request_id": api_request.id,
            "request_digest": _digest_text(_serialize_request(api_request)),
            "existing_cases_digest": _digest_text(_serialize_existing_cases(existing_cases)),
            "mode": mode,
            "count": count,
            "prompt_source": prompt_source,
            "prompt_name": prompt_name,
            "prompt_digest": _digest_text(prompt_template),
            "contract_digest": _digest_text(generation_contract_json),
            "reference_digest": _digest_text(reference_context_json),
            "history_digest": _digest_text(historical_context_json),
            "model_name": model_name,
        },
    )


def _truncate_history_text(value: Any, limit: int = DEFAULT_AI_CASE_GENERATION_HISTORY_TEXT_LIMIT) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:  # noqa: BLE001
            text = str(value)
    else:
        text = str(value)
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: max(0, limit - 3)]}..."


def _extract_response_message_hint(response_snapshot: Any) -> str:
    if not isinstance(response_snapshot, dict):
        return ""
    body = response_snapshot.get("body")
    if isinstance(body, dict):
        for key in ("message", "detail", "error", "msg", "code"):
            if body.get(key) not in (None, ""):
                return _truncate_history_text(body.get(key))
    if response_snapshot.get("text") not in (None, ""):
        return _truncate_history_text(response_snapshot.get("text"))
    return ""


def _extract_failed_assertion_examples(assertions_results: Any) -> list[dict[str, Any]]:
    if not isinstance(assertions_results, list):
        return []

    examples: list[dict[str, Any]] = []
    for item in assertions_results:
        if not isinstance(item, dict) or item.get("passed", True):
            continue
        examples.append(
            {
                "type": str(item.get("type") or item.get("assertion_type") or ""),
                "selector": str(item.get("path") or item.get("selector") or ""),
                "operator": str(item.get("operator") or ""),
                "expected": _truncate_history_text(item.get("expected")),
                "actual": _truncate_history_text(item.get("actual")),
                "message": _truncate_history_text(item.get("message")),
            }
        )
        if len(examples) >= DEFAULT_AI_CASE_GENERATION_HISTORY_ASSERTION_LIMIT:
            break
    return examples


def _extract_assertion_types(assertions_results: Any) -> list[str]:
    if not isinstance(assertions_results, list):
        return []
    return sorted(
        {
            str(item.get("type") or item.get("assertion_type") or "").strip()
            for item in assertions_results
            if isinstance(item, dict) and str(item.get("type") or item.get("assertion_type") or "").strip()
        }
    )


def _extract_workflow_hint(request_snapshot: Any) -> dict[str, Any]:
    if not isinstance(request_snapshot, dict):
        return {}

    workflow_summary = request_snapshot.get("workflow_summary")
    if not isinstance(workflow_summary, dict):
        workflow_summary = {}
    workflow_steps = request_snapshot.get("workflow_steps")
    if not isinstance(workflow_steps, list):
        workflow_steps = []

    failed_steps: list[dict[str, Any]] = []
    for step in workflow_steps:
        if not isinstance(step, dict):
            continue
        status = str(step.get("status") or "").strip().lower()
        if status not in {"failed", "error"} and step.get("error_message") in (None, ""):
            continue
        failed_steps.append(
            {
                "name": _truncate_history_text(step.get("name") or f"step-{step.get('index', len(failed_steps) + 1)}", 80),
                "stage": str(step.get("stage") or ""),
                "status": status or "failed",
                "status_code": step.get("status_code"),
                "error_message": _truncate_history_text(step.get("error_message")),
            }
        )
        if len(failed_steps) >= DEFAULT_AI_CASE_GENERATION_HISTORY_WORKFLOW_STEP_LIMIT:
            break

    has_workflow = bool(workflow_summary.get("enabled") or request_snapshot.get("main_request_blocked") or failed_steps)
    if not has_workflow:
        return {}

    return {
        "enabled": bool(workflow_summary.get("enabled", False)),
        "blocked_main_request": bool(request_snapshot.get("main_request_blocked", False)),
        "configured_step_count": int(workflow_summary.get("configured_step_count") or 0),
        "executed_step_count": int(workflow_summary.get("executed_step_count") or 0),
        "main_request_executed": bool(workflow_summary.get("main_request_executed", True)),
        "failed_steps": failed_steps,
    }


def _build_history_failure_patterns(
    *,
    record: ApiExecutionRecord,
    failed_assertions: list[dict[str, Any]],
    workflow_hint: dict[str, Any],
    response_hint: str,
) -> list[str]:
    patterns: list[str] = []
    error_blob = " ".join(
        item
        for item in [
            str(record.error_message or ""),
            response_hint,
            " ".join(str(item.get("message") or "") for item in failed_assertions),
        ]
        if item
    ).lower()

    if workflow_hint.get("blocked_main_request") or workflow_hint.get("failed_steps"):
        patterns.append("workflow_blocked")
    if record.status_code in {401, 403} or any(
        keyword in error_blob
        for keyword in ("token", "auth", "login", "permission", "unauthorized", "forbidden", "登录", "权限")
    ):
        patterns.append("auth_or_permission")
    if isinstance(record.status_code, int) and record.status_code >= 500:
        patterns.append("server_error")
    if any(item.get("type") in {"response_time"} for item in failed_assertions):
        patterns.append("performance_risk")
    if any(item.get("type") in {"json_schema", "openapi_contract"} for item in failed_assertions):
        patterns.append("contract_mismatch")
    if any(item.get("type") in {"json_path", "exists", "not_exists", "array_length"} for item in failed_assertions):
        patterns.append("response_structure_mismatch")
    if not patterns:
        patterns.append("general_failure")
    return list(dict.fromkeys(patterns))


def _build_generation_history_example(record: ApiExecutionRecord) -> dict[str, Any]:
    failed_assertions = _extract_failed_assertion_examples(record.assertions_results)
    workflow_hint = _extract_workflow_hint(record.request_snapshot)
    response_hint = _extract_response_message_hint(record.response_snapshot)
    assertion_types = _extract_assertion_types(record.assertions_results)

    example = {
        "record_id": record.id,
        "executed_at": record.created_at.isoformat() if record.created_at else "",
        "request_name": str(record.request_name or ""),
        "test_case_name": str(record.test_case.name if record.test_case_id and record.test_case else ""),
        "status": str(record.status or ""),
        "passed": bool(record.passed),
        "status_code": record.status_code,
        "response_time_ms": _normalize_numeric_value(record.response_time),
    }
    if record.error_message:
        example["error_message"] = _truncate_history_text(record.error_message)
    if response_hint and response_hint != example.get("error_message"):
        example["response_hint"] = response_hint
    if failed_assertions:
        example["failed_assertions"] = failed_assertions
    if assertion_types:
        example["assertion_types"] = assertion_types
    if workflow_hint:
        example["workflow"] = workflow_hint
    if not record.passed or str(record.status or "").lower() != "success":
        example["failure_patterns"] = _build_history_failure_patterns(
            record=record,
            failed_assertions=failed_assertions,
            workflow_hint=workflow_hint,
            response_hint=response_hint,
        )
    return example


def _build_generation_history_dedup_key(record: ApiExecutionRecord) -> tuple[Any, ...]:
    failed_assertions = _extract_failed_assertion_examples(record.assertions_results)
    return (
        record.test_case_id or 0,
        str(record.status or ""),
        bool(record.passed),
        record.status_code,
        _truncate_history_text(record.error_message, 80),
        tuple(str(item.get("type") or "") for item in failed_assertions),
    )


def _select_recent_history_records(queryset, limit: int) -> list[ApiExecutionRecord]:
    if limit <= 0:
        return []

    selected: list[ApiExecutionRecord] = []
    seen_keys: set[tuple[Any, ...]] = set()
    raw_limit = max(limit * 4, limit)
    for record in queryset.select_related("test_case").order_by("-created_at", "-id")[:raw_limit]:
        dedup_key = _build_generation_history_dedup_key(record)
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected


def _build_generation_history_context(api_request: ApiRequest) -> dict[str, Any]:
    history_queryset = ApiExecutionRecord.objects.filter(request=api_request)
    failed_records = _select_recent_history_records(
        history_queryset.exclude(status="success", passed=True),
        _get_case_generation_history_failure_limit(),
    )
    success_records = _select_recent_history_records(
        history_queryset.filter(status="success", passed=True),
        _get_case_generation_history_success_limit(),
    )

    failed_examples = [_build_generation_history_example(record) for record in failed_records]
    success_examples = [_build_generation_history_example(record) for record in success_records]

    failure_pattern_counts: dict[str, int] = {}
    for example in failed_examples:
        for pattern in example.get("failure_patterns") or []:
            failure_pattern_counts[pattern] = failure_pattern_counts.get(pattern, 0) + 1

    summary = {
        "history_available": bool(failed_examples or success_examples),
        "failed_example_count": len(failed_examples),
        "success_example_count": len(success_examples),
        "common_failure_patterns": [
            item[0]
            for item in sorted(failure_pattern_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        ],
    }
    if failed_examples and success_examples:
        summary["generation_hint"] = "Cover recent failure patterns, but keep at least one stable success baseline."
    elif failed_examples:
        summary["generation_hint"] = "Bias toward recent failure recovery and boundary cases."
    elif success_examples:
        summary["generation_hint"] = "Use recent successful executions as regression baselines."
    else:
        summary["generation_hint"] = "No execution history is available yet."

    return {
        "summary": summary,
        "recent_failed_examples": failed_examples,
        "recent_success_examples": success_examples,
    }


def _serialize_generation_history_context(api_request: ApiRequest) -> str:
    return json.dumps(_build_generation_history_context(api_request), ensure_ascii=False, indent=2)


def _compact_reference_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (dict, list)):
        try:
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:  # noqa: BLE001
            value = str(value)
    return " ".join(str(value).split())


def _truncate_reference_text(value: Any, limit: int = DEFAULT_AI_CASE_GENERATION_REFERENCE_TEXT_LIMIT) -> str:
    text = _compact_reference_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _build_reference_search_terms(api_request: ApiRequest) -> list[str]:
    request_spec = serialize_request_spec(api_request)
    raw_terms: list[str] = [
        str(api_request.name or ""),
        str(api_request.url or ""),
        str(api_request.description or ""),
        str(api_request.collection.name if api_request.collection_id and api_request.collection else ""),
        str(request_spec.get("graphql_operation_name") or ""),
    ]
    raw_terms.extend(
        re.split(
            r"[^A-Za-z0-9\u4e00-\u9fff]+",
            " ".join(
                [
                    str(api_request.name or ""),
                    str(api_request.url or ""),
                    str(api_request.description or ""),
                    str(api_request.collection.name if api_request.collection_id and api_request.collection else ""),
                ]
            ),
        )
    )

    ignored_terms = {"", "api", "http", "https", "json", "graphql", "www", api_request.method.lower()}
    terms: list[str] = []
    seen: set[str] = set()
    for item in raw_terms:
        normalized = _compact_reference_text(item).lower().strip("/ ")
        if len(normalized) < 2 or normalized in ignored_terms or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
        if len(terms) >= 10:
            break
    return terms


def _build_reference_query(search_terms: list[str], fields: list[str]) -> Q:
    query = Q()
    for term in search_terms[:8]:
        term_query = Q()
        for field in fields:
            term_query |= Q(**{f"{field}__icontains": term})
        query |= term_query
    return query


def _score_reference_candidate(
    *,
    api_request: ApiRequest,
    title: str,
    content: str,
    search_terms: list[str],
) -> tuple[int, list[str]]:
    normalized_title = _compact_reference_text(title).lower()
    normalized_content = _compact_reference_text(content).lower()
    request_name = _compact_reference_text(api_request.name).lower()
    request_url = _compact_reference_text(api_request.url).lower()

    score = 0
    matched_terms: list[str] = []

    if request_name:
        if request_name in normalized_title:
            score += 18
            matched_terms.append(request_name)
        elif request_name in normalized_content:
            score += 12
            matched_terms.append(request_name)

    if request_url:
        if request_url in normalized_title:
            score += 14
            matched_terms.append(request_url)
        elif request_url in normalized_content:
            score += 10
            matched_terms.append(request_url)

    for term in search_terms:
        if not term:
            continue
        term_score = 0
        if term in normalized_title:
            term_score += 6
        if term in normalized_content:
            term_score += 2
        if term_score:
            score += term_score
            matched_terms.append(term)

    if api_request.method.lower() in normalized_title or api_request.method.lower() in normalized_content:
        score += 1

    return score, list(dict.fromkeys(matched_terms))[:4]


def _build_reference_snippet(content: Any, search_terms: list[str]) -> str:
    text = _compact_reference_text(content)
    if not text:
        return ""
    lowered = text.lower()
    match_index = -1
    match_length = 0
    for term in search_terms:
        if not term:
            continue
        index = lowered.find(term)
        if index >= 0 and (match_index < 0 or index < match_index):
            match_index = index
            match_length = len(term)

    if match_index < 0 or len(text) <= DEFAULT_AI_CASE_GENERATION_REFERENCE_TEXT_LIMIT:
        return _truncate_reference_text(text)

    window = DEFAULT_AI_CASE_GENERATION_REFERENCE_TEXT_LIMIT
    start = max(0, match_index - window // 3)
    end = min(len(text), start + window)
    snippet = text[start:end]
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(text):
        snippet = f"{snippet}..."
    return snippet


def _select_reference_entries(entries: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = [item for item in entries if int(item.get("score") or 0) > 0]
    ranked.sort(
        key=lambda item: (
            int(item.get("score") or 0),
            int(item.get("recency_rank") or 0),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    return ranked[:limit]


def _build_knowledge_retrieval_query(api_request: ApiRequest, search_terms: list[str]) -> str:
    request_spec = serialize_request_spec(api_request)
    query_parts = [
        str(api_request.name or "").strip(),
        f"{api_request.method} {api_request.url}".strip(),
        str(api_request.description or "").strip(),
    ]
    body_mode = str(request_spec.get("body_mode") or "").strip()
    if body_mode and body_mode != "none":
        query_parts.append(f"body_mode={body_mode}")
    if search_terms:
        query_parts.append("keywords: " + " ".join(search_terms[:6]))
    return "\n".join(part for part in query_parts if part).strip()


def _collect_knowledge_references_with_hybrid_search(
    api_request: ApiRequest,
    search_terms: list[str],
) -> dict[str, Any]:
    project = api_request.collection.project
    query_text = _build_knowledge_retrieval_query(api_request, search_terms)
    knowledge_bases = list(
        project.knowledge_bases.filter(is_active=True, documents__status="completed")
        .distinct()
        .order_by("-updated_at")[:DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_BASE_LIMIT]
    )
    summary: dict[str, Any] = {
        "query": _truncate_reference_text(query_text, 180),
        "knowledge_base_count": len(knowledge_bases),
        "searched_knowledge_bases": [kb.name for kb in knowledge_bases],
        "used_hybrid_search": False,
        "fallback_used": False,
        "result_count": 0,
    }
    if not query_text or not knowledge_bases:
        return {"references": [], "summary": summary}

    try:
        from knowledge.services import VectorStoreManager
    except Exception as exc:  # noqa: BLE001
        summary["fallback_used"] = True
        summary["error"] = _truncate_reference_text(exc, 180)
        return {"references": [], "summary": summary}

    aggregated: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_keys: set[str] = set()
    for kb in knowledge_bases:
        try:
            manager = VectorStoreManager(kb)
            results = manager.similarity_search(
                query_text,
                k=DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_RETRIEVAL_LIMIT,
                score_threshold=DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_RETRIEVAL_THRESHOLD,
            )
            for index, result in enumerate(results):
                metadata = result.get("metadata") or {}
                content = str(result.get("content") or metadata.get("page_content") or "").strip()
                if not content:
                    continue
                title = str(metadata.get("title") or metadata.get("source") or kb.name).strip()
                similarity_score = float(result.get("similarity_score") or 0.0)
                lexical_score, matched_terms = _score_reference_candidate(
                    api_request=api_request,
                    title=f"{title} {kb.name}",
                    content=content,
                    search_terms=search_terms,
                )
                dedup_key = "|".join(
                    [
                        str(kb.id),
                        str(metadata.get("document_id") or ""),
                        str(metadata.get("chunk_index") or ""),
                        _digest_text(content)[:16],
                    ]
                )
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                aggregated.append(
                    {
                        "source": "knowledge_chunk",
                        "title": _truncate_reference_text(title, 120),
                        "container_title": _truncate_reference_text(kb.name, 120),
                        "snippet": _build_reference_snippet(content, search_terms),
                        "score": max(int(round(similarity_score * 100)), lexical_score),
                        "matched_terms": matched_terms,
                        "recency_rank": max(DEFAULT_AI_CASE_GENERATION_KNOWLEDGE_RETRIEVAL_LIMIT - index, 0),
                        "similarity_score": round(similarity_score, 4),
                        "retrieval_method": "hybrid",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "Knowledge hybrid retrieval unavailable for request %s in KB %s: %s",
                api_request.id,
                kb.id,
                exc,
            )
            errors.append(f"{kb.name}: {exc}")

    aggregated.sort(
        key=lambda item: (
            float(item.get("similarity_score") or 0.0),
            int(item.get("score") or 0),
            int(item.get("recency_rank") or 0),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )
    references = aggregated[:DEFAULT_AI_CASE_GENERATION_REFERENCE_CHUNK_LIMIT]
    summary.update(
        {
            "used_hybrid_search": bool(references),
            "fallback_used": not bool(references),
            "result_count": len(references),
        }
    )
    if errors:
        summary["errors"] = [_truncate_reference_text(item, 160) for item in errors[:2]]
    return {"references": references, "summary": summary}


def _collect_requirement_module_references(api_request: ApiRequest, search_terms: list[str]) -> list[dict[str, Any]]:
    project = api_request.collection.project
    query = _build_reference_query(search_terms, ["title", "content", "document__title", "document__description"])
    if not query:
        return []

    candidates = (
        RequirementModule.objects.select_related("document")
        .filter(document__project=project)
        .exclude(document__status="failed")
        .filter(query)
        .order_by("-updated_at", "-created_at")[:DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT]
    )

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        score, matched_terms = _score_reference_candidate(
            api_request=api_request,
            title=f"{item.title} {item.document.title}",
            content=f"{item.content} {item.document.description or ''}",
            search_terms=search_terms,
        )
        entries.append(
            {
                "source": "requirement_module",
                "title": _truncate_reference_text(item.title, 120),
                "container_title": _truncate_reference_text(item.document.title, 120),
                "snippet": _build_reference_snippet(item.content, search_terms),
                "score": score,
                "matched_terms": matched_terms,
                "recency_rank": DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT - index,
            }
        )
    return _select_reference_entries(entries, DEFAULT_AI_CASE_GENERATION_REFERENCE_MODULE_LIMIT)


def _collect_requirement_document_references(api_request: ApiRequest, search_terms: list[str]) -> list[dict[str, Any]]:
    project = api_request.collection.project
    query = _build_reference_query(search_terms, ["title", "description", "content"])
    if not query:
        return []

    candidates = (
        RequirementDocument.objects.filter(project=project)
        .exclude(status="failed")
        .filter(query)
        .order_by("-uploaded_at", "-updated_at")[:DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT]
    )

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        score, matched_terms = _score_reference_candidate(
            api_request=api_request,
            title=item.title,
            content=f"{item.description or ''} {item.content or ''}",
            search_terms=search_terms,
        )
        entries.append(
            {
                "source": "requirement_document",
                "title": _truncate_reference_text(item.title, 120),
                "container_title": "",
                "snippet": _build_reference_snippet(item.content or item.description or "", search_terms),
                "score": score,
                "matched_terms": matched_terms,
                "recency_rank": DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT - index,
            }
        )
    return _select_reference_entries(entries, DEFAULT_AI_CASE_GENERATION_REFERENCE_DOCUMENT_LIMIT)


def _collect_knowledge_chunk_references(api_request: ApiRequest, search_terms: list[str]) -> list[dict[str, Any]]:
    project = api_request.collection.project
    query = _build_reference_query(search_terms, ["content", "document__title", "document__content"])
    if not query:
        return []

    candidates = (
        DocumentChunk.objects.select_related("document", "document__knowledge_base")
        .filter(document__knowledge_base__project=project, document__knowledge_base__is_active=True, document__status="completed")
        .filter(query)
        .order_by("-created_at", "-chunk_index")[:DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT]
    )

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        score, matched_terms = _score_reference_candidate(
            api_request=api_request,
            title=f"{item.document.title} {item.document.knowledge_base.name}",
            content=item.content,
            search_terms=search_terms,
        )
        entries.append(
            {
                "source": "knowledge_chunk",
                "title": _truncate_reference_text(item.document.title, 120),
                "container_title": _truncate_reference_text(item.document.knowledge_base.name, 120),
                "snippet": _build_reference_snippet(item.content, search_terms),
                "score": score,
                "matched_terms": matched_terms,
                "recency_rank": DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT - index,
            }
        )
    return _select_reference_entries(entries, DEFAULT_AI_CASE_GENERATION_REFERENCE_CHUNK_LIMIT)


def _collect_knowledge_document_references(api_request: ApiRequest, search_terms: list[str]) -> list[dict[str, Any]]:
    project = api_request.collection.project
    query = _build_reference_query(search_terms, ["title", "content", "knowledge_base__name"])
    if not query:
        return []

    candidates = (
        KnowledgeDocument.objects.select_related("knowledge_base")
        .filter(knowledge_base__project=project, knowledge_base__is_active=True, status="completed")
        .filter(query)
        .order_by("-uploaded_at", "-processed_at")[:DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT]
    )

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        score, matched_terms = _score_reference_candidate(
            api_request=api_request,
            title=f"{item.title} {item.knowledge_base.name}",
            content=item.content or "",
            search_terms=search_terms,
        )
        entries.append(
            {
                "source": "knowledge_document",
                "title": _truncate_reference_text(item.title, 120),
                "container_title": _truncate_reference_text(item.knowledge_base.name, 120),
                "snippet": _build_reference_snippet(item.content or "", search_terms),
                "score": score,
                "matched_terms": matched_terms,
                "recency_rank": DEFAULT_AI_CASE_GENERATION_REFERENCE_CANDIDATE_LIMIT - index,
            }
        )
    return _select_reference_entries(entries, DEFAULT_AI_CASE_GENERATION_REFERENCE_DOCUMENT_LIMIT)


def _build_generation_reference_context(api_request: ApiRequest) -> dict[str, Any]:
    project = api_request.collection.project
    search_terms = _build_reference_search_terms(api_request)
    knowledge_retrieval = _collect_knowledge_references_with_hybrid_search(api_request, search_terms)
    knowledge_references = list(knowledge_retrieval.get("references") or [])
    if not knowledge_references:
        knowledge_references = _collect_knowledge_chunk_references(api_request, search_terms) + _collect_knowledge_document_references(
            api_request, search_terms
        )
        knowledge_summary = dict(knowledge_retrieval.get("summary") or {})
        knowledge_summary["fallback_result_count"] = len(knowledge_references)
        knowledge_retrieval = {
            "references": knowledge_references,
            "summary": knowledge_summary,
        }

    references = (
        _collect_requirement_module_references(api_request, search_terms)
        + _collect_requirement_document_references(api_request, search_terms)
        + knowledge_references
    )
    references.sort(
        key=lambda item: (
            int(item.get("score") or 0),
            int(item.get("recency_rank") or 0),
            str(item.get("title") or ""),
        ),
        reverse=True,
    )

    source_counts: dict[str, int] = {}
    for item in references:
        source = str(item.get("source") or "")
        if not source:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1

    summary = {
        "project_name": project.name,
        "reference_available": bool(references),
        "reference_count": len(references),
        "search_terms": search_terms[:6],
        "source_counts": source_counts,
        "knowledge_retrieval": knowledge_retrieval.get("summary") or {},
    }
    if references:
        summary["generation_hint"] = "Prefer explicit requirement rules and project knowledge snippets when designing edge cases and assertions."
    else:
        summary["generation_hint"] = "No relevant project requirement or knowledge documents were matched."

    return {
        "summary": summary,
        "references": references,
    }


def _serialize_generation_reference_context(api_request: ApiRequest) -> str:
    return json.dumps(_build_generation_reference_context(api_request), ensure_ascii=False, indent=2)


def _normalize_assertions(assertions: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(assertions, list):
        for item in assertions:
            if not isinstance(item, dict):
                continue
            assertion_type = str(item.get("assertion_type") or item.get("type") or "").strip()
            if assertion_type not in SUPPORTED_ASSERTIONS:
                continue
            normalized_item: dict[str, Any] = {
                "assertion_type": assertion_type,
                "target": item.get("target") or ("json" if assertion_type == "json_path" else "body"),
                "selector": item.get("selector") or item.get("path") or "",
                "operator": item.get("operator") or "equals",
                "expected_text": item.get("expected_text") or "",
                "expected_number": _coerce_number(item.get("expected_number")),
                "expected_json": _parse_json_object(item.get("expected_json"), {}),
                "min_value": _coerce_number(item.get("min_value")),
                "max_value": _coerce_number(item.get("max_value")),
                "schema_text": _normalize_schema_text(item.get("schema_text")),
            }
            if item.get("expected") not in (None, "") and normalized_item["expected_number"] in (None, ""):
                if isinstance(item.get("expected"), (int, float)):
                    normalized_item["expected_number"] = item.get("expected")
                elif isinstance(item.get("expected"), (dict, list, bool)):
                    normalized_item["expected_json"] = item.get("expected")
                else:
                    normalized_item["expected_text"] = str(item.get("expected"))
            normalized.append(normalized_item)
    return normalized or fallback or [{"assertion_type": "status_code", "expected_number": 200}]


def _normalize_extractors(extractors: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(extractors, list):
        for item in extractors:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or item.get("type") or "").strip()
            variable_name = str(item.get("variable_name") or item.get("name") or "").strip()
            if source not in SUPPORTED_EXTRACTORS or not variable_name:
                continue
            normalized.append(
                {
                    "source": source,
                    "selector": str(item.get("selector") or item.get("path") or ""),
                    "variable_name": variable_name,
                    "default_value": str(item.get("default_value") or ""),
                    "required": _coerce_bool(item.get("required"), False),
                    "enabled": _coerce_bool(item.get("enabled"), True),
                    "order": _coerce_int(item.get("order"), len(normalized)),
                }
            )
    return normalized or fallback or []


def _normalize_named_items(items: Any) -> list[dict[str, Any]]:
    if isinstance(items, dict):
        return [
            {"name": str(key), "value": value, "enabled": True, "order": index}
            for index, (key, value) in enumerate(items.items())
        ]
    if isinstance(items, list):
        normalized = []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("name"):
                continue
            normalized.append(
                {
                    "name": str(item.get("name")),
                    "value": item.get("value", ""),
                    "enabled": bool(item.get("enabled", True)),
                    "order": int(item.get("order", index)),
                }
            )
        return normalized
    return []


def _coerce_bool(value: Any, fallback: bool | None = None) -> bool | None:
    if value in (None, ""):
        return fallback
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return fallback


def _coerce_int(value: Any, fallback: int | None = None) -> int | None:
    if value in (None, ""):
        return fallback
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _coerce_number(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _normalize_numeric_value(value)
    try:
        numeric = float(str(value).strip())
        return _normalize_numeric_value(numeric)
    except (TypeError, ValueError):
        return value


def _parse_json_object(value: Any, fallback: dict[str, Any] | list[Any]):
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:  # noqa: BLE001
            return fallback
        return parsed if isinstance(parsed, type(fallback)) else fallback
    return fallback


def _normalize_schema_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return ""


def _normalize_files(items: Any) -> list[dict[str, Any]]:
    if isinstance(items, dict):
        items = [
            {
                "field_name": key,
                **(value if isinstance(value, dict) else {"file_path": value}),
            }
            for key, value in items.items()
        ]
    if not isinstance(items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or item.get("name") or item.get("key") or "").strip()
        if not field_name:
            continue
        source_type = str(item.get("source_type") or item.get("source") or "path").strip().lower() or "path"
        file_path = str(item.get("file_path") or item.get("path") or item.get("src") or "")
        file_name = str(item.get("file_name") or item.get("filename") or item.get("label") or "")
        content_type = str(item.get("content_type") or item.get("contentType") or item.get("mime_type") or item.get("mimeType") or "")
        base64_content = str(item.get("base64_content") or item.get("base64") or "")
        if source_type == "base64" and not base64_content:
            base64_content = file_path
            file_path = ""
        if not file_path and not base64_content:
            file_path = f"{{{{{field_name}}}}}"
        normalized.append(
            {
                "field_name": field_name,
                "source_type": "base64" if source_type == "base64" else "path",
                "file_path": file_path,
                "file_name": file_name,
                "content_type": content_type,
                "base64_content": base64_content,
                "enabled": _coerce_bool(item.get("enabled"), True),
                "order": _coerce_int(item.get("order"), index),
            }
        )
    return normalized


def _normalize_auth_override(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    raw_auth_type = str(payload.get("auth_type") or payload.get("type") or payload.get("mode") or "").strip().lower()
    if not raw_auth_type:
        if payload.get("username") or payload.get("password") or payload.get("user") or payload.get("pass"):
            raw_auth_type = "basic"
        elif payload.get("cookie_name") or payload.get("cookie"):
            raw_auth_type = "cookie"
        elif payload.get("api_key_name") or payload.get("key") or payload.get("in") or payload.get("location"):
            raw_auth_type = "api_key"
        elif payload.get("bootstrap_request_id") or payload.get("bootstrap_request_name"):
            raw_auth_type = "bootstrap_request"
        elif payload.get("token_value") or payload.get("token") or payload.get("token_variable"):
            raw_auth_type = "bearer"
    auth_type = AUTH_TYPE_ALIASES.get(raw_auth_type, raw_auth_type)
    if auth_type not in SUPPORTED_AUTH_TYPES:
        return {}

    normalized = {"auth_type": auth_type}
    if auth_type == "none":
        return normalized
    if auth_type == "basic":
        normalized["username"] = str(payload.get("username") or payload.get("user") or "")
        normalized["password"] = str(payload.get("password") or payload.get("pass") or "")
        return normalized
    if auth_type in {"bearer", "bootstrap_request"}:
        normalized["token_value"] = str(payload.get("token_value") or payload.get("token") or "")
        normalized["token_variable"] = str(payload.get("token_variable") or payload.get("variable") or "token")
        normalized["header_name"] = str(payload.get("header_name") or payload.get("header") or "Authorization")
        normalized["bearer_prefix"] = str(payload.get("bearer_prefix") or payload.get("prefix") or "Bearer")
        if auth_type == "bootstrap_request":
            normalized["bootstrap_request_id"] = _coerce_int(payload.get("bootstrap_request_id"))
            normalized["bootstrap_request_name"] = str(payload.get("bootstrap_request_name") or "")
            normalized["bootstrap_token_path"] = str(payload.get("bootstrap_token_path") or "")
        return normalized
    if auth_type == "api_key":
        normalized["api_key_name"] = str(payload.get("api_key_name") or payload.get("key") or payload.get("name") or "")
        normalized["api_key_in"] = str(payload.get("api_key_in") or payload.get("in") or payload.get("location") or "header")
        normalized["api_key_value"] = str(payload.get("api_key_value") or payload.get("value") or payload.get("token_value") or "")
        normalized["token_variable"] = str(payload.get("token_variable") or payload.get("variable") or "token")
        return normalized
    if auth_type == "cookie":
        cookie_name = str(payload.get("cookie_name") or payload.get("cookie") or payload.get("name") or "token")
        normalized["cookie_name"] = cookie_name
        normalized["token_value"] = str(payload.get("token_value") or payload.get("value") or "")
        normalized["token_variable"] = str(payload.get("token_variable") or payload.get("variable") or cookie_name)
        return normalized
    return normalized


def _normalize_transport_override(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    normalized = {
        "verify_ssl": _coerce_bool(payload.get("verify_ssl", payload.get("verify")), None),
        "proxy_url": str(payload.get("proxy_url") or payload.get("proxy") or ""),
        "client_cert": str(payload.get("client_cert") or payload.get("cert") or ""),
        "client_key": str(payload.get("client_key") or payload.get("key") or ""),
        "follow_redirects": _coerce_bool(payload.get("follow_redirects", payload.get("follow_redirect")), None),
        "retry_count": _coerce_int(payload.get("retry_count", payload.get("retries")), None),
        "retry_interval_ms": _coerce_int(payload.get("retry_interval_ms", payload.get("retry_interval")), None),
    }
    has_value = any(value not in (None, "", [], {}) for value in normalized.values())
    return normalized if has_value else {}


def _normalize_request_overrides(api_request: ApiRequest, overrides: Any) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        overrides = {}

    base_request_spec = serialize_request_spec(api_request)
    body_mode = str(overrides.get("body_mode") or overrides.get("body_type") or base_request_spec["body_mode"]).lower()
    if body_mode not in SUPPORTED_BODY_TYPES:
        body_mode = base_request_spec["body_mode"]

    normalized = {
        "method": str(overrides.get("method") or ""),
        "url": str(overrides.get("url") or ""),
        "headers": _normalize_named_items(overrides.get("headers")),
        "query": _normalize_named_items(overrides.get("query") or overrides.get("params")),
        "cookies": _normalize_named_items(overrides.get("cookies")),
        "form_fields": _normalize_named_items(overrides.get("form_fields")),
        "multipart_parts": _normalize_named_items(overrides.get("multipart_parts")),
        "files": _normalize_files(overrides.get("files")),
        "body_mode": body_mode,
        "body_json": _parse_json_object(overrides.get("body_json"), {}),
        "raw_text": str(overrides.get("raw_text") or ""),
        "xml_text": str(overrides.get("xml_text") or ""),
        "binary_base64": str(overrides.get("binary_base64") or ""),
        "graphql_query": str(overrides.get("graphql_query") or ""),
        "graphql_operation_name": str(overrides.get("graphql_operation_name") or ""),
        "graphql_variables": _parse_json_object(overrides.get("graphql_variables"), {}),
        "timeout_ms": _coerce_int(
            overrides.get("timeout_ms"),
            int(base_request_spec["timeout_ms"] or api_request.timeout_ms or 30000),
        ),
        "auth": _normalize_auth_override(overrides.get("auth")),
        "transport": _normalize_transport_override(overrides.get("transport")),
    }
    if overrides.get("body") not in (None, ""):
        if body_mode == "json":
            normalized["body_json"] = _parse_json_object(overrides.get("body"), normalized["body_json"])
        elif body_mode in {"form", "urlencoded"}:
            normalized["form_fields"] = _normalize_named_items(overrides.get("body"))
        elif body_mode == "multipart":
            normalized["multipart_parts"] = _normalize_named_items(overrides.get("body"))
        elif body_mode == "graphql":
            if isinstance(overrides.get("body"), dict):
                normalized["graphql_query"] = str(overrides["body"].get("query") or normalized["graphql_query"])
                normalized["graphql_operation_name"] = str(
                    overrides["body"].get("operationName") or normalized["graphql_operation_name"]
                )
                normalized["graphql_variables"] = _parse_json_object(
                    overrides["body"].get("variables"),
                    normalized["graphql_variables"],
                )
            else:
                normalized["graphql_query"] = str(overrides.get("body") or normalized["graphql_query"])
        elif body_mode == "raw":
            normalized["raw_text"] = str(overrides.get("body"))
        elif body_mode == "xml":
            normalized["xml_text"] = str(overrides.get("body"))
        elif body_mode == "binary":
            normalized["binary_base64"] = str(overrides.get("body"))
    return normalized


def _normalize_numeric_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _canonicalize_assertion(assertion: dict[str, Any]) -> dict[str, Any]:
    return {
        "assertion_type": str(assertion.get("assertion_type") or assertion.get("type") or ""),
        "target": str(assertion.get("target") or ""),
        "selector": str(assertion.get("selector") or assertion.get("path") or ""),
        "operator": str(assertion.get("operator") or "equals"),
        "expected_text": str(assertion.get("expected_text") or ""),
        "expected_number": _normalize_numeric_value(assertion.get("expected_number")),
        "expected_json": assertion.get("expected_json") or {},
        "min_value": _normalize_numeric_value(assertion.get("min_value")),
        "max_value": _normalize_numeric_value(assertion.get("max_value")),
        "schema_text": str(assertion.get("schema_text") or ""),
    }


def _canonicalize_named_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "value": item.get("value", ""),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return sorted(normalized, key=lambda entry: (entry["name"], str(entry["value"]), entry["enabled"]))


def _canonicalize_files(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        normalized.append(
            {
                "field_name": field_name,
                "source_type": str(item.get("source_type") or "path"),
                "file_path": str(item.get("file_path") or ""),
                "file_name": str(item.get("file_name") or ""),
                "content_type": str(item.get("content_type") or ""),
                "base64_content": str(item.get("base64_content") or ""),
                "enabled": bool(item.get("enabled", True)),
            }
        )
    return sorted(
        normalized,
        key=lambda entry: (
            entry["field_name"],
            entry["source_type"],
            entry["file_name"],
            entry["file_path"],
            entry["content_type"],
            entry["enabled"],
        ),
    )


def _merge_named_item_lists(base_items: list[dict[str, Any]], override_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered: list[str] = []
    for item in (base_items or []) + (override_items or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        if name not in merged:
            ordered.append(name)
            merged[name] = {"name": name}
        merged[name].update(item)
    return [merged[name] for name in ordered]


def _merge_file_items(base_items: list[dict[str, Any]], override_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    ordered: list[str] = []
    for item in (base_items or []) + (override_items or []):
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        key = f"{field_name}:{item.get('file_name') or item.get('file_path') or item.get('order', 0)}"
        if key not in merged:
            ordered.append(key)
            merged[key] = {"field_name": field_name}
        merged[key].update(item)
    return [merged[key] for key in ordered]


def _merge_config_dict(base_config: dict[str, Any], override_config: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base_config or {})
    for key, value in (override_config or {}).items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def _canonicalize_request_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_request_payload(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalize_request_payload(item) for item in value]
    return value


def _build_effective_request_signature(api_request: ApiRequest, overrides: dict[str, Any]) -> dict[str, Any]:
    base_request_spec = serialize_request_spec(api_request)
    normalized_overrides = _normalize_request_overrides(api_request, overrides)
    body_mode = str(normalized_overrides.get("body_mode") or base_request_spec.get("body_mode") or "none").lower()

    return {
        "method": str(normalized_overrides.get("method") or base_request_spec.get("method") or api_request.method).upper(),
        "url": str(normalized_overrides.get("url") or base_request_spec.get("url") or api_request.url),
        "headers": _canonicalize_named_items(
            _merge_named_item_lists(base_request_spec.get("headers") or [], normalized_overrides.get("headers") or [])
        ),
        "query": _canonicalize_named_items(
            _merge_named_item_lists(base_request_spec.get("query") or [], normalized_overrides.get("query") or [])
        ),
        "cookies": _canonicalize_named_items(
            _merge_named_item_lists(base_request_spec.get("cookies") or [], normalized_overrides.get("cookies") or [])
        ),
        "form_fields": _canonicalize_named_items(
            _merge_named_item_lists(base_request_spec.get("form_fields") or [], normalized_overrides.get("form_fields") or [])
        ),
        "multipart_parts": _canonicalize_named_items(
            _merge_named_item_lists(base_request_spec.get("multipart_parts") or [], normalized_overrides.get("multipart_parts") or [])
        ),
        "files": _canonicalize_files(_merge_file_items(base_request_spec.get("files") or [], normalized_overrides.get("files") or [])),
        "body_mode": body_mode,
        "body_json": _canonicalize_request_payload(
            (normalized_overrides.get("body_json") or base_request_spec.get("body_json") or {})
            if body_mode == "json"
            else {}
        ),
        "raw_text": str((normalized_overrides.get("raw_text") or base_request_spec.get("raw_text") or "") if body_mode == "raw" else ""),
        "xml_text": str((normalized_overrides.get("xml_text") or base_request_spec.get("xml_text") or "") if body_mode == "xml" else ""),
        "binary_base64": str(
            (normalized_overrides.get("binary_base64") or base_request_spec.get("binary_base64") or "")
            if body_mode == "binary"
            else ""
        ),
        "graphql_query": str(
            (normalized_overrides.get("graphql_query") or base_request_spec.get("graphql_query") or "")
            if body_mode == "graphql"
            else ""
        ),
        "graphql_operation_name": str(
            (normalized_overrides.get("graphql_operation_name") or base_request_spec.get("graphql_operation_name") or "")
            if body_mode == "graphql"
            else ""
        ),
        "graphql_variables": _canonicalize_request_payload(
            (normalized_overrides.get("graphql_variables") or base_request_spec.get("graphql_variables") or {})
            if body_mode == "graphql"
            else {}
        ),
        "timeout_ms": int(
            normalized_overrides.get("timeout_ms") or base_request_spec.get("timeout_ms") or api_request.timeout_ms or 30000
        ),
        "auth": _canonicalize_request_payload(
            _merge_config_dict(base_request_spec.get("auth") or {}, normalized_overrides.get("auth") or {})
        ),
        "transport": _canonicalize_request_payload(
            _merge_config_dict(base_request_spec.get("transport") or {}, normalized_overrides.get("transport") or {})
        ),
    }


def _canonicalize_request_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": str(overrides.get("method") or "").upper(),
        "url": str(overrides.get("url") or ""),
        "headers": _canonicalize_named_items(overrides.get("headers") or []),
        "query": _canonicalize_named_items(overrides.get("query") or []),
        "cookies": _canonicalize_named_items(overrides.get("cookies") or []),
        "form_fields": _canonicalize_named_items(overrides.get("form_fields") or []),
        "multipart_parts": _canonicalize_named_items(overrides.get("multipart_parts") or []),
        "files": _canonicalize_files(overrides.get("files") or []),
        "body_mode": str(overrides.get("body_mode") or "none").lower(),
        "body_json": overrides.get("body_json") if isinstance(overrides.get("body_json"), (dict, list)) else {},
        "raw_text": str(overrides.get("raw_text") or ""),
        "xml_text": str(overrides.get("xml_text") or ""),
        "binary_base64": str(overrides.get("binary_base64") or ""),
        "graphql_query": str(overrides.get("graphql_query") or ""),
        "graphql_operation_name": str(overrides.get("graphql_operation_name") or ""),
        "graphql_variables": overrides.get("graphql_variables") if isinstance(overrides.get("graphql_variables"), dict) else {},
        "timeout_ms": int(overrides.get("timeout_ms") or 0),
        "auth": overrides.get("auth") if isinstance(overrides.get("auth"), dict) else {},
        "transport": overrides.get("transport") if isinstance(overrides.get("transport"), dict) else {},
    }


def _collect_override_sections(api_request: ApiRequest, overrides: dict[str, Any]) -> list[str]:
    base_request_spec = serialize_request_spec(api_request)
    sections: list[str] = []

    if overrides.get("method") and str(overrides.get("method")).upper() != str(base_request_spec.get("method") or "").upper():
        sections.append("method")
    if overrides.get("url") and str(overrides.get("url")) != str(base_request_spec.get("url") or ""):
        sections.append("url")
    for bucket in ("headers", "query", "cookies", "form_fields", "multipart_parts", "files"):
        if overrides.get(bucket):
            sections.append(bucket)

    body_mode = str(overrides.get("body_mode") or "").lower()
    if body_mode and body_mode != str(base_request_spec.get("body_mode") or "").lower():
        sections.append("body_mode")
    if overrides.get("body_json"):
        sections.append("body_json")
    if overrides.get("raw_text"):
        sections.append("raw_text")
    if overrides.get("xml_text"):
        sections.append("xml_text")
    if overrides.get("binary_base64"):
        sections.append("binary_base64")
    if overrides.get("graphql_query") or overrides.get("graphql_variables"):
        sections.append("graphql")
    timeout_ms = overrides.get("timeout_ms")
    base_timeout = int(base_request_spec.get("timeout_ms") or api_request.timeout_ms or 30000)
    if timeout_ms not in (None, "", 0) and int(timeout_ms) != base_timeout:
        sections.append("timeout_ms")
    if overrides.get("auth"):
        sections.append("auth")
    if overrides.get("transport"):
        sections.append("transport")
    return list(dict.fromkeys(sections))


def _summarize_case_draft(api_request: ApiRequest, draft: GeneratedCaseDraft) -> dict[str, Any]:
    normalized_overrides = _canonicalize_request_overrides(draft.request_overrides or {})
    assertion_types = sorted(
        {
            str(item.get("assertion_type") or item.get("type") or "").strip()
            for item in draft.assertions
            if isinstance(item, dict) and str(item.get("assertion_type") or item.get("type") or "").strip()
        }
    )
    extractor_variables = [
        str(item.get("variable_name") or "").strip()
        for item in draft.extractors
        if isinstance(item, dict) and str(item.get("variable_name") or "").strip()
    ]
    return {
        "name": draft.name,
        "status": draft.status,
        "tags": list(draft.tags or []),
        "assertion_count": len(draft.assertions or []),
        "extractor_count": len(draft.extractors or []),
        "assertion_types": assertion_types,
        "extractor_variables": extractor_variables,
        "override_sections": _collect_override_sections(api_request, normalized_overrides),
        "body_mode": str(normalized_overrides.get("body_mode") or "none"),
    }


def _summarize_persisted_test_case(api_request: ApiRequest, test_case: ApiTestCase) -> dict[str, Any]:
    normalized_overrides = _canonicalize_request_overrides(serialize_test_case_override(test_case))
    assertion_specs = serialize_assertion_specs(test_case)
    extractor_specs = serialize_extractor_specs(test_case)
    assertion_types = sorted(
        {
            str(item.get("assertion_type") or item.get("type") or "").strip()
            for item in assertion_specs
            if isinstance(item, dict) and str(item.get("assertion_type") or item.get("type") or "").strip()
        }
    )
    extractor_variables = [
        str(item.get("variable_name") or "").strip()
        for item in extractor_specs
        if isinstance(item, dict) and str(item.get("variable_name") or "").strip()
    ]
    return {
        "name": str(test_case.name or ""),
        "status": str(test_case.status or ""),
        "tags": list(test_case.tags or []),
        "assertion_count": len(assertion_specs),
        "extractor_count": len(extractor_specs),
        "assertion_types": assertion_types,
        "extractor_variables": extractor_variables,
        "override_sections": _collect_override_sections(api_request, normalized_overrides),
        "body_mode": str(normalized_overrides.get("body_mode") or "none"),
    }


def summarize_persisted_test_cases(api_request: ApiRequest, test_cases: list[ApiTestCase]) -> list[dict[str, Any]]:
    return [_summarize_persisted_test_case(api_request, test_case) for test_case in test_cases]


def _summarize_case_drafts(api_request: ApiRequest, drafts: list[GeneratedCaseDraft]) -> list[dict[str, Any]]:
    return [_summarize_case_draft(api_request, draft) for draft in drafts]


def _attach_runtime_meta(
    result: AITestCaseGenerationResult,
    *,
    cache_hit: bool,
    cache_key: str | None,
    duration_ms: float,
    lock_wait_ms: float,
) -> AITestCaseGenerationResult:
    note = str(result.note or "").strip()
    meta_note = "本次命中 AI 用例缓存，未再次调用模型。" if cache_hit else f"AI 用例生成耗时约 {duration_ms:.0f} ms。"
    combined_note = f"{note} {meta_note}".strip() if note else meta_note
    return replace(
        result,
        note=combined_note,
        cache_hit=cache_hit,
        cache_key=cache_key,
        duration_ms=duration_ms,
        lock_wait_ms=lock_wait_ms,
    )


def _semantic_case_fingerprint(api_request: ApiRequest, assertions: list[dict[str, Any]], overrides: dict[str, Any]) -> str:
    signature = {
        "assertions": sorted(
            [_canonicalize_assertion(item) for item in assertions or [] if isinstance(item, dict)],
            key=lambda item: (
                item["assertion_type"],
                item["target"],
                item["selector"],
                item["operator"],
                json.dumps(item["expected_json"], ensure_ascii=False, sort_keys=True),
                item["expected_text"],
                str(item["expected_number"]),
                str(item["min_value"]),
                str(item["max_value"]),
                item["schema_text"],
            ),
        ),
        "effective_request": _build_effective_request_signature(api_request, overrides or {}),
    }
    return json.dumps(signature, ensure_ascii=False, sort_keys=True)


def _normalize_case_draft(
    api_request: ApiRequest,
    item: dict[str, Any],
    index: int,
    existing_names: set[str],
    existing_fingerprints: set[str],
) -> GeneratedCaseDraft | None:
    raw_name = str(item.get("name") or "").strip() or f"{api_request.name} - AI场景{index + 1}"
    name = raw_name[:160]
    unique_name = name
    suffix = 2
    while unique_name in existing_names:
        unique_name = f"{name[:150]}-{suffix}"
        suffix += 1
    existing_names.add(unique_name)

    raw_status = str(item.get("status") or "ready").strip().lower()
    status = raw_status if raw_status in SUPPORTED_CASE_STATUSES else "ready"
    tags = [str(tag).strip() for tag in (item.get("tags") or []) if str(tag).strip()]
    if "ai-generated" not in tags:
        tags.append("ai-generated")
    if api_request.method.lower() not in tags:
        tags.append(api_request.method.lower())

    fallback_assertions = serialize_assertion_specs(api_request) or [{"assertion_type": "status_code", "expected_number": 200}]
    assertions = _normalize_assertions(item.get("assertions"), fallback_assertions)
    extractors = _normalize_extractors(item.get("extractors"), [])
    overrides = _normalize_request_overrides(api_request, item.get("request_overrides"))
    fingerprint = _semantic_case_fingerprint(api_request, assertions, overrides)
    if fingerprint in existing_fingerprints:
        return None
    existing_fingerprints.add(fingerprint)

    return GeneratedCaseDraft(
        name=unique_name,
        description=str(item.get("description") or f"AI 生成的 {api_request.name} 测试场景")[:5000],
        status=status,
        tags=list(dict.fromkeys(tags)),
        assertions=assertions,
        extractors=extractors,
        request_overrides=overrides,
    )


def _build_fallback_cases(
    api_request: ApiRequest,
    existing_cases: list[ApiTestCase],
    *,
    count: int,
) -> list[GeneratedCaseDraft]:
    existing_names = {case.name for case in existing_cases}
    existing_fingerprints = {
        _semantic_case_fingerprint(api_request, serialize_assertion_specs(case), serialize_test_case_override(case))
        for case in existing_cases
    }
    base_assertions = serialize_assertion_specs(api_request) or [{"assertion_type": "status_code", "expected_number": 200}]

    templates = [
        {
            "name": f"{api_request.name} - 基础成功校验",
            "description": f"验证 {api_request.method} {api_request.url} 的基础可用性。",
            "tags": ["baseline", "positive"],
            "assertions": base_assertions,
            "extractors": [],
            "request_overrides": {},
        },
        {
            "name": f"{api_request.name} - 响应结构校验",
            "description": f"验证 {api_request.name} 的核心响应字段和断言配置。",
            "tags": ["response-check", "regression"],
            "assertions": base_assertions,
            "extractors": [],
            "request_overrides": {},
        },
        {
            "name": f"{api_request.name} - 回归稳定性校验",
            "description": f"用于回归验证 {api_request.name} 在当前环境下的稳定执行能力。",
            "tags": ["regression", "smoke"],
            "assertions": base_assertions,
            "extractors": [],
            "request_overrides": {},
        },
    ]

    drafts: list[GeneratedCaseDraft] = []
    for index, template in enumerate(templates[: max(1, count)]):
        draft = _normalize_case_draft(api_request, template, index, existing_names, existing_fingerprints)
        if draft:
            drafts.append(draft)
    return drafts


def _generate_test_case_drafts_with_ai_uncached(
    *,
    api_request: ApiRequest,
    user,
    existing_cases: list[ApiTestCase],
    mode: str,
    count: int,
    reference_context_json: str | None = None,
    historical_context_json: str | None = None,
) -> AITestCaseGenerationResult:
    active_config = LLMConfig.objects.filter(is_active=True).first()
    if not active_config:
        fallback_cases = _build_fallback_cases(api_request, existing_cases, count=count)
        return AITestCaseGenerationResult(
            used_ai=False,
            note="未检测到激活的 LLM 配置，已回退到模板生成测试用例。",
            cases=fallback_cases,
            prompt_name="API自动化用例生成",
            prompt_source="builtin_fallback",
            model_name=None,
        )

    prompt_template, prompt_source, prompt_name = _get_generation_prompt(user)
    generation_contract_json = _serialize_generation_contract()
    reference_context_json = reference_context_json or _serialize_generation_reference_context(api_request)
    historical_context_json = historical_context_json or _serialize_generation_history_context(api_request)
    formatted_prompt = _format_prompt(
        prompt_template,
        mode=mode,
        count=count,
        request_json=_serialize_request(api_request),
        existing_cases_json=_serialize_existing_cases(existing_cases),
        reference_context_json=reference_context_json,
        historical_context_json=historical_context_json,
        generation_contract_json=generation_contract_json,
    )
    if "${reference_context_json}" not in prompt_template and "{reference_context_json}" not in prompt_template:
        formatted_prompt = (
            f"{formatted_prompt}\n\n"
            "Project requirement and knowledge context (ranked references, use as hints and do not copy blindly):\n"
            f"{reference_context_json}"
        )
    if "${historical_context_json}" not in prompt_template and "{historical_context_json}" not in prompt_template:
        formatted_prompt = (
            f"{formatted_prompt}\n\n"
            "Historical execution context (recent failures and successes, use as hints and do not copy blindly):\n"
            f"{historical_context_json}"
        )
    if "${generation_contract_json}" not in prompt_template and "{generation_contract_json}" not in prompt_template:
        formatted_prompt = f"{formatted_prompt}\n\nStrict output contract:\n{generation_contract_json}"

    try:
        llm = create_llm_instance(active_config, temperature=0.2)
        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(
                    content=(
                        "你是专业的 API 自动化测试设计助手。"
                        "必须只返回合法 JSON，不能输出 Markdown 或解释文本。"
                    )
                ),
                HumanMessage(content=formatted_prompt),
            ],
        )
        payload = extract_json_from_response(getattr(response, "content", ""))
        if not isinstance(payload, dict):
            raise ValueError("AI 返回结果不是 JSON 对象")

        raw_cases = payload.get("cases") or []
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError("AI 未返回可用的测试用例列表")

        existing_names = {case.name for case in existing_cases}
        existing_fingerprints = {
            _semantic_case_fingerprint(api_request, serialize_assertion_specs(case), serialize_test_case_override(case))
            for case in existing_cases
        }
        drafts: list[GeneratedCaseDraft] = []
        for index, item in enumerate(raw_cases[: max(1, count)]):
            if not isinstance(item, dict):
                continue
            draft = _normalize_case_draft(api_request, item, index, existing_names, existing_fingerprints)
            if draft:
                drafts.append(draft)

        if not drafts:
            raise ValueError("AI 生成结果无法转换为可落库的测试用例")

        summary = str(payload.get("summary") or "").strip()
        return AITestCaseGenerationResult(
            used_ai=True,
            note=summary or f"已通过 AI 为接口 {api_request.name} 生成测试用例。",
            cases=drafts,
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API test case AI generation failed: %s", exc, exc_info=True)
        fallback_cases = _build_fallback_cases(api_request, existing_cases, count=count)
        return AITestCaseGenerationResult(
            used_ai=False,
            note=f"AI 生成测试用例失败，已回退到模板生成。失败原因: {exc}",
            cases=fallback_cases,
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )


def _ensure_case_summaries(api_request: ApiRequest, result: AITestCaseGenerationResult) -> AITestCaseGenerationResult:
    if result.case_summaries:
        return result
    return replace(result, case_summaries=_summarize_case_drafts(api_request, result.cases))


def generate_test_case_drafts_with_ai(
    *,
    api_request: ApiRequest,
    user,
    existing_cases: list[ApiTestCase],
    mode: str,
    count: int,
) -> AITestCaseGenerationResult:
    active_config = LLMConfig.objects.filter(is_active=True).first()
    if not active_config:
        return _ensure_case_summaries(
            api_request,
            _generate_test_case_drafts_with_ai_uncached(
                api_request=api_request,
                user=user,
                existing_cases=existing_cases,
                mode=mode,
                count=count,
            ),
        )

    prompt_template, prompt_source, prompt_name = _get_generation_prompt(user)
    generation_contract_json = _serialize_generation_contract()
    reference_context_json = _serialize_generation_reference_context(api_request)
    historical_context_json = _serialize_generation_history_context(api_request)
    cache_key = _build_case_generation_cache_key(
        api_request=api_request,
        existing_cases=existing_cases,
        mode=mode,
        count=count,
        prompt_template=prompt_template,
        prompt_source=prompt_source,
        prompt_name=prompt_name,
        generation_contract_json=generation_contract_json,
        reference_context_json=reference_context_json,
        historical_context_json=historical_context_json,
        model_name=active_config.name,
    )

    try:
        result, runtime_meta = run_ai_operation(
            user=user,
            feature="test_case_generation",
            cache_key=cache_key,
            cache_ttl_seconds=_get_case_generation_cache_ttl(),
            lock_timeout_seconds=_get_case_generation_lock_timeout(),
            lock_error_message="当前账号已有 AI 用例生成任务正在进行，请稍后重试。",
            compute=lambda: _generate_test_case_drafts_with_ai_uncached(
                api_request=api_request,
                user=user,
                existing_cases=existing_cases,
                mode=mode,
                count=count,
                reference_context_json=reference_context_json,
                historical_context_json=historical_context_json,
            ),
            should_cache=lambda item: bool(item.used_ai and item.cases),
        )
        return _attach_runtime_meta(
            _ensure_case_summaries(api_request, result),
            cache_hit=runtime_meta.cache_hit,
            cache_key=runtime_meta.cache_key,
            duration_ms=runtime_meta.duration_ms,
            lock_wait_ms=runtime_meta.lock_wait_ms,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API test case AI generation wrapper failed: %s", exc, exc_info=True)
        fallback_cases = _build_fallback_cases(api_request, existing_cases, count=count)
        return AITestCaseGenerationResult(
            used_ai=False,
            note=f"AI 用例生成调度失败，已回退到模板生成。失败原因: {exc}",
            cases=fallback_cases,
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
            case_summaries=_summarize_case_drafts(api_request, fallback_cases),
        )


def create_test_cases_from_drafts(
    *,
    api_request: ApiRequest,
    drafts: list[GeneratedCaseDraft],
    creator,
) -> list[ApiTestCase]:
    created_cases: list[ApiTestCase] = []
    for draft in drafts:
        script = build_parameterized_test_case_script(
            request_id=api_request.id,
            method=api_request.method,
            url=api_request.url,
            headers={},
            params={},
            body_type=api_request.body_type,
            body=api_request.body,
            timeout_ms=int(draft.request_overrides.get("timeout_ms") or api_request.timeout_ms or 30000),
            assertions=[],
            extractors=draft.extractors,
            request_override_spec=draft.request_overrides,
        )
        test_case = ApiTestCase.objects.create(
            project=api_request.collection.project,
            request=api_request,
            name=draft.name,
            description=draft.description,
            status=draft.status,
            tags=draft.tags,
            script=script,
            assertions=[],
            creator=creator,
        )
        apply_test_case_override_payload(test_case, draft.request_overrides)
        apply_test_case_assertions_and_extractors(
            test_case,
            assertion_payload=draft.assertions,
            extractor_payload=draft.extractors,
        )
        created_cases.append(test_case)
    return created_cases
