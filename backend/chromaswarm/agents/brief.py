"""Brief reader: a detailed first message is a design brief, not just a topic.

Users often paste a full brief (brand, palette hex codes, fonts, audience, the exact
sections they want, interactive features). Without this module the pipeline kept only
the domain and asked the five pillars again, then built the generic blueprint —
ignoring almost everything the user wrote (LUMIÈRE BOTANIQUE, 2026-11-14: design score 3.9).

`read_brief(prompt, chat)` returns a validated `Brief`:
- every value is either the user's own words or a closed-set choice (theme, layout,
  density, mode, section kinds) — decision 8: nothing is invented, unclear parts stay None;
- hex codes must appear literally in the prompt; fonts must ship Vietnamese (§ decision 9);
- rule-based fallback (no LLM): hex codes, quoted brand name, known font names.

The pipeline then pre-fills the B3 pillars it can (the user still reviews them at B7),
builds the sections in the order the brief lists them, and feeds the brief's facts to the
copywriter.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, Field

from chromaswarm.agents.llm import JSONChat, LLMConfig, LLMError, OpenAICompatChat
from chromaswarm.engines.color import parse_css_color
from chromaswarm.engines.palette import Mode
from chromaswarm.engines.presets import VIETNAMESE_FONTS, Layout, Theme
from chromaswarm.engines.spacing import Density

log = logging.getLogger(__name__)

MIN_BRIEF_CHARS = 160  # shorter first messages are a topic, not a brief

# Section kinds a brief can ask for -> buildable structure (planner / developer.nextjs).
SECTION_KINDS: dict[str, tuple[str, str]] = {
    "announcement": ("announcement-bar", "Thanh thông báo khuyến mãi trên cùng"),
    "hero": ("hero", "Khối mở đầu: tiêu đề, mô tả, nút chính"),
    "usp": ("usp-strip", "Dải cam kết / lợi ích ngắn (3-4 ý)"),
    "metrics": ("inline-metrics", "Dải số liệu"),
    "products": ("grid-4", "Lưới sản phẩm (có thể có tab lọc danh mục)"),
    "collection": ("bento", "Bộ sưu tập nổi bật dạng ô lớn nhỏ"),
    "categories": ("horizontal-scroller", "Dải danh mục"),
    "quiz": ("picker-recommend", "Khối tương tác: chọn một lựa chọn -> gợi ý sản phẩm"),
    "story": ("alternating-z", "Câu chuyện / thành phần: ảnh và chữ xen kẽ"),
    "feature": ("feature-showcase", "Một tính năng / thành phần nổi bật với ảnh rộng"),
    "testimonials": ("testimonials", "Đánh giá khách hàng"),
    "faq": ("accordion", "Hỏi đáp / accordion"),
    "closing": ("full-bleed-band", "Dải kêu gọi hành động cuối trang"),
}

HERO_LAYOUT_WORDS = {
    Layout.CATALOG: ["chia đôi", "bất đối xứng", "55/45", "60/40", "split"],
    Layout.VISUAL_FIRST: ["ảnh tràn", "full-bleed", "toàn màn hình", "hình ảnh lớn"],
    Layout.NARRATIVE: ["kể chuyện", "storytelling", "tạp chí", "editorial"],
}

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


class BriefSection(BaseModel):
    kind: str
    note: str = ""  # the user's own description of the section (shown in PLAN.md)


class Brief(BaseModel):
    brand: str | None = None
    audience: str | None = None
    primary_cta: str | None = None
    secondary_cta: str | None = None
    announcement: str | None = None
    theme: str | None = None
    layout: str | None = None
    margins: str | None = None
    mode: str | None = None
    accent: str | None = None  # hex from the prompt
    background: str | None = None  # main background hex from the prompt (decides the tone when mode is unset)
    heading_font: str | None = None
    body_font: str | None = None
    nav: list[str] = Field(default_factory=list)  # header menu items the user listed
    usp: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    quiz_options: list[str] = Field(default_factory=list)
    sections: list[BriefSection] = Field(default_factory=list)

    def scope(self) -> str | None:
        """B3 scope in the user's words: audience + main action, when both are known."""
        if self.audience and self.primary_cta:
            return f"{self.audience.rstrip('. ')}. Hành động quan trọng nhất: {self.primary_cta}"
        return None

    def summary(self) -> list[str]:
        out = []
        if self.brand:
            out.append(f"thương hiệu {self.brand}")
        if self.accent:
            out.append(f"màu nhấn {self.accent}")
        if self.heading_font:
            out.append(f"font tiêu đề {self.heading_font}")
        if self.sections:
            out.append(f"{len(self.sections)} section theo đúng thứ tự bạn mô tả")
        return out


