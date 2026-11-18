"""Clone mode: read the reference page's animations and effects, so the rebuild moves like it.

Measured in the browser while the page is opened (no content is read):

- scroll reveals   elements below the fold that start hidden / offset and end visible after scrolling
                   (AOS, GSAP ScrollTrigger, Framer Motion, IntersectionObserver...); 3+ revealed siblings
                   under one parent = a staggered reveal
- parallax         elements that move at a different speed than the scroll
- marquee          infinite CSS animations that slide horizontally, or wide tracks that keep moving
- hover effects    a sample of cards, rows, links and buttons is hovered for real: lift (translate up /
                   shadow / scale), image zoom, a preview image that appears, an underline that grows
- page-wide        sticky header with a blurred background, smooth scrolling, animation libraries and
                   things CSS cannot rebuild (custom cursors, WebGL canvases)

Each section gets catalogue effect ids (mcp_motion/server.py builds them as CSS).
"""

from __future__ import annotations

import asyncio
import contextlib

from playwright.async_api import Page

PRE_JS = r"""() => {
  // Below-the-fold elements that start hidden, offset or clipped: candidates for a scroll reveal.
  const vh = innerHeight, pre = new Map();
  const ident = t => !t || t === "none" || t === "matrix(1, 0, 0, 1, 0, 0)";
  for (const el of document.body.querySelectorAll("*")) {
    if (pre.size >= 3000) break;
    const r = el.getBoundingClientRect();
    if (r.top < vh || r.width < 20 || r.height < 10) continue;
    const cs = getComputedStyle(el), op = parseFloat(cs.opacity);
    if (op < 0.99 || !ident(cs.transform) || cs.visibility === "hidden" || cs.clipPath !== "none")
      pre.set(el, { op, tf: cs.transform, vis: cs.visibility, clip: cs.clipPath });
  }
  window.__csPre = pre;
  return pre.size;
}"""

PARALLAX_JS = r"""async () => {
  // Elements whose position changes at a different rate than the scroll.
  const vh = innerHeight, y0 = Math.round(vh * 0.8), step = 400;
  scrollTo(0, y0); await new Promise(r => setTimeout(r, 250));
  const els = [...document.querySelectorAll("img, picture, video, [style*='background-image'], section > div, figure")]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 120 && r.height > 80 && r.bottom > 0 && r.top < vh * 2; })
    .slice(0, 80);
  const before = els.map(e => e.getBoundingClientRect().top);
  scrollTo(0, y0 + step); await new Promise(r => setTimeout(r, 300));
  const out = [];
  els.forEach((e, i) => {
    const r = e.getBoundingClientRect(), drift = (r.top - before[i]) + step;  // 0 = moves with the page
    if (Math.abs(drift) > 24 && getComputedStyle(e).position !== "fixed" && getComputedStyle(e).position !== "sticky")
      out.push({ top: Math.round(r.top + scrollY), h: Math.round(r.height), drift: Math.round(drift), ratio: Math.round(drift / step * 100) / 100 });
  });
  scrollTo(0, 0);
  return out;
}"""

STEP_JS = r"""async (y) => {
  // One step of the slow inspection scroll: watch what starts revealing in this viewport and time it.
  const ident = t => !t || t === "none" || t === "matrix(1, 0, 0, 1, 0, 0)";
  const ty = t => { const m = /matrix\(([^)]+)\)/.exec(t || ""); return m ? parseFloat(m[1].split(",")[5]) : 0; };
  const pre = window.__csPre || new Map();
  const ids = window.__csParents || (window.__csParents = new Map());
  scrollTo(0, y);
  const vh = innerHeight, watch = [];
  await new Promise(r => setTimeout(r, 30));
  for (const [el, s] of pre) {
    if (watch.length >= 8) break;
    if (el.__csTimed || !el.isConnected) continue;
    const r = el.getBoundingClientRect();
    if (r.top < vh * 0.95 && r.bottom > 0) watch.push([el, s, { start: null, end: null }]);
  }
  const t0 = performance.now();
  while (watch.length && performance.now() - t0 < 1800) {
    await new Promise(r => setTimeout(r, 40));
    const t = performance.now() - t0;
    for (const [el, s, m] of watch) {
      const cs = getComputedStyle(el), op = parseFloat(cs.opacity);
      if (m.start === null && (Math.abs(op - s.op) > 0.02 || cs.transform !== s.tf || cs.clipPath !== s.clip)) m.start = t;
      if (m.end === null && op >= 0.99 && ident(cs.transform) && cs.clipPath === "none") m.end = t;
    }
    if (watch.every(([, , m]) => m.end !== null)) break;
  }
  return watch.map(([el, s, m]) => {
    el.__csTimed = true;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect(), p = el.parentElement;
    if (!ids.has(p)) ids.set(p, ids.size);
    const durs = (cs.transitionDuration + "," + cs.animationDuration).split(",").map(d => parseFloat(d) * (d.includes("ms") ? 1 : 1000)).filter(x => x > 0);
    const ease = (cs.transitionDuration !== "0s" ? cs.transitionTimingFunction : cs.animationTimingFunction).split(",")[0].trim();
    return { top: Math.round(r.top + scrollY), h: Math.round(r.height), parent: ids.get(p), fromOp: s.op, fromY: Math.round(ty(s.tf)),
             start: m.start, end: m.end, cssMs: durs.length ? Math.max(...durs) : 0, ease };
  });
}"""

