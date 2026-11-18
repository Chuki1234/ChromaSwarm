"""Clone mode: the smallest pieces of a page — headings, text, links, buttons, images, inputs, cards.

The same JS reads both pages:

* the reference, per reader block (absolute page boxes), while it is analysed (B2), and again live
  during the 1:1 acceptance (B11);
* the rebuild, per `[data-swarm-section]` (each component gets `data-cs-comp="<section>:<i>"`, so the
  factory cursors can fly to it).

Only geometry and computed style are returned — never text, never image URLs — so a structure clone
of someone else's site carries nothing of its content.

`match()` pairs reference and rebuilt components of one section (same kind, nearest position);
`section_score()` turns the pairs into a 0–100 1:1 score; `tune_rules()` writes the CSS that brings the
rebuilt components' measurable style to the reference's (font size / weight / tracking / leading /
case, corner radius, button padding, card shadow and border) — desktop only, so phone layouts keep the
design system's own scale and QA's mobile checks.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict

from pydantic import BaseModel


COMPONENTS_JS = r"""(args) => {
  const { boxes, built, limit } = args;            // boxes: [{key, top, left, width, height}] (page px)
  const pixel = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  const rgba = c => { pixel.clearRect(0,0,1,1); pixel.fillStyle = "#000"; pixel.fillStyle = c; pixel.fillRect(0,0,1,1);
                      const d = pixel.getImageData(0,0,1,1).data; return [d[0], d[1], d[2], d[3] / 255]; };
  const hex = c => "#" + c.slice(0, 3).map(v => v.toString(16).padStart(2, "0")).join("");
  const px = v => parseFloat(v) || 0;
  const sy = scrollY;
  const out = {};
  for (const b of boxes) out[b.key] = [];
  const rootOf = (el) => {
    if (built) { const s = el.closest("[data-swarm-section]"); return s ? s.getAttribute("data-swarm-section") : null; }
    // The block whose band holds the element's centre line: the one around it when there is one (the
    // smallest), else the nearest one sideways (a block can be narrower than its section's content).
    const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + sy + r.height / 2;
    let best = null, bestScore = Infinity;
    for (const b of boxes) {
      if (cy < b.top || cy > b.top + b.height) continue;
      const dx = cx < b.left ? b.left - cx : cx > b.left + b.width ? cx - b.left - b.width : 0;
      const score = dx * 1e7 + b.width * b.height;
      if (score < bestScore) { best = b.key; bestScore = score; }
    }
    return best;
  };
  const boxOf = {};
  if (built) for (const s of document.querySelectorAll("[data-swarm-section]")) {
    const r = s.getBoundingClientRect();
    boxOf[s.getAttribute("data-swarm-section")] = { top: r.top + sy, left: r.left, width: r.width, height: r.height };
  } else for (const b of boxes) boxOf[b.key] = b;
  const ownText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
  const opaque = c => c[3] > 0.05;
  const kindOf = (el, cs, r) => {
    const t = el.tagName;
    if (/^H[1-6]$/.test(t)) return ["heading", +t[1]];
    if (t === "IMG" || t === "VIDEO" || t === "CANVAS" || t === "PICTURE") return r.width >= 24 && r.height >= 24 ? ["image", 0] : null;
    if (t === "svg" || t === "SVG") return r.width >= 64 && r.height >= 64 ? ["image", 0] : null;
    if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT") return cs.type === "hidden" ? null : ["input", 0];
    const bg = rgba(cs.backgroundColor), bw = px(cs.borderTopWidth) + px(cs.borderBottomWidth);
    // A control drawn as plain text (no fill, no border) reads as a link, whatever its tag.
    if ((t === "BUTTON" || t === "A" || el.getAttribute("role") === "button") && (opaque(bg) || bw > 0) && (t === "BUTTON" || px(cs.paddingLeft) >= 6))
      return ["button", 0];
    if (t === "BUTTON" && (el.textContent || "").trim()) return ["link", 0];
    if (cs.backgroundImage.includes("url(") && r.width >= 120 && r.height >= 80 && !ownText(el)) return ["image", 0];
    const box = boxOf[rootOf(el)];
    const framed = opaque(bg) || bw > 0 || cs.boxShadow !== "none";
    if (framed && box && r.width >= 160 && r.height >= 120 && r.width < box.width * 0.9
        && el.querySelector("img, picture, video, svg, h2, h3, h4, h5, h6")) return ["card", 0];
    if (ownText(el)) {
      if (px(cs.fontSize) >= 28) return ["heading", 0];
      return [t === "A" ? "link" : "text", 0];
    }
    return null;
  };
  const scope = built ? document.querySelectorAll("[data-swarm-section] *") : document.body.querySelectorAll("*");
  const taken = new Set();
  const glCanvas = built ? [] : [...document.querySelectorAll("canvas")].map(c => c.getBoundingClientRect()).filter(c => c.width > 80 && c.height > 40);
  const add = (el, cs, r, k, owner) => {
    const key = rootOf(owner || el);
    if (key === null || !(key in out) && !built) return false;
    if (built && !(key in out)) out[key] = [];
    if (out[key].length >= (limit || 60)) return false;
    if (k[0] !== "card" && k[0] !== "image") taken.add(el);
    const box = boxOf[key];
    const fg = rgba(cs.color), bg = rgba(cs.backgroundColor);
    // Text pieces: how many characters they hold (a number, never the words) and the size of their biggest
    // glyphs (a link or button may carry its label in a larger inner span).
    let chars = 0, fsMax = px(cs.fontSize), tw = 0, tx = 0;
    if (["heading", "text", "link", "button"].includes(k[0])) {
      chars = (el.textContent || "").replace(/\s+/g, " ").trim().length;
      // How wide the words really run (a block heading is often far wider than its lines).
      const range = document.createRange();
      range.selectNodeContents(el);
      const rs = [...range.getClientRects()].filter(q => q.width > 1);
      if (rs.length) {
        tw = Math.round(Math.max(...rs.map(q => q.right)) - Math.min(...rs.map(q => q.left)));
        tx = Math.round(Math.min(...rs.map(q => q.left)) - r.left);  // where the words start inside the box
      }
      for (const d of el.querySelectorAll("*")) {
        if ([...d.childNodes].some(x => x.nodeType === 3 && x.textContent.trim())) fsMax = Math.max(fsMax, px(getComputedStyle(d).fontSize));
      }
    }
    const comp = {
      kind: k[0], level: k[1],
      x: Math.round(r.left - box.left), y: Math.round(r.top + sy - box.top), w: Math.round(r.width), h: Math.round(r.height),
      fs: Math.round(fsMax * 10) / 10, fw: px(cs.fontWeight) || 400, chars, tw, tx,
      lh: cs.lineHeight === "normal" ? 0 : Math.round(px(cs.lineHeight) / Math.max(px(cs.fontSize), 1) * 100) / 100,
      ls: Math.round(px(cs.letterSpacing) * 10) / 10, tt: cs.textTransform === "uppercase" ? "uppercase" : "",
      color: hex(fg), bg: opaque(bg) ? hex(bg) : null, radius: Math.round(px(cs.borderTopLeftRadius)),
      pad: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(v => Math.round(px(v))),
      border: Math.round(px(cs.borderTopWidth)), shadow: cs.boxShadow !== "none",
    };
    if (built) {
      const i = out[key].length;
      el.setAttribute("data-cs-comp", `${key}:${i}`);
      const cls = [...el.classList].filter(c => /^[a-z][a-z0-9-]*$/.test(c) && !c.startsWith("cs-")).slice(0, 2);
      const id = el.getAttribute("data-swarm-id");
      comp.sel = id ? `[data-swarm-id="${id}"]` : el.tagName.toLowerCase() + cls.map(c => "." + c).join("");
      comp.i = i;
    } else {
      el.setAttribute("data-cs-ref", `${key}:${out[key].length}`);
      comp.i = out[key].length;
    }
    out[key].push(comp);
    return true;
  };
  // Reference only: a heading / link / button whose words sit in separate pieces (two halves of a headline
  // either side of a picture; a huge email with a small caption) is measured piece by piece.
  const split = (el, cs, r, k) => {
    if (!["heading", "link", "button"].includes(k[0])) return false;
    const parts = [...el.querySelectorAll("*")].filter(d => [...d.childNodes].some(x => x.nodeType === 3 && x.textContent.trim()))
      .map(d => ({ d, r: d.getBoundingClientRect(), cs: getComputedStyle(d) })).filter(p => p.r.width >= 8 && p.r.height >= 8);
    if (parts.length < 2 || parts.length > 6) return false;
    const area = parts.reduce((a, p) => a + p.r.width * p.r.height, 0);
    const sizes = parts.map(p => px(p.cs.fontSize)), big = Math.max(...sizes);
    // Side by side with a real gap (two halves of a headline); lines stacked under each other are one piece.
    const apart = area < 0.5 * r.width * r.height && parts.some(a => parts.some(b => a !== b
      && Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top) > 0 && b.r.left - a.r.right > 40));
    const mixed = big >= 2 * Math.min(...sizes);
    if (!apart && !mixed) return false;
    taken.add(el);
    for (const p of parts) {
      const kind = px(p.cs.fontSize) >= 0.8 * big ? k : ["text", 0];
      add(p.d, p.cs, p.r, kind, el);
      taken.add(p.d);
    }
    return true;
  };
  let n = 0;
  for (const el of scope) {
    if (++n > 12000) break;
    // The rebuild's decorative copies (aria-hidden) are not components; on the reference, aria-hidden only
    // hides from screen readers — a huge decorative wordmark is still part of what people see.
    if (el.closest(built ? "chromaswarm-overlay, chromaswarm-handover, [aria-hidden=true]" : "chromaswarm-overlay, chromaswarm-handover")) continue;
    const cs = getComputedStyle(el);
    if (cs.display === "none") continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    // Big words hidden in the DOM and painted by a canvas over the same spot (WebGL type) are what people see.
    const gl = !built && px(cs.fontSize) >= 28 && ownText(el) && glCanvas.some(c => {
      const ix = Math.max(0, Math.min(r.right, c.right) - Math.max(r.left, c.left));
      const iy = Math.max(0, Math.min(r.bottom, c.bottom) - Math.max(r.top, c.top));
      return ix * iy >= 0.5 * r.width * r.height;
    });
    if (cs.visibility === "hidden" && !gl) continue;
    if (!built && !gl) {
      // The reference has been scrolled through, so what is still transparent is shown only on hover
      // (preview images, menus): not part of the resting layout. (The rebuild's scroll reveals may still be
      // transparent below the fold, so this is only done on the reference.)
      let o = 1;
      for (let e = el; e && e !== document.body && o >= 0.05; e = e.parentElement) {
        const ecs = getComputedStyle(e);
        if (ecs.display !== "contents") o *= parseFloat(ecs.opacity);  // a box-less wrapper's opacity paints nothing
      }
      if (o < 0.05) continue;
      // Slides parked outside a clipping frame (carousels, tab panels): not on screen, not in the layout.
      let shown = 1;
      for (let e = el.parentElement; e && e !== document.body && shown > 0.3; e = e.parentElement) {
        const ecs = getComputedStyle(e);
        if (ecs.overflowX === "visible" && ecs.overflowY === "visible") continue;
        const fr = e.getBoundingClientRect();
        const ix = Math.max(0, Math.min(r.right, fr.right) - Math.max(r.left, fr.left));
        const iy = Math.max(0, Math.min(r.bottom, fr.bottom) - Math.max(r.top, fr.top));
        shown = Math.min(shown, (ix * iy) / (r.width * r.height));
      }
      if (shown <= 0.3) continue;
    }
    const k = kindOf(el, cs, r);
    if (!k) continue;
    // Decorative media (wave canvases, background art) stays out; a decorative wordmark is kept above.
    if (!built && (k[0] === "image" || k[0] === "card") && el.closest("[aria-hidden=true]")) continue;
    // Text inside a heading / button / link already taken is part of it, not a component of its own.
    if (["text", "link", "heading"].includes(k[0])) {
      let p = el.parentElement, inside = false;
      while (p) { if (taken.has(p)) { inside = true; break; } p = p.parentElement; }
      if (inside) continue;
    }
    if (!built && split(el, cs, r, k)) continue;
    add(el, cs, r, k);
  }
  if (!built) {
    // A section's box covers all of its pieces (widened sideways where they lie outside its block).
    for (const [key, list] of Object.entries(out)) {
      const b = boxOf[key];
      if (!b || !list.length) continue;
      const left = Math.min(b.left, ...list.map(c => b.left + c.x));
      const right = Math.max(b.left + b.width, ...list.map(c => b.left + c.x + c.w));
      if (left < b.left || right > b.left + b.width) {
        for (const c of list) c.x += Math.round(b.left - left);
        boxOf[key] = { ...b, left: Math.round(left), width: Math.round(right - left) };
      }
    }
  }
  return { comps: out, boxes: boxOf };
}"""

async def measure_reference(page, boxes: list[dict], limit: int = 60) -> dict:
    """Reference components, one block at a time with that block scrolled into view: pages that hide their
    text again once it leaves the screen (scroll-linked reveals) only show it while it is on screen."""
    import asyncio
    comps_out: dict[str, list[dict]] = {}
    boxes_out: dict[str, dict] = {}
    for b in boxes:
        await page.evaluate("(y) => scrollTo(0, y)", max(0, int(b["top"]) - 80))
        await asyncio.sleep(0.45)
        # Elements are assigned among all boxes (so a neighbour's pieces never leak in), kept for this one.
        found = await page.evaluate(COMPONENTS_JS, {"boxes": boxes, "built": False, "limit": limit})
        comps_out[b["key"]] = found["comps"].get(b["key"], [])
        boxes_out[b["key"]] = found["boxes"].get(b["key"], b)
    await page.evaluate("() => scrollTo(0, 0)")
    return {"comps": comps_out, "boxes": boxes_out}


KINDS = ("heading", "text", "link", "button", "image", "input", "card")
KIND_LABEL = {"heading": "Tiêu đề", "text": "Chữ", "link": "Link", "button": "Nút", "image": "Ảnh",
              "input": "Ô nhập", "card": "Thẻ"}
# Crews of the factory: one per kind group, each with its own colour.
CREWS = {"type": ("Tổ chữ", "#8B5CF6", ("heading", "text", "link")),
         "action": ("Tổ nút & ô nhập", "#3B82F6", ("button", "input")),
         "media": ("Tổ ảnh & thẻ", "#10B981", ("image", "card"))}
WEIGHTS = {"heading": 3.0, "button": 2.0, "card": 2.0, "image": 2.0, "input": 1.5, "text": 1.0, "link": 0.5}
DESKTOP = "@media (min-width: 1200px)"
# Kinds that do the same job and are often drawn either way (a nav link with a pill background reads as a
# button; a framed image as a card): they may pair, for half credit, after same-kind pairs are taken.
NEAR = {frozenset(("link", "button")), frozenset(("link", "text")), frozenset(("image", "card"))}


class Comp(BaseModel):
    kind: str
    level: int = 0
    x: int
    y: int
    w: int
    h: int
    fs: float = 16
    fw: float = 400
    lh: float = 0
    ls: float = 0
    tt: str = ""
    color: str = "#000000"
    bg: str | None = None
    radius: int = 0
    pad: list[int] = [0, 0, 0, 0]
    border: int = 0
    shadow: bool = False
    chars: int = 0  # text pieces: how many characters (never the text itself)
    tw: int = 0  # text pieces: how wide the words actually run (px), often narrower than the box
    tx: int = 0  # text pieces: where the words start inside the box (px from its left edge)
    sel: str | None = None  # rebuilt page only: a stable selector inside its section
    i: int | None = None  # index within its section (data-cs-comp / data-cs-ref attribute)


class Pair(BaseModel):
    ref: Comp
    built: Comp
    diffs: list[str] = []  # human-readable differences ("cỡ chữ 64→48px")


class SectionCompare(BaseModel):
    id: str
    name: str = ""
    score: float  # 0-100
    parts: dict[str, float]  # components, layout, style, height (each 0-1)
    matched: int
    missing: dict[str, int]  # kind -> how many reference components have no counterpart
    extra: dict[str, int]
    diffs: list[str] = []
    ref_height: int = 0
    built_height: int = 0
    effects_missing: list[str] = []
    ref_image: str | None = None  # artifact file names (compare/<id>-ref.jpg)
    built_image: str | None = None


def comps(raw: list[dict]) -> list[Comp]:
    return [Comp(**c) for c in raw if c.get("kind") in KINDS]


def merge_blocks(per_block: dict[str, list[dict]], blocks: list[dict], sources: list[int],
                 widened: dict[str, dict] | None = None) -> tuple[list[dict], dict | None]:
    """Components of a section made of several reader blocks, positioned relative to the section box.
    `widened`: block boxes as COMPONENTS_JS returned them (grown sideways to cover their pieces)."""
    picked = [{**blocks[i]["features"], **{k: v for k, v in ((widened or {}).get(str(blocks[i]["features"].get("index"))) or {}).items()
                                         if k in ("left", "width")}}
              for i in sources if 0 <= i < len(blocks)]
    if not picked:
        return [], None
    top = min(f.get("top", 0) for f in picked)
    left = min(f.get("left", 0) for f in picked)
    bottom = max(f.get("top", 0) + f.get("height", 0) for f in picked)
    right = max(f.get("left", 0) + f.get("width", 1440) for f in picked)
    out: list[dict] = []
    for f in picked:
        for c in per_block.get(str(f.get("index")), []):
            out.append({**c, "x": c["x"] + f.get("left", 0) - left, "y": c["y"] + f.get("top", 0) - top})
    return out, {"top": top, "left": left, "width": right - left, "height": bottom - top}


# ------------------------------------------------------------------ matching

def _cost(a: Comp, b: Comp, ha: float, hb: float, wa: float, wb: float) -> float:
    return abs(a.y / ha - b.y / hb) + abs((a.x + a.w / 2) / wa - (b.x + b.w / 2) / wb) * 0.7 \
        + abs(a.w / wa - b.w / wb) * 0.3


def match(ref: list[Comp], built: list[Comp], ref_box: dict, built_box: dict) -> tuple[list[Pair], list[Comp], list[Comp]]:
    """Same-kind pairs by nearest relative position (greedy on the cost matrix). Headings pair across
    levels; everything else only with its own kind."""
    ha, hb = max(ref_box.get("height", 1), 1), max(built_box.get("height", 1), 1)
    wa, wb = max(ref_box.get("width", 1), 1), max(built_box.get("width", 1), 1)
    cands = []
    for i, a in enumerate(ref):
        for j, b in enumerate(built):
            if a.kind != b.kind and frozenset((a.kind, b.kind)) not in NEAR:
                continue
            c = _cost(a, b, ha, hb, wa, wb) + (0 if a.kind == b.kind else 0.6)  # same kind always first
            if c < (0.6 if a.kind == b.kind else 1.0):
                cands.append((c, i, j))
    cands.sort()
    used_a, used_b, pairs = set(), set(), []
    for _, i, j in cands:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append(Pair(ref=ref[i], built=built[j], diffs=differences(ref[i], built[j])))
    pairs.sort(key=lambda p: (p.ref.y, p.ref.x))
    return pairs, [a for i, a in enumerate(ref) if i not in used_a], [b for j, b in enumerate(built) if j not in used_b]


def differences(a: Comp, b: Comp) -> list[str]:
    """What a person would see differ between the two (reference first)."""
    out = [] if a.kind == b.kind else [f"{KIND_LABEL[a.kind].lower()} ở trang mẫu, {KIND_LABEL[b.kind].lower()} ở bản dựng"]
    if a.kind in ("heading", "text", "link", "button"):
        if abs(a.fs - b.fs) > max(1.0, a.fs * 0.05):
            out.append(f"cỡ chữ {a.fs:g}→{b.fs:g}px")
        if abs(a.fw - b.fw) >= 100:
            out.append(f"độ đậm {a.fw:.0f}→{b.fw:.0f}")
        if abs(a.ls - b.ls) > 0.4:
            out.append(f"giãn chữ {a.ls:g}→{b.ls:g}px")
        if a.lh and b.lh and abs(a.lh - b.lh) > 0.12:
            out.append(f"dãn dòng {a.lh:g}→{b.lh:g}")
        if a.tt != b.tt:
            out.append("chữ hoa" if a.tt else "bỏ chữ hoa")
    if a.kind in ("button", "input", "card", "image") and abs(a.radius - b.radius) > 2:
        out.append(f"bo góc {a.radius}→{b.radius}px")
    if a.kind == "button":
        if abs(a.pad[0] - b.pad[0]) > 2 or abs(a.pad[1] - b.pad[1]) > 3:
            out.append(f"đệm nút {a.pad[0]}/{a.pad[1]}→{b.pad[0]}/{b.pad[1]}px")
    if a.kind == "card":
        if a.shadow != b.shadow:
            out.append("đổ bóng" if a.shadow else "bỏ đổ bóng")
        if (a.border > 0) != (b.border > 0):
            out.append("viền" if a.border else "bỏ viền")
    if abs(a.w - b.w) > max(24, a.w * 0.15):
        out.append(f"rộng {a.w}→{b.w}px")
    return out


# ------------------------------------------------------------------ scoring

def _iou(a: Comp, b: Comp, ha: float, hb: float, wa: float, wb: float) -> float:
    ax0, ay0, ax1, ay1 = a.x / wa, a.y / ha, (a.x + a.w) / wa, (a.y + a.h) / ha
    bx0, by0, bx1, by1 = b.x / wb, b.y / hb, (b.x + b.w) / wb, (b.y + b.h) / hb
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
    if union <= 0:
        return 0.0
    # Small components barely overlap even when placed right: soften with the centre distance.
    centre = 1 - min(1.0, abs((ax0 + ax1) - (bx0 + bx1)) / 2 + abs((ay0 + ay1) - (by0 + by1)) / 2)
    return max(inter / union, centre * 0.8)


def _style(p: Pair) -> float:
    a, b = p.ref, p.built
    parts = []
    if a.kind in ("heading", "text", "link", "button"):
        parts.append(min(a.fs, b.fs) / max(a.fs, b.fs, 1))
        parts.append(1.0 if abs(a.fw - b.fw) < 100 else 0.6)
    if a.kind in ("button", "input", "card", "image"):
        parts.append(max(0.0, 1 - abs(a.radius - b.radius) / 24))
    if a.kind == "card":
        parts.append(1.0 if a.shadow == b.shadow else 0.7)
    return sum(parts) / len(parts) if parts else 1.0


def section_score(sid: str, ref: list[Comp], built: list[Comp], ref_box: dict, built_box: dict,
                  name: str = "") -> tuple[SectionCompare, list[Pair]]:
    pairs, missing, extra = match(ref, built, ref_box, built_box)
    ha, hb = max(ref_box.get("height", 1), 1), max(built_box.get("height", 1), 1)
    wa, wb = max(ref_box.get("width", 1), 1), max(built_box.get("width", 1), 1)
    w_ref = sum(WEIGHTS[c.kind] for c in ref) or 1
    w_built = sum(WEIGHTS[c.kind] for c in built) or 1
    credit = {id(p): (1.0 if p.ref.kind == p.built.kind else 0.5) for p in pairs}
    w_pair = sum(WEIGHTS[p.ref.kind] * credit[id(p)] for p in pairs)
    components = w_pair / max(w_ref, w_built) if (ref or built) else 1.0
    # Placement and style are judged over every reference component: a missing one counts as wrong.
    layout = (sum(_iou(p.ref, p.built, ha, hb, wa, wb) * WEIGHTS[p.ref.kind] * credit[id(p)] for p in pairs) / w_ref) if ref else 1.0
    style = (sum(_style(p) * WEIGHTS[p.ref.kind] * credit[id(p)] for p in pairs) / w_ref) if ref else 1.0
    height = min(ha, hb) / max(ha, hb)
    parts = {"components": round(components, 3), "layout": round(layout, 3), "style": round(style, 3), "height": round(height, 3)}
    score = 100 * (0.40 * components + 0.30 * layout + 0.20 * style + 0.10 * height)

    def count(items: list[Comp]) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for c in items:
            out[c.kind] += 1
        return dict(out)

    diffs = []
    for p in pairs:
        if p.diffs:
            diffs.append(f"{KIND_LABEL[p.ref.kind]}{' h' + str(p.ref.level) if p.ref.level else ''}: " + ", ".join(p.diffs))
    for kind, n in count(missing).items():
        diffs.append(f"thiếu {n} {KIND_LABEL[kind].lower()} so với trang mẫu")
    for kind, n in count(extra).items():
        diffs.append(f"thừa {n} {KIND_LABEL[kind].lower()}")
    return SectionCompare(id=sid, name=name, score=round(score, 1), parts=parts, matched=len(pairs),
                          missing=count(missing), extra=count(extra), diffs=diffs[:12],
                          ref_height=int(ha), built_height=int(hb)), pairs


def page_score(sections: list[SectionCompare]) -> float:
    """Height-weighted mean of the section scores (tall sections matter more)."""
    total = sum(max(s.ref_height, 1) for s in sections)
    return round(sum(s.score * max(s.ref_height, 1) for s in sections) / total, 1) if total else 0.0


# ------------------------------------------------------------------ tuning

_SAFE_SEL = re.compile(r'^(\[data-swarm-id="[a-z0-9-]{1,64}"\]|[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*){0,2})$')


def _median(values: list[float]) -> float:
    return statistics.median(values)


def tune_rules(section_id: str, pairs: list[Pair], page: str = "") -> dict[str, dict[str, str]]:
    """{selector: {property: value}} that move the rebuilt components to the reference's measured style.
    One value per selector (the median over its pairs), so a row of cards stays consistent."""
    scope = (f'[data-swarm-page="{page}"] ' if page else "") + f'[data-swarm-section="{section_id}"]'
    by_sel: dict[str, list[Pair]] = defaultdict(list)
    for p in pairs:
        if p.built.sel and _SAFE_SEL.match(p.built.sel):
            by_sel[p.built.sel].append(p)
    rules: dict[str, dict[str, str]] = {}
    for sel, group in by_sel.items():
        a = [p.ref for p in group]
        b = [p.built for p in group]
        kind = b[0].kind  # floors (body ≥16px, tap targets) follow what the element is on the rebuild
        same = all(p.ref.kind == p.built.kind for p in group)  # near-kind pairs only tune the type
        props: dict[str, str] = {}
        if kind in ("heading", "text", "link", "button"):
            fs_a, fs_b = _median([c.fs for c in a]), _median([c.fs for c in b])
            # Body text never goes under 16px (standards ch.7, QA): only headings follow the reference down.
            floor = 16 if kind == "text" else 12  # nav links, labels and buttons are short: their own size
            if abs(fs_a - fs_b) > max(1.0, fs_a * 0.05) and fs_a >= floor:
                props["font-size"] = f"{fs_a:g}px"
            fw_a, fw_b = _median([c.fw for c in a]), _median([c.fw for c in b])
            if (fw_a >= 550) != (fw_b >= 550):
                props["font-weight"] = "600" if fw_a >= 550 else "400"  # two weights per family (§2.2)
            ls_a, ls_b = _median([c.ls for c in a]), _median([c.ls for c in b])
            if abs(ls_a - ls_b) > 0.4:
                props["letter-spacing"] = f"{ls_a:g}px"
            lhs = [c.lh for c in a if c.lh]
            if lhs and kind != "button":
                lh_a = _median(lhs)
                lh_b = _median([c.lh for c in b if c.lh] or [lh_a])
                # Long text keeps a readable leading (QA: ≥1.4 for body copy).
                lh_a = max(lh_a, 1.4) if kind == "text" else max(lh_a, 0.9)
                if abs(lh_a - lh_b) > 0.12:
                    props["line-height"] = f"{lh_a:g}"
            tt = {c.tt for c in a}
            if len(tt) == 1 and tt != {c.tt for c in b}:
                props["text-transform"] = tt.pop() or "none"
        if same and kind in ("button", "input", "card", "image"):
            r_a, r_b = _median([c.radius for c in a]), _median([c.radius for c in b])
            if abs(r_a - r_b) > 2:
                props["border-radius"] = f"{r_a:.0f}px"
        if same and kind == "button":
            # Only ever larger: tap targets stay ≥48px (QA), so a smaller reference button keeps our padding.
            t_a, t_b = _median([c.pad[0] for c in a]), _median([c.pad[0] for c in b])
            l_a, l_b = _median([c.pad[1] for c in a]), _median([c.pad[1] for c in b])
            if t_a > t_b + 2 or l_a > l_b + 3:
                props["padding"] = f"{round(max(t_a, t_b) / 4) * 4:.0f}px {round(max(l_a, l_b) / 4) * 4:.0f}px"
        if same and kind == "card":
            shadow = sum(c.shadow for c in a) > len(a) / 2
            if shadow != (sum(c.shadow for c in b) > len(b) / 2):
                props["box-shadow"] = "var(--shadow-md)" if shadow else "none"
            border = sum(c.border > 0 for c in a) > len(a) / 2
            if border != (sum(c.border > 0 for c in b) > len(b) / 2):
                props["border"] = "1px solid var(--border-subtle)" if border else "0"
        if props:
            rules[f"{scope} {sel}"] = props
    return rules


def render_rules(blocks: dict[str, dict[str, dict[str, str]]]) -> str:
    """match.css body: one desktop block per section (latest measurement wins per selector)."""
    out = []
    for sid, rules in blocks.items():
        if not rules:
            continue
        body = "\n".join(f"  {sel} {{ " + " ".join(f"{k}: {v};" for k, v in props.items()) + " }"
                         for sel, props in rules.items())
        out.append(f"/* {sid} */\n{DESKTOP} {{\n{body}\n}}")
    return "\n".join(out)


def merge_rules(old: dict[str, dict[str, str]], new: dict[str, dict[str, str]]) -> tuple[dict[str, dict[str, str]], int]:
    """Merge a section's new rules into its old ones; returns (merged, how many properties changed)."""
    merged = {sel: dict(props) for sel, props in old.items()}
    changed = 0
    for sel, props in new.items():
        cur = merged.setdefault(sel, {})
        for k, v in props.items():
            if cur.get(k) != v:
                cur[k] = v
                changed += 1
    return merged, changed


