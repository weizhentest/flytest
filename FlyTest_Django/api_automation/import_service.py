from __future__ import annotations

from collections.abc import Callable
import json
import queue
import re
import threading
from pathlib import Path
from urllib.parse import urlparse

import yaml
from django.conf import settings

from .ai_parser import enhance_import_result_with_ai
from .document_import import (
    DocumentImportResult,
    MARKER_EXTENSIONS,
    ParsedRequestData,
    import_requests_from_document,
    load_document_content_for_ai,
    named_items_from_mapping,
    parse_structured_document,
)
from .generation import generate_script_and_test_case
from .models import ApiCollection, ApiEnvironment, ApiRequest, ApiTestCase
from .serializers import ApiRequestSerializer, ApiTestCaseSerializer
from .specs import (
    apply_environment_spec_payload,
    apply_request_assertions_and_extractors,
    apply_request_spec_payload,
    backfill_request_specs_from_legacy,
    backfill_test_case_specs_from_legacy,
    serialize_environment_specs,
)
from langgraph_integration.models import get_user_active_llm_config

ProgressCallback = Callable[[int, str, str], None] | None
CancelCallback = Callable[[], bool] | None
DEFAULT_IMPORT_AI_STAGE_TIMEOUT_SECONDS = 90

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
SECRET_VARIABLE_KEYWORDS = (
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "access_key",
    "private_key",
    "refresh_token",
)

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


def _build_ai_feedback(*, enable_ai_parse: bool, ai_result) -> dict[str, str | None]:
    if not enable_ai_parse:
        return {
            "issue_code": "disabled",
            "user_message": "本次未启用 AI 增强解析。",
            "action_hint": None,
        }

    if ai_result and ai_result.used:
        return {
            "issue_code": "applied",
            "user_message": "AI 增强解析已生效，并用于补全接口定义。",
            "action_hint": None,
        }

    ai_note = str(getattr(ai_result, "note", "") or "").strip()
    ai_model_name = str(getattr(ai_result, "model_name", "") or "").strip()
    model_prefix = f"当前激活模型 {ai_model_name}" if ai_model_name else "当前激活模型"

    if "未返回可解析正文" in ai_note or "LLM returned empty content" in ai_note:
        return {
            "issue_code": "gateway_incompatible_empty_content",
            "user_message": f"{model_prefix} 调用成功但未返回可解析正文，已自动回退到规则解析。",
            "action_hint": "请在“系统设置 > AI大模型配置”中切换到能正常返回正文的模型或网关后再试。",
        }

    if "未检测到系统设置中的激活 LLM 配置" in ai_note:
        return {
            "issue_code": "llm_not_configured",
            "user_message": "系统未检测到激活的大模型配置，已自动回退到规则解析。",
            "action_hint": "请先到“系统设置 > AI大模型配置”中激活一套可用模型。",
        }

    if "AI 请求超时" in ai_note or "Request timed out" in ai_note or "APITimeoutError" in ai_note:
        return {
            "issue_code": "llm_timeout",
            "user_message": "AI 增强解析调用超时，已自动回退到规则解析。",
            "action_hint": "建议切换更快的模型、缩小文档规模，或稍后重试。",
        }

    if "未找到 API 自动化解析提示词" in ai_note:
        return {
            "issue_code": "prompt_missing",
            "user_message": "未找到 API 自动化解析提示词，已自动回退到规则解析。",
            "action_hint": "请到“提示词管理”中检查 API 自动化解析提示词是否存在。",
        }

    return {
        "issue_code": "fallback_rule_parse",
        "user_message": "AI 增强解析未生效，已自动回退到规则解析。",
        "action_hint": None,
    }


def _report(progress_callback: ProgressCallback, percent: int, stage: str, message: str):
    if progress_callback:
        progress_callback(percent, stage, message)


def _ensure_not_cancelled(cancel_callback: CancelCallback):
    if cancel_callback and cancel_callback():
        raise ValueError("文档解析已手动停止")


