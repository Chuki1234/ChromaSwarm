"""Page language. A Clone keeps the reference page's language: its sample copy, buttons, menus and form
messages are written in that language (English for any language without its own copy set). Creative
pages are Vietnamese. Notes for the user (HUONG_DAN.md, content-file comments) stay Vietnamese.
"""

from __future__ import annotations

import re

from chromaswarm.state_machine.pipeline_state import Domain

SUPPORTED = ("vi", "en")


def normalise(lang: str | None) -> str:
    """'en-US' -> 'en'; a language without its own copy set is built in English."""
    code = (lang or "").strip().lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED else ("en" if code else "vi")


def page_lang(state) -> str:
    clone = getattr(state, "clone", None)
    if getattr(state, "selected_page", None) == "clone" and clone and getattr(clone, "lang", None):
        return normalise(clone.lang)
    return "vi"


# ------------------------------------------------------------------ English sample copy

def _items(*rows):
    from chromaswarm.developer.content import Item  # local: content imports this module
    return [Item(name=n, note=note, price=price, tag=tag) for n, note, price, tag in rows]


def defaults_en(domain: Domain | None) -> dict:
    d = domain or Domain.OTHER
    table = {
        Domain.ECOMMERCE: dict(
            nav=["Collection", "Our story", "FAQ", "Contact"],
            facts=[("48h", "city delivery"), ("30 days", "free returns"), ("2 years", "warranty"), ("100%", "checked before shipping")],
            items=[("Signature piece", "Our best seller", "$249", "New"), ("Compact edition", "For smaller spaces", "$169", ""),
                   ("Value bundle", "10% off together", "$399", ""), ("Accessory", "Completes the set", "$39", "")],
            categories=["Living room", "Bedroom", "Workspace", "Accessories"],
            faqs=[("How fast is delivery?", "Within 48 hours in the city, 3–5 business days elsewhere."),
                  ("Can I return it?", "Free returns within 30 days if the product is undamaged."),
                  ("Do you install it?", "Yes, our team installs it on delivery at no extra cost."),
                  ("How can I pay?", "Card, bank transfer or cash on delivery."),
                  ("What does the warranty cover?", "Two years for manufacturing defects.")]),
        Domain.SAAS: dict(
            nav=["Features", "Pricing", "Customers", "Docs"],
            facts=[("99.9%", "uptime"), ("5 min", "to get started"), ("24/7", "support"), ("ISO 27001", "data security")],
            items=[("Starter", "Up to 5 people", "$0", ""), ("Team", "Unlimited projects", "$19/mo", "Popular"),
                   ("Enterprise", "SSO, roles, SLA", "Contact us", "")],
            categories=["Planning", "Reporting", "Automation", "Integrations"],
            faqs=[("Is there a free trial?", "Yes, 14 days with every feature, no card needed."),
                  ("Where is my data stored?", "On encrypted servers with daily backups."),
                  ("Can I cancel anytime?", "Yes, from settings, with no extra fees."),
                  ("Do you send invoices?", "Yes, an invoice is emailed every billing period."),
                  ("How do integrations work?", "Through our API and ready-made connectors.")]),
        Domain.BOOKING: dict(
            nav=["Services", "Pricing", "Book", "Contact"],
            facts=[("8am–9pm", "every day"), ("15 min", "booking confirmation"), ("4.9/5", "rating"), ("Free", "rescheduling 2h ahead")],
            items=[("Standard session", "60 minutes", "$35", ""), ("Signature session", "90 minutes", "$55", "Most booked"),
                   ("Membership", "5 visits within 3 months", "$150", "")],
            categories=["Care", "Relax", "Membership", "Gifts"],
            faqs=[("Do I need to book ahead?", "Booking keeps your slot; walk-ins are welcome when there is room."),
                  ("How do I reschedule?", "Free up to 2 hours before, from the link in your confirmation."),
                  ("Is there parking?", "Yes, right in front of the entrance."),
                  ("How do I pay?", "Cash, card or transfer at the front desk."),
                  ("Do you sell gift cards?", "Yes, by amount or by service.")]),
        Domain.EDTECH: dict(
            nav=["Courses", "Curriculum", "Mentors", "FAQ"],
            facts=[("12 weeks", "curriculum"), ("40+", "hands-on exercises"), ("1:1", "reviews"), ("Lifetime", "access")],
            items=[("Foundations", "For beginners", "$199", ""), ("Advanced", "Real projects", "$349", "Recommended"),
                   ("1:1 mentoring", "8 sessions with a mentor", "$590", "")],
            categories=["Basics", "Advanced", "Projects", "Exam prep"],
            faqs=[("Can I start from zero?", "Yes, Foundations starts from the very beginning."),
                  ("Which devices work?", "Laptop, phone or tablet."),
                  ("Is there a certificate?", "Yes, once every assignment is submitted."),
                  ("Can I get a refund?", "Full refund within the first 7 days."),
                  ("Where do I ask questions?", "In the student group and the weekly live Q&A.")]),
        Domain.PORTFOLIO: dict(
            nav=["Work", "About", "Experience", "Contact"],
            facts=[("8 years", "experience"), ("40+", "projects"), ("12", "returning clients"), ("3", "awards")],
            items=[("Featured project", "Design & build", "", ""), ("Second project", "User research", "", ""),
                   ("Third project", "Brand identity", "", "")],
            categories=["Design", "Development", "Research", "Writing"],
            faqs=[("What kind of projects do you take?", "Websites, digital products and brand systems."),
                  ("How long does a project take?", "Usually 4–8 weeks depending on scope."),
                  ("Do you work remotely?", "Yes, with a weekly video call."),
                  ("How do you price?", "By scope, after a first conversation."),
                  ("Do you offer support after launch?", "Yes, a monthly maintenance plan.")]),
    }
    out: dict = dict(table.get(d, table[Domain.ECOMMERCE]))
    out["items"] = _items(*out["items"])
    return out


