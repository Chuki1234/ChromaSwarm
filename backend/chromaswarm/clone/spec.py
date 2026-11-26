"""Clone B2: CloneSpec — what the rebuild copies, replaces, skips or leaves to do, item by item.

Built once from the reading (structure read + effect check) and then *used*:

* B9 (developer/measured.py): each link / button gets the href its spec decides (an anchor to the rebuilt
  section for in-page links, a named placeholder for pages of the user's own site, "#" + a slot to fill for
  external links); backgrounds the reference paints itself (gradients, glows) are redrawn as decorative
  layers, with their intro animation when they had one;
* B2 → Motion MCP: effects marked `copy` are built with their measured parameters (an intro animation on
  load becomes the `reveal` effect at the measured duration / distance);
* planner.page_sections: sections marked `skip` are not built;
* B7: the user changes decisions (`overrides`, e.g. skip a section) — the brief and the plan follow;
* B11 1:1 acceptance: only built sections are compared.

CLONE_BRIEF.md section 8 is a rendering of this spec, so the build team reads exactly what the machine does.
Inputs are measurements only: geometry, computed style, timings, where controls lead — never words or URLs of
pictures (decision 11).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["copy", "replace", "skip", "todo"]
ACTION_LABEL = {"copy": "dựng giống", "replace": "thay bằng", "skip": "không dựng", "todo": "làm được, chưa tự động"}

# Effects the Motion MCP builds, and what a reference effect is built as.
BUILD_AS = {"scroll-reveal": "scroll-reveal", "stagger-cards": "stagger-cards", "parallax": "parallax", "marquee": "marquee",
            "hover-lift": "hover-lift", "hover-zoom": "hover-zoom", "hover-image": "hover-image",
            "underline-link": "underline-link", "sticky-blur": "sticky-blur", "smooth-scroll": "smooth-scroll",
            "load-in": "reveal"}
# Where a page of the reference leads, as a placeholder anchor on the user's site (they point it at their page).
ROLE_ANCHOR = {"đăng nhập / đăng ký": "#dang-ky", "bảng giá": "#bang-gia", "blog / bài viết": "#blog",
               "pháp lý": "#phap-ly", "tài liệu": "#tai-lieu"}


class SpecItem(BaseModel):
    id: str  # stable: "section:hero", "control:hero:3", "picture:7", "effect:hero:parallax", "background:hero:0"
    kind: Literal["section", "picture", "icon", "logo", "text", "testimonial", "control", "effect", "background",
                  "font", "function", "link-out"]
    section: str | None = None
    action: Action
    why: str
    replace_with: str = ""
    data: dict = Field(default_factory=dict)  # kind-specific measurements the consumers use


class CloneSpec(BaseModel):
    items: list[SpecItem] = Field(default_factory=list)
    goal: str | None = None  # where most controls lead (sign-in, pricing…)
    overrides: dict[str, Action] = Field(default_factory=dict)  # the user's decisions (B7), by item id

    def action(self, item: SpecItem) -> Action:
        return self.overrides.get(item.id, item.action)

    def of(self, kind: str, section: str | None = None) -> list[SpecItem]:
        return [i for i in self.items if i.kind == kind and (section is None or i.section == section)]

    def skipped_sections(self) -> set[str]:
        return {i.section for i in self.of("section") if i.section and self.action(i) == "skip"}

    def controls(self, section: str) -> list[dict]:
        """The section's controls with the href the rebuild uses (section-relative boxes)."""
        return [{**i.data, "href": i.data.get("href", "#")} for i in self.of("control", section) if self.action(i) != "skip"]

    def layers(self, section: str) -> list[dict]:
        return [i.data for i in self.of("background", section) if self.action(i) == "copy"]

    def effects(self, section: str) -> dict[str, dict]:
        """Motion MCP effect id -> measured params, for effects to build in this section."""
        out: dict[str, dict] = {}
        for i in self.of("effect", section):
            if self.action(i) == "copy" and i.data.get("build"):
                out.setdefault(i.data["build"], i.data.get("params") or {})
        return out


