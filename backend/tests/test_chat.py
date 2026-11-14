"""Creative-mode chat: intents, code-level limits, B3 revise, WebSocket wiring."""

import asyncio

from fastapi.testclient import TestClient

from chromaswarm.agents.chat import ChatTurn, LLMChat, RuleChat, guard
from chromaswarm.agents.llm import LLMError
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import Step

APPROVAL = {"step": "B7", "kind": "approval", "options": []}
THEME = {"step": "B3", "kind": "choice", "key": "theme", "options": [
    {"value": "editorial-luxury", "label": "Sang trọng & tĩnh lặng"},
    {"value": "warm-organic", "label": "Thân thiện & ấm áp"}]}
PAGES = {"step": "B2", "kind": "choice", "key": "selected_page", "options": [
    {"value": "landing", "label": "Landing Page"}, {"value": "home", "label": "Home / Storefront"}]}


class FakeJSON:
    model = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def complete_json(self, system, user, images=None):
        self.seen.append((system, user))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_chat_can_never_approve_the_plan():
    t = guard(ChatTurn(intent="answer", answer={"approve": True}), APPROVAL, "ok duyệt đi")
    assert t.intent == "ask" and "Duyệt & bắt đầu dựng" in t.reply
    t = guard(ChatTurn(intent="answer", answer={"approve": False, "feedback": "đổi sang tông tối"}), APPROVAL, "x")
    assert t.intent == "answer" and t.answer == {"approve": False, "feedback": "đổi sang tông tối"}


def test_choice_answers_must_be_offered_values():
    assert guard(ChatTurn(intent="answer", answer="landing"), PAGES, "trang landing").answer == "landing"
    assert guard(ChatTurn(intent="answer", answer="pricing"), PAGES, "trang giá").intent == "ask"
    assert guard(ChatTurn(intent="answer", answer=None), PAGES, "cho mình làm Home / Storefront trước").answer == "home"


def test_free_text_answers_keep_the_users_own_words():
    q = {"step": "B3", "kind": "text", "key": "scope", "options": []}
    t = guard(ChatTurn(intent="answer", answer={"paraphrase": 1}), q, "Khách 25-40, muốn họ bấm Nhắn tin")
    assert t.answer == "Khách 25-40, muốn họ bấm Nhắn tin"


def test_revise_only_during_b3():
    t = guard(ChatTurn(intent="revise", answer={"revise": "color", "text": "nền tối"}), APPROVAL, "x")
    assert t.intent == "ask"
    assert guard(ChatTurn(intent="revise", answer={"revise": "color", "text": "nền tối"}), THEME, "x").intent == "revise"


def test_llm_chat_answers_questions_and_falls_back_on_errors():
    chat = LLMChat(FakeJSON([{"intent": "ask", "reply": "Bento là lưới ô to nhỏ khác nhau.", "answer": None},
                             LLMError("down")]))
    t = chat.respond("B3", THEME, {}, "", [], "Bento là gì vậy?")
    assert t.intent == "ask" and "Bento" in t.reply
    assert "CHƯƠNG 3" in chat.kb and "CHƯƠNG 5" not in chat.kb  # standards ch.1-3 in context
    t = chat.respond("B3", THEME, {}, "", [], "thân thiện ấm áp")  # provider down: rules take over
    assert t.intent == "answer" and t.answer == "thân thiện ấm áp"  # B3's interpret() maps it to warm-organic


def test_rule_chat_routes_messages_by_question_kind():
    r = RuleChat()
    assert r.respond("B7", APPROVAL, {}, "", [], "bớt chữ ở hero").answer == {"approve": False, "feedback": "bớt chữ ở hero"}
    assert r.respond("B4", {"kind": "assets"}, {}, "", [], "logo.svg").answer["done"] is True


def test_revise_changes_an_earlier_pillar_and_keeps_the_pending_question(tmp_path):
    runner = PipelineRunner(Deps(artifacts_root=tmp_path))

    async def go():
        await runner.start("r")
        for a in ["creative", "Mình muốn làm web bán đồ nội thất tối giản", "landing", "editorial-luxury", "flat", "visual-first"]:
            await runner.answer("r", a)
        return await runner.answer("r", {"revise": "theme", "text": "thân thiện ấm áp"})

    snap = asyncio.run(go())
    p = snap["pipeline"]
    assert p.pillars.theme == "warm-organic" and p.step is Step.B3_ELICITATION
    assert snap["question"]["key"] == "color" and snap["notice"] == "Đã đổi Phong cách."


def test_ws_chat_message_answers_the_pending_question():
    from chromaswarm.main import app

    with TestClient(app).websocket_connect("/ws/session/chat-ws") as ws:
        assert ws.receive_json()["question"]["key"] == "mode"
        ws.send_json({"type": "chat", "text": "creative"})
        assert ws.receive_json() == {"type": "chat", "role": "user", "text": "creative"}
        assert ws.receive_json()["question"]["key"] == "raw_prompt"
        ws.send_json({"type": "chat", "text": "Mình muốn làm web bán giày thể thao"})
        assert ws.receive_json()["role"] == "user"
        assert ws.receive_json()["question"]["key"] == "selected_page"
