import asyncio
import base64
import sys

import pytest
from fastapi.testclient import TestClient

from chromaswarm.clone import preview


def test_preview_captures_local_page_and_reuses_cache(tmp_path, monkeypatch):
    page = tmp_path / "preview.html"
    page.write_text("<title>Preview fixture</title><h1>Reference page</h1>", encoding="utf-8")
    url = page.as_uri()
    try:
        # On Windows this deliberately recreates Uvicorn --reload's event loop.
        factory = asyncio.SelectorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
        with asyncio.Runner(loop_factory=factory) as runner:
            result = runner.run(preview.page_preview(url))
        assert result.title == "Preview fixture"
        assert base64.b64decode(result.image.split(",", 1)[1]).startswith(b"\xff\xd8")

        async def unexpected_capture(*args):
            pytest.fail("A cached preview should not launch another browser")

        monkeypatch.setattr(preview, "_capture_preview", unexpected_capture)
        assert asyncio.run(preview.page_preview(url)) == result
    finally:
        preview._cache.pop(url, None)


def test_preview_api_explains_errors_without_a_message(monkeypatch):
    from chromaswarm import main

    async def fail(url):
        raise NotImplementedError()

    monkeypatch.setattr(main, "page_preview", fail)
    response = TestClient(main.app).get("/clone/preview", params={"url": "https://example.com"})
    assert response.status_code == 502
    assert "Không thể khởi động trình duyệt" in response.json()["detail"]
