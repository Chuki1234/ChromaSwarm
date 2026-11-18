"""Clone: a section rendered from the reference's measured layout (clone/layout.py), not from a template.

Every reference component becomes one element of the same kind at the same place:

* desktop (≥1200px): each row / column / leaf gets its measured left offset and width (% of its parent),
  its vertical gap (px), and its measured type (size, weight, tracking, leading, case), corner radius,
  card shadow / border; the section keeps the reference's top and bottom space and content span;
* tablet: columns share the row; phone: everything stacks, on the design system's own type scale.

Words are the page's own sample copy (or the user's, B4) cut to the length the reference showed there,
so blocks wrap to about the same height; pictures are the template's photos at the measured aspect ratio.
Controls are real: links and buttons with hover / focus styles, inputs with a visible label.
"""

from __future__ import annotations

import html
import itertools
import urllib.parse

from chromaswarm.agents.planner import Section
from chromaswarm.clone.components import Comp, comps
from chromaswarm.clone.layout import Node, build_tree
from chromaswarm.developer.content import PageCopy
from chromaswarm.engines.color import parse_css_color, wcag_luminance

# Structures whose behaviour a static layout cannot carry keep their template.
TEMPLATE_ONLY = {"accordion", "horizontal-scroller", "list-rows", "logo-strip",
                 "picker-recommend", "announcement-bar", "inline-controls"}
DESKTOP = "@media (min-width: 1200px)"


def measurable(section: Section) -> bool:
    return bool(section.layout) and section.structure not in TEMPLATE_ONLY


class _Words:
    """Sample copy of a given length, never repeating a sentence until the pool is used up."""

    def __init__(self, c: PageCopy):
        heads = [c.headline, *[t for t, _ in c.story], c.closing, *[i.name for i in c.cards], *[i.name for i in c.items],
                 *[q for q, _ in c.faqs]]
        body = [c.subhead, *[t for _, t in c.story], c.footer_line, *[a for _, a in c.faqs], *[t for _, t in c.tabs],
                *[i.note for i in c.cards if i.note]]
        short = [c.cta_secondary, *c.nav, *c.categories, *[t for t, _ in c.facts]]
        self.lists = {k: list(dict.fromkeys(x for x in v if x)) or ["—"] for k, v in
                      (("head", heads), ("body", body), ("short", short + heads))}
        self.used: dict[str, set[str]] = {k: set() for k in self.lists}
        self.pools = {k: itertools.cycle(v) for k, v in self.lists.items()}
        self.cta = itertools.cycle([c.cta, c.cta_secondary])

    def _closest(self, kind: str, chars: int) -> str:
        """The unused line whose length is closest to the reference's (headings and labels are one line,
        never several glued together)."""
        free = [x for x in self.lists[kind] if x not in self.used[kind]] or self.lists[kind]
        if len(free) == len(self.lists[kind]):
            self.used[kind].clear()
        best = min(free, key=lambda x: abs(len(x) - chars))
        self.used[kind].add(best)
        if len(best) > chars * 1.6 and chars >= 6:
            cut = best[: int(chars * 1.2)].rsplit(" ", 1)[0].rstrip(",;:—-[")
            best = cut + ("]" if best.startswith("[") and not cut.endswith("]") else "") if len(cut) >= 3 else best
        return best

    def take(self, kind: str, chars: int) -> str:
        if kind == "cta":
            return next(self.cta)
        if kind in ("head", "short"):
            return self._closest(kind, chars)
        pool = self.pools[kind]
        text = next(pool)
        guard = 0
        while len(text) < chars * 0.8 and guard < 6:
            text += (" " if kind != "body" or text.endswith((".", "!", "?")) else ". ") + next(pool)
            guard += 1
        if len(text) > chars * 1.25 and chars >= 8:
            cut = text[: int(chars * 1.1)].rsplit(" ", 1)[0].rstrip(",;:—-")
            text = cut if len(cut) >= 4 else text
        return text


def _chars(c: Comp) -> int:
    """Characters the reference showed here: counted on the page when known, else estimated from the box."""
    if c.chars:
        return max(2, min(c.chars, 600))
    fs = max(c.fs, 8)
    lines = max(1, round(c.h / (fs * (c.lh or 1.3))))
    return max(2, min(int(c.w / (fs * 0.5)) * lines, 420))


def _lum(hex_: str | None) -> float | None:
    if not hex_:
        return None
    parsed = parse_css_color(hex_)
    return wcag_luminance(parsed[0]) if parsed else None


