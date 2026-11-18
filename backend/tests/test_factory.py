"""Clone: effect check (B2), component factory (B9) and the Master's 1:1 acceptance (B11)."""

import asyncio

from chromaswarm.clone import components as cmp
from chromaswarm.clone.motion_check import MotionReport, build_report, summary
from chromaswarm.mcp_motion.server import build_effect
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step
from tests.test_build import FakeBuild
from tests.test_clone import fake_reader

BOX = {"top": 0, "left": 0, "width": 1440, "height": 800}


def comp(kind, x, y, w, h, **kw):
    return cmp.Comp(kind=kind, x=x, y=y, w=w, h=h, **kw)


# ------------------------------------------------------------------ components

def test_components_pair_by_kind_and_position_and_name_the_differences():
    ref = [comp("heading", 100, 80, 800, 80, level=1, fs=64, fw=700, ls=-1.5),
           comp("button", 100, 220, 180, 52, fs=16, radius=999, pad=[16, 28, 16, 28]),
           comp("image", 760, 60, 600, 600, radius=24)]
    built = [comp("heading", 96, 90, 760, 70, level=1, fs=48, fw=600, ls=0, sel="h1.t-display", i=0),
             comp("button", 96, 230, 160, 48, fs=16, radius=8, pad=[12, 20, 12, 20], sel='[data-swarm-id="cta-primary"]', i=1),
             comp("text", 96, 300, 500, 60, fs=18, sel="p.t-lead", i=2)]
    pairs, missing, extra = cmp.match(ref, built, BOX, BOX)
    assert [(p.ref.kind, p.built.kind) for p in pairs] == [("heading", "heading"), ("button", "button")]
    assert [m.kind for m in missing] == ["image"] and [e.kind for e in extra] == ["text"]
    heading = pairs[0].diffs
    assert "cỡ chữ 64→48px" in heading and "độ đậm 700→600" in heading and any("giãn chữ" in d for d in heading)
    assert any("bo góc 999→8px" in d for d in pairs[1].diffs)


def test_section_score_rewards_matching_components_and_drops_with_missing_ones():
    ref = [comp("heading", 100, 80, 800, 80, fs=64), comp("button", 100, 220, 180, 52, radius=12)]
    same = [comp("heading", 100, 80, 800, 80, fs=64, i=0), comp("button", 100, 220, 180, 52, radius=12, i=1)]
    perfect, _ = cmp.section_score("hero", ref, same, BOX, BOX)
    half, _ = cmp.section_score("hero", ref, same[:1], BOX, BOX)
    assert perfect.score == 100
    assert half.score < 80 and half.missing == {"button": 1} and any("thiếu 1 nút" in d for d in half.diffs)


def test_tuning_moves_style_to_the_reference_on_desktop_only_and_never_shrinks_tap_targets():
    ref = [comp("heading", 0, 0, 800, 80, fs=64, fw=700, ls=-1.5, lh=1.05),
           comp("button", 0, 200, 140, 40, fs=14, radius=999, pad=[8, 16, 8, 16]),
           comp("text", 0, 300, 600, 40, fs=14, lh=1.2),
           comp("card", 0, 400, 300, 300, radius=20, shadow=True)]
    built = [comp("heading", 0, 0, 800, 70, fs=48, fw=400, ls=0, lh=1.2, sel="h2.t-h2", i=0),
             comp("button", 0, 200, 160, 48, fs=16, radius=8, pad=[12, 24, 12, 24], sel="a.btn.btn-primary", i=1),
             comp("text", 0, 300, 600, 40, fs=16, lh=1.6, sel="p.t-body", i=2),
             comp("card", 0, 400, 300, 300, radius=8, shadow=False, sel="article.card", i=3)]
    pairs, _, _ = cmp.match(ref, built, BOX, BOX)
    rules = cmp.tune_rules("hero", pairs, "clone")
    scope = '[data-swarm-page="clone"] [data-swarm-section="hero"]'
    h = rules[f"{scope} h2.t-h2"]
    assert h["font-size"] == "64px" and h["font-weight"] == "600" and h["letter-spacing"] == "-1.5px"
    btn = rules[f"{scope} a.btn.btn-primary"]
    assert btn["border-radius"] == "999px" and "padding" not in btn  # smaller reference padding: keep ≥48px targets
    assert "font-size" not in rules.get(f"{scope} p.t-body", {})  # body text never under 16px
    card = rules[f"{scope} article.card"]
    assert card["border-radius"] == "20px" and card["box-shadow"] == "var(--shadow-md)"
    css = cmp.render_rules({"clone:hero": rules})
    assert css.startswith("/* clone:hero */\n@media (min-width: 1200px) {")
    merged, changed = cmp.merge_rules(rules, rules)
    assert changed == 0 and merged == rules


