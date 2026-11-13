"""Creative-mode chat: the user talks to Chroma in their own words at any step.

Each message is turned into one `ChatTurn`:

* answer  — the message answers the pending question; it is passed to the graph
            exactly like a button press, so every validation and gate still applies
* ask     — a question or remark; Chroma replies and the pending question stays
* revise  — during B3, change a pillar answered earlier ("cho mình đổi lại màu")

Hard limits enforced here in code, not by the prompt: the chat can never approve
the plan at B7 (only the button can, decision 2), choice answers must be one of
the offered values, and nothing is filled in for the user (decision 8).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from chromaswarm.agents.consultant import fold
from chromaswarm.agents.llm import JSONChat, LLMError

log = logging.getLogger(__name__)

KB = Path(__file__).resolve().parents[3] / "knowledge-base" / "FRONTEND_STANDARDS.md"
PILLARS = ("theme", "layout", "color", "margins", "scope")
APPROVE_HINT = "Khi đã ưng, bạn bấm nút “Duyệt & bắt đầu dựng”; Chroma không tự duyệt thay bạn."


class ChatTurn(BaseModel):
    intent: Literal["answer", "ask", "revise"]
    reply: str = ""
    answer: Any = None  # value to resume the graph with (answer / revise)


class ChatAgent(Protocol):
    def respond(self, step: str, question: dict | None, pillars: dict, design_summary: str,
                history: list[dict], message: str) -> ChatTurn: ...


def _match_option(question: dict, text: str) -> str | None:
    """Free text onto one offered option: exact value, then unique label/value containment."""
    options = question.get("options") or []
    values = {o["value"] for o in options}
    if text in values:
        return text
    t = _plain(text)
    hits = {o["value"] for o in options
            if _plain(o["label"]) in t or _plain(o["value"]) in t or (len(t) >= 4 and t in _plain(o["label"]))}
    return hits.pop() if len(hits) == 1 else None


def _plain(text: str) -> str:
    """Accent-folded, punctuation-free, single-spaced: 'Thân thiện & ấm áp' -> 'than thien am ap'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", fold(text)).split())


def guard(turn: ChatTurn, question: dict | None, message: str) -> ChatTurn:
    """Code-level limits on whatever the model proposed."""
    kind = (question or {}).get("kind")
    if turn.intent == "revise":
        data = turn.answer if isinstance(turn.answer, dict) else {}
        if (question or {}).get("step") != "B3" or data.get("revise") not in PILLARS or not data.get("text"):
            return ChatTurn(intent="ask", reply=turn.reply or "Sau bước hỏi 5 trụ cột, bạn ghi điều muốn đổi ở bước duyệt kế hoạch nhé.")
        return turn
    if turn.intent != "answer":
        return turn
    if question is None:
        return ChatTurn(intent="ask", reply=turn.reply or "Chroma đang xử lý, bạn đợi một chút nhé.")
    if kind == "approval":
        data = turn.answer if isinstance(turn.answer, dict) else {}
        feedback = str(data.get("feedback") or "").strip()
        if data.get("approve") is True or not feedback:
            return ChatTurn(intent="ask", reply=(turn.reply + " " if turn.reply else "") + APPROVE_HINT)
        return ChatTurn(intent="answer", reply=turn.reply, answer={"approve": False, "feedback": feedback})
    if kind == "choice" and question.get("step") == "B3":
        # Pillar questions accept free text: interpret() (rules or LLM) decides, and re-asks if unclear.
        value = turn.answer if turn.answer in {o["value"] for o in question.get("options", [])} else message
        return ChatTurn(intent="answer", reply=turn.reply, answer=value)
    if kind in ("choice", "mode"):
        value = turn.answer if isinstance(turn.answer, str) else None
        value = value if value in {o["value"] for o in question.get("options", [])} else _match_option(question, message)
        if value is None:
            return ChatTurn(intent="ask", reply=turn.reply or "Bạn chọn giúp mình một phương án trong danh sách nhé.")
        return ChatTurn(intent="answer", reply=turn.reply, answer=value)
    if kind in ("clone_source", "assets", "handover", "recommend_url"):
        return turn if turn.answer not in (None, "") else ChatTurn(intent="ask", reply=turn.reply)
    # text / free-text pillar questions: the user's own words go to interpret(), never a paraphrase
    return ChatTurn(intent="answer", reply=turn.reply, answer=message if not isinstance(turn.answer, str) else turn.answer)


