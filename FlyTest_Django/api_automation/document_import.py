from __future__ import annotations

import importlib.util
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup


HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
STRUCTURED_EXTENSIONS = {".json", ".yaml", ".yml"}
TEXT_EXTENSIONS = {".txt", ".md"}
NATIVE_DOCUMENT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".epub", ".html", ".htm"}
MARKER_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".doc",
    ".xls",
}

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
ENDPOINT_PATTERN = re.compile(
    r"(?im)^(?:#{1,6}\s+)?(?P<method>GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(?P<url>(?:https?://|/)[^\s`]+)"
)
HEADING_PATTERN = re.compile(r"(?m)^(#{1,6})\s+(?P<title>.+)$")
CODE_BLOCK_PATTERN = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\n(?P<content>.*?)```", re.S)
URL_IN_TEXT_PATTERN = re.compile(r"((?:https?://|/)[^\s`\"'<>]+)")
STATUS_CODE_TEXT_PATTERN = re.compile(r"(?:status(?:\s*code)?|状态码|响应码)\s*[:：]?\s*(\d{3})", re.I)
JSON_PATH_TEXT_PATTERN = re.compile(r"((?:data|result|response)(?:\.[A-Za-z0-9_-]+)+)")


@dataclass
class ParsedRequestData:
    name: str
    method: str
    url: str
    description: str = ""
    headers: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    body_type: str = "none"
    body: Any = field(default_factory=dict)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    collection_name: str | None = None


@dataclass
class DocumentImportResult:
    source_type: str
    requests: list[ParsedRequestData]
    marker_used: bool = False
    note: str = ""


