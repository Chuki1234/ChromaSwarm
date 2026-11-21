"""CLONE_BRIEF.md and the reading it depends on: destinations, vertical marquees, intro animations, hover lift,
FAQ vs feature rows — offline (no browser)."""

from chromaswarm.clone.brief_doc import build_brief
from chromaswarm.clone.motion import classify_destination, hover_params
from chromaswarm.clone.motion_check import add_intro, build_report
from chromaswarm.clone.reader import sections_from_blocks
from chromaswarm.state_machine.pipeline_state import CloneSource


def test_destinations_are_classified_by_path_never_by_words():
    page = "https://example.com/"
    assert classify_destination("https://example.com/auth-minimal", page) == {
        "kind": "internal", "target": "/auth-minimal", "role": "đăng nhập / đăng ký"}
    assert classify_destination("https://example.com/terms", page)["role"] == "pháp lý"
    assert classify_destination("https://www.example.com/#faq", page)["kind"] == "same-page"
    assert classify_destination("https://x.com/someone", page) == {"kind": "external", "target": "x.com"}


def test_vertical_marquee_is_reported_but_not_sent_to_the_motion_server():
    boxes = {"hero": {"top": 0, "height": 900}, "testimonials": {"top": 900, "height": 1200}}
    post = {"marquee": [{"top": 1000, "h": 1100, "w": 560, "cycle": 30, "axis": "y", "reverse": False},
                        {"top": 1000, "h": 1100, "w": 560, "cycle": 30, "axis": "y", "reverse": True},
                        {"top": 100, "h": 80, "w": 1200, "cycle": 20, "axis": "x"}]}
    r = build_report(boxes, [], post, [], 3)
    assert "marquee" in r.per_section["hero"]  # sideways: the Motion MCP builds it
    assert "marquee-vertical" not in r.per_section.get("testimonials", [])  # up / down: reported only
    item = next(i for i in r.items if i.effect == "marquee-vertical")
    assert item.section == "testimonials" and "2 cột" in item.how and "ngược chiều" in item.how and "30s" in item.how


def test_intro_animations_and_loops_are_described_from_their_keyframes():
    r = build_report({"hero": {"top": 0, "height": 900}}, [], {}, [], 1)
    add_intro(r, {"hero": {"top": 0, "height": 900}}, {
        "intro": [{"top": 0, "left": 0, "w": 1128, "h": 900, "name": "skewUp", "dur": 1000, "delay": 0, "easing": "linear",
                   "from": "transform: skew(-20deg) translateY(540px); opacity: 0", "to": "transform: skew(-20deg) translateY(0px); opacity: 1"}],
        "loops": []})
    item = next(i for i in r.items if i.effect == "load-in")
    assert "skewUp" in item.how and "1000ms" in item.how and "translateY(540px)" in item.how
    assert r.has_motion and "load-in" not in r.per_section.get("hero", [])


def test_a_hover_never_reads_a_page_scroll_as_a_lift():
    snap = {"tf": "none", "shadow": "none", "imgTf": None, "dur": 250, "ease": "ease", "top": 400}
    assert hover_params(snap, {**snap, "top": 396})["lift_px"] == 4
    assert hover_params(snap, {**snap, "top": 400 - 6132})["lift_px"] == 0  # the track moved, not the card


def _block(i, **f):
    base = dict(tag="section", role=None, index=i, height=600, top=i * 600, left=0, width=1440, h1=False, headings=1,
                lead_text=0, nav=False, links=0, buttons=0, inputs=0, password=False, accordion=0, questions=0, tablist=False,
                images=0, big_image=False, bg_differs=False, bg_image=False, columns=1, scroller=False, text_len=300,
                prices=0, numeric_items=0, card_widths=[], quotes=0, rows=0, row_items_with_img=0, logos=0, padding_y=0, motion=[])
    return {"features": {**base, **f}}


def test_rows_that_open_are_an_faq_only_when_they_ask_questions():
    blocks = [_block(0, tag="nav", nav=True, height=64), _block(1, h1=True, images=1),
              _block(2, accordion=4, questions=0), _block(3, accordion=6, questions=6), _block(4, tag="footer", links=8)]
    ids = [s.id for s in sections_from_blocks(blocks)]
    assert "feature-accordion" in ids and "faq" in ids


