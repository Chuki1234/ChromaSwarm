"""Clone mode: read a reference page into a ChromaSwarm plan.

* Structure (always): the page's top-level sections, each classified onto one of
  the Developer department's section structures, in the page's own order.
* Style (always): the existing Style DNA scraper (aggregates only) -> the 5 pillars
  (theme, layout, colour, density) and the fonts, when they ship Vietnamese.
* Content (only when the user confirmed the site is theirs): headings, paragraphs,
  button labels, card items, FAQ pairs and image URLs per section.

Without ownership the content never leaves the page (the JS does not return it),
so a structure clone of someone else's site carries the user's own copy.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from pydantic import BaseModel

from chromaswarm.agents.planner import Interactive, Section
from chromaswarm.engines.color import parse_css_color, to_hex
from chromaswarm.engines.palette import Mode
from chromaswarm.engines.presets import VIETNAMESE_FONTS, Layout, Theme
from chromaswarm.engines.spacing import Density
from chromaswarm.engines.style_dna import StyleDNA, analyze
from chromaswarm.playwright_engine.style_dna_scraper import collect, open_settled

READER_JS = Path(__file__).with_name("reader.js").read_text(encoding="utf-8")


class CloneAnalysis(BaseModel):
    url: str
    title: str
    owned: bool
    sections: list[Section]
    pillars: dict[str, str]  # theme, layout, color, margins derived from the reference
    heading_font: str | None = None  # kept only when it ships a Vietnamese subset
    body_font: str | None = None
    content: dict | None = None  # per-section copy, owned sites only
    notes: list[str] = []
    content_width: int | None = None  # measured column width (8pt) when the reference is a narrow single column
    dna: StyleDNA | None = None


# ------------------------------------------------------------------ classification

def classify(block: dict, index: int, total: int) -> str:
    f = block["features"]
    is_header = f["tag"] in ("header", "nav") or f["role"] == "banner"
    if index <= 1 and (f["nav"] or is_header) and (f["height"] < 200 or (is_header and f["height"] < 360)):
        return "sticky-bar"  # index 1: a promo strip may sit above the navigation; tall headers (logo + avatar) too
    if f["tag"] == "footer" or f["role"] == "contentinfo" or (index == total - 1 and f["links"] >= 4 and not f["h1"]):
        return "footer-columns"
    if f["password"]:
        return "auth"
    if f["accordion"] >= 3:
        return "accordion"
    if f["tablist"]:
        return "tabs"
    if f["h1"]:
        if f["bg_image"]:
            return "full-bleed-image"
        # No visual in the hero at all: a text-only intro (headline, lead, CTA or signup), not a split.
        return "split-7-5" if f["images"] or f["big_image"] else "hero-text"
    if f["scroller"] and f["images"] >= 3:
        return "horizontal-scroller"
    if f.get("logos", 0) >= 3 and f["text_len"] < 80 and f["height"] < 280 and f["numeric_items"] < 3:
        return "logo-strip"  # "as featured on" / client logos: a short row of marks with almost no text
    if f["columns"] >= 3 and f["numeric_items"] >= 3 and f["images"] == 0:
        return "inline-metrics"
    if f["columns"] >= 6 and max(f["card_widths"] or [0]) <= 200:
        return "inline-metrics"  # a strip of many small items (logos, stats): closest buildable strip
    if f.get("quotes", 0) >= 2:
        return "testimonials"
    if f.get("rows", 0) >= 3 and f["images"] == 0 and f.get("row_items_with_img", 0) == 0:
        return "list-rows"  # a stacked list of one-line entries (posts + dates, work history)
    widths = f["card_widths"]
    uneven = bool(widths) and max(widths) > 1.6 * min(widths)
    with_visual = f.get("row_items_with_img", 0)  # items in one row that carry an image / illustration
    # A row of 3+ cards with visuals: a product grid when it shows prices, feature cards (bento) otherwise.
    if f["columns"] >= 3 and (f["images"] >= 3 or with_visual >= 3):
        return "grid-4" if f["prices"] >= 2 else "bento"
    if f["columns"] >= 2 and with_visual >= 2 and uneven and f["images"] >= 3:
        return "bento"
    if f["bg_differs"] and f["buttons"] >= 1 and f["text_len"] < 300:
        return "full-bleed-band"
    actions = f["buttons"] + f["links"]
    if index >= total - 3 and f["headings"] >= 1 and f["text_len"] < 300 and 1 <= actions <= 6 and f["height"] < 500:
        return "full-bleed-band"  # a short closing call to action near the end, even without its own colour
    if f["columns"] == 2 and f["images"] >= 2:
        return "alternating-z"
    if f["headings"] >= 1 and f["height"] >= 700 and with_visual < 3:
        return "feature-showcase"  # a tall section built around one heading and a large visual / mockup
    if f["columns"] >= 3 and f["images"] == 0 and with_visual == 0 and f["text_len"] >= 200:
        return "text-cards"
    return FALLBACK


FALLBACK = "split-5-7"  # no closer buildable structure: a plain content block
HERO_STRUCTURES = ("split-7-5", "full-bleed-image", "hero-text")
# A text-only hero with an email field (newsletter / waitlist signup) instead of a CTA button.
HERO_SIGNUP = [("hero-email", "input", "email validation"), ("hero-signup", "button", "success / error state")]
NARROW_MAX = 1100  # content narrower than this is a deliberate single column, kept in the rebuild


SECTION_IDS = {"sticky-bar": "site-header", "footer-columns": "site-footer", "accordion": "faq",
               "full-bleed-band": "closing-cta", "auth": "auth"}
NAMES = {"sticky-bar": "Header / Navbar", "split-7-5": "Hero", "full-bleed-image": "Hero banner", "hero-text": "Hero chữ",
         
         "inline-metrics": "Dải số liệu", "alternating-z": "Câu chuyện xen kẽ", "bento": "Lưới nổi bật",
         "grid-4": "Lưới sản phẩm", "horizontal-scroller": "Dải danh mục", "accordion": "Hỏi đáp",
         "full-bleed-band": "Dải kêu gọi hành động", "footer-columns": "Footer", "split-5-7": "Khối nội dung",
         "tabs": "Tabs", "auth": "Đăng nhập", "feature-showcase": "Khối tính năng", "testimonials": "Lời khách hàng",
         "text-cards": "Hàng thẻ chữ", "gallery": "Thư viện hình ảnh", "logo-strip": "Dải logo",
         "list-rows": "Danh sách dòng"}
INTERACTIVE = {
    "sticky-bar": [("nav-logo", "link", "go to home"), ("nav-menu-toggle", "button", "open mobile menu ≤768px")],
    "split-7-5": [("cta-primary", "button", "primary conversion"), ("cta-secondary", "link", "scroll to details")],
    "full-bleed-image": [("cta-primary", "button", "primary conversion")],
    "hero-text": [("cta-primary", "button", "primary conversion")],
    "bento": [("collection-card", "card", "hover lift + quick view"), ("quick-view-trigger", "modal-trigger", "open modal")],
    "grid-4": [("product-card", "card", "hover"), ("add-to-cart", "button", "add item")],
    "horizontal-scroller": [("category-card", "card", "navigate")],
    "accordion": [("faq-item", "button", "expand / collapse")],
    "full-bleed-band": [("cta-closing", "button", "same action as cta-primary")],
    "footer-columns": [("footer-newsletter-input", "input", "email validation"),
                       ("footer-newsletter-submit", "button", "success / error state")],
    "tabs": [("main-tab", "tab", "switch panel")],
    "auth": [("email-input", "input", "validate"), ("submit-login", "button", "loading + error states")],
    "feature-showcase": [("more", "link", "learn more")],
    "list-rows": [("list-row", "link", "open entry"), ("list-more", "button", "show all rows")],
}


def reading_order(blocks: list[dict], viewport_w: int = 1440) -> tuple[list[dict], list[str]]:
    """Two-column pages (content + side column): the side column's h1 block is the page's hero, so it
    moves up right after the navigation, absorbing the image that sat beside it."""
    notes: list[str] = []
    f = lambda b: b["features"]  # noqa: E731
    hero = next((b for b in blocks if f(b)["h1"]), None)
    if not hero or "left" not in f(hero):
        return blocks, notes
    in_side_column = f(hero)["left"] > viewport_w * 0.5 and f(hero)["width"] < viewport_w * 0.45
    first_content = next((i for i, b in enumerate(blocks) if not (f(b)["nav"] or f(b)["height"] < 80)), 0)
    if not in_side_column or blocks.index(hero) <= first_content:
        return blocks, notes
    rest = [b for b in blocks if b is not hero]
    beside = next((b for b in rest if abs(f(b)["top"] - f(hero)["top"]) < 120 and f(b)["text_len"] < 30
                   and f(b)["images"] >= 1 and f(b)["left"] < viewport_w * 0.5), None)
    if beside:
        rest.remove(beside)  # the hero template carries its own visual
        hero = {**hero, "features": {**f(hero), "images": f(hero)["images"] + f(beside)["images"]}}
    rest.insert(first_content, hero)
    notes.append("Trang mẫu có cột bên (sidebar): khối tiêu đề chính được đưa lên làm hero, "
                 "nội dung cột bên xếp sau nội dung chính.")
    return rest, notes


def _media_only(block: dict) -> bool:
    """A block that is essentially pictures: screenshots, a photo row, a figure."""
    f = block["features"]
    own_text = f["text_len"] - f.get("lead_text", 0)
    # A heading with its own sentence and a link around a picture is a feature block, not a gallery tile.
    feature = f["headings"] >= 1 and own_text >= 40 and f["links"] + f["buttons"] >= 1
    return (f["images"] >= 1 and own_text < 120 and not feature and not f["h1"] and not f["nav"]
            and f["tag"] not in ("footer", "header") and not f.get("quotes"))


def group_blocks(blocks: list[dict]) -> list[tuple[list[int], str | None]]:
    """Consecutive picture-only blocks form one gallery (e.g. a theme's screenshot grid);
    every other block stands alone and is classified later."""
    groups: list[tuple[list[int], str | None]] = []
    run: list[int] = []

    def flush():
        if len(run) >= 2 or (run and blocks[run[0]]["features"]["images"] >= 4):
            groups.append((list(run), "gallery"))
        else:
            groups.extend(([i], None) for i in run)
        run.clear()

    for i, b in enumerate(blocks):
        # a block that brings its own heading (lead text) starts a new gallery
        if _media_only(b) and not (run and b["features"].get("lead_text")):
            run.append(i)
            continue
        flush()
        if _media_only(b):
            run.append(i)
        else:
            groups.append(([i], None))
    flush()
    return groups


def sections_from_blocks(blocks: list[dict]) -> list[Section]:
    sections: list[Section] = []
    used: set[str] = set()
    for idx, forced in group_blocks(blocks):
        i, block = idx[0], blocks[idx[0]]
        structure = forced or classify(block, i, len(blocks))
        sid = SECTION_IDS.get(structure) or ("hero" if structure in HERO_STRUCTURES else structure)
        if sid in used:
            n = 2
            while f"{sid}-{n}" in used:
                n += 1
            sid = f"{sid}-{n}"
        used.add(sid)
        images = sum(blocks[j]["features"]["images"] for j in idx)
        if structure == "logo-strip":  # logos are often small <svg>/<img> marks below the media size cut
            images = max(images, block["features"].get("logos", 0))
        where = (f"section #{i + 1}" if len(idx) == 1 else f"section #{i + 1}–#{idx[-1] + 1} (gộp {len(idx)} khối ảnh liên tiếp)")
        sections.append(Section(
            id=sid, name=NAMES[structure], structure=structure, count=images, sources=idx,
            content=(f"Dựng lại từ {where} của trang mẫu ({sum(blocks[j]['features']['height'] for j in idx)}px cao)"
                     + (" — chưa có mẫu đúng kiểu, dựng bằng khối nội dung gần nhất (§2.5 quy tắc 4)"
                        if structure == FALLBACK else "")),
            interactive=[Interactive(id=a, role=b, behavior=c) for a, b, c in
                         (HERO_SIGNUP if structure == "hero-text" and block["features"]["inputs"] else INTERACTIVE.get(structure, []))]))
    if not any(s.structure == "sticky-bar" for s in sections):
        sections.insert(0, Section(id="site-header", name="Header / Navbar", structure="sticky-bar",
                                   content="Thêm vào: trang mẫu không có header rõ ràng",
                                   interactive=[Interactive(id=a, role=b, behavior=c) for a, b, c in INTERACTIVE["sticky-bar"]]))
    return sections


# ------------------------------------------------------------------ style -> pillars

SERIF_HINTS = ("serif", "playfair", "garamond", "times", "georgia", "lora", "fraunces", "cormorant", "merriweather")


def derive_pillars(dna: StyleDNA, sections: list[Section], heading_font: str | None) -> dict[str, str]:
    radius = dna.radius_median or 0
    serif = bool(heading_font) and any(h in heading_font.lower() for h in SERIF_HINTS)
    if radius < 2 and dna.separation == "borders" and not serif:
        theme = Theme.NEO_BRUTALIST
    elif serif:
        theme = Theme.EDITORIAL_LUXURY
    elif radius >= 12:
        theme = Theme.WARM_ORGANIC
    else:
        theme = Theme.PRECISION_TECH
    structures = [s.structure for s in sections]
    if sum(s in ("grid-4", "horizontal-scroller", "bento") for s in structures) >= 2:
        layout = Layout.CATALOG
    elif "full-bleed-image" in structures or structures.count("alternating-z") or "bento" in structures:
        layout = Layout.VISUAL_FIRST
    else:
        layout = Layout.NARRATIVE
    if dna.is_dark:
        mode = Mode.DARK
    elif dna.neutral_temperature == "warm":
        mode = Mode.WARM_PAPER
    else:
        mode = Mode.LIGHT
    color = mode.value
    if dna.accents:
        parsed = parse_css_color(dna.accents[0].css)
        if parsed:
            color = f"{mode.value} {to_hex(parsed[0]).lower()}"
    density = {"airy": Density.AIRY, "dense": Density.DENSE}.get(dna.density, Density.BALANCED)
    return {"theme": theme.value, "layout": layout.value, "color": color, "margins": density.value}


def page_content(raw: dict, sections: list[Section]) -> dict:
    """Owned sites: the copy of each section, keyed by our section id."""
    blocks = raw["blocks"]

    def merged(idx: list[int]) -> dict:
        parts = [blocks[j].get("content", {}) for j in idx]
        if not parts:
            return {}
        out = dict(parts[0])
        out["images"] = [u for p in parts for u in p.get("images", [])]
        return out

    return {"site_title": raw["title"], "description": raw.get("description", ""),
            "sections": {s.id: {**merged(s.sources), "structure": s.structure} for s in sections if s.sources}}


def _aligned(sections: list[Section]) -> list[Section]:
    # sections_from_blocks may prepend a synthetic header; drop it to align with blocks.
    return sections[1:] if sections and sections[0].content.startswith("Thêm vào") else sections


async def analyse(url: str, owned: bool, width: int = 1440, height: int = 900) -> CloneAnalysis:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await open_settled(page, url)
            raw = await page.evaluate(READER_JS, owned)
            dna = analyze(await collect(page, url))
        finally:
            await browser.close()
    return build_analysis(raw, dna, owned)


def prepare_blocks(raw: dict) -> tuple[list[dict], list[str]]:
    """The blocks sections are built from (Section.sources index into this list)."""
    blocks = [b for b in raw["blocks"] if not (b["features"]["height"] < 60 and not b["features"]["nav"]
                                                and b["features"]["index"] == 0)]  # a thin promo strip on top
    return reading_order(blocks)


def build_analysis(raw: dict, dna: StyleDNA, owned: bool) -> CloneAnalysis:
    blocks, notes = prepare_blocks(raw)
    raw = {**raw, "blocks": blocks}
    sections = sections_from_blocks(blocks)
    fonts = {}
    for key in ("heading_font", "body_font"):
        family = raw.get(key)
        if family and family in VIETNAMESE_FONTS:
            fonts[key] = family
        elif family:
            note = f"Font {family!r} của trang mẫu chưa xác nhận có bộ chữ tiếng Việt; dùng font của preset."
            if note not in notes:
                notes.append(note)
    pillars = derive_pillars(dna, sections, raw.get("heading_font"))
    measured = raw.get("content_width") or 0
    content_width = round(measured / 8) * 8 if 480 <= measured < NARROW_MAX else None
    if content_width:
        notes.append(f"Trang mẫu là một cột hẹp ở giữa (~{content_width}px): bản dựng giữ đúng bề rộng cột này.")
    title = raw.get("title") or urlparse(raw.get("url", "")).hostname or "Trang mẫu"
    return CloneAnalysis(url=raw.get("url", ""), title=title[:80], owned=owned, sections=sections, pillars=pillars,
                         content=page_content(raw, sections) if owned else None, notes=notes, dna=dna,
                         content_width=content_width, **fonts)


# ------------------------------------------------------------------ what the user is told

_EXACT = re.compile(r"100\s*%|giống\s+(hệt|hoàn\s+toàn|y\s+hệt|y\s+chang|y\s+nguyên)|\by\s+(hệt|chang|nguyên)\b"
                    r"|(copy|sao\s+chép|clone|chép)\s+(y|nguyên|toàn\s+bộ|hết|100)|giống\s+100", re.IGNORECASE)


def wants_exact_copy(text: str) -> bool:
    """The description asks for an exact copy (text, images, brand), not just the structure."""
    return bool(_EXACT.search(text or ""))


def clone_limits(a: CloneAnalysis) -> list[str]:
    """What the rebuild will not match, said before the plan so the user is never surprised."""
    limits = [f"font {m.group(1)} được thay bằng font có tiếng Việt"
              for n in a.notes if (m := re.match(r"Font '(.+?)'", n))]
    approx = sum("§2.5 quy tắc 4" in s.content for s in a.sections)
    if approx:
        limits.append(f"{approx} section chưa có mẫu đúng kiểu, dựng bằng khối nội dung gần nhất")
    limits.append("hiệu ứng riêng của trang (hover, chuyển động khi cuộn, carousel) chưa được chép — "
                  "bản dựng dùng hiệu ứng có sẵn")
    if not a.owned:
        limits.append("chữ, ảnh và tên thương hiệu là của bạn (để trống chỗ trong file nội dung)")
    return limits
