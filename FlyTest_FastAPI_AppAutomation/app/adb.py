from __future__ import annotations

import subprocess
from typing import Any


class AdbError(RuntimeError):
    """Raised when adb commands cannot be completed."""


def run_adb_command(adb_path: str, *args: str, timeout: int = 10) -> str:
    try:
        completed = subprocess.run(
            [adb_path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
    except FileNotFoundError as exc:
        raise AdbError(f"ADB 不可用，请检查配置路径：{adb_path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdbError("ADB 命令执行超时") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    if completed.returncode != 0:
        raise AdbError(stderr or stdout or "ADB 命令执行失败")

    return stdout


def discover_devices(adb_path: str) -> list[dict[str, Any]]:
    output = run_adb_command(adb_path, "devices", "-l")
    devices: list[dict[str, Any]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        raw_status = parts[1]
        status = "available" if raw_status == "device" else "offline"
        connection_type = "remote_emulator" if ":" in serial else "emulator"

        model = ""
        for part in parts[2:]:
            if part.startswith("model:"):
                model = part.split(":", 1)[1].replace("_", " ")
                break

        android_version = ""
        if raw_status == "device":
            try:
                android_version = run_adb_command(adb_path, "-s", serial, "shell", "getprop", "ro.build.version.release", timeout=5)
            except AdbError:
                android_version = ""

        ip_address = ""
        port = 5555
        if ":" in serial:
            host, _, port_text = serial.partition(":")
            ip_address = host
            if port_text.isdigit():
                port = int(port_text)

        devices.append(
            {
                "device_id": serial,
                "name": model or serial,
                "status": status,
                "android_version": android_version,
                "connection_type": connection_type,
                "ip_address": ip_address,
                "port": port,
                "device_specs": {},
            }
        )

    return devices


def connect_remote_device(adb_path: str, ip_address: str, port: int) -> dict[str, Any]:
    serial = f"{ip_address}:{port}"
    output = run_adb_command(adb_path, "connect", serial)

    if "cannot" in output.lower() or "failed" in output.lower():
        raise AdbError(output)

    return {
        "device_id": serial,
        "name": serial,
        "status": "available",
        "android_version": "",
        "connection_type": "remote_emulator",
        "ip_address": ip_address,
        "port": port,
        "device_specs": {},
    }


def disconnect_remote_device(adb_path: str, serial: str) -> str:
    return run_adb_command(adb_path, "disconnect", serial)


def capture_device_screenshot(adb_path: str, serial: str, timeout: int = 15) -> bytes:
    try:
        completed = subprocess.run(
            [adb_path, "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AdbError(f"ADB 不可用，请检查配置路径：{adb_path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AdbError("设备截图超时，请检查设备连接状态") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        stdout = completed.stdout.decode("utf-8", errors="ignore").strip()
        raise AdbError(stderr or stdout or "设备截图失败")

    if not completed.stdout:
        raise AdbError("设备截图失败，未返回图片数据")

    return completed.stdout
