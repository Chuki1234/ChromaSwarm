"""Clone B2: the reference read top-down, the way a designer would before rebuilding it.

1. Overview (the preparation step): what the site is for, its concept, the dominant layout, how many sections,
   the type and colours it mainly uses, its effects and 3D scenes, every control hovered.
2. Top-down: the navigation bar, then each section in page order — its background, then its pieces from top to
   bottom (headings, text, buttons, links, pictures, 3D canvases, cards) with their colour, size, spacing and type.

Everything here is measured (geometry, computed style, timings); none of the page's words or pictures.
"""

from __future__ import annotations

from collections import Counter

from chromaswarm.clone.components import KIND_LABEL, comps

DOMAIN_WORDS = {"saas": "dịch vụ / phần mềm (SaaS) — trang giới thiệu sản phẩm", "portfolio": "portfolio cá nhân",
                "ecommerce": "bán hàng online", "booking": "đặt lịch / đặt chỗ", "edtech": "khoá học / giáo dục",
                "other": "chưa rõ (bạn đổi được ở B7)"}


def _px(v: float) -> str:
    return f"{v:g}px"


def _alpha(hex_: str | None) -> str:
    if not hex_:
        return "trong suốt"
    if len(hex_) == 9:
        return f"{hex_[:7]} ({round(int(hex_[7:], 16) / 255 * 100)}%)"
    return hex_


def _piece(c) -> str:
    """One line for one piece: what it is, its size and look."""
    kind = KIND_LABEL.get(c.kind, c.kind)
    size = f"{c.w}×{c.h}px tại ({c.x}, {c.y})"
    if c.kind in ("heading", "text", "link"):
        lvl = f" h{c.level}" if c.level else ""
        extra = f", giãn chữ {c.ls:g}px" if abs(c.ls) > 0.05 else ""
        extra += ", chữ hoa" if c.tt else ""
        return (f"{kind}{lvl}: {_px(c.fs)} / đậm {c.fw:.0f} / dòng {c.lh or 'normal'}{extra}, màu {_alpha(c.color)}, "
                f"{c.chars} ký tự, {size}")
    if c.kind == "button":
        return (f"Nút: nền {_alpha(c.bg)}, chữ {_alpha(c.color)} {_px(c.fs)} đậm {c.fw:.0f}, bo góc {c.radius}px, "
                f"đệm {c.pad[0]}/{c.pad[1]}px, viền {c.border}px, {size}")
    if c.kind == "image":
        what = {"canvas": "Canvas / 3D", "video": "Video", "svg": "Hình vẽ SVG", "mockup": "Mockup giao diện (HTML)",
                "img": "Ảnh", "picture": "Ảnh"}.get(c.media, "Ảnh")
        return f"{what}: {size}, bo góc {c.radius}px"
    if c.kind == "card":
        return f"Thẻ: nền {_alpha(c.bg)}, bo góc {c.radius}px{', đổ bóng' if c.shadow else ''}{', viền' if c.border else ''}, {size}"
    if c.kind == "input":
        return f"Ô nhập: bo góc {c.radius}px, {size}"
    return f"{kind}: {size}"


