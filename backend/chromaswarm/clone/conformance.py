"""Clone B11: Master QA checks the rebuild against the reference's DESIGN.md (design.json), item by item.

Every section and every component of the extracted design becomes checks on the finished page, each with a
tolerance a person would not notice:

* section: present · height (±10%, at least 48px) · padding top / bottom (±16px);
* component (paired with the rebuild's by kind and relative place): present · x / y (±24px or 3% / 8%) ·
  width (±16px or 15%) · height for non-text pieces (±12px or 25%) · text size (±1px) and weight (same
  step) · text colour / button and card fill (near-equal) · radius (±2px);
* effects the design lists and the spec builds: present on the page.

Words and pictures are never compared (a structure clone does not copy them). The result: matched / total
items, per section, with every item that differs in words ("Tiêu đề h1 (96, 344): cỡ 60→48px").
"""

from __future__ import annotations

from chromaswarm.clone.components import KIND_LABEL, Comp, comps, match
from chromaswarm.engines.color import parse_css_color

BUILT_EFFECTS = {"scroll-reveal", "stagger-cards", "parallax", "marquee", "hover-lift", "hover-zoom", "hover-image",
                 "underline-link", "sticky-blur", "smooth-scroll", "load-in"}
TEXT = ("heading", "text", "link", "button")


def _hex_close(a: str | None, b: str | None, tol: int = 36) -> bool:
    if not a or not b or len(a) < 7 or len(b) < 7:
        return True  # not measured on one side: nothing to hold against it
    try:
        return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (1, 3, 5)) <= tol
    except ValueError:
        return True


def _same_hue(a: str | None, b: str | None) -> bool:
    """The rebuild's colour is the reference's moved in lightness only (made readable: same hue and chroma)."""
    pa, pb = parse_css_color(a or ""), parse_css_color(b or "")
    if not pa or not pb:
        return False
    ca, cb = pa[0], pb[0]
    if ca.c < 0.04 and cb.c < 0.04:
        return abs(ca.l - cb.l) <= 0.35  # greys: a darker / lighter grey
    dh = abs((ca.h - cb.h + 180) % 360 - 180)
    return dh <= 20 and abs(ca.c - cb.c) <= 0.08


def _iou(a: dict, b: Comp) -> float:
    ix = max(0, min(a["x"] + a["w"], b.x + b.w) - max(a["x"], b.x))
    iy = max(0, min(a["y"] + a["h"], b.y + b.h) - max(a["y"], b.y))
    inter = ix * iy
    union = a["w"] * a["h"] + b.w * b.h - inter
    return inter / union if union else 0.0


def _ref_comp(row: dict, n: int) -> Comp:
    return Comp(kind=row["kind"], x=row["x"], y=row["y"], w=row["w"], h=row["h"], i=n)


def _token(design: dict, kind: str, name: str | None) -> dict:
    return (design.get(kind) or {}).get(name or "", {}) if name else {}


def _padding(cs: list[Comp], height: float, width: float = 1440) -> tuple[float | None, float | None]:
    real = [c for c in cs if c.kind in ("heading", "text", "button", "link", "image", "input")
            and not (c.kind == "image" and height and c.w * c.h >= 0.5 * width * height)]  # a background, not content
    if not real:
        return None, None
    return min(c.y for c in real), max(0.0, height - max(c.y + c.h for c in real)) if height else None


