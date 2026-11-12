"""Target-app workspace on disk + its Next.js dev server.

Writes are tool-gated: a file can only be written when the current pipeline
step grants the matching tool (CLAUDE.md decision 2), so B1-B7 can never emit
code and only the Design department's `write_tokens` touches tokens.css.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import socket
from pathlib import Path

from chromaswarm.developer.nextjs import WorkspaceFile
from chromaswarm.state_machine.pipeline_state import GateError, Step, tools_for

log = logging.getLogger(__name__)
TOKENS_PATH = "app/tokens.css"
FIRST_PORT = 3001


class Workspace:
    def __init__(self, root: Path):
        self.root = root

    def _check(self, step: Step, tool: str) -> None:
        if tool not in tools_for(step):
            raise GateError(f"{tool} is not granted at {step}")

    def write(self, step: Step, f: WorkspaceFile) -> Path:
        tool = "write_tokens" if f.path == TOKENS_PATH else "write_workspace_file"
        self._check(step, tool)
        target = (self.root / f.path).resolve()
        if self.root.resolve() not in target.parents:
            raise GateError(f"refusing to write outside the workspace: {f.path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_text(encoding="utf-8") != f.content:
            target.write_text(f.content, encoding="utf-8")  # unchanged files keep their mtime (no HMR churn)
        return target

    def read(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8")

    async def install(self, step: Step) -> None:
        """npm install, preferring the local cache (a few seconds when Next is already cached)."""
        self._check(step, "run_dev_server")
        if (self.root / "node_modules" / "next").exists():
            return
        proc = await asyncio.create_subprocess_exec(
            "npm", "install", "--prefer-offline", "--no-audit", "--no-fund", cwd=self.root,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await proc.communicate()
        if proc.returncode:
            raise RuntimeError(f"npm install failed:\n{out.decode(errors='replace')[-2000:]}")


def free_port(start: int = FIRST_PORT, limit: int = 100) -> int:
    for port in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"no free port in {start}-{start + limit}")


class DevServer:
    """`next dev` for one workspace, in its own process group so stop() kills the whole tree."""

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.port: int | None = None
        self.proc: asyncio.subprocess.Process | None = None

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    async def start(self, step: Step, timeout: float = 90) -> str:
        self.workspace._check(step, "run_dev_server")
        if self.proc and self.proc.returncode is None:
            return self.url
        self.port = free_port()
        self.proc = await asyncio.create_subprocess_exec(
            "npx", "next", "dev", "-p", str(self.port), cwd=self.workspace.root,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True, env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"})
        await self._wait_ready(timeout)
        return self.url

    async def _wait_ready(self, timeout: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            if self.proc and self.proc.returncode is not None:
                raise RuntimeError("next dev exited during startup")
            with contextlib.suppress(OSError):
                reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
                writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
                await writer.drain()
                status = await asyncio.wait_for(reader.readline(), timeout=60)  # first compile
                writer.close()
                if b" 200 " in status:
                    return
            await asyncio.sleep(0.5)
        raise TimeoutError(f"next dev not ready on {self.url} after {timeout}s")

    async def stop(self) -> None:
        if not self.proc or self.proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(self.proc.wait(), timeout=5)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.proc.pid, signal.SIGKILL)
