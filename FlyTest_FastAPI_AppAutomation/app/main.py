from __future__ import annotations

import base64
import hashlib
import importlib.util
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .adb import (
    AdbError,
    capture_device_screenshot,
    connect_remote_device,
    disconnect_remote_device,
    discover_devices,
    inspect_adb_environment,
)
from .access_control import (
    apply_project_scope_filter,
    bind_request_context,
    enforce_request_module_permission,
    ensure_project_access,
    ensure_row_project_access,
    reset_request_context,
    resolve_scoped_project_ids,
)
from .ai_planner import build_scene_plan, build_step_suggestion
from .asset_paths import (
    extract_project_id_from_asset_path as extract_project_id_from_element_asset_path,
    normalize_asset_path as normalize_element_asset_path,
    resolve_upload_asset_path,
)
from .database import (
    ELEMENT_UPLOADS_DIR,
    connection,
    fetch_all,
    fetch_one,
    init_storage,
    json_dumps,
    json_loads,
    utc_now,
)
from .execution_runtime import AppFlowExecutor, StepExecutionError, StopRequested
from .extended_routes import router as extended_router
from .reporting import ensure_reports_root, get_report_content_type, resolve_report_file, write_execution_report
from .scheduler import app_scheduler
from .schemas import (
    DeviceConnectPayload,
    DeviceUpdatePayload,
    ElementPayload,
    ExecuteTestCasePayload,
    ImageCategoryPayload,
    PackagePayload,
    ScenePlanPayload,
    SettingsPayload,
    StepSuggestionPayload,
    TestCasePayload,
)
from .security import extract_bearer_token, should_skip_auth, validate_request_token

init_storage()


@asynccontextmanager
async def lifespan(_: FastAPI):
    app_scheduler.start()
    try:
        yield
    finally:
        app_scheduler.stop()