POST_JS = r"""async () => {
  const ident = t => !t || t === "none" || t === "matrix(1, 0, 0, 1, 0, 0)";
  const abs = r => ({ top: Math.round(r.top + scrollY), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height) });
  const out = { revealed: [], marquee: [], libs: [], unsupported: [], sticky: false, blur: false, smooth: false, hover: [] };

  // Scroll reveals: what started hidden below the fold and is visible now (after the settle scroll).
  const parents = new Map();
  for (const [el, s] of (window.__csPre || new Map())) {
    if (!el.isConnected) continue;
    const cs = getComputedStyle(el), op = parseFloat(cs.opacity);
    const shown = (s.op < 0.99 && op >= 0.99) || (!ident(s.tf) && ident(cs.transform))
      || (s.clip !== "none" && cs.clipPath === "none") || (s.vis === "hidden" && cs.visibility !== "hidden");
    if (!shown) continue;
    const p = el.parentElement;
    if (!parents.has(p)) parents.set(p, parents.size);
    out.revealed.push({ ...abs(el.getBoundingClientRect()), parent: parents.get(p) });
  }

  // Marquees: infinite CSS animations sliding sideways, or wide tracks that keep moving.
  for (const a of document.getAnimations()) {
    const t = a.effect && a.effect.target, timing = a.effect && a.effect.getTiming();
    if (!t || !timing || timing.iterations !== Infinity) continue;
    const frames = a.effect.getKeyframes().map(k => k.transform || "").join(" ");
    if (/translate(X|3d)?\(/.test(frames)) out.marquee.push({ ...abs(t.getBoundingClientRect()), cycle: (timing.duration || 0) / 1000 });
  }
  const tracks = [...document.querySelectorAll("body *")].filter(el => {
    const p = el.parentElement; if (!p) return false;
    const r = el.getBoundingClientRect(), pr = p.getBoundingClientRect();
    return r.width > pr.width * 1.5 && pr.width > 200 && getComputedStyle(p).overflow.includes("hidden");
  }).slice(0, 12);
  const t0 = tracks.map(el => el.getBoundingClientRect().left);
  await new Promise(r => setTimeout(r, 450));
  tracks.forEach((el, i) => {
    const moved = Math.abs(el.getBoundingClientRect().left - t0[i]);
    if (moved > 2) out.marquee.push({ ...abs(el.parentElement.getBoundingClientRect()),
                                      cycle: Math.round(el.getBoundingClientRect().width / 2 / (moved / 0.45)) });
  });

  // Page-wide.
  const html = document.documentElement;
  if (window.gsap) out.libs.push("GSAP");
  if (window.ScrollTrigger) out.libs.push("ScrollTrigger");
  if (window.Lenis || html.classList.contains("lenis") || html.hasAttribute("data-lenis")) { out.libs.push("Lenis"); out.smooth = true; }
  if (document.querySelector("[data-framer-name], [data-framer-component-type]")) out.libs.push("Framer");
  if (document.querySelector("[data-aos]")) out.libs.push("AOS");
  if (document.querySelector("[data-scroll-container], [data-scroll]")) out.libs.push("Locomotive Scroll");
  if (window.Swiper || document.querySelector(".swiper")) out.libs.push("Swiper");
  if (getComputedStyle(html).scrollBehavior === "smooth") out.smooth = true;
  const cursor = [...document.querySelectorAll("body *")].find(el => {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    return cs.position === "fixed" && cs.pointerEvents === "none" && r.width > 4 && r.width <= 80 && r.height <= 80 && cs.zIndex !== "auto";
  });
  if (cursor) out.unsupported.push("con trỏ chuột riêng");
  if ([...document.querySelectorAll("canvas")].some(c => { const r = c.getBoundingClientRect(); return r.width > 300 && r.height > 200; }))
    out.unsupported.push("canvas / WebGL");
  const header = document.querySelector("header, [role=banner], nav");
  if (header) {
    let el = header;
    for (let i = 0; i < 3 && el && el !== document.body; i++, el = el.parentElement) {
      const cs = getComputedStyle(el);
      if (cs.position === "sticky" || cs.position === "fixed") {
        out.sticky = true; out.blur = out.blur || cs.backdropFilter !== "none";
        const m = /blur\(([\d.]+)px\)/.exec(cs.backdropFilter || ""); if (m) out.blurPx = Math.round(parseFloat(m[1]));
      }
    }
  }

  // Hover candidates: cards (with an image), wide rows, links and buttons that declare a transition.
  const seen = new Set();
  const pick = (el, kind) => {
    if (seen.has(el) || out.hover.length >= 16) return;
    const r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 20 || !el.checkVisibility()) return;
    seen.add(el);
    el.setAttribute("data-cs-hover", String(out.hover.length));
    out.hover.push({ i: out.hover.length, kind, ...abs(r) });
  };
  const timed = el => { const cs = getComputedStyle(el); return cs.transitionDuration.split(",").some(d => parseFloat(d) > 0); };
  document.querySelectorAll("a, article, li, [class*=card]").forEach(el => {
    if (el.querySelector("img, picture") && el.getBoundingClientRect().width < innerWidth * 0.8) pick(el, "card");
  });
  document.querySelectorAll("a, li").forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 400 && r.height < 140 && !el.querySelector("img")) pick(el, "row");
  });
  document.querySelectorAll("main a, section a, footer a").forEach(el => { if (timed(el) && !el.querySelector("img")) pick(el, "link"); });
  document.querySelectorAll("button, [class*=btn], [class*=button]").forEach(el => { if (timed(el)) pick(el, "button"); });
  return out;
}"""