def _type_class(c: Comp) -> str:
    if c.kind == "heading":
        return "t-display" if c.fs >= 56 else "t-h1" if c.fs >= 40 else "t-h2" if c.fs >= 28 else "t-h3" if c.fs >= 21 else "t-h4"
    return "t-caption" if c.fs < 15 else "t-lead" if c.fs >= 19 else "t-body"


class _Render:
    def __init__(self, section: Section, copy: PageCopy, js):
        self.s, self.js = section, js
        self.words = _Words(copy)
        self.n = 0
        self.css: list[str] = []
        self.sel = f'[data-swarm-section="{section.id}"]'
        self.has_h1 = False
        self.filled = False
        self.nav = list(copy.nav_links) if section.structure == "sticky-bar" else []
        self.brand = copy.brand or ""
        self.buttons = 0
        self.elastic: set[int] = set()
        self.tone = 0
        texts = [x for x in comps(section.layout) if x.kind == "heading"] or [x for x in comps(section.layout) if x.kind == "text"]
        self.ink = _lum(texts[0].color) if texts else None

    def rule(self, i: int, props: dict[str, str]) -> None:
        if props:
            self.css.append(f"  {self.sel} .n{i} {{ " + " ".join(f"{k}: {v};" for k, v in props.items()) + " }")

    # ---------------------------------------------------------------- placement
    def place(self, node: Node, parent: Node, prev: Node | None, axis: str, i: int) -> dict[str, str]:
        pw = max(parent_inner_w(parent), 1)
        props: dict[str, str] = {}
        if axis == "rows":
            gap = node.y0 - (prev.y1 if prev else parent_inner_y0(parent))
            props["margin-top"] = f"{max(0, round(gap))}px"
            props["margin-left"] = f"{max(0.0, (node.x0 - parent_inner_x0(parent)) / pw * 100):.3f}%"
        else:
            gap = node.x0 - (prev.x1 if prev else parent_inner_x0(parent))
            # The widest gap of a row (left group | right group) is elastic: it absorbs controls that grew to
            # tap-target size instead of pushing the last ones off the page.
            props["margin-left"] = "auto" if id(node) in self.elastic else f"{max(0.0, gap / pw * 100):.3f}%"
            props["margin-top"] = f"{max(0, round(node.y0 - parent_inner_y0(parent)))}px"
            props["flex"] = "none"
        c = node.comp
        one_line = c is not None and node.kind in ("heading", "text", "link", "button") and \
            node.h < max(c.fs, 8) * (c.lh or 1.3) * 1.6
        if node.kind in ("button", "link"):
            props["width"] = "auto"
            props["min-width"] = f"{round(node.w)}px" if node.kind == "button" else "0"
        elif one_line and axis == "rows":
            props["width"] = "auto"  # a one-line label on the reference stays one line, at its own length
        else:
            # In a row its box holds its place for the next column; stacked, the words' own run decides where
            # the lines break (a 1344px heading block whose lines run 670px wraps like the reference).
            w = node.w
            if axis == "rows" and c is not None and c.tw and c.tw < node.w * 0.9:
                w = c.tw * 1.04
                # Centred / right-aligned words inside a wide box: the narrower block moves to where they start.
                start = node.x0 + max(0, c.tx) - parent_inner_x0(parent)
                props["margin-left"] = f"{max(0.0, start / pw * 100):.3f}%"
            props["width"] = f"{min(100.0, w / pw * 100):.3f}%"
        if one_line:
            props["white-space"] = "nowrap"
        # Centred on the reference (a closing line, a footer heading): centred here too, whatever its length.
        pcx = parent_inner_x0(parent) + pw / 2
        if axis == "rows" and node.w < pw * 0.8 and abs((node.x0 + node.x1) / 2 - pcx) < pw * 0.02:
            props.update({"margin-left": "auto", "margin-right": "auto", "align-self": "center", "text-align": "center"})
        return props

    # ---------------------------------------------------------------- nodes
    def node(self, node: Node, parent: Node | None = None, prev: Node | None = None, axis: str = "rows") -> str:
        i = self.n
        self.n += 1
        desk = self.place(node, parent, prev, axis, i) if parent else {"width": "100%"}
        if node.kind == "layer":
            flow, *back = node.children
            parts = [self.node(flow, node, None, "rows")]
            for b in back:
                parts.append(self.back(b, node))
            desk.update({"position": "relative", "min-height": f"{round(node.h)}px"})
            self.rule(i, desk)
            body = "\n".join(parts)
            return f'<div className="n{i} m-layer" data-n="{i}">\n{body}\n</div>'
        if node.kind in ("rows", "cols", "card"):
            inner_axis = "cols" if node.kind == "cols" else "rows"
            if node.kind == "cols" and len(node.children) > 1:
                gaps = [(b.x0 - a.x1, b) for a, b in zip(node.children, node.children[1:])]
                widest, child = max(gaps, key=lambda g: g[0])
                if widest > 0.12 * max(node.w, 1):
                    self.elastic.add(id(child))
            kids, last = [], None
            for child in node.children:
                kids.append(self.node(child, node, last, inner_axis))
                last = child
            body = "\n".join(kids)
            if node.kind == "card":
                c = node.comp
                assert c is not None
                ix0, iy0, ix1, iy1 = inner(node)
                desk.update({"padding": f"{max(0, round(iy0 - node.y0))}px {max(0, round(node.x1 - ix1))}px "
                                        f"{max(0, round(node.y1 - iy1))}px {max(0, round(ix0 - node.x0))}px",
                             "border-radius": f"{c.radius}px", "gap": "0",
                             "box-shadow": "var(--shadow-md)" if c.shadow else "none",
                             "border": "1px solid var(--border-subtle)" if c.border else "0"})
                if not node.children:
                    desk["min-height"] = f"{round(node.h)}px"
                self.rule(i, desk)
                return f'<div className="n{i} card m-card" data-n="{i}">\n{body}\n</div>'
            desk["gap"] = "0"
            self.rule(i, desk)
            cls = "m-cols" if node.kind == "cols" else "m-rows"
            return f'<div className="n{i} {cls}" data-n="{i}">\n{body}\n</div>'
        return self.leaf(node, i, desk)

    def back(self, node: Node, layer: Node) -> str:
        """A picture behind the layer's flowing content, at its measured place (desktop)."""
        i = self.n
        self.n += 1
        c = node.comp
        assert c is not None
        lw = max(layer.w, 1)
        self.rule(i, {"position": "absolute", "z-index": "0", "margin": "0",
                      "left": f"{(node.x0 - layer.x0) / lw * 100:.3f}%", "top": f"{round(node.y0 - layer.y0)}px",
                      "width": f"{node.w / lw * 100:.3f}%", "border-radius": f"{c.radius}px"})
        if node.kind == "back-card":
            return f'<div className="n{i} m-back m-panel" data-n="{i}" aria-hidden="true" />'
        self.tone += 1
        alt = self.words.take("short", 20)
        return (f'<div className="n{i} m-back m-media" data-n="{i}"><Art label={{{self.js(alt, "image_alt")}}} '
                f'ratio="{max(1, round(c.w))} / {max(1, round(c.h))}" tone={{{self.tone}}} '
                f'sizes="(min-width: 1200px) {round(c.w)}px, 100vw" /></div>')

    def leaf(self, node: Node, i: int, desk: dict[str, str]) -> str:
        c = node.comp
        assert c is not None
        sid = self.s.id
        if c.kind in ("heading", "text", "link", "button"):
            # Two weights per family (standards §2.2): the reference's weight lands on 400 or 600.
            desk.update({"font-size": f"{c.fs:g}px", "font-weight": "600" if c.fw >= 550 else "400", "max-width": "none"})
            if abs(c.ls) > 0.05:
                desk["letter-spacing"] = f"{c.ls:g}px"
            if c.lh and c.kind != "button":
                desk["line-height"] = f"{max(c.lh, 1.4) if c.kind == 'text' and _chars(c) > 120 else c.lh:g}"
            if c.tt:
                desk["text-transform"] = c.tt
            if c.kind == "text" and _chars(c) > 120 and c.fs < 16:
                desk["font-size"] = "16px"  # long text stays readable (standards ch.7, QA)
        if c.kind == "heading":
            level = c.level or (1 if c.fs >= 40 else 2 if c.fs >= 24 else 3)
            if level == 1:
                if self.has_h1 or not self.s.structure.startswith(("split-7-5", "hero", "full-bleed-image")):
                    level = 2
                self.has_h1 = self.has_h1 or level == 1
            self.rule(i, desk)
            # A giant line of type (≥160px) is a wordmark: the brand's name, not a sentence.
            text = self.brand if c.fs >= 160 and self.brand else self.words.take("head", _chars(c))
            return f'<h{level} className="n{i} {_type_class(c)}" data-n="{i}">{{{self.js(text, "heading")}}}</h{level}>'
        if c.kind == "text":
            self.rule(i, desk)
            muted = " muted" if self.ink is not None and (l := _lum(c.color)) is not None and abs(l - self.ink) > 0.12 else ""
            text = self.words.take("body" if _chars(c) > 40 else "short", _chars(c))
            return f'<p className="n{i} {_type_class(c)}{muted}" data-n="{i}">{{{self.js(text, "text")}}}</p>'
        if c.kind == "link":
            self.rule(i, desk)
            if self.nav:  # header: the site's real navigation (built pages first, then in-page anchors)
                label, href = self.nav.pop(0)
                return (f'<a href={{{self.js(href, "href")}}} className="n{i} m-link m-nav" data-n="{i}" '
                        f'data-swarm-id="{sid}-link-{i}" data-swarm-role="link">{{{self.js(label, "link")}}}</a>')
            text = self.words.take("short", _chars(c))
            plain = " m-link-plain" if c.fs >= 28 else ""  # display-size link (an email, a CTA line): no underline
            return (f'<a href="#" className="n{i} m-link{plain}" data-n="{i}" data-swarm-id="{sid}-link-{i}" data-swarm-role="link">'
                    f'{{{self.js(text, "link")}}}</a>')
        if c.kind == "button" and c.bg is None and c.border == 0:
            # Drawn as plain (often large) text on the reference: a link, not a filled bar.
            self.rule(i, desk)
            text = self.words.take("short", _chars(c))
            return (f'<a href="#" className="n{i} m-link m-link-plain" data-n="{i}" data-swarm-id="{sid}-btn-{i}" data-swarm-role="link">'
                    f'{{{self.js(text, "link")}}}</a>')
        if c.kind == "button":
            desk.update({"border-radius": f"{c.radius}px",
                         "padding": f"{max(12, c.pad[0])}px {max(16, c.pad[1])}px"})
            self.rule(i, desk)
            filled = c.bg is not None and (_lum(c.bg) or 1) < 0.85 and not self.filled
            self.filled = self.filled or filled  # one primary action per section (anti-slop §2.6, QA)
            cls = "btn-primary" if filled else "btn-ghost"
            self.buttons += 1  # the page's two actions first, then short labels: never the same label twice
            text = self.words.take("cta" if self.buttons <= 2 else "short", _chars(c))
            return (f'<a href="#" className="n{i} btn {cls}" data-n="{i}" data-swarm-id="{sid}-btn-{i}" data-swarm-role="button">'
                    f'{{{self.js(text, "button")}}}</a>')
        if c.kind == "input":
            desk["border-radius"] = f"{c.radius}px"
            self.rule(i, desk)
            label = self.js("Email", "label")
            return (f'<label className="n{i} m-field" data-n="{i}"><span className="t-caption">{{{label}}}</span>'
                    f'<input className="input" type="email" autoComplete="email" placeholder="name@example.com" '
                    f'data-swarm-id="{sid}-input-{i}" data-swarm-role="input" /></label>')
        # image
        desk["border-radius"] = f"{c.radius}px"
        self.rule(i, desk)
        if c.w <= 72 and c.h <= 72:
            # A logo / icon slot: a neutral monogram, never a stock photo (the user's own logo goes in public/).
            letter = (self.brand[:1] or "•").upper()
            svg = ("data:image/svg+xml;utf8," + urllib.parse.quote(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
                f'<rect width="64" height="64" rx="14" fill="#1a1a1a"/><text x="32" y="42" font-family="sans-serif" '
                f'font-size="30" font-weight="600" fill="#ffffff" text-anchor="middle">{html.escape(letter)}</text></svg>'))
            return (f'<img className="n{i} m-mark" data-n="{i}" alt={{{self.js(self.brand, "brand")}}} src="{svg}" '
                    f'width={{{round(c.w)}}} height={{{round(c.h)}}} />')
        self.tone += 1
        ratio = f"{max(1, round(c.w))} / {max(1, round(c.h))}"
        alt = self.words.take("short", 20)
        return (f'<div className="n{i} m-media" data-n="{i}"><Art label={{{self.js(alt, "image_alt")}}} ratio="{ratio}" '
                f'tone={{{self.tone}}} sizes="(min-width: 1200px) {round(c.w)}px, 100vw" /></div>')


