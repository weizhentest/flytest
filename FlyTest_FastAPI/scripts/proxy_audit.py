from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FASTAPI_ROOT = REPO_ROOT / "FlyTest_FastAPI"


def main():
    service_dir = FASTAPI_ROOT / "app" / "services"
    compat_dir = FASTAPI_ROOT / "app" / "compat"
    proxy_files = []
    compat_proxy_files = []
    compat_proxy_routes: dict[str, list[str]] = {}

    for service_file in sorted(service_dir.rglob("*.py")):
        if service_file.name == "__init__.py":
            continue
        text = service_file.read_text(encoding="utf-8")
        if "app.compat.django_http" in text or "call_django_view" in text or "django_response_to_fastapi" in text:
            proxy_files.append(str(service_file.relative_to(FASTAPI_ROOT)).replace("\\", "/"))

    for compat_file in sorted(compat_dir.rglob("*.py")):
        if compat_file.name == "__init__.py":
            continue
        if compat_file.name == "django_http.py":
            continue
        text = compat_file.read_text(encoding="utf-8")
        if "call_django_view" in text or "django_response_to_fastapi" in text:
            rel_path = str(compat_file.relative_to(FASTAPI_ROOT)).replace("\\", "/")
            compat_proxy_files.append(rel_path)
            route_matches = re.findall(r'\("([A-Z]+)",\s*"([^"]+)"\)', text)
            compat_proxy_routes[rel_path] = [f"{method} {path}" for method, path in route_matches]

    grouped = {}
    for rel_path in proxy_files:
        parts = rel_path.split("/")
        group = parts[2] if len(parts) > 2 else "misc"
        grouped.setdefault(group, []).append(rel_path)

    result = {
        "proxy_file_count": len(proxy_files),
        "proxy_files": proxy_files,
        "proxy_groups": grouped,
        "compat_proxy_file_count": len(compat_proxy_files),
        "compat_proxy_files": compat_proxy_files,
        "compat_proxy_route_count": sum(len(routes) for routes in compat_proxy_routes.values()),
        "compat_proxy_routes": compat_proxy_routes,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
