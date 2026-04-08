from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from string import Template
from types import SimpleNamespace
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langgraph_integration.models import LLMConfig
from prompts.models import PromptType, UserPrompt
from prompts.services import get_default_prompts

from .ai_runtime import build_ai_cache_key, run_ai_operation, stable_digest
from .document_import import HTTP_METHODS, ParsedRequestData, load_document_content_for_ai

logger = logging.getLogger(__name__)

AI_SUPPORTED_ASSERTIONS = {"status_code", "body_contains", "json_path"}
DEFAULT_AI_CHUNK_MAX_WORKERS = 1
DEFAULT_AI_RETRY_BASE_DELAY_SECONDS = 1.5
DEFAULT_AI_PROVIDER_MAX_RETRIES = 0
DEFAULT_AI_USER_LOCK_TIMEOUT_SECONDS = 45
DEFAULT_AI_DOCUMENT_MAX_CHARS = 8000
DEFAULT_AI_PREPARSED_REQUESTS_MAX_CHARS = 3000
DEFAULT_AI_TIMEOUT_SPLIT_MIN_CHARS = 2000
DEFAULT_AI_TIMEOUT_SPLIT_MAX_DEPTH = 2
DEFAULT_AI_ENHANCEMENT_CACHE_TTL_SECONDS = 1800
DEFAULT_AI_NOTE = "AI 增强解析未生效，已回退到规则解析结果。"


def _ensure_not_cancelled(cancel_callback):
    if cancel_callback and cancel_callback():
        raise RuntimeError("文档解析已手动停止")


@dataclass
class AIEnhancementResult:
    requested: bool
    used: bool
    note: str
    prompt_source: str | None = None
    prompt_name: str | None = None
    model_name: str | None = None
    requests: list[ParsedRequestData] | None = None
    cache_hit: bool = False
    cache_key: str | None = None
    duration_ms: float | None = None
    lock_wait_ms: float | None = None


def get_import_ai_compatibility_status(*, user) -> dict[str, Any]:
    active_config = LLMConfig.objects.filter(is_active=True).first()
    if not active_config:
        return {
            "compatible": False,
            "issue_code": "llm_not_configured",
            "level": "warning",
            "title": "未检测到激活模型配置",
            "message": "当前未检测到激活的大模型配置，API 文档导入将回退到规则解析。",
            "action_hint": "请先到“系统设置 > AI大模型配置”中激活一套可用模型。",
            "model_name": None,
            "prompt_source": None,
            "prompt_name": None,
        }

    prompt_template, prompt_source, prompt_name = get_api_automation_prompt(user)
    if not prompt_template:
        return {
            "compatible": False,
            "issue_code": "prompt_missing",
            "level": "warning",
            "title": "未找到解析提示词",
            "message": "当前未找到 API 自动化解析提示词，文档导入将回退到规则解析。",
            "action_hint": "请到“提示词管理”中检查 API 自动化解析提示词是否存在。",
            "model_name": active_config.name,
            "prompt_source": prompt_source,
            "prompt_name": prompt_name,
        }

    cache_key = build_ai_cache_key(
        "document_import_compatibility",
        {
            "config_id": active_config.id,
            "config_updated_at": getattr(active_config, "updated_at", None).isoformat()
            if getattr(active_config, "updated_at", None)
            else None,
            "model_name": active_config.name,
            "api_url": active_config.api_url,
            "prompt_digest": stable_digest(prompt_template),
        },
    )

    def _compute_status() -> dict[str, Any]:
        compatibility_error = _probe_openai_compatible_text_response(active_config)
        if compatibility_error is not None:
            return {
                "compatible": False,
                "issue_code": "gateway_incompatible_empty_content",
                "level": "warning",
                "title": "当前 AI 网关未返回正文",
                "message": f"当前激活模型 {active_config.name} 调用成功但未返回可解析正文，API 文档导入会回退到规则解析。",
                "action_hint": "请在“系统设置 > AI大模型配置”中切换到能正常返回正文的模型或网关。",
                "model_name": active_config.name,
                "prompt_source": prompt_source,
                "prompt_name": prompt_name,
            }

        return {
            "compatible": True,
            "issue_code": "compatible",
            "level": "success",
            "title": "当前 AI 增强解析可用",
            "message": f"当前激活模型 {active_config.name} 可用于 API 文档导入的 AI 增强解析。",
            "action_hint": None,
            "model_name": active_config.name,
            "prompt_source": prompt_source,
            "prompt_name": prompt_name,
        }

    status_payload, runtime_meta = run_ai_operation(
        user=user,
        feature="document_import_compatibility",
        cache_key=cache_key,
        cache_ttl_seconds=300,
        lock_timeout_seconds=15,
        lock_error_message="当前账号已有 API 导入兼容性检测任务正在进行，请稍后重试。",
        compute=_compute_status,
    )
    status_payload["cache_hit"] = runtime_meta.cache_hit
    status_payload["duration_ms"] = runtime_meta.duration_ms
    return status_payload


