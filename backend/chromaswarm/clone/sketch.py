"""Clone sketch step: draw the page from what Chroma *read*, and check it against what is really there.

B2 (after the effect check), as a pass of its own:

1. `draw()` turns the measured reading (section boxes + components) into a grey-box sketch, 1440px wide:
   text = one bar per line, headings darker, buttons = pills, links = short underlined bars, pictures =
   crossed boxes, cards = outlines, inputs = framed fields, each section on its own measured background.
2. Coverage: a full-page screenshot of the reference is split into 24px cells; a cell "has content" when
   its pixels vary (text, pictures, edges — flat colour and soft gradients do not). Content cells that no
   sketched piece covers are reading gaps (e.g. a column of cards that kept moving while it was measured).
3. Gaps are measured again with every animation paused (`REGION_JS`): the pieces found there are added to
   their section, the sketch is redrawn and the coverage computed again.
4. Reference screenshot | sketch, screen by screen, go to `artifacts/sketch/` for the user (B7).

B10 (before the colour pass): the rebuild's wireframe is measured the same way and drawn as a sketch;
reference sketch | rebuild sketch, screen by screen, plus how much of the reference's sketched area the
rebuild covers per section (`compare_sketches`).

Only geometry and computed style are used; no words or pictures leave the reference page.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

CELL = 24
SCREEN_H = 900
WIDTH = 1440


# ------------------------------------------------------------------ drawing

def _lum(hex_: str | None) -> float:
    if not hex_ or not hex_.startswith("#") or len(hex_) < 7:
        return 1.0
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def pieces_abs(boxes: dict[str, dict], comps: dict[str, list[dict]]) -> list[dict]:
    """Every piece in page coordinates, with its section's background (to pick sketch greys)."""
    out = []
    for sid, box in boxes.items():
        for c in comps.get(sid, []):
            if c.get("kind") not in ("heading", "text", "link", "button", "image", "input", "card"):
                continue
            out.append({**c, "sid": sid, "ax": box.get("left", 0) + c.get("x", 0), "ay": box.get("top", 0) + c.get("y", 0),
                        "dark": _lum(box.get("bg") or box.get("page")) < 0.4})
    return out


