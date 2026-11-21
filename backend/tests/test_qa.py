"""Master QA (B11) on a fixture page that seeds one defect per rule."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.demo import DEMO_PAGE
from chromaswarm.playwright_engine.swarm import SwarmOverlay
from chromaswarm.qa.master import heal_css, run_master_qa

DEFECTS = (Path(__file__).parents[1] / "chromaswarm/qa/fixtures/qa_defects.html").resolve().as_uri()

SEEDED = {
    "no-hover", "no-state-change", "console-error", "no-focus-visible", "dead-link",  # test 1
    "sticky-legibility", "stuck-hidden", "broken-image",                 # test 2
    "overflow-x", "collision", "tap-target", "tap-spacing",              # test 3
    "slop-1-gradient", "slop-3-centered", "slop-5-shadow", "slop-6-copy",  # test 4
    "control-border", "placeholder-as-label", "required-red", "link-underline",  # test 4, chapters 6-7
    "disabled-control", "generic-label", "long-text", "font-weights", "number-format",
    "card-row-ragged", "accent-area",
}
UNPATCHABLE = {"no-state-change", "console-error", "dead-link", "broken-image", "collision", "slop-6-copy",
               "placeholder-as-label", "disabled-control", "generic-label", "font-weights", "number-format",
               "card-row-ragged", "accent-area"}


async def qa_on(url: str, heal: bool = False):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        await page.goto(url)
        swarm = await SwarmOverlay.attach(page, instant=True)
        first = await run_master_qa(page, swarm, errors=errors, instant=True)
        second = None
        if heal:
            await page.add_style_tag(content="\n".join(heal_css(first.failures)))
            second = await run_master_qa(page, swarm, errors=errors, instant=True)
        await browser.close()
        return first, second


def test_every_seeded_defect_is_caught_and_patchable_ones_heal():
    first, second = asyncio.run(qa_on(DEFECTS, heal=True))
    rules = {f.rule for f in first.failures}
    assert rules == SEEDED, rules ^ SEEDED
    assert not first.passed and [t.test for t in first.tests] == [1, 2, 3, 4]
    assert all(f.heal is None for f in first.failures if f.rule in UNPATCHABLE)
    left = {f.rule for f in second.failures}
    assert UNPATCHABLE <= left  # still there: those need a human / the Developer
    assert not (left & (SEEDED - UNPATCHABLE))  # every CSS-patchable defect is gone
    # Removing the gradient exposed white-on-white text: the next loop's Design fix handles it.
    assert any(f.rule == "contrast" and f.reading for f in second.failures)


def test_collisions_are_reported_once_across_breakpoints():
    first, _ = asyncio.run(qa_on(DEFECTS))
    collisions = [f for f in first.failures if f.rule == "collision"]
    assert len(collisions) == 1


def test_static_demo_page_dead_ctas_are_caught():
    """The Phase 4 demo page is static HTML: its CTAs have no handler, which B11 must catch,
    while its layout is sound (no overflow, collisions or covered controls)."""
    first, _ = asyncio.run(qa_on(DEMO_PAGE.as_uri()))
    dead = {f.selector for f in first.failures if f.rule == "no-state-change"}
    assert dead == {'[data-swarm-id="cta-book-showroom"]', '[data-swarm-id="cta-view-all"]'}
    assert not {f.rule for f in first.failures} & {"console-error", "overflow-x", "collision", "covered"}
