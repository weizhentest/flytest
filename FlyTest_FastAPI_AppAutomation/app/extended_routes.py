from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from threading import Thread
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .database import connection, fetch_all, fetch_one, json_dumps, json_loads, utc_now
from .reporting import write_execution_report
from .schemas import (
    ComponentPackagePayload,
    ComponentPayload,
    CustomComponentPayload,
    ScheduledTaskPayload,
    TestSuitePayload,
    TestSuiteRunPayload,
)

try:
    from croniter import croniter
except Exception:  # pragma: no cover
    croniter = None

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


router = APIRouter()


def success(data: Any = None, message: str = "success", code: int = 200) -> dict[str, Any]:
    return {"status": "success", "code": code, "message": message, "data": data}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def compute_next_run(
    trigger_type: str,
    cron_expression: str,
    interval_seconds: int | None,
    execute_at: str | None,
) -> str | None:
    current = now_dt()
    if trigger_type == "INTERVAL" and interval_seconds:
        return (current + timedelta(seconds=interval_seconds)).isoformat()
    if trigger_type == "ONCE":
        scheduled = parse_dt(execute_at)
        if scheduled and scheduled > current:
            return scheduled.isoformat()
        return None
    if trigger_type == "CRON" and cron_expression and croniter:
        try:
            return croniter(cron_expression, current).get_next(datetime).isoformat()
        except Exception:
            return None
    return None


def serialize_component(row: dict[str, Any]) -> dict[str, Any]:
    row["schema"] = json_loads(row.pop("schema_json", None), {})
    row["default_config"] = json_loads(row.get("default_config"), {})
    row["enabled"] = bool(row.get("enabled"))
    return row


def serialize_custom_component(row: dict[str, Any]) -> dict[str, Any]:
    row["schema"] = json_loads(row.pop("schema_json", None), {})
    row["default_config"] = json_loads(row.get("default_config"), {})
    row["steps"] = json_loads(row.pop("steps_json", None), [])
    row["enabled"] = bool(row.get("enabled"))
    return row


def serialize_component_package(row: dict[str, Any]) -> dict[str, Any]:
    row["manifest"] = json_loads(row.pop("manifest_json", None), {})
    return row


def _sanitize_package_filename(name: str, suffix: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9._-]+", "-", (name or "app-component-pack").strip()).strip("-._")
    return f"{base or 'app-component-pack'}.{suffix}"


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_manifest_component(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or "").strip(),
        "type": str(item.get("type") or "").strip(),
        "category": str(item.get("category") or "").strip(),
        "description": str(item.get("description") or "").strip(),
        "schema": item.get("schema") if isinstance(item.get("schema"), dict) else {},
        "default_config": item.get("default_config") if isinstance(item.get("default_config"), dict) else {},
        "enabled": _coerce_bool(item.get("enabled"), True),
        "sort_order": int(item.get("sort_order") or 0),
    }


def _normalize_manifest_custom_component(item: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_manifest_component(item)
    normalized["steps"] = item.get("steps") if isinstance(item.get("steps"), list) else []
    return normalized


def _parse_component_package_manifest(filename: str, content: bytes) -> dict[str, Any]:
    text = content.decode("utf-8")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "json":
        manifest = json.loads(text)
    elif suffix in {"yaml", "yml"}:
        if yaml is None:
            raise HTTPException(status_code=500, detail="当前环境未安装 PyYAML，暂不支持 YAML 组件包，请先安装 pyyaml 或改用 JSON。")
        manifest = yaml.safe_load(text)
    else:
        try:
            manifest = json.loads(text)
        except json.JSONDecodeError:
            if yaml is None:
                raise HTTPException(status_code=400, detail="组件包文件格式不支持，请上传 .json/.yaml/.yml 文件。")
            manifest = yaml.safe_load(text)

    if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="组件包内容格式错误，manifest 必须是对象。")
    return manifest


