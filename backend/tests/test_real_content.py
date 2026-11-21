"""B4 real content: asked per domain, parsed from the user's lines, replaces the samples, grounds the copywriter."""

import asyncio

import pytest

from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import facts_for
from chromaswarm.developer.real_content import fields, parse
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars

FORM = {
    "offer": "đồ nội thất gỗ sồi làm thủ công tại Đà Lạt, cho căn hộ nhỏ",
    "different": "Gỗ sồi nguyên khối | không dùng ván ép, kể cả mặt sau ngăn kéo\nBảo hành 5 năm | sửa tận nhà",
    "items": "Bàn gỗ sồi Mộc 120 | 6.900.000₫ | gỗ sồi Nga\nGhế đẩu Mộc 890.000₫\n- Kệ sách treo tường",
    "numbers": "1.200 | đơn đã giao năm 2025\n4,8/5 | 320 đánh giá trên Shopee\nkhông có số | bỏ qua dòng này",
    "reviews": "Bàn chắc, giao đúng hẹn | Chị Hạnh, Thủ Đức",
    "faqs": "Có giao tỉnh không? | Có, phí theo kích thước\nCâu không có trả lời",
    "contact": "12 Lê Lợi, Đà Lạt · 9h–20h",
}
PHOTO = "uploads/product-image-0123456789ab.jpg"


def state(**kw) -> PipelineState:
    return PipelineState(session_id="r", raw_prompt="web bán nội thất gỗ thương hiệu Mộc", domain=Domain.ECOMMERCE,
                         selected_page="landing", pillars=Pillars(scope="Người 28-40 tuổi, muốn họ bấm Mua ngay"), **kw)


@pytest.mark.parametrize("domain", list(Domain))
def test_every_domain_has_its_own_form(domain):
    fs = fields(domain)
    assert [f.key for f in fs] == ["offer", "different", "items", "numbers", "reviews", "faqs", "contact"]
    assert all(f.label and f.placeholder for f in fs)


def test_lines_are_parsed_and_unreadable_lines_left_out():
    rc = parse(FORM)
    assert [(i.name, i.price) for i in rc.items] == [("Bàn gỗ sồi Mộc 120", "6.900.000₫"), ("Ghế đẩu Mộc", "890.000₫"),
                                                     ("Kệ sách treo tường", "")]
    assert rc.numbers == [("1.200", "đơn đã giao năm 2025"), ("4,8/5", "320 đánh giá trên Shopee")]
    assert rc.faqs == [("Có giao tỉnh không?", "Có, phí theo kích thước")]
    assert rc.missing() == []
    assert parse(None).given() == [] and parse({"items": 42}).items == []


def test_real_content_replaces_the_samples_and_empty_fields_keep_them():
    sample = build_copy(state())
    copy = build_copy(state(real_content=parse(FORM).model_dump()))
    assert copy.subhead.startswith("Đồ nội thất gỗ sồi")
    assert copy.items[0].name == "Bàn gỗ sồi Mộc 120" and copy.items[0].price == "6.900.000₫"
    assert [c.name for c in copy.cards][:3] == [i.name for i in copy.items][:3]  # a shop's bento shows its products
    assert copy.facts == [("1.200", "đơn đã giao năm 2025"), ("4,8/5", "320 đánh giá trên Shopee")]
    assert copy.quotes == [("Bàn chắc, giao đúng hẹn", "Chị Hạnh, Thủ Đức")]
    assert copy.faqs[0][0] == "Có giao tỉnh không?" and len(copy.faqs) >= 4
    assert copy.story[0] == ("Gỗ sồi nguyên khối", "không dùng ván ép, kể cả mặt sau ngăn kéo")
    assert "12 Lê Lợi" in copy.footer_line
    only_items = build_copy(state(real_content=parse({"items": FORM["items"]}).model_dump()))
    assert only_items.facts == sample.facts and only_items.headline == sample.headline


def test_copywriter_keeps_the_users_list_and_may_use_their_numbers():
    st = state(real_content=parse(FORM).model_dump())
    base = build_copy(st)
    facts = facts_for(st, base)
    assert facts["noi_dung_that"]["numbers"][0] == ["1.200", "đơn đã giao năm 2025"] or \
        facts["noi_dung_that"]["numbers"][0] == ("1.200", "đơn đã giao năm 2025")
    written = {"items": [["Bàn Mộc (đã viết lại)", "ghi chú"]] * len(base.items), "headline": "Gỗ thật cho nhà nhỏ"}
    copy = build_copy(st.model_copy(update={"page_copy": written}))
    assert copy.headline == "Gỗ thật cho nhà nhỏ"
    assert copy.items[0].name == "Bàn gỗ sồi Mộc 120"  # the user's own names win over the rewrite


def test_b4_card_asks_the_form_and_stores_the_answer(tmp_path):
    from tests.test_graph import HAPPY, drive
    runner = PipelineRunner(Deps(artifacts_root=tmp_path))

    async def go():
        snaps = await drive(runner, "rc", HAPPY[:-1])
        q = snaps[-1]["question"]
        assert q["kind"] == "assets" and [o["value"] for o in q["options"]][0] == "offer"
        return await runner.answer("rc", {"assets": [], "references": [], "content": {**FORM, "item_photos": [PHOTO]}, "done": True})

    snap = asyncio.run(go())
    p = snap["pipeline"]
    assert p.real_content["items"][0]["name"] == "Bàn gỗ sồi Mộc 120"
    assert "danh sách và giá" in (snap.get("notice") or "")
    assert any(a.kind == "product-image" and a.path_or_text == PHOTO for a in p.assets)  # copied into the app at B9


def test_a_photo_attached_to_a_line_goes_to_that_item_only():
    photo = "uploads/product-image-0123456789ab.jpg"
    rc = parse({**FORM, "item_photos": ["", photo, "../../etc/passwd", 7]})
    assert [i.image for i in rc.items] == ["", photo, ""]  # unsafe or non-upload values are dropped
    copy = build_copy(state(real_content=rc.model_dump()))
    assert copy.items[1].image == "/images/product-image-0123456789ab.jpg" and copy.items[0].image == ""
    assert parse({"items": FORM["items"], "item_photos": "x"}).items[0].image == ""
    # it is that item's photo only: never repeated on the hero and the other cards
    from chromaswarm.state_machine.pipeline_state import Asset
    st = state(real_content=rc.model_dump(), assets=[Asset(kind="product-image", path_or_text=photo)])
    assert "/images/product-image-0123456789ab.jpg" not in build_copy(st).images


def test_item_cards_prefer_their_own_photo():
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.agents.planner import NAV
    rc = parse({**FORM, "item_photos": ["uploads/product-image-0123456789ab.jpg"]})
    copy = build_copy(state(real_content=rc.model_dump()))
    grid = render_section(NAV.model_copy(update={"id": "products", "structure": "grid-4"}), copy).content
    assert "src={it.image}" in grid and "/images/product-image-0123456789ab.jpg" in grid
