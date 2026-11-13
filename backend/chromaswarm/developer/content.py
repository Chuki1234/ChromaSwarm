"""Page copy for the rule-based Developer department.

Without an LLM the copy is assembled from what the user actually said (prompt,
CTA, audience, assets such as "Slogan: ...") plus restrained domain defaults.
Every default is marked in PRODUCT.md as sample content to replace at B12.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from chromaswarm.agents.consultant import extract_cta, project_title
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState


class Item(BaseModel):
    name: str
    note: str
    price: str = ""
    tag: str = ""


class PageCopy(BaseModel):
    brand: str
    headline: str
    subhead: str
    cta: str
    cta_secondary: str
    nav: list[str]
    nav_links: list[tuple[str, str]]  # (label, href): built pages first, then in-page anchors
    facts: list[tuple[str, str]]
    story: list[tuple[str, str]]
    items: list[Item]
    categories: list[str]
    faqs: list[tuple[str, str]]
    closing: str
    footer_line: str
    tabs: list[tuple[str, str]]
    images: list[str] = []  # Clone mode, owned site: the reference's own photos (used before tonal placeholders)


DEFAULTS: dict[Domain, dict] = {
    Domain.ECOMMERCE: dict(
        nav=["Bộ sưu tập", "Câu chuyện", "Hỏi đáp", "Liên hệ"],
        facts=[("48h", "giao nội thành"), ("30 ngày", "đổi trả miễn phí"), ("2 năm", "bảo hành"), ("100%", "kiểm tra trước khi giao")],
        items=[Item(name="Sản phẩm chủ lực", note="Mẫu bán chạy nhất", price="2.490.000₫", tag="Mới"),
               Item(name="Phiên bản nhỏ gọn", note="Cho không gian hẹp", price="1.690.000₫"),
               Item(name="Bộ đôi tiết kiệm", note="Mua kèm giảm 10%", price="3.990.000₫"),
               Item(name="Phụ kiện đi kèm", note="Hoàn thiện bộ sản phẩm", price="390.000₫")],
        categories=["Phòng khách", "Phòng ngủ", "Phòng làm việc", "Phụ kiện"],
        faqs=[("Bao lâu thì nhận được hàng?", "Nội thành 48 giờ, tỉnh khác 3–5 ngày làm việc."),
              ("Tôi có được đổi trả không?", "Đổi trả miễn phí trong 30 ngày nếu sản phẩm còn nguyên vẹn."),
              ("Có lắp đặt tại nhà không?", "Có, đội lắp đặt đi kèm khi giao hàng, không tính phí."),
              ("Thanh toán bằng cách nào?", "Chuyển khoản, thẻ hoặc thanh toán khi nhận hàng."),
              ("Bảo hành ra sao?", "Bảo hành 2 năm cho lỗi kỹ thuật, bảo trì trọn đời có tính phí.")],
    ),
    Domain.SAAS: dict(
        nav=["Tính năng", "Bảng giá", "Khách hàng", "Tài liệu"],
        facts=[("99,9%", "thời gian hoạt động"), ("5 phút", "để bắt đầu"), ("24/7", "hỗ trợ"), ("ISO 27001", "bảo mật dữ liệu")],
        items=[Item(name="Gói Cơ bản", note="Cho nhóm đến 5 người", price="0₫"),
               Item(name="Gói Nhóm", note="Không giới hạn dự án", price="390.000₫/tháng", tag="Phổ biến"),
               Item(name="Gói Doanh nghiệp", note="SSO, phân quyền, SLA", price="Liên hệ")],
        categories=["Quản lý", "Báo cáo", "Tự động hóa", "Tích hợp"],
        faqs=[("Có dùng thử miễn phí không?", "Có, 14 ngày đầy đủ tính năng, không cần thẻ."),
              ("Dữ liệu lưu ở đâu?", "Trên máy chủ đặt tại Việt Nam, sao lưu hằng ngày."),
              ("Có hủy được bất cứ lúc nào không?", "Có, hủy trong phần cài đặt, không phát sinh phí."),
              ("Có xuất hóa đơn VAT không?", "Có, hóa đơn điện tử gửi qua email mỗi kỳ."),
              ("Hỗ trợ tích hợp thế nào?", "Có API và kết nối sẵn với các công cụ phổ biến.")],
    ),
    Domain.BOOKING: dict(
        nav=["Dịch vụ", "Bảng giá", "Đặt lịch", "Liên hệ"],
        facts=[("8:00–21:00", "mỗi ngày"), ("15 phút", "xác nhận lịch"), ("4,9/5", "đánh giá"), ("Miễn phí", "đổi lịch trước 2 giờ")],
        items=[Item(name="Dịch vụ tiêu chuẩn", note="60 phút", price="350.000₫"),
               Item(name="Dịch vụ nâng cao", note="90 phút", price="550.000₫", tag="Được chọn nhiều"),
               Item(name="Gói thành viên", note="5 lần, dùng trong 3 tháng", price="1.500.000₫")],
        categories=["Chăm sóc", "Thư giãn", "Gói thành viên", "Quà tặng"],
        faqs=[("Tôi có cần đặt trước không?", "Nên đặt trước để giữ khung giờ, nhận khách vãng lai khi còn chỗ."),
              ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua link trong tin nhắn xác nhận."),
              ("Có chỗ đỗ xe không?", "Có chỗ đỗ xe máy và ô tô ngay trước cửa."),
              ("Thanh toán ra sao?", "Thanh toán tại quầy bằng tiền mặt, thẻ hoặc chuyển khoản."),
              ("Có gói quà tặng không?", "Có thẻ quà tặng theo giá trị hoặc theo dịch vụ.")],
    ),
    Domain.EDTECH: dict(
        nav=["Khóa học", "Lộ trình", "Giảng viên", "Hỏi đáp"],
        facts=[("12 tuần", "lộ trình"), ("40+", "bài thực hành"), ("1:1", "chấm bài"), ("Trọn đời", "xem lại bài giảng")],
        items=[Item(name="Khóa nền tảng", note="Dành cho người mới", price="1.990.000₫"),
               Item(name="Khóa chuyên sâu", note="Dự án thực tế", price="3.490.000₫", tag="Khuyên dùng"),
               Item(name="Kèm cặp 1:1", note="8 buổi với giảng viên", price="5.900.000₫")],
        categories=["Cơ bản", "Nâng cao", "Dự án", "Luyện thi"],
        faqs=[("Tôi chưa biết gì có học được không?", "Được, khóa nền tảng bắt đầu từ con số 0."),
              ("Học trên thiết bị nào?", "Máy tính, điện thoại hoặc máy tính bảng."),
              ("Có chứng chỉ không?", "Có chứng chỉ hoàn thành sau khi nộp đủ bài tập."),
              ("Có hoàn tiền không?", "Hoàn tiền 100% trong 7 ngày đầu nếu chưa phù hợp."),
              ("Hỏi bài ở đâu?", "Trong nhóm học viên và buổi hỏi đáp trực tiếp hằng tuần.")],
    ),
}
DEFAULTS[Domain.PORTFOLIO] = dict(
    nav=["Dự án", "Giới thiệu", "Kinh nghiệm", "Liên hệ"],
    facts=[("8 năm", "kinh nghiệm"), ("40+", "dự án"), ("12", "khách hàng thường xuyên"), ("3", "giải thưởng")],
    items=[Item(name="Dự án nổi bật", note="Thiết kế & triển khai"), Item(name="Dự án thứ hai", note="Nghiên cứu người dùng"),
           Item(name="Dự án thứ ba", note="Hệ thống nhận diện")],
    categories=["Thiết kế", "Phát triển", "Nghiên cứu", "Viết"],
    faqs=[("Bạn nhận dự án loại nào?", "Website, sản phẩm số và hệ thống nhận diện."),
          ("Thời gian một dự án?", "Thường 4–8 tuần tùy phạm vi."),
          ("Làm việc từ xa được không?", "Được, trao đổi qua họp trực tuyến hằng tuần."),
          ("Báo giá thế nào?", "Báo giá theo phạm vi sau buổi trao đổi đầu tiên."),
          ("Có bảo trì sau bàn giao không?", "Có gói bảo trì theo tháng.")],
)
DEFAULTS[Domain.OTHER] = DEFAULTS[Domain.ECOMMERCE]

_SLOGAN = re.compile(r"^\s*(?:slogan|thông điệp|tagline)\s*[:\-]\s*(.+)$", re.I)


def _brand(title: str) -> str:
    """'Web bán đồ nội thất gỗ sồi tối giản' -> 'Nội thất gỗ sồi tối giản'."""
    t = re.sub(r"^(?:web|website|trang web|trang)\s+(?:bán|cho|về|của)?\s*(?:đồ|các)?\s*", "", title, flags=re.I).strip()
    t = t or title
    return t[:1].upper() + t[1:]


def nav_links(state: PipelineState, labels: list[str]) -> list[tuple[str, str]]:
    """Links only to pages that exist (built or being built), so the handover never shows a 404."""
    pages = {p.slug: p.title for p in state.sitemap}
    built = [(pages.get(slug, slug), route) for slug, route in state.page_routes.items() if route != "/"]
    anchors = [(label, "#") for label in labels]
    return (built + anchors)[:5]


def owned_clone_copy(copy: PageCopy, content: dict) -> PageCopy:
    """Clone mode on the user's own site: their real text and images replace the sample copy."""
    secs: dict[str, dict] = content.get("sections", {})
    by_kind = lambda *kinds: [v for v in secs.values() if v.get("structure") in kinds]  # noqa: E731
    hero = next(iter(by_kind("split-7-5", "full-bleed-image")), {})
    header = next(iter(by_kind("sticky-bar")), {})
    updates: dict = {}
    brand = header.get("logo") or content.get("site_title")
    if brand:
        updates["brand"] = brand[:40]
    if hero.get("heading"):
        updates["headline"] = hero["heading"]
    if hero.get("paragraphs"):
        updates["subhead"] = hero["paragraphs"][0]
    if hero.get("buttons"):
        updates["cta"] = hero["buttons"][0]
    nav = [(label, href) for label, href in header.get("nav", []) if label != brand]  # the logo is not a nav item
    if nav:
        updates["nav"] = [label for label, _ in nav][:5]
        updates["nav_links"] = [(label, href if href.startswith(("/", "#", "http")) else "#") for label, href in nav][:5]
    # Each kind of copy comes only from the section kind that holds it on the reference page.
    items = [i for v in by_kind("bento", "grid-4", "horizontal-scroller") for i in v.get("items", []) if i.get("title")]
    if len(items) >= 2:
        updates["items"] = [Item(name=i["title"][:60], note=i.get("note", "")[:140], price=i.get("price", "")) for i in items[:8]]
    faqs = [tuple(f) for v in by_kind("accordion") for f in v.get("faqs", []) if f and f[0]]
    if faqs:
        updates["faqs"] = faqs[:8]
    story = [pair for v in by_kind("alternating-z", "split-5-7")
             for pair in zip([h for h in v.get("headings", []) if h], v.get("paragraphs", []))]
    if story:
        updates["story"] = story[:3]
    metrics = next(iter(by_kind("inline-metrics")), {})
    facts = [(i["title"], i.get("note", "")) for i in metrics.get("items", []) if i.get("title")]
    if len(facts) >= 2:
        updates["facts"] = facts[:4]
    band = next(iter(by_kind("full-bleed-band")), {})
    if band.get("heading"):
        updates["closing"] = band["heading"]
    images = list(dict.fromkeys(u for v in secs.values() for u in v.get("images", []) if u.startswith("https://")))
    if images:
        updates["images"] = images[:12]
    if content.get("site_title"):
        updates["footer_line"] = f"© {content['site_title'][:40]}"
    return copy.model_copy(update=updates)


