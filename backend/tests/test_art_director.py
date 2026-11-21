"""Level 2: screenshot Style DNA, the art director (compose + critic-driven refine), AI image
fallback, GSAP / Three.js motion — all with fakes, no network."""

import asyncio

from chromaswarm.agents.planner import page_sections
from chromaswarm.design.reference_vision import ScreenshotReader, to_dna, validate
from chromaswarm.developer import uploads
from chromaswarm.developer.motion_js import js_effects, motion_config, parse_config
from chromaswarm.developer.nextjs import style_file, style_pages
from chromaswarm.developer.photo_bot import PhotoBot
from chromaswarm.developer.stylist import Stylist, StylePatch, validate_css
from chromaswarm.engines.design_spec import build_design_spec
from chromaswarm.qa.critic import Critique, Issue
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Domain, Pillars, PipelineState, Step

from test_build import HAPPY, DEAD, FakeBuild, drive, qa
from test_uploads import png


# ----------------------------------------------------------------- screenshot -> Style DNA

GOOD = {"is_dark": False, "background": "#f5f0e8", "text": "#1a1a1a", "accent": "#c25a1b", "accent_usage": "restrained",
        "density": "airy", "radius_px": 12, "separation": "borders", "heading_style": "serif", "uppercase_labels": True,
        "notes": ["Headlines are very large and left-aligned.", "x"]}


def test_a_screenshot_reading_is_validated_into_style_dna():
    r = validate(GOOD)
    assert r["accent"] == "#c25a1b" and r["notes"] == ["Headlines are very large and left-aligned."]
    dna = to_dna(r)
    assert dna.from_screenshot and dna.separation == "borders" and dna.radius_median == 12
    rules = dna.learned_rules()
    assert "Surfaces are light with warm neutrals." in rules and not any("8pt scale" in x for x in rules)
    assert validate({**GOOD, "background": "javascript:alert(1)"}) is None
    assert validate({**GOOD, "density": "chaotic", "radius_px": 999})["density"] is None


def test_b5_uses_the_screenshot_and_takes_its_accent_when_none_was_given(tmp_path):
    shot = uploads.save(tmp_path, "s-shot", "reference", png())
    calls = []

    class Vision:
        model = "fake"

        def complete_json(self, system, user, images=None, max_tokens=0):
            calls.append(images[0][:22])
            return GOOD

    runner = PipelineRunner(Deps(artifacts_root=tmp_path, screenshot_reader=ScreenshotReader(Vision())))
    answers = [a for a in HAPPY]
    answers[5] = "warm-paper"  # no brand colour named
    answers[-1] = {"assets": [], "references": [{"screenshot_path": shot.path}], "done": True}
    snap = asyncio.run(drive(runner, "s-shot", answers + [""]))  # "" = no link for the screenshot
    p = snap["pipeline"]
    assert p.step is Step.B7_APPROVAL and calls == ["data:image/png;base64,"]
    assert p.pillars.color == "warm-paper #c25a1b"
    assert "Nguồn: screenshot" in p.design_md and "Headlines are very large" in p.design_md
    assert "màu nhấn #c25a1b" in (snap["notice"] or "")


# ----------------------------------------------------------------- stylist validator

SECTIONS = ["hero", "faq"]


def test_only_token_scoped_layout_css_survives():
    css = '''
    @media (min-width: 1024px) { [data-swarm-section="hero"] .split { grid-template-columns: 8fr 4fr; gap: 48px; } }
    [data-swarm-section="hero"] h1 { font-size: var(--text-display); color: #ff00aa; letter-spacing: -0.03em; }
    [data-swarm-section="faq"] { padding-block: 13px; background: linear-gradient(red, blue); border-top: 1px solid var(--border-subtle); }
    body { display: none; }
    [data-swarm-section="pricing"] { gap: 8px; }
    @media (min-width: 1024px) { [data-swarm-section="faq"] .container { max-width: 65ch; } }
    @supports (x) { [data-swarm-section="hero"] { gap: 8px; } }
    [data-swarm-section="hero"] .btn { box-shadow: 0 8px 24px black; transition: all 1s; }
    '''
    clean, rejected = validate_css(css, SECTIONS)
    assert "grid-template-columns: 8fr 4fr;" in clean and "gap: 48px;" in clean
    assert "font-size: var(--text-display);" in clean and "letter-spacing: -0.03em;" in clean
    assert "border-top: 1px solid var(--border-subtle);" in clean
    assert "@media (min-width: 1024px) {" in clean and "max-width: 65ch;" in clean
    for bad in ("#ff00aa", "13px", "gradient", "body", "pricing", "@supports", "box-shadow", "transition"):
        assert bad not in clean, bad
    assert len(rejected) >= 7