def create_llm_instance(active_config: LLMConfig, temperature: float = 0.1):
    provider = (getattr(active_config, "provider", None) or "openai_compatible").strip()
    model_identifier = active_config.name or "gpt-3.5-turbo"
    request_timeout = getattr(active_config, "request_timeout", None) or 120
    configured_max_retries = getattr(active_config, "max_retries", None)
    provider_retry_cap = configured_max_retries if configured_max_retries is not None else 5
    max_retries = _read_int_env(
        "API_AUTOMATION_AI_PROVIDER_MAX_RETRIES",
        DEFAULT_AI_PROVIDER_MAX_RETRIES,
        minimum=0,
        maximum=max(0, provider_retry_cap),
    )
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


def _read_int_env(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
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


def _exception_text(exc: Exception) -> str:
    return str(exc or "")


def _is_rate_limit_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    return (
        "429" in text
        or "rate_limit" in text
        or "too many requests" in text
        or "璇锋眰杩囧" in text
        or "闄愭祦" in text
    )


def _is_concurrent_request_limit_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    return (
        "concurrent_request_limit_exceeded" in text
        or "骞惰璇锋眰杩囧" in text
        or "concurrent request" in text
        or "parallel request" in text
    )


def _is_timeout_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    return (
        "request timed out" in text
        or "read operation timed out" in text
        or "readtimeout" in text
        or "apitimeouterror" in text
        or "timeout" in text
        or "超时" in text
    )


def _is_connection_error(exc: Exception) -> bool:
    text = _exception_text(exc).lower()
    return (
        "connection error" in text
        or "connect error" in text
        or "connection reset" in text
        or "connection aborted" in text
        or "connection refused" in text
        or "server disconnected" in text
        or "remoteprotocolerror" in text
        or "network error" in text
        or "temporarily unavailable" in text
    )


def _build_retry_delay(attempt: int) -> float:
    raw_value = (os.environ.get("API_AUTOMATION_AI_RETRY_BASE_DELAY_SECONDS") or "").strip()
    try:
        base_delay = float(raw_value) if raw_value else DEFAULT_AI_RETRY_BASE_DELAY_SECONDS
    except ValueError:
        base_delay = DEFAULT_AI_RETRY_BASE_DELAY_SECONDS
    return min(base_delay * (2**attempt), 8.0)


def _get_chunk_max_workers(chunk_count: int) -> int:
    configured_workers = _read_int_env(
        "API_AUTOMATION_AI_CHUNK_MAX_WORKERS",
        DEFAULT_AI_CHUNK_MAX_WORKERS,
        minimum=1,
        maximum=10,
    )
    return max(1, min(chunk_count, configured_workers))


def _get_document_chunk_size() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_DOCUMENT_MAX_CHARS",
        DEFAULT_AI_DOCUMENT_MAX_CHARS,
        minimum=2000,
        maximum=12000,
    )


def _get_preparsed_requests_limit() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_PREPARSED_REQUESTS_MAX_CHARS",
        DEFAULT_AI_PREPARSED_REQUESTS_MAX_CHARS,
        minimum=1000,
        maximum=6000,
    )


def _get_timeout_split_min_chars() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_TIMEOUT_SPLIT_MIN_CHARS",
        DEFAULT_AI_TIMEOUT_SPLIT_MIN_CHARS,
        minimum=1000,
        maximum=8000,
    )


def _get_timeout_split_max_depth() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_TIMEOUT_SPLIT_MAX_DEPTH",
        DEFAULT_AI_TIMEOUT_SPLIT_MAX_DEPTH,
        minimum=0,
        maximum=4,
    )


def _get_ai_enhancement_cache_ttl() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_ENHANCEMENT_CACHE_TTL_SECONDS",
        DEFAULT_AI_ENHANCEMENT_CACHE_TTL_SECONDS,
        minimum=0,
        maximum=24 * 60 * 60,
    )


