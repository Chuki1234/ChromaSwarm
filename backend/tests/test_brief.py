"""Brief reader: a detailed first message pre-fills the pillars and orders the page."""

import asyncio

from chromaswarm.agents.brief import Brief, BriefSection, mode_from_background, rule_brief, validate
from chromaswarm.agents.planner import sections_from_brief
from chromaswarm.developer.nextjs import BY_STRUCTURE
from chromaswarm.engines.presets import Layout, Theme
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step

PROMPT = ("Tôi muốn xây dựng một trang web thương mại điện tử bán mỹ phẩm thuần chay cao cấp mang tên thương hiệu là "
          "\"LUMIÈRE BOTANIQUE\". Đối tượng: nữ 22-38 tuổi. Thanh cam kết: 100% Thuần chay, Kiểm nghiệm da liễu. "
          "Bảng màu: Nền chính (#FAF8F5), Màu nhấn (Primary CTA): Hồng đất (#C87D65). "
          "Tiêu đề Playfair Display hoặc Cormorant Garamond; nội dung Plus Jakarta Sans hoặc Inter.")


def test_rule_brief_reads_literal_facts():
    b = rule_brief(PROMPT)
    assert b.brand == "LUMIÈRE BOTANIQUE" and b.accent == "#c87d65" and b.background == "#faf8f5"
    assert b.heading_font == "Playfair Display" and b.body_font == "Inter"  # Plus Jakarta Sans has no Vietnamese


def test_validate_keeps_closed_sets_and_literal_hex():
    raw = {"theme": "made-up", "layout": "catalog", "accent": "#123456", "heading_font": "Comic Sans",
           "sections": [{"kind": "quiz", "note": "chọn loại da"}, {"kind": "hologram"}, {"kind": "quiz"}],
           "usp": ["100% Thuần chay"] * 6}
    b = validate(raw, PROMPT)
    assert b.theme is None and b.layout == "catalog"
    assert b.accent is None  # not written in the prompt: never invented
    assert b.heading_font is None
    assert [s.kind for s in b.sections] == ["quiz"] and len(b.usp) == 4


def test_warm_background_reads_as_warm_paper():
    assert mode_from_background("#faf8f5") == "warm-paper"
    assert mode_from_background("#111318") == "dark"
    assert mode_from_background("#ffffff") == "light"


def test_sections_follow_the_brief_order_and_are_buildable():
    brief = Brief(announcement="Ưu đãi", sections=[
        BriefSection(kind="hero", note="Bố cục chia đôi 55/45"), BriefSection(kind="usp"),
        BriefSection(kind="products"), BriefSection(kind="quiz"), BriefSection(kind="story"),
        BriefSection(kind="testimonials")]).model_dump()
    secs = sections_from_brief(brief, Layout.VISUAL_FIRST, Theme.WARM_ORGANIC, None)
    assert [s.id for s in secs] == ["announcement", "site-header", "hero", "usp-strip", "bestsellers", "quiz",
                                    "feature-story", "testimonials", "closing-cta", "site-footer"]
    assert secs[2].structure == "split-7-5"  # the user asked for a split hero
    assert "55/45" in secs[2].content
    assert all(s.structure in BY_STRUCTURE for s in secs)
    assert all(a.structure != b.structure for a, b in zip(secs, secs[1:]))


def test_brief_prefills_pillars_and_skips_answered_questions(tmp_path):
    reader = lambda prompt: Brief(brand="LUMIÈRE BOTANIQUE", theme="editorial-luxury", layout="visual-first",  # noqa: E731
                                  margins="airy", background="#faf8f5", accent="#c87d65",
                                  audience="Nữ 22-38 tuổi", primary_cta="Mua ngay")
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, brief_reader=reader))

    async def go():
        await runner.start("b")
        for a in ["creative", PROMPT, "landing"]:
            snap = await runner.answer("b", a)
        return snap

    snap = asyncio.run(go())
    p = snap["pipeline"]
    assert p.pillars.theme == "editorial-luxury" and p.pillars.color == "warm-paper #c87d65"
    assert p.pillars.scope.endswith("Mua ngay")
    assert p.brief["brand"] == "LUMIÈRE BOTANIQUE"
    # all five pillars came from the brief: B3 is done without a single question (material stays flat)
    assert p.step is Step.B4_ASSETS and snap["question"]["key"] == "assets"
    assert p.pillars.clarity_score == 1.0


def test_brief_menu_and_categories_reach_the_page_copy():
    from chromaswarm.developer.content import build_copy
    from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars

    st = PipelineState(session_id="m", raw_prompt=PROMPT, domain=Domain.ECOMMERCE, selected_page="landing",
                       pillars=Pillars(theme="warm-organic", layout="catalog", color="warm-paper", margins="airy",
                                       scope="Nữ 22-38. Hành động quan trọng nhất: Mua ngay"),
                       brief=Brief(brand="LUMIÈRE BOTANIQUE", nav=["Sản phẩm", "Dưỡng da", "Kiểm tra da"],
                                   categories=["Tất cả", "Serum", "Kem dưỡng"], usp=["100% Thuần chay"]).model_dump())
    c = build_copy(st)
    assert c.brand == "LUMIÈRE BOTANIQUE" and [label for label, _ in c.nav_links] == ["Sản phẩm", "Dưỡng da", "Kiểm tra da"]
    assert c.categories == ["Serum", "Kem dưỡng"] and {i.category for i in c.items} == {"Serum", "Kem dưỡng"}
    assert c.usp == ["100% Thuần chay"] and c.cta == "Mua ngay"
