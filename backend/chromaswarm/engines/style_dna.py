"""Style DNA analysis (FRONTEND_STANDARDS.md §2.4).

Input is the *aggregate* sample produced by the Playwright scraper: colors with
areas, font metrics, spacing values, radii, motion. No DOM tree, no text content,
no image URLs are ever accepted here — that is the anti-cloning boundary.
"""

from __future__ import annotations

import math
from collections import Counter
from statistics import median

from pydantic import BaseModel, Field

from chromaswarm.engines.color import OKLCH, parse_css_color
from chromaswarm.engines.spacing import grid_adherence


# ----------------------------------------------------------------- raw input

class BgSample(BaseModel):
    color: str
    area: float


class TextSample(BaseModel):
    color: str
    chars: int  # used only as a weight
    font_family: str
    font_size: float
    font_weight: int
    line_height: float | None = None
    uppercase: bool = False
    letter_spacing: float = 0.0


class MotionSample(BaseModel):
    duration_ms: float
    easing: str


class RawStyleSample(BaseModel):
    source_url: str | None = None
    viewport_w: int
    viewport_h: int
    page_height: int
    backgrounds: list[BgSample] = Field(default_factory=list)
    texts: list[TextSample] = Field(default_factory=list)
    spacing: list[float] = Field(default_factory=list)
    block_padding: list[float] = Field(default_factory=list)  # vertical padding of full-width blocks
    radii: list[float] = Field(default_factory=list)
    border_count: int = 0
    shadow_count: int = 0
    backdrop_blur_count: int = 0
    motion: list[MotionSample] = Field(default_factory=list)


# --------------------------------------------------------------- analysis out

class ColorShare(BaseModel):
    css: str
    share: float


class StyleDNA(BaseModel):
    source_url: str | None
    surfaces: list[ColorShare]
    text_colors: list[ColorShare]
    accents: list[ColorShare]
    area_split: dict[str, float]  # dominant / structural / accent shares of painted area
    neutral_temperature: str  # warm | cool | neutral
    neutral_hue: float | None
    accent_usage: str  # restrained | generous | none
    is_dark: bool
    fonts: list[ColorShare]  # css = family name
    heading_body_weight_contrast: int
    base_font_px: float | None
    type_scale_ratio: float | None
    uppercase_labels: bool
    spacing_adherence: float
    common_spacing: list[int]
    density: str  # airy | balanced | dense
    radius_median: float | None
    separation: str  # borders | shadows | whitespace
    motion_median_ms: float | None
    motion_easing: str | None
    backdrop_blur: bool

    def learned_rules(self) -> list[str]:
        """Plain statements of the Style DNA, safe to put in DESIGN.md."""
        rules = [
            f"Surfaces are {'dark' if self.is_dark else 'light'} with {self.neutral_temperature} neutrals"
            + (f" (hue ~{self.neutral_hue:.0f}°)." if self.neutral_hue is not None else "."),
            f"Accent use is {self.accent_usage}: ~{self.area_split.get('accent', 0) * 100:.0f}% of painted area.",
            f"Surfaces are separated mainly by {self.separation}.",
            f"Spacing feels {self.density}; {self.spacing_adherence * 100:.0f}% of spacing values sit on the 8pt scale.",
        ]
        if self.radius_median is not None:
            rules.append(f"Typical corner radius ~{self.radius_median:.0f}px.")
        if self.type_scale_ratio:
            rules.append(f"Type scale ratio ~{self.type_scale_ratio:.3f}; heading/body weight contrast {self.heading_body_weight_contrast}.")
        if self.uppercase_labels:
            rules.append("Small labels use uppercase with wide tracking.")
        if self.motion_median_ms:
            rules.append(f"Interactions animate in ~{self.motion_median_ms:.0f}ms ({self.motion_easing}).")
        if self.backdrop_blur:
            rules.append("Uses frosted-glass (backdrop-filter: blur) on floating layers.")
        return rules


ANTI_CLONING_BOUNDARY = [
    "Do not reproduce the reference's DOM tree, section order or component count.",
    "Do not reuse its copy, brand name, logo, images or icons.",
    "Do not copy button count/placement unless it serves this page's Scope (B3 pillar 5).",
]

ACCENT_CHROMA = 0.08


def _key(c: OKLCH) -> tuple[int, int, int]:
    return (round(c.l * 50), round(c.c * 100), round(c.h / 10) if c.c > 0.02 else 0)


def _cluster(pairs: list[tuple[OKLCH, float]]) -> list[tuple[OKLCH, float]]:
    buckets: dict[tuple[int, int, int], list[tuple[OKLCH, float]]] = {}
    for c, w in pairs:
        buckets.setdefault(_key(c), []).append((c, w))
    out = []
    for items in buckets.values():
        total = sum(w for _, w in items)
        rep = max(items, key=lambda x: x[1])[0]
        out.append((rep, total))
    return sorted(out, key=lambda x: -x[1])


def _shares(pairs: list[tuple[OKLCH, float]], top: int) -> list[ColorShare]:
    total = sum(w for _, w in pairs) or 1
    return [ColorShare(css=c.css(), share=round(w / total, 4)) for c, w in pairs[:top]]