SYSTEM = """Bạn đọc một bản mô tả (brief) thiết kế trang web tiếng Việt và trích xuất thông tin có cấu trúc.
Chỉ ghi những gì người dùng ĐÃ VIẾT; điều gì không có thì để null hoặc [] — tuyệt đối không bịa.
Các chuỗi giữ nguyên lời người dùng, ngắn gọn.
- theme (cảm giác chủ đạo) chọn một trong: {themes} hoặc null.
  Gợi ý: "quiet luxury", cao cấp, tinh tế, tối giản sang trọng, kiểu Aesop / tạp chí -> editorial-luxury;
  công nghệ, chính xác, SaaS -> precision-tech; thân thiện, gần gũi, vui vẻ, thủ công ấm cúng -> warm-organic;
  cá tính, táo bạo, đường phố -> neo-brutalist. Khi có cả "luxury" và "organic", ưu tiên editorial-luxury.
- layout chọn một trong: {layouts} hoặc null.
- margins (độ thoáng) chọn một trong: {densities} hoặc null.
- mode (tông nền) chọn một trong: {modes} hoặc null.
- accent: mã hex màu nhấn / màu nút chính nếu người dùng ghi mã. background: mã hex màu nền chính nếu có.
- heading_font / body_font: tên font người dùng nêu (lấy font đầu tiên nếu ghi "A hoặc B").
- sections: danh sách các khối trang theo ĐÚNG THỨ TỰ người dùng liệt kê (không tính header và footer),
  mỗi khối có kind thuộc {kinds} và note là mô tả ngắn của người dùng.
- nav: các mục menu điều hướng người dùng liệt kê (tối đa 5).
- usp: các cam kết / lợi ích ngắn (tối đa 4). categories: danh mục sản phẩm (tối đa 6).
- products: tên sản phẩm cụ thể nếu có. quiz_options: các lựa chọn của khối tương tác (ví dụ các loại da).
- announcement: nội dung thanh thông báo nếu có.
Trả về JSON: {{"brand", "audience", "primary_cta", "secondary_cta", "announcement", "theme", "layout",
"margins", "mode", "accent", "background", "heading_font", "body_font", "nav": [], "usp": [], "categories": [], "products": [],
"quiz_options": [], "sections": [{{"kind": "", "note": ""}}]}}"""


def _short(v, limit: int) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    return " ".join(v.split())[:limit]


def _font(v) -> str | None:
    if not isinstance(v, str):
        return None
    for name in re.split(r"\s+(?:hoặc|or)\s+|[,/]", v):
        name = name.strip().strip("\"'")
        hit = next((f for f in VIETNAMESE_FONTS if f.lower() == name.lower()), None)
        if hit:
            return hit
    return None


def validate(raw: dict, prompt: str) -> Brief:
    """Closed sets for every choice, literal hex only, fonts with a Vietnamese subset."""
    pick = lambda v, allowed: v if v in allowed else None  # noqa: E731
    literal_hex = {h.lower() for h in _HEX.findall(prompt)}
    lit = lambda v: v.lower() if isinstance(v, str) and v.lower() in literal_hex else None  # noqa: E731
    accent, background = lit(raw.get("accent")), lit(raw.get("background"))
    sections, seen = [], set()
    for s in raw.get("sections") or []:
        kind = s.get("kind") if isinstance(s, dict) else None
        if kind in SECTION_KINDS and kind not in seen:
            seen.add(kind)
            sections.append(BriefSection(kind=kind, note=_short(s.get("note"), 160) or ""))
    lst = lambda v, n, lim: [x for x in (_short(i, lim) for i in (v or [])[:n] if isinstance(i, str)) if x]  # noqa: E731
    return Brief(
        brand=_short(raw.get("brand"), 40), audience=_short(raw.get("audience"), 160),
        primary_cta=_short(raw.get("primary_cta"), 32), secondary_cta=_short(raw.get("secondary_cta"), 32),
        announcement=_short(raw.get("announcement"), 90),
        theme=pick(raw.get("theme"), {t.value for t in Theme}), layout=pick(raw.get("layout"), {x.value for x in Layout}),
        margins=pick(raw.get("margins"), {d.value for d in Density}), mode=pick(raw.get("mode"), {m.value for m in Mode}),
        accent=accent, background=background, heading_font=_font(raw.get("heading_font")), body_font=_font(raw.get("body_font")),
        nav=lst(raw.get("nav"), 5, 24), usp=lst(raw.get("usp"), 4, 40), categories=lst(raw.get("categories"), 6, 24),
        products=lst(raw.get("products"), 8, 44), quiz_options=lst(raw.get("quiz_options"), 4, 32),
        sections=sections,
    )


