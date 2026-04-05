from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .database import connection, fetch_all
from .extended_routes import trigger_task_run


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class AppAutomationScheduler:
    def __init__(self, poll_interval_seconds: float = 5.0) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running_tasks: set[int] = set()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="app-automation-scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            thread = self._thread
            self._thread = None

        if thread and thread.is_alive():
            thread.join(timeout=2)

    def status(self) -> dict[str, Any]:
        with self._lock:
            alive = bool(self._thread and self._thread.is_alive())
            running_tasks = len(self._running_tasks)
        return {"running": alive, "running_tasks": running_tasks, "poll_interval_seconds": self.poll_interval_seconds}

    def _run(self) -> None:
        while not self._stop_event.wait(self.poll_interval_seconds):
            due_task_ids = self._get_due_task_ids()
            for task_id in due_task_ids:
                if self._stop_event.is_set():
                    return
                self._trigger_due_task(task_id)

    def _get_due_task_ids(self) -> list[int]:
        now = datetime.now(timezone.utc)
        with connection() as conn:
            rows = fetch_all(
                conn,
                """
                SELECT id, next_run_time
                FROM scheduled_tasks
                WHERE status = 'ACTIVE' AND next_run_time IS NOT NULL
                ORDER BY next_run_time ASC
                """,
            )

        due_task_ids: list[int] = []
        with self._lock:
            for row in rows:
                next_run = _parse_dt(row.get("next_run_time"))
                if next_run is None or next_run > now or row["id"] in self._running_tasks:
                    continue
                due_task_ids.append(row["id"])
                self._running_tasks.add(row["id"])

        return due_task_ids

    def _trigger_due_task(self, task_id: int) -> None:
        try:
            trigger_task_run(task_id, "scheduler")
        except Exception:
            # Let the task record its own failure state; the scheduler only keeps the loop alive.
            pass
        finally:
            with self._lock:
                self._running_tasks.discard(task_id)


app_scheduler = AppAutomationScheduler()
