"""LLM copywriter: validation in code, rule-based fallback, applied once per page."""

import pytest

from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import Copywriter, copy_key, facts_for, validate
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars


def state(**kw) -> PipelineState:
    return PipelineState(session_id="c", raw_prompt="shop thời trang streetwear cho giới trẻ", domain=Domain.ECOMMERCE,
                         selected_page="landing", pillars=Pillars(theme="neo-brutalist", layout="visual-first",
                                                                   color="light", margins="balanced",
                                                                   scope="Sinh viên 18-25, muốn họ bấm Mua ngay"), **kw)


def good(base) -> dict:
    return {
        "brand": "Streetwear", "eyebrow": "Phong cách đường phố", "headline": "Chất riêng, không sợ va chạm",
        "subhead": "Đồ mặc hằng ngày cho sinh viên: form rộng, vải dày, dễ phối.", "closing": "Mua ngay kẻo hết size",
        "story": [[f"Tiêu đề {i}", "Nội dung cụ thể về cách may và chọn vải."] for i in range(len(base.story))],
        "items": [["Áo Hoodie Oversize", "Giá: 2.490.000₫ - Rộng rãi, dễ phối"]] * len(base.items),
        "cards": [["Quần Cargo", "Nhiều túi"]] * len(base.cards),
        "categories": ["Áo", "Quần", "Giày", "Phụ kiện"][:len(base.categories)],
        "faqs": [["Đổi size được không?", "Được, trong 7 ngày nếu còn tem."]] * len(base.faqs),
    }


def test_valid_copy_passes_and_prices_are_stripped_from_notes():
    st = state()
    base = build_copy(st)
    out = validate(good(base), base, facts_for(st, base))
    assert out["headline"] == "Chất riêng, không sợ va chạm"
    assert out["items"][0] == ["Áo Hoodie Oversize", "Rộng rãi, dễ phối"]


def test_one_bad_field_falls_back_alone():
    st = state()
    base = build_copy(st)
    raw = {**good(base), "headline": "Nâng tầm phong cách của bạn", "subhead": "Nến cháy 60 giờ, giảm 50% hôm nay."}
    out = validate(raw, base, facts_for(st, base))
    assert out["headline"] == base.headline and out["subhead"] == base.subhead  # only these two fell back
    assert out["closing"] == "Mua ngay kẻo hết size" and out["brand"] == "Streetwear"


@pytest.mark.parametrize("patch, reason", [
    ({"headline": "x" * 80}, "too long"),
    ({"faqs": [["Hỏi?", "Đáp."]]}, "expected"),
    ({"eyebrow": "Chất riêng, không sợ va chạm"}, "repeats"),
])
def test_invalid_copy_is_rejected(patch, reason):
    st = state()
    base = build_copy(st)
    with pytest.raises(ValueError, match=reason):
        validate({**good(base), **patch}, base, facts_for(st, base))


def test_extra_list_items_are_trimmed_to_the_page_shape():
    st = state()
    base = build_copy(st)
    raw = good(base)
    raw["story"] = raw["story"] + [["Thừa", "Thừa"]]
    assert len(validate(raw, base, facts_for(st, base))["story"]) == len(base.story)


class FakeChat:
    model = "fake"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete_json(self, system, user, images=None, max_tokens=1500):
        self.calls += 1
        return self.replies.pop(0)


def test_copywriter_retries_once_then_falls_back():
    st = state()
    base = build_copy(st)
    bad = {**good(base), "faqs": [["Hỏi?", "Đáp."]]}  # wrong shape: retried, then rule copy
    chat = FakeChat([bad, bad])
    assert Copywriter(chat)(st, base) is None and chat.calls == 2
    chat = FakeChat([bad, good(base)])
    assert Copywriter(chat)(st, base)["brand"] == "Streetwear"


def test_build_copy_applies_written_copy_and_keeps_rule_prices():
    st = state()
    base = build_copy(st)
    st.page_copy = validate(good(base), base, facts_for(st, base))
    copy = build_copy(st)
    assert copy.headline == "Chất riêng, không sợ va chạm" and copy.brand == "Streetwear"
    assert copy.items[0].name == "Áo Hoodie Oversize" and copy.items[0].price == base.items[0].price
    assert "mẫu" not in copy.footer_line and "Unsplash" not in copy.footer_line  # no disclaimer on the page


def test_copy_key_changes_with_feedback():
    st = state()
    k = copy_key(st)
    st.plan_feedback.append("viết vui hơn")
    assert copy_key(st) != k


def test_shop_cards_are_the_written_products():
    st = state()
    base = build_copy(st)
    raw = {**good(base), "cards": [["Kiểm tra 100%", "Chính sách"]] * len(base.cards)}
    out = validate(raw, base, facts_for(st, base))
    assert out["cards"] == out["items"][:len(base.cards)]