def _serialize_parsed_request_for_cache(item: ParsedRequestData) -> dict[str, Any]:
    request_spec = item.request_spec if isinstance(item.request_spec, dict) else {}
    return {
        "name": item.name,
        "method": item.method,
        "url": item.url,
        "description": item.description,
        "headers": item.headers or {},
        "params": item.params or {},
        "body_type": item.body_type,
        "body": item.body,
        "assertions": item.assertions or [],
        "request_spec": request_spec,
        "assertion_specs": item.assertion_specs or [],
        "extractor_specs": item.extractor_specs or [],
        "collection_name": item.collection_name,
    }


def _build_ai_enhancement_cache_key(
    *,
    document_content: str,
    source_type: str,
    content_source_type: str,
    marker_used: bool,
    prompt_template: str,
    model_name: str,
    base_requests: list[ParsedRequestData],
) -> str:
    return build_ai_cache_key(
        "document_import_enhancement",
        {
            "document_digest": stable_digest(document_content),
            "source_type": source_type,
            "content_source_type": content_source_type,
            "marker_used": marker_used,
            "prompt_digest": stable_digest(prompt_template),
            "model_name": model_name,
            "base_requests": [_serialize_parsed_request_for_cache(item) for item in base_requests],
        },
    )


def _attach_runtime_meta(result: AIEnhancementResult, *, cache_hit: bool, cache_key: str | None, duration_ms: float, lock_wait_ms: float) -> AIEnhancementResult:
    note = str(result.note or "").strip()
    meta_note = "本次命中 AI 解析缓存，未再次调用模型。" if cache_hit else f"AI 解析耗时约 {duration_ms:.0f} ms。"
    combined_note = f"{note} {meta_note}".strip() if note else meta_note
    return replace(
        result,
        note=combined_note,
        cache_hit=cache_hit,
        cache_key=cache_key,
        duration_ms=duration_ms,
        lock_wait_ms=lock_wait_ms,
    )


def _build_ai_failure_note(exc: Exception, active_config: LLMConfig | None = None) -> str:
    exc_text = _exception_text(exc)
    config_label = ""
    if active_config:
        endpoint = (getattr(active_config, "api_url", "") or "").strip()
        if endpoint:
            config_label = f"当前激活模型 {active_config.name}（{endpoint}）"
        else:
            config_label = f"当前激活模型 {active_config.name}"

    if _is_concurrent_request_limit_error(exc):
        return (
            f"{DEFAULT_AI_NOTE} 失败原因: AI 网关触发并发限流"
            "（429 concurrent_request_limit_exceeded），系统在退避重试后仍未成功，"
            "已自动回退到规则解析。"
        )
    if "当前账号已有 API 文档 AI 解析任务正在进行" in _exception_text(exc):
        return f"{DEFAULT_AI_NOTE} 失败原因: {exc}"
    if _is_timeout_error(exc):
        return (
            f"{DEFAULT_AI_NOTE} 失败原因: AI 请求超时。"
            "系统已尝试缩小文档分片并重试，但仍未在时限内完成，已自动回退到规则解析。"
        )
    if _is_rate_limit_error(exc):
        return f"{DEFAULT_AI_NOTE} 失败原因: AI 网关返回限流（429），系统在退避重试后仍未成功，已自动回退到规则解析。"
    if _is_connection_error(exc):
        return (
            f"{DEFAULT_AI_NOTE} 失败原因: AI 网关连接异常（{exc}）。"
            "系统已自动重试并尝试缩小文档分片，但仍未成功，已回退到规则解析。"
        )
    if "LLM returned empty content" in exc_text:
        if config_label:
            return (
                f"{DEFAULT_AI_NOTE} 失败原因: {config_label} 调用成功但未返回可解析正文。"
                f" 原始信息: {exc_text}。这通常说明当前网关的 OpenAI 兼容性不足，"
                "请切换到能正常返回 message.content 的模型或网关后重试。"
            )
        return (
            f"{DEFAULT_AI_NOTE} 失败原因: AI 模型调用成功但未返回可解析正文。"
            f" 原始信息: {exc_text}。这通常说明当前网关的 OpenAI 兼容性不足，"
            "请切换到能正常返回 message.content 的模型或网关后重试。"
        )
    return f"{DEFAULT_AI_NOTE} 失败原因: {exc}"


