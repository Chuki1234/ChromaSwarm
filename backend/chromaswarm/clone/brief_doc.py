"""Clone B2: CLONE_BRIEF.md — the build team's preparation sheet for any reference page.

Written after the structure read and the effect check, from measurements only (geometry, computed style,
timings, where controls lead): never the page's words, picture URLs or brand.

1. The page: which page of the site, what kind of site, its concept (the goal it drives visitors to).
2. Layout and sections: dominant layout, every section in order with its role in that concept.
3. Spacing: per section, the space above / below, side margins and the gaps between its pieces.
4. Type, colour, backgrounds: fonts and sizes, colour roles, backgrounds the page paints itself.
5. Pictures: how many, which repeat, shown and file sizes, icons and logos.
6. Controls: every button / link — size, what changes on hover, what a click does or where it leads.
7. Effects and animations: where, how many, how they run.
8. What can be cloned, what cannot, and what replaces it.
"""

from __future__ import annotations

import statistics
from collections import Counter

from chromaswarm.clone.analysis import DOMAIN_WORDS
from chromaswarm.clone.components import comps

# Why a section of this kind is on a page: its job in the page's concept.
ROLE = {
    "sticky-bar": "điều hướng; nút hành động chính luôn trong tầm tay",
    "split-7-5": "lời hứa chính của trang + hành động đầu tiên, có hình minh hoạ",
    "full-bleed-image": "lời hứa chính trên nền / hình lớn tràn màn hình + hành động đầu tiên",
    "hero-text": "lời hứa chính bằng chữ + hành động đầu tiên (đăng ký / bắt đầu)",
    "feature-showcase": "giới thiệu một tính năng lớn, kèm hình sản phẩm",
    "bento": "nhóm lợi ích / tính năng dạng thẻ để quét nhanh",
    "alternating-z": "kể lần lượt từng tính năng, chữ và hình đổi bên",
    "text-cards": "các ý chính dạng thẻ chữ",
    "inline-metrics": "con số / dải nhỏ tạo uy tín",
    "logo-strip": "khách hàng / đối tác tiêu biểu — tạo uy tín",
    "testimonials": "bằng chứng xã hội: lời khách hàng — tạo niềm tin",
    "accordion": "giải đáp băn khoăn (FAQ) trước khi hành động",
    "feature-accordion": "liệt kê tính năng; mở từng mục để xem chi tiết",
    "list-rows": "danh sách mục (bài viết, sự kiện, kinh nghiệm…)",
    "tabs": "nội dung chia theo tab",
    "horizontal-scroller": "dải danh mục / thẻ cuộn ngang",
    "grid-4": "lưới sản phẩm để chọn mua",
    "gallery": "bộ sưu tập hình",
    "split-5-7": "khối nội dung chữ + hình",
    "full-bleed-band": "lời kêu gọi hành động (CTA) trước khi rời trang",
    "footer-columns": "liên kết phụ, pháp lý, mạng xã hội",
    "auth": "form đăng nhập / đăng ký",
}
ACTION = {"same-page": "ở lại trang", "external": "sang trang ngoài", "internal": "sang trang", "dialog": "mở hộp thoại / menu",
          "toggle": "mở / đóng một khối", "content": "đổi nội dung trên trang", "scroll": "cuộn tới một phần",
          "none": "không thấy thay đổi", "form-submit": "nút gửi form (không bấm)", "not-clicked": "chưa bấm thử",
          "unknown": "không xác định"}

def _med(xs: list[float]) -> float:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else 0


def _role(sec: dict) -> str:
    if sec["id"] == "feature-accordion":
        return ROLE["feature-accordion"]
    return ROLE.get(sec["structure"], "khối nội dung")


def _spacing(pieces: list[dict], box: dict) -> dict:
    """Space above / below the content, side margins, and the vertical gaps between stacked pieces."""
    cs = sorted((c for c in comps(pieces) if c.kind in ("heading", "text", "button", "link", "image", "card", "input")),
                key=lambda c: (c.y, c.x))
    if not cs:
        return {}
    width, height = float(box.get("width") or 1440), float(box.get("height") or 0)
    top = min(c.y for c in cs)
    bottom = max(c.y + c.h for c in cs)
    gaps = []
    for a, b in zip(cs, cs[1:]):
        gap = b.y - (a.y + a.h)
        if 0 < gap < 400 and b.x < a.x + a.w and b.x + b.w > a.x:  # stacked, overlapping columns
            gaps.append(round(gap))
    return {"top": round(top), "bottom": round(max(0, height - bottom)) if height else None,
            "left": round(min(c.x for c in cs)), "right": round(max(0, width - max(c.x + c.w for c in cs))),
            "gaps": sorted(Counter(gaps).most_common(6), key=lambda g: -g[1])}


