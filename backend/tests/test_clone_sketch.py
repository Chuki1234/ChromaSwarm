"""Sketch step: drawing what was read, coverage against a screenshot, gaps measured again, rebuild vs reference."""

import asyncio

from chromaswarm.clone.sketch import add_found, compare_sketches, coverage, draw, occupancy, pieces_abs, regions

BOXES = {"hero": {"top": 0, "left": 0, "width": 1440, "height": 900, "bg": "#050505"}}
COMPS = {"hero": [{"kind": "heading", "x": 96, "y": 340, "w": 600, "h": 120, "fs": 60, "lh": 1.0},
                  {"kind": "button", "x": 96, "y": 600, "w": 190, "h": 48, "radius": 24},
                  {"kind": "image", "x": 0, "y": 0, "w": 1440, "h": 900}]}  # the hero's background picture


def test_sketch_draws_every_piece_and_marks_gaps():
    svg = draw(BOXES, COMPS, 900, gaps=[{"x": 860, "y": 100, "w": 560, "h": 700}])
    assert svg.startswith("<svg") and 'fill="#050505"' in svg
    assert svg.count('rx="18"') == 2  # two heading bars (120px at line height 60, bar = 0.6 x 60)
    assert "đọc thiếu" in svg


def test_a_background_picture_does_not_count_as_having_read_what_is_on_it():
    cells = occupancy(pieces_abs(BOXES, COMPS), 900, boxes=BOXES)
    right_column = {(c, r) for c in range(40, 58) for r in range(5, 30)}  # where the CV cards are
    content = right_column | {(5, 15)}
    pct, missing = coverage(content, cells)
    assert pct < 10 and missing == right_column
    gap = regions(missing)[0]
    assert gap["x"] == 40 * 24 and gap["w"] == 18 * 24


def test_pieces_found_in_a_gap_join_their_section_once():
    comps = {k: [dict(c) for c in v] for k, v in COMPS.items()}
    found = [{"kind": "image", "ax": 868, "ay": 200, "w": 275, "h": 350},
             {"kind": "text", "ax": 900, "ay": 260, "w": 120, "h": 12},  # a word inside that picture
             {"kind": "button", "ax": 96, "ay": 600, "w": 190, "h": 48}]  # already read
    assert add_found(BOXES, comps, found) == 1
    added = comps["hero"][-1]
    assert added["kind"] == "image" and added["x"] == 868 and added["y"] == 200 and added["found"]


def test_rebuild_sketch_is_scored_per_section():
    ref = {"hero": [{"kind": "heading", "x": 96, "y": 340, "w": 600, "h": 120, "fs": 60},
                    {"kind": "image", "x": 868, "y": 100, "w": 560, "h": 700}]}
    good = compare_sketches(BOXES, ref, BOXES, ref)
    empty_right = compare_sketches(BOXES, ref, BOXES, {"hero": ref["hero"][:1]})
    assert good["score"] == 100.0 and empty_right["sections"]["hero"] < 40


def test_graph_runs_the_sketch_pass_before_the_plan_and_uses_its_pieces(tmp_path):
    from chromaswarm.clone.motion_check import MotionReport
    from chromaswarm.state_machine.graph import Deps, PipelineRunner
    from tests.test_clone import PROMPT, drive, fake_reader

    async def motion(url, boxes):
        return MotionReport(has_motion=False)

    async def sketch(url, boxes, comps, out):
        comps = {**comps, "hero": [*comps.get("hero", []), {"kind": "image", "x": 868, "y": 100, "w": 275, "h": 350, "found": True}]}
        return {"coverage_before": 72.0, "coverage": 96.0, "gaps": 1, "remeasured": 1, "gaps_left": [], "pairs": ["ref-01.jpg"],
                "height": 900, "components": comps}

    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader(), motion_check=motion, sketch_check=sketch))
    snap = asyncio.run(drive(runner, "sk1", ["clone", {"url": "gom-moc.vn", "prompt": PROMPT, "owned": False}]))
    p = snap["pipeline"]
    assert p.step.value == "B7" and p.clone.sketched and p.clone.sketch["coverage"] == 96.0
    assert any(c.get("found") for c in p.clone.components["hero"])


