from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FASTAPI_ROOT = REPO_ROOT / "FlyTest_FastAPI"


def main():
    compat_dir = FASTAPI_ROOT / "app" / "compat"
    runtime_files = []

    for compat_file in sorted(compat_dir.glob("*_runtime.py")):
        runtime_files.append(str(compat_file.relative_to(FASTAPI_ROOT)).replace("\\", "/"))

    payload = {
        "compat_runtime_file_count": len(runtime_files),
        "compat_runtime_files": runtime_files,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