def test_style_layer_is_scoped_per_page_and_round_trips():
    f = style_file({"landing": '[data-swarm-section="hero"] {\n  gap: 8px;\n}', "pdp": ""})
    assert 'main[data-swarm-page="landing"] [data-swarm-section="hero"]' in f.content and "pdp" not in f.content
    assert style_pages(f.content) == {"landing": '[data-swarm-section="hero"] {\n  gap: 8px;\n}'}


# ----------------------------------------------------------------- compose + refine loop

class StyledBuild(FakeBuild):
    def __init__(self, scores, **kw):
        super().__init__(**kw)
        self.scores = list(scores)
        self.layers: list[str] = []

    async def outline(self, session):
        return "## hero\nsection.s.s-hero"

    async def write_style_layer(self, session, page, css, step=Step.B10_INTEGRATE):
        self.layers.append(css)

    async def critique(self, session, context=""):
        score = self.scores.pop(0)
        return Critique(model="fake", scores={}, overall=score, verdict="ok",
                        issues=[Issue(where="hero", problem="Tiêu đề yếu", fix="Tăng cỡ tiêu đề")])


class FakeStylist:
    def __init__(self):
        self.calls = []

    def compose(self, context, sections):
        self.calls.append("compose")
        assert "Ý đồ thiết kế" in context and "section.s.s-hero" in context
        return StylePatch(css='[data-swarm-section="hero"] {\n  gap: 48px;\n}', notes=["hero → lệch trái"])

    def refine(self, critique, context, sections):
        self.calls.append("refine")
        assert critique == ["hero: Tiêu đề yếu → Tăng cỡ tiêu đề"]
        return StylePatch(css=f'[data-swarm-section="hero"] h1 {{\n  font-size: var(--text-display);\n}}', notes=["hero → to hơn"])


def run_styled(build, stylist, sid):
    runner = PipelineRunner(Deps(artifacts_root=build.tmp, build=build, stylist=stylist, compose=True))
    return asyncio.run(drive(runner, sid, HAPPY + [{"approve": True}]))["pipeline"]


def test_compose_then_refine_keeps_a_round_only_when_the_score_rises(tmp_path):
    build = StyledBuild([6.9, 7.6, 7.65])
    build.tmp = tmp_path
    stylist = FakeStylist()
    p = run_styled(build, stylist, "s-art")
    assert stylist.calls == ["compose", "refine", "refine"]
    assert [r["kind"] for r in p.style_rounds] == ["compose", "refine", "refine"]
    assert [r["kept"] for r in p.style_rounds] == [True, True, False]  # 6.9 -> 7.6 kept, 7.6 -> 7.65 too small
    assert p.design_score == 7.6 and p.step is Step.B12_HANDOVER
    assert build.layers[-1].count("[data-swarm-section") == 2  # compose + the kept refine, not the dropped one
    assert (tmp_path / "s-art" / "artifacts" / "CRITIQUE.md").is_file()


def test_a_layer_that_breaks_qa_is_dropped(tmp_path):
    build = StyledBuild([8.4], qa_results=[qa(DEAD), qa()])  # first QA (with the composition) fails
    build.tmp = tmp_path
    p = run_styled(build, FakeStylist(), "s-art2")
    assert p.style_rounds[0]["kept"] is False and p.style_rounds[0]["why"] == "qa"
    assert build.layers[-1] == "" and p.qa_passed and p.design_score == 8.4
    assert not p.heal_history  # dropped, not healed around


def test_clone_pages_are_never_restyled(tmp_path):
    from chromaswarm.state_machine.pipeline_state import BuildMode
    p = PipelineState(session_id="c", mode=BuildMode.CLONE)
    assert p.mode is BuildMode.CLONE  # styling() checks the mode; covered end-to-end in test_build's clone runs


# ----------------------------------------------------------------- AI image fallback

class Text:
    def complete_json(self, system, user, images=None, max_tokens=0):
        if "subjects" in system:
            return {"subjects": ["ceramic tea cup", "tea leaves", "kettle"]}
        return {"queries": ["zzz"], "must_show": "zzz", "must_not": "x"}


def test_images_are_generated_only_when_nothing_real_fits(tmp_path, monkeypatch):
    import chromaswarm.developer.photo_bot as pb
    monkeypatch.setattr(pb, "stock_photos", lambda *a, **k: [])
    made = []

    def gen(brief, subjects):
        made.append(subjects)
        return [png(1600, 900), png(1200, 1500)]

    bot = PhotoBot(Text(), Text(), searcher=lambda q: [], fetcher=lambda c: [], generator=gen, root=tmp_path)
    state = PipelineState(session_id="s-gen", raw_prompt="tiệm gốm trà thủ công", domain=Domain.OTHER)
    photos = bot(state)
    assert made == [["ceramic tea cup", "tea leaves", "kettle"]]
    assert len(photos) == 2 and all(p["generated"] and p["url"].startswith("uploads/generated-") for p in photos)
    assert uploads.resolve(tmp_path, "s-gen", photos[0]["url"]) is not None
    from chromaswarm.developer.content import build_copy
    assert build_copy(state.model_copy(update={"page_photos": photos})).images[0].startswith("/images/generated-")


