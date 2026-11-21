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
import re
import itertools
import urllib.parse

from chromaswarm.agents.planner import Section
from chromaswarm.clone.components import Comp, comps
from chromaswarm.clone.layout import Node, build_tree
from chromaswarm.developer.content import PageCopy
from chromaswarm.engines.color import OKLCH, apca_lc, oklch_to_srgb, parse_css_color, srgb_to_oklch, wcag_contrast, wcag_luminance

# Structures whose behaviour a static layout cannot carry keep their template.
TEMPLATE_ONLY = {"accordion", "horizontal-scroller", "list-rows", "logo-strip",
                 "picker-recommend", "announcement-bar", "inline-controls"}
DESKTOP = "@media (min-width: 1200px)"
# A picture the rebuild does not have (a product screenshot, a 3D scene) keeps its place and width as a skeleton,
# but no taller than this: a 600-800px grey slab reads as an empty page, not as "a picture goes here".
SKEL_MAX = 360
# Labels this small inside such a picture are part of it (an app screenshot's own UI), not the page's copy.
MOCKUP_LABEL_FS = 20


def _inside(c: Comp, box: Comp) -> bool:
    cx, cy = c.x + c.w / 2, c.y + c.h / 2
    return box.x <= cx <= box.x + box.w and box.y <= cy <= box.y + box.h


def _alpha(color: str | None) -> float:
    parsed = parse_css_color(color or "")
    return parsed[1] if parsed else 1.0


def drop_faint_type(pieces: list[Comp]) -> list[Comp]:
    """Giant, almost transparent type (a brand name at 4% behind a footer): decoration, not copy. The CloneSpec
    marks it `skip` — rebuilt, the contrast guard would turn it into a huge solid "[Your name]"."""
    return [c for c in pieces if not (c.kind in ("heading", "text") and c.fs >= 120 and _alpha(c.color) <= 0.15)]


def drop_picture_labels(pieces: list[Comp], width: float, height: float, has_photos: bool) -> list[Comp]:
    """Small text sitting on a big picture that becomes a skeleton: the picture's own UI labels (Linear's app
    screenshot: "Planning", "Roadmaps", "99.9%"…), and the window / panel frames (cards) drawn inside it.
    Without the picture they would float on an empty grey box (a 700px empty card), so they go with it.
    Display type (a headline over the picture) stays; a picture covering the whole section (a background)
    keeps everything over it."""
    if has_photos:
        return pieces
    big = [c for c in pieces if c.kind == "image" and c.w >= 400 and c.h >= 250
           and not (c.w >= 0.9 * width and height and c.h >= 0.8 * height)]
    if not big:
        return pieces
    def part_of_picture(c: Comp) -> bool:
        if c.kind in ("text", "link", "heading", "button"):
            return c.fs <= MOCKUP_LABEL_FS and any(_inside(c, b) for b in big)
        if c.kind == "card":
            return any(_inside(c, b) and c.w * c.h <= 1.1 * b.w * b.h for b in big)
        return False
    return [c for c in pieces if not part_of_picture(c)]


def measurable(section: Section) -> bool:
    if not section.layout:
        return False
    # An accordion keeps its own look too: its rows (cards) open and close for real (<details>).
    return section.structure == "accordion" or section.structure not in TEMPLATE_ONLY


def _key(text: str) -> str:
    """A line by how it starts (a cut copy of a sentence is the same sentence)."""
    return " ".join(text.lower().split())[:28]


def _fill_in(text: str) -> bool:
    """A fill-in mark of the template ("[Your name]", "[Headline: …]"): shown once, where it belongs."""
    return text.lstrip().startswith("[")


