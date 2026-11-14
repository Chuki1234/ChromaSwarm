"""Design critic (qa/critic.py): validation of the model's JSON and the B11 wiring."""

import asyncio

import pytest
from test_build import HAPPY, FakeBuild, drive

from chromaswarm.agents.llm import LLMError
from chromaswarm.qa.critic import DIMENSIONS, Critique, Issue, overall, parse_critique
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step

GOOD = {"scores": {k: 7 for k in DIMENSIONS}, "strengths": ["Khoảng trắng tốt"],
        "issues": [{"where": "hero", "problem": "Ảnh nhỏ", "fix": "Ảnh tràn màn hình"}], "verdict": "Ổn"}


def test_overall_is_computed_here_not_by_the_model():
    raw = dict(GOOD, overall=10)  # a model-supplied total is ignored
    c = parse_critique(raw, "m")
    assert c.overall == 7.0
    assert overall({k: (10 if k == "modernity" else 5) for k in DIMENSIONS}) > 5  # weights apply


def test_scores_are_clamped_and_every_dimension_is_required():
    raw = dict(GOOD, scores={**GOOD["scores"], "imagery": 14, "color": 0})
    c = parse_critique(raw, "m")
    assert c.scores["imagery"] == 10 and c.scores["color"] == 1
    missing = dict(GOOD, scores={k: 7 for k in list(DIMENSIONS)[:-1]})
    with pytest.raises(LLMError):
        parse_critique(missing, "m")


class CriticBuild(FakeBuild):
    async def critique(self, session, context=""):
        self.log.append("critique")
        return Critique(model="m", scores={k: 8 for k in DIMENSIONS}, overall=8.0, verdict="Đẹp",
                        issues=[Issue(where="hero", problem="Chữ hơi nhỏ", fix="Tăng cỡ display")])


def test_b11_records_the_design_score_and_writes_critique_md(tmp_path):
    fake = CriticBuild()
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=fake))
    p = asyncio.run(drive(runner, "cr1", HAPPY + [{"approve": True}]))["pipeline"]
    assert p.step is Step.B12_HANDOVER and p.qa_passed
    assert p.design_score == 8.0 and p.design_critique == ["hero: Chữ hơi nhỏ → Tăng cỡ display"]
    assert "8.0/10" in (tmp_path / "cr1" / "artifacts" / "CRITIQUE.md").read_text()


def test_no_critic_means_no_score(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=FakeBuild()))
    p = asyncio.run(drive(runner, "cr2", HAPPY + [{"approve": True}]))["pipeline"]
    assert p.qa_passed and p.design_score is None
