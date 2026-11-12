"""B8-B10 runtime: owns the per-session resources the graph must not checkpoint
(workspace on disk, `next dev` process, Playwright browser + swarm overlay).

`BuildRuntime` is the interface the graph nodes call; `LocalBuildRuntime` is
the real implementation. Tests inject a fake with the same methods.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from playwright.async_api import Browser, Page, Playwright, async_playwright
from pydantic import BaseModel

from chromaswarm.agents.planner import Section
from chromaswarm.design.dept import TokenChange, TokenFile, fix_contrast, repair
from chromaswarm.developer.content import PageCopy
from chromaswarm.developer.nextjs import WorkspaceFile, heal_file, motion_file, page_file, render_section, scaffold
from chromaswarm.mcp_motion.client import MotionEffect, build_effects
from chromaswarm.mcp_motion.server import pick_effect
from chromaswarm.developer.workspace import TOKENS_PATH, DevServer, Workspace
from chromaswarm.engines.design_spec import DesignSpec
from chromaswarm.playwright_engine.swarm import Agent, ColorReading, Finding, SwarmOverlay, design_pass
from chromaswarm.qa.master import QaReport, run_master_qa
from chromaswarm.state_machine.pipeline_state import Step

log = logging.getLogger(__name__)


class SectionCheck(BaseModel):
    section: str
    changes: list[TokenChange] = []
    open: list[Finding] = []


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
    async def master_qa(self, session: str, spec: DesignSpec) -> QaReport: ...
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


CREATE_ONLY = {"app/heal.css", "app/motion.css"}  # accumulate across pages and heal loops


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
  </style><div class="bar" role="region" aria-label="Bàn giao ChromaSwarm"><p>Trang đã bàn giao. Bạn có thể dùng thử ngay trên cửa sổ này.</p></div>`;
  const bar = root.querySelector('.bar');
  for (const o of options) {
    const b = document.createElement('button');
    b.textContent = o.label;
    if (o.primary) b.className = 'primary';
    b.onclick = () => { bar.querySelectorAll('button').forEach(x => x.disabled = true); window.__chromaswarmChoice(o.value); };
    bar.appendChild(b);
  }
  document.body.appendChild(host);
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
    async def start_app(self, session: str, project: str, spec: DesignSpec, route: str = "/") -> str:
        s = self._s(session)
        for f in scaffold(project, spec):
            if f.path in CREATE_ONLY and (s.workspace.root / f.path).exists():
                continue
            s.workspace.write(Step.B9_DEVELOP, f)
        s.route = route
        page_path = s.workspace.root / page_file([], route=route).path
        if not page_path.exists():
            s.workspace.write(Step.B9_DEVELOP, page_file([], route=route))
        await s.workspace.install(Step.B9_DEVELOP)
        s.base_url = await s.server.start(Step.B9_DEVELOP)
        url = s.base_url.rstrip("/") + (route if route != "/" else "")
        if s.page is None:
            s.pw = await async_playwright().start()
            s.browser = await s.pw.chromium.launch(headless=not self.headed)
            s.page = await s.browser.new_page(viewport={"width": 1440, "height": 900})
            s.page.on("console", lambda m: s.console_errors.append(m.text) if m.type == "error" else None)
            s.page.on("pageerror", lambda e: s.console_errors.append(str(e)))
            await s.page.expose_binding("__chromaswarmChoice", lambda _src, value: self._choice(session, value))
            await s.page.goto(url)
            s.overlay = await SwarmOverlay.attach(s.page, instant=not self.headed, speed=self.speed)
        else:
            await s.page.evaluate("() => document.querySelector('chromaswarm-handover')?.remove()")
            await s.page.goto(url)
            assert s.overlay
            await s.overlay.resume()  # a new build after B12: the swarm comes back
        s.handed_over = False
        return url

    async def _choice(self, session: str, value: Any) -> None:
        if self.on_choice and isinstance(value, dict):
            asyncio.get_running_loop().create_task(self.on_choice(session, value))

    async def write_section(self, session: str, written: list[Section], copy: PageCopy,
                            page: str = "", route: str = "/") -> None:
        s = self._s(session)
        s.workspace.write(Step.B9_DEVELOP, render_section(written[-1], copy, page))
        s.workspace.write(Step.B9_DEVELOP, page_file(written, page, route))

    async def refresh_shared(self, session: str, section: Section, copy: PageCopy, pages: list[str]) -> None:
        """Re-render a shared section (the header) on pages built earlier, so their navigation
        links to the page being built now."""
        s = self._s(session)
        for page in pages:
            if (s.workspace.root / "components" / "sections" / page).exists():
                s.workspace.write(Step.B9_DEVELOP, render_section(section, copy, page))

    # -------------------------------------------------------------- B8.1
    async def motion(self, session: str, section: Section, spec: DesignSpec, page: str = "") -> list[MotionEffect]:
        """Motion & 2D/3D MCP Specialist: asks the Motion MCP server for the PLAN.md effect and
        appends the returned CSS to app/motion.css."""
        effect = pick_effect(section.effect or "")
        if not self.motion_enabled or not effect:
            return []
        s = self._s(session)
        if s.overlay:
            await s.overlay.move(Agent.MOTION, f'[data-swarm-section="{section.id}"]')
            await s.overlay.note(Agent.MOTION, f"B8.1 · MCP build_effect({effect})")
        effects = await build_effects([(effect, section.id)], spec.motion_duration_ms, spec.motion_easing, page=page)
        current = s.workspace.read("app/motion.css") if (s.workspace.root / "app/motion.css").exists() else ""
        blocks = [b.strip("\n") for b in current.split("\n/* fx */\n")[1:]] if "/* fx */" in current else []
        for fx in effects:
            block = f"/* {page or 'index'} · {fx.section_id} · {fx.effect} */\n{fx.css}".strip("\n")
            if block not in blocks:
                blocks.append(block)
        s.workspace.write(Step.B9_DEVELOP, motion_file(["/* fx */\n" + b for b in blocks]))
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
        report = (await design_pass(s.overlay, spec.typography, sections=[section_id])).sections[0]
        tokens = TokenFile(s.workspace.read(TOKENS_PATH))
        changes, leftover = repair(report, tokens)
        if changes:
            s.workspace.write(Step.B9_DEVELOP, WorkspaceFile(path=TOKENS_PATH, content=tokens.css))
            await s.overlay.note(Agent.COLOR, f"tokens.css: {', '.join(c.token for c in changes)}")
            await asyncio.sleep(1.0)  # HMR applies the stylesheet
            report = (await design_pass(s.overlay, spec.typography, sections=[section_id])).sections[0]
            leftover = report.findings
        await s.overlay.clear()
        return SectionCheck(section=section_id, changes=changes, open=leftover)

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

    # -------------------------------------------------------------- B11
    async def master_qa(self, session: str, spec: DesignSpec) -> QaReport:
        s = self._s(session)
        assert s.page and s.overlay
        await s.page.reload()
        await s.page.wait_for_load_state("networkidle")
        s.console_errors.clear()
        report = await run_master_qa(s.page, s.overlay, spec.typography, errors=s.console_errors,
                                     instant=not self.headed)
        return report

    # -------------------------------------------------------------- B12
    async def handover(self, session: str, options: list[dict]) -> None:
        """Remove every AI overlay and give the window to the user, with the next-step buttons."""
        s = self._s(session)
        if s.handed_over or not s.page or not s.overlay:
            return
        await s.overlay.clear()
        await s.overlay.handover()
        await s.page.evaluate(HANDOVER_BAR_JS, options)
        await s.page.bring_to_front()
        s.handed_over = True

    async def close(self, session: str) -> None:
        s = self._sessions.pop(session, None)
        if not s:
            return
        with contextlib.suppress(Exception):
            if s.browser:
                await s.browser.close()
            if s.pw:
                await s.pw.stop()
        await s.server.stop()

    async def close_all(self) -> None:
        for sid in list(self._sessions):
            await self.close(sid)
