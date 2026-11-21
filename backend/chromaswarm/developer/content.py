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
from chromaswarm.developer.industry import pack_for as industry_pack
from chromaswarm.developer.order import OrderSpec, order_spec
from chromaswarm.developer.photo_bot import credit_line
from chromaswarm.developer.photos import stock_photos
from chromaswarm.developer.real_content import RealContent
from chromaswarm.developer.uploads import own_files, public_path, shared_photos
from chromaswarm.state_machine.pipeline_state import Domain, PipelineState


class Item(BaseModel):
    name: str
    note: str
    price: str = ""
    tag: str = ""
    category: str = ""  # for the category tabs of a product grid
    image: str = ""  # the user's own photo of this item ("/images/…"); the shared photo list otherwise


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
    product_ui: bool = False  # software without a real screenshot: the hero shows the product's interface
    # Decorative app window of a software page (app_pages.preview_props): the product's own records,
    # written by the copywriter for this product; empty = the team-board samples.
    preview_nav: list[str] = []
    preview_figures: list[tuple[str, str]] = []
    preview_rows: list[tuple[str, str, str]] = []
    logo: str = ""  # the user's uploaded logo, served from the app ("/images/logo-….png"); the brand name otherwise
    contact: str = ""  # the owner's contact line (B4): address, hours, phone — shown on the contact page
    routes: dict[str, str] = {}  # built pages, sitemap slug -> route (content/routes.ts)
    more_href: str = "#details"  # the secondary CTA ("Xem chi tiết"): the story rows, else the part after the hero
    learn_href: str = ""  # the feature showcase's "Tìm hiểu thêm": the page's FAQ, else no link
    footer_links: list[tuple[str, str]] = []  # shop footer help links that lead somewhere (content.footer_links)
    order: OrderSpec | None = None  # the form the main button opens (developer/order.py)
    taken: list[str] = []  # Clone measured sections: lines earlier sections of the page already show