class _Words:
    """Sample copy for one measured section, chosen by role and length, page-wide without repeats.

    * by role: the hero's first heading is the page headline and its first paragraph the subhead; a closing
      section's first heading is the closing line; an accordion asks the FAQ questions. Everywhere else
      headings come from the feature / story titles, never an FAQ question or a call to contact;
    * page-wide: lines earlier sections already show (`PageCopy.taken`) are skipped until a pool runs out;
    * fill-in marks ("[…]") appear only in their own role, never as filler elsewhere.
    """

    def __init__(self, c: PageCopy, structure: str = "", sid: str = ""):
        self.c = c
        features = [*[t for t, _ in c.story], *[i.name for i in c.cards], *[i.name for i in c.items]]
        faqs = [q for q, _ in c.faqs]
        if structure.startswith(("split-7-5", "hero", "full-bleed-image")) or sid == "hero":
            self.role = "hero"
        elif structure in ("closing-cta", "full-bleed-band") or sid.startswith("closing"):
            self.role = "closing"
        elif structure == "accordion":
            self.role = "faq"
        else:
            self.role = ""
        heads = faqs + features if self.role == "faq" else features
        # (tab panels' sample text only in tabs: it is generic product-page copy elsewhere)
        body = [*[t for _, t in c.story], *[i.note for i in c.cards if i.note],
                *([t for _, t in c.tabs] if structure == "tabs" else []), c.footer_line,
                *([a for _, a in c.faqs] if self.role == "faq" else []), *[i.note for i in c.items if i.note]]
        # Labels: the site's short words, repeated when the page has more labels than words. Feature titles are
        # the headings' and are never spent on labels (a page has ~10 headings but ~80 small labels).
        short = [c.cta_secondary, *c.nav, *c.categories, *[t for t, _ in c.facts]]

        def clean(v: list[str], *fallback: str) -> list[str]:
            out = list(dict.fromkeys(x for x in v if x and not _fill_in(x)))
            return out or list(dict.fromkeys(x for x in fallback if x)) or ["—"]

        self.lists = {"head": clean(heads, c.closing, c.headline), "body": clean(body, c.subhead),
                      "short": clean(short, c.cta_secondary)}
        # One set for all kinds (a heading never comes back as a label), keyed by how a line starts: a sentence
        # cut to the reference's length on an earlier section still counts as shown.
        self.used: set[str] = {_key(t) for t in c.taken}
        self.firsts: set[str] = set()
        self.cta = itertools.cycle([c.cta, c.cta_secondary])

    def _free(self, kind: str) -> list[str]:
        free = [x for x in self.lists[kind] if _key(x) not in self.used]
        if not free:  # the pool ran out: start it again (a repeat beats an empty block)
            self.used -= {_key(x) for x in self.lists[kind]}
            free = list(self.lists[kind])
        return free

    def _use(self, line: str) -> None:
        self.used.add(_key(line))

    def _role_line(self, kind: str) -> str | None:
        """The section's own line for its first heading / paragraph (hero, closing)."""
        if kind in self.firsts:
            return None
        self.firsts.add(kind)
        line = {("hero", "head"): self.c.headline, ("hero", "body"): self.c.subhead,
                ("closing", "head"): self.c.closing}.get((self.role, kind))
        if line and _key(line) not in self.used:
            self._use(line)
            return line
        return None

    def _closest(self, kind: str, chars: int) -> str:
        """The unused line whose length is closest to the reference's (headings and labels are one line,
        never several glued together)."""
        best = min(self._free(kind), key=lambda x: abs(len(x) - chars))
        self._use(best)
        if len(best) > chars * 1.6 and chars >= 6 and not _fill_in(best):
            cut = best[: int(chars * 1.2)].rsplit(" ", 1)[0].rstrip(",;:—-")
            best = cut if len(cut) >= 3 else best
        return best

    def take(self, kind: str, chars: int) -> str:
        if kind == "cta":
            return next(self.cta)
        if kind in ("head", "body") and (line := self._role_line(kind)):
            return line
        if kind in ("head", "short"):
            return self._closest(kind, chars)
        # Body: whole unused sentences, joined until the reference's length is reached.
        parts: list[str] = []
        while sum(len(p) + 1 for p in parts) < chars * 0.8 and len(parts) < 6:
            free = self._free("body")
            nxt = next((x for x in free if x not in parts), None)
            if nxt is None:
                break
            parts.append(nxt)
            self._use(nxt)
        text = " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in parts[:-1]) + (" " if len(parts) > 1 else "") + parts[-1]
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


def _over(fg: tuple, bg: OKLCH) -> OKLCH:
    """A translucent colour composited over its background (what the eye sees)."""
    colour, alpha = fg
    if alpha >= 0.99:
        return colour
    a, b = oklch_to_srgb(colour), oklch_to_srgb(bg)
    return srgb_to_oklch(tuple(x * alpha + y * (1 - alpha) for x, y in zip(a, b)))


def _type_class(c: Comp) -> str:
    if c.kind == "heading":
        return "t-display" if c.fs >= 56 else "t-h1" if c.fs >= 40 else "t-h2" if c.fs >= 28 else "t-h3" if c.fs >= 21 else "t-h4"
    return "t-caption" if c.fs < 15 else "t-lead" if c.fs >= 19 else "t-body"