def _install_component_package(conn, manifest: dict[str, Any], *, overwrite: bool, source: str) -> dict[str, Any]:
    component_items = manifest.get("components") if isinstance(manifest.get("components"), list) else []
    custom_component_items = (
        manifest.get("custom_components") if isinstance(manifest.get("custom_components"), list) else []
    )
    if not component_items and not custom_component_items:
        raise HTTPException(status_code=400, detail="组件包缺少 components 或 custom_components 列表。")

    base_created = 0
    base_updated = 0
    base_skipped = 0
    custom_created = 0
    custom_updated = 0
    custom_skipped = 0
    errors: list[str] = []
    now = utc_now()

    for item in component_items:
        if not isinstance(item, dict):
            errors.append("基础组件定义格式错误")
            continue
        normalized = _normalize_manifest_component(item)
        if not normalized["type"] or not normalized["name"]:
            errors.append("基础组件缺少 name 或 type")
            continue

        existing = fetch_one(conn, "SELECT id FROM components WHERE type = ?", (normalized["type"],))
        if existing is None:
            conn.execute(
                """
                INSERT INTO components (
                    name, type, category, description, schema_json, default_config,
                    enabled, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["name"],
                    normalized["type"],
                    normalized["category"],
                    normalized["description"],
                    json_dumps(normalized["schema"]),
                    json_dumps(normalized["default_config"]),
                    1 if normalized["enabled"] else 0,
                    normalized["sort_order"],
                    now,
                    now,
                ),
            )
            base_created += 1
            continue

        if not overwrite:
            base_skipped += 1
            continue

        conn.execute(
            """
            UPDATE components
            SET name = ?, category = ?, description = ?, schema_json = ?, default_config = ?,
                enabled = ?, sort_order = ?, updated_at = ?
            WHERE type = ?
            """,
            (
                normalized["name"],
                normalized["category"],
                normalized["description"],
                json_dumps(normalized["schema"]),
                json_dumps(normalized["default_config"]),
                1 if normalized["enabled"] else 0,
                normalized["sort_order"],
                now,
                normalized["type"],
            ),
        )
        base_updated += 1

    for item in custom_component_items:
        if not isinstance(item, dict):
            errors.append("自定义组件定义格式错误")
            continue
        normalized = _normalize_manifest_custom_component(item)
        if not normalized["type"] or not normalized["name"]:
            errors.append("自定义组件缺少 name 或 type")
            continue

        existing = fetch_one(conn, "SELECT id FROM custom_components WHERE type = ?", (normalized["type"],))
        if existing is None:
            conn.execute(
                """
                INSERT INTO custom_components (
                    name, type, description, schema_json, default_config, steps_json,
                    enabled, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["name"],
                    normalized["type"],
                    normalized["description"],
                    json_dumps(normalized["schema"]),
                    json_dumps(normalized["default_config"]),
                    json_dumps(normalized["steps"]),
                    1 if normalized["enabled"] else 0,
                    normalized["sort_order"],
                    now,
                    now,
                ),
            )
            custom_created += 1
            continue

        if not overwrite:
            custom_skipped += 1
            continue

        conn.execute(
            """
            UPDATE custom_components
            SET name = ?, description = ?, schema_json = ?, default_config = ?, steps_json = ?,
                enabled = ?, sort_order = ?, updated_at = ?
            WHERE type = ?
            """,
            (
                normalized["name"],
                normalized["description"],
                json_dumps(normalized["schema"]),
                json_dumps(normalized["default_config"]),
                json_dumps(normalized["steps"]),
                1 if normalized["enabled"] else 0,
                normalized["sort_order"],
                now,
                normalized["type"],
            ),
        )
        custom_updated += 1

    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))

    conn.execute(
        """
        INSERT INTO component_packages (name, version, description, author, source, manifest_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(manifest.get("name") or "app-component-pack").strip() or "app-component-pack",
            str(manifest.get("version") or "").strip(),
            str(manifest.get("description") or "").strip(),
            str(manifest.get("author") or "").strip(),
            source,
            json_dumps(manifest),
            now,
            now,
        ),
    )
    package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    package_row = fetch_one(conn, "SELECT * FROM component_packages WHERE id = ?", (package_id,))
    return {
        "package": serialize_component_package(package_row or {}),
        "counts": {
            "base_created": base_created,
            "base_updated": base_updated,
            "base_skipped": base_skipped,
            "custom_created": custom_created,
            "custom_updated": custom_updated,
            "custom_skipped": custom_skipped,
        },
    }


def _build_component_package_manifest(conn, *, include_disabled: bool, name: str, version: str, author: str, description: str) -> dict[str, Any]:
    component_query = "SELECT * FROM components"
    custom_query = "SELECT * FROM custom_components"
    params: tuple[Any, ...] = ()
    if not include_disabled:
        component_query += " WHERE enabled = 1"
        custom_query += " WHERE enabled = 1"

    component_rows = [serialize_component(dict(row)) for row in fetch_all(conn, component_query + " ORDER BY sort_order ASC, updated_at DESC", params)]
    custom_rows = [serialize_custom_component(dict(row)) for row in fetch_all(conn, custom_query + " ORDER BY sort_order ASC, updated_at DESC", params)]

    return {
        "name": name,
        "version": version,
        "description": description,
        "author": author,
        "exported_at": utc_now(),
        "components": [
            {
                "type": item["type"],
                "name": item["name"],
                "category": item["category"],
                "description": item["description"],
                "schema": item["schema"],
                "default_config": item["default_config"],
                "enabled": item["enabled"],
                "sort_order": item["sort_order"],
            }
            for item in component_rows
        ],
        "custom_components": [
            {
                "type": item["type"],
                "name": item["name"],
                "description": item["description"],
                "schema": item["schema"],
                "default_config": item["default_config"],
                "steps": item["steps"],
                "enabled": item["enabled"],
                "sort_order": item["sort_order"],
            }
            for item in custom_rows
        ],
    }


def serialize_suite_case(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "test_case_id": row["test_case_id"],
        "order": row["sort_order"],
        "test_case": {
            "id": row["test_case_id"],
            "name": row["name"],
            "description": row["description"],
            "package_name": row.get("package_name") or "",
            "updated_at": row["updated_at"],
        },
    }


def serialize_suite(row: dict[str, Any], conn) -> dict[str, Any]:
    cases = fetch_all(
        conn,
        """
        SELECT sc.id, sc.test_case_id, sc.sort_order, tc.name, tc.description, tc.updated_at, p.package_name
        FROM test_suite_cases sc
        JOIN test_cases tc ON tc.id = sc.test_case_id
        LEFT JOIN packages p ON p.id = tc.package_id
        WHERE sc.test_suite_id = ?
        ORDER BY sc.sort_order ASC, sc.id ASC
        """,
        (row["id"],),
    )
    execution_stats = fetch_one(
        conn,
        """
        SELECT
            SUM(CASE WHEN result = 'passed' THEN 1 ELSE 0 END) AS passed_count,
            SUM(CASE WHEN result = 'failed' THEN 1 ELSE 0 END) AS failed_count,
            SUM(CASE WHEN result = 'stopped' OR status = 'stopped' THEN 1 ELSE 0 END) AS stopped_count
        FROM executions
        WHERE test_suite_id = ?
        """,
        (row["id"],),
    )
    row["test_case_count"] = len(cases)
    row["suite_cases"] = [serialize_suite_case(item) for item in cases]
    row["stopped_count"] = int((execution_stats or {}).get("stopped_count") or 0)
    return row


def serialize_task(row: dict[str, Any]) -> dict[str, Any]:
    row["notify_emails"] = json_loads(row.get("notify_emails"), [])
    row["last_result"] = json_loads(row.get("last_result"), {})
    row["notify_on_success"] = bool(row.get("notify_on_success"))
    row["notify_on_failure"] = bool(row.get("notify_on_failure"))
    return row


def serialize_notification(row: dict[str, Any]) -> dict[str, Any]:
    row["recipient_info"] = json_loads(row.get("recipient_info"), [])
    row["webhook_bot_info"] = json_loads(row.get("webhook_bot_info"), {})
    row["response_info"] = json_loads(row.get("response_info"), {})
    row["is_retried"] = bool(row.get("is_retried"))
    return row


def serialize_execution(row: dict[str, Any]) -> dict[str, Any]:
    row["logs"] = json_loads(row.get("logs"), [])
    total_steps = int(row.get("total_steps") or 0)
    passed_steps = int(row.get("passed_steps") or 0)
    row["pass_rate"] = round(passed_steps / total_steps * 100, 1) if total_steps else 0
    return row


def get_suite_or_404(conn, suite_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM test_suites WHERE id = ?", (suite_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="测试套件不存在")
    return serialize_suite(row, conn)


def get_task_or_404(conn, task_id: int) -> dict[str, Any]:
    row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="定时任务不存在")
    return serialize_task(row)


def create_notification_log(
    task_id: int | None,
    task_name: str,
    task_type: str,
    actual_notification_type: str,
    content: str,
    status: str = "success",
    error_message: str = "",
    recipients: list[str] | None = None,
    response_info: dict[str, Any] | None = None,
    webhook_bot_info: dict[str, Any] | None = None,
    db_conn=None,
) -> None:
    if db_conn is not None:
        now = utc_now()
        db_conn.execute(
            """
            INSERT INTO notification_logs (
                task_id, task_name, task_type, notification_type, actual_notification_type,
                sender_name, sender_email, recipient_info, webhook_bot_info, notification_content,
                status, error_message, response_info, created_at, sent_at, retry_count, is_retried
            ) VALUES (?, ?, ?, 'task_execution', ?, 'FlyTest', 'noreply@flytest.local', ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                task_id,
                task_name,
                task_type,
                actual_notification_type,
                json_dumps([{"email": item, "name": item.split("@")[0]} for item in (recipients or [])]),
                json_dumps(webhook_bot_info or {}),
                content,
                status,
                error_message,
                json_dumps(response_info or {}),
                now,
                now,
            ),
        )
        return

    with connection() as conn:
        create_notification_log(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            actual_notification_type=actual_notification_type,
            content=content,
            status=status,
            error_message=error_message,
            recipients=recipients,
            response_info=response_info,
            webhook_bot_info=webhook_bot_info,
            db_conn=conn,
        )