class VariableResolver:
    def __init__(self, variables: dict[str, Any] | None = None):
        base_variables = variables.copy() if variables else {}
        base_variables.setdefault("timestamp", int(__import__("time").time()))
        base_variables.setdefault("timestamp_ms", int(__import__("time").time() * 1000))
        base_variables.setdefault("uuid", str(uuid.uuid4()))
        base_variables.setdefault("random_int", random.randint(100000, 999999))
        self.variables = base_variables

    def resolve(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if isinstance(value, str):
            return self.resolve_string(value)
        return value

    def resolve_string(self, value: str) -> Any:
        matched = PLACEHOLDER_PATTERN.fullmatch(value.strip())
        if matched:
            return self.variables.get(matched.group(1), value)

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            replacement = self.variables.get(key, match.group(0))
            if isinstance(replacement, (dict, list)):
                return json.dumps(replacement, ensure_ascii=False)
            return str(replacement)

        return PLACEHOLDER_PATTERN.sub(replace, value)


def build_request_url(base_url: str, request_url: str) -> str:
    if request_url.startswith(("http://", "https://")):
        return request_url
    if not base_url:
        return request_url
    return urljoin(base_url.rstrip("/") + "/", request_url.lstrip("/"))


def extract_json_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            if not part.isdigit():
                return None
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def evaluate_assertions(
    assertions: list[dict[str, Any]],
    status_code: int,
    response_text: str,
    response_json: Any,
) -> tuple[list[dict[str, Any]], bool]:
    if not assertions:
        return [], True

    results: list[dict[str, Any]] = []
    all_passed = True

    for index, assertion in enumerate(assertions, start=1):
        assertion_type = assertion.get("type")
        expected = assertion.get("expected")
        operator = assertion.get("operator", "equals")
        path = assertion.get("path")
        passed = False
        actual: Any = None
        message = ""

        if assertion_type == "status_code":
            actual = status_code
            passed = actual == int(expected)
            message = f"状态码应为 {expected}"
        elif assertion_type == "body_contains":
            actual = response_text
            passed = str(expected) in response_text
            message = f"响应体包含 {expected}"
        elif assertion_type == "json_path":
            actual = extract_json_path(response_json, str(path)) if response_json is not None and path else None
            if operator == "contains":
                passed = str(expected) in str(actual)
            elif operator == "not_equals":
                passed = actual != expected
            else:
                passed = actual == expected
            message = f"JSONPath {path} {operator} {expected}"
        elif assertion_type == "header":
            actual = None
            passed = False
            message = f"暂不支持 header 断言: {path or ''}"
        else:
            actual = None
            passed = False
            message = f"未知断言类型: {assertion_type}"

        results.append(
            {
                "index": index,
                "type": assertion_type,
                "operator": operator,
                "path": path,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "message": message,
            }
        )
        all_passed = all_passed and passed

    return results, all_passed


def import_requests_from_document(file_path: str) -> DocumentImportResult:
    suffix = Path(file_path).suffix.lower()

    structured_result = parse_structured_document(file_path)
    if structured_result is not None:
        return structured_result

    if suffix in TEXT_EXTENSIONS:
        markdown = load_text_document(file_path)
        requests = extract_requests_from_markdown(markdown)
        return DocumentImportResult("text_markdown", requests, False, "已从文本接口文档中抽取接口定义")

    if suffix in NATIVE_DOCUMENT_EXTENSIONS:
        markdown = extract_text_document_content(file_path)
        requests = extract_requests_from_markdown(markdown)
        return DocumentImportResult("native_document", requests, False, "已通过本地文档解析器抽取接口定义")

    if suffix in MARKER_EXTENSIONS:
        markdown = convert_document_with_marker(file_path)
        requests = extract_requests_from_markdown(markdown)
        return DocumentImportResult("marker_markdown", requests, True, "已通过 marker 转换文档并抽取接口定义")

    raise ValueError(f"暂不支持的接口文档格式: {suffix or 'unknown'}")


def load_document_content_for_ai(file_path: str) -> tuple[str, str, bool]:
    suffix = Path(file_path).suffix.lower()

    if suffix in STRUCTURED_EXTENSIONS | TEXT_EXTENSIONS:
        return load_text_document(file_path), "text_document", False

    if suffix in NATIVE_DOCUMENT_EXTENSIONS:
        return extract_text_document_content(file_path), "native_document", False

    if suffix in MARKER_EXTENSIONS:
        return convert_document_with_marker(file_path), "marker_markdown", True

    raise ValueError(f"Unsupported document format for AI parsing: {suffix or 'unknown'}")


def parse_structured_document(file_path: str) -> DocumentImportResult | None:
    suffix = Path(file_path).suffix.lower()
    content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

    if suffix == ".json":
        parsed = json.loads(content)
        if is_openapi_document(parsed):
            return DocumentImportResult("openapi", parse_openapi_document(parsed), False, "已按 OpenAPI/Swagger 结构解析")
        if is_postman_collection(parsed):
            return DocumentImportResult("postman", parse_postman_collection(parsed), False, "已按 Postman Collection 结构解析")
        return None

    if suffix in {".yaml", ".yml"}:
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict) and is_openapi_document(parsed):
            return DocumentImportResult("openapi", parse_openapi_document(parsed), False, "已按 OpenAPI/Swagger YAML 解析")
        return None

    if looks_like_openapi_text(content):
        parsed = yaml.safe_load(content)
        if isinstance(parsed, dict) and is_openapi_document(parsed):
            return DocumentImportResult("openapi", parse_openapi_document(parsed), False, "已按 OpenAPI 文本解析")

    return None


def is_openapi_document(data: Any) -> bool:
    return isinstance(data, dict) and (("openapi" in data and "paths" in data) or ("swagger" in data and "paths" in data))


def looks_like_openapi_text(content: str) -> bool:
    lowered = content.lower()
    return "paths:" in lowered and ("openapi:" in lowered or "swagger:" in lowered)


def is_postman_collection(data: Any) -> bool:
    return isinstance(data, dict) and "item" in data and "info" in data


