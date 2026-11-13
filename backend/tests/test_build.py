"""Phase 5: B8-B10 wiring, gates and the Design department's token repairs."""

import asyncio
import os

import pytest

from chromaswarm.build.runtime import IntegrationReport, SectionCheck
from chromaswarm.design.dept import TokenChange, TokenFile, fix_contrast, fix_spacing, repair
from chromaswarm.developer.nextjs import WorkspaceFile
from chromaswarm.developer.workspace import TOKENS_PATH, Workspace
from chromaswarm.engines.color import apca_lc, parse_css_color, wcag_contrast
from chromaswarm.playwright_engine.swarm import Agent, ColorReading, Finding, Rect, SectionReport
from chromaswarm.qa.master import QaFailure, QaReport, QaTest
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import GateError, Step

HAPPY = [
    "Mình muốn làm web bán đồ nội thất tối giản", "landing",
    "editorial-luxury", "visual-first", "warm-paper #8a3b12", "airy",
    "Người 30-45 tuổi, xem trên điện thoại, muốn họ bấm Đặt lịch xem showroom",
    {"assets": [], "references": [], "done": True},
]


def qa(*failures: QaFailure) -> QaReport:
    return QaReport(tests=[QaTest(test=n, name=str(n), checked=1, failures=[f for f in failures if f.test == n])
                           for n in (1, 2, 3, 4)])


HOVER = QaFailure(test=1, rule="no-hover", selector="#a", detail="no hover", heal="#a:hover { filter: brightness(.9); }")
DEAD = QaFailure(test=1, rule="no-state-change", selector="#b", detail="dead button")


class FakeBuild:
    def __init__(self, fail_at: str | None = None, qa_results: list[QaReport] | None = None):
        self.log: list[str] = []
        self.fail_at = fail_at
        self.qa_results = list(qa_results or [qa()])
        self.heals: list[list[str]] = []

    async def install_design_system(self, session, tokens_css, keep_existing=False):
        assert ":root" in tokens_css
        self.log.append("tokens-keep" if keep_existing else "tokens")

    async def start_app(self, session, project, spec, route="/"):
        self.log.append(f"start:{route}")
        return "http://localhost:3999" + (route if route != "/" else "")

    async def write_section(self, session, written, copy, page="", route="/"):
        if self.fail_at == written[-1].id:
            raise RuntimeError("npm exploded")
        self.log.append(f"write:{written[-1].id}")

    async def motion(self, session, section, spec, page=""):
        from chromaswarm.mcp_motion.client import MotionEffect
        from chromaswarm.mcp_motion.server import pick_effect
        effect = pick_effect(section.effect or "")
        self.log.append(f"motion:{section.id}")
        return [MotionEffect(effect=effect, section_id=section.id, kind="2d-css", css="x")] if effect else []

    async def refresh_shared(self, session, section, copy, pages):
        self.log.append(f"refresh:{section.id}:{','.join(pages)}")
        self.refreshed_links = copy.nav_links

    async def handover(self, session, options):
        self.log.append("handover")
        self.handover_options = options

    async def check_section(self, session, section_id, spec):
        self.log.append(f"check:{section_id}")
        changes = [TokenChange(token="--text-muted", old="a", new="b", reason="contrast")] if section_id == "hero" else []
        return SectionCheck(section=section_id, changes=changes)

    async def integrate(self, session, planned):
        self.log.append("integrate")
        return IntegrationReport()

    async def heal(self, session, rules, contrast):
        self.heals.append(list(rules))
        self.log.append("heal")
        return []

    async def master_qa(self, session, spec):
        self.log.append("qa")
        return self.qa_results.pop(0) if len(self.qa_results) > 1 else self.qa_results[0]

    async def close(self, session):
        pass


async def drive(runner, sid, answers, progress=None):
    await runner.start(sid)
    if not answers or answers[0] not in ("creative", "clone"):
        answers = ["creative", *answers]  # B1 opens with the mode choice
    snap = None
    for a in answers:
        snap = await runner.answer(sid, a, on_progress=progress)
    return snap


