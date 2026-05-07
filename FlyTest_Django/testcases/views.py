from rest_framework import viewsets, permissions, status, filters
from django_filters.rest_framework import (
    DjangoFilterBackend,
)  # 瀵煎叆 DjangoFilterBackend
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db import transaction, close_old_connections
from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import io
import json
import logging
import re
import threading
import time
from collections import defaultdict
from difflib import SequenceMatcher
from copy import deepcopy
from uuid import uuid4

from .models import (
    TestCase,
    TestCaseStep,
    TestCaseModule,
    Project,
    TestCaseScreenshot,
    TestSuite,
    TestExecution,
    TestCaseResult,
    TestCaseAssignment,
    TestReportSnapshot,
    TestBug,
    TestBugAttachment,
    TestBugActivity,
)
from .serializers import (
    TestCaseSerializer,
    TestCaseListSerializer,
    TestCaseModuleSerializer,
    TestCaseScreenshotSerializer,
    TestBugSerializer,
    TestBugListSerializer,
    TestBugAttachmentSerializer,
    TestBugActivitySerializer,
    TestReportSnapshotSerializer,
)
from .permissions import IsProjectMemberForTestCase, IsProjectMemberForTestCaseModule
from .filters import TestBugFilter, TestCaseFilter  # 导入自定义过滤器

# 确保导入项目自定义的权限类
from flytest_django.permissions import HasModelPermission, permission_required
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph_integration.models import get_user_active_llm_config
from langgraph_integration.views import (
    create_llm_instance,
    _extract_llm_response_text,
    invoke_plain_text_llm,
)
from prompts.models import UserPrompt
from requirements.models import RequirementDocument, RequirementModule
from projects.models import ProjectMember
from .ai_test_report_generator import generate_iteration_test_report


logger = logging.getLogger(__name__)
User = get_user_model()
_CASE_GENERATION_JOBS: dict[str, dict] = {}
_CASE_GENERATION_JOBS_LOCK = threading.Lock()
_MAX_REQUIREMENT_CASE_GENERATION_ROUNDS = 3


def _serialize_job_datetime(value):
    if value is None:
        return None
    return value.isoformat()


def _coerce_request_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)

    normalized_value = str(value).strip().lower()
    if normalized_value in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "n", "off", ""}:
        return False
    return bool(normalized_value)


def _get_case_generation_job(job_id: str):
    with _CASE_GENERATION_JOBS_LOCK:
        job = _CASE_GENERATION_JOBS.get(job_id)
        return deepcopy(job) if job else None


def _save_case_generation_job(job_id: str, **updates):
    with _CASE_GENERATION_JOBS_LOCK:
        job = _CASE_GENERATION_JOBS.get(job_id)
        if job is None:
            job = {"id": job_id}
            _CASE_GENERATION_JOBS[job_id] = job
        job.update(updates)
        return deepcopy(job)


def _clear_case_generation_jobs(
    *,
    user_id=None,
    project_id=None,
    test_case_module_id=None,
):
    with _CASE_GENERATION_JOBS_LOCK:
        matched_job_ids = []
        for job_id, job in list(_CASE_GENERATION_JOBS.items()):
            if user_id is not None and job.get("user_id") != user_id:
                continue
            if project_id is not None and job.get("project_id") != project_id:
                continue
            if test_case_module_id is not None and job.get("test_case_module_id") != test_case_module_id:
                continue
            matched_job_ids.append(job_id)

        for job_id in matched_job_ids:
            _CASE_GENERATION_JOBS.pop(job_id, None)

        return matched_job_ids


def _update_case_generation_job_progress(
    job_id: str,
    *,
    progress_percent: int,
    progress_stage: str,
    progress_message: str,
    status: str = "running",
    **extra_updates,
):
    return _save_case_generation_job(
        job_id,
        status=status,
        progress_percent=progress_percent,
        progress_stage=progress_stage,
        progress_message=progress_message,
        **extra_updates,
    )


def _create_case_generation_job(
    job_id: str,
    *,
    user_id,
    project_id,
    requirement_document_id,
    requirement_module_id,
    test_case_module_id,
    prompt_content: str,
    allowed_test_types,
    title_only: bool,
    append_to_existing: bool,
):
    return _save_case_generation_job(
        job_id,
        id=job_id,
        status="pending",
        progress_percent=0,
        progress_stage="queued",
        progress_message="任务已创建，等待开始",
        error_message="",
        generated_count=0,
        summary="",
        gaps=[],
        result_payload=None,
        user_id=user_id,
        project_id=project_id,
        requirement_document_id=requirement_document_id,
        requirement_module_id=requirement_module_id,
        test_case_module_id=test_case_module_id,
        prompt_content=prompt_content,
        allowed_test_types=allowed_test_types,
        title_only=title_only,
        append_to_existing=append_to_existing,
        created_at=timezone.now(),
        started_at=None,
        completed_at=None,
    )


def _mark_case_generation_job_success(job_id: str, result: dict):
    return _update_case_generation_job_progress(
        job_id,
        status="success",
        progress_percent=100,
        progress_stage="completed",
        progress_message="测试用例生成与评审完成",
        generated_count=result.get("generated_count", 0),
        summary=result.get("summary") or "",
        gaps=result.get("gaps") or [],
        result_payload=result,
        error_message="",
        completed_at=timezone.now(),
    )


def _mark_case_generation_job_failed(job_id: str, error_message: str):
    return _update_case_generation_job_progress(
        job_id,
        status="failed",
        progress_percent=100,
        progress_stage="failed",
        progress_message="测试用例生成失败",
        error_message=error_message,
        completed_at=timezone.now(),
    )


def _run_case_generation_progress_heartbeat(
    stop_event: threading.Event,
    progress_callback,
    *,
    start_percent: int = 38,
    end_percent: int = 68,
    interval_seconds: float = 2.0,
):
    """
    在大模型阻塞生成期间平滑推进进度，避免长时间停在固定百分比。
    """
    current_percent = start_percent
    while not stop_event.wait(interval_seconds):
        progress_callback(current_percent, "generate", "AI 正在生成测试用例")
        if current_percent < end_percent:
            current_percent += 3


def _build_case_generation_job_response(job: dict):
    return {
        "job_id": job["id"],
        "status": job.get("status", "pending"),
        "progress_percent": int(job.get("progress_percent", 0) or 0),
        "progress_stage": job.get("progress_stage") or "",
        "progress_message": job.get("progress_message") or "",
        "error_message": job.get("error_message") or "",
        "generated_count": int(job.get("generated_count", 0) or 0),
        "summary": job.get("summary") or "",
        "gaps": job.get("gaps") or [],
        "result_payload": job.get("result_payload") or None,
        "created_at": _serialize_job_datetime(job.get("created_at")),
        "started_at": _serialize_job_datetime(job.get("started_at")),
        "completed_at": _serialize_job_datetime(job.get("completed_at")),
    }


def _normalize_media_url(url: str) -> str:
    """
    规范化媒体 URL，确保正确添加 MEDIA_URL 前缀，
    避免双重前缀问题，例如 `/media//media/...`。
    """
    if not url:
        return url

    # 如果已经是完整的 HTTP URL，直接返回
    if url.startswith("http://") or url.startswith("https://"):
        return url

    # 规范化路径分隔符，将反斜杠替换为正斜杠
    url = url.replace("\\", "/")

    media_url = settings.MEDIA_URL.rstrip("/")  # 通常是 '/media'

    # 如果已经以 MEDIA_URL 开头，直接返回
    if url.startswith(media_url + "/") or url.startswith(media_url):
        return url

    # 如果以 / 开头，去掉开头的 /
    if url.startswith("/"):
        url = url[1:]

    return f"{media_url}/{url}"


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(?P<body>[\s\S]*?)```", re.IGNORECASE)


def _extract_json_payload(text: str):
    """从模型输出中尽量提取 JSON。"""
    if not text:
        raise ValueError("模型未返回内容")

    stripped = text.strip()
    fenced_match = _JSON_BLOCK_RE.search(stripped)
    if fenced_match:
        stripped = fenced_match.group("body").strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    for opening, closing in (("{", "}"), ("[", "]")):
        start = stripped.find(opening)
        end = stripped.rfind(closing)
        if start != -1 and end != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    decoder = json.JSONDecoder()
    candidate_payload = None
    preferred_payload = None
    for index, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        candidate_payload = payload
        if isinstance(payload, dict) and any(
            key in payload for key in ("testcases", "cases", "summary", "gaps")
        ):
            preferred_payload = payload

    if preferred_payload is not None:
        return preferred_payload

    if candidate_payload is not None:
        return candidate_payload

    raise ValueError("无法解析模型返回的 JSON 结果")


def _repair_mojibake_text(value: str):
    text = str(value or "")
    suspicious_markers = ("å", "æ", "ç", "é", "ï¼", "â€", "Ã")
    if not any(marker in text for marker in suspicious_markers):
        return text

    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired if repaired else text


def _repair_payload_mojibake(payload):
    if isinstance(payload, dict):
        return {
            _repair_mojibake_text(key): _repair_payload_mojibake(value)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_repair_payload_mojibake(item) for item in payload]
    if isinstance(payload, str):
        return _repair_mojibake_text(payload)
    return payload


def _normalize_level(level: str | None) -> str:
    candidate = str(level or "").upper().strip()
    return candidate if candidate in {"P0", "P1", "P2", "P3"} else "P2"


def _normalize_test_type(test_type: str | None, allowed_types: list[str]) -> str:
    candidate = str(test_type or "").strip()
    if candidate in allowed_types:
        return candidate
    return allowed_types[0] if allowed_types else "functional"


_TEST_TYPE_LABELS = {
    "smoke": "冒烟测试",
    "functional": "功能测试",
    "boundary": "边界测试",
    "exception": "异常测试",
    "permission": "权限测试",
    "security": "安全测试",
    "compatibility": "兼容性测试",
}


def _get_test_type_display_name(test_type: str | None) -> str:
    normalized_type = str(test_type or "").strip()
    if not normalized_type:
        return "未指定类型"
    return _TEST_TYPE_LABELS.get(normalized_type, normalized_type)


def _normalize_generated_cases(payload, *, allowed_test_types: list[str], title_only: bool):
    """校验并规整模型返回的测试用例。"""
    if isinstance(payload, list):
        raw_cases = payload
        gaps = []
        summary = ""
    elif isinstance(payload, dict):
        raw_cases = payload.get("testcases") or payload.get("cases") or []
        gaps = payload.get("gaps") or payload.get("missing_info") or []
        summary = str(payload.get("summary") or "").strip()
    else:
        raise ValueError("模型返回格式不正确")

    if not isinstance(raw_cases, list):
        raise ValueError("模型返回的 testcases 字段不是数组")

    normalized_cases = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue

        raw_preconditions = item.get("precondition") or item.get("preconditions") or ""
        if isinstance(raw_preconditions, list):
            precondition = "\n".join(
                str(entry).strip() for entry in raw_preconditions if str(entry).strip()
            ).strip()
        else:
            precondition = str(raw_preconditions).strip()

        level = _normalize_level(item.get("level") or item.get("priority"))
        test_type = _normalize_test_type(item.get("test_type"), allowed_test_types)

        raw_steps = item.get("steps") or []
        normalized_steps = []
        if isinstance(raw_steps, list):
            for step in raw_steps:
                if isinstance(step, str):
                    description = step.strip()
                    if description:
                        normalized_steps.append(
                            {
                                "description": description,
                                "expected_result": "系统表现符合需求预期",
                            }
                        )
                    continue
                if not isinstance(step, dict):
                    continue
                description = str(step.get("description") or step.get("step") or "").strip()
                expected_result = str(
                    step.get("expected_result") or step.get("expected") or step.get("result") or ""
                ).strip()
                if not description and not expected_result:
                    continue
                normalized_steps.append(
                    {
                        "description": description or "执行当前步骤",
                        "expected_result": expected_result or "系统表现符合需求预期",
                    }
                )

        if not title_only and not normalized_steps:
            continue

        normalized_cases.append(
            {
                "name": name,
                "precondition": precondition,
                "level": level,
                "test_type": test_type,
                "steps": normalized_steps,
            }
        )

    if not normalized_cases:
        raise ValueError("模型未生成可保存的测试用例")

    normalized_gaps = [str(gap).strip() for gap in (gaps or []) if str(gap).strip()]
    return {
        "summary": summary,
        "gaps": normalized_gaps,
        "testcases": normalized_cases,
    }


_REQUIREMENT_DOCUMENT_ID_PATTERNS = (
    re.compile(r"来源需求文档ID[:：]?\s*([0-9a-fA-F-]+)"),
    re.compile(r"需求文档ID[:：]?\s*([0-9a-fA-F-]+)"),
)
_REQUIREMENT_MODULE_ID_PATTERNS = (
    re.compile(r"来源需求模块ID[:：]?\s*([0-9a-fA-F-]+)"),
    re.compile(r"需求模块ID[:：]?\s*([0-9a-fA-F-]+)"),
)


def _extract_requirement_traceability(notes: str | None):
    if not notes:
        return None

    document_id = None
    module_id = None

    for pattern in _REQUIREMENT_DOCUMENT_ID_PATTERNS:
        match = pattern.search(notes)
        if match:
            document_id = match.group(1).strip()
            break

    for pattern in _REQUIREMENT_MODULE_ID_PATTERNS:
        match = pattern.search(notes)
        if match:
            module_id = match.group(1).strip()
            break

    if document_id and module_id:
        return document_id, module_id
    return None


def _normalize_case_signature(name: str | None) -> str:
    return re.sub(r"\s+", "", str(name or "").strip()).casefold()


def _normalize_case_text_fragment(value: str | None) -> str:
    normalized_value = str(value or "").strip().casefold()
    normalized_value = re.sub(r"\s+", "", normalized_value)
    normalized_value = re.sub(r"[，。；：、,.!?\-_/\\()\[\]{}\"'`~@#$%^&*+=<>|]", "", normalized_value)
    return normalized_value


def _build_case_content_signature(*, precondition: str | None, test_type: str | None, steps) -> str:
    normalized_precondition = _normalize_case_text_fragment(precondition)
    normalized_test_type = _normalize_case_text_fragment(test_type)
    normalized_steps = []

    for step in steps or []:
        if isinstance(step, dict):
            description = step.get("description")
            expected_result = step.get("expected_result")
        else:
            description = getattr(step, "description", "")
            expected_result = getattr(step, "expected_result", "")

        normalized_description = _normalize_case_text_fragment(description)
        normalized_expected_result = _normalize_case_text_fragment(expected_result)
        if normalized_description or normalized_expected_result:
            normalized_steps.append(f"{normalized_description}>{normalized_expected_result}")

    # 标题生成模式下通常没有步骤，如果只剩测试类型/空前置条件，
    # 内容签名会过于宽泛，容易把不同标题误判成重复。
    if not normalized_steps and not normalized_precondition:
        return ""

    signature_parts = [
        normalized_test_type,
        normalized_precondition,
        "||".join(normalized_steps),
    ]
    signature = "::".join(signature_parts).strip(":")
    return signature


def _build_case_semantic_text(
    *,
    name: str | None,
    precondition: str | None,
    test_type: str | None,
    steps,
) -> str:
    fragments = [
        _normalize_case_text_fragment(test_type),
        _normalize_case_text_fragment(name),
        _normalize_case_text_fragment(precondition),
    ]

    for step in steps or []:
        if isinstance(step, dict):
            description = step.get("description")
            expected_result = step.get("expected_result")
        else:
            description = getattr(step, "description", "")
            expected_result = getattr(step, "expected_result", "")
        fragments.append(_normalize_case_text_fragment(description))
        fragments.append(_normalize_case_text_fragment(expected_result))

    semantic_text = " ".join(fragment for fragment in fragments if fragment).strip()
    return semantic_text


def _is_semantic_duplicate(candidate_text: str, existing_texts) -> bool:
    normalized_candidate = str(candidate_text or "").strip()
    if not normalized_candidate:
        return False

    for raw_existing_text in existing_texts or []:
        normalized_existing_text = str(raw_existing_text or "").strip()
        if not normalized_existing_text:
            continue
        if normalized_candidate == normalized_existing_text:
            return True
        shorter_length = min(len(normalized_candidate), len(normalized_existing_text))
        if shorter_length >= 12 and (
            normalized_candidate in normalized_existing_text or normalized_existing_text in normalized_candidate
        ):
            return True
        similarity = SequenceMatcher(None, normalized_candidate, normalized_existing_text).ratio()
        if similarity >= 0.92:
            return True

    return False


def _build_existing_case_context(test_cases):
    context_items = []
    name_signatures = set()
    content_signatures = set()
    semantic_texts = []

    for case in test_cases:
        ordered_steps = list(case.steps.all().order_by("step_number"))
        name_signatures.add(_normalize_case_signature(case.name))
        content_signature = _build_case_content_signature(
            precondition=case.precondition,
            test_type=case.test_type,
            steps=ordered_steps,
        )
        if content_signature:
            content_signatures.add(content_signature)
        semantic_text = _build_case_semantic_text(
            name=case.name,
            precondition=case.precondition,
            test_type=case.test_type,
            steps=ordered_steps,
        )
        if semantic_text:
            semantic_texts.append(semantic_text)
        context_items.append(
            {
                "id": case.id,
                "name": case.name,
                "precondition": case.precondition or "",
                "level": case.level,
                "test_type": case.test_type,
                "steps": [
                    {
                        "description": step.description,
                        "expected_result": step.expected_result,
                    }
                    for step in ordered_steps[:5]
                ],
            }
        )

    return context_items, name_signatures, content_signatures, semantic_texts


def _build_progress_reporter(progress_callback, start_percent: int, end_percent: int):
    if progress_callback is None:
        return None

    safe_start = max(0, min(int(start_percent), 100))
    safe_end = max(safe_start, min(int(end_percent), 100))
    total_span = max(safe_end - safe_start, 0)

    def reporter(percent: int, stage: str, message: str):
        bounded_percent = max(0, min(int(percent), 100))
        mapped_percent = safe_start + round((bounded_percent / 100) * total_span)
        progress_callback(mapped_percent, stage, message)

    return reporter


def _deduplicate_text_items(items):
    deduplicated_items = []
    seen_keys = set()

    for item in items or []:
        normalized_item = str(item or "").strip()
        if not normalized_item:
            continue
        item_key = normalized_item.casefold()
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        deduplicated_items.append(normalized_item)

    return deduplicated_items


def _serialize_cases_for_ai_review(test_cases, *, include_steps: bool):
    serialized_cases = []
    for case in test_cases:
        item = {
            "id": case.id,
            "name": case.name,
            "precondition": case.precondition or "",
            "level": case.level,
            "test_type": case.test_type,
        }
        if include_steps:
            item["steps"] = [
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "expected_result": step.expected_result,
                }
                for step in case.steps.all().order_by("step_number")
            ]
        serialized_cases.append(item)
    return serialized_cases


def _normalize_generation_review(payload):
    if not isinstance(payload, dict):
        raise ValueError("AI 评审结果格式不正确")

    is_complete = bool(payload.get("is_complete"))
    summary = str(payload.get("summary") or "").strip()
    next_generation_guidance = str(payload.get("next_generation_guidance") or "").strip()
    raw_missing_coverages = payload.get("missing_coverages") or payload.get("missing_points") or []
    raw_duplicate_case_names = payload.get("duplicate_case_names") or []
    coverage_score = payload.get("coverage_score")

    if isinstance(coverage_score, bool):
        coverage_score = None
    elif coverage_score is not None:
        try:
            coverage_score = max(0, min(int(coverage_score), 100))
        except (TypeError, ValueError):
            coverage_score = None

    missing_coverages = [str(item).strip() for item in raw_missing_coverages if str(item).strip()]
    duplicate_case_names = [str(item).strip() for item in raw_duplicate_case_names if str(item).strip()]

    return {
        "is_complete": is_complete,
        "summary": summary,
        "coverage_score": coverage_score,
        "missing_coverages": missing_coverages,
        "duplicate_case_names": duplicate_case_names,
        "next_generation_guidance": next_generation_guidance,
    }


def _collect_case_test_types(test_cases) -> set[str]:
    collected_types = set()
    for case in test_cases or []:
        if isinstance(case, dict):
            raw_test_type = case.get("test_type")
        else:
            raw_test_type = getattr(case, "test_type", "")
        normalized_test_type = str(raw_test_type or "").strip()
        if normalized_test_type:
            collected_types.add(normalized_test_type)
    return collected_types


def _build_case_review_text(case) -> str:
    if isinstance(case, dict):
        name = case.get("name")
        precondition = case.get("precondition")
        steps = case.get("steps") or []
    else:
        name = getattr(case, "name", "")
        precondition = getattr(case, "precondition", "")
        steps = list(getattr(case, "steps", []).all().order_by("step_number")) if getattr(case, "steps", None) else []

    fragments = [str(name or "").strip(), str(precondition or "").strip()]
    for step in steps or []:
        if isinstance(step, dict):
            description = step.get("description")
            expected_result = step.get("expected_result")
        else:
            description = getattr(step, "description", "")
            expected_result = getattr(step, "expected_result", "")
        fragments.append(str(description or "").strip())
        fragments.append(str(expected_result or "").strip())
    return "\n".join(fragment for fragment in fragments if fragment)


