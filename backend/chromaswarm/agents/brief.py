"""Brief reader: the first Creative message is read for every answer it already gives.

A complete prompt must not be asked again; a partial one is asked only what is missing.
Accuracy rule (decision 8): a pillar is taken from the prompt only when the model quotes the
words that state it (`evidence`) and that quote is really in the prompt — otherwise it stays
None and the question is asked. Nothing is guessed from the product type.

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

MIN_LISTED_SECTIONS = 3  # the user really described the page's blocks (else the full blueprint is built)
MIN_PROMPT_CHARS = 12  # "web bán nến" and up: every Creative prompt is read

# Pages a prompt can name (sitemap slugs across domains, consultant.SITEMAPS).
PAGE_WORDS: dict[str, list[str]] = {
    "landing": ["landing page", "landing", "trang đích", "trang chiến dịch", "trang giới thiệu sản phẩm"],
    "home": ["trang chủ", "homepage", "home page", "storefront"],
    "catalog": ["trang danh mục", "trang danh sách sản phẩm", "catalog"],
    "pdp": ["trang chi tiết sản phẩm", "product detail"],
    "pricing": ["trang bảng giá", "pricing page"],
}
# The user said where photos come from: B4 (assets) needs no question.
ASSETS_SAID = re.compile(r"unsplash|pexels|ảnh (?:mẫu|minh h[oọ]a|stock|miễn phí)|chưa có (?:ảnh|hình)|"
                         r"không có (?:ảnh|hình)|dùng ảnh (?:có sẵn|của hệ thống)", re.I)
# Evidence for a tone must name a tone; "tối giản" (minimal) is not "tối" (dark). Checked on accent-folded
# text so "nen toi" typed without diacritics counts too.
TONE_WORDS = re.compile(r"\b(?:sang|toi|den|trang|kem|giay|nga|be|dark|light|nen|mode)\b")
# Evidence for a style must name a style or feeling, not only a colour or background ("nền giấy kem" is a tone).
STYLE_WORDS = re.compile(r"\b(?:phong cach|cam giac|giao dien|style|vibe|sang trong|cao cap|tinh te|toi gian|luxury|"
                         r"premium|elegant|minimal\w*|hien dai|cong nghe|chuan xac|modern|tech|clean|sac sao|"
                         r"than thien|am ap|am cung|gan gui|de thuong|vui ve|tre trung|thu cong|organic|moc mac|"
                         r"ca tinh|tao bao|pha cach|duong pho|noi loan|brutal\w*|bold|nang dong)\b")
# A quote right after a negation states what the user does NOT want ("không muốn nền tối").
NEGATION = re.compile(r"\b(?:khong|dung|chang|tranh|not|no|without|ko|k)\b(?:\s+\w+){0,2}\s*$")

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
    page: str | None = None  # sitemap slug the user asked to build first
    assets_said: bool = False  # the user said where the photos come from (B4 needs no question)
    evidence: dict[str, str] = Field(default_factory=dict)  # field -> the user's words it was read from

    def scope(self) -> str | None:
        """B3 scope in the user's words: audience + main action, when both are known."""
        if self.audience and self.primary_cta:
            return f"{self.audience.rstrip('. ')}. Hành động quan trọng nhất: {self.primary_cta}"
        return None

    def listed_sections(self) -> bool:
        """The user listed the page's content blocks themselves (a hero alone is not a page plan)."""
        return len([x for x in self.sections if x.kind != "hero"]) >= MIN_LISTED_SECTIONS

    def summary(self) -> list[str]:
        out = []
        if self.brand:
            out.append(f"thương hiệu {self.brand}")
        if self.accent:
            out.append(f"màu nhấn {self.accent}")
        if self.heading_font:
            out.append(f"font tiêu đề {self.heading_font}")
        if self.listed_sections():
            out.append(f"{len(self.sections)} section theo đúng thứ tự bạn mô tả")
        return out


