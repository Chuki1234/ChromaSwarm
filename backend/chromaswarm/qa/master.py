"""B11 "Cursor Lớn Nhất" — the four Master QA tests of FRONTEND_STANDARDS.md chapter 5.

1. Interactive sweep   — tap size, not covered, hover feedback, click changes state,
                          keyboard focus-visible, no console errors
2. Scroll choreography — sticky header stays legible, nothing stuck at opacity 0, images load
3. 4-breakpoint audit  — 1440/1024/768/375: no horizontal overflow, no text collisions,
                          mobile margins >= 16px, tap targets >= 48px, side-by-side targets >= 8px apart
4. DESIGN.md + anti-slop — fonts match, contrast on every text block, the automatable
                          rules of the 10-point blacklist, and the measurable rules of
                          chapters 6-7 (control borders, labels, links, disabled controls,
                          generic labels, long text, font weights, number format)

The probe (qa_probe.js) only measures; verdicts are computed here. Each failure
carries a `heal` CSS rule when the Developer can patch it deterministically
(written to app/heal.css on the next B9 pass) or a colour reading when the
Design department can repair it in tokens.css; otherwise it is reported as is.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from playwright.async_api import Page
from pydantic import BaseModel

from chromaswarm.engines.color import apca_lc, parse_css_color, wcag_contrast
from chromaswarm.engines.typography import TypeScale
from chromaswarm.playwright_engine.swarm import Agent, ColorReading, Rect, SwarmOverlay, contrast_finding

PROBE_JS = Path(__file__).with_name("qa_probe.js").read_text(encoding="utf-8")
BREAKPOINTS = [(1440, 900, "Desktop"), (1024, 768, "Laptop"), (768, 1024, "Tablet"), (375, 812, "Mobile")]
MIN_TAP = 48  # §5 test 1: 48px (8pt grid), above WCAG's 44px recommendation
# Clone mode rebuilds someone's look on purpose (decision 11, standards §2.5): the house-style rules of
# chapter 2/6 that a reference may break by design are not failures there. Accessibility rules stay
# (contrast, control borders, focus, hover, overflow, collisions, tap targets on phones, broken images).
CLONE_WAIVED = {"font-weights", "slop-2-triple-cards", "slop-3-centered", "slop-7-cta", "long-text", "number-format"}
MIN_TAP_GAP = 8
MOBILE_MARGIN = 16
CONTROL_BORDER_MIN = 3.0  # §2.1 --border-strong
LONG_TEXT_CHARS = 200     # a "long paragraph" for §2.2 / pillar 5 (~3 lines at 65ch)
ACCENT_AREA_MAX = 0.10    # 9/10 modern references keep saturated colour under 5% of the page
# §7.2: link/button labels that say nothing about the destination or action
GENERIC_LABELS = {"xem thêm", "tìm hiểu thêm", "đọc thêm", "bấm vào đây", "nhấn vào đây", "click here",
                  "learn more", "read more", "more", "ok", "here"}
# §7.1: 5+ digit numbers without a thousands separator (4 digits are skipped: years)
BARE_NUMBER = re.compile(r"(?<![\d.,:/@#\-])[1-9]\d{4,}(?![\d.,:/@\-])")
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
            # Clicking the tab / option that is already selected rightly changes nothing.
            selected = await page.evaluate(
                "(s) => { const e = document.querySelector(s); return !!e && ['aria-selected', 'aria-checked', "
                "'aria-pressed'].some((a) => e.getAttribute(a) === 'true'); }", sel)
            before = await _probe(page, "domSig")
            errors_before = len(errors)
            await swarm.pulse()
            await page.mouse.click(pos["x"], pos["y"])
            await page.wait_for_timeout(120 + pause)
            after = await _probe(page, "domSig")
            if before == after and not selected:
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
                                   heal=f"{stop['selector']} {{ background: color-mix(in srgb, var(--bg-primary) 88%, transparent); "
                                        "backdrop-filter: blur(12px); }"))
            break
        if stop["h"] > r["viewport_h"] * 0.2:
            fails.append(QaFailure(test=2, rule="sticky-too-tall", selector=stop["selector"],
                                   detail=f"header cao {stop['h']}px, che hơn 20% màn hình"))
            break
    for sel in r["stuck"]:
        fails.append(QaFailure(test=2, rule="stuck-hidden", selector=sel, detail="phần tử kẹt ở opacity 0 sau khi cuộn",
                               heal=f"{sel} {{ opacity: 1; animation: none; }}"))  # an animation outranks a plain opacity
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
                                       heal=f"@media (max-width: 767px) {{ {t['selector']} {{ display: inline-flex; "
                                            f"align-items: center; justify-content: center; "
                                            f"min-height: {MIN_TAP}px; min-width: {MIN_TAP}px; }} }}"))
        for g in await _probe(page, "tapSpacing", MIN_TAP_GAP):
            fails.append(QaFailure(test=3, rule="tap-spacing", selector=g["a"], viewport=w,
                                   detail=f"cách {g['b']} chỉ {g['gap']}px (cần ≥ {MIN_TAP_GAP}px)",
                                   heal=f"{g['a']} {{ margin-inline-end: {MIN_TAP_GAP}px; }}"))
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
    await swarm.hud("Master Cursor · Bài 4: đối chiếu DESIGN.md, 10 điều cấm & chuẩn thành phần")
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
    comp = await _probe(page, "components", LONG_TEXT_CHARS)
    fails += component_failures(comp, slop["text"])
    checked = len(texts) + len(slop["gradients"]) + slop["headings"] + len(comp["controls"]) + len(comp["labels"])
    return QaTest(test=4, name=TEST_NAMES[4], checked=checked, failures=fails)


def _contrast(a: str, b: str) -> float:
    ca, cb = parse_css_color(a), parse_css_color(b)
    return wcag_contrast(ca[0], cb[0]) if ca and cb else 21.0


def _is_red(color: str) -> bool:
    c = parse_css_color(color)
    return bool(c) and c[0].c > 0.08 and (c[0].h >= 345 or c[0].h <= 40)


def component_failures(comp: dict, page_text: str) -> list[QaFailure]:
    """Verdicts for the measurable rules of FRONTEND_STANDARDS chapters 6-7."""
    fails: list[QaFailure] = []
    for c in comp["controls"]:
        if c["native"]:
            continue  # browser-drawn checkbox/radio: the UA owns its contrast
        edge = _contrast(c["border"], c["outside"]) if c["border_w"] > 0 else 1.0
        fill = _contrast(c["bg"], c["outside"])
        if max(edge, fill) < CONTROL_BORDER_MIN:
            fails.append(QaFailure(test=4, rule="control-border", selector=c["selector"],
                                   detail=f"viền ô nhập chỉ đạt {max(edge, fill):.2f}:1 (cần ≥ 3:1, §2.1 --border-strong)",
                                   # The control's own text colour already passes against
                                   # this background; the token may not (a dark band, a tinted card).
                                   heal=f"{c['selector']} {{ border: 1px solid currentColor; }}"))
        if c["placeholder"] and not c["visible_label"] and not (c["type"] == "search" and c["aria_label"]):
            fails.append(QaFailure(test=4, rule="placeholder-as-label", selector=c["selector"],
                                   detail=f"ô nhập chỉ có placeholder “{c['placeholder'][:30]}”, không có nhãn hiển thị (§6.1)"))
    for a in comp["asterisks"]:
        if _is_red(a["color"]):
            fails.append(QaFailure(test=4, rule="required-red", selector=a["selector"],
                                   detail="dấu * bắt buộc tô đỏ (đỏ là màu lỗi, §6.1)",
                                   heal=f"{a['selector']} {{ color: inherit; }}"))
    for link in comp["links"]:
        if not link["underline"]:
            fails.append(QaFailure(test=4, rule="link-underline", selector=link["selector"],
                                   detail="link trong đoạn văn không gạch chân, chỉ khác chữ thường bằng màu (§2.7)",
                                   heal=f"{link['selector']} {{ text-decoration: underline; text-underline-offset: 3px; }}"))
    for d in comp["disabled"]:
        if not d["explained"]:
            fails.append(QaFailure(test=4, rule="disabled-control", selector=d["selector"],
                                   detail="nút/ô bị vô hiệu hoá mà không có dòng giải thích (§6.4)"))
    for lb in comp["labels"]:
        if lb["text"] in GENERIC_LABELS:
            fails.append(QaFailure(test=4, rule="generic-label", selector=lb["selector"],
                                   detail=f"chữ “{lb['text']}” không mô tả đích đến/hành động (§7.2)"))
    for t in comp["long"]:
        problems, fixes = [], []
        if t["font_size"] < 18:
            problems.append(f"cỡ {t['font_size']:g}px < 18px")
            fixes.append("font-size: 1.125rem;")
        if t["line_height"] < 1.5:
            problems.append(f"line-height {t['line_height']:g} < 1.5")
            fixes.append("line-height: 1.6;")
        if t["align"] == "justify":
            problems.append("căn đều hai bên")
            fixes.append("text-align: left;")
        if problems:
            fails.append(QaFailure(test=4, rule="long-text", selector=t["selector"],
                                   detail=f"đoạn văn dài {t['chars']} ký tự: {', '.join(problems)} (§2.2)",
                                   heal=f"{t['selector']} {{ {' '.join(fixes)} }}"))
    for family, weights in comp["weights"].items():
        if len(weights) > 2:
            fails.append(QaFailure(test=4, rule="font-weights", selector="body",
                                   detail=f"phông “{family}” dùng {len(weights)} độ đậm {weights} (tối đa 2, §2.2)"))
    for r in comp.get("ragged", []):
        fails.append(QaFailure(test=4, rule="card-row-ragged", selector=r["selector"],
                               detail=f"thẻ cùng hàng có ảnh cao lệch nhau {r['heights']}px (§6.6: mép thẻ phải thẳng hàng)"))
    if comp.get("accent_share", 0) > ACCENT_AREA_MAX:
        fails.append(QaFailure(test=4, rule="accent-area", selector="body",
                               detail=f"nền màu bão hoà chiếm {comp['accent_share'] * 100:.0f}% trang "
                                      f"(tối đa {ACCENT_AREA_MAX * 100:.0f}%, màu nhấn dành cho hành động, §2.1)"))
    if m := BARE_NUMBER.search(page_text):
        fails.append(QaFailure(test=4, rule="number-format", selector="body",
                               detail=f"số “{m.group()}” thiếu dấu phân cách hàng nghìn (§7.1)"))
    return fails


# ------------------------------------------------------------------ runner

async def run_master_qa(page: Page, swarm: SwarmOverlay, scale: TypeScale | None = None, *,
                        errors: list[str] | None = None, instant: bool = False, clone: bool = False) -> QaReport:
    errors = errors if errors is not None else []
    await page.set_viewport_size({"width": 1440, "height": 900})
    await page.evaluate("() => scrollTo(0, 0)")
    await swarm.clear()
    await swarm.master(True)
    tests = [await test_interactions(page, swarm, errors, instant),
             await test_scroll(page, swarm),
             await test_breakpoints(page, swarm),
             await test_design_compliance(page, swarm, scale)]
    if clone:
        tests = [t.model_copy(update={"failures": [f for f in t.failures if f.rule not in CLONE_WAIVED]}) for t in tests]
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
