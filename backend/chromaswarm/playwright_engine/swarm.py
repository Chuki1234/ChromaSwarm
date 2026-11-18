"""Python side of the swarm overlay (B8 Design cursors, B11 Master cursor, B12 handover).

`SwarmOverlay` drives `swarm_overlay.js` inside a Playwright page. The script
only returns raw DOM readings; every verdict below (8pt grid, WCAG/APCA, line
length, type scale) is computed here with the deterministic engines, so the
same page always produces the same findings.

`design_pass()` is the Design department's measuring loop: one section at a
time (decision 3: pipelined per section), Layout -> Color -> Typography.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page
from pydantic import BaseModel

from chromaswarm.engines.color import apca_lc, parse_css_color, wcag_contrast
from chromaswarm.engines.spacing import SCALE, snap
from chromaswarm.engines.typography import TypeScale

OVERLAY_JS = (Path(__file__).with_name("swarm_overlay.js")).read_text(encoding="utf-8")
MOBILE_MAX = 767
MIN_GUTTER_MOBILE = 16


class Agent(StrEnum):
    LAYOUT = "layout"
    COLOR = "color"
    TYPOGRAPHY = "typography"
    MOTION = "motion"
    INSPECTOR = "inspector"
    MASTER = "master"


class Rect(BaseModel):
    x: float
    y: float
    w: float
    h: float


class BoxMeasure(BaseModel):
    rect: Rect
    padding: list[float]  # top right bottom left
    margin: list[float]
    gap: float
    viewport_w: int
    content_left: float | None = None  # leftmost text/image box inside the element


class ColorReading(BaseModel):
    fg: str
    bg: str
    font_size: float
    font_weight: float
    rect: Rect
    wcag: float | None = None
    apca: float | None = None


class TypeReading(BaseModel):
    font_family: str
    font_size: float
    line_height: float | None
    font_weight: float
    letter_spacing: str
    line_ch: int
    rect: Rect


class Finding(BaseModel):
    agent: Agent
    section: str
    selector: str
    rule: str  # grid-8pt | gutter-mobile | contrast | line-length | type-scale | missing
    detail: str
    value: float | None = None  # the measured px value, for spacing findings
    reading: ColorReading | None = None  # the colour pair, for contrast findings


class SectionReport(BaseModel):
    section: str
    box: BoxMeasure | None = None
    colors: list[ColorReading] = []
    type: list[TypeReading] = []
    findings: list[Finding] = []


class DesignPassReport(BaseModel):
    viewport_w: int
    sections: list[SectionReport]

    @property
    def findings(self) -> list[Finding]:
        return [f for s in self.sections for f in s.findings]


EventSink = Callable[[dict[str, Any]], Awaitable[None] | None]


class SwarmOverlay:
    """Thin async wrapper over `window.__chromaSwarm`."""

    def __init__(self, page: Page, on_event: EventSink | None = None):
        self.page = page
        self.on_event = on_event

    @classmethod
    async def attach(cls, page: Page, *, instant: bool = False, speed: float = 1.0,
                     on_event: EventSink | None = None) -> SwarmOverlay:
        """Install for this page and every later navigation of its context."""
        await page.context.add_init_script(script=OVERLAY_JS)
        await page.evaluate(OVERLAY_JS)  # the current document, if already loaded
        await page.evaluate("""() => new Promise(r => document.readyState === 'complete'
                               ? r() : addEventListener('load', () => r(), {once: true}))""")
        overlay = cls(page, on_event)
        await overlay._call("configure", {"instant": instant, "speed": speed})
        await overlay._call("install")
        return overlay

    @staticmethod
    async def install_on(context: BrowserContext) -> None:
        await context.add_init_script(script=OVERLAY_JS)

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.on_event:
            res = self.on_event(event)
            if res is not None:
                await res

    async def _call(self, method: str, *args: Any) -> Any:
        return await self.page.evaluate(f"(args) => window.__chromaSwarm.{method}(...args)", list(args))

    # ---------------------------------------------------------------- cursors
    async def move(self, agent: Agent, selector: str) -> Rect | None:
        raw = await self._call("moveTo", agent.value, selector)
        await self._emit({"agent": agent.value, "action": "move", "selector": selector})
        return Rect(**raw) if raw else None

    async def measure(self, agent: Agent, selector: str) -> BoxMeasure | None:
        raw = await self._call("measure", agent.value, selector)
        m = BoxMeasure(**raw) if raw else None
        await self._emit({"agent": agent.value, "action": "measure", "selector": selector,
                          "result": m.model_dump() if m else None})
        return m

    async def color(self, selector: str) -> ColorReading | None:
        raw = await self._call("color", Agent.COLOR.value, selector)
        if not raw:
            return None
        r = ColorReading(**raw)
        fg, bg = parse_css_color(r.fg), parse_css_color(r.bg)
        if fg and bg:
            r.wcag = round(wcag_contrast(fg[0], bg[0]), 2)
            r.apca = round(apca_lc(fg[0], bg[0]), 1)
        await self.note(Agent.COLOR, f"WCAG {r.wcag} · Lc {r.apca}" if r.wcag is not None else "màu không đọc được")
        await self._emit({"agent": "color", "action": "color", "selector": selector, "result": r.model_dump()})
        return r

    async def typography(self, selector: str) -> TypeReading | None:
        raw = await self._call("typography", Agent.TYPOGRAPHY.value, selector)
        t = TypeReading(**raw) if raw else None
        await self._emit({"agent": "typography", "action": "typography", "selector": selector,
                          "result": t.model_dump() if t else None})
        return t

    async def note(self, agent: Agent | str, text: str | None) -> None:
        await self._call("note", getattr(agent, "value", agent), text)

    # ---------------------------------------------------------------- B11 / B12
    # ---------------------------------------------------------------- factory workers
    async def spawn(self, id_: str, label: str, color: str, parent: str | None = None, size: int = 18) -> None:
        await self._call("spawn", id_, label, color, parent, size)

    async def fly_to(self, id_: str, selector: str) -> Rect | None:
        raw = await self._call("flyTo", id_, selector)
        return Rect(**raw) if raw else None

    async def crew(self, items: list[dict]) -> int:
        """items: {id, label, color, from, sel, note, ok}: leaf workers, flown together per viewport."""
        return await self._call("crew", items)

    async def merge(self, ids: list[str], into: str) -> None:
        await self._call("merge", ids, into)

    async def retire(self, id_: str) -> None:
        await self._call("retire", id_)

    async def master(self, on: bool = True) -> None:
        await self._call("master", on)
        await self._emit({"agent": "master", "action": "master", "on": on})

    async def hud(self, text: str | None) -> None:
        await self._call("hud", text)

    async def pulse(self) -> None:
        await self._call("pulse")

    async def flag(self, selector: str, text: str) -> bool:
        ok = await self._call("flag", selector, text)
        await self._emit({"agent": "master", "action": "flag", "selector": selector, "text": text})
        return bool(ok)

    async def clear(self, kind: str | None = None) -> None:
        await self._call("clear", kind)

    async def handover(self) -> None:
        await self._call("handover")
        await self._emit({"agent": "master", "action": "handover"})

    async def resume(self) -> None:
        await self._call("resume")

    async def state(self) -> dict[str, Any]:
        return await self._call("state")


# -------------------------------------------------------------------- verdicts

def _is_large(font_px: float, weight: float) -> bool:
    return font_px >= 24 or (font_px >= 18.66 and weight >= 700)


def contrast_finding(section: str, selector: str, r: ColorReading) -> Finding | None:
    """WCAG 2 AA plus the APCA floor used by the palette engine (body Lc 60, large Lc 45)."""
    if r.wcag is None or r.apca is None:
        return Finding(agent=Agent.COLOR, section=section, selector=selector, rule="contrast",
                       detail=f"không đọc được màu ({r.fg} trên {r.bg})")
    need_w, need_a = (3.0, 45) if _is_large(r.font_size, r.font_weight) else (4.5, 60)
    if r.wcag >= need_w and abs(r.apca) >= need_a:
        return None
    return Finding(agent=Agent.COLOR, section=section, selector=selector, rule="contrast", reading=r,
                   detail=f"WCAG {r.wcag} (cần ≥{need_w}), APCA Lc {abs(r.apca)} (cần ≥{need_a})")


def spacing_findings(section: str, selector: str, m: BoxMeasure) -> list[Finding]:
    out: list[Finding] = []
    values = {"padding-top": m.padding[0], "padding-bottom": m.padding[2], "gap": m.gap}
    for name, v in values.items():
        if v >= 3 and round(v) not in SCALE:
            out.append(Finding(agent=Agent.LAYOUT, section=section, selector=selector, rule="grid-8pt", value=v,
                               detail=f"{name} {v:g}px không thuộc lưới 8pt (gần nhất: {snap(v)}px)"))
    if m.viewport_w <= MOBILE_MAX:
        left = m.content_left if m.content_left is not None else m.rect.x + m.padding[3]
        if left < MIN_GUTTER_MOBILE:
            out.append(Finding(agent=Agent.LAYOUT, section=section, selector=selector, rule="gutter-mobile",
                               detail=f"lề trái nội dung {left:g}px < {MIN_GUTTER_MOBILE}px trên mobile"))
    return out


def type_findings(section: str, selector: str, t: TypeReading, scale: TypeScale | None, body: bool,
                  viewport_w: int = 1440) -> list[Finding]:
    out: list[Finding] = []
    lines = round(t.rect.h / t.line_height) if t.line_height else 1
    # Too long is always wrong. Too short only matters for running text (3+ lines) on screens
    # wide enough to reach 45ch: a 375px phone fits ~40ch of 16px text by construction.
    too_short = t.line_ch < 45 and lines >= 3 and viewport_w > MOBILE_MAX
    if body and (t.line_ch > 72 or too_short):
        out.append(Finding(agent=Agent.TYPOGRAPHY, section=section, selector=selector, rule="line-length",
                           detail=f"dòng chữ dài {t.line_ch}ch (chuẩn 45–72ch)"))
    if scale:
        ok = any(min(s.px_min, s.px_max) - 0.6 <= t.font_size <= max(s.px_min, s.px_max) + 0.6 for s in scale.steps)
        if not ok:
            out.append(Finding(agent=Agent.TYPOGRAPHY, section=section, selector=selector, rule="type-scale",
                               detail=f"cỡ chữ {t.font_size:g}px không thuộc thang chữ của DESIGN.md"))
    return out


TARGETS_JS = """(section) => {
  const root = document.querySelector(`[data-swarm-section="${CSS.escape(section)}"]`);
  if (!root) return null;
  const base = `[data-swarm-section="${CSS.escape(section)}"]`;
  const out = { heading: null, body: null, interactive: [] };
  if (root.querySelector('h1,h2,h3')) out.heading = `${base} :is(h1,h2,h3)`;
  if (root.querySelector('p')) out.body = `${base} p`;
  for (const el of root.querySelectorAll('[data-swarm-id]'))
    out.interactive.push(`[data-swarm-id="${CSS.escape(el.getAttribute('data-swarm-id'))}"]`);
  return out;
}"""


async def design_pass(overlay: SwarmOverlay, scale: TypeScale | None = None,
                      sections: list[str] | None = None) -> DesignPassReport:
    """Run the Design cursors over each `[data-swarm-section]`, top to bottom."""
    page = overlay.page
    if sections is None:
        sections = await page.evaluate(
            "() => [...document.querySelectorAll('[data-swarm-section]')].map(e => e.getAttribute('data-swarm-section'))")
    reports: list[SectionReport] = []
    vw = await page.evaluate("() => innerWidth")
    for sid in sections:
        sel = f'[data-swarm-section="{sid}"]'
        rep = SectionReport(section=sid)
        targets = await page.evaluate(TARGETS_JS, sid)
        if targets is None:
            rep.findings.append(Finding(agent=Agent.LAYOUT, section=sid, selector=sel, rule="missing",
                                        detail="section có trong PLAN.md nhưng chưa có trên trang"))
            reports.append(rep)
            continue

        rep.box = await overlay.measure(Agent.LAYOUT, sel)
        if rep.box:
            rep.findings += spacing_findings(sid, sel, rep.box)

        for target in [t for t in (targets["heading"], targets["body"]) if t] + targets["interactive"][:3]:
            reading = await overlay.color(target)
            if reading:
                rep.colors.append(reading)
                if f := contrast_finding(sid, target, reading):
                    rep.findings.append(f)

        for target, is_body in ((targets["heading"], False), (targets["body"], True)):
            if not target:
                continue
            t = await overlay.typography(target)
            if t:
                rep.type.append(t)
                rep.findings += type_findings(sid, target, t, scale, is_body, vw)

        status = "✓" if not rep.findings else f"{len(rep.findings)} lỗi"
        await overlay.note(Agent.LAYOUT, f"{sid}: {status}")
        reports.append(rep)
    return DesignPassReport(viewport_w=vw, sections=reports)
