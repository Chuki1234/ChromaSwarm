"""OKLCH 60-30-10 palette generator (FRONTEND_STANDARDS.md §2.1).

seed color -> brand hue -> neutrals tinted with that hue (60%), 3-tier text
and border (30%), accent + semantic states (10%). The accent's lightness is
searched so its on-color text meets WCAG >= 4.5:1 AND APCA |Lc| >= 60.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from chromaswarm.engines.color import OKLCH, apca_lc, gamut_map, parse_css_color, to_hex, wcag_contrast


class Mode(StrEnum):
    LIGHT = "light"
    WARM_PAPER = "warm-paper"
    DARK = "dark"


class Role(StrEnum):
    DOMINANT = "60"
    STRUCTURAL = "30"
    ACCENT = "10"


class Token(BaseModel):
    name: str
    role: Role
    l: float
    c: float
    h: float
    css: str
    hex: str

    @classmethod
    def of(cls, name: str, role: Role, color: OKLCH) -> "Token":
        color = gamut_map(color)
        return cls(name=name, role=role, l=round(color.l, 4), c=round(color.c, 4), h=round(color.h, 1),
                   css=color.css(), hex=to_hex(color))

    @property
    def color(self) -> OKLCH:
        return OKLCH(self.l, self.c, self.h)


class ContrastCheck(BaseModel):
    fg: str
    bg: str
    wcag: float
    apca: float
    required_apca: float
    required_wcag: float
    passed: bool


class Palette(BaseModel):
    mode: Mode
    brand_hue: float
    neutral_hue: float
    tokens: list[Token]
    checks: list[ContrastCheck]

    def get(self, name: str) -> Token:
        return next(t for t in self.tokens if t.name == name)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


ACCENT_C_RANGE = (0.16, 0.26)
WARM_NEUTRAL_HUE = 75.0

# (L, C) per neutral token, from §2.1.
NEUTRALS = {
    Mode.LIGHT: {
        "bg-primary": (0.985, 0.005), "bg-surface": (0.96, 0.008), "bg-elevated": (0.995, 0.003),
        "text-primary": (0.15, 0.015), "text-secondary": (0.42, 0.015), "text-muted": (0.58, 0.015),
        "border-subtle": (0.90, 0.010),
    },
    Mode.WARM_PAPER: {
        "bg-primary": (0.97, 0.012), "bg-surface": (0.945, 0.014), "bg-elevated": (0.99, 0.006),
        "text-primary": (0.18, 0.015), "text-secondary": (0.42, 0.015), "text-muted": (0.56, 0.015),
        "border-subtle": (0.88, 0.014),
    },
    Mode.DARK: {
        "bg-primary": (0.13, 0.010), "bg-surface": (0.16, 0.012), "bg-elevated": (0.18, 0.015),
        "text-primary": (0.96, 0.015), "text-secondary": (0.78, 0.015), "text-muted": (0.68, 0.015),
        "border-subtle": (0.24, 0.015),
    },
}
# Deviation from §2.1 (dark mode): text-secondary L=72% gives APCA |Lc| ~53 and
# text-muted L=52% gives ~24 on bg L=13% — both under the 60 / 45 floors used
# here. Minimum passing values are ~77% and ~68%; we use 78% / 68%.

SEMANTIC_HUES = {"success": 150.0, "warning": 75.0, "danger": 27.0}

# (fg token, bg token, required |APCA|, required WCAG)
REQUIRED = [
    ("text-primary", "bg-primary", 75, 7.0),
    ("text-primary", "bg-surface", 75, 7.0),
    ("text-secondary", "bg-primary", 60, 4.5),
    ("text-muted", "bg-primary", 45, 3.0),
    ("accent-fg", "accent", 60, 4.5),
]


def _fits(fg: OKLCH, bg: OKLCH, apca: float, wcag: float) -> bool:
    return abs(apca_lc(fg, bg)) >= apca and wcag_contrast(fg, bg) >= wcag


def _search_accent(seed: OKLCH, light_fg: OKLCH, dark_fg: OKLCH) -> tuple[OKLCH, OKLCH]:
    """Closest lightness to the seed for which white-ish or dark text on it passes."""
    c = min(max(seed.c, ACCENT_C_RANGE[0]), ACCENT_C_RANGE[1])
    steps = [i / 200 for i in range(0, 61)]  # explore +-30% L in 0.5% steps
    for d in steps:
        for l in (seed.l - d, seed.l + d):
            if not 0.2 <= l <= 0.9:
                continue
            cand = gamut_map(OKLCH(l, c, seed.h))
            for fg in (light_fg, dark_fg):
                if _fits(fg, cand, 60, 4.5):
                    return cand, fg
    raise ValueError(f"No accessible accent found for seed {seed.css()}")


def generate_palette(seed: str | OKLCH, mode: Mode = Mode.LIGHT) -> Palette:
    seed_color = parse_css_color(seed)[0] if isinstance(seed, str) else seed  # type: ignore[index]
    brand_h = seed_color.h
    neutral_h = WARM_NEUTRAL_HUE if mode is Mode.WARM_PAPER else brand_h

    tokens: list[Token] = []
    for name, (l, c) in NEUTRALS[mode].items():
        role = Role.DOMINANT if name.startswith("bg-") else Role.STRUCTURAL
        tokens.append(Token.of(name, role, OKLCH(l, c, neutral_h)))

    light_fg = OKLCH(0.985, 0.005, brand_h)
    dark_fg = OKLCH(0.15, 0.015, brand_h)
    accent, accent_fg = _search_accent(seed_color, light_fg, dark_fg)
    hover_dl = -0.06 if mode is not Mode.DARK else 0.06
    tokens += [
        Token.of("accent", Role.ACCENT, accent),
        Token.of("accent-hover", Role.ACCENT, accent.with_(l=accent.l + hover_dl)),
        Token.of("accent-fg", Role.ACCENT, accent_fg),
    ]
    for name, h in SEMANTIC_HUES.items():
        sem, _ = _search_accent(OKLCH(accent.l, 0.16, h), light_fg, dark_fg)
        tokens.append(Token.of(name, Role.ACCENT, sem))

    by_name = {t.name: t.color for t in tokens}
    checks = []
    for fg, bg, req_apca, req_wcag in REQUIRED:
        a = apca_lc(by_name[fg], by_name[bg])
        w = wcag_contrast(by_name[fg], by_name[bg])
        checks.append(ContrastCheck(fg=fg, bg=bg, wcag=round(w, 2), apca=round(a, 1),
                                    required_apca=req_apca, required_wcag=req_wcag,
                                    passed=abs(a) >= req_apca and w >= req_wcag))
    return Palette(mode=mode, brand_hue=round(brand_h, 1), neutral_hue=round(neutral_h, 1),
                   tokens=tokens, checks=checks)
