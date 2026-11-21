"""The user's frontend-ui skill as Master QA rules (Creative only)."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.swarm import SwarmOverlay
from chromaswarm.qa.master import _probe, heal_css, run_master_qa, skill_failures

FIXTURE = (Path(__file__).parents[1] / "chromaswarm/qa/fixtures/skill_defects.html").resolve().as_uri()
SKILL_RULES = {"skill-measure", "skill-radius-scale", "skill-type-scale", "skill-mixed-surface",
               "skill-clickable-div", "skill-no-name", "skill-img-alt", "design-md-display-font"}


async def _run(creative: bool, heal: bool = False):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(FIXTURE)
        swarm = await SwarmOverlay.attach(page, instant=True)
        report = await run_master_qa(page, swarm, instant=True, creative=creative)
        after = None
        if heal:
            await page.add_style_tag(content="\n".join(heal_css(report.failures)))
            after = skill_failures(await _probe(page, "skill"))
        await browser.close()
        return report, after


def test_every_skill_rule_is_caught_on_creative_pages():
    report, after = asyncio.run(_run(creative=True, heal=True))
    rules = {f.rule for f in report.failures if f.rule.startswith(("skill-", "design-md-"))}
    assert rules == SKILL_RULES, rules ^ SKILL_RULES
    measure = next(f for f in report.failures if f.rule == "skill-measure")
    assert measure.selector == "#measure" and "max-width: 65ch" in measure.heal
    left = {f.rule for f in after}
    assert "skill-measure" not in left and "skill-mixed-surface" not in left  # patched by CSS


def test_clone_pages_keep_the_reference_look():
    report, _ = asyncio.run(_run(creative=False))
    assert not any(f.rule.startswith(("skill-", "design-md-")) for f in report.failures)


def test_scales_within_limits_pass():
    clean = {"measure": [], "mixed": [], "click_divs": [], "unnamed": [], "no_alt": [],
             "radii": {"6": ["a"], "10": ["b"], "16": ["c"]}, "sizes": {str(s): 1 for s in (12, 14, 16, 20, 24, 32, 40)}}
    assert skill_failures(clean) == []


def test_plan_starts_with_the_design_intent():
    from chromaswarm.agents.planner import design_intent, page_sections
    from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars
    st = PipelineState(session_id="p", raw_prompt="shop nến thơm", domain=Domain.ECOMMERCE, selected_page="home",
                       pillars=Pillars(theme="editorial-luxury", layout="catalog", color="light", margins="balanced",
                                       scope="Dân văn phòng 25-35, muốn họ bấm Đặt mua"))
    text = "\n".join(design_intent(st, page_sections(st)))
    assert "“Đặt mua”" in text and "Hành động chính duy nhất" in text
    assert "1. **Hero" in text and "`bestsellers`" in text  # hierarchy + the grid's states
    assert "Header" not in text and "Footer" not in text
