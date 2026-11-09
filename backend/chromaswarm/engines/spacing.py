"""8pt spatial grid + law of proximity (FRONTEND_STANDARDS.md §2.3, Pillar 4)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

SCALE: tuple[int, ...] = (4, 8, 12, 16, 24, 32, 48, 64, 80, 96, 128)
IGNORED_BELOW = 3  # 0-2px are hairlines/borders, not spacing decisions


def snap(px: float) -> int:
    return min(SCALE, key=lambda s: (abs(s - px), s))


class GridReport(BaseModel):
    checked: int
    on_grid: int
    adherence: float  # 0..1, the R_SpatialGrid term
    offenders: dict[str, int]  # value -> count


def grid_adherence(values: list[float]) -> GridReport:
    considered = [round(v, 2) for v in values if abs(v) >= IGNORED_BELOW]
    offenders: dict[str, int] = {}
    on = 0
    for v in considered:
        if abs(v) in SCALE:
            on += 1
        else:
            key = f"{abs(v):g}px"
            offenders[key] = offenders.get(key, 0) + 1
    n = len(considered)
    return GridReport(checked=n, on_grid=on, adherence=round(on / n, 4) if n else 1.0, offenders=offenders)


def proximity_ok(inline_gap: int, card_padding: int, section_gap: int) -> bool:
    """d_inline < d_card_padding < d_section (§2.3.2)."""
    return inline_gap < card_padding < section_gap


class Density(StrEnum):
    AIRY = "airy"
    BALANCED = "balanced"
    DENSE = "dense"


class SpatialSystem(BaseModel):
    density: Density
    container_max: int
    section_padding_desktop: int
    section_padding_mobile: int
    page_gutter_mobile: int
    page_gutter_desktop: int
    grid_gap: int
    card_padding: int
    inline_gap: int
    whitespace_target: str


# §1.2 Pillar 4. Dense section padding is listed as 40-56px in the standard,
# but neither value is on the 8pt scale; we use 48px.
DENSITY_PRESETS: dict[Density, SpatialSystem] = {
    Density.AIRY: SpatialSystem(density=Density.AIRY, container_max=1280, section_padding_desktop=128,
                                section_padding_mobile=64, page_gutter_mobile=24, page_gutter_desktop=64,
                                grid_gap=48, card_padding=32, inline_gap=12, whitespace_target=">= 45%"),
    Density.BALANCED: SpatialSystem(density=Density.BALANCED, container_max=1360,
                                    section_padding_desktop=80, section_padding_mobile=48,
                                    page_gutter_mobile=16, page_gutter_desktop=32, grid_gap=24,
                                    card_padding=24, inline_gap=8, whitespace_target="35-40%"),
    Density.DENSE: SpatialSystem(density=Density.DENSE, container_max=1440, section_padding_desktop=48,
                                 section_padding_mobile=32, page_gutter_mobile=16, page_gutter_desktop=24,
                                 grid_gap=16, card_padding=16, inline_gap=8,
                                 whitespace_target="dividers 1px"),
}
