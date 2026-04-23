import os
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "FlyTest_FastAPI"))
sys.path.insert(0, str(REPO_ROOT / "FlyTest_Django"))

os.environ["DATABASE_URL"] = f"sqlite:///{(REPO_ROOT / 'FlyTest_Django' / 'db.sqlite3').as_posix()}"
os.environ["SECRET_KEY"] = "change-me-fastapi-local"
os.environ["APP_ENV"] = "test"
os.environ["API_PREFIX"] = "/api"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flytest_django.settings")

from app.config import get_settings

get_settings.cache_clear()

import django  # noqa: E402

django.setup()

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


def test_accounts_proxy_flow() -> None:
    headers = _auth_headers()

    user_suffix = uuid4().hex[:8]
    register = client.post(
        "/api/accounts/register/",
        json={
            "username": f"fastapi_user_{user_suffix}",
            "email": f"fastapi_user_{user_suffix}@example.com",
            "password": "Password123!",
        },
    )
    assert register.status_code in (200, 201)
    registered_user = _unwrap_data(register.json())
    user_id = registered_user["id"]

    me = client.get("/api/accounts/me/", headers=headers)
    assert me.status_code == 200
    assert _unwrap_data(me.json())["username"] == "admin"

    content_types = client.get("/api/accounts/content-types/", headers=headers)
    assert content_types.status_code == 200
    assert isinstance(_unwrap_data(content_types.json()), list)
    content_type_id = _unwrap_data(content_types.json())[0]["id"]
    content_type_detail = client.get(f"/api/accounts/content-types/{content_type_id}/", headers=headers)
    assert content_type_detail.status_code == 200

    permissions = client.get("/api/accounts/permissions/", headers=headers)
    assert permissions.status_code == 200
    permissions_payload = _unwrap_data(permissions.json())
    assert isinstance(permissions_payload, list)
    permission_id = permissions_payload[0]["id"]
    permission_detail = client.get(f"/api/accounts/permissions/{permission_id}/", headers=headers)
    assert permission_detail.status_code == 200

    group_created = client.post(
        "/api/accounts/groups/",
        headers=headers,
        json={"name": f"FastAPI Group {user_suffix}"},
    )
    assert group_created.status_code in (200, 201)
    group = _unwrap_data(group_created.json())
    group_id = group["id"]

    users_in_group_before = client.get(f"/api/accounts/groups/{group_id}/users/", headers=headers)
    assert users_in_group_before.status_code == 200

    added = client.post(
        f"/api/accounts/groups/{group_id}/add_users/",
        headers=headers,
        json={"user_ids": [user_id]},
    )
    assert added.status_code == 200

    users_in_group_after = client.get(f"/api/accounts/groups/{group_id}/users/", headers=headers)
    assert users_in_group_after.status_code == 200
    assert any(item["id"] == user_id for item in _unwrap_data(users_in_group_after.json()))

    assign_to_group = client.post(
        f"/api/accounts/permissions/{permission_id}/assign_to_group/",
        headers=headers,
        json={"group_id": group_id},
    )
    assert assign_to_group.status_code == 200

    group_permissions = client.get(f"/api/accounts/groups/{group_id}/permissions/", headers=headers)
    assert group_permissions.status_code == 200
    assert any(item["id"] == permission_id for item in _unwrap_data(group_permissions.json()))

    assign_to_user = client.post(
        f"/api/accounts/permissions/{permission_id}/assign_to_user/",
        headers=headers,
        json={"user_id": user_id},
    )
    assert assign_to_user.status_code == 200

    user_permissions = client.get(f"/api/accounts/users/{user_id}/permissions/", headers=headers)
    assert user_permissions.status_code == 200
    user_permissions_payload = _unwrap_data(user_permissions.json())
    assert isinstance(user_permissions_payload, list)
    assert any(item["id"] == permission_id for item in user_permissions_payload)

    remove_from_user = client.post(
        f"/api/accounts/permissions/{permission_id}/remove_from_user/",
        headers=headers,
        json={"user_id": user_id},
    )
    assert remove_from_user.status_code == 200

    remove_from_group = client.post(
        f"/api/accounts/permissions/{permission_id}/remove_from_group/",
        headers=headers,
        json={"group_id": group_id},
    )
    assert remove_from_group.status_code == 200

    removed = client.post(
        f"/api/accounts/groups/{group_id}/remove_users/",
        headers=headers,
        json={"user_ids": [user_id]},
    )
    assert removed.status_code == 200

    deleted_group = client.delete(f"/api/accounts/groups/{group_id}/", headers=headers)
    assert deleted_group.status_code in (200, 204)

    deleted_user = client.delete(f"/api/accounts/users/{user_id}/", headers=headers)
    assert deleted_user.status_code in (200, 204)
