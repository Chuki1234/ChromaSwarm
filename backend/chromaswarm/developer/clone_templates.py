"""Clone: each section rebuilt as a real, well-made component — numbers from the reference's DESIGN.md.

The measured renderer (developer/measured.py) places every box at its measured spot; it reproduces positions
but not intent (a language switch becomes a plain button, a FAQ a column of links). Here a section is first
understood, then built:

1. Model (`build_model`): from the section's spec in design.json — its components with place, size and tokens —
   the roles are read: eyebrow label, heading, sub-text, actions, pictures, cards (with their own label / heading
   / text / picture), rows that open (accordion), link columns (footer), logo / brand / subtitle (navbar).
   Words and pictures: the user's own site → the reader's `texts` / `pics` matched by place to each component;
   otherwise sample copy by role, cut to the length the reference showed (never the reference's words).
2. Template by kind: announcement bar (dismissible, stays closed), navbar (logo, brand, subtitle, language
   switch, primary action), hero (text column + picture or vertical marquee columns), feature accordion (rows
   that open + picture), cards grid (steps / features / posts), testimonials (single quote, or a wall of quote
   cards in marquee columns), FAQ (heading column + rows that open), footer (brand, link columns, bottom line).
3. Style: every number is the reference's — section background, padding, content width, each text style
   (size / weight / leading / tracking / case) and ink, button fill / ink / radius / padding / height, card
   radius / fill / shadow / border, picture radius and aspect, marquee cycle. Colours that would not read are
   moved in lightness only (same hue). Accessibility stays: real controls, focus rings, 48px targets on phones,
   reduced-motion safe.

`render(section, copy)` returns the component's code, or None when the section is not one of these kinds (the
measured renderer / the structure's template then builds it).
"""

from __future__ import annotations

import json
import re

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import PageCopy

HERO = ("split-7-5", "full-bleed-image", "hero-text")


# ------------------------------------------------------------------ model

def _center_in(t: dict, x0: float, y0: float, w: float, h: float, pad: float = 4) -> bool:
    cx, cy = t["x"] + t["w"] / 2, t["y"] + t["h"] / 2
    return x0 - pad <= cx <= x0 + w + pad and y0 - pad <= cy <= y0 + h + pad


def _inside(r: dict, c: dict) -> bool:
    cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
    return c["x"] <= cx <= c["x"] + c["w"] and c["y"] <= cy <= c["y"] + c["h"]