SYSTEM = """Bạn đọc một bản mô tả (brief) thiết kế trang web tiếng Việt và trích xuất thông tin có cấu trúc.
Chỉ ghi những gì người dùng ĐÃ VIẾT; điều gì không có thì để null hoặc [] — tuyệt đối không bịa.
Các chuỗi giữ nguyên lời người dùng, ngắn gọn.
- theme (cảm giác chủ đạo) chọn một trong: {themes} hoặc null.
  Gợi ý: "quiet luxury", cao cấp, tinh tế, tối giản (minimalist), kiểu Aesop / tạp chí -> editorial-luxury;
  hiện đại, công nghệ, chính xác, SaaS -> precision-tech; thân thiện, gần gũi, vui vẻ, thủ công ấm cúng -> warm-organic;
  cá tính, táo bạo, đường phố -> neo-brutalist. Khi có cả "luxury" và "organic", ưu tiên editorial-luxury.
- layout chọn một trong: {layouts} hoặc null. Gợi ý: ảnh lớn, ảnh tràn màn hình, hình ảnh là chính -> visual-first;
  kể chuyện, dẫn dắt từng bước, câu chuyện thương hiệu -> narrative; nhiều sản phẩm, lưới sản phẩm, danh mục -> catalog.
- margins (độ thoáng) chọn một trong: {densities} hoặc null. Gợi ý: thoáng, rộng rãi, nhiều khoảng trắng -> airy;
  vừa phải, cân bằng -> balanced; gọn, xếp gọn, nhiều thông tin, chặt -> dense.
- Người dùng có thể viết KHÔNG DẤU ("nen toi" = "nền tối", "phong cach hien dai" = "phong cách hiện đại") hoặc tiếng Anh.
- Câu phủ định ("không muốn nền tối", "đừng làm kiểu cá tính") là điều người dùng KHÔNG muốn: không lấy giá trị đó.
- mode (tông nền) chọn một trong: {modes} hoặc null.
- accent: mã hex màu nhấn / màu nút chính nếu người dùng ghi mã. background: mã hex màu nền chính nếu có.
- heading_font / body_font: tên font người dùng nêu (lấy font đầu tiên nếu ghi "A hoặc B").
- sections: CHỈ khi người dùng tự liệt kê các khối của trang; theo ĐÚNG THỨ TỰ họ viết (không tính header và footer).
  Người dùng không liệt kê khối nào thì sections = [] (không tự nghĩ ra).
  mỗi khối có kind thuộc {kinds} và note là mô tả ngắn của người dùng.
- nav: các mục menu điều hướng người dùng liệt kê (tối đa 5).
- usp: các cam kết / lợi ích ngắn (tối đa 4). categories: danh mục sản phẩm (tối đa 6).
- products: tên sản phẩm cụ thể nếu có. quiz_options: các lựa chọn của khối tương tác (ví dụ các loại da).
- announcement: nội dung thanh thông báo nếu có.
- page: trang muốn làm trước nếu người dùng nói rõ, thuộc {pages} hoặc null.
- evidence: với MỖI trường theme, layout, margins, mode, audience, primary_cta, page mà bạn điền,
  chép NGUYÊN VĂN 2–12 từ trong brief là căn cứ. Không có câu chữ nói rõ thì để cả giá trị lẫn evidence là null:
  KHÔNG suy đoán từ loại sản phẩm (bán nến KHÔNG có nghĩa là "ấm áp" nếu người dùng không nói).
  "tối giản" là phong cách tối giản, KHÔNG phải tông nền tối.
- audience: chỉ khi người dùng mô tả khách hàng (tuổi, nghề, nhóm người...). primary_cta: đúng chữ nút / hành động
  người dùng muốn khách bấm (ví dụ "Đặt mua"), lấy nguyên văn.
Trả về JSON: {{"brand", "audience", "primary_cta", "secondary_cta", "announcement", "theme", "layout",
"margins", "mode", "accent", "background", "heading_font", "body_font", "nav": [], "usp": [], "categories": [], "products": [],
"quiz_options": [], "sections": [{{"kind": "", "note": ""}}], "page": null,
"evidence": {{"theme": null, "layout": null, "margins": null, "mode": null, "audience": null, "primary_cta": null, "page": null}}}}"""


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


def _norm(text: str) -> str:
    """Accent-folded, punctuation-free, single-spaced: quotes match despite typing differences."""
    from chromaswarm.agents.consultant import fold
    return " ".join(re.sub(r"[^0-9a-z]+", " ", fold(text or "")).split())


def in_prompt(quote, prompt: str) -> bool:
    q = _norm(quote) if isinstance(quote, str) else ""
    return len(q) >= 3 and f" {q} " in f" {_norm(prompt)} "


def _supported(field: str, value, raw: dict, prompt: str):
    """Keep a pillar value only when its quoted evidence is really in the prompt."""
    if value is None:
        return None
    quote = (raw.get("evidence") or {}).get(field)
    if not in_prompt(quote, prompt):
        log.info("brief: %s=%r dropped (evidence %r not in the prompt)", field, value, quote)
        return None
    if field == "mode" and not TONE_WORDS.search(_norm(quote).replace("toi gian", "")):
        return None
    if field == "theme" and not STYLE_WORDS.search(_norm(quote)):
        log.info("brief: theme=%r dropped (%r names no style)", value, quote)
        return None
    if negated(quote, prompt):
        log.info("brief: %s=%r dropped (negated: %r)", field, value, quote)
        return None
    return value