def _build_openai_compatible_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return _extract_text_from_content(message.get("content"))


def _extract_text_from_content(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("content") or "").strip()
            else:
                text = str(
                    getattr(item, "text", "") or getattr(item, "content", "")
                ).strip()
            if text:
                chunks.append(text)
        return "\n".join(chunks).strip()

    if isinstance(content, dict):
        direct_text = str(content.get("text") or content.get("content") or "").strip()
        if direct_text:
            return direct_text
        nested_parts = content.get("parts") or content.get("items")
        if isinstance(nested_parts, list):
            return _extract_text_from_content(nested_parts)
        return ""

    return str(
        getattr(content, "text", "") or getattr(content, "content", "") or ""
    ).strip()


def _extract_llm_response_text(response) -> str:
    if response is None:
        return ""

    response_text = _extract_text_from_content(getattr(response, "content", None))
    if response_text:
        return response_text

    additional_kwargs = getattr(response, "additional_kwargs", {}) or {}
    for key in ("content", "text", "output_text", "reasoning_content"):
        response_text = _extract_text_from_content(additional_kwargs.get(key))
        if response_text:
            return response_text

    return _extract_text_from_content(getattr(response, "text", None))


def _extract_llm_token_usage(response) -> dict[str, Any]:
    response_metadata = getattr(response, "response_metadata", {}) or {}
    token_usage = response_metadata.get("token_usage", {}) or {}
    usage_metadata = getattr(response, "usage_metadata", {}) or {}
    return {
        "prompt_tokens": (
            token_usage.get("prompt_tokens")
            or usage_metadata.get("input_tokens")
            or 0
        ),
        "completion_tokens": (
            token_usage.get("completion_tokens")
            or usage_metadata.get("output_tokens")
            or 0
        ),
        "total_tokens": (
            token_usage.get("total_tokens")
            or usage_metadata.get("total_tokens")
            or 0
        ),
        "finish_reason": response_metadata.get("finish_reason") or "",
    }


def _build_empty_llm_response_error(response) -> RuntimeError:
    usage = _extract_llm_token_usage(response)
    detail_parts = []
    if usage.get("finish_reason"):
        detail_parts.append(f"finish_reason={usage['finish_reason']}")
    if usage.get("completion_tokens"):
        detail_parts.append(f"completion_tokens={usage['completion_tokens']}")
    if usage.get("total_tokens"):
        detail_parts.append(f"total_tokens={usage['total_tokens']}")

    if detail_parts:
        return RuntimeError(f"LLM returned empty content ({', '.join(detail_parts)})")
    return RuntimeError("LLM returned empty content")


def _probe_openai_compatible_text_response(active_config: LLMConfig) -> RuntimeError | None:
    provider = (getattr(active_config, "provider", None) or "openai_compatible").strip()
    if provider != "openai_compatible":
        return None

    api_url = (getattr(active_config, "api_url", "") or "").rstrip("/")
    api_key = (getattr(active_config, "api_key", "") or "").strip()
    model_name = getattr(active_config, "name", "") or "gpt-3.5-turbo"
    if not api_url:
        return None

    headers = _build_openai_compatible_headers(api_key)
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "你是一个有帮助的助手。"},
            {"role": "user", "content": "请只回答：你好"},
        ],
        "temperature": 0.1,
    }

    try:
        response = httpx.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("API automation AI compatibility probe failed: %s", exc)
        return None

    response_text = _extract_chat_completion_text(data)
    if response_text:
        return None

    usage = data.get("usage", {}) or {}
    finish_reason = ((data.get("choices") or [{}])[0].get("finish_reason") or "")
    detail_parts = []
    if finish_reason:
        detail_parts.append(f"finish_reason={finish_reason}")
    if usage.get("completion_tokens"):
        detail_parts.append(f"completion_tokens={usage.get('completion_tokens')}")
    if usage.get("total_tokens"):
        detail_parts.append(f"total_tokens={usage.get('total_tokens')}")
    if detail_parts:
        return RuntimeError(f"LLM returned empty content ({', '.join(detail_parts)})")
    return RuntimeError("LLM returned empty content")


