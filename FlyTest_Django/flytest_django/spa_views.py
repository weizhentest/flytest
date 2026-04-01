from pathlib import Path
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect


FRONTEND_DIST_ROOT = (settings.BASE_DIR.parent / "FlyTest_Vue" / "dist").resolve()
DEV_SERVER_URL = os.environ.get("VITE_DEV_SERVER_URL", "http://127.0.0.1:5173").rstrip("/")


def _frontend_dist_available() -> bool:
    return (FRONTEND_DIST_ROOT / "index.html").is_file()


def _redirect_to_dev_server(request):
    return HttpResponseRedirect(f"{DEV_SERVER_URL}{request.get_full_path()}")


def _safe_resolve(path: str) -> Path:
    target = (FRONTEND_DIST_ROOT / path).resolve()
    if FRONTEND_DIST_ROOT not in target.parents and target != FRONTEND_DIST_ROOT:
        raise Http404("Invalid asset path")
    if not target.exists() or not target.is_file():
        raise Http404("Asset not found")
    return target


def serve_spa_asset(request, asset_path: str):
    if settings.DEBUG and not _frontend_dist_available():
        return _redirect_to_dev_server(request)
    file_path = _safe_resolve(asset_path)
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(open(file_path, "rb"), content_type=content_type)


def serve_spa_index(request, path: str = ""):
    if settings.DEBUG and not _frontend_dist_available():
        return _redirect_to_dev_server(request)
    index_path = _safe_resolve("index.html")
    return FileResponse(open(index_path, "rb"), content_type="text/html; charset=utf-8")
