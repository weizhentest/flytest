from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import logging
import os
from string import Template
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig, get_user_active_llm_config
from prompts.models import UserPrompt

from .ai_parser import create_llm_instance, extract_json_from_response, safe_llm_invoke
from .ai_runtime import build_ai_cache_key, run_ai_operation, stable_digest
from .models import ApiExecutionRecord
from .specs import serialize_assertion_specs, serialize_request_spec, serialize_test_case_override

logger = logging.getLogger(__name__)

DEFAULT_AI_FAILURE_ANALYSIS_CACHE_TTL_SECONDS = 1800
DEFAULT_AI_FAILURE_ANALYSIS_LOCK_TIMEOUT_SECONDS = 25

SUPPORTED_FAILURE_MODES = {
    "workflow_blocked",
    "workflow_failure",
    "auth_or_permission",
    "not_found",
    "server_error",
    "timeout_or_performance",
    "assertion_mismatch",
    "network_or_runtime",
    "unknown_failure",
    "passed",
}
SUPPORTED_ACTION_PRIORITIES = {"high", "medium", "low"}

DEFAULT_FAILURE_ANALYSIS_PROMPT = """你是 FlyTest 的 API 自动化失败复盘专家。
请基于给定的执行记录、断言结果、工作流信息和最近失败历史，输出结构化失败复盘建议。

要求：
1. 只基于输入证据分析，不要臆测不存在的系统内部实现。
2. 优先判断失败属于：工作流阻断、工作流步骤失败、认证/权限、路径/环境、服务端错误、超时性能、断言配置不匹配、网络/运行时异常。
3. 如果更可能是测试数据、环境变量、鉴权、断言配置或工作流步骤问题，要明确指出，不要笼统归因于“后端异常”。
4. 推荐动作要可执行，优先给出测试平台内可落地的动作，例如：补环境变量、调整认证、补提取器、收紧/放宽断言、检查 base_url、补前置步骤、重新生成用例。
5. 输出必须是 JSON，不要输出 Markdown，不要解释。

输出 JSON 结构：
{
  "summary": "一句话总结失败主因",
  "failure_mode": "workflow_blocked | workflow_failure | auth_or_permission | not_found | server_error | timeout_or_performance | assertion_mismatch | network_or_runtime | unknown_failure | passed",
  "likely_root_causes": [
    {
      "title": "根因标题",
      "detail": "根因说明",
      "confidence": 0.0
    }
  ],
  "recommended_actions": [
    {
      "title": "动作标题",
      "detail": "动作说明",
      "priority": "high"
    }
  ],
  "evidence": [
    {
      "label": "证据标签",
      "detail": "证据说明"
    }
  ]
}

执行记录上下文：
${context_json}
"""


@dataclass
class ExecutionFailureAnalysisResult:
    used_ai: bool
    note: str
    summary: str
    failure_mode: str
    likely_root_causes: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    recent_failures: list[dict[str, Any]] = field(default_factory=list)
    prompt_name: str | None = None
    prompt_source: str | None = None
    model_name: str | None = None
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


def _get_failure_analysis_prompt(user) -> tuple[str, str, str]:
    user_prompt = (
        UserPrompt.objects.filter(user=user, is_active=True, name__icontains="失败复盘")
        .order_by("-updated_at")
        .first()
    )
    if user_prompt:
        return user_prompt.content, "user_prompt", user_prompt.name
    return DEFAULT_FAILURE_ANALYSIS_PROMPT, "builtin_fallback", "API 失败复盘"


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


def _get_failure_analysis_cache_ttl() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_FAILURE_ANALYSIS_CACHE_TTL_SECONDS",
        DEFAULT_AI_FAILURE_ANALYSIS_CACHE_TTL_SECONDS,
        minimum=0,
        maximum=24 * 60 * 60,
    )


def _get_failure_analysis_lock_timeout() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_FAILURE_ANALYSIS_LOCK_TIMEOUT_SECONDS",
        DEFAULT_AI_FAILURE_ANALYSIS_LOCK_TIMEOUT_SECONDS,
        minimum=1,
        maximum=300,
    )


def _compact_text(value: Any, limit: int = 1200) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:  # noqa: BLE001
            text = str(value)
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(truncated)"


def _normalize_confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(min(max(parsed, 0.0), 1.0), 2)


def _normalize_failure_mode(value: Any, fallback: str = "unknown_failure") -> str:
    text = str(value or "").strip()
    return text if text in SUPPORTED_FAILURE_MODES else fallback