def safe_llm_invoke(llm, messages, max_retries: int = 4):
    last_error = None
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            response_text = _extract_llm_response_text(response)
            if response_text:
                return SimpleNamespace(
                    content=response_text,
                    response_metadata=getattr(response, "response_metadata", {}) or {},
                    usage_metadata=getattr(response, "usage_metadata", {}) or {},
                    additional_kwargs=getattr(response, "additional_kwargs", {}) or {},
                    raw_response=response,
                )
            last_error = _build_empty_llm_response_error(response)
            logger.warning("API automation AI invoke returned empty content (%s/%s)", attempt + 1, max_retries)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("API automation AI invoke failed: %s", exc)
            if "timed out" in str(exc).lower():
                break

        if attempt >= max_retries - 1:
            break

        use_backoff_retry = _is_rate_limit_error(last_error) or _is_connection_error(last_error)
        retry_delay = _build_retry_delay(attempt) if use_backoff_retry else min(float(attempt + 1), 2.0)
        if _is_rate_limit_error(last_error):
            logger.warning(
                "API automation AI invoke hit rate limit, retrying in %.1fs (%s/%s)",
                retry_delay,
                attempt + 1,
                max_retries,
            )
        elif _is_connection_error(last_error):
            logger.warning(
                "API automation AI invoke hit connection error, retrying in %.1fs (%s/%s)",
                retry_delay,
                attempt + 1,
                max_retries,
            )
        time.sleep(retry_delay)
    raise last_error or RuntimeError("LLM returned empty content")


def _truncate_text(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    return value[:limit], True


def _split_document_for_ai(document_content: str, max_chars: int | None = None) -> list[str]:
    max_chars = max_chars or _get_document_chunk_size()
    if len(document_content) <= max_chars:
        return [document_content]

    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n", document_content) if segment.strip()]
    if not paragraphs:
        return [document_content[:max_chars]]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        piece = paragraph if len(paragraph) <= max_chars else paragraph[:max_chars]
        projected_length = current_length + len(piece) + (2 if current else 0)
        if current and projected_length > max_chars:
            chunks.append("\n\n".join(current))
            current = [piece]
            current_length = len(piece)
            continue
        current.append(piece)
        current_length = projected_length

    if current:
        chunks.append("\n\n".join(current))

    return chunks or [document_content[:max_chars]]


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
        separators=(",", ":"),
    )


def _select_relevant_requests(chunk_content: str, base_requests: list[ParsedRequestData], limit: int = 12) -> list[ParsedRequestData]:
    if not base_requests:
        return []

    chunk_lower = chunk_content.lower()
    matched: list[ParsedRequestData] = []
    for item in base_requests:
        identifiers = [item.url.lower(), item.name.lower()]
        if any(identifier and identifier in chunk_lower for identifier in identifiers):
            matched.append(item)
        if len(matched) >= limit:
            break
    return matched or base_requests[:limit]


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


