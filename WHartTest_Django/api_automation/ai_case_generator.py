from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from string import Template
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig
from prompts.models import UserPrompt

from .ai_parser import create_llm_instance, extract_json_from_response, safe_llm_invoke
from .document_import import HTTP_METHODS
from .generation import build_parameterized_test_case_script
from .models import ApiRequest, ApiTestCase

logger = logging.getLogger(__name__)

SUPPORTED_BODY_TYPES = {"none", "json", "form", "raw"}
SUPPORTED_CASE_STATUSES = {"draft", "ready", "disabled"}
SUPPORTED_ASSERTIONS = {"status_code", "body_contains", "json_path"}

DEFAULT_CASE_PROMPT = """你是 FlyTest 的资深 API 自动化测试设计专家。
请围绕给定接口生成结构化测试用例，要求如下：

1. 每个测试用例必须严格绑定当前接口，不能跨接口。
2. 优先覆盖：基础成功场景、核心业务校验、关键边界场景、常见异常场景。
3. 如果已有测试用例，请避免和现有名称、意图完全重复；在追加生成模式下尤其如此。
4. 断言只允许使用这三种类型：
   - status_code
   - body_contains
   - json_path
5. request_overrides 只返回相对当前接口需要覆盖的字段，可包含：
   - headers
   - params
   - body_type
   - body
   - timeout_ms
6. 结果必须只返回 JSON，不要输出 Markdown，不要解释。

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
        {"type": "status_code", "expected": 200},
        {"type": "json_path", "path": "code", "operator": "equals", "expected": 0}
      ],
      "request_overrides": {
        "headers": {},
        "params": {},
        "body_type": "json",
        "body": {},
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
"""


@dataclass
class GeneratedCaseDraft:
    name: str
    description: str
    status: str
    tags: list[str]
    assertions: list[dict[str, Any]]
    request_overrides: dict[str, Any]


@dataclass
class AITestCaseGenerationResult:
    used_ai: bool
    note: str
    cases: list[GeneratedCaseDraft]
    prompt_name: str | None = None
    prompt_source: str | None = None
    model_name: str | None = None


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
        "method": api_request.method,
        "url": api_request.url,
        "headers": api_request.headers or {},
        "params": api_request.params or {},
        "body_type": api_request.body_type,
        "body": api_request.body,
        "assertions": api_request.assertions or [],
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
            "assertions": case.assertions or [],
            "script": case.script or {},
        }
        for case in existing_cases
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_assertions(assertions: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(assertions, list):
        for item in assertions:
            if not isinstance(item, dict):
                continue
            assertion_type = str(item.get("type") or "").strip()
            if assertion_type not in SUPPORTED_ASSERTIONS:
                continue
            normalized_item: dict[str, Any] = {
                "type": assertion_type,
                "expected": item.get("expected"),
            }
            if assertion_type == "json_path":
                normalized_item["path"] = item.get("path")
                normalized_item["operator"] = item.get("operator") or "equals"
            normalized.append(normalized_item)
    return normalized or fallback or [{"type": "status_code", "expected": 200}]


def _normalize_request_overrides(api_request: ApiRequest, overrides: Any) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        overrides = {}

    headers = overrides.get("headers")
    params = overrides.get("params")
    body_type = str(overrides.get("body_type") or api_request.body_type).lower()
    if body_type not in SUPPORTED_BODY_TYPES:
        body_type = api_request.body_type

    normalized = {
        "headers": headers if isinstance(headers, dict) else {},
        "params": params if isinstance(params, dict) else {},
        "body_type": body_type,
        "body": overrides.get("body", api_request.body if body_type != "none" else {}),
        "timeout_ms": int(overrides.get("timeout_ms") or api_request.timeout_ms or 30000),
    }
    return normalized


def _normalize_case_draft(
    api_request: ApiRequest,
    item: dict[str, Any],
    index: int,
    existing_names: set[str],
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

    fallback_assertions = api_request.assertions or [{"type": "status_code", "expected": 200}]
    assertions = _normalize_assertions(item.get("assertions"), fallback_assertions)
    overrides = _normalize_request_overrides(api_request, item.get("request_overrides"))

    return GeneratedCaseDraft(
        name=unique_name,
        description=str(item.get("description") or f"AI 生成的 {api_request.name} 测试场景")[:5000],
        status=status,
        tags=list(dict.fromkeys(tags)),
        assertions=assertions,
        request_overrides=overrides,
    )


def _build_fallback_cases(
    api_request: ApiRequest,
    existing_cases: list[ApiTestCase],
    *,
    count: int,
) -> list[GeneratedCaseDraft]:
    existing_names = {case.name for case in existing_cases}
    base_assertions = api_request.assertions or [{"type": "status_code", "expected": 200}]

    templates = [
        {
            "name": f"{api_request.name} - 基础成功校验",
            "description": f"验证 {api_request.method} {api_request.url} 的基础可用性。",
            "tags": ["baseline", "positive"],
            "assertions": base_assertions,
            "request_overrides": {},
        },
        {
            "name": f"{api_request.name} - 响应结构校验",
            "description": f"验证 {api_request.name} 的核心响应字段和断言配置。",
            "tags": ["response-check", "regression"],
            "assertions": base_assertions,
            "request_overrides": {},
        },
        {
            "name": f"{api_request.name} - 回归稳定性校验",
            "description": f"用于回归验证 {api_request.name} 在当前环境下的稳定执行能力。",
            "tags": ["regression", "smoke"],
            "assertions": base_assertions,
            "request_overrides": {},
        },
    ]

    drafts: list[GeneratedCaseDraft] = []
    for index, template in enumerate(templates[: max(1, count)]):
        draft = _normalize_case_draft(api_request, template, index, existing_names)
        if draft:
            drafts.append(draft)
    return drafts


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
    formatted_prompt = _format_prompt(
        prompt_template,
        mode=mode,
        count=count,
        request_json=_serialize_request(api_request),
        existing_cases_json=_serialize_existing_cases(existing_cases),
    )

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
        drafts: list[GeneratedCaseDraft] = []
        for index, item in enumerate(raw_cases[: max(1, count)]):
            if not isinstance(item, dict):
                continue
            draft = _normalize_case_draft(api_request, item, index, existing_names)
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
            headers=draft.request_overrides.get("headers") or {},
            params=draft.request_overrides.get("params") or {},
            body_type=draft.request_overrides.get("body_type") or api_request.body_type,
            body=draft.request_overrides.get("body", api_request.body),
            timeout_ms=int(draft.request_overrides.get("timeout_ms") or api_request.timeout_ms or 30000),
            assertions=draft.assertions,
        )
        created_cases.append(
            ApiTestCase.objects.create(
                project=api_request.collection.project,
                request=api_request,
                name=draft.name,
                description=draft.description,
                status=draft.status,
                tags=draft.tags,
                script=script,
                assertions=draft.assertions,
                creator=creator,
            )
        )
    return created_cases