def normalize_task_payload(task: dict[str, Any]) -> None:
    if not task.get("device_id"):
        raise HTTPException(status_code=400, detail="定时任务缺少执行设备配置")
    if task["task_type"] == "TEST_SUITE":
        if not task.get("test_suite_id"):
            raise HTTPException(status_code=400, detail="定时任务缺少测试套件配置")
        return
    if task["task_type"] == "TEST_CASE":
        if not task.get("test_case_id"):
            raise HTTPException(status_code=400, detail="定时任务缺少测试用例配置")
        return
    raise HTTPException(status_code=400, detail="不支持的任务类型")


def update_task_run_state(
    conn,
    task_id: int,
    *,
    next_run_time: str | None,
    status: str,
    success_count: int = 0,
    failure_count: int = 0,
    error_message: str = "",
    last_result: dict[str, Any] | None = None,
    total_run_increment: int = 1,
    update_last_run_time: bool = True,
) -> None:
    now = utc_now()
    last_run_time = now if update_last_run_time else None
    conn.execute(
        """
        UPDATE scheduled_tasks
        SET last_run_time = COALESCE(?, last_run_time), next_run_time = ?, total_runs = total_runs + ?,
            successful_runs = successful_runs + ?, failed_runs = failed_runs + ?,
            status = ?, error_message = ?, last_result = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            last_run_time,
            next_run_time,
            total_run_increment,
            success_count,
            failure_count,
            status,
            error_message,
            json_dumps(last_result or {}),
            now,
            task_id,
        ),
    )


def _resolve_task_status_after_completion(task: dict[str, Any], *, success: bool) -> str:
    trigger_type = str(task.get("trigger_type") or "").upper()
    current_status = str(task.get("status") or "ACTIVE").upper()
    if trigger_type == "ONCE":
        return "COMPLETED" if success else "FAILED"
    if current_status in {"ACTIVE", "PAUSED"}:
        return current_status
    return "ACTIVE" if success else "FAILED"


def _should_notify_for_result(task: dict[str, Any], *, success: bool) -> bool:
    if not str(task.get("notification_type") or "").strip():
        return False
    return bool(task.get("notify_on_success")) if success else bool(task.get("notify_on_failure"))


def _create_task_notification(
    conn,
    task: dict[str, Any],
    *,
    success: bool,
    content: str,
    error_message: str,
    response_info: dict[str, Any],
) -> None:
    if not _should_notify_for_result(task, success=success):
        return

    create_notification_log(
        task_id=task["id"],
        task_name=task["name"],
        task_type=task["task_type"],
        actual_notification_type=task["notification_type"],
        content=content,
        status="success" if success else "failed",
        error_message=error_message,
        recipients=task["notify_emails"],
        response_info={
            "delivery_status": "simulated",
            **response_info,
        },
        db_conn=conn,
    )


def _finalize_case_task_run(task_id: int, execution_id: int, *, triggered_by: str, triggered_at: str) -> None:
    with connection() as conn:
        task_row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        if task_row is None:
            return

        task = serialize_task(task_row)
        execution = fetch_one(
            conn,
            """
            SELECT id, test_case_id, status, result, error_message, finished_at
            FROM executions
            WHERE id = ?
            """,
            (execution_id,),
        )

        if execution is None:
            outcome = "failed"
            success = False
            error_message = "执行记录不存在"
            finished_at = utc_now()
            test_case_id = task.get("test_case_id")
        else:
            outcome = str(execution.get("result") or execution.get("status") or "failed").strip().lower() or "failed"
            success = outcome == "passed"
            error_message = "" if success else str(execution.get("error_message") or outcome or "执行失败")
            finished_at = str(execution.get("finished_at") or utc_now())
            test_case_id = execution.get("test_case_id")

        last_result = {
            "task_id": task_id,
            "task_type": task["task_type"],
            "status": outcome,
            "execution_id": execution_id,
            "test_case_id": test_case_id,
            "triggered_by": triggered_by,
            "triggered_at": triggered_at,
            "finished_at": finished_at,
        }
        if error_message:
            last_result["error_message"] = error_message

        update_task_run_state(
            conn,
            task_id,
            next_run_time=task.get("next_run_time"),
            status=_resolve_task_status_after_completion(task, success=success),
            success_count=1 if success else 0,
            failure_count=0 if success else 1,
            error_message=error_message,
            last_result=last_result,
            total_run_increment=0,
            update_last_run_time=False,
        )

        response_info = {
            "task_id": task_id,
            "task_type": task["task_type"],
            "triggered_by": triggered_by,
            "triggered_at": triggered_at,
            "execution_id": execution_id,
            "test_case_id": test_case_id,
            "execution_result": outcome,
            "finished_at": finished_at,
        }
        _create_task_notification(
            conn,
            task,
            success=success,
            content=(
                f"任务 {task['name']} 执行成功"
                if success
                else f"任务 {task['name']} 执行失败"
            ),
            error_message=error_message,
            response_info=response_info,
        )


def _finalize_suite_task_run(
    task_id: int,
    suite_id: int,
    execution_ids: list[int],
    *,
    triggered_by: str,
    triggered_at: str,
) -> None:
    with connection() as conn:
        task_row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        if task_row is None:
            return

        task = serialize_task(task_row)
        suite = fetch_one(
            conn,
            """
            SELECT id, execution_status, execution_result, passed_count, failed_count, last_run_at
            FROM test_suites
            WHERE id = ?
            """,
            (suite_id,),
        )

        if suite is None:
            outcome = "failed"
            success = False
            error_message = "测试套件不存在"
            finished_at = utc_now()
        else:
            outcome = str(suite.get("execution_result") or suite.get("execution_status") or "failed").strip().lower() or "failed"
            success = outcome == "passed"
            finished_at = str(suite.get("last_run_at") or utc_now())
            passed_count = int(suite.get("passed_count") or 0)
            failed_count = int(suite.get("failed_count") or 0)
            if success:
                error_message = ""
            elif outcome == "stopped":
                error_message = "测试套件执行已停止"
            else:
                error_message = f"测试套件执行失败（通过 {passed_count}，失败 {failed_count}）"

        last_result = {
            "task_id": task_id,
            "task_type": task["task_type"],
            "status": outcome,
            "execution_ids": execution_ids,
            "test_case_count": len(execution_ids),
            "test_suite_id": suite_id,
            "triggered_by": triggered_by,
            "triggered_at": triggered_at,
            "finished_at": finished_at,
        }
        if error_message:
            last_result["error_message"] = error_message

        update_task_run_state(
            conn,
            task_id,
            next_run_time=task.get("next_run_time"),
            status=_resolve_task_status_after_completion(task, success=success),
            success_count=1 if success else 0,
            failure_count=0 if success else 1,
            error_message=error_message,
            last_result=last_result,
            total_run_increment=0,
            update_last_run_time=False,
        )

        response_info = {
            "task_id": task_id,
            "task_type": task["task_type"],
            "triggered_by": triggered_by,
            "triggered_at": triggered_at,
            "execution_ids": execution_ids,
            "test_case_count": len(execution_ids),
            "test_suite_id": suite_id,
            "suite_result": outcome,
            "finished_at": finished_at,
        }
        _create_task_notification(
            conn,
            task,
            success=success,
            content=(
                f"任务 {task['name']} 执行成功"
                if success
                else f"任务 {task['name']} 执行失败"
            ),
            error_message=error_message,
            response_info=response_info,
        )


def _run_case_task_in_background(task_id: int, execution_id: int, *, triggered_by: str, triggered_at: str) -> None:
    execute_case_background(execution_id)
    _finalize_case_task_run(task_id, execution_id, triggered_by=triggered_by, triggered_at=triggered_at)


def _run_suite_task_in_background(
    task_id: int,
    suite_id: int,
    execution_ids: list[int],
    *,
    triggered_by: str,
    triggered_at: str,
) -> None:
    run_suite_background(suite_id, execution_ids)
    _finalize_suite_task_run(task_id, suite_id, execution_ids, triggered_by=triggered_by, triggered_at=triggered_at)


def simulate_case_execution(execution_id: int) -> None:
    try:
        with connection() as conn:
            execution = fetch_one(conn, "SELECT * FROM executions WHERE id = ?", (execution_id,))
            if execution is None:
                return
            test_case = fetch_one(conn, "SELECT * FROM test_cases WHERE id = ?", (execution["test_case_id"],))
            device = fetch_one(conn, "SELECT * FROM devices WHERE id = ?", (execution["device_id"],))
            if test_case is None or device is None:
                return

            steps = json_loads(test_case.get("ui_flow"), {}).get("steps")
            if not isinstance(steps, list) or not steps:
                steps = [{"name": "准备环境"}, {"name": "执行动作"}, {"name": "断言结果"}]

            total_steps = max(len(steps), 1)
            started_at = utc_now()
            logs = [{"timestamp": started_at, "level": "info", "message": f"开始执行 {test_case['name']}"}]
            conn.execute(
                """
                UPDATE executions
                SET status = 'running', progress = 5, started_at = ?, logs = ?, total_steps = ?, passed_steps = 0,
                    failed_steps = 0, updated_at = ?
                WHERE id = ?
                """,
                (started_at, json_dumps(logs), total_steps, started_at, execution_id),
            )
            conn.execute(
                "UPDATE devices SET status = 'locked', locked_by = ?, locked_at = ?, updated_at = ? WHERE id = ?",
                (execution.get("triggered_by") or "FlyTest", started_at, started_at, execution["device_id"]),
            )

        for index, step in enumerate(steps, start=1):
            time.sleep(0.6)
            with connection() as conn:
                current = fetch_one(conn, "SELECT status, logs FROM executions WHERE id = ?", (execution_id,))
                if current is None:
                    return
                if current.get("status") == "stopped":
                    logs = json_loads(current.get("logs"), [])
                    logs.append({"timestamp": utc_now(), "level": "warning", "message": "执行已手动停止"})
                    now = utc_now()
                    conn.execute(
                        """
                        UPDATE executions
                        SET result = 'stopped', finished_at = ?, logs = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (now, json_dumps(logs), now, execution_id),
                    )
                    write_execution_report(conn, execution_id)
                    execution = fetch_one(conn, "SELECT device_id, test_suite_id FROM executions WHERE id = ?", (execution_id,))
                    if execution:
                        conn.execute(
                            "UPDATE devices SET status = 'available', locked_by = '', locked_at = NULL, updated_at = ? WHERE id = ?",
                            (now, execution["device_id"]),
                        )
                        if execution.get("test_suite_id"):
                            refresh_suite_stats(conn, execution["test_suite_id"])
                    return

                logs = json_loads(current.get("logs"), [])
                logs.append(
                    {
                        "timestamp": utc_now(),
                        "level": "info",
                        "message": f"完成步骤 {index}/{total_steps}: {step.get('name') or step.get('action') or 'step'}",
                    }
                )
                progress = min(98, int(index / total_steps * 100))
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
            row = fetch_one(conn, "SELECT logs FROM executions WHERE id = ?", (execution_id,))
            logs = json_loads(row.get("logs") if row else "[]", [])
            logs.append({"timestamp": finished_at, "level": "info", "message": "执行完成"})
            conn.execute(
                """
                UPDATE executions
                SET status = 'completed', result = 'passed', progress = 100, finished_at = ?, duration = ?,
                    logs = ?, passed_steps = ?, report_summary = ?, failed_steps = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    finished_at,
                    0.6 * total_steps,
                    json_dumps(logs),
                    total_steps,
                    "执行完成，可在报告页查看概要结果。",
                    finished_at,
                    execution_id,
                ),
            )
            write_execution_report(conn, execution_id)
            execution = fetch_one(conn, "SELECT test_case_id, test_suite_id, device_id FROM executions WHERE id = ?", (execution_id,))
            conn.execute(
                "UPDATE test_cases SET last_result = 'passed', last_run_at = ?, updated_at = ? WHERE id = ?",
                (finished_at, finished_at, execution["test_case_id"]),
            )
            conn.execute(
                "UPDATE devices SET status = 'available', locked_by = '', locked_at = NULL, updated_at = ? WHERE id = ?",
                (finished_at, execution["device_id"]),
            )
            if execution.get("test_suite_id"):
                refresh_suite_stats(conn, execution["test_suite_id"])
    except Exception as exc:
        with connection() as conn:
            execution = fetch_one(conn, "SELECT device_id, test_suite_id, logs FROM executions WHERE id = ?", (execution_id,))
            if execution is None:
                return
            logs = json_loads(execution.get("logs"), [])
            logs.append({"timestamp": utc_now(), "level": "error", "message": str(exc)})
            now = utc_now()
            conn.execute(
                """
                UPDATE executions
                SET status = 'failed', result = 'failed', error_message = ?, finished_at = ?, logs = ?,
                    failed_steps = CASE WHEN total_steps > 0 THEN 1 ELSE 0 END, updated_at = ?
                WHERE id = ?
                """,
                (str(exc), now, json_dumps(logs), now, execution_id),
            )
            write_execution_report(conn, execution_id)
            conn.execute(
                "UPDATE devices SET status = 'available', locked_by = '', locked_at = NULL, updated_at = ? WHERE id = ?",
                (now, execution["device_id"]),
            )
            if execution.get("test_suite_id"):
                refresh_suite_stats(conn, execution["test_suite_id"])


def refresh_suite_stats(conn, suite_id: int) -> None:
    rows = fetch_all(
        conn,
        """
        SELECT result, status
        FROM executions
        WHERE test_suite_id = ?
        ORDER BY id DESC
        """,
        (suite_id,),
    )
    if not rows:
        return

    passed = len([item for item in rows if item.get("result") == "passed"])
    failed = len([item for item in rows if item.get("result") == "failed"])
    stopped = len([item for item in rows if item.get("result") == "stopped" or item.get("status") == "stopped"])
    has_running = any(item.get("status") in {"pending", "running"} for item in rows)
    execution_status = "running" if has_running else "completed"
    if has_running:
        execution_result = ""
    elif failed:
        execution_result = "failed"
    elif stopped:
        execution_result = "stopped"
    elif passed:
        execution_result = "passed"
    else:
        execution_result = ""
    conn.execute(
        """
        UPDATE test_suites
        SET execution_status = ?, execution_result = ?, passed_count = ?, failed_count = ?, last_run_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (execution_status, execution_result, passed, failed, utc_now(), utc_now(), suite_id),
    )


