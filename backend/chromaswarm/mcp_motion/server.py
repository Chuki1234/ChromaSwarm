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
    "scroll-reveal": "Scroll reveal: the section's blocks fade up 24px as they enter the viewport (CSS view timeline).",
    "marquee": "Marquee: a track of items slides sideways forever (duplicated track, paused on hover).",
    "hover-lift": "Hover lift: cards, rows and buttons rise 4px with a deeper shadow.",
    "hover-zoom": "Hover zoom: images inside cards scale up 5% within their frame.",
    "hover-image": "Hover preview: a list row shows its image beside the cursor area on hover.",
    "underline-link": "Link underline that grows from the left on hover.",
    "sticky-blur": "Sticky header over a translucent, blurred background.",
    "smooth-scroll": "Smooth scrolling for in-page links.",
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


def _scroll_reveal(sel: str, ms: int, easing: str) -> str:
    return f"""@keyframes cs-rise {{ from {{ opacity: 0; transform: translateY(24px); }} to {{ opacity: 1; transform: none; }} }}
@supports (animation-timeline: view()) {{
  {sel} .container > * {{ animation: cs-rise linear both; animation-timeline: view(); animation-range: entry 0% entry 70%; }}
}}
{REDUCED.format(sel=f"{sel} .container > *")}"""


def _marquee(sel: str, ms: int, easing: str) -> str:
    return f"""@keyframes cs-marquee {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
{sel} .marquee {{ overflow: hidden; mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent); }}
{sel} .marquee-track {{ display: flex; width: max-content; animation: cs-marquee 32s linear infinite; }}
{sel} .marquee:hover .marquee-track {{ animation-play-state: paused; }}
{REDUCED.format(sel=f"{sel} .marquee-track")}"""


def _hover_lift(sel: str, ms: int, easing: str) -> str:
    items = ", ".join(f"{sel} {x}" for x in (".card", ".text-card", ".quote", ".list-row", ".btn"))
    hovered = ", ".join(f"{sel} {x}:hover" for x in (".card", ".text-card", ".quote", ".btn"))
    return f"""{items} {{ transition: transform {ms}ms {easing}, box-shadow {ms}ms {easing}; }}
@media (hover: hover) {{
  {hovered} {{ transform: translateY(-4px); box-shadow: var(--shadow-md, 0 8px 24px rgb(0 0 0 / .12)); }}
  {sel} .list-row:hover {{ transform: translateX(4px); }}
}}
@media (prefers-reduced-motion: reduce) {{ {items} {{ transition: none; }} }}"""


def _hover_zoom(sel: str, ms: int, easing: str) -> str:
    return f"""{sel} .card, {sel} .gallery-tile {{ overflow: hidden; }}
{sel} .card .art, {sel} .gallery-tile .art {{ transition: transform {max(ms, 400)}ms {easing}; }}
@media (hover: hover) {{ {sel} .card:hover .art, {sel} .gallery-tile:hover .art {{ transform: scale(1.05); }} }}
@media (prefers-reduced-motion: reduce) {{ {sel} .art {{ transition: none; }} }}"""


def _hover_image(sel: str, ms: int, easing: str) -> str:
    return f"""{sel} .list-row {{ position: relative; }}
{sel} .row-preview {{ position: absolute; right: 18%; top: 50%; width: min(260px, 30vw); pointer-events: none; z-index: 2;
  opacity: 0; transform: translateY(-50%) scale(.94) rotate(-2deg); transition: opacity {ms}ms {easing}, transform {ms}ms {easing}; }}
@media (hover: hover) {{ {sel} .list-row:hover .row-preview {{ opacity: 1; transform: translateY(-50%) scale(1) rotate(0); }} }}
@media (hover: none) {{ {sel} .row-preview {{ display: none; }} }}
@media (prefers-reduced-motion: reduce) {{ {sel} .row-preview {{ transition: none; }} }}"""


def _underline(sel: str, ms: int, easing: str) -> str:
    link = f"{sel} a:not(.btn):not(.card)"
    return f"""{link} {{ text-decoration: none; background: linear-gradient(currentColor, currentColor) 0 100% / 0 1px no-repeat;
  transition: background-size {ms}ms {easing}; }}
{link}:hover, {link}:focus-visible {{ background-size: 100% 1px; }}
@media (prefers-reduced-motion: reduce) {{ {link} {{ transition: none; }} }}"""


def _sticky_blur(sel: str, ms: int, easing: str) -> str:
    return f"""{sel} {{ position: sticky; top: 0; z-index: 20; backdrop-filter: saturate(1.4) blur(14px);
  background: color-mix(in oklch, var(--bg-primary) 78%, transparent); }}"""


def _smooth(sel: str, ms: int, easing: str) -> str:
    return """html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }"""


BUILDERS = {"reveal": _reveal, "parallax": _parallax, "stagger-cards": _stagger, "scroll-reveal": _scroll_reveal,
            "marquee": _marquee, "hover-lift": _hover_lift, "hover-zoom": _hover_zoom, "hover-image": _hover_image,
            "underline-link": _underline, "sticky-blur": _sticky_blur, "smooth-scroll": _smooth}


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
