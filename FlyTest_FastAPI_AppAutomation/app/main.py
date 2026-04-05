from __future__ import annotations

import base64
import hashlib
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .adb import AdbError, capture_device_screenshot, connect_remote_device, disconnect_remote_device, discover_devices
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
from .extended_routes import router as extended_router
from .reporting import get_report_content_type, resolve_report_file, write_execution_report
from .scheduler import app_scheduler
from .schemas import (
    DeviceConnectPayload,
    DeviceUpdatePayload,
    ElementPayload,
    ExecuteTestCasePayload,
    ImageCategoryPayload,
    PackagePayload,
    SettingsPayload,
    TestCasePayload,
)

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


def success(data: Any = None, message: str = "success", code: int = 200) -> dict[str, Any]:
    return {"status": "success", "code": code, "message": message, "data": data}


def get_settings(conn) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM settings WHERE id = 1")
    if row is None:
        raise HTTPException(status_code=500, detail="APP 自动化配置初始化失败")
    row["auto_discover_on_open"] = bool(row["auto_discover_on_open"])
    return row


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


def resolve_element_asset_path(asset_path: str) -> Path:
    cleaned = (asset_path or "").replace("\\", "/").strip().lstrip("/")
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
        return str(config.get("image_path") or "").strip()
    return ""


def compute_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def find_duplicate_element_asset(conn, file_hash: str, exclude_element_id: int | None = None) -> dict[str, Any] | None:
    rows = fetch_all(conn, "SELECT * FROM elements WHERE element_type = 'image' AND is_active = 1")
    for row in rows:
        if exclude_element_id is not None and int(row["id"]) == exclude_element_id:
            continue
        element = serialize_element(row)
        config = element.get("config", {})
        if isinstance(config, dict) and str(config.get("file_hash") or "") == file_hash:
            return element
    return None


def list_image_categories() -> list[dict[str, Any]]:
    root = get_element_asset_root()
    (root / "common").mkdir(parents=True, exist_ok=True)
    categories: list[dict[str, Any]] = []
    for item in sorted(root.iterdir(), key=lambda path: path.name.lower()):
        if not item.is_dir():
            continue
        file_count = sum(1 for file in item.iterdir() if file.is_file())
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


def extract_steps(ui_flow: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(ui_flow, dict):
        steps = ui_flow.get("steps")
        if isinstance(steps, list):
            return [item for item in steps if isinstance(item, dict)]
    return [
        {"name": "准备执行环境", "action": "prepare"},
        {"name": "启动应用", "action": "launch"},
        {"name": "断言结果", "action": "assert"},
    ]


def append_log(logs: list[dict[str, Any]], message: str, level: str = "info") -> list[dict[str, Any]]:
    next_logs = list(logs)
    next_logs.append({"timestamp": utc_now(), "level": level, "message": message})
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
    return row


def get_element_or_404(conn, element_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM elements WHERE id = ?", (element_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="元素不存在")
    return serialize_element(row)


def get_test_case_or_404(conn, test_case_id: int) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        SELECT tc.*, p.name AS package_display_name, p.package_name AS package_name
        FROM test_cases tc
        LEFT JOIN packages p ON p.id = tc.package_id
        WHERE tc.id = ?
        """,
        (test_case_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="测试用例不存在")
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
        device_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return get_device_or_404(conn, device_id)

    next_status = payload.get("status", existing["status"])
    if preserve_lock and existing.get("status") == "locked":
        next_status = "locked"

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
    conn.execute(
        """
        UPDATE devices
        SET status = 'available', locked_by = '', locked_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (now, device_id),
    )


def run_execution(execution_id: int) -> None:
    try:
        with connection() as conn:
            execution = get_execution_or_404(conn, execution_id)
            test_case = get_test_case_or_404(conn, execution["test_case_id"])
            device = get_device_or_404(conn, execution["device_id"])
            steps = extract_steps(test_case["ui_flow"])
            total_steps = max(len(steps), 1)

            logs = append_log([], f"开始执行测试用例: {test_case['name']}")
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
                return

            started_at = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'running', started_at = ?, updated_at = ?, logs = ?, progress = 3,
                    total_steps = ?, passed_steps = 0, failed_steps = 0
                WHERE id = ?
                """,
                (started_at, started_at, json_dumps(logs), total_steps, execution_id),
            )
            conn.execute(
                """
                UPDATE devices
                SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (execution.get("triggered_by") or "FlyTest", started_at, started_at, device["id"]),
            )
            started_time = datetime.fromisoformat(started_at)

        for index, step in enumerate(steps, start=1):
            time.sleep(0.8)
            with connection() as conn:
                current = get_execution_or_404(conn, execution_id)
                if current["status"] == "stopped":
                    logs = append_log(current["logs"], "执行被手动停止", "warning")
                    now = utc_now()
                    conn.execute(
                        """
                        UPDATE executions
                        SET result = 'stopped', finished_at = ?, updated_at = ?, logs = ?
                        WHERE id = ?
                        """,
                        (now, now, json_dumps(logs), execution_id),
                    )
                    write_execution_report(conn, execution_id)
                    finish_device_lock(conn, current["device_id"])
                    return

                step_name = step.get("name") or step.get("action") or f"步骤 {index}"
                progress = min(98, int(index / total_steps * 100))
                logs = append_log(current["logs"], f"完成步骤 {index}/{total_steps}: {step_name}")
                conn.execute(
                    """
                    UPDATE executions
                    SET progress = ?, logs = ?, passed_steps = ?, failed_steps = 0, updated_at = ?
                    WHERE id = ?
                    """,
                    (progress, json_dumps(logs), index, utc_now(), execution_id),
                )

        finished_at = utc_now()
        with connection() as conn:
            current = get_execution_or_404(conn, execution_id)
            duration = max(0.0, (datetime.fromisoformat(finished_at) - started_time).total_seconds())
            logs = append_log(current["logs"], "执行完成，结果通过")
            conn.execute(
                """
                UPDATE executions
                SET status = 'completed', result = 'passed', progress = 100, report_summary = ?,
                    finished_at = ?, duration = ?, logs = ?, passed_steps = ?, failed_steps = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    "MVP 执行器已完成编排与状态流转，可继续接入 Airtest 或 Appium 真实执行。",
                    finished_at,
                    duration,
                    json_dumps(logs),
                    total_steps,
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
    except Exception as exc:
        with connection() as conn:
            execution = fetch_one(conn, "SELECT device_id, logs FROM executions WHERE id = ?", (execution_id,))
            logs = append_log(json_loads(execution.get("logs") if execution else "[]", []), f"执行异常: {exc}", "error")
            now = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'failed', result = 'failed', error_message = ?, finished_at = ?, updated_at = ?, logs = ?,
                    failed_steps = CASE WHEN total_steps > 0 THEN 1 ELSE 0 END
                WHERE id = ?
                """,
                (str(exc), now, now, json_dumps(logs), execution_id),
            )
            write_execution_report(conn, execution_id)
            if execution and execution.get("device_id"):
                finish_device_lock(conn, execution["device_id"])


