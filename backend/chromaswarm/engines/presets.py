"""Pillar presets: plain-language answers -> technical parameters (FRONTEND_STANDARDS.md §1.2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from chromaswarm.engines.typography import Ratio


class Theme(StrEnum):
    EDITORIAL_LUXURY = "editorial-luxury"
    PRECISION_TECH = "precision-tech"
    WARM_ORGANIC = "warm-organic"
    NEO_BRUTALIST = "neo-brutalist"


class Layout(StrEnum):
    VISUAL_FIRST = "visual-first"  # A
    NARRATIVE = "narrative"  # B
    CATALOG = "catalog"  # C


class ThemePreset(BaseModel):
    theme: Theme
    label_vi: str
    heading_font: str
    body_font: str
    mono_font: str | None
    radius_sm: int
    radius_md: int
    radius_lg: int
    button_radius: str
    border: str
    elevation: str
    motion_duration_ms: int
    motion_easing: str
    landing_ratio: Ratio


THEMES: dict[Theme, ThemePreset] = {
    Theme.EDITORIAL_LUXURY: ThemePreset(
        theme=Theme.EDITORIAL_LUXURY, label_vi="Sang trọng & tĩnh lặng",
        heading_font="Instrument Serif", body_font="Inter", mono_font=None,
        radius_sm=0, radius_md=2, radius_lg=4, button_radius="2px", border="1px solid var(--border-subtle)",
        elevation="none — separate surfaces with 1px hairlines and whitespace",
        motion_duration_ms=600, motion_easing="cubic-bezier(0.16, 1, 0.3, 1)", landing_ratio=Ratio.PERFECT_FOURTH),
    Theme.PRECISION_TECH: ThemePreset(
        theme=Theme.PRECISION_TECH, label_vi="Hiện đại & chuẩn xác",
        heading_font="Geist", body_font="Inter", mono_font="Geist Mono",
        radius_sm=4, radius_md=8, radius_lg=12, button_radius="8px",
        border="1px solid color-mix(in oklch, var(--text-primary) 10%, transparent)",
        elevation="layered low-opacity shadows (0.03-0.06) only on floating UI",
        motion_duration_ms=200, motion_easing="cubic-bezier(0.22, 1, 0.36, 1)", landing_ratio=Ratio.MAJOR_THIRD),
    Theme.WARM_ORGANIC: ThemePreset(
        theme=Theme.WARM_ORGANIC, label_vi="Thân thiện & ấm áp",
        heading_font="Outfit", body_font="DM Sans", mono_font=None,
        radius_sm=12, radius_md=16, radius_lg=24, button_radius="9999px", border="1px solid var(--border-subtle)",
        elevation="soft diffused shadows tinted with the background hue",
        motion_duration_ms=300, motion_easing="cubic-bezier(0.22, 1, 0.36, 1)", landing_ratio=Ratio.MAJOR_THIRD),
    Theme.NEO_BRUTALIST: ThemePreset(
        theme=Theme.NEO_BRUTALIST, label_vi="Cá tính & táo bạo",
        heading_font="Space Grotesk", body_font="Inter", mono_font="JetBrains Mono",
        radius_sm=0, radius_md=0, radius_lg=0, button_radius="0px", border="2px solid var(--text-primary)",
        elevation="hard offset shadow 4px 4px 0 var(--text-primary)",
        motion_duration_ms=150, motion_easing="cubic-bezier(0.2, 0, 0, 1)", landing_ratio=Ratio.PERFECT_FOURTH),
}


class LayoutPreset(BaseModel):
    layout: Layout
    label_vi: str
    reading_pattern: str
    grid: str
    image_ratios: list[str]


LAYOUTS: dict[Layout, LayoutPreset] = {
    Layout.VISUAL_FIRST: LayoutPreset(
        layout=Layout.VISUAL_FIRST, label_vi="Hình ảnh lớn làm nhân vật chính",
        reading_pattern="Asymmetric editorial", grid="Hero full-bleed or 7:5 split; asymmetric 12-col grid",
        image_ratios=["16:10", "4:5"]),
    Layout.NARRATIVE: LayoutPreset(
        layout=Layout.NARRATIVE, label_vi="Kể chuyện từng bước",
        reading_pattern="Z-pattern", grid="Alternating left-text / right-visual blocks, chapter progress",
        image_ratios=["16:9", "1:1"]),
    Layout.CATALOG: LayoutPreset(
        layout=Layout.CATALOG, label_vi="Nhiều sản phẩm ngay lập tức",
        reading_pattern="F-pattern", grid="Sticky filter + 4-col (desktop) / 2-col (mobile) product grid",
        image_ratios=["1:1", "4:5"]),
}

ANTI_SLOP_RULES: list[str] = [
    "No default indigo/purple/pink gradients on text or buttons; monochrome OKLCH depth or a <12% radial glow in brand hue.",
    "No repeated 'centered title + 3 identical icon cards' sections; vary rhythm (60/40 splits, tabs, numbered lists, bento).",
    "No center-everything: center only short headings with <= 2 lines (< 65ch); long text left-aligned.",
    "No decorative emoji/icons on every heading; icons only for navigation or state.",
    "No heavy default shadows (shadow-lg/xl); use surface contrast + 1px borders, multi-layer shadows at 0.03-0.06.",
    "No generic copy ('nâng tầm trải nghiệm', lorem ipsum, John Doe); concrete prices, specs, categories.",
    "Exactly 1 primary + 1 secondary CTA per viewport.",
    "Locked image aspect ratios with object-fit: cover; scrim gradient behind text on images.",
    "Every interactive element has hover, active (scale 0.98) and focus-visible states, ~200ms transitions.",
    "Real product states: filters, variant pickers, drawers, modals and form validation actually work.",
]
