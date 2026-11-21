"""Sample copy follows what the business sells, not only the kind of site (developer/industry.py)."""

import pytest

from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import facts_for, validate
from chromaswarm.developer.industry import (BAKERY, BEAUTY, CAFE, CLINIC, FASHION, FOOD, FURNITURE, HAIR, NAIL, RESTAURANT,
                                            RULES, SPA, detect, stray)
from chromaswarm.developer.real_content import fields
from chromaswarm.qa.ai_tells import copy_tells
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars

E, B = Domain.ECOMMERCE, Domain.BOOKING


@pytest.mark.parametrize("prompt,domain,pack", [
    ("mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng, bán bánh mì sourdough", E, BAKERY),
    ("shop quần áo trẻ em tên Bé Mon ở Sơn Trà", E, FASHION),  # "Trà" in a place name is not tea
    ("bán cà phê rang mộc Cầu Đất online", E, FOOD),
    ("mỹ phẩm thuần chay cho da nhạy cảm", E, BEAUTY),
    ("web bán đồ nội thất gỗ sồi", E, FURNITURE),
    ("quán cà phê Gác Nhỏ muốn web để khách đặt bàn", B, CAFE),
    ("quán lẩu bò cho nhóm bạn", B, RESTAURANT),
    ("tiệm nail Hồng Nhung quận 7", B, NAIL),
    ("salon tóc nam nữ Cầu Giấy", B, HAIR),
    ("nha khoa gia đình ở Thanh Khê", B, CLINIC),
    ("spa gội đầu dưỡng sinh quận 3", B, SPA),
    ("web bán hàng online", E, None),
    ("đặt lịch tư vấn tài chính", B, None),
])
def test_the_prompt_picks_the_industry(prompt, domain, pack):
    assert detect(prompt, domain) is pack


def state(prompt: str, domain: Domain) -> PipelineState:
    return PipelineState(session_id="i", raw_prompt=prompt, domain=domain, selected_page="landing",
                         pillars=Pillars(scope="mấy mẹ bỉm sữa 25-40 tuổi, muốn họ bấm đặt bánh"))


@pytest.mark.parametrize("pattern,pack,domains", RULES, ids=[p["label"] for _, p, _ in RULES])
def test_every_pack_is_clean_and_stays_in_its_industry(pattern, pack, domains):
    word = pattern.pattern.split("(?:")[1].split("|")[0]
    copy = build_copy(state(f"web cho {word} Mây", domains[0]))
    assert copy.headline == pack["headline"]
    text = " ".join([copy.headline, copy.subhead, copy.closing, *[f"{a} {b}" for a, b in copy.facts],
                     *[f"{i.name} {i.note}" for i in copy.items + copy.cards], *[f"{q} {a}" for q, a in copy.faqs],
                     *[f"{t} {b}" for t, b in copy.story], *[q for q, _ in copy.quotes]])
    assert stray(text, pack) == []
    assert copy_tells(copy, proof=False) == []
    assert all(f.placeholder for f in fields(domains[0], pack))


@pytest.mark.parametrize("domain", [E, B, Domain.OTHER])
def test_neutral_samples_name_no_industry(domain):
    copy = build_copy(state("web bán hàng online", domain))
    text = " ".join([copy.headline, copy.subhead, copy.closing, *[f"{a} {b}" for a, b in copy.facts],
                     *[f"{q} {a}" for q, a in copy.faqs], *[f"{t} {b}" for t, b in copy.story],
                     *[f"{i.name} {i.note}" for i in copy.cards], *[t for t, _ in copy.tabs]])
    assert stray(text, None) == []


def test_bakery_page_and_form_are_about_bread():
    st = state("mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng, bán bánh mì sourdough", E)
    copy = build_copy(st)
    assert copy.items[0].name == "Sourdough nguyên cám" and copy.categories[0] == "Bánh mì"
    assert not copy.subhead.startswith("Dành cho")  # the owner's description of customers stays off the hero
    assert copy.cta == "Đặt bánh"
    form = " ".join(f.placeholder for f in fields(E, BAKERY))
    assert "bánh" in form.lower() and "gỗ" not in form


def test_stray_words_only_count_when_the_user_did_not_write_them():
    assert stray("Lắp đặt tại nhà, bảo hành 2 năm", BAKERY) == ["lắp đặt", "bảo hành"]
    assert stray("Bảo hành 2 năm", BAKERY, user="bánh kem bảo hành vị ngon 2 năm") == []
    assert stray("Lắp đặt tại nhà", FURNITURE) == []


def test_copywriter_sends_back_a_field_written_for_another_industry():
    st = state("mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng, bán bánh mì sourdough", E)
    base = build_copy(st)
    facts = facts_for(st, base)
    assert facts["nganh"] == "tiệm bánh"
    raw = {"brand": base.brand, "eyebrow": "Tiệm bánh", "headline": "Bánh ra lò mỗi sớm",
           "subhead": "Giao tận nhà, lắp đặt miễn phí.", "closing": base.closing,
           "story": [[t, b] for t, b in base.story], "items": [[i.name, i.note] for i in base.items],
           "cards": [], "faqs": [[q, a] for q, a in base.faqs], "categories": base.categories}
    out = validate(raw, base, facts)
    assert out["subhead"] == base.subhead and out["headline"] == "Bánh ra lò mỗi sớm"