def start_execution_thread(execution_id: int) -> None:
    threading.Thread(target=run_execution, args=(execution_id,), daemon=True).start()


@app.get("/health")
def health_check() -> dict[str, Any]:
    return success({"service": "app-automation", "status": "ok", "scheduler": app_scheduler.status()})


@app.get("/dashboard/statistics/")
def get_dashboard_statistics(project_id: int | None = Query(default=None)) -> dict[str, Any]:
    with connection() as conn:
        device_total = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices")["count"]
        device_online = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices WHERE status IN ('available', 'online')")["count"]
        device_locked = fetch_one(conn, "SELECT COUNT(*) AS count FROM devices WHERE status = 'locked'")["count"]

        filters: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            filters.append("project_id = ?")
            params.append(project_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        package_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM packages {where_clause}", params)["count"]
        element_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM elements {where_clause}", params)["count"]
        test_case_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM test_cases {where_clause}", params)["count"]
        execution_total = fetch_one(conn, f"SELECT COUNT(*) AS count FROM executions {where_clause}", params)["count"]
        execution_passed = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {where_clause} {'AND' if where_clause else 'WHERE'} result = 'passed'",
            params,
        )["count"]
        execution_failed = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {where_clause} {'AND' if where_clause else 'WHERE'} result = 'failed'",
            params,
        )["count"]
        execution_running = fetch_one(
            conn,
            f"SELECT COUNT(*) AS count FROM executions {where_clause} {'AND' if where_clause else 'WHERE'} status = 'running'",
            params,
        )["count"]
        denominator = max(execution_passed + execution_failed, 1)
        pass_rate = round(execution_passed / denominator * 100, 1) if execution_total else 0

        recent_query = """
            SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial
            FROM executions e
            LEFT JOIN test_cases tc ON tc.id = e.test_case_id
            LEFT JOIN devices d ON d.id = e.device_id
        """
        recent_where_clause = ""
        if project_id is not None:
            recent_where_clause = "WHERE e.project_id = ?"
        if recent_where_clause:
            recent_query += f" {recent_where_clause}"
        recent_query += " ORDER BY e.created_at DESC LIMIT 6"
        recent_executions = [serialize_execution(item) for item in fetch_all(conn, recent_query, params)]

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
        _ = get_device_or_404(conn, device_id)
        now = utc_now()
        conn.execute(
            "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
            (user_name, now, now, device_id),
        )
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
                payload.status if payload.status is not None else device["status"],
                now,
                device_id,
            ),
        )
        return success(get_device_or_404(conn, device_id), "设备信息已更新")


