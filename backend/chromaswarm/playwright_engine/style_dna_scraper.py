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
  const rootBg = getComputedStyle(document.body).backgroundColor;
  const htmlBg = getComputedStyle(document.documentElement).backgroundColor;
  out.backgrounds.push({ color: rootBg !== 'rgba(0, 0, 0, 0)' ? rootBg : htmlBg, area: vw * pageH * 0.25 });
  let n = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (n++ > MAX) break;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || px(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const w = Math.min(r.width, vw);
    if (cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)')
      out.backgrounds.push({ color: cs.backgroundColor, area: w * r.height });
    let chars = 0;
    for (const node of el.childNodes) if (node.nodeType === 3) chars += node.textContent.trim().length;
    if (chars > 0) out.texts.push({
      color: cs.color, chars, font_family: cs.fontFamily, font_size: px(cs.fontSize),
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


async def collect(page: Page, source_url: str | None = None) -> RawStyleSample:
    data = await page.evaluate(COLLECT_JS)
    data["source_url"] = source_url
    return RawStyleSample.model_validate(data)


async def scrape_url(url: str, screenshot_to: Path | None = None, width: int = 1440, height: int = 900) -> StyleDNA:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle", timeout=45_000)
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
