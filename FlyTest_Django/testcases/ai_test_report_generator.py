from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from langgraph_integration.models import get_user_active_llm_config
from langgraph_integration.views import invoke_plain_text_llm

logger = logging.getLogger(__name__)

TEST_REPORT_SYSTEM_PROMPT = """
你是 FlyTest 的测试报告分析助手。
请基于输入的套件、测试用例、需求追踪和 BUG 流转记录，输出一次迭代测试报告。

要求：
1. 只能根据输入数据分析，不允许编造版本、环境、根因或结论。
2. 输出必须是 JSON，不要输出 Markdown，不要输出额外说明。
3. 重点关注需求覆盖、执行结果、BUG 闭环情况，以及重复复测失败风险。
4. findings.severity 只能是 high / medium / low。
5. recommendations.priority 只能是 high / medium / low。

JSON 结构：
{
  "summary": "整体结论",
  "quality_overview": "质量概览",
  "risk_overview": "风险概览",
  "findings": [{"title": "标题", "detail": "说明", "severity": "high"}],
  "recommendations": [{"title": "标题", "detail": "说明", "priority": "high"}],
  "evidence": [{"label": "标签", "detail": "说明"}]
}
""".strip()


@dataclass
class IterationTestReportResult:
    used_ai: bool
    note: str
    model_name: str | None
    summary: str
    quality_overview: str
    risk_overview: str
    findings: list[dict[str, str]]
    recommendations: list[dict[str, str]]
    evidence: list[dict[str, str]]


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


def _normalize_level(value: Any, default: str = "medium") -> str:
    candidate = str(value or "").strip().lower()
    if candidate in {"high", "medium", "low"}:
        return candidate
    return default


def _normalize_report_items(items: Any, *, kind: str) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
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
                    "severity": _normalize_level(item.get("severity")),
                }
            )
        elif kind == "recommendation":
            normalized.append(
                {
                    "title": title[:120],
                    "detail": detail[:1000],
                    "priority": _normalize_level(item.get("priority")),
                }
            )
        else:
            normalized.append({"label": title[:120], "detail": detail[:1000]})
    return normalized


