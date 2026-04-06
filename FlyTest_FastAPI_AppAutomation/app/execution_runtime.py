from __future__ import annotations

import base64
import io
import json
import re
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .adb import (
    AdbError,
    capture_device_screenshot,
    dump_device_ui_xml,
    input_device_text,
    launch_device_app,
    press_device_keyevent,
    stop_device_app,
    swipe_device,
    tap_device,
)
from .database import ELEMENT_UPLOADS_DIR, connection, fetch_one, json_loads
from .ocr_helper import get_ocr_helper

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:  # pragma: no cover - optional dependency
    Image = None
    ImageChops = None
    ImageStat = None

try:
    import cv2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import numpy as np  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    np = None


META_KEYS = {
    "id",
    "name",
    "kind",
    "type",
    "action",
    "component_type",
    "config",
    "steps",
    "_expanded",
}
VARIABLE_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}|\$\{\s*([^}]+?)\s*\}")
FULL_VARIABLE_PATTERN = re.compile(r"^\s*(?:\{\{\s*([^}]+?)\s*\}\}|\$\{\s*([^}]+?)\s*\})\s*$")
BOUNDS_PATTERN = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
DEFAULT_POLL_INTERVAL = 0.4
SUPPORTED_BASE_ACTIONS = {
    "touch",
    "double_click",
    "long_press",
    "drag",
    "text",
    "swipe",
    "swipe_to",
    "image_exists_click",
    "image_exists_click_chain",
    "foreach_assert",
    "wait",
    "assert",
    "assert_exists",
    "snapshot",
    "launch_app",
    "stop_app",
    "back",
    "home",
    "keyevent",
    "set_variable",
    "unset_variable",
    "extract_output",
    "api_request",
}
FLOW_CONTROL_ACTIONS = {
    "sequence",
    "if",
    "loop",
    "try",
}
SUPPORTED_BUILTIN_ACTIONS = SUPPORTED_BASE_ACTIONS | FLOW_CONTROL_ACTIONS


class StopRequested(RuntimeError):
    """Raised when execution is stopped by the user."""


class StepExecutionError(RuntimeError):
    """Raised when a scene step fails."""

    def __init__(self, index: int, step_name: str, cause: Exception, screenshot_path: str | None = None):
        self.index = index
        self.step_name = step_name
        self.cause = cause
        self.screenshot_path = screenshot_path
        message = f"Step {index} failed: {step_name}: {cause}"
        super().__init__(message)


@dataclass
class ResolvedTarget:
    kind: str
    description: str
    center: tuple[int, int] | None = None
    bounds: tuple[int, int, int, int] | None = None
    similarity: float | None = None
    used_fallback: bool = False


def normalize_action(step: dict[str, Any]) -> str:
    raw = str(step.get("action") or step.get("type") or step.get("component_type") or "").strip().lower()
    aliases = {
        "click": "touch",
        "tap": "touch",
        "double_tap": "double_click",
        "doubletap": "double_click",
        "input": "text",
        "input_text": "text",
        "type_text": "text",
        "sleep": "wait",
        "screenshot": "snapshot",
        "long_tap": "long_press",
        "longpress": "long_press",
        "press_and_hold": "long_press",
        "launch": "launch_app",
        "start_app": "launch_app",
        "open_app": "launch_app",
        "close_app": "stop_app",
        "exists": "assert_exists",
    }
    return aliases.get(raw, raw)


def sanitize_name(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_\-.]+", "-", str(value or "").strip())
    return safe.strip("-._") or "artifact"