_FUNCTIONAL_VALID_HINTS = (
    "成功",
    "正常",
    "正确",
    "有效",
    "合法",
    "通过",
    "登录",
    "进入",
    "跳转",
    "记住登录",
)

_FUNCTIONAL_INVALID_HINTS = (
    "失败",
    "错误",
    "异常",
    "无效",
    "非法",
    "为空",
    "空值",
    "必填",
    "不存在",
    "未注册",
    "格式不正确",
    "提示",
    "拒绝",
    "拦截",
)

_BOUNDARY_HINTS = (
    "边界",
    "最小",
    "最大",
    "上限",
    "下限",
    "长度",
    "临界",
    "0",
    "1",
    "空格",
)

_EXCEPTION_HINTS = (
    "异常",
    "失败",
    "错误",
    "超时",
    "中断",
    "无响应",
    "断网",
    "接口异常",
    "服务异常",
    "崩溃",
)

_PERMISSION_HINTS = (
    "权限",
    "无权",
    "未授权",
    "禁止",
    "越权",
    "角色",
    "管理员",
    "普通用户",
    "访客",
    "拒绝访问",
)


def _detect_functional_equivalence_partition_gaps(test_cases) -> list[str]:
    has_valid_partition = False
    has_invalid_partition = False

    for case in test_cases or []:
        case_text = _build_case_review_text(case)
        if not case_text:
            continue

        if any(keyword in case_text for keyword in _FUNCTIONAL_VALID_HINTS):
            has_valid_partition = True
        if any(keyword in case_text for keyword in _FUNCTIONAL_INVALID_HINTS):
            has_invalid_partition = True

        if has_valid_partition and has_invalid_partition:
            break

    gaps = []
    if not has_valid_partition:
        gaps.append("功能测试缺少有效等价类覆盖")
    if not has_invalid_partition:
        gaps.append("功能测试缺少无效等价类覆盖")
    return gaps


def _detect_keyword_coverage_gap(test_cases, *, keywords, missing_message: str) -> list[str]:
    for case in test_cases or []:
        case_text = _build_case_review_text(case)
        if case_text and any(keyword in case_text for keyword in keywords):
            return []
    return [missing_message]


def _apply_review_guardrails(review_result: dict, *, allowed_test_types: list[str], all_cases) -> dict:
    guarded_result = dict(review_result or {})
    missing_coverages = list(guarded_result.get("missing_coverages") or [])
    next_generation_guidance = str(guarded_result.get("next_generation_guidance") or "").strip()

    existing_case_types = _collect_case_test_types(all_cases)
    missing_test_types = [
        test_type for test_type in allowed_test_types if test_type and test_type not in existing_case_types
    ]
    if missing_test_types:
        missing_coverages.extend(
            [f"未覆盖所选测试类型：{_get_test_type_display_name(test_type)}" for test_type in missing_test_types]
        )

        guidance_segments = [next_generation_guidance] if next_generation_guidance else []
        guidance_segments.append(
            "请优先补充以下测试类型的缺失用例：" +
            "、".join(_get_test_type_display_name(test_type) for test_type in missing_test_types)
        )
        guarded_result["next_generation_guidance"] = "；".join(
            segment.strip() for segment in guidance_segments if segment and segment.strip()
        )
        guarded_result["is_complete"] = False

        coverage_score = guarded_result.get("coverage_score")
        if isinstance(coverage_score, int):
            guarded_result["coverage_score"] = min(
                coverage_score,
                max(0, 100 - len(missing_test_types) * 20),
            )

    if "functional" in allowed_test_types:
        functional_cases = []
        for case in all_cases or []:
            if isinstance(case, dict):
                raw_test_type = case.get("test_type")
            else:
                raw_test_type = getattr(case, "test_type", "")
            if str(raw_test_type or "").strip() == "functional":
                functional_cases.append(case)

        if functional_cases:
            functional_gaps = _detect_functional_equivalence_partition_gaps(functional_cases)
            if functional_gaps:
                missing_coverages.extend(functional_gaps)
                guidance_segments = [guarded_result.get("next_generation_guidance", "").strip()]
                guidance_segments.append("请补充功能测试中的有效等价类与无效等价类场景，避免只覆盖单一正向流程")
                guarded_result["next_generation_guidance"] = "；".join(
                    segment.strip() for segment in guidance_segments if segment and segment.strip()
                )
                guarded_result["is_complete"] = False
                coverage_score = guarded_result.get("coverage_score")
                if isinstance(coverage_score, int):
                    guarded_result["coverage_score"] = min(
                        coverage_score,
                        max(0, 100 - len(functional_gaps) * 15),
                    )

    typed_guardrails = (
        ("boundary", _BOUNDARY_HINTS, "边界测试缺少临界值或范围边界覆盖"),
        ("exception", _EXCEPTION_HINTS, "异常测试缺少失败、异常或中断场景覆盖"),
        ("permission", _PERMISSION_HINTS, "权限测试缺少角色权限或越权场景覆盖"),
    )
    for target_type, keywords, missing_message in typed_guardrails:
        if target_type not in allowed_test_types:
            continue

        target_cases = []
        for case in all_cases or []:
            if isinstance(case, dict):
                raw_test_type = case.get("test_type")
            else:
                raw_test_type = getattr(case, "test_type", "")
            if str(raw_test_type or "").strip() == target_type:
                target_cases.append(case)

        if not target_cases:
            continue

        guardrail_gaps = _detect_keyword_coverage_gap(
            target_cases,
            keywords=keywords,
            missing_message=missing_message,
        )
        if not guardrail_gaps:
            continue

        missing_coverages.extend(guardrail_gaps)
        guidance_segments = [guarded_result.get("next_generation_guidance", "").strip()]
        guidance_segments.append(f"请补充{_get_test_type_display_name(target_type)}中的关键覆盖点，避免只有单一场景")
        guarded_result["next_generation_guidance"] = "；".join(
            segment.strip() for segment in guidance_segments if segment and segment.strip()
        )
        guarded_result["is_complete"] = False
        coverage_score = guarded_result.get("coverage_score")
        if isinstance(coverage_score, int):
            guarded_result["coverage_score"] = min(
                coverage_score,
                max(0, 100 - len(guardrail_gaps) * 15),
            )

    guarded_result["missing_coverages"] = _deduplicate_text_items(missing_coverages)

    if not guarded_result["is_complete"] and not str(guarded_result.get("summary") or "").strip():
        if guarded_result["missing_coverages"]:
            guarded_result["summary"] = "覆盖仍不完整，仍有缺失测试点需要补充"
        else:
            guarded_result["summary"] = "覆盖仍不完整，需要继续补充测试用例"

    return guarded_result


def _infer_requirement_from_module_cases(project, test_case_module):
    related_cases = (
        TestCase.objects.filter(project=project, module=test_case_module)
        .exclude(notes__isnull=True)
        .exclude(notes__exact="")
        .only("notes")
        .order_by("-id")
    )
    for case in related_cases:
        traceability = _extract_requirement_traceability(case.notes)
        if traceability:
            return traceability
    return None


def _review_generated_testcase_coverage(
    *,
    active_config,
    requirement_document,
    requirement_module,
    test_case_module,
    allowed_test_types: list[str],
    title_only: bool,
    prompt_content: str,
    append_to_existing: bool,
    round_index: int,
    all_cases,
    round_generated_cases,
    progress_callback=None,
):
    if progress_callback:
        progress_callback(10, "review", f"AI 正在评审第 {round_index} 轮覆盖率")

    system_prompt = """
你是 Flytest 的测试用例评审 Agent。请严格根据需求、生成模式、已选测试类型、
当前模块已有测试用例以及本轮新生成用例，判断覆盖是否完整。

规则：
1. 只输出 JSON，不要输出 Markdown，不要输出额外解释。
2. 如果覆盖不完整，必须指出缺失覆盖点，并给出下一轮补生成指引。
3. 如果发现重复或高度重叠的用例标题，要明确指出。
4. 必须基于当前输入完成评审，不要向用户追问。

JSON 结构：
{
  "is_complete": true,
  "summary": "一句话总结",
  "coverage_score": 0,
  "missing_coverages": ["缺失点"],
  "duplicate_case_names": ["重复用例1"],
  "next_generation_guidance": "需要补生成时给出指引，否则返回空字符串"
}
""".strip()

    user_prompt = json.dumps(
        {
            "task": "review_requirement_testcase_coverage",
            "round_index": round_index,
            "generation_mode": "title_only" if title_only else "full",
            "append_to_existing": append_to_existing,
            "prompt_content": prompt_content,
            "allowed_test_types": allowed_test_types,
            "requirement_document": {
                "id": str(requirement_document.id),
                "title": requirement_document.title,
            },
            "requirement_module": {
                "id": str(requirement_module.id),
                "title": requirement_module.title,
                "content": requirement_module.content,
            },
            "test_case_module": {
                "id": test_case_module.id,
                "name": test_case_module.name,
            },
            "current_module_cases": _serialize_cases_for_ai_review(
                all_cases,
                include_steps=not title_only,
            ),
            "current_round_generated_cases": _serialize_cases_for_ai_review(
                round_generated_cases,
                include_steps=not title_only,
            ),
        },
        ensure_ascii=False,
        indent=2,
    )

    response_text = invoke_plain_text_llm(
        active_config,
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        temperature=0.1,
    )
    review_payload = _repair_payload_mojibake(_extract_json_payload(response_text))
    review_result = _normalize_generation_review(review_payload)
    review_result = _apply_review_guardrails(
        review_result,
        allowed_test_types=allowed_test_types,
        all_cases=all_cases,
    )

    if progress_callback:
        progress_callback(
            100,
            "review",
            "AI 覆盖评审完成" if review_result["is_complete"] else "AI 评审认为仍需补充生成",
        )
    return review_result


def _generate_testcases_from_requirement(
    *,
    user,
    project,
    requirement_document,
    requirement_module,
    test_case_module,
    prompt_content: str,
    allowed_test_types: list[str],
    title_only: bool,
    append_to_existing: bool = False,
    active_config=None,
    progress_range: tuple[int, int] = (0, 100),
    progress_callback=None,
):
    emit_progress = _build_progress_reporter(progress_callback, progress_range[0], progress_range[1])
    if emit_progress:
        emit_progress(10, "prepare", "正在整理需求内容")

    active_config = active_config or get_user_active_llm_config(user)
    if active_config is None:
        raise ValueError("当前没有可用的模型配置，请先启用一个 LLM 配置")

    existing_test_cases = list(
        TestCase.objects.filter(project=project, module=test_case_module)
        .prefetch_related("steps")
        .order_by("id")
    )
    (
        existing_case_context,
        existing_case_name_signatures,
        existing_case_content_signatures,
        existing_case_semantic_texts,
    ) = _build_existing_case_context(existing_test_cases)

    system_prompt = """
你是 Flytest 的测试用例生成器。你的任务是基于给定需求模块，
直接生成可保存的中文测试用例。

硬性规则：
1. 只能基于当前给定的需求文档标题、模块标题、模块内容生成。
2. 不要向用户追问，不要要求补充文档，不要输出英文对话。
3. 只输出 JSON，不要输出 Markdown，不要输出解释性文字。
4. JSON 结构必须是：
{
  "summary": "一句话总结",
  "gaps": ["如有缺口则列出，没有则返回空数组"],
  "testcases": [
    {
      "name": "测试用例标题",
      "precondition": "前置条件，没有可留空",
      "level": "P0|P1|P2|P3",
      "test_type": "smoke|functional|boundary|exception|permission|security|compatibility",
      "steps": [
        {
          "description": "步骤描述",
          "expected_result": "预期结果"
        }
      ]
    }
  ]
}
5. 如果是标题生成模式，steps 返回空数组即可。
6. 必须覆盖有效等价类和无效等价类，主流程要完整。
7. 输出内容必须是简体中文。
""".strip()

    task_type = "标题生成" if title_only else "完整生成"
    user_prompt = f"""
【任务类型】{task_type}
【项目ID】{project.id}
【保存测试用例模块ID】{test_case_module.id}
【需求文档ID】{requirement_document.id}
【需求文档标题】{requirement_document.title}
【需求模块ID】{requirement_module.id}
【需求模块标题】{requirement_module.title}
【需求模块内容】{requirement_module.content}

【测试类型要求】{"、".join(allowed_test_types)}

【补充约束】
- 不要再次索要需求文档。
- 如果信息有缺口，只能写入 gaps，同时继续给出可生成的用例。
- {"仅生成标题，不要生成步骤" if title_only else "请生成可直接执行的步骤和预期结果"}
""".strip()
    if prompt_content:
        user_prompt += f"\n\n【补充提示词】\n{prompt_content}"

    if append_to_existing:
        if existing_case_context:
            existing_case_text = json.dumps(existing_case_context[:80], ensure_ascii=False, indent=2)
            user_prompt += (
                "\n\n【当前模块已有测试用例】\n"
                f"{existing_case_text}\n"
                "这些用例已经存在于当前模块，本次只允许追加生成新的测试用例，不要重复已有测试点，也不要仅仅换一个标题复述相同步骤流程。"
            )
        else:
            user_prompt += "\n\n【当前模块已有测试用例】\n当前模块暂无已有测试用例，但本次仍然是追加生成模式，请避免重复语义。"

    if emit_progress:
        emit_progress(35, "generate", "AI 正在生成测试用例")

    heartbeat_stop_event = None
    heartbeat_thread = None
    if emit_progress:
        heartbeat_stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_run_case_generation_progress_heartbeat,
            args=(heartbeat_stop_event, emit_progress),
            kwargs={"start_percent": 38, "end_percent": 68},
            daemon=True,
        )
        heartbeat_thread.start()

    try:
        response_text = invoke_plain_text_llm(
            active_config,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
            temperature=0.2,
        )
    finally:
        if heartbeat_stop_event is not None:
            heartbeat_stop_event.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=0.2)

    if emit_progress:
        emit_progress(72, "parse", "正在解析 AI 返回结果")

    payload = _extract_json_payload(response_text)
    payload = _repair_payload_mojibake(payload)
    normalized = _normalize_generated_cases(
        payload,
        allowed_test_types=allowed_test_types,
        title_only=title_only,
    )

    deduplicated_cases = []
    generated_name_signatures = set()
    generated_content_signatures = set()
    generated_semantic_texts = []
    skipped_duplicate_names = []
    for case_data in normalized["testcases"]:
        name_signature = _normalize_case_signature(case_data["name"])
        content_signature = _build_case_content_signature(
            precondition=case_data.get("precondition"),
            test_type=case_data.get("test_type"),
            steps=case_data.get("steps") or [],
        )
        semantic_text = _build_case_semantic_text(
            name=case_data.get("name"),
            precondition=case_data.get("precondition"),
            test_type=case_data.get("test_type"),
            steps=case_data.get("steps") or [],
        )
        if not name_signature and not content_signature:
            continue
        if (
            (name_signature and (name_signature in existing_case_name_signatures or name_signature in generated_name_signatures))
            or (
                content_signature
                and (
                    content_signature in existing_case_content_signatures
                    or content_signature in generated_content_signatures
                )
            )
            or _is_semantic_duplicate(semantic_text, existing_case_semantic_texts)
            or _is_semantic_duplicate(semantic_text, generated_semantic_texts)
        ):
            skipped_duplicate_names.append(case_data["name"])
            continue
        if name_signature:
            generated_name_signatures.add(name_signature)
        if content_signature:
            generated_content_signatures.add(content_signature)
        if semantic_text:
            generated_semantic_texts.append(semantic_text)
        deduplicated_cases.append(case_data)

    normalized["testcases"] = deduplicated_cases

    traceability_lines = [
        f"来源需求文档ID: {requirement_document.id}",
        f"来源需求文档标题: {requirement_document.title}",
        f"来源需求模块ID: {requirement_module.id}",
        f"来源需求模块标题: {requirement_module.title}",
    ]
    if normalized["gaps"]:
        traceability_lines.append("需求缺口: " + "；".join(normalized["gaps"]))
    if normalized["summary"]:
        traceability_lines.append("AI生成摘要: " + normalized["summary"])
    if skipped_duplicate_names:
        traceability_lines.append("本次跳过重复用例: " + "；".join(skipped_duplicate_names))
    traceability_note = "\n".join(traceability_lines)

    if emit_progress:
        emit_progress(88, "save", "正在保存测试用例")

    created_cases = []
    total_cases = len(normalized["testcases"])
    with transaction.atomic():
        for case_index, case_data in enumerate(normalized["testcases"], start=1):
            test_case = TestCase.objects.create(
                project=project,
                module=test_case_module,
                name=case_data["name"],
                precondition=case_data["precondition"],
                level=case_data["level"],
                test_type=case_data["test_type"],
                notes=traceability_note,
                creator=user,
            )
            for index, step in enumerate(case_data["steps"], start=1):
                TestCaseStep.objects.create(
                    test_case=test_case,
                    step_number=index,
                    description=step["description"],
                    expected_result=step["expected_result"],
                    creator=user,
                )
            created_cases.append(test_case)
            if emit_progress and total_cases > 0:
                save_percent = 88 + int((case_index / total_cases) * 10)
                emit_progress(
                    min(save_percent, 98),
                    "save",
                    f"正在保存测试用例 ({case_index}/{total_cases})",
                )

    serializer = TestCaseSerializer(created_cases, many=True)
    result_message = f"已生成并保存 {len(created_cases)} 条测试用例"
    if len(created_cases) == 0:
        if skipped_duplicate_names:
            result_message = "本轮未新增测试用例，AI 生成结果已全部与现有用例重复"
        else:
            result_message = "本轮未新增测试用例，AI 未产出可保存的有效结果"
    return {
        "message": result_message,
        "generated_count": len(created_cases),
        "gaps": normalized["gaps"],
        "summary": normalized["summary"],
        "data": serializer.data,
        "skipped_duplicate_names": _deduplicate_text_items(skipped_duplicate_names),
        "skipped_duplicate_count": len(_deduplicate_text_items(skipped_duplicate_names)),
    }


