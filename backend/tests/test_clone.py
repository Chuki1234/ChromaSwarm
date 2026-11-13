"""Clone mode: reading a reference page, the B1-B7 flow, and owned-site content."""

import asyncio
from pathlib import Path

from chromaswarm.agents.planner import Interactive, Section, page_sections
from chromaswarm.clone.reader import CloneAnalysis, analyse, classify, sections_from_blocks
from chromaswarm.developer.content import build_copy
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step

DEMO = (Path(__file__).parents[1] / "chromaswarm/playwright_engine/fixtures/demo_landing.html").resolve().as_uri()
PROMPT = "Shop bán gốm thủ công Bát Tràng, khách 25-40 tuổi, muốn họ bấm Nhắn tin đặt hàng"


def feat(**kw):
    base = dict(tag="section", role=None, index=1, height=500, top=0, h1=False, headings=1, nav=False, links=0,
                buttons=0, inputs=0, password=False, accordion=0, tablist=False, images=0, big_image=False,
                bg_differs=False, bg_image=False, columns=1, scroller=False, text_len=400, prices=0,
                numeric_items=0, card_widths=[], padding_y=128)
    return {"features": {**base, **kw}}


def test_blocks_are_classified_onto_buildable_structures():
    assert classify(feat(tag="header", nav=True, height=64), 0, 5) == "sticky-bar"
    assert classify(feat(h1=True, images=1), 1, 5) == "split-7-5"
    assert classify(feat(h1=True, bg_image=True), 1, 5) == "full-bleed-image"
    assert classify(feat(columns=4, numeric_items=4), 2, 5) == "inline-metrics"
    assert classify(feat(columns=4, images=4, prices=4), 2, 5) == "grid-4"
    assert classify(feat(columns=2, images=4, card_widths=[600, 300], row_items_with_img=2), 2, 5) == "bento"
    assert classify(feat(columns=4, images=0, row_items_with_img=4, card_widths=[300] * 4), 2, 5) == "bento"  # feature cards
    assert classify(feat(columns=2, images=3, card_widths=[500, 700], row_items_with_img=1), 2, 5) == "alternating-z"
    assert classify(feat(accordion=5), 3, 5) == "accordion"
    assert classify(feat(bg_differs=True, buttons=1, text_len=80), 3, 5) == "full-bleed-band"
    assert classify(feat(tag="footer", links=8), 4, 5) == "footer-columns"
    assert classify(feat(columns=2, quotes=2), 2, 6) == "testimonials"
    assert classify(feat(headings=1, height=228, text_len=60, links=2), 4, 6) == "full-bleed-band"  # closing CTA
    assert classify(feat(headings=1, height=1200, text_len=900), 2, 9) == "feature-showcase"
    assert classify(feat(columns=4, text_len=800, card_widths=[272] * 4), 2, 9) == "text-cards"


def test_section_ids_are_unique_and_a_header_is_always_present():
    secs = sections_from_blocks([feat(h1=True, images=1), feat(), feat()])
    assert [s.id for s in secs] == ["site-header", "hero", "split-5-7", "split-5-7-2"]


def test_reading_someone_elses_page_returns_no_content():
    a = asyncio.run(analyse(DEMO, owned=False))
    assert a.content is None  # the reader never returned text, links or images
    assert [s.structure for s in a.sections][:2] == ["sticky-bar", "split-7-5"]
    assert a.pillars["theme"] == "editorial-luxury"  # serif headings on the reference
    assert a.pillars["color"].startswith("warm-paper #")  # warm neutrals + its accent colour
    assert a.pillars["margins"] == "airy"


def test_owned_page_content_is_read_per_section():
    a = asyncio.run(analyse(DEMO, owned=True))
    hero = a.content["sections"]["hero"]
    assert hero["heading"] == "Nội thất gỗ sồi, làm chậm để dùng lâu"
    assert "Đặt lịch xem showroom" in hero["buttons"]


def fake_reader(owned_content=None, fail=False):
    async def read(url, owned):
        if fail:
            raise RuntimeError("net::ERR_NAME_NOT_RESOLVED")
        secs = [Section(id="site-header", name="Header", structure="sticky-bar", content="x",
                        interactive=[Interactive(id="nav-logo", role="link", behavior="home")]),
                Section(id="hero", name="Hero", structure="split-7-5", content="x",
                        interactive=[Interactive(id="cta-primary", role="button", behavior="go")]),
                Section(id="grid-4", name="Lưới sản phẩm", structure="grid-4", content="x"),
                Section(id="site-footer", name="Footer", structure="footer-columns", content="x")]
        return CloneAnalysis(url=url, title="Gốm Mộc", owned=owned, sections=secs,
                             pillars={"theme": "warm-organic", "layout": "catalog", "color": "light #0f8f7f",
                                      "margins": "balanced"},
                             content=owned_content if owned else None)
    return read


