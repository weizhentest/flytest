from __future__ import annotations

from collections.abc import Callable
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .ai_parser import enhance_import_result_with_ai
from .document_import import (
    DocumentImportResult,
    MARKER_EXTENSIONS,
    ParsedRequestData,
    import_requests_from_document,
    load_document_content_for_ai,
)
from .generation import generate_script_and_test_case
from .models import ApiCollection, ApiEnvironment, ApiRequest, ApiTestCase
from .serializers import ApiRequestSerializer, ApiTestCaseSerializer

ProgressCallback = Callable[[int, str, str], None] | None
CancelCallback = Callable[[], bool] | None

ABSOLUTE_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.I)
LABELLED_URL_PATTERN = re.compile(r"^(?P<label>[^:：]{1,24})\s*[:：]\s*(?P<url>https?://[^\s\"'<>]+)", re.I)
FULL_BASE_URL_LABEL_PATTERN = re.compile(
    r"(?:base[_\s-]?url|server(?:\s+url)?|server\s+address|api\s+server|api\s+domain|"
    r"\u57fa\u7840\u5730\u5740|\u73af\u5883\u5730\u5740|\u670d\u52a1\u5730\u5740|\u670d\u52a1\u5668\u5730\u5740|\u670d\u52a1\u5730\u5740)"
    r"\s*[:：]\s*(https?://[^\s\"'<>]+)",
    re.I,
)
HOST_LABEL_PATTERN = re.compile(
    r"(?:host|domain|server|server\s+host|server\s+address|"
    r"\u670d\u52a1\u5668|\u57df\u540d|\u4e3b\u673a)"
    r"\s*[:：]\s*([A-Za-z0-9.-]+(?::\d+)?)",
    re.I,
)
SCHEME_LABEL_PATTERN = re.compile(
    r"(?:scheme|protocol|schema|\u534f\u8bae|\u8bf7\u6c42\u534f\u8bae)"
    r"\s*[:：]\s*(https?)",
    re.I,
)
BASE_PATH_LABEL_PATTERN = re.compile(
    r"(?:base[_\s-]?path|context[_\s-]?path|root[_\s-]?path|api[_\s-]?prefix|"
    r"\u57fa\u7840\u8def\u5f84|\u63a5\u53e3\u524d\u7f00|\u57fa\u7840\u524d\u7f00|\u8def\u5f84\u524d\u7f00)"
    r"\s*[:：]\s*(/[^\s\"'<>]*)",
    re.I,
)
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")

ENVIRONMENT_LABEL_MAP = {
    "production": "生产环境",
    "prod": "生产环境",
    "live": "生产环境",
    "正式": "生产环境",
    "生产": "生产环境",
    "线上": "生产环境",
    "test": "测试环境",
    "qa": "测试环境",
    "测试": "测试环境",
    "uat": "预发环境",
    "staging": "预发环境",
    "预发": "预发环境",
    "sandbox": "预发环境",
    "dev": "开发环境",
    "开发": "开发环境",
    "local": "本地环境",
    "本地": "本地环境",
}

ENVIRONMENT_PRIORITY = {
    "测试环境": 0,
    "预发环境": 1,
    "生产环境": 2,
    "开发环境": 3,
    "本地环境": 4,
}


def _report(progress_callback: ProgressCallback, percent: int, stage: str, message: str):
    if progress_callback:
        progress_callback(percent, stage, message)


def _ensure_not_cancelled(cancel_callback: CancelCallback):
    if cancel_callback and cancel_callback():
        raise ValueError("文档解析已手动停止")


def _normalize_request_key(method: str, url: str) -> tuple[str, str]:
    return method.upper().strip(), url.strip()


def _find_existing_request(project_id: int, parsed: ParsedRequestData) -> ApiRequest | None:
    method, url = _normalize_request_key(parsed.method, parsed.url)
    return (
        ApiRequest.objects.filter(collection__project_id=project_id, method=method, url=url)
        .select_related("collection")
        .order_by("id")
        .first()
    )


def _update_request_if_needed(request: ApiRequest, parsed: ParsedRequestData):
    changed = False
    if not request.description and parsed.description:
        request.description = parsed.description[:5000]
        changed = True
    if not request.headers and parsed.headers:
        request.headers = parsed.headers
        changed = True
    if not request.params and parsed.params:
        request.params = parsed.params
        changed = True
    if request.body_type == "none" and parsed.body_type != "none":
        request.body_type = parsed.body_type
        request.body = parsed.body
        changed = True
    if not request.assertions and parsed.assertions:
        request.assertions = parsed.assertions
        changed = True
    if changed:
        request.save(update_fields=["description", "headers", "params", "body_type", "body", "assertions", "updated_at"])


