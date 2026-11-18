"""Page copy for the rule-based Developer department.

Without an LLM the copy is assembled from what the user actually said (prompt,
CTA, audience, assets such as "Slogan: ...") plus restrained domain defaults.
Every default is marked in PRODUCT.md as sample content to replace at B12.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from chromaswarm.agents.consultant import extract_cta, project_title
from chromaswarm.developer.i18n import CLONE_PLACEHOLDERS_EN, copy_en, page_lang
from chromaswarm.developer.photos import stock_photos
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState


class Item(BaseModel):
    name: str
    note: str
    price: str = ""
    tag: str = ""
    category: str = ""  # for the category tabs of a product grid


class PageCopy(BaseModel):
    brand: str
    eyebrow: str = ""  # small label above the hero headline; the brand when empty
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
    quotes: list[tuple[str, str]] = []  # (quote, who) — sample testimonials, clearly marked as samples
    usp: list[str] = []  # brand promises (brief), shown in the usp strip
    quiz_options: list[str] = []  # choices of the interactive picker (brief), e.g. skin types
    announcement: str = ""  # one-line offer above the header
    shop: bool = False  # a store: header gets search / account / cart, footer gets policy links
    cards: list[Item] = []  # bento cards: products for shops / projects for portfolios, features otherwise
    rows: list[tuple[str, str]] = []  # list rows: (entry, meta) — posts with dates, work history with periods
    lang: str = "vi"  # page language (developer/i18n.py): a Clone keeps the reference's language


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

# Sample story rows / feature points per domain (marked as sample content at B12; replaced by real copy).
STORY: dict[Domain, list[tuple[str, str]]] = {
    Domain.ECOMMERCE: [("Chọn vật liệu trước, thiết kế sau", "Mỗi lựa chọn bắt đầu từ vật liệu bền và an toàn, rồi mới đến hình dáng."),
                       ("Làm ít mẫu, làm thật kỹ", "Danh mục gọn để mỗi sản phẩm được kiểm tra kỹ trước khi đến tay bạn."),
                       ("Ở lại sau khi bán", "Bảo hành, bảo trì và tư vấn sau mua là một phần của sản phẩm."),
                       ("Giao tận nơi, lắp đặt tận tay", "Đội giao hàng của cửa hàng lắp đặt và hướng dẫn sử dụng ngay tại nhà."),
                       ("Giá rõ ràng từ đầu", "Giá niêm yết đã gồm thuế và phí giao nội thành, không phát sinh khi thanh toán."),
                       ("Đổi ý vẫn kịp", "Trong 30 ngày, sản phẩm còn nguyên vẹn được đổi hoặc hoàn tiền.")],
    Domain.SAAS: [("Lên kế hoạch trong vài phút", "Tạo dự án, chia việc và đặt hạn cho cả nhóm từ một màn hình."),
                  ("Mọi việc ở cùng một chỗ", "Yêu cầu, lỗi và ý tưởng đổ về một hàng đợi; không còn tìm trong chat."),
                  ("Theo dõi tiến độ không cần họp", "Bảng tiến độ tự cập nhật khi từng việc chuyển trạng thái."),
                  ("Tự động hóa việc lặp lại", "Quy tắc tự gán người, đổi trạng thái và nhắc hạn thay cho thao tác tay."),
                  ("Kết nối công cụ đang dùng", "Đồng bộ với lịch, email và kho mã nguồn qua tích hợp có sẵn."),
                  ("Báo cáo cho quản lý", "Số liệu tuần được tổng hợp sẵn, xuất ra bảng tính bằng một nút.")],
    Domain.BOOKING: [("Đặt lịch trong 30 giây", "Chọn dịch vụ, chọn giờ trống và xác nhận, không cần gọi điện."),
                     ("Nhắc lịch tự động", "Tin nhắn nhắc trước một ngày và trước hai giờ để không lỡ hẹn."),
                     ("Kỹ thuật viên có chứng chỉ", "Mỗi người phụ trách đều qua đào tạo và có chứng chỉ hành nghề."),
                     ("Không gian riêng tư", "Phòng riêng, khử khuẩn sau mỗi lượt khách."),
                     ("Bảng giá công khai", "Giá từng dịch vụ hiển thị rõ trước khi đặt."),
                     ("Đổi lịch linh hoạt", "Đổi miễn phí trước hai giờ ngay trong tin nhắn xác nhận.")],
    Domain.EDTECH: [("Học theo lộ trình", "Bài học sắp theo thứ tự, mỗi bài có mục tiêu và bài tập riêng."),
                    ("Thực hành trên dự án thật", "Mỗi chương kết thúc bằng một sản phẩm bạn tự làm."),
                    ("Giảng viên chấm bài 1:1", "Nhận nhận xét chi tiết cho từng bài nộp trong 48 giờ."),
                    ("Học mọi lúc", "Xem lại bài giảng trên điện thoại hay máy tính, không giới hạn."),
                    ("Cộng đồng học viên", "Hỏi bài và chia sẻ dự án với các bạn cùng khóa."),
                    ("Chứng chỉ hoàn thành", "Nhận chứng chỉ sau khi nộp đủ bài tập của khóa.")],
    Domain.PORTFOLIO: [("Bắt đầu từ vấn đề", "Mỗi dự án mở đầu bằng câu hỏi khách hàng cần trả lời."),
                       ("Thử nhanh, sửa nhanh", "Bản mẫu được thử với người dùng thật trước khi hoàn thiện."),
                       ("Bàn giao trọn vẹn", "Tài liệu, mã nguồn và hướng dẫn được giao đầy đủ."),
                       ("Làm việc minh bạch", "Tiến độ cập nhật hằng tuần, có bảng theo dõi chung."),
                       ("Đo kết quả", "Mỗi dự án có chỉ số đo được trước và sau khi ra mắt."),
                       ("Đồng hành sau ra mắt", "Hỗ trợ điều chỉnh trong 30 ngày đầu.")],
}
STORY[Domain.OTHER] = STORY[Domain.ECOMMERCE]
# Feature cards for bento rows where the domain's "items" are not things to show as cards (plans, services).
FEATURES: dict[Domain, list[tuple[str, str]]] = {
    Domain.SAAS: [("Chu kỳ làm việc", "Chia việc theo chu kỳ hai tuần, tự chuyển việc dở sang chu kỳ sau."),
                  ("Lộ trình sản phẩm", "Kéo thả các mốc lớn, thấy ngay việc nào đang chặn việc nào."),
                  ("Phân quyền theo nhóm", "Mỗi nhóm thấy đúng dự án của mình; khách chỉ xem được phần được chia sẻ."),
                  ("Ứng dụng di động", "Duyệt việc và trả lời bình luận ngay trên điện thoại."),
                  ("Tìm kiếm tức thì", "Gõ vài chữ là ra việc, tài liệu hay người phụ trách."),
                  ("API mở", "Kết nối hệ thống nội bộ qua API và webhook có tài liệu đầy đủ.")],
    Domain.BOOKING: [("Chọn kỹ thuật viên", "Xem lịch trống của từng người và chọn người quen."),
                     ("Thanh toán trước", "Giữ chỗ bằng chuyển khoản hoặc ví điện tử."),
                     ("Thẻ thành viên", "Tích điểm sau mỗi lần đến, đổi lấy buổi miễn phí."),
                     ("Quà tặng", "Mua thẻ quà theo dịch vụ hoặc theo giá trị."),
                     ("Đánh giá sau buổi", "Góp ý trực tiếp cho từng kỹ thuật viên."),
                     ("Nhắc tái khám", "Lời nhắc theo liệu trình bạn đang theo.")],
    Domain.EDTECH: [("Video ngắn", "Mỗi bài dưới 15 phút, có phụ đề tiếng Việt."),
                    ("Bài tập tự chấm", "Chạy thử và nhận kết quả ngay trong trình duyệt."),
                    ("Lộ trình cá nhân", "Gợi ý bài tiếp theo theo điểm của bạn."),
                    ("Hỏi đáp trực tiếp", "Buổi hỏi đáp với giảng viên mỗi tuần."),
                    ("Tài liệu tải về", "Slide và mã nguồn của từng bài."),
                    ("Theo dõi tiến độ", "Biểu đồ số giờ học và bài đã hoàn thành.")],
}

QUOTE_NOTE = "Lời khách hàng mẫu — thay bằng đánh giá thật ở bước bàn giao"
QUOTES: dict[Domain, list[str]] = {
    Domain.ECOMMERCE: ["Hàng giao đúng hẹn, lắp đặt gọn gàng, dùng mấy tháng vẫn như mới.",
                       "Tư vấn kỹ, không ép mua, giá đúng như trên web."],
    Domain.SAAS: ["Nhóm mình bỏ được hai cuộc họp mỗi tuần vì tiến độ đã hiện sẵn.",
                  "Cài đặt trong một buổi chiều, cả nhóm dùng được ngay hôm sau."],
    Domain.BOOKING: ["Đặt lịch nhanh, đến nơi không phải chờ.", "Nhân viên nhẹ nhàng, phòng sạch, giá rõ ràng."],
    Domain.EDTECH: ["Bài tập sát thực tế, giảng viên chấm rất kỹ.", "Học xong mình làm được dự án đầu tiên cho công ty."],
    Domain.PORTFOLIO: ["Làm việc rõ ràng, đúng hạn, kết quả vượt mong đợi.", "Hiểu vấn đề nhanh và đề xuất đúng thứ chúng tôi cần."],
}
QUOTES[Domain.OTHER] = QUOTES[Domain.ECOMMERCE]

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
    hero = next(iter(by_kind("split-7-5", "full-bleed-image", "hero-text")), {})
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
        updates["cards"] = updates["items"]
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
    rows = [tuple(r) for v in by_kind("list-rows") for r in v.get("rows", []) if r and r[0]]
    if rows:
        updates["rows"] = rows[:10]
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
        shop=state.domain is Domain.ECOMMERCE,
        nav=d["nav"], nav_links=nav_links(state, d["nav"]), facts=d["facts"],
        story=STORY.get(state.domain or Domain.OTHER, STORY[Domain.ECOMMERCE]),
        quotes=[(q, QUOTE_NOTE) for q in QUOTES.get(state.domain or Domain.OTHER, QUOTES[Domain.ECOMMERCE])],
        cards=([Item(name=t, note=n) for t, n in FEATURES[state.domain]] if state.domain in FEATURES else d["items"]),
        items=d["items"], categories=d["categories"], faqs=d["faqs"],
        rows=sample_rows(STORY.get(state.domain or Domain.OTHER, STORY[Domain.ECOMMERCE])),
        closing=f"Sẵn sàng bắt đầu? {cta} chỉ mất một phút.",
        # The sample-content note lives in PRODUCT.md and the B12 handover, not on the page itself:
        # a disclaimer in the footer makes every page read as an unfinished mockup (design critic).
        footer_line=f"© {brand}. Bảo lưu mọi quyền.",
        tabs=[("Mô tả", "Thông tin tổng quan về sản phẩm và cách sử dụng."),
              ("Chất liệu", "Thành phần, nguồn gốc và cách bảo quản."),
              ("Giao hàng", "Thời gian giao, phí vận chuyển và chính sách đổi trả.")],
    )
    if state.brief:
        copy = apply_brief(copy, state.brief, state.pillars.scope or "")
    lang = page_lang(state)
    if lang != "vi":  # a Clone keeps its reference's language: sample copy in that language
        en = copy_en(state.domain, brand)
        copy = copy.model_copy(update={**en, "lang": lang, "nav_links": nav_links(state, en["nav"])})
    clone = state.clone
    if state.selected_page == "clone" and clone and clone.owned and clone.content:
        return owned_clone_copy(copy, clone.content)
    # No photos of their own: free-license stock photos picked by topic (§1.3, never grey boxes)
    if photos := stock_photos(f"{state.raw_prompt or ''} {brand} {state.pillars.scope or ''}", state.domain):
        copy = copy.model_copy(update={"images": photos})
    if state.page_copy and lang == "vi":  # written (in Vietnamese) by the LLM copywriter and validated there
        copy = apply_written_copy(copy, state.page_copy)
    if state.selected_page == "clone" and clone and not clone.owned:
        # Structure clone: the page is a template for the user's own words. The lines a visitor reads
        # first are clear placeholders (never the reference's text, never a name guessed from the prompt).
        copy = copy.model_copy(update=CLONE_PLACEHOLDERS if lang == "vi" else CLONE_PLACEHOLDERS_EN)
        copy = user_clone_content(copy, clone.user_texts, clone.user_images)
    return copy


def apply_brief(copy: PageCopy, brief: dict, scope: str) -> PageCopy:
    """What the user's brief states in their own words replaces the sample copy."""
    up: dict = {}
    if brief.get("brand"):
        up["brand"] = brief["brand"]
        up["footer_line"] = f"© {brief['brand']}. Bảo lưu mọi quyền."
    if brief.get("primary_cta") and not extract_cta(scope):
        up["cta"] = brief["primary_cta"]
    if brief.get("secondary_cta"):
        up["cta_secondary"] = brief["secondary_cta"]
    cats = [c for c in brief.get("categories") or [] if c.strip().lower() not in ("tất cả", "all")]
    items = list(copy.items)
    if brief.get("products"):
        items = [it.model_copy(update={"name": n}) for it, n in zip(items, brief["products"])] + items[len(brief["products"]):]
    if cats:
        up["categories"] = cats
        items = [it.model_copy(update={"category": cats[i % len(cats)]}) for i, it in enumerate(items)]
    up["items"] = items
    if copy.cards and [c.name for c in copy.cards] == [i.name for i in copy.items[:len(copy.cards)]]:
        up["cards"] = items[:len(copy.cards)]
    if brief.get("nav"):
        up["nav"] = brief["nav"]
        built = [link for link in copy.nav_links if link[1] != "#"]  # real pages first, then the user's menu
        up["nav_links"] = (built + [(label, "#") for label in brief["nav"]])[:5]
    if brief.get("usp"):
        up["usp"] = brief["usp"]
        up["announcement"] = " · ".join(brief["usp"][:2])
    if brief.get("quiz_options"):
        up["quiz_options"] = brief["quiz_options"]
    return copy.model_copy(update=up)


