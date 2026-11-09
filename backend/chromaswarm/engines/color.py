"""Color science primitives: sRGB <-> OKLab <-> OKLCH, gamut mapping, contrast.

References:
- OKLab: Björn Ottosson, "A perceptual color space for image processing" (2020).
- WCAG 2.x relative luminance / contrast ratio.
- APCA-W3 0.0.98G-4g (Lc value, signed: positive = dark text on light bg).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

RGB = tuple[float, float, float]  # sRGB components in [0, 1]


@dataclass(frozen=True)
class OKLCH:
    l: float  # 0..1 (perceived lightness)
    c: float  # 0..~0.4
    h: float  # degrees 0..360

    def css(self) -> str:
        return f"oklch({self.l * 100:.1f}% {self.c:.3f} {self.h:.1f})"

    def with_(self, l: float | None = None, c: float | None = None, h: float | None = None) -> "OKLCH":
        return OKLCH(self.l if l is None else l, self.c if c is None else c, self.h if h is None else h)


# ----------------------------------------------------------------- transfer

def _to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


# ------------------------------------------------------------ conversions

def srgb_to_oklch(rgb: RGB) -> OKLCH:
    r, g, b = (_to_linear(x) for x in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    A = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    C = math.hypot(A, B)
    H = math.degrees(math.atan2(B, A)) % 360 if C > 1e-6 else 0.0
    return OKLCH(L, C, H)


def oklch_to_linear_rgb(color: OKLCH) -> RGB:
    a = color.c * math.cos(math.radians(color.h))
    b = color.c * math.sin(math.radians(color.h))
    l_ = color.l + 0.3963377774 * a + 0.2158037573 * b
    m_ = color.l - 0.1055613458 * a - 0.0638541728 * b
    s_ = color.l - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def in_gamut(color: OKLCH, eps: float = 1e-4) -> bool:
    return all(-eps <= v <= 1 + eps for v in oklch_to_linear_rgb(color))


def gamut_map(color: OKLCH) -> OKLCH:
    """Reduce chroma (keeping L and H) until the color fits in sRGB."""
    if in_gamut(color):
        return color
    lo, hi = 0.0, color.c
    for _ in range(24):
        mid = (lo + hi) / 2
        if in_gamut(color.with_(c=mid)):
            lo = mid
        else:
            hi = mid
    return color.with_(c=lo)


def oklch_to_srgb(color: OKLCH) -> RGB:
    lin = oklch_to_linear_rgb(gamut_map(color))
    return tuple(min(1.0, max(0.0, _from_linear(min(1.0, max(0.0, v))))) for v in lin)  # type: ignore[return-value]


def to_hex(color: OKLCH) -> str:
    return "#" + "".join(f"{round(v * 255):02x}" for v in oklch_to_srgb(color))


# ----------------------------------------------------------------- parsing

_HEX = re.compile(r"^#([0-9a-f]{3,8})$", re.I)
_FUNC = re.compile(r"^(rgba?|oklch)\((.*)\)$", re.I)


def parse_css_color(value: str) -> tuple[OKLCH, float] | None:
    """Parse hex / rgb() / rgba() / oklch(). Returns (color, alpha) or None."""
    v = value.strip().lower()
    if v in ("transparent", "", "none"):
        return None
    if m := _HEX.match(v):
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8):
            return None
        rgb = tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return srgb_to_oklch(rgb), alpha  # type: ignore[arg-type]
    if m := _FUNC.match(v):
        kind, body = m.group(1), m.group(2)
        parts = [p for p in re.split(r"[\s,/]+", body.strip()) if p]
        try:
            if kind.startswith("rgb"):
                if len(parts) < 3:
                    return None
                rgb = tuple(
                    float(p[:-1]) / 100 if p.endswith("%") else float(p) / 255 for p in parts[:3]
                )
                alpha = _alpha(parts[3]) if len(parts) > 3 else 1.0
                return srgb_to_oklch(rgb), alpha  # type: ignore[arg-type]
            l_raw, c_raw, h_raw = parts[:3]
            l = float(l_raw[:-1]) / 100 if l_raw.endswith("%") else float(l_raw)
            c = float(c_raw[:-1]) / 100 * 0.4 if c_raw.endswith("%") else float(c_raw)
            h = 0.0 if h_raw == "none" else float(h_raw.removesuffix("deg"))
            alpha = _alpha(parts[3]) if len(parts) > 3 else 1.0
            return OKLCH(l, c, h % 360), alpha
        except ValueError:
            return None
    return None


def _alpha(p: str) -> float:
    return float(p[:-1]) / 100 if p.endswith("%") else float(p)


# ---------------------------------------------------------------- contrast

def wcag_luminance(color: OKLCH) -> float:
    r, g, b = (_to_linear(v) for v in oklch_to_srgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_contrast(fg: OKLCH, bg: OKLCH) -> float:
    a, b = wcag_luminance(fg), wcag_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def apca_lc(text: OKLCH, bg: OKLCH) -> float:
    """APCA-W3 0.0.98G-4g lightness contrast. |Lc| >= 75 body, 60 UI/large, 45 large/muted."""

    def y(c: OKLCH) -> float:
        r, g, b = oklch_to_srgb(c)
        yy = 0.2126729 * r ** 2.4 + 0.7151522 * g ** 2.4 + 0.0721750 * b ** 2.4
        return yy + (0.022 - yy) ** 1.414 if yy < 0.022 else yy

    yt, yb = y(text), y(bg)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:  # dark text on light background
        s = (yb ** 0.56 - yt ** 0.57) * 1.14
        out = 0.0 if s < 0.1 else s - 0.027
    else:  # light text on dark background
        s = (yb ** 0.65 - yt ** 0.62) * 1.14
        out = 0.0 if s > -0.1 else s + 0.027
    return out * 100