def _create_imported_requests(
    root_collection: ApiCollection,
    user,
    parsed_requests: list[ParsedRequestData],
) -> list[ApiRequest]:
    created_or_reused_requests: list[ApiRequest] = []
    child_collections: dict[str, ApiCollection] = {}

    for parsed in parsed_requests:
        existing_request = _find_existing_request(root_collection.project_id, parsed)
        if existing_request:
            _update_request_if_needed(existing_request, parsed)
            created_or_reused_requests.append(existing_request)
            continue

        target_collection = root_collection
        if parsed.collection_name and parsed.collection_name.strip():
            normalized_name = parsed.collection_name.strip()[:100]
            if normalized_name and normalized_name != root_collection.name:
                if normalized_name not in child_collections:
                    child_collection, _ = ApiCollection.objects.get_or_create(
                        project=root_collection.project,
                        parent=root_collection,
                        name=normalized_name,
                        defaults={
                            "creator": user,
                            "order": 0,
                        },
                    )
                    child_collections[normalized_name] = child_collection
                target_collection = child_collections[normalized_name]

        created_or_reused_requests.append(
            ApiRequest.objects.create(
                collection=target_collection,
                name=parsed.name[:120],
                description=parsed.description[:5000],
                method=parsed.method,
                url=parsed.url,
                headers=parsed.headers,
                params=parsed.params,
                body_type=parsed.body_type,
                body=parsed.body,
                assertions=parsed.assertions,
                timeout_ms=30000,
                order=0,
                created_by=user,
            )
        )

    return created_or_reused_requests


def _create_generated_test_cases(
    project,
    user,
    created_requests: list[ApiRequest],
    parsed_requests: list[ParsedRequestData],
    *,
    enabled: bool,
) -> list[ApiTestCase]:
    if not enabled:
        return []

    generated_cases: list[ApiTestCase] = []
    for request, parsed in zip(created_requests, parsed_requests, strict=False):
        _, testcase_payload = generate_script_and_test_case(parsed, request.id)
        generated_cases.append(
            ApiTestCase.objects.create(
                project=project,
                request=request,
                name=testcase_payload["name"][:160],
                description=testcase_payload["description"],
                status=testcase_payload["status"],
                tags=testcase_payload["tags"],
                script=testcase_payload["script"],
                assertions=testcase_payload["assertions"],
                creator=user,
            )
        )
    return generated_cases


