from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import logging
import os
from string import Template
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig
from prompts.models import PromptType, UserPrompt
from prompts.services import get_default_prompts

from .ai_parser import create_llm_instance, extract_json_from_response, safe_llm_invoke
from .ai_runtime import (
    build_ai_cache_key,
    pretty_json_dumps,
    resolve_active_llm_config,
    run_ai_operation,
    stable_digest,
)

logger = logging.getLogger(__name__)

DEFAULT_AI_REPORT_SUMMARY_CACHE_TTL_SECONDS = 1800
DEFAULT_AI_REPORT_SUMMARY_LOCK_TIMEOUT_SECONDS = 25
SUPPORTED_ACTION_PRIORITIES = {"high", "medium", "low"}
DEFAULT_REPORT_SUMMARY_PROMPT = """你是 FlyTest 的 API 自动化测试报告分析助手。
请基于给定的测试报告聚合结果，输出结构化的摘要结论。

要求：
1. 只基于输入的报告数据分析，不要编造不存在的接口、环境或根因。
2. 优先指出最影响回归效率的问题，例如鉴权变量缺失、断言不稳定、接口稳定性差、目录级失败集中。
3. 推荐动作必须尽量是平台内可落地的动作，例如补环境变量、检查登录引导接口、优化断言、优先回归某些接口。
4. 输出必须是 JSON，不要输出 Markdown，不要输出解释文字。

输出 JSON 结构：
{
  "summary": "一句话总结整体风险与现状",
  "top_risks": [
    {
      "title": "风险标题",
      "detail": "风险说明"
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
      "detail": "证据内容"
    }
  ]
}

报告上下文：
${report_context_json}
"""


@dataclass
class ExecutionReportSummaryResult:
    used_ai: bool
    note: str
    summary: str
    top_risks: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
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


def _get_report_summary_prompt(user) -> tuple[str, str, str]:
    user_prompt = UserPrompt.get_user_prompt_by_type(user, PromptType.API_AUTOMATION_REPORT_SUMMARY) if user else None
    if user_prompt:
        return user_prompt.content, "user_prompt", user_prompt.name
    for prompt in get_default_prompts():
        if prompt.get("prompt_type") == PromptType.API_AUTOMATION_REPORT_SUMMARY:
            return str(prompt.get("content") or DEFAULT_REPORT_SUMMARY_PROMPT), "builtin_default", str(
                prompt.get("name") or "API测试报告摘要"
            )
    return DEFAULT_REPORT_SUMMARY_PROMPT, "builtin_fallback", "API测试报告摘要"


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


def _get_report_summary_cache_ttl() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_REPORT_SUMMARY_CACHE_TTL_SECONDS",
        DEFAULT_AI_REPORT_SUMMARY_CACHE_TTL_SECONDS,
        minimum=0,
        maximum=24 * 60 * 60,
    )


def _get_report_summary_lock_timeout() -> int:
    return _read_int_env(
        "API_AUTOMATION_AI_REPORT_SUMMARY_LOCK_TIMEOUT_SECONDS",
        DEFAULT_AI_REPORT_SUMMARY_LOCK_TIMEOUT_SECONDS,
        minimum=1,
        maximum=300,
    )


def _compact_text(value: Any, limit: int = 220) -> str:
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


