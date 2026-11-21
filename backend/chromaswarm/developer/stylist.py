"""Art director (LLM) for Creative pages: a composition layer written per page, then refined
from the design critic's notes — inside the design system, never around it.

Two jobs, one output format (`app/style.css`, a layer over the templates):
- compose (B10): after the sections are assembled, decide each section's composition for THIS
  brief — asymmetric column spans, which headline leads, spacing rhythm, a focal anchor — so
  two pages built from the same templates stop looking the same;
- refine (B11): after the critic grades the page, turn its "where: problem → fix" notes into
  concrete CSS changes. A change is kept only if Master QA still passes and the score rises.

The model never writes colours, fonts or sizes of its own. `validate_css` keeps only rules
scoped to a section of this page, properties from an allow-list and values that are tokens
(`var(--…)`), keywords, or lengths on the 4/8pt grid. Everything else is dropped and reported.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

log = logging.getLogger(__name__)

MAX_DECLS = 48
MAX_PX = 160

PROPS = {
    # layout
    "display": r"(grid|flex|block|inline-flex|inline-block|contents)",
    "grid-template-columns": None, "grid-template-rows": None, "grid-column": None, "grid-row": None,
    "grid-auto-flow": r"(row|column|dense|row dense|column dense)",
    "gap": None, "row-gap": None, "column-gap": None,
    "align-items": r"(start|end|center|stretch|baseline|flex-start|flex-end)",
    "justify-content": r"(start|end|center|space-between|space-around|flex-start|flex-end)",
    "justify-items": r"(start|end|center|stretch)", "place-items": r"(start|end|center|stretch)( (start|end|center|stretch))?",
    "align-self": r"(start|end|center|stretch|baseline|auto)", "justify-self": r"(start|end|center|stretch|auto)",
    "order": r"-?[0-9]", "flex-direction": r"(row|column|row-reverse|column-reverse)", "flex-wrap": r"(wrap|nowrap)",
    "flex": None, "flex-basis": None,
    # box
    "max-width": None, "min-width": None, "width": None, "min-height": None, "max-height": None,
    "padding": None, "padding-block": None, "padding-inline": None, "padding-top": None, "padding-bottom": None,
    "padding-left": None, "padding-right": None,
    "margin": None, "margin-block": None, "margin-inline": None, "margin-top": None, "margin-bottom": None,
    "margin-left": None, "margin-right": None,
    "aspect-ratio": r"(auto|[0-9]{1,2} ?/ ?[0-9]{1,2})", "object-position": r"(center|top|bottom|left|right)( (center|top|bottom|left|right))?",
    "position": r"(relative|sticky)", "top": None, "z-index": r"[0-9]", "overflow": r"(hidden|visible|clip)",
    # surfaces: hairlines only (colour stays with the Design department's tokens)
    "border": None, "border-top": None,
    "border-bottom": None, "border-left": None, "border-right": None, "border-color": None,
    "border-radius": None, "box-shadow": r"none", "opacity": r"(0\.[3-9][0-9]?|1)",
    # type: scale tokens only
    "font-size": r"var\(--text-[a-z0-9-]+\)", "font-weight": r"(400|500|600|700)",
    "line-height": r"(1(\.[0-9]{1,2})?|2)", "letter-spacing": r"-?0(\.[0-9]{1,3})?em|normal",
    "text-align": r"(left|center|right|start|end)", "text-wrap": r"(balance|pretty|wrap)",
    "text-transform": r"(none|uppercase)", "font-family": r"var\(--font-(heading|body|mono)\)",
}
FORBIDDEN_VALUE = re.compile(r"#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color|url|image-set|expression)\(|"
                             r"!important|\b(red|blue|green|purple|pink|orange|yellow|white|black|gray|grey)\b|"
                             r"linear-gradient|radial-gradient|conic-gradient", re.I)
LENGTH = re.compile(r"(-?\d+(?:\.\d+)?)(px|rem|em|%|ch|vw|vh|fr)?")
SELECTOR = re.compile(r'^\[data-swarm-section="([a-z0-9-]+)"\]([\s>+~.:\w()\[\]="#*-]*)$', re.I)
MEDIA = re.compile(r"^@media \((min|max)-width: ?(\d{3,4})px\)$")


class StylePatch(BaseModel):
    css: str
    notes: list[str] = []
    rejected: list[str] = []


def _value_ok(prop: str, value: str) -> bool:
    if not value or len(value) > 120 or FORBIDDEN_VALUE.search(value) or ";" in value or "{" in value:
        return False
    pattern = PROPS[prop]
    if pattern is not None:
        return re.fullmatch(pattern, value.strip(), re.I) is not None
    # free-form layout values: tokens, keywords, grid functions, 4pt lengths
    rest = re.sub(r"var\(--[a-z0-9-]+\)", "", value)
    rest = re.sub(r"\b(auto|none|0|min-content|max-content|fit-content|span|subgrid|solid|transparent|currentColor|inherit|"
                  r"repeat|minmax|calc|min|max|clamp|auto-fit|auto-fill|1px)\b", "", rest, flags=re.I)
    for m in LENGTH.finditer(rest):
        number, unit = float(m.group(1)), m.group(2)
        if unit == "px" and (abs(number) > MAX_PX or number % 4):
            return False
        if unit in ("rem", "em") and abs(number) > 10:
            return False
    leftover = LENGTH.sub("", rest)
    return re.fullmatch(r"[\s,/()+*-]*", leftover) is not None


def _parse(css: str) -> list[tuple[str | None, str, str]]:
    """(media | None, selector list, body) for every rule; one level of @media."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, i = [], 0
    while i < len(css):
        start = css.find("{", i)
        if start < 0:
            break
        head = css[i:start].strip()
        if head.startswith("@media"):
            depth, j = 1, start + 1
            while j < len(css) and depth:
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
            for _, sel, body in _parse(css[start + 1:j - 1]):
                out.append((head, sel, body))
            i = j
            continue
        end = css.find("}", start)
        if end < 0:
            break
        out.append((None, head, css[start + 1:end]))
        i = end + 1
    return out


