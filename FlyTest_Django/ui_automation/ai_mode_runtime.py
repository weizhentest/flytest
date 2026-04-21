import base64
import asyncio
import importlib.util
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import timedelta
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

from django.conf import settings
from django.db import close_old_connections
from django.db import transaction
from django.db.utils import OperationalError
from django.utils import timezone
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig, get_user_active_llm_config
from .models import UiAIExecutionRecord, UiElement, UiEnvironmentConfig, UiModule, UiPage

logger = logging.getLogger(__name__)

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

AI_STOP_SIGNALS: dict[int, bool] = {}
AI_EXECUTION_STALE_TIMEOUT_SECONDS = 180
AI_EXECUTION_DISPATCH_INTERVAL_SECONDS = 2.0
AI_EXECUTION_PROCESS_TOKEN = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
UI_AI_CELERY_ENABLED = os.environ.get("UI_AUTOMATION_AI_USE_CELERY", "").strip().lower() in {"1", "true", "yes", "on"}
UI_AI_CELERY_QUEUE = os.environ.get("UI_AUTOMATION_CELERY_QUEUE", "ui_automation")
ACTION_CALL_RE = re.compile(r"^(?P<name>\w+)\((?P<params>.*)\)$")
PLACEHOLDER_SCREENSHOT_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
_BROWSER_USE_RUNTIME_PATCHES_APPLIED = False
_AI_DISPATCHER_THREAD: threading.Thread | None = None
_AI_DISPATCHER_LOCK = threading.Lock()
_AI_DISPATCHER_WAKE_EVENT = threading.Event()
_ACTIVE_EXECUTION_THREADS: dict[int, threading.Thread] = {}
_ACTIVE_EXECUTION_LOCK = threading.Lock()

__all__ = [
    "AI_STOP_SIGNALS",
    "AIExecutionStopped",
    "build_ai_execution_report",
    "get_ai_runtime_capabilities",
    "request_stop_ai_execution",
    "run_ai_execution",
    "start_ai_execution",
]


class AIExecutionStopped(Exception):
    """Raised when the user stops an AI execution."""


@dataclass
class ExecutionRuntimeState:
    record_id: int
    case_name: str
    logs: str = ""
    planned_tasks: list[dict[str, Any]] = field(default_factory=list)
    steps_completed: list[dict[str, Any]] = field(default_factory=list)
    screenshots_sequence: list[str] = field(default_factory=list)
    gif_path: str | None = None
    model_config_name: str | None = None
    execution_backend: str = "planning"
    last_persist_at: float = 0.0

    def append_log(self, message: str) -> None:
        timestamp = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
        self.logs = f"{self.logs}[{timestamp}] {message}\n"


class BrowserUseLangChainAdapter:
    """
    Adapt FlyTest's LangChain chat models to the browser-use LLM protocol.
    """

    _verified_api_keys = False

    def __init__(self, llm: Any, provider: str, model_name: str):
        self._llm = llm
        self._provider = provider or "openai_compatible"
        self.model = model_name

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def name(self) -> str:
        return self.model

    @property
    def model_name(self) -> str:
        return self.model

    async def ainvoke(self, messages: list[Any], output_format: type[Any] | None = None) -> Any:
        lc_messages = self._convert_messages(messages)
        if output_format is None:
            response = await self._llm.ainvoke(lc_messages)
            return SimpleNamespace(completion=_read_llm_content(response))

        structured = await self._invoke_structured_async(lc_messages, output_format)
        return SimpleNamespace(completion=structured)

    def invoke(self, messages: list[Any], output_format: type[Any] | None = None) -> Any:
        lc_messages = self._convert_messages(messages)
        if output_format is None:
            response = self._llm.invoke(lc_messages)
            return SimpleNamespace(completion=_read_llm_content(response))

        structured = self._invoke_structured_sync(lc_messages, output_format)
        return SimpleNamespace(completion=structured)

    def _convert_messages(self, messages: Sequence[Any]) -> list[Any]:
        converted: list[Any] = []
        for message in messages:
            role = getattr(message, "role", "user")
            content = getattr(message, "content", "")
            if role == "system":
                converted.append(SystemMessage(content=self._to_text_content(content)))
            elif role == "assistant":
                converted.append(AIMessage(content=self._assistant_text(message)))
            else:
                converted.append(HumanMessage(content=self._to_human_content(content)))
        return converted

    def _assistant_text(self, message: Any) -> str:
        text = getattr(message, "text", "") or self._to_text_content(getattr(message, "content", ""))
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            return text

        serialized_calls: list[str] = []
        for tool_call in tool_calls:
            name = getattr(getattr(tool_call, "function", None), "name", None)
            arguments = getattr(getattr(tool_call, "function", None), "arguments", None)
            if name:
                serialized_calls.append(f"{name}({arguments or ''})")

        if not serialized_calls:
            return text
        prefix = f"{text}\n\n" if text else ""
        return f"{prefix}Tool calls: {'; '.join(serialized_calls)}"

    def _to_human_content(self, content: Any) -> Any:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content or "")

        parts: list[dict[str, Any]] = []
        for item in content:
            item_type = getattr(item, "type", None)
            if item_type == "text":
                parts.append({"type": "text", "text": getattr(item, "text", "")})
            elif item_type == "image_url":
                image_url = getattr(item, "image_url", None)
                if image_url is None:
                    continue
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": getattr(image_url, "url", ""),
                            "detail": getattr(image_url, "detail", "auto"),
                        },
                    }
                )
        return parts or self._to_text_content(content)

    def _to_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                item_type = getattr(item, "type", None)
                if item_type == "text":
                    text_parts.append(str(getattr(item, "text", "")))
                elif item_type == "refusal":
                    text_parts.append(str(getattr(item, "refusal", "")))
                elif item_type == "image_url":
                    image_url = getattr(item, "image_url", None)
                    if image_url is not None:
                        text_parts.append(f"[image:{getattr(image_url, 'url', '')}]")
                else:
                    text_parts.append(str(item))
            return "\n".join(part for part in text_parts if part)
        return str(content or "")

    async def _invoke_structured_async(self, messages: list[Any], output_format: type[Any]) -> Any:
        with_structured_output = getattr(self._llm, "with_structured_output", None)
        if callable(with_structured_output):
            try:
                structured_llm = with_structured_output(output_format)
                response = await structured_llm.ainvoke(messages)
                return _validate_structured_output(response, output_format)
            except Exception as exc:
                logger.warning("Structured output fallback triggered for async browser-use call: %s", exc)

        response = await self._llm.ainvoke(messages)
        payload = _normalize_structured_payload(_extract_json_payload(_read_llm_content(response)))
        return _validate_structured_output(payload, output_format)

    def _invoke_structured_sync(self, messages: list[Any], output_format: type[Any]) -> Any:
        with_structured_output = getattr(self._llm, "with_structured_output", None)
        if callable(with_structured_output):
            try:
                structured_llm = with_structured_output(output_format)
                response = structured_llm.invoke(messages)
                return _validate_structured_output(response, output_format)
            except Exception as exc:
                logger.warning("Structured output fallback triggered for sync browser-use call: %s", exc)

        response = self._llm.invoke(messages)
        payload = _normalize_structured_payload(_extract_json_payload(_read_llm_content(response)))
        return _validate_structured_output(payload, output_format)


def _apply_browser_use_runtime_patches() -> None:
    global _BROWSER_USE_RUNTIME_PATCHES_APPLIED

    if _BROWSER_USE_RUNTIME_PATCHES_APPLIED:
        return

    try:
        from browser_use.browser.watchdogs.dom_watchdog import DOMWatchdog
        from browser_use.browser.watchdogs.screenshot_watchdog import ScreenshotWatchdog

        original_on_screenshot_event = getattr(ScreenshotWatchdog, "on_ScreenshotEvent", None)
        if callable(original_on_screenshot_event) and not getattr(original_on_screenshot_event, "_flytest_patched", False):

            async def on_screenshot_event(self: Any, event: Any) -> Any:
                try:
                    return await asyncio.wait_for(original_on_screenshot_event(self, event), timeout=3.0)
                except asyncio.TimeoutError:
                    logger.warning("Screenshot watchdog timed out, trying direct CDP screenshot fallback.")
                    try:
                        cdp_session = await self.browser_session.get_or_create_cdp_session(target_id=None)
                        if not cdp_session:
                            raise RuntimeError("No CDP session available for screenshot fallback.")

                        params = {
                            "format": "png",
                            "quality": 50,
                            "from_surface": True,
                            "capture_beyond_viewport": False,
                        }
                        return await asyncio.wait_for(
                            cdp_session.cdp_client.send.Page.captureScreenshot(
                                params=params,
                                session_id=cdp_session.session_id,
                            ),
                            timeout=3.0,
                        )
                    except Exception as exc:
                        logger.warning("Screenshot fallback failed, returning placeholder image: %s", exc)
                        return {"data": PLACEHOLDER_SCREENSHOT_BYTES}
                except Exception as exc:
                    logger.warning("Screenshot watchdog failed unexpectedly, returning placeholder image: %s", exc)
                    return {"data": PLACEHOLDER_SCREENSHOT_BYTES}

            on_screenshot_event._flytest_patched = True  # type: ignore[attr-defined]
            ScreenshotWatchdog.on_ScreenshotEvent = on_screenshot_event

        original_capture_clean_screenshot = getattr(DOMWatchdog, "_capture_clean_screenshot", None)
        if callable(original_capture_clean_screenshot) and not getattr(original_capture_clean_screenshot, "_flytest_patched", False):

            async def capture_clean_screenshot(self: Any) -> Any:
                try:
                    return await asyncio.wait_for(original_capture_clean_screenshot(self), timeout=3.0)
                except Exception as exc:
                    logger.warning("DOM watchdog clean screenshot failed or timed out, continuing: %s", exc)
                    return None

            capture_clean_screenshot._flytest_patched = True  # type: ignore[attr-defined]
            DOMWatchdog._capture_clean_screenshot = capture_clean_screenshot

        _BROWSER_USE_RUNTIME_PATCHES_APPLIED = True
    except Exception as exc:
        logger.warning("Unable to apply browser-use runtime patches: %s", exc)


