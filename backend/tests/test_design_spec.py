import asyncio

import pytest

from chromaswarm.engines.design_spec import DesignInputs, build_design_spec, render_design_md, render_tokens_css
from chromaswarm.engines.palette import Mode
from chromaswarm.engines.presets import Layout, Theme
from chromaswarm.engines.spacing import Density
from chromaswarm.playwright_engine.style_dna_scraper import scrape_html

REFERENCE_HTML = """
<html><body style="margin:0;background:#f7f3ec;color:#1c1a17;font-family:Georgia,serif">
  <header style="padding:24px 64px;border-bottom:1px solid #e4ddd0">
    <span style="font:500 12px/1.4 Arial;text-transform:uppercase;letter-spacing:2px">Secret Label</span>
  </header>
  <section style="padding:128px 64px">
    <h1 style="font-size:64px;font-weight:400;margin:0 0 24px">A confidential headline</h1>
    <p style="font-size:18px;max-width:60ch;margin:0 0 32px">Private copy that must never leak into DESIGN.md.</p>
    <a style="display:inline-block;padding:16px 32px;background:#8a3b12;color:#fff;border-radius:2px;
              transition:background 400ms ease-out">Buy now</a>
  </section>
  <section style="padding:96px 64px;background:#efe9de;border-top:1px solid #e4ddd0">
    <h2 style="font-size:40px;font-weight:400;margin:0 0 16px">Second headline</h2>
    <p style="font-size:18px;margin:0">More secret body text.</p>
  </section>
</body></html>
"""


@pytest.fixture(scope="module")
def dna():
    return asyncio.run(scrape_html(REFERENCE_HTML))


def test_scraper_extracts_dna_without_content(dna):
    dumped = dna.model_dump_json()
    for secret in ("confidential", "Private copy", "Secret Label", "Buy now", "<h1", "section"):
        assert secret not in dumped
    assert dna.is_dark is False
    assert dna.neutral_temperature == "warm"
    assert dna.density == "airy"
    assert dna.separation == "borders"
    assert dna.uppercase_labels is True
    assert dna.accent_usage == "restrained"
    assert dna.radius_median == 2
    assert dna.motion_median_ms == 400
    assert dna.base_font_px == 18


def make_inputs(**kw):
    base = dict(project_name="Maison Lin", page="Landing Page", theme=Theme.EDITORIAL_LUXURY,
                layout=Layout.VISUAL_FIRST, density=Density.AIRY, mode=Mode.WARM_PAPER, seed_color="#8a3b12",
                persona="Người 30-45 tuổi mua nội thất cao cấp", primary_cta="Đặt lịch xem showroom")
    base.update(kw)
    return DesignInputs(**base)


def test_design_md_sections_and_values():
    spec = build_design_spec(make_inputs())
    md = render_design_md(spec)
    for heading in ("## 1. Triết lý", "## 2. Đặc trưng", "## 3. Hệ màu OKLCH", "## 4. Typography",
                    "## 5. Không gian", "## 6. Chuyển động", "## 7. Luật chống AI Slop"):
        assert heading in md
    assert "Instrument Serif" in md and "1280px" in md and "128px" in md
    assert "FAIL" not in md
    assert spec.typography.ratio == pytest.approx(1.333)


def test_dna_refines_surface_but_not_user_choices(dna):
    spec = build_design_spec(make_inputs(theme=Theme.PRECISION_TECH, density=Density.BALANCED, style_dna=dna))
    assert spec.radius["md"] == 0 or spec.radius["md"] in (2, 4)
    assert spec.spatial.density is Density.BALANCED  # user's answer wins over DNA's "airy"
    assert spec.theme.heading_font == "Geist"  # fonts come from user's theme, not copied
    assert spec.motion_duration_ms == 400
    md = render_design_md(spec)
    assert "Ranh giới chống sao chép" in md
    assert "confidential" not in md


def test_tokens_css():
    css = render_tokens_css(build_design_spec(make_inputs()))
    assert "--bg-primary: oklch(" in css and "--accent: oklch(" in css
    assert "--section-y: 128px" in css and "--text-display: clamp(" in css
    assert "#ffffff" not in css.lower()
