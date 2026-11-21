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
    raw = {"theme": "made-up", "layout": "catalog", "evidence": {"layout": "Thanh cam kết"},
           "accent": "#123456", "heading_font": "Comic Sans",
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
    assert c.brand == "LUMIÈRE BOTANIQUE" and [label for label, _ in c.nav_links] == ["Sản phẩm", "Dưỡng da"]  # no quiz on this page: "Kiểm tra da" would lead nowhere
    assert c.categories == ["Serum", "Kem dưỡng"] and {i.category for i in c.items} == {"Serum", "Kem dưỡng"}
    assert c.usp == ["100% Thuần chay"] and c.cta == "Mua ngay"



# ---------------------------------------------------------------- accuracy: evidence, literal facts, skips

def test_pillars_need_a_real_quote_from_the_prompt():
    prompt = "web bán nến thơm handmade, phong cách sang trọng tối giản"
    raw = {"theme": "editorial-luxury", "layout": "narrative", "mode": "dark",
           "evidence": {"theme": "phong cách sang trọng", "layout": "kể chuyện từng bước", "mode": "tối giản"}}
    b = validate(raw, prompt)
    assert b.theme == "editorial-luxury"  # quoted from the prompt
    assert b.layout is None  # quote not in the prompt: guessed, dropped
    assert b.mode is None  # "tối giản" is minimal, not a dark tone


def test_cta_must_be_the_users_own_words():
    b = validate({"primary_cta": "Mua ngay", "evidence": {"primary_cta": "Mua ngay"}}, "web bán nến, muốn họ bấm Đặt mua")
    assert b.primary_cta is None


def test_literal_facts():
    from chromaswarm.agents.brief import _literal_facts
    f = _literal_facts("Làm landing page bán nến thơm, màu chủ đạo xanh rêu, dùng ảnh Unsplash, muốn họ bấm Đặt mua")
    assert f == {"page": "landing", "assets_said": True, "named_accent": "#5b6b2f", "cta": "Đặt mua"}
    assert _literal_facts("web bán cà phê nâu rang xay")["named_accent"] is None  # a drink, not a brand colour


def drive_to(runner, sid, answers):
    async def go():
        await runner.start(sid)
        snap = None
        for a in answers:
            snap = await runner.answer(sid, a)
        return snap
    return asyncio.run(go())


def test_complete_prompt_is_never_asked_again(tmp_path):
    prompt = ("Làm landing page bán nến thơm handmade, phong cách sang trọng, bố cục kể chuyện, nền kem ấm màu chủ đạo "
              "xanh rêu, thoáng đãng, khách là dân văn phòng 25-35 tuổi, muốn họ bấm Đặt mua, dùng ảnh Unsplash")
    reader = lambda text: Brief(theme="editorial-luxury", layout="narrative", mode="warm-paper", margins="airy",  # noqa: E731
                                accent="#5b6b2f", audience="dân văn phòng 25-35 tuổi", primary_cta="Đặt mua",
                                page="landing", assets_said=True)
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, brief_reader=reader))
    snap = drive_to(runner, "full", ["creative", prompt])
    p = snap["pipeline"]
    assert p.step is Step.B7_APPROVAL and snap["question"]["kind"] == "approval"  # B2, B3, B4: no question
    assert p.pillars.clarity_score == 1.0 and p.pillars.color == "warm-paper #5b6b2f"
    assert p.selected_page == "landing" and p.assets_confirmed


def test_partial_prompt_asks_only_what_is_missing(tmp_path):
    reader = lambda text: Brief(theme="editorial-luxury", mode="warm-paper",  # noqa: E731
                                audience="dân văn phòng 25-35 tuổi")
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, brief_reader=reader))
    snap = drive_to(runner, "part", ["creative", "web bán nến thơm cho dân văn phòng 25-35 tuổi, phong cách sang trọng, nền kem",
                                     "landing"])
    assert snap["question"]["key"] == "layout"  # theme and colour came from the prompt; no surface question
    note = snap["question"].get("note") or ""
    assert "Chỉ còn thiếu" in note and "nút QUAN TRỌNG NHẤT" in note and "khách hàng & nút" not in note
    snap = drive_to_more(runner, "part", ["narrative", "balanced"])
    assert snap["question"]["key"] == "scope"
    assert "dân văn phòng" in snap["question"]["text"] and "nút" in snap["question"]["text"]  # asks only the CTA
    snap = drive_to_more(runner, "part", ["Đặt mua"])  # only the missing half
    p = snap["pipeline"]
    assert p.pillars.scope == "dân văn phòng 25-35 tuổi; Đặt mua" and p.step is Step.B4_ASSETS


def drive_to_more(runner, sid, answers):
    async def go():
        snap = None
        for a in answers:
            snap = await runner.answer(sid, a)
        return snap
    return asyncio.run(go())



def test_a_lone_section_is_not_a_page_plan(tmp_path):
    from chromaswarm.agents.planner import page_sections
    from chromaswarm.state_machine.pipeline_state import PipelineState, Pillars
    st = PipelineState(session_id="s", selected_page="landing",
                       pillars=Pillars(theme="editorial-luxury", layout="narrative", color="warm-paper", margins="airy", scope="x"),
                       brief=Brief(sections=[BriefSection(kind="hero"), BriefSection(kind="story")]).model_dump())
    assert len(page_sections(st)) >= 7  # the full landing blueprint, not header + hero + story + footer
    assert "section" not in " ".join(Brief.model_validate(st.brief).summary())


def test_negated_and_unaccented_quotes():
    from chromaswarm.agents.brief import negated
    assert negated("nền tối", "shop mỹ phẩm, không muốn nền tối, thích tông sáng")
    assert not negated("tông sáng", "shop mỹ phẩm, không muốn nền tối, thích tông sáng")
    b = validate({"mode": "dark", "evidence": {"mode": "nền tối"}}, "shop mỹ phẩm, không muốn nền tối")
    assert b.mode is None  # what the user rejected is never taken
    b = validate({"mode": "dark", "evidence": {"mode": "nen toi"}}, "lam web ban giay, nen toi")
    assert b.mode == "dark"  # typed without diacritics


def test_a_background_colour_is_not_a_style():
    prompt = "web bán trà, màu thương hiệu #2E7D32, nền giấy kem"
    assert validate({"theme": "warm-organic", "evidence": {"theme": "nền giấy kem"}}, prompt).theme is None
    assert validate({"theme": "warm-organic", "evidence": {"theme": "phong cách ấm áp"}},
                    "web bán trà, phong cách ấm áp").theme == "warm-organic"
