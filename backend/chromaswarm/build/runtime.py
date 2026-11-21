"""B8-B10 runtime: owns the per-session resources the graph must not checkpoint
(workspace on disk, `next dev` process, Playwright browser + swarm overlay).

`BuildRuntime` is the interface the graph nodes call; `LocalBuildRuntime` is
the real implementation. Tests inject a fake with the same methods.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from playwright.async_api import Browser, Page, Playwright, async_playwright
from playwright.async_api import Error as PlaywrightError
from pydantic import BaseModel

from chromaswarm.agents.planner import Section
from chromaswarm.design.dept import TokenChange, TokenFile, fix_contrast, repair
from chromaswarm.developer.content import PageCopy, copy_for
from chromaswarm.developer.order import order_file
from chromaswarm.developer.nextjs import routes_file
from chromaswarm.developer.nextjs import (WorkspaceFile, content_file, heal_file, images_file, match_file, motion_file,
                                         page_file, render_section, scaffold, skeleton, style_file, style_pages,
                                         wireframe_file)
from chromaswarm.clone import components as cmp
from chromaswarm.clone import motion as motion_probe
from chromaswarm.clone.motion_check import build_report as motion_report
from chromaswarm.playwright_engine.style_dna_scraper import SETTLE_JS
from chromaswarm.mcp_motion.client import MotionEffect, build_effects
from chromaswarm.mcp_motion.server import pick_effect
from chromaswarm.developer.workspace import STYLE_PATH, TOKENS_PATH, DevServer, Workspace
from chromaswarm.engines.design_spec import DesignSpec
from chromaswarm.playwright_engine.swarm import Agent, ColorReading, Finding, SwarmOverlay, design_pass
from chromaswarm.clone.fidelity import Fidelity, score, snapshot_page
from chromaswarm.playwright_engine.style_dna_scraper import open_settled
from chromaswarm.qa.critic import Critique, critique
from chromaswarm.qa.master import QaReport, run_master_qa
from chromaswarm.state_machine.pipeline_state import Step

log = logging.getLogger(__name__)


class SectionCheck(BaseModel):
    section: str
    changes: list[TokenChange] = []
    open: list[Finding] = []
    # Clone factory: 1:1 match of this section's components before / after the crews tuned them.
    match_before: float | None = None
    match_after: float | None = None
    tuned: int = 0
    components: int = 0
    crews: list[str] = []


class IntegrationReport(BaseModel):
    missing: list[str] = []
    console_errors: list[str] = []
    open: list[Finding] = []

    @property
    def ok(self) -> bool:
        return not self.missing and not self.console_errors


HandoverChoice = Callable[[str, dict], Awaitable[None]]


class BuildRuntime(Protocol):
    async def install_design_system(self, session: str, tokens_css: str, keep_existing: bool = False) -> None: ...
    async def start_app(self, session: str, project: str, spec: DesignSpec, route: str = "/") -> str: ...
    async def write_section(self, session: str, written: list[Section], copy: PageCopy,
                            page: str = "", route: str = "/") -> None: ...
    async def motion(self, session: str, section: Section, spec: DesignSpec, page: str = "") -> list[MotionEffect]: ...
    async def handover(self, session: str, options: list[dict]) -> None: ...
    async def check_section(self, session: str, section_id: str, spec: DesignSpec) -> SectionCheck: ...
    async def integrate(self, session: str, planned: list[str]) -> IntegrationReport: ...
    async def heal(self, session: str, rules: list[str], contrast: list[dict]) -> list[TokenChange]: ...
    async def master_qa(self, session: str, spec: DesignSpec, creative: bool = False) -> QaReport: ...
    # optional: async def critique(self, session: str, context: str = "") -> Critique | None
    # optional: async def fidelity(self, session: str, reference_url: str, shots: Path | None = None) -> Fidelity | None
    async def close(self, session: str) -> None: ...


@dataclass
class _Session:
    workspace: Workspace
    server: DevServer
    pw: Playwright | None = None
    browser: Browser | None = None
    page: Page | None = None
    overlay: SwarmOverlay | None = None
    console_errors: list[str] = field(default_factory=list)
    base_url: str | None = None
    route: str = "/"
    handed_over: bool = False
    # Template content per page: section id -> (section, its words), in page order (content/<page>.ts).
    content: dict[str, dict[str, tuple[Section, dict]]] = field(default_factory=dict)
    # Designer passes (Clone): wireframe (greys + skeleton copy) -> colour -> content. Photos wait for content.
    wireframe: bool = False
    photos: list[str] = field(default_factory=list)
    # Clone: the reference's components / boxes per section (from B2) and match.css blocks per page+section.
    ref_components: dict[str, list[dict]] = field(default_factory=dict)
    ref_boxes: dict[str, dict] = field(default_factory=dict)
    ref_names: dict[str, str] = field(default_factory=dict)
    ref_page: str = ""
    match: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    shot_pages: dict[int, Page] = field(default_factory=dict)  # clean tabs for the section eye, by width
    checker: Browser | None = None  # hidden browser for checks; closed when the checks of a step pass
    fluid: bool = False  # the window's tab follows the window size (handover) instead of the fixed build size
    page_bg: str | None = None


CREATE_ONLY = {"app/heal.css", "app/motion.css", "app/match.css", "app/style.css", "content/motion.ts"}  # accumulate across pages and heal loops


HANDOVER_BAR_JS = r"""(options) => {
  document.querySelector('chromaswarm-handover')?.remove();
  const host = document.createElement('chromaswarm-handover');
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `<style>
    :host { all: initial; }
    .bar { position: fixed; right: 24px; bottom: 24px; z-index: 2147483647; display: flex; flex-direction: column;
      gap: 8px; padding: 16px; border-radius: 12px; background: rgb(17 17 17 / .94); color: #fff;
      font: 500 13px/1.4 ui-sans-serif, system-ui, sans-serif; box-shadow: 0 8px 24px rgb(0 0 0 / .2); max-width: 320px; }
    p { margin: 0 0 4px; color: rgb(255 255 255 / .75); }
    button { min-height: 44px; padding: 10px 16px; border-radius: 8px; border: 1px solid rgb(255 255 255 / .25);
      background: transparent; color: #fff; font: inherit; text-align: left; cursor: pointer; }
    button:hover { background: rgb(255 255 255 / .1); }
    button:focus-visible { outline: 2px solid #F5B400; outline-offset: 2px; }
    button.primary { background: #F5B400; border-color: #F5B400; color: #111; }
    button.primary:hover { filter: brightness(1.08); }
    button:disabled { opacity: .5; cursor: default; }
    h2 { margin: 0; font-size: 15px; font-weight: 600; color: #fff; }
    textarea { min-height: 72px; padding: 10px 12px; border-radius: 8px; border: 1px solid rgb(255 255 255 / .35);
      background: rgb(255 255 255 / .06); color: #fff; font: inherit; resize: vertical; }
    textarea:focus-visible { outline: 2px solid #F5B400; outline-offset: 2px; }
    .status { color: #F5B400; }
  </style><div class="bar" role="region" aria-label="Bàn giao ChromaSwarm">
    <h2>Đã bàn giao trang</h2>
    <p>Dùng thử ngay trên cửa sổ này, rồi chọn bước tiếp theo:</p></div>`;
  const bar = root.querySelector('.bar');
  const lock = (msg) => {
    bar.querySelectorAll('button, textarea').forEach(x => x.disabled = true);
    const s = document.createElement('p'); s.className = 'status'; s.setAttribute('role', 'status'); s.textContent = msg;
    bar.appendChild(s);
  };
  for (const o of options) {
    const b = document.createElement('button');
    b.textContent = o.label;
    if (o.primary) b.className = 'primary';
    if (o.feedback) {
      // Refine: the feedback is written right here, no need to switch to the Studio.
      b.onclick = () => {
        if (bar.querySelector('textarea')) return;
        const t = document.createElement('textarea');
        t.placeholder = o.placeholder || '';
        t.setAttribute('aria-label', o.label);
        const send = document.createElement('button');
        send.className = 'primary'; send.textContent = o.submit || 'OK';
        send.onclick = () => {
          const text = t.value.trim();
          if (!text) { t.focus(); return; }
          lock(o.sent || '');
          window.__chromaswarmChoice({ ...o.value, feedback: text });
        };
        b.after(t, send);
        t.focus();
      };
    } else {
      b.onclick = () => { lock(o.sent || ''); window.__chromaswarmChoice(o.value); };
    }
    bar.appendChild(b);
  }
  document.body.appendChild(host);
}"""


OUTLINE_JS = r"""() => {
  const line = (el, depth) => {
    const cls = [...el.classList].filter(c => !c.startsWith('swarm')).slice(0, 4).join('.');
    const kids = depth < 3 ? [...el.children].filter(k => !['SCRIPT', 'STYLE', 'svg', 'path'].includes(k.tagName)).slice(0, 6) : [];
    const me = '  '.repeat(depth) + el.tagName.toLowerCase() + (cls ? '.' + cls : '');
    return [me, ...kids.map(k => line(k, depth + 1))].join('\n');
  };
  return [...document.querySelectorAll('[data-swarm-section]')].map(sec => {
    const r = sec.getBoundingClientRect();
    return `## ${sec.dataset.swarmSection} (${Math.round(r.height)}px high)\n` + line(sec, 0).slice(0, 900);
  }).join('\n');
}"""


# For a section's own picture: sticky / fixed elements outside it (the header) are laid out in place,
# so they never cover the section the reviewer is judging.
UNSTICK_JS = r"""(id) => {
  const target = document.querySelector(`[data-swarm-section="${id}"]`);
  for (const el of document.querySelectorAll('body *')) {
    if (target && (target.contains(el) || el.contains(target))) continue;
    const pos = getComputedStyle(el).position;
    if (pos === 'sticky' || pos === 'fixed') el.style.setProperty('position', 'static', 'important');
  }
}"""


class LocalBuildRuntime:
    def __init__(self, root: Path, headed: bool = True, speed: float = 1.5, motion: bool = True):
        self.root = root
        self.headed = headed
        self.speed = speed
        self.motion_enabled = motion
        self.on_choice: HandoverChoice | None = None  # set by the server: B12 choice made in the browser window
        self._sessions: dict[str, _Session] = {}

    def _s(self, session: str) -> _Session:
        if session not in self._sessions:
            ws = Workspace(self.root / session / "app")
            self._sessions[session] = _Session(workspace=ws, server=DevServer(ws))
        return self._sessions[session]

    # -------------------------------------------------------------- B8
    async def install_design_system(self, session: str, tokens_css: str, keep_existing: bool = False) -> None:
        ws = self._s(session).workspace
        if keep_existing and (ws.root / TOKENS_PATH).exists():
            return  # heal loop: keep the Design department's earlier token repairs
        ws.write(Step.B8_DESIGN, WorkspaceFile(path=TOKENS_PATH, content=tokens_css))

    # -------------------------------------------------------------- B9
    async def start_app(self, session: str, project: str, spec: DesignSpec, route: str = "/",
                        photos: list[str] | None = None) -> str:
        s = self._s(session)
        s.photos = list(photos or [])
        uploads = self.root / session / "uploads"  # the user's own photos (Clone B4), served from /images/
        if uploads.is_dir():
            for f in sorted(uploads.iterdir()):
                if f.is_file():
                    s.workspace.copy_file(Step.B9_DEVELOP, f, f"public/images/{f.name}")
        for f in scaffold(project, spec, [] if s.wireframe else photos):
            if f.path in CREATE_ONLY and (s.workspace.root / f.path).exists():
                continue
            s.workspace.write(Step.B9_DEVELOP, f)
        if s.wireframe:
            s.workspace.write(Step.B9_DEVELOP, wireframe_file(spec))
        s.route = route
        page_path = s.workspace.root / page_file([], route=route).path
        if not page_path.exists():
            s.workspace.write(Step.B9_DEVELOP, page_file([], route=route))
        await s.workspace.install(Step.B9_DEVELOP)
        s.base_url = await s.server.start(Step.B9_DEVELOP)
        url = s.base_url.rstrip("/") + (route if route != "/" else "")
        if s.page is None:
            await self._open_window(s, session, url)
        else:
            await s.page.evaluate("() => document.querySelector('chromaswarm-handover')?.remove()")
            if s.fluid:  # the handover tab follows the window; measurements need the fixed desktop size again
                await s.page.set_viewport_size({"width": 1440, "height": 900})
                s.fluid = False
            await s.page.goto(url)
            assert s.overlay
            await s.overlay.resume()  # a new build after B12: the swarm comes back
        s.handed_over = False
        return url

    async def import_uploads(self, session: str, files: list[Path]) -> list[str]:
        """The user's uploaded photos and logo into public/images/; returns their paths in the app."""
        ws = self._s(session).workspace
        out = []
        for f in files:
            ws.copy_file(Step.B9_DEVELOP, f, f"public/images/{f.name}")
            out.append(f"/images/{f.name}")
        return out

    def has_session(self, session: str) -> bool:
        s = self._sessions.get(session)
        return bool(s and s.page)

    async def reopen(self, session: str, url: str, options: list[dict]) -> str | None:
        """After a backend restart, a handed-over page (B12) is served and shown again: same app on
        disk, same port when free, the handover buttons back in the window. Nothing is rewritten."""
        s = self._s(session)
        if s.page or not (s.workspace.root / "package.json").is_file():
            return None
        target = urlparse(url)
        s.route = target.path or "/"
        await s.workspace.install(Step.B9_DEVELOP)  # restarting the server the build step started
        s.base_url = await s.server.start(Step.B9_DEVELOP, port=target.port)
        new_url = s.base_url.rstrip("/") + (s.route if s.route != "/" else "")
        await self._open_window(s, session, new_url, fluid=True)  # the user's window: no build tab first
        await self.handover(session, options)
        return new_url

    async def _open_window(self, s: _Session, session: str, url: str, fluid: bool = False) -> None:
        """The one window the user sees. Build: fixed 1440×900 (Design and QA measure at that size).
        `fluid`: sized by the window itself (handover), so resizing it is real responsive."""
        if s.pw is None:
            s.pw = await async_playwright().start()
        if s.browser is None:
            s.browser = await s.pw.chromium.launch(headless=not self.headed, args=["--window-size=1440,960"])
        s.page = await (s.browser.new_page(no_viewport=True) if fluid
                        else s.browser.new_page(viewport={"width": 1440, "height": 900}))
        s.fluid = fluid
        await self._listen(s, session, s.page)
        await s.page.goto(url)
        s.overlay = await SwarmOverlay.attach(s.page, instant=not self.headed, speed=self.speed)

    async def _checker(self, s: _Session) -> Browser:
        """A hidden browser for every check (section shots, critic, fidelity): nothing pops up on screen,
        the user only ever sees the build / handover window."""
        if s.checker is None or not s.checker.is_connected():
            if s.pw is None:
                s.pw = await async_playwright().start()
            s.checker = await s.pw.chromium.launch(headless=True)
        return s.checker

    async def release_checks(self, session: str) -> None:
        """A step's checks passed: close its hidden tabs and browser (they reopen if a later step needs them)."""
        s = self._sessions.get(session)
        if not s:
            return
        s.shot_pages.clear()
        if s.checker:
            with contextlib.suppress(Exception):
                await s.checker.close()
            s.checker = None

    async def _listen(self, s: _Session, session: str, page: Page) -> None:
        page.on("console", lambda m: s.console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: s.console_errors.append(str(e)))
        await page.expose_binding("__chromaswarmChoice", lambda _src, value: self._choice(session, value))

    async def _choice(self, session: str, value: Any) -> None:
        if self.on_choice and isinstance(value, dict):
            asyncio.get_running_loop().create_task(self.on_choice(session, value))

    async def write_section(self, session: str, written: list[Section], copy: PageCopy,
                            page: str = "", route: str = "/") -> None:
        s = self._s(session)
        section_copy = copy_for(written[-1].structure, [w.structure for w in written[:-1]], copy)
        # Words earlier sections of this page already show: a measured section picks other lines (no repeats).
        earlier = s.content.get(page, {})
        taken = [t for w in written[:-1] if w.id in earlier for t in _strings(earlier[w.id][1])]
        if taken:
            section_copy = section_copy.model_copy(update={"taken": taken})
        self._write_component(s, written[-1], section_copy, page, keep=[w.id for w in written])
        s.workspace.write(Step.B9_DEVELOP, page_file(written, page, route))
        if copy.order:  # the form the page's main button opens (developer/order.py)
            s.workspace.write(Step.B9_DEVELOP, order_file(copy.order))
            s.workspace.write(Step.B9_DEVELOP, routes_file(copy.routes))

    def _write_component(self, s: _Session, section: Section, copy: PageCopy, page: str,
                         keep: list[str] | None = None) -> None:
        """Component + the page's content file (the section's words live there, editable as a template)."""
        words: dict = {}
        s.workspace.write(Step.B9_DEVELOP, render_section(section, copy, page, content=words))
        current = s.content.setdefault(page, {})
        current[section.id] = (section, words[section.id])
        if keep is not None:  # a refined page may have dropped sections: keep only the page's own, in order
            s.content[page] = current = {sid: current[sid] for sid in keep if sid in current}
        s.workspace.write(Step.B9_DEVELOP, self._content_file(s, page))

    def _content_file(self, s: _Session, page: str) -> WorkspaceFile:
        rows = list(s.content.get(page, {}).values())
        if s.wireframe:  # the real words are kept here and written by the content pass
            rows = [(sec, skeleton(words)) for sec, words in rows]
        return content_file(page, rows)

    # -------------------------------------------------------------- designer passes (Clone)
    def begin_wireframe(self, session: str) -> None:
        """The next build starts as a wireframe: greys, skeleton copy, no photos."""
        self._s(session).wireframe = True

    def wireframe_active(self, session: str) -> bool:
        return self._s(session).wireframe

    async def colour(self, session: str) -> None:
        """Colour pass: the design system's real palette replaces the greys (wireframe.css emptied)."""
        s = self._s(session)
        if s.overlay:
            await s.overlay.note(Agent.COLOR, "Tô màu: áp hệ màu DESIGN.md lên wireframe")
        s.workspace.write(Step.B9_DEVELOP, wireframe_file(None))

    async def fill_content(self, session: str) -> None:
        """Content pass: the words of every page and the photos go in."""
        s = self._s(session)
        if s.overlay:
            await s.overlay.note(Agent.TYPOGRAPHY, "Điền nội dung: chữ và ảnh")
        s.wireframe = False
        for page in s.content:
            s.workspace.write(Step.B9_DEVELOP, self._content_file(s, page))
        s.workspace.write(Step.B9_DEVELOP, images_file(s.photos))
        if s.page:
            # Every page's content changed at once: let the dev server finish recompiling, then start from a
            # clean load, so B10 never reads errors from a page caught between the old and the new modules.
            await asyncio.sleep(1.5)
            with contextlib.suppress(Exception):
                await s.page.reload(wait_until="load", timeout=30000)
                await s.page.wait_for_load_state("networkidle", timeout=15000)
            s.console_errors.clear()

    async def refresh_shared(self, session: str, section: Section, copy: PageCopy, pages: list[str]) -> None:
        """Re-render a shared section (the header) on pages built earlier, so their navigation
        links to the page being built now."""
        s = self._s(session)
        for page in pages:
            if not (s.workspace.root / "components" / "sections" / page).exists():
                continue
            if page in s.content:
                self._write_component(s, section, copy, page)
            else:  # page built before a backend restart: its content file is unknown here, keep words inline
                s.workspace.write(Step.B9_DEVELOP, render_section(section, copy, page))

    # -------------------------------------------------------------- B8.1
    async def motion(self, session: str, section: Section, spec: DesignSpec, page: str = "") -> list[MotionEffect]:
        """Motion & 2D/3D MCP Specialist: asks the Motion MCP server for the PLAN.md effect and
        appends the returned CSS to app/motion.css."""
        # The PLAN.md effect (Creative) plus every effect read from the reference (Clone).
        wanted = list(dict.fromkeys(e for e in [pick_effect(section.effect or ""), *section.motion] if e))
        if not self.motion_enabled or not wanted:
            return []
        s = self._s(session)
        if s.overlay:
            await s.overlay.move(Agent.MOTION, f'[data-swarm-section="{section.id}"]')
            await s.overlay.note(Agent.MOTION, f"B8.1 · MCP build_effect({', '.join(wanted)})")
        # Clone: each effect with the parameters measured on the reference (duration, easing, distance...).
        effects = await build_effects([(e, section.id, section.motion_params.get(e, {})) for e in wanted],
                                      spec.motion_duration_ms, spec.motion_easing, page=page)
        current = s.workspace.read("app/motion.css") if (s.workspace.root / "app/motion.css").exists() else ""
        blocks = [b.strip("\n") for b in current.split("\n/* fx */\n")[1:]] if "/* fx */" in current else []
        for fx in effects:
            block = f"/* {page or 'index'} · {fx.section_id} · {fx.effect} */\n{fx.css}".strip("\n")
            if block not in blocks:
                blocks.append(block)
        s.workspace.write(Step.B9_DEVELOP, motion_file(["/* fx */\n" + b for b in blocks]))
        return effects

    # -------------------------------------------------------------- Clone: component factory
    def set_reference(self, session: str, components: dict[str, list[dict]], boxes: dict[str, dict],
                      names: dict[str, str] | None = None, page: str = "") -> None:
        """What the factory tunes to: the reference's smallest pieces per section (read at B2)."""
        s = self._s(session)
        s.ref_components, s.ref_boxes, s.ref_names, s.ref_page = components or {}, boxes or {}, names or {}, page
        page_bg = next((b.get("page") for b in (boxes or {}).values() if b.get("page")), None)
        if page_bg and page_bg != s.page_bg:  # the reference's own page colour behind every section
            s.page_bg = page_bg
            self._write_match(s)

    def _write_match(self, s: _Session) -> None:
        page = f"body {{ background: {s.page_bg}; }}\n" if s.page_bg else ""
        s.workspace.write(Step.B9_DEVELOP, match_file(page + cmp.render_rules(s.match)))

    async def sketch_check(self, session: str, ref_boxes: dict[str, dict], ref_comps: dict[str, list[dict]],
                           out_dir: Path) -> dict | None:
        """B10, before the colour pass: the rebuild's wireframe measured and drawn the way the reference was
        sketched at B2; reference sketch | rebuild sketch per screen, and how much of each reference section's
        sketched area the rebuild covers."""
        from chromaswarm.clone import sketch
        s = self._s(session)
        if not (s.page and s.browser):
            return None
        with contextlib.suppress(Exception):
            await s.page.reload(wait_until="load", timeout=30000)
        built, boxes = await self._built_components(s)
        built_raw = {k: [c.model_dump() for c in v] for k, v in built.items()}
        result = sketch.compare_sketches(ref_boxes, ref_comps, boxes, built_raw)
        out_dir.mkdir(parents=True, exist_ok=True)
        ref_h = int(max((b.get("top", 0) + b.get("height", 0) for b in ref_boxes.values()), default=900))
        built_h = int(await s.page.evaluate("document.documentElement.scrollHeight"))
        ref_svg = sketch.draw(ref_boxes, ref_comps, ref_h)
        built_svg = sketch.draw(boxes, built_raw, built_h, title=f"Khớp sketch {result['score']:g}%")
        (out_dir / "built.svg").write_text(built_svg, encoding="utf-8")
        # What the eye sees too: the wireframe's screenshot against the reference's (B2), cell by cell.
        built_shot = await s.page.screenshot(full_page=True, type="jpeg", quality=70)
        (out_dir / "built.jpg").write_bytes(built_shot)
        ref_shot_path = out_dir / "reference.jpg"
        ctx = await s.browser.new_context(viewport={"width": 1440, "height": 900})
        try:
            page = await ctx.new_page()
            result["pairs"] = await sketch.sketch_pairs_built(page, ref_svg, built_svg, max(ref_h, built_h), out_dir)
            if ref_shot_path.is_file():
                ref_shot = ref_shot_path.read_bytes()
                work = await ctx.new_page()
                ref_cells, ref_px_h = await sketch.content_cells(work, ref_shot)
                built_cells, built_px_h = await sketch.content_cells(work, built_shot)
                px = sketch.compare_pixels(ref_cells, built_cells, ref_boxes, boxes)
                result["pixel_score"], result["pixel_sections"], result["missing"] = px["score"], px["sections"], px["missing"]
                framed = sketch.shot_with_frames(sketch._data_url(built_shot, "image/jpeg"), 1440, built_px_h, px["missing"],
                                                 f"Giống ảnh chụp {px['score']:g}%")
                result["shot_pairs"] = await sketch.shot_pairs(page, ref_shot, framed, max(ref_px_h, built_px_h), out_dir)
        finally:
            await ctx.close()
        return result

    async def _built_components(self, s: _Session) -> tuple[dict[str, list[cmp.Comp]], dict[str, dict]]:
        assert s.page
        raw = await s.page.evaluate(cmp.COMPONENTS_JS, {"boxes": [], "built": True, "limit": 260})
        return {k: cmp.comps(v) for k, v in raw["comps"].items()}, raw["boxes"]

    async def _factory(self, s: _Session, section_id: str, index: int) -> SectionCheck | None:
        """Section cursor -> crews (type / actions / media) -> one cursor per component. Each component is
        measured against its reference counterpart; the crews' differences are tuned into match.css, the
        section is measured again, and the workers merge back into the section cursor."""
        ref = cmp.comps(s.ref_components.get(section_id, []))
        ref_box = s.ref_boxes.get(section_id)
        if not ref or not ref_box or not s.overlay or not s.page:
            return None
        ov = s.overlay
        built, boxes = await self._built_components(s)
        mine, box = built.get(section_id, []), boxes.get(section_id)
        if not box:
            return None
        before, pairs = cmp.section_score(section_id, ref, mine, ref_box, box)
        sec_id = f"sec-{section_id}"
        name = s.ref_names.get(section_id, section_id)
        await ov.spawn(sec_id, f"S{index} · {name}", "#F5B400", Agent.LAYOUT.value, 26)
        await ov.fly_to(sec_id, f'[data-swarm-section="{section_id}"]')
        await ov.note(sec_id, f"{len(mine)} component · khớp {before.score:.0f}%")
        by_built = {p.built.i: p for p in pairs}
        crews_used: list[str] = []
        leaf_ids: dict[str, list[str]] = {}
        for crew, (label, color, kinds) in cmp.CREWS.items():
            members = [c for c in mine if c.kind in kinds]
            if not members:
                continue
            crew_id = f"crew-{section_id}-{crew}"
            crews_used.append(f"{label} ({len(members)})")
            await ov.spawn(crew_id, f"{label} · {len(members)}", color, sec_id, 20)
            await ov.fly_to(crew_id, f'[data-cs-comp="{section_id}:{members[0].i}"]')
            items = []
            for c in members:
                pair = by_built.get(c.i)
                note = (cmp.KIND_LABEL[c.kind] + (": " + ", ".join(pair.diffs[:2]) if pair and pair.diffs else
                                                  " ✓" if pair else ": không có ở trang mẫu"))
                items.append({"id": f"c-{section_id}-{c.i}", "label": cmp.KIND_LABEL[c.kind], "color": color, "from": crew_id,
                              "sel": f'[data-cs-comp="{section_id}:{c.i}"]', "note": note,
                              "ok": bool(pair and not pair.diffs)})
            await ov.crew(items)
            leaf_ids[crew_id] = [it["id"] for it in items]
        rules = cmp.tune_rules(section_id, pairs, s.ref_page)
        key = f"{s.ref_page}:{section_id}"
        s.match[key], tuned = cmp.merge_rules(s.match.get(key, {}), rules)
        after = before
        if tuned:
            await ov.note(sec_id, f"Tinh chỉnh {tuned} thuộc tính theo trang mẫu…")
            self._write_match(s)
            await asyncio.sleep(1.2)  # HMR applies match.css
            built, boxes = await self._built_components(s)
            if boxes.get(section_id):
                after, _ = cmp.section_score(section_id, ref, built.get(section_id, []), ref_box, boxes[section_id])
        for crew_id, ids in leaf_ids.items():
            await ov.merge(ids, crew_id)
        await ov.merge(list(leaf_ids), sec_id)
        await ov.note(sec_id, f"Khớp {before.score:.0f}% → {after.score:.0f}%")
        await asyncio.sleep(0.4)
        await ov.retire(sec_id)
        return SectionCheck(section=section_id, match_before=before.score, match_after=after.score, tuned=tuned,
                            components=len(mine), crews=crews_used)

    async def motion_js(self, session: str, page: str, section_id: str, effects: list[str]) -> list[str]:
        """GSAP / Three.js effects for a Creative section: listed in content/motion.ts, played by
        components/Motion.tsx. Returns the effects written."""
        from chromaswarm.developer.motion_js import motion_config, parse_config
        if not self.motion_enabled or not effects:
            return []
        s = self._s(session)
        path = "content/motion.ts"
        pages = parse_config(s.workspace.read(path)) if (s.workspace.root / path).exists() else {}
        pages.setdefault(page or "index", {})[section_id] = effects
        s.workspace.write(Step.B9_DEVELOP, WorkspaceFile(path=path, content=motion_config(pages)))
        if s.overlay:
            await s.overlay.move(Agent.MOTION, f'[data-swarm-section="{section_id}"]')
            await s.overlay.note(Agent.MOTION, f"B8.1 · GSAP / Three.js: {', '.join(effects)}")
        return effects

    async def _wait_for(self, s: _Session, selector: str, timeout_ms: int = 30000) -> bool:
        assert s.page
        with contextlib.suppress(Exception):
            await s.page.wait_for_selector(selector, timeout=timeout_ms, state="attached")
            return True
        return False

    async def check_section(self, session: str, section_id: str, spec: DesignSpec) -> SectionCheck:
        s = self._s(session)
        assert s.overlay and s.page
        sel = f'[data-swarm-section="{section_id}"]'
        if not await self._wait_for(s, sel):  # HMR not landed yet: reload once
            await s.page.reload()
            await self._wait_for(s, sel, 15000)
        for attempt in range(3):
            try:
                report = (await design_pass(s.overlay, spec.typography, sections=[section_id])).sections[0]
                break
            except PlaywrightError as e:
                # Writing the next section rewrites the page's content file, and the dev server may do a
                # full reload while Design is still measuring: wait for the new page and measure again.
                if attempt == 2 or "context was destroyed" not in str(e) and "navigat" not in str(e):
                    raise
                with contextlib.suppress(Exception):
                    await s.page.wait_for_load_state("load", timeout=15000)
                await self._wait_for(s, sel, 15000)
        tokens = TokenFile(s.workspace.read(TOKENS_PATH))
        changes, leftover = repair(report, tokens)
        if changes:
            s.workspace.write(Step.B9_DEVELOP, WorkspaceFile(path=TOKENS_PATH, content=tokens.css))
            await s.overlay.note(Agent.COLOR, f"tokens.css: {', '.join(c.token for c in changes)}")
            await asyncio.sleep(1.0)  # HMR applies the stylesheet
            report = (await design_pass(s.overlay, spec.typography, sections=[section_id])).sections[0]
            leftover = report.findings
        with contextlib.suppress(PlaywrightError):  # the next section's write may reload the page meanwhile
            await s.overlay.clear()
        factory = None
        if s.ref_components.get(section_id):
            try:
                index = list(s.ref_boxes).index(section_id) + 1 if section_id in s.ref_boxes else 0
                factory = await self._factory(s, section_id, index)
            except PlaywrightError as e:  # the page reloaded under the crews (next section written): skip
                log.info("factory skipped for %s: %s", section_id, e)
            with contextlib.suppress(Exception):
                await s.overlay.clear()
        out = SectionCheck(section=section_id, changes=changes, open=leftover)
        if factory:
            out = out.model_copy(update=factory.model_dump(include={"match_before", "match_after", "tuned", "components", "crews"}))
        return out

    async def _wait_for_heal_css(self, s: _Session, tries: int = 6) -> None:
        """QA after a heal loop must judge the patched page: wait until the last heal rule is in the page's
        stylesheets (the dev server may still be recompiling heal.css), reloading between tries."""
        path = s.workspace.root / "app/heal.css"
        rules = [ln for ln in (path.read_text(encoding="utf-8").splitlines() if path.exists() else [])
                 if ln.strip() and not ln.startswith("/*")]
        if not rules or not s.page:
            return
        marker = rules[-1].split("{")[0].strip().split()[0][:60]  # e.g. [data-swarm-id="footer-newsletter-input"]
        probe = ("(m) => [...document.styleSheets].some(sh => { try { return [...sh.cssRules]"
                 ".some(r => r.cssText.includes(m)); } catch { return false; } })")
        for _ in range(tries):
            with contextlib.suppress(Exception):
                if await s.page.evaluate(probe, marker):
                    return
            await asyncio.sleep(1)
            with contextlib.suppress(Exception):
                await s.page.reload(wait_until="load", timeout=30000)
                await s.page.wait_for_load_state("networkidle", timeout=15000)
        log.warning("heal.css rule %s not in the page after %d tries", marker, tries)

    async def heal(self, session: str, rules: list[str], contrast: list[dict]) -> list[TokenChange]:
        """B9 after a failed B11: Developer writes heal.css, Design repairs contrast in tokens.css."""
        s = self._s(session)
        existing = s.workspace.read("app/heal.css").splitlines() if (s.workspace.root / "app/heal.css").exists() else []
        kept = [line for line in existing if line and not line.startswith("/*")]
        s.workspace.write(Step.B9_DEVELOP, heal_file(list(dict.fromkeys(kept + [r for rule in rules for r in rule.splitlines()]))))
        tokens = TokenFile(s.workspace.read(TOKENS_PATH))
        changes = [c for r in contrast if (c := fix_contrast(tokens, ColorReading(**r)))]
        if changes:
            s.workspace.write(Step.B9_DEVELOP, WorkspaceFile(path=TOKENS_PATH, content=tokens.css))
        return changes

    # -------------------------------------------------------------- B10
    async def integrate(self, session: str, planned: list[str]) -> IntegrationReport:
        s = self._s(session)
        assert s.page and s.overlay
        s.console_errors.clear()
        await s.page.reload()
        await s.page.wait_for_load_state("networkidle")
        present = await s.page.evaluate(
            "() => [...document.querySelectorAll('[data-swarm-section]')].map(e => e.getAttribute('data-swarm-section'))")
        order_ok = [x for x in present if x in planned] == planned
        missing = [x for x in planned if x not in present] + ([] if order_ok else ["(thứ tự section sai)"])
        report = await design_pass(s.overlay, sections=planned)
        await s.overlay.clear()
        await s.page.evaluate("() => scrollTo(0, 0)")
        return IntegrationReport(missing=missing, console_errors=list(s.console_errors), open=report.findings)

    # -------------------------------------------------------------- art director (stylist)
    async def outline(self, session: str) -> str:
        """Compact DOM outline of the page's sections (tags and classes, no text) for the art director."""
        s = self._s(session)
        if not s.page:
            return ""
        return await s.page.evaluate(OUTLINE_JS)

    async def write_style_layer(self, session: str, page: str, css: str, step: Step = Step.B10_INTEGRATE) -> None:
        s = self._s(session)
        current = s.workspace.read(STYLE_PATH) if (s.workspace.root / STYLE_PATH).exists() else ""
        pages = style_pages(current)
        pages[page or "index"] = css
        s.workspace.write(step, style_file(pages))
        if s.page:
            await asyncio.sleep(1.0)  # HMR applies the stylesheet

    # -------------------------------------------------------------- B9 eyes (qa/section_eye.py)
    async def section_shots(self, session: str, section_id: str, folder: Path, tag: str) -> dict | None:
        """The section alone at 1440 and 375, on clean tabs (no overlay, reduced motion), saved as JPEGs.
        Returns {"images": [desktop, mobile data URIs], "files": [names], "overflow": phone page wider than the screen}."""
        s = self._s(session)
        if not (s.browser and s.base_url):
            return None
        url = s.base_url.rstrip("/") + (s.route if s.route != "/" else "")
        folder.mkdir(parents=True, exist_ok=True)
        out: dict = {"images": [], "files": [], "overflow": False}
        for width, height, name in ((1440, 900, "desktop"), (375, 812, "mobile")):
            page = s.shot_pages.get(width)
            if page is None or page.is_closed():
                page = await (await self._checker(s)).new_page(viewport={"width": width, "height": height},
                                                                reduced_motion="reduce")
                s.shot_pages[width] = page
            try:
                await page.goto(url, wait_until="load", timeout=45000)
                with contextlib.suppress(Exception):
                    await page.wait_for_load_state("networkidle", timeout=8000)
                await page.evaluate(UNSTICK_JS, section_id)
                el = page.locator(f'[data-swarm-section="{section_id}"]').first
                await el.scroll_into_view_if_needed(timeout=5000)
                await page.wait_for_timeout(400)
                data = await el.screenshot(type="jpeg", quality=72, timeout=15000)
            except Exception as e:  # noqa: BLE001 — looking never stops a build
                log.warning("section shot %s/%s failed: %s", section_id, name, e)
                return None
            file = f"{section_id}-{tag}-{name}.jpg"
            (folder / file).write_bytes(data)
            out["files"].append(file)
            out["images"].append("data:image/jpeg;base64," + base64.b64encode(data).decode())
            if width == 375:
                out["overflow"] = await page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
        return out

    # -------------------------------------------------------------- B11
    async def master_qa(self, session: str, spec: DesignSpec, creative: bool = False) -> QaReport:
        s = self._s(session)
        assert s.page and s.overlay
        await s.page.reload()
        await s.page.wait_for_load_state("networkidle")
        await self._wait_for_heal_css(s)
        s.console_errors.clear()
        report = await run_master_qa(s.page, s.overlay, spec.typography, errors=s.console_errors,
                                     instant=not self.headed, creative=creative,
                                     clone=bool(s.ref_components))
        return report

    async def critique(self, session: str, context: str = "") -> Critique | None:
        """Design critic on a clean tab: the build tab carries the swarm overlay, which must not be graded."""
        s = self._s(session)
        if not (s.browser and s.page):
            return None
        page = await (await self._checker(s)).new_page(viewport={"width": 1440, "height": 900})
        url = (s.base_url or s.page.url).rstrip("/") + (s.route if s.route != "/" else "")
        try:
            # The build tab may still be re-compiling (dev server HMR) and abort the first load: retry once.
            for attempt in (1, 2):
                try:
                    await page.goto(url, wait_until="load", timeout=45000)
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    break
                except Exception as e:  # noqa: BLE001
                    if attempt == 2:
                        raise
                    log.info("critic page load retried after: %s", e)
                    await page.wait_for_timeout(2000)
            return await critique(page, context=context)
        except Exception as e:  # noqa: BLE001 — the critic never stops a build
            log.warning("critique failed: %s", e)
            return None
        finally:
            await page.close()

    async def fidelity(self, session: str, reference_url: str, shots: Path | None = None) -> Fidelity | None:
        """Clone mode: read the reference and the rebuilt page with the same reader (clean tabs, no
        overlay) and score how close they are. `shots` also saves both full-page screenshots there."""
        s = self._s(session)
        if not (s.browser and s.page):
            return None
        url = (s.base_url or s.page.url).rstrip("/") + (s.route if s.route != "/" else "")
        checker = await self._checker(s)
        pages = [await checker.new_page(viewport={"width": 1440, "height": 900}) for _ in range(2)]
        try:
            snaps = []
            for page, target, name in zip(pages, (reference_url, url), ("original", "clone")):
                await open_settled(page, target)
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(shots / f"{name}.png"), full_page=True)
                snaps.append(await snapshot_page(page))
            return score(*snaps)
        except Exception as e:  # noqa: BLE001 — measuring never stops a build
            log.warning("fidelity failed: %s", e)
            return None
        finally:
            for page in pages:
                await page.close()

    # -------------------------------------------------------------- B11 · Clone 1:1 acceptance
    async def _hide_overlay(self, page: Page, hidden: bool) -> None:
        with contextlib.suppress(Exception):
            await page.evaluate("(h) => { const o = document.querySelector('chromaswarm-overlay');"
                                " if (o) o.style.display = h ? 'none' : ''; }", hidden)

    async def _shot(self, page: Page, box: dict, path: Path) -> str | None:
        await self._hide_overlay(page, True)
        # Scroll-driven reveals keep everything below the viewport at opacity 0 in a full-page shot: show the
        # end state while photographing (removed right after).
        with contextlib.suppress(Exception):
            await page.add_style_tag(content="[data-swarm-section] *, [data-swarm-section] { animation: none !important; "
                                             "transition: none !important; } /* cs-shot */")
        try:
            clip = {"x": 0, "y": max(0, box["top"]), "width": 1440, "height": max(40, min(box["height"], 2400))}
            await page.screenshot(path=str(path), full_page=True, clip=clip, type="jpeg", quality=62)
            return path.name
        except Exception as e:  # noqa: BLE001
            log.info("section shot failed: %s", e)
            return None
        finally:
            await self._hide_overlay(page, False)
            with contextlib.suppress(Exception):
                await page.evaluate("() => [...document.querySelectorAll('style')]"
                                    ".filter(x => x.textContent.includes('cs-shot')).forEach(x => x.remove())")

    async def _built_motion(self, s: _Session, url: str, boxes: dict[str, dict]) -> dict[str, list[str]]:
        """Effects the rebuilt page really has, found the same way as on the reference."""
        assert s.browser
        page = await s.browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            await page.goto(url, wait_until="load", timeout=45000)
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=8000)
            parallax: list[dict] = []
            with contextlib.suppress(Exception):
                await page.evaluate(motion_probe.PRE_JS)
                parallax = await page.evaluate(motion_probe.PARALLAX_JS)
            with contextlib.suppress(Exception):
                await page.evaluate(SETTLE_JS)
            post = await motion_probe.probe(page)
            return motion_report(boxes, [], post, parallax, 0, header=None).per_section
        except Exception as e:  # noqa: BLE001
            log.info("built motion check failed: %s", e)
            return {}
        finally:
            await page.close()

    async def compare(self, session: str, reference_url: str, sections: list[Section], ref_boxes: dict[str, dict],
                      page: str = "", shots: Path | None = None) -> dict | None:
        """Master cursor, section by section, in both windows at once: the rebuild (with its overlay) and
        the reference link (a second window). Every reference component is paired with the rebuilt one;
        the Master visits each pair (red flag where they still differ), both sections are photographed for
        the side-by-side view, measurable differences are tuned into match.css."""
        s = self._s(session)
        if not (s.browser and s.page and s.overlay):
            return None
        url = (s.base_url or s.page.url).rstrip("/") + (s.route if s.route != "/" else "")
        names = {sec.id: sec.name for sec in sections}
        wanted = {sec.id: sec.motion for sec in sections}
        if shots:
            shots.mkdir(parents=True, exist_ok=True)
        ctx = await s.browser.new_context(viewport={"width": 1440, "height": 900})
        ref = await ctx.new_page()
        try:
            await open_settled(ref, reference_url)
            ref_ov = None
            with contextlib.suppress(Exception):
                ref_ov = await SwarmOverlay.attach(ref, instant=not self.headed, speed=self.speed)
                await ref_ov.master(True)
                await ref_ov.hud("Trang mẫu (link gốc) · Master Cursor đối chiếu")
            keys = [sid for sid in names if sid in ref_boxes]
            raw_ref = await cmp.measure_reference(ref, [{"key": k, **ref_boxes[k]} for k in keys])
            await s.page.reload()
            with contextlib.suppress(Exception):
                await s.page.wait_for_load_state("networkidle", timeout=15000)
            await self._wait_for_heal_css(s)
            built, boxes = await self._built_components(s)
            effects = await self._built_motion(s, url, boxes)
            ov = s.overlay
            await ov.master(True)
            results: list[cmp.SectionCompare] = []
            tuned = 0
            for n, sid in enumerate(keys, 1):
                if sid not in boxes:
                    continue
                ref_c = cmp.comps(raw_ref["comps"].get(sid, []))
                ref_box = raw_ref["boxes"].get(sid) or ref_boxes[sid]  # widened to cover its pieces
                res, pairs = cmp.section_score(sid, ref_c, built.get(sid, []), ref_box, boxes[sid], names[sid])
                res.effects_missing = [e for e in wanted.get(sid, []) if e not in effects.get(sid, [])
                                       and e not in ("smooth-scroll", "sticky-blur")]
                await ov.hud(f"Nghiệm thu 1:1 · {n}/{len(keys)} · {names[sid]} · khớp {res.score:.0f}%")
                if shots:
                    res.built_image = await self._shot(s.page, boxes[sid], shots / f"{sid}-clone.jpg")
                    res.ref_image = await self._shot(ref, raw_ref["boxes"].get(sid, ref_boxes[sid]), shots / f"{sid}-ref.jpg")
                # Slow and thorough: differing pairs first, then the rest (capped per section).
                visit = sorted(pairs, key=lambda p: (not p.diffs, p.ref.y))[:12]
                for p in visit:
                    b_sel, r_sel = f'[data-cs-comp="{sid}:{p.built.i}"]', f'[data-cs-ref="{sid}:{p.ref.i}"]'
                    moves = [ov.move(Agent.MASTER, b_sel)]
                    if ref_ov:
                        moves.append(ref_ov.move(Agent.MASTER, r_sel))
                    with contextlib.suppress(Exception):
                        await asyncio.gather(*moves)
                        if p.diffs:
                            label = f"{cmp.KIND_LABEL[p.ref.kind]}: " + ", ".join(p.diffs[:2])
                            await ov.flag(b_sel, label)
                            if ref_ov:
                                await ref_ov.flag(r_sel, "mẫu")
                        else:
                            await ov.pulse()
                rules = cmp.tune_rules(sid, pairs, page)
                key = f"{page}:{sid}"
                s.match[key], changed = cmp.merge_rules(s.match.get(key, {}), rules)
                tuned += changed
                results.append(res)
                with contextlib.suppress(Exception):
                    await ov.clear("flag")
                    if ref_ov:
                        await ref_ov.clear("flag")
            if tuned:
                self._write_match(s)
            await ov.hud(None)
            await ov.master(False)
            total = cmp.page_score(results)
            return {"total": total, "sections": [r.model_dump() for r in results], "tuned": tuned}
        finally:
            await ctx.close()

    # -------------------------------------------------------------- B12
    async def handover(self, session: str, options: list[dict]) -> None:
        """Remove every AI overlay and give the window to the user, with the next-step buttons."""
        s = self._s(session)
        if s.handed_over or not s.page or not s.overlay:
            return
        await s.overlay.clear()
        await s.overlay.handover()
        await self.release_checks(session)  # every check is done: no hidden tab outlives the handover
        if self.headed and s.browser and not s.fluid:
            # The build tab has a fixed 1440×900 viewport: replace it with ONE tab sized by the window itself.
            build_page = s.page
            await self._open_window(s, session, build_page.url, fluid=True)
            with contextlib.suppress(Exception):
                await s.page.wait_for_load_state("networkidle", timeout=15000)
            await s.overlay.handover()
            await build_page.close()
        await s.page.evaluate(HANDOVER_BAR_JS, options)
        await s.page.bring_to_front()
        s.handed_over = True

    async def close(self, session: str) -> None:
        s = self._sessions.pop(session, None)
        if not s:
            return
        with contextlib.suppress(Exception):
            if s.checker:
                await s.checker.close()
            if s.browser:
                await s.browser.close()
            if s.pw:
                await s.pw.stop()
        await s.server.stop()

    async def close_all(self) -> None:
        for sid in list(self._sessions):
            await self.close(sid)


def _strings(value: Any) -> list[str]:
    """Every text in a section's content entry (nested lists / dicts)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [t for v in value.values() for t in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [t for v in value for t in _strings(v)]
    return []