class RuleChat:
    """No LLM: every message is an answer to the pending question (the original behaviour)."""

    name = "rule-based"

    def respond(self, step, question, pillars, design_summary, history, message) -> ChatTurn:
        kind = (question or {}).get("kind")
        if kind == "approval":
            return guard(ChatTurn(intent="answer", answer={"approve": False, "feedback": message}), question, message)
        if kind == "assets":
            return ChatTurn(intent="answer", answer={"assets": [{"kind": "other", "path_or_text": message}], "done": True})
        if kind == "handover":
            return ChatTurn(intent="answer", answer={"action": "refine", "feedback": message})
        return guard(ChatTurn(intent="answer", answer=message), question, message)


SYSTEM = """Bạn là Chroma, trợ lý thiết kế web nói tiếng Việt cho người không chuyên. Giọng thân thiện, rõ ràng, câu ngắn,
không sáo rỗng, không dùng emoji. Bạn đang dẫn người dùng qua quy trình 12 bước; câu hỏi đang chờ được cho bên dưới.

Phân loại tin nhắn mới nhất của người dùng thành đúng một intent và trả về MỘT object JSON:
{"intent": "answer" | "ask" | "revise", "reply": "<câu trả lời ngắn cho người dùng, tối đa 80 từ>", "answer": ...}

- "answer": tin nhắn trả lời câu hỏi đang chờ.
  * Câu hỏi có lựa chọn (choice/mode): answer = đúng "value" của một lựa chọn; nếu không chắc lựa chọn nào thì dùng "ask".
  * Câu hỏi trả lời tự do (text, trụ cột): answer = nguyên văn lời người dùng. Không diễn giải lại, không thêm ý.
  * Bước duyệt kế hoạch (approval): chỉ khi người dùng muốn SỬA thì answer = {"approve": false, "feedback": "<điều muốn sửa>"}.
    Bạn KHÔNG BAO GIỜ được duyệt thay người dùng; nếu họ muốn duyệt, dùng "ask" và nhắc họ bấm nút duyệt.
  * Bước tài nguyên (assets): answer = {"assets": [{"kind": "other", "path_or_text": "<từng tài nguyên>"}], "references": [{"url": "<link nếu có>"}], "done": true|false}.
  * Bước bàn giao (handover): answer = {"action": "next", "page": "<value trang>"} hoặc {"action": "refine", "feedback": "<điều muốn sửa>"} hoặc {"action": "finish"}.
  reply: một câu xác nhận ngắn (có thể để trống).
- "ask": người dùng hỏi, thắc mắc, hoặc nói điều chưa trả lời được câu hỏi. reply = trả lời dựa trên tài liệu bên dưới và
  thiết kế hiện tại; kết thúc bằng việc nhắc nhẹ câu hỏi đang chờ. answer = null.
- "revise": chỉ trong bước hỏi 5 trụ cột (B3), khi người dùng muốn đổi lại một trụ cột ĐÃ trả lời trước đó.
  answer = {"revise": "theme|layout|color|margins|scope", "text": "<nguyên văn mong muốn mới>"}.

Không bịa số liệu thiết kế; mọi con số đã có trong phần thiết kế hiện tại hoặc tài liệu chuẩn."""


class LLMChat:
    def __init__(self, chat: JSONChat, kb_path: Path = KB):
        self.chat = chat
        self.name = f"llm:{chat.model}"
        text = kb_path.read_text(encoding="utf-8") if kb_path.exists() else ""
        cut = text.find("## CHƯƠNG 4")
        self.kb = text[: cut if cut > 0 else 20000]  # ch.1-3: consulting, design maths, anti-slop

    def respond(self, step, question, pillars, design_summary, history, message) -> ChatTurn:
        q = question or {}
        context = {
            "buoc_hien_tai": step,
            "cau_hoi_dang_cho": {"kind": q.get("kind"), "text": q.get("text"),
                                 "lua_chon": [{"value": o["value"], "label": o["label"]} for o in q.get("options", [])]},
            "tru_cot_da_co": pillars, "thiet_ke_hien_tai": design_summary[:2500],
            "hoi_thoai_gan_day": history[-8:], "tin_nhan_moi": message,
        }
        system = f"{SYSTEM}\n\n# TÀI LIỆU CHUẨN (trích)\n{self.kb}"
        try:
            data = self.chat.complete_json(system, json.dumps(context, ensure_ascii=False))
            turn = ChatTurn(intent=data.get("intent") if data.get("intent") in ("answer", "ask", "revise") else "ask",
                            reply=str(data.get("reply") or "")[:800], answer=data.get("answer"))
        except (LLMError, ValueError) as e:
            log.warning("chat LLM failed, answering with the rules: %s", e)
            return RuleChat().respond(step, question, pillars, design_summary, history, message)
        return guard(turn, question, message)
