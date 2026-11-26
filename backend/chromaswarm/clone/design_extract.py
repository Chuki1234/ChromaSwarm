"""Clone: the reference's own DESIGN.md, extracted backwards from what was measured — section by section.

Creative mode *chooses* its design system (engines, presets). Clone *reads* it off the reference page:

1. Tokens, with how often each is used: colours by role (section backgrounds, text levels, accents / button
   fills, card surfaces), every text style the page really uses (size / weight / leading / tracking / case),
   the spacing scale (section padding and the gaps between pieces), radii, shadows, content width, motion.
2. Component library: repeated pieces grouped into variants (buttons by fill / size / radius, cards, pictures
   by aspect ratio, links), each with its measured size and hover / click behaviour.
3. Section specs, in page order: role, box (height, background, padding, side margins), layout (rows /
   columns of the measured tree), and a table of components — place, size, and the tokens / variant it uses.

`design.json` (the dict) is what the build and Master QA read; DESIGN.md is its rendering. Measurements
only: geometry, computed style, timings — never the page's words or pictures (decision 11).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from chromaswarm.clone.components import KIND_LABEL, comps
from chromaswarm.clone.layout import Node, build_tree

TEXT_KINDS = ("heading", "text", "link", "button")


def _hex(c: str | None) -> str | None:
    if not c or not c.startswith("#") or len(c) < 7:
        return None
    return c[:7].lower()


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _close(a: str, b: str, tol: int = 18) -> bool:
    return sum(abs(x - y) for x, y in zip(_rgb(a), _rgb(b))) <= tol


def _lum(h: str) -> float:
    r, g, b = (v / 255 for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _sat(h: str) -> float:
    r, g, b = _rgb(h)
    return (max(r, g, b) - min(r, g, b)) / 255


class _Palette:
    """Colours clustered (near-equal hexes are one token), weighted by use."""

    def __init__(self) -> None:
        self.groups: list[dict] = []

    def add(self, hexc: str | None, role: str, weight: float = 1.0) -> str | None:
        h = _hex(hexc)
        if not h:
            return None
        for g in self.groups:
            if _close(g["hex"], h):
                g["uses"][role] += weight
                return g["hex"]
        self.groups.append({"hex": h, "uses": Counter({role: weight})})
        return h

    def tokens(self) -> dict[str, dict]:
        """Named tokens: bg/*, surface/*, text/*, accent/*, by role and use."""
        out: dict[str, dict] = {}
        def pick(role: str, prefix: str, names: list[str], key=None):
            key = key or (lambda g: -g["uses"][role])
            groups = sorted([g for g in self.groups if g["uses"][role] > 0], key=key)
            for name, g in zip(names, groups):
                if g.get("name"):
                    continue
                g["name"] = f"{prefix}/{name}"
                out[g["name"]] = {"value": g["hex"], "uses": round(sum(g["uses"].values()), 1), "role": role}
        pick("section", "bg", ["page", "alt", "band", "band-2", "band-3"])
        pick("text", "text", ["primary", "secondary", "muted", "subtle", "extra"])
        pick("fill", "accent", ["primary", "secondary", "tertiary"], key=lambda g: (-_sat(g["hex"]), -g["uses"]["fill"]))
        pick("surface", "surface", ["card", "card-2", "card-3"])
        for g in self.groups:  # anything left keeps a plain name
            if not g.get("name"):
                role = g["uses"].most_common(1)[0][0]
                g["name"] = f"{role}/{g['hex'][1:]}"
                out[g["name"]] = {"value": g["hex"], "uses": round(sum(g["uses"].values()), 1), "role": role}
        return out

    def name_of(self, hexc: str | None) -> str | None:
        h = _hex(hexc)
        if not h:
            return None
        return next((g.get("name") for g in self.groups if _close(g["hex"], h)), None)


def _type_key(c) -> tuple:
    """A text style is its size and weight; its leading / tracking / case are the group's most common values."""
    return (round(c.fs), int(round(c.fw / 100) * 100))


def _bucket(v: float, step: int = 8) -> int:
    return int(round(v / step) * step)


def _tree_summary(node: Node | None, depth: int = 0) -> str:
    """'rows[ cols[ rows(3), picture-stack ], cols(3) ]' — the layout, one line."""
    if node is None:
        return "—"
    if node.kind in ("rows", "cols", "layer"):
        kids = node.children
        if depth >= 2:
            return f"{node.kind}({len(kids)})"
        name = {"rows": "hàng", "cols": "cột", "layer": "lớp"}[node.kind]
        return f"{name}[" + ", ".join(_tree_summary(k, depth + 1) for k in kids) + "]"
    if node.kind == "card":
        return f"thẻ({len(node.children)})"
    return KIND_LABEL.get(node.kind.replace("back-", ""), node.kind).lower()


def extract(clone) -> dict:
    """design.json for a Clone (clone: CloneSource after B2: sections, boxes, components, style, motion)."""
    boxes, pieces = clone.boxes or {}, clone.components or {}
    report = clone.motion_report or {}
    palette = _Palette()
    # Section backgrounds by painted area, text colours by characters, fills / surfaces by count.
    for sid, box in boxes.items():
        palette.add(box.get("bg"), "section", box.get("height", 0) * box.get("width", 1440) / 1e5)
    for sid, cs in pieces.items():
        for c in comps(cs):
            if c.kind in ("heading", "text", "link"):
                palette.add(c.color, "text", max(c.chars, 1))
            if c.kind == "button" and c.bg:
                palette.add(c.bg, "fill", 3)
                palette.add(c.color, "text", max(c.chars, 1))
            if c.kind == "card" and c.bg:
                palette.add(c.bg, "surface", 1)
    colors = palette.tokens()

    # Text styles, named by size: the biggest is display / h1, then h2…, the rest body / caption.
    styles: dict[tuple, dict] = {}
    for sid, cs in pieces.items():
        for c in comps(cs):
            if c.kind not in TEXT_KINDS:
                continue
            k = _type_key(c)
            st = styles.setdefault(k, {"size": k[0], "weight": k[1], "uses": 0, "kinds": Counter(),
                                       "_lh": Counter(), "_ls": Counter(), "_tt": Counter()})
            st["uses"] += 1
            st["kinds"][c.kind] += 1
            st["_lh"][round(c.lh or 0, 1)] += 1
            st["_ls"][round(c.ls, 1)] += 1
            st["_tt"][c.tt or ""] += 1
    for st in styles.values():
        st["leading"] = st.pop("_lh").most_common(1)[0][0]
        st["tracking"] = st.pop("_ls").most_common(1)[0][0]
        st["case"] = st.pop("_tt").most_common(1)[0][0]
    ordered = sorted(styles.values(), key=lambda s: (-s["size"], -s["weight"]))
    lead = {id(s): s["kinds"].most_common(1)[0][0] for s in ordered}  # what the style is mostly used for
    heading_sizes = sorted({s["size"] for s in ordered if lead[id(s)] == "heading"}, reverse=True)
    names = ["display", "h1", "h2", "h3", "h4", "h5"] if heading_sizes and heading_sizes[0] >= 56 else ["h1", "h2", "h3", "h4", "h5", "h6"]
    level = {size: names[min(i, len(names) - 1)] for i, size in enumerate(heading_sizes)}
    type_tokens: dict[str, dict] = {}
    for s in ordered:
        if lead[id(s)] == "heading" and s["size"] in level:
            base = level[s["size"]]
        elif lead[id(s)] == "button":
            base = "button"
        elif lead[id(s)] == "link":
            base = "link"
        else:
            base = "body-lg" if s["size"] >= 18 else "body" if s["size"] >= 15 else "caption" if s["size"] >= 12 else "micro"
        name, n = base, 2
        while name in type_tokens:
            name, n = f"{base}-{n}", n + 1
        s["name"] = name
        type_tokens[name] = {k: s[k] for k in ("size", "weight", "leading", "tracking", "case", "uses")}
    style_name = {k: s["name"] for k, s in styles.items()}

    # Spacing: section padding + gaps between stacked pieces, on a 4px grid, with counts.
    from chromaswarm.clone.brief_doc import _spacing
    spacing = Counter()
    per_section_space: dict[str, dict] = {}
    for sid, box in boxes.items():
        sp = _spacing(pieces.get(sid, []), box)
        if not sp:
            continue
        per_section_space[sid] = sp
        for v in (sp["top"], sp["bottom"]):
            if v:
                spacing[_bucket(v, 4)] += 1
        for g, n in sp["gaps"]:
            spacing[_bucket(g, 4)] += n
    radii = Counter(c.radius for cs in pieces.values() for c in comps(cs) if c.kind in ("button", "card", "image", "input") and c.radius)

    # Component library: variants of buttons, cards, pictures, links.
    variants: dict[str, dict] = {}
    by_key: dict[tuple, str] = {}
    counts: Counter = Counter()

    def variant(c) -> str | None:
        if c.kind == "button":
            fill = palette.name_of(c.bg) or ("transparent" if not c.bg else c.bg)
            key = ("button", fill, palette.name_of(c.color), _bucket(c.h, 4), c.radius >= c.h / 2 - 1, bool(c.border))
            base = "button/" + ("primary" if fill.startswith("accent/primary") else "outline" if not c.bg and c.border
                                else "ghost" if not c.bg else "filled")
        elif c.kind == "card":
            key = ("card", palette.name_of(c.bg), c.radius, c.shadow, bool(c.border), _bucket(c.w, 40), _bucket(c.h, 40))
            base = "card"
        elif c.kind == "image":
            ratio = round(c.w / max(c.h, 1), 1)
            key = ("image", ratio, c.radius, c.media)
            base = "image/" + ("wide" if ratio >= 1.6 else "landscape" if ratio >= 1.1 else "square" if ratio >= 0.9 else "portrait")
        elif c.kind == "link":
            key = ("link", style_name.get(_type_key(c)), palette.name_of(c.color))
            base = "link"
        else:
            return None
        if key not in by_key:
            name, n = base, 2
            while name in variants:
                name, n = f"{base}-{n}", n + 1
            by_key[key] = name
            variants[name] = {"kind": c.kind, "w": c.w, "h": c.h, "radius": c.radius,
                              "fill": palette.name_of(c.bg) if c.kind in ("button", "card") else None,
                              "ink": palette.name_of(c.color) if c.kind in TEXT_KINDS else None,
                              "type": style_name.get(_type_key(c)) if c.kind in TEXT_KINDS else None,
                              "padding": c.pad[:2] if c.kind == "button" else None, "shadow": c.shadow, "border": c.border,
                              "ratio": round(c.w / max(c.h, 1), 2) if c.kind == "image" else None, "hover": [], "uses": 0}
        counts[by_key[key]] += 1
        return by_key[key]

    # Hover / click behaviour of controls, matched to components by place.
    controls = report.get("controls") or []

    def behaviour(sid: str, c) -> dict:
        box = boxes.get(sid, {})
        cx, cy = box.get("left", 0) + c.x + c.w / 2, box.get("top", 0) + c.y + c.h / 2
        best = min(controls, key=lambda k: abs(k.get("left", 0) + k["w"] / 2 - cx) + abs(k["top"] + k["h"] / 2 - cy), default=None)
        if not best or abs(best.get("left", 0) + best["w"] / 2 - cx) + abs(best["top"] + best["h"] / 2 - cy) > 40:
            return {}
        act = best.get("action") or {}
        return {"hover": best.get("changes") or [], "hover_ms": best.get("duration_ms") or 0,
                "click": act.get("kind"), "to": act.get("target") or act.get("note")}

    effects = defaultdict(list)
    for it in report.get("items") or []:
        effects[it.get("section")].append({"effect": it.get("effect"), "label": it.get("label"), "how": it.get("how"),
                                           "params": it.get("params") or {}})

    sections = []
    for order, s in enumerate(clone.sections, 1):
        sid = s["id"]
        box = boxes.get(sid, {})
        cs = comps(pieces.get(sid, []))
        rows = []
        for c in sorted(cs, key=lambda c: (c.y, c.x)):
            row = {"i": c.i, "kind": c.kind, "x": c.x, "y": c.y, "w": c.w, "h": c.h}
            if c.motion:
                row["motion"] = c.motion
            if c.kind in ("heading", "text", "link") and c.tw:
                row["tx"], row["tw"] = c.tx, c.tw  # where the words really run inside the box (centred copy)
            if c.kind == "card" and any(o.kind == "image" and o.w * o.h >= 0.7 * c.w * c.h and c.x - 4 <= o.x and o.x + o.w <= c.x + c.w + 4
                                        for o in cs):
                row["frame"] = True  # a frame around one picture: present when the picture is
            if c.kind in TEXT_KINDS:
                row["type"] = style_name.get(_type_key(c))
                row["ink"] = palette.name_of(c.color)
                row["chars"] = c.chars
            v = variant(c)
            if v:
                row["variant"] = v
            if c.kind in ("button", "link"):
                b = behaviour(sid, c)
                if b:
                    row.update(b)
                    if v and b.get("hover") and not variants[v]["hover"]:
                        variants[v]["hover"] = b["hover"]
                        variants[v]["hover_ms"] = b.get("hover_ms")
            rows.append(row)
        sp = per_section_space.get(sid, {})
        sections.append({
            "order": order, "id": sid, "name": s["name"], "structure": s["structure"],
            "box": {"top": box.get("top"), "left": box.get("left", 0), "height": box.get("height"), "width": box.get("width"),
                    "bg": palette.name_of(box.get("bg")), "band": bool(box.get("band")), "overlay": bool(box.get("overlay"))},
            "padding": {"top": sp.get("top"), "bottom": sp.get("bottom")}, "margins": {"left": sp.get("left"), "right": sp.get("right")},
            "gaps": sp.get("gaps", []), "layout": _tree_summary(build_tree(cs, float(box.get("width") or 1440)) if cs else None),
            "components": rows, "effects": effects.get(sid, []),
            "backgrounds": [b for b in (clone.backgrounds or []) if box and box.get("top", 0) <= b["top"] + b["h"] / 2 <= box.get("top", 0) + box.get("height", 0)],
        })
    for name in variants:
        variants[name]["uses"] = counts[name]

    style = clone.style or {}
    motion = sorted({int((it.get("params") or {})["duration_ms"]) for it in report.get("items") or [] if (it.get("params") or {}).get("duration_ms")})
    easings = Counter((it.get("params") or {}).get("easing") for it in report.get("items") or [] if (it.get("params") or {}).get("easing"))
    return {
        "source": clone.url, "title": clone.title,
        "fonts": [{"family": f.get("family"), "original": f.get("original"), "provider": f.get("provider")} for f in clone.fonts]
                 or [{"family": clone.heading_font}, {"family": clone.body_font}],
        "colors": colors, "type": type_tokens,
        "spacing": [{"value": v, "uses": n} for v, n in sorted(spacing.items()) if v > 0],
        "radii": [{"value": v, "uses": n} for v, n in sorted(radii.items())],
        "content_width": clone.content_width or max((boxes[k].get("width", 1440) - sp["left"] - sp["right"]
                                                      for k, sp in per_section_space.items()), default=None),
        "motion": {"durations_ms": motion, "easing": easings.most_common(1)[0][0] if easings else style.get("motion_easing")},
        "separation": style.get("separation"), "density": style.get("density"),
        "components": variants, "sections": sections,
    }


# ------------------------------------------------------------------ DESIGN.md

def render(design: dict) -> str:
    out = [f"# DESIGN.md — trích ngược từ trang mẫu", "",
           f"- Trang mẫu: {design['source']} · {design.get('title') or ''}",
           "- **Clone:** mọi con số dưới đây **đo được trên trang mẫu** (khổ 1440px), không do engine chọn. "
           "Bản dựng làm theo tài liệu này, và Master QA nghiệm thu bằng cách đối chiếu từng mục với chính tài liệu này.",
           "- Không chứa chữ hay hình của trang mẫu (chỉ vị trí, kích thước, kiểu, thời gian).", ""]
    out += ["## 1. Token", "", "### Màu", "| Token | Giá trị | Vai trò | Dùng |", "|---|---|---|---|"]
    for name, t in design["colors"].items():
        out.append(f"| `{name}` | {t['value']} | {t['role']} | {t['uses']:g} |")
    out += ["", "### Kiểu chữ", "Font: " + ", ".join(f"{f['family']}" + (f" (thay cho {f['original']})" if f.get("original") else "")
                                                  for f in design["fonts"] if f.get("family")), "",
            "| Token | Cỡ | Đậm | Dòng | Giãn chữ | Kiểu | Dùng |", "|---|---|---|---|---|---|---|"]
    for name, t in design["type"].items():
        out.append(f"| `{name}` | {t['size']}px | {t['weight']} | {t['leading'] or '—'} | {t['tracking']:g}px | {t['case'] or '—'} | {t['uses']} |")
    out += ["", "### Khoảng cách", " · ".join(f"{s['value']}px ×{s['uses']}" for s in design["spacing"]) or "—",
            "", "### Bo góc", " · ".join(f"{r['value']}px ×{r['uses']}" for r in design["radii"]) or "—",
            "", f"- Bề rộng nội dung: {design.get('content_width') or '—'}px · tách khối bằng: {design.get('separation') or '—'} · "
            f"độ thoáng: {design.get('density') or '—'}",
            f"- Chuyển động: {', '.join(f'{d}ms' for d in design['motion']['durations_ms']) or '—'} · easing {design['motion'].get('easing') or '—'}", ""]
    out += ["## 2. Thư viện component", "", "| Biến thể | Loại | Kích thước | Nền / chữ | Kiểu chữ | Bo góc | Đệm | Rê chuột | Dùng |",
            "|---|---|---|---|---|---|---|---|---|"]
    for name, v in design["components"].items():
        pad = f"{v['padding'][0]}/{v['padding'][1]}" if v.get("padding") else "—"
        hover = ", ".join(v.get("hover") or []) + (f" · {v['hover_ms']}ms" if v.get("hover_ms") else "")
        out.append(f"| `{name}` | {KIND_LABEL.get(v['kind'], v['kind'])} | {v['w']}×{v['h']}"
                   + (f" ({v['ratio']}:1)" if v.get("ratio") else "") + f" | {v.get('fill') or '—'} / {v.get('ink') or '—'} | "
                   f"{v.get('type') or '—'} | {v['radius']}px | {pad} | {hover or '—'} | {v['uses']} |")
    out += ["", "## 3. Từng section (theo thứ tự trang)", ""]
    for s in design["sections"]:
        b = s["box"]
        out += [f"### {s['order']}. {s['name']} · `{s['id']}` (`{s['structure']}`)",
                f"- Khung: y {b.get('top')} · cao {b.get('height')}px · nền `{b.get('bg') or '—'}`"
                + (" · dải tối" if b.get("band") else "") + (" · **nổi trên section dưới (fixed)**" if b.get("overlay") else ""),
                f"- Đệm trên / dưới: {s['padding'].get('top')} / {s['padding'].get('bottom')}px · lề trái / phải: "
                f"{s['margins'].get('left')} / {s['margins'].get('right')}px · khoảng cách: "
                + (", ".join(f"{g}px×{n}" for g, n in s["gaps"]) or "—"),
                f"- Bố cục: {s['layout']}"]
        for e in s["effects"]:
            out.append(f"- Hiệu ứng · {e['label']}: {e['how']}")
        for bg in s["backgrounds"][:4]:
            out.append(f"- Nền vẽ · {bg['kind']} {bg['w']}×{bg['h']}" + (f": `{bg['css'][:100]}`" if bg.get("css") else ""))
        if s["components"]:
            out += ["", "| # | Loại | Vị trí (x, y) | Kích thước | Token / biến thể | Ký tự | Rê chuột · bấm |", "|---|---|---|---|---|---|---|"]
            for n, c in enumerate(s["components"], 1):
                tok = " · ".join(x for x in (c.get("variant"), c.get("type"), c.get("ink")) if x) or "—"
                act = ", ".join(c.get("hover") or [])
                if c.get("click"):
                    act += (" · " if act else "") + f"bấm: {c['click']}" + (f" {c['to']}" if c.get("to") else "")
                out.append(f"| {n} | {KIND_LABEL.get(c['kind'], c['kind'])} | {c['x']}, {c['y']} | {c['w']}×{c['h']} | {tok} | "
                           f"{c.get('chars') or '—'} | {act or '—'} |")
        out.append("")
    return "\n".join(out) + "\n"
