"""Clone mode fonts: keep the reference's own typefaces.

A family is looked up on the two free font hosts a rebuilt page can load from:
Google Fonts (the css2 response lists a `/* vietnamese */` subset when the font has Vietnamese
glyphs) and Fontshare (free for commercial use; Latin only). A family found on neither is
self-hosted or licensed by the site: it cannot be shipped, so the preset font stands in.

When a kept font has no Vietnamese glyphs, a Vietnamese-capable fallback of the same kind is put
right after it in the CSS font stack: the browser draws only the accented letters with it, so
Vietnamese text never shows broken diacritics.
"""

from __future__ import annotations

import re

import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from functools import lru_cache

from pydantic import BaseModel

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")  # Google serves per-subset CSS (and its subset comments) only to modern browsers
WEIGHTS_GOOGLE = "wght@400;500;600;700"
SERIF_HINTS = ("serif", "playfair", "garamond", "times", "georgia", "lora", "fraunces", "cormorant", "merriweather",
               "domaine", "tiempos", "canela", "ogg", "sectra", "freight", "recoleta", "editorial", "caslon", "baskerville")
# Licensed families no free host serves -> the closest free, Vietnamese-capable Google font of the same feel.
SIMILAR = {"favorit": "Inter", "graphik": "Inter", "circular": "Inter", "gt america": "Inter", "sf pro": "Inter",
           "helvetica": "Inter", "neue montreal": "Inter", "neue haas": "Inter", "söhne": "Inter", "sohne": "Inter",
           "aeonik": "Inter", "satoshi": "Inter", "general sans": "Inter", "suisse": "Inter", "untitled sans": "Inter"}
_SUFFIX = re.compile(r"\s+(website|web|variable|vf|var|text|pro web)$", re.IGNORECASE)
FALLBACK_SERIF = "Playfair Display"
FALLBACK_SANS = "Be Vietnam Pro"


class FontSource(BaseModel):
    family: str
    provider: str | None  # "google" | "fontshare" | None (not loadable: self-hosted / licensed)
    css_url: str | None
    vietnamese: bool
    fallback: str  # Vietnamese-capable Google font of the same kind (serif / sans)
    original: str | None = None  # the reference's own (licensed) family when `family` is a free stand-in for it


Fetch = Callable[[str], tuple[int, str]]


def google_css_url(families: list[str]) -> str:
    return ("https://fonts.googleapis.com/css2?"
            + "&".join("family=" + urllib.parse.quote_plus(f) + ":" + WEIGHTS_GOOGLE for f in families)
            + "&display=swap")


def fontshare_css_url(family: str) -> str:
    slug = family.strip().lower().replace(" ", "-")
    return f"https://api.fontshare.com/v2/css?f[]={urllib.parse.quote(slug)}@400,500,600,700&display=swap"


def fallback_for(family: str) -> str:
    return FALLBACK_SERIF if any(h in family.lower() for h in SERIF_HINTS) else FALLBACK_SANS


def _fetch(url: str) -> tuple[int, str]:
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), context=ctx, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""


def resolve_font(family: str, fetch: Fetch = _fetch) -> FontSource:
    """Where this family can be loaded from, and whether it draws Vietnamese. A site-renamed copy of a free font
    ("Inter Website") is found under its real name; a licensed one gets the closest free font of its kind."""
    family = family.strip().strip("'\"")
    plain = _SUFFIX.sub("", family).strip()
    if plain and plain.lower() != family.lower():
        found = resolve_font(plain, fetch)
        if found.provider:
            return found
    src = _resolve(family, fetch)
    if src.provider:
        return src
    name = family.lower()
    stand_in = next((free for key, free in SIMILAR.items() if key in name.replace("abc", "").strip() or key in name), None)
    stand_in = stand_in or src.fallback  # unknown licensed font: the free font of its kind (serif / sans)
    return FontSource(family=stand_in, provider="google", css_url=google_css_url([stand_in]), vietnamese=True,
                      fallback=src.fallback, original=family)


def _resolve(family: str, fetch: Fetch = _fetch) -> FontSource:
    fallback = fallback_for(family)
    try:
        status, css = fetch(google_css_url([family]))
        if status == 200 and "@font-face" in css:
            return FontSource(family=family, provider="google", css_url=google_css_url([family]),
                              vietnamese="/* vietnamese */" in css, fallback=fallback)
        url = fontshare_css_url(family)
        status, css = fetch(url)
        if status == 200 and "@font-face" in css:
            return FontSource(family=family, provider="fontshare", css_url=url, vietnamese=False, fallback=fallback)
    except Exception:  # noqa: BLE001 — offline / host down: treat as not loadable, the build goes on
        pass
    return FontSource(family=family, provider=None, css_url=None, vietnamese=False, fallback=fallback)


@lru_cache(maxsize=256)
def resolve_font_cached(family: str) -> FontSource:
    return resolve_font(family)


def font_note(src: FontSource) -> str | None:
    """What the user is told about this font (None when it is kept as is)."""
    if src.original:
        return (f"Font '{src.original}' là font riêng của trang mẫu (không có nguồn tải miễn phí); "
                f"dùng {src.family}, font miễn phí gần giống nhất.")
    if src.provider is None:
        return (f"Font '{src.family}' là font riêng của trang mẫu (không có nguồn tải miễn phí); "
                f"dùng font gần giống của preset.")
    if not src.vietnamese:
        return (f"Font '{src.family}' được giữ nguyên nhưng không có dấu tiếng Việt: "
                f"chữ có dấu hiển thị bằng {src.fallback}.")
    return None
