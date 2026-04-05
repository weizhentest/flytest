import asyncio
import importlib.util
import json
import logging
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langgraph_integration.models import LLMConfig

from .models import UiAIExecutionRecord, UiElement, UiEnvironmentConfig, UiModule, UiPage

logger = logging.getLogger(__name__)

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

AI_STOP_SIGNALS: dict[int, bool] = {}
ACTION_CALL_RE = re.compile(r"^(?P<name>\w+)\((?P<params>.*)\)$")

__all__ = [
    "AI_STOP_SIGNALS",
    "AIExecutionStopped",
    "build_ai_execution_report",
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


def start_ai_execution(record_id: int) -> None:
    thread = threading.Thread(
        target=run_ai_execution,
        args=(record_id,),
        daemon=True,
        name=f"ui-ai-exec-{record_id}",
    )
    thread.start()


def request_stop_ai_execution(record_id: int) -> bool:
    AI_STOP_SIGNALS[record_id] = True
    updated = UiAIExecutionRecord.objects.filter(
        id=record_id,
        status__in=["pending", "running"],
    ).update(status="stopped", end_time=timezone.now())
    return updated > 0


def build_ai_execution_report(record: UiAIExecutionRecord) -> dict[str, Any]:
    planned_tasks = record.planned_tasks or []
    completed_tasks = [task for task in planned_tasks if task.get("status") == "completed"]
    failed_tasks = [task for task in planned_tasks if task.get("status") == "failed"]

    return {
        "id": record.id,
        "case_name": record.case_name,
        "status": record.status,
        "execution_mode": record.execution_mode,
        "execution_backend": record.execution_backend,
        "model_config_name": record.model_config_name,
        "task_description": record.task_description,
        "planned_task_count": len(planned_tasks),
        "completed_task_count": len(completed_tasks),
        "failed_task_count": len(failed_tasks),
        "steps_completed": record.steps_completed or [],
        "planned_tasks": planned_tasks,
        "logs": record.logs or "",
        "error_message": record.error_message,
        "start_time": record.start_time,
        "end_time": record.end_time,
        "duration": record.duration,
    }


def run_ai_execution(record_id: int) -> None:
    close_old_connections()

    try:
        record = UiAIExecutionRecord.objects.select_related("project", "ai_case").get(pk=record_id)
    except UiAIExecutionRecord.DoesNotExist:
        logger.warning("AI execution record %s no longer exists", record_id)
        return

    started_at = time.time()
    active_config = _get_active_llm_config()
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

        record.status = "passed"
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        _apply_runtime_state(record, runtime_state)
        runtime_state.append_log("AI 智能模式执行完成。")
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
            ],
        )
    except AIExecutionStopped:
        record.status = "stopped"
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        _apply_runtime_state(record, runtime_state)
        runtime_state.append_log("任务已停止。")
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
            ],
        )
    except Exception as exc:
        logger.exception("AI execution failed for record %s", record_id)
        record.status = "failed"
        record.error_message = str(exc)
        record.end_time = timezone.now()
        record.duration = round(time.time() - started_at, 2)
        _apply_runtime_state(record, runtime_state)
        runtime_state.append_log(f"任务执行失败：{exc}")
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
            ],
        )
    finally:
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

            async def register_new_step_callback(browser_state: Any, model_output: Any, step_number: int) -> None:
                runtime_state.append_log(
                    _format_browser_step_log(
                        task_title=task.get("title") or task.get("description") or f"任务 {index + 1}",
                        step_number=step_number,
                        browser_state=browser_state,
                        model_output=model_output,
                    )
                )
                await _persist_runtime_state(runtime_state)

            async def should_stop_callback() -> bool:
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
                ),
                llm=llm,
                browser_session=browser_session,
                page_extraction_llm=llm,
                use_vision=record.execution_mode == "vision",
                use_judge=False,
                max_actions_per_step=2,
                step_timeout=_resolve_step_timeout(env_config),
                generate_gif=str(gif_target),
                save_conversation_path=conversation_target,
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

            if gif_target.exists():
                runtime_state.gif_path = _to_media_relative_path(gif_target)

            errors = [error for error in history.errors() if error]
            success = history.is_successful()
            final_result = (history.final_result() or "").strip()

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


def _get_active_llm_config() -> LLMConfig | None:
    return LLMConfig.objects.filter(is_active=True).order_by("-updated_at").first()


def _get_default_env_config(project_id: int) -> UiEnvironmentConfig | None:
    return (
        UiEnvironmentConfig.objects.filter(project_id=project_id)
        .order_by("-is_default", "id")
        .first()
    )


def _detect_execution_backend() -> str:
    has_browser_use = importlib.util.find_spec("browser_use") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    return "browser_use" if has_browser_use and has_playwright else "planning"


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


def _build_browser_task_prompt(
    full_task: str,
    current_task: dict[str, Any],
    task_index: int,
    planned_tasks: list[dict[str, Any]],
    project_context: dict[str, Any],
    env_config: UiEnvironmentConfig | None,
    execution_mode: str,
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
        "Reuse the existing browser/session state whenever possible.",
        "Focus only on the current sub-task. Do not proactively execute later sub-tasks.",
        "If the current sub-task is finished, end the agent run clearly.",
    ]

    if base_url:
        instructions.append(f"Preferred base URL: {base_url}")
        instructions.append("If the current page is irrelevant, navigate to the preferred base URL first.")

    if completed_tasks:
        instructions.append(f"Already completed sub-tasks: {json.dumps(completed_tasks, ensure_ascii=False)}")
    if future_tasks:
        instructions.append(f"Future sub-tasks (do not execute yet): {json.dumps(future_tasks, ensure_ascii=False)}")

    instructions.append(f"Project context: {json.dumps(project_context, ensure_ascii=False)}")
    return "\n".join(instructions)


def _format_browser_step_log(task_title: str, step_number: int, browser_state: Any, model_output: Any) -> str:
    actions = _extract_action_descriptions(getattr(model_output, "action", []) or [])
    page_title = getattr(browser_state, "title", "") or "-"
    current_url = getattr(browser_state, "url", "") or "-"
    next_goal = getattr(model_output, "next_goal", "") or "-"
    evaluation = getattr(model_output, "evaluation_previous_goal", "") or "-"
    action_text = ", ".join(actions) if actions else "无动作"
    return (
        f"[{task_title}] 浏览器步骤 {step_number}: {action_text} | "
        f"下一目标：{next_goal} | 评估：{evaluation} | 页面：{page_title} | URL：{current_url}"
    )


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
