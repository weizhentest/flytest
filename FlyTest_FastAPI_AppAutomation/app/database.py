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
