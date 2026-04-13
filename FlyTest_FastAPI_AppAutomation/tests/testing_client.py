from __future__ import annotations

import asyncio
import gc
from typing import Any

import httpx


class TestClient:
    """Minimal sync wrapper around httpx.AsyncClient for ASGI app tests."""

    __test__ = False

    def __init__(self, app, base_url: str = "http://testserver") -> None:
        self.app = app
        self.base_url = base_url
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: httpx.AsyncClient | None = None
        self._lifespan = None

    def __enter__(self) -> "TestClient":
        self._loop = asyncio.new_event_loop()
        self._lifespan = self.app.router.lifespan_context(self.app)
        self._loop.run_until_complete(self._lifespan.__aenter__())
        transport = httpx.ASGITransport(app=self.app)
        self._client = httpx.AsyncClient(
            transport=transport,
            base_url=self.base_url,
            follow_redirects=True,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._client is not None and self._loop is not None:
                self._loop.run_until_complete(self._client.aclose())
        finally:
            if self._lifespan is not None and self._loop is not None:
                self._loop.run_until_complete(self._lifespan.__aexit__(exc_type, exc, tb))
                self._loop.run_until_complete(asyncio.sleep(0.2))
            if self._loop is not None:
                self._loop.close()
            self._client = None
            self._lifespan = None
            self._loop = None
            gc.collect()

    @property
    def cookies(self):
        if self._client is None:
            raise RuntimeError("TestClient must be used as a context manager")
        return self._client.cookies

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None or self._loop is None:
            raise RuntimeError("TestClient must be used as a context manager")
        return self._loop.run_until_complete(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)
