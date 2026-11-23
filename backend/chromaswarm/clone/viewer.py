"""A permanent link to every Clone session's built page.

The build's own dev server (localhost:3001…) lives only while that session's build runtime holds it: the next
session takes the port and a backend restart ends it. The link Chroma sends in the chat therefore points at the
backend — `<public>/sessions/<id>/page` — which redirects to a dev server for that session's app
(`workspaces/<id>/app`): the build's own one while it is running, otherwise one started on demand. A few viewers
are kept warm; the least recently opened is stopped beyond that.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections import OrderedDict
from pathlib import Path

from chromaswarm.developer.workspace import DevServer, Workspace
from chromaswarm.state_machine.pipeline_state import Step

SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def public_base() -> str:
    return os.environ.get("CHROMASWARM_PUBLIC_URL", "http://localhost:8100").rstrip("/")


def page_link(session_id: str) -> str:
    return f"{public_base()}/sessions/{session_id}/page"


def app_dir(root: Path, session_id: str) -> Path | None:
    """The session's built app, when there is one that can run (scaffold + installed packages)."""
    if not SAFE_SESSION.match(session_id):
        return None
    app = root / session_id / "app"
    return app if (app / "package.json").exists() and (app / "node_modules").is_dir() else None


class PageViewer:
    def __init__(self, root: Path, runtime=None, keep: int = 3):
        self.root, self.runtime, self.keep = root, runtime, keep
        self._servers: OrderedDict[str, DevServer] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    def _live(self, session_id: str) -> str | None:
        """The build's own dev server, while it still runs."""
        s = getattr(self.runtime, "_sessions", {}).get(session_id) if self.runtime else None
        server = getattr(s, "server", None)
        proc = getattr(server, "proc", None)
        return server.url if server is not None and proc is not None and proc.returncode is None else None

    async def url(self, session_id: str) -> str | None:
        if live := self._live(session_id):
            return live
        app = app_dir(self.root, session_id)
        if app is None:
            return None
        async with self._locks.setdefault(session_id, asyncio.Lock()):
            server = self._servers.get(session_id)
            if server and server.proc and server.proc.returncode is None:
                self._servers.move_to_end(session_id)
                return server.url
            server = DevServer(Workspace(app))
            await server.start(Step.B10_INTEGRATE, timeout=120)  # a viewer only runs the app the build wrote
            self._servers[session_id] = server
            while len(self._servers) > self.keep:
                _, old = self._servers.popitem(last=False)
                await old.stop()
            return server.url

    async def stop_all(self) -> None:
        for s in list(self._servers.values()):
            await s.stop()
        self._servers.clear()