def draw(boxes: dict[str, dict], comps: dict[str, list[dict]], height: int, gaps: list[dict] | None = None,
         title: str = "") -> str:
    """The sketch as SVG (page coordinates, 1440 wide)."""
    h = max(int(height), 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{h}" viewBox="0 0 {WIDTH} {h}">',
           f'<rect width="{WIDTH}" height="{h}" fill="#ffffff"/>']
    for sid, box in sorted(boxes.items(), key=lambda kv: kv[1].get("top", 0)):
        bg = box.get("bg") or "#ffffff"
        if not (bg.startswith("#") and len(bg) in (7, 9)):
            bg = "#ffffff"
        out.append(f'<rect x="{box.get("left", 0)}" y="{box.get("top", 0)}" width="{box.get("width", WIDTH)}" '
                   f'height="{box.get("height", 0)}" fill="{bg[:7]}"/>')
        out.append(f'<text x="8" y="{box.get("top", 0) + 16}" font-family="monospace" font-size="12" '
                   f'fill="{"#ffffff" if _lum(bg) < 0.4 else "#9ca3af"}" opacity="0.7">{html.escape(sid)}</text>')
    for p in pieces_abs(boxes, comps):
        ink, soft, line = ("#e5e7eb", "#4b5563", "#9ca3af") if p["dark"] else ("#374151", "#d1d5db", "#6b7280")
        x, y, w, hh = p["ax"], p["ay"], max(p.get("w", 0), 1), max(p.get("h", 0), 1)
        k = p["kind"]
        if k in ("heading", "text", "link"):
            fs = max(p.get("fs") or 16, 8)
            lh = fs * (p.get("lh") or 1.3)
            lines = max(1, round(hh / lh))
            bar = max(3, fs * (0.6 if k == "heading" else 0.42))
            tw = p.get("tw") or w
            for n in range(min(lines, 40)):
                bw = tw if n < lines - 1 or lines == 1 else tw * 0.65
                by = y + n * lh + (lh - bar) / 2
                fill = ink if k == "heading" else line
                out.append(f'<rect x="{x + (p.get("tx") or 0):.0f}" y="{by:.0f}" width="{bw:.0f}" height="{bar:.0f}" rx="{bar / 2:.0f}" fill="{fill}"/>')
            if k == "link":
                out.append(f'<rect x="{x}" y="{y + hh - 2}" width="{w}" height="1.5" fill="{line}"/>')
        elif k == "button":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{min(p.get("radius", 8), hh / 2)}" fill="{soft}" stroke="{line}"/>')
            out.append(f'<rect x="{x + w * 0.25:.0f}" y="{y + hh / 2 - 3:.0f}" width="{w * 0.5:.0f}" height="6" rx="3" fill="{line}"/>')
        elif k == "image":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{p.get("radius", 0)}" fill="{soft}" fill-opacity="0.6" stroke="{line}"/>')
            out.append(f'<path d="M{x} {y}L{x + w} {y + hh}M{x + w} {y}L{x} {y + hh}" stroke="{line}" stroke-width="1"/>')
        elif k == "card":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{p.get("radius", 0)}" fill="none" stroke="{line}" stroke-dasharray="6 4"/>')
        elif k == "input":
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="{p.get("radius", 4)}" fill="none" stroke="{line}" stroke-width="2"/>')
    for g in gaps or []:
        out.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" fill="#ef4444" fill-opacity="0.12" '
                   f'stroke="#ef4444" stroke-width="3" stroke-dasharray="10 6"/>')
        out.append(f'<text x="{g["x"] + 8}" y="{g["y"] + 22}" font-family="sans-serif" font-size="16" font-weight="700" '
                   f'fill="#ef4444">{"đã đo lại" if g.get("filled") else "đọc thiếu"}</text>')
    if title:
        out.append(f'<text x="{WIDTH - 12}" y="20" text-anchor="end" font-family="sans-serif" font-size="14" fill="#ef4444">{html.escape(title)}</text>')
    out.append("</svg>")
    return "\n".join(out)


# ------------------------------------------------------------------ occupancy / coverage

