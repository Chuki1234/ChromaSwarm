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
from chromaswarm.playwright_engine.style_dna_scraper import collect

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
    dna: StyleDNA | None = None


# ------------------------------------------------------------------ classification

def classify(block: dict, index: int, total: int) -> str:
    f = block["features"]
    if index == 0 and (f["nav"] or f["tag"] == "header" or f["role"] == "banner") and f["height"] < 200:
        return "sticky-bar"
    if f["tag"] == "footer" or f["role"] == "contentinfo" or (index == total - 1 and f["links"] >= 4 and not f["h1"]):
        return "footer-columns"
    if f["password"]:
        return "auth"
    if f["accordion"] >= 3:
        return "accordion"
    if f["tablist"]:
        return "tabs"
    if f["h1"]:
        return "full-bleed-image" if f["bg_image"] else "split-7-5"
    if f["scroller"] and f["images"] >= 3:
        return "horizontal-scroller"
    if f["columns"] >= 3 and f["numeric_items"] >= 3 and f["images"] == 0:
        return "inline-metrics"
    if f["columns"] >= 6 and max(f["card_widths"] or [0]) <= 200:
        return "inline-metrics"  # a strip of many small items (logos, stats): closest buildable strip
    if f.get("quotes", 0) >= 2:
        return "testimonials"
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


SECTION_IDS = {"sticky-bar": "site-header", "footer-columns": "site-footer", "accordion": "faq",
               "full-bleed-band": "closing-cta", "auth": "auth"}
NAMES = {"sticky-bar": "Header / Navbar", "split-7-5": "Hero", "full-bleed-image": "Hero banner",
         "inline-metrics": "Dải số liệu", "alternating-z": "Câu chuyện xen kẽ", "bento": "Lưới nổi bật",
         "grid-4": "Lưới sản phẩm", "horizontal-scroller": "Dải danh mục", "accordion": "Hỏi đáp",
         "full-bleed-band": "Dải kêu gọi hành động", "footer-columns": "Footer", "split-5-7": "Khối nội dung",
         "tabs": "Tabs", "auth": "Đăng nhập", "feature-showcase": "Khối tính năng", "testimonials": "Lời khách hàng",
         "text-cards": "Hàng thẻ chữ"}
INTERACTIVE = {
    "sticky-bar": [("nav-logo", "link", "go to home"), ("nav-menu-toggle", "button", "open mobile menu ≤768px")],
    "split-7-5": [("cta-primary", "button", "primary conversion"), ("cta-secondary", "link", "scroll to details")],
    "full-bleed-image": [("cta-primary", "button", "primary conversion")],
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
}


def sections_from_blocks(blocks: list[dict]) -> list[Section]:
    sections: list[Section] = []
    used: set[str] = set()
    for i, block in enumerate(blocks):
        structure = classify(block, i, len(blocks))
        sid = SECTION_IDS.get(structure) or ("hero" if structure in ("split-7-5", "full-bleed-image") else structure)
        if sid in used:
            n = 2
            while f"{sid}-{n}" in used:
                n += 1
            sid = f"{sid}-{n}"
        used.add(sid)
        sections.append(Section(
            id=sid, name=NAMES[structure], structure=structure,
            content=(f"Dựng lại từ section #{i + 1} của trang mẫu ({block['features']['height']}px cao)"
                     + (" — chưa có mẫu đúng kiểu, dựng bằng khối nội dung gần nhất (§2.5 quy tắc 4)"
                        if structure == FALLBACK else "")),
            interactive=[Interactive(id=a, role=b, behavior=c) for a, b, c in INTERACTIVE.get(structure, [])]))
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
    return {"site_title": raw["title"], "description": raw.get("description", ""),
            "sections": {s.id: {**b.get("content", {}), "structure": s.structure}
                         for s, b in zip(_aligned(sections), raw["blocks"])}}


def _aligned(sections: list[Section]) -> list[Section]:
    # sections_from_blocks may prepend a synthetic header; drop it to align with blocks.
    return sections[1:] if sections and sections[0].content.startswith("Thêm vào") else sections


async def analyse(url: str, owned: bool, width: int = 1440, height: int = 900) -> CloneAnalysis:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=45000)
            raw = await page.evaluate(READER_JS, owned)
            dna = analyze(await collect(page, url))
        finally:
            await browser.close()
    return build_analysis(raw, dna, owned)


def build_analysis(raw: dict, dna: StyleDNA, owned: bool) -> CloneAnalysis:
    sections = sections_from_blocks(raw["blocks"])
    notes: list[str] = []
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
    title = raw.get("title") or urlparse(raw.get("url", "")).hostname or "Trang mẫu"
    return CloneAnalysis(url=raw.get("url", ""), title=title[:80], owned=owned, sections=sections, pillars=pillars,
                         content=page_content(raw, sections) if owned else None, notes=notes, dna=dna, **fonts)