class AppFlowExecutor:
    def __init__(
        self,
        *,
        adb_path: str,
        device_serial: str,
        project_id: int,
        variables: list[dict[str, Any]] | None = None,
        default_timeout: int = 30,
        default_package_name: str = "",
        default_activity_name: str = "",
        report_dir: str | Path | None = None,
        artifact_dir: str | Path | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.adb_path = adb_path
        self.device_serial = device_serial
        self.project_id = project_id
        self.default_timeout = max(int(default_timeout or 30), 1)
        self.default_package_name = str(default_package_name or "").strip()
        self.default_activity_name = str(default_activity_name or "").strip()
        self.stop_requested = stop_requested

        self.report_dir = Path(report_dir).resolve() if report_dir else None
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        if self.artifact_dir:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.assets_root = ELEMENT_UPLOADS_DIR.parent.resolve()
        self._element_cache: dict[str, dict[str, Any] | None] = {}
        self._custom_component_cache: dict[str, dict[str, Any] | None] = {}
        self._ocr_helper = None

        self.global_context: dict[str, Any] = {}
        self.local_scopes: list[dict[str, Any]] = [{}]
        self.outputs: dict[str, Any] = {}
        self._load_variables(variables or [])

    def count_total_steps(self, steps: list[dict[str, Any]]) -> int:
        total = 0
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            step = self._merge_config(raw_step)
            action = normalize_action(step)
            if action == "sequence":
                total += max(self.count_total_steps(self._extract_step_list(step.get("steps"))), 1)
                continue
            if action == "if":
                then_total = self.count_total_steps(self._extract_step_list(step.get("then_steps") or step.get("steps")))
                else_total = self.count_total_steps(self._extract_step_list(step.get("else_steps")))
                total += max(then_total, else_total, 1)
                continue
            if action == "loop":
                child_total = max(self.count_total_steps(self._extract_step_list(step.get("steps"))), 1)
                total += max(self._estimate_loop_iterations(step), 1) * child_total
                continue
            if action == "try":
                try_total = self.count_total_steps(self._extract_step_list(step.get("try_steps") or step.get("steps")))
                catch_total = self.count_total_steps(self._extract_step_list(step.get("catch_steps")))
                finally_total = self.count_total_steps(self._extract_step_list(step.get("finally_steps")))
                total += max(try_total + finally_total, try_total + catch_total + finally_total, 1)
                continue
            children = self._get_child_steps(step)
            if children is None:
                total += 1
                continue
            child_count = self.count_total_steps(children)
            total += child_count or 1
        return total

    def has_action(self, steps: list[dict[str, Any]], actions: set[str]) -> bool:
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            step = self._merge_config(raw_step)
            action = normalize_action(step)
            if action in actions:
                return True
            for child_steps in self._iter_nested_step_groups(step):
                if child_steps and self.has_action(child_steps, actions):
                    return True
        return False

    def launch_default_app(self) -> str:
        if not self.default_package_name:
            raise ValueError("No application package configured for this test case")
        launch_device_app(
            self.adb_path,
            self.device_serial,
            self.default_package_name,
            self.default_activity_name,
            timeout=max(self.default_timeout, 15),
        )
        return f"Launched app {self.default_package_name}"

    def run(
        self,
        steps: list[dict[str, Any]],
        on_step_complete: Callable[[int, int, str, str], None] | None = None,
    ) -> dict[str, Any]:
        total_steps = max(self.count_total_steps(steps), 1)
        state = {"index": 0}
        for raw_step in steps:
            if not isinstance(raw_step, dict):
                continue
            self._execute_tree(raw_step, state, total_steps, on_step_complete)
        return {
            "total_steps": total_steps,
            "passed_steps": state["index"],
            "failed_steps": 0,
            "outputs": dict(self.outputs),
        }

    def capture_failure_artifact(self, step_name: str) -> str | None:
        path = self._save_screenshot(f"failed-{step_name}")
        return str(path) if path else None

    def _execute_tree(
        self,
        raw_step: dict[str, Any],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        self._assert_not_stopped()
        merged_step = self._merge_config(raw_step)
        action = normalize_action(merged_step)
        if action in FLOW_CONTROL_ACTIONS:
            self._execute_flow_action(merged_step, action, state, total_steps, on_step_complete)
            return

        step = self._render_value(merged_step)

        child_steps = self._get_child_steps(step)

        if child_steps is not None:
            component_name = str(step.get("name") or step.get("type") or step.get("component_type") or "custom")
            with self._pushed_scope(self._extract_component_context(step)):
                if not child_steps:
                    raise ValueError(f"Custom component '{component_name}' has no executable child steps")
                for child_step in child_steps:
                    self._execute_tree(child_step, state, total_steps, on_step_complete)
            return

        if not action:
            raise ValueError(f"Step '{step.get('name') or 'unnamed'}' is missing an action type")

        step_name = str(step.get("name") or step.get("type") or step.get("component_type") or action)
        try:
            detail = self._execute_action(step, action)
        except StopRequested:
            raise
        except Exception as exc:
            screenshot_path = self.capture_failure_artifact(step_name)
            raise StepExecutionError(state["index"] + 1, step_name, exc, screenshot_path) from exc

        state["index"] += 1
        if on_step_complete:
            on_step_complete(state["index"], total_steps, step_name, detail)

    def _execute_action(self, step: dict[str, Any], action: str) -> str:
        handlers: dict[str, Callable[[dict[str, Any]], str]] = {
            "touch": self._action_touch,
            "double_click": self._action_double_click,
            "long_press": self._action_long_press,
            "drag": self._action_drag,
            "text": self._action_text,
            "swipe": self._action_swipe,
            "swipe_to": self._action_swipe_to,
            "image_exists_click": self._action_image_exists_click,
            "image_exists_click_chain": self._action_image_exists_click_chain,
            "foreach_assert": self._action_foreach_assert,
            "wait": self._action_wait,
            "assert": self._action_assert,
            "assert_exists": self._action_assert_exists,
            "snapshot": self._action_snapshot,
            "launch_app": self._action_launch_app,
            "stop_app": self._action_stop_app,
            "back": self._action_back,
            "home": self._action_home,
            "keyevent": self._action_keyevent,
            "set_variable": self._action_set_variable,
            "unset_variable": self._action_unset_variable,
            "extract_output": self._action_extract_output,
            "api_request": self._action_api_request,
        }
        handler = handlers.get(action)
        if handler is None:
            raise ValueError(f"Unsupported action type: {action}")
        return handler(step)

    def _action_touch(self, step: dict[str, Any]) -> str:
        target = self._resolve_target(step, allow_image_position_fallback=True)
        if target.center is None:
            raise ValueError(f"Unable to resolve target for step '{step.get('name') or 'unnamed'}'")
        x, y = target.center
        tap_device(self.adb_path, self.device_serial, x, y)
        detail = f"Tapped {target.description} at ({x}, {y})"
        if target.similarity is not None:
            detail += f", similarity={target.similarity:.2f}"
        if target.used_fallback:
            detail += " using stored region fallback"
        return detail

    def _action_double_click(self, step: dict[str, Any]) -> str:
        target = self._resolve_target(step, allow_image_position_fallback=True)
        if target.center is None:
            raise ValueError(f"Unable to resolve target for step '{step.get('name') or 'unnamed'}'")
        x, y = target.center
        interval_seconds = float(step.get("interval") or step.get("interval_seconds") or 0.12)
        tap_device(self.adb_path, self.device_serial, x, y)
        self._sleep_with_stop(max(interval_seconds, 0.05))
        tap_device(self.adb_path, self.device_serial, x, y)
        return f"Double tapped {target.description} at ({x}, {y})"

    def _action_long_press(self, step: dict[str, Any]) -> str:
        target = self._resolve_target(step, allow_image_position_fallback=True)
        if target.center is None:
            raise ValueError(f"Unable to resolve target for step '{step.get('name') or 'unnamed'}'")
        x, y = target.center
        duration_seconds = float(
            step.get("duration")
            or step.get("duration_seconds")
            or step.get("hold_seconds")
            or 1.0
        )
        duration_ms = max(int(duration_seconds * 1000), 300)
        swipe_device(self.adb_path, self.device_serial, (x, y), (x, y), duration_ms=duration_ms)
        return f"Long pressed {target.description} at ({x}, {y}) for {duration_ms} ms"

    def _action_text(self, step: dict[str, Any]) -> str:
        text_value = str(step.get("text") or step.get("value") or step.get("content") or "")
        if not text_value:
            raise ValueError("Input text step is missing text content")

        if self._step_has_target(step):
            target = self._resolve_target(step, allow_image_position_fallback=True)
            if target.center is None:
                raise ValueError(f"Unable to focus input target for step '{step.get('name') or 'unnamed'}'")
            tap_device(self.adb_path, self.device_serial, target.center[0], target.center[1])
            self._sleep_with_stop(0.3)

        input_device_text(self.adb_path, self.device_serial, text_value, timeout=max(self.default_timeout, 10))
        preview = text_value if len(text_value) <= 24 else f"{text_value[:24]}..."
        return f"Input text '{preview}'"

    def _action_swipe(self, step: dict[str, Any]) -> str:
        start = self._resolve_point(step.get("start"))
        end = self._resolve_point(step.get("end"))
        if start is None or end is None:
            raise ValueError("Swipe step requires valid start and end coordinates")
        duration_seconds = float(step.get("duration") or step.get("duration_seconds") or 0.4)
        duration_ms = max(int(duration_seconds * 1000), 100)
        swipe_device(self.adb_path, self.device_serial, start, end, duration_ms=duration_ms)
        return f"Swiped from {start} to {end} in {duration_ms} ms"

    def _action_drag(self, step: dict[str, Any]) -> str:
        start = self._resolve_drag_point(step, "start", fallback_to_primary=True)
        end = self._resolve_drag_point(step, "end")
        if end is None:
            end = self._resolve_drag_point(step, "to")
        if start is None or end is None:
            raise ValueError("Drag step requires valid start and end targets")
        duration_seconds = float(step.get("duration") or step.get("duration_seconds") or 0.6)
        duration_ms = max(int(duration_seconds * 1000), 150)
        swipe_device(self.adb_path, self.device_serial, start, end, duration_ms=duration_ms)
        return f"Dragged from {start} to {end} in {duration_ms} ms"

    def _action_swipe_to(self, step: dict[str, Any]) -> str:
        target_step = self._build_target_step(step, prefix="target")
        if not self._step_has_target(target_step):
            if self._step_has_target(step):
                target_step = {
                    "name": step.get("name"),
                    "element_id": step.get("element_id"),
                    "selector_type": step.get("selector_type"),
                    "selector": step.get("selector"),
                    "selector_value": step.get("selector_value"),
                    "match_mode": step.get("match_mode"),
                    "match_index": step.get("match_index"),
                    "config": step.get("config"),
                }
            else:
                raise ValueError("Swipe-to step requires a target selector")

        max_swipes = max(int(step.get("max_swipes") or step.get("times") or 5), 1)
        interval_seconds = max(float(step.get("interval") or 0.5), 0.0)
        duration_seconds = float(step.get("duration") or step.get("duration_seconds") or 0.4)
        duration_ms = max(int(duration_seconds * 1000), 100)

        start = self._resolve_drag_point(step, "start")
        end = self._resolve_drag_point(step, "end")
        if start is None or end is None:
            start, end = self._default_swipe_points(str(step.get("direction") or "up"))

        for _ in range(max_swipes):
            target = self._resolve_target_if_available(target_step)
            if target is not None:
                return f"Found target after swipe search: {target.description}"
            swipe_device(self.adb_path, self.device_serial, start, end, duration_ms=duration_ms)
            if interval_seconds > 0:
                self._sleep_with_stop(interval_seconds)

        target = self._resolve_target_if_available(target_step)
        if target is not None:
            return f"Found target after swipe search: {target.description}"
        raise ValueError(f"Unable to find target after {max_swipes} swipes")

    def _action_image_exists_click(self, step: dict[str, Any]) -> str:
        primary_target = self._resolve_target_if_available(step) if self._step_has_target(step) else None
        if primary_target is not None:
            x, y = self._tap_resolved_target(primary_target, step_name=str(step.get("name") or "image_exists_click"))
            return f"Primary target exists, tapped {primary_target.description} at ({x}, {y})"

        fallback_step = self._build_target_step(step, prefix="fallback")
        if not self._step_has_target(fallback_step):
            raise ValueError("image_exists_click requires fallback target when primary target is unavailable")

        fallback_target = self._resolve_target(fallback_step, allow_image_position_fallback=True)
        x, y = self._tap_resolved_target(fallback_target, step_name=str(step.get("name") or "image_exists_click"))
        return f"Primary target unavailable, tapped fallback target {fallback_target.description} at ({x}, {y})"

    def _action_image_exists_click_chain(self, step: dict[str, Any]) -> str:
        fallback_step = self._build_target_step(step, prefix="fallback")
        has_primary_target = self._step_has_target(step)
        has_fallback_target = self._step_has_target(fallback_step)
        if not has_primary_target and not has_fallback_target:
            raise ValueError("image_exists_click_chain requires at least one target")

        detail_parts: list[str] = []
        primary_target = self._resolve_target_if_available(step) if has_primary_target else None
        if primary_target is not None:
            x, y = self._tap_resolved_target(primary_target, step_name=str(step.get("name") or "image_exists_click_chain"))
            detail_parts.append(f"tapped primary target {primary_target.description} at ({x}, {y})")
            if has_fallback_target:
                interval_seconds = max(float(step.get("interval") or 0.5), 0.0)
                if interval_seconds > 0:
                    self._sleep_with_stop(interval_seconds)
        elif not has_fallback_target:
            raise ValueError("Primary target is unavailable and no fallback target is configured")

        if has_fallback_target:
            fallback_target = self._resolve_target(fallback_step, allow_image_position_fallback=True)
            x, y = self._tap_resolved_target(fallback_target, step_name=str(step.get("name") or "image_exists_click_chain"))
            if primary_target is not None:
                detail_parts.append(f"then tapped fallback target {fallback_target.description} at ({x}, {y})")
            else:
                detail_parts.append(f"primary target unavailable, tapped fallback target {fallback_target.description} at ({x}, {y})")

        if not detail_parts:
            raise ValueError("No target available to click")
        return "; ".join(detail_parts)

    def _action_wait(self, step: dict[str, Any]) -> str:
        timeout = float(step.get("timeout") or step.get("duration") or self.default_timeout)
        if timeout <= 0:
            timeout = DEFAULT_POLL_INTERVAL

        if not self._step_has_target(step):
            self._sleep_with_stop(timeout)
            return f"Waited {timeout:.1f} seconds"

        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() <= deadline:
            self._assert_not_stopped()
            try:
                target = self._resolve_target(step, allow_image_position_fallback=False)
                return f"Target is available: {target.description}"
            except Exception as exc:
                last_error = exc
                self._sleep_with_stop(DEFAULT_POLL_INTERVAL)

        if last_error is not None:
            raise ValueError(f"Wait timeout after {timeout:.1f}s: {last_error}") from last_error
        raise ValueError(f"Wait timeout after {timeout:.1f}s")

    def _action_foreach_assert(self, step: dict[str, Any]) -> str:
        click_step = self._build_target_step(step, prefix="click")
        if not self._step_has_target(click_step):
            raise ValueError("foreach_assert requires click_selector or click_element_id")

        ocr_region = self._parse_ocr_region(step)
        expected_values = self._normalize_expected_list(step.get("expected_list") or step.get("expected_values"))
        if not expected_values:
            raise ValueError("foreach_assert requires expected_list")

        assert_type = str(step.get("assert_type") or "text").strip().lower() or "text"
        if assert_type not in {"text", "number", "regex"}:
            raise ValueError("foreach_assert supports assert_type: text, number, regex")

        match_mode = str(step.get("match_mode") or "contains").strip().lower() or "contains"
        if assert_type == "text" and match_mode not in {"exact", "contains", "regex"}:
            raise ValueError("foreach_assert text mode supports: exact, contains, regex")

        max_loops = max(int(step.get("max_loops") or step.get("times") or 1), 1)
        min_match = max(int(step.get("min_match") or 1), 0)
        interval_seconds = max(float(step.get("interval") or 0.5), 0.0)
        timeout_seconds = max(float(step.get("timeout") or 0), 0.0)
        matched_count = 0
        last_value: Any = None

        for _ in range(max_loops):
            target = self._resolve_target(click_step, allow_image_position_fallback=True)
            self._tap_resolved_target(target, step_name=str(step.get("name") or "foreach_assert"))
            if interval_seconds > 0:
                self._sleep_with_stop(interval_seconds)

            matched, actual_value = self._poll_foreach_assert_match(
                ocr_region=ocr_region,
                expected_values=expected_values,
                assert_type=assert_type,
                match_mode=match_mode,
                timeout_seconds=timeout_seconds,
            )
            last_value = actual_value
            if matched:
                matched_count += 1

        if matched_count < min_match:
            raise AssertionError(
                f"foreach_assert failed: expected at least {min_match} matches, got {matched_count}, last={last_value!r}"
            )

        return f"foreach_assert passed: matched {matched_count}/{max_loops}, last={last_value!r}"

    def _action_assert_exists(self, step: dict[str, Any]) -> str:
        timeout = float(step.get("timeout") or 0)
        if timeout > 0:
            return self._action_wait(step)
        target = self._resolve_target(step, allow_image_position_fallback=False)
        return f"Assertion passed: {target.description}"

    def _action_assert(self, step: dict[str, Any]) -> str:
        timeout = max(float(step.get("timeout") or 0), 0.0)
        retry_interval = max(float(step.get("retry_interval") or 0.5), 0.1)
        deadline = time.time() + timeout
        last_error: Exception | None = None

        while True:
            try:
                return self._run_assertion(step)
            except StopRequested:
                raise
            except Exception as exc:
                last_error = exc
                if timeout <= 0 or time.time() >= deadline:
                    raise
                self._sleep_with_stop(min(retry_interval, max(deadline - time.time(), 0.0)))

        if last_error is not None:
            raise last_error
        raise ValueError("Assertion failed")

    def _action_snapshot(self, step: dict[str, Any]) -> str:
        label = str(step.get("name") or step.get("label") or "snapshot")
        path = self._save_screenshot(label)
        if path is None:
            raise ValueError("Failed to capture screenshot")
        return f"Captured screenshot {path}"

    def _action_launch_app(self, step: dict[str, Any]) -> str:
        package_name = str(step.get("package_name") or step.get("package") or self.default_package_name or "").strip()
        activity_name = str(step.get("activity_name") or step.get("activity") or self.default_activity_name or "").strip()
        if not package_name:
            raise ValueError("Launch app step is missing package_name")
        launch_device_app(self.adb_path, self.device_serial, package_name, activity_name, timeout=max(self.default_timeout, 15))
        return f"Launched app {package_name}"

    def _action_stop_app(self, step: dict[str, Any]) -> str:
        package_name = str(step.get("package_name") or step.get("package") or self.default_package_name or "").strip()
        if not package_name:
            raise ValueError("Stop app step is missing package_name")
        stop_device_app(self.adb_path, self.device_serial, package_name)
        return f"Stopped app {package_name}"

    def _action_back(self, _: dict[str, Any]) -> str:
        press_device_keyevent(self.adb_path, self.device_serial, "KEYCODE_BACK")
        return "Pressed BACK"

    def _action_home(self, _: dict[str, Any]) -> str:
        press_device_keyevent(self.adb_path, self.device_serial, "KEYCODE_HOME")
        return "Pressed HOME"

    def _action_keyevent(self, step: dict[str, Any]) -> str:
        keycode = str(step.get("keycode") or step.get("key") or "").strip()
        if not keycode:
            raise ValueError("Keyevent step is missing keycode")
        press_device_keyevent(self.adb_path, self.device_serial, keycode)
        return f"Pressed {keycode}"

    def _action_set_variable(self, step: dict[str, Any]) -> str:
        variable_name = str(step.get("variable_name") or step.get("var_name") or step.get("name") or "").strip()
        if not variable_name:
            raise ValueError("set_variable step is missing variable_name")
        scope = str(step.get("scope") or "local").strip().lower()
        self._set_variable(variable_name, step.get("value"), scope)
        return f"Set {scope}.{variable_name}"

    def _action_unset_variable(self, step: dict[str, Any]) -> str:
        variable_name = str(step.get("variable_name") or step.get("var_name") or step.get("name") or "").strip()
        if not variable_name:
            raise ValueError("unset_variable step is missing variable_name")
        scope = str(step.get("scope") or "local").strip().lower()
        target_scope = self.global_context if scope == "global" else self.local_scopes[-1]
        target_scope.pop(variable_name, None)
        return f"Removed {scope}.{variable_name}"

    def _action_extract_output(self, step: dict[str, Any]) -> str:
        source = str(step.get("source") or step.get("from") or "").strip()
        path = str(step.get("path") or "").strip()
        variable_name = str(step.get("variable_name") or step.get("save_as") or step.get("name") or "").strip()
        scope = str(step.get("scope") or "local").strip().lower()
        if not variable_name:
            raise ValueError("extract_output step is missing variable_name")
        if not source:
            raise ValueError("extract_output step is missing source")

        source_value = self._resolve_value_reference(source)
        if source_value is None:
            raise ValueError(f"Source '{source}' does not exist")

        extracted = self._extract_value_by_path(source_value, path) if path else source_value
        self._set_variable(variable_name, extracted, scope)
        self._remember_output(variable_name, extracted)
        return f"Extracted {source}{'.' + path if path else ''} to {scope}.{variable_name}"

    def _action_api_request(self, step: dict[str, Any]) -> str:
        method = str(step.get("method") or "GET").strip().upper() or "GET"
        url = str(self._render_value(step.get("url") or "")).strip()
        if not url:
            raise ValueError("api_request step is missing url")

        headers = self._render_value(step.get("headers") or {})
        params = self._render_value(step.get("params") or {})
        has_json_payload = "json" in step
        has_form_payload = "data" in step
        json_payload = self._render_value(step.get("json")) if has_json_payload else None
        form_payload = self._render_value(step.get("data")) if has_form_payload else None
        timeout = max(float(step.get("timeout") or 10), 0.1)
        response_type = str(step.get("response_type") or "auto").strip().lower() or "auto"
        expected_status = step.get("expected_status")
        save_as = str(step.get("save_as") or "").strip()
        scope = str(step.get("scope") or "local").strip().lower()
        extracts = step.get("extracts") if isinstance(step.get("extracts"), list) else []

        request_headers = {str(key): str(value) for key, value in (headers.items() if isinstance(headers, dict) else [])}
        if isinstance(params, dict) and params:
            encoded = urlencode(params, doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{encoded}"

        payload_bytes: bytes | None = None
        if has_json_payload:
            payload_bytes = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif has_form_payload:
            if isinstance(form_payload, dict):
                payload_bytes = urlencode(form_payload, doseq=True).encode("utf-8")
                request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            elif isinstance(form_payload, (bytes, bytearray)):
                payload_bytes = bytes(form_payload)
            else:
                payload_bytes = str(form_payload).encode("utf-8")

        request = Request(url=url, data=payload_bytes, method=method, headers=request_headers)

        try:
            with urlopen(request, timeout=timeout) as response:
                status_code = int(response.getcode() or 0)
                response_headers = dict(response.headers.items())
                response_bytes = response.read()
        except HTTPError as exc:
            status_code = int(exc.code or 0)
            response_headers = dict(exc.headers.items()) if exc.headers else {}
            response_bytes = exc.read()
        except URLError as exc:
            raise ValueError(f"HTTP request failed: {exc.reason}") from exc

        body = self._parse_response_body(response_bytes, response_headers, response_type)
        result = {
            "status_code": status_code,
            "headers": response_headers,
            "body": body,
        }

        if expected_status is not None and status_code != int(expected_status):
            raise AssertionError(f"HTTP status assertion failed: expected {expected_status}, got {status_code}")

        if save_as:
            self._set_variable(save_as, result, scope)
            self._remember_output(save_as, result)

        for item in extracts:
            if not isinstance(item, dict):
                continue
            variable_name = str(item.get("name") or item.get("variable_name") or "").strip()
            if not variable_name:
                continue
            extract_scope = str(item.get("scope") or scope).strip().lower()
            extract_path = str(item.get("path") or "").strip()
            extracted = self._extract_value_by_path(result, extract_path) if extract_path else result
            self._set_variable(variable_name, extracted, extract_scope)
            self._remember_output(variable_name, extracted)

        return f"Requested {method} {url} -> {status_code}"

    def _execute_flow_action(
        self,
        step: dict[str, Any],
        action: str,
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        if action == "sequence":
            self._execute_sequence(step, state, total_steps, on_step_complete)
            return
        if action == "if":
            self._execute_if(step, state, total_steps, on_step_complete)
            return
        if action == "loop":
            self._execute_loop(step, state, total_steps, on_step_complete)
            return
        if action == "try":
            self._execute_try(step, state, total_steps, on_step_complete)
            return
        raise ValueError(f"Unsupported flow action: {action}")

    def _execute_sequence(
        self,
        step: dict[str, Any],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        nested_steps = self._extract_step_list(step.get("steps"))
        if not nested_steps:
            raise ValueError("Sequence step requires at least one child step")
        with self._pushed_scope({}):
            self._run_nested_steps(nested_steps, state, total_steps, on_step_complete)

    def _execute_if(
        self,
        step: dict[str, Any],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        left = step.get("left")
        operator = str(step.get("operator") or "truthy").strip()
        right = step.get("right")
        nested_steps = self._extract_step_list(step.get("then_steps") or step.get("steps"))
        else_steps = self._extract_step_list(step.get("else_steps"))
        condition = self._evaluate_condition(self._render_value(left), operator, self._render_value(right))
        branch_steps = nested_steps if condition else else_steps
        if branch_steps:
            with self._pushed_scope({}):
                self._run_nested_steps(branch_steps, state, total_steps, on_step_complete)

    def _execute_loop(
        self,
        step: dict[str, Any],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        nested_steps = self._extract_step_list(step.get("steps"))
        if not nested_steps:
            raise ValueError("Loop step requires child steps")

        mode = str(step.get("mode") or "count").strip().lower()
        interval = max(float(step.get("interval") or 0), 0.0)
        max_loops = max(int(step.get("max_loops") or 10), 1)

        if mode == "count":
            times = max(int(self._render_value(step.get("times") or step.get("count") or step.get("iterations") or 1)), 0)
            for _ in range(times):
                with self._pushed_scope({}):
                    self._run_nested_steps(nested_steps, state, total_steps, on_step_complete)
                if interval > 0:
                    self._sleep_with_stop(interval)
            return

        if mode in {"foreach", "for_each"}:
            items = self._coerce_loop_items(self._render_value(step.get("items")))
            item_var = str(step.get("item_var") or "item").strip() or "item"
            item_scope = str(step.get("item_scope") or "local").strip().lower()
            index_var = str(step.get("index_var") or "").strip()
            for index, item in enumerate(items):
                scope_values: dict[str, Any] = {item_var: item}
                if index_var:
                    scope_values[index_var] = index
                with self._pushed_scope(scope_values):
                    if item_scope == "global":
                        self._set_variable(item_var, item, "global")
                        if index_var:
                            self._set_variable(index_var, index, "global")
                    self._run_nested_steps(nested_steps, state, total_steps, on_step_complete)
                if interval > 0:
                    self._sleep_with_stop(interval)
            return

        if mode == "condition":
            left = step.get("left")
            operator = str(step.get("operator") or "truthy").strip()
            right = step.get("right")
            loop_count = 0
            while loop_count < max_loops and self._evaluate_condition(
                self._render_value(left),
                operator,
                self._render_value(right),
            ):
                loop_count += 1
                with self._pushed_scope({"loop_index": loop_count - 1, "loop_iteration": loop_count}):
                    self._run_nested_steps(nested_steps, state, total_steps, on_step_complete)
                if interval > 0:
                    self._sleep_with_stop(interval)
            return

        raise ValueError(f"Unsupported loop mode: {mode}")

    def _execute_try(
        self,
        step: dict[str, Any],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        try_steps = self._extract_step_list(step.get("try_steps") or step.get("steps"))
        catch_steps = self._extract_step_list(step.get("catch_steps"))
        finally_steps = self._extract_step_list(step.get("finally_steps"))
        error_var = str(step.get("error_var") or "error").strip() or "error"
        error_scope = str(step.get("error_scope") or "local").strip().lower()

        try:
            if try_steps:
                with self._pushed_scope({}):
                    self._run_nested_steps(try_steps, state, total_steps, on_step_complete)
        except StopRequested:
            raise
        except Exception as exc:
            self._set_variable(error_var, str(exc), error_scope)
            if catch_steps:
                with self._pushed_scope({error_var: str(exc)}):
                    self._run_nested_steps(catch_steps, state, total_steps, on_step_complete)
            else:
                raise
        finally:
            if finally_steps:
                with self._pushed_scope({}):
                    self._run_nested_steps(finally_steps, state, total_steps, on_step_complete)

    def _run_nested_steps(
        self,
        steps: list[dict[str, Any]],
        state: dict[str, int],
        total_steps: int,
        on_step_complete: Callable[[int, int, str, str], None] | None,
    ) -> None:
        for child_step in steps:
            self._execute_tree(child_step, state, total_steps, on_step_complete)

    def _extract_step_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _iter_nested_step_groups(self, step: dict[str, Any]) -> Iterator[list[dict[str, Any]]]:
        action = normalize_action(step)
        if action in {"sequence", "loop"}:
            nested_steps = self._extract_step_list(step.get("steps"))
            if nested_steps:
                yield nested_steps
            return
        if action == "if":
            then_steps = self._extract_step_list(step.get("then_steps") or step.get("steps"))
            else_steps = self._extract_step_list(step.get("else_steps"))
            if then_steps:
                yield then_steps
            if else_steps:
                yield else_steps
            return
        if action == "try":
            for key in ("try_steps", "steps", "catch_steps", "finally_steps"):
                nested_steps = self._extract_step_list(step.get(key))
                if nested_steps:
                    yield nested_steps
            return
        child_steps = self._get_child_steps(step)
        if child_steps:
            yield child_steps

    def _estimate_loop_iterations(self, step: dict[str, Any]) -> int:
        mode = str(step.get("mode") or "count").strip().lower()
        if mode == "count":
            return max(int(step.get("times") or step.get("count") or step.get("iterations") or 1), 1)
        if mode in {"foreach", "for_each"}:
            return max(len(self._coerce_loop_items(step.get("items"))), 1)
        return max(int(step.get("max_loops") or 1), 1)

    def _evaluate_condition(self, left: Any, operator: str, right: Any) -> bool:
        op = str(operator or "truthy").strip().lower()
        if op == "==":
            return str(left) == str(right)
        if op == "!=":
            return str(left) != str(right)
        if op in {">", ">=", "<", "<="}:
            try:
                left_value = float(left)
                right_value = float(right)
            except (TypeError, ValueError):
                return False
            if op == ">":
                return left_value > right_value
            if op == ">=":
                return left_value >= right_value
            if op == "<":
                return left_value < right_value
            return left_value <= right_value
        if op == "in":
            return str(left) in str(right)
        if op in {"not in", "not_in"}:
            return str(left) not in str(right)
        if op == "contains":
            return str(right) in str(left)
        if op in {"notcontains", "not_contains"}:
            return str(right) not in str(left)
        if op in {"regex", "match"}:
            try:
                return bool(re.search(str(right), str(left)))
            except re.error:
                return False
        if op in {"truthy", "exists"}:
            return bool(left)
        if op in {"falsy", "not_exists"}:
            return not bool(left)
        if op == "startswith":
            return str(left).startswith(str(right))
        if op == "endswith":
            return str(left).endswith(str(right))
        return False

    def _coerce_loop_items(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json_loads(text, None)
            except TypeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
            return [item.strip() for item in text.split(",") if item.strip()]
        return [value]

    def _resolve_drag_point(self, step: dict[str, Any], prefix: str, *, fallback_to_primary: bool = False) -> tuple[int, int] | None:
        direct_point = self._resolve_point(step.get(prefix))
        if direct_point is not None:
            return direct_point

        point_fields = {
            "x": step.get(f"{prefix}_x"),
            "y": step.get(f"{prefix}_y"),
        }
        if point_fields["x"] is not None and point_fields["y"] is not None:
            point = self._resolve_point(point_fields)
            if point is not None:
                return point

        selector_step = {
            "name": step.get("name"),
            "element_id": step.get(f"{prefix}_element_id"),
            "selector_type": step.get(f"{prefix}_selector_type"),
            "selector": step.get(f"{prefix}_selector"),
            "selector_value": step.get(f"{prefix}_selector_value"),
            "match_mode": step.get(f"{prefix}_match_mode") or step.get("match_mode"),
            "match_index": step.get(f"{prefix}_match_index") or step.get("match_index"),
        }
        if self._step_has_target(selector_step):
            target = self._resolve_target(selector_step, allow_image_position_fallback=True)
            return target.center

        if fallback_to_primary and self._step_has_target(step):
            target = self._resolve_target(step, allow_image_position_fallback=True)
            return target.center
        return None

    def _step_has_target(self, step: dict[str, Any]) -> bool:
        if step.get("element_id") not in (None, ""):
            return True
        if step.get("selector") not in (None, ""):
            return True
        if step.get("selector_value") not in (None, ""):
            return True
        selector_type = str(step.get("selector_type") or "").strip()
        return bool(selector_type)

    def _resolve_target(self, step: dict[str, Any], *, allow_image_position_fallback: bool) -> ResolvedTarget:
        selector_type = str(step.get("selector_type") or "").strip().lower()
        selector_value = step.get("selector")
        if selector_value in (None, ""):
            selector_value = step.get("selector_value")
        element_ref = step.get("element_id")
        if element_ref in (None, "") and selector_type == "element":
            element_ref = selector_value

        if element_ref not in (None, ""):
            element = self._get_element(element_ref)
            if element is None:
                raise ValueError(f"Element '{element_ref}' does not exist")
            target = self._resolve_target_from_element(element, allow_image_position_fallback=allow_image_position_fallback)
            if target is not None:
                return target

        if selector_type in {"pos", "point", "coordinate"}:
            point = self._resolve_point(selector_value)
            if point is None:
                raise ValueError(f"Invalid point selector: {selector_value}")
            return ResolvedTarget(kind="point", description=f"point {point}", center=point)

        if selector_type == "region":
            bounds = self._resolve_bounds(selector_value)
            if bounds is None:
                raise ValueError(f"Invalid region selector: {selector_value}")
            return ResolvedTarget(kind="region", description=f"region {bounds}", bounds=bounds, center=self._center_of(bounds))

        if selector_type == "image":
            image_path = str(selector_value or step.get("image_path") or "").strip()
            config = step.get("config") if isinstance(step.get("config"), dict) else {}
            target = self._resolve_image_target(
                image_path=image_path,
                config=config,
                label=str(step.get("name") or image_path or "image"),
                allow_fallback=allow_image_position_fallback,
            )
            if target is None:
                raise ValueError(f"Image selector '{image_path}' is not available")
            return target

        if selector_type in {"text", "id", "resource-id", "desc", "content-desc", "accessibility_id", "class", "xpath"}:
            value = str(selector_value or "").strip()
            if not value:
                raise ValueError(f"Selector '{selector_type}' is missing a value")
            target = self._resolve_ui_target(selector_type, value, step)
            if target is None:
                raise ValueError(f"Unable to locate selector '{selector_type}={value}'")
            return target

        if selector_value not in (None, "") and not selector_type:
            value = str(selector_value).strip()
            element = self._get_element(value)
            if element is not None:
                target = self._resolve_target_from_element(element, allow_image_position_fallback=allow_image_position_fallback)
                if target is not None:
                    return target
            target = self._resolve_ui_target("text", value, step)
            if target is not None:
                return target

        raise ValueError("No supported selector found")

    def _resolve_target_from_element(
        self,
        element: dict[str, Any],
        *,
        allow_image_position_fallback: bool,
    ) -> ResolvedTarget | None:
        element_type = str(element.get("element_type") or "").strip().lower()
        selector_type = str(element.get("selector_type") or "").strip().lower()
        selector_value = element.get("selector_value")
        config = element.get("config") if isinstance(element.get("config"), dict) else {}

        if element_type == "pos":
            point = self._resolve_point({"x": config.get("x"), "y": config.get("y")}) or self._resolve_point(selector_value)
            if point is None:
                return None
            return ResolvedTarget(kind="point", description=f"element:{element.get('name')}", center=point)

        if element_type == "region":
            bounds = self._resolve_bounds(
                {
                    "x1": config.get("x1"),
                    "y1": config.get("y1"),
                    "x2": config.get("x2"),
                    "y2": config.get("y2"),
                }
            ) or self._resolve_bounds(selector_value)
            if bounds is None:
                return None
            return ResolvedTarget(
                kind="region",
                description=f"element:{element.get('name')}",
                bounds=bounds,
                center=self._center_of(bounds),
            )

        if element_type == "image" or selector_type == "image":
            image_path = str(element.get("image_path") or config.get("image_path") or selector_value or "").strip()
            return self._resolve_image_target(
                image_path=image_path,
                config=config,
                label=str(element.get("name") or image_path or "image"),
                allow_fallback=allow_image_position_fallback,
            )

        if selector_type in {"text", "id", "resource-id", "desc", "content-desc", "accessibility_id", "class", "xpath"}:
            value = str(selector_value or "").strip()
            if not value:
                return None
            return self._resolve_ui_target(selector_type, value, element)

        return None

    def _resolve_image_target(
        self,
        *,
        image_path: str,
        config: dict[str, Any],
        label: str,
        allow_fallback: bool,
    ) -> ResolvedTarget | None:
        if not image_path:
            return None

        crop_bounds = self._resolve_bounds(config.get("crop_region")) or self._resolve_bounds(
            {
                "x1": config.get("x1"),
                "y1": config.get("y1"),
                "x2": config.get("x2"),
                "y2": config.get("y2"),
            }
        )
        threshold = float(config.get("threshold") or 0.7)
        search_full_screen = bool(config.get("search_full_screen", True))

        if crop_bounds is None:
            point = self._resolve_point({"x": config.get("x"), "y": config.get("y")})
            if point is not None:
                crop_bounds = (point[0], point[1], point[0], point[1])

        similarity = None
        if crop_bounds is not None:
            similarity = self._match_image_region(
                image_path=image_path,
                bounds=crop_bounds,
                threshold=threshold,
                rgb=bool(config.get("rgb")),
            )
            if similarity is not None and similarity >= threshold:
                return ResolvedTarget(
                    kind="image",
                    description=f"image:{label}",
                    bounds=crop_bounds,
                    center=self._center_of(crop_bounds),
                    similarity=similarity,
                )

        if search_full_screen:
            matched = self._match_image_template(
                image_path=image_path,
                threshold=threshold,
                rgb=bool(config.get("rgb")),
            )
            if matched is not None:
                bounds, similarity = matched
                return ResolvedTarget(
                    kind="image",
                    description=f"image:{label}",
                    bounds=bounds,
                    center=self._center_of(bounds),
                    similarity=similarity,
                )

        if crop_bounds is not None and allow_fallback:
            return ResolvedTarget(
                kind="image",
                description=f"image:{label}",
                bounds=crop_bounds,
                center=self._center_of(crop_bounds),
                similarity=similarity,
                used_fallback=True,
            )
        return None

    def _resolve_ui_target(self, selector_type: str, selector_value: str, step: dict[str, Any]) -> ResolvedTarget | None:
        root = self._dump_ui_root()
        matches: list[ET.Element] = []
        match_mode = str(step.get("match_mode") or "exact").strip().lower()
        selector_type = selector_type.lower()

        if selector_type in {"id", "resource-id"}:
            matches = self._find_nodes_by_attribute(root, "resource-id", selector_value, match_mode)
        elif selector_type == "text":
            matches = self._find_nodes_by_text(root, selector_value, match_mode)
        elif selector_type in {"desc", "content-desc", "accessibility_id"}:
            matches = self._find_nodes_by_attribute(root, "content-desc", selector_value, match_mode)
        elif selector_type == "class":
            matches = self._find_nodes_by_attribute(root, "class", selector_value, match_mode)
        elif selector_type == "xpath":
            xpath = selector_value if selector_value.startswith(".") else f".{selector_value}" if selector_value.startswith("//") else selector_value
            matches = list(root.findall(xpath))

        match_index = int(step.get("match_index") or 0)
        if not matches or match_index >= len(matches):
            return None

        node = matches[match_index]
        bounds = self._parse_node_bounds(node.attrib.get("bounds", ""))
        return ResolvedTarget(
            kind="ui",
            description=f"{selector_type}={selector_value}",
            bounds=bounds,
            center=self._center_of(bounds) if bounds else None,
        )

    def _find_nodes_by_text(self, root: ET.Element, selector_value: str, match_mode: str) -> list[ET.Element]:
        matches: list[ET.Element] = []
        for node in root.iter():
            if node.tag != "node":
                continue
            for attribute in ("text", "content-desc"):
                value = node.attrib.get(attribute, "")
                if self._matches(value, selector_value, match_mode):
                    matches.append(node)
                    break
        return matches

    def _find_nodes_by_attribute(
        self,
        root: ET.Element,
        attribute_name: str,
        selector_value: str,
        match_mode: str,
    ) -> list[ET.Element]:
        matches: list[ET.Element] = []
        for node in root.iter():
            if node.tag != "node":
                continue
            value = node.attrib.get(attribute_name, "")
            if self._matches(value, selector_value, match_mode):
                matches.append(node)
        return matches

    def _matches(self, value: str, selector_value: str, match_mode: str) -> bool:
        if match_mode == "contains":
            return selector_value in value
        if match_mode == "endswith":
            return value.endswith(selector_value)
        return value == selector_value

    def _dump_ui_root(self) -> ET.Element:
        xml_text = dump_device_ui_xml(self.adb_path, self.device_serial, timeout=max(self.default_timeout, 15))
        start_index = xml_text.find("<?xml")
        if start_index < 0:
            start_index = xml_text.find("<hierarchy")
        if start_index > 0:
            xml_text = xml_text[start_index:]
        return ET.fromstring(xml_text)

    def _match_image_region(
        self,
        *,
        image_path: str,
        bounds: tuple[int, int, int, int],
        threshold: float,
        rgb: bool,
    ) -> float | None:
        if Image is None or ImageChops is None or ImageStat is None:
            return None

        asset_path = self._resolve_asset_path(image_path)
        if asset_path is None or not asset_path.exists():
            return None

        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        with Image.open(io.BytesIO(screenshot_bytes)) as screenshot, Image.open(asset_path) as template:
            screenshot = screenshot.convert("RGB" if rgb else "L")
            template = template.convert("RGB" if rgb else "L")

            x1, y1, x2, y2 = bounds
            width = max(x2 - x1, 1)
            height = max(y2 - y1, 1)
            if x1 < 0 or y1 < 0 or x1 + width > screenshot.width or y1 + height > screenshot.height:
                return None

            current = screenshot.crop((x1, y1, x1 + width, y1 + height))
            if current.size != template.size:
                current = current.resize(template.size)

            diff = ImageChops.difference(current, template)
            rms_values = ImageStat.Stat(diff).rms
            if isinstance(rms_values, list):
                rms = sum(rms_values) / len(rms_values)
            else:
                rms = float(rms_values)
            similarity = max(0.0, 1.0 - rms / 255.0)
            return similarity if similarity >= 0 else threshold

    def _match_image_template(
        self,
        *,
        image_path: str,
        threshold: float,
        rgb: bool,
    ) -> tuple[tuple[int, int, int, int], float] | None:
        if cv2 is None or np is None:
            return None

        asset_path = self._resolve_asset_path(image_path)
        if asset_path is None or not asset_path.exists():
            return None

        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        screenshot_array = np.frombuffer(screenshot_bytes, dtype=np.uint8)
        template_array = np.frombuffer(asset_path.read_bytes(), dtype=np.uint8)
        screenshot = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)
        template = cv2.imdecode(template_array, cv2.IMREAD_COLOR)
        if screenshot is None or template is None:
            return None

        if not rgb:
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        screenshot_height, screenshot_width = screenshot.shape[:2]
        template_height, template_width = template.shape[:2]
        if screenshot_width < template_width or screenshot_height < template_height:
            return None

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
        similarity = float(max_val)
        if similarity < threshold:
            return None

        x1, y1 = int(max_loc[0]), int(max_loc[1])
        bounds = (x1, y1, x1 + int(template_width), y1 + int(template_height))
        return bounds, similarity

    def _resolve_asset_path(self, image_path: str) -> Path | None:
        cleaned = str(image_path or "").replace("\\", "/").strip().lstrip("/")
        if not cleaned:
            return None
        candidate = (self.assets_root / cleaned).resolve()
        try:
            candidate.relative_to(self.assets_root)
        except ValueError:
            return None
        return candidate

    def _resolve_point(self, value: Any) -> tuple[int, int] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            x = value.get("x")
            y = value.get("y")
            if x is None or y is None:
                return None
            return int(float(x)), int(float(y))
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return int(float(value[0])), int(float(value[1]))
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                return int(float(parts[0])), int(float(parts[1]))
        return None

    def _resolve_bounds(self, value: Any) -> tuple[int, int, int, int] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            if {"x1", "y1", "x2", "y2"} <= set(value) and all(value.get(key) is not None for key in ("x1", "y1", "x2", "y2")):
                return (
                    int(float(value["x1"])),
                    int(float(value["y1"])),
                    int(float(value["x2"])),
                    int(float(value["y2"])),
                )
            if {"x", "y", "width", "height"} <= set(value) and all(
                value.get(key) is not None for key in ("x", "y", "width", "height")
            ):
                x = int(float(value["x"]))
                y = int(float(value["y"]))
                width = int(float(value["width"]))
                height = int(float(value["height"]))
                return (x, y, x + width, y + height)
        if isinstance(value, (list, tuple)) and len(value) >= 4:
            return tuple(int(float(item)) for item in value[:4])  # type: ignore[return-value]
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            if len(parts) >= 4 and all(parts[:4]):
                return tuple(int(float(item)) for item in parts[:4])  # type: ignore[return-value]
        return None

    def _parse_node_bounds(self, value: str) -> tuple[int, int, int, int] | None:
        match = BOUNDS_PATTERN.search(value or "")
        if match is None:
            return None
        return tuple(int(item) for item in match.groups())  # type: ignore[return-value]

    def _center_of(self, bounds: tuple[int, int, int, int] | None) -> tuple[int, int] | None:
        if bounds is None:
            return None
        x1, y1, x2, y2 = bounds
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _resolve_target_if_available(self, step: dict[str, Any]) -> ResolvedTarget | None:
        try:
            return self._resolve_target(step, allow_image_position_fallback=False)
        except Exception:
            return None

    def _tap_resolved_target(self, target: ResolvedTarget, *, step_name: str) -> tuple[int, int]:
        if target.center is None:
            raise ValueError(f"Unable to resolve click point for step '{step_name or 'unnamed'}'")
        x, y = target.center
        tap_device(self.adb_path, self.device_serial, x, y)
        return x, y

    def _build_target_step(self, step: dict[str, Any], *, prefix: str) -> dict[str, Any]:
        config = {}
        for field in ("threshold", "crop_region", "x1", "y1", "x2", "y2", "x", "y", "rgb", "search_full_screen"):
            prefixed_key = f"{prefix}_{field}"
            if step.get(prefixed_key) not in (None, ""):
                config[field] = step.get(prefixed_key)

        return {
            "name": step.get("name"),
            "element_id": step.get(f"{prefix}_element_id"),
            "selector_type": step.get(f"{prefix}_selector_type"),
            "selector": step.get(f"{prefix}_selector"),
            "selector_value": step.get(f"{prefix}_selector_value"),
            "image_path": step.get(f"{prefix}_image_path"),
            "match_mode": step.get(f"{prefix}_match_mode") or step.get("match_mode"),
            "match_index": step.get(f"{prefix}_match_index") or step.get("match_index"),
            "config": config,
        }

    def _get_screen_size(self) -> tuple[int, int]:
        if Image is None:
            return (1080, 1920)
        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        with Image.open(io.BytesIO(screenshot_bytes)) as screenshot:
            return screenshot.size

    def _default_swipe_points(self, direction: str) -> tuple[tuple[int, int], tuple[int, int]]:
        width, height = self._get_screen_size()
        current_direction = str(direction or "up").strip().lower()
        if current_direction == "down":
            return ((width // 2, int(height * 0.3)), (width // 2, int(height * 0.7)))
        if current_direction == "left":
            return ((int(width * 0.7), height // 2), (int(width * 0.3), height // 2))
        if current_direction == "right":
            return ((int(width * 0.3), height // 2), (int(width * 0.7), height // 2))
        return ((width // 2, int(height * 0.7)), (width // 2, int(height * 0.3)))

    def _run_assertion(self, step: dict[str, Any]) -> str:
        assert_type = str(step.get("assert_type") or "").strip().lower()
        if not assert_type:
            assert_type = "exists" if self._step_has_target(step) else "condition"

        if assert_type in {"text", "number", "regex", "range"} and self._uses_ocr_region(step):
            return self._run_ocr_assertion(step, assert_type)

        if assert_type == "image":
            return self._run_image_assertion(step)

        if assert_type in {"exists", "not_exists"}:
            expected_exists = bool(step.get("expected_exists", assert_type == "exists"))
            return self._assert_target_exists(step, expected_exists)

        if assert_type == "range":
            actual_value = self._resolve_assert_subject(step)
            try:
                numeric_value = float(actual_value)
            except (TypeError, ValueError) as exc:
                raise AssertionError(f"Range assertion requires a numeric value, got {actual_value!r}") from exc
            min_value = step.get("min")
            max_value = step.get("max")
            if min_value is not None and numeric_value < float(self._render_value(min_value)):
                raise AssertionError(f"Range assertion failed: {numeric_value} < {min_value}")
            if max_value is not None and numeric_value > float(self._render_value(max_value)):
                raise AssertionError(f"Range assertion failed: {numeric_value} > {max_value}")
            return f"Range assertion passed: {numeric_value}"

        actual_value = self._resolve_assert_subject(step)
        if assert_type == "regex":
            pattern = str(self._render_value(step.get("expected") or step.get("right") or "")).strip()
            if not pattern:
                raise ValueError("Regex assertion requires expected or right")
            if re.search(pattern, str(actual_value)) is None:
                raise AssertionError(f"Regex assertion failed: pattern {pattern!r} not found in {actual_value!r}")
            return f"Regex assertion passed: {pattern!r}"

        operator = self._normalize_assert_operator(
            str(step.get("operator") or step.get("match_mode") or step.get("assert_type") or ""),
            has_target=self._step_has_target(step),
        )
        expected_value = self._render_value(step.get("expected") if "expected" in step else step.get("right"))
        if operator in {"truthy", "falsy", "exists", "not_exists"}:
            condition = self._evaluate_condition(actual_value, operator, expected_value)
        else:
            condition = self._evaluate_condition(actual_value, operator, expected_value)
        if not condition:
            raise AssertionError(
                f"Assertion failed: left={actual_value!r}, operator={operator!r}, right={expected_value!r}"
            )
        return f"Assertion passed: {actual_value!r} {operator} {expected_value!r}"

    def _resolve_assert_subject(self, step: dict[str, Any]) -> Any:
        source = str(step.get("source") or "").strip()
        if source:
            return self._resolve_value_reference(source)
        if "actual" in step:
            return self._render_value(step.get("actual"))
        if "left" in step:
            return self._render_value(step.get("left"))
        if "value" in step:
            return self._render_value(step.get("value"))
        if self._step_has_target(step):
            target = self._resolve_target(step, allow_image_position_fallback=False)
            return target.description
        return self._render_value(step.get("expected"))

    def _normalize_assert_operator(self, value: str, *, has_target: bool) -> str:
        operator = str(value or "").strip().lower()
        if operator in {"", "text", "number", "condition", "value"}:
            return "exists" if has_target else "=="
        mapping = {
            "exact": "==",
            "equals": "==",
            "contains": "contains",
            "regex": "regex",
            "match": "regex",
        }
        return mapping.get(operator, operator)

    def _assert_target_exists(self, step: dict[str, Any], expected_exists: bool) -> str:
        target = self._resolve_target_if_available(step)
        exists = target is not None
        if exists != expected_exists:
            if expected_exists:
                raise AssertionError("Expected target to exist, but it was not found")
            raise AssertionError("Expected target to be absent, but it exists")
        if target is not None:
            return f"Existence assertion passed: {target.description}"
        return "Existence assertion passed: target absent"

    def _run_image_assertion(self, step: dict[str, Any]) -> str:
        expected_exists = bool(step.get("expected_exists", True))
        image_step = dict(step)
        image_path = str(
            self._render_value(
                step.get("expected")
                or step.get("image_path")
                or step.get("selector")
                or step.get("selector_value")
                or ""
            )
        ).strip()

        if not self._step_has_target(image_step):
            if not image_path:
                raise ValueError("Image assertion requires expected, image_path, or an image selector")
            asset_path = self._resolve_asset_path(image_path)
            if asset_path is None or not asset_path.exists():
                raise ValueError(f"Image assertion asset does not exist: {image_path}")
            image_step.update(
                {
                    "selector_type": "image",
                    "selector": image_path,
                    "image_path": image_path,
                }
            )

        target = self._resolve_target_if_available(image_step)
        exists = target is not None
        if exists != expected_exists:
            if expected_exists:
                raise AssertionError(f"Image assertion failed: {image_path or 'target'} was not found")
            raise AssertionError(f"Image assertion failed: {image_path or 'target'} unexpectedly exists")

        if target is not None:
            detail = f"Image assertion passed: {target.description}"
            if target.similarity is not None:
                detail += f", similarity={target.similarity:.2f}"
            return detail
        return "Image assertion passed: target absent"

    def _uses_ocr_region(self, step: dict[str, Any]) -> bool:
        if step.get("ocr_selector") not in (None, ""):
            return True
        selector_type = str(step.get("selector_type") or "").strip().lower()
        selector_value = step.get("selector")
        if selector_value in (None, ""):
            selector_value = step.get("selector_value")
        return selector_type == "region" and selector_value not in (None, "")

    def _run_ocr_assertion(self, step: dict[str, Any], assert_type: str) -> str:
        ocr_region = self._parse_ocr_region(step)

        if assert_type in {"text", "regex"}:
            actual_text = self._ocr_recognize_text(ocr_region)
            if assert_type == "regex":
                pattern = str(self._render_value(step.get("expected") if "expected" in step else step.get("right")) or "").strip()
                if not pattern:
                    raise ValueError("Regex assertion requires expected or right")
                if re.search(pattern, actual_text) is None:
                    raise AssertionError(f"Regex assertion failed: pattern {pattern!r} not found in {actual_text!r}")
                return f"Regex OCR assertion passed: {pattern!r}"

            expected_text = str(self._render_value(step.get("expected") if "expected" in step else step.get("right")) or "")
            match_mode = str(step.get("match_mode") or step.get("operator") or "contains").strip().lower() or "contains"
            if match_mode == "exact":
                matched = actual_text == expected_text
            elif match_mode == "contains":
                matched = expected_text in actual_text
            elif match_mode == "regex":
                matched = re.search(expected_text, actual_text) is not None
            else:
                raise ValueError(f"Unsupported OCR text match mode: {match_mode}")
            if not matched:
                raise AssertionError(
                    f"OCR text assertion failed: expected={expected_text!r}, mode={match_mode}, actual={actual_text!r}"
                )
            return f"OCR text assertion passed: {actual_text!r}"

        actual_number = self._ocr_recognize_number(ocr_region)
        if assert_type == "number":
            expected_value = self._coerce_numeric_value(
                self._render_value(step.get("expected") if "expected" in step else step.get("right")),
                label="expected",
            )
            if float(actual_number) != float(expected_value):
                raise AssertionError(f"OCR number assertion failed: expected {expected_value}, got {actual_number}")
            return f"OCR number assertion passed: {actual_number}"

        min_value = step.get("min")
        max_value = step.get("max")
        if min_value is not None and float(actual_number) < self._coerce_numeric_value(self._render_value(min_value), label="min"):
            raise AssertionError(f"OCR range assertion failed: {actual_number} < {min_value}")
        if max_value is not None and float(actual_number) > self._coerce_numeric_value(self._render_value(max_value), label="max"):
            raise AssertionError(f"OCR range assertion failed: {actual_number} > {max_value}")
        return f"OCR range assertion passed: {actual_number}"

    def _parse_ocr_region(self, step: dict[str, Any]) -> tuple[int, int, int, int]:
        selector = step.get("ocr_selector")
        if selector in (None, ""):
            selector = step.get("selector")
        if selector in (None, ""):
            selector = step.get("selector_value")

        selector_type = str(step.get("ocr_selector_type") or step.get("selector_type") or "region").strip().lower()
        if selector_type != "region":
            raise ValueError(f"OCR only supports region selectors, got {selector_type}")

        bounds = self._resolve_bounds(selector)
        if bounds is None:
            raise ValueError(f"Invalid OCR region: {selector!r}")
        return bounds

    def _get_ocr_helper(self):
        if self._ocr_helper is None:
            self._ocr_helper = get_ocr_helper()
        return self._ocr_helper

    def _ocr_recognize_text(self, region: tuple[int, int, int, int]) -> str:
        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        return self._get_ocr_helper().recognize_region_text(screenshot_bytes, region)

    def _ocr_recognize_number(self, region: tuple[int, int, int, int]) -> int | float:
        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        return self._get_ocr_helper().recognize_region_number(screenshot_bytes, region)

    def _normalize_expected_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return [self._render_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._render_value(item) for item in value]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [self._render_value(item) for item in parsed]
            return [item.strip() for item in text.split(",") if item.strip()]
        return [self._render_value(value)]

    def _poll_foreach_assert_match(
        self,
        *,
        ocr_region: tuple[int, int, int, int],
        expected_values: list[Any],
        assert_type: str,
        match_mode: str,
        timeout_seconds: float,
    ) -> tuple[bool, Any]:
        deadline = time.time() + timeout_seconds
        last_value: Any = None

        while True:
            if assert_type == "number":
                last_value = self._ocr_recognize_number(ocr_region)
            else:
                last_value = self._ocr_recognize_text(ocr_region)

            if self._ocr_value_matches(last_value, expected_values, assert_type=assert_type, match_mode=match_mode):
                return True, last_value

            if timeout_seconds <= 0 or time.time() >= deadline:
                return False, last_value
            self._sleep_with_stop(min(DEFAULT_POLL_INTERVAL, max(deadline - time.time(), 0.0)))

    def _ocr_value_matches(self, actual_value: Any, expected_values: list[Any], *, assert_type: str, match_mode: str) -> bool:
        if assert_type == "number":
            actual_number = self._coerce_numeric_value(actual_value, label="actual")
            for expected in expected_values:
                if float(actual_number) == float(self._coerce_numeric_value(expected, label="expected")):
                    return True
            return False

        actual_text = str(actual_value or "")
        for expected in expected_values:
            expected_text = str(expected or "")
            if assert_type == "regex" or match_mode == "regex":
                if re.search(expected_text, actual_text) is not None:
                    return True
                continue
            if match_mode == "exact":
                if actual_text == expected_text:
                    return True
                continue
            if expected_text in actual_text:
                return True
        return False

    def _coerce_numeric_value(self, value: Any, *, label: str) -> int | float:
        text = str(value if value is not None else "").strip()
        normalized = text.replace(",", "").replace(" ", "")
        normalized = re.sub(r"[^0-9.\-]+", "", normalized)
        if normalized in {"", "-", ".", "-."}:
            raise ValueError(f"{label} value is not numeric: {value!r}")
        number = float(normalized)
        if number.is_integer():
            return int(number)
        return number

    def _get_element(self, element_ref: Any) -> dict[str, Any] | None:
        key = str(element_ref or "").strip()
        if not key:
            return None
        if key in self._element_cache:
            return self._element_cache[key]

        with connection() as conn:
            row = None
            if key.isdigit():
                row = fetch_one(conn, "SELECT * FROM elements WHERE id = ? AND project_id = ?", (int(key), self.project_id))
            if row is None:
                row = fetch_one(conn, "SELECT * FROM elements WHERE project_id = ? AND name = ?", (self.project_id, key))

        if row is not None:
            row["config"] = json_loads(row.get("config"), {})
            row["tags"] = json_loads(row.get("tags"), [])
            self._element_cache[key] = row
            self._element_cache[str(row["id"])] = row
            self._element_cache[str(row["name"])] = row
        else:
            self._element_cache[key] = None
        return row

    def _get_custom_component(self, component_type: str) -> dict[str, Any] | None:
        cache_key = str(component_type or "").strip()
        if not cache_key:
            return None
        if cache_key in self._custom_component_cache:
            return self._custom_component_cache[cache_key]

        with connection() as conn:
            row = fetch_one(conn, "SELECT * FROM custom_components WHERE type = ? AND enabled = 1", (cache_key,))

        if row is not None:
            row["default_config"] = json_loads(row.get("default_config"), {})
            row["steps"] = json_loads(row.get("steps_json"), [])
        self._custom_component_cache[cache_key] = row
        return row

    def _get_child_steps(self, step: dict[str, Any]) -> list[dict[str, Any]] | None:
        action = normalize_action(step)
        if action in FLOW_CONTROL_ACTIONS:
            return None

        inline_steps = step.get("steps")
        if isinstance(inline_steps, list):
            return [item for item in inline_steps if isinstance(item, dict)]

        component_type = str(step.get("component_type") or step.get("type") or step.get("action") or "").strip()
        if action in SUPPORTED_BUILTIN_ACTIONS:
            return None

        component = self._get_custom_component(component_type)
        if component is None:
            if str(step.get("kind") or "").lower() == "custom":
                return []
            return None
        return [item for item in component.get("steps", []) if isinstance(item, dict)]

    def _extract_component_context(self, step: dict[str, Any]) -> dict[str, Any]:
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        context = {key: value for key, value in config.items() if key not in META_KEYS}

        component_type = str(step.get("component_type") or step.get("type") or step.get("action") or "").strip()
        component = self._get_custom_component(component_type)
        if component is not None:
            default_config = component.get("default_config")
            if isinstance(default_config, dict):
                merged = dict(default_config)
                merged.update(context)
                context = merged
        return context

    def _merge_config(self, step: dict[str, Any]) -> dict[str, Any]:
        merged = dict(step)
        config = merged.get("config")
        if isinstance(config, dict):
            for key, value in config.items():
                merged.setdefault(key, value)
        return merged

    def _load_variables(self, variables: list[dict[str, Any]]) -> None:
        for item in variables:
            if not isinstance(item, dict):
                continue
            variable_name = str(item.get("name") or "").strip()
            if not variable_name:
                continue
            scope = str(item.get("scope") or "local").strip().lower()
            self._set_variable(variable_name, item.get("value"), scope)

    def _set_variable(self, name: str, value: Any, scope: str) -> None:
        if scope == "global":
            self.global_context[name] = value
            return
        self.local_scopes[-1][name] = value

    def _remember_output(self, name: str, value: Any) -> None:
        clean_name = str(name or "").strip()
        if clean_name:
            self.outputs[clean_name] = value

    @contextmanager
    def _pushed_scope(self, values: dict[str, Any]) -> Iterator[None]:
        self.local_scopes.append(dict(values))
        try:
            yield
        finally:
            self.local_scopes.pop()

    def _resolve_variable(self, name: str) -> Any:
        clean_name = str(name or "").strip()
        for scope in reversed(self.local_scopes):
            if clean_name in scope:
                return scope[clean_name]
        if clean_name in self.global_context:
            return self.global_context[clean_name]
        if clean_name in self.outputs:
            return self.outputs[clean_name]
        return None

    def _resolve_value_reference(self, reference: str) -> Any:
        text = str(reference or "").strip()
        if not text:
            return None

        direct_value = self._resolve_variable(text)
        if direct_value is not None:
            return direct_value

        root_name = text
        nested_path = ""
        if "." in text:
            first, rest = text.split(".", 1)
            if first in {"local", "global", "output", "outputs"}:
                if first == "global":
                    base = self.global_context
                elif first == "local":
                    base = self.local_scopes[-1]
                else:
                    base = self.outputs
                return self._extract_value_by_path(base, rest)
            root_name = first
            nested_path = rest

        root_value = self._resolve_variable(root_name)
        if root_value is None:
            return None
        if not nested_path:
            return root_value
        return self._extract_value_by_path(root_value, nested_path)

    def _extract_value_by_path(self, source: Any, path: str) -> Any:
        current = source
        for key in self._parse_path(path):
            if isinstance(current, dict):
                if key not in current:
                    raise ValueError(f"Path '{path}' is missing key '{key}'")
                current = current[key]
                continue
            if isinstance(current, (list, tuple)):
                try:
                    index = int(key)
                    current = current[index]
                except (TypeError, ValueError, IndexError) as exc:
                    raise ValueError(f"Path '{path}' has invalid index '{key}'") from exc
                continue
            raise ValueError(f"Path '{path}' cannot continue at '{key}'")
        return current

    @staticmethod
    def _parse_path(path: str) -> list[str]:
        keys: list[str] = []
        for part in str(path or "").split("."):
            if "[" in part:
                base, rest = part.split("[", 1)
                if base:
                    keys.append(base)
                for idx_part in rest.split("["):
                    idx_part = idx_part.rstrip("]")
                    if idx_part:
                        keys.append(idx_part)
                continue
            if part:
                keys.append(part)
        return keys

    def _parse_response_body(self, response_bytes: bytes, headers: dict[str, Any], response_type: str) -> Any:
        normalized_type = str(response_type or "auto").strip().lower()
        content_type = str(headers.get("Content-Type") or headers.get("content-type") or "").lower()
        if normalized_type == "binary":
            return base64.b64encode(response_bytes).decode("ascii")

        decoded_text = response_bytes.decode("utf-8", errors="replace")
        if normalized_type == "text":
            return decoded_text

        if normalized_type == "json" or "json" in content_type or "javascript" in content_type:
            try:
                return json.loads(decoded_text)
            except json.JSONDecodeError:
                if normalized_type == "json":
                    raise ValueError("Response body is not valid JSON")
        return decoded_text

    def _render_value(self, value: Any) -> Any:
        if isinstance(value, str):
            full_match = FULL_VARIABLE_PATTERN.match(value)
            if full_match:
                variable_name = full_match.group(1) or full_match.group(2) or ""
                variable_value = self._resolve_variable(variable_name)
                return "" if variable_value is None else variable_value

            def replace(match: re.Match[str]) -> str:
                variable_name = match.group(1) or match.group(2) or ""
                variable_value = self._resolve_variable(variable_name)
                return "" if variable_value is None else str(variable_value)

            return VARIABLE_PATTERN.sub(replace, value)
        if isinstance(value, dict):
            return {key: self._render_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render_value(item) for item in value]
        return value

    def _save_screenshot(self, label: str) -> str | None:
        if self.artifact_dir is None:
            return None
        screenshot_bytes = capture_device_screenshot(self.adb_path, self.device_serial)
        filename = f"{sanitize_name(label)}-{int(time.time() * 1000)}.png"
        path = self.artifact_dir / filename
        path.write_bytes(screenshot_bytes)
        return self._relative_artifact_path(path)

    def _relative_artifact_path(self, path: Path) -> str:
        if self.report_dir is None:
            return str(path)
        try:
            return str(path.resolve().relative_to(self.report_dir.resolve())).replace("\\", "/")
        except ValueError:
            return str(path.resolve())

    def _sleep_with_stop(self, seconds: float) -> None:
        remaining = max(float(seconds), 0.0)
        while remaining > 0:
            self._assert_not_stopped()
            interval = min(DEFAULT_POLL_INTERVAL, remaining)
            time.sleep(interval)
            remaining -= interval

    def _assert_not_stopped(self) -> None:
        if self.stop_requested and self.stop_requested():
            raise StopRequested("Execution was stopped")
