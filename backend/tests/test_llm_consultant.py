"""LLMConsultant with a scripted fake model: no network, no API key."""

import asyncio

import pytest

from chromaswarm.agents.llm import LLMConfig, LLMError, parse_json_object
from chromaswarm.agents.llm_consultant import LLMConsultant
from chromaswarm.main import build_consultant
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Domain


class FakeChat:
    model = "fake-qwen"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user):
        self.calls.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_clicked_option_skips_the_model():
    chat = FakeChat([])
    c = LLMConsultant(chat)
    assert c.interpret("theme", "editorial-luxury") == "editorial-luxury"
    assert c.interpret("color", "dark") == "dark"
    assert chat.calls == []


def test_free_text_is_mapped_and_validated():
    c = LLMConsultant(FakeChat([{"value": "precision-tech"}, {"value": "made-up-theme"}, {"value": None}]))
    assert c.interpret("theme", "nhìn phải ra chất công nghệ, gọn gàng") == "precision-tech"
    assert c.interpret("theme", "kiểu gì cũng được") is None  # value outside the closed set
    assert c.interpret("theme", "vừa sang trọng vừa công nghệ") is None  # model says ambiguous


def test_color_tone_required_and_typed_hex_wins():
    c = LLMConsultant(FakeChat([
        {"mode": "warm-paper", "hex": "#5b6b2f"},
        {"mode": "dark", "hex": "#000000"},
        {"mode": None, "hex": "#1f5fbf"},
        {"mode": "light", "hex": "not-a-color"},
    ]))
    assert c.interpret("color", "nền kem ấm, màu xanh rêu") == "warm-paper #5b6b2f"
    assert c.interpret("color", "tối, mã màu #8A3B12") == "dark #8a3b12"
    assert c.interpret("color", "màu xanh dương") is None  # no tone given -> re-ask
    assert c.interpret("color", "sáng") == "light"


def test_scope_keeps_user_words_only_when_clear():
    c = LLMConsultant(FakeChat([{"clear": True}, {"clear": False}]))
    text = "Dân văn phòng 25-35, chủ yếu điện thoại, muốn họ bấm Đăng ký dùng thử"
    assert c.interpret("scope", text) == text
    assert c.interpret("scope", "ai cũng được") is None


def test_provider_failure_falls_back_to_rules():
    c = LLMConsultant(FakeChat([LLMError("timeout"), LLMError("timeout")]))
    assert c.interpret("margins", "mình thích thoáng đãng") == "airy"
    assert c.classify_domain("web bán giày") is Domain.ECOMMERCE


def test_domain_is_classified_once_per_prompt():
    chat = FakeChat([{"domain": "booking"}])
    c = LLMConsultant(chat)
    assert c.classify_domain("trang cho tiệm nail của chị") is Domain.BOOKING
    assert c.classify_domain("trang cho tiệm nail của chị") is Domain.BOOKING
    assert len(chat.calls) == 1


def test_parse_json_tolerates_think_tags_and_fences():
    assert parse_json_object('<think>hmm {"x":1}</think>\n```json\n{"value": "airy"}\n```') == {"value": "airy"}
    with pytest.raises(LLMError):
        parse_json_object("không có JSON")


def test_config_from_env():
    assert LLMConfig.from_env({}) is None
    cfg = LLMConfig.from_env({
        "CHROMASWARM_LLM_MODEL": "qwen3.8-flash",
        "CHROMASWARM_LLM_BASE_URL": "https://example.test/v1",
        "CHROMASWARM_LLM_API_KEY": "k",
        "CHROMASWARM_LLM_EXTRA_BODY": '{"enable_thinking": false}',
    })
    assert cfg.model == "qwen3.8-flash" and cfg.extra_body == {"enable_thinking": False}
    assert cfg.models["vision"] == "qwen3.8-flash"  # roles fall back to the text model
    with pytest.raises(LLMError):
        LLMConfig.from_env({"CHROMASWARM_LLM_MODEL": "m", "CHROMASWARM_LLM_EXTRA_BODY": "{bad"})


def test_build_consultant_switches_on_env():
    assert getattr(build_consultant({}), "name", "rule-based") == "rule-based"
    c = build_consultant({"CHROMASWARM_LLM_MODEL": "qwen3.8-flash", "CHROMASWARM_LLM_BASE_URL": "http://localhost:1/v1"})
    assert c.name == "llm:qwen3.8-flash"