STORY_EN: dict[Domain, list[tuple[str, str]]] = {
    Domain.ECOMMERCE: [("Materials first, then form", "Every piece starts from durable, safe materials before its shape."),
                       ("Fewer pieces, made with care", "A small range, so every product is checked before it reaches you."),
                       ("Here after the sale", "Warranty, maintenance and advice are part of the product."),
                       ("Delivered and installed", "Our own team delivers, installs and shows you how it works."),
                       ("Clear prices up front", "Listed prices include tax and city delivery, with nothing added at checkout."),
                       ("Changed your mind?", "Undamaged products can be exchanged or refunded within 30 days.")],
    Domain.SAAS: [("Plan in minutes", "Create a project, split the work and set deadlines from one screen."),
                  ("Everything in one place", "Requests, bugs and ideas land in one queue instead of chat threads."),
                  ("Progress without meetings", "Status updates itself as work moves along."),
                  ("Automate the repetitive", "Rules assign, move and remind so nobody has to."),
                  ("Works with your tools", "Sync with calendar, email and code through built-in integrations."),
                  ("Reports for managers", "Weekly numbers are ready, exported to a spreadsheet in one click.")],
    Domain.BOOKING: [("Book in 30 seconds", "Pick a service and an open slot, then confirm — no phone call."),
                     ("Automatic reminders", "A message a day before and two hours before, so nothing is missed."),
                     ("Certified specialists", "Everyone on the team is trained and licensed."),
                     ("Private rooms", "Each room is cleaned after every guest."),
                     ("Transparent pricing", "Every service shows its price before you book."),
                     ("Flexible rescheduling", "Free up to two hours ahead, right from your confirmation.")],
    Domain.EDTECH: [("Learn step by step", "Lessons follow a clear order, each with its own goal and exercise."),
                    ("Practice on real projects", "Every chapter ends with something you build yourself."),
                    ("1:1 reviews", "Detailed feedback on every submission within 48 hours."),
                    ("Learn anytime", "Rewatch lessons on phone or laptop, without limits."),
                    ("A community of learners", "Ask questions and share projects with your cohort."),
                    ("Certificate of completion", "Earned once every assignment is in.")],
    Domain.PORTFOLIO: [("Start from the problem", "Every project opens with the question the client needs answered."),
                       ("Test early, fix early", "Prototypes are tried with real users before they are finished."),
                       ("A complete handover", "Documentation, source files and guides are delivered in full."),
                       ("Transparent process", "Weekly updates on a shared board."),
                       ("Measured outcomes", "Every project tracks a metric before and after launch."),
                       ("Support after launch", "Adjustments included for the first 30 days.")],
}

FEATURES_EN: dict[Domain, list[tuple[str, str]]] = {
    Domain.SAAS: [("Cycles", "Two-week cycles; unfinished work rolls over on its own."),
                  ("Roadmaps", "Drag milestones and see which work blocks which."),
                  ("Team permissions", "Each team sees its own projects; guests see only what is shared."),
                  ("Mobile app", "Review work and reply to comments from your phone."),
                  ("Instant search", "Type a few letters to find work, docs or people."),
                  ("Open API", "Connect internal systems through a documented API and webhooks.")],
    Domain.BOOKING: [("Choose your specialist", "See each person's open slots and pick the one you know."),
                     ("Pay ahead", "Hold your slot with card or wallet."),
                     ("Membership card", "Earn points every visit, redeem them for a free session."),
                     ("Gift cards", "By service or by amount."),
                     ("Post-visit feedback", "Rate each specialist directly."),
                     ("Follow-up reminders", "Reminders that follow your treatment plan.")],
    Domain.EDTECH: [("Short videos", "Every lesson under 15 minutes, with subtitles."),
                    ("Auto-graded exercises", "Run your code and get results in the browser."),
                    ("Personal path", "The next lesson is suggested from your scores."),
                    ("Live Q&A", "A session with mentors every week."),
                    ("Downloads", "Slides and source code for every lesson."),
                    ("Progress tracking", "Hours studied and lessons completed at a glance.")],
}

