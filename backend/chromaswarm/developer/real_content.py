"""The business's real content, asked once at B4 (Creative), in the user's own words.

Without it every page is built from domain samples: invented products, policies and claims — the
largest single reason a generated page reads as made up. The B4 assets card shows a short form
per domain (what you sell, what makes you different, the real list with prices, numbers you can
stand behind, real customer words, real questions, contact). Every field is optional; one line
per entry, parts split by "|". Each line of the list may carry its own photo (uploaded like any
B4 product photo); the page shows it on that item's card instead of a stock photo.

What the user gives replaces the samples in `content.build_copy` (their words are kept as typed:
never rewritten by the rules, never filtered as "AI tells"), and goes to the copywriter as facts:
its numbers become the only numbers the model may write. What they leave empty stays sample copy,
listed in PRODUCT.md as content to replace.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from chromaswarm.developer.uploads import is_upload
from chromaswarm.state_machine.pipeline_state import Domain


class Field(BaseModel):
    key: str
    label: str
    placeholder: str
    rows: int = 2


# What one entry of the list is called, per domain: (label, placeholder)
_ITEMS = {
    Domain.ECOMMERCE: ("Sản phẩm và giá (mỗi dòng: tên | giá | ghi chú ngắn)",
                       "Tên sản phẩm | 390.000₫ | ghi chú ngắn\nSản phẩm thứ hai | 450.000₫ | màu, cỡ, khối lượng"),
    Domain.SAAS: ("Các gói và giá (mỗi dòng: tên gói | giá | gồm gì)",
                  "Miễn phí | 0₫ | 1 kho, 100 mã hàng\nCửa hàng | 290.000₫/tháng | 3 kho, không giới hạn mã hàng"),
    Domain.BOOKING: ("Dịch vụ và giá (mỗi dòng: tên | giá | thời lượng)",
                     "Gội dưỡng thảo mộc | 180.000₫ | 45 phút\nMassage cổ vai gáy | 320.000₫ | 60 phút"),
    Domain.EDTECH: ("Khóa học và học phí (mỗi dòng: tên | học phí | dành cho ai)",
                    "IELTS nền tảng | 4.500.000₫ | mất gốc, 10 tuần\nIELTS 6.5+ | 6.900.000₫ | đã có 5.5"),
    Domain.PORTFOLIO: ("Dự án tiêu biểu (mỗi dòng: tên | năm | bạn làm gì)",
                       "App đặt tour Saigontrip | 2025 | thiết kế UX/UI\nWebsite Mộc Café | 2024 | nhận diện + web"),
}
_OFFER = {
    Domain.ECOMMERCE: "Bán gì, cho ai — đồ handmade làm quà tặng, giao toàn quốc",
    Domain.SAAS: "Phần mềm làm gì, cho ai — quản lý tồn kho cho shop bán trên Shopee và TikTok",
    Domain.BOOKING: "Dịch vụ gì, ở đâu — tiệm gội dưỡng sinh ở quận 3, mở 9h–21h",
    Domain.EDTECH: "Dạy gì, cho ai — luyện IELTS cho người đi làm, học tối và cuối tuần",
    Domain.PORTFOLIO: "Bạn là ai, làm gì — thiết kế sản phẩm số 6 năm, chuyên app đặt chỗ",
}


# Examples for any kind of business; an industry pack (developer/industry.py) gives its own
_NEUTRAL = dict(
    different="Điểm khác biệt | giải thích ngắn bằng việc cụ thể\nĐổi trong 7 ngày | nếu lỗi từ phía cửa hàng",
    numbers="1.200 | đơn đã giao năm 2025\n4,8/5 | 320 đánh giá trên Google Maps",
    reviews="Giao đúng hẹn, hàng giống ảnh | Chị Hạnh, Thủ Đức",
    faqs="Có giao tỉnh không? | Có, 2–4 ngày, phí báo trước khi giao",
    contact="Địa chỉ · giờ mở cửa · Zalo hoặc hotline",
)


def fields(domain: Domain | None, pack: dict | None = None) -> list[Field]:
    """The B4 form for this kind of site; `pack` (the business's industry) gives examples in its own words."""
    d = domain if domain in _ITEMS else Domain.ECOMMERCE
    label, ph = _ITEMS[d]
    ex = {**_NEUTRAL, "offer": _OFFER[d], "items": ph, **((pack or {}).get("form") or {})}
    return [
        Field(key="offer", label="Bạn làm gì, cho ai (1–2 câu, lời của bạn)", placeholder=ex["offer"]),
        Field(key="different", label="Điều khác biệt so với chỗ khác (mỗi dòng: điểm khác biệt | giải thích)", rows=3,
              placeholder=ex["different"]),
        Field(key="items", label=label, placeholder=ex["items"], rows=3),
        Field(key="numbers", label="Con số thật bạn có (mỗi dòng: số | nghĩa là gì)", placeholder=ex["numbers"]),
        Field(key="reviews", label="Lời khách thật (mỗi dòng: lời khách | tên khách)", placeholder=ex["reviews"]),
        Field(key="faqs", label="Câu khách hay hỏi (mỗi dòng: câu hỏi | trả lời)", placeholder=ex["faqs"]),
        Field(key="contact", label="Liên hệ (địa chỉ, giờ mở cửa, hotline, email)", rows=1, placeholder=ex["contact"]),
    ]


class RealItem(BaseModel):
    name: str
    price: str = ""
    note: str = ""
    image: str = ""  # "uploads/product-image-….jpg": the photo the user attached to this line


class RealContent(BaseModel):
    offer: str = ""
    different: list[tuple[str, str]] = []
    items: list[RealItem] = []
    numbers: list[tuple[str, str]] = []
    reviews: list[tuple[str, str]] = []
    faqs: list[tuple[str, str]] = []
    contact: str = ""

    def given(self) -> list[str]:
        """Vietnamese names of what the user gave, for the B4 notice and PRODUCT.md."""
        names = {"offer": "mô tả", "different": "điểm khác biệt", "items": "danh sách và giá", "numbers": "số liệu",
                 "reviews": "lời khách", "faqs": "hỏi đáp", "contact": "liên hệ"}
        return [label for k, label in names.items() if getattr(self, k)]

    def missing(self) -> list[str]:
        names = {"offer": "mô tả", "items": "danh sách và giá", "numbers": "số liệu", "reviews": "lời khách",
                 "faqs": "hỏi đáp"}
        return [label for k, label in names.items() if not getattr(self, k)]


LIMITS = {"offer": 220, "part": 120, "contact": 160}
MAX = {"different": 6, "items": 8, "numbers": 4, "reviews": 3, "faqs": 8}
_SPLIT = re.compile(r"\s*\|\s*|\t+")
_PRICE = re.compile(r"(\d[\d.,]*\s*(?:₫|đ|vnđ|vnd|k|nghìn|ngàn|triệu|tr)(?!\w)(?:\s*/\s*\w+)?|miễn phí|liên hệ|\$\s?\d[\d.,]*)", re.I)


def _clean(text, limit: int) -> str:
    return " ".join(text.split())[:limit].strip() if isinstance(text, str) else ""


def _lines(text) -> list[str]:
    if not isinstance(text, str):
        return []
    return [ln.strip(" -•*\t") for ln in text.splitlines() if ln.strip(" -•*\t")]


def _parts(line: str, n: int) -> list[str]:
    parts = [_clean(p, LIMITS["part"]) for p in _SPLIT.split(line)]
    return (parts + [""] * n)[:n]


def _pairs(text, key: str) -> list[tuple[str, str]]:
    out = []
    for ln in _lines(text)[:MAX[key]]:
        a, b = _parts(ln, 2)
        if a:
            out.append((a, b))
    return out


def _items(text, photos=None) -> list[RealItem]:
    """One item per line; `photos[n]` is the upload attached to the n-th non-empty line (or "")."""
    photos = photos if isinstance(photos, list) else []
    out = []
    for n, ln in enumerate(_lines(text)[:MAX["items"]]):
        photo = photos[n] if n < len(photos) and isinstance(photos[n], str) and is_upload(photos[n]) else ""
        if _SPLIT.search(ln):
            name, price, note = _parts(ln, 3)
        else:  # "Bàn gỗ sồi 6.900.000₫": the price is found in the line itself
            m = _PRICE.search(ln)
            name = _clean(ln[:m.start()] if m else ln, LIMITS["part"]).strip(" -–:,")
            price, note = (_clean(m.group(), 40) if m else ""), ""
        if name:
            out.append(RealItem(name=name, price=price, note=note,
                                image=(photo if photo.startswith("uploads/") else f"uploads/{photo}") if photo else ""))
    return out


def parse(texts: dict | None) -> RealContent:
    """The B4 form answer → RealContent. Never raises; anything unreadable is left out."""
    t = texts if isinstance(texts, dict) else {}
    numbers = [(a, b) for a, b in _pairs(t.get("numbers"), "numbers") if re.search(r"\d", a) and b]
    return RealContent(
        offer=_clean(t.get("offer"), LIMITS["offer"]),
        different=_pairs(t.get("different"), "different"),
        items=_items(t.get("items"), t.get("item_photos")),
        numbers=numbers,
        reviews=[(q, who) for q, who in _pairs(t.get("reviews"), "reviews")],
        faqs=[(q, a) for q, a in _pairs(t.get("faqs"), "faqs") if a],
        contact=_clean(t.get("contact"), LIMITS["contact"]),
    )