def _get_import_ai_stage_timeout_seconds(user) -> int:
    configured = DEFAULT_IMPORT_AI_STAGE_TIMEOUT_SECONDS
    active_config = get_user_active_llm_config(user)
    if active_config and getattr(active_config, "request_timeout", None):
        configured = min(max(int(active_config.request_timeout), 30), 180)
    env_value = getattr(settings, "API_AUTOMATION_IMPORT_AI_STAGE_TIMEOUT_SECONDS", None)
    if isinstance(env_value, int) and env_value > 0:
        configured = min(max(env_value, 15), 300)
    return configured


def _run_ai_enhancement_with_timeout(
    *,
    user,
    file_path: str,
    source_type: str,
    base_requests: list[ParsedRequestData],
    cancel_callback: CancelCallback = None,
):
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _target():
        try:
            result_queue.put(
                ("result", enhance_import_result_with_ai(
                    file_path=file_path,
                    user=user,
                    source_type=source_type,
                    base_requests=base_requests,
                    cancel_callback=cancel_callback,
                ))
            )
        except Exception as exc:  # noqa: BLE001
            result_queue.put(("error", exc))

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout=_get_import_ai_stage_timeout_seconds(user))

    if worker.is_alive():
        active_config = get_user_active_llm_config(user)
        model_name = getattr(active_config, "name", None) if active_config else None
        from api_automation.ai_parser import AIEnhancementResult

        return AIEnhancementResult(
            requested=True,
            used=False,
            note="AI 请求超时，已自动回退到规则解析结果。",
            prompt_source=None,
            prompt_name=None,
            model_name=model_name,
            requests=base_requests,
        )

    outcome, payload = result_queue.get()
    if outcome == "error":
        raise payload
    return payload


def _build_ai_feedback(*, ai_requested: bool, ai_result) -> dict[str, str | None]:
    if not ai_requested:
        return {
            "issue_code": "not_requested",
            "user_message": "本次未执行 AI 文档解析。",
            "action_hint": None,
        }

    if ai_result and ai_result.used:
        return {
            "issue_code": "applied",
            "user_message": "AI 文档解析已生效，并用于生成接口定义。",
            "action_hint": None,
        }

    ai_note = str(getattr(ai_result, "note", "") or "").strip()
    ai_model_name = str(getattr(ai_result, "model_name", "") or "").strip()
    model_prefix = f"当前激活模型 {ai_model_name}" if ai_model_name else "当前激活模型"

    if "未返回可解析正文" in ai_note or "LLM returned empty content" in ai_note:
        return {
            "issue_code": "gateway_incompatible_empty_content",
            "user_message": f"{model_prefix} 调用成功但未返回可解析正文，本次 AI 文档解析未完成。",
            "action_hint": "请在“系统设置 > AI大模型配置”中切换到能正常返回正文的模型或网关后再试。",
        }

    if "未检测到系统设置中的激活 LLM 配置" in ai_note:
        return {
            "issue_code": "llm_not_configured",
            "user_message": "系统未检测到激活的大模型配置，无法执行 AI 文档解析。",
            "action_hint": "请先到“系统设置 > AI大模型配置”中激活一套可用模型。",
        }

    if "AI 请求超时" in ai_note or "Request timed out" in ai_note or "APITimeoutError" in ai_note:
        return {
            "issue_code": "llm_timeout",
            "user_message": "AI 文档解析调用超时，本次导入未完成。",
            "action_hint": "建议切换更快的模型、缩小文档规模，或稍后重试。",
        }

    if "未找到 API 自动化解析提示词" in ai_note:
        return {
            "issue_code": "prompt_missing",
            "user_message": "未找到 API 自动化解析提示词，无法执行 AI 文档解析。",
            "action_hint": "请到“提示词管理”中检查 API 自动化解析提示词是否存在。",
        }

    return {
        "issue_code": "ai_parse_failed",
        "user_message": "AI 文档解析未成功完成。",
        "action_hint": None,
    }


