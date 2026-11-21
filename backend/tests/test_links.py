"""Every link of a generated site leads somewhere (content.nav_links, nextjs routes_file, QA dead-link)."""

import re

import pytest

from chromaswarm.agents.planner import page_sections
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.nextjs import render_section, routes_file
from chromaswarm.developer.order import ORDER_DIALOG_TSX
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars

ROUTES = {"landing": "/", "catalog": "/catalog", "pdp": "/pdp", "cart": "/cart"}


def state(page="landing", routes=None, domain=Domain.ECOMMERCE) -> PipelineState:
    return PipelineState(session_id="l", raw_prompt="mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng", domain=domain,
                         selected_page=page, page_routes=routes if routes is not None else ROUTES,
                         pillars=Pillars(scope="mẹ bỉm sữa, muốn họ bấm đặt bánh", layout="catalog", theme="warm-organic"))


def test_menu_links_are_short_local_names_and_real_targets():
    links = build_copy(state()).nav_links
    assert links[0] == ("Sản phẩm", "/catalog")  # not "Product Catalog & Filter"
    hrefs = dict(links)
    assert "Giỏ hàng" not in hrefs and "Chi tiết sản phẩm" not in hrefs  # cart icon / product cards reach those
    assert hrefs["Đặt trước"] == "#dat-hang" and hrefs["Hỏi đáp"] == "/#faq" and hrefs["Liên hệ"] == "/#site-footer"
    assert all(h not in ("#", "") for _, h in links)
    # the home page's own sections are what "/#…" points at
    ids = {s.id for s in page_sections(state())}
    assert all(h[2:] in ids for _, h in links if h.startswith("/#"))


def test_contact_goes_to_the_contact_page_once_built():
    hrefs = dict(build_copy(state(routes={**ROUTES, "contact": "/contact"})).nav_links)
    assert hrefs["Liên hệ"] == "/contact"


@pytest.mark.parametrize("page", ["landing", "home", "catalog", "pdp", "cart"])
def test_no_generated_section_has_a_bare_hash_link(page):
    st = state(page, {**ROUTES, page: ROUTES.get(page, f"/{page}")})
    copy = build_copy(st)
    for sec in page_sections(st):
        code = render_section(sec, copy, page).content
        assert 'href="#"' not in code, (page, sec.id)
        for target in re.findall(r'href="#([\w-]+)"', code):  # in-page links point at a section of this page
            assert target == "details" or target in {s.id for s in page_sections(st)}, (page, sec.id, target)


def test_sections_can_be_linked_to():
    copy = build_copy(state())
    code = render_section(page_sections(state())[-1], copy, "landing").content
    assert 'id="site-footer"' in code


def test_product_cards_open_the_product_they_show():
    f = routes_file(ROUTES)
    assert '"pdp": "/pdp"' in f.content and "export const detail" in f.content and "?sp=" in f.content
    copy = build_copy(state("pdp"))
    pdp = render_section(next(s for s in page_sections(state("pdp")) if s.id == "product-main"), copy, "pdp").content
    assert 'get("sp")' in pdp and "ITEMS.findIndex" in pdp and "useEffect" in pdp
    catalog = build_copy(state("catalog"))
    body = render_section(next(s for s in page_sections(state("catalog")) if s.structure == "sidebar-grid-4"), catalog, "catalog").content
    assert "href={detail(it.name)}" in body and 'get("dm")' in body and 'import { ROUTES, detail } from "@/content/routes"' in body


def test_order_links_open_the_form_from_any_page():
    assert '"#dat-hang"' in ORDER_DIALOG_TSX and "hashchange" in ORDER_DIALOG_TSX


def test_shop_footer_lists_only_links_that_lead_somewhere():
    copy = build_copy(state())
    assert ("Câu hỏi thường gặp", "/#faq") in copy.footer_links and all(h for _, h in copy.footer_links)
    assert not any(label in ("Vận chuyển", "Đổi trả", "Bảo mật", "Điều khoản") for label, _ in copy.footer_links)


def test_categories_come_from_the_items_never_handed_out_in_turn():
    from chromaswarm.developer.content import guess_category
    cats = ["Bánh mì", "Bánh ngọt", "Bánh kem", "Hộp quà"]
    assert guess_category("Bánh kem bắp", cats) == "Bánh kem" and guess_category("Croissant bơ", cats) == ""
    copy = build_copy(state("catalog"))
    body = render_section(next(s for s in page_sections(state("catalog")) if s.structure == "sidebar-grid-4"), copy, "catalog").content
    assert '"name": "Croissant bơ"' in body and '"cat": ""' in body  # no category rather than a wrong one
    assert 'const CATS = ["Bánh mì", "Bánh kem"]' in body  # only categories that have items are filters