def _in(box: dict, top: float, h: float = 0) -> bool:
    mid = top + h / 2
    return box.get("top", 0) <= mid <= box.get("top", 0) + max(box.get("height", 0), 1)


def _section_at(boxes: dict[str, dict], top: float, h: float = 0) -> str | None:
    return next((k for k, b in boxes.items() if _in(b, top, h)), None)


def _anchor_for(fragment: str, section_ids: list[str]) -> str:
    """An in-page link of the reference (#faq, #pricing) → the rebuilt section it most likely points at."""
    f = fragment.lstrip("#").lower()
    if not f:
        return "#"
    hit = next((s for s in section_ids if s == f or s.startswith(f) or f in s), None)
    return f"#{hit}" if hit else "#"


def _distance(frames: str) -> int:
    m = re.search(r"translateY\((-?\d+(?:\.\d+)?)px\)", frames or "")
    return min(120, abs(round(float(m.group(1))))) if m else 24


def build_spec(clone) -> CloneSpec:
    """Every decision for the rebuild, from what B2 read (`clone`: CloneSource)."""
    boxes = clone.boxes or {}
    report = clone.motion_report or {}
    section_ids = [s["id"] for s in clone.sections]
    items: list[SpecItem] = []

    # Sections: all built by default (the user may skip one at B7).
    for s in clone.sections:
        items.append(SpecItem(id=f"section:{s['id']}", kind="section", section=s["id"], action="copy",
                              why=f"{s['name']} — bố cục, khoảng cách, chữ và màu đo được",
                              data={"name": s["name"], "structure": s["structure"]}))

    # Words, testimonials, brand.
    items.append(SpecItem(id="text:all", kind="text", action="copy", why="giữ nội dung chữ của trang mẫu"))

    # Pictures, icons, logos.
    for n, m in enumerate(clone.media or []):
        sid = _section_at(boxes, m["top"], m["h"])
        if m.get("icon"):
            kind, why = "icon", "giữ icon của trang mẫu"
        elif m.get("logo"):
            kind, why = "logo", "giữ logo / thương hiệu của trang mẫu"
        else:
            kind, why = "picture", "giữ hình ảnh của trang mẫu"
        items.append(SpecItem(id=f"{kind}:{n}", kind=kind, section=sid, action="copy", why=why,
                              data={k: m.get(k) for k in ("kind", "top", "left", "w", "h", "nw", "nh", "file")}))

    # Controls: where each one leads in the rebuild.
    goal_count: dict[str, int] = {}
    for n, c in enumerate(report.get("controls") or []):
        top, h = c.get("top", 0), c.get("h", 0)
        sid = c.get("section") if c.get("section") in boxes else _section_at(boxes, top, h)
        act = c.get("action") or {}
        kind = act.get("kind", "")
        box = boxes.get(sid or "", {})
        data = {"x": c.get("left", 0), "y": top - box.get("top", 0), "w": c.get("w", 0), "h": h, "kind": c.get("kind"),
                "dest": act, "href": "#"}
        action: Action = "copy"
        why, repl = "nút / link với hiệu ứng rê chuột đo được", ""
        if kind == "same-page":
            data["href"] = _anchor_for(act.get("target", ""), section_ids)
            why = "link trong trang → phần tương ứng của bản dựng"
        elif kind == "internal":
            role = act.get("role") or ""
            if role:
                goal_count[role] = goal_count.get(role, 0) + 1
            data["href"] = ROLE_ANCHOR.get(role, "#")
            action = "replace"
            why = f"dẫn tới {act.get('target')}" + (f" ({role})" if role else "") + " trên site gốc"
            repl = f"trang {role or 'tương ứng'} của bạn (đặt link trong content/)"
            if act.get("broken"):
                action, why, repl = "skip", f"link hỏng trên site gốc ({act['broken']})", "không chép hành vi; nút giữ dáng, link '#'"
        elif kind == "external":
            action, why, repl = "replace", f"mở trang ngoài {act.get('target')}", "link của bạn (để trống trong content/)"
        elif kind == "none":
            action, why, repl = "skip", "bấm trên site gốc không có phản hồi", "giữ dáng nút, không có hành vi"
        elif kind in ("toggle", "dialog", "content"):
            built = sid and next((s for s in clone.sections if s["id"] == sid and s["structure"] == "accordion"), None)
            action = "copy" if (kind == "toggle" and built) else "todo"
            why = {"toggle": "mở / đóng một khối", "dialog": "mở menu / hộp thoại", "content": "đổi nội dung trên trang"}[kind]
            repl = "" if action == "copy" else "bản dựng giữ nút, hành vi này chưa tự dựng"
        elif kind == "form-submit":
            action, why, repl = "replace", "gửi form trên site gốc", "form của bạn (chưa nối hệ thống)"
        items.append(SpecItem(id=f"control:{sid}:{n}", kind="control", section=sid, action=action, why=why,
                              replace_with=repl, data=data))
    goal = max(goal_count, key=lambda k: goal_count[k]) if goal_count else None
    if goal in ("đăng nhập / đăng ký", "bảng giá"):
        items.append(SpecItem(id="function:backend", kind="function", action="replace",
                              why=f"chức năng phía sau ({goal}, lưu dữ liệu…)", replace_with="Chroma dựng giao diện; nút trỏ tới chỗ trống"))
    hosts = sorted({str((c.get("action") or {}).get("target")) for c in report.get("controls") or []
                    if (c.get("action") or {}).get("kind") == "external"})
    if hosts:
        items.append(SpecItem(id="link-out:all", kind="link-out", action="replace", why=f"{len(hosts)} trang ngoài: {', '.join(hosts[:6])}",
                              replace_with="link mạng xã hội / trang của bạn"))

    # Backgrounds the page paints itself: redrawn as decorative layers (big ones); giant faint type is the brand.
    intro = report.get("intro") or []
    for n, b in enumerate(clone.backgrounds or []):
        sid = _section_at(boxes, b["top"], b["h"])
        box = boxes.get(sid or "", {})
        if b["kind"] == "faint-type":
            items.append(SpecItem(id=f"background:{sid}:{n}", kind="background", section=sid, action="copy",
                                  why=f"chữ khổng lồ mờ {b.get('font_px')}px (tên thương hiệu)", replace_with="tên của bạn nếu muốn"))
            continue
        big = b["w"] >= 160 and b["h"] >= 120
        layer = {"x": b["left"], "y": b["top"] - box.get("top", 0), "w": b["w"], "h": b["h"], "css": b.get("css", ""),
                 "blur": b.get("blur", ""), "glass": b.get("glass", ""), "tf": b.get("tf", ""), "opacity": b.get("opacity", 1),
                 "kind": b["kind"]}
        # Its intro animation: same size (its place moves while it plays, e.g. sliding in from 540px below).
        twin = next((a for a in intro if abs(a["w"] - b["w"]) <= 4 and abs(a["h"] - b["h"]) <= 4), None)
        if twin:
            layer["intro"] = {k: twin[k] for k in ("from", "to", "dur", "delay", "easing")}
        if not big or b["kind"] == "glass" or not b.get("css"):
            continue  # small gradients sit inside components (avatars, badges); glass is the header's sticky-blur effect
        items.append(SpecItem(id=f"background:{sid}:{n}", kind="background", section=sid, action="copy",
                              why=f"nền vẽ bằng CSS ({'quầng sáng' if b['kind'] == 'glow' else 'gradient'} {b['w']}×{b['h']})"
                              + (" + hiệu ứng khi tải" if twin else ""), data=layer))

    # Effects.
    # Intro animations a background layer plays itself (same size); the rest may become a section `reveal`.
    sizes = {(round(b["w"]), round(b["h"])) for b in clone.backgrounds or []}
    unplayed = [a for a in intro if not any(abs(a["w"] - w) <= 4 and abs(a["h"] - h) <= 4 for w, h in sizes)]
    for it in report.get("items") or []:
        sid, eff = it.get("section"), it.get("effect")
        params = dict(it.get("params") or {})
        if eff == "marquee-vertical":
            items.append(SpecItem(id=f"effect:{sid}:{eff}", kind="effect", section=sid, action="copy", why=it["how"],
                                  data={"renderer": "section-template", "params": params, "label": it.get("label")}))
            continue
        build = BUILD_AS.get(eff)
        if eff == "load-in":
            first = next((a for a in unplayed if _section_at(boxes, a["top"], a["h"]) == sid), None)
            if first is None:
                continue  # played by the background layers themselves
            params = {"duration_ms": params.get("duration_ms"), "distance_px": _distance(first.get("from", "")),
                      "easing": first.get("easing") if first.get("easing") in ("linear", "ease", "ease-out", "ease-in-out") else ""}
        if eff == "canvas-3d":
            items.append(SpecItem(id=f"effect:{sid}:{eff}", kind="effect", section=sid, action="replace", why=it["how"],
                                  replace_with="khung giữ chỗ đúng kích thước (CSS không vẽ lại được 3D)"))
            continue
        action: Action = "copy" if build else ("skip" if eff == "loop" else "todo")
        items.append(SpecItem(id=f"effect:{sid}:{eff}", kind="effect", section=sid, action=action, why=it["how"],
                              replace_with="" if build else ("chuyển động trang trí nhỏ" if eff == "loop" else "Motion MCP chưa dựng được loại này"),
                              data={"build": build, "params": {k: v for k, v in params.items() if v not in (None, "", 0)}, "label": it.get("label")}))

    # Fonts that cannot come across as they are.
    for note in clone.notes:
        if "font" in note.lower():
            items.append(SpecItem(id=f"font:{len(items)}", kind="font", action="replace", why=note, replace_with="font gần nhất"))
    return CloneSpec(items=items, goal=goal)