def _get_import_ai_stage_timeout_seconds(user, file_path: str | None = None) -> int:
    configured = DEFAULT_IMPORT_AI_STAGE_TIMEOUT_SECONDS
    active_config = get_user_active_llm_config(user)
    if active_config and getattr(active_config, "request_timeout", None):
        configured = min(max(int(active_config.request_timeout) * 2, 180), 900)
    env_value = getattr(settings, "API_AUTOMATION_IMPORT_AI_STAGE_TIMEOUT_SECONDS", None)
    if isinstance(env_value, int) and env_value > 0:
        configured = min(max(env_value, 15), 900)

    if file_path:
        try:
            document_content, _, _ = load_document_content_for_ai(file_path)
            chunk_hint = max(1, len(document_content) // 1800)
            configured = min(max(configured, 120 + chunk_hint * 45), 900)
        except Exception:
            pass

    return configured


def _run_ai_enhancement_with_timeout(
    *,
    user,
    file_path: str,
    source_type: str,
    base_requests: list[ParsedRequestData],
    cancel_callback: CancelCallback = None,
):
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _target():
        try:
            result_queue.put(
                ("result", enhance_import_result_with_ai(
                    file_path=file_path,
                    user=user,
                    source_type=source_type,
                    base_requests=base_requests,
                    cancel_callback=cancel_callback,
                ))
            )
        except Exception as exc:  # noqa: BLE001
            result_queue.put(("error", exc))

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout=_get_import_ai_stage_timeout_seconds(user, file_path))

    if worker.is_alive():
        active_config = get_user_active_llm_config(user)
        model_name = getattr(active_config, "name", None) if active_config else None
        from api_automation.ai_parser import AIEnhancementResult

        return AIEnhancementResult(
            requested=True,
            used=False,
            note="AI 请求超时，文档 AI 解析未完成。",
            prompt_source=None,
            prompt_name=None,
            model_name=model_name,
            requests=base_requests,
        )

    outcome, payload = result_queue.get()
    if outcome == "error":
        raise payload
    return payload


