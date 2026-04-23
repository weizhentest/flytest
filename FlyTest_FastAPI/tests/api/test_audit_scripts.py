import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")


def _base_env():
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{(REPO_ROOT / 'FlyTest_Django' / 'db.sqlite3').as_posix()}"
    env["SECRET_KEY"] = "change-me-fastapi-local"
    env["APP_ENV"] = "test"
    env["API_PREFIX"] = "/api"
    env.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")
    return env


def test_route_audit_script_runs() -> None:
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "FlyTest_FastAPI" / "scripts" / "route_audit.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        env=_base_env(),
    )
    payload = json.loads(result.stdout)
    assert "missing_count" in payload
    assert payload["missing_count"] == 0


def test_proxy_audit_script_runs() -> None:
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "FlyTest_FastAPI" / "scripts" / "proxy_audit.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        env=_base_env(),
    )
    payload = json.loads(result.stdout)
    assert "proxy_file_count" in payload
    assert payload["proxy_file_count"] == 0


def test_django_runtime_audit_script_runs() -> None:
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "FlyTest_FastAPI" / "scripts" / "django_runtime_audit.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        env=_base_env(),
    )
    payload = json.loads(result.stdout)
    assert "service_file_count" in payload
    assert "django_runtime_file_count" in payload
    assert isinstance(payload["django_runtime_groups"], dict)


def test_compat_runtime_audit_script_runs() -> None:
    result = subprocess.run(
        [PYTHON, str(REPO_ROOT / "FlyTest_FastAPI" / "scripts" / "compat_runtime_audit.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        env=_base_env(),
    )
    payload = json.loads(result.stdout)
    assert "compat_runtime_file_count" in payload
    assert isinstance(payload["compat_runtime_files"], list)
