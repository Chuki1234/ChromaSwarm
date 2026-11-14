"""Modular typography scale (FRONTEND_STANDARDS.md §2.2): S_n = S_0 * r^n, fluid via clamp()."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

VIEWPORT_MIN, VIEWPORT_MAX = 375, 1440
FLUID_FROM_PX = 32  # sizes >= 32px get clamp() and negative tracking
# Modern hero headlines run ~64-96px on desktop (knowledge-base/MODERN_UI_REFERENCES.md,
# pattern 6). A small ratio would leave display at ~60px, so desktop display is floored.
DISPLAY_MIN_DESKTOP_PX = 72


class Ratio(float, Enum):
    MAJOR_SECOND = 1.125
    MINOR_THIRD = 1.2
    MAJOR_THIRD = 1.25
    PERFECT_FOURTH = 1.333


LEVELS = [("caption", -1), ("body", 0), ("lead", 1), ("h4", 2), ("h3", 3), ("h2", 4), ("h1", 5), ("display", 6)]


class TypeStep(BaseModel):
    name: str
    n: int
    px_max: float
    px_min: float
    css_size: str
    line_height: float
    letter_spacing: str


class TypeScale(BaseModel):
    base_px: int
    ratio: float
    heading_font: str
    body_font: str
    mono_font: str | None
    measure: str = "45ch-72ch"
    steps: list[TypeStep]


def _fluid(px_min: float, px_max: float) -> str:
    slope = (px_max - px_min) / (VIEWPORT_MAX - VIEWPORT_MIN)
    intercept = px_min - slope * VIEWPORT_MIN
    return f"clamp({px_min / 16:.3f}rem, {intercept / 16:.3f}rem + {slope * 100:.3f}vw, {px_max / 16:.3f}rem)"


def build_scale(base_px: int, ratio: Ratio, heading_font: str, body_font: str,
                mono_font: str | None = None) -> TypeScale:
    # Mobile uses a gentler ratio so the hierarchy stays monotonic at every
    # viewport (h4 < h3 < h2 ...): r_mobile = 1 + 0.6 * (r - 1).
    mobile_ratio = 1 + 0.6 * (ratio.value - 1)
    steps = []
    for name, n in LEVELS:
        px = base_px * ratio.value ** n
        if name == "display":
            px = max(px, DISPLAY_MIN_DESKTOP_PX)
        px_min = base_px * mobile_ratio ** n if n > 0 else px
        if px - px_min >= 1:
            css = _fluid(round(px_min, 1), round(px, 1))
        else:
            px_min = px
            css = f"{px / 16:.3f}rem"
        if px >= FLUID_FROM_PX:
            # -0.02em at 32px -> -0.035em at >= 72px
            t = min(1.0, (px - 32) / 40)
            tracking = f"{-(0.02 + 0.015 * t):.3f}em"
        else:
            tracking = "0"
        if name in ("display", "h1"):
            lh = 1.1
        elif n >= 2:
            lh = 1.2
        elif name == "caption":
            lh = 1.4
        else:
            lh = 1.55
        steps.append(TypeStep(name=name, n=n, px_max=round(px, 2), px_min=round(px_min, 2),
                              css_size=css, line_height=lh, letter_spacing=tracking))
    return TypeScale(base_px=base_px, ratio=ratio.value, heading_font=heading_font, body_font=body_font,
                     mono_font=mono_font, steps=steps)