def create_execution(
    conn,
    project_id: int,
    test_case_id: int,
    device_id: int,
    triggered_by: str,
    test_suite_id: int | None = None,
) -> int:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO executions (
            project_id, test_case_id, test_suite_id, device_id, status, result, progress, trigger_mode,
            triggered_by, logs, report_summary, report_path, error_message, total_steps, passed_steps, failed_steps,
            started_at, finished_at, duration, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'pending', '', 0, 'manual', ?, '[]', '', '', '', 0, 0, 0, NULL, NULL, 0, ?, ?)
        """,
        (project_id, test_case_id, test_suite_id, device_id, triggered_by, now, now),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def execute_case_background(execution_id: int) -> None:
    from .main import run_execution

    run_execution(execution_id)


def run_suite_background(suite_id: int, execution_ids: list[int]) -> None:
    for execution_id in execution_ids:
        execute_case_background(execution_id)
    with connection() as conn:
        refresh_suite_stats(conn, suite_id)


def _detach_notification_logs_for_tasks(conn, task_ids: list[int]) -> None:
    if not task_ids:
        return
    placeholders = ", ".join("?" for _ in task_ids)
    conn.execute(f"UPDATE notification_logs SET task_id = NULL WHERE task_id IN ({placeholders})", tuple(task_ids))


def _delete_scheduled_tasks(conn, task_ids: list[int]) -> None:
    if not task_ids:
        return
    _detach_notification_logs_for_tasks(conn, task_ids)
    placeholders = ", ".join("?" for _ in task_ids)
    conn.execute(f"DELETE FROM scheduled_tasks WHERE id IN ({placeholders})", tuple(task_ids))


@router.get("/components/")
def list_components() -> dict[str, Any]:
    with connection() as conn:
        rows = [serialize_component(item) for item in fetch_all(conn, "SELECT * FROM components ORDER BY sort_order ASC, updated_at DESC")]
    return success(rows)


@router.post("/components/")
def create_component(payload: ComponentPayload) -> dict[str, Any]:
    with connection() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO components (name, type, category, description, schema_json, default_config, enabled, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.type,
                payload.category,
                payload.description,
                json_dumps(payload.schema_definition),
                json_dumps(payload.default_config),
                1 if payload.enabled else 0,
                payload.sort_order,
                now,
                now,
            ),
        )
        component_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = fetch_one(conn, "SELECT * FROM components WHERE id = ?", (component_id,))
    return success(serialize_component(row or {}), "组件已创建", 201)


@router.get("/custom-components/")
def list_custom_components() -> dict[str, Any]:
    with connection() as conn:
        rows = [serialize_custom_component(item) for item in fetch_all(conn, "SELECT * FROM custom_components ORDER BY sort_order ASC, updated_at DESC")]
    return success(rows)


@router.post("/custom-components/")
def create_custom_component(payload: CustomComponentPayload) -> dict[str, Any]:
    with connection() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO custom_components (
                name, type, description, schema_json, default_config, steps_json, enabled, sort_order, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.type,
                payload.description,
                json_dumps(payload.schema_definition),
                json_dumps(payload.default_config),
                json_dumps(payload.steps),
                1 if payload.enabled else 0,
                payload.sort_order,
                now,
                now,
            ),
        )
        custom_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = fetch_one(conn, "SELECT * FROM custom_components WHERE id = ?", (custom_id,))
    return success(serialize_custom_component(row or {}), "自定义组件已创建", 201)


@router.put("/custom-components/{custom_id}/")
def update_custom_component(custom_id: int, payload: CustomComponentPayload) -> dict[str, Any]:
    with connection() as conn:
        existing = fetch_one(conn, "SELECT id FROM custom_components WHERE id = ?", (custom_id,))
        if existing is None:
            raise HTTPException(status_code=404, detail="自定义组件不存在")
        conn.execute(
            """
            UPDATE custom_components
            SET name = ?, type = ?, description = ?, schema_json = ?, default_config = ?, steps_json = ?,
                enabled = ?, sort_order = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name,
                payload.type,
                payload.description,
                json_dumps(payload.schema_definition),
                json_dumps(payload.default_config),
                json_dumps(payload.steps),
                1 if payload.enabled else 0,
                payload.sort_order,
                utc_now(),
                custom_id,
            ),
        )
        row = fetch_one(conn, "SELECT * FROM custom_components WHERE id = ?", (custom_id,))
    return success(serialize_custom_component(row or {}), "自定义组件已更新")