def _concept(clone, domain: str, sections: list[dict], controls: list[dict]) -> list[str]:
    kinds = [s["structure"] for s in sections]
    goals = Counter(c["action"].get("role") for c in controls
                    if c.get("action", {}).get("kind") == "internal" and c["action"].get("role"))
    goal = goals.most_common(1)[0][0] if goals else ""
    lines = [f"- **Loại trang:** {DOMAIN_WORDS.get(domain, domain)}."]
    page = "trang chủ (/)" if (clone.url.rstrip("/").count("/") <= 2) else f"trang {clone.url.split('/', 3)[-1]}"
    lines.append(f"- **Trang nào trong web:** {page}.")
    if goal:
        n = sum(1 for c in controls if c.get("action", {}).get("role") == goal)
        lines.append(f"- **Mục tiêu chuyển đổi:** đưa khách tới **{goal}** ({n} nút / link dẫn tới đó).")
    funnel = []
    if any(k in kinds for k in ("split-7-5", "full-bleed-image", "hero-text")):
        funnel.append("lời hứa (hero)")
    if any(k in kinds for k in ("bento", "feature-showcase", "alternating-z", "text-cards")) or any(s["id"] == "feature-accordion" for s in sections):
        funnel.append("lợi ích / tính năng")
    if "testimonials" in kinds or "logo-strip" in kinds:
        funnel.append("bằng chứng xã hội")
    if "list-rows" in kinds or "grid-4" in kinds:
        funnel.append("nội dung / sản phẩm")
    if any(s["structure"] == "accordion" and s["id"] != "feature-accordion" for s in sections):
        funnel.append("giải đáp băn khoăn (FAQ)")
    if "full-bleed-band" in kinds:
        funnel.append("lời kêu gọi cuối")
    if funnel:
        lines.append("- **Concept (luồng thuyết phục):** " + " → ".join(funnel) + ".")
    return lines


def _hex(css: str) -> str:
    return css.replace("oklch(", "oklch(").strip()


