import io
import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "FlyTest_FastAPI"))

os.environ["DATABASE_URL"] = f"sqlite:///{(REPO_ROOT / 'FlyTest_Django' / 'db.sqlite3').as_posix()}"
os.environ["SECRET_KEY"] = "change-me-fastapi-local"
os.environ["APP_ENV"] = "test"
os.environ["API_PREFIX"] = "/api"

from app.config import get_settings

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


client = TestClient(create_app())


def _unwrap_data(payload):
    if isinstance(payload, dict) and "status" in payload and "data" in payload:
        return payload["data"]
    return payload


def _auth_headers() -> dict[str, str]:
    response = client.post("/api/token/", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access']}"}


def _build_excel_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["name_col", "module_col", "steps_col"])
    sheet.append(["sample case", "module A", "step 1"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def test_testcase_template_flow() -> None:
    headers = _auth_headers()
    template_name = f"FastAPI Template {uuid4().hex[:8]}"

    created = client.post(
        "/api/testcase-templates/",
        headers=headers,
        json={
            "name": template_name,
            "template_type": "import",
            "description": "FastAPI template migration test",
            "header_row": 1,
            "data_start_row": 2,
            "field_mappings": {"name": "name_col"},
            "value_transformations": {},
            "step_parsing_mode": "single_cell",
            "step_config": {},
            "module_path_delimiter": "/",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    template = created.json()["data"]
    template_id = template["id"]

    listing = client.get("/api/testcase-templates/", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == template_id for item in listing.json()["data"])

    detail = client.get(f"/api/testcase-templates/{template_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == template_name

    excel_bytes = _build_excel_bytes()
    parsed = client.post(
        "/api/testcase-templates/parse_headers/",
        headers=headers,
        files={"file": ("template.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"sheet_name": "Sheet1", "header_row": "1"},
    )
    assert parsed.status_code == 200
    assert parsed.json()["data"]["headers"][:2] == ["name_col", "module_col"]

    field_options = client.get("/api/testcase-templates/field_options/", headers=headers)
    assert field_options.status_code == 200
    assert any(item["value"] == "name" for item in field_options.json()["data"]["fields"])

    duplicated = client.post(f"/api/testcase-templates/{template_id}/duplicate/", headers=headers)
    assert duplicated.status_code == 201
    assert duplicated.json()["data"]["name"].startswith(template_name)

    uploaded_template = client.post(
        f"/api/testcase-templates/{template_id}/upload-template-file/",
        headers=headers,
        files={"file": ("template.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert uploaded_template.status_code == 200
    assert _unwrap_data(uploaded_template.json())["template_headers"][:2] == ["name_col", "module_col"]

    deleted = client.delete(f"/api/testcase-templates/{template_id}/", headers=headers)
    assert deleted.status_code == 200
