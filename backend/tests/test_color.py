import pytest

from chromaswarm.engines.color import (
    OKLCH,
    apca_lc,
    gamut_map,
    in_gamut,
    parse_css_color,
    srgb_to_oklch,
    to_hex,
    wcag_contrast,
)


@pytest.mark.parametrize("hex_", ["#ffffff", "#000000", "#ff0000", "#3b82f6", "#f59e0b", "#1a2b3c"])
def test_hex_roundtrip(hex_):
    color, alpha = parse_css_color(hex_)
    assert alpha == 1.0
    assert to_hex(color) == hex_


def test_known_oklch_values():
    white = srgb_to_oklch((1, 1, 1))
    assert white.l == pytest.approx(1.0, abs=1e-4) and white.c < 1e-4
    red = srgb_to_oklch((1, 0, 0))  # reference: oklch(62.8% 0.2577 29.23)
    assert red.l == pytest.approx(0.628, abs=1e-3)
    assert red.c == pytest.approx(0.2577, abs=1e-3)
    assert red.h == pytest.approx(29.23, abs=0.1)


def test_parse_variants():
    assert parse_css_color("transparent") is None
    c, a = parse_css_color("rgba(0, 0, 0, 0.5)")
    assert a == 0.5 and c.l < 0.01
    c, a = parse_css_color("rgb(255 255 255 / 20%)")
    assert a == pytest.approx(0.2)
    c, _ = parse_css_color("oklch(62.8% 0.2577 29.23)")
    assert to_hex(c) == "#ff0000"


def test_gamut_mapping_keeps_hue_and_lightness():
    vivid = OKLCH(0.7, 0.4, 145)
    assert not in_gamut(vivid)
    mapped = gamut_map(vivid)
    assert in_gamut(mapped)
    assert mapped.l == vivid.l and mapped.h == vivid.h and mapped.c < vivid.c


def test_wcag_contrast_extremes():
    black, white = OKLCH(0, 0, 0), OKLCH(1, 0, 0)
    assert wcag_contrast(black, white) == pytest.approx(21, abs=0.01)
    assert wcag_contrast(white, white) == pytest.approx(1)


def test_apca_reference_values():
    # Reference pairs from the APCA-W3 test suite (0.0.98G-4g).
    def lc(t, b):
        return apca_lc(parse_css_color(t)[0], parse_css_color(b)[0])

    assert lc("#888888", "#ffffff") == pytest.approx(63.06, abs=0.1)
    assert lc("#ffffff", "#888888") == pytest.approx(-68.54, abs=0.1)
    assert lc("#000000", "#aaaaaa") == pytest.approx(58.15, abs=0.1)
    assert lc("#aaaaaa", "#000000") == pytest.approx(-56.24, abs=0.1)