def test_unsafe_selectors_are_never_written():
    p = cmp.Pair(ref=comp("heading", 0, 0, 10, 10, fs=60), built=comp("heading", 0, 0, 10, 10, fs=40, sel="h1{}body", i=0))
    assert cmp.tune_rules("hero", [p]) == {}


def test_compare_report_lists_sections_and_differences():
    res, _ = cmp.section_score("hero", [comp("heading", 0, 0, 800, 80, fs=64)],
                               [comp("heading", 0, 0, 800, 80, fs=40, i=0)], BOX, BOX, "Hero")
    md = cmp.render_compare({"total": res.score, "rounds": 1, "tuned": 3, "sections": [res.model_dump()]}, "https://x.dev")
    assert "Nghiệm thu 1:1 với https://x.dev" in md and "| Hero |" in md and "cỡ chữ 64→40px" in md


# ------------------------------------------------------------------ effect check

def test_effect_report_times_reveals_stagger_hover_and_marquee_per_section():
    boxes = {"hero": {"top": 0, "height": 900}, "grid": {"top": 900, "height": 900}, "logos": {"top": 1800, "height": 200}}
    timed = [{"top": 1000 + i * 10, "h": 300, "parent": 7, "fromOp": 0, "fromY": 40, "start": 20 + i * 100,
              "end": 620 + i * 100, "cssMs": 600, "ease": "cubic-bezier(0.16, 1, 0.3, 1)"} for i in range(4)]
    post = {"revealed": [], "marquee": [{"top": 1850, "h": 80, "cycle": 25}], "libs": ["GSAP"], "unsupported": [],
            "sticky": True, "blurPx": 12, "smooth": False,
            "hover": [{"top": 1100, "h": 300, "kind": "card", "effects": ["hover-lift"],
                       "params": {"duration_ms": 250, "easing": "ease-out", "lift_px": 6, "scale": 1, "zoom": 1}}]}
    r = build_report(boxes, timed, post, [], steps=5)
    assert r.has_motion and r.per_section["grid"] == ["stagger-cards", "hover-lift"]
    stagger = r.params["grid"]["stagger-cards"]
    assert stagger == {"duration_ms": 600, "distance_px": 40, "easing": "cubic-bezier(0.16, 1, 0.3, 1)", "stagger_ms": 100}
    assert r.params["grid"]["hover-lift"]["distance_px"] == 6
    assert r.params["logos"]["marquee"]["cycle_s"] == 25
    assert r.params["site-header"]["sticky-blur"]["blur_px"] == 12
    how = next(i.how for i in r.items if i.effect == "stagger-cards")
    assert "trượt lên 40px" in how and "600ms" in how and "trễ 100ms" in how
    assert "tìm thấy" in summary(r) and "GSAP" in summary(r)


def test_a_still_page_is_reported_as_having_no_effects():
    r = build_report({"hero": {"top": 0, "height": 900}}, [], {"hover": []}, [], steps=3, header=None)
    assert not r.has_motion and "không có hiệu ứng" in summary(r)


def test_measured_parameters_shape_the_motion_css():
    lift = build_effect("hover-lift", "grid", 250, "ease-out", distance_px=6, scale=1.02)["css"]
    assert "translateY(-6px) scale(1.02)" in lift and "250ms ease-out" in lift
    assert "18s linear infinite" in build_effect("marquee", "logos", cycle_s=18)["css"]
    assert "blur(10px)" in build_effect("sticky-blur", "site-header", blur_px=10)["css"]
    stagger = build_effect("stagger-cards", "grid", 600, "ease", distance_px=40, stagger_ms=100)["css"]
    assert "translateY(40px)" in stagger and "nth-child(2) { animation-range: entry 4% entry 84%; }" in stagger
    assert "error" in build_effect("hover-lift", "grid", easing="steps(4)")  # unknown easing is still refused