def apply_overrides(spec: CloneSpec, overrides: dict[str, str]) -> list[str]:
    """The user's decisions (B7): item id -> action. Returns what changed, in words."""
    changed = []
    ids = {i.id: i for i in spec.items}
    for key, value in overrides.items():
        if key in ids and value in ACTION_LABEL and spec.action(ids[key]) != value:
            spec.overrides[key] = value  # type: ignore[assignment]
            name = ids[key].data.get("name") or ids[key].why
            changed.append(f"{name}: {ACTION_LABEL[value]}")
    return changed


def render(spec: CloneSpec) -> list[str]:
    """CLONE_BRIEF.md section 8: the spec grouped by decision."""
    groups: dict[str, list[SpecItem]] = {a: [] for a in ACTION_LABEL}
    for i in spec.items:
        groups[spec.action(i)].append(i)
    kinds = {"section": "Section", "picture": "Hình", "icon": "Icon", "logo": "Logo", "text": "Chữ", "testimonial": "Lời khách",
             "control": "Nút / link", "effect": "Hiệu ứng", "background": "Nền vẽ", "font": "Font", "function": "Chức năng",
             "link-out": "Link ngoài"}
    out = []
    titles = {"copy": "### ✅ Dựng giống (copy)", "replace": "### 🔁 Thay bằng (replace)", "skip": "### ⛔ Không dựng (skip)",
              "todo": "### 🕓 Làm được, chưa tự động (todo)"}
    for action, rows in groups.items():
        if not rows:
            continue
        out += [titles[action], "", "| Mục | Loại | Section | Vì sao | Thay bằng |", "|---|---|---|---|---|"]
        # Many identical rows (21 pictures, 30 links) read better grouped by kind + replacement.
        seen: dict[tuple, list[SpecItem]] = {}
        for i in rows:
            key = (i.kind, i.replace_with) if i.kind in ("picture", "icon", "logo") else (i.id,)
            seen.setdefault(key, []).append(i)
        for group in seen.values():
            i = group[0]
            label = f"{len(group)} {kinds[i.kind].lower()}" if len(group) > 1 else (i.data.get("name") or i.data.get("label") or i.id)
            secs = ", ".join(dict.fromkeys(g.section for g in group if g.section)) or "—"
            out.append(f"| {label} | {kinds[i.kind]} | {secs} | {i.why} | {i.replace_with or '—'} |")
        out.append("")
    out.append(f"*{len(spec.items)} quyết định; bạn đổi được ở B7 (vd. bỏ một section).*" + (f" Đã đổi: {len(spec.overrides)}." if spec.overrides else ""))
    return out
