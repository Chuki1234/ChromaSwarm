"""The main button opens a real order / booking / contact form (developer/order.py)."""

import io
import zipfile

import pytest

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.industry import BAKERY, CAFE
from chromaswarm.developer.nextjs import render_section, scaffold
from chromaswarm.developer.order import channels, order_file, order_spec
from chromaswarm.developer.template import template_zip
from chromaswarm.engines.presets import Surface
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars


@pytest.mark.parametrize("contact,phone,zalo,email", [
    ("45 Lê Đình Dương · 6h30–20h · zalo 0905 111 222", "0905111222", "0905111222", ""),
    ("Hotline 0909.123.456 · Zalo: 0912 345 678 · ban@tiem.vn", "0909123456", "0912345678", "ban@tiem.vn"),
    ("+84 905 111 222", "0905111222", "", ""),
    ("Mở 9h–21h, 12 Lê Lợi", "", "", ""),  # hours and house numbers are not phone numbers
])
def test_channels_come_from_the_owners_contact_line(contact, phone, zalo, email):
    ch = channels(contact)
    assert (ch.phone, ch.zalo, ch.email) == (phone, zalo, email)


def state(prompt: str, domain: Domain, **kw) -> PipelineState:
    return PipelineState(session_id="o", raw_prompt=prompt, domain=domain, selected_page="landing",
                         pillars=Pillars(scope="mấy mẹ bỉm sữa, muốn họ bấm đặt bánh"), **kw)


def test_bakery_order_asks_the_cake_the_day_and_pickup_or_delivery():
    copy = build_copy(state("mình mở tiệm bánh tên Bếp Nhà Mây ở Đà Nẵng", Domain.ECOMMERCE,
                            real_content={"contact": "zalo 0905 111 222", "items": []}))
    o = copy.order
    assert o.kind == "shop" and o.title == "Đặt bánh" and o.item_label == "Bánh"
    assert o.items[0] == ("Sourdough nguyên cám", "85.000₫") and o.qty and o.delivery
    assert o.when == "Ngày nhận bánh" and o.time and o.channels.zalo == "0905111222"


def test_kinds_follow_the_site():
    cafe = order_spec(Domain.BOOKING, "Gác Nhỏ", "Đặt bàn", [], "", CAFE)
    assert cafe.kind == "booking" and cafe.party and not cafe.item_required and cafe.when == "Ngày đặt bàn"
    saas = order_spec(Domain.SAAS, "StockPilot", "Dùng thử", [], "", None)
    assert saas.kind == "lead" and not saas.qty and not saas.when
    folio = build_copy(state("portfolio thiết kế của Lan", Domain.PORTFOLIO)).order
    assert folio.kind == "lead" and folio.items == []  # past work is not something to order
    en = order_spec(Domain.ECOMMERCE, "Mây", "Order", [], "", BAKERY, lang="en")
    assert en.labels["submit"] == "Send" and en.when == ""  # Vietnamese pack labels never land on an English page


def test_main_buttons_open_the_form_instead_of_faking_a_reply():
    copy = build_copy(state("mình mở tiệm bánh tên Bếp Nhà Mây", Domain.ECOMMERCE))
    for structure, sid in (("split-7-5", "hero"), ("full-bleed-band", "closing-cta"), ("bento", "collection")):
        code = render_section(Section(id=sid, name=sid, structure=structure, content=""), copy).content
        assert "Đã ghi nhận" not in code and "setSent" not in code
        assert 'import { openOrder } from "@/components/OrderDialog"' in code and "openOrder(" in code
    quick = render_section(Section(id="collection", name="c", structure="bento", content=""), copy).content
    assert "openOrder(name)" in quick and "quick-view-order" in quick


def test_the_app_ships_the_dialog_the_api_and_a_guide():
    from tests.test_surfaces import spec_for
    spec = spec_for(Surface.FLAT)
    files = {f.path: f.content for f in scaffold("Mây", spec)}
    assert "<OrderDialog />" in files["app/layout.tsx"]
    assert "export function openOrder" in files["components/OrderDialog.tsx"]
    route = files["app/api/orders/route.ts"]
    assert "ORDER_WEBHOOK_URL" in route and "status: 400" in route and "status: 503" in route
    assert "Nhận đơn" in files["HUONG_DAN.md"] and "content/order.ts" in files
    copy = build_copy(state("tiệm bánh Mây", Domain.ECOMMERCE))
    assert '"when": "Ngày nhận bánh"' in order_file(copy.order).content


def test_received_orders_never_leave_with_the_template(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "orders.jsonl").write_text('{"contact": "0905111222"}\n')
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text("x")
    names = zipfile.ZipFile(io.BytesIO(template_zip(tmp_path))).namelist()
    assert not any("orders.jsonl" in n for n in names) and any(n.endswith("app/page.tsx") for n in names)


@pytest.mark.parametrize("structure,source,button", [
    ("cart-checkout", "checkout", "place-order"), ("booking-flow", "booking", "booking-confirm"),
    ("contact-form", "contact", "contact-send"),
])
def test_page_forms_send_for_real(structure, source, button):
    copy = build_copy(state("tiệm bánh Mây", Domain.ECOMMERCE))
    code = render_section(Section(id=structure, name=structure, structure=structure, content=""), copy).content
    assert f'sendOrder({{ source: "{source}"' in code and f'<Undelivered summary={{summary}} id="{source}"' in code
    assert 'import { sendOrder, Undelivered } from "@/components/OrderDialog"' in code
    assert "setDone(true)" not in code and f'data-swarm-id="{button}"' in code
    from chromaswarm.developer.order import ORDER_ROUTE_TS
    assert f'"{source}"' in ORDER_ROUTE_TS


def test_contact_page_shows_the_owners_contact_never_an_invented_one():
    real = {"contact": "45 Lê Đình Dương, Đà Nẵng · 6h30–20h · zalo 0905 111 222 · banh@may.vn", "items": []}
    copy = build_copy(state("tiệm bánh Mây", Domain.ECOMMERCE, real_content=real))
    code = render_section(Section(id="contact", name="c", structure="contact-form", content=""), copy).content
    assert "45 Lê Đình Dương" in code and "tel:0905111222" in code and "mailto:banh@may.vn" in code
    assert "Nguyễn Huệ" not in code and "hello@example.com" not in code
    bare = render_section(Section(id="contact", name="c", structure="contact-form", content=""),
                          build_copy(state("tiệm bánh Mây", Domain.ECOMMERCE))).content
    assert "contact-facts" not in bare and "Nguyễn Huệ" not in bare


@pytest.mark.parametrize("price,amount", [("85k", 85000), ("120.000đ", 120000), ("1,5tr", 1500000), ("2 triệu", 2000000),
                                          ("Từ 200.000₫", 200000), ("Liên hệ", None)])
def test_cart_reads_prices_as_shops_write_them(price, amount):
    from chromaswarm.developer.app_pages import _amount
    assert _amount(price) == amount
