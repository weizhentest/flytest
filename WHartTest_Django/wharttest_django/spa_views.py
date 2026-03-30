from pathlib import Path
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404


FRONTEND_DIST_ROOT = (settings.BASE_DIR.parent / "WHartTest_Vue" / "dist").resolve()


def _safe_resolve(path: str) -> Path:
    target = (FRONTEND_DIST_ROOT / path).resolve()
    if FRONTEND_DIST_ROOT not in target.parents and target != FRONTEND_DIST_ROOT:
        raise Http404("Invalid asset path")
    if not target.exists() or not target.is_file():
        raise Http404("Asset not found")
    return target


def serve_spa_asset(request, asset_path: str):
    file_path = _safe_resolve(asset_path)
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(open(file_path, "rb"), content_type=content_type)


def serve_spa_index(request, path: str = ""):
    index_path = _safe_resolve("index.html")
    return FileResponse(open(index_path, "rb"), content_type="text/html; charset=utf-8")