def _process_document_import_ai_only(
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
    ai_requested = False

    structured_result = None
    if suffix in {".json", ".yaml", ".yml"}:
        structured_result = parse_structured_document(file_path)

    if structured_result is not None:
        _report(progress_callback, 18, "structured_parse", "已识别为结构化接口文档，正在直接导入接口定义。")
        import_result = structured_result
        parsed_requests = import_result.requests
    else:
        if not enable_ai_parse:
            raise ValueError("当前接口文档导入已改为 AI 解析模式，请开启 AI 解析后重试。")

        ai_requested = True
        _report(progress_callback, 12, "ai_prepare", "正在抽取文档正文并切分 AI 解析片段。")
        _report(progress_callback, 40, "ai_parse", "正在使用 AI 解析接口文档正文。")
        ai_result = _run_ai_enhancement_with_timeout(
            user=user,
            file_path=file_path,
            source_type="ai_document",
            base_requests=[],
            cancel_callback=cancel_callback,
        )
        if not ai_result.used or not ai_result.requests:
            raise ValueError(
                ai_result.note
                or "AI 未从接口文档中识别到可落库的接口，请补充清晰的请求方式、路径、参数和示例后重试。"
            )

        parsed_requests = ai_result.requests
        import_result = DocumentImportResult(
            source_type="ai_document",
            requests=parsed_requests,
            marker_used=suffix in MARKER_EXTENSIONS,
            note=ai_result.note or "已完成 AI 文档解析。",
        )

    _ensure_not_cancelled(cancel_callback)
    if not parsed_requests:
        raise ValueError("未能从接口文档中识别到接口，请补充清晰的请求方式、路径、参数与示例后重试。")

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
    environment_suggestions = _build_environment_suggestions(
        parsed_requests=parsed_requests,
        created_requests=created_requests,
        environment_drafts=environment_drafts,
        saved_environments=saved_environments,
        primary_environment_draft=primary_environment_draft,
        primary_environment=primary_environment,
    )

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
    ai_feedback = _build_ai_feedback(ai_requested=ai_requested, ai_result=ai_result)

    payload = {
        "created_count": len({request.id for request in created_requests}),
        "generated_script_count": len({item["request_id"] for item in generated_scripts}),
        "created_testcase_count": len(created_test_cases),
        "source_type": import_result.source_type,
        "marker_used": import_result.marker_used,
        "note": import_result.note,
        "ai_requested": ai_requested,
        "ai_used": bool(ai_result and ai_result.used),
        "ai_note": ai_result.note if ai_result else "",
        "ai_prompt_source": ai_result.prompt_source if ai_result else None,
        "ai_prompt_name": ai_result.prompt_name if ai_result else None,
        "ai_model_name": ai_result.model_name if ai_result else None,
        "ai_cache_hit": ai_result.cache_hit if ai_result else False,
        "ai_cache_key": ai_result.cache_key if ai_result else None,
        "ai_duration_ms": ai_result.duration_ms if ai_result else None,
        "ai_lock_wait_ms": ai_result.lock_wait_ms if ai_result else None,
        "ai_issue_code": ai_feedback["issue_code"],
        "ai_user_message": ai_feedback["user_message"],
        "ai_action_hint": ai_feedback["action_hint"],
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
        "environment_suggestions": environment_suggestions,
        "items": serialized_requests,
        "generated_scripts": generated_scripts,
        "test_cases": testcase_serializer.data,
    }
    _report(progress_callback, 100, "completed", "接口文档解析完成。")
    return payload


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
    if parsed.request_spec:
        apply_request_spec_payload(request, parsed.request_spec)
        apply_request_assertions_and_extractors(
            request,
            assertion_payload=parsed.assertion_specs or None,
            extractor_payload=parsed.extractor_specs or None,
        )


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
            if not getattr(existing_request, "request_spec", None):
                backfill_request_specs_from_legacy(existing_request)
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
        if parsed.request_spec:
            apply_request_spec_payload(created_or_reused_requests[-1], parsed.request_spec)
            apply_request_assertions_and_extractors(
                created_or_reused_requests[-1],
                assertion_payload=parsed.assertion_specs or None,
                extractor_payload=parsed.extractor_specs or None,
            )
        else:
            backfill_request_specs_from_legacy(created_or_reused_requests[-1])

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
        backfill_test_case_specs_from_legacy(generated_cases[-1])
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


def _collect_placeholders_from_value(value: Any, found: set[str]):
    if isinstance(value, str):
        for match in PLACEHOLDER_PATTERN.finditer(value):
            found.add(match.group(1))
        return
    if isinstance(value, list):
        for item in value:
            _collect_placeholders_from_value(item, found)
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_placeholders_from_value(item, found)


def _classify_variable_category(name: str) -> str:
    lowered = name.lower()
    if any(keyword in lowered for keyword in SECRET_VARIABLE_KEYWORDS) or any(
        keyword in lowered for keyword in ("auth", "login", "phone", "username", "account", "session", "cookie")
    ):
        return "auth"
    return "business"


def _build_variable_suggestions(parsed_requests: list[ParsedRequestData]) -> list[dict]:
    usage: dict[str, dict] = {}
    for request in parsed_requests:
        placeholders: set[str] = set()
        for value in (
            request.url,
            request.headers,
            request.params,
            request.body,
            request.request_spec or {},
            request.assertion_specs or [],
            request.extractor_specs or [],
        ):
            _collect_placeholders_from_value(value, placeholders)

        for name in sorted(placeholders):
            if name == "base_url":
                continue
            entry = usage.setdefault(
                name,
                {
                    "name": name,
                    "request_count": 0,
                    "category": _classify_variable_category(name),
                    "is_secret": any(keyword in name.lower() for keyword in SECRET_VARIABLE_KEYWORDS),
                    "example_requests": [],
                    "suggested_value": "",
                },
            )
            entry["request_count"] += 1
            if len(entry["example_requests"]) < 3 and request.name not in entry["example_requests"]:
                entry["example_requests"].append(request.name)

    return sorted(
        usage.values(),
        key=lambda item: (
            0 if item["category"] == "auth" else 1,
            -int(item["request_count"]),
            item["name"],
        ),
    )


def _score_auth_candidate(parsed_request: ParsedRequestData) -> tuple[int, str]:
    combined = f"{parsed_request.name} {parsed_request.url}".lower()
    score = 0
    reasons: list[str] = []
    if parsed_request.method.upper() == "POST":
        score += 20
        reasons.append("POST 请求")
    if any(keyword in combined for keyword in ("login", "signin", "auth", "token", "session", "oauth")):
        score += 35
        reasons.append("名称或路径包含鉴权关键词")
    if any(keyword in parsed_request.name for keyword in ("登录", "鉴权", "认证", "令牌")):
        score += 35
        reasons.append("接口名称疑似登录/鉴权接口")
    return score, "，".join(reasons)


def _resolve_token_variable_name(variable_suggestions: list[dict]) -> str:
    priorities = ["token", "access_token", "authorization", "refresh_token", "refreshToken"]
    existing_names = {str(item.get("name") or "") for item in variable_suggestions}
    for name in priorities:
        if name in existing_names:
            return name
    return "token"


def _build_auth_suggestions(
    parsed_requests: list[ParsedRequestData],
    created_requests: list[ApiRequest],
    variable_suggestions: list[dict],
) -> list[dict]:
    token_variable = _resolve_token_variable_name(variable_suggestions)
    suggestions: list[dict] = []
    for parsed_request, created_request in zip(parsed_requests, created_requests, strict=False):
        score, reason = _score_auth_candidate(parsed_request)
        if score < 35:
            continue
        confidence = "high" if score >= 70 else "medium"
        suggestions.append(
            {
                "request_id": created_request.id,
                "request_name": created_request.name,
                "collection_name": created_request.collection.name,
                "method": created_request.method,
                "url": created_request.url,
                "token_variable": token_variable,
                "token_path": "data.token",
                "token_path_candidates": [
                    "data.token",
                    "data.accessToken",
                    "data.access_token",
                    "token",
                    "accessToken",
                    "authorization",
                ],
                "confidence": confidence,
                "reason": reason or "接口特征与常见登录/鉴权接口相符",
            }
        )
    suggestions.sort(
        key=lambda item: (
            0 if item["confidence"] == "high" else 1,
            item["request_name"],
        )
    )
    return suggestions[:3]


def _build_environment_patch(
    variable_suggestions: list[dict],
    auth_suggestions: list[dict],
    primary_environment_draft: dict | None,
) -> dict:
    suggested_variables: list[dict] = []
    seen_names: set[str] = set()

    def add_variable(name: str, value: str, *, is_secret: bool = False, reason: str = ""):
        if not name or name in seen_names:
            return
        seen_names.add(name)
        suggested_variables.append(
            {
                "name": name,
                "value": value,
                "is_secret": is_secret,
                "reason": reason,
            }
        )

    if auth_suggestions:
        primary_auth = auth_suggestions[0]
        add_variable(
            "auth_request_id",
            str(primary_auth.get("request_id") or ""),
            reason="推荐作为自动获取 token 的登录接口 ID",
        )
        add_variable(
            "auth_request_name",
            str(primary_auth.get("request_name") or ""),
            reason="推荐作为自动获取 token 的登录接口名称",
        )
        add_variable(
            "auth_token_path",
            str(primary_auth.get("token_path") or "data.token"),
            reason="推荐的 token 提取路径",
        )

    for item in variable_suggestions:
        add_variable(
            str(item.get("name") or ""),
            str(item.get("suggested_value") or ""),
            is_secret=bool(item.get("is_secret")),
            reason=f"在 {item.get('request_count') or 0} 个接口中被引用",
        )

    return {
        "base_url": str((primary_environment_draft or {}).get("base_url") or ""),
        "variables": suggested_variables,
    }


def _build_environment_suggestions(
    *,
    parsed_requests: list[ParsedRequestData],
    created_requests: list[ApiRequest],
    environment_drafts: list[dict],
    saved_environments: list[ApiEnvironment],
    primary_environment_draft: dict | None,
    primary_environment: ApiEnvironment | None,
) -> dict:
    variable_suggestions = _build_variable_suggestions(parsed_requests)
    auth_suggestions = _build_auth_suggestions(parsed_requests, created_requests, variable_suggestions)

    base_url_candidates: list[dict] = []
    for index, environment_draft in enumerate(environment_drafts):
        saved_environment = saved_environments[index] if index < len(saved_environments) else None
        base_url = str(environment_draft.get("base_url") or "").strip()
        if not base_url:
            continue
        base_url_candidates.append(
            {
                "name": str(environment_draft.get("name") or f"环境{index + 1}"),
                "base_url": base_url,
                "environment_id": saved_environment.id if saved_environment else None,
                "selected": bool(primary_environment and saved_environment and saved_environment.id == primary_environment.id),
            }
        )

    return {
        "recommended_environment_id": primary_environment.id if primary_environment else None,
        "recommended_environment_name": primary_environment.name if primary_environment else None,
        "base_url_candidates": base_url_candidates,
        "variable_suggestions": variable_suggestions,
        "auth_suggestions": auth_suggestions,
        "environment_patch": _build_environment_patch(variable_suggestions, auth_suggestions, primary_environment_draft),
    }


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


def _collect_common_cookies(parsed_requests: list[ParsedRequestData]) -> list[dict]:
    if not parsed_requests:
        return []

    first_cookies = ((parsed_requests[0].request_spec or {}).get("cookies")) or []
    common_cookies: list[dict] = []

    for index, cookie in enumerate(first_cookies):
        if not isinstance(cookie, dict):
            continue
        name = str(cookie.get("name") or "").strip()
        if not name:
            continue
        domain = str(cookie.get("domain") or "")
        path = str(cookie.get("path") or "/")
        value = cookie.get("value", "")
        if all(
            any(
                isinstance(candidate, dict)
                and str(candidate.get("name") or "").strip() == name
                and str(candidate.get("domain") or "") == domain
                and str(candidate.get("path") or "/") == path
                and candidate.get("value", "") == value
                for candidate in (((request.request_spec or {}).get("cookies")) or [])
            )
            for request in parsed_requests[1:]
        ):
            common_cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "enabled": bool(cookie.get("enabled", True)),
                    "order": int(cookie.get("order", index)),
                }
            )

    return common_cookies