def negated(quote: str, prompt: str) -> bool:
    """The quote follows "không / đừng / tránh ..." in the prompt: the user rejects it."""
    q, p = _norm(quote), f" {_norm(prompt)} "
    i = p.find(f" {q} ")
    return i >= 0 and bool(NEGATION.search(p[:i]))


def validate(raw: dict, prompt: str) -> Brief:
    """Closed sets for every choice, evidence for every pillar, literal hex only, Vietnamese fonts."""
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
    ev = lambda f, v: _supported(f, v, raw, prompt)  # noqa: E731
    cta = _short(raw.get("primary_cta"), 32)
    if cta and not in_prompt(cta, prompt):  # the button label must be the user's own words
        cta = None
    return Brief(
        brand=_short(raw.get("brand"), 40), audience=ev("audience", _short(raw.get("audience"), 160)),
        primary_cta=ev("primary_cta", cta), secondary_cta=_short(raw.get("secondary_cta"), 32),
        announcement=_short(raw.get("announcement"), 90),
        theme=ev("theme", pick(raw.get("theme"), {t.value for t in Theme})),
        layout=ev("layout", pick(raw.get("layout"), {x.value for x in Layout})),
        margins=ev("margins", pick(raw.get("margins"), {d.value for d in Density})),
        mode=ev("mode", pick(raw.get("mode"), {m.value for m in Mode})),
        page=ev("page", pick(raw.get("page"), set(PAGE_WORDS))),
        evidence={k: v for k, v in (raw.get("evidence") or {}).items() if isinstance(v, str) and in_prompt(v, prompt)},
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


def _literal_facts(prompt: str) -> dict:
    """Facts read with exact patterns, with or without an LLM: page, photo source, colour name, CTA."""
    from chromaswarm.agents.consultant import COLOR_NAMES, extract_cta
    low = prompt.lower()
    # A colour name counts only after "màu" ("màu chủ đạo xanh rêu"): "cà phê nâu" is a drink, not a brand colour.
    names = "|".join(re.escape(n) for n in sorted(COLOR_NAMES, key=len, reverse=True) if n != "đen")
    m = re.search(rf"\bmàu\s+(?:(?:chủ đạo|nhấn|thương hiệu|chính)\s+)?(?:là\s+)?({names})\b", low)
    page = next((slug for slug, words in PAGE_WORDS.items()
                 if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)), None)
    return {"page": page, "assets_said": bool(ASSETS_SAID.search(prompt)),
            "named_accent": COLOR_NAMES[m.group(1)] if m else None, "cta": extract_cta(prompt)}


def read_brief(prompt: str, chat: JSONChat | None) -> Brief | None:
    if not prompt or len(prompt.strip()) < MIN_PROMPT_CHARS:
        return None
    facts = _literal_facts(prompt)
    if chat is None:
        b = rule_brief(prompt)
        return b.model_copy(update={"page": facts["page"], "assets_said": facts["assets_said"],
                                    "primary_cta": facts["cta"], "accent": b.accent or facts["named_accent"]})
    system = SYSTEM.format(themes=[t.value for t in Theme], layouts=[x.value for x in Layout],
                           densities=[d.value for d in Density], modes=[m.value for m in Mode],
                           kinds={k: v[1] for k, v in SECTION_KINDS.items()}, pages=list(PAGE_WORDS))
    try:
        raw = chat.complete_json(system, json.dumps({"brief": prompt}, ensure_ascii=False), max_tokens=2500)
        brief = validate(raw, prompt)
    except (LLMError, ValueError, TypeError, AttributeError) as e:
        log.warning("brief reader failed, using rules: %s", e)
        return rule_brief(prompt)
    if brief.announcement is None and re.search(r"thanh thông báo|announcement bar|top bar khuyến mãi", prompt, re.I):
        brief = brief.model_copy(update={"announcement": "Thanh thông báo trên cùng"})  # text comes from the copy
    rules = rule_brief(prompt)  # literal facts the model may have dropped
    update = {k: getattr(rules, k) for k in ("brand", "accent", "background", "heading_font", "body_font")
              if getattr(brief, k) is None and getattr(rules, k)}
    update["assets_said"] = facts["assets_said"]
    if brief.page is None and facts["page"]:
        update["page"] = facts["page"]
    if brief.accent is None and not update.get("accent") and facts["named_accent"]:
        update["accent"] = facts["named_accent"]  # "màu xanh rêu" -> its hex (consultant.COLOR_NAMES)
    if brief.primary_cta is None and facts["cta"]:
        update["primary_cta"] = facts["cta"]  # "muốn họ bấm Đặt mua"
    return brief.model_copy(update=update)


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
