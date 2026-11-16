"""Clone fidelity: how close a rebuilt page is to its reference, as one 0-100 score with parts.

Both pages are read with the same Clone reader and Style DNA scraper (layout measurements only, no
content), so the score compares like with like:

- structure   (35) the section sequence, exact kind and kind family (any hero, any card row, ...)
- proportions (25) how the page height is shared out between matched sections
- length      (10) total page height
- width       (10) measured content width (narrow single column vs full width)
- style       (20) page surface, text and accent colours (OKLab distance) and base font size

Pure scoring (`score`) is separate from the browser reads (`snapshot_page`, `snapshot_url`).
"""

from __future__ import annotations

import math
from difflib import SequenceMatcher

from playwright.async_api import Page, async_playwright
from pydantic import BaseModel

from chromaswarm.clone.reader import READER_JS, prepare_blocks, sections_from_blocks
from chromaswarm.engines.color import parse_css_color
from chromaswarm.engines.style_dna import StyleDNA, analyze
from chromaswarm.playwright_engine.style_dna_scraper import collect, open_settled

WEIGHTS = {"structure": 35, "proportions": 25, "length": 10, "width": 10, "style": 20}

# Kinds that play the same role on a page: a wrong kind inside the right family earns half credit.
FAMILIES = {
    "hero": {"split-7-5", "full-bleed-image", "hero-text"},
    "cards": {"bento", "grid-4", "text-cards", "horizontal-scroller", "sidebar-grid-4"},
    "media": {"gallery", "feature-showcase", "alternating-z"},
    "strip": {"inline-metrics", "logo-strip"},
    "text": {"split-5-7", "list-rows", "accordion", "tabs"},
    "cta": {"full-bleed-band"},
}
FAMILY_OF = {kind: fam for fam, kinds in FAMILIES.items() for kind in kinds}

COLOUR_JND = 0.2  # OKLab distance at which a colour earns no credit (0.02 is about one noticeable step)


class SectionShape(BaseModel):
    kind: str
    height: int


class Snapshot(BaseModel):
    url: str
    sections: list[SectionShape]
    page_height: int
    content_width: int | None
    dna: StyleDNA


class SectionMatch(BaseModel):
    original: SectionShape | None
    clone: SectionShape | None
    match: str  # exact | family | missing | extra


class Fidelity(BaseModel):
    total: float  # 0-100
    parts: dict[str, float]  # each 0-1
    sections: list[SectionMatch]
    notes: list[str]

    def summary(self) -> str:
        parts = " · ".join(f"{k} {v * 100:.0f}%" for k, v in self.parts.items())
        return f"{self.total:.0f}/100 ({parts})"


# ------------------------------------------------------------------ reading

def snapshot_from(raw: dict, dna: StyleDNA, page_height: int) -> Snapshot:
    blocks, _ = prepare_blocks(raw)
    shapes = [SectionShape(kind=s.structure, height=sum(blocks[i]["features"]["height"] for i in s.sources))
              for s in sections_from_blocks(blocks) if s.sources]  # a synthetic header has no sources
    return Snapshot(url=raw.get("url", ""), sections=shapes, page_height=page_height,
                    content_width=raw.get("content_width"), dna=dna)


async def snapshot_page(page: Page) -> Snapshot:
    """Read a page that is already open and settled."""
    raw = await page.evaluate(READER_JS, False)
    dna = analyze(await collect(page, page.url))
    height = await page.evaluate("document.scrollingElement.scrollHeight")
    return snapshot_from(raw, dna, int(height))


async def snapshot_url(url: str, width: int = 1440, height: int = 900, screenshot_to: str | None = None) -> Snapshot:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await open_settled(page, url)
            if screenshot_to:
                await page.screenshot(path=screenshot_to, full_page=True)
            return await snapshot_page(page)
        finally:
            await browser.close()


# ------------------------------------------------------------------ scoring

def _ratio(a: float | None, b: float | None) -> float:
    if not a or not b:
        return 1.0 if not a and not b else 0.5
    return min(a, b) / max(a, b)


def _oklab(css: str) -> tuple[float, float, float] | None:
    parsed = parse_css_color(css)
    if not parsed:
        return None
    c = parsed[0]
    return c.l, c.c * math.cos(math.radians(c.h)), c.c * math.sin(math.radians(c.h))


def colour_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 1.0 if not a and not b else 0.5  # one page has no accent at all
    la, lb = _oklab(a), _oklab(b)
    if not la or not lb:
        return 0.5
    return max(0.0, 1 - math.dist(la, lb) / COLOUR_JND)


def _top(shares) -> str | None:
    return shares[0].css if shares else None