@app.delete("/devices/{device_id}/")
def delete_device(device_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_device_or_404(conn, device_id)
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        return success(None, "设备已删除")


@app.get("/packages/")
def list_packages(project_id: int | None = Query(default=None), search: str | None = Query(default=None)) -> dict[str, Any]:
    query = "SELECT * FROM packages WHERE 1 = 1"
    params: list[Any] = []
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
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
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
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
def get_element_image_categories() -> dict[str, Any]:
    return success(list_image_categories())


@app.post("/elements/image-categories/create/")
def create_element_image_category(payload: ImageCategoryPayload) -> dict[str, Any]:
    category_name = normalize_category_name(payload.name)
    category_path = get_element_asset_root() / category_name
    if category_path.exists():
        raise HTTPException(status_code=400, detail="图片分类已存在")
    category_path.mkdir(parents=True, exist_ok=True)
    return success({"name": category_name}, "图片分类已创建", 201)


@app.delete("/elements/image-categories/{category_name}/")
def delete_element_image_category(category_name: str) -> dict[str, Any]:
    name = normalize_category_name(category_name)
    if name == "common":
        raise HTTPException(status_code=400, detail="默认分类不可删除")

    category_path = get_element_asset_root() / name
    if not category_path.exists():
        raise HTTPException(status_code=404, detail="图片分类不存在")
    if any(category_path.iterdir()):
        raise HTTPException(status_code=400, detail="分类不为空，无法删除")
    category_path.rmdir()
    return success(None, "图片分类已删除")


@app.get("/elements/assets/{asset_path:path}")
def get_element_asset(asset_path: str) -> FileResponse:
    file_path = resolve_element_asset_path(asset_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="元素资源不存在")
    return FileResponse(str(file_path), media_type=get_report_content_type(file_path))


@app.get("/elements/{element_id}/preview/")
def preview_element(element_id: int) -> FileResponse:
    with connection() as conn:
        element = get_element_or_404(conn, element_id)
        image_path = build_element_image_path(element)
    file_path = resolve_element_asset_path(image_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="元素图片不存在")
    return FileResponse(str(file_path), media_type=get_report_content_type(file_path))


@app.post("/elements/")
def create_element(payload: ElementPayload) -> dict[str, Any]:
    with connection() as conn:
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

    category_name = normalize_category_name(category)
    file_hash = compute_file_hash(content)

    with connection() as conn:
        duplicate = find_duplicate_element_asset(conn, file_hash, exclude_element_id=element_id)
        if duplicate is not None:
            image_path = build_element_image_path(duplicate)
            duplicate_config = duplicate.get("config", {})
            duplicate_category = ""
            if isinstance(duplicate_config, dict):
                duplicate_category = str(duplicate_config.get("image_category") or "")
            if not duplicate_category and "/" in image_path:
                duplicate_category = image_path.split("/", 1)[0]
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

    target_dir = get_element_asset_root() / category_name
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
    if project_id is not None:
        query += " AND tc.project_id = ?"
        params.append(project_id)
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
        if payload.package_id is not None:
            _ = get_package_or_404(conn, payload.package_id)
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
        if payload.package_id is not None:
            _ = get_package_or_404(conn, payload.package_id)
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
        conn.execute("DELETE FROM test_cases WHERE id = ?", (test_case_id,))
        return success(None, "测试用例已删除")


@app.post("/test-cases/{test_case_id}/execute/")
def execute_test_case(test_case_id: int, payload: ExecuteTestCasePayload) -> dict[str, Any]:
    with connection() as conn:
        test_case = get_test_case_or_404(conn, test_case_id)
        _ = get_device_or_404(conn, payload.device_id)
        now = utc_now()
        conn.execute(
            """
            INSERT INTO executions (
                project_id, test_case_id, device_id, status, result, progress, trigger_mode, triggered_by,
                logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
                started_at, finished_at, duration, created_at, updated_at
            ) VALUES (?, ?, ?, 'pending', '', 0, ?, ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
            """,
            (test_case["project_id"], test_case_id, payload.device_id, payload.trigger_mode, payload.triggered_by, now, now),
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
    if project_id is not None:
        query += " AND e.project_id = ?"
        params.append(project_id)
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
            "UPDATE executions SET status = 'stopped', finished_at = COALESCE(finished_at, ?), updated_at = ?, logs = ? WHERE id = ?",
            (now, now, json_dumps(logs), execution_id),
        )
        write_execution_report(conn, execution_id)
        return success(get_execution_or_404(conn, execution_id), "执行已停止")


@app.delete("/executions/{execution_id}/")
def delete_execution(execution_id: int) -> dict[str, Any]:
    with connection() as conn:
        execution = get_execution_or_404(conn, execution_id)
        if execution["status"] in {"pending", "running"} and execution.get("device_id"):
            finish_device_lock(conn, execution["device_id"])
        conn.execute("DELETE FROM executions WHERE id = ?", (execution_id,))
        return success(None, "执行记录已删除")


@app.get("/settings/current/")
def get_current_settings() -> dict[str, Any]:
    with connection() as conn:
        return success(get_settings(conn))


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