# ------------------------------------------------------------------ graph

def _with_boxes(reader):
    async def read(url, owned):
        a = await reader(url, owned)
        a.boxes = {"hero": {"top": 0, "left": 0, "width": 1440, "height": 800},
                   "grid-4": {"top": 800, "left": 0, "width": 1440, "height": 900}}
        a.components = {"hero": [comp("heading", 100, 80, 800, 80, fs=64).model_dump()]}
        return a
    return read


def test_effect_check_is_a_pass_of_its_own_and_feeds_the_sections(tmp_path):
    calls = []

    async def check(url, boxes):
        calls.append(sorted(boxes))
        return MotionReport(has_motion=True, per_section={"grid-4": ["stagger-cards"]}, steps=4, hovered=3,
                            params={"grid-4": {"stagger-cards": {"duration_ms": 500, "stagger_ms": 90}}})

    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=_with_boxes(fake_reader()), motion_check=check))
    notices = []

    async def seen(snap):
        notices.append(snap["notice"] or "")

    async def run():
        await runner.start("m1")
        await runner.answer("m1", "clone")
        return await runner.answer("m1", {"url": "https://gom-moc.vn"}, seen)
    p = asyncio.run(run())["pipeline"]
    assert calls == [["grid-4", "hero"]]
    assert any("Tiếp theo: kiểm tra hiệu ứng" in n for n in notices)
    assert p.clone.motion_checked and p.clone.motion_report["has_motion"]
    grid = next(s for s in p.clone.sections if s["id"] == "grid-4")
    assert grid["motion"] == ["stagger-cards"] and grid["motion_params"]["stagger-cards"]["stagger_ms"] == 90


def test_effect_check_failure_never_blocks_the_clone(tmp_path):
    async def check(url, boxes):
        raise RuntimeError("browser crashed")

    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader(), motion_check=check))

    async def run():
        await runner.start("m2")
        await runner.answer("m2", "clone")
        return await runner.answer("m2", {"url": "https://gom-moc.vn"})
    p = asyncio.run(run())["pipeline"]
    assert p.step is Step.B7_APPROVAL and p.clone.motion_report["error"] == "browser crashed"


class AcceptBuild(FakeBuild):
    def __init__(self, tuned_rounds):
        super().__init__()
        self.tuned_rounds = list(tuned_rounds)
        self.refs = None

    def set_reference(self, session, components, boxes, names=None, page=""):
        self.refs = (sorted(components), page)

    async def compare(self, session, url, sections, boxes, page="", shots=None):
        tuned = self.tuned_rounds.pop(0) if self.tuned_rounds else 0
        self.log.append(f"compare:{tuned}")
        return {"total": 91.0 if not tuned else 78.0, "tuned": tuned,
                "sections": [{"id": "hero", "name": "Hero", "score": 91.0, "parts": {"components": 1, "layout": .9, "style": .8, "height": 1},
                              "matched": 3, "missing": {}, "extra": {}, "diffs": [], "ref_height": 800, "built_height": 790,
                              "effects_missing": [], "ref_image": None, "built_image": None}]}


def test_master_accepts_1to1_after_qa_and_rechecks_after_tuning(tmp_path):
    fake = AcceptBuild(tuned_rounds=[4, 0])
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake, clone_reader=_with_boxes(fake_reader())))

    async def run():
        await runner.start("a1")
        await runner.answer("a1", "clone")
        await runner.answer("a1", {"url": "https://gom-moc.vn"})
        return await runner.answer("a1", {"approve": True})
    p = asyncio.run(run())["pipeline"]
    assert p.step is Step.B12_HANDOVER and p.qa_passed
    assert fake.refs == (["hero"], "clone")
    flow = [x for x in fake.log if x == "qa" or x.startswith("compare")]
    assert flow == ["qa", "compare:4", "qa", "compare:0"]  # tuned -> QA again -> compare again
    assert p.compare_rounds == 1 and p.clone_compare["total"] == 91.0
    assert (tmp_path / "a1" / "artifacts" / "COMPARE.md").exists()


