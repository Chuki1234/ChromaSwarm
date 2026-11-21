"""Clone mode: a quick look at the reference page before it is read.

One screenshot of the first screen (JPEG, as a data URL) and the page title, so the user can check
that the link is the page they mean. Nothing is stored beyond a small in-memory cache.
"""

from __future__ import annotations

import base64
import contextlib
from collections import OrderedDict

from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.style_dna_scraper import goto_ready
from pydantic import BaseModel

CACHE_SIZE = 24
_cache: OrderedDict[str, "PagePreview"] = OrderedDict()


class PagePreview(BaseModel):
    url: str  # where the page ended up (after redirects)
    title: str
    image: str  # data:image/jpeg;base64,...


async def page_preview(url: str, width: int = 1280, height: int = 800) -> PagePreview:
    if url in _cache:
        _cache.move_to_end(url)
        return _cache[url]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await goto_ready(page, url, 25_000, 10_000)
            with contextlib.suppress(Exception):  # fonts / hero images: a short wait, never the full settle
                await page.wait_for_load_state("networkidle", timeout=3_000)
            shot = await page.screenshot(type="jpeg", quality=70)
            title = (await page.title()) or url
            final = page.url
        finally:
            await browser.close()
    result = PagePreview(url=final, title=title[:120],
                         image="data:image/jpeg;base64," + base64.b64encode(shot).decode())
    _cache[url] = result
    while len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return result
