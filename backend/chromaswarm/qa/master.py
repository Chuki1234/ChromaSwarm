"""B11 "Cursor Lớn Nhất" — the four Master QA tests of FRONTEND_STANDARDS.md chapter 5.

1. Interactive sweep   — tap size, not covered, hover feedback, click changes state,
                          keyboard focus-visible, no console errors
2. Scroll choreography — sticky header stays legible, nothing stuck at opacity 0, images load
3. 4-breakpoint audit  — 1440/1024/768/375: no horizontal overflow, no text collisions,
                          mobile margins >= 16px, tap targets >= 40px
4. DESIGN.md + anti-slop — fonts match, contrast on every text block, the automatable
                          rules of the 10-point blacklist

The probe (qa_probe.js) only measures; verdicts are computed here. Each failure
carries a `heal` CSS rule when the Developer can patch it deterministically
(written to app/heal.css on the next B9 pass) or a colour reading when the
Design department can repair it in tokens.css; otherwise it is reported as is.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import Page
from pydantic import BaseModel

from chromaswarm.engines.color import apca_lc, parse_css_color, wcag_contrast
from chromaswarm.engines.typography import TypeScale
from chromaswarm.playwright_engine.swarm import Agent, ColorReading, Rect, SwarmOverlay, contrast_finding

PROBE_JS = Path(__file__).with_name("qa_probe.js").read_text(encoding="utf-8")
BREAKPOINTS = [(1440, 900, "Desktop"), (1024, 768, "Laptop"), (768, 1024, "Tablet"), (375, 812, "Mobile")]
MIN_TAP = 40
MOBILE_MARGIN = 16
CLICKABLE_ROLES = {"button", "tab", "filter-tab", "modal-trigger"}
GENERIC_COPY = ["lorem ipsum", "john doe", "nâng tầm trải nghiệm", "khám phá tiềm năng vô hạn",
                "giải pháp đột phá hàng đầu", "trải nghiệm đẳng cấp", "elevate your", "unlock the power"]
TEST_NAMES = {1: "Thao tác từng nút", 2: "Cuộn trang", 3: "Đa màn hình", 4: "DESIGN.md & chống AI-slop"}


class QaFailure(BaseModel):
    test: int
    rule: str
    selector: str
    detail: str
    viewport: int | None = None
    heal: str | None = None  # CSS rule the Developer can apply
    reading: ColorReading | None = None  # contrast pair the Design department can repair


class QaTest(BaseModel):
    test: int
    name: str
    checked: int
    failures: list[QaFailure] = []

    @property
    def passed(self) -> bool:
        return not self.failures


class QaReport(BaseModel):
    tests: list[QaTest]

    @property
    def passed(self) -> bool:
        return all(t.passed for t in self.tests)

    @property
    def failures(self) -> list[QaFailure]:
        return [f for t in self.tests for f in t.failures]

    def summary(self) -> str:
        return " · ".join(f"{t.test}. {t.name}: {'PASS' if t.passed else f'{len(t.failures)} lỗi'}" for t in self.tests)


async def _probe(page: Page, fn: str, *args):
    await page.evaluate(PROBE_JS)
    return await page.evaluate(f"(args) => window.__chromaQA.{fn}(...args)", list(args))


def _sel(selector: str) -> str:
    return selector  # selectors from the probe are already valid CSS


# ------------------------------------------------------------------ test 1

async def test_interactions(page: Page, swarm: SwarmOverlay, errors: list[str], instant: bool) -> QaTest:
    items = await _probe(page, "interactives")
    fails: list[QaFailure] = []
    pause = 0 if instant else 120
    for n, it in enumerate(items, 1):
        sel = it["selector"]
        await swarm.hud(f"Master Cursor · Bài 1: {n}/{len(items)} phần tử · {it['label'] or it['tag']}")
        pos = await _probe(page, "probe", sel)
        if not pos:
            continue
        await swarm.move(Agent.MASTER, sel)
        if pos["covered"]:
            fails.append(QaFailure(test=1, rule="covered", selector=sel,
                                   detail=f"bị che bởi {pos['covered_by']}", heal=f"{_sel(sel)} {{ position: relative; z-index: 1; }}"))
            continue
        await page.mouse.move(0, 0)
        await page.wait_for_timeout(20)
        rest = await _probe(page, "styleSig", sel)
        await page.mouse.move(pos["x"], pos["y"])
        await page.wait_for_timeout(30 + pause)
        hovered = await _probe(page, "styleSig", sel)
        if rest == hovered:
            fails.append(QaFailure(test=1, rule="no-hover", selector=sel, detail=f"“{it['label']}” không đổi style khi rê chuột",
                                   heal=f"{_sel(sel)} {{ transition: filter 200ms cubic-bezier(0.22, 1, 0.36, 1); }}\n"
                                        f"{_sel(sel)}:hover {{ filter: brightness(0.92); }}"))
        is_button = it["tag"] == "button" or (it["role"] in CLICKABLE_ROLES and it["tag"] != "a")
        if is_button:
            before = await _probe(page, "domSig")
            errors_before = len(errors)
            await swarm.pulse()
            await page.mouse.click(pos["x"], pos["y"])
            await page.wait_for_timeout(120 + pause)
            after = await _probe(page, "domSig")
            if before == after:
                fails.append(QaFailure(test=1, rule="no-state-change", selector=sel,
                                       detail=f"bấm “{it['label']}” nhưng giao diện không phản hồi"))
            if len(errors) > errors_before:
                fails.append(QaFailure(test=1, rule="console-error", selector=sel, detail=errors[-1][:160]))
            if await page.evaluate("() => !!document.querySelector('[role=dialog]') || location.hash.length > 1"):
                await page.reload()  # restore the baseline for the next element
                await page.wait_for_load_state("networkidle")
                await swarm.master(True)

    # keyboard focus-visible on the first tabbable elements
    await page.evaluate("() => { document.activeElement?.blur(); scrollTo(0, 0); }")
    baseline = {it["selector"]: await _probe(page, "focusSig", it["selector"]) for it in items[:30]}
    checked: set[str] = set()
    for _ in range(min(30, len(items))):
        await page.keyboard.press("Tab")
        sel = await _probe(page, "activeSelector")
        if not sel or sel in checked or sel not in baseline:
            continue
        checked.add(sel)
        if await _probe(page, "focusSig", sel) == baseline[sel]:
            fails.append(QaFailure(test=1, rule="no-focus-visible", selector=sel, detail="không có viền focus khi dùng bàn phím",
                                   heal=f"{_sel(sel)}:focus-visible {{ outline: 2px solid var(--accent, currentColor); outline-offset: 2px; }}"))
    await page.evaluate("() => document.activeElement?.blur()")
    await page.mouse.move(0, 0)  # later tests must measure the resting state, not a hover state
    return QaTest(test=1, name=TEST_NAMES[1], checked=len(items), failures=fails)


# ------------------------------------------------------------------ test 2

async def test_scroll(page: Page, swarm: SwarmOverlay) -> QaTest:
    await swarm.hud("Master Cursor · Bài 2: cuộn từ đầu đến cuối trang")
    r = await _probe(page, "scrollAudit")
    fails: list[QaFailure] = []
    for stop in r["sticky"]:
        if stop["top"] < -1:
            fails.append(QaFailure(test=2, rule="sticky-lost", selector=stop["selector"],
                                   detail=f"header trôi khỏi màn hình ở scrollY={stop['y']}"))
            break
        if stop["bg_alpha"] < 0.6 and not stop["blur"]:
            fails.append(QaFailure(test=2, rule="sticky-legibility", selector=stop["selector"],
                                   detail="header dính không có nền hoặc blur, chữ chìm vào nội dung",
                                   heal=f"{stop['selector']} {{ background: color-mix(in oklch, var(--bg-primary) 88%, transparent); "
                                        "backdrop-filter: blur(12px); }"))
            break
        if stop["h"] > r["viewport_h"] * 0.2:
            fails.append(QaFailure(test=2, rule="sticky-too-tall", selector=stop["selector"],
                                   detail=f"header cao {stop['h']}px, che hơn 20% màn hình"))
            break
    for sel in r["stuck"]:
        fails.append(QaFailure(test=2, rule="stuck-hidden", selector=sel, detail="phần tử kẹt ở opacity 0 sau khi cuộn",
                               heal=f"{sel} {{ opacity: 1; }}"))
    for sel in r["broken_images"]:
        fails.append(QaFailure(test=2, rule="broken-image", selector=sel, detail="ảnh không tải được (naturalWidth = 0)"))
    return QaTest(test=2, name=TEST_NAMES[2], checked=len(r["sticky"]) + 1, failures=fails)


# ------------------------------------------------------------------ test 3

async def test_breakpoints(page: Page, swarm: SwarmOverlay) -> QaTest:
    fails: list[QaFailure] = []
    for w, h, label in BREAKPOINTS:
        await page.set_viewport_size({"width": w, "height": h})
        await page.wait_for_timeout(250)
        await swarm.hud(f"Master Cursor · Bài 3: {w}px {label}")
        ov = await _probe(page, "overflow")
        if ov["scroll_w"] > ov["client_w"]:
            fails.append(QaFailure(test=3, rule="overflow-x", selector=ov["offender"] or "html", viewport=w,
                                   detail=f"tràn ngang {ov['scroll_w'] - ov['client_w']}px ở {w}px",
                                   heal=f"{ov['offender']} {{ max-width: 100%; overflow-wrap: anywhere; }}" if ov["offender"] else None))
        for c in await _probe(page, "collisions"):
            fails.append(QaFailure(test=3, rule="collision", selector=c["a"], viewport=w,
                                   detail=f"chồng lấn với {c['b']} ({c['area']}px²) ở {w}px"))
        if w <= 767:
            for m in await _probe(page, "margins", MOBILE_MARGIN):
                section = f'[data-swarm-section="{m["section"]}"]' if m["section"] else None
                fails.append(QaFailure(test=3, rule="mobile-margin", selector=m["selector"], viewport=w,
                                       detail=f"cách mép trái {m['left']}px / phải {m['right']}px (cần ≥ {MOBILE_MARGIN}px)",
                                       heal=(f"@media (max-width: 767px) {{ {section} > .container {{ padding-inline: "
                                             f"max({MOBILE_MARGIN}px, var(--gutter)); }} }}") if section else None))
            for t in await _probe(page, "tapTargets", MIN_TAP):
                fails.append(QaFailure(test=3, rule="tap-target", selector=t["selector"], viewport=w,
                                       detail=f"vùng bấm “{t['label']}” {t['w']}×{t['h']}px (cần ≥ {MIN_TAP}px)",
                                       heal=f"@media (max-width: 767px) {{ {t['selector']} {{ min-height: 44px; min-width: 44px; }} }}"))
    await page.set_viewport_size({"width": 1440, "height": 900})
    # one finding per (rule, element): a collision seen at 4 widths is one defect
    unique: dict[tuple[str, str], QaFailure] = {}
    for f in fails:
        unique.setdefault((f.rule, f.selector), f)
    return QaTest(test=3, name=TEST_NAMES[3], checked=len(BREAKPOINTS), failures=list(unique.values()))


# ------------------------------------------------------------------ test 4

def _purple_pink(stops: list[str]) -> bool:
    hits = 0
    for s in stops:
        c = parse_css_color(s)
        if c and c[0].c > 0.08 and 265 <= c[0].h <= 355:
            hits += 1
    return hits >= 2


async def test_design_compliance(page: Page, swarm: SwarmOverlay, scale: TypeScale | None) -> QaTest:
    await swarm.hud("Master Cursor · Bài 4: đối chiếu DESIGN.md & 10 điều cấm")
    await page.mouse.move(0, 0)
    fails: list[QaFailure] = []
    fonts = await _probe(page, "fonts")
    if scale:
        for kind, expected in (("heading", scale.heading_font), ("body", scale.body_font)):
            if fonts[kind] and fonts[kind] != expected:
                fails.append(QaFailure(test=4, rule="font", selector="h1, h2, h3" if kind == "heading" else "p",
                                       detail=f"phông {kind} là “{fonts[kind]}”, DESIGN.md quy định “{expected}”"))
    texts = await _probe(page, "texts")
    seen: set[tuple] = set()
    for t in texts:
        if t["over_image"]:
            continue  # text on a gradient/photo: no single background colour to measure against
        key = (t["fg"], t["bg"], t["font_size"] >= 24, t["font_weight"] >= 700)
        if key in seen:
            continue
        seen.add(key)
        fg, bg = parse_css_color(t["fg"]), parse_css_color(t["bg"])
        r = ColorReading(fg=t["fg"], bg=t["bg"], font_size=t["font_size"], font_weight=t["font_weight"],
                         rect=Rect(x=0, y=0, w=0, h=0),
                         wcag=round(wcag_contrast(fg[0], bg[0]), 2) if fg and bg else None,
                         apca=round(apca_lc(fg[0], bg[0]), 1) if fg and bg else None)
        if f := contrast_finding(t["section"] or "", t["selector"], r):
            fails.append(QaFailure(test=4, rule="contrast", selector=t["selector"], detail=f.detail, reading=r))
    slop = await _probe(page, "slop")
    for g in slop["gradients"]:
        if (g["clip_text"] or g["control"]) and _purple_pink(g["stops"]):
            fails.append(QaFailure(test=4, rule="slop-1-gradient", selector=g["selector"],
                                   detail="gradient tím–hồng mặc định trên chữ/nút",
                                   heal=f"{g['selector']} {{ background-image: none; }}"))
    if slop["triple_card_sections"] >= 2:
        fails.append(QaFailure(test=4, rule="slop-2-triple-cards", selector="[data-swarm-section]",
                               detail=f"{slop['triple_card_sections']} section lặp mẫu “tiêu đề giữa + 3 thẻ giống nhau”"))
    for c in slop["centered"]:
        fails.append(QaFailure(test=4, rule="slop-3-centered", selector=c["selector"],
                               detail=f"đoạn {c['lines']} dòng căn giữa", heal=f"{c['selector']} {{ text-align: left; }}"))
    if slop["headings"] >= 3 and slop["icon_headings"] >= max(2, slop["headings"] / 2):
        fails.append(QaFailure(test=4, rule="slop-4-icons", selector="h1, h2, h3, h4",
                               detail=f"{slop['icon_headings']}/{slop['headings']} tiêu đề mở đầu bằng icon/emoji"))
    for s in slop["shadows"]:
        if not s["floating"]:
            fails.append(QaFailure(test=4, rule="slop-5-shadow", selector=s["selector"],
                                   detail=f"bóng đổ nặng (alpha {s['alpha']}, blur {s['blur']:g}px)",
                                   heal=f"{s['selector']} {{ box-shadow: 0 1px 2px oklch(0 0 0 / 0.04), 0 8px 24px oklch(0 0 0 / 0.05); }}"))
    for phrase in GENERIC_COPY:
        if phrase in slop["text"]:
            fails.append(QaFailure(test=4, rule="slop-6-copy", selector="body", detail=f"nội dung sáo rỗng: “{phrase}”"))
    for c in slop["ctas"]:
        if len(c["filled"]) > 1:
            fails.append(QaFailure(test=4, rule="slop-7-cta", selector=f'[data-swarm-section="{c["section"]}"]',
                                   detail=f"{len(c['filled'])} nút chính khác nhau trong một section: {', '.join(c['filled'][:3])}"))
    for d in slop["distorted"]:
        fails.append(QaFailure(test=4, rule="slop-8-image-ratio", selector=d["selector"],
                               detail=f"ảnh bị méo {d['drift'] * 100:.0f}%", heal=f"{d['selector']} {{ object-fit: cover; }}"))
    return QaTest(test=4, name=TEST_NAMES[4], checked=len(texts) + len(slop["gradients"]) + slop["headings"], failures=fails)


# ------------------------------------------------------------------ runner

async def run_master_qa(page: Page, swarm: SwarmOverlay, scale: TypeScale | None = None, *,
                        errors: list[str] | None = None, instant: bool = False) -> QaReport:
    errors = errors if errors is not None else []
    await page.set_viewport_size({"width": 1440, "height": 900})
    await page.evaluate("() => scrollTo(0, 0)")
    await swarm.clear()
    await swarm.master(True)
    tests = [await test_interactions(page, swarm, errors, instant),
             await test_scroll(page, swarm),
             await test_breakpoints(page, swarm),
             await test_design_compliance(page, swarm, scale)]
    report = QaReport(tests=tests)
    for f in report.failures[:30]:
        await swarm.flag(f.selector, f"B11 · {f.detail}"[:90])
    total = len(report.failures)
    await swarm.hud("Master Cursor · 100% PASSED — 4/4 bài kiểm tra đạt" if report.passed
                    else f"Master Cursor · {total} lỗi · {report.summary()}")
    await asyncio.sleep(0 if instant else 1.5)
    return report


def heal_css(failures: list[QaFailure]) -> list[str]:
    """Deterministic Developer patches, de-duplicated and in a stable order."""
    return list(dict.fromkeys(f.heal for f in failures if f.heal))