def apply_written_copy(copy: PageCopy, written: dict) -> PageCopy:
    """Overlay validated copywriter output on the rule-based copy (prices and facts stay the rules')."""
    updates: dict = {k: written[k] for k in ("eyebrow", "headline", "subhead", "closing", "announcement")
                     if written.get(k)}
    if written.get("brand"):
        updates["brand"] = written["brand"]
        updates["footer_line"] = f"© {written['brand']}. Bảo lưu mọi quyền."
    for pool in ("story", "faqs"):
        if written.get(pool):
            updates[pool] = [tuple(x) for x in written[pool]]
    if written.get("categories"):
        updates["categories"] = written["categories"]
    for pool in ("items", "cards"):
        if written.get(pool):
            base = getattr(copy, pool)
            updates[pool] = [b.model_copy(update={"name": n, "note": t}) for b, (n, t) in zip(base, written[pool])]
    return copy.model_copy(update=updates)


# Neutral meta for sample list rows (posts with dates): replaced by the real list at handover.
ROW_META = ["12 Th3", "28 Th2", "15 Th2", "02 Th2", "20 Th1", "08 Th1", "18 Th12", "05 Th12"]


def sample_rows(story: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(title, ROW_META[i % len(ROW_META)]) for i, (title, _) in enumerate(story)]