def _generate_and_review_testcases_from_requirement(
    *,
    user,
    project,
    requirement_document,
    requirement_module,
    test_case_module,
    prompt_content: str,
    allowed_test_types: list[str],
    title_only: bool,
    append_to_existing: bool = False,
    progress_callback=None,
):
    active_config = get_user_active_llm_config(user)
    if active_config is None:
        raise ValueError("当前没有可用的模型配置，请先启用一个 LLM 配置")

    all_generated_cases = []
    all_gaps = []
    review_history = []
    all_skipped_duplicate_names = []
    final_review = {
        "is_complete": False,
        "summary": "",
        "coverage_score": None,
        "missing_coverages": [],
        "duplicate_case_names": [],
        "next_generation_guidance": "",
    }
    current_prompt_content = prompt_content

    for round_index in range(1, _MAX_REQUIREMENT_CASE_GENERATION_ROUNDS + 1):
        round_start = int(((round_index - 1) / _MAX_REQUIREMENT_CASE_GENERATION_ROUNDS) * 90)
        round_mid = round_start + int((90 / _MAX_REQUIREMENT_CASE_GENERATION_ROUNDS) * 0.72)
        round_end = int((round_index / _MAX_REQUIREMENT_CASE_GENERATION_ROUNDS) * 90)

        round_result = _generate_testcases_from_requirement(
            user=user,
            project=project,
            requirement_document=requirement_document,
            requirement_module=requirement_module,
            test_case_module=test_case_module,
            prompt_content=current_prompt_content,
            allowed_test_types=allowed_test_types,
            title_only=title_only,
            append_to_existing=(append_to_existing or round_index > 1),
            active_config=active_config,
            progress_range=(round_start, round_mid),
            progress_callback=progress_callback,
        )

        all_generated_cases.extend(round_result["data"])
        all_gaps.extend(round_result["gaps"])
        all_skipped_duplicate_names.extend(round_result.get("skipped_duplicate_names") or [])

        current_module_cases = list(
            TestCase.objects.filter(project=project, module=test_case_module)
            .prefetch_related("steps")
            .order_by("id")
        )
        current_round_case_ids = {item["id"] for item in round_result["data"] if item.get("id")}
        current_round_cases = [case for case in current_module_cases if case.id in current_round_case_ids]

        review_progress = _build_progress_reporter(progress_callback, round_mid, round_end)
        final_review = _review_generated_testcase_coverage(
            active_config=active_config,
            requirement_document=requirement_document,
            requirement_module=requirement_module,
            test_case_module=test_case_module,
            allowed_test_types=allowed_test_types,
            title_only=title_only,
            prompt_content=current_prompt_content,
            append_to_existing=(append_to_existing or round_index > 1),
            round_index=round_index,
            all_cases=current_module_cases,
            round_generated_cases=current_round_cases,
            progress_callback=review_progress,
        )
        final_review["missing_coverages"] = _deduplicate_text_items(final_review["missing_coverages"])
        final_review["duplicate_case_names"] = _deduplicate_text_items(final_review["duplicate_case_names"])

        review_history.append(
            {
                "round": round_index,
                "generated_count": round_result["generated_count"],
                "summary": final_review["summary"],
                "coverage_score": final_review["coverage_score"],
                "coverage_complete": final_review["is_complete"],
                "missing_coverages": final_review["missing_coverages"],
                "duplicate_case_names": final_review["duplicate_case_names"],
            }
        )

        if final_review["is_complete"] or round_index >= _MAX_REQUIREMENT_CASE_GENERATION_ROUNDS:
            break

        guidance_parts = [current_prompt_content.strip()]
        guidance_parts.append("以下是上一轮 AI 评审结论，请只补充缺失覆盖点，不要重复已有测试用例：")
        guidance_parts.append(f"评审总结：{final_review['summary'] or '当前覆盖仍不完整'}")
        if final_review["missing_coverages"]:
            guidance_parts.append(
                "缺失覆盖点：\n" + "\n".join(f"- {item}" for item in final_review["missing_coverages"] if item)
            )
        if final_review["duplicate_case_names"]:
            guidance_parts.append("避免与这些用例重复：" + "；".join(final_review["duplicate_case_names"]))
        if final_review["next_generation_guidance"]:
            guidance_parts.append("补生成指引：" + final_review["next_generation_guidance"])
        guidance_parts.append("要求：仅生成当前模块仍缺失的测试用例，禁止重复输出已有测试点。")
        current_prompt_content = "\n\n".join(part for part in guidance_parts if part and part.strip())

    deduplicated_gaps = _deduplicate_text_items(all_gaps)
    missing_coverage_points = _deduplicate_text_items(final_review["missing_coverages"])
    duplicate_case_names = _deduplicate_text_items(final_review["duplicate_case_names"])
    skipped_duplicate_names = _deduplicate_text_items(all_skipped_duplicate_names)

    coverage_complete = bool(final_review["is_complete"])
    if progress_callback:
        progress_callback(100, "completed", "测试用例生成与评审完成")

    result_message = f"已生成并评审 {len(all_generated_cases)} 条测试用例"
    if len(all_generated_cases) == 0:
        if skipped_duplicate_names:
            result_message = "未新增测试用例，AI 生成结果均与现有用例重复"
        elif missing_coverage_points:
            result_message = "未新增测试用例，当前覆盖仍不完整，请根据缺失点继续补充"
        else:
            result_message = "未新增测试用例，本次未得到可保存的生成结果"

    return {
        "message": result_message,
        "generated_count": len(all_generated_cases),
        "gaps": deduplicated_gaps,
        "summary": final_review["summary"] or "",
        "data": all_generated_cases,
        "review_completed": True,
        "coverage_complete": coverage_complete,
        "coverage_score": final_review["coverage_score"],
        "review_rounds": len(review_history),
        "review_history": review_history,
        "missing_coverage_points": missing_coverage_points,
        "duplicate_case_names": duplicate_case_names,
        "skipped_duplicate_names": skipped_duplicate_names,
        "skipped_duplicate_count": len(skipped_duplicate_names),
        "next_generation_guidance": final_review["next_generation_guidance"],
    }



def _run_requirement_case_generation_job(job_id: str):
    close_old_connections()
    job = _get_case_generation_job(job_id)
    if not job:
        return

    try:
        _update_case_generation_job_progress(
            job_id,
            progress_percent=5,
            progress_stage="prepare",
            progress_message="任务已开始，正在准备生成",
            started_at=timezone.now(),
            completed_at=None,
            error_message="",
        )

        user = User.objects.get(pk=job["user_id"])
        project = Project.objects.get(pk=job["project_id"])
        requirement_document = RequirementDocument.objects.get(
            pk=job["requirement_document_id"],
            project=project,
        )
        requirement_module = RequirementModule.objects.get(
            pk=job["requirement_module_id"],
            document=requirement_document,
        )
        test_case_module = TestCaseModule.objects.get(
            pk=job["test_case_module_id"],
            project=project,
        )

        result = _generate_and_review_testcases_from_requirement(
            user=user,
            project=project,
            requirement_document=requirement_document,
            requirement_module=requirement_module,
            test_case_module=test_case_module,
            prompt_content=job.get("prompt_content") or "",
            allowed_test_types=job.get("allowed_test_types") or ["functional"],
            title_only=bool(job.get("title_only")),
            append_to_existing=bool(job.get("append_to_existing")),
            progress_callback=lambda percent, stage, message: _update_case_generation_job_progress(
                job_id,
                progress_percent=percent,
                progress_stage=stage,
                progress_message=message,
            ),
        )

        _mark_case_generation_job_success(job_id, result)
    except Exception as exc:
        logger.exception("AI 生成测试用例后台任务失败")
        _mark_case_generation_job_failed(job_id, str(exc))
    finally:
        close_old_connections()


def _start_requirement_case_generation_job(job_id: str):
    worker = threading.Thread(
        target=_run_requirement_case_generation_job,
        args=(job_id,),
        daemon=True,
    )
    worker.start()