def _is_secret_variable_name(name: str) -> bool:
    lowered = str(name or "").strip().lower()
    return any(keyword in lowered for keyword in SECRET_VARIABLE_KEYWORDS)


def _build_environment_spec_payload(
    common_headers: dict[str, str],
    variables: dict[str, str],
    cookies: list[dict] | None = None,
) -> dict[str, list[dict]]:
    return {
        "headers": named_items_from_mapping(common_headers),
        "variables": [
            {
                "name": key,
                "value": value,
                "enabled": True,
                "is_secret": _is_secret_variable_name(key),
                "order": index,
            }
            for index, (key, value) in enumerate((variables or {}).items())
        ],
        "cookies": [
            {
                "name": str(item.get("name") or "").strip(),
                "value": item.get("value", ""),
                "domain": str(item.get("domain") or ""),
                "path": str(item.get("path") or "/"),
                "enabled": bool(item.get("enabled", True)),
                "order": int(item.get("order", index)),
            }
            for index, item in enumerate(cookies or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ],
    }


def _merge_environment_spec_items(
    incoming_items: list[dict] | None,
    existing_items: list[dict] | None,
    *,
    key_fields: tuple[str, ...],
) -> list[dict]:
    merged: dict[tuple[str, ...], dict] = {}
    ordered_keys: list[tuple[str, ...]] = []

    for source_items in (incoming_items or [], existing_items or []):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            key = []
            for field_name in key_fields:
                default_value = "/" if field_name == "path" else ""
                key.append(str(item.get(field_name) or default_value))
            key_tuple = tuple(key)
            if not key_tuple[0]:
                continue
            normalized = dict(item)
            normalized["enabled"] = bool(item.get("enabled", True))
            if "is_secret" in normalized:
                normalized["is_secret"] = bool(item.get("is_secret", False))
            if key_tuple not in merged:
                ordered_keys.append(key_tuple)
            merged[key_tuple] = normalized

    results: list[dict] = []
    for index, key in enumerate(ordered_keys):
        item = dict(merged[key])
        item["order"] = index
        results.append(item)
    return results


def _build_environment_drafts(file_path: str, parsed_requests: list[ParsedRequestData]) -> list[dict]:
    document_content, _, _ = load_document_content_for_ai(file_path)
    common_headers = _collect_common_headers(parsed_requests)
    variables = _collect_variables(document_content, parsed_requests)
    common_cookies = _collect_common_cookies(parsed_requests)
    environment_specs = _build_environment_spec_payload(common_headers, variables, common_cookies)

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
                "environment_specs": environment_specs,
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
                    "environment_specs": environment_specs,
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
        environment_specs = environment_draft.get("environment_specs") or _build_environment_spec_payload(
            common_headers,
            variables,
            [],
        )
        timeout_ms = int(environment_draft.get("timeout_ms") or 30000)
        draft_name = str(environment_draft.get("name") or f"环境{index + 1}").strip()

        has_cookies = bool((environment_specs or {}).get("cookies"))

        if not base_url and not common_headers and not variables and not has_cookies:
            continue

        if base_url:
            existing = ApiEnvironment.objects.filter(project=collection.project, base_url=base_url).first()
            if existing:
                updated = False
                current_specs = serialize_environment_specs(existing)
                merged_specs = {
                    "headers": _merge_environment_spec_items(
                        (environment_specs or {}).get("headers"),
                        current_specs.get("headers"),
                        key_fields=("name",),
                    ),
                    "variables": _merge_environment_spec_items(
                        (environment_specs or {}).get("variables"),
                        current_specs.get("variables"),
                        key_fields=("name",),
                    ),
                    "cookies": _merge_environment_spec_items(
                        (environment_specs or {}).get("cookies"),
                        current_specs.get("cookies"),
                        key_fields=("name", "domain", "path"),
                    ),
                }
                if merged_specs != current_specs:
                    apply_environment_spec_payload(existing, merged_specs)
                    updated = True
                desired_base_name = _build_environment_name(draft_name, collection)
                desired_name = _build_unique_environment_name(collection.project, desired_base_name, exclude_id=existing.id)
                if existing.name != desired_name and existing.name.startswith("自动解析环境-"):
                    existing.name = desired_name
                    updated = True
                if existing.timeout_ms == 30000 and timeout_ms != existing.timeout_ms:
                    existing.timeout_ms = timeout_ms
                    updated = True
                if updated:
                    existing.save(update_fields=["name", "timeout_ms", "updated_at"])
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
        apply_environment_spec_payload(saved_environments[-1], environment_specs)

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
    return _process_document_import_ai_only(
        collection=collection,
        user=user,
        file_path=file_path,
        generate_test_cases=generate_test_cases,
        enable_ai_parse=enable_ai_parse,
        progress_callback=progress_callback,
        cancel_callback=cancel_callback,
    )

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
    environment_suggestions = _build_environment_suggestions(
        parsed_requests=parsed_requests,
        created_requests=created_requests,
        environment_drafts=environment_drafts,
        saved_environments=saved_environments,
        primary_environment_draft=primary_environment_draft,
        primary_environment=primary_environment,
    )

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
    ai_feedback = _build_ai_feedback(enable_ai_parse=enable_ai_parse, ai_result=ai_result)

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
        "ai_cache_hit": ai_result.cache_hit if ai_result else False,
        "ai_cache_key": ai_result.cache_key if ai_result else None,
        "ai_duration_ms": ai_result.duration_ms if ai_result else None,
        "ai_lock_wait_ms": ai_result.lock_wait_ms if ai_result else None,
        "ai_issue_code": ai_feedback["issue_code"],
        "ai_user_message": ai_feedback["user_message"],
        "ai_action_hint": ai_feedback["action_hint"],
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
        "environment_suggestions": environment_suggestions,
        "items": serialized_requests,
        "generated_scripts": generated_scripts,
        "test_cases": testcase_serializer.data,
    }
    _report(progress_callback, 100, "completed", "接口文档解析完成。")
    return payload
