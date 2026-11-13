"""B1-B4 Product Consultant.

`ConsultantAgent` is the interface the LangGraph nodes call. `RuleBasedConsultant`
implements it with keyword rules and the tables of FRONTEND_STANDARDS.md §1:
it runs without an API key and is the non-LLM baseline for the paper's ablation.
`LLMConsultant` (llm_consultant.py) implements the same interface with an LLM.

Zero-guessing: `interpret()` returns None when an answer is ambiguous or empty,
and the graph re-asks instead of filling the gap itself.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from pydantic import BaseModel

from chromaswarm.engines.design_spec import Philosophy
from chromaswarm.engines.palette import Mode
from chromaswarm.engines.presets import LAYOUTS, THEMES, Layout, Theme
from chromaswarm.engines.spacing import Density
from chromaswarm.state_machine.pipeline_state import Domain, Pillars, SitemapPage


class Option(BaseModel):
    value: str
    label: str
    hint: str = ""


class Question(BaseModel):
    step: str
    kind: str  # text | choice | assets | recommend_url | approval | info
    key: str
    text: str
    options: list[Option] = []
    recommended: str | None = None
    allow_free_text: bool = True
    note: str | None = None  # e.g. "answer was unclear, please pick one"


class ConsultantAgent(Protocol):
    def classify_domain(self, prompt: str) -> Domain | None: ...
    def sitemap_for(self, domain: Domain) -> tuple[list[SitemapPage], str]: ...
    def pillar_question(self, pillar: str) -> Question: ...
    def interpret(self, pillar: str, answer: str) -> str | None: ...
    def interpret_feedback(self, feedback: str, pillars: Pillars) -> dict[str, str]: ...
    def write_philosophy(self, facts: dict) -> Philosophy | None: ...


def fold(text: str) -> str:
    """Lowercase + strip Vietnamese diacritics so 'Sang trọng' matches 'sang trong'."""
    text = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _hits(text: str, table: dict[str, list[str]], norm) -> set[str]:
    t = norm(text)
    return {key for key, words in table.items() if any(re.search(rf"\b{re.escape(norm(w))}\b", t) for w in words)}


def _match(answer: str, table: dict[str, list[str]]) -> str | None:
    """Unique keyword match. Accented match first ('sang trọng' != 'sáng trong'),
    accent-folded match only when the user typed without diacritics."""
    hits = _hits(answer, table, str.lower)
    if not hits:
        hits = _hits(answer, table, fold)
    return hits.pop() if len(hits) == 1 else None


DOMAIN_WORDS: dict[str, list[str]] = {
    Domain.ECOMMERCE: ["bán hàng", "bán", "shop", "cửa hàng", "thời trang", "nội thất", "giày", "store",
                       "ecommerce", "e-commerce", "mỹ phẩm", "sell"],
    Domain.SAAS: ["saas", "phần mềm", "dashboard", "quản lý", "web app", "fintech", "crm"],
    Domain.BOOKING: ["đặt lịch", "đặt bàn", "booking", "spa", "nhà hàng", "salon", "khách sạn", "phòng khám"],
    Domain.EDTECH: ["khóa học", "course", "học online", "edtech", "lớp học"],
    Domain.PORTFOLIO: ["portfolio", "hồ sơ cá nhân", "trang cá nhân", "cv"],
}

SITEMAPS: dict[Domain, tuple[list[tuple[str, str, str]], str]] = {
    Domain.ECOMMERCE: ([
        ("landing", "Landing Page", "Trang chiến dịch / ra mắt sản phẩm chủ lực"),
        ("home", "Home / Storefront", "Trang chủ trưng bày danh mục"),
        ("catalog", "Product Catalog & Filter", "Tìm kiếm và lọc sản phẩm"),
        ("pdp", "Product Detail Page", "Chi tiết sản phẩm và chọn phân loại"),
        ("cart", "Cart & Checkout", "Giỏ hàng và thanh toán"),
        ("account", "Login / Register & Profile", "Tài khoản và lịch sử đơn hàng"),
    ], "landing"),
    Domain.SAAS: ([
        ("landing", "Marketing Landing Page", "Giới thiệu giải pháp và bảng giá"),
        ("login", "Login / Onboarding", "Đăng nhập và thiết lập ban đầu"),
        ("dashboard", "Main Dashboard", "Bảng điều khiển trung tâm"),
        ("workspace", "Feature Workspace", "Trang thao tác tính năng chính"),
        ("settings", "Settings & Billing", "Cài đặt và quản lý gói cước"),
    ], "landing"),
    Domain.BOOKING: ([
        ("home", "Home / Brand Story", "Trang chủ và câu chuyện thương hiệu"),
        ("services", "Service Menu", "Danh mục dịch vụ và bảng giá"),
        ("booking", "Interactive Booking Flow", "Chọn ngày giờ và đặt lịch"),
        ("my-bookings", "Login / My Bookings", "Quản lý lịch hẹn cá nhân"),
    ], "home"),
    Domain.EDTECH: ([
        ("landing", "Course Landing Page", "Giới thiệu khóa học"),
        ("directory", "Course Directory", "Thư viện khóa học"),
        ("learn", "Learning Room", "Trang học tập và bài tập"),
        ("student", "Login & Student Dashboard", "Tiến độ học tập"),
    ], "landing"),
    Domain.PORTFOLIO: ([
        ("home", "Home / Intro", "Giới thiệu bản thân và điểm nổi bật"),
        ("projects", "Projects", "Danh sách dự án"),
        ("project", "Project Detail", "Câu chuyện từng dự án"),
        ("contact", "Contact", "Liên hệ / đặt lịch trao đổi"),
    ], "home"),
}

PILLAR_QUESTIONS: dict[str, tuple[str, list[Option]]] = {
    "theme": (
        "Khi khách hàng mở trang web này lên, bạn muốn họ có cảm giác gì đầu tiên?",
        [Option(value=t.value, label=p.label_vi, hint=f"{p.heading_font} · bo góc {p.radius_md}px")
         for t, p in THEMES.items()],
    ),
    "layout": (
        "Bạn muốn cách sắp xếp nội dung trên trang đi theo hướng nào?",
        [Option(value=l.value, label=p.label_vi, hint=p.reading_pattern) for l, p in LAYOUTS.items()],
    ),
    "color": (
        "Thương hiệu của bạn đã có màu chủ đạo chưa (ví dụ #8a3b12 hoặc 'nâu đất')? "
        "Và bạn thích tông Sáng trong trẻo, Sáng ấm dịu mắt, hay Tối sang trọng?",
        [Option(value=Mode.LIGHT.value, label="Sáng trong trẻo"),
         Option(value=Mode.WARM_PAPER.value, label="Sáng ấm dịu mắt (giấy kem)"),
         Option(value=Mode.DARK.value, label="Tối sang trọng")],
    ),
    "margins": (
        "Bạn muốn các mục trên trang nằm thoáng đãng, cách xa nhau, hay xếp gọn để khách xem được nhiều thông tin cùng lúc?",
        [Option(value=Density.AIRY.value, label="Thoáng đãng, cao cấp", hint="section 128px"),
         Option(value=Density.BALANCED.value, label="Cân bằng", hint="section 80px"),
         Option(value=Density.DENSE.value, label="Gọn, nhiều thông tin", hint="section 48px")],
    ),
    "scope": (
        "Khách hàng chính vào trang này là ai (độ tuổi, dùng điện thoại hay máy tính nhiều hơn)? "
        "Và hành động QUAN TRỌNG NHẤT bạn muốn họ bấm trước khi rời trang là gì?",
        [],
    ),
}

THEME_WORDS = {
    Theme.EDITORIAL_LUXURY: ["sang trọng", "cao cấp", "luxury", "tĩnh lặng", "tối giản", "showroom", "editorial"],
    Theme.PRECISION_TECH: ["công nghệ", "hiện đại", "tech", "chuẩn xác", "sắc sảo", "saas"],
    Theme.WARM_ORGANIC: ["thân thiện", "ấm áp", "gần gũi", "organic", "đời sống", "dễ thương"],
    Theme.NEO_BRUTALIST: ["cá tính", "táo bạo", "phá cách", "năng động", "brutalist", "nổi loạn"],
}
LAYOUT_WORDS = {
    Layout.VISUAL_FIRST: ["hình ảnh", "ảnh lớn", "ít chữ", "visual", "phương án a"],
    Layout.NARRATIVE: ["kể chuyện", "dẫn dắt", "từng bước", "storytelling", "phương án b"],
    Layout.CATALOG: ["danh mục", "nhiều sản phẩm", "catalog", "dễ chọn", "phương án c"],
}
MODE_WORDS = {
    Mode.DARK: ["tối", "dark", "đen sang trọng"],
    Mode.WARM_PAPER: ["ấm", "kem", "giấy", "warm", "dịu mắt"],
    Mode.LIGHT: ["sáng trong", "trắng", "light", "trong trẻo"],
}
DENSITY_WORDS = {
    Density.AIRY: ["thoáng", "rộng", "airy", "thư thái", "cách xa"],
    Density.BALANCED: ["cân bằng", "vừa phải", "balanced"],
    Density.DENSE: ["gọn", "nhiều thông tin", "dày", "compact", "cô đọng"],
}
COLOR_NAMES = {
    "nâu đất": "#8a4b2a", "nâu": "#7c4a2d", "đỏ": "#c62828", "cam": "#e0661b", "vàng": "#d4a017",
    "xanh lá": "#2e7d32", "xanh rêu": "#5b6b2f", "xanh ngọc": "#0f8f7f", "xanh dương": "#1f5fbf",
    "xanh navy": "#1e3a6b", "hồng": "#d14d72", "đen": "#1a1a1a", "be": "#b89b72",
}
DEFAULT_SEED_BY_THEME = {
    Theme.EDITORIAL_LUXURY: "#7a4a2a", Theme.PRECISION_TECH: "#1f5fbf",
    Theme.WARM_ORGANIC: "#c25a1b", Theme.NEO_BRUTALIST: "#d1332e",
}

HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


class RuleBasedConsultant:
    def classify_domain(self, prompt: str) -> Domain | None:
        hit = _match(prompt, {k.value: v for k, v in DOMAIN_WORDS.items()})
        return Domain(hit) if hit else None

    def sitemap_for(self, domain: Domain) -> tuple[list[SitemapPage], str]:
        pages, first = SITEMAPS.get(domain, SITEMAPS[Domain.PORTFOLIO])
        return [SitemapPage(slug=s, title=t, purpose=p) for s, t, p in pages], first

    def pillar_question(self, pillar: str) -> Question:
        text, options = PILLAR_QUESTIONS[pillar]
        return Question(step="B3", kind="choice" if options else "text", key=pillar, text=text, options=options)

    def interpret(self, pillar: str, answer: str) -> str | None:
        answer = (answer or "").strip()
        if not answer:
            return None
        options = {o.value for o in PILLAR_QUESTIONS[pillar][1]}
        if pillar == "color":
            return self._interpret_color(answer)
        if answer in options:
            return answer
        if pillar == "theme":
            return _match(answer, {k.value: v for k, v in THEME_WORDS.items()})
        if pillar == "layout":
            letter = re.fullmatch(r"\s*([abc])\s*", answer.lower())
            if letter:
                return [Layout.VISUAL_FIRST, Layout.NARRATIVE, Layout.CATALOG]["abc".index(letter.group(1))].value
            return _match(answer, {k.value: v for k, v in LAYOUT_WORDS.items()})
        if pillar == "margins":
            return _match(answer, {k.value: v for k, v in DENSITY_WORDS.items()})
        if pillar == "scope":
            return answer if len(answer) >= 12 else None
        return None

    def _interpret_color(self, answer: str) -> str | None:
        modes = {m.value for m in Mode}
        parts = answer.split()
        mode = next((p for p in parts if p in modes), None)
        if mode is None:
            mode = _match(answer, {k.value: v for k, v in MODE_WORDS.items()})
        if mode is None:
            return None
        hex_ = HEX.search(answer)
        if hex_:
            return f"{mode} {hex_.group(0).lower()}"
        named = named_color(answer)
        return f"{mode} {named}" if named else mode  # no brand colour yet: a theme default is shown at B7

    # ------------------------------------------------------------ B7 / B5
    def interpret_feedback(self, feedback: str, pillars: Pillars) -> dict[str, str]:
        """Pillar changes stated *explicitly* in B7 feedback ('đổi sang tông tối').
        Anything else (copy, imagery...) changes nothing here and is passed to the
        Dev department as a recorded rule."""
        fb = (feedback or "").strip()
        if not fb:
            return {}
        found: dict[str, str | None] = {
            "theme": _match(fb, {k.value: v for k, v in THEME_WORDS.items()}),
            "layout": _match(fb, {k.value: v for k, v in LAYOUT_WORDS.items()}),
            "margins": _match(fb, {k.value: v for k, v in DENSITY_WORDS.items()}),
        }
        mode = _match(fb, {k.value: v for k, v in MODE_WORDS.items()})
        hex_ = HEX.search(fb)
        seed = hex_.group(0).lower() if hex_ else named_color(fb, exclude=("đen",))
        found["color"] = merge_color(pillars.color, mode, seed)
        return {k: v for k, v in found.items() if v and v != getattr(pillars, k)}

    def write_philosophy(self, facts: dict) -> Philosophy | None:
        return None  # the engine's default_philosophy is the baseline prose


def named_color(text: str, exclude: tuple[str, ...] = ()) -> str | None:
    """'màu xanh rêu' -> '#5b6b2f' from COLOR_NAMES, longest name first.

    Accented match first: 'cảm giác' must not read as 'cam' (orange). The accent-folded
    match is used only when the user typed without diacritics at all."""
    names = [n for n in sorted(COLOR_NAMES, key=len, reverse=True) if n not in exclude]
    lower = (text or "").lower()
    for name in names:
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return COLOR_NAMES[name]
    if fold(lower) == lower:  # no Vietnamese diacritics anywhere: 'mau xanh reu'
        for name in names:
            if re.search(rf"\b{re.escape(fold(name))}\b", lower):
                return COLOR_NAMES[name]
    return None


def merge_color(current: str | None, mode: str | None, seed: str | None) -> str | None:
    """Apply a partial colour change: keep whichever half the user did not mention."""
    if not mode and not seed:
        return None
    parts = (current or "light").split()
    new_mode = mode or parts[0]
    new_seed = seed or (parts[1] if len(parts) > 1 else None)
    return f"{new_mode} {new_seed}" if new_seed else new_mode


def split_color(value: str, theme: Theme) -> tuple[Mode, str, bool]:
    """'warm-paper #8a3b12' -> (mode, seed, user_supplied)."""
    parts = value.split()
    mode = Mode(parts[0])
    if len(parts) > 1:
        return mode, parts[1], True
    return mode, DEFAULT_SEED_BY_THEME[theme], False


_CTA = re.compile(r"(?:bấm|nhấn|click|chọn|hành động(?: chính)?(?: là)?)\s*[:\-]?\s*[\"“']?([^,.;\"”'\n]{3,48})", re.I)
_FILLER = re.compile(r"^\s*(?:mình|tôi|em|anh|chị)?\s*(?:muốn|cần)?\s*(?:làm|xây dựng|tạo)?\s*(?:cho mình|cho tôi)?\s*(?:một|1)?\s*", re.I)


def extract_cta(scope: str) -> str | None:
    """'... muốn họ bấm Đặt lịch xem showroom' -> 'Đặt lịch xem showroom'."""
    m = _CTA.search(scope or "")
    return m.group(1).strip().rstrip("!?") if m else None


def project_title(prompt: str, limit: int = 48) -> str:
    """Short project title cut at a word boundary, filler ('mình muốn làm...') removed."""
    text = _FILLER.sub("", (prompt or "").strip()) or (prompt or "Dự án").strip()
    text = text[0].upper() + text[1:] if text else "Dự án"
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def base_font_for(scope: str) -> int:
    return 18 if re.search(r"\b(lớn tuổi|trung niên|người già|50|60|đọc nhiều)\b", scope.lower()) else 16