def test_brief_covers_every_part_and_says_what_is_not_cloned():
    clone = CloneSource(
        url="https://example.com/", title="Example", lang="en", fonts=[{"family": "Lexend"}],
        sections=[{"id": "hero", "name": "Hero", "structure": "split-7-5"},
                  {"id": "testimonials", "name": "Lời khách hàng", "structure": "testimonials"},
                  {"id": "faq", "name": "Hỏi đáp", "structure": "accordion"}],
        boxes={"hero": {"top": 0, "height": 800, "width": 1440, "bg": "#050505", "band": True},
               "testimonials": {"top": 800, "height": 600, "width": 1440}, "faq": {"top": 1400, "height": 700, "width": 1440}},
        components={"hero": [{"kind": "heading", "x": 96, "y": 300, "w": 600, "h": 120, "fs": 60, "fw": 700, "level": 1},
                             {"kind": "text", "x": 96, "y": 452, "w": 560, "h": 84, "fs": 18},
                             {"kind": "button", "x": 96, "y": 564, "w": 190, "h": 48, "fs": 16}]},
        style={"surfaces": [{"css": "oklch(100% 0 0)", "share": 0.7}], "text_colors": [], "accents": [{"css": "oklch(68% 0.2 146)", "share": 0.6}],
               "spacing_adherence": 0.9, "common_spacing": [8, 16, 24], "density": "airy", "radius_median": 16, "separation": "borders",
               "base_font_px": 16, "type_scale_ratio": 1.39, "uppercase_labels": True, "is_dark": False, "accent_usage": "restrained"},
        backgrounds=[{"kind": "glow", "top": 0, "left": 0, "w": 520, "h": 520, "css": "radial-gradient(circle, #0f0 0%, transparent 70%)"}],
        media=[{"kind": "img", "top": 200, "left": 860, "w": 275, "h": 350, "nw": 700, "nh": 890, "file": 0, "icon": False},
               {"kind": "img", "top": 600, "left": 860, "w": 275, "h": 350, "nw": 700, "nh": 890, "file": 0, "icon": False},
               {"kind": "svg", "top": 560, "left": 250, "w": 20, "h": 20, "file": None, "icon": True}],
        motion_report={"items": [{"effect": "hover-lift", "section": "hero", "label": "Nổi lên khi rê chuột", "how": "nổi lên 2px, 250ms"}],
                       "controls": [{"section": "hero", "kind": "button", "w": 190, "h": 48, "changes": ["đổi màu nền"], "duration_ms": 250,
                                     "action": {"kind": "internal", "target": "/signup", "role": "đăng nhập / đăng ký"}},
                                    {"section": "faq", "kind": "link", "w": 80, "h": 20, "changes": [],
                                     "action": {"kind": "internal", "target": "/old", "broken": 404}}],
                       "steps": 4, "hovered": 2})
    md = build_brief(clone, "saas")
    for part in ("## 1. Trang này là gì", "## 2. Layout", "## 3. Khoảng cách", "## 4. Chữ, màu, nền", "## 5. Hình",
                 "## 6. Nút và link", "## 7. Hiệu ứng", "## 8. Clone được gì"):
        assert part in md
    assert "đăng nhập / đăng ký" in md and "Mục tiêu chuyển đổi" in md
    assert "| 96 / " in md or "96 /" in md  # hero side margin measured
    assert "×2" in md  # the same picture shown twice
    assert "link hỏng (404)" in md
    assert "CloneSpec" in md and "| 2 hình | Hình |" in md  # pictures grouped: replaced by placeholders
    assert "lời và tên người thật" in md and "| Icon |" in md and "### ⛔ Không dựng (skip)" in md
    assert "radial" in md and "Lexend" in md


def _spec_clone(**kw):
    base = dict(
        url="https://example.com/", sections=[{"id": "hero", "name": "Hero", "structure": "split-7-5", "content": "x"},
                                              {"id": "faq", "name": "Hỏi đáp", "structure": "accordion", "content": "x"},
                                              {"id": "blog", "name": "Bài viết", "structure": "bento", "content": "x"}],
        boxes={"hero": {"top": 0, "height": 900, "width": 1440}, "faq": {"top": 900, "height": 600, "width": 1440},
               "blog": {"top": 1500, "height": 500, "width": 1440}},
        backgrounds=[{"kind": "gradient", "top": 0, "left": -160, "w": 1128, "h": 900, "css": "linear-gradient(100deg, red, transparent)",
                      "tf": "matrix(1, 0, -0.36, 1, 0, 0)", "blur": "blur(12px)", "opacity": 1},
                     {"kind": "gradient", "top": 1000, "left": 200, "w": 24, "h": 24, "css": "linear-gradient(red, blue)"}],
        motion_report={
            "intro": [{"top": 0, "left": -160, "w": 1128, "h": 900, "name": "skewUp", "dur": 1000, "delay": 0, "easing": "linear",
                       "from": "transform: translateY(540px); opacity: 0", "to": "transform: translateY(0px); opacity: 1"}],
            "items": [{"effect": "load-in", "section": "hero", "label": "Hiệu ứng khi tải trang", "how": "…", "params": {"duration_ms": 1000}},
                      {"effect": "parallax", "section": "blog", "label": "Parallax", "how": "…", "params": {"distance_px": 30}},
                      {"effect": "marquee-vertical", "section": "faq", "label": "Cột chạy dọc", "how": "…", "params": {"cycle_s": 30}}],
            "controls": [{"section": "hero", "kind": "button", "top": 600, "left": 96, "w": 190, "h": 48,
                          "action": {"kind": "internal", "target": "/auth", "role": "đăng nhập / đăng ký"}},
                         {"section": "hero", "kind": "link", "top": 640, "left": 320, "w": 80, "h": 20,
                          "action": {"kind": "same-page", "target": "#faq"}},
                         {"section": "faq", "kind": "button", "top": 1000, "left": 700, "w": 536, "h": 84, "action": {"kind": "toggle"}},
                         {"section": "blog", "kind": "link", "top": 1900, "left": 100, "w": 60, "h": 20,
                          "action": {"kind": "external", "target": "x.com"}}]})
    base.update(kw)
    return CloneSource(**base)