def build_brief(clone, domain: str, spec=None) -> str:
    """`spec`: the CloneSpec the rebuild follows (section 8 renders it); built from `clone` when not given."""
    from chromaswarm.clone.spec import CloneSpec, build_spec
    spec = spec if spec is not None else (CloneSpec.model_validate(clone.spec) if clone.spec else build_spec(clone))
    sections = clone.sections
    boxes, pieces = clone.boxes or {}, clone.components or {}
    report = clone.motion_report or {}
    controls = report.get("controls") or []
    style = clone.style or {}
    out = [f"# CLONE_BRIEF.md — chuẩn bị dữ liệu cho đội thi công", "",
           f"- Trang mẫu: {clone.url}", f"- Tiêu đề trang: {clone.title or '—'} · ngôn ngữ: {clone.lang or '—'}",
           "- Mọi số liệu dưới đây là **đo được** (vị trí, kích thước, style, thời gian, nơi nút dẫn tới); "
           "không chép chữ, hình hay thương hiệu của trang.", ""]

    # 1. page + concept
    out += ["## 1. Trang này là gì", *_concept(clone, domain, sections, controls), ""]

    # 2. layout + sections
    total = max((b.get("top", 0) + b.get("height", 0) for b in boxes.values()), default=0)
    out += ["## 2. Layout và các section", f"- **Layout:** trang xếp dọc {len(sections)} section, cao ~{total}px ở khổ 1440px"
            + (f"; cột nội dung hẹp ~{clone.content_width}px" if clone.content_width else "") + ".", "",
            "| # | Section | Kiểu | Vị trí · cao | Nền | Có gì | Vì sao có trong concept |", "|---|---|---|---|---|---|---|"]
    for i, sec in enumerate(sections, 1):
        box = boxes.get(sec["id"], {})
        kinds = Counter(c.get("kind") for c in pieces.get(sec["id"], []))
        has = ", ".join(f"{n} {k}" for k, n in kinds.most_common(5)) or "—"
        where = f"y {box['top']} · {box['height']}px" if box else "không có trên trang mẫu — Chroma thêm vào"
        bg = (box.get("bg") or "—") + (" (dải tối)" if box.get("band") and box.get("bg") else "")
        out.append(f"| {i} | {sec['name']} | `{sec['structure']}` | {where} | {bg} | {has} | {_role(sec)} |")
    out.append("")

    # 3. spacing
    out += ["## 3. Khoảng cách (px, khổ 1440)", "", "| Section | Đệm trên / dưới | Lề trái / phải | Khoảng cách giữa các phần tử (px × số lần) |",
            "|---|---|---|---|"]
    for sec in sections:
        sp = _spacing(pieces.get(sec["id"], []), boxes.get(sec["id"], {}))
        if sp:
            gaps = ", ".join(f"{g}×{n}" for g, n in sp["gaps"]) or "—"
            out.append(f"| {sec['name']} | {sp['top']} / {sp['bottom'] if sp['bottom'] is not None else '—'} | {sp['left']} / {sp['right']} | {gaps} |")
    if style:
        out += ["", f"- Lưới: {round(style.get('spacing_adherence', 0) * 100)}% khoảng cách nằm trên lưới 4/8px; bước hay dùng: "
                f"{', '.join(str(x) for x in style.get('common_spacing', [])[:8])}. Độ thoáng: {style.get('density', '—')}; "
                f"bo góc trung vị {style.get('radius_median') or 0:g}px; tách khối bằng {style.get('separation', '—')}."]
    out.append("")

    # 4. type, colour, backgrounds
    out += ["## 4. Chữ, màu, nền"]
    fonts = [f.get("family") for f in clone.fonts] or [x for x in (clone.heading_font, clone.body_font) if x]
    type_rows: dict[str, list] = {}
    for sec_pieces in pieces.values():
        for c in comps(sec_pieces):
            if c.kind == "heading":
                type_rows.setdefault(f"h{c.level or 2}", []).append(c)
            elif c.kind in ("text", "link", "button"):
                type_rows.setdefault(c.kind, []).append(c)
    out.append(f"- **Font:** {', '.join(dict.fromkeys(fonts)) or 'font của trang không tải được từ máy chủ miễn phí (dùng font thay thế)'}"
               + (f" · cỡ gốc {style.get('base_font_px'):g}px, tỉ lệ cỡ chữ {style.get('type_scale_ratio')}" if style.get("base_font_px") else "")
               + (", nhãn chữ in hoa" if style.get("uppercase_labels") else "") + ".")
    for k in sorted(type_rows):
        cs = type_rows[k]
        sizes = sorted({round(c.fs) for c in cs})
        weights = sorted({round(c.fw / 100) * 100 for c in cs})
        out.append(f"  - {k}: {len(cs)} chỗ · cỡ {', '.join(f'{x}px' for x in sizes[:6])} · đậm {', '.join(str(w) for w in weights)}"
                   f" · dòng ~{_med([c.lh for c in cs if c.lh]):.2f}")
    if style:
        roles = (("Nền", style.get("surfaces", [])), ("Chữ", style.get("text_colors", [])), ("Màu nhấn", style.get("accents", [])))
        for name, cols in roles:
            if cols:
                out.append(f"- **{name}:** " + ", ".join(f"{_hex(c['css'])} ({round(c['share'] * 100)}%)" for c in cols[:5]))
        out.append(f"- Tổng thể: nền {'tối' if style.get('is_dark') else 'sáng'}, màu nhấn dùng {style.get('accent_usage', '—')}"
                   + (", có nền mờ (backdrop blur)" if style.get("backdrop_blur") else "") + ".")
    bgs = clone.backgrounds or []
    if bgs:
        out.append(f"- **Nền vẽ riêng (CSS, không phải ảnh):** {len(bgs)} lớp")
        for b in bgs[:14]:
            what = {"gradient": "gradient", "glow": "quầng sáng (radial)", "glass": "kính mờ", "faint-type": "chữ khổng lồ mờ"}[b["kind"]]
            extra = (" · xiên" if b.get("skew") else "") + (f" · {b['blur']}" if b.get("blur") else "") + (f" · {b['glass']}" if b.get("glass") else "") \
                + (f" · chữ {b['font_px']}px" if b.get("font_px") else "")
            out.append(f"  - {what} {b['w']}×{b['h']} tại y {b['top']}{extra}" + (f": `{b['css'][:140]}`" if b.get("css") else ""))
    else:
        out.append("- Nền vẽ riêng: không thấy gradient / kính mờ đáng kể.")
    out.append("")

    # 5. pictures
    media = clone.media or []
    pics = [m for m in media if not m["icon"] and m["kind"] in ("img", "video", "background", "canvas", "picture")]
    icons = [m for m in media if m["icon"]]
    deco = [m for m in media if not m["icon"] and m["kind"] == "svg"]
    files = {m["file"] for m in pics if m.get("file") is not None}
    out += ["## 5. Hình", f"- **{len(pics)} hình** ({len(files)} file khác nhau), **{len(icons)} icon** ≤48px, {len(deco)} hình vẽ SVG lớn.", ""]
    if pics:
        out += ["| Ở section | Loại | Kích thước hiển thị | File gốc | Lặp lại |", "|---|---|---|---|---|"]
        by_file = Counter(m.get("file") for m in pics)
        for m in pics[:40]:
            sec = next((s["name"] for s in sections if boxes.get(s["id"]) and boxes[s["id"]]["top"] <= m["top"] + m["h"] / 2
                        <= boxes[s["id"]]["top"] + boxes[s["id"]]["height"]), "—")
            nat = f"{m['nw']}×{m['nh']}" if m.get("nw") else "—"
            rep = f"×{by_file[m['file']]}" if m.get("file") is not None and by_file[m["file"]] > 1 else ""
            out.append(f"| {sec} | {m['kind']}{' · logo' if m.get('logo') else ''} | {m['w']}×{m['h']} | {nat} | {rep} |")
    for m in deco[:6]:
        out.append(f"- Hình vẽ SVG {m['w']}×{m['h']} tại y {m['top']}" + (" (trang trí)" if m.get("decorative") else ""))
    out.append("")

    # 6. controls
    out += ["## 6. Nút và link", f"- **{len(controls)} nút / link** được rê chuột thật và kiểm tra khi bấm.", "",
            "| Section | Loại | Kích thước | Khi rê chuột | Khi bấm |", "|---|---|---|---|---|"]
    for c in controls[:60]:
        act = c.get("action") or {}
        sec = next((s["name"] for s in sections if s["id"] == c.get("section")), c.get("section", "—"))
        click: str = ACTION.get(act.get("kind", ""), str(act.get("kind") or "—"))
        if act.get("target"):
            click += f" {act['target']}"
        if act.get("role"):
            click += f" ({act['role']})"
        if act.get("redirect"):
            click += f" → chuyển tiếp {act['redirect']}"
        if act.get("new_tab"):
            click += " · tab mới"
        if act.get("broken"):
            click += f" · **link hỏng ({act['broken']})**"
        hover = ", ".join(c.get("changes") or []) or "không đổi"
        if c.get("duration_ms"):
            hover += f" · {c['duration_ms']}ms"
        out.append(f"| {sec} | {c.get('kind')} | {c.get('w')}×{c.get('h')} | {hover} | {click} |")
    out.append("")

    # 7. effects
    items = report.get("items") or []
    out += ["## 7. Hiệu ứng và animation", f"- **{len(items)} hiệu ứng** (đã cuộn {report.get('steps', 0)} màn hình, rê chuột {report.get('hovered', 0)} phần tử)"
            + (f"; thư viện: {', '.join(report['libs'])}" if report.get("libs") else "") + ".", ""]
    for it in items:
        sec = next((s["name"] for s in sections if s["id"] == it.get("section")), it.get("section", "trang"))
        out.append(f"- **{it['label']}** · {sec}: {it['how']}")
    for m in report.get("models") or []:
        out.append(f"- **Canvas / 3D** · {m['w']}×{m['h']} tại y {m['top']}: {m['how']}")
    out.append("")

    # 8. clone / do-not-clone
    from chromaswarm.clone.spec import render
    out += ["## 8. Clone được gì, không clone gì (CloneSpec — bản dựng làm đúng như bảng này)", ""] + render(spec)
    return "\n".join(out) + "\n"

