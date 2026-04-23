from __future__ import annotations

import inspect
from typing import Any
from urllib.parse import urlencode

from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from app.compat.django_bridge import ensure_django_setup


def _build_request_path(path: str, query_params: dict[str, Any] | None = None) -> str:
    if not query_params:
        return path
    pairs: list[tuple[str, str]] = []
    for key, value in query_params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                pairs.append((key, str(item)))
        else:
            pairs.append((key, str(value)))
    if not pairs:
        return path
    return f"{path}?{urlencode(pairs)}"


async def call_django_view(
    *,
    view_callable,
    method: str,
    path: str,
    body: bytes | None = None,
    content_type: str = "application/json",
    authorization: str | None = None,
    query_params: dict[str, Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    user=None,
):
    ensure_django_setup()
    from django.test.client import AsyncRequestFactory
    from rest_framework.test import force_authenticate

    request_path = _build_request_path(path, query_params)
    factory = AsyncRequestFactory()
    extra = {}
    if authorization:
        extra["HTTP_AUTHORIZATION"] = authorization
    request = factory.generic(
        method.upper(),
        request_path,
        data=body or b"",
        content_type=content_type,
        **extra,
    )
    if authorization:
        request.META["HTTP_AUTHORIZATION"] = authorization
    if user is not None:
        force_authenticate(request, user=user)
    if inspect.iscoroutinefunction(view_callable):
        result = view_callable(request, **(kwargs or {}))
        if inspect.isawaitable(result):
            return await result
        return result

    result = await run_in_threadpool(view_callable, request, **(kwargs or {}))
    if inspect.isawaitable(result):
        return await result
    return result


def django_response_to_fastapi(response):
    if hasattr(response, "render") and not getattr(response, "is_rendered", True):
        response = response.render()

    headers = {}
    for key, value in response.items():
        if key.lower() in {"content-length", "content-type"}:
            continue
        headers[key] = value

    content_type = response.get("Content-Type", None)
    status_code = getattr(response, "status_code", 200)

    if getattr(response, "streaming", False):
        streaming_content = response.streaming_content
        if hasattr(streaming_content, "__aiter__"):
            async def async_stream():
                async for chunk in streaming_content:
                    yield chunk.encode("utf-8") if isinstance(chunk, str) else chunk
            return StreamingResponse(async_stream(), status_code=status_code, media_type=content_type, headers=headers)

        def sync_stream():
            for chunk in streaming_content:
                yield chunk.encode("utf-8") if isinstance(chunk, str) else chunk

        return StreamingResponse(sync_stream(), status_code=status_code, media_type=content_type, headers=headers)

    return Response(content=bytes(response.content), status_code=status_code, media_type=content_type, headers=headers)