QUOTE_NOTE_EN = "Sample testimonial — replace with a real review"
QUOTES_EN: dict[Domain, list[str]] = {
    Domain.ECOMMERCE: ["Arrived on time, installed neatly, still like new after months.",
                       "Honest advice, no pressure, and the price matched the website."],
    Domain.SAAS: ["We dropped two meetings a week because progress is already visible.",
                  "Set up in an afternoon; the whole team was using it the next day."],
    Domain.BOOKING: ["Quick to book and no waiting when I arrived.", "Gentle staff, spotless rooms, clear prices."],
    Domain.EDTECH: ["Exercises close to real work, and the reviews are thorough.",
                    "After the course I shipped my first project at work."],
    Domain.PORTFOLIO: ["Clear, on time, and the result exceeded our expectations.",
                       "Understood the problem fast and proposed exactly what we needed."],
}

ROW_META_EN = ["Mar 12", "Feb 28", "Feb 15", "Feb 2", "Jan 20", "Jan 8", "Dec 18", "Dec 5"]

CLONE_PLACEHOLDERS_EN = {
    "brand": "[Your name]",
    "headline": "[Headline: what you do, and for whom]",
    "subhead": "[One or two sentences introducing you or your product]",
    "footer_line": "© [Your name]. Edit the text in the content/ folder.",
}


def copy_en(domain: Domain | None, brand: str) -> dict:
    """English values for every PageCopy pool."""
    d = domain or Domain.OTHER
    base = defaults_en(d)
    story = STORY_EN.get(d, STORY_EN[Domain.ECOMMERCE])
    cta = "Get in touch"
    return dict(
        headline=f"{brand}, done right down to the details", subhead="Clear about what you get, what it costs and when.",
        cta=cta, cta_secondary="See how it works", nav=base["nav"], facts=base["facts"], story=story,
        quotes=[(q, QUOTE_NOTE_EN) for q in QUOTES_EN.get(d, QUOTES_EN[Domain.ECOMMERCE])],
        cards=(_items(*[(t, n, "", "") for t, n in FEATURES_EN[d]]) if d in FEATURES_EN else base["items"]),
        items=base["items"], categories=base["categories"], faqs=base["faqs"],
        closing=f"Ready to start? {cta} — it takes a minute.", footer_line=f"© {brand}. All rights reserved.",
        tabs=[("Overview", "What it is and how to use it."), ("Materials", "What it is made of and how to care for it."),
              ("Shipping", "Delivery times, costs and returns.")],
        rows=[(t, ROW_META_EN[i % len(ROW_META_EN)]) for i, (t, _) in enumerate(story)],
    )


# ------------------------------------------------------------------ template UI strings

