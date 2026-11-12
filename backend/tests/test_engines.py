import pytest

from chromaswarm.engines.color import apca_lc, wcag_contrast
from chromaswarm.engines.palette import Mode, Role, generate_palette
from chromaswarm.engines.spacing import DENSITY_PRESETS, SCALE, grid_adherence, proximity_ok, snap
from chromaswarm.engines.typography import Ratio, build_scale

SEEDS = ["#3b82f6", "#f59e0b", "#0f766e", "#b91c1c", "#111111", "#a78bfa", "#facc15"]


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("mode", list(Mode))
def test_palette_passes_all_contrast_checks(seed, mode):
    p = generate_palette(seed, mode)
    failed = [c for c in p.checks if not c.passed]
    assert not failed, failed


def test_palette_structure_light():
    p = generate_palette("#3b82f6", Mode.LIGHT)
    roles = {t.name: t.role for t in p.tokens}
    assert roles["bg-primary"] is Role.DOMINANT
    assert roles["text-primary"] is Role.STRUCTURAL
    assert roles["accent"] is Role.ACCENT
    bg = p.get("bg-primary")
    assert bg.hex != "#ffffff" and 0.003 <= bg.c <= 0.012  # tinted, never pure white
    assert abs(bg.h - p.brand_hue) < 1
    accent = p.get("accent")
    assert 0.16 - 1e-3 <= accent.c <= 0.26  # chroma window (may shrink for gamut)


def test_warm_paper_uses_warm_neutrals():
    p = generate_palette("#3b82f6", Mode.WARM_PAPER)
    assert p.get("bg-primary").h == pytest.approx(75, abs=1)
    assert p.get("accent").h == pytest.approx(p.brand_hue, abs=1)


def test_dark_mode_never_pure_black():
    p = generate_palette("#3b82f6", Mode.DARK)
    assert p.get("bg-primary").hex != "#000000"
    assert p.get("bg-elevated").l > p.get("bg-primary").l


def test_accent_fg_contrast():
    p = generate_palette("#facc15", Mode.LIGHT)  # bright yellow seed -> dark text expected
    a, fg = p.get("accent").color, p.get("accent-fg").color
    assert wcag_contrast(fg, a) >= 4.5 and abs(apca_lc(fg, a)) >= 60


def test_snap_and_adherence():
    assert snap(13) == 12 and snap(27) == 24 and snap(19) == 16 and snap(200) == 128
    r = grid_adherence([0, 1, 8, 16, 13, 27, 24, 24])
    assert r.checked == 6 and r.on_grid == 4
    assert r.offenders == {"13px": 1, "27px": 1}
    assert r.adherence == pytest.approx(4 / 6, abs=1e-3)


def test_density_presets_obey_grid_and_proximity():
    for preset in DENSITY_PRESETS.values():
        for field in ("section_padding_desktop", "section_padding_mobile", "grid_gap", "card_padding",
                      "inline_gap", "page_gutter_mobile", "page_gutter_desktop"):
            assert getattr(preset, field) in SCALE, (preset.density, field)
        assert proximity_ok(preset.inline_gap, preset.card_padding, preset.section_padding_desktop)
        assert preset.page_gutter_mobile >= 16


def test_type_scale():
    s = build_scale(16, Ratio.MAJOR_THIRD, "Instrument Serif", "Inter")
    by = {st.name: st for st in s.steps}
    assert by["body"].px_max == 16
    assert by["h1"].px_max == pytest.approx(16 * 1.25 ** 5, abs=0.01)
    assert by["display"].css_size.startswith("clamp(")
    assert by["body"].css_size == "1.000rem"
    assert by["display"].letter_spacing.startswith("-0.0")
    assert by["display"].px_min < by["display"].px_max
    assert by["display"].line_height == 1.1 and by["body"].line_height == 1.55


@pytest.mark.parametrize("ratio", list(Ratio))
def test_type_scale_monotonic_on_mobile_and_desktop(ratio):
    s = build_scale(16, ratio, "A", "B")
    mins = [st.px_min for st in s.steps]
    maxs = [st.px_max for st in s.steps]
    assert mins == sorted(mins) and len(set(mins)) == len(mins)
    assert maxs == sorted(maxs)


def test_every_preset_font_supports_vietnamese():
    from chromaswarm.engines.presets import THEMES, VIETNAMESE_FONTS

    for preset in THEMES.values():
        for font in filter(None, (preset.heading_font, preset.body_font, preset.mono_font)):
            assert font in VIETNAMESE_FONTS, f"{preset.theme}: {font} has no Vietnamese subset"