@router.delete("/custom-components/{custom_id}/")
def delete_custom_component(custom_id: int) -> dict[str, Any]:
    with connection() as conn:
        existing = fetch_one(conn, "SELECT id FROM custom_components WHERE id = ?", (custom_id,))
        if existing is None:
            raise HTTPException(status_code=404, detail="自定义组件不存在")
        conn.execute("DELETE FROM custom_components WHERE id = ?", (custom_id,))
    return success(None, "自定义组件已删除")


@router.get("/component-packages/")
def list_component_packages() -> dict[str, Any]:
    with connection() as conn:
        rows = [serialize_component_package(item) for item in fetch_all(conn, "SELECT * FROM component_packages ORDER BY updated_at DESC")]
    return success(rows)


@router.post("/component-packages/")
def create_component_package(payload: ComponentPackagePayload) -> dict[str, Any]:
    with connection() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO component_packages (name, version, description, author, source, manifest_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.version,
                payload.description,
                payload.author,
                payload.source,
                json_dumps(payload.manifest),
                now,
                now,
            ),
        )
        package_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = fetch_one(conn, "SELECT * FROM component_packages WHERE id = ?", (package_id,))
    return success(serialize_component_package(row or {}), "组件包已创建", 201)


@router.post("/component-packages/import/")
async def import_component_package(
    file: UploadFile = File(...),
    overwrite: str = Form(default="1"),
) -> dict[str, Any]:
    filename = str(file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="请上传组件包文件。")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="组件包文件为空。")

    manifest = _parse_component_package_manifest(filename, content)
    with connection() as conn:
        result = _install_component_package(conn, manifest, overwrite=_coerce_bool(overwrite, True), source="upload")
    return success(result, "组件包已导入", 201)


@router.get("/component-packages/export/")
def export_component_package(
    export_format: str = Query(default="yaml"),
    include_disabled: int = Query(default=0),
    name: str = Query(default="app-component-pack"),
    version: str = Query(default=""),
    author: str = Query(default=""),
    description: str = Query(default="导出的组件包"),
) -> dict[str, Any]:
    normalized_format = str(export_format or "yaml").strip().lower()
    if normalized_format not in {"json", "yaml", "yml"}:
        raise HTTPException(status_code=400, detail="导出格式仅支持 json 或 yaml。")

    manifest_version = version.strip() or datetime.now().strftime("%Y.%m.%d")
    with connection() as conn:
        manifest = _build_component_package_manifest(
            conn,
            include_disabled=bool(include_disabled),
            name=name.strip() or "app-component-pack",
            version=manifest_version,
            author=author.strip(),
            description=description.strip() or "导出的组件包",
        )

    if normalized_format == "json":
        content = json.dumps(manifest, ensure_ascii=False, indent=2)
        filename = _sanitize_package_filename(manifest["name"], "json")
        content_type = "application/json"
    else:
        if yaml is None:
            raise HTTPException(status_code=500, detail="当前环境未安装 PyYAML，暂不支持 YAML 导出，请先安装 pyyaml 或改用 JSON。")
        content = yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False)
        filename = _sanitize_package_filename(manifest["name"], "yaml")
        content_type = "application/x-yaml"

    return success(
        {
            "filename": filename,
            "content": content,
            "content_type": content_type,
            "export_format": "json" if normalized_format == "json" else "yaml",
            "component_count": len(manifest.get("components") or []),
            "custom_component_count": len(manifest.get("custom_components") or []),
        }
    )