def test_build_runs_pipelined_and_reaches_b11(tmp_path):
    fake = FakeBuild()
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    seen = []

    async def progress(snap):
        seen.append(snap["pipeline"].step)

    snap = asyncio.run(drive(runner, "b1", HAPPY + [{"approve": True}], progress))
    p = snap["pipeline"]
    assert p.step is Step.B12_HANDOVER and p.integrated and p.qa_passed
    assert snap["question"]["kind"] == "handover" and not snap["finished"]  # waiting for the user
    assert p.preview_url == "http://localhost:3999"
    planned = p.sections_planned
    assert planned[0] == "site-header" and planned[-1] == "site-footer"
    # Dev writes N while Design checks N-1; Design always trails by exactly one section.
    work = [e for e in fake.log if e.startswith(("write:", "check:"))]
    assert work[0] == f"write:{planned[0]}"
    for n, sid in enumerate(planned[1:], 1):
        assert work.index(f"write:{sid}") < work.index(f"check:{sid}")
        assert work.index(f"check:{planned[n - 1]}") < work.index(f"check:{sid}")
    assert fake.log[:2] == ["tokens", "start:/"] and fake.log[-3:] == ["integrate", "qa", "handover"]
    assert p.token_changes == ["--text-muted: a → b (contrast)"]
    assert Step.B9_DEVELOP in seen  # progress streamed while building
    assert "Master QA đạt 100%" in snap["question"]["text"]
    # B8.1: the PLAN effects (hero reveal, feature-story parallax) went through the Motion agent
    assert {"motion:hero", "motion:feature-story"} <= set(fake.log)
    assert any("hero: reveal" in m for m in p.motion_effects)


def test_heal_loop_patches_then_passes(tmp_path):
    fake = FakeBuild(qa_results=[qa(HOVER), qa()])
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    p = asyncio.run(drive(runner, "h1", HAPPY + [{"approve": True}]))["pipeline"]
    assert p.qa_passed and p.step is Step.B12_HANDOVER and len(p.heal_history) == 1
    assert fake.heals == [[HOVER.heal]]  # Developer received the patch on the rebuild
    assert fake.log.count("qa") == 2 and "tokens-keep" in fake.log  # earlier token repairs kept


def test_unpatchable_failures_escalate_without_rebuilding(tmp_path):
    fake = FakeBuild(qa_results=[qa(DEAD)])
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    snap = asyncio.run(drive(runner, "h2", HAPPY + [{"approve": True}]))
    p = snap["pipeline"]
    assert p.escalated_to_user and not p.qa_passed and p.step is Step.B12_HANDOVER
    assert fake.log.count("qa") == 1 and fake.heals == []
    assert "dead button" in p.qa_failures[0]


def test_heal_loop_is_capped_at_three(tmp_path):
    from chromaswarm.state_machine.pipeline_state import MAX_HEAL_ITERATIONS

    loops = [qa(QaFailure(test=1, rule="no-hover", selector=f"#x{i}", detail="h", heal=f"#x{i}:hover {{ opacity: .9; }}"))
             for i in range(10)]
    fake = FakeBuild(qa_results=loops)
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    p = asyncio.run(drive(runner, "h3", HAPPY + [{"approve": True}]))["pipeline"]
    assert p.escalated_to_user and len(p.heal_history) == MAX_HEAL_ITERATIONS
    assert fake.log.count("qa") == MAX_HEAL_ITERATIONS


def test_build_failure_stops_with_a_visible_error(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=FakeBuild(fail_at="hero")))
    snap = asyncio.run(drive(runner, "b2", HAPPY + [{"approve": True}]))
    assert snap["finished"] and snap["pipeline"].step is Step.B9_DEVELOP
    assert "npm exploded" in snap["pipeline"].build_error and snap["notice"].startswith("Dừng dựng trang")


def test_without_runtime_pipeline_stops_after_approval(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path))
    snap = asyncio.run(drive(runner, "b3", HAPPY + [{"approve": True}]))
    assert snap["pipeline"].step is Step.B8_DESIGN and "chưa được bật" in snap["notice"]


def test_workspace_writes_are_tool_gated(tmp_path):
    ws = Workspace(tmp_path)
    code = WorkspaceFile(path="app/page.tsx", content="x")
    tokens = WorkspaceFile(path=TOKENS_PATH, content=":root{}")
    with pytest.raises(GateError):
        ws.write(Step.B7_APPROVAL, tokens)  # nothing is written before approval
    with pytest.raises(GateError):
        ws.write(Step.B8_DESIGN, code)  # B8 is Design: tokens yes, components no
    ws.write(Step.B8_DESIGN, tokens)
    ws.write(Step.B9_DEVELOP, code)
    with pytest.raises(GateError):
        ws.write(Step.B9_DEVELOP, WorkspaceFile(path="../escape.txt", content="x"))
    with pytest.raises(GateError):
        ws.write(Step.B11_MASTER_QA, code)  # QA reports, it never edits


