"""The shop's cart is kept across pages (developer/cart.py)."""

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import Item, build_copy
from chromaswarm.developer.nextjs import render_section, scaffold
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState, Pillars


def state(domain=Domain.ECOMMERCE, routes=None, **kw) -> PipelineState:
    return PipelineState(session_id="c", raw_prompt="mình mở tiệm bánh tên Bếp Nhà Mây", domain=domain,
                         selected_page="landing", page_routes=routes or {"landing": "/"},
                         pillars=Pillars(scope="mấy mẹ bỉm sữa, muốn họ bấm đặt bánh"), **kw)


def render(structure: str, copy, sid: str = "x") -> str:
    return render_section(Section(id=sid, name=sid, structure=structure, content=""), copy).content


def test_cart_route_appears_only_once_the_cart_page_is_built():
    assert build_copy(state()).order.cart == ""
    assert build_copy(state(routes={"landing": "/", "cart": "/cart"})).order.cart == "/cart"
    assert build_copy(state(Domain.SAAS, routes={"landing": "/", "cart": "/cart"})).order.cart == ""


def test_the_app_ships_the_cart_store():
    from tests.test_surfaces import spec_for
    from chromaswarm.engines.presets import Surface
    files = {f.path: f.content for f in scaffold("Mây", spec_for(Surface.FLAT))}
    cart = files["components/Cart.tsx"]
    assert "localStorage" in cart and "useSyncExternalStore" in cart and "export function addToCart" in cart
    assert '"cart": ""' in files["content/order.ts"]


def test_product_buttons_fill_the_cart_or_order_the_item():
    copy = build_copy(state())
    grid = render("grid-4", copy, "product-grid")
    assert 'import { addToCart } from "@/components/Cart"' in grid and 'import { ORDER } from "@/content/order"' in grid
    assert "addToCart({ name: it.name, price: it.amount" in grid and "openOrder(it.name)" in grid
    assert '"amount": 85000' in grid and "cart:add" not in grid  # the price as the shop wrote it, read as ₫
    quick = render("bento", copy, "collection")
    assert "addToCart({ name, price: it.amount" in quick and "openOrder(name)" in quick
    pdp = render("split-7-5", copy.model_copy(update={"items": [Item(name="Sourdough", note="", price="85k")]}), "product-main")
    assert "addToCart({ name: `${it.name} · ${variant}`, price: it.amount" in pdp and '"amount": 85000' in pdp
    assert "openOrder(it.name)" in pdp and "href={ORDER.cart}" in pdp


def test_header_shows_the_carts_lines_only_with_a_cart_page():
    nav = render("sticky-bar", build_copy(state()), "site-header")
    assert "useCart()" in nav and "{ORDER.cart && <div className=\"cart-wrap\">" in nav
    assert "href={ORDER.cart}" in nav and "cart:add" not in nav and "useEffect" not in nav


def test_cart_page_reads_the_visitors_cart_never_invented_lines():
    copy = build_copy(state(routes={"landing": "/", "cart": "/cart"}))
    page = render("cart-checkout", copy, "cart")
    assert "const lines = useCart();" in page and "setCartQty(it.name" in page
    assert "clearCart(); return;" in page and "390000" not in page and "530000" not in page
    assert "ready && lines.length === 0" in page  # a full cart never flashes "empty" while it loads
    priced = copy.model_copy(update={"items": [Item(name="A", note="", price="85k"), Item(name="B", note="", price="Liên hệ")]})
    page = render("cart-checkout", priced, "cart")
    assert '"name": "A"' in page and '"name": "B"' not in page  # suggestions only for items with a price