def _ensure_ai_dispatcher_started() -> None:
    global _AI_DISPATCHER_THREAD

    with _AI_DISPATCHER_LOCK:
        if _AI_DISPATCHER_THREAD and _AI_DISPATCHER_THREAD.is_alive():
            return

        _AI_DISPATCHER_THREAD = threading.Thread(
            target=_dispatch_ai_executions_forever,
            daemon=True,
            name="ui-ai-dispatcher",
        )
        _AI_DISPATCHER_THREAD.start()


def _dispatch_ai_executions_forever() -> None:
    while True:
        try:
            _requeue_stale_ai_executions()
            claimed = _claim_next_ai_execution()
            if claimed:
                record_id, worker_token = claimed
                _spawn_ai_execution_worker(record_id, worker_token)
                continue
        except OperationalError as exc:
            if 'locked' in str(exc).lower():
                logger.debug("Skip one dispatcher cycle because database is locked")
            else:
                logger.exception("UI AI execution dispatcher hit database error")
        except Exception:
            logger.exception("UI AI execution dispatcher loop failed")

        _AI_DISPATCHER_WAKE_EVENT.wait(timeout=AI_EXECUTION_DISPATCH_INTERVAL_SECONDS)
        _AI_DISPATCHER_WAKE_EVENT.clear()


def _requeue_stale_ai_executions() -> None:
    close_old_connections()
    stale_before = timezone.now() - timedelta(seconds=AI_EXECUTION_STALE_TIMEOUT_SECONDS)
    UiAIExecutionRecord.objects.filter(
        status="running",
        heartbeat_at__lt=stale_before,
    ).update(
        status="pending",
        worker_token=None,
        heartbeat_at=None,
        end_time=None,
        duration=None,
        error_message=None,
    )


def _claim_next_ai_execution() -> tuple[int, str] | None:
    close_old_connections()
    with transaction.atomic():
        record = (
            UiAIExecutionRecord.objects.select_for_update()
            .filter(status="pending")
            .order_by("start_time", "id")
            .first()
        )
        if record is None:
            return None

        worker_token = f"{AI_EXECUTION_PROCESS_TOKEN}:{record.id}:{uuid.uuid4().hex[:8]}"
        record.status = "running"
        record.worker_token = worker_token
        record.heartbeat_at = timezone.now()
        record.end_time = None
        record.duration = None
        record.error_message = None
        record.save(update_fields=["status", "worker_token", "heartbeat_at", "end_time", "duration", "error_message"])
        return record.id, worker_token


def _spawn_ai_execution_worker(record_id: int, worker_token: str) -> None:
    with _ACTIVE_EXECUTION_LOCK:
        existing = _ACTIVE_EXECUTION_THREADS.get(record_id)
        if existing and existing.is_alive():
            return

        thread = threading.Thread(
            target=run_ai_execution,
            args=(record_id, worker_token),
            daemon=True,
            name=f"ui-ai-exec-{record_id}",
        )
        _ACTIVE_EXECUTION_THREADS[record_id] = thread
        thread.start()


def _release_ai_execution_worker(record_id: int) -> None:
    with _ACTIVE_EXECUTION_LOCK:
        _ACTIVE_EXECUTION_THREADS.pop(record_id, None)


def _claim_ai_execution_for_worker(record_id: int, worker_token: str) -> bool:
    close_old_connections()
    with transaction.atomic():
        record = (
            UiAIExecutionRecord.objects.select_for_update()
            .filter(pk=record_id)
            .first()
        )
        if record is None:
            return False

        if record.status == "running":
            return record.worker_token == worker_token

        if record.status != "pending":
            return False

        record.status = "running"
        record.worker_token = worker_token
        record.heartbeat_at = timezone.now()
        record.end_time = None
        record.duration = None
        record.error_message = None
        record.save(update_fields=["status", "worker_token", "heartbeat_at", "end_time", "duration", "error_message"])
        return True


def start_ai_execution(record_id: int) -> None:
    close_old_connections()
    UiAIExecutionRecord.objects.filter(pk=record_id).update(
        status="pending",
        queue_task_id=None,
        worker_token=None,
        heartbeat_at=None,
        end_time=None,
        duration=None,
        error_message=None,
    )
    if UI_AI_CELERY_ENABLED:
        try:
            from .tasks import execute_ui_ai_record

            async_result = execute_ui_ai_record.apply_async(args=[record_id], queue=UI_AI_CELERY_QUEUE)
            UiAIExecutionRecord.objects.filter(pk=record_id).update(queue_task_id=async_result.id)
            logger.info("Queued UI AI execution %s to Celery task %s", record_id, async_result.id)
            return
        except Exception as exc:
            logger.warning("Failed to queue UI AI execution %s to Celery, fallback to local dispatcher: %s", record_id, exc)

    _ensure_ai_dispatcher_started()
    _AI_DISPATCHER_WAKE_EVENT.set()


def request_stop_ai_execution(record_id: int) -> bool:
    AI_STOP_SIGNALS[record_id] = True
    record = UiAIExecutionRecord.objects.filter(
        id=record_id,
        status__in=["pending", "running"],
    ).first()
    if record is None:
        AI_STOP_SIGNALS.pop(record_id, None)
        return False

    if record.queue_task_id:
        try:
            from flytest_django.celery import app as celery_app

            celery_app.control.revoke(record.queue_task_id, terminate=False)
        except Exception as exc:
            logger.warning("Failed to revoke Celery task %s for UI AI execution %s: %s", record.queue_task_id, record_id, exc)

    record.status = "stopped"
    record.end_time = timezone.now()
    if record.start_time:
        record.duration = round((record.end_time - record.start_time).total_seconds(), 2)
    stop_message = "[System] 已发送停止信号，等待当前步骤安全结束。"
    current_logs = (record.logs or "").rstrip()
    if stop_message not in current_logs:
        record.logs = f"{current_logs}\n{stop_message}".strip()
    record.save(update_fields=["status", "end_time", "duration", "logs"])
    return True


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return round(number, 2)


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds < 60:
        return f"{seconds:.2f}s"

    minutes, remain = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {remain}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {remain}s"


def _normalize_task_status(status: Any) -> str:
    value = str(status or "pending").strip().lower()
    aliases = {
        "passed": "completed",
        "success": "completed",
        "done": "completed",
        "running": "in_progress",
        "processing": "in_progress",
        "cancelled": "stopped",
    }
    normalized = aliases.get(value, value)
    return normalized if normalized in {"completed", "pending", "failed", "skipped", "in_progress", "stopped"} else "pending"


def _normalize_step_status(status: Any) -> str:
    value = str(status or "pending").strip().lower()
    aliases = {
        "success": "passed",
        "completed": "passed",
        "done": "passed",
        "error": "failed",
        "cancelled": "stopped",
    }
    normalized = aliases.get(value, value)
    return normalized if normalized in {"passed", "failed", "stopped", "pending", "running"} else "pending"


def _task_status_label(status: str) -> str:
    return {
        "completed": "已完成",
        "pending": "待执行",
        "failed": "失败",
        "skipped": "已跳过",
        "in_progress": "执行中",
        "stopped": "已停止",
    }.get(status, status)