def _normalize_risk_items(items: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not title or not detail:
                continue
            normalized.append({"title": title[:120], "detail": detail[:1000]})
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


def _build_rule_based_report_summary(report_payload: dict[str, Any]) -> ExecutionReportSummaryResult:
    summary_payload = dict(report_payload.get("summary") or {})
    hierarchy_summary = dict(report_payload.get("hierarchy_summary") or {})
    failing_requests = list(report_payload.get("failing_requests") or [])
    collection_breakdown = list(report_payload.get("collection_breakdown") or [])

    total_count = int(summary_payload.get("total_count") or 0)
    pass_rate = float(summary_payload.get("pass_rate") or 0)
    failed_test_case_count = int(hierarchy_summary.get("failed_test_case_count") or 0)
    failed_interface_count = int(hierarchy_summary.get("failed_interface_count") or 0)

    if total_count <= 0:
        return ExecutionReportSummaryResult(
            used_ai=False,
            note="当前筛选条件下暂无可分析的执行记录，已返回规则摘要。",
            summary="当前筛选条件下暂无执行记录。",
        )

    top_failing_request = failing_requests[0] if failing_requests else {}
    top_failing_collection = collection_breakdown[0] if collection_breakdown else {}
    summary = (
        f"最近报告共 {total_count} 条执行记录，通过率 {pass_rate:.2f}%。"
        f" 当前未通过测试用例 {failed_test_case_count} 条，涉及接口 {failed_interface_count} 个。"
    )
    top_risks: list[dict[str, Any]] = []
    recommended_actions: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    if pass_rate < 60:
        top_risks.append(
            {
                "title": "整体通过率偏低",
                "detail": "当前时间窗内接口执行通过率较低，建议优先处理高频失败接口和环境配置问题。",
            }
        )
        recommended_actions.append(
            {
                "title": "优先回归高频失败接口",
                "detail": "从测试报告中的高频失败接口开始排查环境变量、登录引导接口和断言配置。",
                "priority": "high",
            }
        )
    if top_failing_request:
        top_risks.append(
            {
                "title": f"接口 {top_failing_request.get('request_name') or '未命名接口'} 失败集中",
                "detail": f"该接口最近失败 {top_failing_request.get('total') or 0} 次，建议优先检查其环境变量和鉴权链路。",
            }
        )
        evidence.append(
            {
                "label": "高频失败接口",
                "detail": _compact_text(top_failing_request),
            }
        )
    if top_failing_collection:
        evidence.append(
            {
                "label": "高频失败目录",
                "detail": _compact_text(top_failing_collection),
            }
        )
        recommended_actions.append(
            {
                "title": "按目录集中排查",
                "detail": "可先从失败量最高的接口目录入手，集中检查公共环境配置和共用断言。",
                "priority": "medium",
            }
        )

    if not top_risks:
        top_risks.append(
            {
                "title": "失败记录需要持续观察",
                "detail": "虽然没有明显的单点集中风险，但仍建议关注最近失败接口与执行趋势变化。",
            }
        )
    if not recommended_actions:
        recommended_actions.append(
            {
                "title": "持续观察执行趋势",
                "detail": "结合最近 7/30/90 天趋势与失败接口排行，逐步优化断言和环境配置。",
                "priority": "medium",
            }
        )

    return ExecutionReportSummaryResult(
        used_ai=False,
        note="已根据测试报告聚合结果生成规则摘要。",
        summary=summary,
        top_risks=top_risks[:3],
        recommended_actions=recommended_actions[:3],
        evidence=evidence[:3],
    )


def _build_report_context_payload(report_payload: dict[str, Any]) -> dict[str, Any]:
    summary_payload = dict(report_payload.get("summary") or {})
    hierarchy_summary = dict(report_payload.get("hierarchy_summary") or {})
    return {
        "summary": summary_payload,
        "hierarchy_summary": hierarchy_summary,
        "method_breakdown": list(report_payload.get("method_breakdown") or [])[:6],
        "collection_breakdown": list(report_payload.get("collection_breakdown") or [])[:6],
        "failing_requests": list(report_payload.get("failing_requests") or [])[:6],
        "trend": list(report_payload.get("trend") or [])[-7:],
        "run_groups": [
            {
                "run_name": item.get("run_name"),
                "run_type": item.get("run_type"),
                "total_count": item.get("total_count"),
                "failed_count": item.get("failed_count"),
                "error_count": item.get("error_count"),
                "failed_interface_count": item.get("failed_interface_count"),
                "failed_test_case_count": item.get("failed_test_case_count"),
            }
            for item in list(report_payload.get("run_groups") or [])[:4]
        ],
    }


def _build_report_summary_cache_key(
    *,
    report_payload: dict[str, Any],
    prompt_template: str,
    prompt_source: str,
    prompt_name: str,
    model_name: str,
) -> str:
    return build_ai_cache_key(
        "execution_report_summary",
        {
            "report_digest": stable_digest(_build_report_context_payload(report_payload)),
            "prompt_digest": stable_digest(prompt_template),
            "prompt_source": prompt_source,
            "prompt_name": prompt_name,
            "model_name": model_name,
        },
    )


def _attach_runtime_meta(
    result: ExecutionReportSummaryResult,
    *,
    cache_hit: bool,
    cache_key: str | None,
    duration_ms: float,
    lock_wait_ms: float,
) -> ExecutionReportSummaryResult:
    note = str(result.note or "").strip()
    meta_note = "本次命中 AI 报告摘要缓存，未再次调用模型。" if cache_hit else f"AI 摘要耗时约 {duration_ms:.0f} ms。"
    combined_note = f"{note} {meta_note}".strip() if note else meta_note
    return replace(
        result,
        note=combined_note,
        cache_hit=cache_hit,
        cache_key=cache_key,
        duration_ms=duration_ms,
        lock_wait_ms=lock_wait_ms,
    )


def _summarize_execution_report_uncached(*, report_payload: dict[str, Any], user) -> ExecutionReportSummaryResult:
    fallback_result = _build_rule_based_report_summary(report_payload)
    active_config = resolve_active_llm_config(user)
    if not active_config:
        return fallback_result

    prompt_template, prompt_source, prompt_name = _get_report_summary_prompt(user)
    context_payload = _build_report_context_payload(report_payload)
    formatted_prompt = _format_prompt(
        prompt_template,
        report_context_json=pretty_json_dumps(context_payload),
    )

    try:
        llm = create_llm_instance(
            active_config,
            temperature=0.1,
            usage_context={
                "user": user,
                "llm_config": active_config,
                "source": "api_automation",
                "metadata": {"feature": "report_summary"},
            },
        )
        response = safe_llm_invoke(
            llm,
            [
                SystemMessage(
                    content=(
                        "你是专业的 API 自动化测试报告分析助手。"
                        "必须只返回合法 JSON，不能输出 Markdown 或解释性文本。"
                    )
                ),
                HumanMessage(content=formatted_prompt),
            ],
        )
        payload = extract_json_from_response(getattr(response, "content", ""))
        if not isinstance(payload, dict):
            raise ValueError("AI 测试报告摘要返回结果不是 JSON 对象")

        summary = str(payload.get("summary") or "").strip() or fallback_result.summary
        top_risks = _normalize_risk_items(payload.get("top_risks"), fallback_result.top_risks)
        recommended_actions = _normalize_action_items(
            payload.get("recommended_actions"),
            fallback_result.recommended_actions,
        )
        evidence = _normalize_evidence_items(payload.get("evidence"), fallback_result.evidence)
        return ExecutionReportSummaryResult(
            used_ai=True,
            note="已基于测试报告聚合结果生成 AI 摘要建议。",
            summary=summary,
            top_risks=top_risks,
            recommended_actions=recommended_actions,
            evidence=evidence,
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("API execution report summary failed: %s", exc, exc_info=True)
        return replace(
            fallback_result,
            note=f"AI 测试报告摘要失败，已回退到规则摘要。失败原因: {exc}",
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )


def summarize_execution_report(*, report_payload: dict[str, Any], user) -> ExecutionReportSummaryResult:
    active_config = resolve_active_llm_config(user)
    if not active_config:
        return _build_rule_based_report_summary(report_payload)

    prompt_template, prompt_source, prompt_name = _get_report_summary_prompt(user)
    cache_key = _build_report_summary_cache_key(
        report_payload=report_payload,
        prompt_template=prompt_template,
        prompt_source=prompt_source,
        prompt_name=prompt_name,
        model_name=active_config.name,
    )

    try:
        result, runtime_meta = run_ai_operation(
            user=user,
            feature="execution_report_summary",
            cache_key=cache_key,
            cache_ttl_seconds=_get_report_summary_cache_ttl(),
            lock_timeout_seconds=_get_report_summary_lock_timeout(),
            lock_error_message="当前账号已有 AI 测试报告摘要任务正在执行，请稍后重试。",
            compute=lambda: _summarize_execution_report_uncached(report_payload=report_payload, user=user),
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
        logger.warning("API execution report summary wrapper failed: %s", exc, exc_info=True)
        fallback_result = _build_rule_based_report_summary(report_payload)
        return replace(
            fallback_result,
            note=f"AI 测试报告摘要调度失败，已回退到规则摘要。失败原因: {exc}",
            prompt_name=prompt_name,
            prompt_source=prompt_source,
            model_name=active_config.name,
        )
