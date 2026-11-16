"""Clone fidelity score: pure scoring on snapshots, plus one real read of two local pages."""

import asyncio
from pathlib import Path

from chromaswarm.clone.fidelity import SectionShape, Snapshot, align, colour_similarity, score, snapshot_url
from chromaswarm.engines.style_dna import ColorShare, StyleDNA


def dna(surface="#ffffff", text="#111111", accent="#eb3f02", base=16.0) -> StyleDNA:
    shares = lambda c: [ColorShare(css=c, share=1.0)] if c else []  # noqa: E731
    return StyleDNA(source_url=None, surfaces=shares(surface), text_colors=shares(text), accents=shares(accent),
                    area_split={}, neutral_temperature="neutral", neutral_hue=None, accent_usage="restrained",
                    is_dark=False, fonts=[], heading_body_weight_contrast=0, base_font_px=base,
                    type_scale_ratio=None, uppercase_labels=False, spacing_adherence=1.0, common_spacing=[],
                    density="balanced", radius_median=None, separation="whitespace", motion_median_ms=None,
                    motion_easing=None, backdrop_blur=False)


def snap(kinds_heights, width=1200, d=None) -> Snapshot:
    shapes = [SectionShape(kind=k, height=h) for k, h in kinds_heights]
    return Snapshot(url="x", sections=shapes, page_height=sum(h for _, h in kinds_heights),
                    content_width=width, dna=d or dna())


PAGE = [("sticky-bar", 80), ("split-7-5", 600), ("bento", 900), ("testimonials", 500), ("footer-columns", 300)]


def test_identical_pages_score_100():
    f = score(snap(PAGE), snap(PAGE))
    assert f.total == 100 and all(v == 1 for v in f.parts.values()) and not f.notes


def test_wrong_kind_in_the_right_family_earns_half_credit():
    clone = [("sticky-bar", 80), ("hero-text", 600), ("grid-4", 900), ("testimonials", 500), ("footer-columns", 300)]
    f = score(snap(PAGE), snap(clone))
    assert f.parts["structure"] == 0.8  # 3 exact + 2 family (0.5 each) of 5
    assert [m.match for m in f.sections] == ["exact", "family", "family", "exact", "exact"]
    assert f.parts["proportions"] == 1


def test_missing_section_and_shifted_heights_are_penalised():
    clone = [("sticky-bar", 80), ("split-7-5", 1200), ("testimonials", 500), ("footer-columns", 300)]
    f = score(snap(PAGE), snap(clone))
    assert any(m.match == "missing" and m.original.kind == "bento" for m in f.sections)
    assert f.parts["structure"] == 0.8 and f.parts["proportions"] < 0.8
    assert any("Thiếu" in n and "bento" in n for n in f.notes)


def test_extra_section_is_reported():
    clone = PAGE[:3] + [("full-bleed-band", 300)] + PAGE[3:]
    f = score(snap(PAGE), snap(clone))
    assert [m.match for m in f.sections].count("extra") == 1 and any("Thừa" in n for n in f.notes)


def test_style_and_width_differences_lower_the_score():
    narrow = snap(PAGE, width=640)
    other = snap(PAGE, width=1200, d=dna(surface="#0b0b0f", text="#f5f5f5", accent="#2563eb", base=18))
    f = score(narrow, other)
    assert f.parts["width"] < 0.6 and f.parts["style"] < 0.4 and f.total < 85  # structure still identical
    assert colour_similarity("#eb3f02", "#eb3f02") == 1 and colour_similarity("#000000", "#ffffff") == 0
    assert colour_similarity(None, None) == 1 and colour_similarity("#eb3f02", None) == 0.5


def test_align_keeps_page_order():
    a = [SectionShape(kind=k, height=1) for k in ("sticky-bar", "gallery", "footer-columns")]
    b = [SectionShape(kind=k, height=1) for k in ("sticky-bar", "footer-columns")]
    assert [m.match for m in align(a, b)] == ["exact", "missing", "exact"]


DEMO = (Path(__file__).parents[1] / "chromaswarm/playwright_engine/fixtures/demo_landing.html").resolve().as_uri()


def test_a_page_read_against_itself_scores_100():
    s = asyncio.run(snapshot_url(DEMO))
    assert s.sections and s.page_height > 0
    assert score(s, s).total == 100