def check(design: dict, built: dict[str, list[dict]], built_boxes: dict[str, dict],
          effects_missing: dict[str, list[str]] | None = None, skipped: set[str] | None = None) -> dict:
    """Item-by-item conformance of the rebuild (`built`: measured components per section, section-relative)
    to the extracted design."""
    effects_missing = effects_missing or {}
    skipped = skipped or set()
    sections = []
    fixes: dict[str, dict[str, dict[str, str]]] = {}  # section -> {built selector: {property: value}}
    total = passed = 0
    for s in design.get("sections", []):
        sid = s["id"]
        if sid in skipped:
            continue
        items: list[tuple[str, bool, str]] = []  # (label, ok, why)
        box = s.get("box") or {}
        bb = built_boxes.get(sid)
        items.append(("Có section", bool(bb), "" if bb else "không có trên bản dựng"))
        if bb:
            ha, hb = float(box.get("height") or 0), float(bb.get("height") or 0)
            if ha:
                ok = abs(hb - ha) <= max(48.0, ha * 0.10)
                items.append(("Chiều cao section", ok, "" if ok else f"{ha:.0f}→{hb:.0f}px"))
            mine = comps(built.get(sid, []))
            top, bottom = _padding(mine, hb)
            for label, want, got in (("Đệm trên", s["padding"].get("top"), top), ("Đệm dưới", s["padding"].get("bottom"), bottom)):
                if want is not None and got is not None:
                    ok = abs(got - want) <= 16
                    items.append((label, ok, "" if ok else f"{want:.0f}→{got:.0f}px"))
            ref = [_ref_comp(r, n) for n, r in enumerate(s["components"])]
            pairs, _missing, _extra = match(ref, mine, {"height": ha or hb, "width": box.get("width") or 1440},
                                           {"height": hb, "width": bb.get("width") or 1440})
            paired = {p.ref.i: p.built for p in pairs}
            width = float(box.get("width") or 1440)
            for n, row in enumerate(s["components"]):
                what = f"{KIND_LABEL.get(row['kind'], row['kind'])}" + (f" {row['type']}" if row.get("type") else "") + f" ({row['x']}, {row['y']})"
                b = paired.get(n)
                if b is None and row.get("frame"):
                    # A frame around one picture: present when that picture (or a frame) stands in its place.
                    if any(c.kind in ("image", "card") and _iou(row, c) > 0.6 for c in mine):
                        items.append((what, True, ""))
                        continue
                if b is None:
                    items.append((what, False, "thiếu trên bản dựng"))
                    continue
                diffs = []
                fix: dict[str, str] = {}
                # Words: where they really run (a centred line in a wide box is judged by its line, not its box).
                rx, rw = (row["x"] + row.get("tx", 0), row["tw"]) if row.get("tw") else (row["x"], row["w"])
                bx, bw = (b.x + b.tx, b.tw) if (row.get("tw") and b.tw) else (b.x, b.w)
                if abs(bx - rx) > max(24.0, width * 0.03):
                    diffs.append(f"x {rx}→{bx}")
                if abs(b.y - row["y"]) > max(24.0, (ha or hb) * 0.08):
                    diffs.append(f"y {row['y']}→{b.y}")
                if abs(bw - rw) > max(16.0, rw * 0.15) and not (row["kind"] in TEXT and row.get("tw")):
                    diffs.append(f"rộng {rw}→{bw}px")
                if row["kind"] not in TEXT and abs(b.h - row["h"]) > max(12.0, row["h"] * 0.25):
                    diffs.append(f"cao {row['h']}→{b.h}px")
                t = _token(design, "type", row.get("type"))
                if t and row["kind"] in TEXT:
                    if abs(b.fs - t["size"]) > 1:
                        diffs.append(f"cỡ chữ {t['size']}→{b.fs:g}px")
                        if t["size"] >= (16 if row["kind"] == "text" else 12):  # body text never under 16px (QA)
                            fix["font-size"] = f"{t['size']}px"
                    if abs(round(b.fw / 100) * 100 - t["weight"]) >= 100:
                        diffs.append(f"độ đậm {t['weight']}→{b.fw:.0f}")
                        fix["font-weight"] = str(t["weight"])
                ink = _token(design, "colors", row.get("ink")).get("value")
                if ink and row["kind"] in TEXT and not _hex_close(ink, b.color) and not _same_hue(ink, b.color):
                    diffs.append(f"màu chữ {ink}→{b.color}")
                    fix["color"] = ink  # made readable by the heal (same hue) before it is written
                v = (design.get("components") or {}).get(row.get("variant") or "", {})
                fill = _token(design, "colors", v.get("fill")).get("value") if v else None
                if fill and row["kind"] in ("button", "card") and not _hex_close(fill, b.bg) and not _same_hue(fill, b.bg):
                    diffs.append(f"nền {fill}→{b.bg or 'trong suốt'}")
                    fix["background-color"] = fill
                if v and row["kind"] in ("button", "card", "image") and abs(b.radius - v.get("radius", 0)) > 2 \
                        and not (v.get("radius", 0) >= row["h"] / 2 - 1 and b.radius >= b.h / 2 - 1):
                    diffs.append(f"bo góc {v.get('radius', 0)}→{b.radius}px")
                    fix["border-radius"] = f"{v.get('radius', 0)}px"
                if fix and b.sel:
                    fixes.setdefault(sid, {})[b.sel] = {**fix, "_bg": _token(design, "colors", box.get("bg")).get("value") or "",
                                                         "_large": "1" if (b.fs >= 24 or row["kind"] == "heading") else ""}
                items.append((what, not diffs, ", ".join(diffs)))
        for e in s.get("effects", []):
            if e.get("effect") in BUILT_EFFECTS:
                ok = e["effect"] not in effects_missing.get(sid, [])
                items.append((f"Hiệu ứng {e.get('label') or e['effect']}", ok, "" if ok else "chưa có trên trang"))
        ok_n = sum(1 for _, ok, _ in items if ok)
        total += len(items)
        passed += ok_n
        sections.append({"id": sid, "name": s["name"], "passed": ok_n, "total": len(items),
                         "failed": [f"{label}: {why}" for label, ok, why in items if not ok][:40]})
    return {"passed": passed, "total": total, "pct": round(100 * passed / total, 1) if total else 0.0, "sections": sections,
            "fixes": fixes}
