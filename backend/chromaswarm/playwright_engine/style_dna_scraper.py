"""B4/B5: read computed styles from a reference URL with Playwright.

The in-page script returns only aggregate measurements (colors + painted area,
font metrics weighted by character count, spacing values, radii, motion).
It never returns text content, tag names, class names, attributes, image URLs
or tree structure — the anti-cloning boundary is enforced at the source.
"""

from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page, async_playwright

from chromaswarm.engines.style_dna import RawStyleSample, StyleDNA, analyze

COLLECT_JS = r"""
() => {
  const MAX = 4000;
  const vw = innerWidth, pageH = document.documentElement.scrollHeight;
  const px = v => parseFloat(v) || 0;
  const out = { viewport_w: vw, viewport_h: innerHeight, page_height: pageH,
    backgrounds: [], texts: [], spacing: [], block_padding: [], radii: [], border_count: 0,
    shadow_count: 0, backdrop_blur_count: 0, motion: [] };
  // Chromium serialises oklch()/color-mix() colours as lab()/oklch(none ...): paint one pixel and
  // read it back so the engines always receive sRGB.
  const pix = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const srgb = c => {
    pix.clearRect(0, 0, 1, 1); pix.fillStyle = '#000'; pix.fillStyle = c; pix.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = pix.getImageData(0, 0, 1, 1).data;
    return a === 0 ? 'rgba(0, 0, 0, 0)' : (a < 255 ? `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})` : `rgb(${r}, ${g}, ${b})`);
  };
  const rootBg = srgb(getComputedStyle(document.body).backgroundColor);
  const htmlBg = srgb(getComputedStyle(document.documentElement).backgroundColor);
  out.backgrounds.push({ color: rootBg !== 'rgba(0, 0, 0, 0)' ? rootBg : htmlBg, area: vw * pageH * 0.25 });
  let n = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (n++ > MAX) break;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || px(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const w = Math.min(r.width, vw);
    const bg = srgb(cs.backgroundColor);
    if (bg !== 'rgba(0, 0, 0, 0)')
      out.backgrounds.push({ color: bg, area: w * r.height });
    let chars = 0;
    for (const node of el.childNodes) if (node.nodeType === 3) chars += node.textContent.trim().length;
    if (chars > 0) out.texts.push({
      color: srgb(cs.color), chars, font_family: cs.fontFamily, font_size: px(cs.fontSize),
      font_weight: parseInt(cs.fontWeight) || 400,
      line_height: cs.lineHeight === 'normal' ? null : px(cs.lineHeight) / px(cs.fontSize),
      uppercase: cs.textTransform === 'uppercase', letter_spacing: px(cs.letterSpacing) });
    for (const k of ['paddingTop','paddingRight','paddingBottom','paddingLeft',
                     'marginTop','marginBottom','rowGap','columnGap']) {
      const v = px(cs[k]); if (v) out.spacing.push(v);
    }
    if (w >= vw * 0.6) for (const k of ['paddingTop', 'paddingBottom']) {
      const v = px(cs[k]); if (v >= 24) out.block_padding.push(v);
    }
    const rad = px(cs.borderTopLeftRadius);
    if (rad < 9999 && (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || px(cs.borderTopWidth) > 0)) out.radii.push(rad);
    if (px(cs.borderTopWidth) > 0 || px(cs.borderBottomWidth) > 0) out.border_count++;
    if (cs.boxShadow && cs.boxShadow !== 'none') out.shadow_count++;
    if (cs.backdropFilter && cs.backdropFilter.includes('blur')) out.backdrop_blur_count++;
    const d = cs.transitionDuration.split(',')[0];
    const ms = d.endsWith('ms') ? px(d) : px(d) * 1000;
    if (ms > 0) out.motion.push({ duration_ms: ms, easing: cs.transitionTimingFunction.split(/,(?![^(]*\))/)[0].trim() });
  }
  return out;
}
"""


SETTLE_JS = """async () => {
  // Scroll through the page so lazy images load and scroll-revealed content becomes visible,
  // then return to the top. Bounded: at most ~40 steps.
  const step = Math.max(400, innerHeight * 0.8);
  for (let y = 0, n = 0; y < document.documentElement.scrollHeight && n < 40; y += step, n++) {
    scrollTo(0, y);
    await new Promise(r => setTimeout(r, 120));
  }
  scrollTo(0, document.documentElement.scrollHeight);
  await new Promise(r => setTimeout(r, 400));
  scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 300));
}"""


async def goto_ready(page: Page, url: str, timeout_ms: int = 45_000, load_ms: int = 20_000) -> None:
    """Open a page as soon as its HTML is in, then give `load` up to `load_ms`: some sites keep a resource
    loading forever (a video, a long poll) and never fire it, although the page is long on screen."""
    import contextlib

    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("load", timeout=load_ms)


async def open_settled(page: Page, url: str, timeout_ms: int = 45_000) -> None:
    """Open a page robustly: wait for `load` (≤20s after the HTML), give the network a short chance to go idle
    (pages with analytics, video or live connections never do), then scroll through it once."""
    import contextlib

    await goto_ready(page, url, timeout_ms)
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=8_000)
    with contextlib.suppress(Exception):
        await page.evaluate(SETTLE_JS)


async def collect(page: Page, source_url: str | None = None) -> RawStyleSample:
    data = await page.evaluate(COLLECT_JS)
    data["source_url"] = source_url
    return RawStyleSample.model_validate(data)


async def scrape_url(url: str, screenshot_to: Path | None = None, width: int = 1440, height: int = 900) -> StyleDNA:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await open_settled(page, url)
            if screenshot_to:
                await page.screenshot(path=str(screenshot_to), full_page=True)
            return analyze(await collect(page, url))
        finally:
            await browser.close()


async def scrape_html(html: str, width: int = 1440, height: int = 900) -> StyleDNA:
    """Same pipeline on inline HTML (tests, uploaded snapshots)."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.set_content(html)
            return analyze(await collect(page))
        finally:
            await browser.close()
