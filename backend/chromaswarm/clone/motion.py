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

LOAD_JS = r"""() => {
  // Animations the page plays by itself right after it loads (an intro): finite CSS / Web animations,
  // and endless decorative loops (float, pulse, orbit) that are not marquees. Keyframes are summarised.
  const abs = r => ({ top: Math.round(r.top + scrollY), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height) });
  const props = k => Object.entries(k).filter(([p]) => ["transform", "opacity", "clipPath", "filter", "scale", "translate", "rotate"].includes(p))
    .map(([p, v]) => `${p}: ${v}`).join("; ");
  const out = { intro: [], loops: [] };
  for (const a of document.getAnimations()) {
    const t = a.effect && a.effect.target, tm = a.effect && a.effect.getTiming();
    if (!t || !tm || !t.getBoundingClientRect) continue;
    const r = t.getBoundingClientRect();
    if (r.width < 16 || r.height < 16) continue;
    const kf = a.effect.getKeyframes();
    const item = { ...abs(r), name: a.animationName || a.transitionProperty || "", dur: Math.round(tm.duration || 0),
                   delay: Math.round(tm.delay || 0), easing: tm.easing, from: props(kf[0] || {}), to: props(kf[kf.length - 1] || {}) };
    if (tm.iterations === Infinity) {
      if (!/translate/.test(kf.map(k => k.transform || "").join(" "))) out.loops.push(item);  // marquees are read later
    } else if (a.constructor.name !== "CSSTransition" && (tm.duration || 0) >= 150) out.intro.push(item);
  }
  out.intro = out.intro.slice(0, 24); out.loops = out.loops.slice(0, 24);
  return out;
}"""

PARALLAX_JS = r"""async () => {
  // Elements whose position changes at a different rate than the scroll.
  const vh = innerHeight, y0 = Math.round(vh * 0.8), step = 400;
  // Elements inside an endless animation (a marquee track) move by themselves: never parallax / hover lift.
  const loops = document.getAnimations().filter(a => a.effect && a.effect.target && a.effect.getTiming().iterations === Infinity)
    .map(a => a.effect.target);
  const inLoop = e => loops.some(t => t === e || t.contains(e));
  // Instant jumps, and the scroll that really happened: smooth-scrolling pages lag behind scrollTo().
  scrollTo({ top: y0, behavior: "instant" }); await new Promise(r => setTimeout(r, 250));
  const startY = scrollY;
  const els = [...document.querySelectorAll("img, picture, video, [style*='background-image'], section > div, figure")]
    .filter(e => { const r = e.getBoundingClientRect(); return r.width > 120 && r.height > 80 && r.bottom > 0 && r.top < vh * 2 && !inLoop(e); })
    .slice(0, 80);
  const before = els.map(e => e.getBoundingClientRect().top);
  scrollTo({ top: y0 + step, behavior: "instant" }); await new Promise(r => setTimeout(r, 300));
  const moved = scrollY - startY;
  const out = [];
  if (moved < step / 2) { scrollTo({ top: 0, behavior: "instant" }); return out; }  // the page would not scroll
  els.forEach((e, i) => {
    const r = e.getBoundingClientRect(), drift = (r.top - before[i]) + moved;  // 0 = moves with the page
    if (Math.abs(drift) > 24 && getComputedStyle(e).position !== "fixed" && getComputedStyle(e).position !== "sticky")
      out.push({ top: Math.round(r.top + scrollY), h: Math.round(r.height), drift: Math.round(drift), ratio: Math.round(drift / moved * 100) / 100 });
  });
  scrollTo({ top: 0, behavior: "instant" });
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
    // The first timing function of the list (cubic-bezier(...) has commas of its own).
    const firstFn = v => ((v || "").match(/^\s*([a-z-]+\([^)]*\)|[a-z-]+)/) || [, ""])[1];
    const ease = firstFn(cs.transitionDuration !== "0s" ? cs.transitionTimingFunction : cs.animationTimingFunction);
    return { top: Math.round(r.top + scrollY), h: Math.round(r.height), parent: ids.get(p), fromOp: s.op, fromY: Math.round(ty(s.tf)),
             start: m.start, end: m.end, cssMs: durs.length ? Math.max(...durs) : 0, ease };
  });
}"""

