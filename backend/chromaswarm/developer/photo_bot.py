"""Photo bot (B9): finds photos that show what THIS user sells, instead of a fixed topic set.

The curated topics in photos.py are safe but coarse: an oolong-tea page got matcha whisks
(design critic, 2026-11-18), a sneaker shop had no topic at all. The bot works in three steps:

1. Queries: the text model turns the brief into 3 short English search queries plus what the
   photos must show and must NOT show ("oolong tea" -> must not: matcha, green powder, latte art).
2. Search: free-license sources, no scraping:
   - Unsplash official API when `UNSPLASH_ACCESS_KEY` is set (best quality);
   - Openverse (api.openverse.org, keyless) otherwise, commercial use + modification allowed.
3. Look: the vision model sees the candidates' thumbnails and keeps only those that fit the brief,
   with no visible brand logo or text and a clean, modern look; it orders them with the best
   wide hero photo first. The verdict is checked in code (indices in range, at least MIN_KEEP).

Anything off (no LLM, network down, too few good photos) -> None and photos.py's curated topic
photos are used. Every kept photo carries its credit; CC BY photos are credited in the footer.
`CHROMASWARM_PHOTO_BOT=0` turns the bot off.
"""

from __future__ import annotations

import hashlib
import json
import logging
import base64
from pathlib import Path
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from chromaswarm.developer.photos import stock_photos
from chromaswarm.agents.llm import JSONChat, LLMConfig, LLMError, OpenAICompatChat
from chromaswarm.state_machine.pipeline_state import PipelineState

log = logging.getLogger(__name__)

OPENVERSE = "https://api.openverse.org/v1/images/"
UNSPLASH = "https://api.unsplash.com/search/photos"
COMMONS = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "ChromaSwarm-photo-bot/1.0 (website builder)"
PER_QUERY = 20
MAX_CANDIDATES = 14   # searched thumbnails per vision call (curated topic photos are added on top)
MIN_KEEP = 3          # fewer good photos than this: the curated topic photos are better
MAX_KEEP = 8
MIN_WIDTH = 1000      # a hero is drawn up to ~1440px wide

QUERY_SYSTEM = """You plan a stock-photo search for a website. From the project brief (Vietnamese),
return JSON only:
{"queries": ["<1-3 English words>", ...4 queries: most specific first, the last a broad one (e.g. "tea")],
 "must_show": "<English, 2-5 words: the SUBJECT only (e.g. 'bonsai tree', 'oolong tea'), never a setting or pose>",
 "must_not": "<English: look-alikes to reject, e.g. for oolong tea: matcha, green tea powder, latte art>"}
Queries name the actual product and its real context (ingredients, how it is used, where it is made),
never abstract ideas ("luxury", "success"), never people's faces as the subject.
For software or a service, search the customer's real work it serves, not offices: an inventory app ->
"warehouse shelves", "packing parcels"; a clinic booking app -> "dental clinic"; never "office meeting",
"laptop", "team working", "business people"."""

LOOK_SYSTEM = """You are a photo editor for a modern brand website. You see numbered candidate photos.
Keep a photo only if ALL hold: it clearly shows {must_show}; it is NOT {must_not};
no visible brand logo, brand stripes / swoosh, watermark or overlaid text; professional quality you
would see on a premium brand site or Unsplash: sharp, deliberate light and composition, contemporary.
REJECT amateur snapshots, flash photos, dated colours, cluttered backgrounds, clip-art, collages, and generic
office scenes (meetings, people at laptops, handshakes) unless the brief itself is about offices; stickers or
logos on laptops and phones count as brand logos.
Judge the subject, not the setting: a good photo of the subject anywhere is fine.
Fewer good photos beat many mediocre ones. Order kept photos best first; the first one must work as a wide hero
(calm area for a headline). Return JSON only: {{"keep": [<photo numbers, 1-based>], "why": "<short>"}}"""


# Second look, only when the first kept nothing and there is no curated photo for this idea:
# an on-topic photo of ordinary quality still beats an empty grey box on the page.
RELAXED_SYSTEM = """You pick photos for a website about: {must_show}. You see numbered candidate photos.
Keep every photo that clearly shows {must_show} as its main subject, is NOT {must_not}, and has no
watermark or overlaid text. Order the best (sharpest, cleanest background) first.
Return JSON only: {{"keep": [<photo numbers, 1-based>], "why": "<short>"}}"""


def enabled() -> bool:
    return os.environ.get("CHROMASWARM_PHOTO_BOT", "1") != "0" and os.environ.get("CHROMASWARM_STOCK_PHOTOS", "1") != "0"


