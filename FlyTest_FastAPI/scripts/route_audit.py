from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DJANGO_ROOT = REPO_ROOT / "FlyTest_Django"
FASTAPI_ROOT = REPO_ROOT / "FlyTest_FastAPI"

if str(DJANGO_ROOT) not in sys.path:
    sys.path.insert(0, str(DJANGO_ROOT))
if str(FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(FASTAPI_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

import django  # noqa: E402

django.setup()

from django.urls import URLPattern, URLResolver, get_resolver  # noqa: E402
from app.main import create_app  # noqa: E402


DJANGO_PARAM_RE = re.compile(r"\(\?P<[^>]+>[^)]+\)")
FASTAPI_PARAM_RE = re.compile(r"\{[^}:]+(?::[^}]+)?\}")


def _walk_django(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLPattern):
            callback = pattern.callback
            actions = getattr(callback, "actions", None)
            methods = sorted(m.upper() for m in actions.keys()) if actions else ["*"]
            yield prefix + str(pattern.pattern), methods
        elif isinstance(pattern, URLResolver):
            yield from _walk_django(pattern.url_patterns, prefix + str(pattern.pattern))


def _normalize_common(path: str) -> str:
    normalized = path.replace("^", "").replace("$", "")
    normalized = normalized.replace("\\", "")
    normalized = normalized.replace(".(?P<format>[a-z0-9]+)/?", "")
    normalized = normalized.replace("<drf_format_suffix:format>", "")
    normalized = DJANGO_PARAM_RE.sub("{param}", normalized)
    normalized = DJANGO_PARAM_RE.sub("{param}", normalized)
    normalized = FASTAPI_PARAM_RE.sub("{param}", normalized)
    normalized = re.sub(r"/{2,}", "/", normalized)
    normalized = normalized.rstrip("/")
    return normalized or "/"


def _collect_fastapi_routes():
    app = create_app()
    routes = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = sorted(m for m in (getattr(route, "methods", None) or []) if m not in {"HEAD", "OPTIONS"})
        routes[_normalize_common(path)] = methods
    return routes


def _is_covered(django_path: str, fastapi_routes: dict[str, list[str]]) -> bool:
    if django_path in fastapi_routes:
        return True
    if django_path.startswith("/api/accounts") and "/api/accounts/{param}" in fastapi_routes:
        return True
    return False


def main():
    django_routes = {}
    for path, methods in _walk_django(get_resolver().url_patterns):
        if not path.startswith("api/"):
            continue
        if methods == ["*"]:
            continue
        normalized = _normalize_common("/" + path)
        if normalized in {"/api", "/api/<drf_format_suffix:format>"}:
            continue
        django_routes[normalized] = methods

    fastapi_routes = _collect_fastapi_routes()
    missing = sorted(path for path in django_routes if not _is_covered(path, fastapi_routes))

    by_prefix: dict[str, list[str]] = defaultdict(list)
    for path in missing:
        parts = [part for part in path.split("/") if part]
        prefix = parts[1] if len(parts) >= 2 else "misc"
        by_prefix[prefix].append(path)

    result = {
        "django_route_count": len(django_routes),
        "fastapi_route_count": len(fastapi_routes),
        "missing_count": len(missing),
        "missing_by_prefix": {key: values for key, values in sorted(by_prefix.items())},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
