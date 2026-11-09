import asyncio

import pytest

from chromaswarm.agents.consultant import RuleBasedConsultant
from chromaswarm.engines.style_dna import StyleDNA
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def runner(tmp_path):
    return PipelineRunner(Deps(artifacts_root=tmp_path))


async def drive(runner, sid, answers):
    snap = await runner.start(sid)
    trace = [snap]
    for a in answers:
        snap = await runner.answer(sid, a)
        trace.append(snap)
    return trace


HAPPY = [
    "Mình muốn làm web bán đồ nội thất tối giản",  # B1
    "landing",  # B2
    "editorial-luxury", "visual-first", "warm-paper #8a3b12", "airy",  # B3 pillars 1-4
    "Người 30-45 tuổi, xem trên điện thoại, muốn họ bấm Đặt lịch xem showroom",  # B3 scope
    {"assets": [{"kind": "logo", "path_or_text": "logo.svg"}], "references": [], "done": True},  # B4
]


def test_happy_path_reaches_approval_and_writes_artifacts(runner, tmp_path):
    trace = run(drive(runner, "s1", HAPPY))
    first, last = trace[0], trace[-1]
    assert first["question"]["step"] == "B1"
    assert [t["question"]["step"] for t in trace[1:6]] == ["B2", "B3", "B3", "B3", "B3"]
    assert trace[2]["question"]["key"] == "theme" and trace[5]["question"]["key"] == "margins"
    assert last["pipeline"].step is Step.B7_APPROVAL
    assert last["question"]["kind"] == "approval"
    p = last["pipeline"]
    assert p.pillars.clarity_score == 1.0
    assert "Instrument Serif" in p.design_md and "FAIL" not in p.design_md
    assert "data-swarm-section" in p.plan_md and "`cta-primary`" in p.plan_md
    for name in ("DESIGN.md", "PRODUCT.md", "PLAN.md", "tokens.css"):
        assert (tmp_path / "s1" / "artifacts" / name).exists()


def test_b2_advises_full_sitemap_before_building(runner):
    trace = run(drive(runner, "s2", ["Làm web bán giày thể thao"]))
    q = trace[-1]["question"]
    assert q["step"] == "B2" and q["recommended"] == "landing"
    assert {o["value"] for o in q["options"]} >= {"landing", "pdp", "cart", "account"}


def test_unclear_pillar_answer_is_reasked_not_guessed(runner):
    trace = run(drive(runner, "s3", HAPPY[:2] + ["ừm, đẹp là được"]))
    snap = trace[-1]
    assert snap["pipeline"].step is Step.B3_ELICITATION
    assert snap["pipeline"].pillars.theme is None
    assert snap["question"]["key"] == "theme" and snap["question"]["note"]


def test_ambiguous_domain_asks_user(runner):
    trace = run(drive(runner, "s4", ["Làm cho mình một trang web thật đẹp"]))
    q = trace[-1]["question"]
    assert q["step"] == "B1" and q["key"] == "domain"


def test_screenshot_without_url_triggers_recommendation(runner):
    answers = HAPPY[:-1] + [{"assets": [], "references": [{"screenshot_path": "ref.png"}], "done": True}]
    trace = run(drive(runner, "s5", answers))
    q = trace[-1]["question"]
    assert q["kind"] == "recommend_url"
    snap = run(runner.answer("s5", None))  # user skips the URL
    assert snap["pipeline"].step is Step.B7_APPROVAL


def test_url_reference_is_scraped_into_design_md(tmp_path):
    from chromaswarm.engines.style_dna import RawStyleSample, analyze

    async def fake_scrape(url):
        return analyze(RawStyleSample(source_url=url, viewport_w=1440, viewport_h=900, page_height=3000,
                                      backgrounds=[{"color": "#f6f1e8", "area": 1e6}], radii=[0, 0, 2],
                                      border_count=6, block_padding=[128, 96]))

    r = PipelineRunner(Deps(artifacts_root=tmp_path, scrape=fake_scrape))
    answers = HAPPY[:-1] + [{"assets": [], "references": [{"screenshot_path": "a.png", "url": "https://example.com"}],
                             "done": True}]
    snap = run(drive(r, "s6", answers))[-1]
    assert "Nguồn: https://example.com" in snap["pipeline"].design_md
    assert "Ranh giới chống sao chép" in snap["pipeline"].design_md


def test_b7_changes_loop_back_and_approval_unlocks_b8(runner):
    run(drive(runner, "s7", HAPPY))
    snap = run(runner.answer("s7", {"approve": False, "feedback": "Bớt chữ ở hero"}))
    assert snap["pipeline"].step is Step.B7_APPROVAL  # B5 -> B6 regenerated, back at the gate
    assert "Bớt chữ ở hero" in snap["pipeline"].design_md
    snap = run(runner.answer("s7", {"approve": True}))
    assert snap["pipeline"].step is Step.B8_DESIGN
    assert snap["pipeline"].plan_approved
    assert snap["finished"]


def test_consultant_matching():
    c = RuleBasedConsultant()
    assert c.interpret("theme", "Sang trọng như showroom") == "editorial-luxury"
    assert c.interpret("theme", "sang trong, cao cap") == "editorial-luxury"
    assert c.interpret("theme", "vừa sang trọng vừa công nghệ") is None  # ambiguous -> re-ask
    assert c.interpret("layout", "B") == "narrative"
    assert c.interpret("color", "Tối sang trọng, màu nâu đất") == "dark #8a4b2a"
    assert c.interpret("color", "light") == "light"
    assert c.interpret("color", "chưa biết") is None
    assert c.interpret("margins", "gọn gàng, nhiều thông tin") == "dense"
    assert c.interpret("scope", "ai cũng") is None


def test_cta_and_title_extraction():
    from chromaswarm.agents.consultant import extract_cta, project_title

    assert extract_cta("Người 30-45 tuổi, muốn họ bấm Đặt lịch xem showroom") == "Đặt lịch xem showroom"
    assert extract_cta("Dân văn phòng, hành động chính: Mua ngay") == "Mua ngay"
    assert extract_cta("Người trẻ") is None
    assert project_title("Mình muốn làm web bán đồ nội thất gỗ sồi tối giản") == "Web bán đồ nội thất gỗ sồi tối giản"
    long = project_title("Mình muốn làm " + "rất " * 30 + "đẹp")
    assert long.endswith("…") and not long[:-1].endswith(" ")
