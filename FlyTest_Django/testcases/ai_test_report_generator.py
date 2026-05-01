from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import get_user_active_llm_config
from langgraph_integration.views import invoke_plain_text_llm

logger = logging.getLogger(__name__)

TEST_REPORT_SYSTEM_PROMPT = """
你是 FlyTest 的测试报告分析助手。
请基于输入的测试套件、测试用例、BUG 数据，生成一次迭代测试报告。

要求：
1. 只能基于输入数据分析，不允许臆造不存在的版本、环境、结论或根因。
2. 输出必须是 JSON，不要输出 Markdown，不要输出额外解释。
3. 结论要偏实战，突出覆盖情况、质量风险、阻塞问题、建议动作。
4. 推荐项请给出明确优先级：high、medium、low。

JSON 结构：
{
  "summary": "一段整体总结",
  "quality_overview": "对测试覆盖、执行情况、质量趋势的概述",
  "risk_overview": "对主要风险、阻塞点、遗留问题的概述",
  "findings": [
    {
      "title": "关键发现标题",
      "detail": "关键发现说明",
      "severity": "high"
    }
  ],
  "recommendations": [
    {
      "title": "建议标题",
      "detail": "建议内容",
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
""".strip()


@dataclass
class IterationTestReportResult:
    used_ai: bool
    note: str
    summary: str
    quality_overview: str
    risk_overview: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    model_name: str | None = None