class TestCaseViewSet(viewsets.ModelViewSet):
    """
    用例视图集，处理测试用例的 CRUD 操作，
    并支持嵌套创建和更新用例步骤。
    API 端点示例：`/api/projects/{project_pk}/testcases/`
    """

    serializer_class = TestCaseSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
    ]  # 添加 DjangoFilterBackend
    filterset_class = TestCaseFilter  # 使用自定义过滤器
    search_fields = ["name", "precondition"]

    def get_serializer_class(self):
        if self.action == "list":
            return TestCaseListSerializer
        return TestCaseSerializer

    def get_permissions(self):
        """
        返回当前视图所需的权限实例列表，
        用于覆盖 `settings.DEFAULT_PERMISSION_CLASSES`。
        """
        # 确保所有权限类都被实例化
        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),  # 支持 @permission_required 装饰器
            IsProjectMemberForTestCase(),
        ]

    def get_queryset(self):
        """
        根据 URL 中的 `project_pk` 过滤用例，
        确保只返回指定项目下的数据。
        """
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            # IsProjectMemberForTestCase 已检查用户是否属于当前项目
            queryset = (
                TestCase.objects.filter(project=project)
                .order_by("-created_at", "-id")
                .select_related("creator", "module", "assignment__assignee")
            )
            if self.action != "list":
                queryset = queryset.prefetch_related("steps", "assignment__suite")
            return queryset
        # 理论上不会发生，因为这里是嵌套路由
        return TestCase.objects.none()

    def perform_create(self, serializer):
        """
        创建用例时，自动关联所属项目和创建人。
        """
        project_pk = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_pk)
        serializer.save(creator=self.request.user, project=project)

    def perform_destroy(self, instance):
        module_id = instance.module_id
        project_id = instance.project_id
        user_id = self.request.user.id
        instance.delete()
        if module_id:
            _clear_case_generation_jobs(
                user_id=user_id,
                project_id=project_id,
                test_case_module_id=module_id,
            )

    def _ensure_project_admin(self, project):
        if project.creator_id == self.request.user.id:
            return
        if ProjectMember.objects.filter(
            project=project,
            user=self.request.user,
            role__in=["owner", "admin"],
        ).exists():
            return
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("只有项目管理员可以分配测试用例")

    @action(detail=False, methods=["post"], url_path="generate-from-requirement")
    def generate_from_requirement(self, request, project_pk=None):
        """根据需求模块启动异步测试用例生成任务。"""
        project = get_object_or_404(Project, pk=project_pk)

        requirement_document_id = request.data.get("requirement_document_id")
        requirement_module_id = request.data.get("requirement_module_id")
        test_case_module_id = request.data.get("test_case_module_id")
        prompt_id = request.data.get("prompt_id")
        generate_mode = str(request.data.get("generate_mode") or "full").strip()
        selected_test_types = request.data.get("test_types") or ["functional"]
        extra_prompt = str(request.data.get("extra_prompt") or "").strip()
        append_to_existing = _coerce_request_bool(request.data.get("append_to_existing"))
        auto_infer_requirement = _coerce_request_bool(request.data.get("auto_infer_requirement"))

        if generate_mode not in {"full", "title_only"}:
            return Response(
                {"error": "当前生成接口仅支持完整生成和标题生成模式"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not test_case_module_id:
            return Response(
                {"error": "保存模块不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(selected_test_types, list) or not selected_test_types:
            selected_test_types = ["functional"]

        allowed_test_types = [
            item
            for item in selected_test_types
            if item in {"smoke", "functional", "boundary", "exception", "permission", "security", "compatibility"}
        ]
        if not allowed_test_types:
            allowed_test_types = ["functional"]

        test_case_module = get_object_or_404(
            TestCaseModule, pk=test_case_module_id, project=project
        )

        if (not requirement_document_id or not requirement_module_id) and auto_infer_requirement:
            inferred_requirement = _infer_requirement_from_module_cases(project, test_case_module)
            if inferred_requirement:
                requirement_document_id, requirement_module_id = inferred_requirement

        if not requirement_document_id or not requirement_module_id:
            return Response(
                {"error": "未找到当前模块对应的需求来源，请先通过生成用例绑定需求后再进行追加生成"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requirement_document = get_object_or_404(
            RequirementDocument, pk=requirement_document_id, project=project
        )
        requirement_module = get_object_or_404(
            RequirementModule,
            pk=requirement_module_id,
            document=requirement_document,
        )

        prompt_content = ""
        if prompt_id:
            prompt = UserPrompt.objects.filter(
                id=prompt_id, user=request.user, is_active=True
            ).first()
            if prompt is None:
                return Response(
                    {"error": "所选提示词不存在或已停用"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            prompt_content = (prompt.content or "").strip()
        if extra_prompt:
            prompt_content = f"{prompt_content}\n\n{extra_prompt}".strip() if prompt_content else extra_prompt

        active_config = get_user_active_llm_config(request.user)
        if active_config is None:
            return Response(
                {"error": "当前没有可用的模型配置，请先在系统中启用一个 LLM 配置"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title_only = generate_mode == "title_only"
        job_id = uuid4().hex
        _create_case_generation_job(
            job_id,
            user_id=request.user.id,
            project_id=project.id,
            requirement_document_id=str(requirement_document.id),
            requirement_module_id=str(requirement_module.id),
            test_case_module_id=test_case_module.id,
            prompt_content=prompt_content,
            allowed_test_types=allowed_test_types,
            title_only=title_only,
            append_to_existing=append_to_existing,
        )
        _start_requirement_case_generation_job(job_id)

        return Response(
            {
                "success": True,
                "message": "测试用例生成任务已提交，后台正在生成",
                "job_id": job_id,
                "status": "pending",
                "progress_percent": 0,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path=r"generation-jobs/(?P<job_id>[^/.]+)",
    )
    def generation_job_status(self, request, project_pk=None, job_id=None):
        project = get_object_or_404(Project, pk=project_pk)
        job = _get_case_generation_job(job_id or "")
        if not job or job.get("project_id") != project.id or job.get("user_id") != request.user.id:
            return Response(
                {"error": "生成任务不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "success": True,
                "data": _build_case_generation_job_response(job),
            },
            status=status.HTTP_200_OK,
        )

    def _clear_generation_jobs_for_modules(self, *, user_id: int, project_id: int, module_ids):
        cleared_job_ids = []
        for module_id in {int(module_id) for module_id in module_ids if module_id}:
            cleared_job_ids.extend(
                _clear_case_generation_jobs(
                    user_id=user_id,
                    project_id=project_id,
                    test_case_module_id=module_id,
                )
            )
        return cleared_job_ids

    @action(detail=False, methods=["post"], url_path="clear-module")
    def clear_module(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        module_id = request.data.get("module_id")

        if not module_id:
            return Response(
                {"error": "module_id 不能为空"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            module_id = int(module_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "module_id 参数格式错误"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_case_module = get_object_or_404(
            TestCaseModule,
            pk=module_id,
            project=project,
        )

        queryset = self.get_queryset().filter(module=test_case_module)
        deleted_testcases_info = [
            {
                "id": testcase.id,
                "name": testcase.name,
                "module": testcase.module.name if testcase.module else None,
            }
            for testcase in queryset
        ]

        try:
            with transaction.atomic():
                _, deleted_details = queryset.delete()
                cleared_job_ids = self._clear_generation_jobs_for_modules(
                    user_id=request.user.id,
                    project_id=project.id,
                    module_ids=[test_case_module.id],
                )

            return Response(
                {
                    "message": f"已清空模块 {test_case_module.name} 下的测试用例",
                    "deleted_count": len(deleted_testcases_info),
                    "deleted_testcases": deleted_testcases_info,
                    "deletion_details": deleted_details,
                    "cleared_job_count": len(cleared_job_ids),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"error": f"清空模块测试用例失败: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="batch-move")
    def batch_move(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        ids_data = request.data.get("ids", [])
        target_module_id = request.data.get("target_module_id")

        if not ids_data:
            return Response({"error": "请提供要移动的测试用例 ID 列表"}, status=status.HTTP_400_BAD_REQUEST)
        if not target_module_id:
            return Response({"error": "请选择目标模块"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            testcase_ids = [int(item) for item in ids_data]
            target_module_id = int(target_module_id)
        except (TypeError, ValueError):
            return Response({"error": "移动参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        target_module = get_object_or_404(TestCaseModule, pk=target_module_id, project=project)
        queryset = self.get_queryset().filter(id__in=testcase_ids)
        found_ids = list(queryset.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不存在或不属于当前项目: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_module_ids = set(queryset.values_list("module_id", flat=True))
        if len(source_module_ids) != 1:
            return Response({"error": "一次只能移动同一模块下的测试用例"}, status=status.HTTP_400_BAD_REQUEST)
        source_module_id = next(iter(source_module_ids))
        if source_module_id == target_module.id:
            return Response({"error": "目标模块不能与当前模块相同"}, status=status.HTTP_400_BAD_REQUEST)

        testcase_names = [testcase.name for testcase in queryset]
        existing_duplicate_names = set(
            TestCase.objects.filter(project=project, module=target_module, name__in=testcase_names)
            .values_list("name", flat=True)
        )
        if existing_duplicate_names:
            duplicate_names_text = "、".join(sorted(existing_duplicate_names))
            return Response(
                {"error": f"目标模块下已存在同名测试用例：{duplicate_names_text}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved_testcases = [
            {
                "id": testcase.id,
                "name": testcase.name,
                "from_module": testcase.module.name if testcase.module else None,
                "to_module": target_module.name,
            }
            for testcase in queryset
        ]

        with transaction.atomic():
            updated_count = queryset.update(module=target_module)
            cleared_job_ids = self._clear_generation_jobs_for_modules(
                user_id=request.user.id,
                project_id=project.id,
                module_ids=[source_module_id, target_module.id],
            )

        return Response(
            {
                "message": f"已成功移动 {updated_count} 个测试用例",
                "moved_count": updated_count,
                "moved_testcases": moved_testcases,
                "target_module_id": target_module.id,
                "target_module_name": target_module.name,
                "cleared_job_count": len(cleared_job_ids),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="batch-copy")
    def batch_copy(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        ids_data = request.data.get("ids", [])
        target_module_id = request.data.get("target_module_id")

        if not ids_data:
            return Response({"error": "请提供要复制的测试用例 ID 列表"}, status=status.HTTP_400_BAD_REQUEST)
        if not target_module_id:
            return Response({"error": "请选择目标模块"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            testcase_ids = [int(item) for item in ids_data]
            target_module_id = int(target_module_id)
        except (TypeError, ValueError):
            return Response({"error": "复制参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        target_module = get_object_or_404(TestCaseModule, pk=target_module_id, project=project)
        queryset = self.get_queryset().filter(id__in=testcase_ids).prefetch_related("steps")
        found_ids = list(queryset.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不存在或不属于当前项目: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_module_ids = set(queryset.values_list("module_id", flat=True))
        if len(source_module_ids) != 1:
            return Response({"error": "一次只能复制同一模块下的测试用例"}, status=status.HTTP_400_BAD_REQUEST)
        source_module_id = next(iter(source_module_ids))
        if source_module_id == target_module.id:
            return Response({"error": "目标模块不能与当前模块相同"}, status=status.HTTP_400_BAD_REQUEST)

        testcase_names = [testcase.name for testcase in queryset]
        existing_duplicate_names = set(
            TestCase.objects.filter(project=project, module=target_module, name__in=testcase_names)
            .values_list("name", flat=True)
        )
        if existing_duplicate_names:
            duplicate_names_text = "、".join(sorted(existing_duplicate_names))
            return Response(
                {"error": f"目标模块下已存在同名测试用例：{duplicate_names_text}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected_duplicate_names = {
            name for name in testcase_names if testcase_names.count(name) > 1
        }
        if selected_duplicate_names:
            duplicate_names_text = "、".join(sorted(selected_duplicate_names))
            return Response(
                {"error": f"所选测试用例中包含重复名称，无法复制到同一模块：{duplicate_names_text}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        copied_cases = []
        with transaction.atomic():
            for testcase in queryset:
                copied_case = TestCase.objects.create(
                    project=project,
                    module=target_module,
                    name=testcase.name,
                    precondition=testcase.precondition,
                    level=testcase.level,
                    creator=request.user,
                    notes=testcase.notes,
                    screenshot=testcase.screenshot,
                    review_status=testcase.review_status,
                    test_type=testcase.test_type,
                )
                for step in testcase.steps.all().order_by("step_number"):
                    TestCaseStep.objects.create(
                        test_case=copied_case,
                        step_number=step.step_number,
                        description=step.description,
                        expected_result=step.expected_result,
                        creator=request.user,
                    )
                copied_cases.append(copied_case)

            cleared_job_ids = self._clear_generation_jobs_for_modules(
                user_id=request.user.id,
                project_id=project.id,
                module_ids=[target_module.id],
            )

        serializer = TestCaseListSerializer(copied_cases, many=True)
        return Response(
            {
                "message": f"已成功复制 {len(copied_cases)} 个测试用例",
                "copied_count": len(copied_cases),
                "target_module_id": target_module.id,
                "target_module_name": target_module.name,
                "data": serializer.data,
                "cleared_job_count": len(cleared_job_ids),
            },
            status=status.HTTP_201_CREATED,
        )

    # create/update 默认走序列化器中的嵌套写入逻辑。
    # 如果后续需要更细粒度控制，可以继续覆写相关方法。

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()  # get_object 会触发对象级权限检查

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        self.perform_update(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            # 如果 queryset 使用过 prefetch_related，需要清空缓存
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    # perform_update 默认会调用 serializer.save()，
    # 序列化器内部的 update 方法会继续处理嵌套步骤。
    # perform_destroy 默认会调用 instance.delete()。

    @action(detail=False, methods=["get", "post"], url_path="export-excel")
    def export_excel(self, request, project_pk=None):
        """
        导出 Excel 格式的测试用例。
        支持两种传参方式：
        1. GET: `/api/projects/1/testcases/export-excel/?ids=1,2,3`
        2. POST: `{"ids": [1, 2, 3], "template_id": 1}`
        如果不提供 ids，则导出当前项目下的全部用例。
        如果提供 template_id，则按模板配置导出。
        """
        from testcase_templates.models import ImportExportTemplate
        from testcase_templates.export_service import TestCaseExportService

        testcase_ids = None
        template_id = None
        module_ids = None

        if request.method == "POST":
            # POST 请求：从请求体中获取 ids、template_id 和 module_ids
            ids_data = request.data.get("ids", [])
            template_id = request.data.get("template_id")
            module_ids_data = request.data.get("module_ids", [])
            if ids_data:
                try:
                    testcase_ids = [int(id) for id in ids_data]
                except (ValueError, TypeError):
                    from rest_framework.response import Response

                    return Response(
                        {"error": "ids参数格式错误，应为数字列表"}, status=400
                    )
            if module_ids_data:
                try:
                    module_ids = [int(id) for id in module_ids_data]
                except (ValueError, TypeError):
                    return Response(
                        {"error": "module_ids参数格式错误，应为数字列表"}, status=400
                    )
        else:
            # GET 请求：从查询参数中获取 ids、template_id 和 module_ids
            ids_param = request.query_params.get("ids", "")
            template_id = request.query_params.get("template_id")
            module_ids_param = request.query_params.get("module_ids", "")
            if ids_param:
                try:
                    testcase_ids = [
                        int(id.strip()) for id in ids_param.split(",") if id.strip()
                    ]
                except ValueError:
                    from rest_framework.response import Response

                    return Response(
                        {"error": "ids参数格式错误，应为逗号分隔的数字列表"}, status=400
                    )
            if module_ids_param:
                try:
                    module_ids = [
                        int(id.strip())
                        for id in module_ids_param.split(",")
                        if id.strip()
                    ]
                except ValueError:
                    return Response(
                        {"error": "module_ids参数格式错误，应为逗号分隔的数字列表"},
                        status=400,
                    )

        # 根据过滤条件构建 queryset
        queryset = self.get_queryset()
        if testcase_ids:
            queryset = queryset.filter(id__in=testcase_ids)
        elif module_ids:
            # 收集所选模块及其所有子模块的 ID
            all_module_ids = set()
            for mid in module_ids:
                try:
                    module = TestCaseModule.objects.get(id=mid)
                    all_module_ids.update(module.get_all_descendant_ids())
                except TestCaseModule.DoesNotExist:
                    pass
            if all_module_ids:
                queryset = queryset.filter(module_id__in=all_module_ids)
            else:
                queryset = queryset.none()

        # 获取导出模板（如果指定）
        template = None
        if template_id:
            try:
                template = ImportExportTemplate.objects.get(
                    pk=template_id, is_active=True, template_type__in=["export", "both"]
                )
            except ImportExportTemplate.DoesNotExist:
                return Response(
                    {"error": "指定的导出模板不存在或不可用"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 获取项目名称
        project = get_object_or_404(Project, pk=project_pk)

        # 调用导出服务
        export_service = TestCaseExportService(template)
        try:
            excel_data, filename = export_service.export(queryset, project.name)
        except Exception as e:
            import logging

            logging.getLogger(__name__).exception("导出 Excel 失败")
            return Response(
                {"error": f"导出失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 构建 HTTP 响应
        response = HttpResponse(
            excel_data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    def _get_module_path(self, module):
        """
        获取模块的完整路径。
        """
        if not module:
            return ""

        path_parts = []
        current = module
        while current:
            path_parts.insert(0, current.name)
            current = current.parent

        return "/" + "/".join(path_parts)

    def _format_steps(self, steps):
        """
        格式化步骤描述和预期结果。
        """
        steps_desc = []
        expected_results = []

        for step in steps.order_by("step_number"):
            steps_desc.append(f"[{step.step_number}]{step.description}")
            expected_results.append(f"[{step.step_number}]{step.expected_result}")

        return "\n".join(steps_desc), "\n".join(expected_results)

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request, **kwargs):
        """
        批量删除用例。
        POST 请求体格式: `{"ids": [1, 2, 3, 4]}`
        """
        project_pk = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_pk)

        # 获取要删除的用例 ID 列表
        ids_data = request.data.get("ids", [])

        if not ids_data:
            return Response(
                {"error": "请提供要删除的用例 ID 列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 校验 ID 格式
        try:
            testcase_ids = [int(id) for id in ids_data]
        except (ValueError, TypeError):
            return Response(
                {"error": "ids参数格式错误，应为数字列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not testcase_ids:
            return Response(
                {"error": "用例 ID 列表不能为空"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 获取当前项目下的用例 queryset，确保数据隔离
        queryset = self.get_queryset()

        # 过滤出待删除用例，确保仅删除当前项目下的数据
        testcases_to_delete = queryset.filter(id__in=testcase_ids)

        # 检查请求中的所有 ID 是否都存在
        found_ids = list(testcases_to_delete.values_list("id", flat=True))
        not_found_ids = [id for id in testcase_ids if id not in found_ids]

        if not_found_ids:
            return Response(
                {
                    "error": f"以下用例 ID 不存在或不属于当前项目: {not_found_ids}",
                    "not_found_ids": not_found_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 记录删除前的信息，便于返回给前端
        deleted_testcases_info = []
        affected_module_ids = set()
        for testcase in testcases_to_delete:
            if testcase.module_id:
                affected_module_ids.add(testcase.module_id)
            deleted_testcases_info.append(
                {
                    "id": testcase.id,
                    "name": testcase.name,
                    "module": testcase.module.name if testcase.module else None,
                }
            )

        # 执行批量删除
        try:
            with transaction.atomic():
                # 删除用例时，关联步骤会因外键级联自动删除
                deleted_count, deleted_details = testcases_to_delete.delete()
                cleared_job_ids = self._clear_generation_jobs_for_modules(
                    user_id=request.user.id,
                    project_id=project.id,
                    module_ids=affected_module_ids,
                )

                return Response(
                    {
                        "message": f"成功删除 {len(deleted_testcases_info)} 个用例",
                        "deleted_count": len(deleted_testcases_info),
                        "deleted_testcases": deleted_testcases_info,
                        "deletion_details": deleted_details,
                        "cleared_job_count": len(cleared_job_ids),
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            return Response(
                {"error": f"删除过程中发生错误: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="batch-update-execution-status")
    def batch_update_execution_status(self, request, project_pk=None):
        ids_data = request.data.get("ids", [])
        execution_status = request.data.get("execution_status")

        if not ids_data:
            return Response(
                {"error": "请提供要更新的测试用例 ID 列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not execution_status:
            return Response(
                {"error": "请选择执行状态"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            testcase_ids = [int(item) for item in ids_data]
        except (TypeError, ValueError):
            return Response(
                {"error": "批量更新参数格式错误"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_statuses = {
            choice[0] for choice in TestCase.EXECUTION_STATUS_CHOICES
        }
        if execution_status not in allowed_statuses:
            return Response(
                {"error": "执行状态无效"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(id__in=testcase_ids)
        found_ids = list(queryset.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不存在或不属于当前项目: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_payload = {"execution_status": execution_status}
        if execution_status in {"passed", "failed"}:
            update_payload["executed_at"] = timezone.now()

        updated_count = queryset.update(**update_payload)
        return Response(
            {
                "success": True,
                "message": f"已成功更新 {updated_count} 个测试用例的执行状态",
                "updated_count": updated_count,
                "execution_status": execution_status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="batch-assign")
    def batch_assign(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        self._ensure_project_admin(project)

        ids_data = request.data.get("ids", [])
        suite_id = request.data.get("suite_id")
        assignee_id = request.data.get("assignee_id")

        if not ids_data:
            return Response({"error": "请提供要分配的测试用例 ID 列表"}, status=status.HTTP_400_BAD_REQUEST)
        if not suite_id:
            return Response({"error": "请选择测试套件"}, status=status.HTTP_400_BAD_REQUEST)
        if not assignee_id:
            return Response({"error": "请选择执行人"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            testcase_ids = [int(item) for item in ids_data]
            suite_id = int(suite_id)
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            return Response({"error": "分配参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        suite = get_object_or_404(TestSuite, pk=suite_id, project=project)
        member = ProjectMember.objects.filter(project=project, user_id=assignee_id).select_related("user").first()
        if member is None:
            return Response({"error": "执行人必须是当前项目成员"}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(id__in=testcase_ids)
        found_ids = list(queryset.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不存在或不属于当前项目: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unapproved_cases = list(
            queryset.exclude(review_status="approved").values_list("name", flat=True)
        )
        if unapproved_cases:
            return Response(
                {
                    "error": "只有审核状态为“通过”的测试用例才能分配",
                    "invalid_testcases": unapproved_cases,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for testcase in queryset:
                TestCaseAssignment.objects.update_or_create(
                    testcase=testcase,
                    defaults={
                        "suite": suite,
                        "assignee": member.user,
                        "assigned_by": request.user,
                    },
                )
            suite.testcases.add(*list(queryset))

        return Response(
            {
                "success": True,
                "message": f"已成功分配 {len(found_ids)} 个测试用例",
                "assigned_count": len(found_ids),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="upload-screenshots")
    @permission_required("testcases.add_testcasescreenshot")
    def upload_screenshots(self, request, project_pk=None, pk=None):
        """
        上传测试用例截图，支持多张图片。
        POST /api/projects/{project_pk}/testcases/{pk}/upload-screenshots/
        请求体: multipart/form-data
        支持字段:
        - screenshots: 图片文件，可多个
        - title: 图片标题，可选
        - description: 图片描述，可选
        - step_number: 对应步骤编号，可选
        - mcp_session_id: MCP 会话 ID，可选
        - page_url: 页面 URL，可选
        """
        testcase = self.get_object()

        # 获取上传的截图文件
        uploaded_files = request.FILES.getlist("screenshots")
        if not uploaded_files:
            # 兼容单文件上传
            if "screenshot" in request.FILES:
                uploaded_files = [request.FILES["screenshot"]]
            else:
                return Response(
                    {"error": "请提供截图文件，字段名为 screenshots 或 screenshot"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 校验文件数量限制
        if len(uploaded_files) > 10:
            return Response(
                {"error": "一次最多只能上传10张图片"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 校验文件类型和大小
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif"]
        max_size = 5 * 1024 * 1024  # 5MB

        for file in uploaded_files:
            if file.content_type not in allowed_types:
                return Response(
                    {
                        "error": f"文件 {file.name} 格式不支持，仅支持 JPEG、PNG、GIF"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if file.size > max_size:
                return Response(
                    {"error": f"文件 {file.name} 大小超过 5MB 限制"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            created_screenshots = []

            # 获取附加信息
            title = request.data.get("title", "")
            description = request.data.get("description", "")
            step_number = request.data.get("step_number")
            mcp_session_id = request.data.get("mcp_session_id", "")
            page_url = request.data.get("page_url", "")

            # 处理 step_number
            if step_number:
                try:
                    step_number = int(step_number)
                except (ValueError, TypeError):
                    step_number = None

            # 为每个文件创建截图记录
            for i, file in enumerate(uploaded_files):
                screenshot_data = {
                    "test_case": testcase.id,
                    "screenshot": file,
                    "title": f"{title} ({i + 1})"
                    if title and len(uploaded_files) > 1
                    else title,
                    "description": description,
                    "step_number": step_number,
                    "mcp_session_id": mcp_session_id,
                    "page_url": page_url,
                }

                serializer = TestCaseScreenshotSerializer(
                    data=screenshot_data, context={"request": request}
                )

                if serializer.is_valid():
                    screenshot = serializer.save()
                    created_screenshots.append(serializer.data)
                else:
                    return Response(
                        {"error": f"文件 {file.name} 保存失败: {serializer.errors}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            return Response(
                {
                    "message": f"成功上传 {len(created_screenshots)} 张截图",
                    "screenshots": created_screenshots,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response(
                {"error": f"上传失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="screenshots")
    def list_screenshots(self, request, project_pk=None, pk=None):
        """
        获取测试用例的所有截图。
        GET /api/projects/{project_pk}/testcases/{pk}/screenshots/
        """
        testcase = self.get_object()
        screenshots = testcase.screenshots.all()
        serializer = TestCaseScreenshotSerializer(
            screenshots, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["delete"],
        url_path="screenshots/(?P<screenshot_id>[^/.]+)",
    )
    @permission_required("testcases.delete_testcasescreenshot")
    def delete_screenshot(self, request, project_pk=None, pk=None, screenshot_id=None):
        """
        删除指定截图。
        DELETE /api/projects/{project_pk}/testcases/{pk}/screenshots/{screenshot_id}/
        """
        testcase = self.get_object()

        try:
            screenshot = testcase.screenshots.get(id=screenshot_id)
            screenshot.delete()
            return Response({"message": "截图删除成功"}, status=status.HTTP_200_OK)
        except TestCaseScreenshot.DoesNotExist:
            return Response({"error": "截图不存在"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["post"], url_path="screenshots/batch-delete")
    @permission_required("testcases.delete_testcasescreenshot")
    def batch_delete_screenshots(self, request, project_pk=None, pk=None):
        """
        批量删除测试用例截图。
        POST /api/projects/{project_pk}/testcases/{pk}/screenshots/batch-delete/
        请求体: `{"ids": [1, 2, 3]}`
        """
        testcase = self.get_object()

        # 获取要删除的截图 ID 列表
        ids_data = request.data.get("ids", [])

        if not ids_data:
            return Response(
                {"error": "请提供要删除的截图 ID 列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 校验 ID 格式
        try:
            screenshot_ids = [int(id) for id in ids_data]
        except (ValueError, TypeError):
            return Response(
                {"error": "ids参数格式错误，应为数字列表"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not screenshot_ids:
            return Response(
                {"error": "截图 ID 列表不能为空"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 过滤出待删除截图，确保只删除当前用例下的数据
        screenshots_to_delete = testcase.screenshots.filter(id__in=screenshot_ids)

        # 检查请求中的所有 ID 是否都存在
        found_ids = list(screenshots_to_delete.values_list("id", flat=True))
        not_found_ids = [id for id in screenshot_ids if id not in found_ids]

        if not_found_ids:
            return Response(
                {
                    "error": f"以下截图 ID 不存在或不属于当前测试用例: {not_found_ids}",
                    "not_found_ids": not_found_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 记录删除前的信息
        deleted_screenshots_info = []
        for screenshot in screenshots_to_delete:
            deleted_screenshots_info.append(
                {
                    "id": screenshot.id,
                    "title": screenshot.title or "无标题",
                    "step_number": screenshot.step_number,
                }
            )

        # 执行批量删除
        try:
            with transaction.atomic():
                deleted_count, _ = screenshots_to_delete.delete()



                return Response(
                    {
                        "message": f"成功删除 {len(deleted_screenshots_info)} 张截图",
                        "deleted_count": len(deleted_screenshots_info),
                        "deleted_screenshots": deleted_screenshots_info,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            return Response(
                {"error": f"删除过程中发生错误: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TestCaseModuleViewSet(viewsets.ModelViewSet):
    """
    用例模块视图集，处理模块的 CRUD 操作，
    支持多级子模块。
    API 端点示例：`/api/projects/{project_pk}/testcase-modules/`
    """

    serializer_class = TestCaseModuleSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_permissions(self):
        """
        返回当前视图所需的权限实例列表。
        """
        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),
            IsProjectMemberForTestCaseModule(),
        ]

    def get_queryset(self):
        """
        根据 URL 中的 `project_pk` 过滤模块，
        确保只返回指定项目下的数据。
        """
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            # IsProjectMemberForTestCaseModule 已检查项目成员权限
            return (
                TestCaseModule.objects.filter(project=project)
                .select_related("creator", "parent")
                .annotate(testcase_count=Count("testcases", distinct=True))
            )
        return TestCaseModule.objects.none()

    def perform_create(self, serializer):
        """
        创建模块时，自动关联所属项目和创建人。
        """
        project_pk = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_pk)
        # 将项目实例传入序列化器上下文，用于校验
        serializer.context["project"] = project
        # 保存模块，并设置创建人和项目
        serializer.save(creator=self.request.user, project=project)

    def perform_destroy(self, instance):
        """
        删除模块前，检查是否仍有关联测试用例。
        """
        if instance.testcases.exists():
            from rest_framework.exceptions import ValidationError

            testcase_count = instance.testcases.count()
            raise ValidationError(
                f"无法删除模块 {instance.name}，因为该模块下还有 {testcase_count} 个测试用例，请先处理这些用例。"
            )
        instance.delete()

    def get_serializer_context(self):
        """
        为序列化器提供额外上下文。
        """
        context = super().get_serializer_context()
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            context["project"] = project
        return context


class TestSuiteViewSet(viewsets.ModelViewSet):
    """
    测试套件视图集，处理测试套件的 CRUD 操作。
    API 端点示例：`/api/projects/{project_pk}/test-suites/`
    """

    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "description"]

    def get_permissions(self):
        """返回当前视图所需的权限实例列表。"""
        from .permissions import IsProjectMemberForTestSuite

        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),
            IsProjectMemberForTestSuite(),
        ]

    def get_queryset(self):
        """根据 URL 中的 `project_pk` 过滤测试套件。"""
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            queryset = TestSuite.objects.filter(project=project).select_related(
                "creator", "parent"
            )

            module_id = self.request.query_params.get("module_id")
            if module_id:
                try:
                    module = TestCaseModule.objects.get(project=project, id=int(module_id))
                except (ValueError, TypeError, TestCaseModule.DoesNotExist):
                    return TestSuite.objects.none()

                queryset = queryset.filter(
                    testcases__module_id__in=module.get_all_descendant_ids()
                ).distinct()

            return queryset.annotate(testcase_count=Count("testcases", distinct=True))
        return TestSuite.objects.none()

    def get_serializer_class(self):
        """根据 action 返回对应的序列化器。"""
        from .serializers import TestSuiteSerializer

        return TestSuiteSerializer

    def get_serializer_context(self):
        """为序列化器提供额外上下文。"""
        context = super().get_serializer_context()
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            context["project_id"] = int(project_pk)
        return context

    def perform_create(self, serializer):
        """创建测试套件时，自动关联项目和创建人。"""
        project_pk = self.kwargs.get("project_pk")
        project = get_object_or_404(Project, pk=project_pk)
        serializer.save(creator=self.request.user, project=project)

    def perform_destroy(self, instance):
        if instance.children.exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(f"无法删除套件 {instance.name}，请先删除其子套件。")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="move-testcases")
    def move_testcases(self, request, project_pk=None, pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        source_suite = get_object_or_404(TestSuite, pk=pk, project=project)
        ids_data = request.data.get("ids", [])
        target_suite_id = request.data.get("target_suite_id")

        if not ids_data:
            return Response({"error": "请提供要移动的测试用例 ID 列表"}, status=status.HTTP_400_BAD_REQUEST)
        if not target_suite_id:
            return Response({"error": "请选择目标套件"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            testcase_ids = [int(item) for item in ids_data]
            target_suite_id = int(target_suite_id)
        except (TypeError, ValueError):
            return Response({"error": "移动参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        target_suite = get_object_or_404(TestSuite, pk=target_suite_id, project=project)
        if target_suite.id == source_suite.id:
            return Response({"error": "目标套件不能与当前套件相同"}, status=status.HTTP_400_BAD_REQUEST)

        source_testcases = source_suite.testcases.filter(id__in=testcase_ids)
        found_ids = list(source_testcases.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不在当前套件中: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moved_testcases = list(source_testcases)
        with transaction.atomic():
            source_suite.testcases.remove(*moved_testcases)
            target_suite.testcases.add(*moved_testcases)
            TestCaseAssignment.objects.filter(
                testcase_id__in=found_ids,
                suite=source_suite,
            ).update(suite=target_suite)

        return Response(
            {
                "success": True,
                "message": f"已成功移动 {len(found_ids)} 个测试用例",
                "moved_count": len(found_ids),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="copy-testcases")
    def copy_testcases(self, request, project_pk=None, pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        source_suite = get_object_or_404(TestSuite, pk=pk, project=project)
        ids_data = request.data.get("ids", [])
        target_suite_id = request.data.get("target_suite_id")

        if not ids_data:
            return Response({"error": "请提供要复制的测试用例 ID 列表"}, status=status.HTTP_400_BAD_REQUEST)
        if not target_suite_id:
            return Response({"error": "请选择目标套件"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            testcase_ids = [int(item) for item in ids_data]
            target_suite_id = int(target_suite_id)
        except (TypeError, ValueError):
            return Response({"error": "复制参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        target_suite = get_object_or_404(TestSuite, pk=target_suite_id, project=project)
        if target_suite.id == source_suite.id:
            return Response({"error": "目标套件不能与当前套件相同"}, status=status.HTTP_400_BAD_REQUEST)

        source_testcases = source_suite.testcases.filter(id__in=testcase_ids)
        found_ids = list(source_testcases.values_list("id", flat=True))
        missing_ids = [item for item in testcase_ids if item not in found_ids]
        if missing_ids:
            return Response(
                {"error": f"以下测试用例不在当前套件中: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_target_ids = set(target_suite.testcases.filter(id__in=found_ids).values_list("id", flat=True))
        testcase_list = list(source_testcases)
        addable_testcases = [item for item in testcase_list if item.id not in existing_target_ids]

        with transaction.atomic():
            if addable_testcases:
                target_suite.testcases.add(*addable_testcases)

        return Response(
            {
                "success": True,
                "message": f"已成功复制 {len(addable_testcases)} 个测试用例",
                "copied_count": len(addable_testcases),
                "skipped_count": len(existing_target_ids),
            },
            status=status.HTTP_200_OK,
        )


class TestBugViewSet(viewsets.ModelViewSet):
    """测试套件下的 BUG 管理视图集。"""

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TestBugFilter
    search_fields = ["title", "steps", "actual_result", "expected_result", "keywords"]
    ordering_fields = ["id", "severity", "priority", "opened_at", "assigned_at", "resolved_at", "closed_at"]
    ordering = ["-id"]
    _attachment_sections = {"steps", "expected_result", "actual_result"}
    _workflow_actions = {
        "upload_attachments",
        "delete_attachment",
        "assign",
        "change_status",
        "confirm",
        "fix",
        "resolve",
        "activate",
        "close",
        "batch_assign",
        "batch_change_status",
        "batch_update_priority",
        "batch_update_severity",
        "batch_update_bug_type",
        "batch_update_resolution",
        "batch_delete",
    }

    def get_permissions(self):
        from .permissions import IsProjectMemberForTestSuite

        if self.action in self._workflow_actions:
            return [
                permissions.IsAuthenticated(),
                IsProjectMemberForTestSuite(),
            ]

        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),
            IsProjectMemberForTestSuite(),
        ]

    def get_queryset(self):
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            return TestBug.objects.filter(project=project).select_related(
                "suite",
                "testcase",
                "assigned_to",
                "opened_by",
                "resolved_by",
                "closed_by",
                "activated_by",
            ).prefetch_related(
                "attachments",
                "attachments__uploaded_by",
                "assigned_users",
                "related_testcases",
                "activities",
                "activities__operator",
            )
        return TestBug.objects.none()

    def get_serializer_class(self):
        if self.action == "list":
            return TestBugListSerializer
        return TestBugSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            context["project"] = get_object_or_404(Project, pk=project_pk)
        return context

    def _get_bug_choice_label(self, choices, value, default="-"):
        if value in (None, ""):
            return default
        return dict(choices).get(value, str(value))

    def _get_bug_status_label(self, value):
        return self._get_bug_choice_label(TestBug.WORKFLOW_STATUS_CHOICES, value)

    def _get_bug_type_label(self, value):
        return self._get_bug_choice_label(TestBug.TYPE_CHOICES, value)

    def _get_bug_resolution_label(self, value):
        return self._get_bug_choice_label(TestBug.RESOLUTION_CHOICES, value)

    def _get_bug_attachment_section_label(self, value):
        return self._get_bug_choice_label(TestBugAttachment.SECTION_CHOICES, value)

    def _build_bug_snapshot(self, bug):
        related_testcases = list(bug.related_testcases.order_by("id").values("id", "name"))
        assigned_users = list(bug.assigned_users.order_by("id").values("id", "username"))
        return {
            "title": bug.title or "",
            "bug_type": bug.bug_type or "",
            "severity": bug.severity or "",
            "priority": bug.priority or "",
            "status": bug.get_effective_status(),
            "resolution": bug.resolution or "",
            "deadline": bug.deadline.isoformat() if bug.deadline else "",
            "keywords": bug.keywords or "",
            "suite_name": bug.suite.name if bug.suite_id and bug.suite else "",
            "testcase_ids": [item["id"] for item in related_testcases],
            "testcase_names": [item["name"] for item in related_testcases],
            "assigned_to_ids": [item["id"] for item in assigned_users],
            "assigned_to_names": [item["username"] for item in assigned_users],
        }

    def _format_bug_history_value(self, field_name, value):
        if field_name == "bug_type":
            return self._get_bug_type_label(value)
        if field_name == "status":
            return self._get_bug_status_label(value)
        if field_name == "resolution":
            return self._get_bug_resolution_label(value)
        if field_name == "severity":
            return f"S{value}" if value else "-"
        if field_name == "priority":
            return f"P{value}" if value else "-"
        if field_name in {"testcase_names", "assigned_to_names"}:
            return "、".join(value) if value else "-"
        return value if value not in (None, "", []) else "-"

    def _build_bug_change_lines(self, before_snapshot, after_snapshot):
        field_labels = {
            "title": "Bug标题",
            "bug_type": "BUG类型",
            "severity": "严重程度",
            "priority": "优先级",
            "status": "BUG状态",
            "resolution": "解决方案",
            "deadline": "截止日期",
            "keywords": "关键词",
            "testcase_names": "关联用例",
            "assigned_to_names": "指派给",
        }
        changes = []
        for field_name, field_label in field_labels.items():
            before_value = before_snapshot.get(field_name)
            after_value = after_snapshot.get(field_name)
            if before_value == after_value:
                continue
            changes.append(
                f"{field_label}：{self._format_bug_history_value(field_name, before_value)} -> "
                f"{self._format_bug_history_value(field_name, after_value)}"
            )
        return changes

    def _log_bug_activity(self, bug, action, *, operator, content, metadata=None):
        TestBugActivity.objects.create(
            bug=bug,
            action=action,
            content=content or "",
            metadata=metadata or {},
            operator=operator,
        )

    def perform_create(self, serializer):
        project = self.get_serializer_context()["project"]
        assigned_to = serializer.validated_data.get("assigned_to")
        assigned_to_ids = serializer.validated_data.get("assigned_to_ids")
        has_assignees = bool(assigned_to) or bool(assigned_to_ids)
        resolution = str(serializer.validated_data.get("resolution") or "").strip()
        initial_status = (
            TestBug.STATUS_FIXED
            if resolution
            else (TestBug.STATUS_ASSIGNED if has_assignees else TestBug.STATUS_UNASSIGNED)
        )
        bug = serializer.save(project=project, opened_by=self.request.user, status=initial_status)
        self._sync_bug_status_and_resolution(
            bug,
            user=self.request.user,
            status_explicit=True,
            resolution_explicit=bool(resolution),
            prefer_confirmed_when_reopen=False,
        )
        bug.refresh_from_db()
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_CREATE,
            operator=self.request.user,
            content=(
                f"新建了 BUG，当前状态为“{self._get_bug_status_label(bug.get_effective_status())}”，"
                f"BUG类型为“{self._get_bug_type_label(bug.bug_type)}”。"
            ),
            metadata=self._build_bug_snapshot(bug),
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        self._ensure_can_edit_bug(instance)
        before_snapshot = self._build_bug_snapshot(instance)
        status_explicit = "status" in serializer.validated_data
        resolution_explicit = "resolution" in serializer.validated_data
        previous_status = instance.get_effective_status()
        assigned_to_present = "assigned_to" in serializer.validated_data
        assigned_to_ids_present = "assigned_to_ids" in serializer.validated_data
        if not assigned_to_present and not assigned_to_ids_present:
            bug = serializer.save()
            self._sync_bug_status_and_resolution(
                bug,
                user=self.request.user,
                status_explicit=status_explicit,
                resolution_explicit=resolution_explicit,
                previous_status=previous_status,
            )
            self._record_bug_update_activity(bug, before_snapshot)
            return

        previous_assignee_ids = list(instance.assigned_users.values_list("id", flat=True))
        next_assignee_ids = serializer.validated_data.get("assigned_to_ids")
        if next_assignee_ids is None:
            assigned_user = serializer.validated_data.get("assigned_to")
            next_assignee_ids = [assigned_user.id] if assigned_user else []
        next_assignee_ids = list(dict.fromkeys(next_assignee_ids))

        if previous_assignee_ids == next_assignee_ids:
            bug = serializer.save()
            self._sync_bug_status_and_resolution(
                bug,
                user=self.request.user,
                status_explicit=status_explicit,
                resolution_explicit=resolution_explicit,
                previous_status=previous_status,
            )
            self._record_bug_update_activity(bug, before_snapshot)
            return

        bug = serializer.save(assigned_at=timezone.now() if next_assignee_ids else None)
        self._sync_bug_status_and_resolution(
            bug,
            user=self.request.user,
            status_explicit=status_explicit,
            resolution_explicit=resolution_explicit,
            previous_status=previous_status,
        )
        self._record_bug_update_activity(bug, before_snapshot)

    def perform_destroy(self, instance):
        self._ensure_can_edit_bug(instance)
        instance.delete()

    def _record_bug_update_activity(self, bug, before_snapshot):
        bug.refresh_from_db()
        after_snapshot = self._build_bug_snapshot(bug)
        change_lines = self._build_bug_change_lines(before_snapshot, after_snapshot)
        if not change_lines:
            return
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_UPDATE,
            operator=self.request.user,
            content="；".join(change_lines),
            metadata={
                "before": before_snapshot,
                "after": after_snapshot,
                "changes": change_lines,
            },
        )

    def _get_bug_assignee_ids(self, bug):
        if bug.assigned_to_id:
            primary_id = bug.assigned_to_id
        else:
            primary_id = None
        assigned_ids = list(bug.assigned_users.values_list("id", flat=True))
        if primary_id and primary_id not in assigned_ids:
            assigned_ids.insert(0, primary_id)
        return assigned_ids

    def _has_bug_assignees(self, bug):
        return bool(self._get_bug_assignee_ids(bug))

    def _get_default_unresolved_bug_status(self, bug, *, prefer_confirmed=False):
        if not self._has_bug_assignees(bug):
            return TestBug.STATUS_UNASSIGNED
        return TestBug.STATUS_CONFIRMED if prefer_confirmed else TestBug.STATUS_ASSIGNED

    def _sync_bug_status_and_resolution(
        self,
        bug,
        *,
        user,
        status_explicit=False,
        resolution_explicit=False,
        previous_status=None,
        prefer_confirmed_when_reopen=True,
    ):
        resolved_statuses = {
            TestBug.STATUS_FIXED,
            TestBug.STATUS_PENDING_RETEST,
            TestBug.STATUS_CLOSED,
        }
        active_statuses = {
            TestBug.STATUS_UNASSIGNED,
            TestBug.STATUS_ASSIGNED,
            TestBug.STATUS_CONFIRMED,
        }
        workflow_status = bug.get_workflow_status()
        effective_status = bug.get_effective_status()
        previous_status = previous_status or effective_status
        changed_fields = set()

        if status_explicit:
            if workflow_status in active_statuses:
                if bug.resolution:
                    bug.resolution = ""
                    changed_fields.add("resolution")
            elif workflow_status in resolved_statuses and not bug.resolution:
                bug.resolution = "fixed"
                changed_fields.add("resolution")
        elif resolution_explicit:
            if bug.resolution:
                if workflow_status in active_statuses:
                    bug.status = TestBug.STATUS_FIXED
                    workflow_status = TestBug.STATUS_FIXED
                    changed_fields.add("status")
            elif workflow_status in resolved_statuses:
                bug.status = self._get_default_unresolved_bug_status(
                    bug,
                    prefer_confirmed=prefer_confirmed_when_reopen,
                )
                workflow_status = bug.status
                changed_fields.add("status")
        else:
            if bug.resolution and workflow_status in active_statuses:
                bug.status = TestBug.STATUS_FIXED
                workflow_status = TestBug.STATUS_FIXED
                changed_fields.add("status")
            elif not bug.resolution and workflow_status in resolved_statuses:
                bug.status = self._get_default_unresolved_bug_status(
                    bug,
                    prefer_confirmed=prefer_confirmed_when_reopen,
                )
                workflow_status = bug.status
                changed_fields.add("status")

        effective_status = (
            TestBug.STATUS_EXPIRED
            if workflow_status != TestBug.STATUS_CLOSED and bug.deadline and bug.deadline < timezone.localdate()
            else workflow_status
        )

        if workflow_status in active_statuses:
            if bug.resolution:
                bug.resolution = ""
                changed_fields.add("resolution")
            if bug.resolved_by_id is not None:
                bug.resolved_by = None
                changed_fields.add("resolved_by")
            if bug.resolved_at is not None:
                bug.resolved_at = None
                changed_fields.add("resolved_at")
            if bug.closed_by_id is not None:
                bug.closed_by = None
                changed_fields.add("closed_by")
            if bug.closed_at is not None:
                bug.closed_at = None
                changed_fields.add("closed_at")

        if workflow_status in {TestBug.STATUS_FIXED, TestBug.STATUS_PENDING_RETEST}:
            if not bug.resolution:
                bug.resolution = "fixed"
                changed_fields.add("resolution")
            bug.resolved_by = user
            bug.resolved_at = timezone.now()
            changed_fields.update({"resolved_by", "resolved_at"})
            if bug.closed_by_id is not None:
                bug.closed_by = None
                changed_fields.add("closed_by")
            if bug.closed_at is not None:
                bug.closed_at = None
                changed_fields.add("closed_at")

        if workflow_status == TestBug.STATUS_CLOSED:
            if not bug.resolution:
                bug.resolution = "fixed"
                changed_fields.add("resolution")
            if not bug.resolved_at:
                bug.resolved_by = user
                bug.resolved_at = timezone.now()
                changed_fields.update({"resolved_by", "resolved_at"})
            bug.closed_by = user
            bug.closed_at = timezone.now()
            changed_fields.update({"closed_by", "closed_at"})

        if previous_status != effective_status:
            bug.status = workflow_status
            changed_fields.add("status")

        if changed_fields:
            changed_fields.add("updated_at")
            bug.save(update_fields=list(changed_fields))
        return bug

    def _resolve_assigned_members(self, bug, request_data):
        raw_assigned_to_ids = request_data.get("assigned_to_ids", None)
        if raw_assigned_to_ids is None:
            raw_single_assignee = request_data.get("assigned_to", None)
            raw_assigned_to_ids = [] if raw_single_assignee in (None, "", []) else [raw_single_assignee]

        if not isinstance(raw_assigned_to_ids, list):
            return None, Response({"error": "指派人员格式不正确"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_ids = []
        for raw_user_id in raw_assigned_to_ids:
            if raw_user_id in (None, ""):
                continue
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                return None, Response({"error": "指派人员格式不正确"}, status=status.HTTP_400_BAD_REQUEST)
            if user_id not in normalized_ids:
                normalized_ids.append(user_id)

        if not normalized_ids:
            return [], None

        members = list(
            ProjectMember.objects.filter(project=bug.project, user_id__in=normalized_ids)
            .select_related("user")
            .distinct()
        )
        member_map = {member.user_id: member for member in members}
        invalid_ids = [user_id for user_id in normalized_ids if user_id not in member_map]
        if invalid_ids:
            return None, Response({"error": "指派人必须是当前项目成员"}, status=status.HTTP_400_BAD_REQUEST)
        return [member_map[user_id] for user_id in normalized_ids], None

    def _parse_bug_ids(self, request):
        ids_data = request.data.get("ids", [])
        if not ids_data:
            return None, Response({"error": "请至少选择一条 BUG"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            bug_ids = [int(item) for item in ids_data]
        except (TypeError, ValueError):
            return None, Response({"error": "BUG ID 参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)
        if not bug_ids:
            return None, Response({"error": "BUG ID 列表不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        return list(dict.fromkeys(bug_ids)), None

    def _get_batch_bug_queryset(self, request):
        bug_ids, error_response = self._parse_bug_ids(request)
        if error_response is not None:
            return None, None, error_response
        queryset = self.get_queryset().filter(id__in=bug_ids)
        found_ids = list(queryset.values_list("id", flat=True))
        missing_ids = [item for item in bug_ids if item not in found_ids]
        if missing_ids:
            return None, None, Response(
                {"error": f"以下 BUG 不存在或不属于当前项目: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return bug_ids, queryset, None

    def _can_manage_bug_status(self, bug, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.id in self._get_bug_assignee_ids(bug) or bug.opened_by_id == user.id:
            return True
        return ProjectMember.objects.filter(
            project=bug.project,
            user=user,
            role__in=["owner", "admin"],
        ).exists()

    def _ensure_can_manage_bug_status(self, bug):
        if self._can_manage_bug_status(bug, self.request.user):
            return
        raise PermissionDenied("只有 BUG 指派人、创建人或管理员可以更改 BUG 状态")

    def _ensure_can_edit_bug(self, bug):
        if self._can_manage_bug_status(bug, self.request.user):
            return
        raise PermissionDenied("只有 BUG 指派人、创建人或管理员可以编辑 BUG")

    def _apply_bug_status_change(
        self,
        bug,
        target_status,
        *,
        user,
        solution="",
        resolution=None,
        members=None,
        activated=False,
    ):
        previous_status = bug.get_effective_status()

        if target_status == TestBug.STATUS_UNASSIGNED:
            bug.assigned_to = None
            bug.assigned_at = None
            bug.status = TestBug.STATUS_UNASSIGNED
            bug.save(update_fields=["assigned_to", "assigned_at", "status", "updated_at"])
            bug.assigned_users.clear()
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=False,
                previous_status=previous_status,
                prefer_confirmed_when_reopen=False,
            )
            return

        if target_status == TestBug.STATUS_ASSIGNED:
            if members is not None:
                if not members:
                    raise PermissionDenied("请选择指派人")
                bug.assigned_to = members[0].user
                bug.assigned_at = timezone.now()
                bug.status = TestBug.STATUS_ASSIGNED
                bug.save(update_fields=["assigned_to", "assigned_at", "status", "updated_at"])
                bug.assigned_users.set([member.user for member in members])
            elif not self._has_bug_assignees(bug):
                raise PermissionDenied("请先为 BUG 指派处理人")
            else:
                bug.status = TestBug.STATUS_ASSIGNED
                bug.assigned_at = timezone.now()
                bug.save(update_fields=["status", "assigned_at", "updated_at"])
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=False,
                previous_status=previous_status,
                prefer_confirmed_when_reopen=False,
            )
            return

        if target_status == TestBug.STATUS_CONFIRMED:
            if not self._has_bug_assignees(bug):
                raise PermissionDenied("请先为 BUG 指派处理人")
            bug.status = TestBug.STATUS_CONFIRMED
            bug.save(update_fields=["status", "updated_at"])
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=False,
                previous_status=previous_status,
            )
            return

        if target_status == TestBug.STATUS_FIXED:
            bug.status = TestBug.STATUS_FIXED
            bug.resolution = resolution or bug.resolution or "fixed"
            bug.solution = solution or bug.solution
            bug.save(update_fields=["status", "resolution", "solution", "updated_at"])
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=True,
                previous_status=previous_status,
            )
            return

        if target_status == TestBug.STATUS_PENDING_RETEST:
            bug.status = TestBug.STATUS_PENDING_RETEST
            if resolution is not None:
                bug.resolution = resolution or "fixed"
            if solution:
                bug.solution = solution
            update_fields = ["status", "updated_at"]
            if resolution is not None:
                update_fields.append("resolution")
            if solution:
                update_fields.append("solution")
            bug.save(update_fields=update_fields)
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=True,
                previous_status=previous_status,
            )
            return

        if target_status == TestBug.STATUS_CLOSED:
            bug.status = TestBug.STATUS_CLOSED
            bug.resolution = resolution or bug.resolution or "fixed"
            bug.solution = solution or bug.solution
            bug.save(update_fields=["status", "resolution", "solution", "updated_at"])
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=True,
                previous_status=previous_status,
            )
            return

        if target_status == "activate":
            bug.status = self._get_default_unresolved_bug_status(bug, prefer_confirmed=True)
            bug.activated_by = user
            bug.activated_at = timezone.now()
            bug.activated_count = (bug.activated_count or 0) + 1
            bug.save(
                update_fields=[
                    "status",
                    "activated_by",
                    "activated_at",
                    "activated_count",
                    "updated_at",
                ]
            )
            self._sync_bug_status_and_resolution(
                bug,
                user=user,
                status_explicit=True,
                resolution_explicit=False,
                previous_status=previous_status,
                prefer_confirmed_when_reopen=True,
            )
            return

        raise PermissionDenied("不支持修改为该 BUG 状态")

    def _classify_bug_attachment_type(self, uploaded_file):
        content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("video/"):
            return "video"
        return "file"

    @action(detail=True, methods=["post"], url_path="upload-attachments")
    @permission_required("testcases.change_testbug")
    def upload_attachments(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_edit_bug(bug)
        section = str(request.data.get("section") or "").strip()
        if section not in self._attachment_sections:
            return Response({"error": "请选择有效的附件区域"}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_files = request.FILES.getlist("files")
        if not uploaded_files and "file" in request.FILES:
            uploaded_files = [request.FILES["file"]]
        if not uploaded_files:
            return Response({"error": "请上传至少一个文件"}, status=status.HTTP_400_BAD_REQUEST)
        if len(uploaded_files) > 10:
            return Response({"error": "一次最多上传 10 个附件"}, status=status.HTTP_400_BAD_REQUEST)

        max_size = 100 * 1024 * 1024
        created_items = []
        for uploaded_file in uploaded_files:
            if uploaded_file.size > max_size:
                return Response(
                    {"error": f"文件 {uploaded_file.name} 超过 100MB 限制"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            created_items.append(
                TestBugAttachment.objects.create(
                    bug=bug,
                    section=section,
                    attachment=uploaded_file,
                    original_name=uploaded_file.name,
                    file_type=self._classify_bug_attachment_type(uploaded_file),
                    content_type=getattr(uploaded_file, "content_type", "") or "",
                    file_size=getattr(uploaded_file, "size", 0) or 0,
                    uploaded_by=request.user,
                )
            )

        serializer = TestBugAttachmentSerializer(created_items, many=True, context=self.get_serializer_context())
        if created_items:
            attachment_names = "、".join(item.original_name or "未命名文件" for item in created_items[:5])
            if len(created_items) > 5:
                attachment_names = f"{attachment_names} 等 {len(created_items)} 个附件"
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_UPLOAD_ATTACHMENT,
                operator=request.user,
                content=(
                    f"在“{self._get_bug_attachment_section_label(section)}”中上传了附件：{attachment_names}"
                ),
                metadata={
                    "section": section,
                    "attachment_ids": [item.id for item in created_items],
                    "attachment_names": [item.original_name for item in created_items],
                },
            )
        return Response({"data": serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    @permission_required("testcases.change_testbug")
    def delete_attachment(self, request, project_pk=None, pk=None, attachment_id=None):
        bug = self.get_object()
        self._ensure_can_edit_bug(bug)
        attachment = get_object_or_404(TestBugAttachment, pk=attachment_id, bug=bug)
        attachment_name = attachment.original_name or "未命名文件"
        section_label = self._get_bug_attachment_section_label(attachment.section)
        attachment.delete()
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_DELETE_ATTACHMENT,
            operator=request.user,
            content=f"从“{section_label}”中删除了附件：{attachment_name}",
            metadata={
                "section": attachment.section,
                "attachment_id": attachment_id,
                "attachment_name": attachment_name,
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="assign")
    @permission_required("testcases.change_testbug")
    def assign(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        members, error_response = self._resolve_assigned_members(bug, request.data)
        if error_response is not None:
            return error_response
        try:
            self._apply_bug_status_change(
                bug,
                TestBug.STATUS_ASSIGNED,
                user=request.user,
                members=members,
            )
        except PermissionDenied as exc:
            return Response({"error": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_ASSIGN,
            operator=request.user,
            content=f"将 BUG 指派给：{'、'.join(member.user.username for member in members)}",
            metadata={
                "assigned_to_ids": [member.user_id for member in members],
                "assigned_to_names": [member.user.username for member in members],
            },
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="change-status")
    @permission_required("testcases.change_testbug")
    def change_status(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        target_status = str(request.data.get("status") or "").strip()
        if target_status == TestBug.STATUS_EXPIRED:
            return Response({"error": "已过期状态由系统自动判断，不能手动修改"}, status=status.HTTP_400_BAD_REQUEST)

        allowed_statuses = {
            TestBug.STATUS_UNASSIGNED,
            TestBug.STATUS_ASSIGNED,
            TestBug.STATUS_CONFIRMED,
            TestBug.STATUS_FIXED,
            TestBug.STATUS_PENDING_RETEST,
            TestBug.STATUS_CLOSED,
        }
        if target_status not in allowed_statuses:
            return Response({"error": "请选择有效的 BUG 状态"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            previous_status = bug.get_effective_status()
            self._apply_bug_status_change(bug, target_status, user=request.user)
        except PermissionDenied as exc:
            return Response({"error": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_STATUS_CHANGE,
            operator=request.user,
            content=(
                f"BUG状态从“{self._get_bug_status_label(previous_status)}”变更为"
                f"“{self._get_bug_status_label(bug.get_effective_status())}”"
            ),
            metadata={
                "before_status": previous_status,
                "after_status": bug.get_effective_status(),
            },
        )

        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    @permission_required("testcases.change_testbug")
    def confirm(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        try:
            self._apply_bug_status_change(
                bug,
                TestBug.STATUS_CONFIRMED,
                user=request.user,
            )
        except PermissionDenied as exc:
            return Response({"error": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_CONFIRM,
            operator=request.user,
            content="确认接收该 BUG，状态更新为“已确认”",
            metadata={"status": TestBug.STATUS_CONFIRMED},
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="fix")
    @permission_required("testcases.change_testbug")
    def fix(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        resolution = request.data.get("resolution")
        solution = request.data.get("solution", "")

        allowed_resolutions = {choice[0] for choice in TestBug.RESOLUTION_CHOICES if choice[0]}
        if resolution not in allowed_resolutions:
            return Response({"error": "请选择有效的解决方案"}, status=status.HTTP_400_BAD_REQUEST)

        self._apply_bug_status_change(
            bug,
            TestBug.STATUS_FIXED,
            user=request.user,
            resolution=resolution,
            solution=solution,
        )
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_FIX,
            operator=request.user,
            content=(
                f"将 BUG 标记为“已修复”，解决方案为“{self._get_bug_resolution_label(bug.resolution)}”"
            ),
            metadata={
                "status": bug.get_effective_status(),
                "resolution": bug.resolution,
                "solution": bug.solution,
            },
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="resolve")
    @permission_required("testcases.change_testbug")
    def resolve(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        resolution = str(request.data.get("resolution") or bug.resolution or "").strip()
        if not resolution:
            resolution = "fixed"
        solution = request.data.get("solution", "")
        self._apply_bug_status_change(
            bug,
            TestBug.STATUS_PENDING_RETEST,
            user=request.user,
            resolution=resolution,
            solution=solution,
        )
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_RESOLVE,
            operator=request.user,
            content=(
                f"提交复测，当前解决方案为“{self._get_bug_resolution_label(bug.resolution)}”"
            ),
            metadata={
                "status": bug.get_effective_status(),
                "resolution": bug.resolution,
                "solution": bug.solution,
            },
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="activate")
    @permission_required("testcases.change_testbug")
    def activate(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        self._apply_bug_status_change(
            bug,
            "activate",
            user=request.user,
            activated=True,
        )
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_ACTIVATE,
            operator=request.user,
            content=(
                f"重新激活 BUG，状态更新为“{self._get_bug_status_label(bug.get_effective_status())}”"
            ),
            metadata={
                "status": bug.get_effective_status(),
                "activated_count": bug.activated_count,
            },
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="close")
    @permission_required("testcases.change_testbug")
    def close(self, request, project_pk=None, pk=None):
        bug = self.get_object()
        self._ensure_can_manage_bug_status(bug)
        resolution = str(request.data.get("resolution") or bug.resolution or "").strip()
        solution = request.data.get("solution", "")
        self._apply_bug_status_change(
            bug,
            TestBug.STATUS_CLOSED,
            user=request.user,
            resolution=resolution or "fixed",
            solution=solution,
        )
        self._log_bug_activity(
            bug,
            TestBugActivity.ACTION_CLOSE,
            operator=request.user,
            content=(
                f"关闭了 BUG，解决方案为“{self._get_bug_resolution_label(bug.resolution)}”"
            ),
            metadata={
                "status": bug.get_effective_status(),
                "resolution": bug.resolution,
                "solution": bug.solution,
            },
        )
        return Response(TestBugSerializer(bug, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["post"], url_path="batch-assign")
    @permission_required("testcases.change_testbug")
    def batch_assign(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        sample_bug = queryset.first()
        members, error_response = self._resolve_assigned_members(sample_bug, request.data)
        if error_response is not None:
            return error_response
        if not members:
            return Response({"error": "请选择指派人"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        assigned_to_ids = [member.user_id for member in members]
        assigned_to_names = [member.user.username for member in members]
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            self._apply_bug_status_change(
                bug,
                TestBug.STATUS_ASSIGNED,
                user=request.user,
                members=members,
            )
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_ASSIGN,
                operator=request.user,
                content=f"批量指派给：{'、'.join(assigned_to_names)}",
                metadata={
                    "assigned_to_ids": assigned_to_ids,
                    "assigned_to_names": assigned_to_names,
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量指派 {len(updated_ids)} 条 BUG",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-change-status")
    @permission_required("testcases.change_testbug")
    def batch_change_status(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        target_status = str(request.data.get("status") or "").strip()
        allowed_statuses = {
            TestBug.STATUS_UNASSIGNED,
            TestBug.STATUS_ASSIGNED,
            TestBug.STATUS_CONFIRMED,
            TestBug.STATUS_FIXED,
            TestBug.STATUS_PENDING_RETEST,
            TestBug.STATUS_CLOSED,
        }
        if target_status == TestBug.STATUS_EXPIRED:
            return Response({"error": "已过期状态由系统自动判断，不能手动修改"}, status=status.HTTP_400_BAD_REQUEST)
        if target_status not in allowed_statuses:
            return Response({"error": "请选择有效的 BUG 状态"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            previous_status = bug.get_effective_status()
            try:
                self._apply_bug_status_change(bug, target_status, user=request.user)
            except PermissionDenied as exc:
                return Response({"error": str(exc.detail)}, status=status.HTTP_400_BAD_REQUEST)
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_STATUS_CHANGE,
                operator=request.user,
                content=(
                    f"批量将 BUG 状态从“{self._get_bug_status_label(previous_status)}”变更为"
                    f"“{self._get_bug_status_label(bug.get_effective_status())}”"
                ),
                metadata={
                    "before_status": previous_status,
                    "after_status": bug.get_effective_status(),
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量更新 {len(updated_ids)} 条 BUG 的状态",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-update-priority")
    @permission_required("testcases.change_testbug")
    def batch_update_priority(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        priority = str(request.data.get("priority") or "").strip()
        allowed_priorities = {choice[0] for choice in TestBug.PRIORITY_CHOICES}
        if priority not in allowed_priorities:
            return Response({"error": "请选择有效的优先级"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            if bug.priority == priority:
                continue
            previous_priority = bug.priority
            bug.priority = priority
            bug.save(update_fields=["priority", "updated_at"])
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_UPDATE,
                operator=request.user,
                content=f"批量将优先级从“P{previous_priority}”调整为“P{priority}”",
                metadata={
                    "before_priority": previous_priority,
                    "after_priority": priority,
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量更新 {len(updated_ids)} 条 BUG 的优先级",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-update-severity")
    @permission_required("testcases.change_testbug")
    def batch_update_severity(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        severity = str(request.data.get("severity") or "").strip()
        allowed_severities = {choice[0] for choice in TestBug.SEVERITY_CHOICES}
        if severity not in allowed_severities:
            return Response({"error": "请选择有效的严重程度"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            if bug.severity == severity:
                continue
            previous_severity = bug.severity
            bug.severity = severity
            bug.save(update_fields=["severity", "updated_at"])
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_UPDATE,
                operator=request.user,
                content=f"批量将严重程度从“S{previous_severity}”调整为“S{severity}”",
                metadata={
                    "before_severity": previous_severity,
                    "after_severity": severity,
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量更新 {len(updated_ids)} 条 BUG 的严重程度",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-update-bug-type")
    @permission_required("testcases.change_testbug")
    def batch_update_bug_type(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        bug_type = str(request.data.get("bug_type") or "").strip()
        allowed_bug_types = {choice[0] for choice in TestBug.TYPE_CHOICES}
        if bug_type not in allowed_bug_types:
            return Response({"error": "请选择有效的 BUG 类型"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            if bug.bug_type == bug_type:
                continue
            previous_bug_type = bug.bug_type
            bug.bug_type = bug_type
            bug.save(update_fields=["bug_type", "updated_at"])
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_UPDATE,
                operator=request.user,
                content=(
                    f"批量将 BUG 类型从“{self._get_bug_type_label(previous_bug_type)}”调整为"
                    f"“{self._get_bug_type_label(bug_type)}”"
                ),
                metadata={
                    "before_bug_type": previous_bug_type,
                    "after_bug_type": bug_type,
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量更新 {len(updated_ids)} 条 BUG 的类型",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-update-resolution")
    @permission_required("testcases.change_testbug")
    def batch_update_resolution(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        resolution = str(request.data.get("resolution") or "").strip()
        solution = str(request.data.get("solution") or "").strip()
        allowed_resolutions = {choice[0] for choice in TestBug.RESOLUTION_CHOICES}
        if resolution not in allowed_resolutions:
            return Response({"error": "请选择有效的解决方案"}, status=status.HTTP_400_BAD_REQUEST)

        updated_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            previous_resolution = bug.resolution
            previous_status = bug.get_effective_status()
            if previous_resolution == resolution and (not solution or bug.solution == solution):
                continue

            bug.resolution = resolution
            if solution:
                bug.solution = solution
            bug.save(update_fields=["resolution", "solution", "updated_at"] if solution else ["resolution", "updated_at"])
            self._sync_bug_status_and_resolution(
                bug,
                user=request.user,
                status_explicit=False,
                resolution_explicit=True,
                previous_status=previous_status,
                prefer_confirmed_when_reopen=False,
            )
            self._log_bug_activity(
                bug,
                TestBugActivity.ACTION_UPDATE,
                operator=request.user,
                content=(
                    f"批量将解决方案从“{self._get_bug_resolution_label(previous_resolution)}”调整为"
                    f"“{self._get_bug_resolution_label(resolution)}”"
                ),
                metadata={
                    "before_resolution": previous_resolution,
                    "after_resolution": resolution,
                    "status": bug.get_effective_status(),
                    "solution": bug.solution,
                    "batch": True,
                },
            )
            updated_ids.append(bug.id)

        return Response({
            "message": f"已批量更新 {len(updated_ids)} 条 BUG 的解决方案",
            "updated_ids": updated_ids,
        })

    @action(detail=False, methods=["post"], url_path="batch-delete")
    @permission_required("testcases.delete_testbug")
    def batch_delete(self, request, project_pk=None):
        bug_ids, queryset, error_response = self._get_batch_bug_queryset(request)
        if error_response is not None:
            return error_response

        deleted_ids = []
        for bug in queryset:
            self._ensure_can_manage_bug_status(bug)
            deleted_ids.append(bug.id)
            bug.delete()

        return Response({
            "message": f"已批量删除 {len(deleted_ids)} 条 BUG",
            "updated_ids": deleted_ids,
        })


class TestExecutionViewSet(viewsets.ModelViewSet):
    """
    测试执行视图集，处理测试执行的创建、查看与管理。
    API 端点示例：`/api/projects/{project_pk}/test-executions/`
    """

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["suite__name"]
    ordering_fields = ["created_at", "started_at", "completed_at", "status"]
    ordering = ["-created_at"]

    def _get_snapshot_queryset(self, project):
        return TestReportSnapshot.objects.filter(project=project).select_related("creator")

    def _normalize_report_suite_ids(self, project, suite_ids, *, allow_empty=False):
        if not isinstance(suite_ids, list):
            return None, Response({"error": "测试套件参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            normalized_suite_ids = [int(item) for item in suite_ids]
        except (TypeError, ValueError):
            return None, Response({"error": "测试套件参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_suite_ids = list(dict.fromkeys(normalized_suite_ids))
        if not allow_empty and not normalized_suite_ids:
            return None, Response({"error": "请至少选择一个测试套件"}, status=status.HTTP_400_BAD_REQUEST)

        existing_suite_ids = set(
            TestSuite.objects.filter(project=project, id__in=normalized_suite_ids).values_list("id", flat=True)
        )
        missing_ids = [item for item in normalized_suite_ids if item not in existing_suite_ids]
        if missing_ids:
            return (
                None,
                Response(
                    {"error": f"以下测试套件不存在或不属于当前项目: {missing_ids}"},
                    status=status.HTTP_400_BAD_REQUEST,
                ),
            )

        return normalized_suite_ids, None

    def get_permissions(self):
        """返回当前视图所需的权限实例列表。"""
        from .permissions import IsProjectMemberForTestExecution

        return [
            permissions.IsAuthenticated(),
            HasModelPermission(),
            IsProjectMemberForTestExecution(),
        ]

    def get_queryset(self):
        """根据 URL 中的 `project_pk` 过滤测试执行记录。"""
        project_pk = self.kwargs.get("project_pk")
        if project_pk:
            project = get_object_or_404(Project, pk=project_pk)
            return (
                TestExecution.objects.filter(suite__project=project)
                .select_related("suite", "executor")
                .prefetch_related("results")
            )
        return TestExecution.objects.none()

    def get_serializer_class(self):
        """根据 action 返回对应的序列化器。"""
        from .serializers import TestExecutionSerializer, TestExecutionCreateSerializer



        if self.action == "create":
            return TestExecutionCreateSerializer
        return TestExecutionSerializer

    def create(self, request, *args, **kwargs):
        """创建测试执行并启动 Celery 任务。"""
        from .serializers import TestExecutionCreateSerializer, TestExecutionSerializer
        from .tasks import execute_test_suite

        serializer = TestExecutionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)



        suite_id = serializer.validated_data["suite_id"]
        generate_playwright_script = serializer.validated_data.get(
            "generate_playwright_script", False
        )
        suite = get_object_or_404(TestSuite, id=suite_id)

        # 校验套件属于当前项目
        project_pk = self.kwargs.get("project_pk")
        if suite.project_id != int(project_pk):
            return Response(
                {"error": "测试套件不属于当前项目"}, status=status.HTTP_400_BAD_REQUEST
            )

        # 创建执行记录
        execution = TestExecution.objects.create(
            suite=suite,
            executor=request.user,
            status="pending",
            generate_playwright_script=generate_playwright_script,
        )

        # 使用 transaction.on_commit() 确保事务提交后再启动 Celery 任务
        def start_execution_task():
            task = execute_test_suite.delay(execution.id)
            # 更新 celery_task_id
            TestExecution.objects.filter(id=execution.id).update(celery_task_id=task.id)

        transaction.on_commit(start_execution_task)

        # 返回创建后的执行记录
        result_serializer = TestExecutionSerializer(
            execution, context={"request": request}
        )
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, project_pk=None, pk=None):
        """取消测试执行。"""
        from .tasks import cancel_test_execution
        from celery import current_app

        execution = self.get_object()



        if execution.status not in ["pending", "running"]:
            return Response(
                {"error": f"无法取消状态为 {execution.get_status_display()} 的执行"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 尝试撤销 Celery 任务
        if execution.celery_task_id:
            current_app.control.revoke(execution.celery_task_id, terminate=True)

        # 调用取消任务
        cancel_test_execution.delay(execution.id)

        return Response(
            {"message": "测试执行取消请求已发送"}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, project_pk=None, pk=None):
        """获取测试执行的全部结果。"""
        from .serializers import TestCaseResultSerializer

        execution = self.get_object()
        results = execution.results.all().select_related("testcase")
        serializer = TestCaseResultSerializer(
            results, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="report")
    def report(self, request, project_pk=None, pk=None):
        """生成测试执行报告。"""
        execution = self.get_object()

        report_data = {
            "execution_id": execution.id,
            "suite": {
                "id": execution.suite.id,
                "name": execution.suite.name,
                "description": execution.suite.description,
            },
            "executor": {
                "id": execution.executor.id,
                "username": execution.executor.username,
            }
            if execution.executor
            else None,
            "status": execution.status,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "duration": execution.duration,
            "statistics": {
                "total": execution.total_count,
                "passed": execution.passed_count,
                "failed": execution.failed_count,
                "skipped": execution.skipped_count,
                "error": execution.error_count,
                "pass_rate": execution.pass_rate,
            },
            "results": [],
        }

        # 添加用例执行结果
        for result in execution.results.all().select_related("testcase"):
            screenshots_urls = [
                _normalize_media_url(path) for path in (result.screenshots or [])
            ]
            report_data["results"].append(
                {
                    "testcase_id": result.testcase.id,
                    "testcase_name": result.testcase.name,
                    "status": result.status,
                    "error_message": result.error_message,
                    "execution_time": result.execution_time,
                    "screenshots": screenshots_urls,
                }
            )

        # 添加脚本执行结果
        report_data["script_results"] = []
        for script_result in execution.script_results.all().select_related("script"):
            screenshots_urls = [
                _normalize_media_url(path) for path in (script_result.screenshots or [])
            ]
            videos_urls = [
                _normalize_media_url(path) for path in (script_result.videos or [])
            ]
            report_data["script_results"].append(
                {
                    "script_id": script_result.script.id,
                    "script_name": script_result.script.name,
                    "status": script_result.status,
                    "error_message": script_result.error_message,
                    "execution_time": script_result.execution_time,
                    "output": script_result.output,
                    "screenshots": screenshots_urls,
                    "videos": videos_urls,
                }
            )

        return Response(report_data)

    @action(detail=False, methods=["post"], url_path="ai-report")
    def ai_report(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)
        suite_ids = request.data.get("suite_ids") or []
        selected_suite_ids, error_response = self._normalize_report_suite_ids(project, suite_ids)
        if error_response is not None:
            return error_response

        selected_suites = list(
            TestSuite.objects.filter(project=project, id__in=selected_suite_ids)
            .select_related("parent", "creator")
            .prefetch_related("children")
        )

        expanded_suite_ids = set()
        for suite in selected_suites:
            expanded_suite_ids.update(suite.get_all_descendant_ids())

        suites = list(
            TestSuite.objects.filter(project=project, id__in=expanded_suite_ids)
            .select_related("parent", "creator")
            .prefetch_related("testcases")
        )
        suites_by_id = {suite.id: suite for suite in suites}

        testcase_queryset = (
            TestCase.objects.filter(test_suites__id__in=expanded_suite_ids)
            .select_related("module", "creator")
            .prefetch_related(
                "steps",
                Prefetch(
                    "test_suites",
                    queryset=TestSuite.objects.filter(id__in=expanded_suite_ids).only("id", "name"),
                    to_attr="report_test_suites",
                ),
            )
            .distinct()
        )
        testcases = list(testcase_queryset)
        testcase_ids = [testcase.id for testcase in testcases]

        assignment_map = {
            (assignment.suite_id, assignment.testcase_id): assignment
            for assignment in TestCaseAssignment.objects.filter(
                testcase_id__in=testcase_ids,
                suite_id__in=expanded_suite_ids,
            ).select_related("assignee", "suite")
        }

        bug_queryset = (
            TestBug.objects.filter(project=project, suite_id__in=expanded_suite_ids)
            .select_related("suite", "testcase", "assigned_to", "opened_by", "resolved_by", "closed_by")
            .prefetch_related("related_testcases", "assigned_users")
            .distinct()
        )
        bugs = list(bug_queryset)
        bug_ids = [bug.id for bug in bugs]

        execution_status_distribution = {}
        review_status_distribution = {}
        bug_status_distribution = {}
        bug_priority_distribution = {}
        requirement_document_case_map: dict[str, set[int]] = defaultdict(set)
        requirement_module_case_map: dict[str, set[int]] = defaultdict(set)
        testcase_traceability_map: dict[int, tuple[str, str]] = {}

        suite_case_map: dict[int, list[TestCase]] = {suite.id: [] for suite in suites}
        for testcase in testcases:
            linked_suites = list(getattr(testcase, "report_test_suites", []))
            for suite in linked_suites:
                suite_case_map.setdefault(suite.id, []).append(testcase)

            execution_status_distribution[testcase.execution_status] = (
                execution_status_distribution.get(testcase.execution_status, 0) + 1
            )
            review_status_distribution[testcase.review_status or ""] = (
                review_status_distribution.get(testcase.review_status or "", 0) + 1
            )

            traceability = _extract_requirement_traceability(testcase.notes)
            if traceability:
                document_id, module_id = traceability
                testcase_traceability_map[testcase.id] = traceability
                requirement_document_case_map[document_id].add(testcase.id)
                requirement_module_case_map[module_id].add(testcase.id)

        for bug in bugs:
            effective_status = bug.get_effective_status()
            bug_status_distribution[effective_status] = bug_status_distribution.get(effective_status, 0) + 1
            bug_priority_distribution[bug.priority] = bug_priority_distribution.get(bug.priority, 0) + 1

        testcase_payload = []
        for testcase in testcases:
            linked_suites = list(getattr(testcase, "report_test_suites", []))
            testcase_assignments = []
            assignment_names = []
            for suite in linked_suites:
                assignment = assignment_map.get((suite.id, testcase.id))
                if not assignment:
                    continue
                assignee_name = assignment.assignee.username if assignment.assignee else ""
                testcase_assignments.append(
                    {
                        "suite_id": suite.id,
                        "suite_name": suite.name,
                        "assignee": assignee_name,
                        "assigned_at": assignment.created_at.isoformat() if assignment.created_at else None,
                    }
                )
                if assignee_name and assignee_name not in assignment_names:
                    assignment_names.append(assignee_name)
            steps_payload = [
                {
                    "step_number": getattr(step, "step_number", index + 1),
                    "description": step.description,
                    "expected_result": step.expected_result,
                }
                for index, step in enumerate(testcase.steps.all())
            ]
            testcase_payload.append(
                {
                    "id": testcase.id,
                    "name": testcase.name,
                    "module": testcase.module.name if testcase.module else "",
                    "precondition": testcase.precondition or "",
                    "priority": testcase.level,
                    "test_type": testcase.get_test_type_display() if hasattr(testcase, "get_test_type_display") else testcase.test_type,
                    "review_status": testcase.review_status,
                    "execution_status": testcase.execution_status,
                    "executed_at": testcase.executed_at.isoformat() if testcase.executed_at else None,
                    "creator": testcase.creator.username if testcase.creator else "",
                    "assignee": "、".join(assignment_names),
                    "assigned_at": testcase_assignments[0]["assigned_at"] if len(testcase_assignments) == 1 else None,
                    "assignments": testcase_assignments,
                    "steps": steps_payload,
                    "notes": testcase.notes or "",
                    "related_bug_count": getattr(testcase, "related_bug_count", None),
                }
            )

        linked_document_ids = list(requirement_document_case_map.keys())
        linked_module_ids = list(requirement_module_case_map.keys())
        linked_modules = list(
            RequirementModule.objects.filter(pk__in=linked_module_ids).select_related("document")
        )
        linked_documents = list(
            RequirementDocument.objects.filter(project=project, pk__in=linked_document_ids)
        )
        latest_documents = list(
            RequirementDocument.objects.filter(project=project, is_latest=True)
            .exclude(status="failed")
            .order_by("-updated_at")
        )
        requirement_documents_payload = []
        requirement_document_ids_in_payload: set[str] = set()
        for document in linked_documents + latest_documents:
            document_id = str(document.id)
            if document_id in requirement_document_ids_in_payload:
                continue
            requirement_document_ids_in_payload.add(document_id)
            requirement_documents_payload.append(
                {
                    "id": document_id,
                    "title": document.title,
                    "status": document.status,
                    "version": document.version,
                    "is_latest": bool(document.is_latest),
                    "linked_testcase_count": len(requirement_document_case_map.get(document_id, set())),
                    "module_count": document.modules.count(),
                }
            )

        linked_modules.sort(
            key=lambda item: (
                item.document.title if item.document_id else "",
                item.order,
                item.title,
            )
        )
        requirement_modules_payload = [
            {
                "id": str(module.id),
                "title": module.title,
                "document_id": str(module.document_id),
                "document_title": module.document.title if module.document_id else "",
                "matched_testcase_count": len(requirement_module_case_map.get(str(module.id), set())),
                "content_excerpt": (module.content or "").strip()[:160],
            }
            for module in linked_modules
        ]
        requirement_summary = {
            "testcase_count": len(testcases),
            "traceable_testcase_count": len(testcase_traceability_map),
            "unlinked_testcase_count": max(len(testcases) - len(testcase_traceability_map), 0),
            "linked_document_count": len(linked_document_ids),
            "linked_module_count": len(linked_module_ids),
            "project_latest_document_count": len(latest_documents),
            "documents": requirement_documents_payload,
            "modules": requirement_modules_payload,
        }

        bug_activity_counts: dict[int, dict[str, int]] = defaultdict(
            lambda: {
                "fix_count": 0,
                "resolve_count": 0,
                "activate_count": 0,
                "close_count": 0,
                "confirm_count": 0,
                "assign_count": 0,
            }
        )
        if bug_ids:
            for activity in TestBugActivity.objects.filter(bug_id__in=bug_ids).order_by("created_at", "id"):
                counts = bug_activity_counts[activity.bug_id]
                if activity.action == TestBugActivity.ACTION_FIX:
                    counts["fix_count"] += 1
                elif activity.action == TestBugActivity.ACTION_RESOLVE:
                    counts["resolve_count"] += 1
                elif activity.action == TestBugActivity.ACTION_ACTIVATE:
                    counts["activate_count"] += 1
                elif activity.action == TestBugActivity.ACTION_CLOSE:
                    counts["close_count"] += 1
                elif activity.action == TestBugActivity.ACTION_CONFIRM:
                    counts["confirm_count"] += 1
                elif activity.action == TestBugActivity.ACTION_ASSIGN:
                    counts["assign_count"] += 1

        bug_payload = []
        for bug in bugs:
            workflow_counts = bug_activity_counts.get(
                bug.id,
                {
                    "fix_count": 0,
                    "resolve_count": 0,
                    "activate_count": 0,
                    "close_count": 0,
                    "confirm_count": 0,
                    "assign_count": 0,
                },
            )
            related_testcases = []
            if bug.testcase_id and bug.testcase:
                related_testcases.append({"id": bug.testcase.id, "name": bug.testcase.name})
            related_testcases.extend(
                [
                    {"id": item.id, "name": item.name}
                    for item in bug.related_testcases.exclude(id=bug.testcase_id).order_by("id")
                ]
            )
            bug_payload.append(
                {
                    "id": bug.id,
                    "title": bug.title,
                    "suite": bug.suite.name if bug.suite else "",
                    "bug_type": bug.get_bug_type_display(),
                    "severity": bug.get_severity_display(),
                    "priority": f"P{bug.priority}",
                    "status": bug.get_effective_status_display(),
                    "resolution": bug.get_resolution_display() if bug.resolution else "-",
                    "assigned_to": [user.username for user in bug.assigned_users.order_by("id")] or ([bug.assigned_to.username] if bug.assigned_to else []),
                    "opened_by": bug.opened_by.username if bug.opened_by else "",
                    "opened_at": bug.opened_at.isoformat() if bug.opened_at else None,
                    "assigned_at": bug.assigned_at.isoformat() if bug.assigned_at else None,
                    "resolved_at": bug.resolved_at.isoformat() if bug.resolved_at else None,
                    "closed_at": bug.closed_at.isoformat() if bug.closed_at else None,
                    "deadline": bug.deadline.isoformat() if bug.deadline else None,
                    "keywords": bug.keywords or "",
                    "solution": bug.solution or "",
                    "steps": bug.steps or "",
                    "expected_result": bug.expected_result or "",
                    "actual_result": bug.actual_result or "",
                    "related_testcases": related_testcases,
                    "workflow_counts": {
                        **workflow_counts,
                        "failed_retest_count": workflow_counts.get("activate_count", 0),
                    },
                }
            )

        top_retest_failed_bugs = sorted(
            [
                {
                    "id": bug.id,
                    "title": bug.title,
                    "status": bug.get_effective_status_display(),
                    "suite": bug.suite.name if bug.suite_id else "",
                    "failed_retest_count": bug_activity_counts.get(bug.id, {}).get("activate_count", 0),
                    "fix_count": bug_activity_counts.get(bug.id, {}).get("fix_count", 0),
                    "resolve_count": bug_activity_counts.get(bug.id, {}).get("resolve_count", 0),
                    "close_count": bug_activity_counts.get(bug.id, {}).get("close_count", 0),
                }
                for bug in bugs
                if bug_activity_counts.get(bug.id, {}).get("activate_count", 0) > 0
            ],
            key=lambda item: (-item["failed_retest_count"], item["id"]),
        )
        bug_workflow_summary = {
            "bug_count": len(bugs),
            "fixed_bug_count": sum(1 for bug in bugs if bug_activity_counts.get(bug.id, {}).get("fix_count", 0) > 0),
            "submitted_retest_bug_count": sum(
                1 for bug in bugs if bug_activity_counts.get(bug.id, {}).get("resolve_count", 0) > 0
            ),
            "closed_bug_count": sum(
                1
                for bug in bugs
                if bug.get_effective_status() == TestBug.STATUS_CLOSED
                or bug_activity_counts.get(bug.id, {}).get("close_count", 0) > 0
            ),
            "reactivated_bug_count": sum(
                1 for bug in bugs if bug_activity_counts.get(bug.id, {}).get("activate_count", 0) > 0
            ),
            "confirmed_bug_count": sum(
                1 for bug in bugs if bug_activity_counts.get(bug.id, {}).get("confirm_count", 0) > 0
            ),
            "retest_failed_total_count": sum(
                bug_activity_counts.get(bug.id, {}).get("activate_count", 0) for bug in bugs
            ),
            "bugs_with_failed_retest": top_retest_failed_bugs,
            "top_retest_failed_bugs": top_retest_failed_bugs[:5],
        }

        suite_breakdown = []
        for suite in sorted(suites, key=lambda item: (item.level, item.id)):
            related_cases = suite_case_map.get(suite.id, [])
            suite_bug_list = [bug for bug in bugs if bug.suite_id == suite.id]
            suite_breakdown.append(
                {
                    "id": suite.id,
                    "name": suite.name,
                    "level": suite.level,
                    "parent_id": suite.parent_id,
                    "path": self._build_suite_path(suite, suites_by_id),
                    "testcase_count": len(related_cases),
                    "approved_testcase_count": sum(1 for case in related_cases if case.review_status == "approved"),
                    "failed_testcase_count": sum(1 for case in related_cases if case.execution_status == "failed"),
                    "not_executed_testcase_count": sum(
                        1 for case in related_cases if case.execution_status == "not_executed"
                    ),
                    "bug_count": len(suite_bug_list),
                    "pending_retest_bug_count": sum(
                        1 for bug in suite_bug_list if bug.get_effective_status() == TestBug.STATUS_PENDING_RETEST
                    ),
                    "open_bug_count": sum(
                        1
                        for bug in suite_bug_list
                        if bug.get_effective_status()
                        in {
                            TestBug.STATUS_UNASSIGNED,
                            TestBug.STATUS_ASSIGNED,
                            TestBug.STATUS_CONFIRMED,
                            TestBug.STATUS_FIXED,
                            TestBug.STATUS_PENDING_RETEST,
                            TestBug.STATUS_EXPIRED,
                        }
                    ),
                }
            )

        generated_at = timezone.localtime()
        report_context = {
            "project": {
                "id": project.id,
                "name": project.name,
            },
            "selected_suite_ids": selected_suite_ids,
            "selected_suite_names": [suite.name for suite in selected_suites],
            "generated_at": generated_at.isoformat(),
            "totals": {
                "suite_count": len(suites),
                "selected_suite_count": len(selected_suites),
                "testcase_count": len(testcases),
                "approved_testcase_count": sum(1 for case in testcases if case.review_status == "approved"),
                "bug_count": len(bugs),
            },
            "execution_status_distribution": execution_status_distribution,
            "review_status_distribution": review_status_distribution,
            "bug_status_distribution": bug_status_distribution,
            "bug_priority_distribution": bug_priority_distribution,
            "requirement_summary": requirement_summary,
            "bug_workflow_summary": bug_workflow_summary,
            "suite_breakdown": suite_breakdown,
            "testcases": testcase_payload,
            "bugs": bug_payload,
        }

        report_result = generate_iteration_test_report(user=request.user, report_context=report_context)

        severity_label_map = {
            "1": "致命",
            "2": "严重",
            "3": "一般",
            "4": "轻微",
        }
        execution_label_map = {
            "passed": "通过",
            "failed": "失败",
            "not_executed": "未执行",
            "not_applicable": "阻塞/无需执行",
        }
        bug_status_label_map = {
            TestBug.STATUS_UNASSIGNED: "未指派",
            TestBug.STATUS_ASSIGNED: "未确认",
            TestBug.STATUS_CONFIRMED: "已确认",
            TestBug.STATUS_FIXED: "已修复",
            TestBug.STATUS_PENDING_RETEST: "待复测",
            TestBug.STATUS_CLOSED: "已关闭",
            TestBug.STATUS_EXPIRED: "已过期",
        }

        def _display_name(user_obj):
            if not user_obj:
                return "-"
            return getattr(user_obj, "real_name", "") or getattr(user_obj, "username", "") or "-"

        def _normalize_version(value):
            version = str(value or "").strip()
            if not version:
                return "V1.0"
            return version if version.lower().startswith("v") else f"V{version}"

        def _strip_rich_text(value):
            text = re.sub(r"<[^>]+>", " ", value or "")
            text = (
                text.replace("&nbsp;", " ")
                .replace("&ensp;", " ")
                .replace("&emsp;", " ")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
            )
            return re.sub(r"\s+", " ", text).strip()

        def _short_text(value, limit=80):
            text = _strip_rich_text(value)
            if len(text) <= limit:
                return text or "-"
            return f"{text[:limit].rstrip()}..."

        latest_requirement_item = next(
            (
                item
                for item in requirement_documents_payload
                if item.get("is_latest") and item.get("version")
            ),
            None,
        ) or next((item for item in requirement_documents_payload if item.get("version")), None)
        report_version = _normalize_version(latest_requirement_item.get("version") if latest_requirement_item else None)

        report_author = _display_name(request.user)
        report_owner = _display_name(getattr(project, "creator", None))
        reviewer_candidate = (
            ProjectMember.objects.filter(project=project, role__in=["owner", "admin"])
            .select_related("user")
            .exclude(user=request.user)
            .first()
        )
        report_reviewer = _display_name(
            reviewer_candidate.user if reviewer_candidate and getattr(reviewer_candidate, "user", None) else getattr(project, "creator", None)
        )

        all_project_suites = list(TestSuite.objects.filter(project=project).select_related("parent"))
        all_project_suite_count = len(all_project_suites)
        all_project_suites_by_id = {suite.id: suite for suite in all_project_suites}
        excluded_suite_ids = [suite.id for suite in all_project_suites if suite.id not in expanded_suite_ids]
        excluded_suite_count = len(excluded_suite_ids)
        suite_breakdown_by_id = {item["id"]: item for item in suite_breakdown}
        selected_suite_nodes = [suite_breakdown_by_id[item] for item in selected_suite_ids if item in suite_breakdown_by_id]
        selected_suite_paths = [item["path"] for item in selected_suite_nodes]
        selected_suite_scope = (
            f"本次直接选择 {len(selected_suite_ids)} 个套件：{'；'.join(selected_suite_paths[:5])}"
            if selected_suite_paths
            else "未选择测试套件"
        )
        if selected_suite_paths:
            selected_suite_scope += f"。报告自动覆盖其下共 {len(expanded_suite_ids)} 个套件节点"
            if len(expanded_suite_ids) > len(selected_suite_ids):
                selected_suite_scope += f"（含 {len(expanded_suite_ids) - len(selected_suite_ids)} 个子套件）"
            selected_suite_scope += "。"
        excluded_suite_paths = [
            self._build_suite_path(all_project_suites_by_id[item], all_project_suites_by_id)
            for item in excluded_suite_ids[:5]
            if item in all_project_suites_by_id
        ]
        excluded_scope = (
            f"未纳入本次报告的套件/子套件共 {excluded_suite_count} 个：{'；'.join(excluded_suite_paths)}"
            + (" 等。" if excluded_suite_count > len(excluded_suite_paths) else "。")
            if excluded_suite_count > 0
            else "当前项目全部套件均已纳入本次测试报告。"
        )

        observed_time_points = [generated_at]
        observed_time_points.extend([case.executed_at for case in testcases if case.executed_at])
        observed_time_points.extend([assignment.created_at for assignment in assignment_map.values() if assignment and assignment.created_at])
        observed_time_points.extend([bug.opened_at for bug in bugs if bug.opened_at])
        observed_time_points.extend([bug.assigned_at for bug in bugs if bug.assigned_at])
        observed_time_points.extend([bug.resolved_at for bug in bugs if bug.resolved_at])
        observed_time_points.extend([bug.closed_at for bug in bugs if bug.closed_at])
        observed_time_points = [item for item in observed_time_points if item]
        observed_start = min(observed_time_points) if observed_time_points else generated_at
        observed_end = max(observed_time_points) if observed_time_points else generated_at

        distinct_test_types = sorted(
            {
                testcase.get_test_type_display() if hasattr(testcase, "get_test_type_display") else testcase.test_type
                for testcase in testcases
                if (testcase.get_test_type_display() if hasattr(testcase, "get_test_type_display") else testcase.test_type)
            }
        )

        passed_count = execution_status_distribution.get("passed", 0)
        failed_count = execution_status_distribution.get("failed", 0)
        not_executed_count = execution_status_distribution.get("not_executed", 0)
        blocked_count = execution_status_distribution.get("not_applicable", 0)
        executed_count = max(len(testcases) - not_executed_count, 0)
        pass_rate = round((passed_count / executed_count) * 100, 2) if executed_count else 0
        approved_testcase_count = sum(1 for case in testcases if case.review_status == "approved")
        unapproved_testcase_count = max(len(testcases) - approved_testcase_count, 0)
        pending_review_testcase_count = (
            review_status_distribution.get("pending_review", 0)
            + review_status_distribution.get("optimization_pending_review", 0)
        )
        traceable_testcase_count = requirement_summary.get("traceable_testcase_count", 0)
        unlinked_testcase_count = requirement_summary.get("unlinked_testcase_count", 0)

        severity_distribution = {
            "致命": 0,
            "严重": 0,
            "一般": 0,
            "轻微": 0,
        }
        open_bugs = []
        by_module_bug_map = defaultdict(int)
        bug_list_rows = []
        for bug in bugs:
            severity_label = severity_label_map.get(bug.severity, bug.severity or "-")
            effective_status = bug.get_effective_status()
            status_label = bug_status_label_map.get(effective_status, bug.get_effective_status_display())
            workflow_counts = bug_activity_counts.get(
                bug.id,
                {
                    "fix_count": 0,
                    "resolve_count": 0,
                    "activate_count": 0,
                    "close_count": 0,
                    "confirm_count": 0,
                    "assign_count": 0,
                },
            )
            related_testcase_names = list(bug.related_testcases.order_by("id").values_list("name", flat=True))
            impact_parts = []
            if bug.suite:
                impact_parts.append(f"影响套件：{bug.suite.name}")
            if related_testcase_names:
                testcase_scope = "、".join(related_testcase_names[:3])
                if len(related_testcase_names) > 3:
                    testcase_scope += "等"
                impact_parts.append(f"关联用例：{testcase_scope}")
            actual_summary = _short_text(bug.actual_result or bug.expected_result or bug.steps, 70)
            if actual_summary and actual_summary != "-":
                impact_parts.append(f"问题表现：{actual_summary}")

            if effective_status == TestBug.STATUS_CLOSED:
                risk_acceptance = "该 BUG 已完成关闭验证，可接受当前风险。"
            elif effective_status == TestBug.STATUS_EXPIRED:
                risk_acceptance = "该 BUG 已超过解决时间且仍未关闭，当前风险不可接受。"
            elif workflow_counts.get("activate_count", 0) > 0:
                risk_acceptance = (
                    f"该 BUG 已复测失败 {workflow_counts['activate_count']} 次，需继续修复并重新验证，当前不建议接受风险。"
                )
            elif bug.severity in {"1", "2"}:
                risk_acceptance = "存在未关闭的高风险缺陷，当前不建议接受风险。"
            elif effective_status in {TestBug.STATUS_FIXED, TestBug.STATUS_PENDING_RETEST}:
                risk_acceptance = "开发已完成处理但尚未闭环，需测试复测通过后再评估是否接受风险。"
            else:
                risk_acceptance = "缺陷尚未闭环，需继续指派、修复并跟进验证。"
            severity_distribution[severity_label] = severity_distribution.get(severity_label, 0) + 1
            by_module_bug_map[bug.suite.name if bug.suite else "未归属套件"] += 1
            if effective_status != TestBug.STATUS_CLOSED:
                open_bugs.append(bug)
            bug_list_rows.append(
                {
                    "id": bug.id,
                    "title": bug.title,
                    "severity": severity_label,
                    "status": status_label,
                    "module": bug.suite.name if bug.suite else "未归属套件",
                    "impact_scope": "；".join(impact_parts) if impact_parts else "-",
                    "repro_steps": _short_text(bug.steps, 120),
                    "planned_fix_version": bug.deadline.isoformat() if bug.deadline else "未设置解决时间",
                    "risk_acceptance": risk_acceptance,
                }
            )

        high_severity_open_bug_count = sum(
            1
            for bug in open_bugs
            if bug.severity in {"1", "2"}
        )

        module_bug_distribution = [
            {"name": name, "count": count}
            for name, count in sorted(by_module_bug_map.items(), key=lambda item: (-item[1], item[0]))
        ]
        bug_status_summary = [
            {
                "name": bug_status_label_map.get(key, key),
                "count": value,
            }
            for key, value in sorted(bug_status_distribution.items(), key=lambda item: item[0])
        ]
        severity_summary = [
            {"name": name, "count": count}
            for name, count in severity_distribution.items()
        ]

        completion_criteria = [
            {
                "name": "测试范围内至少已有有效执行结果",
                "passed": executed_count > 0,
                "detail": f"当前已执行用例 {executed_count} 条，未执行用例 {not_executed_count} 条",
            },
            {
                "name": "无未关闭致命/严重缺陷",
                "passed": high_severity_open_bug_count == 0,
                "detail": f"当前未关闭致命/严重缺陷 {high_severity_open_bug_count} 个",
            },
            {
                "name": "核心测试执行失败数为 0",
                "passed": failed_count == 0,
                "detail": f"当前失败用例 {failed_count} 条",
            },
            {
                "name": "测试用例均已审核通过",
                "passed": unapproved_testcase_count == 0,
                "detail": (
                    f"当前审核通过 {approved_testcase_count} 条，未通过审核 {unapproved_testcase_count} 条，"
                    f"其中待审核/优化待审核 {pending_review_testcase_count} 条"
                ),
            },
            {
                "name": "测试范围内用例已全部执行",
                "passed": not_executed_count == 0,
                "detail": f"当前未执行用例 {not_executed_count} 条",
            },
            {
                "name": "测试用例已完成需求追踪",
                "passed": unlinked_testcase_count == 0,
                "detail": f"当前已关联需求 {traceable_testcase_count} 条，未关联需求 {unlinked_testcase_count} 条",
            },
            {
                "name": "BUG 闭环达到收敛状态",
                "passed": bug_workflow_summary["retest_failed_total_count"] == 0 and len(open_bugs) == 0,
                "detail": (
                    f"当前未关闭 BUG {len(open_bugs)} 个，复测失败累计 {bug_workflow_summary['retest_failed_total_count']} 次"
                ),
            },
        ]
        passed_criteria_count = sum(1 for item in completion_criteria if item["passed"])
        all_criteria_passed = passed_criteria_count == len(completion_criteria)
        has_blocking_quality_risk = any(
            [
                len(testcases) == 0,
                approved_testcase_count == 0 and len(testcases) > 0,
                unapproved_testcase_count > 0,
                executed_count == 0 and len(testcases) > 0,
                high_severity_open_bug_count > 0,
                failed_count > 0,
            ]
        )
        has_residual_release_risk = any(
            [
                len(open_bugs) > 0,
                bug_workflow_summary["retest_failed_total_count"] > 0,
                not_executed_count > 0,
                unlinked_testcase_count > 0,
            ]
        )

        if len(testcases) == 0:
            quality_rating = "不合格"
            release_recommendation = "不建议发布"
        elif has_blocking_quality_risk:
            quality_rating = "不合格"
            release_recommendation = "不建议发布"
        elif all_criteria_passed:
            quality_rating = "优"
            release_recommendation = "建议发布"
        elif has_residual_release_risk:
            quality_rating = "良"
            release_recommendation = "有条件发布"
        elif passed_criteria_count >= len(completion_criteria) - 1:
            quality_rating = "合格"
            release_recommendation = "建议发布"
        else:
            quality_rating = "良"
            release_recommendation = "有条件发布"

        process_risks = []
        if unapproved_testcase_count > 0:
            process_risks.append(
                f"当前仍有 {unapproved_testcase_count} 条测试用例未审核通过，其中待审核/优化待审核 {pending_review_testcase_count} 条，测试资产尚未达到发布评估前提。"
            )
        if unlinked_testcase_count > 0:
            process_risks.append(
                f"仍有 {unlinked_testcase_count} 条测试用例未关联需求，测试范围与需求覆盖关系追溯不完整。"
            )
        if not_executed_count > 0:
            process_risks.append(f"仍有 {not_executed_count} 条测试用例未执行，当前测试活动尚未完整覆盖所选套件范围。")
        if not distinct_test_types:
            process_risks.append("当前测试用例未完整标注测试类型，测试活动分类统计存在缺口。")
        process_risks.append("当前系统未结构化记录硬件、网络、浏览器、中间件版本等环境数据，环境可追溯性不足。")

        residual_risks = []
        if executed_count == 0 and len(testcases) > 0:
            residual_risks.append("当前测试范围内用例尚未开始执行，缺少有效执行结果，无法支撑发布判断。")
        if high_severity_open_bug_count > 0:
            residual_risks.append(
                f"仍有 {high_severity_open_bug_count} 个致命/严重 BUG 未关闭，核心业务上线风险较高。"
            )
        if len(open_bugs) > 0:
            residual_risks.append(f"仍有 {len(open_bugs)} 个 BUG 未关闭，需在发布前确认影响范围与风险接受策略。")
        if bug_workflow_summary["retest_failed_total_count"] > 0:
            residual_risks.append(
                f"BUG 复测失败累计 {bug_workflow_summary['retest_failed_total_count']} 次，说明部分问题修复质量仍需重点验证。"
            )
        if not_executed_count > 0:
            residual_risks.append(f"未执行用例 {not_executed_count} 条，剩余需求覆盖与边界风险仍未被完全验证。")
        if unlinked_testcase_count > 0:
            residual_risks.append(
                f"仍有 {unlinked_testcase_count} 条测试用例未完成需求追踪映射，发布后的问题回溯与覆盖证明存在缺口。"
            )

        follow_up_actions = []
        if unapproved_testcase_count > 0:
            follow_up_actions.append("先完成测试用例审核，使测试范围内用例全部达到可执行、可评估状态后再生成发布结论。")
        if executed_count == 0 and len(testcases) > 0:
            follow_up_actions.append("先执行当前测试范围内测试用例并回填真实执行结果，再生成测试报告。")
        if high_severity_open_bug_count > 0:
            follow_up_actions.append("优先关闭全部未关闭的致命/严重 BUG，完成复测通过后再进入发布评审。")
        if failed_count > 0:
            follow_up_actions.append("按失败用例所属套件逐项复盘失败原因，并补充回归验证记录。")
        if not_executed_count > 0:
            follow_up_actions.append("补齐未执行用例的执行结果，避免测试报告范围与实际交付范围不一致。")
        if unlinked_testcase_count > 0:
            follow_up_actions.append("为未关联需求的测试用例补齐需求文档与需求模块映射，提升报告可追溯性。")
        for item in report_result.recommendations[:5]:
            detail = item["detail"]
            if detail and detail not in follow_up_actions:
                follow_up_actions.append(detail)
        if not follow_up_actions:
            follow_up_actions.append("建议持续补齐环境记录、执行结果和 BUG 闭环信息，确保后续版本测试报告可直接复用。")

        conclusion_parts = [
            f"本轮共纳入 {len(testcases)} 条测试用例，已执行 {executed_count} 条，通过 {passed_count} 条，失败 {failed_count} 条，未执行 {not_executed_count} 条，执行通过率 {pass_rate}%。",
            f"当前审核通过 {approved_testcase_count} 条，未通过审核 {unapproved_testcase_count} 条。",
            f"同步统计 BUG {len(bugs)} 个，其中未关闭 {len(open_bugs)} 个，致命/严重未关闭 {high_severity_open_bug_count} 个，复测失败累计 {bug_workflow_summary['retest_failed_total_count']} 次。",
        ]
        if unlinked_testcase_count > 0:
            conclusion_parts.append(
                f"当前仍有 {unlinked_testcase_count} 条测试用例未完成需求追踪映射，报告追溯完整性仍需补齐。"
            )
        if approved_testcase_count == 0 and len(testcases) > 0:
            conclusion_parts.append("当前测试范围内用例均未审核通过，尚不具备发布评估前提。")
        elif unapproved_testcase_count > 0:
            conclusion_parts.append("当前仍有部分测试用例未审核通过，测试资产完整性不足。")
        if executed_count == 0 and len(testcases) > 0:
            conclusion_parts.append("当前测试范围内用例尚未执行，缺少有效执行证据。")
        if release_recommendation == "建议发布":
            conclusion_parts.append("核心完成标准已达成，当前质量状态支持进入发布或上线验证阶段。")
        elif release_recommendation == "有条件发布":
            conclusion_parts.append("当前建议有条件发布，需先明确遗留缺陷、未执行项或复测风险的接受与跟进责任。")
        else:
            conclusion_parts.append("当前仍存在阻断发布的质量风险，暂不建议进入发布阶段。")
        computed_conclusion = "".join(conclusion_parts)

        report_standard = {
            "basic_info": {
                "report_no": f"TR-{project.id}-{generated_at.strftime('%Y%m%d%H%M%S')}",
                "report_version": report_version,
                "report_date": generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "author": report_author,
                "owner": report_owner,
                "reviewer": report_reviewer,
            },
            "test_overview": {
                "test_object": project.name,
                "target_version": report_version,
                "scope_included": selected_suite_scope,
                "scope_excluded": excluded_scope,
                "objectives": [
                    "验证所选测试套件及其子套件下测试用例的执行结果与覆盖情况。",
                    "核对需求文档、需求模块与测试用例之间的追踪关系是否完整。",
                    "评估 BUG 从提出、指派、修复到复测/关闭的闭环质量与风险状态。",
                ],
            },
            "environment": {
                "hardware_network": "当前系统未采集服务器硬件、终端型号和网络模拟信息，需由测试执行人补充。",
                "software_environment": "当前系统未采集操作系统、数据库、浏览器、中间件版本信息，报告仅基于测试资产与缺陷数据生成。",
                "test_tools": ["FlyTest 测试用例库", "FlyTest BUG 管理", "需求文档追踪", "AI 测试报告生成"],
                "third_party_services": "当前系统未记录第三方服务版本与依赖信息。",
            },
            "activity_summary": {
                "test_types": distinct_test_types or ["未标注"],
                "test_round": "当前迭代测试报告",
                "time_span": {
                    "start": observed_start.isoformat() if observed_start else None,
                    "end": observed_end.isoformat() if observed_end else None,
                },
                "workload": {
                    "person_days": "当前系统未统计",
                    "total_cases": len(testcases),
                    "executed_cases": executed_count,
                    "automation_ratio": "当前系统未统计",
                    "bug_count": len(bugs),
                },
            },
            "result_details": {
                "case_execution": {
                    "total": len(testcases),
                    "passed": passed_count,
                    "failed": failed_count,
                    "blocked": blocked_count,
                    "not_executed": not_executed_count,
                    "pass_rate": pass_rate,
                },
                "execution_breakdown": [
                    {"name": execution_label_map.get(key, key), "count": value}
                    for key, value in execution_status_distribution.items()
                ],
            },
            "defect_summary": {
                "by_severity": severity_summary,
                "by_status": bug_status_summary,
                "by_module": module_bug_distribution,
                "trend_summary": {
                    "discovered": len(bugs),
                    "closed": bug_workflow_summary["closed_bug_count"],
                    "reactivated": bug_workflow_summary["reactivated_bug_count"],
                    "retest_failed_total": bug_workflow_summary["retest_failed_total_count"],
                },
                "legacy_defects": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "severity": item["severity"],
                        "status": item["status"],
                        "module": item["module"],
                        "repro_steps": item["repro_steps"],
                        "impact_scope": item["impact_scope"],
                        "planned_fix_version": item["planned_fix_version"],
                        "risk_acceptance": item["risk_acceptance"],
                    }
                    for item in bug_list_rows
                    if item["status"] != "已关闭"
                ],
            },
            "quality_conclusion": {
                "rating": quality_rating,
                "release_recommendation": release_recommendation,
                "criteria": completion_criteria,
                "conclusion": computed_conclusion,
            },
            "risk_and_suggestions": {
                "process_risks": process_risks,
                "residual_risks": residual_risks or ["当前未识别额外剩余风险。"],
                "follow_up_actions": follow_up_actions,
            },
            "appendices": {
                "defect_list_summary": {
                    "total": len(bugs),
                    "open_total": len(open_bugs),
                    "items": bug_list_rows[:20],
                },
                "key_testcases": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "module": item["module"],
                        "test_type": item["test_type"],
                        "execution_status": item["execution_status"],
                    }
                    for item in testcase_payload[:20]
                ],
                "requirement_documents": [
                    {
                        "title": item["title"],
                        "version": item["version"],
                        "status": item["status"],
                    }
                    for item in requirement_documents_payload
                ],
                "test_data_note": "当前报告直接使用所选套件下的测试用例、需求追踪与 BUG 数据生成，未额外注入模拟测试数据。",
            },
        }

        normalized_findings = [
            {
                "title": str(item.get("title") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
                "severity": str(item.get("severity") or "medium").strip().lower() or "medium",
            }
            for item in (report_result.findings or [])
            if isinstance(item, dict) and str(item.get("title") or "").strip() and str(item.get("detail") or "").strip()
        ]
        normalized_recommendations = [
            {
                "title": str(item.get("title") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
                "priority": str(item.get("priority") or "medium").strip().lower() or "medium",
            }
            for item in (report_result.recommendations or [])
            if isinstance(item, dict) and str(item.get("title") or "").strip() and str(item.get("detail") or "").strip()
        ]
        normalized_evidence = [
            {
                "label": str(item.get("label") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
            }
            for item in (report_result.evidence or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip() and str(item.get("detail") or "").strip()
        ]

        return Response(
            {
                "success": True,
                "data": {
                    "suite_ids": selected_suite_ids,
                    "suite_count": len(suites),
                    "selected_suite_count": len(selected_suites),
                    "testcase_count": len(testcases),
                    "bug_count": len(bugs),
                    "generated_at": report_context["generated_at"],
                    "used_ai": report_result.used_ai,
                    "note": report_result.note,
                    "model_name": report_result.model_name,
                    "generation_source": getattr(report_result, "generation_source", "ai" if report_result.used_ai else "rule"),
                    "generation_status": getattr(report_result, "generation_status", "completed"),
                    "generation_duration_ms": getattr(report_result, "generation_duration_ms", 0),
                    "fallback_reason": getattr(report_result, "fallback_reason", ""),
                    "summary": str(report_result.summary or "").strip(),
                    "quality_overview": str(report_result.quality_overview or "").strip(),
                    "risk_overview": str(report_result.risk_overview or "").strip(),
                    "findings": normalized_findings,
                    "recommendations": normalized_recommendations,
                    "evidence": normalized_evidence,
                    "suite_breakdown": suite_breakdown,
                    "execution_status_distribution": execution_status_distribution,
                    "bug_status_distribution": bug_status_distribution,
                    "review_status_distribution": review_status_distribution,
                    "requirement_summary": requirement_summary,
                    "bug_workflow_summary": bug_workflow_summary,
                    "report_standard": report_standard,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get", "post"], url_path="report-snapshots")
    def report_snapshots(self, request, project_pk=None):
        project = get_object_or_404(Project, pk=project_pk)

        if request.method.lower() == "get":
            snapshots = self._get_snapshot_queryset(project)[:20]
            serializer = TestReportSnapshotSerializer(snapshots, many=True)
            return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

        title = str(request.data.get("title") or "").strip()
        suite_ids = request.data.get("suite_ids") or []
        report_data = request.data.get("report_data") or {}

        if not title:
            return Response({"error": "快照标题不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(report_data, dict):
            return Response({"error": "报告数据格式错误"}, status=status.HTTP_400_BAD_REQUEST)

        normalized_suite_ids, error_response = self._normalize_report_suite_ids(project, suite_ids)
        if error_response is not None:
            return error_response

        snapshot = TestReportSnapshot.objects.create(
            project=project,
            title=title,
            is_pinned=bool(request.data.get("is_pinned", False)),
            suite_ids=normalized_suite_ids,
            report_data=report_data,
            creator=request.user,
        )

        snapshots_to_keep = list(self._get_snapshot_queryset(project).values_list("id", flat=True)[:20])
        self._get_snapshot_queryset(project).exclude(id__in=snapshots_to_keep).delete()

        serializer = TestReportSnapshotSerializer(snapshot)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["delete"], url_path=r"report-snapshots/(?P<snapshot_id>[^/.]+)")
    def delete_report_snapshot(self, request, project_pk=None, snapshot_id=None):
        project = get_object_or_404(Project, pk=project_pk)
        snapshot = get_object_or_404(self._get_snapshot_queryset(project), pk=snapshot_id)
        snapshot.delete()
        return Response({"success": True, "message": "报告快照已删除"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["patch"], url_path=r"report-snapshots/(?P<snapshot_id>[^/.]+)/update")
    def update_report_snapshot(self, request, project_pk=None, snapshot_id=None):
        project = get_object_or_404(Project, pk=project_pk)
        snapshot = get_object_or_404(self._get_snapshot_queryset(project), pk=snapshot_id)

        updated_fields = []
        title = request.data.get("title")
        if title is not None:
            title = str(title).strip()
            if not title:
                return Response({"error": "快照标题不能为空"}, status=status.HTTP_400_BAD_REQUEST)
            snapshot.title = title
            updated_fields.append("title")

        if "is_pinned" in request.data:
            snapshot.is_pinned = bool(request.data.get("is_pinned"))
            updated_fields.append("is_pinned")

        if "suite_ids" in request.data:
            suite_ids = request.data.get("suite_ids") or []
            normalized_suite_ids, error_response = self._normalize_report_suite_ids(project, suite_ids)
            if error_response is not None:
                return error_response
            snapshot.suite_ids = normalized_suite_ids
            updated_fields.append("suite_ids")

        if "report_data" in request.data:
            report_data = request.data.get("report_data") or {}
            if not isinstance(report_data, dict):
                return Response({"error": "report_data 参数格式错误"}, status=status.HTTP_400_BAD_REQUEST)
            snapshot.report_data = report_data
            updated_fields.append("report_data")

        if not updated_fields:
            return Response({"error": "没有可更新的内容"}, status=status.HTTP_400_BAD_REQUEST)

        updated_fields.append("updated_at")
        snapshot.save(update_fields=updated_fields)
        serializer = TestReportSnapshotSerializer(snapshot)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def _build_suite_path(self, suite, suites_by_id):
        names = [suite.name]
        parent_id = suite.parent_id
        while parent_id:
            parent_suite = suites_by_id.get(parent_id)
            if parent_suite is None:
                break
            names.append(parent_suite.name)
            parent_id = parent_suite.parent_id
        names.reverse()
        return " / ".join(names)

    def destroy(self, request, *args, **kwargs):
        """
        删除测试执行记录。
        仅允许删除已完成、失败或已取消的记录。
        """
        execution = self.get_object()

        # 正在运行或等待中的执行不允许直接删除
        if execution.status in ["pending", "running"]:
            return Response(
                {
                    "error": f'无法删除状态为 "{execution.get_status_display()}" 的执行记录，请先取消执行'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 记录删除前信息，便于返回给前端
        execution_info = {
            "id": execution.id,
            "suite_name": execution.suite.name,
            "status": execution.status,
            "created_at": execution.created_at,
        }

        # 执行删除，关联的 TestCaseResult 会级联删除
        execution.delete()


        return Response(
            {"message": "测试执行记录已删除", "deleted_execution": execution_info},
            status=status.HTTP_200_OK,
        )
