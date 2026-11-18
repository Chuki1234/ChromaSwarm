"""Clone: rebuild a section's layout from the reference's own components instead of a template.

The reader measured every smallest piece of the reference section (clone/components.py: kind, box,
computed style). This module turns those boxes back into a layout tree a browser can flow:

1. containment — every component inside a card (≥85% of its area) becomes that card's child;
2. recursive XY-cut — siblings are split into rows wherever a horizontal band of empty space crosses
   all of them, otherwise into columns wherever a vertical band does; boxes that cannot be cut
   (text laid over a picture) fall back to reading order;
3. each node keeps its measured span, so the desktop CSS can put every row / column / leaf where it was
   (left offset and width as % of the parent, vertical gaps in px), while phones get a plain stack.

No text or image of the reference is involved: leaves are filled with the page's own sample copy of the
same length (developer/measured.py).
"""

from __future__ import annotations

from pydantic import BaseModel

from chromaswarm.clone.components import Comp

MIN_GAP = 4  # px of empty space that separates two rows / columns


class Node(BaseModel):
    # "rows" | "cols" | "card" | "layer" (first child flows, the "back-*" children sit behind it at their
    # measured place) | leaf kind (heading, text, link, button, image, input)
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    comp: Comp | None = None  # leaves and cards
    children: list["Node"] = []

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


def _leaf(c: Comp) -> Node:
    return Node(kind=c.kind, x0=c.x, y0=c.y, x1=c.x + c.w, y1=c.y + c.h, comp=c)


def _span(nodes: list[Node]) -> tuple[float, float, float, float]:
    return (min(n.x0 for n in nodes), min(n.y0 for n in nodes), max(n.x1 for n in nodes), max(n.y1 for n in nodes))


def _inside(inner: Comp, outer: Comp) -> bool:
    ix = max(0, min(inner.x + inner.w, outer.x + outer.w) - max(inner.x, outer.x))
    iy = max(0, min(inner.y + inner.h, outer.y + outer.h) - max(inner.y, outer.y))
    return inner.w * inner.h > 0 and ix * iy >= 0.85 * inner.w * inner.h


