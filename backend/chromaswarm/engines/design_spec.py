"""DesignSpec (B5): deterministic assembly of DESIGN.md + tokens.css.

The LLM (Phase 3) only writes `philosophy` prose and may pick presets; every
number in DESIGN.md comes from the engines, so it is reproducible and testable.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from chromaswarm.engines.palette import Mode, Palette, generate_palette
from chromaswarm.engines.presets import (
    ANTI_SLOP_RULES, LAYOUTS, SURFACES, THEMES, Layout, LayoutPreset, Surface, SurfacePreset, Theme, ThemePreset,
)
from chromaswarm.engines.spacing import DENSITY_PRESETS, Density, SpatialSystem, snap
from chromaswarm.engines.style_dna import ANTI_CLONING_BOUNDARY, StyleDNA
from chromaswarm.engines.typography import Ratio, TypeScale, build_scale


class Philosophy(BaseModel):
    statement: str
    principles: list[str] = Field(min_length=3, max_length=3)


class DesignInputs(BaseModel):
    project_name: str
    page: str
    theme: Theme
    layout: Layout
    surface: Surface = Surface.FLAT
    density: Density
    mode: Mode
    seed_color: str
    exact_accent: bool = False  # the user wrote this hex: keep its chroma (palette._search_accent)
    brand_actions: bool = False  # the user said the accent is for the main buttons: actions use it in every theme
    page_kind: str = "landing"  # landing | app
    base_font_px: int = 16
    persona: str = ""
    primary_cta: str = ""
    motion_effects: list[str] = Field(default_factory=list)  # B8.1 requests
    style_dna: StyleDNA | None = None
    philosophy: Philosophy | None = None
    extra_rules: list[str] = Field(default_factory=list)
    clone_level: str | None = None  # Clone mode: "structure" | "full" (§2.5); None = Creative (§2.4 applies)
    content_width: int | None = None  # Clone mode: the reference's measured column width (narrow single column)
    heading_font: str | None = None  # Clone mode: the reference's font, when it ships Vietnamese
    body_font: str | None = None


CLONE_POLICY = {
    "structure": [
        "Section order and the layout type of each section reproduce the reference page.",
        "Palette tone, accent, spacing density and type feel follow the reference, rebuilt on the engines above.",
        "Copy, brand name, logo and images are the user's own; none were read from the reference.",
    ],
    "full": [
        "Clone 100%: the user confirmed the reference is their own site.",
        "Section order, layout, copy, brand name, logo and images reproduce the reference.",
        "Colours, type scale and spacing are rebuilt on the engines above so the page passes B11.",
    ],
}


class DesignSpec(BaseModel):
    inputs: DesignInputs
    philosophy: Philosophy
    theme: ThemePreset
    layout: LayoutPreset
    surface: SurfacePreset
    palette: Palette
    typography: TypeScale
    spatial: SpatialSystem
    radius: dict[str, int]
    elevation: str
    motion_easing: str
    motion_duration_ms: int
    dna_rules: list[str]
    anti_slop: list[str]


def default_philosophy(theme: ThemePreset, spatial: SpatialSystem, palette: Palette, cta: str,
                       fonts: tuple[str, str] | None = None) -> Philosophy:
    """Rule-based baseline philosophy (used without an LLM and as the ablation baseline)."""
    fonts = fonts or (theme.heading_font, theme.body_font)
    calm = spatial.section_padding_desktop >= 96
    return Philosophy(
        statement=(
            f"{theme.label_vi}: {'khoảng trắng rộng là chất liệu chính' if calm else 'thông tin rõ ràng, nhịp đều'}, "
            f"màu nhấn chỉ xuất hiện ở hành động quan trọng nhất."
        ),
        principles=[
            f"Nhịp không gian: section cách nhau {spatial.section_padding_desktop}px, mọi khoảng cách thuộc lưới 8pt.",
            f"Một điểm nhấn: màu accent ({palette.get('accent').css}) chỉ dành cho "
            f"{cta or 'Primary CTA'} và trạng thái đang chọn.",
            f"Chữ dẫn dắt: {fonts[0]} cho tiêu đề, {fonts[1]} cho nội dung, dòng chữ 45–72ch.",
        ],
    )


def philosophy_facts(spec: DesignSpec) -> dict:
    """The only facts an LLM may cite when writing the philosophy prose."""
    i = spec.inputs
    return {
        "project": i.project_name, "page": i.page, "persona_and_goal": i.persona,
        "primary_cta": i.primary_cta or "Primary CTA",
        "style": spec.theme.label_vi, "surface": spec.surface.label_vi, "layout": spec.layout.label_vi, "reading_pattern": spec.layout.reading_pattern,
        "mode": spec.palette.mode.value, "accent": spec.palette.get("accent").css,
        "heading_font": spec.typography.heading_font, "body_font": spec.typography.body_font,
        "section_padding_px": spec.spatial.section_padding_desktop, "grid": "8pt", "line_length": "45-72ch", "color_rule": "60-30-10",
        "learned_from_reference": spec.dna_rules,
        "user_feedback": [r for r in i.extra_rules if r.startswith("User feedback")],
    }


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def philosophy_is_grounded(phil: Philosophy, facts: dict) -> bool:
    """Decision 7: every number in DESIGN.md comes from the engines. Reject prose
    that cites any number not present in the facts it was given."""
    allowed = set(_NUMBER.findall(json.dumps(facts, ensure_ascii=False)))
    text = " ".join([phil.statement, *phil.principles])
    return all(n in allowed for n in _NUMBER.findall(text))


def build_design_spec(inp: DesignInputs) -> DesignSpec:
    theme = THEMES[inp.theme]
    layout = LAYOUTS[inp.layout]
    spatial = DENSITY_PRESETS[inp.density]
    if inp.content_width:  # the container's max-width includes its gutters (border-box)
        spatial = spatial.model_copy(update={"container_max": inp.content_width + 2 * spatial.page_gutter_desktop})
    palette = generate_palette(inp.seed_color, inp.mode, exact=inp.exact_accent)

    if inp.page_kind == "landing":
        ratio = theme.landing_ratio
    else:
        ratio = Ratio.MINOR_THIRD if inp.density is not Density.DENSE else Ratio.MAJOR_SECOND
    typography = build_scale(inp.base_font_px, ratio, inp.heading_font or theme.heading_font,
                             inp.body_font or theme.body_font, theme.mono_font)

    radius = {"sm": theme.radius_sm, "md": theme.radius_md, "lg": theme.radius_lg}
    elevation = theme.elevation
    duration, easing = theme.motion_duration_ms, theme.motion_easing
    dna_rules: list[str] = []
    if inp.style_dna:
        dna = inp.style_dna
        dna_rules = dna.learned_rules()
        # DNA refines surface treatment; the user's B3 answers (theme/density/mode) stay authoritative.
        if dna.radius_median is not None and inp.theme is not Theme.NEO_BRUTALIST:
            md = 0 if dna.radius_median < 2 else snap(dna.radius_median)
            radius = {"sm": max(0, md // 2), "md": md, "lg": md * 2 if md else 0}
        if dna.separation == "borders":
            elevation = "none — separate surfaces with 1px borders (learned from reference)"
        if dna.motion_median_ms:
            duration = int(min(600, max(120, dna.motion_median_ms)))

    surface = SURFACES[inp.surface]
    if surface.radius is not None:  # the material's shape wins over the theme's and the reference's radii
        radius = dict(zip(("sm", "md", "lg"), surface.radius))
    if surface.elevation:
        elevation = surface.elevation

    philosophy = inp.philosophy or default_philosophy(theme, spatial, palette, inp.primary_cta,
                                                      (typography.heading_font, typography.body_font))
    return DesignSpec(inputs=inp, philosophy=philosophy, theme=theme, layout=layout, surface=surface, palette=palette,
                      typography=typography, spatial=spatial, radius=radius, elevation=elevation,
                      motion_easing=easing, motion_duration_ms=duration, dna_rules=dna_rules,
                      anti_slop=ANTI_SLOP_RULES + inp.extra_rules)


# ------------------------------------------------------------------ render

def render_design_md(spec: DesignSpec) -> str:
    i, p, t, s = spec.inputs, spec.palette, spec.typography, spec.spatial
    lines = [
        f"# DESIGN.md — {i.project_name} · {i.page}",
        "",
        "## 1. Triết lý Thiết kế (Design Philosophy)",
        "",
        f"> {spec.philosophy.statement}",
        "",
        *[f"{n}. {pr}" for n, pr in enumerate(spec.philosophy.principles, 1)],
        "",
        "## 2. Đặc trưng học từ tham khảo (Extracted Style DNA)",
        "",
    ]
    if spec.dna_rules:
        src = i.style_dna.source_url if i.style_dna and i.style_dna.source_url else "screenshot"
        lines += [f"Nguồn: {src}", "", *[f"- {r}" for r in spec.dna_rules], ""]
        if i.clone_level:
            lines += ["**Clone mode (FRONTEND_STANDARDS §2.5):**", "", *[f"- {r}" for r in CLONE_POLICY[i.clone_level]]]
        else:
            lines += ["**Ranh giới chống sao chép:**", "", *[f"- {r}" for r in ANTI_CLONING_BOUNDARY]]
    else:
        lines.append("_Không có ảnh/URL tham khảo — thiết kế dựa hoàn toàn trên câu trả lời 5 trụ cột._")
    lines += [
        "",
        f"## 3. Hệ màu OKLCH 60-30-10 ({p.mode}, brand hue {p.brand_hue}°)",
        "",
        "| Token | Vai trò | OKLCH | Hex fallback |",
        "| :--- | :---: | :--- | :--- |",
        *[f"| `--{tk.name}` | {tk.role.value}% | `{tk.css}` | `{tk.hex}` |" for tk in p.tokens],
        "",
        "**Kiểm tra tương phản**",
        "",
        "| Chữ / Nền | WCAG | APCA Lc | Yêu cầu | Kết quả |",
        "| :--- | ---: | ---: | :--- | :---: |",
        *[f"| {c.fg} / {c.bg} | {c.wcag}:1 | {c.apca} | ≥{c.required_wcag}:1, \\|Lc\\|≥{c.required_apca:g} | "
          f"{'PASS' if c.passed else 'FAIL'} |" for c in p.checks],
        "",
        f"## 4. Typography (ratio {t.ratio}, base {t.base_px}px)",
        "",
        f"- Heading: **{t.heading_font}** · Body: **{t.body_font}**" + (f" · Mono: **{t.mono_font}**" if t.mono_font else ""),
        f"- Độ dài dòng: {t.measure}",
        "",
        "| Cấp | Desktop | Mobile | CSS | Line-height | Tracking |",
        "| :--- | ---: | ---: | :--- | ---: | ---: |",
        *[f"| {st.name} | {st.px_max:g}px | {st.px_min:g}px | `{st.css_size}` | {st.line_height} | {st.letter_spacing} |"
          for st in t.steps],
        "",
        f"## 5. Không gian & Lề ({s.density})",
        "",
        f"- Container max-width: **{s.container_max}px**"
        + (f" (cột nội dung {i.content_width}px đo từ trang mẫu + 2 gutter)" if i.content_width else "") + "; gutter {s.page_gutter_mobile}px (mobile) / {s.page_gutter_desktop}px (desktop)",
        f"- Section padding: **{s.section_padding_desktop}px** desktop / {s.section_padding_mobile}px mobile",
        f"- Grid gap {s.grid_gap}px · Card padding {s.card_padding}px · Inline gap {s.inline_gap}px",
        f"- Luật gần kề: {s.inline_gap} < {s.card_padding} < {s.section_padding_desktop} ✓",
        f"- Thang 8pt duy nhất được phép: 4, 8, 12, 16, 24, 32, 48, 64, 80, 96, 128",
        f"- Bo góc: sm {spec.radius['sm']}px · md {spec.radius['md']}px · lg {spec.radius['lg']}px · nút {spec.theme.button_radius}",
        f"- Chất liệu bề mặt: **{spec.surface.label_vi}** ({spec.surface.hint})",
        f"- Elevation: {spec.elevation}",
        "- Đổ bóng (đúng 3 mức): " + " · ".join(f"{k} `{v}`" for k, v in shadow_tokens(spec).items()),
        ("- Màu hành động: **gần đen** (`--text-primary`) — giao diện trung tính, màu sắc đến từ ảnh"
         if neutral_actions(spec) else "- Màu hành động: màu nhấn thương hiệu (`--accent`)"),
        f"- Bố cục: {spec.layout.label_vi} — {spec.layout.reading_pattern}; {spec.layout.grid}; tỷ lệ ảnh {', '.join(spec.layout.image_ratios)}",
        "",
        "## 6. Chuyển động & Hiệu ứng 2D/3D (B8.1)",
        "",
        f"- Mặc định: `{spec.motion_duration_ms}ms {spec.motion_easing}`; nhấn `scale(0.98)`; `focus-visible` rõ ràng",
        *([f"- B8.1: {e}" for e in i.motion_effects] or ["- B8.1: không yêu cầu hiệu ứng nâng cao"]),
        "",
        "## 7. Luật chống AI Slop của dự án",
        "",
        *[f"{n}. {r}" for n, r in enumerate(spec.anti_slop, 1)],
        "",
    ]
    return "\n".join(lines)


def shadow_tokens(spec: DesignSpec) -> dict[str, str]:
    """Exactly three elevation levels (§2.6): light from above, tinted with the
    text hue instead of pure black, low alpha (anti-slop #5)."""
    h = spec.palette.get("text-primary").h
    tint = lambda a: f"oklch(0.2 0.02 {h:g} / {a})"  # noqa: E731
    surface = spec.inputs.surface
    if surface is Surface.BRUTAL:  # hard offset, no blur: the ink shadow is part of the shape
        return {"sm": "2px 2px 0 var(--text-primary)", "md": "4px 4px 0 var(--text-primary)",
                "lg": "8px 8px 0 var(--text-primary)"}
    if surface is Surface.CLAY:  # puffy: soft drop + light from the top edge + shade at the bottom edge
        inner = f"inset 0 2px 4px oklch(1 0 0 / 0.55), inset 0 -4px 8px {tint(0.08)}"
        # soft but under the anti-slop ceiling (QA: blur >= 10px needs alpha <= 0.1)
        return {"sm": f"0 4px 8px {tint(0.07)}, {inner}",
                "md": f"0 8px 24px {tint(0.08)}, {inner}",
                "lg": f"0 16px 40px {tint(0.09)}, {inner}"}
    if surface is Surface.GLASS:  # wide, soft and low: glass floats, it does not cast hard shadows
        rim = "inset 0 1px 0 oklch(1 0 0 / 0.45)"
        return {"sm": f"{rim}, 0 2px 8px {tint(0.06)}",
                "md": f"{rim}, 0 8px 24px {tint(0.08)}",
                "lg": f"{rim}, 0 16px 48px {tint(0.09)}"}
    return {
        "sm": f"0 1px 2px {tint(0.06)}",
        "md": f"0 1px 2px {tint(0.04)}, 0 4px 12px {tint(0.08)}",
        "lg": f"0 2px 4px {tint(0.04)}, 0 12px 32px {tint(0.10)}",
    }


# Luxury and warm brands keep the UI chrome neutral and let photography carry the colour:
# 9 of 10 reference sites give the accent <= 5% of the page and use near-black actions
# (knowledge-base/MODERN_UI_REFERENCES.md, pattern 2). Still one colour for every action (§2.1).
NEUTRAL_ACTION_THEMES = {Theme.EDITORIAL_LUXURY, Theme.WARM_ORGANIC}


def neutral_actions(spec: DesignSpec) -> bool:
    return spec.inputs.theme in NEUTRAL_ACTION_THEMES and not spec.inputs.brand_actions


def action_tokens(spec: DesignSpec) -> dict[str, str]:
    if neutral_actions(spec):
        return {"action": "var(--text-primary)", "action-fg": "var(--bg-primary)",
                "action-hover": "color-mix(in srgb, var(--text-primary) 82%, var(--bg-primary))",
                "action-ink": "var(--text-primary)",
                # on the dark closing band the neutral action inverts to the page background
                "band-action": "var(--bg-primary)", "band-action-fg": "var(--text-primary)"}
    # Brand-coloured actions keep their colour on the dark band: a white button there reads as disabled.
    return {"action": "var(--accent)", "action-fg": "var(--accent-fg)", "action-hover": "var(--accent-hover)",
            "action-ink": "var(--accent-ink)", "band-action": "var(--accent)", "band-action-fg": "var(--accent-fg)"}


def render_tokens_css(spec: DesignSpec) -> str:
    """CSS variables for the generated workspace (Design department writes back here)."""
    out = [":root {"]
    out += [f"  --{tk.name}: {tk.css};" for tk in spec.palette.tokens]
    out += [f"  --{k}: {v};" for k, v in action_tokens(spec).items()]
    out += [f"  --radius-{k}: {v}px;" for k, v in spec.radius.items()]
    out += [f"  --shadow-{k}: {v};" for k, v in shadow_tokens(spec).items()]
    out += [f"  --font-heading: '{spec.typography.heading_font}', serif;" if spec.inputs.theme is Theme.EDITORIAL_LUXURY
            else f"  --font-heading: '{spec.typography.heading_font}', system-ui, sans-serif;",
            f"  --font-body: '{spec.typography.body_font}', system-ui, sans-serif;"]
    if spec.typography.mono_font:
        out.append(f"  --font-mono: '{spec.typography.mono_font}', ui-monospace, monospace;")
    out += [f"  --text-{st.name}: {st.css_size};" for st in spec.typography.steps]
    s = spec.spatial
    out += [
        f"  --container-max: {s.container_max}px;",
        f"  --gutter: {s.page_gutter_mobile}px;",
        f"  --section-y: {s.section_padding_mobile}px;",
        f"  --grid-gap: {s.grid_gap}px;",
        f"  --card-padding: {s.card_padding}px;",
        f"  --ease: {spec.motion_easing};",
        f"  --duration: {spec.motion_duration_ms}ms;",
        "}",
        "@media (min-width: 1024px) {",
        f"  :root {{ --gutter: {s.page_gutter_desktop}px; --section-y: {s.section_padding_desktop}px; }}",
        "}",
    ]
    return "\n".join(out) + "\n"