def build(clone, domain: str, sections: list) -> str:
    """ANALYSIS.md for the Clone source (`clone` = CloneSource), its sections (Section dumps) and the guessed domain."""
    report = clone.motion_report or {}
    boxes = clone.boxes or {}
    every = [c for sid in boxes for c in comps(clone.components.get(sid, []))]
    heads = [c for c in every if c.kind == "heading"]
    texts = [c for c in every if c.kind == "text"]
    buttons = [c for c in every if c.kind == "button"]
    bgs = Counter(b.get("bg") for b in boxes.values() if b.get("bg"))
    page_bg = next((b.get("page") for b in boxes.values() if b.get("page")), None)
    fills = Counter(c.bg for c in buttons if c.bg)
    theme = clone.pillars.get("theme", "")
    centred = sum(1 for sid, b in boxes.items() for c in comps(clone.components.get(sid, []))
                  if c.kind == "heading" and abs((c.x + c.w / 2) - b.get("width", 1440) / 2) < 40)
    lines = [f"# Phân tích trang mẫu {clone.url}", "",
             "## 1. Tổng quan (bước chuẩn bị)", "",
             f"- **Mục đích trang:** {DOMAIN_WORDS.get(domain, domain)}",
             f"- **Concept:** {theme or '—'} · bố cục {clone.pillars.get('layout', '—')} · độ thoáng {clone.pillars.get('margins', '—')}"
             + (" · nền tối" if page_bg and _dark(page_bg) else " · nền sáng" if page_bg else ""),
             f"- **Layout chủ đạo:** {len(sections)} section; tiêu đề {'căn giữa' if heads and centred >= len(heads) / 2 else 'căn trái'}"
             + (f"; cột nội dung ~{clone.content_width}px" if clone.content_width else "; nội dung trải rộng toàn trang"),
             f"- **Chữ:** tiêu đề {clone.heading_font or '—'}, nội dung {clone.body_font or '—'}; cỡ tiêu đề "
             + ", ".join(f"{s:g}px" for s, _ in Counter(round(c.fs) for c in heads).most_common(4))
             + (f"; cỡ chữ thường {Counter(round(c.fs) for c in texts).most_common(1)[0][0]}px" if texts else ""),
             f"- **Màu:** nền trang {page_bg or '—'}; nền section "
             + ", ".join(f"{c} ({n})" for c, n in bgs.most_common(4))
             + (f"; nút chính {fills.most_common(1)[0][0]}" if fills else ""),
             f"- **Hiệu ứng:** " + (", ".join(dict.fromkeys(i.get("label", "") for i in report.get("items", []))) or "không có"),
             ]
    models = report.get("models", [])
    if models:
        lines.append(f"- **Mô hình 3D / canvas:** {len(models)} — " + "; ".join(f"{m['section']}: {m['how']}" for m in models))
    controls = report.get("controls", [])
    if controls:
        live = [c for c in controls if c.get("changes")]
        lines.append(f"- **Nút & link:** đã rê chuột thử {len(controls)}, {len(live)} có phản hồi khi rê chuột")
    lines += ["", "## 2. Từ trên xuống", ""]
    for n, sec in enumerate(sections, 1):
        sid = sec["id"]
        box = boxes.get(sid)
        lines.append(f"### {n}. {sec['name']} (`{sid}` · {sec['structure']})")
        if not box:
            lines += ["- Không đo được khung của phần này (thêm vào để trang có header).", ""]
            continue
        lines.append(f"- Khung {box.get('width')}×{box.get('height')}px · nền {box.get('bg') or 'trong suốt'}"
                     + (" · dải ngược màu so với trang" if box.get("band") else ""))
        if sec.get("motion"):
            lines.append("- Hiệu ứng: " + ", ".join(sec["motion"]))
        for m in [m for m in models if m["section"] == sid]:
            lines.append(f"- 3D: {m['how']}")
        pieces = sorted(comps(clone.components.get(sid, [])), key=lambda c: (c.y, c.x))
        for c in pieces[:40]:
            lines.append(f"  - {_piece(c)}")
        if len(pieces) > 40:
            lines.append(f"  - … và {len(pieces) - 40} thành phần nữa")
        mine = [c for c in controls if c.get("section") == sid]
        if mine:
            lines.append("- Rê chuột: " + "; ".join(
                f"{'nút' if c['kind'] == 'button' else 'link'} {c['w']}×{c['h']}px → {', '.join(c['changes']) or 'không đổi'}"
                + (f" ({c['duration_ms']}ms)" if c.get("duration_ms") else "") for c in mine[:12]))
        lines.append("")
    return "\n".join(lines)


def _dark(hex_: str) -> bool:
    try:
        r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return False
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.35