async def drive(runner, sid, answers):
    await runner.start(sid)
    snap = None
    for a in answers:
        snap = await runner.answer(sid, a)
    return snap


def test_clone_flow_reaches_approval_with_the_reference_sections(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader()))
    snap = asyncio.run(drive(runner, "c1", ["clone", {"url": "gom-moc.vn", "prompt": PROMPT, "owned": False}]))
    p = snap["pipeline"]
    assert p.step is Step.B7_APPROVAL and snap["question"]["kind"] == "approval"  # B2-B6 ran on their own
    assert p.selected_page == "clone" and p.sitemap[0].title == "Bản dựng lại · Gốm Mộc"
    assert p.pillars.theme == "warm-organic" and p.pillars.layout == "catalog" and p.pillars.scope == PROMPT
    assert [s.id for s in page_sections(p)] == ["site-header", "hero", "grid-4", "site-footer"]
    assert "grid-4" in p.plan_md
    assert p.references[0].url == "https://gom-moc.vn"  # B5 learns its Style DNA from the same link


def test_clone_asks_again_for_a_bad_link_or_a_missing_description(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader()))
    snap = asyncio.run(drive(runner, "c2", ["clone", {"url": "khong phai link", "prompt": PROMPT}]))
    assert snap["question"]["kind"] == "clone_source" and "link hợp lệ" in snap["notice"]
    snap = asyncio.run(runner.answer("c2", {"url": "https://gom-moc.vn", "prompt": "gốm"}))
    assert snap["question"]["kind"] == "clone_source" and "mô tả thêm" in snap["notice"]


def test_unreachable_link_goes_back_to_the_link_question(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader(fail=True)))
    snap = asyncio.run(drive(runner, "c3", ["clone", {"url": "https://khong-ton-tai.vn", "prompt": PROMPT}]))
    assert snap["pipeline"].step is Step.B1_READ_PROMPT and snap["question"]["kind"] == "clone_source"
    assert "Không mở được trang" in snap["notice"]


def test_owned_clone_uses_the_sites_own_copy_and_photos(tmp_path):
    content = {"site_title": "Gốm Mộc · Trang chủ", "sections": {
        "site-header": {"structure": "sticky-bar", "logo": "Gốm Mộc",
                        "nav": [["Gốm Mộc", "/"], ["Sản phẩm", "/san-pham"], ["Liên hệ", "#lien-he"]],
                        "items": [{"title": "Sản phẩm"}, {"title": "Liên hệ"}]},
        "hero": {"structure": "split-7-5", "heading": "Gốm làm tay, nung củi",
                 "paragraphs": ["Mỗi chiếc bát qua 12 công đoạn tại Bát Tràng."],
                 "buttons": ["Nhắn tin đặt hàng"], "images": ["https://gom-moc.vn/hero.jpg"],
                 "items": [{"title": "Gốm làm tay, nung củi"}]},
        "grid-4": {"structure": "grid-4", "heading": "Bán chạy",
                   "items": [{"title": "Bát men lam", "note": "Đường kính 12cm", "price": "180.000₫"},
                             {"title": "Đĩa men rạn", "note": "Đường kính 20cm", "price": "250.000₫"}]}}}
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader(content)))
    p = asyncio.run(drive(runner, "c4", ["clone", {"url": "https://gom-moc.vn", "prompt": PROMPT, "owned": True}]))["pipeline"]
    copy = build_copy(p)
    assert copy.brand == "Gốm Mộc" and copy.headline == "Gốm làm tay, nung củi" and copy.cta == "Nhắn tin đặt hàng"
    assert [i.name for i in copy.items] == ["Bát men lam", "Đĩa men rạn"] and copy.items[0].price == "180.000₫"
    assert copy.images == ["https://gom-moc.vn/hero.jpg"] and ("Sản phẩm", "/san-pham") in copy.nav_links
    assert ("Gốm Mộc", "/") not in copy.nav_links  # the logo is not a nav item
    # header links and the hero heading never leak into the product cards
    assert all(i.name not in ("Sản phẩm", "Liên hệ", "Gốm làm tay, nung củi") for i in copy.items)


def test_not_owned_clone_keeps_the_users_own_copy(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader({"site_title": "X", "sections": {}})))
    p = asyncio.run(drive(runner, "c5", ["clone", {"url": "https://gom-moc.vn", "prompt": PROMPT, "owned": False}]))["pipeline"]
    assert p.clone.content is None and build_copy(p).images == []


