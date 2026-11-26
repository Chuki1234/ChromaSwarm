"""ChromaSwarm Motion MCP server (B8.1 "Motion & 2D/3D MCP Specialist").

A real Model Context Protocol server over stdio. The Motion agent talks to it
through an MCP client, so this server can be swapped for any external MCP
server (GSAP, Three.js, Spline...) that implements the same two tools:

  list_effects()                       -> catalogue of effect ids + descriptions
  build_effect(effect, section_id, duration_ms, easing)
                                       -> {"kind", "css", "notes"}

CSS effects remain dependency-free. build_special_asset(section_id, asset_id, scene)
also emits a React/Three.js renderer, a typed scene component and pinned npm dependencies.
It accepts source GLB/glTF or declarative geometry/camera/lights/tracks; it never invents
geometry from a canvas screenshot. The measured DOM host owns position and spacing.

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


def _reveal(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    d, gap = (p or {}).get("distance_px", 16), (p or {}).get("stagger_ms", 80)
    return f"""@keyframes cs-reveal-{d} {{ from {{ opacity: 0; transform: translateY({d}px); }} to {{ opacity: 1; transform: none; }} }}
{sel} .container > * {{ animation: cs-reveal-{d} {ms}ms {easing} both; }}
{sel} .container > *:nth-child(2) {{ animation-delay: {gap}ms; }}
{sel} .container > *:nth-child(3) {{ animation-delay: {gap * 2}ms; }}
{REDUCED.format(sel=f"{sel} .container > *")}"""


def _parallax(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    d = (p or {}).get("distance_px", 24)
    return f"""@keyframes cs-parallax-{d} {{ from {{ transform: translateY({d}px); }} to {{ transform: translateY(-{d}px); }} }}
@supports (animation-timeline: view()) {{
  {sel} .art {{ animation: cs-parallax-{d} linear both; animation-timeline: view(); animation-range: entry 0% exit 100%; }}
}}
{REDUCED.format(sel=f"{sel} .art")}"""


def _stagger(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    d, gap = (p or {}).get("distance_px", 12), (p or {}).get("stagger_ms", 0)
    if gap:  # measured on the reference: each card starts `gap` ms after the previous one
        # Scroll-driven animations ignore time delays: the measured gap becomes a later start in the entry range.
        step = max(2, min(round(gap / 25), 10))
        delays = "\n".join(f"  {sel} .card:nth-child({i}) {{ animation-range: entry {step * (i - 1)}% entry {min(100, 80 + step * (i - 1))}%; }}"
                           for i in range(2, 9))
        return f"""@keyframes cs-fade-up-{d} {{ from {{ opacity: 0; transform: translateY({d}px); }} to {{ opacity: 1; transform: none; }} }}
@supports (animation-timeline: view()) {{
  {sel} .card {{ animation: cs-fade-up-{d} {ms}ms {easing} both; animation-timeline: view(); animation-range: entry 0% entry 80%; }}
{delays}
}}
{REDUCED.format(sel=f"{sel} .card")}"""
    return f"""@keyframes cs-fade-up-{d} {{ from {{ opacity: 0; transform: translateY({d}px); }} to {{ opacity: 1; transform: none; }} }}
@supports (animation-timeline: view()) {{
  {sel} .card {{ animation: cs-fade-up-{d} linear both; animation-timeline: view(); animation-range: entry 0% entry 60%; }}
}}
{REDUCED.format(sel=f"{sel} .card")}"""


def _scroll_reveal(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    d = (p or {}).get("distance_px", 24)
    return f"""@keyframes cs-rise-{d} {{ from {{ opacity: 0; transform: translateY({d}px); }} to {{ opacity: 1; transform: none; }} }}
@supports (animation-timeline: view()) {{
  {sel} .container > * {{ animation: cs-rise-{d} linear both; animation-timeline: view(); animation-range: entry 0% entry 70%; }}
}}
{REDUCED.format(sel=f"{sel} .container > *")}"""


def _marquee(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    cycle = (p or {}).get("cycle_s", 32)
    return f"""@keyframes cs-marquee {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
{sel} .marquee {{ overflow: hidden; mask-image: linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent); }}
{sel} .marquee-track {{ display: flex; width: max-content; animation: cs-marquee {cycle:g}s linear infinite; }}
{sel} .marquee:hover .marquee-track {{ animation-play-state: paused; }}
{REDUCED.format(sel=f"{sel} .marquee-track")}"""


def _hover_lift(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    items = ", ".join(f"{sel} {x}" for x in (".card", ".text-card", ".quote", ".list-row", ".btn"))
    hovered = ", ".join(f"{sel} {x}:hover" for x in (".card", ".text-card", ".quote", ".btn"))
    lift, scale = (p or {}).get("distance_px", 4), (p or {}).get("scale", 0)
    move = f"translateY(-{lift}px)" + (f" scale({scale})" if scale else "")
    return f"""{items} {{ transition: transform {ms}ms {easing}, box-shadow {ms}ms {easing}; }}