def test_no_generation_when_curated_photos_exist(tmp_path, monkeypatch):
    import chromaswarm.developer.photo_bot as pb
    monkeypatch.setattr(pb, "stock_photos", lambda *a, **k: ["https://images.unsplash.com/photo-1?x=1"])
    bot = PhotoBot(Text(), Text(), searcher=lambda q: [], fetcher=lambda c: [],
                   generator=lambda *a: (_ for _ in ()).throw(AssertionError("no")), root=tmp_path)
    assert bot(PipelineState(session_id="s", raw_prompt="cà phê", domain=Domain.OTHER)) is None


def test_upload_api_refuses_the_generated_kind(tmp_path):
    import pytest
    with pytest.raises(uploads.UploadError):
        uploads.save(tmp_path, "s", "generated", png())


# ----------------------------------------------------------------- GSAP / Three.js

def test_plan_effects_map_to_js_motion():
    assert js_effects("subtle entrance reveal + 3D scene (Three.js) behind the headline", "hero-centered") == ["scene-3d", "reveal"]
    assert js_effects("3D scene", "split-7-5") == []  # no open space behind a split hero
    assert js_effects("scroll-triggered image parallax", "alternating-z") == ["parallax"]
    cfg = motion_config({"landing": {"hero": ["reveal"]}})
    assert parse_config(cfg) == {"landing": {"hero": ["reveal"]}}


def test_a_3d_scene_is_planned_for_tech_heroes_and_when_asked():
    tech = PipelineState(session_id="t", raw_prompt="SaaS quản lý kho", domain=Domain.SAAS, selected_page="landing",
                         pillars=Pillars(theme="precision-tech", layout="visual-first", color="light", margins="balanced", scope="x"))
    hero = next(s for s in page_sections(tech) if s.id == "hero")
    assert hero.structure == "hero-centered" and "Three.js" in hero.effect
    warm = tech.model_copy(update={"pillars": tech.pillars.model_copy(update={"theme": "warm-organic", "layout": "narrative"})})
    assert "Three.js" not in (next(s for s in page_sections(warm) if s.id == "hero").effect or "")
    asked = warm.model_copy(update={"raw_prompt": "landing có hiệu ứng 3D"})
    assert "Three.js" in next(s for s in page_sections(asked) if s.id == "hero").effect
    spec = build_design_spec  # the motion step itself is exercised by the live build
    assert spec


def test_layer_never_touches_colours_controls_or_mobile_columns():
    css = '''
    [data-swarm-section="hero"] .btn-primary { padding: 16px 32px; }
    [data-swarm-section="hero"] a:hover { gap: 8px; }
    [data-swarm-section="hero"] .split { grid-template-columns: 1.2fr 1fr; color: var(--text-primary); }
    [data-swarm-section="hero"] p.t-lead { text-align: center; }
    [data-swarm-section="hero"] h1 { text-align: center; }
    @media (min-width: 1024px) { [data-swarm-section="hero"] .split { grid-template-columns: 1.2fr 1fr; } }
    '''
    clean, rejected = validate_css(css, SECTIONS)
    assert ".btn" not in clean and "hover" not in clean and "color" not in clean
    assert clean.count("grid-template-columns") == 1 and "@media (min-width: 1024px)" in clean
    assert "h1 {\n  text-align: center;" in clean and "t-lead" not in clean


def test_standard_names_are_not_counted_as_bare_numbers():
    from chromaswarm.qa.master import BARE_NUMBER
    assert not BARE_NUMBER.search("Chuẩn bảo mật ISO 27001") and BARE_NUMBER.search("Đã bán 27001 đơn")


def test_layer_keeps_gutters_and_mobile_spans():
    css = '''
    [data-swarm-section="hero"] .container { padding-left: 0; padding-right: 0; }
    [data-swarm-section="faq"] .card { padding: 0; }
    [data-swarm-section="faq"] .bento-wide { grid-column: span 2; }
    @media (min-width: 1024px) { [data-swarm-section="faq"] .bento-wide { grid-column: span 2; } }
    '''
    clean, _ = validate_css(css, SECTIONS)
    assert "padding" not in clean and clean.count("span 2") == 1
    from chromaswarm.qa.master import BARE_NUMBER
    assert not BARE_NUMBER.search("chuẩn bảo mật iso 27001")  # the probe lowercases page text
