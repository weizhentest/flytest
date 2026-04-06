from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
ELEMENT_UPLOADS_DIR = UPLOADS_DIR / "elements"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = DATA_DIR / "app_automation.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ELEMENT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (ELEMENT_UPLOADS_DIR / "common").mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                adb_path TEXT NOT NULL DEFAULT 'adb',
                default_timeout INTEGER NOT NULL DEFAULT 300,
                workspace_root TEXT NOT NULL DEFAULT '',
                auto_discover_on_open INTEGER NOT NULL DEFAULT 1,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'offline',
                android_version TEXT NOT NULL DEFAULT '',
                connection_type TEXT NOT NULL DEFAULT 'emulator',
                ip_address TEXT NOT NULL DEFAULT '',
                port INTEGER NOT NULL DEFAULT 5555,
                locked_by TEXT NOT NULL DEFAULT '',
                locked_at TEXT,
                device_specs TEXT NOT NULL DEFAULT '{}',
                description TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                last_seen_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
            CREATE INDEX IF NOT EXISTS idx_devices_updated_at ON devices(updated_at DESC);

            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                package_name TEXT NOT NULL,
                activity_name TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT 'android',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, package_name)
            );

            CREATE INDEX IF NOT EXISTS idx_packages_project ON packages(project_id);
            CREATE INDEX IF NOT EXISTS idx_packages_name ON packages(name);

            CREATE TABLE IF NOT EXISTS elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                element_type TEXT NOT NULL,
                selector_type TEXT NOT NULL DEFAULT '',
                selector_value TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                config TEXT NOT NULL DEFAULT '{}',
                image_path TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, name)
            );

            CREATE INDEX IF NOT EXISTS idx_elements_project ON elements(project_id);
            CREATE INDEX IF NOT EXISTS idx_elements_type ON elements(element_type);

            CREATE TABLE IF NOT EXISTS test_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                package_id INTEGER,
                ui_flow TEXT NOT NULL DEFAULT '{}',
                variables TEXT NOT NULL DEFAULT '[]',
                tags TEXT NOT NULL DEFAULT '[]',
                timeout INTEGER NOT NULL DEFAULT 300,
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_result TEXT NOT NULL DEFAULT '',
                last_run_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(package_id) REFERENCES packages(id)
            );

            CREATE INDEX IF NOT EXISTS idx_test_cases_project ON test_cases(project_id);
            CREATE INDEX IF NOT EXISTS idx_test_cases_updated_at ON test_cases(updated_at DESC);

            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                test_case_id INTEGER,
                test_suite_id INTEGER,
                device_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT NOT NULL DEFAULT '',
                progress INTEGER NOT NULL DEFAULT 0,
                trigger_mode TEXT NOT NULL DEFAULT 'manual',
                triggered_by TEXT NOT NULL DEFAULT '',
                logs TEXT NOT NULL DEFAULT '[]',
                report_summary TEXT NOT NULL DEFAULT '',
                report_path TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                total_steps INTEGER NOT NULL DEFAULT 0,
                passed_steps INTEGER NOT NULL DEFAULT 0,
                failed_steps INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                finished_at TEXT,
                duration REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(test_case_id) REFERENCES test_cases(id),
                FOREIGN KEY(test_suite_id) REFERENCES test_suites(id),
                FOREIGN KEY(device_id) REFERENCES devices(id)
            );

            CREATE INDEX IF NOT EXISTS idx_executions_project ON executions(project_id);
            CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
            CREATE INDEX IF NOT EXISTS idx_executions_created_at ON executions(created_at DESC);

            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                schema_json TEXT NOT NULL DEFAULT '{}',
                default_config TEXT NOT NULL DEFAULT '{}',
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                schema_json TEXT NOT NULL DEFAULT '{}',
                default_config TEXT NOT NULL DEFAULT '{}',
                steps_json TEXT NOT NULL DEFAULT '[]',
                enabled INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS component_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'upload',
                manifest_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS test_suites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                execution_status TEXT NOT NULL DEFAULT 'not_run',
                execution_result TEXT NOT NULL DEFAULT '',
                passed_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                last_run_at TEXT,
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_test_suites_project ON test_suites(project_id);
            CREATE INDEX IF NOT EXISTS idx_test_suites_updated_at ON test_suites(updated_at DESC);

            CREATE TABLE IF NOT EXISTS test_suite_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_suite_id INTEGER NOT NULL,
                test_case_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(test_suite_id, test_case_id),
                FOREIGN KEY(test_suite_id) REFERENCES test_suites(id) ON DELETE CASCADE,
                FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                cron_expression TEXT NOT NULL DEFAULT '',
                interval_seconds INTEGER,
                execute_at TEXT,
                device_id INTEGER,
                package_id INTEGER,
                test_suite_id INTEGER,
                test_case_id INTEGER,
                notify_on_success INTEGER NOT NULL DEFAULT 0,
                notify_on_failure INTEGER NOT NULL DEFAULT 1,
                notification_type TEXT NOT NULL DEFAULT '',
                notify_emails TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                last_run_time TEXT,
                next_run_time TEXT,
                total_runs INTEGER NOT NULL DEFAULT 0,
                successful_runs INTEGER NOT NULL DEFAULT 0,
                failed_runs INTEGER NOT NULL DEFAULT 0,
                last_result TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(device_id) REFERENCES devices(id),
                FOREIGN KEY(package_id) REFERENCES packages(id),
                FOREIGN KEY(test_suite_id) REFERENCES test_suites(id),
                FOREIGN KEY(test_case_id) REFERENCES test_cases(id)
            );

            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_project ON scheduled_tasks(project_id);
            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks(next_run_time);

            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL DEFAULT '',
                notification_type TEXT NOT NULL,
                actual_notification_type TEXT NOT NULL DEFAULT '',
                sender_name TEXT NOT NULL DEFAULT 'FlyTest',
                sender_email TEXT NOT NULL DEFAULT 'noreply@flytest.local',
                recipient_info TEXT NOT NULL DEFAULT '[]',
                webhook_bot_info TEXT NOT NULL DEFAULT '{}',
                notification_content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT NOT NULL DEFAULT '',
                response_info TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                sent_at TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                is_retried INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(task_id) REFERENCES scheduled_tasks(id)
            );

            CREATE INDEX IF NOT EXISTS idx_notification_logs_status ON notification_logs(status);
            CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at ON notification_logs(created_at DESC);
            """
        )

        execution_columns = {row["name"] for row in conn.execute("PRAGMA table_info(executions)").fetchall()}
        if "test_suite_id" not in execution_columns:
            conn.execute("ALTER TABLE executions ADD COLUMN test_suite_id INTEGER")
        if "report_path" not in execution_columns:
            conn.execute("ALTER TABLE executions ADD COLUMN report_path TEXT NOT NULL DEFAULT ''")
        if "total_steps" not in execution_columns:
            conn.execute("ALTER TABLE executions ADD COLUMN total_steps INTEGER NOT NULL DEFAULT 0")
        if "passed_steps" not in execution_columns:
            conn.execute("ALTER TABLE executions ADD COLUMN passed_steps INTEGER NOT NULL DEFAULT 0")
        if "failed_steps" not in execution_columns:
            conn.execute("ALTER TABLE executions ADD COLUMN failed_steps INTEGER NOT NULL DEFAULT 0")

        existing = conn.execute("SELECT id FROM settings WHERE id = 1").fetchone()
        if existing is None:
            now = utc_now()
            conn.execute(
                """
                INSERT INTO settings (id, adb_path, default_timeout, workspace_root, auto_discover_on_open, notes, created_at, updated_at)
                VALUES (1, 'adb', 300, '', 1, '', ?, ?)
                """,
                (now, now),
            )

        component_count = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        if component_count == 0:
            now = utc_now()
            default_components = [
                (
                    "点击元素",
                    "touch",
                    "interaction",
                    "点击指定元素或坐标",
                    json_dumps({"selector_type": "string", "selector": "string"}),
                    json_dumps({"selector_type": "element", "selector": ""}),
                    1,
                    10,
                    now,
                    now,
                ),
                (
                    "等待元素",
                    "wait",
                    "assertion",
                    "等待元素出现",
                    json_dumps({"selector_type": "string", "selector": "string", "timeout": "number"}),
                    json_dumps({"selector_type": "element", "selector": "", "timeout": 10}),
                    1,
                    20,
                    now,
                    now,
                ),
                (
                    "输入文本",
                    "text",
                    "interaction",
                    "输入文本内容",
                    json_dumps({"text": "string"}),
                    json_dumps({"text": ""}),
                    1,
                    30,
                    now,
                    now,
                ),
                (
                    "滑动",
                    "swipe",
                    "interaction",
                    "执行滑动动作",
                    json_dumps({"start": "string", "end": "string", "duration": "number"}),
                    json_dumps({"start": "0,0", "end": "100,100", "duration": 0.4}),
                    1,
                    40,
                    now,
                    now,
                ),
                (
                    "断言存在",
                    "assert_exists",
                    "assertion",
                    "断言元素存在",
                    json_dumps({"selector_type": "string", "selector": "string"}),
                    json_dumps({"selector_type": "element", "selector": ""}),
                    1,
                    50,
                    now,
                    now,
                ),
                (
                    "截图",
                    "snapshot",
                    "utility",
                    "执行截图动作",
                    json_dumps({"name": "string"}),
                    json_dumps({"name": "snapshot"}),
                    1,
                    60,
                    now,
                    now,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO components (
                    name, type, category, description, schema_json, default_config,
                    enabled, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                default_components,
            )

        now = utc_now()
        supplemental_components = [
            (
                "启动应用",
                "launch_app",
                "device",
                "启动指定应用包",
                json_dumps({"package_name": "string", "activity_name": "string"}),
                json_dumps({"package_name": "", "activity_name": ""}),
                1,
                70,
                now,
                now,
            ),
            (
                "关闭应用",
                "stop_app",
                "device",
                "关闭指定应用包",
                json_dumps({"package_name": "string"}),
                json_dumps({"package_name": ""}),
                1,
                80,
                now,
                now,
            ),
            (
                "返回",
                "back",
                "device",
                "执行 Android BACK 键",
                json_dumps({}),
                json_dumps({}),
                1,
                90,
                now,
                now,
            ),
            (
                "桌面",
                "home",
                "device",
                "返回 Android HOME",
                json_dumps({}),
                json_dumps({}),
                1,
                100,
                now,
                now,
            ),
            (
                "按键事件",
                "keyevent",
                "device",
                "执行 Android keyevent",
                json_dumps({"keycode": "string"}),
                json_dumps({"keycode": "KEYCODE_ENTER"}),
                1,
                110,
                now,
                now,
            ),
            (
                "设置变量",
                "set_variable",
                "utility",
                "设置局部或全局变量",
                json_dumps({"variable_name": "string", "value": "any", "scope": "string"}),
                json_dumps({"variable_name": "token", "value": "", "scope": "local"}),
                1,
                120,
                now,
                now,
            ),
            (
                "删除变量",
                "unset_variable",
                "utility",
                "删除局部或全局变量",
                json_dumps({"variable_name": "string", "scope": "string"}),
                json_dumps({"variable_name": "token", "scope": "local"}),
                1,
                130,
                now,
                now,
            ),
            (
                "双击元素",
                "double_click",
                "interaction",
                "对指定元素或坐标执行双击",
                json_dumps({"selector_type": "string", "selector": "string", "interval": "number"}),
                json_dumps({"selector_type": "element", "selector": "", "interval": 0.12}),
                1,
                140,
                now,
                now,
            ),
            (
                "长按元素",
                "long_press",
                "interaction",
                "对指定元素或坐标执行长按",
                json_dumps({"selector_type": "string", "selector": "string", "duration": "number"}),
                json_dumps({"selector_type": "element", "selector": "", "duration": 1.0}),
                1,
                150,
                now,
                now,
            ),
            (
                "拖拽",
                "drag",
                "interaction",
                "从起点拖拽到终点，支持坐标或元素",
                json_dumps({"start": "string", "end": "string", "duration": "number"}),
                json_dumps({"start": "200,300", "end": "600,300", "duration": 0.6}),
                1,
                160,
                now,
                now,
            ),
            (
                "顺序执行",
                "sequence",
                "flow",
                "顺序执行一组子步骤",
                json_dumps({"steps": "array"}),
                json_dumps({"steps": []}),
                1,
                170,
                now,
                now,
            ),
            (
                "条件分支",
                "if",
                "flow",
                "根据条件执行 then_steps 或 else_steps",
                json_dumps({"left": "any", "operator": "string", "right": "any", "then_steps": "array", "else_steps": "array"}),
                json_dumps({"left": "", "operator": "truthy", "right": "", "then_steps": [], "else_steps": []}),
                1,
                180,
                now,
                now,
            ),
            (
                "循环执行",
                "loop",
                "flow",
                "支持计数、遍历和条件循环",
                json_dumps({"mode": "string", "times": "number", "items": "array", "left": "any", "operator": "string", "right": "any", "max_loops": "number", "steps": "array", "interval": "number"}),
                json_dumps({"mode": "count", "times": 2, "items": [], "left": "", "operator": "truthy", "right": "", "max_loops": 10, "steps": [], "interval": 0}),
                1,
                190,
                now,
                now,
            ),
            (
                "异常处理",
                "try",
                "flow",
                "执行 try/catch/finally 子步骤",
                json_dumps({"try_steps": "array", "catch_steps": "array", "finally_steps": "array", "error_var": "string", "error_scope": "string"}),
                json_dumps({"try_steps": [], "catch_steps": [], "finally_steps": [], "error_var": "error", "error_scope": "local"}),
                1,
                200,
                now,
                now,
            ),
            (
                "滑动查找",
                "swipe_to",
                "interaction",
                "按方向滑动直到目标元素出现",
                json_dumps(
                    {
                        "target_selector_type": "string",
                        "target_selector": "string",
                        "direction": "string",
                        "max_swipes": "number",
                        "interval": "number",
                    }
                ),
                json_dumps(
                    {
                        "target_selector_type": "text",
                        "target_selector": "",
                        "direction": "up",
                        "max_swipes": 5,
                        "interval": 0.5,
                    }
                ),
                1,
                210,
                now,
                now,
            ),
            (
                "通用断言",
                "assert",
                "assertion",
                "支持存在性、条件、正则和范围断言",
                json_dumps(
                    {
                        "assert_type": "string",
                        "source": "string",
                        "operator": "string",
                        "expected": "any",
                        "timeout": "number",
                        "retry_interval": "number",
                    }
                ),
                json_dumps(
                    {
                        "assert_type": "condition",
                        "source": "",
                        "operator": "==",
                        "expected": "",
                        "timeout": 0,
                        "retry_interval": 0.5,
                    }
                ),
                1,
                220,
                now,
                now,
            ),
            (
                "提取输出",
                "extract_output",
                "utility",
                "从变量或接口结果中提取字段保存为新变量",
                json_dumps({"source": "string", "path": "string", "variable_name": "string", "scope": "string"}),
                json_dumps({"source": "response", "path": "body.data", "variable_name": "value", "scope": "local"}),
                1,
                230,
                now,
                now,
            ),
            (
                "接口请求",
                "api_request",
                "network",
                "执行 HTTP 请求并提取响应数据",
                json_dumps(
                    {
                        "method": "string",
                        "url": "string",
                        "headers": "object",
                        "params": "object",
                        "json": "object",
                        "data": "any",
                        "expected_status": "number",
                        "save_as": "string",
                        "extracts": "array",
                        "timeout": "number",
                    }
                ),
                json_dumps(
                    {
                        "method": "GET",
                        "url": "",
                        "headers": {},
                        "params": {},
                        "json": {},
                        "data": "",
                        "expected_status": 200,
                        "save_as": "response",
                        "extracts": [],
                        "timeout": 10,
                    }
                ),
                1,
                240,
                now,
                now,
            ),
            (
                "图片存在点击",
                "image_exists_click",
                "interaction",
                "主定位存在则点击主定位，否则点击备用定位",
                json_dumps(
                    {
                        "selector_type": "string",
                        "selector": "string",
                        "fallback_selector_type": "string",
                        "fallback_selector": "string",
                    }
                ),
                json_dumps(
                    {
                        "selector_type": "image",
                        "selector": "",
                        "fallback_selector_type": "element",
                        "fallback_selector": "",
                    }
                ),
                1,
                250,
                now,
                now,
            ),
            (
                "图片存在连点",
                "image_exists_click_chain",
                "interaction",
                "主定位存在时先点击主定位，再点击备用定位；否则只点击备用定位",
                json_dumps(
                    {
                        "selector_type": "string",
                        "selector": "string",
                        "fallback_selector_type": "string",
                        "fallback_selector": "string",
                        "interval": "number",
                    }
                ),
                json_dumps(
                    {
                        "selector_type": "image",
                        "selector": "",
                        "fallback_selector_type": "element",
                        "fallback_selector": "",
                        "interval": 0.5,
                    }
                ),
                1,
                260,
                now,
                now,
            ),
            (
                "循环点击断言",
                "foreach_assert",
                "assertion",
                "循环点击目标并对 OCR 区域结果执行匹配断言",
                json_dumps(
                    {
                        "click_selector_type": "string",
                        "click_selector": "string",
                        "ocr_selector_type": "string",
                        "ocr_selector": "string",
                        "expected_list": "array",
                        "assert_type": "string",
                        "match_mode": "string",
                        "max_loops": "number",
                        "min_match": "number",
                        "interval": "number",
                        "timeout": "number",
                    }
                ),
                json_dumps(
                    {
                        "click_selector_type": "element",
                        "click_selector": "",
                        "ocr_selector_type": "region",
                        "ocr_selector": "0,0,200,80",
                        "expected_list": [],
                        "assert_type": "text",
                        "match_mode": "contains",
                        "max_loops": 3,
                        "min_match": 1,
                        "interval": 0.5,
                        "timeout": 1.5,
                    }
                ),
                1,
                270,
                now,
                now,
            ),
        ]
        existing_component_types = {row["type"] for row in conn.execute("SELECT type FROM components").fetchall()}
        missing_components = [item for item in supplemental_components if item[1] not in existing_component_types]
        if missing_components:
            conn.executemany(
                """
                INSERT INTO components (
                    name, type, category, description, schema_json, default_config,
                    enabled, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                missing_components,
            )

        conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def fetch_one(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, tuple(params)).fetchone()
    if row is None:
        return None
    return dict(row)


def fetch_all(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]
