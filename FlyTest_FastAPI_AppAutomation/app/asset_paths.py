from __future__ import annotations

from pathlib import Path

from . import database


def normalize_asset_path(asset_path: str) -> str:
    return (asset_path or "").replace("\\", "/").strip().lstrip("/")


def get_asset_root() -> Path:
    return database.ELEMENT_UPLOADS_DIR.resolve()


def resolve_upload_asset_path(asset_path: str) -> Path | None:
    cleaned = normalize_asset_path(asset_path)
    if not cleaned:
        return None

    relative_parts = [segment for segment in cleaned.split("/") if segment]
    if relative_parts and relative_parts[0] == "elements":
        relative_parts = relative_parts[1:]
    if not relative_parts:
        return None

    candidate = get_asset_root().joinpath(*relative_parts).resolve()
    try:
        candidate.relative_to(get_asset_root())
    except ValueError:
        return None
    return candidate


def extract_project_id_from_asset_path(asset_path: str) -> int | None:
    parts = [segment for segment in normalize_asset_path(asset_path).split("/") if segment]
    for segment in parts:
        if not segment.startswith("project-"):
            continue
        project_suffix = segment.removeprefix("project-")
        if project_suffix.isdigit():
            return int(project_suffix)
    return None
