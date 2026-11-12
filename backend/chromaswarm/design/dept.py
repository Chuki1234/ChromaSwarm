"""B8 Design department: measures each live section and repairs what tokens can repair.

Decision 4: a fix is written to the workspace's tokens.css (then picked up by
HMR), never only applied through CSSOM, so what the user sees is what ships.
Fixes are deterministic engine operations:

* contrast  -> move the offending colour token's OKLCH lightness away from its
               background until WCAG + APCA pass (hue and chroma kept)
* grid-8pt  -> snap the spacing token that produced the value onto the 8pt scale

Anything a token cannot fix (missing section, line length, type off-scale) is
reported for the Developer department.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from chromaswarm.engines.color import OKLCH, apca_lc, gamut_map, parse_css_color, wcag_contrast
from chromaswarm.engines.spacing import snap
from chromaswarm.playwright_engine.swarm import ColorReading, Finding, SectionReport, _is_large

_DECL = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
SPACING_TOKENS = ("--section-y", "--grid-gap", "--card-padding", "--gutter")


class TokenChange(BaseModel):
    token: str
    old: str
    new: str
    reason: str


class TokenFile:
    """Edits the first (base) declaration of each custom property in tokens.css."""

    def __init__(self, css: str):
        self.css = css

    def values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, value in _DECL.findall(self.css):
            out.setdefault(name, value.strip())
        return out

    def replace_value(self, name: str, old: str, new: str) -> int:
        """Rewrite every declaration of `name` whose value is `old` (base and @media overrides)."""
        pattern = re.compile(rf"({re.escape(name)}\s*:\s*){re.escape(old)}(\s*;)")
        self.css, n = pattern.subn(lambda m: m.group(1) + new + m.group(2), self.css)
        return n

    def set(self, name: str, value: str) -> None:
        pattern = re.compile(rf"({re.escape(name)}\s*:\s*)([^;]+)(;)")
        self.css, n = pattern.subn(lambda m: m.group(1) + value + m.group(3), self.css, count=1)
        if not n:
            raise KeyError(name)


def _fmt(c: OKLCH) -> str:
    return f"oklch({c.l * 100:.1f}% {c.c:.3f} {c.h:.1f})"


def _closest_color_token(tokens: dict[str, str], rgb: str) -> str | None:
    target = parse_css_color(rgb)
    if not target:
        return None
    best, best_d = None, 0.02  # must be practically the same colour
    for name, value in tokens.items():
        parsed = parse_css_color(value)
        if not parsed:
            continue
        c, t = parsed[0], target[0]
        d = abs(c.l - t.l) + abs(c.c - t.c)
        if d < best_d:
            best, best_d = name, d
    return best


def fix_contrast(tokens: TokenFile, reading: ColorReading) -> TokenChange | None:
    values = tokens.values()
    name = _closest_color_token(values, reading.fg)
    bg = parse_css_color(reading.bg)
    if not name or not bg:
        return None
    fg = parse_css_color(values[name])[0]
    need_w, need_a = (3.0, 45) if _is_large(reading.font_size, reading.font_weight) else (4.5, 60)
    direction = -1 if bg[0].l > 0.5 else 1  # darker text on light ground, lighter on dark
    c = fg
    for _ in range(100):
        if wcag_contrast(c, bg[0]) >= need_w and abs(apca_lc(c, bg[0])) >= need_a:
            new = _fmt(gamut_map(c))
            tokens.set(name, new)
            return TokenChange(token=name, old=values[name], new=new,
                               reason=f"tương phản chưa đạt trên nền {reading.bg} (WCAG {reading.wcag}, Lc {reading.apca})")
        c = OKLCH(min(1.0, max(0.0, c.l + direction * 0.01)), c.c, c.h)
    return None


def fix_spacing(tokens: TokenFile, finding: Finding) -> TokenChange | None:
    if finding.value is None:
        return None
    old = f"{finding.value:g}px"
    new = f"{snap(finding.value)}px"
    for name in SPACING_TOKENS:
        if tokens.replace_value(name, old, new):
            return TokenChange(token=name, old=old, new=new, reason=finding.detail)
    return None


def repair(report: SectionReport, tokens: TokenFile) -> tuple[list[TokenChange], list[Finding]]:
    """Apply token fixes for this section; return (changes, findings left for the Developer)."""
    changes: list[TokenChange] = []
    leftover: list[Finding] = []
    for f in report.findings:
        change = None
        if f.rule == "contrast" and f.reading:
            change = fix_contrast(tokens, f.reading)
        elif f.rule == "grid-8pt":
            change = fix_spacing(tokens, f)
        if change:
            if not any(c.token == change.token for c in changes):
                changes.append(change)
        else:
            leftover.append(f)
    return changes, leftover
