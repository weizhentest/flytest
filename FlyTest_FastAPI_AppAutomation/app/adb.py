from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class AdbError(RuntimeError):
    """Raised when adb commands cannot be completed."""


def resolve_adb_path(adb_path: str) -> str:
    candidate = str(adb_path or "").strip() or "adb"
    if Path(candidate).is_file():
        return candidate

    resolved = shutil.which(candidate)
    if resolved:
        return resolved

    env_roots = [
        os.environ.get("ANDROID_SDK_ROOT", ""),
        os.environ.get("ANDROID_HOME", ""),
    ]
    common_paths = [
        r"C:\Users\66674\AppData\Local\Android\Sdk",
        r"C:\Android\Sdk",
        r"D:\Android\Sdk",
        r"C:\Android",
        r"D:\Android",
        r"C:\Program Files\Android\platform-tools",
        r"C:\Program Files (x86)\Android\platform-tools",
        r"C:\Program Files\platform-tools",
        r"C:\platform-tools",
        r"D:\platform-tools",
    ]
    emulator_paths = [
        r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Program Files\BlueStacks\HD-Adb.exe",
        r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\Microvirt\MEmu\adb.exe",
        r"C:\Program Files\Genymobile\Genymotion\tools\adb.exe",
    ]

    for root in [*env_roots, *common_paths]:
        root_path = str(root or "").strip()
        if not root_path:
            continue
        path = Path(root_path)
        for probe in (path / "platform-tools" / "adb.exe", path / "adb.exe"):
            if probe.is_file():
                return str(probe)

    for entry in emulator_paths:
        if Path(entry).is_file():
            return entry

    return candidate


def run_adb_command(adb_path: str, *args: str, timeout: int = 10) -> str:
    adb_executable = resolve_adb_path(adb_path)
    try:
        completed = subprocess.run(
            [adb_executable, *args],
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


def inspect_adb_environment(adb_path: str) -> dict[str, Any]:
    configured_path = str(adb_path or "").strip() or "adb"
    resolved_path = resolve_adb_path(configured_path)
    executable_found = Path(resolved_path).is_file() or bool(shutil.which(configured_path))
    diagnostics: dict[str, Any] = {
        "configured_path": configured_path,
        "resolved_path": resolved_path,
        "executable_found": executable_found,
        "version": "",
        "device_count": 0,
        "devices": [],
        "error": "",
    }

    if not executable_found:
        diagnostics["error"] = f"ADB 不可用，请检查配置路径：{configured_path}"
        return diagnostics

    try:
        version_output = run_adb_command(configured_path, "version", timeout=8)
        diagnostics["version"] = next((line.strip() for line in version_output.splitlines() if line.strip()), "")
    except AdbError as exc:
        diagnostics["error"] = str(exc)
        return diagnostics

    try:
        devices = discover_devices(configured_path)
        diagnostics["devices"] = devices
        diagnostics["device_count"] = len(devices)
    except AdbError as exc:
        diagnostics["error"] = str(exc)

    return diagnostics


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
    adb_executable = resolve_adb_path(adb_path)
    try:
        completed = subprocess.run(
            [adb_executable, "-s", serial, "exec-out", "screencap", "-p"],
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


def run_adb_device_command(adb_path: str, serial: str, *args: str, timeout: int = 10) -> str:
    return run_adb_command(adb_path, "-s", serial, *args, timeout=timeout)


def tap_device(adb_path: str, serial: str, x: int, y: int, timeout: int = 10) -> None:
    run_adb_device_command(adb_path, serial, "shell", "input", "tap", str(int(x)), str(int(y)), timeout=timeout)


def swipe_device(
    adb_path: str,
    serial: str,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    duration_ms: int = 400,
    timeout: int = 10,
) -> None:
    run_adb_device_command(
        adb_path,
        serial,
        "shell",
        "input",
        "swipe",
        str(int(start[0])),
        str(int(start[1])),
        str(int(end[0])),
        str(int(end[1])),
        str(int(duration_ms)),
        timeout=timeout,
    )


def _escape_text_for_adb(text: str) -> str:
    replacements = {
        " ": "%s",
        '"': '\\"',
        "'": "\\'",
        "&": "\\&",
        "|": "\\|",
        "<": "\\<",
        ">": "\\>",
        ";": "\\;",
        "(": "\\(",
        ")": "\\)",
        "$": "\\$",
    }
    return "".join(replacements.get(char, char) for char in str(text))


def input_device_text(adb_path: str, serial: str, text: str, timeout: int = 10) -> None:
    safe_text = _escape_text_for_adb(text)
    run_adb_device_command(adb_path, serial, "shell", "input", "text", safe_text, timeout=timeout)


def launch_device_app(
    adb_path: str,
    serial: str,
    package_name: str,
    activity_name: str = "",
    timeout: int = 15,
) -> str:
    package_name = str(package_name or "").strip()
    activity_name = str(activity_name or "").strip()
    if not package_name:
        raise AdbError("缺少应用包名，无法启动应用")

    if activity_name:
        if "/" in activity_name:
            component_name = activity_name
        elif activity_name.startswith("."):
            component_name = f"{package_name}/{activity_name}"
        else:
            component_name = f"{package_name}/{activity_name}"
        return run_adb_device_command(
            adb_path,
            serial,
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            component_name,
            timeout=timeout,
        )

    return run_adb_device_command(
        adb_path,
        serial,
        "shell",
        "monkey",
        "-p",
        package_name,
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
        timeout=timeout,
    )


def stop_device_app(adb_path: str, serial: str, package_name: str, timeout: int = 10) -> None:
    run_adb_device_command(adb_path, serial, "shell", "am", "force-stop", str(package_name).strip(), timeout=timeout)


def press_device_keyevent(adb_path: str, serial: str, keycode: str | int, timeout: int = 10) -> None:
    run_adb_device_command(adb_path, serial, "shell", "input", "keyevent", str(keycode), timeout=timeout)


def dump_device_ui_xml(adb_path: str, serial: str, timeout: int = 15) -> str:
    remote_path = "/data/local/tmp/flytest_ui_dump.xml"
    run_adb_device_command(adb_path, serial, "shell", "uiautomator", "dump", remote_path, timeout=timeout)
    xml_text = run_adb_device_command(adb_path, serial, "shell", "cat", remote_path, timeout=timeout)
    if not xml_text.strip():
        raise AdbError("未能读取设备 UI 层级信息")
    return xml_text
