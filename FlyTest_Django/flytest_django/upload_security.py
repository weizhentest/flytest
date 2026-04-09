from __future__ import annotations

from pathlib import Path
import zipfile

from PIL import Image, UnidentifiedImageError


def validate_uploaded_file_size(uploaded_file, *, max_size: int, label: str) -> str | None:
    size = getattr(uploaded_file, "size", None)
    if size is None:
        return None
    if size > max_size:
        size_mb = max_size / (1024 * 1024)
        return f"{label}大小不能超过 {size_mb:.0f} MB。"
    return None


def validate_uploaded_file_extension(uploaded_file, *, allowed_extensions: set[str], label: str) -> str | None:
    suffix = Path(getattr(uploaded_file, "name", "")).suffix.lower()
    if suffix not in allowed_extensions:
        readable = "、".join(sorted(allowed_extensions))
        return f"{label}格式不受支持，仅允许：{readable}。"
    return None


def validate_image_file(uploaded_file, *, allowed_formats: set[str] | None = None) -> str | None:
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()
            image_format = (image.format or "").upper()
        uploaded_file.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        uploaded_file.seek(0)
        return "上传的截图不是有效的图片文件。"

    if allowed_formats and image_format not in allowed_formats:
        readable = "、".join(sorted(allowed_formats))
        return f"截图图片格式不受支持，仅允许：{readable}。"
    return None


def validate_zip_file(uploaded_file) -> str | None:
    try:
        uploaded_file.seek(0)
        is_zip = zipfile.is_zipfile(uploaded_file)
        uploaded_file.seek(0)
    except OSError:
        uploaded_file.seek(0)
        return "上传的 Trace 文件无法读取。"

    if not is_zip:
        return "上传的 Trace 文件必须是有效的 ZIP 压缩包。"
    return None