def align(original: list[SectionShape], clone: list[SectionShape]) -> list[SectionMatch]:
    """Pair sections in order (by family first, so a wrong kind in the right place still pairs)."""
    fam = lambda xs: [FAMILY_OF.get(s.kind, s.kind) for s in xs]  # noqa: E731
    out: list[SectionMatch] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(a=fam(original), b=fam(clone), autojunk=False).get_opcodes():
        if op == "equal":
            out += [SectionMatch(original=o, clone=c, match="exact" if o.kind == c.kind else "family")
                    for o, c in zip(original[i1:i2], clone[j1:j2])]
            continue
        # replace / delete / insert: the reference's sections are missing, the clone's are extra
        out += [SectionMatch(original=o, clone=None, match="missing") for o in original[i1:i2]]
        out += [SectionMatch(original=None, clone=c, match="extra") for c in clone[j1:j2]]
    return out


def score(original: Snapshot, clone: Snapshot) -> Fidelity:
    matches = align(original.sections, clone.sections)
    n = max(len(original.sections), len(clone.sections), 1)
    exact = sum(m.match == "exact" for m in matches)
    family = sum(m.match == "family" for m in matches)
    structure = (exact + 0.5 * family) / n

    # Proportions: total variation distance between the two height distributions, where a section
    # with no partner counts with its whole share.
    to = sum(s.height for s in original.sections) or 1
    tc = sum(s.height for s in clone.sections) or 1
    tv = 0.0
    for m in matches:
        a = m.original.height / to if m.original else 0.0
        b = m.clone.height / tc if m.clone else 0.0
        tv += abs(a - b)
    proportions = max(0.0, 1 - tv / 2)

    length = _ratio(original.page_height, clone.page_height)
    width = _ratio(original.content_width, clone.content_width)
    od, cd = original.dna, clone.dna
    style_parts = [
        colour_similarity(_top(od.surfaces), _top(cd.surfaces)),
        colour_similarity(_top(od.text_colors), _top(cd.text_colors)),
        colour_similarity(_top(od.accents), _top(cd.accents)),
        _ratio(od.base_font_px, cd.base_font_px),
    ]
    style = sum(style_parts) / len(style_parts)

    parts = {"structure": structure, "proportions": proportions, "length": length, "width": width, "style": style}
    total = sum(WEIGHTS[k] * v for k, v in parts.items())  # weights sum to 100
    notes = []
    missing = [m.original.kind for m in matches if m.match == "missing" and m.original]
    extra = [m.clone.kind for m in matches if m.match == "extra" and m.clone]
    if missing:
        notes.append(f"Thiếu so với trang gốc: {', '.join(missing)}")
    if extra:
        notes.append(f"Thừa so với trang gốc: {', '.join(extra)}")
    if family:
        notes.append(f"{family} section đúng vai trò nhưng khác kiểu")
    if length < 0.85:
        notes.append(f"Độ dài trang lệch: gốc {original.page_height}px, bản dựng {clone.page_height}px")
    if width < 0.85:
        notes.append(f"Bề rộng nội dung lệch: gốc {original.content_width}px, bản dựng {clone.content_width}px")
    if style_parts[2] < 0.6:
        notes.append("Màu nhấn khác trang gốc")
    return Fidelity(total=round(total, 1), parts={k: round(v, 3) for k, v in parts.items()},
                    sections=matches, notes=notes)


def render_markdown(f: Fidelity, original_url: str) -> str:
    rows = [f"| {i + 1} | {m.original.kind if m.original else '—'} | {m.original.height if m.original else ''} "
            f"| {m.clone.kind if m.clone else '—'} | {m.clone.height if m.clone else ''} | {m.match} |"
            for i, m in enumerate(f.sections)]
    return "\n".join([
        "# FIDELITY.md — độ giống trang mẫu",
        "",
        f"- Trang gốc: {original_url}",
        f"- **Điểm: {f.total:.0f}/100**",
        "",
        "| Phần | Trọng số | Đạt |",
        "| :--- | ---: | ---: |",
        *[f"| {k} | {WEIGHTS[k]} | {v * 100:.0f}% |" for k, v in f.parts.items()],
        "",
        *([f"- {n}" for n in f.notes] or ["- Không có chênh lệch đáng kể."]),
        "",
        "| # | Gốc | Cao (px) | Bản dựng | Cao (px) | Khớp |",
        "| ---: | :--- | ---: | :--- | ---: | :--- |",
        *rows,
        "",
        "Cả hai trang được đọc bằng cùng một bộ đọc Clone (chỉ đo bố cục, không lấy nội dung).",
    ])