@router.delete("/component-packages/{package_id}/")
def delete_component_package(package_id: int) -> dict[str, Any]:
    with connection() as conn:
        existing = fetch_one(conn, "SELECT id FROM component_packages WHERE id = ?", (package_id,))
        if existing is None:
            raise HTTPException(status_code=404, detail="组件包不存在")
        conn.execute("DELETE FROM component_packages WHERE id = ?", (package_id,))
    return success(None, "组件包已删除")


@router.get("/test-suites/")
def list_test_suites(project_id: int | None = Query(default=None), search: str | None = Query(default=None)) -> dict[str, Any]:
    query = "SELECT * FROM test_suites WHERE 1 = 1"
    params: list[Any] = []
    if project_id is not None:
        query += " AND project_id = ?"
        params.append(project_id)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY updated_at DESC"
    with connection() as conn:
        rows = [serialize_suite(item, conn) for item in fetch_all(conn, query, params)]
    return success(rows)


@router.get("/test-suites/{suite_id}/")
def get_test_suite(suite_id: int) -> dict[str, Any]:
    with connection() as conn:
        return success(get_suite_or_404(conn, suite_id))


@router.post("/test-suites/")
def create_test_suite(payload: TestSuitePayload, created_by: str = Query(default="FlyTest")) -> dict[str, Any]:
    with connection() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO test_suites (
                project_id, name, description, execution_status, execution_result, passed_count, failed_count,
                last_run_at, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, 'not_run', '', 0, 0, NULL, ?, ?, ?)
            """,
            (payload.project_id, payload.name, payload.description, created_by, now, now),
        )
        suite_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for index, test_case_id in enumerate(payload.test_case_ids):
            conn.execute(
                "INSERT OR IGNORE INTO test_suite_cases (test_suite_id, test_case_id, sort_order, created_at) VALUES (?, ?, ?, ?)",
                (suite_id, test_case_id, index, now),
            )
        suite = get_suite_or_404(conn, suite_id)
    return success(suite, "测试套件已创建", 201)


@router.put("/test-suites/{suite_id}/")
def update_test_suite(suite_id: int, payload: TestSuitePayload) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        conn.execute(
            "UPDATE test_suites SET project_id = ?, name = ?, description = ?, updated_at = ? WHERE id = ?",
            (payload.project_id, payload.name, payload.description, utc_now(), suite_id),
        )
        conn.execute("DELETE FROM test_suite_cases WHERE test_suite_id = ?", (suite_id,))
        now = utc_now()
        for index, test_case_id in enumerate(payload.test_case_ids):
            conn.execute(
                "INSERT INTO test_suite_cases (test_suite_id, test_case_id, sort_order, created_at) VALUES (?, ?, ?, ?)",
                (suite_id, test_case_id, index, now),
            )
        suite = get_suite_or_404(conn, suite_id)
    return success(suite, "测试套件已更新")


@router.delete("/test-suites/{suite_id}/")
def delete_test_suite(suite_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        now = utc_now()
        task_ids = [item["id"] for item in fetch_all(conn, "SELECT id FROM scheduled_tasks WHERE test_suite_id = ?", (suite_id,))]
        _delete_scheduled_tasks(conn, task_ids)
        conn.execute("UPDATE executions SET test_suite_id = NULL, updated_at = ? WHERE test_suite_id = ?", (now, suite_id))
        conn.execute("DELETE FROM test_suite_cases WHERE test_suite_id = ?", (suite_id,))
        conn.execute("DELETE FROM test_suites WHERE id = ?", (suite_id,))
    return success(None, "测试套件已删除")


@router.get("/test-suites/{suite_id}/test_cases/")
def get_suite_test_cases(suite_id: int) -> dict[str, Any]:
    with connection() as conn:
        suite = get_suite_or_404(conn, suite_id)
    return success(suite["suite_cases"])


@router.post("/test-suites/{suite_id}/add_test_case/")
def add_test_case_to_suite(suite_id: int, test_case_id: int = Query(...), order: int | None = Query(default=None)) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        if order is None:
            existing = fetch_one(conn, "SELECT MAX(sort_order) AS max_order FROM test_suite_cases WHERE test_suite_id = ?", (suite_id,))
            order = (existing["max_order"] or 0) + 1
        conn.execute(
            "INSERT OR IGNORE INTO test_suite_cases (test_suite_id, test_case_id, sort_order, created_at) VALUES (?, ?, ?, ?)",
            (suite_id, test_case_id, order, utc_now()),
        )
        suite = get_suite_or_404(conn, suite_id)
    return success(suite, "用例已加入套件")


@router.post("/test-suites/{suite_id}/remove_test_case/")
def remove_test_case_from_suite(suite_id: int, test_case_id: int = Query(...)) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        conn.execute("DELETE FROM test_suite_cases WHERE test_suite_id = ? AND test_case_id = ?", (suite_id, test_case_id))
        suite = get_suite_or_404(conn, suite_id)
    return success(suite, "用例已移出套件")


@router.post("/test-suites/{suite_id}/update_test_case_order/")
def update_suite_case_order(suite_id: int, test_case_orders: list[dict[str, int]]) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        for item in test_case_orders:
            conn.execute(
                "UPDATE test_suite_cases SET sort_order = ? WHERE test_suite_id = ? AND test_case_id = ?",
                (item["order"], suite_id, item["test_case_id"]),
            )
        suite = get_suite_or_404(conn, suite_id)
    return success(suite, "套件顺序已更新")


@router.post("/test-suites/{suite_id}/run/")
def run_test_suite(suite_id: int, payload: TestSuiteRunPayload) -> dict[str, Any]:
    with connection() as conn:
        suite = get_suite_or_404(conn, suite_id)
        if not suite["suite_cases"]:
            raise HTTPException(status_code=400, detail="该测试套件没有可执行的用例")
        conn.execute(
            "UPDATE test_suites SET execution_status = 'running', execution_result = '', updated_at = ? WHERE id = ?",
            (utc_now(), suite_id),
        )
        execution_ids: list[int] = []
        for item in suite["suite_cases"]:
            execution_ids.append(
                create_execution(conn, suite["project_id"], item["test_case"]["id"], payload.device_id, payload.triggered_by, suite_id)
            )
    Thread(target=run_suite_background, args=(suite_id, execution_ids), daemon=True).start()
    return success(
        {"suite_id": suite_id, "execution_ids": execution_ids, "test_case_count": len(execution_ids)},
        f"测试套件已提交执行，共 {len(execution_ids)} 个用例",
        201,
    )


@router.get("/test-suites/{suite_id}/executions/")
def get_suite_executions(suite_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_suite_or_404(conn, suite_id)
        rows = [
            serialize_execution(item)
            for item in fetch_all(
                conn,
                """
                SELECT e.*, tc.name AS case_name, d.name AS device_name, d.device_id AS device_serial
                FROM executions e
                LEFT JOIN test_cases tc ON tc.id = e.test_case_id
                LEFT JOIN devices d ON d.id = e.device_id
                WHERE e.test_suite_id = ?
                ORDER BY e.created_at DESC
                """,
                (suite_id,),
            )
        ]
    return success(rows)


def trigger_task_run(task_id: int, triggered_by: str = "FlyTest") -> dict[str, Any]:
    try:
        with connection() as conn:
            task = get_task_or_404(conn, task_id)
            normalize_task_payload(task)
            triggered_at = utc_now()
            next_run_time = compute_next_run(
                task["trigger_type"],
                task["cron_expression"],
                task["interval_seconds"],
                task["execute_at"],
            )
            next_status = task["status"]

            if task["task_type"] == "TEST_SUITE":
                suite = get_suite_or_404(conn, task["test_suite_id"])
                if not suite["suite_cases"]:
                    raise HTTPException(status_code=400, detail="测试套件中没有可执行的用例")
                execution_ids: list[int] = []
                for item in suite["suite_cases"]:
                    execution_ids.append(
                        create_execution(
                            conn,
                            task["project_id"],
                            item["test_case"]["id"],
                            task["device_id"],
                            triggered_by,
                            suite["id"],
                        )
                    )
                conn.execute(
                    "UPDATE test_suites SET execution_status = 'running', execution_result = '', updated_at = ? WHERE id = ?",
                    (triggered_at, suite["id"]),
                )
                Thread(
                    target=_run_suite_task_in_background,
                    args=(task_id, suite["id"], execution_ids),
                    kwargs={"triggered_by": triggered_by, "triggered_at": triggered_at},
                    daemon=True,
                ).start()
                payload = {"task_id": task_id, "execution_ids": execution_ids, "test_case_count": len(execution_ids)}
                last_result = {
                    "task_id": task_id,
                    "task_type": task["task_type"],
                    "status": "triggered",
                    "execution_ids": execution_ids,
                    "test_case_count": len(execution_ids),
                    "test_suite_id": suite["id"],
                    "triggered_by": triggered_by,
                    "triggered_at": triggered_at,
                }
            else:
                execution_id = create_execution(conn, task["project_id"], task["test_case_id"], task["device_id"], triggered_by, None)
                Thread(
                    target=_run_case_task_in_background,
                    args=(task_id, execution_id),
                    kwargs={"triggered_by": triggered_by, "triggered_at": triggered_at},
                    daemon=True,
                ).start()
                payload = {"task_id": task_id, "execution_id": execution_id}
                last_result = {
                    "task_id": task_id,
                    "task_type": task["task_type"],
                    "status": "triggered",
                    "execution_id": execution_id,
                    "test_case_id": task["test_case_id"],
                    "triggered_by": triggered_by,
                    "triggered_at": triggered_at,
                }

            update_task_run_state(
                conn,
                task_id,
                next_run_time=next_run_time,
                status=next_status,
                last_result=last_result,
            )
            row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))

        if False and task.get("notification_type") and (task.get("notify_on_success") or task.get("notify_on_failure")):
            create_notification_log(
                task_id=task_id,
                task_name=task["name"],
                task_type=task["task_type"],
                actual_notification_type=task["notification_type"],
                content=f"任务 {task['name']} 已触发执行",
                status="success",
                recipients=task["notify_emails"],
                response_info={
                    "delivery_status": "simulated",
                    "detail": "task execution notification created",
                    "task_id": task_id,
                    "task_type": task["task_type"],
                    "triggered_by": triggered_by,
                    "triggered_at": triggered_at,
                    **payload,
                },
            )

        return serialize_task(row or {}) | {"trigger_payload": payload}
    except HTTPException as exc:
        with connection() as conn:
            existing = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
            if existing is not None:
                next_status = "FAILED" if existing["trigger_type"] == "ONCE" else existing["status"]
                update_task_run_state(
                    conn,
                    task_id,
                    next_run_time=existing.get("next_run_time"),
                    status=next_status,
                    failure_count=1,
                    error_message=str(exc.detail),
                    last_result={"task_id": task_id, "status": "failed"},
                )
                if existing.get("notification_type") and existing.get("notify_on_failure"):
                    create_notification_log(
                        task_id=task_id,
                        task_name=existing["name"],
                        task_type=existing["task_type"],
                        actual_notification_type=existing["notification_type"],
                        content=f"任务 {existing['name']} 触发失败",
                        status="failed",
                        error_message=str(exc.detail),
                        recipients=json_loads(existing.get("notify_emails"), []),
                        response_info={
                            "delivery_status": "simulated",
                            "task_id": task_id,
                            "task_type": existing["task_type"],
                            "detail": str(exc.detail),
                        },
                    )
        raise
    except Exception as exc:
        with connection() as conn:
            existing = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
            if existing is not None:
                next_status = "FAILED" if existing["trigger_type"] == "ONCE" else existing["status"]
                update_task_run_state(
                    conn,
                    task_id,
                    next_run_time=existing.get("next_run_time"),
                    status=next_status,
                    failure_count=1,
                    error_message=str(exc),
                    last_result={"task_id": task_id, "status": "failed"},
                )
                if existing.get("notification_type") and existing.get("notify_on_failure"):
                    create_notification_log(
                        task_id=task_id,
                        task_name=existing["name"],
                        task_type=existing["task_type"],
                        actual_notification_type=existing["notification_type"],
                        content=f"任务 {existing['name']} 触发失败",
                        status="failed",
                        error_message=str(exc),
                        recipients=json_loads(existing.get("notify_emails"), []),
                        response_info={
                            "delivery_status": "simulated",
                            "task_id": task_id,
                            "task_type": existing["task_type"],
                            "detail": str(exc),
                        },
                    )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def build_scheduled_task_query() -> str:
    return """
        SELECT st.*, d.name AS device_name, p.name AS app_package_name, ts.name AS test_suite_name, tc.name AS test_case_name
        FROM scheduled_tasks st
        LEFT JOIN devices d ON d.id = st.device_id
        LEFT JOIN packages p ON p.id = st.package_id
        LEFT JOIN test_suites ts ON ts.id = st.test_suite_id
        LEFT JOIN test_cases tc ON tc.id = st.test_case_id
    """


@router.get("/scheduled-tasks/")
def list_scheduled_tasks(
    project_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    trigger_type: str | None = Query(default=None),
) -> dict[str, Any]:
    query = build_scheduled_task_query() + "\nWHERE 1 = 1"
    params: list[Any] = []
    if project_id is not None:
        query += " AND st.project_id = ?"
        params.append(project_id)
    if search:
        query += " AND (st.name LIKE ? OR st.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        query += " AND st.status = ?"
        params.append(status)
    if task_type:
        query += " AND st.task_type = ?"
        params.append(task_type)
    if trigger_type:
        query += " AND st.trigger_type = ?"
        params.append(trigger_type)
    query += " ORDER BY st.created_at DESC"
    with connection() as conn:
        rows = [serialize_task(item) for item in fetch_all(conn, query, params)]
    return success(rows)


@router.get("/scheduled-tasks/{task_id}/")
def get_scheduled_task(task_id: int) -> dict[str, Any]:
    with connection() as conn:
        row = fetch_one(conn, build_scheduled_task_query() + "\nWHERE st.id = ?", (task_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
    return success(serialize_task(row))


@router.post("/scheduled-tasks/")
def create_scheduled_task(payload: ScheduledTaskPayload) -> dict[str, Any]:
    next_run_time = compute_next_run(payload.trigger_type, payload.cron_expression, payload.interval_seconds, payload.execute_at)
    with connection() as conn:
        now = utc_now()
        conn.execute(
            """
            INSERT INTO scheduled_tasks (
                project_id, name, description, task_type, trigger_type, cron_expression, interval_seconds, execute_at,
                device_id, package_id, test_suite_id, test_case_id, notify_on_success, notify_on_failure,
                notification_type, notify_emails, status, last_run_time, next_run_time, total_runs, successful_runs,
                failed_runs, last_result, error_message, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 0, 0, 0, '{}', '', ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.name,
                payload.description,
                payload.task_type,
                payload.trigger_type,
                payload.cron_expression,
                payload.interval_seconds,
                payload.execute_at,
                payload.device_id,
                payload.package_id,
                payload.test_suite_id,
                payload.test_case_id,
                1 if payload.notify_on_success else 0,
                1 if payload.notify_on_failure else 0,
                payload.notification_type,
                json_dumps(payload.notify_emails),
                payload.status,
                next_run_time,
                payload.created_by,
                now,
                now,
            ),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    return success(serialize_task(row or {}), "定时任务已创建", 201)


