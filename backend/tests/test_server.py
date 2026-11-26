import asyncio
import sys

import pytest
import uvicorn

from chromaswarm.clone.reader import analyse
from chromaswarm import server


@pytest.mark.skipif(sys.platform != "win32", reason="Windows reload subprocess regression")
def test_windows_launcher_can_run_the_real_clone_reader(tmp_path, monkeypatch):
    options = {}
    monkeypatch.setattr(sys, "argv", ["chromaswarm.server", "--reload"])
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: options.update(kwargs))
    server.main()
    assert options["reload"] is False
    page = tmp_path / "reference.html"
    page.write_text("<title>Local clone reference</title><main><h1>Clone me</h1><p>Local fixture</p></main>",
                    encoding="utf-8")
    config = uvicorn.Config("chromaswarm.main:app", **options)
    with asyncio.Runner(loop_factory=config.get_loop_factory()) as runner:
        async def read():
            assert isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop)
            return await analyse(page.as_uri(), owned=False)
        result = runner.run(read())
    assert result.title == "Local clone reference"
    assert result.sections
