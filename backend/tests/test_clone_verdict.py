"""Clone DESIGN.md extracted backwards, Master QA's item-by-item check against it, and the verdict."""

from chromaswarm.clone.conformance import check
from chromaswarm.clone.design_extract import extract, render
from chromaswarm.clone.verdict import judge, render as render_verdict
from chromaswarm.state_machine.pipeline_state import CloneSource, PipelineState

HERO = [{"kind": "heading", "x": 96, "y": 344, "w": 672, "h": 120, "fs": 60, "fw": 700, "lh": 1.0, "color": "#ffffff", "chars": 34, "i": 0},
        {"kind": "text", "x": 96, "y": 496, "w": 576, "h": 84, "fs": 18, "fw": 400, "lh": 1.55, "color": "#d1d5db", "chars": 145, "i": 1},
        {"kind": "button", "x": 96, "y": 608, "w": 198, "h": 48, "fs": 15, "fw": 600, "bg": "#00b83d", "color": "#ffffff",
         "radius": 9999, "pad": [10, 24, 10, 24], "chars": 13, "i": 2},
        {"kind": "image", "x": 868, "y": 30, "w": 275, "h": 348, "radius": 8, "i": 3}]
WHY = [{"kind": "heading", "x": 112, "y": 178, "w": 576, "h": 50, "fs": 40, "fw": 600, "lh": 1.25, "color": "#111827", "chars": 20, "i": 0},
       {"kind": "text", "x": 112, "y": 252, "w": 576, "h": 140, "fs": 18, "fw": 400, "lh": 1.55, "color": "#4b5563", "chars": 400, "i": 1}]


def _clone():
    return CloneSource(url="https://example.com/", title="Example", fonts=[{"family": "Lexend", "provider": "google"}],
                       sections=[{"id": "hero", "name": "Hero", "structure": "split-7-5"}, {"id": "why", "name": "Why", "structure": "bento"}],
                       boxes={"hero": {"top": 0, "left": 0, "width": 1440, "height": 900, "bg": "#050505", "band": True},
                              "why": {"top": 900, "left": 0, "width": 1440, "height": 520, "bg": "#ffffff"}},
                       components={"hero": HERO, "why": WHY},
                       motion_report={"items": [{"effect": "parallax", "section": "why", "label": "Parallax", "how": "…", "params": {"distance_px": 30}}],
                                      "controls": [{"top": 608, "left": 96, "w": 198, "h": 48, "changes": ["đổi màu nền"], "duration_ms": 250,
                                                    "action": {"kind": "internal", "target": "/signup"}}]})


def test_design_is_extracted_backwards_with_tokens_variants_and_section_specs():
    d = extract(_clone())
    assert d["colors"]["bg/page"]["value"] == "#050505" and d["colors"]["text/primary"]["value"] in ("#4b5563", "#d1d5db", "#111827")
    assert d["colors"]["accent/primary"]["value"] == "#00b83d"
    assert d["type"]["display"]["size"] == 60 and d["type"]["h1"]["size"] == 40  # 60px opens the scale as display
    btn = d["components"]["button/primary"]
    assert btn["w"] == 198 and btn["radius"] == 9999 and btn["hover"] == ["đổi màu nền"]
    hero = d["sections"][0]
    assert hero["box"]["bg"] == "bg/page" and hero["padding"]["top"] == 30
    row = next(r for r in hero["components"] if r["kind"] == "button")
    assert row["variant"] == "button/primary" and row["click"] == "internal" and row["to"] == "/signup"
    md = render(d)
    assert "trích ngược" in md and "| `button/primary` |" in md and "### 1. Hero" in md and "Parallax" in md


def test_the_rebuild_is_checked_item_by_item_against_it():
    d = extract(_clone())
    good = check(d, {"hero": HERO, "why": WHY}, {"hero": {"height": 900, "width": 1440}, "why": {"height": 520, "width": 1440}})
    assert good["passed"] == good["total"] and good["total"] > 10
    off = [dict(c) for c in HERO]
    off[0]["fs"] = 48  # the headline came out smaller
    off[2]["bg"] = "#ffffff"  # the primary button lost its fill
    bad = check(d, {"hero": off[:3]}, {"hero": {"height": 900, "width": 1440}}, effects_missing={"why": ["parallax"]})
    hero = next(s for s in bad["sections"] if s["id"] == "hero")
    joined = " | ".join(hero["failed"])
    assert "cỡ chữ 60→48px" in joined and "nền #00b83d→#ffffff" in joined and "thiếu trên bản dựng" in joined
    why = next(s for s in bad["sections"] if s["id"] == "why")
    assert why["failed"][0].startswith("Có section")