SNAP_JS = r"""(i) => {
  const el = document.querySelector(`[data-cs-hover="${i}"]`);
  if (!el) return null;
  const cs = getComputedStyle(el), img = el.querySelector("img");
  const visibleImages = [...document.images].filter(m => {
    const r = m.getBoundingClientRect();
    return r.width > 80 && r.height > 60 && parseFloat(getComputedStyle(m).opacity) > 0.5 && m.checkVisibility({ opacityProperty: true });
  }).length;
  const dur = Math.max(...cs.transitionDuration.split(",").map(d => parseFloat(d) * (d.includes("ms") ? 1 : 1000)), 0);
  const ease = cs.transitionTimingFunction.split(",")[0].trim();
  return { tf: cs.transform, shadow: cs.boxShadow, ease, bgSize: cs.backgroundSize, deco: cs.textDecorationLine,
           border: cs.borderBottomWidth + " " + cs.borderBottomStyle, imgTf: img ? getComputedStyle(img).transform : null,
           visibleImages, dur, top: el.getBoundingClientRect().top };
}"""


def _scale_y(transform: str | None) -> tuple[float, float]:
    """(scale, translateY) from a computed matrix(...) string."""
    if not transform or not transform.startswith("matrix("):
        return 1.0, 0.0
    try:
        a, b, c, d, e, f = (float(x) for x in transform[7:-1].split(","))
    except ValueError:
        return 1.0, 0.0
    return (a * a + b * b) ** 0.5, f