def parse_openapi_document(spec: dict[str, Any]) -> list[ParsedRequestData]:
    requests: list[ParsedRequestData] = []
    base_url = ""
    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict):
        base_url = str(servers[0].get("url") or "").strip()
    elif spec.get("swagger"):
        host = str(spec.get("host") or "").strip()
        base_path = str(spec.get("basePath") or "").strip()
        schemes = spec.get("schemes") or ["http"]
        scheme = str(schemes[0]).strip() if schemes else "http"
        if host:
            normalized_base_path = ""
            if base_path:
                normalized_base_path = base_path if base_path.startswith("/") else f"/{base_path}"
            base_url = f"{scheme}://{host}{normalized_base_path}"

    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        path_level_params = path_item.get("parameters") or []
        for method, operation in path_item.items():
            upper_method = str(method).upper()
            if upper_method not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            parameters = list(path_level_params) + list(operation.get("parameters") or [])
            params: dict[str, Any] = {}
            headers: dict[str, Any] = {}
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                name = parameter.get("name")
                location = parameter.get("in")
                if not name or not location:
                    continue
                example = extract_parameter_example(parameter)
                if location == "query":
                    params[name] = example
                elif location == "header":
                    headers[name] = example

            body_type = "none"
            body: Any = {}
            request_body = operation.get("requestBody") or {}
            if isinstance(request_body, dict):
                body_type, body = parse_request_body(request_body)

            success_status = extract_success_status(operation.get("responses") or {})
            tags = operation.get("tags") or []
            request_name = operation.get("summary") or operation.get("operationId") or f"{upper_method} {path}"
            final_url = normalize_request_url(base_url, path)

            requests.append(
                ParsedRequestData(
                    name=request_name,
                    method=upper_method,
                    url=final_url,
                    description=str(operation.get("description") or ""),
                    headers=headers,
                    params=params,
                    body_type=body_type,
                    body=body,
                    assertions=[{"type": "status_code", "expected": success_status}],
                    collection_name=tags[0] if tags else guess_collection_name_from_path(path),
                )
            )

    return requests


def parse_postman_collection(collection: dict[str, Any]) -> list[ParsedRequestData]:
    requests: list[ParsedRequestData] = []

    def walk_items(items: list[dict[str, Any]], folder_name: str | None = None):
        for item in items:
            if not isinstance(item, dict):
                continue
            if "item" in item and isinstance(item["item"], list):
                walk_items(item["item"], item.get("name") or folder_name)
                continue

            request_data = item.get("request") or {}
            method = str(request_data.get("method") or "GET").upper()
            if method not in HTTP_METHODS:
                continue

            url = parse_postman_url(request_data.get("url"))
            headers = parse_postman_headers(request_data.get("header") or [])
            body_type, body = parse_postman_body(request_data.get("body") or {})
            requests.append(
                ParsedRequestData(
                    name=item.get("name") or f"{method} {url}",
                    method=method,
                    url=url,
                    description=str(item.get("description") or ""),
                    headers=headers,
                    params={},
                    body_type=body_type,
                    body=body,
                    assertions=[{"type": "status_code", "expected": 200}],
                    collection_name=folder_name,
                )
            )

    walk_items(collection.get("item") or [])
    return requests


def parse_postman_url(url_data: Any) -> str:
    if isinstance(url_data, str):
        return url_data
    if isinstance(url_data, dict):
        raw = url_data.get("raw")
        if raw:
            return str(raw)
        host = "".join(url_data.get("host") or [])
        path = "/".join(url_data.get("path") or [])
        protocol = url_data.get("protocol")
        if host:
            base = f"{protocol}://{host}" if protocol else host
            return f"{base}/{path}".rstrip("/")
        return f"/{path}".replace("//", "/")
    return "/"


def parse_postman_headers(header_list: list[dict[str, Any]]) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    for header in header_list:
        if isinstance(header, dict) and header.get("key"):
            headers[str(header["key"])] = header.get("value", "")
    return headers


def parse_postman_body(body_data: dict[str, Any]) -> tuple[str, Any]:
    mode = body_data.get("mode")
    if mode == "raw":
        raw = body_data.get("raw", "")
        try:
            return "json", json.loads(raw)
        except Exception:  # noqa: BLE001
            return "raw", raw
    if mode in {"urlencoded", "formdata"}:
        values = {}
        for item in body_data.get(mode) or []:
            if isinstance(item, dict) and item.get("key"):
                values[str(item["key"])] = item.get("value", "")
        return "form", values
    return "none", {}


