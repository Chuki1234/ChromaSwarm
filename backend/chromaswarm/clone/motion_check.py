"""Clone B2 · effect check: drive the reference page with Playwright and find out how it moves.

A step of its own, after the structure is read. The page is opened again (in a visible window when
CHROMASWARM_HEADED is not 0, with the Motion Inspector cursor) and operated like a person would:

1. before anything scrolls, every below-the-fold element that starts hidden / offset / clipped is noted;
2. parallax: the page is scrolled 400px and elements drifting against it are measured (ratio);
3. a slow scroll, one viewport at a time: each element that starts revealing is timed frame by frame
   (start delay, duration until it is fully shown, starting offset and opacity, easing) — siblings
   that start one after the other give the stagger delay;
4. marquees (infinite sideways animations: cycle length), sticky / blurred header, smooth scroll,
   animation libraries, custom cursors and WebGL canvases;
5. up to 16 cards, rows, links and buttons are hovered for real: lift (px), scale, image zoom,
   preview images, underlines, with their transition duration and easing.

Result: does the page move at all, what moves where (per section), how (a sentence per effect), and
the measured parameters the Motion MCP server builds the CSS with.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import statistics
from collections import Counter, defaultdict

from playwright.async_api import async_playwright

from chromaswarm.playwright_engine.style_dna_scraper import goto_ready
from pydantic import BaseModel

from chromaswarm.clone import motion
from chromaswarm.playwright_engine.swarm import Agent, SwarmOverlay

EFFECT_LABEL = {
    "scroll-reveal": "Hiện dần khi cuộn", "stagger-cards": "Hiện lần lượt từng thẻ", "parallax": "Parallax",
    "marquee": "Dải chạy ngang", "hover-lift": "Nổi lên khi rê chuột", "hover-zoom": "Phóng ảnh khi rê chuột",
    "hover-image": "Ảnh xem trước khi rê chuột", "underline-link": "Gạch chân link khi rê chuột",
    "sticky-blur": "Header dính, nền mờ", "smooth-scroll": "Cuộn mượt",
}


class MotionItem(BaseModel):
    effect: str
    section: str  # section id, "page" for page-wide
    label: str
    how: str  # how it works, in the user's words
    params: dict = {}


class Model3D(BaseModel):
    """A canvas on the reference (3D scene, WebGL animation): what the rebuild cannot redraw, measured so the
    template keeps a placeholder of exactly its size and the user knows how it behaves."""
    section: str
    top: int
    left: int
    w: int
    h: int
    webgl: bool
    animating: bool  # frames change on their own
    motion: float  # share of pixels changing per 0.4s (0-1)
    pointer: bool  # reacts to the mouse moving over it
    colour: str  # dominant colour (hex)
    dark: bool
    how: str


class MotionReport(BaseModel):
    has_motion: bool
    items: list[MotionItem] = []
    libs: list[str] = []
    unsupported: list[str] = []
    steps: int = 0  # viewports scrolled
    hovered: int = 0  # elements hovered for real
    per_section: dict[str, list[str]] = {}  # section id -> effect ids
    models: list[Model3D] = []  # canvases (3D / WebGL scenes) per section
    controls: list[dict] = []  # every button / link hovered: section, kind, size, what changes on hover
    params: dict[str, dict[str, dict]] = {}  # section id -> effect id -> measured parameters


def _med(values: list[float], default: float = 0) -> float:
    values = [v for v in values if v]
    return statistics.median(values) if values else default


def _ease(values: list[str]) -> str:
    ok = [v for v in values if v and (v.startswith("cubic-bezier(") or v in ("ease", "ease-in", "ease-out", "ease-in-out", "linear"))]
    return Counter(ok).most_common(1)[0][0] if ok else ""


def _inside(item: dict, box: dict) -> bool:
    mid = item["top"] + item.get("h", 0) / 2
    return box["top"] <= mid <= box["top"] + max(box["height"], 1)


def build_report(boxes: dict[str, dict], timed: list[dict], post: dict, parallax: list[dict], steps: int,
                 header: str | None = "site-header") -> MotionReport:
    """Effects per section with their measured parameters, from the raw probe results."""
    per: dict[str, list[str]] = defaultdict(list)
    params: dict[str, dict[str, dict]] = defaultdict(dict)
    items: list[MotionItem] = []

    def add(sid: str, effect: str, how: str, prm: dict) -> None:
        if effect in per[sid]:
            return
        per[sid].append(effect)
        params[sid][effect] = {k: v for k, v in prm.items() if v not in (None, "", 0)}
        items.append(MotionItem(effect=effect, section=sid, label=EFFECT_LABEL.get(effect, effect), how=how, params=params[sid][effect]))

    revealed = post.get("revealed", [])
    for sid, box in boxes.items():
        here = [t for t in timed if _inside(t, box) and t.get("end") is not None]
        loose = [r for r in revealed if _inside(r, box)]
        if here or loose:
            groups: dict[int, list[dict]] = defaultdict(list)
            for t in here:
                groups[t["parent"]].append(t)
            big = max(groups.values(), key=len) if groups else []
            loose_groups = Counter(r["parent"] for r in loose)
            stagger = len(big) >= 3 or (loose_groups and max(loose_groups.values()) >= 3)
            dur = _med([(t["end"] - (t["start"] or 0)) for t in here]) or _med([t["cssMs"] for t in here], 600)
            dur = round(max(150, min(dur, 1500)) / 10) * 10
            dist = round(_med([abs(t["fromY"]) for t in here]))
            ease = _ease([t["ease"] for t in here])
            starts = sorted(t["start"] or 0 for t in big)
            gap = round(_med([b - a for a, b in zip(starts, starts[1:]) if b - a > 15])) if len(starts) >= 2 else 0
            effect = "stagger-cards" if stagger else "scroll-reveal"
            how = (f"{'Từng thẻ hiện lần lượt' if stagger else 'Khối hiện dần'} khi cuộn tới: mờ → rõ"
                   + (f", trượt lên {dist}px" if dist else "") + f" trong {dur}ms" + (f" ({ease})" if ease else "")
                   + (f", thẻ sau trễ {gap}ms" if stagger and gap else ""))
            add(sid, effect, how, {"duration_ms": dur, "distance_px": dist, "easing": ease, "stagger_ms": gap})
        drift = [p for p in parallax if _inside(p, box)]
        if drift:
            ratio = _med([abs(p.get("ratio", 0)) for p in drift], 0.1)
            add(sid, "parallax", f"Ảnh trôi lệch nhịp cuộn khoảng {round(ratio * 100)}% (chậm/nhanh hơn trang)",
                {"distance_px": round(min(80, max(12, ratio * 200)))})
        loops = [m for m in post.get("marquee", []) if _inside(m, box)]
        if loops:
            cycle = round(_med([m.get("cycle", 0) for m in loops], 30))
            add(sid, "marquee", f"Dải chạy ngang liên tục, một vòng khoảng {cycle}s, dừng khi rê chuột",
                {"cycle_s": max(6, min(cycle, 120))})
        hov = [h for h in post.get("hover", []) if _inside(h, box)]
        for effect in dict.fromkeys(e for h in hov for e in h.get("effects", [])):
            hp = [h["params"] for h in hov if effect in h.get("effects", []) and h.get("params")]
            dur = round(_med([x["duration_ms"] for x in hp], 300))
            ease = _ease([x["easing"] for x in hp])
            if effect == "hover-lift":
                lift = round(_med([x["lift_px"] for x in hp]))
                scale = _med([x["scale"] for x in hp if x["scale"] != 1], 1)
                how = ("Rê chuột: " + (f"nổi lên {lift}px" if lift else "nổi lên") + (f", phóng {scale:g}×" if scale != 1 else "")
                       + f", đổ bóng sâu hơn, {dur}ms")
                add(sid, effect, how, {"duration_ms": dur, "easing": ease, "distance_px": lift, "scale": scale if scale != 1 else 0})
            elif effect == "hover-zoom":
                zoom = _med([x["zoom"] for x in hp if x["zoom"] != 1], 1.05)
                add(sid, effect, f"Rê chuột: ảnh trong thẻ phóng {zoom:g}× trong khung, {dur}ms",
                    {"duration_ms": dur, "easing": ease, "scale": zoom})
            elif effect == "hover-image":
                add(sid, effect, f"Rê chuột lên từng dòng: ảnh xem trước hiện ra, {dur}ms", {"duration_ms": dur, "easing": ease})
            elif effect == "underline-link":
                add(sid, effect, f"Rê chuột lên link: gạch chân chạy ra, {dur}ms", {"duration_ms": dur, "easing": ease})
    if header:
        if post.get("sticky"):
            blur = post.get("blurPx") or 0
            add(header, "sticky-blur", "Header dính đầu trang khi cuộn" + (f", nền mờ blur {blur}px" if blur else ""),
                {"blur_px": blur})
        if post.get("smooth"):
            add(header, "smooth-scroll", "Cuộn mượt" + (" (Lenis)" if "Lenis" in post.get("libs", []) else ""), {})
    return MotionReport(has_motion=bool(items), items=items, libs=post.get("libs", []), unsupported=post.get("unsupported", []),
                        steps=steps, hovered=len(post.get("hover", [])), per_section=dict(per), params=dict(params))


CANVAS_JS = r"""() => [...document.querySelectorAll("canvas")].map(c => {
  const r = c.getBoundingClientRect();
  let webgl = false;
  try { webgl = !!(c.getContext("webgl2") || c.getContext("webgl")); } catch (e) {}
  return { top: Math.round(r.top + scrollY), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), webgl };
}).filter(c => c.w >= 150 && c.h >= 150)"""

DIFF_JS = r"""async (shots) => {
  // Pixel difference between consecutive screenshots of one canvas + its dominant colour (in the browser).
  const load = src => new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.src = src; });
  const imgs = await Promise.all(shots.map(load));
  const W = 96, H = Math.max(1, Math.round(96 * imgs[0].height / imgs[0].width));
  const px = imgs.map(i => { const c = document.createElement("canvas"); c.width = W; c.height = H;
                             const g = c.getContext("2d"); g.drawImage(i, 0, 0, W, H); return g.getImageData(0, 0, W, H).data; });
  const changed = (a, b) => { let n = 0; for (let k = 0; k < a.length; k += 4)
    if (Math.abs(a[k] - b[k]) + Math.abs(a[k+1] - b[k+1]) + Math.abs(a[k+2] - b[k+2]) > 30) n++; return n / (a.length / 4); };
  const diffs = []; for (let k = 1; k < px.length; k++) diffs.push(changed(px[k - 1], px[k]));
  let r = 0, g = 0, b = 0; const d = px[0];
  for (let k = 0; k < d.length; k += 4) { r += d[k]; g += d[k+1]; b += d[k+2]; }
  const n = d.length / 4; r = Math.round(r / n); g = Math.round(g / n); b = Math.round(b / n);
  return { diffs, colour: "#" + [r, g, b].map(v => v.toString(16).padStart(2, "0")).join(""), lum: (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 };
}"""


async def probe_models(page, boxes: dict[str, dict], overlay=None) -> list[Model3D]:
    """Watch every large canvas for a moment: does it move on its own, does it follow the mouse."""
    import base64
    out: list[Model3D] = []
    for c in (await page.evaluate(CANVAS_JS))[:6]:
        sid = next((k for k, b in boxes.items() if b["top"] <= c["top"] + c["h"] / 2 <= b["top"] + max(b["height"], 1)), "page")
        await page.evaluate("(y) => scrollTo(0, y)", max(0, c["top"] - 120))
        await asyncio.sleep(0.5)
        top = await page.evaluate("(y) => y - scrollY", c["top"])
        clip = {"x": max(0, c["left"]), "y": max(0, top), "width": min(c["w"], 1440 - max(0, c["left"])), "height": min(c["h"], 880)}
        if clip["width"] < 20 or clip["height"] < 20:
            continue
        if overlay:
            with contextlib.suppress(Exception):
                await overlay.note(Agent.INSPECTOR, f"Quan sát canvas {c['w']}×{c['h']}px: chuyển động, phản ứng chuột")
        shots = []
        for _ in range(3):
            shots.append("data:image/png;base64," + base64.b64encode(await page.screenshot(clip=clip)).decode())
            await asyncio.sleep(0.4)
        await page.mouse.move(clip["x"] + clip["width"] * 0.2, clip["y"] + clip["height"] * 0.5)
        await asyncio.sleep(0.2)
        a = await page.screenshot(clip=clip)
        await page.mouse.move(clip["x"] + clip["width"] * 0.8, clip["y"] + clip["height"] * 0.3, steps=8)
        await asyncio.sleep(0.4)
        b = await page.screenshot(clip=clip)
        await page.mouse.move(2, 2)
        idle = await page.evaluate(DIFF_JS, shots)
        moved = await page.evaluate(DIFF_JS, ["data:image/png;base64," + base64.b64encode(x).decode() for x in (a, b)])
        motion = max(idle["diffs"] or [0])
        animating = motion > 0.01
        pointer = moved["diffs"][0] > max(0.02, motion * 2.5)
        kind = "mô hình 3D (WebGL)" if c["webgl"] else "hình vẽ canvas"
        how = (f"{kind.capitalize()} {c['w']}×{c['h']}px, "
               + (f"tự chuyển động liên tục (~{round(motion * 100)}% điểm ảnh đổi mỗi 0,4s)" if animating else "đứng yên khi không tương tác")
               + (", phản ứng khi rê chuột" if pointer else ", không phản ứng khi rê chuột")
               + f", tông {'tối' if idle['lum'] < 0.35 else 'sáng'} (màu chủ đạo {idle['colour']}). "
               + "Chưa vẽ lại được bằng CSS: bản dựng chừa đúng khung này.")
        out.append(Model3D(section=sid, top=c["top"], left=c["left"], w=c["w"], h=c["h"], webgl=c["webgl"],
                           animating=animating, motion=round(motion, 3), pointer=pointer, colour=idle["colour"],
                           dark=idle["lum"] < 0.35, how=how))
    return out


def _headed() -> bool:
    return os.environ.get("CHROMASWARM_HEADED", "1") != "0"


async def inspect_motion(url: str, boxes: dict[str, dict], headed: bool | None = None,
                         width: int = 1440, height: int = 900) -> MotionReport:
    """Open the reference, operate it and measure every effect (module docstring)."""
    headed = _headed() if headed is None else headed
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await goto_ready(page, url)
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=8_000)
            overlay = None
            if headed:
                with contextlib.suppress(Exception):
                    overlay = await SwarmOverlay.attach(page, speed=1.4)
                    await overlay.hud("Kiểm tra hiệu ứng · Playwright đang thao tác trang mẫu")

            async def say(text: str) -> None:
                if overlay:
                    with contextlib.suppress(Exception):
                        await overlay.note(Agent.INSPECTOR, text)

            parallax: list[dict] = []
            with contextlib.suppress(Exception):
                await page.evaluate(motion.PRE_JS)
                await say("Tìm phần tử ẩn chờ hiện khi cuộn")
                parallax = await page.evaluate(motion.PARALLAX_JS)
            total = await page.evaluate("() => document.documentElement.scrollHeight")
            timed: list[dict] = []
            steps = 0
            y = 0
            while y < total and steps < 40:
                steps += 1
                await say(f"Cuộn thử {steps} · đo thời gian hiện của từng khối")
                with contextlib.suppress(Exception):
                    timed += await page.evaluate(motion.STEP_JS, y)
                y += int(height * 0.7)
                total = await page.evaluate("() => document.documentElement.scrollHeight")
            await page.evaluate("() => scrollTo(0, document.documentElement.scrollHeight)")
            await asyncio.sleep(0.4)

            async def on_hover(sel: str, i: int, n: int, kind: str) -> None:
                if overlay:
                    await page.evaluate(f"document.querySelector('{sel}')?.scrollIntoView({{block: 'center'}})")
                    await overlay.move(Agent.INSPECTOR, sel)
                    await say(f"Rê chuột thử {i + 1}/{n} · {kind}")

            post: dict = {}
            with contextlib.suppress(Exception):
                post = await motion.probe(page, on_hover=on_hover if overlay else None)
            models: list[Model3D] = []
            with contextlib.suppress(Exception):
                models = await probe_models(page, boxes, overlay)
            controls: list[dict] = []
            with contextlib.suppress(Exception):
                controls = await motion.sweep_controls(page, on_hover=on_hover if overlay else None)
            if overlay:
                with contextlib.suppress(Exception):
                    await overlay.hud(None)
        finally:
            await browser.close()
    report = build_report(boxes, timed, post, parallax, steps)
    for m in models:
        report.items.append(MotionItem(effect="canvas-3d", section=m.section, label="Mô hình 3D / canvas", how=m.how,
                                       params={"w": m.w, "h": m.h}))
    report.models = models
    for ctl in controls:
        ctl["section"] = next((k for k, b in boxes.items() if b["top"] <= ctl["top"] + ctl["h"] / 2 <= b["top"] + max(b["height"], 1)), "page")
    report.controls = controls
    report.hovered = max(report.hovered, len(controls))
    report.has_motion = report.has_motion or any(m.animating for m in models)
    return report


def summary(report: MotionReport) -> str:
    """One line for the Studio notice."""
    if not report.has_motion:
        return (f"Kiểm tra hiệu ứng: đã cuộn {report.steps} màn hình và rê chuột {report.hovered} phần tử — "
                "trang mẫu không có hiệu ứng hay animation nào đáng kể.")
    kinds = list(dict.fromkeys(i.label.lower() for i in report.items))
    out = (f"Kiểm tra hiệu ứng: đã cuộn {report.steps} màn hình và rê chuột {report.hovered} phần tử — "
           f"tìm thấy {len(report.items)} hiệu ứng ({', '.join(kinds)}), đã đo thời gian, độ trượt và easing để dựng lại.")
    if report.libs:
        out += f" Thư viện: {', '.join(report.libs)}."
    if report.unsupported:
        out += f" Không dựng lại được bằng CSS: {', '.join(report.unsupported)}."
    return out