class Model:
    """The section's roles, each a component row of design.json (+ its words / picture)."""

    def __init__(self, section: Section, copy: PageCopy):
        from chromaswarm.developer.measured import _Words
        d = section.design
        self.spec = d["section"]
        self.type, self.colors, self.variants = d.get("type", {}), d.get("colors", {}), d.get("components", {})
        self.box = self.spec["box"]
        self.width = float(self.box.get("width") or 1440)
        self.height = float(self.box.get("height") or 0)
        self.owned = section.owned or {}
        self.words = _Words(copy, section.structure, section.id)
        rows = [dict(r) for r in self.spec.get("components", [])]
        area = self.width * max(self.height, 1)
        self.background = [r for r in rows if r["kind"] in ("image", "card") and r["w"] * r["h"] >= 0.5 * area]
        rows = [r for r in rows if r not in self.background]
        frames = [r for r in rows if r.get("frame")]
        # A frame around the section's main content (it holds the biggest heading, or a large share of the
        # section) is a wrapper, not an item card: its pieces are the section's own.
        biggest = max((r for r in rows if r["kind"] == "heading"), key=lambda r: self.size(r), default=None)
        wrappers = [r for r in rows if r["kind"] == "card" and not r.get("frame")
                    and ((biggest is not None and _inside(biggest, r)) or r["w"] * r["h"] >= 0.4 * area)]
        rows = [r for r in rows if r not in wrappers]
        self.cards = [r for r in rows if r["kind"] == "card" and not r.get("frame")]
        for c in self.cards:
            c["members"] = sorted([r for r in rows if r is not c and r["kind"] != "card" and _inside(r, c)],
                                  key=lambda r: (r["y"], r["x"]))
        in_card = {id(m) for c in self.cards for m in c["members"]}
        self.loose = sorted([r for r in rows if r["kind"] != "card" and id(r) not in in_card], key=lambda r: (r["y"], r["x"]))
        self.loose += [f for f in frames if id(f) not in in_card]
        heads = [r for r in self.loose if r["kind"] == "heading"]
        self.heading = max(heads, key=lambda r: (self.size(r), -r["y"]), default=None)
        hy = self.heading["y"] if self.heading else 0

        def aligned(r: dict) -> bool:  # same left edge as the heading, or both centred on the same line
            h = self.heading
            if not h:
                return False
            cr, ch = r["x"] + r["w"] / 2, h["x"] + h["w"] / 2
            return abs(r["x"] - h["x"]) < 48 or abs(cr - ch) < 48
        smalls = [r for r in self.loose if r["kind"] == "text" and r["y"] < hy and hy - (r["y"] + r["h"]) < 96
                  and aligned(r) and (self.size(r) <= 15 or self.case(r) == "uppercase")]
        self.eyebrow = smalls[-1] if smalls else None
        self.subs = [r for r in self.loose if r["kind"] == "text" and r["y"] > hy and (r.get("chars") or 0) >= 20
                     and r is not self.eyebrow and aligned(r) and r["y"] - hy < 320][:2] if self.heading else []
        self.actions = sorted([r for r in self.loose if r["kind"] == "button" and r["y"] >= hy - 8], key=lambda r: (r["y"] // 24, r["x"]))
        self.pictures = [r for r in self.loose if r["kind"] in ("image", "card")]
        self.links = [r for r in self.loose if r["kind"] == "link"]
        self.toggles = [r for r in rows if r.get("click") == "toggle"] or [c for c in self.cards if not any(m["kind"] == "image" for m in c["members"])]

    # tokens
    def size(self, r: dict | None) -> float:
        return float(self.type.get((r or {}).get("type") or "", {}).get("size", 16))

    def case(self, r: dict) -> str:
        return self.type.get(r.get("type") or "", {}).get("case", "")

    def color(self, name: str | None) -> str | None:
        return (self.colors.get(name or "") or {}).get("value")

    @property
    def bg(self) -> str:
        return self.color(self.box.get("bg")) or "#ffffff"

    @property
    def content_width(self) -> float:
        m = self.spec.get("margins") or {}
        if m.get("left") is not None and m.get("right") is not None:
            return max(320.0, self.width - m["left"] - m["right"])
        return min(self.width, 1200.0)

    @property
    def centered(self) -> bool:
        h = self.heading
        return bool(h and abs((h["x"] + h.get("tx", 0) + (h.get("tw") or h["w"]) / 2) - self.width / 2) < self.width * 0.04)

    # words / pictures
    def text(self, r: dict | None, role: str = "short") -> str:
        if r is None:
            return ""
        x0 = (self.box.get("left") or 0) + r["x"]
        y0 = (self.box.get("top") or 0) + r["y"]
        found = [t for t in self.owned.get("texts", []) if _center_in(t, x0, y0, r["w"], r["h"], 0)]
        if found and r["kind"] == "heading":  # a moving quote / name passing under a heading is not part of it
            size = self.size(r)
            found = [t for t in found if not t.get("fs") or float(t["fs"]) >= 0.75 * size] or found
        if found:
            found.sort(key=lambda t: (t["y"], t["x"]))
            return " ".join(dict.fromkeys(t["t"] for t in found))[:400]
        if r["kind"] == "button" and role != "short":
            return self.words.take("cta", r.get("chars") or 12)
        return self.words.take(role, max(2, r.get("chars") or 12))

    def texts_in(self, r: dict) -> list[str]:
        x0, y0 = (self.box.get("left") or 0) + r["x"], (self.box.get("top") or 0) + r["y"]
        found = sorted([t for t in self.owned.get("texts", []) if _center_in(t, x0, y0, r["w"], r["h"], 0)], key=lambda t: (t["y"], t["x"]))
        return list(dict.fromkeys(t["t"] for t in found))

    def picture(self, r: dict) -> str | None:
        x0, y0 = (self.box.get("left") or 0) + r["x"], (self.box.get("top") or 0) + r["y"]
        return next((p["src"] for p in self.owned.get("pics", []) if _center_in(p, x0, y0, r["w"], r["h"], 8)), None)


# ------------------------------------------------------------------ style

class Style:
    """Scoped CSS for one section: classes per text token / button variant / card, from the measured values."""

    def __init__(self, m: Model, sid: str):
        self.m, self.sel = m, f'[data-swarm-section="{sid}"]'
        self.rules: list[str] = []
        self.done: set[str] = set()

    def add(self, rule: str) -> None:
        self.rules.append(rule)

    def ink(self, name: str | None, large: bool, on: str | None = None) -> str | None:
        from chromaswarm.developer.measured import readable_variant
        c = self.m.color(name)
        return readable_variant(c, on or self.m.bg, large) if c else None

    def tok(self, r: dict | None, on: str | None = None) -> str:
        """Class for a text row's token (+ its ink on what is beneath)."""
        if not r:
            return ""
        name = r.get("type") or "body"
        t = self.m.type.get(name, {"size": 16, "weight": 400, "leading": 1.5, "tracking": 0, "case": ""})
        ink = self.ink(r.get("ink"), t["size"] >= 24, on)
        key = f"tk-{re.sub(r'[^a-z0-9-]', '', name)}-{(ink or '')[1:]}"
        if key not in self.done:
            self.done.add(key)
            size = t["size"]
            props = [f"font-size: {size}px", f"font-weight: {t['weight']}", f"line-height: {t.get('leading') or 1.3}",
                     f"letter-spacing: {t.get('tracking') or 0}px", f"text-transform: {t.get('case') or 'none'}", "margin: 0"]
            if ink:
                props.append(f"color: {ink}")
            self.add(f"{self.sel} .{key} {{ {'; '.join(props)}; }}")
            if size > 28:  # phones: the display sizes step down on the reference's own scale
                self.add(f"@media (max-width: 767px) {{ {self.sel} .{key} {{ font-size: {round(max(28, size * 0.62))}px; }} }}")
        return key

    def btn(self, r: dict) -> str:
        v = self.m.variants.get(r.get("variant") or "", {})
        from chromaswarm.developer.measured import readable_variant
        fill = self.m.color(v.get("fill"))
        label = self.m.color(r.get("ink")) or ("#ffffff" if fill else None)
        if fill and label:
            fill = readable_variant(fill, label, False) or fill
        elif label:
            label = readable_variant(label, self.m.bg, False) or label
        key = f"bv-{abs(hash((r.get('variant'), fill, label))) % 10**6}"
        if key not in self.done:
            self.done.add(key)
            pad = v.get("padding") or [10, 24]
            radius = v.get("radius", 8)
            props = [f"min-height: {max(40, round(v.get('h') or r['h']))}px", f"padding: {pad[0]}px {pad[1]}px",
                     f"border-radius: {radius}px", "display: inline-flex", "align-items: center", "justify-content: center",
                     "gap: 8px", "white-space: nowrap", "text-decoration: none", "font-weight: 600",
                     "transition: filter var(--duration) var(--ease), transform var(--duration) var(--ease)"]
            props.append(f"background: {fill}" if fill else "background: transparent")
            if label:
                props.append(f"color: {label}")
            if not fill:
                props.append(f"border: 1px solid color-mix(in oklch, {label or 'currentColor'} 30%, transparent)")
            t = self.m.type.get(r.get("type") or "", {})
            if t:
                props += [f"font-size: {t['size']}px", f"font-weight: {t['weight']}"]
            self.add(f"{self.sel} .{key} {{ {'; '.join(props)}; }}")
            self.add(f"{self.sel} .{key}:hover {{ filter: brightness(0.94); transform: translateY(-1px); }}")
            self.add(f"{self.sel} .{key}:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}")
            self.add(f"@media (max-width: 767px) {{ {self.sel} .{key} {{ min-height: 48px; }} }}")
        return key

    def card(self, c: dict) -> str:
        v = self.m.variants.get(c.get("variant") or "", {})
        fill = self.m.color(v.get("fill"))
        key = f"cv-{abs(hash((c.get('variant'), fill))) % 10**6}"
        if key not in self.done:
            self.done.add(key)
            props = [f"border-radius: {v.get('radius', c.get('radius', 12))}px", "overflow: hidden", "display: flex",
                     "flex-direction: column", f"background: {fill or 'transparent'}"]
            props.append("box-shadow: var(--shadow-md)" if v.get("shadow") else "box-shadow: none")
            props.append("border: 1px solid var(--border-subtle)" if v.get("border") or (not fill and not v.get("shadow")) else "border: 0")
            self.add(f"{self.sel} .{key} {{ {'; '.join(props)}; }}")
        return key

    def section(self, extra: str = "") -> str:
        m = self.m
        pad = m.spec.get("padding") or {}
        top, bottom = pad.get("top"), pad.get("bottom")
        top = 48 if top is None else top
        bottom = 48 if bottom is None else bottom
        base = (f"{self.sel}.s {{ position: relative; overflow-x: clip; background: {m.bg}; padding-top: {max(0, round(top))}px; padding-bottom: {max(0, round(bottom))}px; }}\n"
                f"{self.sel} > .container {{ max-width: {round(m.content_width)}px; padding-inline: 24px; box-sizing: content-box; }}\n"
                f"@media (max-width: 767px) {{ {self.sel}.s {{ padding-top: {min(64, max(24, round(top * 0.6)))}px; "
                f"padding-bottom: {min(64, max(24, round(bottom * 0.6)))}px; }} }}\n")
        return base + extra + "\n".join(self.rules)


# ------------------------------------------------------------------ JSX helpers

def _t(js, value: str, name: str) -> str:
    return "{" + js(value, name) + "}"


def _img(js, src: str | None, r: dict, eager: bool = False) -> str:
    w, h = max(1, round(r["w"])), max(1, round(r["h"]))
    if src:
        return (f'<img className="cl-img" src={{{js(src, "image")}}} alt="" width={{{w}}} height={{{h}}} '
                f'loading="{"eager" if eager else "lazy"}" style={{{{ aspectRatio: "{w} / {h}" }}}} />')
    return f'<div className="cl-skel" aria-hidden="true" style={{{{ aspectRatio: "{w} / {h}" }}}} />'


ARROW = ('<svg className="cl-ico" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">'
         '<path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>')


def _has_icon(m: Model, r: dict, label: str) -> bool:
    """The reference button is clearly wider than its words + padding: it held an icon (arrow / chevron)."""
    v = m.variants.get(r.get("variant") or "", {})
    pad = (v.get("padding") or [10, 24])[1]
    t = m.type.get(r.get("type") or "", {})
    need = len(label) * float(t.get("size") or 16) * 0.56 + 2 * pad
    return r["w"] - need >= 14


def _button(m: Model, st: Style, js, r: dict, sid: str, href: str = "#", role: str = "cta") -> str:
    label = m.text(r, role)
    icon = ARROW if _has_icon(m, r, label) else ""
    return (f'<a href="{href}" className="btn {st.btn(r)}" data-swarm-id="{sid}" data-swarm-role="button">'
            f'{_t(js, label, "button")}{icon}</a>')


def _actions(m: Model, st: Style, js, sid: str, rows: list[dict]) -> str:
    out = []
    for n, r in enumerate(rows[:3]):
        out.append(_button(m, st, js, r, f"{sid}-btn-{n}"))
    return f'<div className="cl-actions">{"".join(out)}</div>' if out else ""


def _header(m: Model, st: Style, js, sid: str, with_actions: bool = True, on: str | None = None) -> str:
    parts = []
    if m.eyebrow:
        parts.append(f'<p className="{st.tok(m.eyebrow, on)}">{_t(js, m.text(m.eyebrow), "eyebrow")}</p>')
    if m.heading:
        level = 1 if sid.startswith("hero") else 2
        parts.append(f'<h{level} className="{st.tok(m.heading, on)}">{_t(js, m.text(m.heading, "head"), "heading")}</h{level}>')
    for r in m.subs:
        parts.append(f'<p className="{st.tok(r, on)}">{_t(js, m.text(r, "body"), "text")}</p>')
    if with_actions and m.actions:
        parts.append(_actions(m, st, js, sid, m.actions))
    return f'<div className="cl-head{" is-center" if m.centered else ""}">{"".join(parts)}</div>'


COMMON = """{sel} .cl-head {{ display: flex; flex-direction: column; gap: 16px; max-width: 720px; }}
{sel} .cl-head.is-center {{ margin-inline: auto; text-align: center; align-items: center; }}
{sel} .cl-actions {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }}
{sel} .cl-ico {{ flex: none; transition: transform var(--duration) var(--ease); }}
{sel} .btn:hover .cl-ico {{ transform: translateX(2px); }}
{sel} .cl-img {{ display: block; width: 100%; height: auto; object-fit: cover; border-radius: inherit; }}
{sel} .cl-skel {{ width: 100%; border-radius: inherit; background: color-mix(in oklch, currentColor 9%, transparent); }}
{sel} a:focus-visible, {sel} button:focus-visible, {sel} summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}"""


# ------------------------------------------------------------------ templates

def _announcement(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    row = next((r for r in m.loose if r["kind"] in ("text", "link")), None)
    words = m.text(row) if row else m.words.take("short", 40)
    bg = m.bg
    jsx = f'''<div data-swarm-section="{s.id}" role="region" aria-label="Thông báo">{{open && (
      <div className="cl-announce">
      <p className="{st.tok(row) if row else "t-caption"}">{_t(js, words, "text")}</p>
      <button type="button" className="cl-announce-close" aria-label="Đóng thông báo" data-swarm-id="announcement-close"
        data-swarm-role="button" onClick={{close}}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      </button>
      </div>)}}
    </div>'''
    from chromaswarm.developer.measured import readable_variant
    ink = readable_variant("#ffffff", bg, False) or "#ffffff"
    css = (f'{st.sel} {{ position: sticky; top: 0; z-index: 41; }}\n'
           f':root {{ --cs-announce-h: {max(32, round(m.height))}px; }}\n'
           f'{st.sel} .cl-announce {{ position: relative; display: flex; align-items: center; justify-content: center; gap: 16px; '
           f'min-height: {max(32, round(m.height))}px; padding: 4px 56px; background: {bg}; color: {ink}; text-align: center; }}\n'
           f'{st.sel} .cl-announce-close {{ position: absolute; right: 16px; top: 50%; transform: translateY(-50%); display: grid; '
           f'place-items: center; width: 32px; height: 32px; border: 0; border-radius: 8px; background: transparent; color: inherit; cursor: pointer; }}\n'
           f'{st.sel} .cl-announce-close:hover {{ background: color-mix(in oklch, currentColor 14%, transparent); }}\n'
           f'@media (max-width: 767px) {{ {st.sel} .cl-announce-close {{ width: 48px; height: 48px; right: 4px; }} }}\n'
           + "\n".join(st.rules))
    body = ('  const [open, setOpen] = useState(true);\n'
            '  useEffect(() => { try { if (localStorage.getItem("cs-announce-closed") === "1") setOpen(false); } catch {} }, []);\n'
            '  const close = () => { setOpen(false); try { localStorage.setItem("cs-announce-closed", "1"); } catch {} };\n'
            '  useEffect(() => { document.documentElement.style.setProperty("--cs-announce-h", open ? "%dpx" : "0px"); }, [open]);\n' % max(32, round(m.height)))
    return jsx, css, body


def _nav(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    logo = next((r for r in m.loose if r["kind"] == "image" and r["w"] <= 120), None)
    texts = [r for r in m.loose if r["kind"] in ("text", "heading") and r["x"] < m.width / 2]
    brand = max(texts, key=lambda r: m.size(r), default=None)
    subtitle = next((r for r in texts if r is not brand and brand and r["y"] > brand["y"]), None)
    right = sorted([r for r in m.loose if r["kind"] in ("button", "link") and r["x"] > m.width / 2], key=lambda r: r["x"])
    switch = next((r for r in right if r.get("click") in ("dialog", "toggle", "content")), None)
    ctas = [r for r in right if r is not switch]
    parts = ['<a href="#" className="cl-brand" data-swarm-id="nav-logo" data-swarm-role="link">']
    if logo:
        parts.append(_img(js, m.picture(logo), logo, eager=True).replace('className="cl-img"', 'className="cl-logo"').replace('className="cl-skel"', 'className="cl-logo cl-skel"'))
    parts.append('<span className="cl-brand-text">')
    if brand:
        parts.append(f'<span className="{st.tok(brand)}">{_t(js, m.text(brand), "brand")}</span>')
    if subtitle:
        parts.append(f'<span className="{st.tok(subtitle)}">{_t(js, m.text(subtitle), "text")}</span>')
    parts.append("</span></a>")
    tools = []
    body = ""
    if switch:
        current = (m.text(switch) or "EN").strip()[:6] or "EN"
        tools.append(
            f'<div className="cl-lang"><button type="button" className="btn {st.btn(switch)}" aria-haspopup="listbox" aria-expanded={{lang}} '
            f'aria-label="Ngôn ngữ" data-swarm-id="nav-language" data-swarm-role="button" onClick={{() => setLang(!lang)}}>'
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />'
            '<path d="M3 12h18M12 3c2.5 2.6 3.6 5.6 3.6 9s-1.1 6.4-3.6 9c-2.5-2.6-3.6-5.6-3.6-9S9.5 5.6 12 3Z" stroke="currentColor" strokeWidth="1.6" /></svg>'
            f'<span>{_t(js, current, "label")}</span>'
            '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3 4.5 3 3 3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>'
            '</button>{lang && (<ul className="cl-lang-menu" role="listbox" aria-label="Ngôn ngữ">'
            '<li role="option" aria-selected="true"><button type="button" onClick={() => setLang(false)} data-swarm-id="nav-language-en" data-swarm-role="button">English</button></li>'
            '<li role="option" aria-selected="false"><button type="button" onClick={() => setLang(false)} data-swarm-id="nav-language-vi" data-swarm-role="button">Tiếng Việt</button></li>'
            '</ul>)}</div>')
        body = "  const [lang, setLang] = useState(false);\n"
    for n, r in enumerate(ctas[:2]):
        tools.append(_button(m, st, js, r, f"nav-cta-{n}", href="#dang-ky"))
    jsx = f'''<header data-swarm-section="{s.id}" className="s cl-nav">
      <div className="container cl-nav-row">{"".join(parts)}<div className="cl-nav-tools">{"".join(tools)}</div></div>
    </header>'''
    top = m.box.get("top") or 0
    css = st.section(f'''{st.sel}.cl-nav {{ position: sticky; top: var(--cs-announce-h, 0px); z-index: 40; padding-top: 0; padding-bottom: 0;
  backdrop-filter: blur(16px); background: color-mix(in oklch, {m.bg} 88%, transparent); }}
{st.sel} .cl-nav-row {{ display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: {max(56, round(m.height))}px; }}
{st.sel} .cl-brand {{ display: inline-flex; align-items: center; gap: 12px; text-decoration: none; color: inherit; min-height: 48px; min-width: 48px; }}
{st.sel} .cl-brand-text {{ display: flex; flex-direction: column; }}
{st.sel} .cl-logo {{ width: {round(logo["w"]) if logo else 32}px; height: {round(logo["h"]) if logo else 32}px; border-radius: 8px; object-fit: contain; }}
{st.sel} .cl-nav-tools {{ display: flex; align-items: center; gap: 12px; }}
{st.sel} .cl-lang {{ position: relative; }}
{st.sel} .cl-lang > .btn {{ gap: 8px; cursor: pointer; }}
{st.sel} .cl-lang-menu {{ position: absolute; right: 0; top: calc(100% + 8px); min-width: 160px; margin: 0; padding: 6px; list-style: none;
  border-radius: 12px; background: #ffffff; color: #111827; box-shadow: var(--shadow-lg); z-index: 50; }}
{st.sel} .cl-lang-menu button {{ width: 100%; min-height: 48px; padding: 8px 12px; border: 0; border-radius: 8px; background: #ffffff; color: #111827;
  font: inherit; text-align: left; cursor: pointer; }}
{st.sel} .cl-lang-menu button:hover {{ background: #f1f3f5; }}
{st.sel} .cl-ico {{ flex: none; }}
@media (max-width: 639px) {{ {st.sel} .cl-brand-text > :not(:first-child), {st.sel} .cl-lang > .btn > span {{ display: none; }}
  {st.sel} .cl-nav-tools {{ gap: 8px; }} {st.sel} .cl-nav-tools .btn {{ padding-inline: 14px; }} }}
/* the reference's bar sat {round(top)}px from the top (under its announcement bar) */
{COMMON.format(sel=st.sel)}''')
    return jsx, css, body


def _marquee_columns(m: Model, js, pics: list[dict], cycle: float) -> tuple[str, str]:
    cols: list[list[dict]] = []
    for r in sorted(pics, key=lambda r: r["x"]):
        if cols and abs(cols[-1][0]["x"] - r["x"]) < 40:
            cols[-1].append(r)
        else:
            cols.append([r])
    owned = list(dict.fromkeys(p["src"] for p in m.owned.get("pics", []) if p["x"] > m.width * 0.45))  # each picture once
    html = []
    for n, col in enumerate(cols[:3]):
        items = sorted(col, key=lambda r: r["y"])
        mine = owned[n::max(1, len(cols[:3]))] if owned else []
        cards = "".join(f'<li className="cl-mq-item">{_img(js, mine[k % len(mine)] if mine else m.picture(r), r, eager=True)}</li>'
                        for k, r in enumerate(items))
        html.append(f'<div className="cl-mq-col{" is-rev" if n % 2 else ""}" aria-hidden="true"><ul className="cl-mq-track">{cards}{cards}</ul></div>')
    css = (f"@keyframes cl-mqv {{ from {{ transform: translateY(0); }} to {{ transform: translateY(-50%); }} }}\n"
           f"SEL .cl-mq {{ display: flex; gap: 20px; height: 100%; max-height: 100%; overflow: hidden; "
           f"mask-image: linear-gradient(transparent, #000 10%, #000 90%, transparent); }}\n"
           f"SEL .cl-mq-col {{ flex: 1; min-width: 0; }}\n"
           f"SEL .cl-mq-track {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 20px; "
           f"animation: cl-mqv {cycle:g}s linear infinite; }}\n"
           f"SEL .cl-mq-col.is-rev .cl-mq-track {{ animation-direction: reverse; }}\n"
           f"SEL .cl-mq:hover .cl-mq-track {{ animation-play-state: paused; }}\n"
           f"SEL .cl-mq-item {{ border-radius: 8px; overflow: hidden; background: #fff; box-shadow: var(--shadow-md); }}\n"
           f"@media (prefers-reduced-motion: reduce) {{ SEL .cl-mq-track {{ animation: none; }} }}")
    return f'<div className="cl-mq">{"".join(html)}</div>', css


def _effect(m: Model, effect: str) -> dict | None:
    return next((e for e in m.spec.get("effects", []) if e.get("effect") == effect), None)


def _hero(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    on = m.bg
    head = _header(m, st, js, s.id, on=on)
    pics = [r for r in m.pictures if r["x"] > m.width * 0.45]
    marquee = _effect(m, "marquee-vertical")
    media, extra = "", ""
    if pics and marquee:
        media, extra = _marquee_columns(m, js, pics, float((marquee.get("params") or {}).get("cycle_s") or 30))
        extra = extra.replace("SEL", st.sel)
    elif pics:
        big = max(pics, key=lambda r: r["w"] * r["h"])
        media = f'<div className="cl-hero-pic">{_img(js, m.picture(big), big, eager=True)}</div>'
    layers = "".join(f'<div className="m-paint m-paint-{k}" aria-hidden="true" />' for k, _ in enumerate(s.paint[:8]))
    jsx = (f'{layers}<div className="cl-hero{" has-media" if media else ""}"><div className="cl-hero-text">{head}</div>'
           + (f'<div className="cl-hero-media">{media}</div>' if media else "") + "</div>")
    from chromaswarm.developer.measured import paint_layers
    _, paint_css = paint_layers(s, st.sel)
    text_w = (m.heading["w"] if m.heading else 640)
    sub_w = max((r["w"] for r in m.subs), default=text_w)
    mg = m.spec.get("margins") or {}
    left = float(mg.get("left") or 0) or (m.heading["x"] if m.heading else 96)
    media_x = min((r["x"] for r in pics), default=m.width * 0.55)
    media_r = max((r["x"] + r["w"] for r in pics), default=m.width)
    right = max(0.0, m.width - media_r)
    css = st.section(f'''{st.sel} .cl-hero {{ display: grid; grid-template-columns: 1fr; gap: 48px; align-items: center; min-height: {max(320, round(m.height - 96))}px; }}
@media (min-width: 1024px) {{ {st.sel} .cl-hero.has-media {{ grid-template-columns: minmax(0, {round(media_x - left)}fr) minmax(0, {round(media_r - media_x)}fr); gap: 0; }} }}
@media (min-width: 1200px) {{ {st.sel} > .container {{ max-width: none; padding-left: {round(left)}px; padding-right: {round(right)}px; }} }}
{st.sel} .cl-hero-text p {{ max-width: {round(sub_w)}px; }}
{st.sel} .cl-hero-media {{ height: {round(min(m.height, 900))}px; max-height: 80vh; }}
{st.sel} .cl-hero-pic {{ border-radius: 16px; overflow: hidden; }}
{st.sel} .cl-head {{ max-width: {round(text_w)}px; }}
{extra}
{paint_css}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def _card_jsx(m: Model, st: Style, js, c: dict, sid: str, n: int) -> str:
    on = m.color((m.variants.get(c.get("variant") or "") or {}).get("fill")) or m.bg
    parts = []
    for r in c["members"]:
        if r["kind"] == "image":
            parts.append(f'<div className="cl-card-pic">{_img(js, m.picture(r), r)}</div>')
    body = []
    for r in c["members"]:
        if r["kind"] == "heading":
            body.append(f'<h3 className="{st.tok(r, on)}">{_t(js, m.text(r, "head"), "heading")}</h3>')
        elif r["kind"] == "text":
            body.append(f'<p className="{st.tok(r, on)}">{_t(js, m.text(r, "body" if (r.get("chars") or 0) > 40 else "short"), "text")}</p>')
        elif r["kind"] in ("link", "button"):
            body.append(f'<a href="#" className="{st.tok(r, on)} cl-card-link" data-swarm-id="{sid}-link-{n}" data-swarm-role="link">'
                        f'{_t(js, m.text(r), "link")}</a>')
    if body:
        parts.append(f'<div className="cl-card-body">{"".join(body)}</div>')
    return f'<li className="cl-card {st.card(c)}">{"".join(parts)}</li>'


def _cards(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    cards = sorted(m.cards, key=lambda c: (round(c["y"] / 40), c["x"]))
    first_row = [c for c in cards if abs(c["y"] - cards[0]["y"]) < 40]
    cols = max(1, len(first_row))
    head = _header(m, st, js, s.id, with_actions=False)
    items = "".join(_card_jsx(m, st, js, c, s.id, n) for n, c in enumerate(cards))
    after = [r for r in m.actions if cards and r["y"] > max(c["y"] + c["h"] for c in cards) - 8]
    before = [r for r in m.actions if r not in after]
    gap = round(first_row[1]["x"] - first_row[0]["x"] - first_row[0]["w"]) if len(first_row) > 1 else 24
    head_gap = round(cards[0]["y"] - ((m.subs[-1]["y"] + m.subs[-1]["h"]) if m.subs else (m.heading["y"] + m.heading["h"]) if m.heading else cards[0]["y"])) if cards else 48
    jsx = (head + (_actions(m, st, js, s.id, before) if before else "")
           + f'<ul className="cl-cards">{items}</ul>'
           + (f'<div className="cl-after">{_actions(m, st, js, s.id + "-more", after)}</div>' if after else ""))
    css = st.section(f'''{st.sel} .cl-cards {{ list-style: none; margin: {max(24, head_gap)}px 0 0; padding: 0; display: grid; gap: {max(16, gap)}px;
  grid-template-columns: repeat({cols}, minmax(0, 1fr)); }}
@media (max-width: 1023px) {{ {st.sel} .cl-cards {{ grid-template-columns: repeat({min(cols, 2)}, minmax(0, 1fr)); }} }}
@media (max-width: 639px) {{ {st.sel} .cl-cards {{ grid-template-columns: 1fr; }} }}
{st.sel} .cl-card-body {{ display: flex; flex-direction: column; gap: 8px; padding: 20px; }}
{st.sel} .cl-card-link {{ text-decoration: none; min-height: 24px; }}
{st.sel} .cl-after {{ display: flex; justify-content: center; margin-top: 32px; }}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def owned_quotes(m: Model) -> list[tuple[str, str]]:
    """(quote, "Name – Role") from the user's own words, in reading order, each quote once."""
    texts = m.owned.get("texts", [])
    out, seen = [], set()
    for n, t in enumerate(texts):
        if not (t.get("quote") or t["t"].lstrip().startswith(("“", '"', "«"))) or len(t["t"]) < 30:
            continue
        key = t["t"].strip()[:60]
        if key in seen:
            continue
        seen.add(key)
        after = [x["t"] for x in texts[n + 1:n + 4] if len(x["t"]) < 80 and not x.get("quote")]
        out.append((t["t"].strip(), " ".join(after[:2]).strip()))
    return out


def _testimonials(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    quotes = [r for r in m.loose if r["kind"] == "text" and (r.get("chars") or 0) >= 40 and r not in m.subs]
    names = [r for r in m.loose if r["kind"] in ("text", "heading") and (r.get("chars") or 0) < 60 and r not in (m.eyebrow,) and r not in m.subs
             and r is not m.heading]
    def name_for(q: dict) -> dict | None:
        below = [n for n in names if n["y"] > q["y"] and n["y"] - (q["y"] + q["h"]) < 80 and abs(n["x"] - q["x"]) < 120]
        above = [n for n in names if n["y"] < q["y"] and q["y"] - (n["y"] + n["h"]) < 80 and abs(n["x"] - q["x"]) < 400]
        return (below or above or [None])[0]
    cards = []
    qcls = st.tok(quotes[0]) if quotes else "t-body"
    ncls = st.tok(next((name_for(q) for q in quotes if name_for(q)), None)) or "t-caption"
    owned = owned_quotes(m)
    if owned:  # the user's own quotes, in reading order (a moving wall cannot be matched by place)
        for q, who in owned[:12]:
            name, _, role = re.split(r"\s[–-]\s", who, maxsplit=1)[0], None, (re.split(r"\s[–-]\s", who, maxsplit=1) + [""])[1]
            person = (f'<p className="cl-who {ncls}">{_t(js, name, "text")}'
                      + (f'<span className="cl-role"> – {_t(js, role, "text")}</span>' if role else "") + "</p>")
            cards.append(f'<li className="cl-quote"><blockquote className="{qcls}">{_t(js, q, "quote")}</blockquote>'
                         f'<div className="cl-person"><span className="cl-avatar" aria-hidden="true" />{person}</div></li>')
    for q in ([] if owned else quotes[:12]):
        n = name_for(q)
        who = f'<p className="cl-who {st.tok(n)}">{_t(js, m.text(n), "text")}</p>' if n else ""
        cards.append(f'<li className="cl-quote"><blockquote className="{st.tok(q)}">{_t(js, m.text(q, "body"), "quote")}</blockquote>'
                     f'<div className="cl-person"><span className="cl-avatar" aria-hidden="true" />{who}</div></li>')
    head = _header(m, st, js, s.id, with_actions=False) if m.heading else ""
    marquee = _effect(m, "marquee-vertical")
    wall_h = round(m.height - 260)
    above = max([m.heading["y"] + m.heading["h"]] if m.heading else [0] + [r["y"] + r["h"] for r in m.subs])
    above = max([above] + [r["y"] + r["h"] for r in m.subs])
    wall_gap = round(min((r["y"] for r in quotes), default=above + 40) - above)
    if marquee and len(cards) >= 4:
        half = (len(cards) + 1) // 2
        cycle = float((marquee.get("params") or {}).get("cycle_s") or 30)
        cols = [cards[:half], cards[half:]]
        span = [r for r in quotes] or []
        wall_h = round(max(r["y"] + r["h"] for r in span) - min(r["y"] for r in span)) if span else round(m.height - 260)
        wall_h = max(480, wall_h)
        reps = max(1, -(-wall_h // max(1, (len(cols[0]) or 1) * 180)))  # enough cards that a column never runs dry
        cols = [c * reps for c in cols]
        body = '<div className="cl-mq cl-wall">' + "".join(
            f'<div className="cl-mq-col{" is-rev" if k else ""}"><ul className="cl-mq-track">{"".join(c)}'
            + "".join(x.replace('<li className="cl-quote">', '<li className="cl-quote" aria-hidden="true">', 1) for x in c)
            + "</ul></div>"
            for k, c in enumerate(cols)) + "</div>"
        _, mq = _marquee_columns(m, js, [], cycle)
        mq = mq.replace("SEL", st.sel)
    else:
        body = f'<ul className="cl-quotes{" is-single" if len(cards) == 1 else ""}">{"".join(cards)}</ul>'
        mq = ""
    jsx = head + body
    css = st.section(f'''{st.sel} .cl-quotes {{ list-style: none; margin: 32px 0 0; padding: 0; display: grid; gap: 24px; justify-items: center; }}
{st.sel} .cl-quote {{ display: flex; flex-direction: column; gap: 16px; padding: 24px; border-radius: 16px; background: color-mix(in oklch, {m.bg} 96%, #000);
  border: 1px solid var(--border-subtle); max-width: 720px; }}
{st.sel} .cl-quote blockquote {{ margin: 0; }}
{st.sel} .cl-quotes.is-single .cl-quote {{ background: none; border: 0; padding: 0; align-items: center; text-align: center; max-width: 880px; }}
{st.sel} .cl-quotes.is-single {{ margin-top: 0; }}
{st.sel} .cl-person {{ display: flex; align-items: center; gap: 10px; }}
{st.sel} .cl-avatar {{ width: 28px; height: 28px; border-radius: 999px; flex: none; background: linear-gradient(135deg, var(--accent), color-mix(in oklch, var(--accent) 40%, #000)); }}
{st.sel} .cl-mq.cl-wall {{ height: {wall_h}px; max-height: none; margin-top: {max(32, wall_gap)}px; }}
{st.sel} .cl-wall .cl-quote {{ max-width: none; gap: 12px; padding: 8px 8px 12px; border-radius: 20px; }}
{st.sel} .cl-wall .cl-quote blockquote {{ padding: 16px; border-radius: 14px; background: {m.bg}; box-shadow: 0 1px 2px color-mix(in oklch, #000 6%, transparent); font-weight: 400; }}
{st.sel} .cl-wall .cl-person {{ padding-inline: 8px; }}
{st.sel} .cl-role {{ font-weight: 400; opacity: .7; }}
{mq}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def _rows(m: Model, st: Style, js, sid: str, rows: list[dict], copy_faqs: list) -> str:
    out = []
    for n, r in enumerate(rows[:10]):
        found = m.texts_in(r)
        if len(found) == 1 and "?" in found[0][:200] and not found[0].rstrip().endswith("?"):
            cut = found[0].index("?") + 1  # the reference's row holds its question and its answer in one control
            found = [found[0][:cut].strip(), found[0][cut:].strip()]
        if found:
            q, a = found[0], " ".join(found[1:])
        elif n < len(copy_faqs):
            q, a = copy_faqs[n]
        else:
            q, a = m.words.take("head", 40), m.words.take("body", 140)
        out.append(f'<details className="cl-row"{" open" if n == 0 else ""}><summary data-swarm-id="{sid}-item-{n}" data-swarm-role="button">'
                   f'<span className="cl-q">{_t(js, q, "question")}</span>'
                   f'<svg className="cl-chev" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 6 4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>'
                   f'</summary>' + (f'<p className="cl-a">{_t(js, a, "answer")}</p>' if a else "") + "</details>")
    return f'<div className="cl-rows">{"".join(out)}</div>'


def rows_metrics(m: Model, rows: list[dict]) -> dict:
    """Row height, inner side padding and gap between rows, as measured on the reference."""
    rs = sorted(rows, key=lambda r: r["y"])
    closed = sorted(r["h"] for r in rs[1:]) or [56]
    gaps = [b["y"] - (a["y"] + a["h"]) for a, b in zip(rs, rs[1:]) if b["y"] > a["y"] + a["h"]]
    cards = {id(c): c for c in m.cards}
    inner = next((r["x"] - c["x"] for r in rs for c in cards.values() if _inside(r, c)), None)
    ink = m.color(rs[0].get("ink")) if rs else None
    return {"h": max(48, round(closed[len(closed) // 2])), "gap": max(8, round(min(gaps))) if gaps else 8,
            "pad": 40 if inner is not None and inner >= 6 else 24, "ink": ink}


def rows_css(m: Model, st: Style, rows: list[dict]) -> str:
    k = rows_metrics(m, rows)
    from chromaswarm.developer.measured import readable_variant
    ink = (readable_variant(k["ink"], m.bg, False) if k["ink"] else None) or "var(--text-primary)"
    shadow = any((m.variants.get(c.get("variant") or "") or {}).get("shadow") for c in m.cards)
    return (ROWS_CSS.format(sel=st.sel, card=m.bg)
            + f"\n{st.sel} .cl-rows {{ gap: {k['gap']}px; }}"
            + f"\n{st.sel} .cl-row {{ border-radius: 16px;{' box-shadow: var(--shadow-sm);' if shadow else ''} }}"
            + f"\n{st.sel} .cl-row > summary {{ min-height: {k['h']}px; padding: 16px {k['pad'] - 16}px 16px {k['pad']}px; color: {ink}; font-size: 18px; }}"
            + f"\n{st.sel} .cl-a {{ padding: 0 {k['pad']}px 24px; }}"
            + f"\n{st.sel} .cl-chev {{ box-sizing: content-box; padding: 9px; border-radius: 999px; border: 1px solid var(--border-subtle); }}")


ROWS_CSS = """{sel} .cl-rows {{ display: flex; flex-direction: column; gap: 8px; }}
{sel} .cl-row {{ border-radius: 12px; border: 1px solid var(--border-subtle); background: {card}; }}
{sel} .cl-row > summary {{ list-style: none; cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 16px;
  min-height: 56px; padding: 12px 20px; font-weight: 600; }}
{sel} .cl-row > summary::-webkit-details-marker {{ display: none; }}
{sel} .cl-row > summary:hover {{ background: color-mix(in oklch, currentColor 4%, transparent); }}
{sel} .cl-row[open] .cl-chev {{ transform: rotate(180deg); }}
{sel} .cl-chev {{ flex: none; transition: transform var(--duration) var(--ease); }}
{sel} .cl-a {{ margin: 0; padding: 0 20px 16px; color: var(--text-secondary); line-height: 1.6; }}"""


def _faq(m: Model, st: Style, js, s: Section, copy: PageCopy) -> tuple[str, str, str]:
    rows = m.toggles or m.cards
    head = _header(m, st, js, s.id)
    jsx = f'<div className="cl-faq"><div className="cl-faq-side">{head}</div>{_rows(m, st, js, s.id, rows, list(copy.faqs))}</div>'
    side = round(m.heading["w"]) if m.heading else 460
    css = st.section(f'''{st.sel} .cl-faq {{ display: grid; gap: 40px; grid-template-columns: 1fr; }}
@media (min-width: 1024px) {{ {st.sel} .cl-faq {{ grid-template-columns: minmax(0, {side}px) minmax(0, 1fr); gap: 64px; align-items: start; }} }}
{rows_css(m, st, rows)}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def _feature_accordion(m: Model, st: Style, js, s: Section, copy: PageCopy) -> tuple[str, str, str]:
    rows = m.toggles
    head = _header(m, st, js, s.id)
    pics = [r for r in m.pictures if r["x"] > m.width * 0.45]
    big = max(pics, key=lambda r: r["w"] * r["h"], default=None)
    media = f'<div className="cl-feature-pic">{_img(js, m.picture(big), big)}</div>' if big else ""
    jsx = f'<div className="cl-feature"><div className="cl-feature-text">{head}{_rows(m, st, js, s.id, rows, list(copy.faqs))}</div>{media}</div>'
    css = st.section(f'''{st.sel} .cl-feature {{ display: grid; gap: 48px; grid-template-columns: 1fr; align-items: center; }}
@media (min-width: 1024px) {{ {st.sel} .cl-feature {{ grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }} }}
{st.sel} .cl-feature-text {{ display: flex; flex-direction: column; gap: 32px; }}
{st.sel} .cl-feature-pic {{ border-radius: 24px; overflow: hidden; }}
{rows_css(m, st, rows)}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def _footer(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    logo = next((r for r in m.loose if r["kind"] == "image" and r["w"] <= 120), None)
    links = sorted(m.links, key=lambda r: r["x"])
    columns: list[list[dict]] = []
    for r in links:
        if columns and abs(columns[-1][0]["x"] - r["x"]) < 80:
            columns[-1].append(r)
        else:
            columns.append([r])
    heads = [r for r in m.loose if r["kind"] == "heading" and m.size(r) < 96]
    brand_text = next((r for r in m.loose if r["kind"] in ("text", "heading") and r["x"] < m.width * 0.35 and r["y"] < 200), None)
    bottom = max([r for r in m.loose if r["kind"] == "text" and r is not brand_text], key=lambda r: r["y"], default=None)
    cols_jsx = []
    for n, col in enumerate(columns[:5]):
        col.sort(key=lambda r: r["y"])
        h = min([x for x in heads if abs(x["x"] - col[0]["x"]) < 60 and x["y"] < col[0]["y"]], key=lambda x: col[0]["y"] - x["y"], default=None)
        lis = "".join(f'<li><a href="#" className="{st.tok(r)} cl-flink" data-swarm-id="{s.id}-link-{n}-{k}" data-swarm-role="link">'
                      f'{_t(js, m.text(r), "link")}</a></li>' for k, r in enumerate(col))
        cols_jsx.append(f'<nav className="cl-fcol">' + (f'<p className="{st.tok(h)}">{_t(js, m.text(h, "head"), "heading")}</p>' if h else "")
                        + f'<ul>{lis}</ul></nav>')
    brand = ('<div className="cl-fbrand">' + (_img(js, m.picture(logo), logo).replace('className="cl-img"', 'className="cl-logo"').replace('className="cl-skel"', 'className="cl-logo cl-skel"') if logo else "")
             + (f'<span className="{st.tok(brand_text)}">{_t(js, m.text(brand_text), "brand")}</span>' if brand_text else "") + "</div>")
    giant = next((r for r in m.loose if r["kind"] == "heading" and m.size(r) >= 96), None)
    # Decorative (faint by design): drawn by CSS from an attribute, so it is not page text.
    wordmark = (f'<div className="cl-fgiant" aria-hidden="true" data-word={{{js(m.text(giant, "head") or m.text(brand_text), "brand")}}} />'
                if giant else "")
    jsx = (f'<footer className="cl-footer"><div className="cl-ftop">{brand}<div className="cl-fcols">{"".join(cols_jsx)}</div></div>'
           + (f'<p className="cl-fbottom {st.tok(bottom)}">{_t(js, m.text(bottom), "text")}</p>' if bottom else "") + wordmark + "</footer>")
    left = round(min((c[0]["x"] for c in columns), default=600))
    mleft = float((m.spec.get("margins") or {}).get("left") or 0)
    inset = max(0, round((logo or brand_text or {"x": mleft})["x"] - mleft))
    btop = round(bottom["y"] - max([r["y"] + r["h"] for r in links] + [0])) if bottom else 48
    gt = m.type.get((giant or {}).get("type") or "", {})
    css = st.section(f'''{st.sel} .cl-ftop {{ display: grid; gap: 40px; grid-template-columns: 1fr; }}
@media (min-width: 1024px) {{ {st.sel} .cl-ftop {{ grid-template-columns: minmax(0, {max(200, left - (m.spec.get("margins") or {}).get("left", 0) - 48)}px) 1fr; }} }}
{st.sel} .cl-ftop {{ align-items: start; }}
{st.sel} .cl-fbrand {{ display: flex; align-items: center; gap: 12px; padding-left: {inset}px; }}
{st.sel} .cl-fgiant::before {{ content: attr(data-word); }}
{st.sel} .cl-fgiant {{ margin: 24px 0 0; font-size: clamp(64px, 18vw, {round(gt.get("size") or 240)}px); font-weight: {gt.get("weight") or 700};
  line-height: .8; letter-spacing: -0.04em; text-align: center; color: color-mix(in oklch, currentColor 7%, transparent); white-space: nowrap;
  overflow: hidden; pointer-events: none; user-select: none; }}
{st.sel} .cl-logo {{ width: {round(logo["w"]) if logo else 44}px; height: {round(logo["h"]) if logo else 44}px; border-radius: 10px; object-fit: contain; }}
{st.sel} .cl-fcols {{ display: grid; gap: 32px; grid-template-columns: repeat({max(1, len(cols_jsx))}, minmax(0, 1fr)); }}
@media (max-width: 767px) {{ {st.sel} .cl-fcols {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
{st.sel} .cl-fcol ul {{ list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }}
{st.sel} .cl-flink {{ text-decoration: none; display: inline-flex; min-height: 24px; align-items: center; }}
{st.sel} .cl-flink:hover {{ text-decoration: underline; text-underline-offset: 4px; }}
{st.sel} .cl-fbottom {{ margin-top: {max(24, btop)}px; padding-left: {inset}px; }}
@media (max-width: 767px) {{ {st.sel} .cl-flink {{ min-height: 48px; }} }}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


def _features(m: Model, st: Style, js, s: Section) -> tuple[str, str, str]:
    """Heading + text on one side, pictures (stacked mockups keep their offsets) on the other, then a row of
    features below — each its icon, heading and text, in the reference's columns."""
    hy = (m.heading["y"] + m.heading["h"]) if m.heading else 0
    feats = [r for r in m.loose if r["kind"] == "heading" and r is not m.heading and r["y"] > hy]
    pics = [r for r in m.pictures if r["w"] > 48 and r["x"] > m.width * 0.4]
    head = _header(m, st, js, s.id)
    stack = ""
    chip_fill = "var(--accent)"
    if pics:
        x0, y0 = min(r["x"] for r in pics), min(r["y"] for r in pics)
        x1, y1 = max(r["x"] + r["w"] for r in pics), max(r["y"] + r["h"] for r in pics)
        layers = "".join(f'<div className="cl-stack-item" style={{{{ left: "{(r["x"] - x0) / max(1, x1 - x0) * 100:.2f}%", '
                         f'top: "{(r["y"] - y0) / max(1, y1 - y0) * 100:.2f}%", width: "{r["w"] / max(1, x1 - x0) * 100:.2f}%" }}}}>'
                         f'{_img(js, m.picture(r), r)}</div>' for r in sorted(pics, key=lambda r: r["w"] * r["h"], reverse=True))
        chips = [r for r in m.loose if r["kind"] in ("text", "button") and r is not m.heading and r not in m.subs and r is not m.eyebrow
                 and r["x"] >= x0 - 120 and r["y"] <= y1 and (r.get("chars") or 0) < 30 and r["h"] >= 32]
        for ci, r in enumerate(chips):
            light = (m.color(r.get("ink")) or "").lower() in ("#ffffff", "#fff")
            from chromaswarm.developer.measured import readable_variant
            raw = m.color((m.variants.get("button/filled") or {}).get("fill"))
            chip_fill = (readable_variant(raw, "#e6e6e6", False) or raw) if raw else "var(--accent)"  # a margin over 4.5:1  # white label stays readable
            layers += (f'<span className="cl-chip cl-chip-{ci}{" is-filled" if light else ""}" style={{{{ left: "{(r["x"] - x0) / max(1, x1 - x0) * 100:.2f}%", '
                       f'top: "{(r["y"] - y0) / max(1, y1 - y0) * 100:.2f}%" }}}}>{_t(js, m.text(r), "label")}</span>')
        stack = (f'<div className="cl-stack" style={{{{ aspectRatio: "{round(x1 - x0)} / {round(y1 - y0)}", maxWidth: {round(x1 - x0)} }}}}>'
                 f'{layers}</div>')
    cols = []
    for n, f in enumerate(sorted(feats, key=lambda r: (r["y"] // 40, r["x"]))[:6]):
        icon = next((r for r in m.loose if r["kind"] == "image" and r["w"] <= 64 and abs(r["x"] - f["x"]) < 40 and 0 < f["y"] - r["y"] < 120), None)
        texts = [r for r in m.loose if r["kind"] == "text" and abs(r["x"] - f["x"]) < 24 and 0 < r["y"] - f["y"] < 240]
        cols.append('<li className="cl-feat">' + ('<span className="cl-icon" aria-hidden="true" />' if icon else "")
                    + f'<h3 className="{st.tok(f)}">{_t(js, m.text(f, "head"), "heading")}</h3>'
                    + "".join(f'<p className="{st.tok(t)}">{_t(js, m.text(t, "body"), "text")}</p>' for t in texts[:2]) + "</li>")
    gap_feats = round(min((f["y"] for f in feats), default=hy) - max([hy] + [r["y"] + r["h"] for r in pics] + [r["y"] + r["h"] for r in m.subs]))
    jsx = (f'<div className="cl-split"><div>{head}</div>{stack}</div>'
           + (f'<ul className="cl-feats" style={{{{ marginTop: {max(32, gap_feats)} }}}}>{"".join(cols)}</ul>' if cols else ""))
    ncol = len([f for f in feats if abs(f["y"] - (feats[0]["y"] if feats else 0)) < 40]) or 3
    css = st.section(f'''{st.sel} .cl-split {{ display: grid; gap: 48px; grid-template-columns: 1fr; align-items: start; }}
@media (min-width: 1024px) {{ {st.sel} .cl-split {{ grid-template-columns: minmax(0, {round(m.heading["w"]) if m.heading else 576}fr) minmax(0, 520fr); }} }}
{st.sel} .cl-stack {{ position: relative; width: 100%; justify-self: end; }}
{st.sel} .cl-chip {{ position: absolute; z-index: 2; display: inline-flex; align-items: center; min-height: 40px; padding: 8px 16px; border-radius: 999px;
  font-size: 15px; font-weight: 600; white-space: nowrap; background: #fff; color: var(--text-primary); box-shadow: var(--shadow-md); }}
@media (max-width: 1023px) {{ {st.sel} .cl-chip {{ display: none; }} }}
{st.sel} .cl-chip.is-filled {{ background: {chip_fill}; color: #fff; }}
{st.sel} .cl-stack-item {{ position: absolute; border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-md); background: #fff; }}
{st.sel} .cl-feats {{ list-style: none; padding: 0; margin-bottom: 0; display: grid; gap: 40px; grid-template-columns: repeat({min(ncol, 4)}, minmax(0, 1fr)); }}
@media (max-width: 767px) {{ {st.sel} .cl-feats {{ grid-template-columns: 1fr; }} }}
{st.sel} .cl-feat {{ display: flex; flex-direction: column; gap: 12px; }}
{st.sel} .cl-icon {{ width: 40px; height: 40px; border-radius: 10px; background: var(--accent); opacity: .9; }}
{COMMON.format(sel=st.sel)}''')
    return jsx, css, ""


# ------------------------------------------------------------------ entry

def kind_of(s: Section) -> str | None:
    if not s.design or not s.design.get("section"):
        return None
    st = s.structure
    if st == "announcement-bar":
        return "announcement"
    if st == "sticky-bar":
        return "nav"
    if st in HERO:
        return "hero"
    if st == "accordion":
        return "feature-accordion" if s.id == "feature-accordion" else "faq"
    if st == "testimonials":
        return "testimonials"
    if st == "footer-columns":
        return "footer"
    cards = [r for r in s.design["section"].get("components", []) if r["kind"] == "card" and not r.get("frame")]
    if len(cards) >= 2:
        return "cards"
    rows = s.design["section"].get("components", [])
    if sum(1 for r in rows if r["kind"] == "heading") >= 2 or any(r["kind"] in ("image", "card") for r in rows):
        return "features"
    return None


def render(section: Section, copy: PageCopy) -> str | None:
    """The section's component code, or None (not one of the kinds above)."""
    from chromaswarm.developer.nextjs import _component, _js
    kind = kind_of(section)
    if kind is None:
        return None
    m = Model(section, copy)
    st = Style(m, section.id)
    js = _js
    if kind == "announcement":
        jsx, css, body = _announcement(m, st, js, section)
        out = _component(section, f"<>{jsx}<style>{{{json.dumps(css)}}}</style></>", client=True, body=body)
        return out.replace('import { useState } from "react";', 'import { useEffect, useState } from "react";')
    if kind == "nav":
        jsx, css, body = _nav(m, st, js, section)
        return _component(section, f"<>{jsx}<style>{{{json.dumps(css)}}}</style></>", client=bool(body), body=body)
    build = {"hero": _hero, "cards": _cards, "testimonials": _testimonials, "footer": _footer, "features": _features}.get(kind)
    if build:
        inner, css, _ = build(m, st, js, section)
    elif kind == "faq":
        inner, css, _ = _faq(m, st, js, section, copy)
    else:
        inner, css, _ = _feature_accordion(m, st, js, section, copy)
    band = " s-band" if section.design["section"]["box"].get("band") else ""
    tag = "footer" if kind == "footer" else "section"
    jsx = (f'<{tag} data-swarm-section="{section.id}" className="s cl-sec{band}">\n'
           f'      <div className="container">\n{inner}\n      <style>{{{json.dumps(css)}}}</style>\n      </div>\n    </{tag}>')
    if kind == "footer":
        jsx = jsx.replace('<footer className="cl-footer">', '<div className="cl-footer">').replace("</footer>\n      <style>", "</div>\n      <style>", 1)
    return _component(section, jsx)