def _normalize_cause_items(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not title or not detail:
                continue
            normalized.append(
                {
                    "title": title[:120],
                    "detail": detail[:1000],
                    "confidence": _normalize_confidence(item.get("confidence")),
                }
            )
    return normalized or fallback


def _normalize_action_items(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            priority = str(item.get("priority") or "medium").strip().lower()
            if not title or not detail:
                continue
            normalized.append(
                {
                    "title": title[:120],
                    "detail": detail[:1000],
                    "priority": priority if priority in SUPPORTED_ACTION_PRIORITIES else "medium",
                }
            )
    return normalized or fallback


def _normalize_evidence_items(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not label or not detail:
                continue
            normalized.append({"label": label[:120], "detail": detail[:1000]})
    return normalized or fallback


def _serialize_failed_assertions(record: ApiExecutionRecord) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, item in enumerate(record.assertions_results or []):
        if not isinstance(item, dict):
            continue
        if item.get("passed") is True:
            continue
        payload.append(
            {
                "index": item.get("index", index),
                "type": item.get("type") or item.get("assertion_type") or "assertion",
                "expected": _compact_text(item.get("expected"), 240),
                "actual": _compact_text(item.get("actual"), 240),
                "message": _compact_text(item.get("message"), 240),
            }
        )
    return payload[:8]


def _serialize_failed_workflow_steps(record: ApiExecutionRecord) -> list[dict[str, Any]]:
    steps = []
    request_snapshot = record.request_snapshot or {}
    raw_steps = request_snapshot.get("workflow_steps")
    if not isinstance(raw_steps, list):
        return steps
    for index, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            continue
        status_text = str(item.get("status") or "").strip()
        passed = item.get("passed")
        if passed is True or status_text == "success":
            continue
        steps.append(
            {
                "index": item.get("index", index),
                "name": item.get("name") or item.get("request_name") or f"步骤 {index + 1}",
                "stage": item.get("stage") or ("request" if item.get("kind") == "main_request" else "prepare"),
                "status": status_text or ("failed" if passed is False else "error"),
                "status_code": item.get("status_code"),
                "error_message": _compact_text(item.get("error_message"), 240),
            }
        )
    return steps[:6]


def _serialize_recent_failures(record: ApiExecutionRecord, limit: int = 4) -> list[dict[str, Any]]:
    queryset = ApiExecutionRecord.objects.filter(project=record.project, passed=False).exclude(pk=record.pk)
    if record.test_case_id:
        queryset = queryset.filter(test_case_id=record.test_case_id)
    elif record.request_id:
        queryset = queryset.filter(request_id=record.request_id)
    else:
        queryset = queryset.filter(request_name=record.request_name, method=record.method, url=record.url)

    payload: list[dict[str, Any]] = []
    for item in queryset.order_by("-created_at")[:limit]:
        payload.append(
            {
                "id": item.id,
                "status": item.status,
                "status_code": item.status_code,
                "response_time": item.response_time,
                "error_message": _compact_text(item.error_message, 240),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    return payload


def _build_context_payload(record: ApiExecutionRecord) -> dict[str, Any]:
    failed_assertions = _serialize_failed_assertions(record)
    failed_workflow_steps = _serialize_failed_workflow_steps(record)
    recent_failures = _serialize_recent_failures(record)

    return {
        "record": {
            "id": record.id,
            "run_name": record.run_name,
            "request_name": record.request_name,
            "interface_name": record.request.name if record.request_id and record.request else record.request_name,
            "test_case_name": record.test_case.name if record.test_case_id and record.test_case else None,
            "method": record.method,
            "url": record.url,
            "status": record.status,
            "passed": record.passed,
            "status_code": record.status_code,
            "response_time": record.response_time,
            "environment_name": record.environment.name if record.environment_id and record.environment else None,
            "error_message": _compact_text(record.error_message, 500),
        },
        "request_spec": serialize_request_spec(record.request) if record.request_id and record.request else {},
        "request_assertion_specs": serialize_assertion_specs(record.request) if record.request_id and record.request else [],
        "test_case_override_spec": serialize_test_case_override(record.test_case) if record.test_case_id and record.test_case else {},
        "test_case_assertion_specs": serialize_assertion_specs(record.test_case) if record.test_case_id and record.test_case else [],
        "failed_assertions": failed_assertions,
        "workflow_summary": (
            dict((record.request_snapshot or {}).get("workflow_summary"))
            if isinstance((record.request_snapshot or {}).get("workflow_summary"), dict)
            else {}
        ),
        "failed_workflow_steps": failed_workflow_steps,
        "request_snapshot": _compact_text(record.request_snapshot, 3200),
        "response_snapshot": _compact_text(record.response_snapshot, 3200),
        "recent_failures": recent_failures,
    }


def _build_failure_analysis_cache_key(
    *,
    record: ApiExecutionRecord,
    prompt_template: str,
    prompt_source: str,
    prompt_name: str,
    model_name: str,
    context_payload: dict[str, Any],
) -> str:
    return build_ai_cache_key(
        "execution_failure_analysis",
        {
            "record_id": record.id,
            "record_digest": stable_digest(context_payload),
            "prompt_digest": stable_digest(prompt_template),
            "prompt_source": prompt_source,
            "prompt_name": prompt_name,
            "model_name": model_name,
        },
    )


def _build_rule_based_analysis(record: ApiExecutionRecord) -> ExecutionFailureAnalysisResult:
    failed_assertions = _serialize_failed_assertions(record)
    failed_workflow_steps = _serialize_failed_workflow_steps(record)
    recent_failures = _serialize_recent_failures(record)

    if record.passed:
        return ExecutionFailureAnalysisResult(
            used_ai=False,
            note="当前执行已通过，无需生成失败复盘建议。",
            summary="当前执行记录已通过。",
            failure_mode="passed",
            likely_root_causes=[],
            recommended_actions=[],
            evidence=[{"label": "执行结果", "detail": "当前记录 passed=true，状态为 success。"}],
            recent_failures=recent_failures,
        )

    failure_mode = "unknown_failure"
    summary = "本次执行未通过，建议先结合错误信息、断言差异和工作流步骤排查。"
    causes: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if bool((record.request_snapshot or {}).get("main_request_blocked")):
        failure_mode = "workflow_blocked"
        summary = "主请求被前置工作流阻断，根因更可能出在 prepare 步骤、鉴权准备或上下文变量提取失败。"
        causes.append({"title": "前置步骤阻断主请求", "detail": "至少一个 prepare 步骤失败且未配置失败后继续，主请求没有真正发出。", "confidence": 0.95})
        actions.extend(
            [
                {"title": "优先修复失败的前置步骤", "detail": "检查登录、令牌获取、变量提取等 prepare 步骤的请求和断言配置。", "priority": "high"},
                {"title": "核对环境变量和提取器", "detail": "确认工作流步骤是否正确提取 token、session、主键等上下文变量。", "priority": "high"},
            ]
        )
    elif failed_workflow_steps:
        failure_mode = "workflow_failure"
        first_step = failed_workflow_steps[0]
        summary = f"工作流步骤“{first_step.get('name') or '未命名步骤'}”执行失败，当前失败更可能是前后置流程问题而非主接口本身。"
        causes.append({"title": "工作流步骤失败", "detail": f"失败步骤为 {first_step.get('stage')} 阶段，状态 {first_step.get('status')}。", "confidence": 0.88})
        actions.extend(
            [
                {"title": "检查失败步骤的请求配置", "detail": "重点检查该步骤的 URL、认证、环境变量、提取器和断言。", "priority": "high"},
                {"title": "确认是否需要 continue_on_failure", "detail": "如果步骤失败不应阻断主流程，可评估是否开启失败后继续。", "priority": "medium"},
            ]
        )
    elif record.status_code in {401, 403}:
        failure_mode = "auth_or_permission"
        summary = "失败特征更偏向认证或权限问题，建议优先排查 token、Cookie、API Key 和登录前置步骤。"
        causes.append({"title": "认证或权限失效", "detail": f"响应状态码为 {record.status_code}，常见于 token 过期、权限不足或鉴权头缺失。", "confidence": 0.9})
        actions.extend(
            [
                {"title": "检查认证配置", "detail": "确认 Auth、Headers、Cookies、环境变量中的认证信息是否完整且最新。", "priority": "high"},
                {"title": "补齐登录工作流或提取器", "detail": "如果依赖登录态，建议用 prepare 步骤获取 token 并通过 extractor 传递。", "priority": "high"},
            ]
        )
    elif record.status_code == 404:
        failure_mode = "not_found"
        summary = "失败更偏向路径或环境配置问题，建议优先检查 base_url、接口路径和环境切换是否正确。"
        causes.append({"title": "路径或环境不匹配", "detail": "响应状态码 404 常见于 base_url、路由前缀或接口版本不一致。", "confidence": 0.86})
        actions.extend(
            [
                {"title": "检查环境地址与接口路径", "detail": "确认 base_url、请求路径、目录导入结果和实际部署环境一致。", "priority": "high"},
                {"title": "核对接口文档与实现版本", "detail": "若接口已升级或迁移，建议同步更新接口定义和用例覆盖。", "priority": "medium"},
            ]
        )
    elif record.status_code and record.status_code >= 500:
        failure_mode = "server_error"
        summary = "失败表现为服务端异常，但仍需先确认请求数据、上下文变量和前置步骤是否正确。"
        causes.append({"title": "服务端返回 5xx", "detail": f"本次响应状态码为 {record.status_code}，服务端处理请求时出现异常。", "confidence": 0.78})
        actions.extend(
            [
                {"title": "先核对请求数据与上下文", "detail": "确认当前请求体、查询参数、认证信息和前置变量是否符合接口约束。", "priority": "high"},
                {"title": "保留失败快照给后端排查", "detail": "把请求/响应快照、状态码和最近相似失败记录交给后端定位。", "priority": "medium"},
            ]
        )
    elif record.status == "error" or "timeout" in str(record.error_message or "").lower():
        failure_mode = "timeout_or_performance" if "timeout" in str(record.error_message or "").lower() else "network_or_runtime"
        summary = "失败更像请求超时、网络异常或运行时问题，建议优先检查超时、代理、证书和环境连通性。"
        causes.append({"title": "运行时或网络异常", "detail": _compact_text(record.error_message, 400) or "执行阶段返回了 error 状态。", "confidence": 0.82})
        actions.extend(
            [
                {"title": "检查超时与传输配置", "detail": "确认 timeout、verify_ssl、proxy、client_cert、follow_redirects 等配置是否合理。", "priority": "high"},
                {"title": "验证环境可达性", "detail": "在相同环境下确认目标服务、网关和认证服务是否可访问。", "priority": "high"},
            ]
        )
    elif failed_assertions:
        failure_mode = "assertion_mismatch"
        first_assertion = failed_assertions[0]
        summary = "请求已发出，但断言结果与响应不一致，建议优先判断是断言过严、测试数据变化还是接口契约变更。"
        causes.append({"title": "断言与实际响应不匹配", "detail": f"失败断言类型为 {first_assertion.get('type')}，预期与实际存在差异。", "confidence": 0.84})
        actions.extend(
            [
                {"title": "检查断言是否过旧或过严", "detail": "确认状态码、字段路径、结构断言和响应时间阈值是否仍符合接口当前行为。", "priority": "high"},
                {"title": "考虑为用例补充提取器/前置条件", "detail": "如果失败由动态数据导致，建议通过工作流和提取器准备更稳定的上下文。", "priority": "medium"},
            ]
        )
    else:
        causes.append({"title": "失败证据不足", "detail": "当前错误信息、状态码或断言结果不足以明确定位，需要结合请求/响应快照继续排查。", "confidence": 0.55})
        actions.append({"title": "补充可观测性", "detail": "建议为关键接口补充结构化断言、提取器和工作流步骤，减少失败后排查成本。", "priority": "medium"})

    evidence = [
        {"label": "执行状态", "detail": f"status={record.status}, passed={record.passed}"},
        {"label": "状态码", "detail": str(record.status_code) if record.status_code is not None else "无状态码"},
    ]
    if record.error_message:
        evidence.append({"label": "错误信息", "detail": _compact_text(record.error_message, 280)})
    for item in failed_assertions[:2]:
        evidence.append(
            {
                "label": f"失败断言 #{item.get('index', 0)}",
                "detail": f"{item.get('type')} | expected={item.get('expected') or '-'} | actual={item.get('actual') or '-'}",
            }
        )
    for item in failed_workflow_steps[:2]:
        evidence.append(
            {
                "label": f"失败步骤 #{item.get('index', 0)}",
                "detail": f"{item.get('name')} | {item.get('stage')} | status={item.get('status')} | code={item.get('status_code')}",
            }
        )
    if recent_failures:
        evidence.append({"label": "最近相似失败", "detail": f"发现 {len(recent_failures)} 条相同接口/用例的失败历史，可结合趋势判断是否为持续性问题。"})

    return ExecutionFailureAnalysisResult(
        used_ai=False,
        note="已基于执行记录、断言差异和工作流信息生成规则复盘建议。",
        summary=summary,
        failure_mode=failure_mode,
        likely_root_causes=causes,
        recommended_actions=actions,
        evidence=evidence,
        recent_failures=recent_failures,
    )


def _attach_runtime_meta(
    result: ExecutionFailureAnalysisResult,
    *,
    cache_hit: bool,
    cache_key: str | None,
    duration_ms: float,
    lock_wait_ms: float,
) -> ExecutionFailureAnalysisResult:
    note = str(result.note or "").strip()
    meta_note = "本次命中 AI 失败复盘缓存，未再次调用模型。" if cache_hit else f"AI 失败复盘耗时约 {duration_ms:.0f} ms。"
    combined_note = f"{note} {meta_note}".strip() if note else meta_note
    return replace(
        result,
        note=combined_note,
        cache_hit=cache_hit,
        cache_key=cache_key,
        duration_ms=duration_ms,
        lock_wait_ms=lock_wait_ms,
    )


def _analyze_execution_failure_uncached(*, record: ApiExecutionRecord, user) -> ExecutionFailureAnalysisResult:
    fallback_result = _build_rule_based_analysis(record)
    if record.passed:
        return fallback_result

    active_config = get_user_active_llm_config(user)
    if not active_config:
        return replace(
            fallback_result,
            note="未检测到激活的 LLM 配置，已回退到规则复盘建议。",
            prompt_name="API 失败复盘",
            prompt_source="builtin_fallback",
        )

    prompt_template, prompt_source, prompt_name = _get_failure_analysis_prompt(user)
    context_payload = _build_context_payload(record)
    formatted_prompt = _format_prompt(
        prompt_template,
        context_json=json.dumps(context_payload, ensure_ascii=False, indent=2),
    )

    try:
        llm = create_llm_instance(active_config, temperature=0.1)
        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(
                    content=(
                        "你是 API 自动化失败复盘助手。"
                        "必须只返回合法 JSON，不要输出 Markdown 或解释性文本。"
                    )
                ),
                HumanMessage(content=formatted_prompt),
            ],
        )
        payload = extract_json_from_response(getattr(response, "content", ""))
        if not isinstance(payload, dict):
            raise ValueError("AI 失败复盘返回结果不是 JSON 对象")

        summary = str(payload.get("summary") or "").strip() or fallback_result.summary
        failure_mode = _normalize_failure_mode(payload.get("failure_mode"), fallback_result.failure_mode)
        likely_root_causes = _normalize_cause_items(payload.get("likely_root_causes"), fallback_result.likely_root_causes)
        recommended_actions = _normalize_action_items(payload.get("recommended_actions"), fallback_result.recommended_actions)
        evidence = _normalize_evidence_items(payload.get("evidence"), fallback_result.evidence)

        return ExecutionFailureAnalysisResult(
            used_ai=True,
            note="已基于执行快照、断言差异和最近失败历史生成 AI 复盘建议。",
            summary=summary,
            failure_mode=failure_mode,
            likely_root_causes=likely_root_causes,
            recommended_actions=recommended_actions,
            evidence=evidence,
            recent_failures=context_payload["recent_failures"],
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API execution failure analysis failed: %s", exc, exc_info=True)
        return replace(
            fallback_result,
            note=f"AI 失败复盘失败，已回退到规则复盘建议。失败原因: {exc}",
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )


def analyze_execution_failure(*, record: ApiExecutionRecord, user) -> ExecutionFailureAnalysisResult:
    active_config = get_user_active_llm_config(user)
    if record.passed or not active_config:
        return _analyze_execution_failure_uncached(record=record, user=user)

    prompt_template, prompt_source, prompt_name = _get_failure_analysis_prompt(user)
    cache_key = _build_failure_analysis_cache_key(
        record=record,
        prompt_template=prompt_template,
        prompt_source=prompt_source,
        prompt_name=prompt_name,
        model_name=active_config.name,
        context_payload=_build_context_payload(record),
    )

    try:
        result, runtime_meta = run_ai_operation(
            user=user,
            feature="execution_failure_analysis",
            cache_key=cache_key,
            cache_ttl_seconds=_get_failure_analysis_cache_ttl(),
            lock_timeout_seconds=_get_failure_analysis_lock_timeout(),
            lock_error_message="当前账号已有 AI 失败复盘任务正在执行，请稍后重试。",
            compute=lambda: _analyze_execution_failure_uncached(record=record, user=user),
            should_cache=lambda item: bool(item.summary),
        )
        return _attach_runtime_meta(
            result,
            cache_hit=runtime_meta.cache_hit,
            cache_key=runtime_meta.cache_key,
            duration_ms=runtime_meta.duration_ms,
            lock_wait_ms=runtime_meta.lock_wait_ms,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API execution failure analysis wrapper failed: %s", exc, exc_info=True)
        fallback_result = _build_rule_based_analysis(record)
        return replace(
            fallback_result,
            note=f"AI 失败复盘调度失败，已回退到规则复盘建议。失败原因: {exc}",
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )
