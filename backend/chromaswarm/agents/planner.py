"""B5-B6 rule-based Architect & Planner: pipeline state -> DesignInputs, PRODUCT.md, PLAN.md.

Section blueprints guarantee varied visual rhythm (no two consecutive sections
share a structure) and give every interactive element a data-swarm-id that
the Design cursors (B8) and the Master QA Cursor (B11) will target.
"""

from __future__ import annotations

from pydantic import BaseModel

from chromaswarm.agents.consultant import base_font_for, extract_cta, split_color
from chromaswarm.engines.design_spec import DesignInputs, DesignSpec
from chromaswarm.engines.presets import Layout, Surface, Theme
from chromaswarm.engines.spacing import Density
from chromaswarm.engines.style_dna import StyleDNA
from chromaswarm.state_machine.pipeline_state import PipelineState


class Interactive(BaseModel):
    id: str
    role: str  # button | link | input | tab | card | modal-trigger | filter-tab
    behavior: str


class Section(BaseModel):
    id: str
    name: str
    structure: str
    content: str
    interactive: list[Interactive] = []
    effect: str | None = None  # B8.1 candidate
    surface: str | None = None  # "alt": tinted band (bg-surface) for rhythm between sections


def _i(id_: str, role: str, behavior: str) -> Interactive:
    return Interactive(id=id_, role=role, behavior=behavior)


NAV = Section(id="site-header", name="Header / Navbar", structure="sticky-bar",
              content="Logo, 4-5 nav links, 1 secondary action; blur backdrop on scroll",
              interactive=[_i("nav-logo", "link", "go to home"), _i("nav-menu-toggle", "button", "open mobile menu ≤768px")])
FOOTER = Section(id="site-footer", name="Footer", structure="footer-columns",
                 content="Brand line, link columns, newsletter input, legal",
                 interactive=[_i("footer-newsletter-input", "input", "email validation"),
                              _i("footer-newsletter-submit", "button", "show success / error state")])

BLUEPRINTS: dict[str, list[Section]] = {
    "landing": [
        NAV,
        Section(id="hero", name="Hero", structure="split-7-5",
                content="Concrete value proposition (real product, real price/spec), hero image 4:5",
                interactive=[_i("cta-primary", "button", "primary conversion"),
                             _i("cta-secondary", "link", "scroll to details, arrow nudges on hover")],
                effect="subtle entrance reveal"),
        Section(id="proof-strip", name="Proof strip", structure="inline-metrics",
                content="3-4 quantified facts (numbers, materials, delivery time) — no icons"),
        Section(id="feature-story", name="Feature story", structure="alternating-z",
                content="2-3 alternating text/visual rows explaining why this product",
                effect="scroll-triggered image parallax"),
        Section(id="collection", name="Featured collection", structure="bento",
                content="Mixed-size tiles (col-span-2 + col-span-1) with real products",
                interactive=[_i("collection-card", "card", "hover lift + quick view"),
                             _i("quick-view-trigger", "modal-trigger", "open quick-view modal")]),
        Section(id="faq", name="FAQ", structure="accordion",
                content="5 concrete questions (shipping, returns, materials)",
                interactive=[_i("faq-item", "button", "expand / collapse, aria-expanded")]),
        Section(id="closing-cta", name="Closing CTA", structure="full-bleed-band",
                content="One restated offer", interactive=[_i("cta-closing", "button", "same action as cta-primary")]),
        FOOTER,
    ],
    "home": [
        NAV,
        Section(id="hero", name="Hero banner", structure="full-bleed-image",
                content="Seasonal campaign image with scrim, short headline",
                interactive=[_i("cta-primary", "button", "go to catalog")]),
        Section(id="categories", name="Category rail", structure="horizontal-scroller",
                content="Real category names with images 1:1",
                interactive=[_i("category-card", "card", "navigate to filtered catalog")]),
        Section(id="bestsellers", name="Bestsellers", structure="grid-4",
                content="8 products with price, variant dots",
                interactive=[_i("product-card", "card", "hover shows second image"),
                             _i("add-to-cart", "button", "add item, open cart drawer")]),
        Section(id="brand-story", name="Brand story", structure="split-5-7", content="Origin, materials, process"),
        FOOTER,
    ],
    "catalog": [
        NAV,
        Section(id="catalog-header", name="Catalog header", structure="title-with-count",
                content="Category title, result count, sort select",
                interactive=[_i("sort-select", "input", "re-order products")]),
        Section(id="catalog-body", name="Filters + grid", structure="sidebar-grid-4",
                content="Sticky filter sidebar (drawer on mobile), product grid",
                interactive=[_i("filter-tab", "filter-tab", "filter products for real"),
                             _i("filter-drawer-toggle", "button", "open filters ≤768px"),
                             _i("product-card", "card", "navigate to PDP")]),
        Section(id="pagination", name="Pagination", structure="inline-controls",
                content="Load more", interactive=[_i("load-more", "button", "append next page")]),
        FOOTER,
    ],
    "pdp": [
        NAV,
        Section(id="product-main", name="Gallery + buy box", structure="split-7-5",
                content="Image gallery 4:5, title, price, variant pickers, stock",
                interactive=[_i("gallery-thumb", "button", "switch main image"),
                             _i("variant-picker", "tab", "select size/color, update price & stock"),
                             _i("add-to-cart", "button", "always enabled; explains a missing variant, then adds to cart")]),
        Section(id="product-details", name="Details", structure="tabs",
                content="Description / Materials / Shipping",
                interactive=[_i("details-tab", "tab", "switch panel")]),
        Section(id="related", name="Related products", structure="horizontal-scroller",
                content="4-6 related items", interactive=[_i("product-card", "card", "navigate")]),
        FOOTER,
    ],
    "login": [
        Section(id="auth", name="Auth form", structure="split-5-7",
                content="Form on one side, brand visual on the other",
                interactive=[_i("email-input", "input", "validate format"),
                             _i("password-input", "input", "show/hide toggle"),
                             _i("submit-login", "button", "loading + error states")]),
    ],
}
BLUEPRINTS["account"] = BLUEPRINTS["login"]
GENERIC = [NAV, Section(id="page-hero", name="Page intro", structure="split-7-5", content="Title + summary",
                        interactive=[_i("cta-primary", "button", "primary action")]),
           Section(id="page-body", name="Main content", structure="tabs", content="Primary task of the page",
                   interactive=[_i("main-tab", "tab", "switch view")]), FOOTER]


CLONE_PAGE = "clone"  # sitemap slug of the page rebuilt from the Clone-mode reference


def page_sections(state: PipelineState) -> list[Section]:
    """Sections of the page being built: read from the reference in Clone mode, blueprints otherwise."""
    if state.selected_page == CLONE_PAGE and state.clone and state.clone.sections:
        return [Section.model_validate(s) for s in state.clone.sections]
    theme = Theme(state.pillars.theme) if state.pillars.theme else None
    surface = Surface(state.pillars.surface) if state.pillars.surface in {x.value for x in Surface} else None
    return sections_for(state.selected_page or "", Layout(state.pillars.layout), theme, surface)


# Landing hero by layout pillar (knowledge-base/MODERN_UI_REFERENCES.md): a varied repertoire
# instead of one split hero for every site.
#   catalog      -> split-7-5        compact, products follow right away
#   narrative    -> hero-editorial   very large headline across the page, wide image below (Linear)
#   visual-first -> hero-overlay     full-bleed photo with scrim and copy on it (Chamberlain, Marou)
#                   hero-centered    for precision-tech: product centred on a quiet panel (Apple)
# Liquid Glass needs something behind the glass: visual-first always gets the photo hero,
# with the copy on a frosted panel over it.
def hero_structure(layout: Layout, theme: Theme | None, surface: Surface | None = None) -> str:
    if layout is Layout.NARRATIVE:
        return "hero-editorial"
    if layout is Layout.VISUAL_FIRST:
        if surface is Surface.GLASS:
            return "hero-overlay"
        return "hero-centered" if theme is Theme.PRECISION_TECH else "hero-overlay"
    return "split-7-5"


FULL_WIDTH = {"sticky-bar", "footer-columns", "full-bleed-band", "full-bleed-image", "hero-overlay"}


def sections_for(slug: str, layout: Layout, theme: Theme | None = None,
                 surface: Surface | None = None) -> list[Section]:
    sections = [s.model_copy(deep=True) for s in BLUEPRINTS.get(slug, GENERIC)]
    if layout is Layout.CATALOG and slug == "landing":
        # Catalog-first landing: surface products earlier.
        sections.insert(2, sections.pop(4))
    if slug == "landing":
        hero = next(s for s in sections if s.id == "hero")
        hero.structure = hero_structure(layout, theme, surface)
    # Rhythm: content sections after the hero alternate plain / tinted background bands.
    body = [s for s in sections[1:] if s.structure not in FULL_WIDTH and s.id != "hero"]
    for n, s in enumerate(body):
        s.surface = "alt" if n % 2 == 0 and len(body) > 1 else None
    for a, b in zip(sections, sections[1:]):
        assert a.structure != b.structure, f"rhythm violation: {a.id} -> {b.id}"
    return sections


def design_inputs(state: PipelineState, project_name: str, dna: StyleDNA | None = None) -> DesignInputs:
    p = state.pillars
    theme = Theme(p.theme)
    mode, seed, _ = split_color(p.color or "light", theme)
    page = next((pg.title for pg in state.sitemap if pg.slug == state.selected_page), state.selected_page or "")
    effects = [s.effect for s in page_sections(state) if s.effect]
    clone = state.clone if state.selected_page == CLONE_PAGE else None
    return DesignInputs(
        project_name=project_name, page=page, theme=theme, layout=Layout(p.layout),
        surface=Surface(p.surface) if p.surface in {x.value for x in Surface} else Surface.FLAT, density=Density(p.margins),
        mode=mode, seed_color=seed, page_kind="app" if state.selected_page in ("dashboard", "workspace") else "landing",
        base_font_px=base_font_for(p.scope or ""), persona=p.scope or "", primary_cta=extract_cta(p.scope or "") or "",
        motion_effects=effects, style_dna=dna,
        heading_font=clone.heading_font if clone else None, body_font=clone.body_font if clone else None,
        extra_rules=[f"User feedback (B7): {f}" for f in state.plan_feedback],
    )


def render_product_md(state: PipelineState, project_name: str, seed_note: str | None) -> str:
    status = {"pending": "[Chờ xây dựng]", "building": "[Đang xây dựng]", "done": "[Đã hoàn thành]"}
    lines = [
        f"# PRODUCT.md — {project_name}",
        "",
        "## 1. Chân dung người dùng & mục tiêu (Scope)",
        "",
        f"- Yêu cầu gốc (B1): “{state.raw_prompt}”",
        f"- Lĩnh vực: {state.domain}",
        f"- Người dùng & hành động chính (B3): {state.pillars.scope}",
        "",
        "## 2. Bản đồ hệ thống trang",
        "",
        *[f"- {status[pg.status if pg.slug != state.selected_page else 'building']} **{pg.title}** — {pg.purpose}"
          for pg in state.sitemap],
        "",
        "## 3. Kho tài nguyên (Assets)",
        "",
    ]
    if state.assets:
        lines += [f"- {a.kind}: {a.path_or_text}" + (f" ({a.note})" if a.note else "") for a in state.assets]
    else:
        lines.append("- Chưa có ảnh sản phẩm: dùng ảnh chất lượng cao đúng chủ đề (Unsplash/Pexels hoặc tạo ảnh), "
                     "không để khung xám trống.")
    for r in state.references:
        lines.append(f"- Tham khảo: {r.url or r.screenshot_path} — chỉ học Design DNA, không sao chép bố cục.")
    if seed_note:
        lines += ["", f"> {seed_note}"]
    lines += [
        "",
        "## 4. Luồng liên trang",
        "",
        *[f"- `{state.selected_page}` → `{pg.slug}` ({pg.title})" for pg in state.sitemap if pg.slug != state.selected_page],
        "",
    ]
    return "\n".join(lines)


BREAKPOINTS = [(1440, 900), (1024, 768), (768, 1024), (375, 812)]


def render_plan_md(state: PipelineState, spec: DesignSpec) -> str:
    sections = page_sections(state)
    lines = [
        f"# PLAN.md — Kế hoạch triển khai trang: {spec.inputs.page}",
        "",
        "## 1. Cấu trúc phân vùng & nhịp thị giác",
        "",
        "| # | Section | `data-swarm-section` | Cấu trúc | Nội dung |",
        "| ---: | :--- | :--- | :--- | :--- |",
        *[f"| {n} | {s.name} | `{s.id}` | {s.structure} | {s.content} |" for n, s in enumerate(sections, 1)],
        "",
        "## 2. Phân công vi mô",
        "",
        "### Phòng DESIGN (Playwright, B8)",
        "",
    ]
    for s in sections:
        lines.append(f"- **{s.id}** — Layout Cursor: đo gutter {spec.spatial.page_gutter_desktop}px / "
                     f"section {spec.spatial.section_padding_desktop}px; Color Cursor: kiểm tra tương phản trên "
                     f"`--bg-*`; Typography Cursor: thang chữ {spec.typography.ratio}, dòng ≤72ch"
                     + (f"; **Motion/MCP Cursor (B8.1)**: {s.effect}" if s.effect else ""))
    lines += ["", "### Phòng DEVELOPER (Next.js, B9)", ""]
    for s in sections:
        comp = "".join(w.capitalize() for w in s.id.split("-"))
        ids = ", ".join(f"`{i.id}` ({i.role})" for i in s.interactive) or "—"
        lines.append(f"- `<{comp} />` — `data-swarm-section=\"{s.id}\"`; tương tác: {ids}")
    lines += ["", "## 3. Test case cho Cursor Lớn Nhất (B11)", "", "### Bài 1 — Từng nút một", ""]
    for s in sections:
        for i in s.interactive:
            lines.append(f"- [ ] `{i.id}` ({i.role}): hover đổi style · {i.behavior} · không có console.error")
    lines += [
        "",
        "### Bài 2 — Cuộn trang",
        "",
        "- [ ] Cuộn 0 → đáy → 0: header dính không che nội dung; không phần tử kẹt ở opacity 0; mọi ảnh naturalWidth > 0",
        "",
        "### Bài 3 — Responsive",
        "",
        *[f"- [ ] {w}×{h}: scrollWidth ≤ clientWidth; không chồng lấn; lề ≥ 16px; vùng chạm ≥ 44px" for w, h in BREAKPOINTS],
        "",
        "### Bài 4 — Tuân thủ DESIGN.md & chống AI Slop",
        "",
        f"- [ ] Font hiển thị = {spec.typography.heading_font} / {spec.typography.body_font}",
        f"- [ ] ≥ 95% giá trị spacing thuộc thang 8pt; màu chỉ lấy từ token `--*`",
        "- [ ] Không vi phạm 10 điều cấm (DESIGN.md §7)",
        "",
    ]
    return "\n".join(lines)