CLONE_PLACEHOLDERS = {
    "brand": "[Tên của bạn]",
    "headline": "[Câu tiêu đề: bạn làm gì, cho ai]",
    "subhead": "[Một hai câu giới thiệu ngắn về bạn hoặc sản phẩm của bạn]",
    "footer_line": "© [Tên của bạn]. Sửa nội dung trong thư mục content/.",
}


def user_clone_content(copy: PageCopy, texts: dict[str, str], images: list[str]) -> PageCopy:
    """Structure clone: the photos and words the user brought at B4 (by slot) replace placeholders and samples."""
    updates: dict = {}
    if images:
        updates["images"] = [f"/images/{name}" for name in images]
    if name := texts.get("name"):
        updates["brand"] = name[:60]
        updates["footer_line"] = f"© {name[:60]}"
    if headline := texts.get("headline"):
        updates["headline"] = headline
    if intro := texts.get("intro"):
        updates["subhead"] = intro
    projects = [p.strip() for p in re.split(r"[\n;]", texts.get("projects", "")) if p.strip()]
    if projects:
        cards = [it.model_copy(update={"name": title[:80]}) for it, title in zip(copy.cards or copy.items, projects)]
        cards += [Item(name=title[:80], note="") for title in projects[len(cards):]]
        updates["cards"] = cards[:8]
        updates["items"] = cards[:8]
        story = list(copy.story)
        updates["story"] = [(title, story[i][1] if i < len(story) else "") for i, title in enumerate(projects[:6])]
    return copy.model_copy(update=updates) if updates else copy


