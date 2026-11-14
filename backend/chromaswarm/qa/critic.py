"""Design critic — the "eye" that the measurable QA rules cannot be.

Master QA (master.py) proves a page is not *wrong* (contrast, grid, tap targets...).
Whether it is *beautiful* needs eyes: this module screenshots the page and asks the
vision model (`CHROMASWARM_LLM_MODEL_VISION`) to grade it against a fixed rubric
anchored on real reference sites (knowledge-base/MODERN_UI_REFERENCES.md).

- The model only scores each dimension (1-10) and names concrete issues; the
  overall score is computed here with fixed weights, never taken from the model.
- Non-blocking: no vision model, or any provider error -> `None`, the build goes on.
- CLI to benchmark any page: `uv run python -m chromaswarm.qa.critic URL [URL ...]`
"""

from __future__ import annotations

import asyncio
import base64
import logging
import sys

from playwright.async_api import Page, async_playwright
from pydantic import BaseModel

from chromaswarm.agents.llm import JSONChat, LLMConfig, LLMError, OpenAICompatChat

log = logging.getLogger(__name__)

# dimension -> (weight, what the model must judge)
DIMENSIONS: dict[str, tuple[float, str]] = {
    "hierarchy": (1.2, "one obvious focal point per screen; headings, body, actions clearly ranked by size/weight/contrast"),
    "composition": (1.3, "layout variety and rhythm between sections; alignment to a grid; no monotonous repeated blocks"),
    "whitespace": (1.0, "generous, intentional spacing; groups read clearly; no cramped or empty dead areas"),
    "typography": (1.1, "type pairing, display size and tracking, line length, readable body; Vietnamese diacritics clean"),
    "imagery": (1.2, "real, relevant, well-cropped photos with a consistent tone; no fake/placeholder art"),
    "color": (0.9, "restrained palette; accent reserved for actions; surfaces layered with subtle contrast"),
    "polish": (1.0, "consistent radii, borders, icons, buttons; aligned edges; nothing broken, ragged or misaligned"),
    "modernity": (1.3, "looks like a current professional brand site (2024-2026), not a template or AI-generated page"),
}

SYSTEM = """You are a senior product designer reviewing a web page from screenshots
(desktop first screen, the rest of the desktop page in order, then the mobile first screen).
Grade each dimension from 1 to 10 using this scale, and be strict:
 9-10 = reference craft (Aesop, Apple product pages, Linear, Blue Bottle): art-directed, distinctive, flawless.
 7-8  = solid professional work a real brand would ship.
 5-6  = clean but generic: looks like a template; nothing wrong, nothing memorable.
 3-4  = amateur: weak hierarchy, monotonous layout, placeholder imagery, visible defects.
 1-2  = broken.
Signs of AI-generated / template pages that must lower "modernity" and "composition":
purple-pink gradients, every section a centered title + 3 identical cards, icons on every heading,
heavy drop shadows, generic copy, placeholder images, too many saturated buttons, everything centered.
Return JSON only:
{"scores": {<dimension>: <int 1-10>, ...},
 "strengths": [<short Vietnamese phrase>, ...max 3],
 "issues": [{"where": "<section, e.g. hero / product grid / footer / mobile header>",
             "problem": "<Vietnamese, concrete>", "fix": "<Vietnamese, concrete design change>"}, ...max 6],
 "verdict": "<one Vietnamese sentence>"}
Dimensions: """ + "; ".join(f"{k}: {v[1]}" for k, v in DIMENSIONS.items())


class Issue(BaseModel):
    where: str
    problem: str
    fix: str


class Critique(BaseModel):
    model: str
    scores: dict[str, int]
    overall: float  # weighted mean, 1-10, computed here
    strengths: list[str] = []
    issues: list[Issue] = []
    verdict: str = ""

    def summary(self) -> str:
        return f"{self.overall:.1f}/10 — {self.verdict}"


def overall(scores: dict[str, int]) -> float:
    total = sum(DIMENSIONS[k][0] for k in DIMENSIONS)
    return round(sum(scores[k] * DIMENSIONS[k][0] for k in DIMENSIONS) / total, 2)


