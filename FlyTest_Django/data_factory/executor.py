from __future__ import annotations

import base64
import colorsys
import csv
import difflib
import hashlib
import hmac
import io
import json
import random
import re
import secrets
import string
import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote
from xml.etree.ElementTree import Element, SubElement, tostring
from zoneinfo import ZoneInfo

import barcode
import qrcode
import yaml
from barcode.writer import ImageWriter
from croniter import croniter
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from faker import Faker
from jsonpath_ng.ext import parse as jsonpath_parse

faker = Faker("zh_CN")

HEX_COLOR_PATTERN = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RGB_COLOR_PATTERN = re.compile(
    r"^rgb\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})\s*\)$",
    re.IGNORECASE,
)
HSL_COLOR_PATTERN = re.compile(
    r"^hsl\(\s*(?P<h>\d{1,3})\s*,\s*(?P<s>\d{1,3})%\s*,\s*(?P<l>\d{1,3})%\s*\)$",
    re.IGNORECASE,
)


class DataFactoryExecutionError(ValueError):
    """工具执行异常。"""


def _result(
    tool_name: str,
    result: Any,
    *,
    summary: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "tool_name": tool_name,
        "result": result,
        "summary": summary,
        "metadata": metadata or {},
    }


def _ensure_text(value: Any, field_name: str) -> str:
    if value is None:
        raise DataFactoryExecutionError(f"{field_name} 不能为空")
    return str(value)


def _ensure_number(value: Any, field_name: str, *, integer: bool = False) -> int | float:
    try:
        return int(value) if integer else float(value)
    except (TypeError, ValueError) as exc:
        raise DataFactoryExecutionError(f"{field_name} 必须是数字") from exc