def inner(node: Node) -> tuple[float, float, float, float]:
    """Span of a container's children (a card's padding box), the container's own box when empty."""
    if not node.children:
        return node.x0, node.y0, node.x1, node.y1
    return (min(c.x0 for c in node.children), min(c.y0 for c in node.children),
            max(c.x1 for c in node.children), max(c.y1 for c in node.children))


def parent_inner_x0(p: Node) -> float:
    return inner(p)[0] if p.kind == "card" else p.x0


def parent_inner_y0(p: Node) -> float:
    return inner(p)[1] if p.kind == "card" else p.y0


def parent_inner_w(p: Node) -> float:
    if p.kind == "card":
        x0, _, x1, _ = inner(p)
        return x1 - x0
    return p.w


def render_measured(section: Section, copy: PageCopy, js) -> tuple[str, str] | None:
    """(inner JSX, CSS) for the section, or None when its layout cannot be rebuilt."""
    box = section.layout_box or {}
    width = float(box.get("width") or 1440)
    height = float(box.get("height") or 0)
    tree = build_tree(comps(section.layout), width)
    if tree is None:
        return None
    if tree.kind not in ("rows", "cols"):
        tree = Node(kind="rows", x0=tree.x0, y0=tree.y0, x1=tree.x1, y1=tree.y1, children=[tree])
    r = _Render(section, copy, js)
    jsx = r.node(tree)
    sel = r.sel
    left = tree.x0 / 1440 * 100
    right = max(0.0, (width - tree.x1)) / 1440 * 100
    top, bottom = round(tree.y0), round(max(0.0, height - tree.y1)) if height else 64
    base = f"""{sel} {{ overflow-x: clip; }}
{sel} .m-rows {{ display: flex; flex-direction: column; align-items: flex-start; gap: 16px; }}
{sel} .m-cols {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 24px; }}
{sel} .m-cols > * {{ flex: 1 1 260px; min-width: 0; }}
{sel} .m-rows > .m-rows, {sel} .m-rows > .m-cols, {sel} .m-rows > .m-card, {sel} .m-rows > .m-media,
{sel} .m-rows > h1, {sel} .m-rows > h2, {sel} .m-rows > h3, {sel} .m-rows > h4, {sel} .m-rows > p {{ align-self: stretch; }}
{sel} .m-card {{ gap: 16px; }}
{sel} .m-media {{ width: 100%; overflow: hidden; }}
{sel} .m-media .art {{ display: block; width: 100%; height: auto; border-radius: inherit; }}
{sel} .m-link {{ display: inline-flex; align-items: center; min-height: 48px; color: inherit; text-decoration: underline;
  text-underline-offset: 4px; transition: opacity var(--duration) var(--ease); }}
{sel} .m-link:hover {{ opacity: 0.72; }}
{sel} .m-nav {{ text-decoration: none; }}
{sel} .btn-ghost:hover {{ background: color-mix(in oklch, currentColor 10%, transparent); }}
{sel} .m-mark {{ display: block; width: 40px; height: auto; }}
{sel} .m-link-plain {{ text-decoration: none; font-family: var(--font-heading); line-height: 1.1; }}
{sel} .m-link:focus-visible, {sel} .btn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
{sel} .m-field {{ display: flex; flex-direction: column; gap: 8px; }}
{sel} .m-layer {{ display: flex; flex-direction: column; gap: 24px; }}
{sel} .m-layer > :first-child {{ position: relative; z-index: 1; }}
{sel} .m-panel {{ min-height: 120px; border-radius: var(--radius-md); background: var(--bg-surface); }}
{DESKTOP} {{
  {sel}.s {{ padding-top: {top}px; padding-bottom: {bottom}px; }}
  {sel} > .container {{ max-width: none; padding-left: {left:.3f}vw; padding-right: {right:.3f}vw; }}
  {sel} .m-rows, {sel} .m-cols {{ gap: 0; }}
  {sel} .m-cols {{ flex-wrap: nowrap; }}
{chr(10).join(r.css)}
}}"""
    return jsx, base


def measured_interactive(section: Section) -> list[tuple[str, str, str]]:
    """The controls a measured section will have (for PLAN.md): (id, role, behaviour)."""
    tree = build_tree(comps(section.layout), float((section.layout_box or {}).get("width") or 1440))
    if tree is None:
        return []
    out, n = [], 0

    def walk(node: Node) -> None:
        nonlocal n
        i = n
        n += 1
        for c in node.children:
            walk(c)
        if node.kind == "button":
            out.append((f"{section.id}-btn-{i}", "button", "action like the reference's button"))
        elif node.kind == "link":
            out.append((f"{section.id}-link-{i}", "link", "link like the reference's"))
        elif node.kind == "input":
            out.append((f"{section.id}-input-{i}", "input", "email field"))
    walk(tree if tree.kind in ("rows", "cols") else Node(kind="rows", x0=0, y0=0, x1=1, y1=1, children=[tree]))
    return out