def test_vision_answers_are_validated_and_laid_out_on_their_grid():
    from chromaswarm.clone.sketch import parse_vision, pieces_from_vision, placeholder
    assert parse_vision({"kind": "spaceship"}) is None and parse_vision("no") is None
    seen = parse_vision({"kind": "card", "count": 6, "layout": "grid", "rows": 3, "cols": 2, "note": "CV previews"})
    assert seen == {"kind": "card", "count": 6, "layout": "grid", "rows": 3, "cols": 2, "note": "CV previews"}
    gap = {"x": 860, "y": 100, "w": 576, "h": 700}
    cards = pieces_from_vision(gap, seen)
    assert len(cards) == 6 and cards[0]["ax"] == 860 and cards[1]["ax"] == 860 + 280 + 16  # (576 - 16) / 2 = 280
    assert all(c["kind"] == "card" and c["vision"] == "CV previews" for c in cards)
    row = parse_vision({"kind": "logo", "count": 5, "layout": "row"})
    assert row["rows"] == 1 and row["cols"] == 5 and pieces_from_vision(gap, row)[0]["kind"] == "image"
    assert placeholder(gap)[0]["w"] == 576 and placeholder(gap)[0]["media"] == "unknown"


def test_screenshots_are_compared_section_by_section():
    from chromaswarm.clone.sketch import compare_pixels
    ref_boxes = {"hero": {"top": 0, "height": 960}, "why": {"top": 960, "height": 480}}
    built_boxes = {"hero": {"top": 0, "height": 960}, "why": {"top": 1200, "height": 480}}  # pushed down 240px
    ref = {(c, r) for c in range(36, 58) for r in range(4, 30)} | {(c, 45) for c in range(4, 20)}  # hero cards + why text
    built = {(c, 55) for c in range(4, 20)}  # the cards are missing; why's text is there, 10 rows lower
    px = compare_pixels(ref, built, ref_boxes, built_boxes)
    assert px["sections"]["why"] == 100.0  # aligned at its own top: not penalised for moving down
    assert px["sections"]["hero"] == 0.0 and px["missing"][0]["sid"] == "hero" and px["missing"][0]["x"] == 36 * 24


def _tree(pieces):
    from chromaswarm.clone.components import comps
    from chromaswarm.clone.layout import build_tree
    return build_tree(comps(pieces), 1440)


def test_pictures_on_a_full_section_background_are_kept():
    tree = _tree([{"kind": "image", "x": 0, "y": 0, "w": 1440, "h": 900},
                  {"kind": "heading", "x": 96, "y": 344, "w": 672, "h": 120, "fs": 60},
                  {"kind": "image", "x": 868, "y": 30, "w": 275, "h": 348},
                  {"kind": "image", "x": 1161, "y": 265, "w": 275, "h": 348}])
    backs = [c for c in tree.children if c.kind.startswith("back-")]
    assert tree.kind == "layer" and len(backs) == 3  # the background and both cards on it
    assert tree.children[0].kind != "back-image"  # the heading flows in front


def test_overlapping_mockups_stack_instead_of_doubling_the_height():
    tree = _tree([{"kind": "heading", "x": 112, "y": 178, "w": 576, "h": 50, "fs": 40},
                  {"kind": "card", "x": 1001, "y": 96, "w": 235, "h": 295}, {"kind": "image", "x": 1002, "y": 97, "w": 233, "h": 293},
                  {"kind": "card", "x": 1070, "y": 128, "w": 210, "h": 264}, {"kind": "image", "x": 1071, "y": 129, "w": 208, "h": 262},
                  {"kind": "heading", "x": 136, "y": 608, "w": 325, "h": 28, "fs": 20}])
    stack = tree.children[0].children[1]
    assert stack.kind == "layer" and stack.h < 320  # one picture tall, not two
    assert tree.children[-1].y0 == 608  # the row below keeps its place


def test_a_header_floating_over_the_hero_is_kept_floating():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import PipelineState
    sec = Section(id="site-header", name="Header", structure="sticky-bar", content="x",
                  layout=[{"kind": "text", "x": 148, "y": 12, "w": 138, "h": 28, "fs": 20, "chars": 6},
                          {"kind": "button", "x": 1159, "y": 8, "w": 177, "h": 48, "fs": 16, "bg": "#16a34a", "color": "#ffffff", "chars": 11}],
                  layout_box={"top": 32, "left": 0, "width": 1440, "height": 64, "bg": "#07140b", "overlay": True})
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content={}).content
    assert "position: fixed !important; top: 32px" in code
