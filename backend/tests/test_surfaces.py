"""Surface materials (presets.Surface): spec, tokens, CSS and the B3/B7 wiring."""

import asyncio
import re

import pytest

from chromaswarm.agents.consultant import interpret_surface, surface_in_text
from chromaswarm.developer.nextjs import scaffold
from chromaswarm.developer.surfaces import surface_css
from chromaswarm.engines.design_spec import DesignInputs, build_design_spec, render_design_md, render_tokens_css
from chromaswarm.engines.palette import Mode
from chromaswarm.engines.presets import SURFACES, Layout, Surface, Theme
from chromaswarm.engines.spacing import Density
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Pillars, Step


def spec_for(surface: Surface, theme: Theme = Theme.PRECISION_TECH):
    return build_design_spec(DesignInputs(project_name="P", page="Landing", theme=theme, layout=Layout.VISUAL_FIRST,
                                          surface=surface, density=Density.BALANCED, mode=Mode.LIGHT,
                                          seed_color="#1f5fbf"))


def test_default_surface_is_flat_and_keeps_the_theme():
    spec = spec_for(Surface.FLAT, Theme.EDITORIAL_LUXURY)
    assert spec.radius == {"sm": 0, "md": 2, "lg": 4}
    assert "Phẳng" in render_design_md(spec)


@pytest.mark.parametrize("surface", [Surface.GLASS, Surface.CLAY, Surface.BRUTAL])
def test_surface_overrides_radius_and_elevation(surface):
    spec = spec_for(surface, Theme.EDITORIAL_LUXURY)
    assert tuple(spec.radius.values()) == SURFACES[surface].radius
    assert spec.elevation == SURFACES[surface].elevation
    md = render_design_md(spec)
    assert SURFACES[surface].label_vi in md


def test_brutal_shadows_are_hard_and_clay_has_inner_light():
    brutal = render_tokens_css(spec_for(Surface.BRUTAL))
    assert "--shadow-md: 4px 4px 0 var(--text-primary);" in brutal
    clay = render_tokens_css(spec_for(Surface.CLAY))
    assert "inset 0 2px 4px" in clay and "inset 0 -4px 8px" in clay


@pytest.mark.parametrize("surface", list(Surface))
def test_surface_css_uses_tokens_only(surface):
    css = surface_css(surface)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "colours must come from tokens"
    body = re.sub(r"@media[^{]*\{", "", css).replace("9999px", "")  # breakpoints and pill radius are not spacing
    for px in map(int, re.findall(r"(?<![\w.-])(\d+)px", body)):
        assert px in {0, 1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 72}, f"{px}px is off the 8pt scale"


def test_glass_keeps_text_on_opaque_enough_fills_and_body_solid():
    css = surface_css(Surface.GLASS)
    fills = [int(n) for n in re.findall(r"var\(--bg-elevated\) (\d+)%", css)]
    assert fills and min(fills) >= 72
    assert "body::before" in css and not re.search(r"^body \{", css, re.M)  # QA measures contrast against body
    assert "prefers-reduced-transparency" in css


def test_scaffold_writes_and_imports_surface_css():
    files = {f.path: f.content for f in scaffold("P", spec_for(Surface.GLASS))}
    assert "Liquid Glass" in files["app/surface.css"]
    layout = files["app/layout.tsx"]
    assert layout.index('"./base.css"') < layout.index('"./surface.css"') < layout.index('"./heal.css"')


def test_surface_words_do_not_collide_with_products():
    assert interpret_surface("liquid-glass") == "liquid-glass"
    assert interpret_surface("làm kiểu kính mờ như Apple") == "liquid-glass"
    assert interpret_surface("Viền đậm, bóng cứng") == "brutal"
    assert surface_in_text("cửa hàng kính mắt thời trang") is None  # 'kính' alone is a product, not a material
    assert surface_in_text("shop thời trang mềm mại") is None


def drive(runner, sid, answers):
    async def go():
        await runner.start(sid)
        snap = None
        for a in answers:
            snap = await runner.answer(sid, a)
        return snap
    return asyncio.run(go())


def test_material_named_in_the_first_message_skips_the_question(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path))
    snap = drive(runner, "g", ["creative", "Web bán tai nghe, giao diện kiểu liquid glass", "landing", "precision-tech"])
    p = snap["pipeline"]
    assert p.pillars.surface == "liquid-glass" and snap["question"]["key"] == "layout"
    assert p.step is Step.B3_ELICITATION


def test_b7_feedback_changes_the_material(tmp_path):
    from chromaswarm.agents.consultant import RuleBasedConsultant
    from chromaswarm.state_machine.graph import feedback_changes

    p = Pillars(theme="warm-organic", layout="narrative", color="light", margins="airy", scope="x", surface="flat")
    assert feedback_changes(RuleBasedConsultant(), "đổi sang kiểu đất sét nhé", p) == {"surface": "clay"}
    p.surface = "clay"
    assert feedback_changes(RuleBasedConsultant(), "giữ kiểu đất sét", p) == {}