def _parse_json_text(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataFactoryExecutionError(f"JSON 解析失败: {exc.msg}") from exc


def _parse_list_input(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    text = _ensure_text(value, "列表数据").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in text.splitlines() if item.strip()]


def _parse_flags(flags: Iterable[str] | None) -> int:
    value = 0
    for item in flags or []:
        if item == "i":
            value |= re.IGNORECASE
        elif item == "m":
            value |= re.MULTILINE
        elif item == "s":
            value |= re.DOTALL
    return value


def _split_words(text: str) -> list[str]:
    prepared = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    prepared = re.sub(r"[_\-.]+", " ", prepared)
    return [part for part in re.split(r"\s+", prepared.strip()) if part]


def _join_case(parts: list[str], target_case: str) -> str:
    if target_case == "upper":
        return " ".join(parts).upper()
    if target_case == "lower":
        return " ".join(parts).lower()
    if target_case == "title":
        return " ".join(part.capitalize() for part in parts)
    if target_case == "capitalize":
        return " ".join(parts).capitalize()
    if target_case == "swapcase":
        return " ".join(parts).swapcase()
    if not parts:
        return ""
    lowered = [part.lower() for part in parts]
    if target_case == "camel":
        return lowered[0] + "".join(part.capitalize() for part in lowered[1:])
    if target_case == "pascal":
        return "".join(part.capitalize() for part in lowered)
    if target_case == "snake":
        return "_".join(lowered)
    if target_case == "kebab":
        return "-".join(lowered)
    raise DataFactoryExecutionError("不支持的大小写转换类型")


def _normalize_base64_binary(value: str) -> tuple[str | None, bytes]:
    text = value.strip()
    mime_type = None
    if text.startswith("data:") and "," in text:
        header, body = text.split(",", 1)
        mime_type = header.split(";")[0][5:] or "application/octet-stream"
        text = body
    try:
        return mime_type, base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise DataFactoryExecutionError("Base64 数据不合法") from exc


def _binary_to_data_url(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('utf-8')}"


def _derive_aes_key(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def _flatten_dict(value: Any, prefix: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.update(_flatten_dict(item, next_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            next_prefix = f"{prefix}.{index}" if prefix else str(index)
            items.update(_flatten_dict(item, next_prefix))
    else:
        items[prefix or "value"] = value
    return items


def _dict_to_xml(parent: Element, data: Any, key_name: str = "item") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            child = SubElement(parent, str(key))
            _dict_to_xml(child, value, "item")
        return
    if isinstance(data, list):
        for item in data:
            child = SubElement(parent, key_name)
            _dict_to_xml(child, item, key_name)
        return
    parent.text = "" if data is None else str(data)


def _json_diff(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    if type(left) is not type(right):
        diffs.append({"path": path, "type": "type_changed", "left": left, "right": right})
        return diffs
    if isinstance(left, dict):
        keys = set(left.keys()) | set(right.keys())
        for key in sorted(keys):
            next_path = f"{path}.{key}"
            if key not in left:
                diffs.append({"path": next_path, "type": "added", "left": None, "right": right[key]})
            elif key not in right:
                diffs.append({"path": next_path, "type": "removed", "left": left[key], "right": None})
            else:
                diffs.extend(_json_diff(left[key], right[key], next_path))
        return diffs
    if isinstance(left, list):
        max_length = max(len(left), len(right))
        for index in range(max_length):
            next_path = f"{path}[{index}]"
            if index >= len(left):
                diffs.append({"path": next_path, "type": "added", "left": None, "right": right[index]})
            elif index >= len(right):
                diffs.append({"path": next_path, "type": "removed", "left": left[index], "right": None})
            else:
                diffs.extend(_json_diff(left[index], right[index], next_path))
        return diffs
    if left != right:
        diffs.append({"path": path, "type": "changed", "left": left, "right": right})
    return diffs


def _parse_color(value: str) -> tuple[int, int, int]:
    text = value.strip()
    hex_match = HEX_COLOR_PATTERN.match(text)
    if hex_match:
        color = hex_match.group(1)
        if len(color) == 3:
            color = "".join(char * 2 for char in color)
        return tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    rgb_match = RGB_COLOR_PATTERN.match(text)
    if rgb_match:
        rgb = tuple(int(rgb_match.group(name)) for name in ("r", "g", "b"))
        if any(not 0 <= item <= 255 for item in rgb):
            raise DataFactoryExecutionError("RGB 颜色值必须在 0-255 之间")
        return rgb  # type: ignore[return-value]
    hsl_match = HSL_COLOR_PATTERN.match(text)
    if hsl_match:
        h = int(hsl_match.group("h")) % 360
        s = int(hsl_match.group("s"))
        l = int(hsl_match.group("l"))
        if any(not 0 <= item <= 100 for item in (s, l)):
            raise DataFactoryExecutionError("HSL 的饱和度和亮度必须在 0-100 之间")
        red, green, blue = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
        return int(round(red * 255)), int(round(green * 255)), int(round(blue * 255))
    raise DataFactoryExecutionError("无法识别颜色值，请输入 HEX、RGB 或 HSL")


def handle_normalize_string(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    mode = str(payload.get("mode") or "trim")
    if mode == "trim":
        value = text.strip()
    elif mode == "remove_all_whitespace":
        value = re.sub(r"\s+", "", text)
    elif mode == "collapse_spaces":
        value = re.sub(r"[ \t]+", " ", text).strip()
    elif mode == "remove_blank_lines":
        value = "\n".join(line for line in text.splitlines() if line.strip())
    elif mode == "single_line":
        value = re.sub(r"\s+", " ", text).strip()
    else:
        raise DataFactoryExecutionError("不支持的字符串处理方式")
    return _result(tool_name, value, summary=f"字符串处理完成，输出长度 {len(value)}")


def handle_text_diff(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    left_text = _ensure_text(payload.get("left_text"), "文本 A")
    right_text = _ensure_text(payload.get("right_text"), "文本 B")
    matcher = difflib.SequenceMatcher(None, left_text, right_text)
    diff_lines = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile="text_a",
            tofile="text_b",
            lineterm="",
        )
    )
    return _result(
        tool_name,
        {
            "similarity": round(matcher.ratio() * 100, 2),
            "same": left_text == right_text,
            "diff_lines": diff_lines,
            "left_line_count": len(left_text.splitlines()),
            "right_line_count": len(right_text.splitlines()),
        },
        summary=f"文本相似度 {round(matcher.ratio() * 100, 2)}%",
    )


def handle_regex_test(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    pattern = _ensure_text(payload.get("pattern"), "正则表达式")
    text = _ensure_text(payload.get("text"), "测试文本")
    flags = _parse_flags(payload.get("flags") or [])
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise DataFactoryExecutionError(f"正则表达式错误: {exc}") from exc
    matches = list(compiled.finditer(text))
    data = [
        {
            "match": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "groups": list(match.groups()),
            "group_dict": match.groupdict(),
        }
        for match in matches
    ]
    return _result(
        tool_name,
        {"matched": bool(matches), "count": len(matches), "matches": data},
        summary=f"共匹配到 {len(matches)} 处结果",
    )


def handle_word_count(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    words = re.findall(r"\b[\w-]+\b", text, flags=re.UNICODE)
    result = {
        "characters": len(text),
        "characters_without_spaces": len(re.sub(r"\s+", "", text)),
        "words": len(words),
        "lines": len(text.splitlines()) if text else 0,
        "paragraphs": len([item for item in re.split(r"\n\s*\n", text) if item.strip()]),
        "chinese_characters": len(chinese_chars),
    }
    return _result(tool_name, result, summary=f"统计完成，共 {result['characters']} 个字符")


def handle_case_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    target_case = str(payload.get("target_case") or "upper")
    words = _split_words(text)
    value = _join_case(words or [text], target_case)
    return _result(tool_name, value, summary=f"已转换为 {target_case} 格式")


def handle_replace_string(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    search = _ensure_text(payload.get("search"), "查找内容")
    replace = str(payload.get("replace") or "")
    use_regex = bool(payload.get("use_regex"))
    ignore_case = bool(payload.get("ignore_case"))
    count = int(payload.get("count") or 0)
    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        replaced, actual_count = re.subn(search, replace, text, count=count or 0, flags=flags)
    else:
        if ignore_case:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            replaced, actual_count = pattern.subn(replace, text, count=count or 0)
        else:
            actual_count = text.count(search) if count == 0 else min(text.count(search), count)
            replaced = text.replace(search, replace, count or -1)
    return _result(tool_name, {"text": replaced, "replace_count": actual_count}, summary=f"共替换 {actual_count} 次")


def handle_split_text(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    delimiter = _ensure_text(payload.get("delimiter"), "分隔符").encode("utf-8").decode("unicode_escape")
    parts = text.split(delimiter)
    if bool(payload.get("trim_items", True)):
        parts = [item.strip() for item in parts]
    if bool(payload.get("remove_empty", True)):
        parts = [item for item in parts if item != ""]
    return _result(tool_name, parts, summary=f"共拆分出 {len(parts)} 项")


def handle_join_text(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    items = _parse_list_input(payload.get("items"))
    delimiter = _ensure_text(payload.get("delimiter"), "连接符").encode("utf-8").decode("unicode_escape")
    prefix = str(payload.get("prefix") or "")
    suffix = str(payload.get("suffix") or "")
    value = prefix + delimiter.join(str(item) for item in items) + suffix
    return _result(tool_name, value, summary=f"已拼接 {len(items)} 个元素")


def handle_string_format(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    format_type = str(payload.get("format_type") or "template")
    if format_type == "template":
        variables = payload.get("variables") or {}
        if isinstance(variables, str):
            variables = _parse_json_text(variables)
        if not isinstance(variables, dict):
            raise DataFactoryExecutionError("模板变量必须是对象")
        value = text.format(**variables)
    elif format_type == "reverse":
        value = text[::-1]
    else:
        width = int(payload.get("width") or 20)
        fillchar = str(payload.get("fillchar") or " ")[:1]
        if format_type == "ljust":
            value = text.ljust(width, fillchar)
        elif format_type == "rjust":
            value = text.rjust(width, fillchar)
        elif format_type == "center":
            value = text.center(width, fillchar)
        else:
            raise DataFactoryExecutionError("不支持的字符串格式化方式")
    return _result(tool_name, value, summary="字符串格式化完成")


def handle_random_integer(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    min_value = int(payload.get("min_value") or 0)
    max_value = int(payload.get("max_value") or 100)
    count = int(payload.get("count") or 1)
    if min_value > max_value:
        raise DataFactoryExecutionError("最小值不能大于最大值")
    values = [random.randint(min_value, max_value) for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个随机整数")


def handle_random_float(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    min_value = float(payload.get("min_value") or 0)
    max_value = float(payload.get("max_value") or 1)
    precision = int(payload.get("precision") or 2)
    count = int(payload.get("count") or 1)
    if min_value > max_value:
        raise DataFactoryExecutionError("最小值不能大于最大值")
    values = [round(random.uniform(min_value, max_value), precision) for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个随机浮点数")


def handle_random_string(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    length = int(payload.get("length") or 12)
    count = int(payload.get("count") or 1)
    char_type = str(payload.get("char_type") or "alphanumeric")
    charsets = {
        "digits": string.digits,
        "lower": string.ascii_lowercase,
        "upper": string.ascii_uppercase,
        "letters": string.ascii_letters,
        "alphanumeric": string.ascii_letters + string.digits,
        "hex": string.hexdigits.lower()[:16],
        "all": string.ascii_letters + string.digits + "!@#$%^&*()-_=+",
    }
    charset = charsets.get(char_type)
    if not charset:
        raise DataFactoryExecutionError("不支持的字符集类型")
    values = ["".join(secrets.choice(charset) for _ in range(length)) for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个随机字符串")


def handle_random_uuid(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = int(payload.get("version") or 4)
    count = int(payload.get("count") or 1)
    factory = uuid.uuid1 if version == 1 else uuid.uuid4
    values = [str(factory()) for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个 UUID")


def handle_random_boolean(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    probability = float(payload.get("true_probability") or 50) / 100
    count = int(payload.get("count") or 1)
    values = [random.random() < probability for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个随机布尔值")


def handle_random_list_element(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    items = _parse_list_input(payload.get("items"))
    count = int(payload.get("count") or 1)
    unique = bool(payload.get("unique"))
    if not items:
        raise DataFactoryExecutionError("列表数据不能为空")
    if unique:
        if count > len(items):
            raise DataFactoryExecutionError("不重复抽取时，数量不能大于列表长度")
        value = random.sample(items, count)
    else:
        value = [random.choice(items) for _ in range(count)]
    return _result(tool_name, value[0] if count == 1 else value, summary=f"已抽取 {count} 个列表元素")


def handle_generate_chinese_name(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("count") or 1)
    gender = str(payload.get("gender") or "random")
    values: list[str] = []
    for _ in range(count):
        if gender == "male":
            values.append(faker.name_male())
        elif gender == "female":
            values.append(faker.name_female())
        else:
            values.append(faker.name())
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个中文姓名")


def handle_generate_chinese_phone(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("count") or 1)
    values = [faker.phone_number() for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个手机号")


def handle_generate_chinese_email(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("count") or 1)
    domain = str(payload.get("domain") or "example.com")
    values = [f"{faker.user_name()}@{domain}" for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个邮箱地址")


def handle_generate_chinese_address(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    count = int(payload.get("count") or 1)
    full_address = bool(payload.get("full_address", True))
    values = [faker.address().replace("\n", " ") if full_address else faker.city() for _ in range(count)]
    return _result(tool_name, values[0] if count == 1 else values, summary=f"生成 {count} 个地址")


def handle_base64_encode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    encoding = str(payload.get("encoding") or "utf-8")
    value = base64.b64encode(text.encode(encoding)).decode("utf-8")
    return _result(tool_name, value, summary="Base64 编码完成")


def handle_base64_decode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "Base64 内容")
    encoding = str(payload.get("encoding") or "utf-8")
    try:
        value = base64.b64decode(text).decode(encoding)
    except Exception as exc:  # noqa: BLE001
        raise DataFactoryExecutionError("Base64 解码失败，请检查输入内容") from exc
    return _result(tool_name, value, summary="Base64 解码完成")


def handle_timestamp_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "seconds_to_datetime")
    value = _ensure_text(payload.get("value"), "输入值").strip()
    timezone_name = str(payload.get("timezone") or "Asia/Shanghai")
    datetime_format = str(payload.get("datetime_format") or "%Y-%m-%d %H:%M:%S")
    tz = ZoneInfo(timezone_name)
    if mode == "seconds_to_datetime":
        dt = datetime.fromtimestamp(int(float(value)), tz)
        result = dt.strftime(datetime_format)
    elif mode == "milliseconds_to_datetime":
        dt = datetime.fromtimestamp(float(value) / 1000, tz)
        result = dt.strftime(datetime_format)
    elif mode == "datetime_to_seconds":
        dt = datetime.strptime(value, datetime_format).replace(tzinfo=tz)
        result = int(dt.timestamp())
    elif mode == "datetime_to_milliseconds":
        dt = datetime.strptime(value, datetime_format).replace(tzinfo=tz)
        result = int(dt.timestamp() * 1000)
    else:
        raise DataFactoryExecutionError("不支持的时间戳转换方式")
    return _result(tool_name, result, summary="时间戳转换完成", metadata={"timezone": timezone_name})


def handle_unicode_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    mode = str(payload.get("mode") or "encode")
    if mode == "encode":
        result = text.encode("unicode_escape").decode("utf-8")
    elif mode == "decode":
        result = text.encode("utf-8").decode("unicode_escape")
    else:
        raise DataFactoryExecutionError("不支持的 Unicode 转换方式")
    return _result(tool_name, result, summary="Unicode 转换完成")


def handle_base_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    value = _ensure_text(payload.get("value"), "原始数值").strip().lower()
    from_base = int(payload.get("from_base") or 10)
    to_base = int(payload.get("to_base") or 16)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    try:
        integer = int(value, from_base)
    except ValueError as exc:
        raise DataFactoryExecutionError("输入值与原进制不匹配") from exc
    if integer == 0:
        result = "0"
    else:
        negative = integer < 0
        integer = abs(integer)
        parts: list[str] = []
        while integer > 0:
            integer, remainder = divmod(integer, to_base)
            parts.append(digits[remainder])
        result = ("-" if negative else "") + "".join(reversed(parts))
    return _result(tool_name, result, summary=f"已完成 {from_base} -> {to_base} 进制转换")


def handle_color_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    rgb = _parse_color(_ensure_text(payload.get("value"), "颜色值"))
    output_type = str(payload.get("output_type") or "hex")
    if output_type == "hex":
        result = "#{:02x}{:02x}{:02x}".format(*rgb)
    elif output_type == "rgb":
        result = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
    elif output_type == "hsl":
        hue, lightness, saturation = colorsys.rgb_to_hls(*(item / 255 for item in rgb))
        result = "hsl({h}, {s}%, {l}%)".format(
            h=round(hue * 360),
            s=round(saturation * 100),
            l=round(lightness * 100),
        )
    else:
        raise DataFactoryExecutionError("不支持的颜色输出格式")
    return _result(tool_name, {"rgb": rgb, "value": result}, summary="颜色值转换完成")


def handle_url_encode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    safe = str(payload.get("safe") or "")
    return _result(tool_name, quote(text, safe=safe), summary="URL 编码完成")


def handle_url_decode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "URL 编码文本")
    return _result(tool_name, unquote(text), summary="URL 解码完成")


def handle_jwt_decode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = _ensure_text(payload.get("token"), "JWT Token").strip()
    parts = token.split(".")
    if len(parts) < 2:
        raise DataFactoryExecutionError("JWT 格式不正确")

    def decode_part(value: str) -> Any:
        padded = value + "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return raw.decode("utf-8", errors="replace")

    result = {
        "header": decode_part(parts[0]),
        "payload": decode_part(parts[1]),
        "signature": parts[2] if len(parts) > 2 else "",
    }
    return _result(tool_name, result, summary="JWT 解码完成")


def handle_generate_barcode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "条形码内容")
    barcode_type = str(payload.get("barcode_type") or "code128").lower()
    barcode_class = barcode.get_barcode_class(barcode_type)
    buffer = io.BytesIO()
    barcode_instance = barcode_class(text, writer=ImageWriter())
    barcode_instance.write(buffer)
    image_bytes = buffer.getvalue()
    result = {
        "data_url": _binary_to_data_url(image_bytes, "image/png"),
        "mime_type": "image/png",
        "size": len(image_bytes),
    }
    return _result(tool_name, result, summary="条形码生成完成")


def handle_generate_qrcode(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "二维码内容")
    box_size = int(payload.get("box_size") or 8)
    border = int(payload.get("border") or 2)
    qr = qrcode.QRCode(box_size=box_size, border=border)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()
    result = {
        "data_url": _binary_to_data_url(image_bytes, "image/png"),
        "mime_type": "image/png",
        "size": len(image_bytes),
    }
    return _result(tool_name, result, summary="二维码生成完成")


def handle_image_base64_convert(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "image_to_base64")
    image_data = _ensure_text(payload.get("image_data"), "图片或 Base64 数据")
    include_prefix = bool(payload.get("include_prefix", True))
    mime_type, raw_bytes = _normalize_base64_binary(image_data)
    mime_type = mime_type or "image/png"
    if mode == "image_to_base64":
        base64_text = base64.b64encode(raw_bytes).decode("utf-8")
        value = _binary_to_data_url(raw_bytes, mime_type) if include_prefix else base64_text
    elif mode == "base64_to_image":
        value = {
            "data_url": _binary_to_data_url(raw_bytes, mime_type),
            "mime_type": mime_type,
            "size": len(raw_bytes),
        }
    else:
        raise DataFactoryExecutionError("不支持的图片 Base64 转换方式")
    return _result(tool_name, value, summary="图片 Base64 转换完成")


def _hash(tool_name: str, payload: dict[str, Any], algorithm: str) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    digest = getattr(hashlib, algorithm)(text.encode("utf-8")).hexdigest()
    return _result(tool_name, digest, summary=f"{algorithm.upper()} 哈希完成")


def handle_aes_encrypt(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "输入文本")
    password = _ensure_text(payload.get("password"), "密钥口令")
    mode = str(payload.get("mode") or "CBC").upper()
    key = _derive_aes_key(password)
    if mode == "CBC":
        iv = secrets.token_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted = iv + cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))
    elif mode == "ECB":
        cipher = AES.new(key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))
        iv = b""
    else:
        raise DataFactoryExecutionError("AES 当前仅支持 CBC 和 ECB")
    return _result(
        tool_name,
        {
            "cipher_text": base64.b64encode(encrypted).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8") if iv else "",
            "mode": mode,
        },
        summary="AES 加密完成",
    )


def handle_aes_decrypt(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    cipher_text = _ensure_text(payload.get("cipher_text"), "密文")
    password = _ensure_text(payload.get("password"), "密钥口令")
    mode = str(payload.get("mode") or "CBC").upper()
    raw = base64.b64decode(cipher_text)
    key = _derive_aes_key(password)
    if mode == "CBC":
        iv, content = raw[:16], raw[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
    elif mode == "ECB":
        content = raw
        cipher = AES.new(key, AES.MODE_ECB)
    else:
        raise DataFactoryExecutionError("AES 当前仅支持 CBC 和 ECB")
    try:
        result = unpad(cipher.decrypt(content), AES.block_size).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise DataFactoryExecutionError("AES 解密失败，请检查密钥或密文") from exc
    return _result(tool_name, result, summary="AES 解密完成")


def handle_hmac_sign(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "原始文本")
    secret = _ensure_text(payload.get("secret"), "签名密钥")
    algorithm = str(payload.get("algorithm") or "sha256").lower()
    digestmod = getattr(hashlib, algorithm, None)
    if digestmod is None:
        raise DataFactoryExecutionError("不支持的 HMAC 算法")
    signature = hmac.new(secret.encode("utf-8"), text.encode("utf-8"), digestmod).hexdigest()
    return _result(tool_name, signature, summary=f"HMAC {algorithm.upper()} 签名完成")


def handle_hash_compare(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "原始文本")
    expected_hash = _ensure_text(payload.get("expected_hash"), "目标哈希").strip().lower()
    algorithm = str(payload.get("algorithm") or "sha256").lower()
    actual_hash = getattr(hashlib, algorithm)(text.encode("utf-8")).hexdigest()
    result = {"matched": hmac.compare_digest(actual_hash, expected_hash), "actual_hash": actual_hash}
    return _result(tool_name, result, summary="哈希校验完成")


def handle_json_format(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    indent = int(payload.get("indent") or 2)
    sort_keys = bool(payload.get("sort_keys"))
    text = json.dumps(parsed, ensure_ascii=False, indent=indent, sort_keys=sort_keys)
    return _result(tool_name, {"text": text, "parsed": parsed}, summary="JSON 格式化完成")


def handle_json_minify(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    return _result(tool_name, json.dumps(parsed, ensure_ascii=False, separators=(",", ":")), summary="JSON 压缩完成")


def handle_json_validate(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    text = _ensure_text(payload.get("text"), "JSON 内容")
    try:
        parsed = json.loads(text)
        result = {"valid": True, "type": type(parsed).__name__}
        summary = "JSON 校验通过"
    except json.JSONDecodeError as exc:
        result = {"valid": False, "message": exc.msg, "line": exc.lineno, "column": exc.colno}
        summary = "JSON 校验未通过"
    return _result(tool_name, result, summary=summary)


def handle_jsonpath_query(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    path = _ensure_text(payload.get("path"), "JSONPath")
    try:
        expression = jsonpath_parse(path)
    except Exception as exc:  # noqa: BLE001
        raise DataFactoryExecutionError(f"JSONPath 表达式错误: {exc}") from exc
    matches = [match.value for match in expression.find(parsed)]
    return _result(tool_name, {"path": path, "matches": matches, "count": len(matches)}, summary=f"JSONPath 命中 {len(matches)} 个结果")


def handle_json_diff(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    left_text = _ensure_text(payload.get("left_text"), "JSON A")
    right_text = _ensure_text(payload.get("right_text"), "JSON B")
    left = _parse_json_text(left_text)
    right = _parse_json_text(right_text)
    diffs = _json_diff(left, right)
    return _result(tool_name, {"different": bool(diffs), "count": len(diffs), "diffs": diffs}, summary=f"发现 {len(diffs)} 处差异")


def handle_json_to_xml(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    root = Element(str(payload.get("root_name") or "root"))
    _dict_to_xml(root, parsed)
    xml_text = tostring(root, encoding="unicode")
    return _result(tool_name, xml_text, summary="JSON 转 XML 完成")


def handle_json_to_yaml(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    return _result(tool_name, yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False), summary="JSON 转 YAML 完成")


def handle_json_to_csv(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = _parse_json_text(_ensure_text(payload.get("text"), "JSON 内容"))
    rows = parsed if isinstance(parsed, list) else [parsed]
    flattened_rows = [_flatten_dict(item if isinstance(item, dict) else {"value": item}) for item in rows]
    headers = sorted({key for row in flattened_rows for key in row.keys()})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(flattened_rows)
    return _result(tool_name, buffer.getvalue(), summary="JSON 转 CSV 完成", metadata={"columns": headers})


def handle_cron_generate(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    expression = " ".join(
        str(payload.get(key) or "*").strip()
        for key in ("minute", "hour", "day", "month", "weekday")
    )
    croniter(expression)
    return _result(tool_name, expression, summary="Crontab 表达式生成完成")


def handle_cron_parse(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    expression = _ensure_text(payload.get("expression"), "Crontab 表达式")
    fields = expression.split()
    if len(fields) != 5:
        raise DataFactoryExecutionError("Crontab 表达式必须为 5 段")
    result = {
        "expression": expression,
        "minute": fields[0],
        "hour": fields[1],
        "day": fields[2],
        "month": fields[3],
        "weekday": fields[4],
    }
    return _result(tool_name, result, summary="Crontab 表达式解析完成")


def handle_cron_next_runs(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    expression = _ensure_text(payload.get("expression"), "Crontab 表达式")
    count = int(payload.get("count") or 5)
    timezone_name = str(payload.get("timezone") or "Asia/Shanghai")
    tz = ZoneInfo(timezone_name)
    base_time = datetime.now(tz)
    iterator = croniter(expression, base_time)
    values = [iterator.get_next(datetime).isoformat() for _ in range(count)]
    return _result(tool_name, values, summary=f"已计算未来 {count} 次执行时间", metadata={"timezone": timezone_name})


def handle_cron_validate(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    expression = _ensure_text(payload.get("expression"), "Crontab 表达式")
    try:
        croniter(expression)
        result = {"valid": True}
        summary = "Crontab 表达式合法"
    except Exception as exc:  # noqa: BLE001
        result = {"valid": False, "message": str(exc)}
        summary = "Crontab 表达式不合法"
    return _result(tool_name, result, summary=summary)


TOOL_HANDLERS: dict[str, Any] = {
    "normalize_string": handle_normalize_string,
    "text_diff": handle_text_diff,
    "regex_test": handle_regex_test,
    "word_count": handle_word_count,
    "case_convert": handle_case_convert,
    "replace_string": handle_replace_string,
    "split_text": handle_split_text,
    "join_text": handle_join_text,
    "string_format": handle_string_format,
    "base64_encode": handle_base64_encode,
    "base64_decode": handle_base64_decode,
    "timestamp_convert": handle_timestamp_convert,
    "unicode_convert": handle_unicode_convert,
    "base_convert": handle_base_convert,
    "color_convert": handle_color_convert,
    "url_encode": handle_url_encode,
    "url_decode": handle_url_decode,
    "jwt_decode": handle_jwt_decode,
    "generate_barcode": handle_generate_barcode,
    "generate_qrcode": handle_generate_qrcode,
    "image_base64_convert": handle_image_base64_convert,
    "random_integer": handle_random_integer,
    "random_float": handle_random_float,
    "random_string": handle_random_string,
    "random_uuid": handle_random_uuid,
    "random_boolean": handle_random_boolean,
    "random_list_element": handle_random_list_element,
    "md5_hash": lambda tool_name, payload: _hash(tool_name, payload, "md5"),
    "sha1_hash": lambda tool_name, payload: _hash(tool_name, payload, "sha1"),
    "sha256_hash": lambda tool_name, payload: _hash(tool_name, payload, "sha256"),
    "sha512_hash": lambda tool_name, payload: _hash(tool_name, payload, "sha512"),
    "aes_encrypt": handle_aes_encrypt,
    "aes_decrypt": handle_aes_decrypt,
    "hmac_sign": handle_hmac_sign,
    "hash_compare": handle_hash_compare,
    "generate_chinese_name": handle_generate_chinese_name,
    "generate_chinese_phone": handle_generate_chinese_phone,
    "generate_chinese_email": handle_generate_chinese_email,
    "generate_chinese_address": handle_generate_chinese_address,
    "json_format": handle_json_format,
    "json_minify": handle_json_minify,
    "json_validate": handle_json_validate,
    "jsonpath_query": handle_jsonpath_query,
    "json_diff": handle_json_diff,
    "json_to_xml": handle_json_to_xml,
    "json_to_yaml": handle_json_to_yaml,
    "json_to_csv": handle_json_to_csv,
    "cron_generate": handle_cron_generate,
    "cron_parse": handle_cron_parse,
    "cron_next_runs": handle_cron_next_runs,
    "cron_validate": handle_cron_validate,
}


def execute_tool(tool_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        raise DataFactoryExecutionError(f"未找到工具: {tool_name}")
    try:
        return handler(tool_name, payload or {})
    except DataFactoryExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataFactoryExecutionError(f"工具执行失败: {exc}") from exc
