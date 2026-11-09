"""DesignSpec (B5): deterministic assembly of DESIGN.md + tokens.css.

The LLM (Phase 3) only writes `philosophy` prose and may pick presets; every
number in DESIGN.md comes from the engines, so it is reproducible and testable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from chromaswarm.engines.palette import Mode, Palette, generate_palette
from chromaswarm.engines.presets import ANTI_SLOP_RULES, LAYOUTS, THEMES, Layout, LayoutPreset, Theme, ThemePreset
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
    density: Density
    mode: Mode
    seed_color: str
    page_kind: str = "landing"  # landing | app
    base_font_px: int = 16
    persona: str = ""
    primary_cta: str = ""
    motion_effects: list[str] = Field(default_factory=list)  # B8.1 requests
    style_dna: StyleDNA | None = None
    philosophy: Philosophy | None = None
    extra_rules: list[str] = Field(default_factory=list)


class DesignSpec(BaseModel):
    inputs: DesignInputs
    philosophy: Philosophy
    theme: ThemePreset
    layout: LayoutPreset
    palette: Palette
    typography: TypeScale
    spatial: SpatialSystem
    radius: dict[str, int]
    elevation: str
    motion_easing: str
    motion_duration_ms: int
    dna_rules: list[str]
    anti_slop: list[str]


def default_philosophy(theme: ThemePreset, spatial: SpatialSystem, palette: Palette, cta: str) -> Philosophy:
    """Rule-based baseline philosophy (used without an LLM and as the ablation baseline)."""
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
            f"Chữ dẫn dắt: {theme.heading_font} cho tiêu đề, {theme.body_font} cho nội dung, dòng chữ 45–72ch.",
        ],
    )


def build_design_spec(inp: DesignInputs) -> DesignSpec:
    theme = THEMES[inp.theme]
    layout = LAYOUTS[inp.layout]
    spatial = DENSITY_PRESETS[inp.density]
    palette = generate_palette(inp.seed_color, inp.mode)

    if inp.page_kind == "landing":
        ratio = theme.landing_ratio
    else:
        ratio = Ratio.MINOR_THIRD if inp.density is not Density.DENSE else Ratio.MAJOR_SECOND
    typography = build_scale(inp.base_font_px, ratio, theme.heading_font, theme.body_font, theme.mono_font)

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

    philosophy = inp.philosophy or default_philosophy(theme, spatial, palette, inp.primary_cta)
    return DesignSpec(inputs=inp, philosophy=philosophy, theme=theme, layout=layout, palette=palette,
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
        lines += [f"Nguồn: {src}", "", *[f"- {r}" for r in spec.dna_rules], "", "**Ranh giới chống sao chép:**", ""]
        lines += [f"- {r}" for r in ANTI_CLONING_BOUNDARY]
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
        f"- Container max-width: **{s.container_max}px**; gutter {s.page_gutter_mobile}px (mobile) / {s.page_gutter_desktop}px (desktop)",
        f"- Section padding: **{s.section_padding_desktop}px** desktop / {s.section_padding_mobile}px mobile",
        f"- Grid gap {s.grid_gap}px · Card padding {s.card_padding}px · Inline gap {s.inline_gap}px",
        f"- Luật gần kề: {s.inline_gap} < {s.card_padding} < {s.section_padding_desktop} ✓",
        f"- Thang 8pt duy nhất được phép: 4, 8, 12, 16, 24, 32, 48, 64, 80, 96, 128",
        f"- Bo góc: sm {spec.radius['sm']}px · md {spec.radius['md']}px · lg {spec.radius['lg']}px · nút {spec.theme.button_radius}",
        f"- Elevation: {spec.elevation}",
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


def render_tokens_css(spec: DesignSpec) -> str:
    """CSS variables for the generated workspace (Design department writes back here)."""
    out = [":root {"]
    out += [f"  --{tk.name}: {tk.css};" for tk in spec.palette.tokens]
    out += [f"  --radius-{k}: {v}px;" for k, v in spec.radius.items()]
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