def parse_critique(raw: dict, model: str) -> Critique:
    """Validate the model's JSON: every dimension present and clamped to 1-10."""
    got = raw.get("scores") or {}
    scores: dict[str, int] = {}
    for k in DIMENSIONS:
        try:
            scores[k] = min(10, max(1, int(round(float(got[k])))))
        except (KeyError, TypeError, ValueError) as e:
            raise LLMError(f"critic: missing or invalid score for {k!r}") from e
    issues = []
    for i in (raw.get("issues") or [])[:6]:
        if isinstance(i, dict) and i.get("problem"):
            issues.append(Issue(where=str(i.get("where", ""))[:60], problem=str(i["problem"])[:240],
                                fix=str(i.get("fix", ""))[:240]))
    strengths = [str(s)[:120] for s in (raw.get("strengths") or [])[:3]]
    return Critique(model=model, scores=scores, overall=overall(scores), strengths=strengths, issues=issues,
                    verdict=str(raw.get("verdict", ""))[:240])


def vision_chat() -> JSONChat | None:
    cfg = LLMConfig.from_env()
    return OpenAICompatChat(cfg.for_role("vision")) if cfg else None


def _data_url(png: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(png).decode()


async def screenshots(page: Page, max_chunks: int = 4) -> list[str]:
    """Desktop first screen, the rest of the page in 1440x1800 slices, mobile first screen."""
    shots: list[str] = []
    await page.set_viewport_size({"width": 1440, "height": 900})
    await page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) "
                        "{ scrollTo(0, y); await new Promise(r => setTimeout(r, 80)); } scrollTo(0, 0); }")
    await page.wait_for_timeout(600)
    shots.append(_data_url(await page.screenshot(type="jpeg", quality=70)))
    height = await page.evaluate("document.documentElement.scrollHeight")
    y = 900
    while y < height and len(shots) <= max_chunks:
        h = min(1800, height - y)
        shots.append(_data_url(await page.screenshot(type="jpeg", quality=65, full_page=True,
                                                     clip={"x": 0, "y": y, "width": 1440, "height": h})))
        y += h
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.evaluate("scrollTo(0, 0)")
    await page.wait_for_timeout(400)
    shots.append(_data_url(await page.screenshot(type="jpeg", quality=70)))
    await page.set_viewport_size({"width": 1440, "height": 900})
    return shots


async def critique(page: Page, chat: JSONChat | None = None, context: str = "") -> Critique | None:
    """Grade the page currently loaded in `page`. None when no vision model is configured or it fails."""
    chat = chat or vision_chat()
    if chat is None:
        return None
    try:
        images = await screenshots(page)
        user = "Review this page." + (f" Context: {context}" if context else "")
        raw = await asyncio.to_thread(chat.complete_json, SYSTEM, user, images)
        return parse_critique(raw, getattr(chat, "model", "?"))
    except Exception as e:  # never stop a build because the critic failed
        log.warning("design critic failed: %s", e)
        return None


def render_markdown(c: Critique) -> str:
    rows = "\n".join(f"| {k} | {v}/10 | {DIMENSIONS[k][1]} |" for k, v in c.scores.items())
    issues = "\n".join(f"{n}. **{i.where}** — {i.problem}\n   → {i.fix}" for n, i in enumerate(c.issues, 1)) or "_Không có._"
    strengths = "\n".join(f"- {s}" for s in c.strengths) or "-"
    return (f"# CRITIQUE.md — Chấm điểm thẩm mỹ (B11)\n\n**{c.overall:.1f}/10** · {c.verdict}\n\n"
            f"_Model: {c.model}. Thang: 9–10 đẳng cấp trang mẫu · 7–8 chuyên nghiệp · 5–6 template · ≤4 nghiệp dư._\n\n"
            f"| Tiêu chí | Điểm | Nội dung |\n| :--- | ---: | :--- |\n{rows}\n\n## Điểm mạnh\n\n{strengths}\n\n"
            f"## Cần cải thiện\n\n{issues}\n")


async def _cli(urls: list[str]) -> int:
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    chat = vision_chat()
    if chat is None:
        print("Chưa cấu hình model đọc ảnh (CHROMASWARM_LLM_MODEL / _VISION trong backend/.env).")
        return 1
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        for url in urls:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3000)
            except Exception as e:  # noqa: BLE001
                print(f"{url}: không mở được ({e})")
                continue
            c = await critique(page, chat)
            if c is None:
                print(f"{url}: critic lỗi")
                continue
            dims = " ".join(f"{k[:4]}={v}" for k, v in c.scores.items())
            print(f"{c.overall:4.1f}  {url}\n      {dims}\n      {c.verdict}")
            for i in c.issues[:3]:
                print(f"      - {i.where}: {i.problem}")
        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_cli(sys.argv[1:])))