def _rot(xs: list, k: int) -> list:
    return xs[k % len(xs):] + xs[:k % len(xs)] if xs else xs


# How much of each copy pool a section structure shows (so the next section continues after it).
USES = {
    "story": {"alternating-z": 3, "split-5-7": 1, "feature-showcase": 1, "text-cards": 3, "gallery": 1},
    "items": {"grid-4": 8, "sidebar-grid-4": 8},
    "cards": {"bento": 4},
    "quotes": {"testimonials": 2},
    "categories": {"horizontal-scroller": 4},
    "faqs": {"accordion": 5},
    "tabs": {"tabs": 3},
    "rows": {"list-rows": 6},
}


def copy_for(structure: str, earlier: list[str], copy: PageCopy) -> PageCopy:
    """Copy for one section: each pool continues where the earlier sections of the page stopped,
    so two sections never show the same sample text until the pool runs out."""
    updates = {}
    for pool, uses in USES.items():
        if structure not in uses:
            continue
        offset = sum(uses.get(prev, 0) for prev in earlier)
        values = getattr(copy, pool)
        if offset and values:
            # When the pool is smaller than what the page shows, shift by one more each full pass,
            # so a repeated section at least shows a different order instead of an identical copy.
            updates[pool] = _rot(values, offset + offset // len(values))
    return copy.model_copy(update=updates) if updates else copy