def _safe_json_loads(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("模型未返回内容")
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _normalize_priority(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"high", "medium", "low"}:
        return candidate
    return "medium"


def _normalize_severity(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"high", "medium", "low"}:
        return candidate
    return "medium"


def _normalize_items(items: Any, *, kind: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return normalized
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("label") or "").strip()
        detail = str(item.get("detail") or "").strip()
        if not title or not detail:
            continue
        if kind == "finding":
            normalized.append(
                {
                    "title": title[:120],
                    "detail": detail[:1000],
                    "severity": _normalize_severity(item.get("severity")),
                }
            )
        elif kind == "recommendation":
            normalized.append(
                {
                    "title": title[:120],
                    "detail": detail[:1000],
                    "priority": _normalize_priority(item.get("priority")),
                }
            )
        else:
            normalized.append({"label": title[:120], "detail": detail[:1000]})
    return normalized


def build_rule_based_iteration_report(report_context: dict[str, Any]) -> IterationTestReportResult:
    totals = report_context.get("totals") or {}
    suite_breakdown = list(report_context.get("suite_breakdown") or [])
    bug_status_distribution = report_context.get("bug_status_distribution") or {}
    execution_status_distribution = report_context.get("execution_status_distribution") or {}

    suite_count = int(totals.get("suite_count") or 0)
    testcase_count = int(totals.get("testcase_count") or 0)
    bug_count = int(totals.get("bug_count") or 0)
    approved_count = int(totals.get("approved_testcase_count") or 0)
    passed_count = int(execution_status_distribution.get("passed") or 0)
    failed_count = int(execution_status_distribution.get("failed") or 0)
    not_executed_count = int(execution_status_distribution.get("not_executed") or 0)
    pending_retest_count = int(bug_status_distribution.get("pending_retest") or 0)
    unassigned_bug_count = int(bug_status_distribution.get("unassigned") or 0)
    expired_bug_count = int(bug_status_distribution.get("expired") or 0)

    summary = (
        f"本次报告覆盖 {suite_count} 个套件、{testcase_count} 条测试用例、{bug_count} 条 BUG。"
        f" 其中已审核通过用例 {approved_count} 条，执行通过 {passed_count} 条，执行失败 {failed_count} 条。"
    )
    quality_overview = (
        f"当前纳入报告的用例中，未执行 {not_executed_count} 条，"
        f"已通过审核的用例 {approved_count} 条。"
        f" 如失败与未执行用例占比偏高，说明本轮回归闭环仍未完成。"
    )
    risk_overview = (
        f"当前待复测 BUG {pending_retest_count} 条、未指派 BUG {unassigned_bug_count} 条、"
        f"已过期 BUG {expired_bug_count} 条。"
        f" 这些问题会直接影响本轮迭代交付质量与验证效率。"
    )

    findings: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    if failed_count > 0:
        findings.append(
            {
                "title": "存在执行失败用例",
                "detail": f"当前选中范围内共有 {failed_count} 条测试用例执行失败，需要优先定位失败原因并安排回归。",
                "severity": "high",
            }
        )
    if not_executed_count > 0:
        findings.append(
            {
                "title": "仍有未执行用例",
                "detail": f"当前仍有 {not_executed_count} 条测试用例未执行，测试覆盖闭环尚未完成。",
                "severity": "medium",
            }
        )
    if pending_retest_count > 0 or expired_bug_count > 0:
        findings.append(
            {
                "title": "BUG 闭环存在风险",
                "detail": f"待复测 BUG {pending_retest_count} 条，已过期 BUG {expired_bug_count} 条，建议优先推进修复验证。",
                "severity": "high",
            }
        )

    recommendations.append(
        {
            "title": "优先清理失败与待复测问题",
            "detail": "优先处理执行失败用例、待复测 BUG 和已过期 BUG，确保本轮迭代的高风险问题先闭环。",
            "priority": "high",
        }
    )
    if not_executed_count > 0:
        recommendations.append(
            {
                "title": "补齐未执行用例覆盖",
                "detail": "尽快补齐未执行测试用例，避免因覆盖不足导致上线风险残留。",
                "priority": "medium",
            }
        )

    for suite in suite_breakdown[:5]:
        evidence.append(
            {
                "label": f"套件 {suite.get('name') or '-'}",
                "detail": (
                    f"包含测试用例 {suite.get('testcase_count') or 0} 条，"
                    f"BUG {suite.get('bug_count') or 0} 条，"
                    f"失败用例 {suite.get('failed_testcase_count') or 0} 条，"
                    f"待复测 BUG {suite.get('pending_retest_bug_count') or 0} 条。"
                ),
            }
        )

    return IterationTestReportResult(
        used_ai=False,
        note="当前使用规则统计生成测试报告摘要。",
        summary=summary,
        quality_overview=quality_overview,
        risk_overview=risk_overview,
        findings=findings,
        recommendations=recommendations,
        evidence=evidence,
    )


def generate_iteration_test_report(*, user, report_context: dict[str, Any]) -> IterationTestReportResult:
    fallback = build_rule_based_iteration_report(report_context)
    active_config = get_user_active_llm_config(user)
    if active_config is None:
        fallback.note = "当前未配置可用模型，已返回规则统计版测试报告。"
        return fallback

    user_prompt = (
        "请基于以下测试数据生成一次迭代测试报告。\n"
        "仅输出 JSON。\n\n"
        f"{json.dumps(report_context, ensure_ascii=False, indent=2)}"
    )

    try:
        response_text = invoke_plain_text_llm(
            active_config,
            [
                SystemMessage(content=TEST_REPORT_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ],
            temperature=0.2,
        )
        payload = _safe_json_loads(response_text)

        summary = str(payload.get("summary") or "").strip() or fallback.summary
        quality_overview = str(payload.get("quality_overview") or "").strip() or fallback.quality_overview
        risk_overview = str(payload.get("risk_overview") or "").strip() or fallback.risk_overview
        findings = _normalize_items(payload.get("findings"), kind="finding") or fallback.findings
        recommendations = _normalize_items(payload.get("recommendations"), kind="recommendation") or fallback.recommendations
        evidence = _normalize_items(payload.get("evidence"), kind="evidence") or fallback.evidence

        model_name = getattr(active_config, "model", None) or getattr(active_config, "model_name", None)
        return IterationTestReportResult(
            used_ai=True,
            note="测试报告已通过 AI 自动生成。",
            summary=summary,
            quality_overview=quality_overview,
            risk_overview=risk_overview,
            findings=findings,
            recommendations=recommendations,
            evidence=evidence,
            model_name=model_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to generate AI iteration test report: %s", exc)
        fallback.note = f"AI 生成失败，已降级为规则统计版测试报告：{exc}"
        return fallback