def load_text_document(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() in {".html", ".htm"}:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        return soup.get_text("\n")
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_document_content(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in {".html", ".htm"}:
        return load_text_document(file_path)
    if suffix == ".docx":
        return extract_docx_text(file_path)
    if suffix == ".pptx":
        return extract_pptx_text(file_path)
    if suffix == ".xlsx":
        return extract_xlsx_text(file_path)
    if suffix == ".epub":
        return extract_epub_text(file_path)
    return load_text_document(file_path)


def extract_docx_text(file_path: str) -> str:
    from docx import Document

    document = Document(file_path)
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)
    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if values:
                lines.append(" | ".join(values))
    return "\n".join(lines)


def extract_pptx_text(file_path: str) -> str:
    from pptx import Presentation

    presentation = Presentation(file_path)
    lines: list[str] = []
    for index, slide in enumerate(presentation.slides, start=1):
        lines.append(f"# Slide {index}")
        for shape in slide.shapes:
            text = getattr(shape, "text", "")
            if text and text.strip():
                lines.append(text.strip())
    return "\n".join(lines)


def extract_xlsx_text(file_path: str) -> str:
    from openpyxl import load_workbook

    workbook = load_workbook(file_path, data_only=True)
    lines: list[str] = []
    for sheet in workbook.worksheets:
        lines.append(f"# Sheet {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if values:
                lines.append(" | ".join(values))
    return "\n".join(lines)


def extract_epub_text(file_path: str) -> str:
    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(file_path)
    lines: list[str] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        text = soup.get_text("\n").strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def convert_document_with_marker(file_path: str) -> str:
    marker_single = find_marker_single()
    if marker_single:
        return run_marker_cli(marker_single, file_path)

    if importlib.util.find_spec("marker") is not None:
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered

            converter = PdfConverter(artifact_dict=create_model_dict())
            rendered = converter(file_path)
            text, _, _ = text_from_rendered(rendered)
            return text
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"marker 文档转换失败: {exc}") from exc

    raise ValueError("当前环境未安装 marker。请先安装 marker-pdf[full]，以支持 PDF、图片等文档导入。")


def find_marker_single() -> str | None:
    configured = os.environ.get("MARKER_SINGLE_PATH")
    if configured and Path(configured).exists():
        return configured

    local_runtime = Path(__file__).resolve().parents[2] / "marker_runtime" / "Scripts" / "marker_single.exe"
    if local_runtime.exists():
        return str(local_runtime)

    local_runtime_cmd = Path(__file__).resolve().parents[2] / "marker_runtime" / "Scripts" / "marker_single"
    if local_runtime_cmd.exists():
        return str(local_runtime_cmd)

    return shutil.which("marker_single")


def run_marker_cli(marker_single: str, file_path: str) -> str:
    with tempfile.TemporaryDirectory(prefix="flytest-marker-") as tmpdir:
        command = [
            marker_single,
            file_path,
            "--output_format",
            "markdown",
            "--output_dir",
            tmpdir,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            if "libgobject-2.0-0" in stderr:
                raise ValueError(
                    "marker 在当前 Windows 环境下缺少 WeasyPrint 依赖库，暂时无法直接转换该 Office 文档。"
                    " 当前版本已内置 DOCX/PPTX/XLSX/EPUB/HTML 本地解析兜底，请优先使用这些格式的原生导入；"
                    " PDF 和图片仍可直接通过 marker 导入。"
                )
            raise ValueError(stderr or completed.stdout.strip() or "marker CLI 执行失败")

        stem = Path(file_path).stem
        markdown_path = Path(tmpdir) / f"{stem}.md"
        if not markdown_path.exists():
            nested_markdown_path = Path(tmpdir) / stem / f"{stem}.md"
            if nested_markdown_path.exists():
                markdown_path = nested_markdown_path
            else:
                candidates = list(Path(tmpdir).rglob("*.md"))
                if not candidates:
                    raise ValueError("marker 未生成 Markdown 输出")
                markdown_path = candidates[0]
        return markdown_path.read_text(encoding="utf-8", errors="ignore")


def extract_requests_from_markdown(markdown: str) -> list[ParsedRequestData]:
    requests: list[ParsedRequestData] = []
    seen: set[tuple[str, str]] = set()

    for parsed in extract_requests_from_curl(markdown):
        dedupe_key = (parsed.method, parsed.url)
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            requests.append(parsed)

    for parsed in extract_requests_from_structured_text(markdown):
        dedupe_key = (parsed.method, parsed.url)
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            requests.append(parsed)

    headings = list(HEADING_PATTERN.finditer(markdown))
    code_blocks = list(CODE_BLOCK_PATTERN.finditer(markdown))

    for match in ENDPOINT_PATTERN.finditer(markdown):
        method = match.group("method").upper()
        url = match.group("url").strip()
        dedupe_key = (method, url)
        if dedupe_key in seen:
            continue

        heading = nearest_heading(match.start(), headings)
        body_type = "none"
        body: Any = {}
        next_json_block = find_next_json_block(match.end(), code_blocks)
        if next_json_block and method not in {"GET", "DELETE", "HEAD", "OPTIONS"}:
            parsed = try_parse_json(next_json_block)
            if parsed is not None:
                body_type = "json"
                body = parsed
            else:
                body_type = "raw"
                body = next_json_block.strip()

        request_name = heading or f"{method} {url}"
        requests.append(
            ParsedRequestData(
                name=request_name,
                method=method,
                url=url,
                description=request_name,
                body_type=body_type,
                body=body,
                assertions=[{"type": "status_code", "expected": 200}],
                collection_name=heading,
            )
        )
        seen.add(dedupe_key)

    if not requests:
        raise ValueError("未能从接口文档中识别到接口，请优先上传 Swagger/OpenAPI/Postman 文件，或包含清晰 cURL 示例的接口文档。")

    return requests


def extract_requests_from_structured_text(markdown: str) -> list[ParsedRequestData]:
    requests: list[ParsedRequestData] = []
    candidate = create_structured_candidate()

    for raw_line in markdown.splitlines():
        line = normalize_structured_line(raw_line)
        if not line:
            finalized = finalize_structured_candidate(candidate)
            if finalized:
                requests.append(finalized)
            candidate = create_structured_candidate()
            continue

        label, value = split_structured_label(line)
        field_type = match_structured_field(label) if label else None

        if field_type == "name":
            finalized = finalize_structured_candidate(candidate)
            if finalized:
                requests.append(finalized)
                candidate = create_structured_candidate()
            candidate["name"] = value or candidate["name"]
            continue

        if field_type == "method":
            method = extract_method_from_text(value)
            if method:
                candidate["method"] = method
            continue

        if field_type == "url":
            url = extract_url_from_text(value)
            if url:
                candidate["url"] = url
            continue

        if field_type == "headers":
            candidate["headers"].update(parse_key_value_payload(value))
            continue

        if field_type == "query":
            candidate["query_params"].update(parse_parameter_payload(value))
            continue

        if field_type == "request_params":
            candidate["request_params"].update(parse_parameter_payload(value))
            continue

        if field_type == "body":
            body_type, body = parse_body_payload(value)
            if body_type != "none":
                candidate["body_type"] = body_type
                candidate["body"] = body
            continue

        if field_type == "success":
            candidate["success_notes"].append(value)
            continue

        if field_type == "description":
            candidate["description_lines"].append(value)
            continue

        inline_method = extract_method_from_text(line)
        inline_url = extract_url_from_text(line)
        if inline_method and inline_url:
            finalized = finalize_structured_candidate(candidate)
            if finalized:
                requests.append(finalized)
                candidate = create_structured_candidate()
            candidate["method"] = inline_method
            candidate["url"] = inline_url
            if not candidate["name"]:
                candidate["name"] = line
            continue

        if not candidate["name"] and looks_like_structured_name(line):
            candidate["name"] = line
            continue

        candidate["description_lines"].append(line)

    finalized = finalize_structured_candidate(candidate)
    if finalized:
        requests.append(finalized)

    deduped_requests: list[ParsedRequestData] = []
    seen: set[tuple[str, str]] = set()
    for item in requests:
        key = (item.method, item.url)
        if key in seen:
            continue
        seen.add(key)
        deduped_requests.append(item)
    return deduped_requests


def create_structured_candidate() -> dict[str, Any]:
    return {
        "name": "",
        "method": "",
        "url": "",
        "headers": {},
        "query_params": {},
        "request_params": {},
        "body_type": "none",
        "body": {},
        "description_lines": [],
        "success_notes": [],
    }


def normalize_structured_line(line: str) -> str:
    normalized = line.strip()
    normalized = re.sub(r"^#{1,6}\s*", "", normalized)
    normalized = re.sub(r"^[\-\*\u2022]\s*", "", normalized)
    normalized = re.sub(r"^\d+\.\s*", "", normalized)
    normalized = re.sub("^\\d+\u3001\\s*", "", normalized)
    return normalized.strip()


def split_structured_label(line: str) -> tuple[str | None, str]:
    for separator in ("\uFF1A", ":"):
        if separator in line:
            label, value = line.split(separator, 1)
            return label.strip(), value.strip()
    return None, line


def match_structured_field(label: str | None) -> str | None:
    if not label:
        return None
    normalized = re.sub(r"\s+", "", label).lower()
    field_aliases = {
        "name": {
            "\u63a5\u53e3\u540d\u79f0",
            "\u63a5\u53e3\u540d",
            "api\u540d\u79f0",
            "apiname",
            "\u540d\u79f0",
            "name",
        },
        "method": {
            "\u8bf7\u6c42\u65b9\u5f0f",
            "\u8bf7\u6c42\u65b9\u6cd5",
            "method",
            "httpmethod",
        },
        "url": {
            "\u8bf7\u6c42\u5730\u5740",
            "\u63a5\u53e3\u5730\u5740",
            "\u8bf7\u6c42\u8def\u5f84",
            "\u63a5\u53e3\u8def\u5f84",
            "\u8bf7\u6c42url",
            "\u63a5\u53e3url",
            "url",
            "path",
            "endpoint",
        },
        "headers": {"\u8bf7\u6c42\u5934", "header", "headers"},
        "query": {
            "\u67e5\u8be2\u53c2\u6570",
            "query",
            "queryparams",
            "querystring",
            "url\u53c2\u6570",
        },
        "request_params": {
            "\u8bf7\u6c42\u53c2\u6570",
            "\u5165\u53c2",
            "\u53c2\u6570",
            "requestparams",
            "path\u53c2\u6570",
            "pathparams",
        },
        "body": {
            "\u8bf7\u6c42\u4f53",
            "body",
            "body\u53c2\u6570",
            "\u8bf7\u6c42\u62a5\u6587",
            "bodypayload",
        },
        "success": {
            "\u6210\u529f\u54cd\u5e94",
            "\u54cd\u5e94\u7ed3\u679c",
            "\u8fd4\u56de\u7ed3\u679c",
            "\u8fd4\u56de\u793a\u4f8b",
            "\u54cd\u5e94\u793a\u4f8b",
            "\u54cd\u5e94\u5185\u5bb9",
            "\u8fd4\u56de\u5185\u5bb9",
            "\u8fd4\u56de\u5b57\u6bb5",
        },
        "description": {
            "\u63a5\u53e3\u63cf\u8ff0",
            "\u63cf\u8ff0",
            "\u8bf4\u660e",
            "\u7528\u9014",
            "\u529f\u80fd\u8bf4\u660e",
        },
    }
    for field_type, aliases in field_aliases.items():
        if normalized in aliases:
            return field_type
    return None


def looks_like_structured_name(line: str) -> bool:
    if extract_url_from_text(line):
        return False
    if extract_method_from_text(line):
        return False
    if len(line) > 80:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z]", line))


def extract_method_from_text(value: str) -> str | None:
    matched = re.search(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", value, re.I)
    if not matched:
        return None
    method = matched.group(1).upper()
    return method if method in HTTP_METHODS else None


def extract_url_from_text(value: str) -> str | None:
    matched = URL_IN_TEXT_PATTERN.search(value)
    if not matched:
        return None
    return matched.group(1).rstrip(".,;，；)")


def parse_key_value_payload(value: str) -> dict[str, Any]:
    parsed_json = try_parse_json(value)
    if isinstance(parsed_json, dict):
        return parsed_json

    pairs: dict[str, Any] = {}
    for key, raw_value in re.findall(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*(?:=|:|：)\s*([^,\n，；;]+)", value):
        pairs[key] = raw_value.strip()
    return pairs


def parse_parameter_payload(value: str) -> dict[str, Any]:
    parsed_json = try_parse_json(value)
    if isinstance(parsed_json, dict):
        return parsed_json

    pairs = parse_key_value_payload(value)
    if pairs:
        return pairs

    params: dict[str, Any] = {}
    for token in re.split(r"[,\n，；;、]+", value):
        token = token.strip()
        if not token:
            continue
        matched = re.match(r"([A-Za-z_][A-Za-z0-9_.-]*)", token)
        if not matched:
            continue
        key = matched.group(1)
        params[key] = f"{{{{{key}}}}}"
    return params


def parse_body_payload(value: str) -> tuple[str, Any]:
    parsed_json = try_parse_json(value)
    if parsed_json is not None:
        return "json", parsed_json

    parsed_params = parse_parameter_payload(value)
    if parsed_params:
        return "json", parsed_params

    stripped = value.strip()
    if stripped:
        return "raw", stripped
    return "none", {}


def extract_success_status_from_text(text: str, method: str) -> int:
    matched = STATUS_CODE_TEXT_PATTERN.search(text)
    if matched:
        try:
            return int(matched.group(1))
        except ValueError:
            pass
    if method == "POST" and any(
        keyword in text for keyword in ("\u521b\u5efa", "\u65b0\u589e", "create")
    ):
        return 201
    return 200


def extract_success_assertions(text: str, method: str) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = [{"type": "status_code", "expected": extract_success_status_from_text(text, method)}]
    seen_paths: set[str] = set()
    for path in JSON_PATH_TEXT_PATTERN.findall(text):
        if path in seen_paths:
            continue
        seen_paths.add(path)
        assertions.append(
            {
                "type": "json_path",
                "path": path,
                "operator": "not_equals",
                "expected": None,
            }
        )
        if len(seen_paths) >= 3:
            break
    return assertions


def finalize_structured_candidate(candidate: dict[str, Any]) -> ParsedRequestData | None:
    method = extract_method_from_text(candidate["method"]) or "GET"
    url = extract_url_from_text(candidate["url"])
    if not url:
        return None

    params = dict(candidate["query_params"])
    body_type = candidate["body_type"]
    body = candidate["body"]

    if candidate["request_params"]:
        if method in {"GET", "DELETE", "HEAD", "OPTIONS"}:
            params.update(candidate["request_params"])
        elif body_type == "none":
            body_type = "json"
            body = candidate["request_params"]

    success_text = " ".join(candidate["success_notes"]).strip()
    description_parts = [part for part in candidate["description_lines"] if part]
    if success_text:
        description_parts.append(success_text)
    description = " ".join(description_parts)[:5000]

    name = candidate["name"].strip() if candidate["name"] else ""
    if not name:
        name = f"{method} {url}"

    return ParsedRequestData(
        name=name[:120],
        method=method,
        url=url,
        description=description,
        headers=candidate["headers"],
        params=params,
        body_type=body_type if body_type in {"none", "json", "form", "raw"} else "none",
        body=body if body_type != "none" else {},
        assertions=extract_success_assertions(success_text, method),
        collection_name=guess_collection_name_from_path(url),
    )


def extract_requests_from_curl(markdown: str) -> list[ParsedRequestData]:
    requests: list[ParsedRequestData] = []
    headings = list(HEADING_PATTERN.finditer(markdown))

    for block_match in CODE_BLOCK_PATTERN.finditer(markdown):
        content = block_match.group("content") or ""
        if "curl " not in content:
            continue
        normalized = content.replace("\\\n", " ").replace("\\\r\n", " ").strip()
        try:
            args = shlex.split(normalized)
        except ValueError:
            continue
        if not args or args[0] != "curl":
            continue

        method = "GET"
        url = ""
        headers: dict[str, Any] = {}
        body_type = "none"
        body: Any = {}
        i = 1
        while i < len(args):
            token = args[i]
            if token in {"-X", "--request"} and i + 1 < len(args):
                method = args[i + 1].upper()
                i += 2
                continue
            if token in {"-H", "--header"} and i + 1 < len(args):
                header_value = args[i + 1]
                if ":" in header_value:
                    key, value = header_value.split(":", 1)
                    headers[key.strip()] = value.strip()
                i += 2
                continue
            if token in {"-d", "--data", "--data-raw", "--data-binary"} and i + 1 < len(args):
                raw_body = args[i + 1]
                parsed = try_parse_json(raw_body)
                if parsed is not None:
                    body_type = "json"
                    body = parsed
                else:
                    body_type = "raw"
                    body = raw_body
                i += 2
                continue
            if token.startswith(("http://", "https://", "/")):
                url = token
            i += 1

        if not url:
            continue

        heading = nearest_heading(block_match.start(), headings)
        requests.append(
            ParsedRequestData(
                name=heading or f"{method} {url}",
                method=method,
                url=url,
                headers=headers,
                body_type=body_type,
                body=body,
                assertions=[{"type": "status_code", "expected": 200}],
                collection_name=heading,
            )
        )

    return requests


def nearest_heading(position: int, headings: list[re.Match[str]]) -> str | None:
    current = None
    for heading in headings:
        if heading.start() >= position:
            break
        current = heading.group("title").strip()
    return current


def find_next_json_block(position: int, code_blocks: list[re.Match[str]]) -> str | None:
    for block in code_blocks:
        if block.start() < position:
            continue
        language = (block.group("lang") or "").lower()
        content = block.group("content") or ""
        if language in {"json", "javascript", "js"}:
            return content
        if try_parse_json(content) is not None:
            return content
        return None
    return None


def try_parse_json(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except Exception:  # noqa: BLE001
        return None


def extract_parameter_example(parameter: dict[str, Any]) -> Any:
    if "example" in parameter:
        return parameter.get("example")
    schema = parameter.get("schema") or {}
    if "example" in schema:
        return schema.get("example")
    if "default" in schema:
        return schema.get("default")
    enum_values = schema.get("enum") or []
    if enum_values:
        return enum_values[0]
    return ""


def parse_request_body(request_body: dict[str, Any]) -> tuple[str, Any]:
    content = request_body.get("content") or {}
    if "application/json" in content:
        return "json", extract_content_example(content["application/json"])
    if "application/x-www-form-urlencoded" in content:
        return "form", extract_content_example(content["application/x-www-form-urlencoded"])
    if "multipart/form-data" in content:
        return "form", extract_content_example(content["multipart/form-data"])
    if "text/plain" in content:
        example = extract_content_example(content["text/plain"])
        return "raw", example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
    return "none", {}


def extract_content_example(content_item: dict[str, Any]) -> Any:
    if "example" in content_item:
        return content_item["example"]
    examples = content_item.get("examples") or {}
    if isinstance(examples, dict) and examples:
        first_example = next(iter(examples.values()))
        if isinstance(first_example, dict) and "value" in first_example:
            return first_example["value"]
        return first_example
    schema = content_item.get("schema") or {}
    return build_example_from_schema(schema)


def build_example_from_schema(schema: dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return {}
    if "example" in schema:
        return schema["example"]
    schema_type = schema.get("type")
    if schema_type == "object":
        return {key: build_example_from_schema(value) for key, value in (schema.get("properties") or {}).items()}
    if schema_type == "array":
        return [build_example_from_schema(schema.get("items") or {})]
    if schema_type == "integer":
        return schema.get("default", 0)
    if schema_type == "number":
        return schema.get("default", 0)
    if schema_type == "boolean":
        return schema.get("default", False)
    return schema.get("default", "")


def extract_success_status(responses: dict[str, Any]) -> int:
    for key in responses.keys():
        if str(key).startswith("2"):
            try:
                return int(str(key))
            except ValueError:
                continue
    return 200


def normalize_request_url(base_url: str, path: str) -> str:
    if not base_url:
        return path if path.startswith("/") else f"/{path}"
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def guess_collection_name_from_path(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    return segments[0] if segments else None