def hover_effects(kind: str, before: dict, after: dict) -> list[str]:
    """Which catalogue hover effects one before/after pair shows."""
    found: list[str] = []
    s0, y0 = _scale_y(before["tf"])
    s1, y1 = _scale_y(after["tf"])
    moved_up = (y1 - y0) <= -2 or (after["top"] - before["top"]) <= -2
    if moved_up or s1 > s0 + 0.01 or (after["shadow"] != before["shadow"] and after["shadow"] != "none"):
        found.append("hover-lift")
    if before["imgTf"] is not None and _scale_y(after["imgTf"])[0] > _scale_y(before["imgTf"])[0] + 0.01:
        found.append("hover-zoom")
    if after["visibleImages"] > before["visibleImages"] and kind in ("row", "link", "card"):
        found.append("hover-image")
    if kind in ("link", "row") and (after["bgSize"] != before["bgSize"] or after["deco"] != before["deco"]
                                    or after["border"] != before["border"]):
        found.append("underline-link")
    return found


def hover_params(before: dict, after: dict) -> dict:
    """How the hover moves: duration, easing, lift (px), scale, image zoom."""
    s0, y0 = _scale_y(before["tf"])
    s1, y1 = _scale_y(after["tf"])
    lift = min(y1 - y0, after["top"] - before["top"])
    zoom = _scale_y(after["imgTf"])[0] / max(_scale_y(before["imgTf"])[0], 0.01) if before.get("imgTf") else 1.0
    return {"duration_ms": round(before.get("dur") or 0), "easing": before.get("ease") or "",
            "lift_px": round(-lift) if lift < -1 else 0, "scale": round(s1 / max(s0, 0.01), 3), "zoom": round(zoom, 3)}


async def probe(page: Page, on_hover=None) -> dict:
    """Run after PRE_JS (before the settle scroll) and the settle scroll: reveals, marquees, page-wide
    facts, and the hover sample hovered for real. `on_hover(selector, index, total, kind)` is awaited
    before each hover (the inspector's visible cursor)."""
    post = await page.evaluate(POST_JS)
    hovers = []
    for cand in post["hover"]:
        sel = f'[data-cs-hover="{cand["i"]}"]'
        if on_hover:
            with contextlib.suppress(Exception):
                await on_hover(sel, cand["i"], len(post["hover"]), cand["kind"])
        with contextlib.suppress(Exception):
            # Bring it into view first: the hover's own scroll must not read as a "lift".
            await page.evaluate(f"document.querySelector('{sel}')?.scrollIntoView({{block: 'center'}})")
            await asyncio.sleep(0.15)
            before = await page.evaluate(SNAP_JS, cand["i"])
            if not before:
                continue
            await page.hover(sel, timeout=2000)
            await asyncio.sleep(min(max(before["dur"], 250), 600) / 1000 + 0.05)
            after = await page.evaluate(SNAP_JS, cand["i"])
            await page.mouse.move(2, 2)
            if after:
                hovers.append({**cand, "effects": hover_effects(cand["kind"], before, after),
                               "params": hover_params(before, after)})
    post["hover"] = hovers
    return post


def assign(blocks: list[dict], post: dict, parallax: list[dict]) -> dict:
    """Catalogue effect ids per block (written into block["features"]["motion"]) + page-wide facts."""
    def inside(item: dict, f: dict) -> bool:
        mid = item["top"] + item["h"] / 2
        return f["top"] <= mid <= f["top"] + max(f["height"], 1)

    for b in blocks:
        f = b["features"]
        motion: list[str] = []
        revealed = [r for r in post.get("revealed", []) if inside(r, f)]
        if revealed:
            groups: dict[int, int] = {}
            for r in revealed:
                groups[r["parent"]] = groups.get(r["parent"], 0) + 1
            motion.append("stagger-cards" if max(groups.values()) >= 3 else "scroll-reveal")
        if any(inside(p, f) for p in parallax):
            motion.append("parallax")
        if any(inside(m, f) for m in post.get("marquee", [])):
            motion.append("marquee")
        for h in post.get("hover", []):
            if inside(h, f):
                motion += [e for e in h["effects"] if e not in motion]
        f["motion"] = motion
    return {"libs": post.get("libs", []), "unsupported": post.get("unsupported", []),
            "smooth": post.get("smooth", False), "sticky": post.get("sticky", False)}


def page_wide(sections: list, facts: dict) -> None:
    """Header effects belong to the header section (synthetic or read)."""
    header = next((s for s in sections if s.structure == "sticky-bar"), None)
    if not header:
        return
    for effect, on in (("sticky-blur", facts.get("sticky")), ("smooth-scroll", facts.get("smooth"))):
        if on and effect not in header.motion:
            header.motion.append(effect)