def test_a_pill_nav_link_pairs_with_a_plain_link_for_half_credit_and_only_its_type_is_tuned():
    ref = [comp("button", 900, 20, 90, 36, fs=16, radius=999, pad=[8, 16, 8, 16], bg="#eeeeee")]
    built = [comp("link", 900, 22, 80, 24, fs=14, sel="a.nav-link", i=0)]
    pairs, missing, extra = cmp.match(ref, built, BOX, BOX)
    assert len(pairs) == 1 and not missing and not extra
    assert pairs[0].diffs[0] == "nút ở trang mẫu, link ở bản dựng"
    res, _ = cmp.section_score("site-header", ref, built, BOX, BOX)
    assert res.parts["components"] == 0.5
    rules = cmp.tune_rules("site-header", pairs)
    assert list(rules.values()) == [{"font-size": "16px"}]  # no radius / padding on a different kind


# ------------------------------------------------------------------ measured layout

def test_xy_cut_rebuilds_rows_and_columns_and_cards_hold_their_pieces():
    from chromaswarm.clone.layout import build_tree
    pieces = [comp("heading", 100, 40, 600, 80, fs=56),
              comp("card", 100, 200, 380, 300, radius=16), comp("image", 100, 200, 380, 220), comp("heading", 120, 440, 300, 30, fs=20),
              comp("card", 530, 200, 380, 300, radius=16), comp("image", 530, 200, 380, 220), comp("heading", 550, 440, 300, 30, fs=20)]
    tree = build_tree(pieces)
    assert tree.kind == "rows" and [c.kind for c in tree.children] == ["heading", "cols"]
    cards = tree.children[1].children
    assert [c.kind for c in cards] == ["card", "card"]
    assert [k.kind for k in cards[0].children] == ["image", "heading"]


def test_text_over_a_picture_becomes_a_layer_with_the_picture_behind():
    from chromaswarm.clone.layout import build_tree
    tree = build_tree([comp("image", 300, 0, 800, 800), comp("heading", 100, 200, 1200, 200, fs=96),
                       comp("button", 1000, 700, 140, 48)])
    assert tree.kind == "layer" and tree.children[1].kind == "back-image"


def test_measured_section_places_pieces_at_their_measured_spot_on_desktop_only():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import PipelineState
    layout = [comp("heading", 120, 96, 600, 128, fs=64, fw=500, ls=-2, lh=1).model_dump(),
              comp("text", 840, 100, 480, 72, fs=18, lh=1.5, color="#555555").model_dump(),
              comp("button", 840, 200, 160, 48, radius=999, pad=[12, 24, 12, 24], bg="#111111").model_dump(),
              comp("image", 120, 320, 1200, 520, radius=12).model_dump()]
    sec = Section(id="feature-showcase", name="Showcase", structure="feature-showcase", content="x",
                  layout=layout, layout_box={"top": 0, "left": 0, "width": 1440, "height": 920})
    words: dict = {}
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content=words).content
    assert "m-rows" in code and "m-cols" in code and 'data-swarm-id="feature-showcase-btn-' in code
    assert "@media (min-width: 1200px)" in code and "font-size: 64px" in code and "letter-spacing: -2px" in code
    assert "padding-top: 96px" in code and "padding-bottom: 80px" in code  # the reference's own space
    assert 'ratio="1200 / 520"' in code and "border-radius: 999px" in code
    assert set(words["feature-showcase"]) >= {"heading", "text", "button", "image_alt"}  # words in content/, editable
    assert "<h2" in code  # only a hero gets the page's h1


def test_interactive_structures_keep_their_template():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.measured import measurable
    layout = [comp("heading", 0, 0, 100, 40).model_dump(), comp("text", 0, 60, 100, 40).model_dump()]
    assert not measurable(Section(id="faq", name="FAQ", structure="accordion", content="x", layout=layout))
    assert measurable(Section(id="site-header", name="H", structure="sticky-bar", content="x", layout=layout))
    assert measurable(Section(id="hero", name="H", structure="split-7-5", content="x", layout=layout))