POST_JS = r"""async () => {
  const ident = t => !t || t === "none" || t === "matrix(1, 0, 0, 1, 0, 0)";
  const abs = r => ({ top: Math.round(r.top + scrollY), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height) });
  const out = { revealed: [], marquee: [], libs: [], unsupported: [], sticky: false, blur: false, smooth: false, hover: [] };
  // Elements inside an endless animation (a marquee track) move by themselves: never parallax / hover lift.
  const loops = document.getAnimations().filter(a => a.effect && a.effect.target && a.effect.getTiming().iterations === Infinity)
    .map(a => a.effect.target);
  const inLoop = e => loops.some(t => t === e || t.contains(e));

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

  // Marquees: infinite CSS animations sliding sideways (or up / down: columns of cards that scroll by
  // themselves), or wide tracks that keep moving.
  for (const a of document.getAnimations()) {
    const t = a.effect && a.effect.target, timing = a.effect && a.effect.getTiming();
    if (!t || !timing || timing.iterations !== Infinity) continue;
    const frames = a.effect.getKeyframes().map(k => k.transform || "").join(" ");
    const vertical = /translateY\(|translate3d\([^,]+,\s*-?[1-9]/.test(frames) && !/translateX\(/.test(frames);
    if (/translate(X|Y|3d)?\(/.test(frames)) {
      const r=t.getBoundingClientRect();
      let top=r.top,bottom=r.bottom,left=r.left,right=r.right;
      for(let p=t.parentElement;p&&p!==document.body;p=p.parentElement){
        const style=getComputedStyle(p),q=p.getBoundingClientRect();
        if(style.overflowY!=='visible'){top=Math.max(top,q.top);bottom=Math.min(bottom,q.bottom);}
        if(style.overflowX!=='visible'){left=Math.max(left,q.left);right=Math.min(right,q.right);}
      }
      let reverse=/-50%\)?\s*$/.test(String(a.effect.getKeyframes()[0].transform || ""));
      if(timing.direction==='reverse')reverse=!reverse;
      out.marquee.push({ ...abs(r), clip:{top:Math.round(top+scrollY),left:Math.round(left),w:Math.max(0,right-left),h:Math.max(0,bottom-top)},
                        cycle:(timing.duration||0)/1000,axis:vertical?'y':'x',reverse });
    }
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
    if (seen.has(el) || out.hover.length >= 16 || inLoop(el)) return;
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
  const ease = ((cs.transitionTimingFunction || "").match(/^\s*([a-z-]+\([^)]*\)|[a-z-]+)/) || [, ""])[1];
  return { tf: cs.transform, shadow: cs.boxShadow, ease, bgSize: cs.backgroundSize, deco: cs.textDecorationLine,
           border: cs.borderBottomWidth + " " + cs.borderBottomStyle, imgTf: img ? getComputedStyle(img).transform : null,
           visibleImages, dur, top: el.getBoundingClientRect().top };
}"""


CONTROLS_JS = r"""(limit) => {
  // Every visible button and link (in page order), tagged so each one can be hovered for real.
  const out = [];
  for (const el of document.querySelectorAll("a[href], button, [role=button]")) {
    if (out.length >= limit) break;
    const r = el.getBoundingClientRect();
    if (r.width < 12 || r.height < 12 || !el.checkVisibility({ opacityProperty: true })) continue;
    const cs = getComputedStyle(el), bg = cs.backgroundColor;
    const filled = !/rgba\(0, 0, 0, 0\)|transparent/.test(bg);
    el.setAttribute("data-cs-ctl", String(out.length));
    const href = el.tagName === "A" ? el.href : null;
    let pinned = false;  // inside a fixed bar: its place on the page is its place in the window
    for (let e = el; e && e !== document.body; e = e.parentElement) if (getComputedStyle(e).position === "fixed") { pinned = true; break; }
    out.push({ i: out.length, kind: el.tagName === "BUTTON" || filled || parseFloat(cs.borderTopWidth) > 0 ? "button" : "link",
               top: Math.round(r.top + (pinned ? 0 : scrollY)), pinned, left: Math.round(r.left), h: Math.round(r.height), w: Math.round(r.width),
               href: href && /^https?:/.test(href) ? href : null, hash: href ? href.startsWith(location.href.split("#")[0] + "#") : false,
               newTab: el.getAttribute("target") === "_blank", submit: !!el.form && (el.type === "submit" || el.tagName === "BUTTON" && !el.type),
               expands: el.hasAttribute("aria-expanded") || el.tagName === "SUMMARY" });
  }
  return out;
}"""

