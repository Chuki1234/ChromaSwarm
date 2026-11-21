"""B5: Style DNA read from a reference screenshot the user uploaded (spec B4/B5).

With a link, Playwright measures the page (playwright_engine/style_dna_scraper.py). With only a
screenshot, a vision model looks at it and answers a fixed form; every answer is validated here
(hex colours parsed, enums checked, radius bounded) and turned into a StyleDNA marked
`from_screenshot`, so DESIGN.md says where it came from. Only design traits are learned — the
anti-cloning boundary of DESIGN.md applies exactly as for a link.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from chromaswarm.engines.color import parse_css_color, to_hex
from chromaswarm.engines.style_dna import ColorShare, StyleDNA

log = logging.getLogger(__name__)

SYSTEM = """You are a senior visual designer. Look at the screenshot of a web page and describe its
DESIGN TRAITS only (never its text, brand or content). Answer JSON only:
{"is_dark": bool, "background": "#rrggbb", "text": "#rrggbb", "accent": "#rrggbb" or null,
 "accent_usage": "restrained" | "generous" | "none",
 "density": "airy" | "balanced" | "dense",
 "radius_px": number (typical corner radius of cards/buttons, 0 if sharp),
 "separation": "borders" | "shadows" | "whitespace",
 "heading_style": "serif" | "sans" | "display" | "mono",
 "uppercase_labels": bool,
 "notes": [up to 4 short sentences on layout and type that a designer could reuse, e.g.
           "Headlines are very large and left-aligned with a narrow measure."]}
Colours are what you see most: the page background, body text and the one brand/action colour."""

ENUMS = {"accent_usage": {"restrained", "generous", "none"}, "density": {"airy", "balanced", "dense"},
         "separation": {"borders", "shadows", "whitespace"}, "heading_style": {"serif", "sans", "display", "mono"}}


def _hex(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = parse_css_color(value.strip())
    return to_hex(parsed[0]) if parsed else None


def validate(raw: dict) -> dict | None:
    """The model's answer, kept only when it is well-formed."""
    bg, text = _hex(raw.get("background")), _hex(raw.get("text"))
    if not bg or not text or not isinstance(raw.get("is_dark"), bool):
        return None
    out: dict[str, Any] = {"is_dark": raw["is_dark"], "background": bg, "text": text, "accent": _hex(raw.get("accent"))}
    for key, allowed in ENUMS.items():
        out[key] = raw.get(key) if raw.get(key) in allowed else None
    try:
        r = float(raw.get("radius_px"))
        out["radius_px"] = r if 0 <= r <= 48 else None
    except (TypeError, ValueError):
        out["radius_px"] = None
    out["uppercase_labels"] = raw.get("uppercase_labels") is True
    notes = raw.get("notes") if isinstance(raw.get("notes"), list) else []
    out["notes"] = [n.strip()[:160] for n in notes if isinstance(n, str) and 8 <= len(n.strip())][:4]
    return out


def to_dna(reading: dict) -> StyleDNA:
    bg = parse_css_color(reading["background"])[0]
    temp = "neutral" if bg.c < 0.008 else "warm" if 30 <= bg.h <= 110 else "cool"
    accents = [ColorShare(css=reading["accent"], share=0.08)] if reading.get("accent") else []
    return StyleDNA(
        source_url=None, surfaces=[ColorShare(css=reading["background"], share=0.7)],
        text_colors=[ColorShare(css=reading["text"], share=1.0)], accents=accents,
        area_split={}, neutral_temperature=temp, neutral_hue=bg.h if bg.c >= 0.008 else None,
        accent_usage=reading.get("accent_usage") or ("restrained" if accents else "none"), is_dark=reading["is_dark"],
        fonts=[], heading_body_weight_contrast=0, base_font_px=None, type_scale_ratio=None,
        uppercase_labels=reading["uppercase_labels"], spacing_adherence=0.0, common_spacing=[],
        density=reading.get("density") or "balanced", radius_median=reading.get("radius_px"),
        separation=reading.get("separation") or "whitespace", motion_median_ms=None, motion_easing=None,
        backdrop_blur=False, from_screenshot=True,
        notes=[*([f"Headings read as {reading['heading_style']}."] if reading.get("heading_style") else []), *reading["notes"]],
    )


def data_uri(path: Path) -> str:
    kind = {"png": "png", "jpg": "jpeg", "webp": "webp", "gif": "gif"}.get(path.suffix.lstrip("."), "png")
    return f"data:image/{kind};base64," + base64.b64encode(path.read_bytes()).decode()


class ScreenshotReader:
    """(path) -> validated reading dict | None. Never raises: a failed read leaves B5 as without a screenshot."""

    def __init__(self, vision):
        self.vision = vision
        self.name = f"vision:{getattr(vision, 'model', '?')}"

    def __call__(self, path: Path) -> dict | None:
        try:
            raw = self.vision.complete_json(SYSTEM, "Describe the design traits of this page.", images=[data_uri(path)],
                                            max_tokens=700)
        except Exception as e:  # noqa: BLE001
            log.warning("screenshot read failed: %s", e)
            return None
        return validate(raw if isinstance(raw, dict) else {})


def build_screenshot_reader(env: dict[str, str] | None = None) -> ScreenshotReader | None:
    from chromaswarm.agents.llm import LLMConfig, OpenAICompatChat
    cfg = LLMConfig.from_env(env)
    return ScreenshotReader(OpenAICompatChat(cfg.for_role("vision"))) if cfg else None
