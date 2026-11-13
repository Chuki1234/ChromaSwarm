import pytest

from chromaswarm.state_machine.pipeline_state import (
    CODEGEN_TOOLS,
    MAX_HEAL_ITERATIONS,
    Domain,
    GateError,
    PipelineState,
    Reference,
    SitemapPage,
    Step,
    tools_for,
)


def walk_to_b7() -> PipelineState:
    s = PipelineState(session_id="t", mode="creative")
    s.raw_prompt = "Làm web bán đồ nội thất tối giản"
    s.domain = Domain.ECOMMERCE
    s.advance()  # -> B2
    s.sitemap = [SitemapPage(slug="landing", title="Landing", purpose="launch"),
                 SitemapPage(slug="pdp", title="Product Detail", purpose="buy")]
    s.selected_page = "landing"
    s.advance()  # -> B3
    for f in ("theme", "layout", "color", "margins", "scope"):
        setattr(s.pillars, f, "x")
    s.advance()  # -> B4
    s.assets_confirmed = True
    s.advance()  # -> B5
    s.design_md = "# DESIGN"
    s.advance()  # -> B6
    s.product_md, s.plan_md = "# PRODUCT", "# PLAN"
    s.advance()  # -> B7
    assert s.step is Step.B7_APPROVAL
    return s


def test_cannot_skip_b1_without_prompt():
    s = PipelineState(session_id="t")
    with pytest.raises(GateError):
        s.advance()


def test_b3_requires_all_five_pillars_in_order():
    s = PipelineState(session_id="t", step=Step.B3_ELICITATION)
    assert s.pillars.next_question() == "theme"
    assert s.pillars.clarity_score == 0
    s.pillars.theme = "Editorial luxury"
    s.pillars.layout = "Visual-first"
    assert s.pillars.next_question() == "color"
    assert s.pillars.clarity_score == 0.4
    with pytest.raises(GateError):
        s.advance()


def test_screenshot_without_url_requires_recommendation():
    s = PipelineState(session_id="t", step=Step.B4_ASSETS, assets_confirmed=True)
    s.references.append(Reference(screenshot_path="ref.png"))
    assert "reference[0]:recommend_url" in s.missing_for_exit()
    s.references[0].url_recommended = True
    assert s.can_advance()


def test_b7_cannot_be_passed_by_advance():
    s = walk_to_b7()
    with pytest.raises(GateError):
        s.advance()
    s.approve_plan()
    assert s.step is Step.B8_DESIGN


def test_b7_request_changes_goes_back_to_b5():
    s = walk_to_b7()
    s.request_plan_changes()
    assert s.step is Step.B5_DESIGN_MD
    assert s.design_md is None


def test_codegen_tools_locked_before_b8():
    for step in Step:
        granted = tools_for(step) & CODEGEN_TOOLS
        if step in (Step.B9_DEVELOP, Step.B10_INTEGRATE):
            assert granted
        else:
            assert not granted, f"{step} must not grant codegen tools"


def test_heal_loop_is_capped():
    s = walk_to_b7()
    s.approve_plan()
    for _ in range(MAX_HEAL_ITERATIONS):
        s.step = Step.B11_MASTER_QA
        s.record_qa_failure(["overflow@375"])
    assert s.escalated_to_user
    assert s.step is Step.B11_MASTER_QA
    s.advance()
    assert s.step is Step.B12_HANDOVER


def test_build_next_page_keeps_design_md():
    s = walk_to_b7()
    s.approve_plan()
    s.step = Step.B12_HANDOVER
    s.build_next_page("pdp")
    assert s.step is Step.B6_PLAN
    assert s.design_md == "# DESIGN"
    assert s.plan_md is None
    assert {p.slug: p.status for p in s.sitemap} == {"landing": "done", "pdp": "building"}