# Controls keep the templates' own states (hover / active / focus / disabled): the layer never styles them.
CONTROL = re.compile(r"(\bbutton\b|\.btn|\binput\b|\bselect\b|\btextarea\b|\ba\b(?![-\w])|\.tab\b|\.filter\b|\.icon-btn|"
                     r"\.nav-link|\.link-arrow|:hover|:focus|:active)", re.I)
MULTI_COLUMN = re.compile(r"\b(repeat\(\s*([2-9]|\d{2})|\S+\s+\S+)", re.I)
HEADING = re.compile(r"(\bh[1-4]\b|\.t-(display|h[1-4])|\.section-head|\.eyebrow)", re.I)


def _desktop_only(media: str | None) -> bool:
    m = MEDIA.match(media or "")
    return bool(m and m.group(1) == "min" and int(m.group(2)) >= 768)


def validate_css(css: str, sections: list[str]) -> tuple[str, list[str]]:
    """Only rules this layer may contain; returns (clean css, what was dropped and why)."""
    known, rejected, blocks, count = set(sections), [], [], 0
    for media, selectors, body in _parse(css or ""):
        if media and not MEDIA.match(media):
            rejected.append(f"{media}: chỉ nhận @media (min-width|max-width: Npx)")
            continue
        sels = [x.strip() for x in selectors.split(",") if x.strip()]
        good = []
        for sel in sels:
            m = SELECTOR.match(sel)
            if not m or m.group(1) not in known:
                rejected.append(f"{sel}: selector phải bắt đầu bằng một section của trang")
            elif CONTROL.search(m.group(2)):
                rejected.append(f"{sel}: không chỉnh nút / link / ô nhập (giữ trạng thái hover, focus của template)")
            else:
                good.append(sel)
        if not good:
            continue
        decls = []
        for part in body.split(";"):
            if ":" not in part:
                continue
            prop, value = (x.strip() for x in part.split(":", 1))
            prop = prop.lower()
            if prop not in PROPS:
                rejected.append(f"{prop}: thuộc tính không được phép")
            elif not _value_ok(prop, value):
                rejected.append(f"{prop}: {value[:60]} — giá trị ngoài hệ thiết kế")
            elif prop in ("grid-template-columns", "flex-direction") and not _desktop_only(media) and \
                    (MULTI_COLUMN.search(value) if prop == "grid-template-columns" else value.startswith("row")):
                rejected.append(f"{prop}: {value[:40]} — nhiều cột chỉ trong @media (min-width ≥ 768px), mobile một cột")
            elif prop in ("padding", "padding-inline", "padding-left", "padding-right", "margin-inline") and \
                    (".container" in " ".join(good) or re.fullmatch(r"0(px)?( .*)?", value.strip())):
                rejected.append(f"{prop}: {value[:40]} — không đổi lề trang (gutter ≥ 16px do token quyết định)")
            elif prop in ("grid-column", "grid-row") and "span" in value and not _desktop_only(media):
                rejected.append(f"{prop}: {value[:40]} — ô kéo dài chỉ trong @media (min-width ≥ 768px)")
            elif prop == "text-align" and value.strip() == "center" and not all(HEADING.search(g) for g in good):
                rejected.append("text-align: center — chỉ cho tiêu đề, đoạn văn căn trái")
            elif count < MAX_DECLS:
                decls.append(f"  {prop}: {value};")
                count += 1
        if decls:
            rule = f"{', '.join(good)} {{\n" + "\n".join(decls) + "\n}"
            blocks.append(f"{media} {{\n{rule}\n}}" if media else rule)
    return "\n".join(blocks), rejected


