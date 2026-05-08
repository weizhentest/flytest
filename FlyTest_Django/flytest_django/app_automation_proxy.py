from __future__ import annotations

import os
from urllib.parse import urljoin

import requests
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


APP_AUTOMATION_PROXY_TARGET = os.environ.get(
    "APP_AUTOMATION_PROXY_TARGET",
    "http://127.0.0.1:8010",
).rstrip("/")

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _build_target_url(subpath: str) -> str:
    normalized = subpath.lstrip("/")
    return urljoin(f"{APP_AUTOMATION_PROXY_TARGET}/", normalized)


def _copy_request_headers(request: HttpRequest) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        headers[key] = value
    return headers


def _copy_response_headers(response: requests.Response, django_response: HttpResponse) -> None:
    for key, value in response.headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS:
            continue
        django_response[key] = value


@csrf_exempt
def proxy_app_automation(request: HttpRequest, subpath: str = "") -> HttpResponse:
    target_url = _build_target_url(subpath)
    query_string = request.META.get("QUERY_STRING", "").strip()
    if query_string:
        target_url = f"{target_url}?{query_string}"

    try:
        upstream_response = requests.request(
            method=request.method,
            url=target_url,
            headers=_copy_request_headers(request),
            data=request.body or None,
            timeout=60,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        return JsonResponse(
            {
                "status": "error",
                "code": 502,
                "message": "APP 自动化服务暂时不可用",
                "data": None,
                "errors": {"detail": str(exc)},
            },
            status=502,
        )

    django_response = HttpResponse(
        content=upstream_response.content,
        status=upstream_response.status_code,
        content_type=upstream_response.headers.get("Content-Type"),
    )
    _copy_response_headers(upstream_response, django_response)
    return django_response