def _load_structured_document(file_path: str) -> dict | None:
    suffix = Path(file_path).suffix.lower()
    try:
        if suffix == ".json":
            return json.loads(Path(file_path).read_text(encoding="utf-8", errors="ignore"))
        if suffix in {".yaml", ".yml"}:
            return yaml.safe_load(Path(file_path).read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    return None


def _extract_structured_environment_urls(file_path: str) -> list[tuple[str, str]]:
    data = _load_structured_document(file_path)
    if not isinstance(data, dict):
        return []

    environments: list[tuple[str, str]] = []

    servers = data.get("servers") or []
    for index, server in enumerate(servers):
        if isinstance(server, dict):
            url = str(server.get("url") or "").strip().rstrip("/")
            if not url:
                continue
            description = str(server.get("description") or server.get("name") or "").strip()
            environments.append((description or f"环境{index + 1}", url))

    if environments:
        return environments

    if "swagger" in data and "host" in data:
        schemes = data.get("schemes") or ["http"]
        scheme = str(schemes[0]).strip() if schemes else "http"
        host = str(data.get("host") or "").strip()
        base_path = str(data.get("basePath") or "").strip()
        if host:
            if base_path and not base_path.startswith("/"):
                base_path = f"/{base_path}"
            environments.append(("默认环境", f"{scheme}://{host}{base_path}".rstrip("/")))

    return environments


def _normalize_environment_name(label: str, index: int) -> str:
    normalized_label = label.strip()
    lowered = normalized_label.lower()
    for keyword, env_name in ENVIRONMENT_LABEL_MAP.items():
        if keyword in lowered or keyword in normalized_label:
            return env_name
    return normalized_label or f"环境{index + 1}"


def _extract_text_environment_urls(document_content: str) -> list[tuple[str, str]]:
    environments: list[tuple[str, str]] = []
    for raw_line in document_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matched = LABELLED_URL_PATTERN.match(line)
        if not matched:
            continue
        label = matched.group("label").strip()
        url = matched.group("url").strip().rstrip("/")
        if not url:
            continue
        environments.append((label, url))
    return environments


def _extract_fallback_base_url(document_content: str, parsed_requests: list[ParsedRequestData], file_path: str) -> str:
    explicit_full = FULL_BASE_URL_LABEL_PATTERN.search(document_content)
    explicit_base_path_match = BASE_PATH_LABEL_PATTERN.search(document_content)
    explicit_base_path = explicit_base_path_match.group(1).strip() if explicit_base_path_match else ""
    if explicit_base_path and not explicit_base_path.startswith("/"):
        explicit_base_path = f"/{explicit_base_path}"

    if explicit_full:
        explicit_url = explicit_full.group(1).rstrip("/")
        parsed_explicit = urlparse(explicit_url)
        if explicit_base_path and parsed_explicit.scheme and parsed_explicit.netloc and parsed_explicit.path in {"", "/"}:
            return f"{parsed_explicit.scheme}://{parsed_explicit.netloc}{explicit_base_path}".rstrip("/")
        return explicit_url

    host_match = HOST_LABEL_PATTERN.search(document_content)
    if host_match:
        scheme_match = SCHEME_LABEL_PATTERN.search(document_content)
        scheme = scheme_match.group(1).lower() if scheme_match else "http"
        return f"{scheme}://{host_match.group(1)}{explicit_base_path}".rstrip("/")

    structured_envs = _extract_structured_environment_urls(file_path)
    if structured_envs:
        return structured_envs[0][1]

    absolute_urls = [urlparse(item.url) for item in parsed_requests if urlparse(item.url).scheme and urlparse(item.url).netloc]
    if not absolute_urls:
        return ""

    first = absolute_urls[0]
    if not all(item.scheme == first.scheme and item.netloc == first.netloc for item in absolute_urls[1:]):
        return ""

    if len(absolute_urls) == 1:
        return f"{first.scheme}://{first.netloc}"

    segment_lists = [[segment for segment in item.path.split("/") if segment] for item in absolute_urls]
    common_segments: list[str] = []
    for segment_group in zip(*segment_lists):
        if len(set(segment_group)) != 1:
            break
        common_segments.append(segment_group[0])
    common_path = f"/{'/'.join(common_segments)}" if common_segments else ""
    return f"{first.scheme}://{first.netloc}{common_path}".rstrip("/")


def _build_environment_name(base_name: str, collection: ApiCollection) -> str:
    normalized = (base_name or "").strip()
    if not normalized:
        normalized = f"{collection.name}-环境"
    return normalized[:100]


def _build_unique_environment_name(project, base_name: str, exclude_id: int | None = None) -> str:
    candidate_name = base_name
    suffix = 2
    queryset = ApiEnvironment.objects.filter(project=project)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    while queryset.filter(name=candidate_name).exists():
        candidate_name = f"{base_name[:94]}-{suffix}"
        suffix += 1
    return candidate_name


def _collect_common_headers(parsed_requests: list[ParsedRequestData]) -> dict[str, str]:
    common_headers: dict[str, str] = {}
    if parsed_requests:
        first_headers = parsed_requests[0].headers or {}
        for key, value in first_headers.items():
            if all((item.headers or {}).get(key) == value for item in parsed_requests[1:]):
                common_headers[key] = value
    return common_headers


def _collect_variables(document_content: str, parsed_requests: list[ParsedRequestData]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for item in parsed_requests:
        for candidate in [item.url, *(item.headers or {}).values(), *(item.params or {}).values()]:
            if isinstance(candidate, str):
                for match in PLACEHOLDER_PATTERN.finditer(candidate):
                    key = match.group(1)
                    if key != "base_url":
                        variables.setdefault(key, "")

    if "token" in document_content.lower() and "token" not in variables:
        variables["token"] = ""

    return variables


def _build_environment_drafts(file_path: str, parsed_requests: list[ParsedRequestData]) -> list[dict]:
    document_content, _, _ = load_document_content_for_ai(file_path)
    common_headers = _collect_common_headers(parsed_requests)
    variables = _collect_variables(document_content, parsed_requests)

    draft_candidates: list[dict] = []
    seen_urls: set[str] = set()

    for index, (label, base_url) in enumerate(_extract_text_environment_urls(document_content) or _extract_structured_environment_urls(file_path)):
        if not base_url or base_url in seen_urls:
            continue
        seen_urls.add(base_url)
        draft_candidates.append(
            {
                "name": _normalize_environment_name(label, index),
                "base_url": base_url,
                "common_headers": common_headers,
                "variables": dict(variables),
                "timeout_ms": 30000,
                "is_default": False,
            }
        )

    if not draft_candidates:
        fallback_url = _extract_fallback_base_url(document_content, parsed_requests, file_path)
        if fallback_url or common_headers or variables:
            draft_candidates.append(
                {
                    "name": "文档解析环境草稿",
                    "base_url": fallback_url,
                    "common_headers": common_headers,
                    "variables": variables,
                    "timeout_ms": 30000,
                    "is_default": False,
                }
            )

    draft_candidates.sort(key=lambda item: ENVIRONMENT_PRIORITY.get(item["name"], 99))
    return draft_candidates


def _create_or_reuse_environments(collection: ApiCollection, user, environment_drafts: list[dict]) -> list[ApiEnvironment]:
    saved_environments: list[ApiEnvironment] = []

    for index, environment_draft in enumerate(environment_drafts):
        base_url = str(environment_draft.get("base_url") or "").strip()
        common_headers = environment_draft.get("common_headers") or {}
        variables = environment_draft.get("variables") or {}
        timeout_ms = int(environment_draft.get("timeout_ms") or 30000)
        draft_name = str(environment_draft.get("name") or f"环境{index + 1}").strip()

        if not base_url and not common_headers and not variables:
            continue

        if base_url:
            existing = ApiEnvironment.objects.filter(project=collection.project, base_url=base_url).first()
            if existing:
                updated = False
                merged_headers = dict(common_headers)
                merged_headers.update(existing.common_headers or {})
                merged_variables = dict(variables)
                merged_variables.update(existing.variables or {})
                if merged_headers != (existing.common_headers or {}):
                    existing.common_headers = merged_headers
                    updated = True
                if merged_variables != (existing.variables or {}):
                    existing.variables = merged_variables
                    updated = True
                desired_base_name = _build_environment_name(draft_name, collection)
                desired_name = _build_unique_environment_name(collection.project, desired_base_name, exclude_id=existing.id)
                if existing.name != desired_name and existing.name.startswith("自动解析环境-"):
                    existing.name = desired_name
                    updated = True
                if updated:
                    existing.save(update_fields=["name", "common_headers", "variables", "updated_at"])
                saved_environments.append(existing)
                continue

        base_name = _build_environment_name(draft_name, collection)
        candidate_name = _build_unique_environment_name(collection.project, base_name)

        saved_environments.append(
            ApiEnvironment.objects.create(
                project=collection.project,
                name=candidate_name,
                base_url=base_url,
                common_headers=common_headers,
                variables=variables,
                timeout_ms=timeout_ms,
                is_default=False,
                creator=user,
            )
        )

    return saved_environments


def process_document_import(
    *,
    collection: ApiCollection,
    user,
    file_path: str,
    generate_test_cases: bool,
    enable_ai_parse: bool,
    progress_callback: ProgressCallback = None,
    cancel_callback: CancelCallback = None,
) -> dict:
    _ensure_not_cancelled(cancel_callback)
    suffix = Path(file_path).suffix.lower()
    ai_result = None
    parsed_requests: list[ParsedRequestData] = []

    if enable_ai_parse and suffix in MARKER_EXTENSIONS:
        _report(progress_callback, 12, "ai_parse", "检测到 PDF/图片类文档，优先使用 AI 解析接口定义。")
        ai_result = enhance_import_result_with_ai(
            file_path=file_path,
            user=user,
            source_type="ai_direct_document",
            base_requests=[],
            cancel_callback=cancel_callback,
        )
        if ai_result.requests:
            import_result = DocumentImportResult(
                source_type="ai_direct_document",
                requests=ai_result.requests,
                marker_used=True,
                note="PDF/图片类文档已优先使用 AI 解析接口定义。",
            )
            parsed_requests = ai_result.requests
        else:
            _ensure_not_cancelled(cancel_callback)
            _report(progress_callback, 24, "rule_parse", "AI 未识别到接口，回退到规则解析继续尝试。")
            import_result = import_requests_from_document(file_path)
            parsed_requests = import_result.requests
    else:
        _report(progress_callback, 12, "rule_parse", "正在抽取文档正文并进行规则解析。")
        try:
            _ensure_not_cancelled(cancel_callback)
            import_result = import_requests_from_document(file_path)
            parsed_requests = import_result.requests
        except ValueError as exc:
            if not enable_ai_parse:
                raise

            import_result = DocumentImportResult(
                source_type="ai_fallback",
                requests=[],
                marker_used=False,
                note=f"规则解析未识别到接口，已切换为 AI 解析。原因: {exc}",
            )
            _report(progress_callback, 48, "ai_parse", "规则解析未命中，正在切换到 AI 增强解析。")
            ai_result = enhance_import_result_with_ai(
                file_path=file_path,
                user=user,
                source_type=import_result.source_type,
                base_requests=[],
                cancel_callback=cancel_callback,
            )
            if ai_result.requests:
                parsed_requests = ai_result.requests
            else:
                raise ValueError(ai_result.note or str(exc))
        else:
            if enable_ai_parse:
                _ensure_not_cancelled(cancel_callback)
                _report(progress_callback, 48, "ai_parse", "正在使用 AI 对规则解析结果做增强补全。")
                ai_result = enhance_import_result_with_ai(
                    file_path=file_path,
                    user=user,
                    source_type=import_result.source_type,
                    base_requests=import_result.requests,
                    cancel_callback=cancel_callback,
                )
                if ai_result.requests:
                    parsed_requests = ai_result.requests

    _ensure_not_cancelled(cancel_callback)
    if not parsed_requests:
        raise ValueError(
            ai_result.note
            if ai_result
            else "未能从接口文档中识别到接口，请优先上传 Swagger/OpenAPI/Postman 文件，"
            "或在文档中补充清晰的请求方式、路径、参数与 cURL 示例。"
        )

    _ensure_not_cancelled(cancel_callback)
    _report(progress_callback, 76, "save_requests", "正在保存解析得到的接口请求。")
    created_requests = _create_imported_requests(collection, user, parsed_requests)

    _ensure_not_cancelled(cancel_callback)
    _report(progress_callback, 88, "generate_cases", "正在生成接口脚本和测试用例。")
    created_test_cases = _create_generated_test_cases(
        collection.project,
        user,
        created_requests,
        parsed_requests,
        enabled=generate_test_cases,
    )

    environment_drafts = _build_environment_drafts(file_path, parsed_requests)
    saved_environments = _create_or_reuse_environments(collection, user, environment_drafts)
    primary_environment_draft = environment_drafts[0] if environment_drafts else None
    primary_environment = saved_environments[0] if saved_environments else None

    serializer = ApiRequestSerializer(created_requests, many=True)
    serialized_requests = serializer.data
    generated_scripts = [
        {
            "request_id": item["id"],
            "request_name": item["name"],
            "collection_name": item.get("collection_name"),
            "script": item["generated_script"],
        }
        for item in serialized_requests
    ]
    testcase_serializer = ApiTestCaseSerializer(created_test_cases, many=True)

    payload = {
        "created_count": len({request.id for request in created_requests}),
        "generated_script_count": len({item["request_id"] for item in generated_scripts}),
        "created_testcase_count": len(created_test_cases),
        "source_type": import_result.source_type,
        "marker_used": import_result.marker_used,
        "note": import_result.note,
        "ai_requested": enable_ai_parse,
        "ai_used": bool(ai_result and ai_result.used),
        "ai_note": ai_result.note if ai_result else "",
        "ai_prompt_source": ai_result.prompt_source if ai_result else None,
        "ai_prompt_name": ai_result.prompt_name if ai_result else None,
        "ai_model_name": ai_result.model_name if ai_result else None,
        "environment_draft": primary_environment_draft,
        "environment_items": [
            {
                "id": item.id,
                "name": item.name,
                "base_url": item.base_url,
                "is_default": item.is_default,
            }
            for item in saved_environments
        ],
        "environment_auto_saved": bool(saved_environments),
        "environment_auto_saved_count": len(saved_environments),
        "environment_id": primary_environment.id if primary_environment else None,
        "environment_name": primary_environment.name if primary_environment else None,
        "items": serialized_requests,
        "generated_scripts": generated_scripts,
        "test_cases": testcase_serializer.data,
    }
    _report(progress_callback, 100, "completed", "接口文档解析完成。")
    return payload