def analyze(raw: RawStyleSample) -> StyleDNA:
    bgs = []
    for b in raw.backgrounds:
        parsed = parse_css_color(b.color)
        if parsed and parsed[1] > 0.5 and b.area > 0:
            bgs.append((parsed[0], b.area))
    bg_clusters = _cluster(bgs)
    total_area = sum(w for _, w in bg_clusters) or 1

    neutrals = [(c, w) for c, w in bg_clusters if c.c < ACCENT_CHROMA]
    accents = [(c, w) for c, w in bg_clusters if c.c >= ACCENT_CHROMA]

    texts = []
    for t in raw.texts:
        parsed = parse_css_color(t.color)
        if parsed:
            texts.append((parsed[0], float(t.chars)))
            if parsed[0].c >= ACCENT_CHROMA:
                accents.append((parsed[0], t.chars * t.font_size ** 2 * 0.5))  # glyph area proxy
    text_clusters = _cluster(texts)
    accent_clusters = _cluster(accents)

    dominant = neutrals[0][1] / total_area if neutrals else 0.0
    accent_area = sum(w for _, w in accent_clusters) / (total_area + sum(w for _, w in accent_clusters) or 1)
    structural = max(0.0, 1 - dominant - accent_area)

    dom_color = neutrals[0][0] if neutrals else None
    if dom_color is None or dom_color.c < 0.004:
        temp, nh = "neutral", None
    else:
        nh = dom_color.h
        temp = "warm" if 30 <= nh <= 110 else "cool" if 180 <= nh <= 300 else "neutral"

    fam_weights: Counter[str] = Counter()
    size_weights: Counter[float] = Counter()
    weights_by_size: dict[float, list[int]] = {}
    upper = 0
    for t in raw.texts:
        fam = t.font_family.split(",")[0].strip().strip("'\"")
        fam_weights[fam] += t.chars
        size = round(t.font_size)
        size_weights[size] += t.chars
        weights_by_size.setdefault(size, []).append(t.font_weight)
        if t.uppercase and t.letter_spacing > 0 and t.font_size <= 14:
            upper += t.chars
    total_chars = sum(fam_weights.values()) or 1
    fonts = [ColorShare(css=f, share=round(w / total_chars, 4)) for f, w in fam_weights.most_common(3)]

    base = size_weights.most_common(1)[0][0] if size_weights else None
    ratio = None
    if base:
        larger = sorted(s for s, w in size_weights.items() if s > base and w > 0)
        if larger:
            n_steps = len(larger)
            ratio = round((larger[-1] / base) ** (1 / n_steps), 3) if n_steps else None
    if weights_by_size and base:
        largest = max(weights_by_size)
        contrast = int(median(weights_by_size[largest]) - median(weights_by_size[base]))
    else:
        contrast = 0

    grid = grid_adherence(raw.spacing)
    big = raw.block_padding or [abs(v) for v in raw.spacing if abs(v) >= 48]
    big_med = max(big) if big else 0  # the most generous section rhythm defines the feel
    density = "airy" if big_med >= 96 else "balanced" if big_med >= 64 else "dense"
    common = [int(v) for v, _ in Counter(round(abs(v)) for v in raw.spacing if abs(v) >= 3).most_common(8)]

    nonzero_radii = [r for r in raw.radii if r > 0]
    radius_med = median(nonzero_radii) if nonzero_radii else (0.0 if raw.radii else None)

    if raw.shadow_count > raw.border_count and raw.shadow_count >= 2:
        separation = "shadows"
    elif raw.border_count >= 2:
        separation = "borders"
    else:
        separation = "whitespace"

    durations = [m.duration_ms for m in raw.motion if m.duration_ms > 0]
    easing = Counter(m.easing for m in raw.motion if m.duration_ms > 0).most_common(1)

    accent_share = round(accent_area, 4)
    return StyleDNA(
        source_url=raw.source_url,
        surfaces=_shares(neutrals or bg_clusters, 5),
        text_colors=_shares(text_clusters, 3),
        accents=_shares(accent_clusters, 3),
        area_split={"dominant": round(dominant, 4), "structural": round(structural, 4), "accent": accent_share},
        neutral_temperature=temp,
        neutral_hue=round(nh, 1) if nh is not None else None,
        accent_usage="none" if not accent_clusters else "restrained" if accent_share <= 0.15 else "generous",
        is_dark=bool(dom_color and dom_color.l < 0.5),
        fonts=fonts,
        heading_body_weight_contrast=contrast,
        base_font_px=float(base) if base else None,
        type_scale_ratio=ratio if ratio and math.isfinite(ratio) else None,
        uppercase_labels=upper / total_chars > 0.01,
        spacing_adherence=grid.adherence,
        common_spacing=common,
        density=density,
        radius_median=radius_med,
        separation=separation,
        motion_median_ms=median(durations) if durations else None,
        motion_easing=easing[0][0] if easing else None,
        backdrop_blur=raw.backdrop_blur_count > 0,
    )