RULES = """Hard rules (anything else is discarded by a validator):
- Every selector starts with [data-swarm-section="<id>"] of a section listed below, then may go down to its
  classes/elements (e.g. [data-swarm-section="hero"] .split, [data-swarm-section="faq"] h2).
- Never set colours or backgrounds (the Design department owns them); borders only as hairlines with
  var(--border-subtle) or var(--border-strong). Sizes ONLY from tokens: font-size: var(--text-display|h1|h2|h3|h4|lead|body|caption),
  radius: var(--radius-sm|md|lg).
- Never style buttons, links, inputs, tabs or :hover/:focus states — they keep the template's states.
- More than one column (and any span) only inside @media (min-width: 1024px); mobile stays one column. Center only headings.
- Never change the page gutters (.container padding) or set horizontal padding to 0.
- Lengths in px are multiples of 4 (8pt grid), at most 160px. No gradients, no shadows, no hex/rgb colours,
  no !important, no animations. One @media level, (min-width: Npx) or (max-width: Npx) only.
- Never hide content, never change text colour contrast, keep touch targets ≥ 48px.
Answer JSON only: {"css": "<css>", "notes": ["<Vietnamese, one line per change: section → what and why>"]}"""

COMPOSE_SYSTEM = f"""You are the art director of a design studio known for Swiss editorial precision. A page has been
assembled from section templates; give it a composition that belongs to THIS brief instead of the template's
default: one asymmetric focal anchor, a clear reading order (what is seen 1st, 2nd, 3rd), varied rhythm
between sections (not every section the same width and spacing), the main action obvious within 3 seconds.
Change at most 6 sections, with restraint: fewer, decisive changes beat many small ones.
Desktop composition goes in @media (min-width: 1024px); mobile stays one column.
{RULES}"""

REFINE_SYSTEM = f"""You are the art director fixing a page after a design critique. Turn each critique note into a
concrete CSS change on the named section (skip notes CSS cannot fix, e.g. photo choice or copy). Prefer
spacing, alignment, column spans, hierarchy (which text leads) and hairline borders.
{RULES}"""


FIX_SYSTEM = f"""You are the art director fixing ONE section right after it was built. You see it on desktop
(image 1) and on a phone (image 2), the reviewer's notes, and the section's DOM outline (tags and classes).
Fix exactly those notes with the smallest CSS change that does it — spacing, alignment, column spans,
which element leads, line length, stacking on the phone. Selectors must start with the given section.
{RULES}"""


class Stylist:
    """compose(context) / refine(critique, context) / fix_section(...) -> StylePatch | None. Never raises."""

    def __init__(self, llm, vision=None):
        self.llm = llm
        self.vision = vision  # sees the section's screenshots for fix_section; the code model otherwise
        self.name = f"stylist:{getattr(llm, 'model', '?')}"

    def fix_section(self, section_id: str, notes: list[str], outline: str, images: list[str]) -> StylePatch | None:
        user = (f"Section: [data-swarm-section=\"{section_id}\"]\nReviewer notes:\n" + "\n".join(f"- {n}" for n in notes)
                + f"\n\nDOM outline:\n{outline[:2500]}")
        return self._ask(FIX_SYSTEM, user, [section_id], images=images, llm=self.vision or self.llm)

    def _ask(self, system: str, user: str, sections: list[str], images: list[str] | None = None,
             llm=None) -> StylePatch | None:
        try:
            raw = (llm or self.llm).complete_json(system, user, images=images or None, max_tokens=2200)
        except Exception as e:  # noqa: BLE001
            log.warning("stylist failed: %s", e)
            return None
        css, rejected = validate_css(str((raw or {}).get("css") or ""), sections)
        if not css.strip():
            return None
        notes = [n.strip()[:200] for n in (raw.get("notes") or []) if isinstance(n, str) and n.strip()][:8]
        if rejected:
            log.info("stylist: %d rule(s) dropped: %s", len(rejected), rejected[:5])
        return StylePatch(css=css, notes=notes, rejected=rejected)

    def compose(self, context: str, sections: list[str]) -> StylePatch | None:
        return self._ask(COMPOSE_SYSTEM, context, sections)

    def refine(self, critique: list[str], context: str, sections: list[str]) -> StylePatch | None:
        if not critique:
            return None
        notes = "\n".join(f"- {c}" for c in critique)
        return self._ask(REFINE_SYSTEM, f"Critique of the page:\n{notes}\n\n{context}", sections)


def build_stylist(env: dict[str, str] | None = None) -> Stylist | None:
    import os
    from chromaswarm.agents.llm import LLMConfig, OpenAICompatChat
    values = dict(os.environ if env is None else env)
    if values.get("CHROMASWARM_STYLIST", "1") == "0":
        return None
    cfg = LLMConfig.from_env(env)
    return Stylist(OpenAICompatChat(cfg.for_role("code")), vision=OpenAICompatChat(cfg.for_role("vision"))) if cfg else None