def test_pipeline_runs_b1_to_b7_with_llm_consultant(tmp_path):
    chat = FakeChat([
        {"domain": "ecommerce"},                      # B1 free-text prompt
        {"value": "editorial-luxury"},                # theme as free text
        {"mode": "warm-paper", "hex": "#8a4b2a"},     # color
        {"clear": True},                              # scope
        {"statement": "Gốm thủ công cần khoảng lặng: mỗi trang chỉ dẫn khách tới một việc là Đặt hàng.",
         "principles": ["Section cách nhau 128px trên lưới 8pt.", "Màu nhấn chỉ cho nút Đặt hàng.",
                        "Dòng chữ giữ trong 45-72ch."]},             # B5 philosophy
        {"theme": None, "layout": None, "margins": None, "mode": "dark", "hex": None},  # B7 feedback
        {"statement": "Bản tối: không gian trầm để sản phẩm gốm nổi bật.",
         "principles": ["Một nút chính.", "Nền tối, chữ sáng.", "Ảnh lớn dẫn mắt."]},  # B5 again
    ])
    runner = PipelineRunner(Deps(consultant=LLMConsultant(chat), artifacts_root=tmp_path))

    async def go():
        await runner.start("q1")
        for a in ["creative", "Mình muốn mở tiệm gốm thủ công trên mạng", "landing", "yên tĩnh, sang, kiểu tạp chí",
                  "flat", "visual-first", "giấy kem, màu nâu đất", "airy",
                  "Người 30-45 tuổi, xem trên điện thoại, muốn họ bấm Đặt hàng",
                  {"assets": [], "references": [], "done": True}]:
            snap = await runner.answer("q1", a)
        at_gate = snap
        snap = await runner.answer("q1", {"approve": False, "feedback": "cho mình bản tông tối nhé"})
        return at_gate, snap

    at_gate, snap = asyncio.run(go())
    assert at_gate["pipeline"].step == "B7"
    assert "Gốm thủ công cần khoảng lặng" in at_gate["pipeline"].design_md
    assert snap["pipeline"].step == "B7"
    assert snap["pipeline"].pillars.color == "dark #8a4b2a"  # tone changed, brand colour kept
    assert "Bản tối" in snap["pipeline"].design_md and "(dark," in snap["pipeline"].design_md
    assert snap["notice"].startswith("Đã cập nhật: Màu sắc → Tối")
    assert chat.replies == []  # every scripted reply consumed, no extra calls


def test_placeholder_key_means_not_configured():
    assert LLMConfig.from_env({"CHROMASWARM_LLM_MODEL": "qwen3.8-flash",
                               "CHROMASWARM_LLM_API_KEY": "sk-your-dashscope-key"}) is None


def test_ungrounded_philosophy_falls_back_to_engine_default(tmp_path):
    """Decision 7: prose citing a number the engines did not produce is rejected."""
    from chromaswarm.engines.design_spec import Philosophy, philosophy_is_grounded

    facts = {"section_padding_px": 128, "line_length": "45-72ch", "accent": "oklch(0.52 0.16 45)"}
    ok = Philosophy(statement="Thoáng.", principles=["Section 128px.", "Dòng 45-72ch.", "Accent oklch(0.52 0.16 45)."])
    bad = Philosophy(statement="Thoáng.", principles=["Section 96px.", "Một nút.", "Một màu."])
    assert philosophy_is_grounded(ok, facts) and not philosophy_is_grounded(bad, facts)


def test_llm_feedback_is_validated_and_merged():
    from chromaswarm.state_machine.pipeline_state import Pillars

    p = Pillars(theme="editorial-luxury", layout="visual-first", color="warm-paper #8a4b2a", margins="airy", scope="x")
    c = LLMConsultant(FakeChat([
        {"theme": "precision-tech", "layout": "not-a-layout", "margins": None, "mode": None, "hex": "#5b6b2f"},
        {"theme": None, "layout": None, "margins": None, "mode": None, "hex": None},
        LLMError("down"),
    ]))
    assert c.interpret_feedback("hiện đại hơn, màu xanh rêu", p) == {"theme": "precision-tech",
                                                                     "color": "warm-paper #5b6b2f"}
    assert c.interpret_feedback("bớt chữ ở hero", p) == {}
    assert c.interpret_feedback("đổi sang tông tối", p) == {"color": "dark #8a4b2a"}  # rules fallback


def test_named_colour_survives_when_the_model_drops_it():
    # Seen live with qwen/qwen3.8-flash: tone understood, "xanh rêu" lost.
    c = LLMConsultant(FakeChat([{"mode": "warm-paper", "hex": None}]))
    assert c.interpret("color", "giấy kem ấm, màu xanh rêu") == "warm-paper #5b6b2f"
