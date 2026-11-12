"""Watch the swarm overlay on a real browser window.

  uv run python -m chromaswarm.playwright_engine.demo                 # built-in demo page
  uv run python -m chromaswarm.playwright_engine.demo http://localhost:3001
  uv run python -m chromaswarm.playwright_engine.demo --headless --screenshot out.png

Runs the B8 Design pass (Layout -> Color -> Typography per section), then a
preview of the B11 Master cursor (hover every [data-swarm-role], flag the
findings) and finally the B12 handover. The full B11 test suite is Phase 6.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.swarm import Agent, SwarmOverlay, design_pass

DEMO_PAGE = Path(__file__).with_name("fixtures") / "demo_landing.html"


async def run(url: str, headless: bool, speed: float, screenshot: Path | None, hold: float) -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(url)
        swarm = await SwarmOverlay.attach(page, instant=headless, speed=speed)

        print(f"B8 · Phòng Design đo {url}")
        report = await design_pass(swarm)
        for s in report.sections:
            mark = "✓" if not s.findings else "✗"
            print(f"  {mark} {s.section}")
            for f in s.findings:
                print(f"      [{f.agent}] {f.rule}: {f.detail}")

        print("B11 · Master cursor (bản xem trước)")
        await swarm.clear()
        await swarm.master(True)
        roles = await page.evaluate(
            "() => [...document.querySelectorAll('[data-swarm-role]')].map(e => e.getAttribute('data-swarm-id'))")
        roles = [r for r in roles if r]
        for n, rid in enumerate(roles, 1):
            sel = f'[data-swarm-id="{rid}"]'
            await swarm.hud(f"Master Cursor: {n}/{len(roles)} phần tử · Viewport {report.viewport_w}px")
            await swarm.move(Agent.MASTER, sel)
            await page.hover(sel)
            await swarm.pulse()
            await page.wait_for_timeout(0 if headless else 250)
        by_selector: dict[str, list[str]] = {}
        for f in report.findings:
            by_selector.setdefault(f.selector, []).append(f.detail)
        for sel, details in by_selector.items():
            for d in dict.fromkeys(details):
                await swarm.flag(sel, d[:90])
        total = len(report.findings)
        await swarm.hud(f"Master Cursor: {len(roles)}/{len(roles)} đã kiểm · {total} lỗi cần sửa"
                        if total else f"Master Cursor: {len(roles)}/{len(roles)} · 100% PASSED")
        if screenshot:
            await page.screenshot(path=str(screenshot), full_page=False)
            print(f"Ảnh chụp: {screenshot}")
        if not headless and hold:
            await page.wait_for_timeout(hold * 1000)

        print("B12 · Bàn giao: gỡ lớp phủ")
        await swarm.handover()
        await browser.close()
        return 1 if total else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", default=DEMO_PAGE.as_uri())
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0, help="cursor speed multiplier")
    ap.add_argument("--screenshot", type=Path)
    ap.add_argument("--hold", type=float, default=8, help="seconds to keep the window open at the end")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(run(a.url, a.headless, a.speed, a.screenshot, a.hold)))


if __name__ == "__main__":
    main()