def _reading(fg, bg="#ffffff", size=16, weight=400):
    f, b = parse_css_color(fg)[0], parse_css_color(bg)[0]
    return ColorReading(fg=fg, bg=bg, font_size=size, font_weight=weight, rect=Rect(x=0, y=0, w=1, h=1),
                        wcag=round(wcag_contrast(f, b), 2), apca=round(apca_lc(f, b), 1))


def test_contrast_fix_edits_the_token_until_it_passes():
    tokens = TokenFile(":root {\n  --text-primary: oklch(20% 0.01 60);\n  --text-muted: oklch(80% 0.01 60);\n}\n")
    muted = parse_css_color("oklch(80% 0.01 60)")[0]
    from chromaswarm.engines.color import to_hex
    change = fix_contrast(tokens, _reading(to_hex(muted)))
    assert change and change.token == "--text-muted"
    new = parse_css_color(tokens.values()["--text-muted"])[0]
    white = parse_css_color("#fff")[0]
    assert wcag_contrast(new, white) >= 4.5 and abs(apca_lc(new, white)) >= 60
    assert abs(new.h - 60) < 1 and new.l < 0.8  # same hue, only darker
    assert tokens.values()["--text-primary"] == "oklch(20% 0.01 60)"  # untouched


def test_spacing_fix_snaps_base_and_media_declarations():
    css = ":root { --section-y: 72px; }\n@media (min-width: 1024px) { :root { --section-y: 72px; } }\n"
    tokens = TokenFile(css)
    f = Finding(agent=Agent.LAYOUT, section="s", selector="x", rule="grid-8pt", value=72, detail="padding-top 72px")
    change = fix_spacing(tokens, f)
    assert change and change.new == "64px" and tokens.css.count("--section-y: 64px") == 2


def test_repair_leaves_untokenable_findings_for_the_developer():
    tokens = TokenFile(":root { --section-y: 64px; }")
    report = SectionReport(section="s", findings=[
        Finding(agent=Agent.TYPOGRAPHY, section="s", selector="p", rule="line-length", detail="134ch")])
    changes, left = repair(report, tokens)
    assert changes == [] and [f.rule for f in left] == ["line-length"]


@pytest.mark.skipif(os.environ.get("CHROMASWARM_E2E") != "1", reason="real Next.js build; set CHROMASWARM_E2E=1")
def test_end_to_end_real_next_app(tmp_path):
    """B1 -> B11 with the real runtime: npm, next dev, headless Chromium, swarm overlay."""
    from chromaswarm.build.runtime import LocalBuildRuntime

    build = LocalBuildRuntime(tmp_path / "ws", headed=False)
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=build))

    async def go():
        try:
            first = await drive(runner, "e2e", HAPPY + [{"approve": True}])
            # B12: the overlay is gone and the handover bar's button reaches the server callback
            page = build._sessions["e2e"].page
            assert await page.evaluate("() => window.__chromaSwarm.state().installed") is False
            clicked: list = []

            async def record(session, value):
                clicked.append((session, value))

            build.on_choice = record
            await page.evaluate("""() => document.querySelector('chromaswarm-handover').shadowRoot
                                   .querySelector('button.primary').click()""")
            await asyncio.sleep(0.3)
            assert clicked == [("e2e", {"action": "next", "page": "home"})]
            await runner.answer("e2e", {"action": "next", "page": "home"})
            second = await runner.answer("e2e", {"approve": True})
            return first, second
        finally:
            await build.close_all()

    first, second = asyncio.run(go())
    p = first["pipeline"]
    assert p.build_error is None, p.build_error
    assert p.step is Step.B12_HANDOVER and p.integrated
    assert set(p.sections_checked) == set(p.sections_planned)
    assert p.qa_passed, p.qa_failures  # the generated page passes all 4 Master QA tests
    assert any("qua MCP" in m for m in p.motion_effects)  # B8.1 ran through the Motion MCP server
    p2 = second["pipeline"]
    assert p2.build_error is None, p2.build_error
    assert p2.page_routes == {"landing": "/", "home": "/home"} and p2.preview_url.endswith("/home")
    assert p2.qa_passed, p2.qa_failures
    app = tmp_path / "ws" / "e2e" / "app"
    assert (app / "app/page.tsx").exists() and (app / "app/home/page.tsx").exists()
    assert "data-swarm-page" in (app / "app/motion.css").read_text()
    assert (app / "app/motion.css").read_text().count("/* fx */") == 2  # one block per effect, no duplicates
    assert '"/home"' in (app / "components/sections/landing/SiteHeaderSection.tsx").read_text()