def rule_brief(prompt: str) -> Brief:
    """No LLM: what can be read reliably with patterns."""
    brand = re.search(r"(?:thương hiệu|tên)\s+(?:là\s+)?[\"“']([^\"”']{2,40})[\"”']", prompt, re.I)
    hexes = _HEX.findall(prompt)
    accent = None
    for m in _HEX.finditer(prompt):  # the hex written next to "nhấn / CTA / accent"
        if re.search(r"nhấn|cta|accent|nút", prompt[max(0, m.start() - 60):m.start()], re.I):
            accent = m.group(0).lower()
            break
    background = None
    for m in _HEX.finditer(prompt):
        if re.search(r"nền chính|background|màu nền", prompt[max(0, m.start() - 60):m.start()], re.I):
            background = m.group(0).lower()
            break
    found = {f: m.start() for f in VIETNAMESE_FONTS if (m := re.search(rf"\b{re.escape(f)}\b", prompt, re.I))}
    fonts = sorted(found, key=found.get)  # the first font the user named wins ("A hoặc B" -> A)
    serif = {"Playfair Display", "Cormorant Garamond", "Lora", "Fraunces"}
    return Brief(brand=brand.group(1).strip() if brand else None, accent=accent or (hexes[-1].lower() if len(hexes) == 1 else None), background=background,
                 heading_font=next((f for f in fonts if f in serif), None),
                 body_font=next((f for f in fonts if f not in serif), None))


def read_brief(prompt: str, chat: JSONChat | None) -> Brief | None:
    if not prompt or len(prompt) < MIN_BRIEF_CHARS:
        return None
    if chat is None:
        return rule_brief(prompt)
    system = SYSTEM.format(themes=[t.value for t in Theme], layouts=[x.value for x in Layout],
                           densities=[d.value for d in Density], modes=[m.value for m in Mode],
                           kinds={k: v[1] for k, v in SECTION_KINDS.items()})
    try:
        raw = chat.complete_json(system, json.dumps({"brief": prompt}, ensure_ascii=False), max_tokens=2500)
        brief = validate(raw, prompt)
    except (LLMError, ValueError, TypeError, AttributeError) as e:
        log.warning("brief reader failed, using rules: %s", e)
        return rule_brief(prompt)
    if brief.announcement is None and re.search(r"thanh thông báo|announcement bar|top bar khuyến mãi", prompt, re.I):
        brief = brief.model_copy(update={"announcement": "Thanh thông báo trên cùng"})  # text comes from the copy
    rules = rule_brief(prompt)  # literal facts the model may have dropped
    return brief.model_copy(update={k: getattr(rules, k) for k in ("brand", "accent", "background", "heading_font", "body_font")
                                    if getattr(brief, k) is None and getattr(rules, k)})


def mode_from_background(hex_: str) -> str:
    """Light / warm paper / dark from the brief's background colour."""
    parsed = parse_css_color(hex_)
    if parsed is None:
        return Mode.LIGHT.value
    c = parsed[0]
    if c.l < 0.35:
        return Mode.DARK.value
    return Mode.WARM_PAPER.value if c.c > 0.003 and 30 <= c.h <= 110 else Mode.LIGHT.value  # alabaster ≈ C 0.0045


class BriefReader:
    def __init__(self, chat: JSONChat | None):
        self.chat = chat

    def __call__(self, prompt: str) -> Brief | None:
        return read_brief(prompt, self.chat)


def build_brief_reader(env: dict[str, str] | None = None) -> BriefReader:
    cfg = LLMConfig.from_env(env)
    return BriefReader(OpenAICompatChat(cfg.for_role("text")) if cfg else None)