CTL_SNAP_JS = r"""(i) => {
  const el = document.querySelector(`[data-cs-ctl="${i}"]`);
  if (!el) return null;
  const cs = getComputedStyle(el);
  const dur = Math.max(...cs.transitionDuration.split(",").map(d => parseFloat(d) * (d.includes("ms") ? 1 : 1000)), 0);
  return { bg: cs.backgroundColor, color: cs.color, border: cs.borderTopColor, shadow: cs.boxShadow, tf: cs.transform,
           opacity: cs.opacity, deco: cs.textDecorationLine, filter: cs.filter, dur, top: el.getBoundingClientRect().top };
}"""

HOVER_WORDS = {"bg": "đổi màu nền", "color": "đổi màu chữ", "border": "đổi màu viền", "shadow": "đổ bóng",
               "opacity": "đổi độ mờ", "deco": "gạch chân", "filter": "sáng/tối hơn"}


async def sweep_controls(page: Page, limit: int = 40, on_hover=None) -> list[dict]:
    """Hover every button and link once and say what changes (nothing is clicked: links would leave the page)."""
    out = []
    for c in await page.evaluate(CONTROLS_JS, limit):
        sel = f'[data-cs-ctl="{c["i"]}"]'
        with contextlib.suppress(Exception):
            await page.evaluate(f"document.querySelector('{sel}')?.scrollIntoView({{block: 'center', behavior: 'instant'}})")
            await asyncio.sleep(0.08)
            before = await page.evaluate(CTL_SNAP_JS, c["i"])
            if not before:
                continue
            if on_hover:
                await on_hover(sel, c["i"], limit, c["kind"])
            await page.hover(sel, timeout=1500)
            await asyncio.sleep(min(max(before["dur"], 150), 500) / 1000 + 0.05)
            after = await page.evaluate(CTL_SNAP_JS, c["i"])
            await page.mouse.move(2, 2)
            changes = [w for k, w in HOVER_WORDS.items() if after and after[k] != before[k]]
            s0, y0 = _scale_y(before["tf"])
            s1, y1 = _scale_y(after["tf"]) if after else (s0, y0)
            if after and (y1 - y0 <= -1 or -_MAX_LIFT <= after["top"] - before["top"] <= -1):
                changes.append("nhích lên")
            if after and s1 > s0 + 0.01:
                changes.append("phóng to")
            out.append({**c, "changes": changes, "duration_ms": round(before["dur"])})
    return out


_MAX_LIFT = 40  # px: a hover never lifts further; a bigger move is the page or a track moving under the pointer


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
    moved_up = (y1 - y0) <= -2 or -_MAX_LIFT <= (after["top"] - before["top"]) <= -2
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
    box = after["top"] - before["top"]  # the box's own move; a scroll or a moving track is not a lift
    lift = min(y1 - y0, box if -_MAX_LIFT <= box <= 0 else 0)
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


# ------------------------------------------------------------------ what each control does when clicked

AUTH_PATH = ("auth", "login", "log-in", "signin", "sign-in", "signup", "sign-up", "register", "account", "dang-nhap", "dang-ky")
# The clicked row and its card: an FAQ that opens by height alone (no aria-expanded, answer already in the DOM).
ROW_JS = r"""(sel) => { const el = document.querySelector(sel); if (!el) return 0;
  const card = el.parentElement || el; return Math.round(card.getBoundingClientRect().height); }"""
