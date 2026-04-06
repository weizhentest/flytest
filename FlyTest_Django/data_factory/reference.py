from __future__ import annotations

import json
import re
from typing import Any

from django.utils.text import slugify

from .models import DataFactoryRecord, DataFactoryTag


def build_tag_code(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "tag"
    code = slugify(raw, allow_unicode=True).replace("-", "_")
    code = re.sub(r"\s+", "_", code)
    code = re.sub(r"[^\w\u4e00-\u9fff]+", "_", code)
    code = re.sub(r"_+", "_", code).strip("_")
    return code or "tag"


def make_unique_tag_code(project_id: int, name: str, exclude_id: int | None = None) -> str:
    base_code = build_tag_code(name)
    candidate = base_code
    index = 2
    queryset = DataFactoryTag.objects.filter(project_id=project_id)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    existing_codes = set(queryset.values_list("code", flat=True))
    while candidate in existing_codes:
        candidate = f"{base_code}_{index}"
        index += 1
    return candidate


def extract_reference_value(output_data: Any) -> Any:
    value = output_data.get("result") if isinstance(output_data, dict) and "result" in output_data else output_data
    # json-tree tools keep both formatted text and parsed data for display; references should point to the parsed payload.
    if isinstance(value, dict) and "parsed" in value and "text" in value and isinstance(value.get("text"), str):
        return value.get("parsed")
    return value


def preview_reference_value(value: Any, *, limit: int = 80) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = "" if value is None else str(value)
    return text if len(text) <= limit else f"{text[:limit]}..."


def build_reference_tree(project_id: int) -> dict[str, Any]:
    records = (
        DataFactoryRecord.objects.filter(project_id=project_id, is_saved=True)
        .prefetch_related("tags")
        .order_by("-created_at", "-id")
    )
    tag_tree: dict[str, Any] = {}
    record_tree: dict[str, Any] = {}
    for record in records:
        value = extract_reference_value(record.output_data)
        record_tree[str(record.id)] = value
        for tag in record.tags.all():
            tag_tree.setdefault(tag.code, value)
    return {"tag": tag_tree, "record": record_tree}


def build_reference_options(project_id: int) -> dict[str, list[dict[str, Any]]]:
    records = (
        DataFactoryRecord.objects.filter(project_id=project_id, is_saved=True)
        .prefetch_related("tags")
        .order_by("-created_at", "-id")
    )
    tag_options: list[dict[str, Any]] = []
    record_options: list[dict[str, Any]] = []
    seen_tag_ids: set[int] = set()
    for record in records:
        value = extract_reference_value(record.output_data)
        record_options.append(
            {
                "id": record.id,
                "tool_name": record.tool_name,
                "tool_category": record.tool_category,
                "created_at": record.created_at,
                "preview": preview_reference_value(value),
                "value": value,
                "tag_codes": [tag.code for tag in record.tags.all()],
            }
        )
        for tag in record.tags.all():
            if tag.id in seen_tag_ids:
                continue
            seen_tag_ids.add(tag.id)
            tag_options.append(
                {
                    "id": tag.id,
                    "name": tag.name,
                    "code": tag.code,
                    "color": tag.color,
                    "description": tag.description,
                    "preview": preview_reference_value(value),
                    "value": value,
                }
            )
    return {"tags": tag_options, "records": record_options}


def build_reference_placeholder(key_type: str, value: str, *, mode: str = "api") -> str:
    expression = f"df.{key_type}.{value}"
    if mode == "ui":
        return f"${{{{{expression}}}}}"
    return f"{{{{{expression}}}}}"
