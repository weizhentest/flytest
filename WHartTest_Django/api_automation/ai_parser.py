from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langgraph_integration.models import LLMConfig
from prompts.models import PromptType, UserPrompt
from prompts.services import get_default_prompts

from .document_import import HTTP_METHODS, ParsedRequestData, load_document_content_for_ai

logger = logging.getLogger(__name__)

AI_SUPPORTED_ASSERTIONS = {"status_code", "body_contains", "json_path"}
DEFAULT_AI_NOTE = "AI 增强解析未生效，已回退到规则解析结果。"


@dataclass
class AIEnhancementResult:
    requested: bool
    used: bool
    note: str
    prompt_source: str | None = None
    prompt_name: str | None = None
    model_name: str | None = None
    requests: list[ParsedRequestData] | None = None


def create_llm_instance(active_config: LLMConfig, temperature: float = 0.1):
    provider = (getattr(active_config, "provider", None) or "openai_compatible").strip()
    model_identifier = active_config.name or "gpt-3.5-turbo"
    request_timeout = getattr(active_config, "request_timeout", None) or 120
    max_retries = getattr(active_config, "max_retries", None) or 3
    base_url = (active_config.api_url or "").strip() or None
    api_key = (active_config.api_key or "").strip()

    if provider == "qwen":
        from langchain_qwq import ChatQwen

        llm_kwargs = {
            "model": model_identifier,
            "temperature": temperature,
            "timeout": request_timeout,
            "max_retries": max_retries,
        }
        if api_key:
            llm_kwargs["api_key"] = api_key
        if base_url:
            llm_kwargs["base_url"] = base_url
        return ChatQwen(**llm_kwargs)

    return ChatOpenAI(
        model=model_identifier,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
        timeout=request_timeout,
        max_retries=max_retries,
    )


def format_prompt_template(template: str, **kwargs) -> str:
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", str(value))

    try:
        result = Template(result).safe_substitute(**kwargs)
    except Exception:
        pass

    return result