def test_spec_decides_hrefs_layers_and_effects_the_build_uses():
    from chromaswarm.clone.spec import build_spec
    spec = build_spec(_spec_clone())
    hero = spec.controls("hero")
    assert {c["href"] for c in hero} == {"#dang-ky", "#faq"}  # sign-up → named placeholder; in-page link → rebuilt section
    assert hero[0]["y"] == 600 and hero[0]["x"] == 96  # section-relative box, for matching the rendered control
    assert spec.goal == "đăng nhập / đăng ký"
    layers = spec.layers("hero")
    assert len(layers) == 1 and layers[0]["intro"]["dur"] == 1000  # the beam layer carries its own intro
    assert spec.layers("faq") == []  # a 24px gradient is part of a component, not a background layer
    assert "reveal" not in spec.effects("hero")  # the intro is played by the layer, not as a section reveal
    assert spec.effects("blog") == {"parallax": {"distance_px": 30}}
    todo = [i for i in spec.items if i.kind == "effect" and spec.action(i) == "todo"]
    assert [i.data["label"] for i in todo] == ["Cột chạy dọc"]
    faq_row = next(i for i in spec.items if i.kind == "control" and i.section == "faq")
    assert spec.action(faq_row) == "copy"  # an accordion row opens for real in the rebuild


def test_user_overrides_skip_a_section_and_the_plan_drops_it():
    from chromaswarm.agents.planner import page_sections
    from chromaswarm.clone.spec import apply_overrides, build_spec
    from chromaswarm.state_machine.pipeline_state import PipelineState
    clone = _spec_clone()
    spec = build_spec(clone)
    changed = apply_overrides(spec, {"section:blog": "skip", "section:nope": "skip", "section:hero": "bogus"})
    assert changed == ["Bài viết: không dựng"] and spec.skipped_sections() == {"blog"}
    clone.spec = spec.model_dump()
    p = PipelineState(session_id="s", raw_prompt="x", selected_page="clone", clone=clone)
    assert [s.id for s in page_sections(p)] == ["hero", "faq"]


def test_the_build_follows_the_spec_links_and_painted_layers():
    from chromaswarm.agents.planner import Section
    from chromaswarm.clone.spec import build_spec
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import PipelineState
    clone = _spec_clone()
    spec = build_spec(clone)
    layout = [{"kind": "heading", "x": 96, "y": 300, "w": 700, "h": 120, "fs": 60, "fw": 700, "chars": 34, "level": 1},
              {"kind": "button", "x": 96, "y": 600, "w": 190, "h": 48, "fs": 16, "bg": "#16a34a", "color": "#ffffff", "chars": 12},
              {"kind": "link", "x": 320, "y": 640, "w": 80, "h": 20, "fs": 16, "chars": 8},
              {"kind": "link", "x": 900, "y": 640, "w": 80, "h": 20, "fs": 16, "chars": 8}]
    sec = Section(id="hero", name="Hero", structure="split-7-5", content="x", layout=layout,
                  layout_box={"top": 0, "left": 0, "width": 1440, "height": 900, "bg": "#050505"},
                  links=spec.controls("hero"), paint=spec.layers("hero"))
    words: dict = {}
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content=words).content
    hrefs = [v for k, v in words["hero"].items() if k.startswith("href")]
    assert sorted(hrefs) == ["#dang-ky", "#faq"]  # the unmatched link stays "#"
    assert 'className="m-paint m-paint-0" aria-hidden="true"' in code and "linear-gradient(100deg, red, transparent)" in code
    assert "@keyframes cs-paint-hero-0" in code and "translateY(540px)" in code and "1000ms linear" in code
    assert "prefers-reduced-motion" in code


def test_giant_faint_type_is_decoration_and_is_not_rebuilt():
    from chromaswarm.clone.components import comps
    from chromaswarm.developer.measured import drop_faint_type
    pieces = comps([{"kind": "heading", "x": 140, "y": 500, "w": 1160, "h": 300, "fs": 317, "color": "#ffffff0a", "chars": 6},
                    {"kind": "heading", "x": 140, "y": 40, "w": 400, "h": 60, "fs": 48, "color": "#ffffff", "chars": 20}])
    assert [c.fs for c in drop_faint_type(pieces)] == [48]