UI_EN = {
    "Bài viết": "Writing", "Bán chạy": "Best sellers", "Bảo mật": "Privacy", "Bộ lọc": "Filters",
    "Bộ sưu tập": "Collection", "Chính sách": "Policies", "Chọn nhu cầu": "Choose a need",
    "Chọn nhu cầu của bạn, chúng tôi gợi ý bộ sản phẩm phù hợp": "Pick what you need and we suggest the right set",
    "Chọn phân loại trước khi thêm vào giỏ": "Choose an option before adding to cart",
    "Chọn theo nhu cầu của bạn": "Choose by what you need", "Câu hỏi thường gặp": "Frequently asked questions",
    "Danh mục": "Categories", "Danh sách": "List", "Email chưa đúng định dạng.": "Please enter a valid email.",
    "Giá giảm dần": "Price: high to low", "Giá tăng dần": "Price: low to high",
    "Giỏ hàng có ${count} sản phẩm.": "Your cart has ${count} items.", "Giỏ hàng đang trống.": "Your cart is empty.",
    "Giỏ hàng, ${count} sản phẩm": "Cart, ${count} items", "Giỏ hàng: ${cart}": "Cart: ${cart}",
    "Gợi ý cho riêng bạn": "Picked for you", "Hiện": "Show", "Hiện thêm 8 sản phẩm": "Show 8 more",
    "Hình ${i + 1}": "Image ${i + 1}", "Hỏi đáp": "FAQ", "Hỗ trợ": "Support", "Khách hàng nói gì": "What clients say",
    "Khách mua lại nhiều nhất tháng này": "Most re-ordered this month", "Khám phá": "Explore", "Liên hệ": "Contact",
    "Lọc theo danh mục": "Filter by category", "Lựa chọn 1": "Option 1", "Lựa chọn 2": "Option 2", "Lựa chọn 3": "Option 3",
    "Mật khẩu": "Password", "Mật khẩu cần ít nhất 8 ký tự.": "Password needs at least 8 characters.",
    "Mới nhất": "Newest", "Mở menu": "Open menu", "Nhận tin mới qua email": "Get updates by email",
    "Nhập email đầy đủ, ví dụ ten@email.com": "Enter a full email, e.g. name@email.com",
    "Những mẫu được chọn nhiều nhất": "Most chosen pieces", "Nổi bật": "Featured", "Phân loại": "Options",
    "Sản phẩm liên quan": "Related products", "Thu gọn": "Show less", "Thêm vào giỏ": "Add to cart",
    "Thông báo": "Announcement", "Thư viện hình ảnh": "Gallery", "Tìm hiểu thêm": "See the details", "Tìm kiếm": "Search",
    "Tìm sản phẩm": "Search products", "Tất cả": "All", "Vận chuyển": "Shipping",
    "Xem tất cả (${ROWS.length})": "View all (${ROWS.length})",
    "Chưa có đánh giá": "No reviews yet", "Thêm đánh giá thật ở bước bàn giao": "Add real reviews at handover",
    "Điều bạn nên biết trước khi bắt đầu": "What to know before you start", "Điều hướng chính": "Main navigation",
    "Điều khoản": "Terms", "Đã ghi nhận": "Received", "Đã ghi nhận, chúng tôi sẽ liên hệ": "Received — we'll be in touch",
    "Đã thêm vào giỏ": "Added to cart", "Đã đăng ký, cảm ơn bạn.": "Subscribed — thank you.", "Đóng": "Close",
    "Đóng menu": "Close menu", "Đóng thông báo": "Dismiss", "Đóng tìm kiếm": "Close search", "Đăng ký": "Subscribe",
    "Đăng ký nhận tin": "Subscribe", "Đăng nhập": "Sign in", "Được nhắc đến trên": "Featured on",
    "Đối tác và báo chí": "Partners and press", "Đổi trả": "Returns", "Ảnh thương hiệu": "Brand image",
    "Xem nhanh": "Quick view", "Xem chi tiết": "View details", "Liên hệ ngay": "Get in touch", "Menu": "Menu",
    "Chọn phân loại": "Choose an option", "sản phẩm": "products", "Hình": "Image",
    "Ẩn": "Hide", "Ảnh ${i + 1}": "Image ${i + 1}", "Tài khoản": "Account",
}

# A UI string is replaced only where it stands as a whole literal: in quotes, backticks or as JSX text.
_LITERAL = re.compile(r'(?P<q>["`])(?P<s>[^"`\n]*?)(?P=q)|>(?P<t>[^<>{}\n]+)<')


# Words inside mixed text ("Đang hiển thị {shown} sản phẩm", "4 sản phẩm", a label before a <select>).
FRAGMENTS_EN = [(re.compile(r"Đang hiển thị "), "Showing "), (re.compile(r"(\d+|\}) sản phẩm"), r"\1 products"),
                (re.compile(r"Sắp xếp"), "Sort by"), (re.compile(r">Xem nhanh \{"), ">Quick view: {")]


def translate(text: str, lang: str) -> str:
    if lang == "vi":
        return text
    stripped = text.strip()
    if stripped in UI_EN:
        return text.replace(stripped, UI_EN[stripped])
    for pattern, repl in FRAGMENTS_EN:
        text = pattern.sub(repl, text)
    return text


def localize_code(code: str, lang: str) -> str:
    """Generated component code with its fixed Vietnamese UI strings in the page language."""
    if lang == "vi":
        return code

    def sub(m: re.Match) -> str:
        if m.group("t") is not None:
            return ">" + translate(m.group("t"), lang) + "<"
        return m.group("q") + translate(m.group("s"), lang) + m.group("q")
    code = _LITERAL.sub(sub, code)
    for pattern, repl in FRAGMENTS_EN:  # mixed JSX text the literal pass cannot see whole
        code = pattern.sub(repl, code)
    return code


def localize_value(value, lang: str):
    """Content-file values (lifted section titles, labels) in the page language."""
    if lang == "vi":
        return value
    if isinstance(value, str):
        return translate(value, lang)
    if isinstance(value, list):
        return [localize_value(v, lang) for v in value]
    if isinstance(value, dict):
        return {k: localize_value(v, lang) for k, v in value.items()}
    return value