def test_a_measured_header_links_to_the_sites_real_pages_and_gets_a_monogram_not_a_photo():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import PipelineState
    layout = [comp("image", 48, 20, 32, 32).model_dump(), comp("link", 600, 24, 60, 24, fs=14, chars=5).model_dump(),
              comp("link", 700, 24, 70, 24, fs=14, chars=8).model_dump()]
    sec = Section(id="site-header", name="Header", structure="sticky-bar", content="x", layout=layout,
                  layout_box={"top": 0, "left": 0, "width": 1440, "height": 72})
    copy = build_copy(PipelineState(session_id="s", raw_prompt="x"))
    words: dict = {}
    code = render_section(sec, copy, "clone", content=words).content
    assert "m-mark" in code and "<Art" not in code
    assert words["site-header"]["href"] == copy.nav_links[0][1] and words["site-header"]["link"] == copy.nav_links[0][0]


def test_reference_measuring_handles_split_headlines_carousels_wrappers_and_wordmarks():
    """The reader's component JS on a page built to contain each trap the alex-lehmann.com clone hit."""
    from playwright.async_api import async_playwright
    from chromaswarm.clone.components import COMPONENTS_JS
    html = """<body style="margin:0;font:16px sans-serif">
    <section style="position:relative;height:900px">
      <h1 style="position:absolute;inset:0;display:grid;grid-template-columns:1fr 1fr;align-items:start;font-size:120px;margin:0">
        <span style="display:block;width:400px;margin:100px 0 0 100px">Left half</span>
        <span style="display:block;width:400px;margin:100px 0 0 100px">Right half</span></h1>
      <div style="display:contents;opacity:0"><p style="position:absolute;top:700px;left:100px;width:400px">Shown text</p></div>
      <div style="position:absolute;top:500px;left:900px;width:300px;height:200px;overflow:hidden">
        <img style="position:absolute;left:0;width:300px;height:200px" src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">
        <img style="position:absolute;left:300px;width:300px;height:200px" src="data:image/gif;base64,R0lGODlhAQABAAAAACw="></div>
      <p style="position:absolute;top:780px;left:100px;opacity:0">Hover only</p>
      <div aria-hidden="true" style="position:absolute;top:800px;left:0;width:1440px"><span style="font-size:80px">Wordmark</span></div>
      <button style="position:absolute;top:400px;left:300px;background:none;border:0">
        <span style="display:block;font-size:100px">mail@site</span><span style="display:block;font-size:12px">copy</span></button>
    </section></body>"""

    async def run():
        async with async_playwright() as pw:
            b = await pw.chromium.launch()
            p = await b.new_page(viewport={"width": 1440, "height": 900})
            await p.set_content(html)
            r = await p.evaluate(COMPONENTS_JS, {"boxes": [{"key": "s", "top": 0, "left": 0, "width": 1440, "height": 900}],
                                                 "built": False, "limit": 60})
            await b.close()
            return r["comps"]["s"]
    got = asyncio.run(run())
    kinds = [(c["kind"], c["fs"], c["chars"]) for c in got]
    heads = [c for c in got if c["kind"] == "heading" and c["fs"] == 120]
    assert len(heads) == 2 and all(c["w"] <= 420 for c in heads)  # two halves, not the 1440px h1 box
    assert ("text", 16, 10) in kinds  # behind a box-less transparent wrapper: still visible
    assert sum(c["kind"] == "image" for c in got) == 1  # the slide parked outside its frame is skipped
    assert not any(c["chars"] == 10 and c["y"] > 770 and c["kind"] == "text" and c["fs"] == 16 and c["x"] == 100
                   and c["y"] < 790 for c in got)  # hover-only paragraph skipped
    assert any(c["fs"] == 80 for c in got)  # aria-hidden wordmark is still seen
    assert ("link", 100, 9) in kinds and ("text", 12, 4) in kinds  # big email split from its small caption


def test_one_line_and_centred_pieces_stay_one_line_and_centred():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import PipelineState
    layout = [comp("heading", 651, 140, 138, 37, fs=37, chars=10).model_dump(),
              comp("text", 120, 600, 1200, 120, fs=18, lh=1.5, chars=300).model_dump()]
    sec = Section(id="site-footer", name="Footer", structure="footer-columns", content="x", layout=layout,
                  layout_box={"top": 0, "left": 0, "width": 1440, "height": 800})
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content={}).content
    head_rule = next(line for line in code.split("\\n") if ".n1 {" in line)
    assert "white-space: nowrap" in head_rule and "margin-left: auto" in head_rule and "text-align: center" in head_rule
    body_rule = next(line for line in code.split("\\n") if ".n2 {" in line)
    assert "nowrap" not in body_rule and "%" in body_rule
