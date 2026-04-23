from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FASTAPI_ROOT = REPO_ROOT / "FlyTest_FastAPI"


def main():
    service_dir = FASTAPI_ROOT / "app" / "services"
    service_files = []
    django_runtime_files = []
    django_runtime_groups: dict[str, list[str]] = {}

    for service_file in sorted(service_dir.rglob("*.py")):
        if service_file.name == "__init__.py":
            continue
        rel_path = str(service_file.relative_to(FASTAPI_ROOT)).replace("\\", "/")
        service_files.append(rel_path)
        text = service_file.read_text(encoding="utf-8")
        if (
            "ensure_django_setup" in text
            or "get_django_user" in text
            or re.search(r"from\s+django[\.\s]", text)
            or re.search(r"from\s+[a-zA-Z_][\w]*\.serializers\s+import", text)
            or re.search(r"from\s+[a-zA-Z_][\w]*\.models\s+import", text)
        ):
            django_runtime_files.append(rel_path)
            parts = rel_path.split("/")
            group = parts[2] if len(parts) > 2 else "misc"
            django_runtime_groups.setdefault(group, []).append(rel_path)

    result = {
        "service_file_count": len(service_files),
        "django_runtime_file_count": len(django_runtime_files),
        "django_runtime_files": django_runtime_files,
        "django_runtime_groups": django_runtime_groups,
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