def crew_of(kind: str) -> str:
    return next(c for c, (_, _, kinds) in CREWS.items() if kind in kinds)


def render_compare(result: dict, url: str) -> str:
    """COMPARE.md: the 1:1 acceptance, section by section."""
    lines = [f"# Nghiệm thu 1:1 với {url}", "",
             f"**Giống {result.get('total', 0):.0f}%** (trung bình theo chiều cao từng section) · "
             f"{result.get('rounds', 0)} vòng tinh chỉnh · đã chỉnh {result.get('tuned_total', result.get('tuned', 0))} thuộc tính.", "",
             "Mỗi section: component (tiêu đề, chữ, link, nút, ảnh, ô nhập, thẻ) của trang mẫu được ghép với component "
             "cùng loại ở vị trí gần nhất trên bản dựng. Điểm = 40% đủ component · 30% vị trí và kích thước · "
             "20% kiểu chữ, bo góc, đổ bóng · 10% chiều cao section. Chữ và ảnh không được so (structure clone không chép chúng).", "",
             "| Section | Giống | Component | Vị trí | Kiểu | Cao (mẫu → dựng) |", "|---|---|---|---|---|---|"]
    for s in result.get("sections", []):
        pr = s["parts"]
        lines.append(f"| {s.get('name') or s['id']} | {s['score']:.0f}% | {pr['components'] * 100:.0f}% | {pr['layout'] * 100:.0f}% | "
                     f"{pr['style'] * 100:.0f}% | {s['ref_height']} → {s['built_height']}px |")
    lines.append("")
    for s in result.get("sections", []):
        notes = s.get("diffs", []) + [f"thiếu hiệu ứng: {e}" for e in s.get("effects_missing", [])]
        if notes:
            lines.append(f"## {s.get('name') or s['id']}")
            lines += [f"- {d}" for d in notes]
            lines.append("")
    return "\n".join(lines)