def _build_ai_prompt(report_context: dict[str, Any]) -> str:
    prompt_payload = {
        "project": report_context.get("project") or {},
        "selected_suite_ids": report_context.get("selected_suite_ids") or [],
        "selected_suite_names": report_context.get("selected_suite_names") or [],
        "generated_at": report_context.get("generated_at"),
        "totals": report_context.get("totals") or {},
        "execution_status_distribution": report_context.get("execution_status_distribution") or {},
        "review_status_distribution": report_context.get("review_status_distribution") or {},
        "bug_status_distribution": report_context.get("bug_status_distribution") or {},
        "requirement_summary": report_context.get("requirement_summary") or {},
        "bug_workflow_summary": report_context.get("bug_workflow_summary") or {},
        "suite_breakdown": report_context.get("suite_breakdown") or [],
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _truncate(value: str, limit: int = 120) -> str:
    text = (value or "").strip().replace("\r", " ").replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _build_requirement_findings(requirement_summary: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []

    traceable_count = _safe_int(requirement_summary.get("traceable_testcase_count"))
    testcase_count = _safe_int(requirement_summary.get("testcase_count"))
    unlinked_count = _safe_int(requirement_summary.get("unlinked_testcase_count"))
    linked_document_count = _safe_int(requirement_summary.get("linked_document_count"))
    linked_module_count = _safe_int(requirement_summary.get("linked_module_count"))

    evidence.append(
        {
            "label": "需求追踪",
            "detail": (
                f"本轮共 {testcase_count} 条测试用例，其中 {traceable_count} 条已关联需求，"
                f"覆盖 {linked_document_count} 份需求文档、{linked_module_count} 个需求模块。"
            ),
        }
    )

    if testcase_count > 0 and unlinked_count > 0:
        findings.append(
            {
                "title": "需求追踪存在断点",
                "detail": f"仍有 {unlinked_count} 条测试用例未写入来源需求文档或模块，报告对需求覆盖面的判断会变弱。",
                "severity": "medium",
            }
        )
        recommendations.append(
            {
                "title": "补齐用例与需求映射",
                "detail": "为未关联需求的测试用例补充来源需求文档ID与来源需求模块ID，方便后续按迭代自动生成更准确的覆盖报告。",
                "priority": "medium",
            }
        )

    modules = requirement_summary.get("modules") or []
    if modules:
        top_modules = "；".join(
            f"{item.get('document_title', '-')}/{item.get('title', '-')}"
            f"（匹配 {item.get('matched_testcase_count', 0)} 条）"
            for item in modules[:3]
        )
        evidence.append({"label": "重点需求模块", "detail": top_modules})

    return findings, recommendations, evidence


def _build_bug_findings(bug_workflow_summary: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []

    fixed_bug_count = _safe_int(bug_workflow_summary.get("fixed_bug_count"))
    submitted_retest_bug_count = _safe_int(bug_workflow_summary.get("submitted_retest_bug_count"))
    closed_bug_count = _safe_int(bug_workflow_summary.get("closed_bug_count"))
    reactivated_bug_count = _safe_int(bug_workflow_summary.get("reactivated_bug_count"))
    retest_failed_total_count = _safe_int(bug_workflow_summary.get("retest_failed_total_count"))

    evidence.append(
        {
            "label": "BUG闭环",
            "detail": (
                f"已修复 {fixed_bug_count} 个，已提交复测 {submitted_retest_bug_count} 个，"
                f"已关闭 {closed_bug_count} 个，重新激活 {reactivated_bug_count} 个。"
            ),
        }
    )

    if retest_failed_total_count > 0:
        findings.append(
            {
                "title": "存在复测回退BUG",
                "detail": f"本轮 BUG 处理过程中累计出现 {retest_failed_total_count} 次复测失败后重新激活，说明修复质量或回归覆盖仍有缺口。",
                "severity": "high",
            }
        )
        recommendations.append(
            {
                "title": "针对反复激活BUG补强回归",
                "detail": "优先对重复复测失败的BUG补充前置检查、回归用例和复盘记录，避免同类问题在下一轮迭代继续回流。",
                "priority": "high",
            }
        )

    top_failed = bug_workflow_summary.get("top_retest_failed_bugs") or []
    if top_failed:
        evidence.append(
            {
                "label": "重复复测失败TOP BUG",
                "detail": "；".join(
                    f"{item.get('title', '-')}"
                    f"（失败 {item.get('failed_retest_count', 0)} 次，当前 {item.get('status', '-')}）"
                    for item in top_failed[:3]
                ),
            }
        )

    return findings, recommendations, evidence


def build_rule_based_iteration_report(report_context: dict[str, Any]) -> IterationTestReportResult:
    totals = report_context.get("totals") or {}
    suite_count = _safe_int(totals.get("suite_count"))
    selected_suite_count = _safe_int(totals.get("selected_suite_count"))
    testcase_count = _safe_int(totals.get("testcase_count"))
    approved_testcase_count = _safe_int(totals.get("approved_testcase_count"))
    bug_count = _safe_int(totals.get("bug_count"))

    execution_distribution = report_context.get("execution_status_distribution") or {}
    passed_count = _safe_int(execution_distribution.get("passed"))
    failed_count = _safe_int(execution_distribution.get("failed"))
    not_executed_count = _safe_int(execution_distribution.get("not_executed"))
    not_applicable_count = _safe_int(execution_distribution.get("not_applicable"))

    requirement_summary = report_context.get("requirement_summary") or {}
    bug_workflow_summary = report_context.get("bug_workflow_summary") or {}

    linked_document_count = _safe_int(requirement_summary.get("linked_document_count"))
    linked_module_count = _safe_int(requirement_summary.get("linked_module_count"))
    traceable_testcase_count = _safe_int(requirement_summary.get("traceable_testcase_count"))
    retest_failed_total_count = _safe_int(bug_workflow_summary.get("retest_failed_total_count"))
    reactivated_bug_count = _safe_int(bug_workflow_summary.get("reactivated_bug_count"))
    closed_bug_count = _safe_int(bug_workflow_summary.get("closed_bug_count"))

    summary = (
        f"本轮报告覆盖 {selected_suite_count} 个所选套件及其下共 {suite_count} 个套件节点，"
        f"纳入 {testcase_count} 条测试用例与 {bug_count} 个 BUG。"
        f"其中已执行通过 {passed_count} 条、失败 {failed_count} 条、未执行 {not_executed_count} 条。"
        f"需求侧已追踪 {linked_document_count} 份文档、{linked_module_count} 个模块；"
        f"BUG 闭环侧累计关闭 {closed_bug_count} 个，复测失败重新激活 {retest_failed_total_count} 次。"
    )

    quality_overview = (
        f"当前用例审核通过 {approved_testcase_count}/{testcase_count} 条，"
        f"可直接纳入评估的需求追踪用例 {traceable_testcase_count} 条。"
        f"执行结果中通过 {passed_count} 条、失败 {failed_count} 条、无需执行 {not_applicable_count} 条，"
        f"整体质量判断已同时参考套件执行结果、需求映射和 BUG 流转记录。"
    )

    risk_overview = (
        f"当前主要风险集中在 {failed_count} 条失败用例、{not_executed_count} 条未执行用例，"
        f"以及 {reactivated_bug_count} 个被重新激活的 BUG。"
        f"若复测失败次数持续增加，说明修复验证链路仍不稳定，需要优先补齐回归与需求追踪。"
    )

    findings: list[dict[str, str]] = []
    recommendations: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []

    if failed_count > 0:
        findings.append(
            {
                "title": "存在执行失败用例",
                "detail": f"本轮共有 {failed_count} 条测试用例执行失败，建议优先定位失败集中模块并结合相关 BUG 一并复核。",
                "severity": "high",
            }
        )
    if not_executed_count > 0:
        findings.append(
            {
                "title": "仍有未执行覆盖空档",
                "detail": f"当前仍有 {not_executed_count} 条测试用例未执行，可能导致部分需求与风险点尚未被本轮验证。",
                "severity": "medium",
            }
        )
    if bug_count > 0 and closed_bug_count < bug_count:
        findings.append(
            {
                "title": "BUG闭环尚未完成",
                "detail": f"当前共有 {bug_count} 个 BUG 纳入报告，其中仅 {closed_bug_count} 个已关闭，仍需继续跟进未闭环问题。",
                "severity": "medium",
            }
        )

    requirement_findings, requirement_recommendations, requirement_evidence = _build_requirement_findings(
        requirement_summary
    )
    bug_findings, bug_recommendations, bug_evidence = _build_bug_findings(bug_workflow_summary)

    findings.extend(requirement_findings)
    findings.extend(bug_findings)
    recommendations.extend(requirement_recommendations)
    recommendations.extend(bug_recommendations)
    evidence.extend(requirement_evidence)
    evidence.extend(bug_evidence)

    if not recommendations:
        recommendations.append(
            {
                "title": "维持当前回归节奏",
                "detail": "继续按套件维度维护执行状态、需求追踪和 BUG 闭环记录，确保后续测试报告可持续复用。",
                "priority": "low",
            }
        )

    suite_breakdown = report_context.get("suite_breakdown") or []
    if suite_breakdown:
        top_suite = max(suite_breakdown, key=lambda item: _safe_int(item.get("failed_testcase_count")))
        if _safe_int(top_suite.get("failed_testcase_count")) > 0:
            evidence.append(
                {
                    "label": "失败用例集中套件",
                    "detail": (
                        f"{top_suite.get('path', top_suite.get('name', '-'))}："
                        f"失败 {_safe_int(top_suite.get('failed_testcase_count'))} 条，"
                        f"待复测BUG {_safe_int(top_suite.get('pending_retest_bug_count'))} 个。"
                    ),
                }
            )

    requirement_documents = requirement_summary.get("documents") or []
    if requirement_documents:
        evidence.append(
            {
                "label": "需求文档范围",
                "detail": "；".join(
                    f"{item.get('title', '-')}"
                    f"（版本 {item.get('version', '-')}, 关联用例 {item.get('linked_testcase_count', 0)} 条）"
                    for item in requirement_documents[:3]
                ),
            }
        )

    note = "报告已基于测试套件、需求追踪和 BUG 闭环记录自动生成；当前未调用外部模型。"

    return IterationTestReportResult(
        used_ai=False,
        note=note,
        model_name=None,
        summary=_truncate(summary, 300),
        quality_overview=_truncate(quality_overview, 300),
        risk_overview=_truncate(risk_overview, 300),
        findings=findings[:8],
        recommendations=recommendations[:8],
        evidence=evidence[:10],
    )


def generate_iteration_test_report(*, user, report_context: dict[str, Any]) -> IterationTestReportResult:
    fallback = build_rule_based_iteration_report(report_context)
    active_config = get_user_active_llm_config(user)
    if not active_config:
        return fallback

    try:
        response_text = invoke_plain_text_llm(
            active_config,
            [
                SystemMessage(content=TEST_REPORT_SYSTEM_PROMPT),
                HumanMessage(content=_build_ai_prompt(report_context)),
            ],
            temperature=0.2,
        )
        payload = _safe_json_loads(response_text)

        summary = _truncate(str(payload.get("summary") or fallback.summary), 300)
        quality_overview = _truncate(
            str(payload.get("quality_overview") or fallback.quality_overview),
            300,
        )
        risk_overview = _truncate(str(payload.get("risk_overview") or fallback.risk_overview), 300)
        findings = _normalize_report_items(payload.get("findings"), kind="finding") or fallback.findings
        recommendations = (
            _normalize_report_items(payload.get("recommendations"), kind="recommendation")
            or fallback.recommendations
        )
        evidence = _normalize_report_items(payload.get("evidence"), kind="evidence") or fallback.evidence

        return IterationTestReportResult(
            used_ai=True,
            note="报告已结合当前模型输出与结构化测试数据自动生成。",
            model_name=getattr(active_config, "name", None) or None,
            summary=summary,
            quality_overview=quality_overview,
            risk_overview=risk_overview,
            findings=findings[:8],
            recommendations=recommendations[:8],
            evidence=evidence[:10],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("生成 AI 测试报告失败，已回退到规则报告: %s", exc, exc_info=True)
        return fallback