def test_unclear_domain_is_asked_not_guessed_in_clone_mode(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader()))
    snap = asyncio.run(drive(runner, "c6", ["clone", {"url": "https://gom-moc.vn",
                                                       "prompt": "Trang của tiệm gốm nhà mình ở Bát Tràng"}]))
    assert snap["question"]["key"] == "domain"
    snap = asyncio.run(runner.answer("c6", "ecommerce"))
    assert snap["pipeline"].step is Step.B7_APPROVAL


def test_style_dna_reads_oklch_colours():
    """Chromium reports oklch() colours as lab(); the DNA scraper must still see the accent."""
    from chromaswarm.playwright_engine.style_dna_scraper import scrape_html

    html = """<body style="margin:0;background:oklch(97% 0.012 75);color:oklch(20% 0.015 75)">
      <section style="padding:128px 64px"><h1>Gốm</h1><p>Mô tả sản phẩm đủ dài để được tính là chữ.</p>
      <button style="background:oklch(48% 0.134 47);color:white;padding:16px 32px;border:0">Đặt hàng</button></section></body>"""
    dna = asyncio.run(scrape_html(html))
    assert dna.accents, "accent colour lost (lab() not parsed)"
    assert not dna.is_dark and dna.neutral_temperature == "warm"


def test_product_md_states_the_clone_level_and_plan_flags_approximations(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader()))
    p = asyncio.run(drive(runner, "c7", ["clone", {"url": "https://gom-moc.vn", "prompt": PROMPT, "owned": False}]))["pipeline"]
    assert "Clone cấu trúc" in p.product_md and "§2.5" in p.product_md
    secs = sections_from_blocks([feat(h1=True, images=1), feat(text_len=900)])
    assert "khối nội dung gần nhất" in secs[-1].content  # an unmatched block is flagged in PLAN.md


def test_design_md_shows_the_clone_policy_not_the_anti_cloning_boundary(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, clone_reader=fake_reader(),
                                 scrape=_fake_dna))
    p = asyncio.run(drive(runner, "c8", ["clone", {"url": "https://gom-moc.vn", "prompt": PROMPT}]))["pipeline"]
    assert "Clone mode (FRONTEND_STANDARDS §2.5)" in p.design_md
    assert "Ranh giới chống sao chép" not in p.design_md


async def _fake_dna(url):
    from chromaswarm.engines.style_dna import RawStyleSample, analyze
    return analyze(RawStyleSample(source_url=url, viewport_w=1440, viewport_h=900, page_height=3000,
                                  backgrounds=[{"color": "rgb(250, 247, 240)", "area": 1e6}],
                                  texts=[{"color": "rgb(20, 20, 20)", "chars": 400, "font_family": "Inter",
                                          "font_size": 16, "font_weight": 400}],
                                  spacing=[16, 24, 32], block_padding=[128], radii=[8], border_count=2,
                                  shadow_count=0, backdrop_blur_count=0, motion=[]))


def test_sections_of_the_same_kind_never_repeat_sample_copy():
    from chromaswarm.developer.content import copy_for
    from chromaswarm.state_machine.pipeline_state import Domain, PipelineState

    copy = build_copy(PipelineState(session_id="x", raw_prompt="phần mềm quản lý", domain=Domain.SAAS))
    seq = ["alternating-z", "split-5-7", "feature-showcase", "split-5-7", "text-cards"]
    used = []
    for i, st in enumerate(seq):
        n = {"alternating-z": 3, "text-cards": 3}.get(st, 1)
        used += [t for t, _ in copy_for(st, seq[:i], copy).story[:n]]
    assert len(used) == 9 and len(set(used[:6])) == 6  # the first 6 rows are all different
    assert "vật liệu" not in " ".join(used)  # SaaS copy, not the furniture story


def test_testimonials_with_css_quote_marks_are_recognised():
    """Quote marks drawn with ::before and 'Role, Company' lines (as on linear.app)."""
    import urllib.parse

    card = ('<a href="#" class="t"><p class="q">This tool changed how our whole team plans and ships every week.</p>'
            '<span>Jane Tran</span><span>Head of Engineering, Acme</span></a>')
    html = ("<style>body{margin:0;font:16px sans-serif} .t{display:block;width:500px;padding:24px}"
            ".q::before{content:'“'} .row{display:flex;gap:24px;padding:48px}</style>"
            "<header><nav><a href='/'>Brand</a></nav></header>"
            "<section><h1>Hero heading</h1><p>Some text here for the hero section.</p></section>"
            f"<section class='row'>{card}{card}</section>"
            "<footer><a>a</a><a>b</a><a>c</a><a>d</a></footer>")
    a = asyncio.run(analyse("data:text/html," + urllib.parse.quote(html), owned=False))
    assert "testimonials" in [s.structure for s in a.sections]
