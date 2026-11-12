"""ChromaSwarm Motion MCP server (B8.1 "Motion & 2D/3D MCP Specialist").

A real Model Context Protocol server over stdio. The Motion agent talks to it
through an MCP client, so this server can be swapped for any external MCP
server (GSAP, Three.js, Spline...) that implements the same two tools:

  list_effects()                       -> catalogue of effect ids + descriptions
  build_effect(effect, section_id, duration_ms, easing)
                                       -> {"kind", "css", "notes"}

The built-in effects are dependency-free CSS (no JS bundle, works in every
framework adapter): an entrance reveal and a scroll-driven parallax. Both
respect prefers-reduced-motion and only animate transform/opacity, and the
reveal ends at opacity 1 so B11's "stuck at opacity 0" check stays green.

Run standalone:  uv run python -m chromaswarm.mcp_motion.server
"""

from __future__ import annotations

import re

from mcp.server.mcpserver import MCPServer

server = MCPServer("chromaswarm-motion")

EFFECTS = {
    "reveal": "Entrance reveal: children of the section rise 16px and fade in, staggered 80ms.",
    "parallax": "Scroll-driven parallax: images in the section drift 24px against the scroll (CSS view timeline).",
    "stagger-cards": "Cards and grid items fade up in sequence as the section enters the viewport.",
}
_SAFE_ID = re.compile(r"^[a-z0-9-]{1,64}$")
_SAFE_EASING = re.compile(r"^(cubic-bezier\([0-9.,\s-]+\)|ease|ease-in|ease-out|ease-in-out|linear)$")

REDUCED = "@media (prefers-reduced-motion: reduce) {{ {sel} {{ animation: none !important; }} }}"


def _reveal(sel: str, ms: int, easing: str) -> str:
    return f"""@keyframes cs-reveal {{ from {{ opacity: 0; transform: translateY(16px); }} to {{ opacity: 1; transform: none; }} }}
{sel} .container > * {{ animation: cs-reveal {ms}ms {easing} both; }}
{sel} .container > *:nth-child(2) {{ animation-delay: 80ms; }}
{sel} .container > *:nth-child(3) {{ animation-delay: 160ms; }}
{REDUCED.format(sel=f"{sel} .container > *")}"""


def _parallax(sel: str, ms: int, easing: str) -> str:
    return f"""@keyframes cs-parallax {{ from {{ transform: translateY(24px); }} to {{ transform: translateY(-24px); }} }}
@supports (animation-timeline: view()) {{
  {sel} .art {{ animation: cs-parallax linear both; animation-timeline: view(); animation-range: entry 0% exit 100%; }}
}}
{REDUCED.format(sel=f"{sel} .art")}"""


def _stagger(sel: str, ms: int, easing: str) -> str:
    return f"""@keyframes cs-fade-up {{ from {{ opacity: 0; transform: translateY(12px); }} to {{ opacity: 1; transform: none; }} }}
@supports (animation-timeline: view()) {{
  {sel} .card {{ animation: cs-fade-up linear both; animation-timeline: view(); animation-range: entry 0% entry 60%; }}
}}
{REDUCED.format(sel=f"{sel} .card")}"""


BUILDERS = {"reveal": _reveal, "parallax": _parallax, "stagger-cards": _stagger}


@server.tool()
def list_effects() -> dict:
    """List the motion effects this server can build."""
    return {"effects": EFFECTS}


@server.tool()
def build_effect(effect: str, section_id: str, duration_ms: int = 600,
                 easing: str = "cubic-bezier(0.16, 1, 0.3, 1)", page: str = "") -> dict:
    """Return framework-agnostic CSS that applies `effect` to [data-swarm-section=section_id],
    scoped to [data-swarm-page=page] when a page id is given."""
    if effect not in BUILDERS:
        return {"error": f"unknown effect {effect!r}", "effects": list(EFFECTS)}
    if not _SAFE_ID.match(section_id) or (page and not _SAFE_ID.match(page)) or not _SAFE_EASING.match(easing.strip()):
        return {"error": "section_id, page or easing has unexpected characters"}
    ms = max(120, min(int(duration_ms), 1200))
    sel = (f'[data-swarm-page="{page}"] ' if page else "") + f'[data-swarm-section="{section_id}"]'
    return {"kind": "2d-css", "css": BUILDERS[effect](sel, ms, easing.strip()), "notes": EFFECTS[effect]}


def pick_effect(plan_effect: str) -> str | None:
    """Map a PLAN.md effect description onto a catalogue id."""
    text = plan_effect.lower()
    if "parallax" in text:
        return "parallax"
    if any(w in text for w in ("reveal", "entrance", "xuất hiện")):
        return "reveal"
    if any(w in text for w in ("stagger", "cards", "lần lượt")):
        return "stagger-cards"
    return None


if __name__ == "__main__":
    server.run("stdio")
