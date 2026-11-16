"""Clone regression suite: a fixed set of reference URLs, read and (optionally) rebuilt and scored.

    uv run python -m chromaswarm.clone.suite                 # reader only (~10s/site): sections vs baseline
    uv run python -m chromaswarm.clone.suite --build         # + full Clone build, fidelity score, compare images
    uv run python -m chromaswarm.clone.suite --only linear,kyoto-demo --build
    uv run python -m chromaswarm.clone.suite --build --update  # accept the current results as the new baseline

Sites and baselines live in `suite.json` next to this file. A run fails (exit 1) when a site's
section sequence differs from its baseline, or its fidelity drops more than `DROP` points below it.
Builds are rule-based and headless (no LLM, no critic) so runs are comparable. Output, one folder per
site: original.png, clone.png, compare.jpg, FIDELITY.md, plus report.md for the whole run.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import sys
import time
from pathlib import Path

SUITE = Path(__file__).with_name("suite.json")
ROOT = Path(__file__).resolve().parents[3]
DROP = 5.0  # fidelity points a site may lose against its baseline before the run fails


def load() -> list[dict]:
    return json.loads(SUITE.read_text(encoding="utf-8"))


async def read_site(site: dict) -> list[str]:
    from chromaswarm.clone.reader import analyse
    a = await analyse(site["url"], owned=False)
    return [s.structure for s in a.sections]


async def build_site(site: dict, out: Path):
    """Full Clone pipeline B1 -> B12 for one site; returns (sections, Fidelity | None, error | None)."""
    from chromaswarm.agents.consultant import RuleBasedConsultant
    from chromaswarm.build.runtime import LocalBuildRuntime
    from chromaswarm.state_machine.graph import Deps, PipelineRunner

    ws = out / "ws"
    shutil.rmtree(ws, ignore_errors=True)
    build = LocalBuildRuntime(ws, headed=False)
    runner = PipelineRunner(Deps(artifacts_root=ws, build=build, consultant=RuleBasedConsultant()))
    sid = site["name"]
    try:
        await runner.start(sid)
        await runner.answer(sid, "clone")
        snap = await runner.answer(sid, {"url": site["url"], "owned": False, "prompt": site["prompt"]})
        for _ in range(3):  # B3 may ask what the reference cannot tell (domain)
            q = snap.get("question")
            if not q or q.get("key") != "domain":
                break
            snap = await runner.answer(sid, site.get("domain", "other"))
        p = snap["pipeline"]
        if p.step.value != "B7":
            return [], None, f"stopped at {p.step.value}: {snap.get('notice') or ''}"
        sections = [s["structure"] for s in p.clone.sections]
        snap = await runner.answer(sid, {"approve": True})
        p = snap["pipeline"]
        if p.build_error:
            return sections, None, p.build_error
        fid = await build.fidelity(sid, site["url"], shots=out)
        return sections, fid, None if fid else "fidelity could not be measured"
    finally:
        await build.close_all()
        # Each build installs its own Next.js (~400MB): keep the sources, drop the installed packages.
        for junk in ("node_modules", ".next"):
            shutil.rmtree(ws / sid / "app" / junk, ignore_errors=True)


async def compare_image(out: Path) -> None:
    """Original and clone side by side (both scaled to 600px wide) as one JPEG, drawn by Chromium."""
    from playwright.async_api import async_playwright
    imgs = {n: base64.b64encode((out / f"{n}.png").read_bytes()).decode() for n in ("original", "clone")
            if (out / f"{n}.png").exists()}
    if len(imgs) < 2:
        return
    html = ("<body style='margin:0;font:14px system-ui;background:#fff;display:flex;gap:24px;padding:16px'>"
            + "".join(f"<div><p style='margin:0 0 8px'>{label}</p><img style='width:600px;display:block;"
                      f"border:1px solid #ddd' src='data:image/png;base64,{imgs[n]}'></div>"
                      for n, label in (("original", "Trang gốc"), ("clone", "Bản clone"))) + "</body>")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1272, "height": 800})
        await page.set_content(html, wait_until="load")
        await page.screenshot(path=str(out / "compare.jpg"), full_page=True, type="jpeg", quality=80)
        await browser.close()


async def run(args) -> int:
    from chromaswarm.clone.fidelity import render_markdown
    sites = load()
    if args.only:
        wanted = set(args.only.split(","))
        sites = [s for s in sites if s["name"] in wanted]
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    rows, failed, results = [], False, {}
    for site in sites:
        out = out_root / site["name"]
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        fid, error = None, None
        try:
            if args.build:
                sections, fid, error = await build_site(site, out)
            else:
                sections = await read_site(site)
        except Exception as e:  # noqa: BLE001 — one broken site must not stop the run
            sections, error = [], f"{type(e).__name__}: {e}"
        expected = site.get("expect")
        same = expected is None or sections == expected
        baseline = site.get("fidelity")
        drop = fid is not None and baseline is not None and fid.total < baseline - DROP
        status = "ERROR" if error else ("DIFF" if not same else ("DROP" if drop else "PASS"))
        failed |= status != "PASS"
        if fid:
            (out / "FIDELITY.md").write_text(render_markdown(fid, site["url"]), encoding="utf-8")
            await compare_image(out)
        results[site["name"]] = {"sections": sections, "fidelity": fid.total if fid else None}
        line = (f"{status:5} {site['name']:<16} {len(sections):>2} sections"
                + (f" · fidelity {fid.summary()}" if fid else "")
                + (f" (baseline {baseline:.0f})" if fid and baseline is not None else "")
                + f" · {time.monotonic() - t0:.0f}s")
        print(line, flush=True)
        if not same and sections:
            print(f"      expected {expected}\n      got      {sections}")
        if error:
            print(f"      {error}")
        rows.append((status, site, sections, fid, error))
        if args.update and not error:
            site["expect"] = sections
            if fid:
                site["fidelity"] = fid.total
    write_report(out_root / "report.md", rows, args.build)
    if args.update:
        everything = {s["name"]: s for s in load()}
        everything.update({s["name"]: s for s in sites})
        SUITE.write_text(json.dumps(list(everything.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"baseline updated in {SUITE}")
    print(f"report: {out_root / 'report.md'}")
    return 1 if failed and not args.update else 0


def write_report(path: Path, rows, built: bool) -> None:
    lines = ["# Clone suite", "", "| Site | Kết quả | Section | Độ giống | Ghi chú |", "| :--- | :--- | ---: | ---: | :--- |"]
    for status, site, sections, fid, error in rows:
        note = error or "; ".join(fid.notes if fid else []) or ""
        lines.append(f"| [{site['name']}]({site['url']}) | {status} | {len(sections)} "
                     f"| {f'{fid.total:.0f}' if fid else ('—' if not built else '?')} | {note} |")
    scored = [r[3].total for r in rows if r[3]]
    if scored:
        lines += ["", f"Trung bình: **{sum(scored) / len(scored):.1f}/100** trên {len(scored)} trang."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Clone regression suite")
    ap.add_argument("--build", action="store_true", help="rebuild each site and score fidelity (~1-2 min/site)")
    ap.add_argument("--only", help="comma-separated site names")
    ap.add_argument("--update", action="store_true", help="accept the current results as the new baseline")
    ap.add_argument("--out", default=str(ROOT / "workspaces" / "_suite"))
    args = ap.parse_args()
    # Comparable runs: rule-based, no LLM copy, no vision critic.
    for key in ("CHROMASWARM_LLM_MODEL", "CHROMASWARM_LLM_MODEL_CODE", "CHROMASWARM_LLM_MODEL_VISION"):
        os.environ[key] = ""
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