def _calculate_task_statistics(planned_tasks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    statistics = {
        "total": len(planned_tasks),
        "completed": 0,
        "pending": 0,
        "failed": 0,
        "skipped": 0,
        "in_progress": 0,
        "stopped": 0,
        "completion_rate": 0.0,
        "success_rate": 0.0,
    }

    for task in planned_tasks:
        status = _normalize_task_status(task.get("status"))
        statistics[status] = statistics.get(status, 0) + 1

    total = statistics["total"]
    attempted = statistics["completed"] + statistics["failed"]
    statistics["completion_rate"] = round((statistics["completed"] / total) * 100, 2) if total else 0.0
    statistics["success_rate"] = round((statistics["completed"] / attempted) * 100, 2) if attempted else 0.0
    return statistics


def _build_detailed_steps(steps_completed: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    detailed_steps: list[dict[str, Any]] = []
    for index, step in enumerate(steps_completed, start=1):
        step_number = step.get("step") or step.get("step_number") or index
        title = step.get("title") or step.get("action") or f"步骤 {step_number}"
        description = step.get("description") or step.get("message") or ""
        duration = (
            _coerce_float(step.get("duration"))
            or _coerce_float(step.get("elapsed_seconds"))
            or _coerce_float(step.get("cost"))
            or _coerce_float(step.get("estimated_duration"))
        )
        detailed_steps.append(
            {
                "step_number": step_number,
                "title": title,
                "status": _normalize_step_status(step.get("status")),
                "action": step.get("action") or title,
                "description": description,
                "expected_result": step.get("expected_result") or "",
                "thinking": step.get("thinking") or step.get("reasoning") or "",
                "element": step.get("element") or step.get("selector") or step.get("locator") or "",
                "message": step.get("message") or "",
                "completed_at": step.get("completed_at"),
                "duration": duration,
                "browser_step_count": step.get("browser_step_count"),
                "screenshots": list(step.get("screenshots") or []),
            }
        )
    return detailed_steps


def _resolve_runtime_terminal_status(runtime_state: ExecutionRuntimeState) -> str:
    task_statuses = {
        _normalize_task_status(task.get("status"))
        for task in runtime_state.planned_tasks
    }
    step_statuses = {
        _normalize_step_status(step.get("status"))
        for step in runtime_state.steps_completed
    }

    if "failed" in task_statuses or "failed" in step_statuses:
        return "failed"
    if "stopped" in task_statuses or "stopped" in step_statuses:
        return "stopped"
    if any(status in {"pending", "in_progress"} for status in task_statuses):
        return "failed"
    return "passed"


def _derive_runtime_error_message(runtime_state: ExecutionRuntimeState) -> str | None:
    for step in runtime_state.steps_completed:
        if _normalize_step_status(step.get("status")) != "failed":
            continue
        message = step.get("message") or step.get("description") or step.get("title")
        if message:
            return str(message)

    for task in runtime_state.planned_tasks:
        if _normalize_task_status(task.get("status")) != "failed":
            continue
        message = (
            task.get("error_message")
            or task.get("result")
            or task.get("message")
            or task.get("description")
            or task.get("title")
        )
        if message:
            return str(message)

    return None


def _build_timeline(planned_tasks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for index, task in enumerate(planned_tasks, start=1):
        status = _normalize_task_status(task.get("status"))
        timeline.append(
            {
                "id": task.get("id") or index,
                "title": task.get("title") or f"任务 {index}",
                "description": task.get("description") or task.get("title") or "",
                "status": status,
                "status_display": _task_status_label(status),
                "expected_result": task.get("expected_result") or "",
            }
        )
    return timeline


def _analyze_action_distribution(
    planned_tasks: Sequence[dict[str, Any]],
    detailed_steps: Sequence[dict[str, Any]],
    logs: str,
) -> list[dict[str, Any]]:
    action_keywords = {
        "导航": ("open", "navigate", "visit", "goto", "打开", "访问", "进入", "跳转"),
        "点击": ("click", "tap", "press", "点击", "单击", "提交"),
        "输入": ("input", "fill", "type", "enter", "输入", "填写"),
        "断言": ("assert", "verify", "check", "expect", "校验", "断言", "检查"),
        "等待": ("wait", "sleep", "等待"),
        "截图": ("screenshot", "capture", "截图", "拍照"),
    }
    counters = {name: 0 for name in action_keywords}
    counters["其他"] = 0

    texts: list[str] = []
    texts.extend(
        f"{task.get('title', '')} {task.get('description', '')} {task.get('expected_result', '')}".strip()
        for task in planned_tasks
    )
    texts.extend(
        f"{step.get('title', '')} {step.get('action', '')} {step.get('description', '')} {step.get('message', '')}".strip()
        for step in detailed_steps
    )

    if not texts and logs:
        texts.append(logs)

    for text in texts:
        normalized = text.lower()
        matched = False
        for name, keywords in action_keywords.items():
            if any(keyword in normalized for keyword in keywords):
                counters[name] += 1
                matched = True
        if not matched and text:
            counters["其他"] += 1

    return [{"action": name, "count": count} for name, count in counters.items() if count > 0]


def _build_step_performance(
    detailed_steps: Sequence[dict[str, Any]],
    total_duration: float | None,
) -> list[dict[str, Any]]:
    durations = [step["duration"] for step in detailed_steps if step.get("duration") is not None]
    fallback_duration = None
    if not durations and detailed_steps and total_duration:
        fallback_duration = round(total_duration / len(detailed_steps), 2)

    performance: list[dict[str, Any]] = []
    for step in detailed_steps:
        duration = step.get("duration")
        if duration is None:
            duration = fallback_duration
        performance.append(
            {
                "step_number": step["step_number"],
                "title": step.get("title") or step.get("action") or f"步骤 {step['step_number']}",
                "action": step.get("action") or step.get("title") or "",
                "status": step.get("status") or "pending",
                "duration": duration,
            }
        )
    return performance


def _calculate_performance_metrics(step_performance: Sequence[dict[str, Any]], total_duration: float | None) -> dict[str, Any]:
    durations = [step["duration"] for step in step_performance if step.get("duration") is not None]
    measured_total = round(sum(durations), 2) if durations else round(total_duration or 0, 2)
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    return {
        "total_steps": len(step_performance),
        "passed_steps": sum(1 for step in step_performance if step.get("status") == "passed"),
        "failed_steps": sum(1 for step in step_performance if step.get("status") == "failed"),
        "pass_rate": round(
            (
                sum(1 for step in step_performance if step.get("status") == "passed")
                / len(step_performance)
            ) * 100,
            2,
        ) if step_performance else 0.0,
        "total_duration": measured_total,
        "avg_step_duration": avg_duration,
        "max_step_duration": round(max(durations), 2) if durations else 0.0,
        "min_step_duration": round(min(durations), 2) if durations else 0.0,
    }


def _identify_bottlenecks(step_performance: Sequence[dict[str, Any]], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    avg_duration = metrics.get("avg_step_duration") or 0
    if avg_duration <= 0:
        return []

    bottlenecks: list[dict[str, Any]] = []
    for step in step_performance:
        duration = step.get("duration")
        if duration is None or duration <= avg_duration * 1.2:
            continue
        bottlenecks.append(
            {
                "step_number": step["step_number"],
                "action": step.get("action") or step.get("title") or f"步骤 {step['step_number']}",
                "duration": round(duration, 2),
                "slower_than_avg_by": round(((duration - avg_duration) / avg_duration) * 100, 2),
            }
        )

    return sorted(bottlenecks, key=lambda item: item["duration"], reverse=True)[:5]


def _collect_report_errors(
    record: UiAIExecutionRecord,
    planned_tasks: Sequence[dict[str, Any]],
    detailed_steps: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    if record.error_message:
        errors.append({"type": "error", "message": record.error_message})

    for task in planned_tasks:
        if _normalize_task_status(task.get("status")) != "failed":
            continue
        message = task.get("message") or task.get("description") or task.get("title") or "任务执行失败"
        errors.append({"type": "error", "message": message})

    for step in detailed_steps:
        if step.get("status") != "failed":
            continue
        message = step.get("message") or step.get("description") or step.get("title") or "步骤执行失败"
        errors.append(
            {
                "type": "error",
                "message": message,
                "step_number": step.get("step_number"),
            }
        )

    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in errors:
        key = (item.get("type"), item.get("message"), item.get("step_number"))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)
    return deduplicated


def _build_recommendations(
    record: UiAIExecutionRecord,
    metrics: dict[str, Any],
    bottlenecks: Sequence[dict[str, Any]],
    errors: Sequence[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []

    if errors:
        recommendations.append("存在失败任务或失败步骤，建议优先检查页面元素定位、断言条件以及测试数据准备。")
    if bottlenecks:
        recommendations.append("检测到慢步骤，建议减少不必要等待、复用登录态，并检查目标页面网络或接口响应时间。")
    if metrics.get("avg_step_duration", 0) > 5:
        recommendations.append("平均步骤耗时偏高，建议拆分大步骤并为关键节点补充更细粒度的步骤记录。")
    if record.execution_mode == "vision":
        recommendations.append("视觉模式下建议保持页面分辨率稳定，并尽量减少动画、弹层和长时间过渡效果。")
    if record.execution_backend == "planning":
        recommendations.append("当前记录使用规划回退模式，如需真实浏览器自动化，请补齐 browser-use、Playwright 和可用的 LLM 配置。")
    if not recommendations:
        recommendations.append("本次执行未发现明显异常，可继续扩大回归范围并沉淀为稳定回归场景。")

    return recommendations


def build_ai_execution_report(record: UiAIExecutionRecord, report_type: str = "summary") -> dict[str, Any]:
    report_type = (report_type or "summary").strip().lower()
    if report_type not in {"summary", "detailed", "performance"}:
        report_type = "summary"

    planned_tasks = record.planned_tasks or []
    steps_completed = record.steps_completed or []
    detailed_steps = _build_detailed_steps(steps_completed)
    task_statistics = _calculate_task_statistics(planned_tasks)
    action_distribution = _analyze_action_distribution(planned_tasks, detailed_steps, record.logs or "")
    step_performance = _build_step_performance(detailed_steps, record.duration)
    performance_metrics = _calculate_performance_metrics(step_performance, record.duration)
    bottlenecks = _identify_bottlenecks(step_performance, performance_metrics)
    errors = _collect_report_errors(record, planned_tasks, detailed_steps)

    completed_tasks = [task for task in planned_tasks if _normalize_task_status(task.get("status")) == "completed"]
    failed_tasks = [task for task in planned_tasks if _normalize_task_status(task.get("status")) == "failed"]
    passed_steps = [step for step in detailed_steps if step.get("status") == "passed"]
    failed_steps = [step for step in detailed_steps if step.get("status") == "failed"]

    report = {
        "id": record.id,
        "report_type": report_type,
        "case_name": record.case_name,
        "status": record.status,
        "status_display": record.get_status_display(),
        "execution_mode": record.execution_mode,
        "execution_mode_display": record.get_execution_mode_display(),
        "execution_backend": record.execution_backend,
        "execution_backend_display": record.get_execution_backend_display(),
        "model_config_name": record.model_config_name,
        "task_description": record.task_description,
        "planned_task_count": len(planned_tasks),
        "completed_task_count": len(completed_tasks),
        "failed_task_count": len(failed_tasks),
        "step_count": len(detailed_steps),
        "passed_step_count": len(passed_steps),
        "failed_step_count": len(failed_steps),
        "steps_completed": steps_completed,
        "planned_tasks": planned_tasks,
        "screenshots_sequence": record.screenshots_sequence or [],
        "gif_path": record.gif_path,
        "logs": record.logs or "",
        "error_message": record.error_message,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "duration": record.duration,
        "statistics": task_statistics,
    }

    if report_type == "summary":
        report.update(
            {
                "overview": {
                    "status": record.get_status_display(),
                    "status_color": {
                        "passed": "success",
                        "failed": "danger",
                        "running": "warning",
                        "pending": "info",
                        "stopped": "warning",
                    }.get(record.status, "info"),
                    "duration": record.duration or 0,
                    "duration_formatted": _format_duration(record.duration),
                    "avg_step_time": performance_metrics["avg_step_duration"],
                    "total_steps": len(detailed_steps),
                    "total_actions": sum(item["count"] for item in action_distribution),
                    "completion_rate": task_statistics["completion_rate"],
                },
                "timeline": _build_timeline(planned_tasks),
                "metrics": performance_metrics,
                "action_distribution": action_distribution,
            }
        )
    elif report_type == "detailed":
        report.update(
            {
                "detailed_steps": detailed_steps,
                "errors": errors,
            }
        )
    else:
        report.update(
            {
                "metrics": performance_metrics,
                "action_distribution": action_distribution,
                "bottlenecks": bottlenecks,
                "recommendations": _build_recommendations(record, performance_metrics, bottlenecks, errors),
            }
        )

    return report


def run_ai_execution(record_id: int, worker_token: str | None = None) -> None:
    close_old_connections()

    if worker_token and not _claim_ai_execution_for_worker(record_id, worker_token):
        logger.info("Skip UI AI execution %s because it cannot be claimed by worker %s", record_id, worker_token)
        _release_ai_execution_worker(record_id)
        return

    try:
        record = UiAIExecutionRecord.objects.select_related("project", "ai_case").get(pk=record_id)
    except UiAIExecutionRecord.DoesNotExist:
        logger.warning("AI execution record %s no longer exists", record_id)
        _release_ai_execution_worker(record_id)
        return

    started_at = time.time()
    active_config = _get_active_llm_config(getattr(record, "executed_by", None))
    env_config = _get_default_env_config(record.project_id)
    runtime_state = ExecutionRuntimeState(
        record_id=record.id,
        case_name=record.case_name,
        logs=record.logs or "",
        planned_tasks=list(record.planned_tasks or []),
        steps_completed=list(record.steps_completed or []),
        screenshots_sequence=list(record.screenshots_sequence or []),
        gif_path=record.gif_path,
        model_config_name=record.model_config_name,
    )

    try:
        AI_STOP_SIGNALS[record_id] = False
        runtime_state.execution_backend = _detect_execution_backend()
        runtime_state.model_config_name = active_config.config_name if active_config else None
        runtime_state.append_log(f"开始执行 AI 智能任务：{record.case_name}")

        if env_config and env_config.base_url:
            runtime_state.append_log(f"使用默认环境：{env_config.name} ({env_config.base_url})")

        if runtime_state.execution_backend == "planning":
            runtime_state.append_log("当前环境缺少 browser-use 或 Playwright，已切换到规划回退模式。")
        else:
            runtime_state.append_log("已检测到 browser-use 执行环境，将使用真实浏览器智能执行。")
        if not record.enable_gif:
            runtime_state.append_log("当前任务已关闭 GIF 录制，将只保留必要日志和截图。")

        if runtime_state.execution_backend == "browser_use" and not active_config:
            raise ValueError("AI 智能模式需要先启用一个 LLM 配置。")

        if record.execution_mode == "vision":
            if not active_config:
                raise ValueError("视觉模式需要先启用一个支持视觉能力的 LLM 配置。")
            if not active_config.supports_vision:
                raise ValueError("当前激活的 LLM 配置不支持视觉模式，请切换到支持图片输入的模型。")

        plan_result = _build_task_plan(record, active_config, runtime_state.execution_backend)
        runtime_state.planned_tasks = plan_result["tasks"]
        if plan_result.get("model_config_name"):
            runtime_state.model_config_name = plan_result["model_config_name"]
        if plan_result.get("warning"):
            runtime_state.append_log(f"任务规划回退到规则拆解：{plan_result['warning']}")
        else:
            runtime_state.append_log("AI 任务规划完成，开始执行。")

        _update_runtime_state_sync(runtime_state)

        if runtime_state.execution_backend == "browser_use":
            asyncio.run(
                _run_browser_use_execution(
                    record=record,
                    runtime_state=runtime_state,
                    active_config=active_config,
                    env_config=env_config,
                    project_context=_build_project_context(record.project_id),
                )
            )
        else:
            _run_planning_fallback(record, runtime_state, plan_result)

        final_status = _resolve_runtime_terminal_status(runtime_state)
        record.status = final_status
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        if final_status == "failed":
            record.error_message = _derive_runtime_error_message(runtime_state) or "执行完成，但检测到失败任务。"
            _finalize_tasks_for_terminal_status(runtime_state, "failed", record.error_message)
        elif final_status == "stopped":
            _finalize_tasks_for_terminal_status(runtime_state, "stopped", "任务已由用户停止")
        _apply_runtime_state(record, runtime_state)
        if final_status == "failed":
            runtime_state.append_log(f"任务执行失败：{record.error_message}")
            _append_task_summary_log(runtime_state, prefix="失败总结")
        elif final_status == "stopped":
            runtime_state.append_log("任务已停止。")
            _append_task_summary_log(runtime_state, prefix="停止总结")
        else:
            runtime_state.append_log("AI 智能模式执行完成。")
            _append_task_summary_log(runtime_state, prefix="执行总结")
        record.logs = runtime_state.logs
        update_fields = [
            "status",
            "end_time",
            "duration",
            "logs",
            "planned_tasks",
            "steps_completed",
            "screenshots_sequence",
            "gif_path",
            "model_config_name",
            "execution_backend",
        ]
        if final_status == "failed":
            update_fields.append("error_message")
        _save_record(record, update_fields)
    except AIExecutionStopped:
        record.status = "stopped"
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        _finalize_tasks_for_terminal_status(runtime_state, "stopped", "任务已由用户停止")
        _apply_runtime_state(record, runtime_state)
        runtime_state.append_log("任务已停止。")
        _append_task_summary_log(runtime_state, prefix="停止总结")
        record.logs = runtime_state.logs
        _save_record(
            record,
            [
                "status",
                "end_time",
                "duration",
                "logs",
                "planned_tasks",
                "steps_completed",
                "screenshots_sequence",
                "gif_path",
                "model_config_name",
                "execution_backend",
                "worker_token",
                "heartbeat_at",
            ],
        )
    except Exception as exc:
        logger.exception("AI execution failed for record %s", record_id)
        record.status = "failed"
        record.error_message = str(exc)
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        _finalize_tasks_for_terminal_status(runtime_state, "failed", str(exc))
        _apply_runtime_state(record, runtime_state)
        runtime_state.append_log(f"任务执行失败：{exc}")
        _append_task_summary_log(runtime_state, prefix="失败总结")
        record.logs = runtime_state.logs
        _save_record(
            record,
            [
                "status",
                "error_message",
                "end_time",
                "duration",
                "logs",
                "planned_tasks",
                "steps_completed",
                "screenshots_sequence",
                "gif_path",
                "model_config_name",
                "execution_backend",
                "worker_token",
                "heartbeat_at",
            ],
        )
    finally:
        UiAIExecutionRecord.objects.filter(pk=record_id).update(
            worker_token=None,
            heartbeat_at=timezone.now(),
        )
        _release_ai_execution_worker(record_id)
        AI_STOP_SIGNALS.pop(record_id, None)
        close_old_connections()


def _run_planning_fallback(
    record: UiAIExecutionRecord,
    runtime_state: ExecutionRuntimeState,
    plan_result: dict[str, Any],
) -> None:
    for index, task in enumerate(runtime_state.planned_tasks):
        _ensure_not_stopped(record.id)
        _mark_task_running(runtime_state, index)
        runtime_state.append_log(
            f"开始执行任务 {index + 1}/{len(runtime_state.planned_tasks)}：{task.get('title') or task.get('description')}"
        )
        _update_runtime_state_sync(runtime_state)

        step_started_at = time.time()
        time.sleep(0.15)
        _ensure_not_stopped(record.id)

        step_result = _build_fallback_step_result(
            index=index,
            task=task,
            execution_mode=record.execution_mode,
            execution_backend=runtime_state.execution_backend,
            used_ai=plan_result.get("used_ai", False),
            duration=round(time.time() - step_started_at, 2),
        )
        runtime_state.steps_completed.append(step_result)
        _mark_task_completed(runtime_state, index, step_result["message"])
        runtime_state.append_log(f"任务完成：{task.get('title') or task.get('description')}")
        _update_runtime_state_sync(runtime_state)


async def _run_browser_use_execution(
    record: UiAIExecutionRecord,
    runtime_state: ExecutionRuntimeState,
    active_config: LLMConfig | None,
    env_config: UiEnvironmentConfig | None,
    project_context: dict[str, Any],
) -> None:
    if active_config is None:
        raise ValueError("AI 智能模式需要先启用一个 LLM 配置。")

    _apply_browser_use_runtime_patches()

    from browser_use import Agent
    from browser_use.browser.session import BrowserSession

    llm = _create_browser_use_llm(active_config)
    if llm is None:
        raise ValueError("当前激活的 LLM 配置初始化失败，无法执行 browser-use 智能模式。")

    artifact_dir = _ensure_artifact_dir(record.id)
    browser_session = BrowserSession(
        browser_profile=_build_browser_profile(env_config=env_config, artifact_dir=artifact_dir)
    )

    try:
        for index, task in enumerate(runtime_state.planned_tasks):
            await _ensure_not_stopped_async(record.id)
            _mark_task_running(runtime_state, index)
            runtime_state.append_log(
                f"开始真实浏览器执行任务 {index + 1}/{len(runtime_state.planned_tasks)}：{task.get('title') or task.get('description')}"
            )
            await _persist_runtime_state(runtime_state, force=True)

            task_artifact_dir = artifact_dir / f"task-{index + 1}"
            task_artifact_dir.mkdir(parents=True, exist_ok=True)
            gif_target = task_artifact_dir / "agent-history.gif"
            conversation_target = task_artifact_dir / "conversation.json"
            per_task_screenshots: list[str] = []
            auth_failure_tracker = {"count": 0, "message": None}

            async def register_new_step_callback(browser_state: Any, model_output: Any, step_number: int) -> None:
                runtime_state.append_log(
                    _format_browser_step_log(
                        task_title=task.get("title") or task.get("description") or f"任务 {index + 1}",
                        step_number=step_number,
                        browser_state=browser_state,
                        model_output=model_output,
                    )
                )

                if _is_login_related_task(task):
                    signal_text = _collect_browser_failure_signals(browser_state, model_output)
                    if _contains_auth_failure_signal(signal_text):
                        auth_failure_tracker["count"] += 1
                        if auth_failure_tracker["count"] >= 3 and auth_failure_tracker["message"] is None:
                            auth_failure_tracker["message"] = (
                                "检测到登录或认证连续失败 3 次，已停止当前浏览器任务，请检查账号、密码或目标环境权限配置。"
                            )
                            runtime_state.append_log(auth_failure_tracker["message"])
                    elif auth_failure_tracker["count"]:
                        auth_failure_tracker["count"] = 0

                await _persist_runtime_state(runtime_state)

            async def should_stop_callback() -> bool:
                if auth_failure_tracker["message"]:
                    return True
                return await _should_stop_async(record.id)

            agent = Agent(
                task=_build_browser_task_prompt(
                    full_task=record.task_description,
                    current_task=task,
                    task_index=index,
                    planned_tasks=runtime_state.planned_tasks,
                    project_context=project_context,
                    env_config=env_config,
                    execution_mode=record.execution_mode,
                    model_name=getattr(active_config, "name", "") if active_config else "",
                ),
                llm=llm,
                browser_session=browser_session,
                page_extraction_llm=llm,
                use_vision=record.execution_mode == "vision",
                use_judge=False,
                max_actions_per_step=_resolve_max_actions_per_step(task, record.execution_mode),
                max_failures=2,
                llm_timeout=60,
                step_timeout=_resolve_step_timeout(env_config),
                generate_gif=str(gif_target) if record.enable_gif else False,
                save_conversation_path=conversation_target,
                include_recent_events=True,
                register_new_step_callback=register_new_step_callback,
                register_should_stop_callback=should_stop_callback,
            )

            history = await agent.run(max_steps=_resolve_max_steps(task))
            await _ensure_not_stopped_async(record.id)

            copied_screenshots = _copy_screenshots_to_media(
                history.screenshot_paths(return_none_if_not_screenshot=False),
                task_artifact_dir / "screenshots",
            )
            for screenshot_path in copied_screenshots:
                if screenshot_path not in runtime_state.screenshots_sequence:
                    runtime_state.screenshots_sequence.append(screenshot_path)
                    per_task_screenshots.append(screenshot_path)

            if record.enable_gif and gif_target.exists():
                runtime_state.gif_path = _to_media_relative_path(gif_target)

            errors = [error for error in history.errors() if error]
            success = history.is_successful()
            final_result = (history.final_result() or "").strip()

            if auth_failure_tracker["message"]:
                error_message = auth_failure_tracker["message"]
                _mark_task_failed(runtime_state, index, error_message)
                runtime_state.steps_completed.append(
                    _build_browser_step_result(
                        index=index,
                        task=task,
                        execution_mode=record.execution_mode,
                        execution_backend=runtime_state.execution_backend,
                        status="failed",
                        message=error_message,
                        browser_steps=history.number_of_steps(),
                        screenshots=per_task_screenshots,
                    )
                )
                await _persist_runtime_state(runtime_state, force=True)
                raise RuntimeError(error_message)

            if success is False:
                error_message = errors[-1] if errors else (final_result or "智能浏览器任务未成功完成。")
                _mark_task_failed(runtime_state, index, error_message)
                runtime_state.steps_completed.append(
                    _build_browser_step_result(
                        index=index,
                        task=task,
                        execution_mode=record.execution_mode,
                        execution_backend=runtime_state.execution_backend,
                        status="failed",
                        message=error_message,
                        browser_steps=history.number_of_steps(),
                        screenshots=per_task_screenshots,
                    )
                )
                await _persist_runtime_state(runtime_state, force=True)
                raise RuntimeError(error_message)

            if success is None and not final_result:
                error_message = errors[-1] if errors else "智能浏览器任务未在限定步骤内完成。"
                _mark_task_failed(runtime_state, index, error_message)
                runtime_state.steps_completed.append(
                    _build_browser_step_result(
                        index=index,
                        task=task,
                        execution_mode=record.execution_mode,
                        execution_backend=runtime_state.execution_backend,
                        status="failed",
                        message=error_message,
                        browser_steps=history.number_of_steps(),
                        screenshots=per_task_screenshots,
                    )
                )
                await _persist_runtime_state(runtime_state, force=True)
                raise RuntimeError(error_message)

            completion_message = final_result or f"任务已完成，共执行 {history.number_of_steps()} 个浏览器步骤。"
            _mark_task_completed(runtime_state, index, completion_message)
            runtime_state.steps_completed.append(
                _build_browser_step_result(
                    index=index,
                    task=task,
                    execution_mode=record.execution_mode,
                    execution_backend=runtime_state.execution_backend,
                    status="passed",
                    message=completion_message,
                    browser_steps=history.number_of_steps(),
                    screenshots=per_task_screenshots,
                )
            )
            runtime_state.append_log(f"任务完成：{task.get('title') or task.get('description')}")
            await _persist_runtime_state(runtime_state, force=True)
    finally:
        try:
            await browser_session.stop()
        except Exception as exc:
            logger.warning("Failed to stop browser session for record %s: %s", record.id, exc)


def _get_active_llm_config(user=None) -> LLMConfig | None:
    return get_user_active_llm_config(user)


def _get_default_env_config(project_id: int) -> UiEnvironmentConfig | None:
    env_config = (
        UiEnvironmentConfig.objects.filter(project_id=project_id)
        .order_by("-is_default", "id")
        .first()
    )
    if env_config is not None:
        return env_config

    fallback_base_url = (
        getattr(settings, "UI_AUTOMATION_DEFAULT_BASE_URL", "")
        or "http://localhost:5173"
    )

    return UiEnvironmentConfig.objects.create(
        project_id=project_id,
        name="默认环境",
        base_url=fallback_base_url,
        browser="chromium",
        headless=True,
        viewport_width=1280,
        viewport_height=720,
        timeout=30000,
        is_default=True,
        creator_id=None,
    )


def _detect_execution_backend() -> str:
    has_browser_use = importlib.util.find_spec("browser_use") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    return "browser_use" if has_browser_use and has_playwright else "planning"


def get_ai_runtime_capabilities(project_id: int | None = None, user=None) -> dict[str, Any]:
    active_config = _get_active_llm_config(user)
    env_config = _get_default_env_config(project_id) if project_id else None
    has_browser_use = importlib.util.find_spec("browser_use") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    browser_executable = _find_browser_executable()
    execution_backend = "browser_use" if has_browser_use and has_playwright else "planning"
    llm_configured = active_config is not None
    supports_vision = bool(getattr(active_config, "supports_vision", False))
    browser_mode_ready = execution_backend == "browser_use" and llm_configured
    text_mode_ready = execution_backend == "planning" or browser_mode_ready
    vision_mode_ready = browser_mode_ready and supports_vision

    issues: list[str] = []
    recommendations: list[str] = []

    if execution_backend != "browser_use":
        issues.append("未检测到完整的 browser-use / Playwright 环境，当前会回退到 AI 规划执行模式。")
        recommendations.append("如需真实浏览器智能执行，请补齐 browser-use 与 Playwright 依赖。")
    elif not browser_executable:
        issues.append("已检测到 browser-use 与 Playwright，但未找到本机浏览器可执行文件。")
        recommendations.append("请安装 Chrome 或 Edge，确保真实浏览器执行链路可用。")

    if not llm_configured:
        issues.append("当前没有激活的 LLM 配置。")
        recommendations.append("请先在大模型配置中启用一个可用模型，避免真实浏览器模式直接失败。")
    elif not supports_vision:
        issues.append("当前激活模型不支持视觉模式。")
        recommendations.append("如需视觉模式，请切换到支持图片输入的模型配置。")

    if project_id and env_config is None:
        issues.append("当前项目未配置默认环境。")
        recommendations.append("建议为项目配置默认环境，补齐基础 URL、浏览器和超时设置。")

    if not recommendations:
        recommendations.append("当前 AI 智能模式核心能力已就绪，可直接发起真实浏览器任务。")

    if execution_backend == "browser_use":
        if browser_mode_ready:
            summary = "已启用真实浏览器智能执行链路。"
        else:
            summary = "已检测到真实浏览器执行链路，但缺少可用模型配置。"
    else:
        summary = "当前将使用 AI 规划回退模式执行。"

    capability_payload = {
        "execution_backend": execution_backend,
        "browser_use_available": has_browser_use,
        "playwright_available": has_playwright,
        "browser_executable_found": bool(browser_executable),
        "llm_configured": llm_configured,
        "text_mode_ready": text_mode_ready,
        "vision_mode_ready": vision_mode_ready,
        "supports_vision": supports_vision,
        "summary": summary,
        "issues": issues,
        "recommendations": recommendations,
        "default_environment": None,
        "model_config_name": None,
        "model_provider": None,
        "model_name": None,
    }

    if active_config is not None:
        capability_payload.update(
            {
                "model_config_name": active_config.config_name,
                "model_provider": active_config.get_provider_display(),
                "model_name": active_config.name,
            }
        )

    if env_config is not None:
        capability_payload["default_environment"] = {
            "id": env_config.id,
            "name": env_config.name,
            "base_url": env_config.base_url,
            "browser": env_config.browser,
            "headless": env_config.headless,
            "is_default": env_config.is_default,
        }

    return capability_payload


def _build_task_plan(
    record: UiAIExecutionRecord,
    active_config: LLMConfig | None,
    execution_backend: str,
) -> dict[str, Any]:
    project_context = _build_project_context(record.project_id)
    fallback_tasks = _fallback_plan(record.task_description, record.execution_mode, execution_backend)

    if not active_config:
        return {
            "tasks": fallback_tasks,
            "used_ai": False,
            "warning": "当前没有激活的 LLM 配置",
            "model_config_name": None,
        }

    llm = _create_llm(active_config)
    if llm is None:
        return {
            "tasks": fallback_tasks,
            "used_ai": False,
            "warning": "LLM 初始化失败",
            "model_config_name": active_config.config_name,
        }

    prompt = (
        "你是 FlyTest 的 UI 自动化任务规划器。"
        "请根据用户任务描述拆分出 3 到 8 个按顺序执行的自动化子任务。"
        "只返回 JSON，不要输出 Markdown。"
        'JSON 结构必须为 {"tasks":[{"id":1,"title":"任务标题","description":"任务说明","expected_result":"预期结果","status":"pending"}]}。'
        "每个任务都必须简洁、可执行、适合真实浏览器自动化。"
        f"执行模式：{record.execution_mode}。"
        f"执行后端：{execution_backend}。"
        f"项目上下文：{json.dumps(project_context, ensure_ascii=False)}。"
        f"用户任务：{record.task_description}"
    )

    try:
        response = llm.invoke(prompt)
        payload = _extract_json_payload(_read_llm_content(response))
        tasks = _normalize_tasks(payload.get("tasks"))
        if not tasks:
            raise ValueError("模型返回的任务列表为空")
        return {
            "tasks": tasks,
            "used_ai": True,
            "warning": None,
            "model_config_name": active_config.config_name,
        }
    except Exception as exc:
        logger.warning("Failed to build AI task plan with model %s: %s", active_config.config_name, exc)
        return {
            "tasks": fallback_tasks,
            "used_ai": False,
            "warning": str(exc),
            "model_config_name": active_config.config_name,
        }


def _build_project_context(project_id: int) -> dict[str, Any]:
    modules = list(UiModule.objects.filter(project_id=project_id).values_list("name", flat=True)[:12])
    pages = list(UiPage.objects.filter(project_id=project_id).values("name", "url")[:12])
    elements = list(
        UiElement.objects.filter(page__project_id=project_id).values("name", "locator_type")[:20]
    )

    return {
        "modules": modules,
        "pages": pages,
        "elements": elements,
    }


def _create_llm(active_config: LLMConfig) -> Any | None:
    try:
        from langgraph_integration.views import create_llm_instance

        return create_llm_instance(active_config, temperature=0.2)
    except Exception as exc:
        logger.warning("Unable to initialize LLM instance for %s: %s", active_config.config_name, exc)
        return None


def _create_browser_use_llm(active_config: LLMConfig) -> BrowserUseLangChainAdapter | None:
    llm = _create_llm(active_config)
    if llm is None:
        return None
    return BrowserUseLangChainAdapter(
        llm=llm,
        provider=(getattr(active_config, "provider", None) or "openai_compatible").strip(),
        model_name=active_config.name,
    )


def _read_llm_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
                elif item.get("type") == "image_url":
                    parts.append("[image]")
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content or "")


def _extract_json_payload(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    candidates = [text]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("无法解析模型返回的 JSON 结果")


def _normalize_tasks(tasks: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(tasks, list):
        return normalized

    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            continue

        title = str(task.get("title") or task.get("name") or task.get("description") or f"任务 {index}").strip()
        description = str(task.get("description") or title).strip()
        expected_result = str(task.get("expected_result") or task.get("expected") or "任务完成").strip()
        normalized.append(
            {
                "id": index,
                "title": title,
                "description": description,
                "expected_result": expected_result,
                "status": "pending",
            }
        )
    return normalized


def _fallback_plan(task_description: str, execution_mode: str, execution_backend: str) -> list[dict[str, Any]]:
    pieces = _split_task_description(task_description)
    if not pieces:
        pieces = [
            "确认测试目标和关键业务路径",
            "梳理页面入口与依赖数据",
            "设计执行步骤与断言点",
            "整理执行结果与风险说明",
        ]

    tasks: list[dict[str, Any]] = []
    for index, piece in enumerate(pieces[:8], start=1):
        tasks.append(
            {
                "id": index,
                "title": piece[:40],
                "description": piece,
                "expected_result": f"完成第 {index} 个 {execution_mode} 模式自动化任务（{execution_backend}）",
                "status": "pending",
            }
        )
    return tasks


def _split_task_description(task_description: str) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|[;；]+|(?<=[。！？.!?])", task_description or "")
    cleaned: list[str] = []
    for part in raw_parts:
        item = re.sub(r"^[\-\*\d\.\)\s]+", "", part or "").strip()
        if item:
            cleaned.append(item)
    return cleaned


def _build_fallback_step_result(
    index: int,
    task: dict[str, Any],
    execution_mode: str,
    execution_backend: str,
    used_ai: bool,
    duration: float,
) -> dict[str, Any]:
    title = task.get("title") or task.get("description") or f"任务 {index + 1}"
    description = task.get("description") or title
    suffix = "AI 规划回退执行" if execution_backend == "planning" else "智能浏览器执行"
    source = "AI 规划" if used_ai else "规则拆解"

    return {
        "step": index + 1,
        "title": title,
        "description": description,
        "expected_result": task.get("expected_result") or "",
        "status": "passed",
        "message": f"{title} 已完成，当前采用 {suffix}，步骤来源：{source}。",
        "execution_mode": execution_mode,
        "execution_backend": execution_backend,
        "duration": duration,
        "completed_at": timezone.now().isoformat(),
    }


def _build_browser_step_result(
    index: int,
    task: dict[str, Any],
    execution_mode: str,
    execution_backend: str,
    status: str,
    message: str,
    browser_steps: int,
    screenshots: list[str],
) -> dict[str, Any]:
    return {
        "step": index + 1,
        "title": task.get("title") or task.get("description") or f"任务 {index + 1}",
        "description": task.get("description") or "",
        "expected_result": task.get("expected_result") or "",
        "status": status,
        "message": message,
        "execution_mode": execution_mode,
        "execution_backend": execution_backend,
        "browser_step_count": browser_steps,
        "screenshots": screenshots,
        "completed_at": timezone.now().isoformat(),
    }


def _apply_runtime_state(record: UiAIExecutionRecord, runtime_state: ExecutionRuntimeState) -> None:
    record.logs = runtime_state.logs
    record.planned_tasks = runtime_state.planned_tasks
    record.steps_completed = runtime_state.steps_completed
    record.screenshots_sequence = runtime_state.screenshots_sequence
    record.gif_path = runtime_state.gif_path
    record.model_config_name = runtime_state.model_config_name
    record.execution_backend = runtime_state.execution_backend


def _save_record(record: UiAIExecutionRecord, update_fields: list[str]) -> None:
    close_old_connections()
    record.save(update_fields=update_fields)


def _update_runtime_state_sync(runtime_state: ExecutionRuntimeState) -> None:
    close_old_connections()
    UiAIExecutionRecord.objects.filter(pk=runtime_state.record_id).update(
        logs=runtime_state.logs,
        planned_tasks=runtime_state.planned_tasks,
        steps_completed=runtime_state.steps_completed,
        screenshots_sequence=runtime_state.screenshots_sequence,
        gif_path=runtime_state.gif_path,
        model_config_name=runtime_state.model_config_name,
        execution_backend=runtime_state.execution_backend,
        heartbeat_at=timezone.now(),
    )
    runtime_state.last_persist_at = time.monotonic()


async def _persist_runtime_state(runtime_state: ExecutionRuntimeState, force: bool = False) -> None:
    if not force and (time.monotonic() - runtime_state.last_persist_at) < 0.25:
        return
    await asyncio.to_thread(_update_runtime_state_sync, runtime_state)


def _mark_task_running(runtime_state: ExecutionRuntimeState, index: int) -> None:
    task = runtime_state.planned_tasks[index]
    task["status"] = "running"
    task["started_at"] = timezone.now().isoformat()
    task.pop("error_message", None)


def _mark_task_completed(runtime_state: ExecutionRuntimeState, index: int, message: str) -> None:
    task = runtime_state.planned_tasks[index]
    task["status"] = "completed"
    task["completed_at"] = timezone.now().isoformat()
    task["result"] = message


def _mark_task_failed(runtime_state: ExecutionRuntimeState, index: int, error_message: str) -> None:
    task = runtime_state.planned_tasks[index]
    task["status"] = "failed"
    task["completed_at"] = timezone.now().isoformat()
    task["result"] = error_message
    task["error_message"] = error_message


def _finalize_tasks_for_terminal_status(
    runtime_state: ExecutionRuntimeState,
    final_status: str,
    message: str | None = None,
) -> None:
    terminal_status = str(final_status or "").strip().lower()
    if terminal_status not in {"failed", "stopped"}:
        return

    timestamp = timezone.now().isoformat()
    for task in runtime_state.planned_tasks:
        normalized_status = _normalize_task_status(task.get("status"))

        if terminal_status == "stopped" and normalized_status in {"pending", "in_progress"}:
            task["status"] = "stopped"
            task["completed_at"] = task.get("completed_at") or timestamp
            task["result"] = task.get("result") or (message or "任务已停止")
            if normalized_status == "in_progress":
                task["error_message"] = task.get("error_message") or (message or "任务已停止")
            continue

        if terminal_status == "failed":
            if normalized_status == "in_progress":
                task["status"] = "failed"
                task["completed_at"] = task.get("completed_at") or timestamp
                task["result"] = task.get("result") or (message or "任务执行失败")
                task["error_message"] = task.get("error_message") or (message or "任务执行失败")
            elif normalized_status == "pending":
                task["status"] = "skipped"
                task["completed_at"] = task.get("completed_at") or timestamp
                task["result"] = task.get("result") or "因前置任务失败，后续任务已跳过"


def _append_task_summary_log(runtime_state: ExecutionRuntimeState, prefix: str = "任务总结") -> None:
    statistics = _calculate_task_statistics(runtime_state.planned_tasks)
    total = statistics.get("total", 0)
    if not total:
        return

    summary_parts = [f"共 {total} 项", f"完成 {statistics.get('completed', 0)} 项"]
    if statistics.get("failed"):
        summary_parts.append(f"失败 {statistics['failed']} 项")
    if statistics.get("skipped"):
        summary_parts.append(f"跳过 {statistics['skipped']} 项")
    pending_count = statistics.get("pending", 0) + statistics.get("in_progress", 0)
    if pending_count:
        summary_parts.append(f"未完成 {pending_count} 项")
    if statistics.get("stopped"):
        summary_parts.append(f"停止 {statistics['stopped']} 项")
    runtime_state.append_log(f"{prefix}：{'，'.join(summary_parts)}。")


def _ensure_not_stopped(record_id: int) -> None:
    if AI_STOP_SIGNALS.get(record_id):
        raise AIExecutionStopped()

    close_old_connections()
    if UiAIExecutionRecord.objects.filter(pk=record_id, status="stopped").exists():
        raise AIExecutionStopped()


async def _ensure_not_stopped_async(record_id: int) -> None:
    if await _should_stop_async(record_id):
        raise AIExecutionStopped()


async def _should_stop_async(record_id: int) -> bool:
    if AI_STOP_SIGNALS.get(record_id):
        return True
    return await asyncio.to_thread(_is_stopped_in_db, record_id)


def _is_stopped_in_db(record_id: int) -> bool:
    close_old_connections()
    return UiAIExecutionRecord.objects.filter(pk=record_id, status="stopped").exists()


def _ensure_artifact_dir(record_id: int) -> Path:
    artifact_dir = Path(settings.MEDIA_ROOT) / "ui_ai_execution" / str(record_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _to_media_relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _copy_screenshots_to_media(screenshot_paths: Sequence[str | None], target_dir: Path) -> list[str]:
    copied: list[str] = []
    if not screenshot_paths:
        return copied

    target_dir.mkdir(parents=True, exist_ok=True)
    for index, screenshot_path in enumerate(screenshot_paths, start=1):
        if not screenshot_path:
            continue

        source = Path(screenshot_path)
        if not source.exists():
            continue

        target = target_dir / f"step-{index}{source.suffix or '.png'}"
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        copied.append(_to_media_relative_path(target))
    return copied


def _build_browser_profile(env_config: UiEnvironmentConfig | None, artifact_dir: Path) -> Any:
    from browser_use.browser.profile import BrowserProfile

    browser_name = (getattr(env_config, "browser", None) or "chromium").lower()
    if browser_name not in {"chromium", "chrome", "msedge", "edge"}:
        logger.warning(
            "Environment browser '%s' is not supported by browser-use directly, fallback to chromium.",
            browser_name,
        )

    browser_path = _find_browser_executable()
    viewport_width = getattr(env_config, "viewport_width", 1440) or 1440
    viewport_height = getattr(env_config, "viewport_height", 900) or 900

    profile_kwargs: dict[str, Any] = {
        "headless": bool(getattr(env_config, "headless", True)),
        "viewport": {"width": viewport_width, "height": viewport_height},
        "downloads_path": str(artifact_dir / "downloads"),
        "user_data_dir": str(artifact_dir / "browser-profile"),
        "minimum_wait_page_load_time": 0.5,
        "wait_for_network_idle_page_load_time": 1.0,
        "wait_between_actions": 0.75,
        "highlight_elements": False,
        "dom_highlight_elements": False,
        "cross_origin_iframes": True,
        "keep_alive": True,
    }
    if browser_path:
        profile_kwargs["executable_path"] = browser_path

    return BrowserProfile(**profile_kwargs)


def _find_browser_executable() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _resolve_step_timeout(env_config: UiEnvironmentConfig | None) -> int:
    timeout_ms = getattr(env_config, "timeout", None) or 30000
    timeout_seconds = max(30, int(timeout_ms / 1000))
    return min(timeout_seconds, 180)


def _resolve_max_steps(task: dict[str, Any]) -> int:
    description = str(task.get("description") or "")
    return 20 if len(description) < 120 else 28


def _resolve_max_actions_per_step(task: dict[str, Any], execution_mode: str) -> int:
    description = str(task.get("description") or task.get("title") or "")
    base_limit = 4 if execution_mode == "vision" else 5
    if len(description) > 160:
        return min(base_limit + 1, 6)
    return base_limit


def _sanitize_browser_prompt_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"(https?://[^\s\u4e00-\u9fa5]+?)(?=[，。；：！？、])", r"\1 ", text)


def _contains_auth_failure_signal(text: str) -> bool:
    if not text:
        return False

    normalized = str(text).lower()
    keywords = [
        "登录失败",
        "login failed",
        "invalid credentials",
        "incorrect password",
        "用户名或密码",
        "账号或密码",
        "authentication failed",
        "auth failed",
        "bad credentials",
        "unauthorized",
        "401",
        "403",
        "access denied",
    ]
    return any(keyword in normalized for keyword in keywords)


def _is_login_related_task(task: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(task.get(key) or "")
        for key in ("title", "description", "expected_result")
    ).lower()
    return any(keyword in haystack for keyword in ("登录", "login", "sign in", "signin", "authenticate", "认证"))


def _collect_browser_failure_signals(browser_state: Any, model_output: Any) -> str:
    parts: list[str] = []

    for field_name in ("thinking", "evaluation_previous_goal", "memory", "next_goal"):
        value = getattr(model_output, field_name, None)
        if value:
            parts.append(str(value))

    recent_events = getattr(browser_state, "recent_events", None)
    if recent_events:
        parts.append(str(recent_events))

    for item in getattr(browser_state, "browser_errors", []) or []:
        if item:
            parts.append(str(item))

    for item in getattr(browser_state, "closed_popup_messages", []) or []:
        if item:
            parts.append(str(item))

    return " ".join(parts)


def _build_browser_task_prompt(
    full_task: str,
    current_task: dict[str, Any],
    task_index: int,
    planned_tasks: list[dict[str, Any]],
    project_context: dict[str, Any],
    env_config: UiEnvironmentConfig | None,
    execution_mode: str,
    model_name: str = "",
) -> str:
    completed_tasks = [
        task.get("title") or task.get("description")
        for task in planned_tasks[:task_index]
        if task.get("status") == "completed"
    ]
    future_tasks = [
        task.get("title") or task.get("description")
        for task in planned_tasks[task_index + 1 :]
        if task.get("status") in {"pending", "running"}
    ]
    base_url = getattr(env_config, "base_url", None) or ""

    instructions = [
        "You are executing one sub-task of a FlyTest UI automation case.",
        f"Overall case goal: {full_task}",
        f"Current sub-task: {current_task.get('title') or current_task.get('description')}",
        f"Sub-task detail: {current_task.get('description') or ''}",
        f"Expected result: {current_task.get('expected_result') or 'Complete the current sub-task successfully.'}",
        f"Execution mode: {execution_mode}.",
        f"Current time: {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}.",
        "Reuse the existing browser/session state whenever possible.",
        "Focus only on the current sub-task. Do not proactively execute later sub-tasks.",
        "If the current sub-task is already satisfied by the current page state, finish it immediately without redundant actions.",
        "If the current sub-task is finished, end the agent run clearly.",
        "When a click opens a dropdown, popup, tab, or modal, stop after the opening action and use the next step to interact with newly visible elements.",
        "If a link opens a new tab, switch to the newest tab and continue there. Do not click the same link again unless you verified the first click failed.",
        "Before save or submit, inspect the page for validation errors or missing required fields.",
        "If save or submit fails, stay on the current page, inspect the error, complete missing fields, and retry instead of closing the dialog.",
        "Avoid repeated clicks or repeated searches when the page state has already changed.",
        "Use browser-use native action parameters: use 'index' for click/input/select actions and 'text' for typed content.",
        "Never invent, replace, or guess credentials. Only use credentials explicitly provided in the task.",
        "Keep thinking concise and action-oriented.",
    ]

    if base_url:
        instructions.append(f"Preferred base URL: {base_url}")
        instructions.append("If the current page is irrelevant, navigate to the preferred base URL first.")

    if completed_tasks:
        instructions.append(f"Already completed sub-tasks: {json.dumps(completed_tasks, ensure_ascii=False)}")
    if future_tasks:
        instructions.append(f"Future sub-tasks (do not execute yet): {json.dumps(future_tasks, ensure_ascii=False)}")

    if model_name and any(keyword in model_name.lower() for keyword in ("qwen", "deepseek")):
        instructions.append("Minimize output tokens. Keep reasoning extremely short while preserving accuracy.")

    instructions.append(f"Project context: {json.dumps(project_context, ensure_ascii=False)}")
    return _sanitize_browser_prompt_text("\n".join(instructions))


def _format_browser_step_log(task_title: str, step_number: int, browser_state: Any, model_output: Any) -> str:
    actions = _extract_action_descriptions(getattr(model_output, "action", []) or [])
    page_title = getattr(browser_state, "title", "") or "-"
    current_url = getattr(browser_state, "url", "") or "-"
    next_goal = getattr(model_output, "next_goal", "") or "-"
    evaluation = getattr(model_output, "evaluation_previous_goal", "") or "-"
    recent_events = getattr(browser_state, "recent_events", "") or ""
    browser_errors = " | ".join(str(item) for item in (getattr(browser_state, "browser_errors", []) or []) if item)
    popup_messages = " | ".join(str(item) for item in (getattr(browser_state, "closed_popup_messages", []) or []) if item)
    action_text = ", ".join(actions) if actions else "无动作"
    log_message = (
        f"[{task_title}] 浏览器步骤 {step_number}: {action_text} | "
        f"下一目标：{next_goal} | 评估：{evaluation} | 页面：{page_title} | URL：{current_url}"
    )
    if recent_events:
        log_message += f" | 最近事件：{recent_events}"
    if browser_errors:
        log_message += f" | 浏览器错误：{browser_errors}"
    if popup_messages:
        log_message += f" | 弹窗信息：{popup_messages}"
    return log_message


def _extract_action_descriptions(actions: Sequence[Any]) -> list[str]:
    descriptions: list[str] = []
    for action in actions:
        if hasattr(action, "model_dump"):
            action_dict = action.model_dump(exclude_none=True)
        elif isinstance(action, dict):
            action_dict = action
        else:
            action_dict = {}

        if not action_dict:
            continue

        action_name, action_params = next(iter(action_dict.items()))
        if isinstance(action_params, dict) and action_params:
            descriptions.append(f"{action_name}({json.dumps(action_params, ensure_ascii=False)})")
        else:
            descriptions.append(action_name)
    return descriptions


def _validate_structured_output(value: Any, output_format: type[Any]) -> Any:
    if isinstance(value, output_format):
        return value

    if hasattr(output_format, "model_validate"):
        return output_format.model_validate(value)

    return output_format(**value)


def _normalize_structured_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    if "action" in payload:
        actions = payload["action"]
        if isinstance(actions, dict):
            actions = [actions]
        normalized_actions: list[dict[str, Any]] = []
        for action in actions if isinstance(actions, list) else []:
            normalized_action = _normalize_action_item(action)
            if normalized_action:
                normalized_actions.append(normalized_action)
        payload["action"] = normalized_actions
    return payload


def _normalize_action_item(action: Any) -> dict[str, Any] | None:
    if isinstance(action, str):
        return _parse_action_string(action)
    if not isinstance(action, dict):
        return None

    normalized: dict[str, Any] = {}
    for action_name, action_params in action.items():
        normalized_name = _normalize_action_name(action_name)
        normalized[normalized_name] = _normalize_action_params(normalized_name, action_params)
    return normalized or None


def _normalize_action_name(action_name: str) -> str:
    aliases = {
        "switch": "switch_tab",
    }
    return aliases.get(action_name, action_name)


def _normalize_action_params(action_name: str, action_params: Any) -> Any:
    if isinstance(action_params, int):
        return {"index": action_params}

    if action_name == "switch_tab" and isinstance(action_params, str):
        return {"tab_id": action_params}

    if not isinstance(action_params, dict):
        return action_params

    normalized_params: dict[str, Any] = {}
    for key, value in action_params.items():
        normalized_key = key
        if key in {"element_index", "element_id", "node_id", "id"}:
            normalized_key = "index"
        elif key in {"tab", "target", "target_id"} and action_name == "switch_tab":
            normalized_key = "tab_id"
        elif key in {"content", "value"} and action_name in {"input", "input_text"}:
            normalized_key = "text"
        normalized_params[normalized_key] = value
    return normalized_params


def _parse_action_string(raw_action: str) -> dict[str, Any] | None:
    match = ACTION_CALL_RE.match(raw_action.strip())
    if not match:
        return None

    action_name = _normalize_action_name(match.group("name"))
    params_text = match.group("params").strip()
    if not params_text:
        return {action_name: {}}

    parsed_params: dict[str, Any] = {}
    for chunk in [item.strip() for item in params_text.split(",") if item.strip()]:
        key, separator, value = chunk.partition("=")
        if not separator:
            continue
        parsed_params[key.strip()] = _coerce_string_value(value.strip())
    return {action_name: _normalize_action_params(action_name, parsed_params)}


def _coerce_string_value(value: str) -> Any:
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value