def _built(tmp_path, sid, fake=None):
    fake = fake or FakeBuild()
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    asyncio.run(drive(runner, sid, HAPPY + [{"approve": True}]))
    return runner, fake


def test_b12_next_page_keeps_design_and_builds_on_its_own_route(tmp_path):
    runner, fake = _built(tmp_path, "n1")
    first = asyncio.run(runner.snapshot("n1"))["pipeline"]
    assert fake.handover_options[0]["value"] == {"action": "next", "page": "home"}  # browser-window button
    snap = asyncio.run(runner.answer("n1", {"action": "next", "page": "home"}))
    p = snap["pipeline"]
    assert p.step is Step.B7_APPROVAL and snap["question"]["kind"] == "approval"  # new PLAN.md needs approval
    assert p.design_md == first.design_md and p.selected_page == "home"
    snap = asyncio.run(runner.answer("n1", {"approve": True}))
    p = snap["pipeline"]
    assert p.page_routes == {"landing": "/", "home": "/home"}
    assert "start:/home" in fake.log and fake.log.count("tokens-keep") == 1  # tokens of page 1 kept
    assert "refresh:site-header:landing" in fake.log  # page 1's header now links to page 2
    assert ("Home / Storefront", "/home") in fake.refreshed_links
    assert p.step is Step.B12_HANDOVER
    assert [o["value"] for o in snap["question"]["options"]][0] == "catalog"  # landing + home are built


def test_b12_refine_goes_back_through_approval(tmp_path):
    runner, _ = _built(tmp_path, "r1")
    snap = asyncio.run(runner.answer("r1", {"action": "refine", "feedback": ""}))
    assert snap["pipeline"].step is Step.B12_HANDOVER and "ghi rõ" in snap["notice"]
    snap = asyncio.run(runner.answer("r1", {"action": "refine", "feedback": "đổi sang tông tối"}))
    p = snap["pipeline"]
    assert p.step is Step.B7_APPROVAL and p.pillars.color.startswith("dark")
    assert "(dark," in p.design_md and not p.plan_approved


def test_b12_finish_ends_the_session(tmp_path):
    runner, _ = _built(tmp_path, "f1")
    snap = asyncio.run(runner.answer("f1", {"action": "finish"}))
    assert snap["finished"] and snap["pipeline"].handover_closed and "npm run dev" in snap["notice"]


def test_motion_failure_never_stops_the_build(tmp_path):
    class BrokenMotion(FakeBuild):
        async def motion(self, session, section, spec, page=""):
            raise RuntimeError("MCP server not reachable")

    fake = BrokenMotion()
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    p = asyncio.run(drive(runner, "m1", HAPPY + [{"approve": True}]))["pipeline"]
    assert p.step is Step.B12_HANDOVER and p.build_error is None
    assert any("bỏ qua hiệu ứng" in m for m in p.motion_effects)


def test_every_generated_button_has_a_handler():
    """B11 escalates dead buttons; the Developer templates must never produce one."""
    import re

    from chromaswarm.agents.planner import BLUEPRINTS, GENERIC
    from chromaswarm.developer.content import build_copy
    from chromaswarm.developer.nextjs import render_section
    from chromaswarm.state_machine.pipeline_state import Domain, PipelineState

    copy = build_copy(PipelineState(session_id="x", raw_prompt="web bán đồ", domain=Domain.ECOMMERCE))
    from chromaswarm.agents.planner import Section
    from chromaswarm.developer.nextjs import BY_STRUCTURE

    clone_kinds = [Section(id=k, name=k, structure=k, content="x") for k in BY_STRUCTURE]
    for slug, sections in list(BLUEPRINTS.items()) + [("generic", GENERIC), ("clone", clone_kinds)]:
        for section in sections:
            code = render_section(section, copy).content
            for button in re.findall(r"<button\b[^>]*>", code, flags=re.S):
                assert "onClick" in button or 'type="submit"' in button, (slug, section.id, button[:120])