@router.put("/scheduled-tasks/{task_id}/")
def update_scheduled_task(task_id: int, payload: ScheduledTaskPayload) -> dict[str, Any]:
    next_run_time = compute_next_run(payload.trigger_type, payload.cron_expression, payload.interval_seconds, payload.execute_at)
    with connection() as conn:
        _ = get_task_or_404(conn, task_id)
        conn.execute(
            """
            UPDATE scheduled_tasks
            SET project_id = ?, name = ?, description = ?, task_type = ?, trigger_type = ?, cron_expression = ?,
                interval_seconds = ?, execute_at = ?, device_id = ?, package_id = ?, test_suite_id = ?, test_case_id = ?,
                notify_on_success = ?, notify_on_failure = ?, notification_type = ?, notify_emails = ?, status = ?,
                next_run_time = ?, created_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.project_id,
                payload.name,
                payload.description,
                payload.task_type,
                payload.trigger_type,
                payload.cron_expression,
                payload.interval_seconds,
                payload.execute_at,
                payload.device_id,
                payload.package_id,
                payload.test_suite_id,
                payload.test_case_id,
                1 if payload.notify_on_success else 0,
                1 if payload.notify_on_failure else 0,
                payload.notification_type,
                json_dumps(payload.notify_emails),
                payload.status,
                next_run_time,
                payload.created_by,
                utc_now(),
                task_id,
            ),
        )
        row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    return success(serialize_task(row or {}), "定时任务已更新")


@router.delete("/scheduled-tasks/{task_id}/")
def delete_scheduled_task(task_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_task_or_404(conn, task_id)
        _delete_scheduled_tasks(conn, [task_id])
    return success(None, "定时任务已删除")


@router.post("/scheduled-tasks/{task_id}/pause/")
def pause_scheduled_task(task_id: int) -> dict[str, Any]:
    with connection() as conn:
        _ = get_task_or_404(conn, task_id)
        conn.execute("UPDATE scheduled_tasks SET status = 'PAUSED', updated_at = ? WHERE id = ?", (utc_now(), task_id))
        row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    return success(serialize_task(row or {}), "任务已暂停")


@router.post("/scheduled-tasks/{task_id}/resume/")
def resume_scheduled_task(task_id: int) -> dict[str, Any]:
    with connection() as conn:
        task = get_task_or_404(conn, task_id)
        next_run_time = compute_next_run(task["trigger_type"], task["cron_expression"], task["interval_seconds"], task["execute_at"])
        conn.execute(
            "UPDATE scheduled_tasks SET status = 'ACTIVE', next_run_time = ?, updated_at = ? WHERE id = ?",
            (next_run_time, utc_now(), task_id),
        )
        row = fetch_one(conn, "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
    return success(serialize_task(row or {}), "任务已恢复")


@router.post("/scheduled-tasks/{task_id}/run_now/")
def run_now(task_id: int, triggered_by: str = Query(default="FlyTest")) -> dict[str, Any]:
    return success(trigger_task_run(task_id, triggered_by), "任务已触发")


@router.get("/notification-logs/")
def list_notification_logs(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    notification_type: str | None = Query(default=None),
    task_id: int | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        parsed_start = (
            datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if start_date
            else None
        )
        parsed_end = (
            datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            if end_date
            else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式必须为 YYYY-MM-DD") from exc

    query = "SELECT * FROM notification_logs WHERE 1 = 1"
    params: list[Any] = []
    if search:
        query += " AND (task_name LIKE ? OR notification_content LIKE ? OR error_message LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if status:
        query += " AND status = ?"
        params.append(status)
    if notification_type:
        query += " AND actual_notification_type = ?"
        params.append(notification_type)
    if task_id is not None:
        query += " AND task_id = ?"
        params.append(task_id)
    if parsed_start:
        start_at = parsed_start.isoformat()
        query += " AND created_at >= ?"
        params.append(start_at)
    if parsed_end:
        end_at = parsed_end.isoformat()
        query += " AND created_at < ?"
        params.append(end_at)
    query += " ORDER BY created_at DESC"
    with connection() as conn:
        rows = [serialize_notification(item) for item in fetch_all(conn, query, params)]
    return success(rows)


@router.post("/notification-logs/{log_id}/retry/")
def retry_notification(log_id: int) -> dict[str, Any]:
    with connection() as conn:
        row = fetch_one(conn, "SELECT * FROM notification_logs WHERE id = ?", (log_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="通知日志不存在")
        current_retry_count = int(row.get("retry_count") or 0) + 1
        retried_at = utc_now()
        response_info = json_loads(row.get("response_info"), {})
        response_info.update(
            {
                "delivery_status": "simulated",
                "retry_status": "success",
                "retry_count": current_retry_count,
                "retried_at": retried_at,
            }
        )
        conn.execute(
            """
            UPDATE notification_logs
            SET retry_count = ?, is_retried = 1, status = 'success', error_message = '', response_info = ?, sent_at = ?
            WHERE id = ?
            """,
            (current_retry_count, json_dumps(response_info), retried_at, log_id),
        )
        updated = fetch_one(conn, "SELECT * FROM notification_logs WHERE id = ?", (log_id,))
    return success(serialize_notification(updated or {}), "通知已重试")
