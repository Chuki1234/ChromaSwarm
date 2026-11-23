"""Clone templates: sections understood and built as real components, words matched by place (owned site)."""

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.nextjs import render_section
from chromaswarm.state_machine.pipeline_state import PipelineState

TYPE = {"h1": {"size": 60, "weight": 700, "leading": 1.0, "tracking": 0, "case": "", "uses": 1},
        "brand": {"size": 20, "weight": 600, "leading": 1.4, "tracking": 0, "case": "", "uses": 1},
        "caption": {"size": 12, "weight": 500, "leading": 1.3, "tracking": 0, "case": "", "uses": 1},
        "button": {"size": 16, "weight": 600, "leading": 1.5, "tracking": 0, "case": "", "uses": 1},
        "h2": {"size": 46, "weight": 600, "leading": 1.1, "tracking": 0, "case": "", "uses": 1},
        "body": {"size": 16, "weight": 400, "leading": 1.5, "tracking": 0, "case": "", "uses": 1}}
COLORS = {"bg/band": {"value": "#07140b", "uses": 1, "role": "section"}, "bg/page": {"value": "#ffffff", "uses": 1, "role": "section"},
          "text/primary": {"value": "#111827", "uses": 1, "role": "text"}, "accent/primary": {"value": "#00b83d", "uses": 1, "role": "fill"},
          "text/white": {"value": "#ffffff", "uses": 1, "role": "text"}}
VARIANTS = {"button/primary": {"kind": "button", "w": 177, "h": 48, "radius": 16, "fill": "accent/primary", "ink": "text/white",
                               "type": "button", "padding": [8, 28], "shadow": False, "border": 0, "hover": [], "uses": 1}}


def _sec(sid, structure, box, rows, owned=None, effects=()):
    spec = {"id": sid, "name": sid, "structure": structure, "box": {"left": 0, **box}, "padding": {"top": 8, "bottom": 8},
            "margins": {"left": 104, "right": 104}, "gaps": [], "layout": "", "components": rows, "effects": list(effects), "backgrounds": []}
    return Section(id=sid, name=sid, structure=structure, content="x",
                   design={"section": spec, "type": TYPE, "colors": COLORS, "components": VARIANTS}, owned=owned or {})


def _render(sec):
    words: dict = {}
    code = render_section(sec, build_copy(PipelineState(session_id="s", raw_prompt="x")), "clone", content=words).content
    return code, words.get(sec.id, {})


def test_announcement_bar_closes_and_stays_closed():
    sec = _sec("announcement", "announcement-bar", {"top": 0, "height": 32, "width": 1440, "bg": "accent/primary"},
               [{"i": 0, "kind": "text", "x": 617, "y": 8, "w": 205, "h": 17, "type": "caption", "ink": "text/white", "chars": 41}],
               owned={"texts": [{"t": "Find jobs smarter with AI – Discover now!", "x": 617, "y": 8, "w": 205, "h": 17}]})
    code, words = _render(sec)
    assert "Find jobs smarter with AI – Discover now!" in words.values()
    assert "{open && (" in code and "localStorage.setItem" in code and 'data-swarm-id="announcement-close"' in code


def test_navbar_takes_logo_brand_subtitle_language_switch_and_action():
    rows = [{"i": 0, "kind": "image", "x": 104, "y": 16, "w": 32, "h": 32},
            {"i": 1, "kind": "text", "x": 148, "y": 12, "w": 138, "h": 28, "type": "brand", "ink": "text/white", "chars": 6},
            {"i": 2, "kind": "text", "x": 148, "y": 36, "w": 138, "h": 16, "type": "caption", "ink": "text/white", "chars": 23},
            {"i": 3, "kind": "button", "x": 1053, "y": 12, "w": 98, "h": 40, "type": "button", "click": "dialog", "chars": 2},
            {"i": 4, "kind": "button", "x": 1159, "y": 8, "w": 177, "h": 48, "type": "button", "variant": "button/primary", "chars": 11}]
    texts = [{"t": "FormCV", "x": 148, "y": 44, "w": 138, "h": 28}, {"t": "Professional CV Builder", "x": 148, "y": 68, "w": 138, "h": 16},
             {"t": "EN", "x": 1053, "y": 44, "w": 98, "h": 40}, {"t": "Get Started", "x": 1159, "y": 40, "w": 177, "h": 48}]
    sec = _sec("site-header", "sticky-bar", {"top": 32, "height": 64, "width": 1440, "bg": "bg/band"}, rows,
               owned={"texts": texts, "pics": [{"src": "https://example.com/logo.png", "x": 104, "y": 48, "w": 32, "h": 32}]})
    code, words = _render(sec)
    values = list(words.values())
    assert "FormCV" in values and "Professional CV Builder" in values and "Get Started" in values  # brand ≠ subtitle
    assert 'aria-haspopup="listbox"' in code and 'data-swarm-id="nav-language"' in code and "https://example.com/logo.png" in values
    assert "position: sticky" in code


def test_faq_rows_split_question_and_answer_and_open():
    rows = [{"i": 0, "kind": "heading", "x": 184, "y": 40, "w": 454, "h": 104, "type": "h2", "ink": "text/primary", "chars": 26},
            {"i": 1, "kind": "button", "x": 702, "y": 96, "w": 536, "h": 84, "click": "toggle"},
            {"i": 2, "kind": "button", "x": 702, "y": 200, "w": 536, "h": 84, "click": "toggle"}]
    texts = [{"t": "Frequently Asked Questions", "x": 184, "y": 5740, "w": 454, "h": 104},
             {"t": "What is FormCV? FormCV is a free online CV builder.", "x": 702, "y": 5796, "w": 536, "h": 84},
             {"t": "Is FormCV really free? Yes, the basic plan is free.", "x": 702, "y": 5900, "w": 536, "h": 84}]
    sec = _sec("faq", "accordion", {"top": 5700, "height": 400, "width": 1440, "bg": "bg/page"}, rows, owned={"texts": texts})
    code, words = _render(sec)
    values = list(words.values())
    assert "What is FormCV?" in values and "FormCV is a free online CV builder." in values
    assert code.count("<details") == 2 and "grid-template-columns: minmax(0, 454px)" in code


def test_a_frame_around_the_main_content_is_a_wrapper_not_a_card():
    rows = [{"i": 0, "kind": "card", "x": 100, "y": 60, "w": 560, "h": 700},
            {"i": 1, "kind": "heading", "x": 112, "y": 140, "w": 520, "h": 100, "type": "h2", "ink": "text/primary", "chars": 30},
            {"i": 2, "kind": "button", "x": 112, "y": 300, "w": 504, "h": 60, "click": "toggle"},
            {"i": 3, "kind": "button", "x": 112, "y": 370, "w": 504, "h": 60, "click": "toggle"}]
    sec = _sec("feature-accordion", "accordion", {"top": 1800, "height": 846, "width": 1440, "bg": "bg/page"}, rows)
    code, _ = _render(sec)
    assert "<h2" in code and "font-size: 46px" in code  # the big heading is the section's, not a card's