def extract_json_from_response(content: str) -> dict[str, Any] | list[Any] | None:
    if not content:
        return None

    content = content.strip()

    json_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(content[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

    first_bracket = content.find("[")
    last_bracket = content.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(content[first_bracket : last_bracket + 1])
        except json.JSONDecodeError:
            pass

    return None


def get_default_prompt_by_type(prompt_type: str) -> dict[str, Any] | None:
    for prompt in get_default_prompts():
        if prompt.get("prompt_type") == prompt_type:
            return prompt
    return None


def get_api_automation_prompt(user) -> tuple[str | None, str | None, str | None]:
    if user:
        user_prompt = UserPrompt.get_user_prompt_by_type(user, PromptType.API_AUTOMATION_PARSING)
        if user_prompt:
            return user_prompt.content, "user_prompt", user_prompt.name

    default_prompt = get_default_prompt_by_type(PromptType.API_AUTOMATION_PARSING)
    if default_prompt:
        return default_prompt.get("content"), "builtin_default", default_prompt.get("name")

    return None, None, None


def safe_llm_invoke(llm, messages, max_retries: int = 3):
    last_error = None
    for _ in range(max_retries):
        try:
            response = llm.invoke(messages)
            if response and getattr(response, "content", None):
                return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("API automation AI invoke failed: %s", exc)
            continue
    raise last_error or RuntimeError("LLM returned empty content")


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _normalized_request_key(method: str, url: str) -> tuple[str, str]:
    return method.upper().strip(), url.strip()


def _merge_value(current: Any, fallback: Any) -> Any:
    if current in (None, "", [], {}):
        return fallback
    return current


def _normalize_assertions(assertions: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(assertions, list):
        for item in assertions:
            if not isinstance(item, dict):
                continue
            assertion_type = str(item.get("type") or "").strip()
            if assertion_type not in AI_SUPPORTED_ASSERTIONS:
                continue
            normalized_item = {
                "type": assertion_type,
                "expected": item.get("expected"),
            }
            if assertion_type == "json_path":
                normalized_item["path"] = item.get("path")
                normalized_item["operator"] = item.get("operator") or "equals"
            normalized.append(normalized_item)

    return normalized or fallback or [{"type": "status_code", "expected": 200}]


def _normalize_ai_request(item: dict[str, Any], fallback: ParsedRequestData | None = None) -> ParsedRequestData | None:
    method = str(item.get("method") or (fallback.method if fallback else "")).upper().strip()
    url = str(item.get("url") or (fallback.url if fallback else "")).strip()
    if method not in HTTP_METHODS or not url:
        return None

    body_type = str(item.get("body_type") or (fallback.body_type if fallback else "none")).strip().lower()
    if body_type not in {"none", "json", "form", "raw"}:
        body_type = fallback.body_type if fallback else "none"

    fallback_headers = fallback.headers if fallback else {}
    fallback_params = fallback.params if fallback else {}
    fallback_body = fallback.body if fallback else {}
    fallback_assertions = fallback.assertions if fallback else [{"type": "status_code", "expected": 200}]

    headers = item.get("headers")
    params = item.get("params")
    body = item.get("body")

    return ParsedRequestData(
        name=str(_merge_value(item.get("name"), fallback.name if fallback else f"{method} {url}"))[:120],
        method=method,
        url=url,
        description=str(_merge_value(item.get("description"), fallback.description if fallback else ""))[:5000],
        headers=headers if isinstance(headers, dict) else fallback_headers,
        params=params if isinstance(params, dict) else fallback_params,
        body_type=body_type,
        body=_merge_value(body, fallback_body),
        assertions=_normalize_assertions(item.get("assertions"), fallback_assertions),
        collection_name=(
            str(item.get("collection_name")).strip()
            if item.get("collection_name") not in (None, "")
            else (fallback.collection_name if fallback else None)
        ),
    )


def _serialize_requests_for_prompt(parsed_requests: list[ParsedRequestData]) -> str:
    return json.dumps(
        [
            {
                "name": item.name,
                "collection_name": item.collection_name,
                "method": item.method,
                "url": item.url,
                "description": item.description,
                "headers": item.headers,
                "params": item.params,
                "body_type": item.body_type,
                "body": item.body,
                "assertions": item.assertions,
            }
            for item in parsed_requests
        ],
        ensure_ascii=False,
        indent=2,
    )


def _merge_ai_requests(
    base_requests: list[ParsedRequestData],
    ai_payload: dict[str, Any] | list[Any],
) -> list[ParsedRequestData]:
    if isinstance(ai_payload, dict):
        ai_items = ai_payload.get("requests") or []
    elif isinstance(ai_payload, list):
        ai_items = ai_payload
    else:
        ai_items = []

    base_map = {_normalized_request_key(item.method, item.url): item for item in base_requests}
    merged_map = dict(base_map)

    for ai_item in ai_items:
        if not isinstance(ai_item, dict):
            continue
        method = str(ai_item.get("method") or "").upper().strip()
        url = str(ai_item.get("url") or "").strip()
        key = _normalized_request_key(method, url) if method and url else None
        fallback = base_map.get(key) if key else None
        normalized = _normalize_ai_request(ai_item, fallback=fallback)
        if not normalized:
            continue
        merged_map[_normalized_request_key(normalized.method, normalized.url)] = normalized

    return list(merged_map.values()) or base_requests


def enhance_import_result_with_ai(
    *,
    file_path: str,
    user,
    source_type: str,
    base_requests: list[ParsedRequestData],
) -> AIEnhancementResult:
    active_config = LLMConfig.objects.filter(is_active=True).first()
    if not active_config:
        return AIEnhancementResult(
            requested=True,
            used=False,
            note="未检测到系统设置中的激活 LLM 配置，已回退到规则解析结果。",
            model_name=None,
            requests=base_requests,
        )

    prompt_template, prompt_source, prompt_name = get_api_automation_prompt(user)
    if not prompt_template:
        return AIEnhancementResult(
            requested=True,
            used=False,
            note="未找到 API 自动化解析提示词，已回退到规则解析结果。",
            prompt_source=prompt_source,
            prompt_name=prompt_name,
            model_name=active_config.name,
            requests=base_requests,
        )

    try:
        llm = create_llm_instance(active_config, temperature=0.1)
        document_content, content_source_type, marker_used = load_document_content_for_ai(file_path)
        document_content, truncated_document = _truncate_text(document_content, 50000)
        preparsed_requests_json, truncated_preparsed = _truncate_text(_serialize_requests_for_prompt(base_requests), 15000)

        formatted_prompt = format_prompt_template(
            prompt_template,
            document_content=document_content,
            source_type=content_source_type or source_type,
            file_name=Path(file_path).name,
            marker_used=marker_used,
            preparsed_requests_json=preparsed_requests_json,
        )

        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(
                    content=(
                        "你是专业的 API 自动化测试分析助手。"
                        "你必须只返回合法 JSON，不要输出 Markdown，不要解释。"
                    )
                ),
                HumanMessage(content=formatted_prompt),
            ],
        )
        payload = extract_json_from_response(getattr(response, "content", ""))
        if payload is None:
            return AIEnhancementResult(
                requested=True,
                used=False,
                note="AI 返回结果无法解析为 JSON，已回退到规则解析结果。",
                prompt_source=prompt_source,
                prompt_name=prompt_name,
                model_name=active_config.name,
                requests=base_requests,
            )

        merged_requests = _merge_ai_requests(base_requests, payload)
        notes: list[str] = ["已应用 AI 增强解析。"]
        if truncated_document:
            notes.append("文档内容过长，已截断后送入模型。")
        if truncated_preparsed:
            notes.append("预解析结果过长，已截断后送入模型。")
        if isinstance(payload, dict) and payload.get("summary"):
            notes.append(str(payload["summary"]).strip())

        return AIEnhancementResult(
            requested=True,
            used=True,
            note=" ".join(notes),
            prompt_source=prompt_source,
            prompt_name=prompt_name,
            model_name=active_config.name,
            requests=merged_requests,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API automation AI enhancement failed: %s", exc, exc_info=True)
        return AIEnhancementResult(
            requested=True,
            used=False,
            note=f"{DEFAULT_AI_NOTE} 失败原因: {exc}",
            prompt_source=prompt_source,
            prompt_name=prompt_name,
            model_name=active_config.name,
            requests=base_requests,
        )