app = FastAPI(title="FlyTest APP Automation Service", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def require_app_automation_auth(request: Request, call_next):
    if should_skip_auth(request):
        return await call_next(request)

    context_tokens: dict[str, Any] | None = None
    try:
        raw_token = extract_bearer_token(request)
        request.state.auth = validate_request_token(request, token=raw_token)
        context_tokens = bind_request_context(request.state.auth, raw_token)
        await run_in_threadpool(enforce_request_module_permission, request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    try:
        return await call_next(request)
    finally:
        reset_request_context(context_tokens)


def success(data: Any = None, message: str = "success", code: int = 200) -> dict[str, Any]:
    return {"status": "success", "code": code, "message": message, "data": data}


def get_settings(conn) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM settings WHERE id = 1")
    if row is None:
        raise HTTPException(status_code=500, detail="APP 自动化配置初始化失败")
    row["auto_discover_on_open"] = bool(row["auto_discover_on_open"])
    return row


def build_adb_diagnostics(settings: dict[str, Any]) -> dict[str, Any]:
    diagnostics = inspect_adb_environment(settings.get("adb_path", "adb"))
    diagnostics["checked_at"] = utc_now()
    return diagnostics


def resolve_distribution_version(*distribution_names: str) -> str:
    for distribution_name in distribution_names:
        try:
            return version(distribution_name)
        except PackageNotFoundError:
            continue
    return ""


def build_runtime_capabilities() -> dict[str, Any]:
    dependency_definitions = [
        ("EasyOCR", "easyocr", ("easyocr",)),
        ("NumPy", "numpy", ("numpy",)),
        ("Pillow", "PIL", ("Pillow",)),
        ("OpenCV", "cv2", ("opencv-python", "opencv-python-headless")),
    ]

    dependencies: list[dict[str, Any]] = []
    installed_modules: set[str] = set()
    for label, module_name, distributions in dependency_definitions:
        installed = importlib.util.find_spec(module_name) is not None
        if installed:
            installed_modules.add(module_name)
        dependencies.append(
            {
                "name": label,
                "module_name": module_name,
                "installed": installed,
                "version": resolve_distribution_version(*distributions) if installed else "",
            }
        )

    def capability(
        key: str,
        label: str,
        required_modules: list[str],
        success_message: str,
        fallback_message: str,
    ) -> dict[str, Any]:
        missing = [module_name for module_name in required_modules if module_name not in installed_modules]
        ready = not missing
        return {
            "key": key,
            "label": label,
            "ready": ready,
            "dependencies": required_modules,
            "missing": missing,
            "message": success_message if ready else f"{fallback_message}：缺少 {', '.join(missing)}",
        }

    capabilities = [
        capability(
            "ocr_assertions",
            "OCR 断言",
            ["easyocr", "numpy", "PIL"],
            "OCR 文本、数字、范围、正则断言已就绪",
            "OCR 断言暂不可用",
        ),
        capability(
            "foreach_assert",
            "循环点击断言",
            ["easyocr", "numpy", "PIL"],
            "foreach_assert 已可执行",
            "foreach_assert 暂不可用",
        ),
        capability(
            "template_matching",
            "全屏模板找图",
            ["cv2", "numpy"],
            "全屏模板找图已就绪",
            "全屏模板找图暂不可用",
        ),
        capability(
            "basic_image_matching",
            "基础图片比对",
            ["PIL"],
            "裁剪区域图片比对已就绪",
            "基础图片比对暂不可用",
        ),
    ]

    return {
        "checked_at": utc_now(),
        "python_version": sys.version.split()[0],
        "install_command": "python -m pip install easyocr numpy pillow opencv-python",
        "dependencies": dependencies,
        "capabilities": capabilities,
    }


def serialize_device(row: dict[str, Any]) -> dict[str, Any]:
    row["device_specs"] = json_loads(row.get("device_specs"), {})
    row["is_locked"] = row.get("status") == "locked"
    return row


def serialize_element(row: dict[str, Any]) -> dict[str, Any]:
    row["tags"] = json_loads(row.get("tags"), [])
    row["config"] = json_loads(row.get("config"), {})
    row["is_active"] = bool(row.get("is_active"))
    return row


def normalize_category_name(category: str) -> str:
    name = (category or "common").strip()
    if not re.fullmatch(r"[\w\-\u4e00-\u9fa5]+", name):
        raise HTTPException(status_code=400, detail="图片分类名称不合法")
    return name


def get_element_asset_root() -> Path:
    root = ELEMENT_UPLOADS_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_asset_path(asset_path: str) -> str:
    return normalize_element_asset_path(asset_path)


def resolve_element_asset_path(asset_path: str) -> Path:
    cleaned = normalize_asset_path(asset_path)
    if not cleaned:
        raise HTTPException(status_code=404, detail="元素资源不存在")

    base_root = get_element_asset_root().parent.resolve()
    candidate = (base_root / cleaned).resolve()
    try:
        candidate.relative_to(base_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="非法的元素资源路径") from exc
    return candidate


def build_element_image_path(element: dict[str, Any]) -> str:
    image_path = str(element.get("image_path") or "").strip()
    if image_path:
        return image_path

    config = element.get("config")
    if isinstance(config, str):
        config = json_loads(config, {})
    if isinstance(config, dict):
        config_image_path = str(config.get("image_path") or "").strip()
        if config_image_path:
            return config_image_path

    element_type = str(element.get("element_type") or "").strip().lower()
    selector_type = str(element.get("selector_type") or "").strip().lower()
    if element_type == "image" or selector_type == "image":
        return str(element.get("selector_value") or "").strip()
    return ""


def build_project_asset_dir(category_name: str, project_id: int) -> Path:
    return get_element_asset_root() / category_name / f"project-{project_id}"


def extract_project_id_from_asset_path(asset_path: str) -> int | None:
    parts = [segment for segment in normalize_asset_path(asset_path).split("/") if segment]
    for segment in parts:
        if not segment.startswith("project-"):
            continue
        project_suffix = segment.removeprefix("project-")
        if project_suffix.isdigit():
            return int(project_suffix)
    return None


def extract_image_category_from_asset_path(asset_path: str) -> str:
    parts = [segment for segment in normalize_asset_path(asset_path).split("/") if segment]
    if parts and parts[0] == "elements":
        parts = parts[1:]
    if not parts:
        return ""

    category = parts[0]
    if category.startswith("project-"):
        return ""
    return category


def asset_is_visible_to_scoped_project(conn, asset_path: str) -> bool:
    normalized_path = normalize_asset_path(asset_path)
    query = "SELECT * FROM elements WHERE 1 = 1"
    params: list[Any] = []
    query, params = apply_project_scope_filter(query, params, None)
    query += " AND (image_path = ? OR selector_value = ?)"
    params.extend([normalized_path, normalized_path])
    rows = fetch_all(conn, query, params)
    return any(build_element_image_path(serialize_element(row)) == normalized_path for row in rows)


def ensure_element_asset_access(conn, asset_path: str) -> None:
    scoped_project_ids = resolve_scoped_project_ids(None)
    if scoped_project_ids is None:
        return
    if not scoped_project_ids:
        raise HTTPException(status_code=403, detail="当前用户无权访问该元素资源")

    scoped_project_id = extract_project_id_from_asset_path(asset_path)
    if scoped_project_id is not None:
        if scoped_project_id in scoped_project_ids:
            return
        raise HTTPException(status_code=403, detail="当前用户无权访问该元素资源")

    if asset_is_visible_to_scoped_project(conn, asset_path):
        return

    raise HTTPException(status_code=403, detail="当前用户无权访问该元素资源")


def resolve_element_asset_file(asset_path: str) -> Path:
    cleaned = normalize_asset_path(asset_path)
    if not cleaned:
        raise HTTPException(status_code=404, detail="Element asset not found")

    candidate = resolve_upload_asset_path(cleaned)
    if candidate is None:
        raise HTTPException(status_code=400, detail="Invalid element asset path")
    return candidate


def _collect_element_asset_references(payload: ElementPayload) -> list[str]:
    references: list[str] = []

    def add_reference(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in references:
            references.append(text)

    add_reference(payload.image_path)

    element_type = payload.element_type.strip().lower()
    selector_type = payload.selector_type.strip().lower()
    if element_type == "image" or selector_type == "image":
        add_reference(payload.selector_value)

    config = payload.config if isinstance(payload.config, dict) else {}
    add_reference(config.get("image_path"))
    return references


def ensure_element_assets_belong_to_project(
    conn,
    *,
    project_id: int,
    asset_paths: list[str],
) -> None:
    for asset_path in asset_paths:
        normalized_path = normalize_asset_path(asset_path)
        if not normalized_path:
            continue

        if resolve_upload_asset_path(normalized_path) is None:
            raise HTTPException(status_code=400, detail="Invalid element asset path")

        scoped_project_id = extract_project_id_from_asset_path(normalized_path)
        if scoped_project_id is not None:
            if scoped_project_id != project_id:
                raise HTTPException(status_code=400, detail="Element asset does not belong to the current project")
            continue

        existing_reference = fetch_one(
            conn,
            """
            SELECT id
            FROM elements
            WHERE project_id = ? AND (image_path = ? OR selector_value = ?)
            LIMIT 1
            """,
            (project_id, normalized_path, normalized_path),
        )
        if existing_reference is None:
            raise HTTPException(status_code=400, detail="Element asset does not belong to the current project")


def compute_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def find_duplicate_element_asset(
    conn,
    file_hash: str,
    *,
    project_id: int,
    exclude_element_id: int | None = None,
) -> dict[str, Any] | None:
    rows = fetch_all(
        conn,
        "SELECT * FROM elements WHERE project_id = ? AND element_type = 'image' AND is_active = 1",
        (project_id,),
    )
    for row in rows:
        if exclude_element_id is not None and int(row["id"]) == exclude_element_id:
            continue
        element = serialize_element(row)
        config = element.get("config", {})
        if isinstance(config, dict) and str(config.get("file_hash") or "") == file_hash:
            return element
    return None


def list_image_categories(project_id: int) -> list[dict[str, Any]]:
    root = get_element_asset_root()
    build_project_asset_dir("common", project_id).mkdir(parents=True, exist_ok=True)
    categories: list[dict[str, Any]] = []
    for item in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not item.is_dir():
            continue
        project_dir = build_project_asset_dir(item.name, project_id)
        if not project_dir.exists() and item.name != "common":
            continue
        file_count = sum(1 for file in project_dir.rglob("*") if file.is_file()) if project_dir.exists() else 0
        categories.append({"name": item.name, "count": file_count, "path": item.name})
    return categories


def serialize_test_case(row: dict[str, Any]) -> dict[str, Any]:
    row["ui_flow"] = json_loads(row.get("ui_flow"), {})
    row["variables"] = json_loads(row.get("variables"), [])
    row["tags"] = json_loads(row.get("tags"), [])
    return row


def serialize_execution(row: dict[str, Any]) -> dict[str, Any]:
    row["logs"] = json_loads(row.get("logs"), [])
    total_steps = int(row.get("total_steps") or 0)
    passed_steps = int(row.get("passed_steps") or 0)
    row["pass_rate"] = round(passed_steps / total_steps * 100, 1) if total_steps else 0
    return row


def ensure_package_belongs_to_project(package: dict[str, Any], project_id: int) -> None:
    package_project_id = package.get("project_id")
    if isinstance(package_project_id, str) and package_project_id.isdigit():
        package_project_id = int(package_project_id)
    if package_project_id != project_id:
        raise HTTPException(status_code=400, detail="应用包不属于当前项目")


def extract_steps(ui_flow: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(ui_flow, list):
        return [item for item in ui_flow if isinstance(item, dict)]
    if isinstance(ui_flow, dict):
        steps = ui_flow.get("steps")
        if isinstance(steps, list):
            return [item for item in steps if isinstance(item, dict)]
    return []


def append_log(
    logs: list[dict[str, Any]],
    message: str,
    level: str = "info",
    *,
    artifact: str | None = None,
) -> list[dict[str, Any]]:
    next_logs = list(logs)
    entry = {"timestamp": utc_now(), "level": level, "message": message}
    if artifact:
        entry["artifact"] = artifact
    next_logs.append(entry)
    return next_logs


def get_device_or_404(conn, device_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM devices WHERE id = ?", (device_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return serialize_device(row)


def get_package_or_404(conn, package_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM packages WHERE id = ?", (package_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="应用包不存在")
    ensure_row_project_access(row)
    return row


def get_element_or_404(conn, element_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM elements WHERE id = ?", (element_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="元素不存在")
    ensure_row_project_access(row)
    return serialize_element(row)


def get_test_case_or_404(conn, test_case_id: int) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        SELECT tc.*, p.name AS package_display_name, p.package_name AS package_name, p.activity_name AS activity_name
        FROM test_cases tc
        LEFT JOIN packages p ON p.id = tc.package_id
        WHERE tc.id = ?
        """,
        (test_case_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    ensure_row_project_access(row)
    return serialize_test_case(row)


def get_execution_or_404(conn, execution_id: int) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial
        FROM executions e
        LEFT JOIN test_cases tc ON tc.id = e.test_case_id
        LEFT JOIN devices d ON d.id = e.device_id
        WHERE e.id = ?
        """,
        (execution_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    ensure_row_project_access(row)
    return serialize_execution(row)


def upsert_device(conn, payload: dict[str, Any], preserve_lock: bool = True) -> dict[str, Any]:
    now = utc_now()
    existing = fetch_one(conn, "SELECT * FROM devices WHERE device_id = ?", (payload["device_id"],))
    if existing is None:
        conn.execute(
            """
            INSERT INTO devices (
                device_id, name, status, android_version, connection_type, ip_address, port,
                locked_by, locked_at, device_specs, description, location, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '', NULL, ?, '', '', ?, ?, ?)
            """,
            (
                payload["device_id"],
                payload.get("name", payload["device_id"]),
                payload.get("status", "available"),
                payload.get("android_version", ""),
                payload.get("connection_type", "emulator"),
                payload.get("ip_address", ""),
                payload.get("port", 5555),
                json_dumps(payload.get("device_specs", {})),
                now,
                now,
                now,
            ),
        )
        created_device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return get_device_or_404(conn, created_device_id)

    next_status = payload.get("status", existing["status"])
    if preserve_lock and existing.get("status") in {"locked", "stopping"}:
        next_status = existing["status"]

    conn.execute(
        """
        UPDATE devices
        SET name = ?, status = ?, android_version = ?, connection_type = ?, ip_address = ?, port = ?,
            device_specs = ?, last_seen_at = ?, updated_at = ?
        WHERE device_id = ?
        """,
        (
            payload.get("name", existing["name"]),
            next_status,
            payload.get("android_version", existing["android_version"]),
            payload.get("connection_type", existing["connection_type"]),
            payload.get("ip_address", existing["ip_address"]),
            payload.get("port", existing["port"]),
            json_dumps(payload.get("device_specs", json_loads(existing.get("device_specs"), {}))),
            now,
            now,
            payload["device_id"],
        ),
    )
    updated = fetch_one(conn, "SELECT * FROM devices WHERE device_id = ?", (payload["device_id"],))
    return serialize_device(updated or {})


def finish_device_lock(conn, device_id: int) -> None:
    now = utc_now()
    next_execution = fetch_one(
        conn,
        """
        SELECT triggered_by, created_at
        FROM executions
        WHERE device_id = ? AND status IN ('pending', 'running')
        ORDER BY CASE WHEN status = 'running' THEN 0 ELSE 1 END, created_at ASC, id ASC
        LIMIT 1
        """,
        (device_id,),
    )
    if next_execution is not None:
        conn.execute(
            """
            UPDATE devices
            SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                str(next_execution.get("triggered_by") or "").strip(),
                next_execution.get("created_at") or now,
                now,
                device_id,
            ),
        )
        return

    conn.execute(
        """
        UPDATE devices
        SET status = 'available', locked_by = '', locked_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (now, device_id),
    )


def _execution_is_stopped(execution_id: int) -> bool:
    with connection() as conn:
        row = fetch_one(conn, "SELECT status FROM executions WHERE id = ?", (execution_id,))
        return bool(row and row.get("status") == "stopped")


def reserve_device_for_execution(conn, device_id: int, *, locked_by: str) -> dict[str, Any]:
    device = get_device_or_404(conn, device_id)
    device_name = str(device.get("name") or device.get("device_id") or device_id)
    if device["status"] == "offline":
        raise HTTPException(status_code=409, detail=f"设备 {device_name} 当前离线，无法执行")
    if device["status"] == "stopping":
        raise HTTPException(status_code=409, detail=f"设备 {device_name} 正在停止上一个执行，请稍后再试")
    if device["status"] == "locked":
        holder = str(device.get("locked_by") or "").strip()
        detail = f"设备 {device_name} 当前正被占用，无法执行"
        if holder:
            detail = f"设备 {device_name} 当前正被 {holder} 占用，无法执行"
        raise HTTPException(status_code=409, detail=detail)

    now = utc_now()
    updated = conn.execute(
        """
        UPDATE devices
        SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ?
        WHERE id = ? AND status NOT IN ('locked', 'offline', 'stopping')
        """,
        (locked_by.strip(), now, now, device_id),
    )
    if updated.rowcount != 1:
        fresh_device = get_device_or_404(conn, device_id)
        if fresh_device["status"] == "offline":
            raise HTTPException(status_code=409, detail=f"设备 {device_name} 当前离线，无法执行")
        if fresh_device["status"] == "stopping":
            raise HTTPException(status_code=409, detail=f"设备 {device_name} 正在停止上一个执行，请稍后再试")
        holder = str(fresh_device.get("locked_by") or "").strip()
        detail = f"设备 {device_name} 当前正被占用，无法执行"
        if holder:
            detail = f"设备 {device_name} 当前正被 {holder} 占用，无法执行"
        raise HTTPException(status_code=409, detail=detail)
    return get_device_or_404(conn, device_id)


def claim_pending_execution(
    conn,
    execution_id: int,
    *,
    started_at: str,
    logs: list[dict[str, Any]],
    total_steps: int,
) -> bool:
    updated = conn.execute(
        """
        UPDATE executions
        SET status = 'running', started_at = ?, updated_at = ?, logs = ?, progress = 3,
            total_steps = ?, passed_steps = 0, failed_steps = 0, error_message = ''
        WHERE id = ? AND status = 'pending'
        """,
        (started_at, started_at, json_dumps(logs), total_steps, execution_id),
    )
    return updated.rowcount == 1


def _refresh_suite_stats_for_execution(conn, execution_id: int) -> None:
    execution = fetch_one(conn, "SELECT test_suite_id FROM executions WHERE id = ?", (execution_id,))
    suite_id = execution.get("test_suite_id") if execution else None
    if suite_id:
        from .extended_routes import refresh_suite_stats

        refresh_suite_stats(conn, suite_id)


def _update_test_case_last_run(conn, test_case_id: int | None, result: str, finished_at: str) -> None:
    if not test_case_id:
        return
    conn.execute(
        """
        UPDATE test_cases
        SET last_result = ?, last_run_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (result, finished_at, finished_at, test_case_id),
    )


def run_execution(execution_id: int) -> None:
    executor: AppFlowExecutor | None = None
    started_time: datetime | None = None

    try:
        with connection() as conn:
            execution = get_execution_or_404(conn, execution_id)
            if execution["status"] == "stopped":
                return
            if execution["status"] != "pending":
                return
            test_case = get_test_case_or_404(conn, execution["test_case_id"])
            device = get_device_or_404(conn, execution["device_id"])
            settings = get_settings(conn)
            steps = extract_steps(test_case["ui_flow"])
            package_override = (
                get_package_or_404(conn, int(execution["package_id"]))
                if execution.get("package_id")
                else None
            )

            report_dir = ensure_reports_root(conn) / f"execution-{execution_id}"
            artifact_dir = report_dir / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)

            executor = AppFlowExecutor(
                adb_path=str(settings.get("adb_path") or "adb").strip() or "adb",
                device_serial=str(device.get("device_id") or "").strip(),
                project_id=int(test_case["project_id"]),
                variables=test_case.get("variables") or [],
                default_timeout=int(test_case.get("timeout") or settings.get("default_timeout") or 30),
                default_package_name=str(
                    (package_override or {}).get("package_name") or test_case.get("package_name") or ""
                ).strip(),
                default_activity_name=str(
                    (package_override or {}).get("activity_name") or test_case.get("activity_name") or ""
                ).strip(),
                report_dir=report_dir,
                artifact_dir=artifact_dir,
                stop_requested=lambda: _execution_is_stopped(execution_id),
            )

            total_steps = max(executor.count_total_steps(steps), 1)
            logs = append_log([], f"开始执行测试用例 {test_case['name']}")

            if device["status"] == "offline":
                logs = append_log(logs, "设备离线，无法执行", "error")
                now = utc_now()
                conn.execute(
                    """
                    UPDATE executions
                    SET status = 'failed', result = 'failed', error_message = ?, logs = ?, finished_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("设备离线，无法执行", json_dumps(logs), now, now, execution_id),
                )
                _update_test_case_last_run(conn, test_case["id"], "failed", now)
                finish_device_lock(conn, device["id"])
                write_execution_report(conn, execution_id)
                _refresh_suite_stats_for_execution(conn, execution_id)
                return

            if not steps:
                logs = append_log(logs, "未检测到可执行步骤，请先在场景编排中添加步骤", "error")
                now = utc_now()
                conn.execute(
                    """
                    UPDATE executions
                    SET status = 'failed', result = 'failed', error_message = ?, logs = ?, finished_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("未检测到可执行步骤", json_dumps(logs), now, now, execution_id),
                )
                _update_test_case_last_run(conn, test_case["id"], "failed", now)
                finish_device_lock(conn, device["id"])
                write_execution_report(conn, execution_id)
                _refresh_suite_stats_for_execution(conn, execution_id)
                return

            started_at = utc_now()
            if not claim_pending_execution(
                conn,
                execution_id,
                started_at=started_at,
                logs=logs,
                total_steps=total_steps,
            ):
                current = get_execution_or_404(conn, execution_id)
                if current["status"] == "stopped":
                    return
                return
            conn.execute(
                """
                UPDATE devices
                SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (execution.get("triggered_by") or "FlyTest", started_at, started_at, device["id"]),
            )
            started_time = datetime.fromisoformat(started_at)

        if executor is None:
            raise RuntimeError("Execution runtime was not initialized")

        if executor.default_package_name and not executor.has_action(steps, {"launch_app"}):
            launch_detail = executor.launch_default_app()
            with connection() as conn:
                current = get_execution_or_404(conn, execution_id)
                logs = append_log(current["logs"], launch_detail)
                conn.execute(
                    "UPDATE executions SET logs = ?, updated_at = ? WHERE id = ?",
                    (json_dumps(logs), utc_now(), execution_id),
                )

        def on_step_complete(index: int, total: int, step_name: str, detail: str) -> None:
            with connection() as conn:
                current = get_execution_or_404(conn, execution_id)
                if current["status"] == "stopped":
                    raise StopRequested("Execution was stopped")
                progress = min(98, max(5, int(index / max(total, 1) * 100)))
                message = f"完成步骤 {index}/{total}: {step_name}"
                if detail:
                    message = f"{message} - {detail}"
                logs = append_log(current["logs"], message)
                conn.execute(
                    """
                    UPDATE executions
                    SET progress = ?, logs = ?, passed_steps = ?, failed_steps = 0, updated_at = ?
                    WHERE id = ?
                    """,
                    (progress, json_dumps(logs), index, utc_now(), execution_id),
                )

        result = executor.run(steps, on_step_complete=on_step_complete)

        finished_at = utc_now()
        with connection() as conn:
            current = get_execution_or_404(conn, execution_id)
            duration = max(0.0, (datetime.fromisoformat(finished_at) - started_time).total_seconds()) if started_time else 0.0
            logs = append_log(current["logs"], "执行完成，结果通过")
            summary = f"APP 自动化真实执行完成，共执行 {result['passed_steps']}/{result['total_steps']} 个步骤。"
            conn.execute(
                """
                UPDATE executions
                SET status = 'completed', result = 'passed', progress = 100, report_summary = ?,
                    finished_at = ?, duration = ?, logs = ?, passed_steps = ?, failed_steps = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    summary,
                    finished_at,
                    duration,
                    json_dumps(logs),
                    result["passed_steps"],
                    finished_at,
                    execution_id,
                ),
            )
            write_execution_report(conn, execution_id)
            conn.execute(
                """
                UPDATE test_cases
                SET last_result = 'passed', last_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (finished_at, finished_at, current["test_case_id"]),
            )
            finish_device_lock(conn, current["device_id"])
            _refresh_suite_stats_for_execution(conn, execution_id)
    except StopRequested:
        with connection() as conn:
            execution = fetch_one(
                conn,
                "SELECT status, device_id, test_case_id, logs FROM executions WHERE id = ?",
                (execution_id,),
            )
            if execution and execution.get("status") == "stopped":
                if execution.get("device_id"):
                    finish_device_lock(conn, execution["device_id"])
                write_execution_report(conn, execution_id)
                _refresh_suite_stats_for_execution(conn, execution_id)
                return
            logs = append_log(json_loads(execution.get("logs") if execution else "[]", []), "执行已停止", "warning")
            now = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'stopped', result = 'stopped', finished_at = ?, updated_at = ?, logs = ?
                WHERE id = ?
                """,
                (now, now, json_dumps(logs), execution_id),
            )
            _update_test_case_last_run(conn, execution.get("test_case_id") if execution else None, "stopped", now)
            write_execution_report(conn, execution_id)
            if execution and execution.get("device_id"):
                finish_device_lock(conn, execution["device_id"])
            _refresh_suite_stats_for_execution(conn, execution_id)
    except StepExecutionError as exc:
        with connection() as conn:
            execution = fetch_one(
                conn,
                "SELECT status, device_id, test_case_id, logs FROM executions WHERE id = ?",
                (execution_id,),
            )
            if execution and execution.get("status") == "stopped":
                if execution.get("device_id"):
                    finish_device_lock(conn, execution["device_id"])
                write_execution_report(conn, execution_id)
                _refresh_suite_stats_for_execution(conn, execution_id)
                return
            logs = append_log(
                json_loads(execution.get("logs") if execution else "[]", []),
                f"步骤失败 {exc.index}: {exc.step_name} - {exc.cause}",
                "error",
                artifact=exc.screenshot_path,
            )
            now = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'failed', result = 'failed', error_message = ?, report_summary = ?, finished_at = ?, updated_at = ?,
                    logs = ?, failed_steps = 1
                WHERE id = ?
                """,
                (
                    f"{exc.step_name}: {exc.cause}",
                    f"执行在步骤 {exc.index} 失败: {exc.step_name}",
                    now,
                    now,
                    json_dumps(logs),
                    execution_id,
                ),
            )
            _update_test_case_last_run(conn, execution.get("test_case_id") if execution else None, "failed", now)
            write_execution_report(conn, execution_id)
            if execution and execution.get("device_id"):
                finish_device_lock(conn, execution["device_id"])
            _refresh_suite_stats_for_execution(conn, execution_id)
    except Exception as exc:
        with connection() as conn:
            execution = fetch_one(
                conn,
                "SELECT status, device_id, test_case_id, logs FROM executions WHERE id = ?",
                (execution_id,),
            )
            if execution and execution.get("status") == "stopped":
                if execution.get("device_id"):
                    finish_device_lock(conn, execution["device_id"])
                write_execution_report(conn, execution_id)
                _refresh_suite_stats_for_execution(conn, execution_id)
                return
            logs = append_log(json_loads(execution.get("logs") if execution else "[]", []), f"执行异常: {exc}", "error")
            now = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'failed', result = 'failed', error_message = ?, report_summary = ?, finished_at = ?, updated_at = ?, logs = ?,
                    failed_steps = CASE WHEN total_steps > 0 THEN 1 ELSE 0 END
                WHERE id = ?
                """,
                (str(exc), str(exc), now, now, json_dumps(logs), execution_id),
            )
            _update_test_case_last_run(conn, execution.get("test_case_id") if execution else None, "failed", now)
            write_execution_report(conn, execution_id)
            if execution and execution.get("device_id"):
                finish_device_lock(conn, execution["device_id"])
            _refresh_suite_stats_for_execution(conn, execution_id)


def start_execution_thread(execution_id: int) -> None:
    threading.Thread(target=run_execution, args=(execution_id,), daemon=True).start()


@app.get("/health")
def health_check() -> dict[str, Any]:
    return success(
        {
            "service": "app-automation",
            "status": "ok",
            "version": app.version,
            "checked_at": utc_now(),
            "scheduler": app_scheduler.status(),
        }
    )


@app.get("/dashboard/statistics/")
def get_dashboard_statistics(project_id: int | None = Query(default=None)) -> dict[str, Any]:
    with connection() as conn:
        device_total = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices")["count"]
        device_online = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices WHERE status IN ('available', 'online')")["count"]
        device_locked = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices WHERE status = 'locked'")["count"]

        package_where, package_params = apply_project_scope_filter("WHERE 1 = 1", [], project_id)
        package_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM packages {package_where}", package_params)["count"]
        element_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM elements {package_where}", package_params)["count"]
        test_case_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM test_cases {package_where}", package_params)["count"]
        execution_where, execution_params = apply_project_scope_filter("WHERE 1 = 1", [], project_id)
        execution_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM executions {execution_where}", execution_params)["count"]
        execution_passed = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {execution_where} AND result = 'passed'",
            execution_params,
        )["count"]
        execution_failed = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {execution_where} AND result = 'failed'",
            execution_params,
        )["count"]
        execution_running = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {execution_where} AND status = 'running'",
            execution_params,
        )["count"]
        denominator = max(execution_passed + execution_failed, 1)
        pass_rate = round(execution_passed / denominator * 100, 1) if execution_total else 0

        recent_query = """
            SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial
            FROM executions e
            LEFT JOIN test_cases tc ON tc.id = e.test_case_id
            LEFT JOIN devices d ON d.id = e.device_id
            WHERE 1 = 1
        """
        recent_query, recent_params = apply_project_scope_filter(recent_query, [], project_id, column="e.project_id")
        recent_query += " ORDER BY e.created_at DESC LIMIT 6"
        recent_executions = [serialize_execution(item) for item in fetch_all(conn, recent_query, recent_params)]

    return success(
        {
            "devices": {"total": device_total, "online": device_online, "locked": device_locked},
            "packages": {"total": package_total},
            "elements": {"total": element_total},
            "test_cases": {"total": test_case_total},
            "executions": {
                "total": execution_total,
                "running": execution_running,
                "passed": execution_passed,
                "failed": execution_failed,
                "pass_rate": pass_rate,
            },
            "recent_executions": recent_executions,
        }
    )


@app.get("/devices/")
def list_devices(search: str | None = Query(default=None), status: str | None = Query(default=None)) -> dict[str, Any]:
    query = "SELECT * FROM devices WHERE 1 = 1"
    params: list[Any] = []
    if search:
        query += " AND (name LIKE ? OR device_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC"
    with connection() as conn:
        devices = [serialize_device(item) for item in fetch_all(conn, query, params)]
    return success(devices)


@app.get("/devices/discover/")
def refresh_devices() -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
        try:
            discovered = discover_devices(settings["adb_path"])
            devices = [upsert_device(conn, item) for item in discovered]
            return success(devices, "设备同步完成")
        except AdbError as exc:
            cached = [serialize_device(item) for item in fetch_all(conn, "SELECT * FROM devices ORDER BY updated_at DESC")]
            return success(cached, f"{exc}，已返回缓存设备列表")


@app.post("/devices/connect/")
def connect_device(payload: DeviceConnectPayload) -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
        try:
            device = connect_remote_device(settings["adb_path"], payload.ip_address, payload.port)
        except AdbError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return success(upsert_device(conn, device, preserve_lock=False), "远程设备连接成功")


@app.post("/devices/{device_id}/lock/")
def lock_device(device_id: int, user_name: str = Query(default="FlyTest")) -> dict[str, Any]:
    with connection() as conn:
        device = reserve_device_for_execution(conn, device_id, locked_by=user_name)
        return success(get_device_or_404(conn, device_id), "设备已锁定")


@app.post("/devices/{device_id}/unlock/")
def unlock_device(device_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_device_or_404(conn, device_id)
        finish_device_lock(conn, device_id)
        return success(get_device_or_404(conn, device_id), "设备已释放")


@app.post("/devices/{device_id}/disconnect/")
def disconnect_device(device_id: int) -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
        device = get_device_or_404(conn, device_id)
        if device["status"] in {"locked", "stopping"}:
            raise HTTPException(status_code=409, detail="device is currently in use and cannot be disconnected")
        try:
            disconnect_remote_device(settings["adb_path"], device["device_id"])
        except AdbError:
            pass
        now = utc_now()
        conn.execute(
            "UPDATE devices SET status = 'offline', locked_by = '', locked_at = NULL, updated_at = ? WHERE id = ?",
            (now, device_id),
        )
        return success(get_device_or_404(conn, device_id), "设备已断开")


@app.post("/devices/{device_id}/screenshot/")
def screenshot_device(device_id: int) -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
        device = get_device_or_404(conn, device_id)
        if device["status"] == "offline":
            raise HTTPException(status_code=400, detail="设备离线，无法截图")

        try:
            screenshot_bytes = capture_device_screenshot(settings["adb_path"], device["device_id"])
        except AdbError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_ts = int(time.time())
    content = base64.b64encode(screenshot_bytes).decode("utf-8")
    return success(
        {
            "filename": f"device-{device_id}-{current_ts}.png",
            "content": f"data:image/png;base64,{content}",
            "device_id": device["device_id"],
            "timestamp": current_ts,
        },
        "设备截图成功",
    )


@app.patch("/devices/{device_id}/")
def update_device(device_id: int, payload: DeviceUpdatePayload) -> dict[str, Any]:
    with connection() as conn:
        device = get_device_or_404(conn, device_id)
        next_status = payload.status if payload.status is not None else device["status"]
        allowed_statuses = {"available", "online", "offline", "locked", "stopping"}
        if next_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="unsupported device status")
        current_status = str(device.get("status") or "")
        if current_status in {"locked", "stopping"} and next_status != current_status:
            raise HTTPException(status_code=409, detail="device is currently in use and cannot change status")
        if next_status == "locked" and current_status != "locked":
            raise HTTPException(status_code=400, detail="use the lock endpoint to lock a device")
        if next_status == "stopping" and current_status != "stopping":
            raise HTTPException(status_code=400, detail="device stopping status is system managed")
        now = utc_now()
        conn.execute(
            """
            UPDATE devices
            SET name = ?, description = ?, location = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name if payload.name is not None else device["name"],
                payload.description if payload.description is not None else device["description"],
                payload.location if payload.location is not None else device["location"],
                next_status,
                now,
                device_id,
            ),
        )
        return success(get_device_or_404(conn, device_id), "设备信息已更新")


@app.delete("/devices/{device_id}/")
def delete_device(device_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_device_or_404(conn, device_id)
        active_execution = fetch_one(conn, "SELECT id FROM executions WHERE device_id = ? LIMIT 1", (device_id,))
        if active_execution is not None:
            raise HTTPException(status_code=409, detail="device is referenced by executions")
        scheduled_task = fetch_one(conn, "SELECT id FROM scheduled_tasks WHERE device_id = ? LIMIT 1", (device_id,))
        if scheduled_task is not None:
            raise HTTPException(status_code=409, detail="device is referenced by scheduled tasks")
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return success(None, "设备已删除")


@app.get("/packages/")
def list_packages(project_id: int | None = Query(default=None), search: str | None = Query(default=None)) -> dict[str, Any]:
    query = "SELECT * FROM packages WHERE 1 = 1"
    params: list[Any] = []
    query, params = apply_project_scope_filter(query, params, project_id)
    if search:
        query += " AND (name LIKE ? OR package_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY updated_at DESC"
    with connection() as conn:
        rows = fetch_all(conn, query, params)
    return success(rows)


@app.post("/packages/")
def create_package(payload: PackagePayload) -> dict[str, Any]:
    with connection() as conn:
        ensure_project_access(payload.project_id)
        now = utc_now()
        conn.execute(
            """
            INSERT INTO packages (project_id, name, package_name, activity_name, platform, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.package_name.strip(),
                payload.activity_name.strip(),
                payload.platform.strip() or "android",
                payload.description.strip(),
                now,
                now,
            ),
        )
        package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return success(get_package_or_404(conn, package_id), "应用包已创建", 201)


@app.put("/packages/{package_id}/")
def update_package(package_id: int, payload: PackagePayload) -> dict[str, Any]:
    with connection() as conn:
        _ = get_package_or_404(conn, package_id)
        ensure_project_access(payload.project_id)
        conn.execute(
            """
            UPDATE packages
            SET project_id = ?, name = ?, package_name = ?, activity_name = ?, platform = ?, description = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.package_name.strip(),
                payload.activity_name.strip(),
                payload.platform.strip() or "android",
                payload.description.strip(),
                utc_now(),
                package_id,
            ),
        )
        return success(get_package_or_404(conn, package_id), "应用包已更新")


@app.delete("/packages/{package_id}/")
def delete_package(package_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_package_or_404(conn, package_id)
        referenced_case = fetch_one(conn, "SELECT id FROM test_cases WHERE package_id = ? LIMIT 1", (package_id,))
        if referenced_case is not None:
            raise HTTPException(status_code=409, detail="package is referenced by test cases")
        referenced_execution = fetch_one(conn, "SELECT id FROM executions WHERE package_id = ? LIMIT 1", (package_id,))
        if referenced_execution is not None:
            raise HTTPException(status_code=409, detail="package is referenced by executions")
        referenced_task = fetch_one(conn, "SELECT id FROM scheduled_tasks WHERE package_id = ? LIMIT 1", (package_id,))
        if referenced_task is not None:
            raise HTTPException(status_code=409, detail="package is referenced by scheduled tasks")
        conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
        return success(None, "应用包已删除")


@app.get("/elements/")
def list_elements(
    project_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    element_type: str | None = Query(default=None),
) -> dict[str, Any]:
    query = "SELECT * FROM elements WHERE 1 = 1"
    params: list[Any] = []
    query, params = apply_project_scope_filter(query, params, project_id)
    if search:
        query += " AND (name LIKE ? OR selector_value LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if element_type:
        query += " AND element_type = ?"
        params.append(element_type)
    query += " ORDER BY updated_at DESC"
    with connection() as conn:
        rows = [serialize_element(item) for item in fetch_all(conn, query, params)]
    return success(rows)


@app.get("/elements/image-categories/")
def get_element_image_categories(project_id: int = Query(...)) -> dict[str, Any]:
    ensure_project_access(project_id)
    return success(list_image_categories(project_id))


@app.post("/elements/image-categories/create/")
def create_element_image_category(payload: ImageCategoryPayload) -> dict[str, Any]:
    ensure_project_access(payload.project_id)
    category_name = normalize_category_name(payload.name)
    category_path = build_project_asset_dir(category_name, payload.project_id)
    if category_path.exists():
        raise HTTPException(status_code=400, detail="图片分类已存在")
    category_path.mkdir(parents=True, exist_ok=True)
    return success({"name": category_name}, "图片分类已创建", 201)


@app.delete("/elements/image-categories/{category_name}/")
def delete_element_image_category(category_name: str, project_id: int = Query(...)) -> dict[str, Any]:
    name = normalize_category_name(category_name)
    if name == "common":
        raise HTTPException(status_code=400, detail="默认分类不可删除")

    ensure_project_access(project_id)

    category_root = get_element_asset_root() / name
    category_path = build_project_asset_dir(name, project_id)
    if not category_path.exists():
        raise HTTPException(status_code=404, detail="图片分类不存在")
    if any(path.is_file() for path in category_path.rglob("*")):
        raise HTTPException(status_code=400, detail="分类不为空，无法删除")
    nested_dirs = sorted(
        [path for path in category_path.rglob("*") if path.is_dir()],
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for nested_dir in nested_dirs:
        nested_dir.rmdir()
    category_path.rmdir()
    if category_root.exists() and not any(category_root.iterdir()):
        category_root.rmdir()
    return success(None, "图片分类已删除")


@app.get("/elements/assets/{asset_path:path}")
def get_element_asset(asset_path: str) -> FileResponse:
    file_path = resolve_element_asset_file(asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="元素资源不存在")
    with connection() as conn:
        ensure_element_asset_access(conn, asset_path)
    return FileResponse(str(file_path), media_type=get_report_content_type(file_path))


@app.get("/elements/{element_id}/preview/")
def preview_element(element_id: int) -> FileResponse:
    with connection() as conn:
        element = get_element_or_404(conn, element_id)
        image_path = build_element_image_path(element)
    file_path = resolve_element_asset_file(image_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="元素图片不存在")
    with connection() as conn:
        ensure_element_asset_access(conn, image_path)
    return FileResponse(str(file_path), media_type=get_report_content_type(file_path))


@app.post("/elements/")
def create_element(payload: ElementPayload) -> dict[str, Any]:
    with connection() as conn:
        ensure_project_access(payload.project_id)
        ensure_element_assets_belong_to_project(
            conn,
            project_id=payload.project_id,
            asset_paths=_collect_element_asset_references(payload),
        )
        now = utc_now()
        conn.execute(
            """
            INSERT INTO elements (
                project_id, name, element_type, selector_type, selector_value, description,
                tags, config, image_path, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.element_type.strip(),
                payload.selector_type.strip(),
                payload.selector_value.strip(),
                payload.description.strip(),
                json_dumps(payload.tags),
                json_dumps(payload.config),
                payload.image_path.strip(),
                1 if payload.is_active else 0,
                now,
                now,
            ),
        )
        element_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return success(get_element_or_404(conn, element_id), "元素已创建", 201)


@app.put("/elements/{element_id}/")
def update_element(element_id: int, payload: ElementPayload) -> dict[str, Any]:
    with connection() as conn:
        _ = get_element_or_404(conn, element_id)
        ensure_project_access(payload.project_id)
        ensure_element_assets_belong_to_project(
            conn,
            project_id=payload.project_id,
            asset_paths=_collect_element_asset_references(payload),
        )
        conn.execute(
            """
            UPDATE elements
            SET project_id = ?, name = ?, element_type = ?, selector_type = ?, selector_value = ?,
                description = ?, tags = ?, config = ?, image_path = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.element_type.strip(),
                payload.selector_type.strip(),
                payload.selector_value.strip(),
                payload.description.strip(),
                json_dumps(payload.tags),
                json_dumps(payload.config),
                payload.image_path.strip(),
                1 if payload.is_active else 0,
                utc_now(),
                element_id,
            ),
        )
        return success(get_element_or_404(conn, element_id), "元素已更新")


@app.post("/elements/upload/")
async def upload_element_asset(
    file: UploadFile,
    project_id: int = Query(...),
    category: str = Query(default="common"),
    element_id: int | None = Query(default=None),
) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="未接收到图片文件")

    ensure_project_access(project_id)
    category_name = normalize_category_name(category)
    file_hash = compute_file_hash(content)

    with connection() as conn:
        if element_id is not None:
            element = get_element_or_404(conn, element_id)
            if int(element["project_id"]) != project_id:
                raise HTTPException(status_code=400, detail="元素不属于当前项目")
        duplicate = find_duplicate_element_asset(
            conn,
            file_hash,
            project_id=project_id,
            exclude_element_id=element_id,
        )
        if duplicate is not None:
            image_path = build_element_image_path(duplicate)
            duplicate_config = duplicate.get("config", {})
            duplicate_category = ""
            if isinstance(duplicate_config, dict):
                duplicate_category = str(duplicate_config.get("image_category") or "")
            if not duplicate_category:
                duplicate_category = extract_image_category_from_asset_path(image_path)
            return success(
                {
                    "project_id": project_id,
                    "image_path": image_path,
                    "file_hash": file_hash,
                    "image_category": duplicate_category or category_name,
                    "duplicate": True,
                    "existing_element": {
                        "id": duplicate["id"],
                        "name": duplicate["name"],
                        "image_path": image_path,
                    },
                },
                "检测到重复图片，已复用现有资源",
            )

    target_dir = build_project_asset_dir(category_name, project_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "element.png").suffix or ".png"
    base_name = Path(file.filename or "element").stem or "element"
    safe_name = re.sub(r"[^\w\-\u4e00-\u9fa5]+", "_", base_name).strip("_") or "element"
    file_name = f"{safe_name}_{int(time.time() * 1000)}{suffix}"
    file_path = target_dir / file_name
    file_path.write_bytes(content)
    relative_path = str(file_path.relative_to(get_element_asset_root().parent)).replace("\\", "/")

    return success(
        {
            "project_id": project_id,
            "image_path": relative_path,
            "file_hash": file_hash,
            "image_category": category_name,
            "duplicate": False,
            "url": f"/elements/assets/{relative_path}",
        },
        "图片已上传",
    )


@app.delete("/elements/{element_id}/")
def delete_element(element_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_element_or_404(conn, element_id)
        conn.execute("DELETE FROM elements WHERE id = ?", (element_id,))
        return success(None, "元素已删除")


@app.get("/test-cases/")
def list_test_cases(project_id: int | None = Query(default=None), search: str | None = Query(default=None)) -> dict[str, Any]:
    query = """
        SELECT tc.*, p.name AS package_display_name, p.package_name AS package_name
        FROM test_cases tc
        LEFT JOIN packages p ON p.id = tc.package_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    query, params = apply_project_scope_filter(query, params, project_id, column="tc.project_id")
    if search:
        query += " AND (tc.name LIKE ? OR tc.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY tc.updated_at DESC"
    with connection() as conn:
        rows = [serialize_test_case(item) for item in fetch_all(conn, query, params)]
    return success(rows)


@app.get("/test-cases/{test_case_id}/")
def get_test_case_detail(test_case_id: int) -> dict[str, Any]:
    with connection() as conn:
        return success(get_test_case_or_404(conn, test_case_id))


@app.post("/test-cases/")
def create_test_case(payload: TestCasePayload) -> dict[str, Any]:
    with connection() as conn:
        ensure_project_access(payload.project_id)
        if payload.package_id is not None:
            package = get_package_or_404(conn, payload.package_id)
            ensure_package_belongs_to_project(package, payload.project_id)
        now = utc_now()
        conn.execute(
            """
            INSERT INTO test_cases (
                project_id, name, description, package_id, ui_flow, variables, tags,
                timeout, retry_count, last_result, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.description.strip(),
                payload.package_id,
                json_dumps(payload.ui_flow),
                json_dumps(payload.variables),
                json_dumps(payload.tags),
                payload.timeout,
                payload.retry_count,
                now,
                now,
            ),
        )
        test_case_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return success(get_test_case_or_404(conn, test_case_id), "测试用例已创建", 201)


@app.put("/test-cases/{test_case_id}/")
def update_test_case(test_case_id: int, payload: TestCasePayload) -> dict[str, Any]:
    with connection() as conn:
        _ = get_test_case_or_404(conn, test_case_id)
        ensure_project_access(payload.project_id)
        if payload.package_id is not None:
            package = get_package_or_404(conn, payload.package_id)
            ensure_package_belongs_to_project(package, payload.project_id)
        conn.execute(
            """
            UPDATE test_cases
            SET project_id = ?, name = ?, description = ?, package_id = ?, ui_flow = ?, variables = ?, tags = ?,
                timeout = ?, retry_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.project_id,
                payload.name.strip(),
                payload.description.strip(),
                payload.package_id,
                json_dumps(payload.ui_flow),
                json_dumps(payload.variables),
                json_dumps(payload.tags),
                payload.timeout,
                payload.retry_count,
                utc_now(),
                test_case_id,
            ),
        )
        return success(get_test_case_or_404(conn, test_case_id), "测试用例已更新")


@app.delete("/test-cases/{test_case_id}/")
def delete_test_case(test_case_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_test_case_or_404(conn, test_case_id)
        referenced_execution = fetch_one(conn, "SELECT id FROM executions WHERE test_case_id = ? LIMIT 1", (test_case_id,))
        if referenced_execution is not None:
            raise HTTPException(status_code=409, detail="test case is referenced by executions")
        referenced_task = fetch_one(conn, "SELECT id FROM scheduled_tasks WHERE test_case_id = ? LIMIT 1", (test_case_id,))
        if referenced_task is not None:
            raise HTTPException(status_code=409, detail="test case is referenced by scheduled tasks")
        conn.execute("DELETE FROM test_cases WHERE id = ?", (test_case_id,))
        return success(None, "测试用例已删除")


@app.post("/ai/scene-plan/")
def generate_scene_plan(payload: ScenePlanPayload) -> dict[str, Any]:
    with connection() as conn:
        ensure_project_access(payload.project_id)
        if payload.package_id is not None:
            package = get_package_or_404(conn, payload.package_id)
            ensure_package_belongs_to_project(package, payload.project_id)
        plan = build_scene_plan(conn, payload.model_dump())
    return success(plan, "APP AI 场景规划已生成")


@app.post("/ai/step-suggestion/")
def generate_step_suggestion(payload: StepSuggestionPayload) -> dict[str, Any]:
    with connection() as conn:
        ensure_project_access(payload.project_id)
        if payload.package_id is not None:
            package = get_package_or_404(conn, payload.package_id)
            ensure_package_belongs_to_project(package, payload.project_id)
        suggestion = build_step_suggestion(conn, payload.model_dump())
    return success(suggestion, "APP AI 步骤补全已生成")


@app.post("/test-cases/{test_case_id}/execute/")
def execute_test_case(test_case_id: int, payload: ExecuteTestCasePayload) -> dict[str, Any]:
    with connection() as conn:
        test_case = get_test_case_or_404(conn, test_case_id)
        reserve_device_for_execution(
            conn,
            payload.device_id,
            locked_by=payload.triggered_by or "FlyTest",
        )
        now = utc_now()
        conn.execute(
            """
            INSERT INTO executions (
                project_id, test_case_id, package_id, device_id, status, result, progress, trigger_mode, triggered_by,
                logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                started_at, finished_at, duration, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', '', 0, ?, ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
            """,
            (
                test_case["project_id"],
                test_case_id,
                test_case.get("package_id"),
                payload.device_id,
                payload.trigger_mode,
                payload.triggered_by,
                now,
                now,
            ),
        )
        execution_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        execution = get_execution_or_404(conn, execution_id)

    start_execution_thread(execution_id)
    return success(execution, "执行任务已启动", 201)


@app.get("/executions/")
def list_executions(
    project_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    test_suite_id: int | None = Query(default=None),
) -> dict[str, Any]:
    query = """
        SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial
        FROM executions e
        LEFT JOIN test_cases tc ON tc.id = e.test_case_id
        LEFT JOIN devices d ON d.id = e.device_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    query, params = apply_project_scope_filter(query, params, project_id, column="e.project_id")
    if status:
        query += " AND e.status = ?"
        params.append(status)
    if search:
        query += " AND (tc.name LIKE ? OR d.name LIKE ? OR d.device_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if test_suite_id is not None:
        query += " AND e.test_suite_id = ?"
        params.append(test_suite_id)
    query += " ORDER BY e.created_at DESC"
    with connection() as conn:
        rows = [serialize_execution(item) for item in fetch_all(conn, query, params)]
    return success(rows)


@app.get("/executions/{execution_id}/")
def get_execution_detail(execution_id: int) -> dict[str, Any]:
    with connection() as conn:
        return success(get_execution_or_404(conn, execution_id))


@app.get("/executions/{execution_id}/report/")
def serve_execution_report(execution_id: int) -> FileResponse:
    with connection() as conn:
        _ = get_execution_or_404(conn, execution_id)
        try:
            file_path = resolve_report_file(conn, execution_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(str(file_path), media_type=get_report_content_type(file_path))


@app.get("/executions/{execution_id}/report/{file_path:path}")
def serve_execution_report_asset(execution_id: int, file_path: str) -> FileResponse:
    with connection() as conn:
        _ = get_execution_or_404(conn, execution_id)
        try:
            resolved_path = resolve_report_file(conn, execution_id, file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(str(resolved_path), media_type=get_report_content_type(resolved_path))


@app.post("/executions/{execution_id}/stop/")
def stop_execution(execution_id: int) -> dict[str, Any]:
    with connection() as conn:
        execution = get_execution_or_404(conn, execution_id)
        if execution["status"] not in {"pending", "running"}:
            return success(execution, "当前执行已结束")
        logs = append_log(execution["logs"], "收到停止指令", "warning")
        now = utc_now()
        conn.execute(
            """
            UPDATE executions
            SET status = 'stopped', result = 'stopped', finished_at = COALESCE(finished_at, ?), updated_at = ?, logs = ?
            WHERE id = ?
            """,
            (now, now, json_dumps(logs), execution_id),
        )
        if execution["status"] == "pending" and execution.get("device_id"):
            finish_device_lock(conn, execution["device_id"])
        elif execution["status"] == "running" and execution.get("device_id"):
            conn.execute(
                """
                UPDATE devices
                SET status = 'stopping', updated_at = ?
                WHERE id = ? AND status = 'locked'
                """,
                (now, execution["device_id"]),
            )
        write_execution_report(conn, execution_id)
        _refresh_suite_stats_for_execution(conn, execution_id)
        return success(get_execution_or_404(conn, execution_id), "执行已停止")


@app.delete("/executions/{execution_id}/")
def delete_execution(execution_id: int) -> dict[str, Any]:
    with connection() as conn:
        execution = get_execution_or_404(conn, execution_id)
        if execution["status"] in {"pending", "running"}:
            raise HTTPException(status_code=409, detail="执行仍在收尾中，请等待完成后再删除")
        conn.execute("DELETE FROM executions WHERE id = ?", (execution_id,))
        return success(None, "执行记录已删除")


@app.get("/settings/current/")
def get_current_settings() -> dict[str, Any]:
    with connection() as conn:
        return success(get_settings(conn))


@app.get("/settings/diagnostics/")
def get_settings_diagnostics() -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
    return success(build_adb_diagnostics(settings))


@app.get("/settings/runtime-capabilities/")
def get_runtime_capabilities() -> dict[str, Any]:
    return success(build_runtime_capabilities())


@app.post("/settings/detect-adb/")
def detect_adb() -> dict[str, Any]:
    with connection() as conn:
        settings = get_settings(conn)
        diagnostics = build_adb_diagnostics(settings)
        if diagnostics["executable_found"]:
            detected_path = str(diagnostics.get("resolved_path") or diagnostics.get("configured_path") or "").strip()
            if detected_path and detected_path != settings["adb_path"]:
                conn.execute(
                    "UPDATE settings SET adb_path = ?, updated_at = ? WHERE id = 1",
                    (detected_path, utc_now()),
                )
                settings = get_settings(conn)
            return success(
                {"settings": settings, "diagnostics": diagnostics},
                "ADB 自动检测完成",
            )
        return success(
            {"settings": settings, "diagnostics": diagnostics},
            "未检测到可用 ADB，请检查 Android SDK 或模拟器安装",
        )


@app.post("/settings/save/")
def save_settings(payload: SettingsPayload) -> dict[str, Any]:
    with connection() as conn:
        conn.execute(
            """
            UPDATE settings
            SET adb_path = ?, default_timeout = ?, workspace_root = ?, auto_discover_on_open = ?, notes = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                payload.adb_path.strip(),
                payload.default_timeout,
                payload.workspace_root.strip(),
                1 if payload.auto_discover_on_open else 0,
                payload.notes.strip(),
                utc_now(),
            ),
        )
        return success(get_settings(conn), "环境设置已保存")


app.include_router(extended_router)