def clean(comps: list[Comp], width: float) -> list[Comp]:
    """Drop what cannot be laid out: off-section boxes, exact duplicates, images inside images."""
    out: list[Comp] = []
    seen: set[tuple] = set()
    for c in sorted(comps, key=lambda c: (c.y, c.x)):
        if c.w < 8 or c.h < 8 or c.x + c.w <= 0 or c.x >= width:
            continue
        key = (c.kind, c.x // 4, c.y // 4, c.w // 4, c.h // 4)
        if key in seen:
            continue
        seen.add(key)
        if c.kind == "image" and any(o.kind == "image" and _inside(c, o) for o in out):
            continue
        out.append(c.model_copy(update={"x": max(0, c.x), "w": min(c.w, width - max(0, c.x))}))
    return out


def _contain(comps: list[Comp]) -> list[Node]:
    """Top-level nodes: cards hold the components inside them (smallest card wins)."""
    cards = sorted([c for c in comps if c.kind == "card"], key=lambda c: c.w * c.h)
    owner: dict[int, int] = {}
    for i, c in enumerate(comps):
        for j, card in enumerate(cards):
            # A picture that fills its frame is the same size as the card (or a hair larger): still its child.
            if card is c or (c.kind == "card" and card.w * card.h <= c.w * c.h) or card.w * card.h < 0.9 * c.w * c.h:
                continue
            if _inside(c, card):
                owner[i] = j
                break
    nodes: dict[int, Node] = {}
    for j, card in enumerate(cards):
        nodes[j] = Node(kind="card", x0=card.x, y0=card.y, x1=card.x + card.w, y1=card.y + card.h, comp=card)
    top: list[Node] = []
    # Cards nest too: a card inside a bigger card is that card's child.
    for j, card in enumerate(cards):
        parent = next((k for k in range(j + 1, len(cards)) if _inside(card, cards[k])), None)
        (nodes[parent].children if parent is not None else top).append(nodes[j])
    for i, c in enumerate(comps):
        if c.kind == "card":
            continue
        (nodes[owner[i]].children if i in owner else top).append(_leaf(c))
    return top


def _groups(nodes: list[Node], axis: str) -> list[list[Node]]:
    """Split along y ("rows") or x ("cols") wherever empty space crosses every node."""
    lo, hi = ("y0", "y1") if axis == "rows" else ("x0", "x1")
    ordered = sorted(nodes, key=lambda n: getattr(n, lo))
    groups: list[list[Node]] = [[ordered[0]]]
    end = getattr(ordered[0], hi)
    for n in ordered[1:]:
        if getattr(n, lo) >= end + MIN_GAP - 1e-6 or (getattr(n, lo) >= end - 2 and axis == "rows"):
            groups.append([n])
        else:
            groups[-1].append(n)
        end = max(end, getattr(n, hi))
    return groups


def _grid(nodes: list[Node]) -> list[list[Node]] | None:
    """Rows of similar tiles grouped by their centre line (tolerance: half a tile), when every row is a clean
    left-to-right sequence. None when the nodes are not tiles."""
    if len(nodes) < 3:
        return None
    hs = sorted(n.h for n in nodes)
    med = hs[len(hs) // 2]
    if any(n.h > med * 2.2 or n.h < med * 0.4 for n in nodes):
        return None
    rows: list[list[Node]] = []
    for n in sorted(nodes, key=lambda n: (n.y0 + n.y1) / 2):
        mid = (n.y0 + n.y1) / 2
        if rows and abs(mid - sum((m.y0 + m.y1) / 2 for m in rows[-1]) / len(rows[-1])) <= med * 0.5:
            rows[-1].append(n)
        else:
            rows.append([n])
    if len(rows) == len(nodes):
        return None  # one per row: nothing tiles side by side
    for row in rows:
        row.sort(key=lambda n: n.x0)
        if any(b.x0 < a.x0 + a.w * 0.5 for a, b in zip(row, row[1:])):
            return None  # really stacked on top of each other, not tiles
    return rows


def cut(nodes: list[Node], depth: int = 0) -> Node:
    """Recursive XY-cut of sibling nodes into a rows / cols tree."""
    if len(nodes) == 1:
        n = nodes[0]
        if n.kind == "card" and n.children:
            inner = cut(n.children, depth + 1)
            n.children = inner.children if inner.kind == "rows" else [inner]
        return n
    x0, y0, x1, y1 = _span(nodes)
    for axis in ("rows", "cols"):
        groups = _groups(nodes, axis)
        if len(groups) > 1 and depth < 12:
            return Node(kind=axis, x0=x0, y0=y0, x1=x1, y1=y1, children=[cut(g, depth + 1) for g in groups])
    # Text laid over a picture: the pictures become a back layer at their measured place, the rest is cut
    # again and flows on top.
    back = [n for n in nodes if n.kind == "image" or (n.kind == "card" and not n.children)]
    front = [n for n in nodes if n not in back]
    if back and front:
        flow = cut(front, depth + 1)
        for b in back:
            b.kind = "back-" + b.kind
        return Node(kind="layer", x0=x0, y0=y0, x1=x1, y1=y1, children=[flow, *back])
    # Tiles that overlap a little (rotated / offset cards on a canvas): rows by centre line, then columns.
    grid = _grid(nodes)
    if grid:
        return Node(kind="rows", x0=x0, y0=y0, x1=x1, y1=y1,
                    children=[Node(kind="cols", **dict(zip(("x0", "y0", "x1", "y1"), _span(row))),
                                   children=[cut([n], depth + 1) for n in sorted(row, key=lambda n: n.x0)])
                              if len(row) > 1 else cut(row, depth + 1) for row in grid])
    # Anything else that overlaps: reading order, each keeps its own box.
    ordered = sorted(nodes, key=lambda n: (n.y0, n.x0))
    return Node(kind="rows", x0=x0, y0=y0, x1=x1, y1=y1, children=[cut([n], depth + 1) for n in ordered])


def build_tree(comps: list[Comp], width: float = 1440) -> Node | None:
    """The section's layout tree, or None when there is nothing to lay out."""
    kept = clean(comps, width)
    if not kept:
        return None
    return cut(_contain(kept))


def leaves(node: Node) -> list[Node]:
    if node.kind in ("rows", "cols", "layer") or (node.kind == "card" and node.children):
        out = [node] if node.kind == "card" else []
        for c in node.children:
            out += leaves(c)
        return out
    return [node]


def usable(comps: list[Comp]) -> bool:
    """Worth rebuilding from components: a few real pieces, not a wall of hundreds."""
    real = [c for c in comps if c.kind != "card"]
    return 2 <= len(real) <= 48 and any(c.kind in ("heading", "text", "image", "button") for c in real)
