import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
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

from app.main import create_app  # noqa: E402

import django  # noqa: E402

django.setup()


client = TestClient(create_app())


def _auth_headers() -> dict[str, str]:
    response = client.post("/api/token/", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access']}"}


class FakeMCPClient:
    def __init__(self, *_args, **_kwargs):
        pass

    async def get_tools(self):
        return [SimpleNamespace(name="browser_open"), SimpleNamespace(name="browser_click")]

    def session(self, *_args, **_kwargs):
        class _SessionContext:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

            async def list_tools(self_inner):
                return SimpleNamespace(tools=[SimpleNamespace(name="browser_open", description="open browser", inputSchema={}), SimpleNamespace(name="browser_click", description="click browser", inputSchema={})])

        return _SessionContext()


@patch("app.services.mcp_tools.service.MultiServerMCPClient", side_effect=lambda *args, **kwargs: FakeMCPClient())
def test_remote_mcp_config_crud_and_ping_flow(_mock_client) -> None:
    from mcp_tools.models import MCPTool

    headers = _auth_headers()
    config_name = f"FastAPI MCP {uuid4().hex[:8]}"

    created = client.post(
        "/api/mcp_tools/remote-configs/",
        headers=headers,
        json={
            "name": config_name,
            "url": "https://example.test/mcp",
            "transport": "streamable-http",
            "headers": {"Authorization": "Bearer token"},
            "is_active": True,
        },
    )
    assert created.status_code == 201
    config = created.json()["data"]
    config_id = config["id"]

    listing = client.get("/api/mcp_tools/remote-configs/", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == config_id for item in listing.json()["data"])

    detail = client.get(f"/api/mcp_tools/remote-configs/{config_id}/", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == config_name

    updated = client.patch(
        f"/api/mcp_tools/remote-configs/{config_id}/",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["is_active"] is False

    ping = client.post(
        "/api/mcp_tools/remote-configs/ping/",
        headers=headers,
        json={"config_id": config_id},
    )
    assert ping.status_code == 200
    assert ping.json()["data"]["status"] == "online"
    assert ping.json()["data"]["tools_count"] == 2

    synced = client.post(
        f"/api/mcp_tools/remote-configs/{config_id}/sync_tools/",
        headers=headers,
    )
    assert synced.status_code == 200
    assert synced.json()["data"]["success"] is True

    assert MCPTool.objects.filter(mcp_config_id=config_id, name="browser_open").exists()
    assert MCPTool.objects.filter(mcp_config_id=config_id, name="browser_click").exists()

    tools = client.get(
        f"/api/mcp_tools/remote-configs/{config_id}/tools/",
        headers=headers,
    )
    assert tools.status_code == 200
    assert tools.json()["data"]["tools_count"] == 2
    assert {item["name"] for item in tools.json()["data"]["tools"]} == {"browser_open", "browser_click"}

    called = client.post(
        "/api/mcp_tools/call/",
        headers=headers,
        json={"name": "get_project_list", "arguments": {}},
    )
    assert called.status_code == 200
    assert isinstance(called.json()["data"], list)

    deleted = client.delete(f"/api/mcp_tools/remote-configs/{config_id}/", headers=headers)
    assert deleted.status_code == 200
