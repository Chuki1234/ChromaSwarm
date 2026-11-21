"""B9 eyes: each section shot at 1440 / 375, judged, fixed by sight, kept only when better."""

import asyncio

from chromaswarm.developer.stylist import StylePatch
from chromaswarm.qa.section_eye import Verdict, validate
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step

from test_build import DEAD, HAPPY, FakeBuild, drive, qa


def test_verdicts_are_validated_and_ok_means_nothing_fixable_left():
    v = validate({"ok": True, "score": 7, "issues": [{"kind": "spacing", "problem": "Chật", "fix": "Thoáng hơn"},
                                                     {"kind": "weird", "problem": "x", "fix": "y"}]})
    assert v.ok is False and [i.kind for i in v.issues] == ["spacing", "other"]
    assert validate({"ok": "yes", "score": 7}) is None and validate({"ok": True, "score": 42}) is None
    good = validate({"ok": True, "score": 8, "issues": [{"kind": "imagery", "problem": "Ảnh chung chung", "fix": "Ảnh kho"}]})
    assert good.ok and not good.fixable  # a photo problem is reported, not "fixed" with CSS
    assert Verdict(ok=True, score=7).better_than(Verdict(ok=False, score=7))
    assert not Verdict(ok=False, score=6.2).better_than(Verdict(ok=False, score=6))


class EyeBuild(FakeBuild):
    def __init__(self, overflow_on=(), **kw):
        super().__init__(**kw)
        self.layers, self.shots, self.overflow_on = [], [], set(overflow_on)

    async def outline(self, session):
        return "## hero (600px high)\nsection.s\n## faq (400px high)\nsection.s"

    async def write_style_layer(self, session, page, css, step=Step.B10_INTEGRATE):
        self.layers.append(css)

    async def section_shots(self, session, section_id, folder, tag):
        self.shots.append(f"{section_id}:{tag}")
        return {"images": ["data:image/jpeg;base64,AA", "data:image/jpeg;base64,BB"],
                "files": [f"{section_id}-{tag}-desktop.jpg", f"{section_id}-{tag}-mobile.jpg"],
                "overflow": f"{section_id}:{tag}" in self.overflow_on}


class Eye:
    """hero: cramped first, fixed after one try. faq: a fix that overflows the phone is dropped."""

    def __init__(self):
        self.seen = {}

    def look(self, name, purpose, brief, images):
        n = self.seen[name] = self.seen.get(name, 0) + 1
        if name in ("Hero", "FAQ") and n == 1:
            return Verdict.model_validate({"ok": False, "score": 5, "issues": [
                {"kind": "spacing", "problem": "Tiêu đề sát nút", "fix": "Thêm khoảng cách"}]})
        return Verdict(ok=True, score=8)


class Fixer:
    def __init__(self):
        self.calls = []

    def fix_section(self, section_id, notes, outline, images):
        self.calls.append((section_id, notes, outline.splitlines()[0], len(images)))
        return StylePatch(css=f'[data-swarm-section="{section_id}"] h1 {{\n  margin-bottom: 32px;\n}}')

    def refine(self, *a):
        return None


def run(build, fixer, sid, tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path, build=build, stylist=fixer, section_eye=Eye()))
    return asyncio.run(drive(runner, sid, HAPPY + [{"approve": True}]))["pipeline"]


def test_each_section_is_looked_at_before_the_next_and_fixed_by_sight(tmp_path):
    build = EyeBuild(overflow_on={"faq:v1", "faq:v2", "faq:v3"})
    fixer = Fixer()
    p = run(build, fixer, "s-eye", tmp_path)
    assert p.step is Step.B12_HANDOVER
    hero, faq = p.section_reviews["hero"], p.section_reviews["faq"]
    assert hero["ok"] and hero["fixed"] == 1 and hero["first_score"] == 5 and hero["files"][0] == "hero-v1-desktop.jpg"
    assert not faq["ok"] and faq["fixed"] == 0  # the fix overflowed at 375: dropped, review kept honest
    assert fixer.calls[0] == ("hero", ["Tiêu đề sát nút → Thêm khoảng cách"], "## hero (600px high)", 2)
    # looked at in build order: hero (and its re-shot) before the section after it
    assert build.shots.index("hero:v1") < build.shots.index("proof-strip:v0")
    kept = [r for r in p.style_rounds if r["kind"] == "section"]
    assert [(r["section"], r["kept"], r["variant"]) for r in kept] == [
        ("hero", True, None),  # no variant for this hero: fixed by sight
        ("faq", False, "tiêu đề trên, câu hỏi dưới"), ("faq", False, "cột tiêu đề hẹp hơn"),  # variants tried first
        ("faq", False, None)]
    assert "faq" not in build.layers[-1] and "hero" in build.layers[-1]


def test_fixes_that_break_master_qa_are_all_dropped(tmp_path):
    build = EyeBuild(qa_results=[qa(DEAD), qa()])
    p = run(build, Fixer(), "s-eye2", tmp_path)
    sec = [r for r in p.style_rounds if r["kind"] == "section"]
    assert sec and all(r["kept"] is False for r in sec) and p.qa_passed and not p.heal_history
    assert build.layers[-1] == ""


def test_a_named_brand_is_used_instead_of_the_prompt_sentence():
    from chromaswarm.developer.content import named_brand
    assert named_brand("Làm landing page cho phần mềm quản lý kho StockPilot dành cho shop online") == "StockPilot"
    assert named_brand("Web bán trà tên Mộc Trà ở Đà Lạt") == "Mộc Trà"
    assert named_brand("web bán đồ nội thất tối giản") is None



def test_a_variant_is_tried_first_and_kept_when_the_eye_prefers_it(tmp_path):
    build = EyeBuild()
    fixer = Fixer()
    p = run(build, fixer, "s-eye3", tmp_path)
    faq = p.section_reviews["faq"]
    assert faq["ok"] and faq["variant"] == "tiêu đề trên, câu hỏi dưới"
    assert all(c[0] != "faq" for c in fixer.calls)  # no model CSS needed
    assert '[data-swarm-section="faq"] .faq' in build.layers[-1]


def test_the_users_dislikes_reach_every_reviewer():
    from chromaswarm.qa.section_eye import SectionEye
    seen = {}

    class Vision:
        def complete_json(self, system, user, images=None, max_tokens=0):
            seen["user"] = user
            return {"ok": True, "score": 8, "issues": []}

    SectionEye(Vision()).look("Hero", "x", "brief", ["data:image/jpeg;base64,AA"])
    assert "gradient or flat colour block standing in for a photo" in seen["user"]


def test_every_variant_passes_the_layer_rules():
    from chromaswarm.developer.stylist import validate_css
    from chromaswarm.developer.variants import VARIANTS
    for structure, variants in VARIANTS.items():
        for v in variants:
            clean, rejected = validate_css(v.for_section("x"), ["x"])
            assert clean and not rejected, (structure, v.name, rejected)