class _Render:
    def __init__(self, section: Section, copy: PageCopy, js):
        self.s, self.js = section, js
        self.words = _Words(copy, section.structure, section.id)
        self.n = 0
        self.css: list[str] = []
        self.sel = f'[data-swarm-section="{section.id}"]'
        self.has_h1 = False
        self.paints: list[str] = []
        box = section.layout_box or {}
        self.bgs: list[str | None] = [box.get("bg") or box.get("page")]  # what is painted beneath, innermost last
        self.nav = list(copy.nav_links) if section.structure == "sticky-bar" else []
        self.links = [dict(x) for x in section.links]  # CloneSpec: where each reference control leads
        self.brand = copy.brand or ""
        self.has_photos = bool(copy.images)  # the user's own (B4 uploads / owned site): otherwise skeletons
        self.buttons = 0
        self.elastic: set[int] = set()
        self.tone = 0
        texts = [x for x in comps(section.layout) if x.kind == "heading"] or [x for x in comps(section.layout) if x.kind == "text"]
        self.ink = _lum(texts[0].color) if texts else None

    def readable(self, fg: str | None, bg: str | None, large: bool) -> bool:
        """The measured colour is used only where it still reads on what this rebuild paints beneath it
        (white words over a photo on the reference would vanish on our light section)."""
        if not fg or not bg:
            return False
        f, b = parse_css_color(fg), parse_css_color(bg)
        if not f or not b or f[1] < 0.35:
            return False
        seen = _over(f, b[0])
        return (wcag_contrast(seen, b[0]) >= (3.0 if large else 4.5)
                and abs(apca_lc(seen, b[0])) >= (45 if large else 60))  # QA checks both (standards §2.1)

    def ink_for(self, bg: str | None) -> str:
        """Black or white, whichever reads on this background (when the measured colour does not)."""
        b = parse_css_color(bg or "") if bg else None
        if not b:
            return ""
        dark, light = parse_css_color("#111111")[0], parse_css_color("#ffffff")[0]
        return "#111111" if wcag_contrast(dark, b[0]) >= wcag_contrast(light, b[0]) else "#ffffff"

    def paint(self, i: int, props: dict[str, str]) -> None:
        """The reference's own colours, at every width (layout is desktop-only, colour is not)."""
        props = {k: v for k, v in props.items() if v}
        if props:
            self.paints.append(f"{self.sel} .n{i} {{ " + " ".join(f"{k}: {v};" for k, v in props.items()) + " }")

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
        # Centred on the reference (a closing line, a footer heading): centred here too, whatever its length.
        pcx = parent_inner_x0(parent) + pw / 2
        if axis == "rows" and node.w < pw * 0.8 and abs((node.x0 + node.x1) / 2 - pcx) < pw * 0.02:
            props.update({"margin-left": "auto", "margin-right": "auto", "align-self": "center"})
            if c is not None:  # containers centre as blocks only: their children decide their own alignment
                props["text-align"] = "center"  # Clone keeps centred copy centred (QA's house rule is waived there)
                if one_line:
                    props["white-space"] = "nowrap"
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
            # Pictures behind become skeletons no taller than SKEL_MAX: the layer only needs to reach their end.
            reach = [round(b.y1 - node.y0) if b.comp is None or self.covers(b.comp) or b.kind == "back-card"
                     or self.picture_label(b.comp) is None
                     else round(b.y0 - node.y0) + min(SKEL_MAX, round(b.comp.h)) for b in back]
            desk.update({"position": "relative", "min-height": f"{min(round(node.h), max(reach, default=round(node.h)))}px"})
            self.rule(i, desk)
            body = "\n".join(parts)
            return f'<div className="n{i} m-layer" data-n="{i}">\n{body}\n</div>'
        if node.kind in ("rows", "cols", "card"):
            inner_axis = "cols" if node.kind == "cols" else "rows"
            card_bg = node.comp.bg if node.kind == "card" and node.comp and node.comp.bg else None
            if card_bg:
                self.bgs.append(card_bg)
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
            if card_bg:
                self.bgs.pop()
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
                self.paint(i, {"background": c.bg or "transparent"})
                if self.s.structure == "accordion" and node.children:
                    # A question row of the reference, closed like it; the answer (sample) opens below it.
                    answer = self.js(self.words.take("body", 140), "answer")
                    return (f'<details className="n{i} card m-card m-acc" data-n="{i}">\n'
                            f'<summary data-swarm-id="{self.s.id}-item-{i}" data-swarm-role="button">\n{body}\n</summary>\n'
                            f'<p className="t-body m-answer">{{{answer}}}</p>\n</details>')
                return f'<div className="n{i} card m-card" data-n="{i}">\n{body}\n</div>'
            desk["gap"] = "0"
            self.rule(i, desk)
            cls = "m-cols" if node.kind == "cols" else "m-rows"
            return f'<div className="n{i} {cls}" data-n="{i}">\n{body}\n</div>'
        return self.leaf(node, i, desk)

    def skeleton_img(self, c: Comp, label: str = "") -> str:
        """An exact-size placeholder for a picture the rebuild does not have (translucent grey: reads on any
        background, never a stand-in photo)."""
        w, h = max(1, round(c.w)), min(SKEL_MAX, max(1, round(c.h)))
        text = (f'<text x="{w / 2:.0f}" y="{h / 2 + 6:.0f}" font-family="sans-serif" font-size="16" fill="#808080" '
                f'text-anchor="middle">{label}</text>') if label else ""
        svg = ("data:image/svg+xml;utf8," + urllib.parse.quote(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" rx="{c.radius}" fill="#808080" fill-opacity="0.16"/>{text}</svg>'))
        return f'<img alt="" src="{svg}" width={{{w}}} height={{{h}}} style={{{{ width: "100%", height: "auto" }}}} />'

    def href(self, c: Comp) -> str:
        """Where this control leads, as the CloneSpec decided (Section.links): the matching control of the
        reference — same place (centres within 32px) and about the same size. '#' when none matches."""
        cx, cy = c.x + c.w / 2, c.y + c.h / 2
        best, dist = None, 1e9
        for link in self.links:
            lx, ly = link.get("x", 0) + link.get("w", 0) / 2, link.get("y", 0) + link.get("h", 0) / 2
            d = abs(lx - cx) + abs(ly - cy)
            if d <= 32 and d < dist and abs(link.get("w", 0) - c.w) <= max(40, c.w * 0.6):
                best, dist = link, d
        if best is not None:
            self.links.remove(best)  # one reference control per rendered one
        href = (best or {}).get("href") or "#"
        return '"#"' if href == "#" else "{" + self.js(href, "href") + "}"

    def covers(self, c: Comp) -> bool:
        """The picture covers the whole section on the reference (a background texture / photo)."""
        box = self.s.layout_box or {}
        return c.w >= 0.9 * float(box.get("width") or 1440) and c.h >= 0.8 * float(box.get("height") or 1)

    def picture_label(self, c: Comp) -> str | None:
        """None: use the user's photo (Art). Otherwise the skeleton's label ("" = none)."""
        if c.media == "canvas":
            return "3D"
        if c.media == "video":
            return "Video"
        return None if self.has_photos else ""

    def back(self, node: Node, layer: Node) -> str:
        """A picture behind the layer's flowing content, at its measured place (desktop)."""
        i = self.n
        self.n += 1
        c = node.comp
        assert c is not None
        if self.covers(c):
            # Covering the whole section on the reference (a background texture / photo): a faint frame only,
            # the section's own measured colour shows through instead of a stand-in picture.
            self.rule(i, {"position": "absolute", "z-index": "0", "margin": "0", "inset": "0", "width": "100%", "height": "100%"})
            return f'<div className="n{i} m-back m-bgframe" data-n="{i}" aria-hidden="true" />'

        lw = max(layer.w, 1)
        self.rule(i, {"position": "absolute", "z-index": "0", "margin": "0",
                      "left": f"{(node.x0 - layer.x0) / lw * 100:.3f}%", "top": f"{round(node.y0 - layer.y0)}px",
                      "width": f"{node.w / lw * 100:.3f}%", "border-radius": f"{c.radius}px"})
        if node.kind == "back-card":
            return f'<div className="n{i} m-back m-panel" data-n="{i}" aria-hidden="true" />'
        label = self.picture_label(c)
        if label is not None:
            return f'<div className="n{i} m-back m-media m-skel" data-n="{i}">{self.skeleton_img(c, label)}</div>'
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
            # The reference's own type, as measured (Clone keeps its weights and sizes, decision 11).
            desk.update({"font-size": f"{c.fs:g}px", "font-weight": f"{round(c.fw / 100) * 100:.0f}", "max-width": "none"})
            if abs(c.ls) > 0.05:
                desk["letter-spacing"] = f"{c.ls:g}px"
            if c.lh and c.kind != "button":
                desk["line-height"] = f"{c.lh:g}"
            if c.tt:
                desk["text-transform"] = c.tt
            if c.kind != "button":
                large = c.fs >= 24 or (c.fs >= 18.6 and c.fw >= 700)
                self.paint(i, {"color": c.color if self.readable(c.color, self.bgs[-1], large) else self.ink_for(self.bgs[-1])})
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
            return (f'<a href={self.href(c)} className="n{i} m-link{plain}" data-n="{i}" data-swarm-id="{sid}-link-{i}" data-swarm-role="link">'
                    f'{{{self.js(text, "link")}}}</a>')
        if c.kind == "button" and c.bg is None and c.border == 0:
            # Drawn as plain (often large) text on the reference: a link, not a filled bar.
            self.rule(i, desk)
            text = self.words.take("short", _chars(c))
            return (f'<a href={self.href(c)} className="n{i} m-link m-link-plain" data-n="{i}" data-swarm-id="{sid}-btn-{i}" data-swarm-role="link">'
                    f'{{{self.js(text, "link")}}}</a>')
        if c.kind == "button":
            # Desktop: the reference's own size (tap targets are checked on phones, where .btn keeps 48px).
            desk.update({"border-radius": f"{c.radius}px", "padding": f"{c.pad[0]}px {c.pad[1]}px", "min-height": "24px"})
            self.rule(i, desk)
            cls = "btn-primary" if c.bg is not None else "btn-ghost"
            fill = c.bg or self.bgs[-1]
            if self.readable(c.color, fill, c.fs >= 24):
                self.paint(i, {"background": c.bg or "transparent", "color": c.color,
                               "border-color": f"color-mix(in oklch, {c.color} 35%, transparent)" if c.border and not c.bg else ""})
            self.buttons += 1  # the page's two actions first, then short labels: never the same label twice
            text = self.words.take("cta" if self.buttons <= 2 else "short", _chars(c))
            return (f'<a href={self.href(c)} className="n{i} btn {cls}" data-n="{i}" data-swarm-id="{sid}-btn-{i}" data-swarm-role="button">'
                    f'{{{self.js(text, "button")}}}</a>')
        if c.kind == "input":
            desk["border-radius"] = f"{c.radius}px"
            self.rule(i, desk)
            if ink := self.ink_for(self.bgs[-1]):  # field, label and border read on whatever is painted beneath
                self.paints.append(f"{self.sel} .n{i}, {self.sel} .n{i} .input {{ color: {ink}; }} "
                                   f"{self.sel} .n{i} .input {{ background: transparent; border-color: {ink}; }}")
            label = self.js("Email", "label")
            return (f'<label className="n{i} m-field" data-n="{i}"><span className="t-caption">{{{label}}}</span>'
                    f'<input className="input" type="email" autoComplete="email" placeholder="name@example.com" '
                    f'data-swarm-id="{sid}-input-{i}" data-swarm-role="input" /></label>')
        # image
        desk["border-radius"] = f"{c.radius}px"
        self.rule(i, desk)
        if c.w <= 120 and c.h <= 72:
            # A logo / icon slot (proprietary on the reference): a skeleton of its exact measured size, never a
            # stand-in picture. Translucent grey reads on light and dark sections alike; the user's logo goes in public/.
            w, h = max(1, round(c.w)), max(1, round(c.h))
            svg = ("data:image/svg+xml;utf8," + urllib.parse.quote(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
                f'<rect width="{w}" height="{h}" rx="{min(8, h // 4)}" fill="#808080" fill-opacity="0.28"/></svg>'))
            return (f'<img className="n{i} m-mark m-skel" data-n="{i}" alt={{{self.js(self.brand or "Logo", "brand")}}} src="{svg}" '
                    f'width={{{w}}} height={{{h}}} />')
        label = self.picture_label(c)
        if label is not None:
            # A 3D scene / video, or a picture the user has not brought yet: an exact-size skeleton holds its place
            # (how a 3D scene moves is in the analysis and the effect report).
            return f'<div className="n{i} m-media m-skel" data-n="{i}">{self.skeleton_img(c, label)}</div>'
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
    pieces = drop_faint_type(drop_picture_labels(comps(section.layout), width, height, bool(copy.images)))
    tree = build_tree(pieces, width)
    if tree is None:
        return None
    if tree.kind not in ("rows", "cols"):
        tree = Node(kind="rows", x0=tree.x0, y0=tree.y0, x1=tree.x1, y1=tree.y1, children=[tree])
    r = _Render(section, copy, js)
    jsx = r.node(tree)
    sel = r.sel
    paint_jsx, paint_css = paint_layers(section, sel)
    jsx = paint_jsx + jsx
    left = tree.x0 / 1440 * 100
    right = max(0.0, (width - tree.x1)) / 1440 * 100
    top, bottom = round(tree.y0), round(max(0.0, height - tree.y1)) if height else 64
    # A dark band (or a light one on a dark page): everything inside takes its colours from the band.
    band_css = (f"""{sel}.s-band .muted {{ color: color-mix(in oklch, currentColor 78%, transparent); }}
{sel}.s-band .btn-primary {{ background: var(--band-action); color: var(--band-action-fg); }}
{sel}.s-band .btn-ghost {{ color: inherit; border-color: currentColor; }}
{sel}.s-band .m-card, {sel}.s-band .m-panel {{ background: color-mix(in oklch, currentColor 8%, transparent);
  border-color: color-mix(in oklch, currentColor 20%, transparent); color: inherit; }}
{sel}.s-band .input {{ background: transparent; color: inherit; border-color: currentColor; }}
""" if box.get("band") else "")
    section_bg = f"{sel}.s {{ background: {box['bg']}; }}\n" if box.get("bg") else ""
    if box.get("overlay"):
        # Floats over the section below, as on the reference: it takes no room, the next section starts under it.
        section_bg += (f"{sel}.s {{ position: fixed !important; top: {round(box.get('top', 0))}px; left: 0; right: 0; "
                       f"z-index: 40; }}\n")
    base = f"""{sel} {{ overflow-x: clip; }}
{sel} .m-rows {{ display: flex; flex-direction: column; align-items: flex-start; gap: 16px; }}
{sel} .m-cols {{ display: flex; flex-wrap: wrap; align-items: flex-start; gap: 24px; }}
{sel} .m-cols > * {{ flex: 1 1 260px; min-width: 0; }}
{sel} .m-rows > .m-rows, {sel} .m-rows > .m-cols, {sel} .m-rows > .m-card, {sel} .m-rows > .m-media,
{sel} .m-rows > h1, {sel} .m-rows > h2, {sel} .m-rows > h3, {sel} .m-rows > h4, {sel} .m-rows > p {{ align-self: stretch; }}
{sel} .m-card {{ gap: 16px; }}
{sel} .m-media {{ width: 100%; overflow: hidden; }}
{sel} .m-media .art {{ display: block; width: 100%; height: auto; border-radius: inherit; }}
{sel} .btn:hover {{ filter: brightness(0.92); }}
{sel} .m-link {{ min-height: 24px; }}  /* WCAG 2.2 AA target size; a tiny link must stay under the pointer */
@media (max-width: 767px) {{ {sel} .m-link, {sel} .btn {{ min-height: 48px; }} }}  /* after it: phones need 48px (QA) */
{sel} .m-link {{ display: inline-flex; align-items: center; color: inherit; text-decoration: underline;
  text-underline-offset: 4px; transition: opacity var(--duration) var(--ease); }}
{sel} .m-link:hover {{ opacity: 0.72; }}
{sel} .m-nav {{ text-decoration: none; }}
{sel} .btn-ghost:hover {{ background: color-mix(in oklch, currentColor 10%, transparent); }}
{sel} .m-mark {{ display: block; max-width: 100%; height: auto; }}
{sel} .m-link-plain {{ text-decoration: none; font-family: var(--font-heading); line-height: 1.1; }}
{sel} .m-link:focus-visible, {sel} .btn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
{sel} .m-field {{ display: flex; flex-direction: column; gap: 8px; }}
{sel} .m-acc > summary {{ display: flex; flex-direction: column; list-style: none; cursor: pointer; border-radius: inherit;
  transition: opacity var(--duration) var(--ease); }}
{sel} .m-acc > summary::-webkit-details-marker {{ display: none; }}
{sel} .m-acc > summary:hover {{ opacity: 0.8; }}
{sel} .m-acc > summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
{sel} .m-acc[open] > .m-answer {{ margin-top: 12px; }}
{sel} .m-layer {{ display: flex; flex-direction: column; gap: 24px; }}
{sel} .m-layer > :first-child {{ position: relative; z-index: 1; }}
{sel} .m-panel {{ min-height: 120px; border-radius: var(--radius-md); background: var(--bg-surface); }}
{sel} .m-bgframe {{ background: color-mix(in oklch, currentColor 4%, transparent); pointer-events: none; }}
{band_css}{section_bg}{paint_css}{chr(10).join(r.paints)}
{DESKTOP} {{
  {sel}.s {{ padding-top: {top}px; padding-bottom: {bottom}px; }}
  {sel} > .container {{ max-width: none; padding-left: {left:.3f}vw; padding-right: {right:.3f}vw; }}
  {sel} .m-rows, {sel} .m-cols {{ gap: 0; }}
  /* A row that no longer fits (controls grown to tap-target size, longer sample words) wraps its last piece
     to a new line instead of pushing it off the page, where nobody could reach it. */
  {sel} .m-cols {{ flex-wrap: wrap; }}
{chr(10).join(r.css)}
}}"""
    return jsx, base


def _frame(text: str) -> str:
    """'transform: translateY(540px); opacity: 0' (a keyframe summary of the reference) -> CSS declarations."""
    keep = []
    for part in (text or "").split("; "):
        prop, _, value = part.partition(": ")
        if prop in ("transform", "opacity", "filter") and value and all(ch not in value for ch in "{};<>"):
            keep.append(f"{prop}: {value}")
    return "; ".join(keep)


def paint_layers(section: Section, sel: str) -> tuple[str, str]:
    """Backgrounds the reference paints itself (CloneSpec `background` items: gradients, glows), redrawn as
    decorative layers behind the section's content at their measured place, with their own intro animation
    (e.g. light beams that slide in on load). Decorative only: aria-hidden, no pointer events, reduced-motion safe."""
    if not section.paint:
        return "", ""
    jsx, css = [], [f"{sel}.s {{ position: relative; isolation: isolate; }}",
                    f"{sel} .m-paint {{ position: absolute; z-index: -1; pointer-events: none; }}"]
    for k, layer in enumerate(section.paint[:8]):
        bg = layer.get("css", "")
        if not bg or any(ch in bg for ch in "{};<>") or "url(" in bg:
            continue  # gradients only: never a picture file
        decl = [f"left: {layer['x'] / 1440 * 100:.2f}%", f"top: {round(layer['y'])}px", f"width: {layer['w'] / 1440 * 100:.2f}%",
                f"height: {round(layer['h'])}px", f"background: {bg}"]
        for prop, key in (("filter", "blur"), ("transform", "tf")):
            v = layer.get(key) or ""
            if v and all(ch not in v for ch in "{};<>"):
                decl.append(f"{prop}: {v}")
        if (op := layer.get("opacity")) is not None and op < 1:
            decl.append(f"opacity: {op:g}")
        intro = layer.get("intro")
        if intro and (a := _frame(intro.get("from", ""))) and (b := _frame(intro.get("to", ""))):
            name = f"cs-paint-{section.id}-{k}"
            easing = intro.get("easing") if re.match(r"^(linear|ease(-in|-out|-in-out)?|cubic-bezier\([\d.,\s-]+\))$", intro.get("easing") or "") else "ease-out"
            css.append(f"@keyframes {name} {{ from {{ {a}; }} to {{ {b}; }} }}")
            decl.append(f"animation: {name} {int(intro.get('dur') or 800)}ms {easing} {int(intro.get('delay') or 0)}ms both")
        css.append(f"{sel} .m-paint-{k} {{ {'; '.join(decl)}; }}")
        jsx.append(f'<div className="m-paint m-paint-{k}" aria-hidden="true" />')
    css.append(f"@media (prefers-reduced-motion: reduce) {{ {sel} .m-paint {{ animation: none !important; }} }}")
    return ("\n".join(jsx) + "\n") if jsx else "", "\n".join(css) + "\n"


def measured_interactive(section: Section, has_photos: bool = False) -> list[tuple[str, str, str]]:
    """The controls a measured section will have (for PLAN.md): (id, role, behaviour)."""
    box = section.layout_box or {}
    width, height = float(box.get("width") or 1440), float(box.get("height") or 0)
    tree = build_tree(drop_faint_type(drop_picture_labels(comps(section.layout), width, height, has_photos)), width)
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
