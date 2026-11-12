"""Swarm overlay (Phase 4) in headless Chromium: rendering never disturbs the page,
readings are exact, and verdicts come from the Python engines."""

import asyncio

import pytest
from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.demo import DEMO_PAGE
from chromaswarm.playwright_engine.swarm import (
    Agent,
    ColorReading,
    Rect,
    SwarmOverlay,
    contrast_finding,
    design_pass,
)

PLAIN = """<!doctype html><html><body style="margin:0;font:16px/1.5 sans-serif;background:#fff;color:#111">
<section data-swarm-section="a" style="padding:32px 24px 48px;display:grid;gap:16px">
  <h2>Tiêu đề</h2>
  <button id="b" data-swarm-id="btn" data-swarm-role="button" style="width:200px;height:48px"
          onclick="window.clicks=(window.clicks||0)+1">Bấm</button>
</section></body></html>"""


def run(coro):
    return asyncio.run(coro)


async def with_page(fn, html=PLAIN, url=None, width=1280, height=800):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": width, "height": height})
        if url:
            await page.goto(url)
        else:
            await page.set_content(html)
        try:
            return await fn(page)
        finally:
            await browser.close()


def test_overlay_never_blocks_clicks_or_changes_styles():
    async def go(page):
        before = await page.evaluate("() => getComputedStyle(document.querySelector('#b')).cssText.length "
                                     "+ getComputedStyle(document.body).backgroundColor")
        swarm = await SwarmOverlay.attach(page, instant=True)
        await swarm.measure(Agent.LAYOUT, '[data-swarm-section="a"]')
        await swarm.master(True)
        await swarm.flag("#b", "FAIL")  # a red box drawn right over the button
        await page.mouse.click(*(await page.evaluate(
            "() => { const r = document.querySelector('#b').getBoundingClientRect();"
            " return [r.x + r.width / 2, r.y + r.height / 2]; }")))
        after = await page.evaluate("() => getComputedStyle(document.querySelector('#b')).cssText.length "
                                    "+ getComputedStyle(document.body).backgroundColor")
        return await page.evaluate("() => window.clicks"), before == after, await swarm.state()

    clicks, same_style, state = run(with_page(go))
    assert clicks == 1  # pointer-events: none on the whole overlay
    assert same_style  # shadow DOM: no style leaks into the page
    assert state["installed"] and state["master"] and "flag" in state["annotations"]


def test_measure_reads_exact_box_model():
    async def go(page):
        swarm = await SwarmOverlay.attach(page, instant=True)
        return await swarm.measure(Agent.LAYOUT, '[data-swarm-section="a"]')

    m = run(with_page(go))
    assert m.padding == [32, 24, 48, 24] and m.gap == 16 and m.rect.w == 1280


def test_overlay_survives_rerender_and_navigation():
    async def go(page):
        await SwarmOverlay.attach(page, instant=True)
        await page.evaluate("() => { document.body.innerHTML = '<main>re-rendered</main>'; }")
        await page.wait_for_timeout(50)
        rerendered = await page.evaluate("() => window.__chromaSwarm.state().installed")
        await page.goto(DEMO_PAGE.as_uri())  # init script re-injects on navigation
        navigated = await page.evaluate("() => window.__chromaSwarm.state().installed")
        return rerendered, navigated

    assert run(with_page(go)) == (True, True)


def test_handover_removes_every_trace():
    async def go(page):
        swarm = await SwarmOverlay.attach(page, instant=True)
        await swarm.master(True)
        await swarm.hud("Master Cursor: 1/1")
        await swarm.handover()
        await swarm.note(Agent.LAYOUT, "should not come back")
        return (await page.evaluate("() => document.querySelectorAll('chromaswarm-overlay').length"),
                await swarm.state())

    count, state = run(with_page(go))
    assert count == 0 and state["handed_over"] and not state["installed"]


def test_design_pass_finds_exactly_the_seeded_defects():
    async def go(page):
        swarm = await SwarmOverlay.attach(page, instant=True)
        return await design_pass(swarm)

    report = run(with_page(go, url=DEMO_PAGE.as_uri(), width=1440, height=900))
    found = {(f.section, f.rule) for f in report.findings}
    assert found == {("story", "grid-8pt"), ("story", "line-length"), ("collection", "contrast")}
    assert [s.section for s in report.sections] == ["navbar", "hero", "story", "collection"]
    hero = next(s for s in report.sections if s.section == "hero")
    assert hero.box.padding[0] == 128 and all(c.wcag >= 4.5 for c in hero.colors)


def test_mobile_gutter_is_checked_at_375px():
    html = PLAIN.replace("padding:32px 24px 48px", "padding:32px 8px 48px")

    async def go(page):
        swarm = await SwarmOverlay.attach(page, instant=True)
        return await design_pass(swarm)

    report = run(with_page(go, html=html, width=375, height=812))
    assert [f.rule for f in report.findings] == ["gutter-mobile"]


@pytest.mark.parametrize("size,weight,fg,expect_fail", [
    (16, 400, "#767676", False),  # 4.54:1 but APCA Lc ~71 -> passes
    (16, 400, "#949494", True),   # body text below AA
    (32, 700, "#949494", False),  # large text: WCAG 3 / Lc 45 suffices
])
def test_contrast_thresholds(size, weight, fg, expect_fail):
    from chromaswarm.engines.color import apca_lc, parse_css_color, wcag_contrast

    f, b = parse_css_color(fg)[0], parse_css_color("#ffffff")[0]
    r = ColorReading(fg=fg, bg="#ffffff", font_size=size, font_weight=weight, rect=Rect(x=0, y=0, w=1, h=1),
                     wcag=round(wcag_contrast(f, b), 2), apca=round(apca_lc(f, b), 1))
    assert (contrast_finding("s", "p", r) is not None) is expect_fail