def photo_key(state: PipelineState) -> str:
    src = [state.raw_prompt, (state.brief or {}).get("products"), (state.brief or {}).get("brand"), str(state.domain)]
    return hashlib.sha1(json.dumps(src, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def brief_text(state: PipelineState) -> str:
    b = state.brief or {}
    parts = [state.raw_prompt or "", b.get("brand") or "", ", ".join(b.get("products") or []),
             ", ".join(b.get("categories") or []), state.pillars.scope or ""]
    return " · ".join(p for p in parts if p)


def _openverse(client: httpx.Client, query: str) -> list[dict]:
    # Size is filtered here, not with `size=large` (that filter empties most specific queries).
    for attempt in (1, 2):  # the keyless API answers 5xx / non-JSON now and then: one retry
        try:
            r = client.get(OPENVERSE, params={"q": query, "page_size": PER_QUERY, "mature": "false",
                                              "license_type": "commercial,modification"})
            r.raise_for_status()
            results = r.json().get("results", [])
            break
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise
            time.sleep(1.5)
    out = []
    for x in results:
        if (x.get("width") or 0) < MIN_WIDTH or not x.get("url", "").startswith("https://"):
            continue
        out.append({"url": x["url"], "thumb": x.get("thumbnail") or x["url"], "creator": x.get("creator") or "",
                    "license": f"CC {(x.get('license') or '').upper()}".strip(), "source": x.get("foreign_landing_url") or "",
                    "needs_credit": (x.get("license") or "") not in ("cc0", "pdm")})
    return out


def _unsplash(client: httpx.Client, query: str, key: str) -> list[dict]:
    r = client.get(UNSPLASH, params={"query": query, "per_page": PER_QUERY, "content_filter": "high"},
                   headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    r.raise_for_status()
    return [{"url": x["urls"]["raw"] + "&auto=format&fit=crop&q=80", "thumb": x["urls"]["small"],
             "creator": (x.get("user") or {}).get("name") or "", "license": "Unsplash License",
             "source": (x.get("links") or {}).get("html") or "", "needs_credit": False}
            for x in r.json().get("results", []) if (x.get("width") or 0) >= MIN_WIDTH]


_TAGS = re.compile(r"<[^>]+>")


def _commons(client: httpx.Client, query: str) -> list[dict]:
    """Wikimedia Commons (keyless, reliable): free-license photos, credited when the license asks."""
    r = client.get(COMMONS, params={"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
                                    "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": PER_QUERY, "prop": "imageinfo",
                                    "iiprop": "url|size|extmetadata", "iiurlwidth": 1600})
    r.raise_for_status()
    out = []
    for page in (r.json().get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        lic = (meta.get("LicenseShortName") or {}).get("value", "")
        if (info.get("width") or 0) < MIN_WIDTH or not info.get("thumburl") or "NC" in lic or "ND" in lic:
            continue
        out.append({"url": info["thumburl"], "thumb": info["thumburl"].replace("1600px-", "400px-"),
                    "creator": _TAGS.sub("", (meta.get("Artist") or {}).get("value", "")).strip()[:40],
                    "license": lic, "source": info.get("descriptionurl") or "",
                    "needs_credit": not re.search(r"public domain|cc0|pdm", lic, re.I)})
    return out


def search(queries: list[str], env: dict | None = None) -> list[dict]:
    """Unsplash with a key; keyless: Openverse, then Wikimedia Commons for what is still missing."""
    env = env if env is not None else os.environ
    key = env.get("UNSPLASH_ACCESS_KEY", "")
    sources = [lambda c, q: _unsplash(c, q, key)] if key else [_openverse, _commons]
    seen, out = set(), []
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for source in sources:
            for q in queries[:4]:
                if len(out) >= MAX_CANDIDATES:
                    break
                try:
                    found = source(client, q)
                except (httpx.HTTPError, ValueError, KeyError) as e:
                    log.warning("photo bot: search %r failed: %s", q, e)
                    continue
                for x in found:
                    if x["url"] not in seen:
                        seen.add(x["url"])
                        out.append(x)
    return out[:MAX_CANDIDATES]


def fetch_thumbs(candidates: list[dict]) -> list[tuple[dict, str]]:
    """Thumbnails downloaded here and sent inline: the vision provider cannot fetch every host itself
    (Openverse thumbs answered 424 to it). Candidates whose thumbnail does not load are dropped."""
    def one(c: dict) -> tuple[dict, str] | None:
        try:
            r = httpx.get(c["thumb"], timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            kind = r.headers.get("content-type", "image/jpeg").split(";")[0]
            if not kind.startswith("image/") or len(r.content) > 1_500_000:
                return None
            return c, f"data:{kind};base64,{base64.b64encode(r.content).decode()}"
        except httpx.HTTPError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [x for x in pool.map(one, candidates) if x]


def check_keep(raw: dict, n: int) -> list[int]:
    """The vision verdict, validated: 1-based numbers in range, no repeats, at least one."""
    keep = raw.get("keep") if isinstance(raw, dict) else None
    if not isinstance(keep, list):
        raise ValueError("keep missing")
    idx = list(dict.fromkeys(int(k) - 1 for k in keep if isinstance(k, (int, float)) or str(k).isdigit()))
    idx = [i for i in idx if 0 <= i < n][:MAX_KEEP]
    if not idx:
        raise ValueError("no fitting photo")
    return idx


class PhotoBot:
    def __init__(self, text: JSONChat, vision: JSONChat, searcher=search, fetcher=fetch_thumbs,
                 generator=None, root: Path | None = None):
        self.text, self.vision, self.search, self.fetch = text, vision, searcher, fetcher
        self.generator, self.root = generator, root  # developer/image_gen.py: last resort, saved under uploads/

    def __call__(self, state: PipelineState) -> list[dict] | None:
        found = self.find(state)
        if self.generator is None or self.root is None or (found and len(found) >= MIN_KEEP):
            return found
        if found is None and stock_photos(brief_text(state), state.domain):
            return None  # curated photos exist for this topic: they are better than generated ones
        return (found or []) + self.generate(state, MIN_KEEP - len(found or [])) or None

    def generate(self, state: PipelineState, n: int) -> list[dict]:
        """Images made for the brief when nothing real fits; labelled as AI-generated."""
        from chromaswarm.developer.uploads import GENERATED, save
        try:
            plan = self.text.complete_json(SUBJECT_SYSTEM, brief_text(state), max_tokens=300)
            subjects = [x for x in plan.get("subjects", []) if isinstance(x, str) and x.strip()][:n] or [brief_text(state)[:80]]
        except (LLMError, ValueError, TypeError, AttributeError):
            subjects = [brief_text(state)[:80]] * n
        out = []
        for data in self.generator(brief_text(state), subjects):
            try:
                up = save(self.root, state.session_id, GENERATED, data, generated=True)
            except ValueError as e:
                log.warning("generated image refused: %s", e)
                continue
            out.append({"url": up.path, "thumb": "", "creator": "", "license": "Ảnh tạo bằng AI (minh hoạ)",
                        "source": "", "needs_credit": False, "generated": True})
        log.info("photo bot: generated %d image(s) for %s", len(out), subjects)
        return out

    def find(self, state: PipelineState) -> list[dict] | None:
        try:
            plan = self.text.complete_json(QUERY_SYSTEM, brief_text(state), max_tokens=400)
            queries = [q for q in plan.get("queries", []) if isinstance(q, str) and q.strip()]
            if not queries:
                raise ValueError("no queries")
            # The curated topic photos (photos.py, checked by eye) compete in the same look: the bot
            # only changes a photo when it finds a better one for this brief.
            curated = [{"url": u, "thumb": u + "&w=400", "creator": "", "license": "Unsplash License",
                        "source": "", "needs_credit": False}
                       for u in stock_photos(brief_text(state), state.domain)]
            shown = self.fetch(curated + self.search(queries))
            candidates = [c for c, _ in shown]
            if len(candidates) < MIN_KEEP:
                raise ValueError(f"only {len(candidates)} candidates for {queries}")
            system = LOOK_SYSTEM.format(must_show=plan.get("must_show") or queries[0],
                                        must_not=plan.get("must_not") or "an unrelated subject")
            listing = "\n".join(f"{i + 1}." for i in range(len(candidates)))
            user = f"Brief: {brief_text(state)}\nPhotos:\n{listing}"
            images = [img for _, img in shown]
            verdict = self.vision.complete_json(system, user, images=images, max_tokens=300)
            try:
                picked = [candidates[i] for i in check_keep(verdict, len(candidates))]
            except ValueError:
                if curated:
                    raise
                verdict = self.vision.complete_json(
                    RELAXED_SYSTEM.format(must_show=plan.get("must_show") or queries[0],
                                          must_not=plan.get("must_not") or "an unrelated subject"),
                    user, images=images, max_tokens=300)
                picked = [candidates[i] for i in check_keep(verdict, len(candidates))]
            # The approved photos lead, the curated ones fill up to MIN_KEEP. With no curated photos for
            # this idea, even one approved photo is used (the page repeats it) rather than grey boxes.
            picked += [c for c in curated if c not in picked][:max(0, MIN_KEEP - len(picked))]
            log.info("photo bot: %d/%d kept for %s (%s)", len(picked), len(candidates), queries, verdict.get("why", ""))
            return picked
        except (LLMError, ValueError, TypeError, KeyError, httpx.HTTPError) as e:
            log.warning("photo bot: using curated topic photos (%s)", e)
            return None


SUBJECT_SYSTEM = """List what website photos for this brief should show, as short English noun phrases
(subject only, no setting words like "website"): the first suits a wide hero image. JSON only:
{"subjects": ["<2-6 words>", "<2-6 words>", "<2-6 words>"]}"""


def credit_line(photos: list[dict]) -> str:
    """Footer credit for photos whose license asks for it (CC BY / BY-SA)."""
    names = list(dict.fromkeys(p["creator"] for p in photos if p.get("needs_credit") and p.get("creator")))
    return f"Ảnh: {', '.join(names[:4])}{' và cộng sự' if len(names) > 4 else ''} (Creative Commons)" if names else ""


def build_photo_bot(env: dict[str, str] | None = None) -> PhotoBot | None:
    cfg = LLMConfig.from_env(env)
    if not cfg or not enabled():
        return None
    from chromaswarm.developer.image_gen import build_image_generator
    root = Path(__file__).resolve().parents[3] / "workspaces"
    return PhotoBot(OpenAICompatChat(cfg.for_role("text")), OpenAICompatChat(cfg.for_role("vision")),
                    generator=build_image_generator(env), root=root)