CLICK_SNAP_JS = r"""() => ({ len: (document.body.innerText || "").length, y: Math.round(scrollY),
  dialog: !!document.querySelector("[role=dialog]:not([hidden]), dialog[open], [aria-modal=true]"),
  expanded: [...document.querySelectorAll("[aria-expanded=true]")].length, url: location.href })"""


def classify_destination(url: str, page_url: str) -> dict:
    """Where a link goes, without its words: same page / internal path (sign-in, blog, legal…) / external host."""
    from urllib.parse import urlparse
    u, here = urlparse(url), urlparse(page_url)
    if u.netloc and u.netloc.removeprefix("www.") != here.netloc.removeprefix("www."):
        return {"kind": "external", "target": u.netloc.removeprefix("www.")}
    path = u.path or "/"
    if path.rstrip("/") == here.path.rstrip("/") and (u.fragment or path == here.path):
        return {"kind": "same-page", "target": "#" + u.fragment if u.fragment else "/"}
    low = path.lower()
    role = ("đăng nhập / đăng ký" if any(w in low for w in AUTH_PATH) else "bảng giá" if "pric" in low or "billing" in low
            else "blog / bài viết" if "blog" in low or "post" in low or "article" in low
            else "pháp lý" if any(w in low for w in ("terms", "privacy", "legal", "policy", "cookie"))
            else "tài liệu" if "doc" in low else "")
    return {"kind": "internal", "target": path, "role": role}


async def click_controls(browser, url: str, controls: list[dict], limit_clicks: int = 12,
                         width: int = 1440, height: int = 900) -> list[dict]:
    """What every control does, in a fresh tab each time it has to be clicked (nothing is typed or submitted):

    * a link is not clicked: its destination is classified (same page, internal path and its role, external
      host, new tab) and internal pages are fetched once to catch broken links (404);
    * a form's submit button is never pressed;
    * a button without a link is clicked for real (up to `limit_clicks`): did the page navigate, open a
      new tab, a dialog, expand something, change its content or scroll?"""
    from chromaswarm.playwright_engine.style_dna_scraper import goto_ready
    context = await browser.new_context(viewport={"width": width, "height": height})  # its own tabs, cookies
    try:
        return await _click_all(context, goto_ready, url, controls, limit_clicks)
    finally:
        await context.close()