def build_copy(state: PipelineState) -> PageCopy:
    d = DEFAULTS.get(state.domain or Domain.OTHER, DEFAULTS[Domain.ECOMMERCE])
    title = project_title(state.raw_prompt or "Dự án", limit=40).rstrip("…")
    brand = _brand(title)
    cta = extract_cta(state.pillars.scope or "") or "Liên hệ ngay"
    slogan = next((m.group(1).strip() for a in state.assets if (m := _SLOGAN.match(a.path_or_text))), None)
    headline = slogan or f"{brand}, làm đúng từ chi tiết nhỏ nhất"
    persona = (state.pillars.scope or "").split(",")[0].strip()
    subhead = (f"Dành cho {persona[:1].lower() + persona[1:]}: " if persona else "") + \
        "rõ ràng về chất liệu, giá và thời gian nhận hàng ngay trên trang này."
    copy = PageCopy(
        brand=brand, headline=headline, subhead=subhead, cta=cta, cta_secondary="Xem chi tiết",
        nav=d["nav"], nav_links=nav_links(state, d["nav"]), facts=d["facts"],
        story=[("Chọn vật liệu trước, thiết kế sau", "Mỗi lựa chọn bắt đầu từ vật liệu bền và an toàn, rồi mới đến hình dáng."),
               ("Làm ít mẫu, làm thật kỹ", "Danh mục gọn để mỗi sản phẩm được kiểm tra kỹ trước khi đến tay bạn."),
               ("Ở lại sau khi bán", "Bảo hành, bảo trì và tư vấn sau mua là một phần của sản phẩm.")],
        items=d["items"], categories=d["categories"], faqs=d["faqs"],
        closing=f"Sẵn sàng bắt đầu? {cta} chỉ mất một phút.",
        footer_line=f"© {brand}. Nội dung mẫu — thay bằng thông tin thật ở bước bàn giao.",
        tabs=[("Mô tả", "Thông tin tổng quan về sản phẩm và cách sử dụng."),
              ("Chất liệu", "Thành phần, nguồn gốc và cách bảo quản."),
              ("Giao hàng", "Thời gian giao, phí vận chuyển và chính sách đổi trả.")],
    )
    clone = state.clone
    if state.selected_page == "clone" and clone and clone.owned and clone.content:
        return owned_clone_copy(copy, clone.content)
    return copy