DEFAULTS: dict[Domain, dict] = {
    Domain.ECOMMERCE: dict(  # neutral: nothing that belongs to one kind of shop (developer/industry.py has those)
        nav=["Sản phẩm", "Cách đặt hàng", "Hỏi đáp", "Liên hệ"],
        facts=[("2–4 ngày", "giao toàn quốc"), ("Kiểm hàng", "trước khi trả tiền"), ("7 ngày", "đổi nếu lỗi từ cửa hàng"),
               ("Tư vấn", "qua tin nhắn trước khi mua")],
        items=[Item(name="Mẫu bán chạy", note="Được đặt nhiều nhất tháng này", price="390.000₫", tag="Bán chạy"),
               Item(name="Mẫu mới về", note="Số lượng ít", price="450.000₫"),
               Item(name="Combo hai món", note="Rẻ hơn mua lẻ", price="690.000₫"),
               Item(name="Quà tặng", note="Gói sẵn, kèm thiệp", price="250.000₫")],
        categories=["Bán chạy", "Mới về", "Combo", "Quà tặng"],
        faqs=[("Bao lâu thì nhận được hàng?", "Nội thành 1–2 ngày, tỉnh khác 2–4 ngày làm việc."),
              ("Có được kiểm hàng không?", "Có, bạn mở gói kiểm hàng trước khi trả tiền."),
              ("Hàng lỗi thì sao?", "Cửa hàng đổi trong 7 ngày nếu lỗi từ phía cửa hàng."),
              ("Thanh toán bằng cách nào?", "Chuyển khoản, ví điện tử hoặc thanh toán khi nhận hàng."),
              ("Mua số lượng nhiều có giá riêng không?", "Có, nhắn cửa hàng để nhận báo giá.")],
    ),
    Domain.SAAS: dict(
        nav=["Tính năng", "Bảng giá", "Khách hàng", "Tài liệu"],
        facts=[("14 ngày", "dùng thử, không cần thẻ"), ("5 phút", "để bắt đầu"), ("24/7", "hỗ trợ"), ("ISO 27001", "bảo mật dữ liệu")],
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
        facts=[("8:00–21:00", "mỗi ngày"), ("15 phút", "xác nhận lịch"), ("Giá", "ghi rõ từng dịch vụ"), ("Miễn phí", "đổi lịch trước 2 giờ")],
        items=[Item(name="Dịch vụ tiêu chuẩn", note="60 phút", price="350.000₫"),
               Item(name="Dịch vụ nâng cao", note="90 phút", price="550.000₫", tag="Được chọn nhiều"),
               Item(name="Gói thành viên", note="5 lần, dùng trong 3 tháng", price="1.500.000₫")],
        categories=["Dịch vụ", "Gói", "Thành viên", "Quà tặng"],
        faqs=[("Tôi có cần đặt trước không?", "Nên đặt trước để giữ khung giờ, nhận khách vãng lai khi còn chỗ."),
              ("Đổi lịch thế nào?", "Đổi miễn phí trước 2 giờ qua link trong tin nhắn xác nhận."),
              ("Có chỗ đỗ xe không?", "Có chỗ đỗ xe máy và ô tô ngay trước cửa."),
              ("Thanh toán ra sao?", "Thanh toán tại quầy bằng tiền mặt, thẻ hoặc chuyển khoản."),
              ("Có thẻ quà tặng không?", "Có thẻ quà tặng theo giá trị hoặc theo dịch vụ.")],
    ),
    Domain.EDTECH: dict(
        nav=["Khóa học", "Lộ trình", "Giảng viên", "Hỏi đáp"],
        facts=[("12 tuần", "lộ trình"), ("Bài tập", "sau mỗi buổi"), ("1:1", "chấm bài"), ("Trọn đời", "xem lại bài giảng")],
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
    facts=[("4–8 tuần", "một dự án"), ("Hằng tuần", "cập nhật tiến độ"), ("Từ xa", "hoặc tại chỗ"), ("30 ngày", "hỗ trợ sau ra mắt")],
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
    Domain.ECOMMERCE: [("Ảnh chụp hàng thật", "Mỗi sản phẩm có ảnh chụp thật, không dùng ảnh mạng."),
                       ("Giá ghi rõ từ đầu", "Giá và phí giao hiện trước khi đặt, không phát sinh khi nhận hàng."),
                       ("Đóng gói cẩn thận", "Hàng được chèn kỹ để đến tay bạn như lúc rời cửa hàng."),
                       ("Hỏi trước khi mua", "Nhắn tin để được tư vấn, trả lời trong giờ làm việc."),
                       ("Kiểm hàng khi nhận", "Mở gói xem hàng trước khi trả tiền."),
                       ("Đổi nếu lỗi", "Hàng lỗi từ cửa hàng được đổi trong 7 ngày.")],
    Domain.SAAS: [("Lên kế hoạch trong vài phút", "Tạo dự án, chia việc và đặt hạn cho cả nhóm từ một màn hình."),
                  ("Mọi việc ở cùng một chỗ", "Yêu cầu, lỗi và ý tưởng đổ về một hàng đợi; không còn tìm trong chat."),
                  ("Theo dõi tiến độ không cần họp", "Bảng tiến độ tự cập nhật khi từng việc chuyển trạng thái."),
                  ("Tự động hóa việc lặp lại", "Quy tắc tự gán người, đổi trạng thái và nhắc hạn thay cho thao tác tay."),
                  ("Kết nối công cụ đang dùng", "Đồng bộ với lịch, email và kho mã nguồn qua tích hợp có sẵn."),
                  ("Báo cáo cho quản lý", "Số liệu tuần được tổng hợp sẵn, xuất ra bảng tính bằng một nút.")],
    Domain.BOOKING: [("Đặt lịch trong 30 giây", "Chọn dịch vụ, chọn giờ trống và xác nhận, không cần gọi điện."),
                     ("Nhắc lịch tự động", "Tin nhắn nhắc trước một ngày và trước hai giờ để không lỡ hẹn."),
                     ("Người phục vụ có kinh nghiệm", "Mỗi người phụ trách đều được đào tạo trước khi nhận khách."),
                     ("Sạch sẽ sau mỗi lượt", "Chỗ ngồi và dụng cụ được vệ sinh sau mỗi lượt khách."),
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
    Domain.BOOKING: [("Chọn người phục vụ", "Xem lịch trống của từng người và chọn người quen."),
                     ("Thanh toán trước", "Giữ chỗ bằng chuyển khoản hoặc ví điện tử."),
                     ("Thẻ thành viên", "Tích điểm sau mỗi lần đến, đổi lấy buổi miễn phí."),
                     ("Quà tặng", "Mua thẻ quà theo dịch vụ hoặc theo giá trị."),
                     ("Đánh giá sau buổi", "Góp ý trực tiếp sau mỗi lần đến."),
                     ("Nhắc lịch định kỳ", "Lời nhắc khi đến hạn quay lại.")],
    Domain.EDTECH: [("Video ngắn", "Mỗi bài dưới 15 phút, có phụ đề tiếng Việt."),
                    ("Bài tập tự chấm", "Chạy thử và nhận kết quả ngay trong trình duyệt."),
                    ("Lộ trình cá nhân", "Gợi ý bài tiếp theo theo điểm của bạn."),
                    ("Hỏi đáp trực tiếp", "Buổi hỏi đáp với giảng viên mỗi tuần."),
                    ("Tài liệu tải về", "Slide và mã nguồn của từng bài."),
                    ("Theo dõi tiến độ", "Biểu đồ số giờ học và bài đã hoàn thành.")],
}

QUOTE_NOTE = "Lời khách hàng mẫu — thay bằng đánh giá thật ở bước bàn giao"
QUOTES: dict[Domain, list[str]] = {
    Domain.ECOMMERCE: ["Hàng giống ảnh, đóng gói cẩn thận, giao đúng hẹn.",
                       "Tư vấn kỹ, không ép mua, giá đúng như trên web."],
    Domain.SAAS: ["Nhóm mình bỏ được hai cuộc họp mỗi tuần vì tiến độ đã hiện sẵn.",
                  "Cài đặt trong một buổi chiều, cả nhóm dùng được ngay hôm sau."],
    Domain.BOOKING: ["Đặt lịch nhanh, đến nơi không phải chờ.", "Nhân viên nhẹ nhàng, sạch sẽ, giá rõ ràng."],
    Domain.EDTECH: ["Bài tập sát thực tế, giảng viên chấm rất kỹ.", "Học xong mình làm được dự án đầu tiên cho công ty."],
    Domain.PORTFOLIO: ["Làm việc rõ ràng, đúng hạn, bàn giao đủ tài liệu.", "Hiểu vấn đề nhanh và đề xuất đúng thứ chúng tôi cần."],
}
QUOTES[Domain.OTHER] = QUOTES[Domain.ECOMMERCE]

# Sample hero / closing lines per domain: plain statements, no formula (qa/ai_tells.py checks them).
HEADLINE: dict[Domain, str] = {
    Domain.ECOMMERCE: "Hàng thật, giá rõ, giao tận nơi", Domain.SAAS: "Cả nhóm thấy cùng một tiến độ",
    Domain.BOOKING: "Chọn giờ trống, đến là được phục vụ", Domain.EDTECH: "Học có lộ trình, có người chấm bài",
    Domain.PORTFOLIO: "Website và sản phẩm số, từ buổi trao đổi đầu tiên đến ngày ra mắt",
}
SUBHEAD: dict[Domain, str] = {
    Domain.ECOMMERCE: "xem ảnh thật, giá và phí giao trước khi đặt.",
    Domain.SAAS: "việc, hạn và người phụ trách nằm trên một bảng, tự cập nhật khi việc đổi trạng thái.",
    Domain.BOOKING: "xem giờ còn trống và đặt ngay, không cần gọi điện.",
    Domain.EDTECH: "mỗi buổi có bài giảng, bài tập và nhận xét của giảng viên.",
    Domain.PORTFOLIO: "thiết kế và làm cho nhóm nhỏ, cập nhật hằng tuần và bàn giao đầy đủ.",
}
CLOSING: dict[Domain, str] = {
    Domain.ECOMMERCE: "Chưa biết chọn món nào? Nhắn cửa hàng, có người tư vấn trong giờ làm việc.",
    Domain.SAAS: "Dùng thử 14 ngày với việc thật của nhóm bạn, không cần thẻ.",
    Domain.BOOKING: "Tuần này vẫn còn giờ trống, đặt trước để giữ chỗ.",
    Domain.EDTECH: "Học thử bài đầu tiên trước khi đăng ký.",
    Domain.PORTFOLIO: "Đang nhận dự án mới, gửi vài dòng về việc bạn cần làm.",
}
for _pool in (HEADLINE, SUBHEAD, CLOSING):
    _pool[Domain.OTHER] = _pool[Domain.ECOMMERCE]

_SLOGAN = re.compile(r"^\s*(?:slogan|thông điệp|tagline)\s*[:\-]\s*(.+)$", re.I)


NAMED = re.compile(r"(?:tên|thương hiệu|brand)\s+[“\"']?([A-ZÀ-Ỹ][\wÀ-ỹ&'-]{1,24}(?:\s[A-ZÀ-Ỹ][\wÀ-ỹ&'-]{1,24})?)")
CAMEL = re.compile(r"\b([A-Z][a-z]+[A-Z][A-Za-z]+|[A-Z]{2,}[a-z][A-Za-z]*)\b")


def named_brand(prompt: str) -> str | None:
    """A brand the prompt names ("tên Mộc Trà", "StockPilot") — never the whole sentence as a name."""
    if m := NAMED.search(prompt or ""):
        return m.group(1)
    if m := CAMEL.search(prompt or ""):
        return m.group(1)
    return None


def _brand(title: str) -> str:
    """'Web bán đồ nội thất gỗ sồi tối giản' -> 'Nội thất gỗ sồi tối giản'."""
    t = re.sub(r"^(?:web|website|trang web|trang)\s+(?:bán|cho|về|của)?\s*(?:đồ|các)?\s*", "", title, flags=re.I).strip()
    t = t or title
    return t[:1].upper() + t[1:]


# Short menu label of each sitemap page (the sitemap titles are long English names: "Product Detail Page").
PAGE_LABELS: dict[str, tuple[str, str]] = {
    "home": ("Trang chủ", "Home"), "landing": ("Trang chủ", "Home"), "catalog": ("Sản phẩm", "Shop"),
    "pdp": ("Chi tiết sản phẩm", "Product"), "cart": ("Giỏ hàng", "Cart"), "account": ("Tài khoản", "Account"),
    "login": ("Đăng nhập", "Log in"), "dashboard": ("Bảng điều khiển", "Dashboard"), "workspace": ("Làm việc", "Workspace"),
    "settings": ("Cài đặt", "Settings"), "services": ("Dịch vụ", "Services"), "booking": ("Đặt lịch", "Book"),
    "my-bookings": ("Lịch của tôi", "My bookings"), "contact": ("Liên hệ", "Contact"), "directory": ("Khóa học", "Courses"),
    "learn": ("Phòng học", "Learn"), "student": ("Học viên", "Students"), "projects": ("Dự án", "Projects"),
    "project": ("Dự án", "Project"),
}
# Reached another way, never from the menu: the cart and account icons, a product / project card.
OFF_MENU = {"cart", "pdp", "project", "account"}
ORDER_ANCHOR = "#dat-hang"  # any link to it opens the order form (components/OrderDialog.tsx)

# A menu word -> what it points at on the home page: section structures, "order" (the order form) or
# "contact" (the contact page, else the footer that carries the owner's contact line). First match wins.
_ANCHORS: list[tuple[re.Pattern, tuple[str, ...]]] = [(re.compile(p, re.I), kinds) for p, kinds in [
    (r"liên hệ|contact|địa chỉ|tìm (đường|tiệm)", ("contact",)),
    (r"hỏi|faq|question", ("accordion",)),
    (r"kiểm tra|trắc nghiệm|quiz|tìm .*hợp|chọn .*hợp|loại da|skin type", ("picker-recommend",)),
    (r"đánh giá|khách (hàng )?nói|cảm nhận|review|testimonial", ("testimonials",)),
    (r"giá|gói|pricing|plan", ("price-list", "plan-cards")),
    (r"câu chuyện|về (chúng|tiệm|mình|nhà)|giới thiệu|about|story|cách dùng|quy trình|how it works|tính năng|feature",
     ("alternating-z", "feature-showcase", "split-5-7")),
    (r"menu|thực đơn|sản phẩm|bộ sưu tập|mới về|bán chạy|món|dịch vụ|cửa hàng|danh mục|bảng size|shop|product|collection|"
     r"service|khóa học|course|dự án|project|work",
     ("grid-4", "bento", "sidebar-grid-4", "horizontal-scroller", "price-list", "picker-recommend")),
    (r"đặt|order|book|mua|đăng ký|sign ?up|dùng thử|try", ("order",)),
]]


def nav_links(state: PipelineState, labels: list[str]) -> list[tuple[str, str]]:
    """Menu links that all lead somewhere: the built pages (short labels in the page's language), then the
    menu words matched to a part of the home page ("/#faq"), the order form or the contact page. A word
    nothing on the site answers is left out — never a "#" link. Hrefs are absolute ("/#faq") because the
    header is shared by every page."""
    en = page_lang(state) != "vi"
    routes = {slug: route for slug, route in state.page_routes.items()}
    labels_of = dict(PAGE_LABELS)
    if state.domain is Domain.ECOMMERCE:  # a storefront besides the landing page is "the shop", not "home"
        labels_of["home"] = ("Cửa hàng", "Shop")
    else:
        labels_of["home"] = ("Giới thiệu", "About")
    built = [((labels_of.get(slug) or (slug, slug))[en], route) for slug, route in routes.items()
             if route != "/" and slug not in OFF_MENU]
    by_kind = _home_parts(state)
    out = list(built)
    for label in labels:
        if any(_same(label, b) for b, _ in out):
            continue
        href = _anchor(label, by_kind, routes)
        if href:
            out.append((label, href))
    return out[:5]


def _home_parts(state: PipelineState) -> dict[str, str]:
    """Section structure -> section id on the home page ("/"), which every page's shared header links into."""
    home = next((slug for slug, route in state.page_routes.items() if route == "/"), state.selected_page)
    try:
        from chromaswarm.agents.planner import page_sections  # local: the planner reads this module's neighbours
        sections = page_sections(state.model_copy(update={"selected_page": home}))
    except Exception:
        return {}
    by_kind: dict[str, str] = {}
    for s in sections:
        by_kind.setdefault(s.structure, s.id)
    return by_kind


def footer_links(state: PipelineState, cta: str, en: bool) -> list[tuple[str, str]]:
    """The shop footer's help links that lead somewhere: FAQ, the order form, the contact page. Policy pages
    (shipping, returns, privacy, terms) are not built yet, so they are not listed."""
    by_kind, routes = _home_parts(state), state.page_routes
    links = [("FAQ" if en else "Câu hỏi thường gặp", f"/#{by_kind['accordion']}" if "accordion" in by_kind else ""),
             (cta, ORDER_ANCHOR), ("Contact" if en else "Liên hệ", routes.get("contact", ""))]
    return [(label, href) for label, href in links if href]


def _same(a: str, b: str) -> bool:
    return a.strip().lower() == b.strip().lower()


def _anchor(label: str, by_kind: dict[str, str], routes: dict[str, str]) -> str:
    for pattern, kinds in _ANCHORS:
        if not pattern.search(label):
            continue
        for kind in kinds:
            if kind == "order":
                return ORDER_ANCHOR
            if kind == "contact":
                return routes.get("contact") or ("/#site-footer" if "footer-columns" in by_kind else "")
            if kind in by_kind:
                return f"/#{by_kind[kind]}"
        return ""  # the word is clear but the site has no such part
    # Any other word the owner put in the menu is most often a group of what they sell ("Dưỡng da").
    listing = next((by_kind[k] for k in _LISTINGS if k in by_kind), "")
    return f"/#{listing}" if listing else ""


_LISTINGS = ("grid-4", "bento", "sidebar-grid-4", "price-list", "horizontal-scroller")


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
        # entries with no address on this site are left out (QA dead-link), never "#"
        updates["nav_links"] = [(label, href) for label, href in nav if href.startswith(("/", "http")) or len(href) > 1 and href.startswith("#")][:5]
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
    copy = _build_copy(state)
    real = state.real_content or {}
    # The main button opens a real order / booking / contact form, built from the page's own list
    # and the contact line the owner typed (its phone / Zalo / email become the fallback channels).
    spec = order_spec(state.domain, copy.brand, copy.cta, copy.items, str(real.get("contact") or ""),
                      industry_pack(state), copy.lang)
    # A cart only once the cart page exists (developer/cart.py); content/order.ts is rewritten on every page build.
    if copy.shop and (route := state.page_routes.get("cart")):
        spec = spec.model_copy(update={"cart": route})
    extra = {"footer_links": footer_links(state, copy.cta, copy.lang != "vi")} if copy.shop else {}
    return copy.model_copy(update={"order": spec, "routes": dict(state.page_routes), **_in_page_links(state), **extra})


def _in_page_links(state: PipelineState) -> dict:
    """Targets of the in-page links, from the sections this page is built with (each section root has id=<its id>)."""
    try:
        from chromaswarm.agents.planner import page_sections  # local: keeps this module free of the planner at import
        sections = page_sections(state)
    except Exception:
        return {}
    ids = [s.id for s in sections if s.structure not in ("sticky-bar", "announcement-bar", "footer-columns")]
    if not ids:
        return {}
    hero = next((n for n, sid in enumerate(ids) if "hero" in sid), -1)
    after = ids[hero + 1] if hero + 1 < len(ids) else ids[-1]
    more = "#details" if any(s.structure == "alternating-z" for s in sections) else f"#{after}"
    faq = next((s.id for s in sections if s.structure == "accordion"), "")
    return {"more_href": more, "learn_href": f"#{faq}" if faq else ""}


def _build_copy(state: PipelineState) -> PageCopy:
    dom = state.domain or Domain.OTHER
    d = DEFAULTS.get(dom, DEFAULTS[Domain.ECOMMERCE])
    # What the business sells (bakery, nail salon…) picks the samples within the domain (developer/industry.py)
    pk = industry_pack(state) or {}
    title = project_title(state.raw_prompt or "Dự án", limit=40).rstrip("…")
    brand = named_brand(state.raw_prompt or "") or _brand(title)
    cta = extract_cta(state.pillars.scope or "") or "Liên hệ ngay"
    cta = cta[:1].upper() + cta[1:]
    slogan = next((m.group(1).strip() for a in state.assets if (m := _SLOGAN.match(a.path_or_text))), None)
    headline = slogan or pk.get("headline") or HEADLINE[dom]
    # The hero speaks to the customer: never the owner's description of them ("Dành cho mấy mẹ bỉm sữa…")
    sub = pk.get("subhead") or SUBHEAD[dom]
    story = pk.get("story") or STORY.get(dom, STORY[Domain.ECOMMERCE])
    items = [Item(name=n, note=note, price=price, tag=tag) for n, note, price, tag in pk["items"]] if "items" in pk else d["items"]
    features = pk.get("features") or FEATURES.get(dom)
    nav = pk.get("nav") or d["nav"]
    copy = PageCopy(
        brand=brand, headline=headline, subhead=sub[:1].upper() + sub[1:], cta=cta, cta_secondary="Xem chi tiết",
        shop=state.domain is Domain.ECOMMERCE,
        nav=nav, nav_links=nav_links(state, nav), facts=pk.get("facts") or d["facts"],
        story=story,
        quotes=[(q, QUOTE_NOTE) for q in pk.get("quotes") or QUOTES.get(dom, QUOTES[Domain.ECOMMERCE])],
        cards=([Item(name=t, note=n) for t, n in features] if features and dom is not Domain.ECOMMERCE else items),
        items=items, categories=pk.get("categories") or d["categories"], faqs=pk.get("faqs") or d["faqs"],
        rows=sample_rows(story),
        closing=pk.get("closing") or CLOSING[dom],
        # The sample-content note lives in PRODUCT.md and the B12 handover, not on the page itself:
        # a disclaimer in the footer makes every page read as an unfinished mockup (design critic).
        footer_line=f"© {brand}. Bảo lưu mọi quyền.",
        tabs=pk.get("tabs") or [("Mô tả", "Thông tin tổng quan về sản phẩm và cách sử dụng."),
                                ("Thông tin", "Thành phần, kích cỡ và cách bảo quản."),
                                ("Giao hàng", "Thời gian giao, phí vận chuyển và đổi hàng.")],
    )
    if state.brief:
        copy = apply_brief(copy, state.brief, state.pillars.scope or "", state)
    real = RealContent.model_validate(state.real_content) if state.real_content else None
    if real and state.selected_page != "clone":
        copy = apply_real(copy, real)
    lang = page_lang(state)
    if lang != "vi":  # a Clone keeps its reference's language: sample copy in that language
        en = copy_en(state.domain, brand)
        copy = copy.model_copy(update={**en, "lang": lang, "nav_links": nav_links(state, en["nav"])})
    clone = state.clone
    if state.selected_page == "clone" and clone and clone.owned and clone.content:
        return owned_clone_copy(copy, clone.content)
    # A Clone never adds pictures the reference did not have: its picture slots stay exact-size skeletons
    # (the Art placeholder) until the user brings their own (B4 uploads).
    is_clone = state.selected_page == "clone" and clone is not None
    own = [public_path(f) for f in shared_photos(state)]
    if state.domain is Domain.SAAS and not own_files(state, "product-image") and state.selected_page != "clone":
        copy = copy.model_copy(update={"product_ui": True})
    if logos := own_files(state, "logo"):
        copy = copy.model_copy(update={"logo": public_path(logos[0])})
    # The user's own photos first (B4 upload); none: photos found by the bot, then curated stock (§1.3)
    if own:
        copy = copy.model_copy(update={"images": own})
    elif state.page_photos:  # found and checked by eye by the photo bot for this brief
        credit = credit_line(state.page_photos)
        copy = copy.model_copy(update={"images": [public_path(x["url"]) if x["url"].startswith("uploads/") else x["url"]
                                                  for x in state.page_photos],
                                       "footer_line": f"{copy.footer_line} {credit}".strip() if credit else copy.footer_line})
    elif not is_clone and (photos := stock_photos(f"{state.raw_prompt or ''} {brand} {state.pillars.scope or ''}", state.domain)):
        copy = copy.model_copy(update={"images": photos})
    if state.page_copy and lang == "vi":  # written (in Vietnamese) by the LLM copywriter and validated there
        copy = apply_written_copy(copy, state.page_copy)
        if real and state.selected_page != "clone":  # the user's own list, numbers and words always win
            copy = apply_real(copy, real, written=True)
    if state.selected_page == "clone" and clone and not clone.owned:
        # Structure clone: the page is a template for the user's own words. The lines a visitor reads
        # first are clear placeholders (never the reference's text, never a name guessed from the prompt).
        copy = copy.model_copy(update=CLONE_PLACEHOLDERS if lang == "vi" else CLONE_PLACEHOLDERS_EN)
        copy = user_clone_content(copy, clone.user_texts, clone.user_images)
    return copy


def guess_category(name: str, categories: list[str]) -> str:
    """The category an item's own name says it is in ("Bánh kem bắp" -> "Bánh kem"); "" when it does not say.
    Never a category handed out in turn: a filter would then show a croissant under "Bánh kem"."""
    low = name.lower()
    hits = [c for c in categories if c and c.lower() in low]
    return max(hits, key=len) if hits else ""


def apply_real(copy: PageCopy, real: RealContent, written: bool = False) -> PageCopy:
    """The business's real content (B4 form) in place of the samples; empty fields keep the samples.

    `written`: applied again over the copywriter's text, which was given the same facts — only what
    must stay exactly as the user typed it (their list, numbers, customers' words, answers, contact)."""
    up: dict = {}
    if real.items:
        items = [Item(name=i.name, price=i.price, note=i.note, image=public_path(i.image) if i.image else "",
                      category=guess_category(i.name, copy.categories))
                 for i in real.items]
        if copy.items and copy.items[0].tag:
            items[0] = items[0].model_copy(update={"tag": copy.items[0].tag})
        up["items"] = items
        if copy.cards and [c.name for c in copy.cards] == [i.name for i in copy.items[:len(copy.cards)]]:
            up["cards"] = items[:max(len(copy.cards), 3)]  # a shop's bento shows its products
    if len(real.numbers) >= 2:
        up["facts"] = real.numbers
    elif real.numbers:
        up["facts"] = real.numbers + copy.facts[:3]
    if real.reviews:
        up["quotes"] = [(q, who or "Khách hàng") for q, who in real.reviews]
    if real.faqs:
        extra = [f for f in copy.faqs if f[0] not in {q for q, _ in real.faqs}]
        up["faqs"] = (real.faqs + extra)[:max(len(real.faqs), 4)]
    if real.contact:
        up["footer_line"] = f"{real.contact} · © {copy.brand}"
        up["contact"] = real.contact
    if not written:
        if real.offer:
            up["subhead"] = real.offer[:1].upper() + real.offer[1:]
        if real.different:
            up["story"] = [(t, b) for t, b in real.different]
            up["usp"] = [t for t, _ in real.different][:4]
    return copy.model_copy(update=up)


def apply_brief(copy: PageCopy, brief: dict, scope: str, state: PipelineState | None = None) -> PageCopy:
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
        if state is not None:  # real pages first, then the user's menu words that lead somewhere
            up["nav_links"] = nav_links(state, brief["nav"])
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
    if pv := written.get("preview"):
        updates.update(preview_nav=pv["nav"], preview_figures=[tuple(x) for x in pv["figures"]],
                       preview_rows=[tuple(x) for x in pv["rows"]])
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