def _state(qa=True):
    p = PipelineState(session_id="v", raw_prompt="x", clone=_clone())
    p.qa_passed = qa
    p.qa_failures = [] if qa else ["Tap target 32px < 48px (mobile)"]
    return p


def test_verdict_is_conformance_to_the_reference_design():
    d = extract(_clone())
    built = {"hero": HERO, "why": WHY}
    boxes = {"hero": {"height": 900, "width": 1440}, "why": {"height": 520, "width": 1440}}
    full = check(d, built, boxes)
    v = judge(_state(), full)
    assert v.status == "success" and f"{full['passed']}/{full['total']}" in v.title
    assert judge(_state(qa=False), full).status == "failed"
    assert judge(_state(), None).status == "failed"  # not checked is not a pass
    md = render_verdict(v, "https://example.com/")
    assert "✅ Clone thành công" in md and "| Hero · `hero` |" in md and "Chỉ số tham khảo" in md


def test_unreadable_reference_colours_keep_their_hue_and_still_count_as_matching():
    from chromaswarm.clone.conformance import _same_hue
    from chromaswarm.developer.measured import readable_variant
    green = readable_variant("#00ae34", "#ffffff", False)
    assert green != "#00ae34" and _same_hue("#00ae34", green)  # darker green, not black
    assert readable_variant("#111827", "#ffffff", False) == "#111827"  # already readable: untouched
    assert not _same_hue("#00ae34", "#111111")  # turned black: a real difference


def test_centred_words_are_judged_by_their_line_and_frames_by_their_picture():
    ref = [{"kind": "heading", "x": 340, "y": 148, "w": 760, "h": 40, "fs": 36, "fw": 500, "lh": 1.1, "color": "#0d0d10",
            "chars": 30, "tw": 520, "tx": 120, "i": 0},
           {"kind": "card", "x": 1001, "y": 96, "w": 235, "h": 295, "i": 1},
           {"kind": "image", "x": 1002, "y": 97, "w": 233, "h": 293, "i": 2}]
    clone = CloneSource(url="https://example.com/", sections=[{"id": "s", "name": "S", "structure": "bento"}],
                        boxes={"s": {"top": 0, "left": 0, "width": 1440, "height": 500, "bg": "#ffffff"}}, components={"s": ref})
    d = extract(clone)
    built = [{**ref[0], "x": 450, "w": 540, "tw": 520, "tx": 10, "sel": "h2.n1"},  # box shrunk around the same line
             {"kind": "image", "x": 1002, "y": 97, "w": 233, "h": 293, "i": 1, "sel": "div.n2"}]  # the frame became the picture
    res = check(d, {"s": built}, {"s": {"height": 500, "width": 1440}})
    assert res["passed"] == res["total"], res["sections"][0]["failed"]


def test_style_differences_come_back_as_fixes_for_their_own_component():
    d = extract(_clone())
    off = [dict(c) for c in HERO]
    off[0] = {**off[0], "fs": 48, "sel": "h1.n4"}
    res = check(d, {"hero": off, "why": WHY}, {"hero": {"height": 900, "width": 1440}, "why": {"height": 520, "width": 1440}})
    fix = res["fixes"]["hero"]["h1.n4"]
    assert fix["font-size"] == "60px" and fix["_bg"] == "#050505"


def test_words_inside_an_accordion_row_are_never_a_dead_link():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    layout = [{"kind": "heading", "x": 184, "y": 40, "w": 454, "h": 104, "fs": 46, "fw": 600, "chars": 26},
              {"kind": "card", "x": 702, "y": 96, "w": 536, "h": 84},
              {"kind": "link", "x": 720, "y": 120, "w": 300, "h": 28, "fs": 18, "chars": 22},
              {"kind": "card", "x": 702, "y": 200, "w": 536, "h": 84},
              {"kind": "link", "x": 720, "y": 224, "w": 300, "h": 28, "fs": 18, "chars": 22}]
    sec = Section(id="faq", name="FAQ", structure="accordion", content="x", layout=layout,
                  layout_box={"top": 0, "left": 0, "width": 1440, "height": 400, "bg": "#ffffff"})
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content={}).content
    assert code.count("<details") == 2 and "<summary" in code
    assert 'data-swarm-role="link"' not in code  # the question line opens the row; nothing inside it is a link