async def _click_all(context, goto_ready, url: str, controls: list[dict], limit_clicks: int) -> list[dict]:
    checked: dict[str, int] = {}
    done: list[dict] = []
    clicked = 0
    for c in controls:
        if c.get("submit"):
            c["action"] = {"kind": "form-submit", "note": "nút gửi form: không bấm"}
            continue
        if c.get("href") and not c.get("hash"):
            dest = classify_destination(c["href"], url)
            if c.get("newTab"):
                dest["new_tab"] = True
            if dest["kind"] == "internal" and len(checked) < 24:
                if dest["target"] not in checked:
                    with contextlib.suppress(Exception):
                        r = await context.request.get(c["href"], timeout=8000, max_redirects=5)
                        checked[dest["target"]] = r.status
                        if r.url != c["href"]:
                            dest["redirect"] = classify_destination(r.url, url).get("target")
                if checked.get(dest["target"], 0) >= 400:
                    dest["broken"] = checked[dest["target"]]
            c["action"] = dest
            continue
        # A row identical to one just clicked (FAQ / feature rows): same size, close below — same behaviour.
        twin = next((d for d in reversed(done) if abs(d["w"] - c["w"]) <= 4 and abs(d["h"] - c["h"]) <= 40
                     and 0 < c["top"] - d["top"] <= 600 and d.get("action", {}).get("kind") in ("toggle", "content", "scroll", "dialog", "none")), None)
        if twin:
            c["action"] = {**twin["action"], "note": (twin["action"].get("note") or "") + " (như hàng trên)"}
            done.append(c)
            continue
        if clicked >= limit_clicks:
            c["action"] = {"kind": "not-clicked", "note": "quá số lần bấm thử"}
            continue
        clicked += 1
        page = await context.new_page()
        try:
            await goto_ready(page, url, timeout_ms=30000, load_ms=8000)
            await page.wait_for_timeout(600)
            # Found again by size and place, not by order: a fresh tab may show a banner the first one had not.
            fresh = await page.evaluate(CONTROLS_JS, 80)
            same = [f for f in fresh if abs(f["w"] - c["w"]) <= 4 and abs(f["h"] - c["h"]) <= 4]
            if not same:
                c["action"] = {"kind": "unknown", "note": "không tìm lại được nút"}
                continue
            twin = min(same, key=lambda f: abs(f["top"] - c["top"]) + abs(f.get("left", 0) - c.get("left", 0)))
            sel = f'[data-cs-ctl="{twin["i"]}"]'
            # In view first: the scroll Playwright makes to reach it is not something the button did.
            await page.locator(sel).scroll_into_view_if_needed(timeout=3000)
            await page.wait_for_timeout(300)
            before = await page.evaluate(CLICK_SNAP_JS)
            box0 = await page.evaluate(ROW_JS, sel)
            popup = None
            try:
                async with context.expect_page(timeout=2500) as info:
                    await page.click(sel, timeout=3000)
                popup = await info.value
            except Exception:
                pass
            await page.wait_for_timeout(1200)
            after = await page.evaluate(CLICK_SNAP_JS)
            box1 = await page.evaluate(ROW_JS, sel)
            if popup:
                with contextlib.suppress(Exception):
                    await popup.wait_for_load_state("domcontentloaded", timeout=8000)
                c["action"] = {**classify_destination(popup.url, url), "new_tab": True}
                await popup.close()
            elif after["url"].split("#")[0] != before["url"].split("#")[0]:
                c["action"] = classify_destination(after["url"], url)
            elif after["dialog"] and not before["dialog"]:
                c["action"] = {"kind": "dialog", "note": "mở hộp thoại / menu"}
            elif after["expanded"] != before["expanded"] or (box0 and box1 and abs(box1 - box0) > 8):
                c["action"] = {"kind": "toggle", "note": "mở / đóng một khối"}
            elif abs(after["len"] - before["len"]) > 2:
                c["action"] = {"kind": "content", "note": "đổi nội dung trên trang"}
            elif abs(after["y"] - before["y"]) > 40:
                c["action"] = {"kind": "scroll", "note": "cuộn tới một phần của trang"}
            else:
                c["action"] = {"kind": "none", "note": "không thấy thay đổi nào đo được"}
        except Exception as e:  # one control never stops the check
            c["action"] = {"kind": "unknown", "note": str(e)[:80]}
        finally:
            await page.close()
        done.append(c)
    await _soft_404(context, goto_ready, controls)
    return controls


SOFT_404 = r"""() => /\b404\b|not found|không tìm thấy|page not found/i.test(document.title + " " + (document.querySelector("h1")?.innerText || ""))"""


async def _soft_404(context, goto_ready, controls: list[dict], limit: int = 8) -> None:
    """Single-page apps answer 200 for a missing page and render "404" themselves: render each internal
    destination once and look at its title / h1 (only to flag it as broken; nothing is kept)."""
    paths = list(dict.fromkeys(c["action"]["target"] for c in controls
                               if c.get("action", {}).get("kind") == "internal" and not c["action"].get("broken")
                               and not c["action"].get("redirect") and c.get("href")))[:limit]
    hrefs = {c["action"]["target"]: c["href"] for c in controls if c.get("action", {}).get("target") in paths}
    for path in paths:
        page = await context.new_page()
        try:
            await goto_ready(page, hrefs[path], timeout_ms=20000, load_ms=6000)
            await page.wait_for_timeout(500)
            if await page.evaluate(SOFT_404):
                for c in controls:
                    if c.get("action", {}).get("target") == path:
                        c["action"]["broken"] = "404 (trang báo không tìm thấy)"
        except Exception:
            pass
        finally:
            await page.close()
