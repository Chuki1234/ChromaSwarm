"""AI tells: one list of stock phrases and formula sentences, checked on every copy source."""

import pytest

from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import facts_for, validate
from chromaswarm.developer.i18n import copy_en
from chromaswarm.qa.ai_tells import copy_tells, find
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars

from tests.test_copywriter import good, state


@pytest.mark.parametrize("text", [
    "Sẵn sàng bắt đầu? Đăng ký chỉ mất một phút.",
    "Mộc Trà, làm đúng từ chi tiết nhỏ nhất",
    "Không chỉ là trà, mà còn là cả một nghi thức.",
    "Nâng tầm trải nghiệm uống trà của bạn",
    "Ready to start? It takes a minute.",
    "Seamless collaboration for modern teams",
    "Unlock the power of your data in just a few clicks",
    "Ưu đãi cuối tuần 🎉",
    "Chỉ mất 5 phút để thiết lập hệ thống.",  # seen in a live LLM build (StockPilot)
    "Bạn yên tâm bán hàng mọi lúc, mọi nơi.",
])
def test_tells_are_found(text):
    assert find(text)


@pytest.mark.parametrize("text", [
    "Cả nhóm thấy cùng một tiến độ",
    "Đổi trả miễn phí trong 30 ngày nếu sản phẩm còn nguyên vẹn.",
    "Lên kế hoạch trong vài phút",  # a plain claim about the product, not the "chỉ mất một phút" formula
    "Bài 3 ✓ đã học",  # UI glyphs are not emoji decoration
    "The elevator pitch, written by you",  # "elevate your" is matched as whole words only
])
def test_plain_copy_is_clean(text):
    assert find(text) == []


def test_unsourced_proof_only_when_asked():
    assert find("4,9/5 đánh giá") == []
    assert find("4,9/5 đánh giá", proof=True)
    assert find("Hơn 40+ khách hàng tin dùng", proof=True)


@pytest.mark.parametrize("domain", list(Domain))
def test_rule_copy_of_every_domain_has_no_tells(domain):
    st = PipelineState(session_id="t", raw_prompt="Website cho thương hiệu Mộc Trà", domain=domain,
                       pillars=Pillars(scope="Khách văn phòng, muốn họ đặt mua"))
    copy = build_copy(st)
    assert copy_tells(copy) == []
    assert copy_tells(copy.model_copy(update=copy_en(domain, "Moc"))) == []


def test_saas_subhead_is_about_software_not_materials():
    st = PipelineState(session_id="t", raw_prompt="phần mềm quản lý dự án", domain=Domain.SAAS)
    assert "chất liệu" not in build_copy(st).subhead


@pytest.mark.parametrize("field,text", [
    ("closing", "Sẵn sàng thay đổi? Đăng ký chỉ mất một phút."),
    ("headline", "Không chỉ là áo, mà còn là cá tính"),
    ("subhead", "Mặc là chất, phối là đẹp!"),
])
def test_copywriter_sends_a_formula_field_back_to_rule_copy(field, text):
    st = state()
    base = build_copy(st)
    out = validate({**good(base), field: text}, base, facts_for(st, base))
    assert out[field] == getattr(base, field)


def _saas_state():
    return PipelineState(session_id="t", raw_prompt="phần mềm quản lý kho StockPilot", domain=Domain.SAAS,
                         selected_page="landing", pillars=Pillars(scope="Chủ shop online, muốn họ dùng thử"))


def test_product_preview_never_lists_plans_as_records():
    from chromaswarm.developer.app_pages import preview_props
    copy = build_copy(_saas_state())
    props = preview_props(copy)
    plans = {i.name for i in copy.items}
    assert copy.product_ui and not plans & {r["name"] for r in props["rows"]}
    assert not {f[1] for f in props["figures"]} & {k for _, k in copy.facts}  # app data, not marketing facts


def test_copywriter_preview_is_used_when_valid_and_dropped_when_not():
    st = _saas_state()
    base = build_copy(st)
    pv = {"nav": ["Tổng quan", "Hàng hóa", "Nhập kho", "Xuất kho", "Báo cáo"],
          "figures": [["1.248", "mã hàng"], ["37", "sắp hết"], ["12", "phiếu nhập hôm nay"]],
          "rows": [["Áo thun basic trắng M", "SKU AT-021 · còn 8", "Sắp hết"],
                   ["Quần jean slim 30", "SKU QJ-114 · còn 64", "Đủ hàng"],
                   ["Túi tote canvas", "SKU TT-003 · còn 0", "Hết hàng"]]}
    out = validate({**good(base), "preview": pv}, base, facts_for(st, base))
    assert out["preview"]["rows"][0][0] == "Áo thun basic trắng M"
    from chromaswarm.developer.content import apply_written_copy
    assert apply_written_copy(base, out).preview_rows[2][2] == "Hết hàng"
    bad = {**pv, "rows": pv["rows"][:2]}
    assert validate({**good(base), "preview": bad}, base, facts_for(st, base))["preview"] is None


def test_closing_band_has_both_actions_and_a_facts_line():
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.nextjs import _band
    copy = build_copy(_saas_state())
    sec = Section(id="closing-cta", name="Closing", content="", structure="full-bleed-band")
    jsx = _band(sec, copy)
    assert "band-actions" in jsx and "cta-closing-secondary" in jsx and "band-note" in jsx
    assert copy.facts[0][0] in jsx
