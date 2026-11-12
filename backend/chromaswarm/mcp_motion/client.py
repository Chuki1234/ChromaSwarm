"""MCP client used by the Motion agent (B8.1).

By default it launches ChromaSwarm's own Motion MCP server over stdio. Set
CHROMASWARM_MOTION_MCP to another command (e.g. "npx some-motion-mcp") to use
an external server with the same `build_effect` tool contract.
"""

from __future__ import annotations

import json
import os
import shlex
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel


class MotionEffect(BaseModel):
    effect: str
    section_id: str
    kind: str
    css: str
    notes: str = ""


class MotionError(RuntimeError):
    pass


def server_params(env: dict[str, str] | None = None) -> StdioServerParameters:
    env = dict(os.environ if env is None else env)
    custom = env.get("CHROMASWARM_MOTION_MCP", "").strip()
    if custom:
        cmd, *args = shlex.split(custom)
        return StdioServerParameters(command=cmd, args=args)
    return StdioServerParameters(command=sys.executable, args=["-m", "chromaswarm.mcp_motion.server"])


def _payload(result) -> dict:
    if getattr(result, "is_error", False):
        raise MotionError(" ".join(getattr(c, "text", "") for c in result.content))
    data = getattr(result, "structured_content", None)
    if isinstance(data, dict):
        return data.get("result", data)
    for c in getattr(result, "content", []):
        if getattr(c, "text", None):
            return json.loads(c.text)
    raise MotionError("empty MCP tool result")


async def build_effects(requests: list[tuple[str, str]], duration_ms: int, easing: str,
                        params: StdioServerParameters | None = None, page: str = "") -> list[MotionEffect]:
    """One MCP session, one `build_effect` call per (effect, section_id)."""
    if not requests:
        return []
    out: list[MotionEffect] = []
    error: str | None = None
    async with stdio_client(params or server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for effect, section_id in requests:
                try:
                    data = _payload(await session.call_tool("build_effect", {
                        "effect": effect, "section_id": section_id, "duration_ms": duration_ms,
                        "easing": easing, "page": page}))
                except MotionError as e:
                    error = str(e)
                    break
                if "error" in data:
                    error = data["error"]
                    break
                out.append(MotionEffect(effect=effect, section_id=section_id, kind=data["kind"],
                                        css=data["css"], notes=data.get("notes", "")))
    # Raised outside the stdio task group, so callers get a MotionError, not an ExceptionGroup.
    if error:
        raise MotionError(error)
    return out