def occupancy(pieces: list[dict], height: int, pad: int = 1, boxes: dict[str, dict] | None = None) -> set[tuple[int, int]]:
    """Grid cells (col, row) covered by sketched pieces (a cell of slack around each). A card frame and a
    picture filling half its section or more are backgrounds: they do not count as having read what is on them."""
    cells: set[tuple[int, int]] = set()
    rows, cols = height // CELL + 1, WIDTH // CELL + 1
    for p in pieces:
        if p["kind"] == "card":
            continue
        if p["kind"] == "image" and boxes and p.get("sid") in boxes:
            b = boxes[p["sid"]]
            if p.get("w", 0) * p.get("h", 0) >= 0.5 * max(1, b.get("width", WIDTH) * b.get("height", 0)):
                continue
        x0, y0 = int(p["ax"] // CELL) - pad, int(p["ay"] // CELL) - pad
        x1, y1 = int((p["ax"] + p.get("w", 0)) // CELL) + pad, int((p["ay"] + p.get("h", 0)) // CELL) + pad
        for r in range(max(0, y0), min(rows, y1 + 1)):
            for c in range(max(0, x0), min(cols, x1 + 1)):
                cells.add((c, r))
    return cells


def regions(cells: set[tuple[int, int]], min_cells: int = 8) -> list[dict]:
    """Connected uncovered cells → page rectangles (small specks dropped)."""
    seen: set[tuple[int, int]] = set()
    out = []
    for start in cells:
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            c, r = stack.pop()
            group.append((c, r))
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                n = (c + d[0], r + d[1])
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if len(group) >= min_cells:
            xs, ys = [g[0] for g in group], [g[1] for g in group]
            out.append({"x": min(xs) * CELL, "y": min(ys) * CELL, "w": (max(xs) - min(xs) + 1) * CELL,
                        "h": (max(ys) - min(ys) + 1) * CELL, "cells": len(group)})
    return sorted(out, key=lambda g: -g["cells"])


def coverage(content: set[tuple[int, int]], covered: set[tuple[int, int]]) -> tuple[float, set[tuple[int, int]]]:
    if not content:
        return 100.0, set()
    missing = content - covered
    return round(100 * (1 - len(missing) / len(content)), 1), missing


CONTENT_JS = r"""async ({ src, cell, width }) => {
  // Cells of a full-page screenshot that hold something (text, pictures, edges): luminance varies inside.
  const img = await new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = src; });
  const scale = width / img.width, W = width, H = Math.round(img.height * scale);
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, W, H);
  const out = [];
  for (let y = 0; y < H; y += cell) {
    const d = g.getImageData(0, y, W, Math.min(cell, H - y)).data, rowW = W * 4, hh = Math.min(cell, H - y);
    for (let x = 0; x < W; x += cell) {
      let n = 0, s = 0, s2 = 0;
      for (let yy = 0; yy < hh; yy += 2) for (let xx = x; xx < Math.min(x + cell, W); xx += 2) {
        const k = yy * rowW + xx * 4, l = 0.2126 * d[k] + 0.7152 * d[k + 1] + 0.0722 * d[k + 2];
        n++; s += l; s2 += l * l;
      }
      const sd = Math.sqrt(Math.max(0, s2 / n - (s / n) ** 2));
      if (sd > 14) out.push([x / cell, y / cell]);
    }
  }
  return { cells: out, height: H };
}"""

REGION_JS = r"""({ rects, limit }) => {
  // Pieces inside the given page rectangles, with every animation paused (moving tracks stand still).
  for (const a of document.getAnimations()) { try { a.pause(); } catch (e) {} }
  const sy = scrollY, out = [];
  const hex = c => { const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/.exec(c || ""); if (!m || (m[4] !== undefined && +m[4] < 0.05)) return null;
    return "#" + [m[1], m[2], m[3]].map(v => Math.round(+v).toString(16).padStart(2, "0")).join(""); };
  const inRect = (r, R) => { const ix = Math.max(0, Math.min(r.right, R.x + R.w) - Math.max(r.left, R.x));
    const iy = Math.max(0, Math.min(r.bottom + sy, R.y + R.h) - Math.max(r.top + sy, R.y)); return ix * iy >= 0.5 * r.width * r.height; };
  for (const el of document.querySelectorAll("img, svg, video, canvas, picture, h1, h2, h3, h4, h5, h6, p, li, a, button, span, div, input")) {
    if (out.length >= limit) break;
    if (el.tagName !== "svg" && el.closest("svg")) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8 || !el.checkVisibility({ opacityProperty: true })) continue;
    if (!rects.some(R => inRect(r, R))) continue;
    const cs = getComputedStyle(el), tag = el.tagName;
    const media = /^(IMG|SVG|VIDEO|CANVAS|PICTURE)$/i.test(tag) || (cs.backgroundImage.includes("url(") && r.width >= 40);
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length >= 2);
    let kind = null;
    if (media && r.width >= 24 && r.height >= 24) kind = "image";
    else if (tag === "BUTTON" || el.getAttribute("role") === "button") kind = "button";
    else if (tag === "A" && own) kind = "link";
    else if (tag === "INPUT") kind = "input";
    else if (/^H[1-6]$/.test(tag) && own) kind = "heading";
    else if (own && (el.innerText || "").trim().length >= 2) kind = "text";
    if (!kind) continue;
    if (kind !== "image" && el.closest("button, a") && el.closest("button, a") !== el) continue;
    out.push({ kind, ax: Math.round(r.left), ay: Math.round(r.top + sy), w: Math.round(r.width), h: Math.round(r.height),
               fs: parseFloat(cs.fontSize) || 16, fw: parseFloat(cs.fontWeight) || 400,
               lh: (parseFloat(cs.lineHeight) || 0) / (parseFloat(cs.fontSize) || 16), color: hex(cs.color) || "#000000",
               bg: hex(cs.backgroundColor), radius: Math.round(parseFloat(cs.borderTopLeftRadius) || 0),
               chars: kind === "image" ? 0 : (el.innerText || "").trim().length, level: /^H([1-6])$/.test(tag) ? +tag[1] : 0,
               media: kind === "image" ? tag.toLowerCase() : "" });
  }
  for (const a of document.getAnimations()) { try { a.play(); } catch (e) {} }
  return out;
}"""


def _iou(a: dict, b: dict) -> float:
    ix = max(0, min(a["ax"] + a["w"], b["ax"] + b["w"]) - max(a["ax"], b["ax"]))
    iy = max(0, min(a["ay"] + a["h"], b["ay"] + b["h"]) - max(a["ay"], b["ay"]))
    inter = ix * iy
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union else 0.0


def add_found(boxes: dict[str, dict], comps: dict[str, list[dict]], found: list[dict]) -> int:
    """Pieces measured again in the gaps → their section (section-relative), unless already there."""
    have = pieces_abs(boxes, comps)
    added = 0
    for f in found:
        cy = f["ay"] + f["h"] / 2
        sid = next((k for k, b in boxes.items() if b.get("top", 0) <= cy <= b.get("top", 0) + b.get("height", 0)), None)
        if not sid or any(_iou(f, h) > 0.4 for h in have):
            continue
        # A text inside a picture of the same gap is part of it (a screenshot's own words).
        if f["kind"] != "image" and any(g["kind"] == "image" and g is not f and _iou({**f, "w": f["w"], "h": f["h"]}, g) > 0
                                        and g["ax"] <= f["ax"] and g["ay"] <= f["ay"] and g["ax"] + g["w"] >= f["ax"] + f["w"]
                                        and g["ay"] + g["h"] >= f["ay"] + f["h"] for g in found):
            continue
        box = boxes[sid]
        piece = {k: v for k, v in f.items() if k not in ("ax", "ay")}
        if piece["kind"] in ("link", "button") and not piece.get("vision"):
            piece["kind"] = "text"  # found in a gap, its behaviour unknown: drawn as words, never a dead control
        piece.update(x=int(f["ax"] - box.get("left", 0)), y=int(f["ay"] - box.get("top", 0)), found=True)
        comps.setdefault(sid, []).append(piece)
        have.append({**f, "sid": sid})
        added += 1
    return added


# ------------------------------------------------------------------ vision: what is in a gap

VISION_KINDS = {"image", "card", "button", "text", "heading", "logo", "icon", "input", "video", "mixed"}
VISION_LAYOUTS = {"single", "row", "column", "grid"}
VISION_SYSTEM = """You look at a crop of a web page that a layout reader could not measure.
Name the user-interface components it shows, as JSON only:
{"kind": one of image|card|button|text|heading|logo|icon|input|video|mixed,
 "count": how many of them (1-24), "layout": single|row|column|grid, "rows": n, "cols": n,
 "note": a few words on what it is (e.g. "two columns of CV template previews")}.
Count repeated items (cards, logos, buttons) one by one. Never transcribe the page's words."""
# Their kind in the reading (what the rebuild draws): pictures of any kind are images, a mixed block a card.
AS_KIND = {"logo": "image", "icon": "image", "video": "image", "mixed": "card"}


def parse_vision(raw: dict) -> dict | None:
    """The model's answer, validated against closed sets (anything else = no answer)."""
    if not isinstance(raw, dict) or raw.get("kind") not in VISION_KINDS:
        return None
    layout = raw.get("layout") if raw.get("layout") in VISION_LAYOUTS else "single"
    try:
        count = max(1, min(int(raw.get("count") or 1), 24))
        rows = max(1, min(int(raw.get("rows") or 1), 12))
        cols = max(1, min(int(raw.get("cols") or 1), 12))
    except (TypeError, ValueError):
        return None
    if layout == "single":
        rows = cols = count = 1
    elif layout == "row":
        rows, cols = 1, count
    elif layout == "column":
        rows, cols = count, 1
    else:
        count = min(count, rows * cols) or rows * cols
    return {"kind": raw["kind"], "count": count, "layout": layout, "rows": rows, "cols": cols,
            "note": str(raw.get("note") or "")[:80]}


def pieces_from_vision(gap: dict, seen: dict, gutter: int = 16) -> list[dict]:
    """A described gap → pieces of that kind laid out on its grid (page coordinates)."""
    rows, cols = seen["rows"], seen["cols"]
    w = (gap["w"] - gutter * (cols - 1)) / cols
    h = (gap["h"] - gutter * (rows - 1)) / rows
    kind = AS_KIND.get(seen["kind"], seen["kind"])
    out = []
    for n in range(seen["count"]):
        r, c = divmod(n, cols)
        out.append({"kind": kind, "ax": round(gap["x"] + c * (w + gutter)), "ay": round(gap["y"] + r * (h + gutter)),
                    "w": max(8, round(w)), "h": max(8, round(h)), "fs": 16 if kind != "heading" else 32, "fw": 400,
                    "lh": 1.4, "color": "#000000", "radius": 8 if kind in ("card", "button", "image") else 0,
                    "chars": 24 if kind in ("text", "heading", "button") else 0,
                    "media": seen["kind"] if kind == "image" else "", "vision": seen["note"] or seen["kind"]})
    return out


def placeholder(gap: dict) -> list[dict]:
    """No vision model: keep the gap's place as one block, so the rebuild does not close it up."""
    return [{"kind": "image", "ax": gap["x"], "ay": gap["y"], "w": gap["w"], "h": gap["h"], "fs": 16, "fw": 400,
             "color": "#000000", "radius": 0, "media": "unknown", "vision": "chưa nhận dạng"}]


async def describe_gaps(page, gaps: list[dict], vision) -> list[tuple[dict, dict | None]]:
    """Crop each gap off the reference (animations paused) and ask the vision model what it is."""
    import asyncio
    out = []
    for g in gaps[:8]:
        seen = None
        if vision is not None:
            try:
                crop = await page.screenshot(type="jpeg", quality=75, full_page=True,
                                             clip={"x": g["x"], "y": g["y"], "width": g["w"], "height": g["h"]})
                raw = await asyncio.to_thread(vision.complete_json, VISION_SYSTEM,
                                              f"The crop is {g['w']}x{g['h']} px of a 1440px-wide page.",
                                              [_data_url(crop, "image/jpeg")], 400)
                seen = parse_vision(raw)
            except Exception:  # noqa: BLE001 — no answer = a placeholder block
                seen = None
        out.append((g, seen))
    return out


# ------------------------------------------------------------------ the B2 pass

def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(data).decode()


async def _pairs(page, left_src: str, right_svg: str, height: int, out_dir: Path, prefix: str,
                 labels: tuple[str, str]) -> list[str]:
    """Left image | right sketch, one JPEG per 900px screen."""
    doc = (f'<html><body style="margin:0;background:#fff;width:{WIDTH * 2 + 24}px">'
           f'<div style="display:flex;gap:24px;align-items:flex-start">'
           f'<div style="position:relative;width:{WIDTH}px"><img src="{left_src}" style="display:block;width:{WIDTH}px"/>'
           f'<div style="position:absolute;top:8px;left:8px;background:#111;color:#fff;font:600 16px sans-serif;padding:4px 10px;border-radius:6px">{labels[0]}</div></div>'
           f'<div style="position:relative;width:{WIDTH}px">{right_svg}'
           f'<div style="position:absolute;top:8px;left:8px;background:#111;color:#fff;font:600 16px sans-serif;padding:4px 10px;border-radius:6px">{labels[1]}</div></div>'
           f'</div></body></html>')
    await page.set_viewport_size({"width": WIDTH * 2 + 24, "height": SCREEN_H})
    await page.set_content(doc, wait_until="load")
    names = []
    for k, y in enumerate(range(0, min(height, SCREEN_H * 14), SCREEN_H)):
        name = f"{prefix}-{k + 1:02d}.jpg"
        await page.screenshot(path=str(out_dir / name), type="jpeg", quality=72, full_page=True,
                              clip={"x": 0, "y": y, "width": WIDTH * 2 + 24, "height": min(SCREEN_H, height - y)})
        names.append(name)
    return names


async def check_reading(url: str, boxes: dict[str, dict], comps: dict[str, list[dict]], out_dir: Path,
                        vision=None) -> dict:
    """Sketch what was read, find reading gaps against the real page, measure them again (B2); what is
    still not read is cropped and named by the vision model (`vision`: JSONChat), or kept as a block."""
    from playwright.async_api import async_playwright

    from chromaswarm.playwright_engine.style_dna_scraper import goto_ready
    out_dir.mkdir(parents=True, exist_ok=True)
    comps = {k: [dict(c) for c in v] for k, v in comps.items()}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            page = await browser.new_page(viewport={"width": WIDTH, "height": SCREEN_H})
            await goto_ready(page, url)
            total = await page.evaluate("document.documentElement.scrollHeight")
            for y in range(0, total, SCREEN_H // 2):  # lazy content in, then back to the top
                await page.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
                await page.wait_for_timeout(120)
            await page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
            await page.wait_for_timeout(600)
            # Fixed bars would repeat on every screen of a full-page shot: drop them out of the flow for the shot.
            await page.add_style_tag(content="*{animation-play-state:paused!important}")
            shot = await page.screenshot(full_page=True, type="jpeg", quality=70)
            (out_dir / "reference.jpg").write_bytes(shot)
            work = await browser.new_page()
            found_px = await work.evaluate(CONTENT_JS, {"src": _data_url(shot, "image/jpeg"), "cell": CELL, "width": WIDTH})
            height = int(found_px["height"])
            content = {(c, r) for c, r in found_px["cells"]}
            before, missing = coverage(content, occupancy(pieces_abs(boxes, comps), height, boxes=boxes))
            gaps = regions(missing)
            added = 0
            if gaps:
                found = await page.evaluate(REGION_JS, {"rects": gaps[:12], "limit": 240})
                added = add_found(boxes, comps, found)
            after, missing = coverage(content, occupancy(pieces_abs(boxes, comps), height, boxes=boxes))
            left = regions(missing)
            # Still not read: what the eye sees there, named by the vision model and laid out on its grid.
            described = []
            for g, seen in await describe_gaps(page, [r for r in left if r["w"] >= 48 and r["h"] >= 48], vision):
                if not seen and g.get("cells", 0) < 24:
                    continue  # a small unnamed speck (a gradient edge, a rule): not worth a block
                found = pieces_from_vision(g, seen) if seen else placeholder(g)
                n = add_found(boxes, comps, found)
                added += n
                described.append({**{k: g[k] for k in ("x", "y", "w", "h")}, "seen": seen, "added": n})
            after, missing = coverage(content, occupancy(pieces_abs(boxes, comps), height, boxes=boxes))
            left = regions(missing)
            for g in gaps:
                g["filled"] = not any(_iou({"ax": g["x"], "ay": g["y"], "w": g["w"], "h": g["h"]},
                                           {"ax": r["x"], "ay": r["y"], "w": r["w"], "h": r["h"]}) > 0.3 for r in left)
            svg = draw(boxes, comps, height, gaps=gaps, title=f"Chroma đọc được {after:g}% trang")
            (out_dir / "sketch.svg").write_text(svg, encoding="utf-8")
            pairs = await _pairs(work, _data_url(shot, "image/jpeg"), svg, height, out_dir, "ref",
                                 ("Trang mẫu (ảnh chụp)", "Sketch từ những gì Chroma đọc được"))
        finally:
            await browser.close()
    return {"coverage_before": before, "coverage": after, "gaps": len(gaps), "remeasured": added, "described": described,
            "gaps_left": [{k: g[k] for k in ("x", "y", "w", "h")} for g in left[:12]],
            "pairs": pairs, "height": height, "components": comps}


# ------------------------------------------------------------------ the B10 check

def compare_sketches(ref_boxes: dict[str, dict], ref_comps: dict[str, list[dict]],
                     built_boxes: dict[str, dict], built_comps: dict[str, list[dict]]) -> dict:
    """How much of each reference section's sketched area the rebuild's sketch covers, both laid out
    section by section from the top of each section (the rebuild's sections may be taller or shorter)."""
    out: dict[str, float] = {}
    for sid, box in ref_boxes.items():
        if sid not in built_boxes:
            continue
        ref_local = pieces_abs({sid: {**box, "top": 0, "left": 0}}, {sid: ref_comps.get(sid, [])})
        built_local = pieces_abs({sid: {**built_boxes[sid], "top": 0, "left": 0}}, {sid: built_comps.get(sid, [])})
        h = int(max(box.get("height", 0), built_boxes[sid].get("height", 0))) + CELL
        a, b = occupancy(ref_local, h, pad=0), occupancy(built_local, h, pad=1)
        if a:
            out[sid] = round(100 * len(a & b) / len(a), 1)
    total = round(sum(out.values()) / len(out), 1) if out else 0.0
    return {"score": total, "sections": out}


def compare_pixels(ref_cells: set[tuple[int, int]], built_cells: set[tuple[int, int]],
                   ref_boxes: dict[str, dict], built_boxes: dict[str, dict]) -> dict:
    """What the eye sees, section by section: the reference screenshot's content cells that the rebuild's
    screenshot also has content in (one cell of slack), each section aligned at its own top. Missing regions
    come back in the rebuild's page coordinates (red frames on its screenshot)."""
    out: dict[str, float] = {}
    missing_px: list[dict] = []
    for sid, box in ref_boxes.items():
        bb = built_boxes.get(sid)
        if not bb:
            continue
        r0, r1 = int(box.get("top", 0) // CELL), int((box.get("top", 0) + box.get("height", 0)) // CELL)
        b0, b1 = int(bb.get("top", 0) // CELL), int((bb.get("top", 0) + bb.get("height", 0)) // CELL)
        ref_local = {(c, r - r0) for c, r in ref_cells if r0 <= r < r1}
        built_local = {(c, r - b0) for c, r in built_cells if b0 <= r < b1}
        slack = {(c + dc, r + dr) for c, r in built_local for dc in (-1, 0, 1) for dr in (-1, 0, 1)}
        if not ref_local:
            continue
        miss = ref_local - slack
        out[sid] = round(100 * (1 - len(miss) / len(ref_local)), 1)
        for g in regions(miss, min_cells=12)[:4]:
            missing_px.append({**g, "y": g["y"] + b0 * CELL, "sid": sid})
    total = round(sum(out.values()) / len(out), 1) if out else 0.0
    return {"score": total, "sections": out, "missing": missing_px}


def shot_with_frames(shot_src: str, width: int, height: int, frames: list[dict], title: str) -> str:
    """An SVG of a screenshot with red frames over what it lacks."""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             f'<image href="{shot_src}" x="0" y="0" width="{width}" height="{height}"/>']
    for g in frames:
        parts.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" fill="#ef4444" fill-opacity="0.1" '
                     f'stroke="#ef4444" stroke-width="3" stroke-dasharray="10 6"/>')
        parts.append(f'<text x="{g["x"] + 8}" y="{g["y"] + 22}" font-family="sans-serif" font-size="16" font-weight="700" fill="#ef4444">thiếu so với trang mẫu</text>')
    parts.append(f'<text x="{width - 12}" y="24" text-anchor="end" font-family="sans-serif" font-size="16" font-weight="700" fill="#ef4444">{html.escape(title)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


async def content_cells(page, shot: bytes) -> tuple[set[tuple[int, int]], int]:
    found = await page.evaluate(CONTENT_JS, {"src": _data_url(shot, "image/jpeg"), "cell": CELL, "width": WIDTH})
    return {(c, r) for c, r in found["cells"]}, int(found["height"])


async def shot_pairs(page, ref_shot: bytes, built_svg: str, height: int, out_dir: Path, prefix: str = "shot") -> list[str]:
    return await _pairs(page, _data_url(ref_shot, "image/jpeg"), built_svg, height, out_dir, prefix,
                        ("Trang mẫu (ảnh chụp)", "Bản dựng wireframe (ảnh chụp) · khung đỏ = thiếu"))


async def sketch_pairs_built(page, ref_svg: str, built_svg: str, height: int, out_dir: Path, prefix: str = "built") -> list[str]:
    return await _pairs(page, _data_url(ref_svg.encode(), "image/svg+xml"), built_svg, height, out_dir, prefix,
                        ("Sketch trang mẫu", "Sketch bản dựng (wireframe)"))