def _invoke_ai_for_chunk(
    *,
    active_config: LLMConfig,
    prompt_template: str,
    file_path: str,
    content_source_type: str,
    marker_used: bool,
    chunk_content: str,
    chunk_index: int,
    chunk_total: int,
    related_requests: list[ParsedRequestData],
    chunk_label: str | None = None,
    preparsed_limit: int | None = None,
) -> tuple[dict[str, Any] | list[Any] | None, bool, bool]:
    llm = create_llm_instance(active_config, temperature=0.1)
    chunk_char_limit = _get_document_chunk_size()
    trimmed_chunk, truncated_chunk = _truncate_text(chunk_content, chunk_char_limit)
    if preparsed_limit is None:
        preparsed_limit = _get_preparsed_requests_limit()
    preparsed_requests_json, truncated_preparsed = _truncate_text(
        _serialize_requests_for_prompt(related_requests),
        preparsed_limit,
    )
    chunk_descriptor = chunk_label or f"chunk {chunk_index + 1}/{chunk_total}"

    formatted_prompt = format_prompt_template(
        prompt_template,
        document_content=trimmed_chunk,
        source_type=f"{content_source_type} {chunk_descriptor}",
        file_name=f"{Path(file_path).name} [{chunk_descriptor}]",
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
    return payload, truncated_chunk, truncated_preparsed


def _invoke_ai_for_chunk_with_timeout_fallback(
    *,
    active_config: LLMConfig,
    prompt_template: str,
    file_path: str,
    content_source_type: str,
    marker_used: bool,
    chunk_content: str,
    chunk_index: int,
    chunk_total: int,
    related_requests: list[ParsedRequestData],
    base_requests: list[ParsedRequestData],
    split_depth: int = 0,
    chunk_label: str | None = None,
) -> tuple[list[dict[str, Any] | list[Any]], bool, bool, bool, bool]:
    preparsed_limit = max(1000, _get_preparsed_requests_limit() // (2**split_depth))
    try:
        payload, truncated_chunk, truncated_preparsed = _invoke_ai_for_chunk(
            active_config=active_config,
            prompt_template=prompt_template,
            file_path=file_path,
            content_source_type=content_source_type,
            marker_used=marker_used,
            chunk_content=chunk_content,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
            related_requests=related_requests,
            chunk_label=chunk_label,
            preparsed_limit=preparsed_limit,
        )
        return ([payload] if payload is not None else []), truncated_chunk, truncated_preparsed, False, False
    except Exception as exc:
        split_due_to_connection_error = _is_connection_error(exc)
        if not (_is_timeout_error(exc) or split_due_to_connection_error):
            raise

        max_split_depth = _get_timeout_split_max_depth()
        min_chunk_chars = _get_timeout_split_min_chars()
        if split_depth >= max_split_depth or len(chunk_content) <= min_chunk_chars:
            raise

        next_chunk_chars = max(min_chunk_chars, len(chunk_content) // 2)
        subchunks = _split_document_for_ai(chunk_content, max_chars=next_chunk_chars)
        if len(subchunks) <= 1:
            raise

        parent_label = chunk_label or f"chunk {chunk_index + 1}/{chunk_total}"
        if split_due_to_connection_error:
            logger.warning(
                "API automation AI chunk hit connection error, splitting %s into %s smaller chunks at depth %s",
                parent_label,
                len(subchunks),
                split_depth + 1,
            )
        else:
            logger.warning(
                "API automation AI chunk timed out, splitting %s into %s smaller chunks at depth %s",
                parent_label,
                len(subchunks),
                split_depth + 1,
            )

        payloads: list[dict[str, Any] | list[Any]] = []
        truncated_chunk = False
        truncated_preparsed = False
        used_connection_split = split_due_to_connection_error
        for sub_index, subchunk in enumerate(subchunks):
            sub_payloads, sub_truncated_chunk, sub_truncated_preparsed, _, sub_used_connection_split = _invoke_ai_for_chunk_with_timeout_fallback(
                active_config=active_config,
                prompt_template=prompt_template,
                file_path=file_path,
                content_source_type=content_source_type,
                marker_used=marker_used,
                chunk_content=subchunk,
                chunk_index=sub_index,
                chunk_total=len(subchunks),
                related_requests=_select_relevant_requests(subchunk, base_requests),
                base_requests=base_requests,
                split_depth=split_depth + 1,
                chunk_label=f"{parent_label} subchunk {sub_index + 1}/{len(subchunks)}",
            )
            payloads.extend(sub_payloads)
            truncated_chunk = truncated_chunk or sub_truncated_chunk
            truncated_preparsed = truncated_preparsed or sub_truncated_preparsed
            used_connection_split = used_connection_split or sub_used_connection_split

        return payloads, truncated_chunk, truncated_preparsed, True, used_connection_split


def _normalize_chunk_invoke_result(
    result: tuple[Any, ...],
) -> tuple[list[dict[str, Any] | list[Any]], bool, bool, bool, bool]:
    if len(result) == 5:
        payloads, truncated_chunk, truncated_preparsed, used_timeout_split, used_connection_split = result
        return payloads, truncated_chunk, truncated_preparsed, used_timeout_split, used_connection_split
    if len(result) == 4:
        payloads, truncated_chunk, truncated_preparsed, used_timeout_split = result
        return payloads, truncated_chunk, truncated_preparsed, used_timeout_split, False
    raise ValueError(f"Unexpected AI chunk result shape: {len(result)}")


def enhance_import_result_with_ai(
    *,
    file_path: str,
    user,
    source_type: str,
    base_requests: list[ParsedRequestData],
    cancel_callback=None,
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

    compatibility_error = _probe_openai_compatible_text_response(active_config)
    if compatibility_error is not None:
        return AIEnhancementResult(
            requested=True,
            used=False,
            note=_build_ai_failure_note(compatibility_error, active_config=active_config),
            prompt_source=prompt_source,
            prompt_name=prompt_name,
            model_name=active_config.name,
            requests=base_requests,
        )

    _ensure_not_cancelled(cancel_callback)
    document_content, content_source_type, marker_used = load_document_content_for_ai(file_path)
    cache_key = _build_ai_enhancement_cache_key(
        document_content=document_content,
        source_type=source_type,
        content_source_type=content_source_type or source_type,
        marker_used=marker_used,
        prompt_template=prompt_template,
        model_name=active_config.name,
        base_requests=base_requests,
    )
    lock_timeout_seconds = _read_int_env(
        "API_AUTOMATION_AI_USER_LOCK_TIMEOUT_SECONDS",
        DEFAULT_AI_USER_LOCK_TIMEOUT_SECONDS,
        minimum=1,
        maximum=300,
    )

    def _compute_enhancement_result() -> AIEnhancementResult:
        chunks = _split_document_for_ai(document_content, max_chars=_get_document_chunk_size())

        payloads: list[dict[str, Any] | list[Any]] = []
        truncated_document = len(chunks) > 1
        truncated_preparsed = False
        chunk_max_workers = 1
        used_sequential_fallback = False
        used_timeout_split_fallback = False
        used_connection_split_fallback = False

        if len(chunks) == 1:
            _ensure_not_cancelled(cancel_callback)
            chunk_payloads, chunk_truncated, preparsed_truncated, used_timeout_split, used_connection_split = _normalize_chunk_invoke_result(
                _invoke_ai_for_chunk_with_timeout_fallback(
                    active_config=active_config,
                    prompt_template=prompt_template,
                    file_path=file_path,
                    content_source_type=content_source_type or source_type,
                    marker_used=marker_used,
                    chunk_content=chunks[0],
                    chunk_index=0,
                    chunk_total=1,
                    related_requests=_select_relevant_requests(chunks[0], base_requests),
                    base_requests=base_requests,
                )
            )
            truncated_document = truncated_document or chunk_truncated
            truncated_preparsed = truncated_preparsed or preparsed_truncated
            used_timeout_split_fallback = used_timeout_split_fallback or used_timeout_split
            used_connection_split_fallback = used_connection_split_fallback or used_connection_split
            if not chunk_payloads:
                return AIEnhancementResult(
                    requested=True,
                    used=False,
                    note="AI 返回结果无法解析为 JSON，已回退到规则解析结果。",
                    prompt_source=prompt_source,
                    prompt_name=prompt_name,
                    model_name=active_config.name,
                    requests=base_requests,
                )
            payloads.extend(chunk_payloads)
        else:
            chunk_max_workers = _get_chunk_max_workers(len(chunks))
            if chunk_max_workers == 1:
                for index, chunk in enumerate(chunks):
                    _ensure_not_cancelled(cancel_callback)
                    chunk_payloads, chunk_truncated, preparsed_truncated, used_timeout_split, used_connection_split = _normalize_chunk_invoke_result(
                        _invoke_ai_for_chunk_with_timeout_fallback(
                            active_config=active_config,
                            prompt_template=prompt_template,
                            file_path=file_path,
                            content_source_type=content_source_type or source_type,
                            marker_used=marker_used,
                            chunk_content=chunk,
                            chunk_index=index,
                            chunk_total=len(chunks),
                            related_requests=_select_relevant_requests(chunk, base_requests),
                            base_requests=base_requests,
                        )
                    )
                    truncated_document = truncated_document or chunk_truncated
                    truncated_preparsed = truncated_preparsed or preparsed_truncated
                    used_timeout_split_fallback = used_timeout_split_fallback or used_timeout_split
                    used_connection_split_fallback = used_connection_split_fallback or used_connection_split
                    payloads.extend(chunk_payloads)
            else:
                futures = []
                try:
                    with ThreadPoolExecutor(max_workers=chunk_max_workers) as executor:
                        for index, chunk in enumerate(chunks):
                            _ensure_not_cancelled(cancel_callback)
                            futures.append(
                                executor.submit(
                                    _invoke_ai_for_chunk_with_timeout_fallback,
                                    active_config=active_config,
                                    prompt_template=prompt_template,
                                    file_path=file_path,
                                    content_source_type=content_source_type or source_type,
                                    marker_used=marker_used,
                                    chunk_content=chunk,
                                    chunk_index=index,
                                    chunk_total=len(chunks),
                                    related_requests=_select_relevant_requests(chunk, base_requests),
                                    base_requests=base_requests,
                                )
                            )

                        for future in as_completed(futures):
                            _ensure_not_cancelled(cancel_callback)
                            chunk_payloads, chunk_truncated, preparsed_truncated, used_timeout_split, used_connection_split = _normalize_chunk_invoke_result(
                                future.result()
                            )
                            truncated_document = truncated_document or chunk_truncated
                            truncated_preparsed = truncated_preparsed or preparsed_truncated
                            used_timeout_split_fallback = used_timeout_split_fallback or used_timeout_split
                            used_connection_split_fallback = used_connection_split_fallback or used_connection_split
                            payloads.extend(chunk_payloads)
                except Exception as exc:
                    if not _is_concurrent_request_limit_error(exc):
                        raise
                    logger.warning(
                        "API automation AI chunk parsing hit concurrent limit with max_workers=%s, switching to sequential retries",
                        chunk_max_workers,
                    )
                    payloads = []
                    truncated_document = len(chunks) > 1
                    truncated_preparsed = False
                    chunk_max_workers = 1
                    used_sequential_fallback = True
                    for index, chunk in enumerate(chunks):
                        _ensure_not_cancelled(cancel_callback)
                        chunk_payloads, chunk_truncated, preparsed_truncated, used_timeout_split, used_connection_split = _normalize_chunk_invoke_result(
                            _invoke_ai_for_chunk_with_timeout_fallback(
                                active_config=active_config,
                                prompt_template=prompt_template,
                                file_path=file_path,
                                content_source_type=content_source_type or source_type,
                                marker_used=marker_used,
                                chunk_content=chunk,
                                chunk_index=index,
                                chunk_total=len(chunks),
                                related_requests=_select_relevant_requests(chunk, base_requests),
                                base_requests=base_requests,
                            )
                        )
                        truncated_document = truncated_document or chunk_truncated
                        truncated_preparsed = truncated_preparsed or preparsed_truncated
                        used_timeout_split_fallback = used_timeout_split_fallback or used_timeout_split
                        used_connection_split_fallback = used_connection_split_fallback or used_connection_split
                        payloads.extend(chunk_payloads)

        if not payloads:
            return AIEnhancementResult(
                requested=True,
                used=False,
                note="AI 返回结果无法解析为 JSON，已回退到规则解析结果。",
                prompt_source=prompt_source,
                prompt_name=prompt_name,
                model_name=active_config.name,
                requests=base_requests,
            )

        merged_requests = list(base_requests)
        for payload in payloads:
            merged_requests = _merge_ai_requests(merged_requests, payload)

        notes: list[str] = ["已应用 AI 增强解析。"]
        if len(chunks) > 1:
            if chunk_max_workers == 1:
                notes.append(f"文档过大，已切分为 {len(chunks)} 份并顺序解析，以降低 AI 网关并发压力。")
            else:
                notes.append(f"文档过大，已切分为 {len(chunks)} 份，最大并发 {chunk_max_workers} 进行解析。")
        if used_sequential_fallback:
            notes.append("检测到 AI 网关并发限流，已自动切换为顺序重试。")
        if used_timeout_split_fallback:
            notes.append("检测到 AI 请求超时，已自动缩小文档分片后继续解析。")
        if used_connection_split_fallback:
            notes.append("检测到 AI 网关连接异常，已自动缩小文档分片并再次尝试。")
        if truncated_document:
            notes.append("部分文档分片内容过长，已截断后送入模型。")
        if truncated_preparsed:
            notes.append("预解析结果过长，已截断后送入模型。")
        for payload in payloads:
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

    try:
        result, runtime_meta = run_ai_operation(
            user=user,
            feature="document_import_enhancement",
            cache_key=cache_key,
            cache_ttl_seconds=_get_ai_enhancement_cache_ttl(),
            lock_timeout_seconds=lock_timeout_seconds,
            lock_error_message="当前账号已有 API 文档 AI 解析任务正在进行，请稍后重试。",
            compute=_compute_enhancement_result,
            should_cache=lambda item: bool(item.used and item.requests),
        )
        return _attach_runtime_meta(
            result,
            cache_hit=runtime_meta.cache_hit,
            cache_key=runtime_meta.cache_key,
            duration_ms=runtime_meta.duration_ms,
            lock_wait_ms=runtime_meta.lock_wait_ms,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API automation AI enhancement failed: %s", exc, exc_info=True)
        return AIEnhancementResult(
            requested=True,
            used=False,
            note=_build_ai_failure_note(exc, active_config=active_config),
            prompt_source=prompt_source,
            prompt_name=prompt_name,
            model_name=active_config.name,
            requests=base_requests,
        )