@media (hover: hover) {{
  {hovered} {{ transform: {move}; box-shadow: var(--shadow-md, 0 8px 24px rgb(0 0 0 / .12)); }}
  {sel} .list-row:hover {{ transform: translateX(4px); }}
}}
@media (prefers-reduced-motion: reduce) {{ {items} {{ transition: none; }} }}"""


def _hover_zoom(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    zoom = (p or {}).get("scale", 1.05)
    return f"""{sel} .card, {sel} .gallery-tile {{ overflow: hidden; }}
{sel} .card .art, {sel} .gallery-tile .art {{ transition: transform {max(ms, 400)}ms {easing}; }}
@media (hover: hover) {{ {sel} .card:hover .art, {sel} .gallery-tile:hover .art {{ transform: scale({zoom}); }} }}
@media (prefers-reduced-motion: reduce) {{ {sel} .art {{ transition: none; }} }}"""


def _hover_image(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    return f"""{sel} .list-row {{ position: relative; }}
{sel} .row-preview {{ position: absolute; right: 18%; top: 50%; width: min(260px, 30vw); pointer-events: none; z-index: 2;
  opacity: 0; transform: translateY(-50%) scale(.94) rotate(-2deg); transition: opacity {ms}ms {easing}, transform {ms}ms {easing}; }}
@media (hover: hover) {{ {sel} .list-row:hover .row-preview {{ opacity: 1; transform: translateY(-50%) scale(1) rotate(0); }} }}
@media (hover: none) {{ {sel} .row-preview {{ display: none; }} }}
@media (prefers-reduced-motion: reduce) {{ {sel} .row-preview {{ transition: none; }} }}"""


def _underline(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    link = f"{sel} a:not(.btn):not(.card)"
    return f"""{link} {{ text-decoration: none; background: linear-gradient(currentColor, currentColor) 0 100% / 0 1px no-repeat;
  transition: background-size {ms}ms {easing}; }}
{link}:hover, {link}:focus-visible {{ background-size: 100% 1px; }}
@media (prefers-reduced-motion: reduce) {{ {link} {{ transition: none; }} }}"""


def _sticky_blur(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    blur = (p or {}).get("blur_px", 14)
    return f"""{sel} {{ position: sticky; top: 0; z-index: 20; backdrop-filter: saturate(1.4) blur({blur}px);
  background: color-mix(in oklch, var(--bg-primary) 78%, transparent); }}"""


def _smooth(sel: str, ms: int, easing: str, p: dict | None = None) -> str:
    return """html { scroll-behavior: smooth; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }"""


BUILDERS = {"reveal": _reveal, "parallax": _parallax, "stagger-cards": _stagger, "scroll-reveal": _scroll_reveal,
            "marquee": _marquee, "hover-lift": _hover_lift, "hover-zoom": _hover_zoom, "hover-image": _hover_image,
            "underline-link": _underline, "sticky-blur": _sticky_blur, "smooth-scroll": _smooth}


@server.tool()
def list_effects() -> dict:
    """List the motion effects this server can build."""
    return {"effects": {**EFFECTS, "threejs-scene": "Measured special asset: glTF/GLB or declarative Three.js scene, resize-aware and reduced-motion safe."}}


@server.tool()
def build_special_asset(section_id: str, asset_id: str, scene: dict) -> dict:
    """Generate React/Three.js source files from measured scene data. The native DOM host controls layout.
    scene: model_url (GLB/glTF) or objects (geometry, size, material, transforms), camera, lights, animation tracks.
    Missing geometry is reported, never replaced with an invented scene."""
    from chromaswarm.mcp_motion.special import build_special
    return build_special(section_id, asset_id, scene)


@server.tool()
def build_effect(effect: str, section_id: str, duration_ms: int = 600,
                 easing: str = "cubic-bezier(0.16, 1, 0.3, 1)", page: str = "", distance_px: int = 0,
                 scale: float = 0, cycle_s: float = 0, stagger_ms: int = 0, blur_px: int = 0) -> dict:
    """Return framework-agnostic CSS that applies `effect` to [data-swarm-section=section_id],
    scoped to [data-swarm-page=page] when a page id is given. The optional measured parameters (a Clone
    reads them off the reference) shape the effect: travel distance / lift (px), scale or zoom, marquee
    cycle (s), stagger delay (ms), header blur (px)."""
    if effect not in BUILDERS:
        return {"error": f"unknown effect {effect!r}", "effects": list(EFFECTS)}
    if not _SAFE_ID.match(section_id) or (page and not _SAFE_ID.match(page)) or not _SAFE_EASING.match(easing.strip()):
        return {"error": "section_id, page or easing has unexpected characters"}
    ms = max(120, min(int(duration_ms), 1500))
    p: dict = {}
    if distance_px:
        p["distance_px"] = max(2, min(int(distance_px), 120))
    if scale:
        p["scale"] = round(max(0.8, min(float(scale), 1.3)), 3)
    if cycle_s:
        p["cycle_s"] = round(max(4.0, min(float(cycle_s), 180.0)), 1)
    if stagger_ms:
        p["stagger_ms"] = max(20, min(int(stagger_ms), 600))
    if blur_px:
        p["blur_px"] = max(2, min(int(blur_px), 40))
    sel = (f'[data-swarm-page="{page}"] ' if page else "") + f'[data-swarm-section="{section_id}"]'
    return {"kind": "2d-css", "css": BUILDERS[effect](sel, ms, easing.strip(), p), "notes": EFFECTS[effect]}


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
