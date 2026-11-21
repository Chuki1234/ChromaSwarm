"""B9 "eyes": every section is looked at as soon as it is built, before the next one starts.

The Developer writes section N, Design measures it, then this checker gets two screenshots of
that section alone — desktop (1440) and phone (375), on a clean tab without the swarm overlay
and with motion reduced — and a vision model judges it like a senior designer would at a desk
review. Problems come back in a fixed set of kinds; the art director gets the same pictures and
fixes that one section (developer/stylist.Stylist.fix_section). The section is shot and judged
again: a fix is kept only when the verdict improves and the phone width does not overflow, at
most MAX_FIXES times. Then the build moves on.

Screenshots are saved as files (artifacts/shots/), never in the checkpointed state.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from chromaswarm.qa.taste import taste_block

log = logging.getLogger(__name__)

MAX_FIXES = 2
KINDS = {"spacing", "overlap", "alignment", "hierarchy", "imagery", "readability", "mobile", "empty", "consistency", "other"}
# Kinds the CSS layer can act on. Imagery (wrong photo) and copy are reported, not "fixed" with CSS.
FIXABLE = {"spacing", "overlap", "alignment", "hierarchy", "readability", "mobile", "consistency"}

SYSTEM = """You are a senior product designer doing a desk review of ONE section of a web page, as soon as it
is built. Image 1 is the section on desktop (1440px wide), image 2 the same section on a phone (375px).
Judge it against real, professionally designed sites (Linear, Stripe, Apple, Aesop), not against templates.
Report only real, visible problems a client would notice — cramped or uneven spacing, text overlapping or
clipped, weak hierarchy (nothing leads, or two things fight), misaligned edges, hard-to-read text, a layout
that breaks or is cramped on the phone, an empty or placeholder-looking visual, a photo unrelated to the
brief, inconsistent card heights. Do not report taste preferences or things outside this section.
Answer JSON only:
{"ok": true|false, "score": 1-10,
 "issues": [{"kind": "spacing|overlap|alignment|hierarchy|imagery|readability|mobile|empty|consistency|other",
             "where": "desktop|mobile|both", "problem": "<Vietnamese, concrete>", "fix": "<Vietnamese, concrete design change>"}]}
"ok" is true only when a demanding client would sign this section off as is. At most 4 issues."""


class Issue(BaseModel):
    kind: str
    where: str = "both"
    problem: str
    fix: str

    def line(self) -> str:
        return f"{self.problem} → {self.fix}"


class Verdict(BaseModel):
    ok: bool
    score: float
    issues: list[Issue] = []

    @property
    def fixable(self) -> list[Issue]:
        return [i for i in self.issues if i.kind in FIXABLE]

    def better_than(self, other: "Verdict") -> bool:
        return (self.ok and not other.ok) or self.score >= other.score + 0.5 or \
            (self.score >= other.score and len(self.fixable) < len(other.fixable))


def validate(raw: dict) -> Verdict | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("ok"), bool):
        return None
    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError):
        return None
    if not 1 <= score <= 10:
        return None
    issues = []
    for it in raw.get("issues") or []:
        if not isinstance(it, dict) or not str(it.get("problem") or "").strip():
            continue
        kind = it.get("kind") if it.get("kind") in KINDS else "other"
        where = it.get("where") if it.get("where") in ("desktop", "mobile", "both") else "both"
        issues.append(Issue(kind=kind, where=where, problem=str(it["problem"]).strip()[:220],
                            fix=str(it.get("fix") or "").strip()[:220]))
    ok = raw["ok"] and not any(i.kind in FIXABLE for i in issues)
    return Verdict(ok=ok, score=score, issues=issues[:4])


class SectionEye:
    """look(name, purpose, brief, images) -> Verdict | None. Never raises."""

    def __init__(self, vision):
        self.vision = vision
        self.name = f"eye:{getattr(vision, 'model', '?')}"

    def look(self, name: str, purpose: str, brief: str, images: list[str]) -> Verdict | None:
        user = f"Brief: {brief[:400]}\nSection: {name} — {purpose[:200]}\n\n{taste_block()}"
        try:
            raw = self.vision.complete_json(SYSTEM, user, images=images, max_tokens=700)
        except Exception as e:  # noqa: BLE001
            log.warning("section eye failed for %s: %s", name, e)
            return None
        return validate(raw)


def build_section_eye(env: dict[str, str] | None = None) -> SectionEye | None:
    import os
    from chromaswarm.agents.llm import LLMConfig, OpenAICompatChat
    values = dict(os.environ if env is None else env)
    if values.get("CHROMASWARM_SECTION_EYE", "1") == "0":
        return None
    cfg = LLMConfig.from_env(env)
    return SectionEye(OpenAICompatChat(cfg.for_role("vision"))) if cfg else None
