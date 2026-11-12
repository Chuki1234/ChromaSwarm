"""LLM-backed B1-B4 consultant (any OpenAI-compatible model, e.g. Qwen).

Same `ConsultantAgent` interface as `RuleBasedConsultant`, so the graph and
the gates do not change. Division of labour:

* Questions, sitemaps and option lists stay deterministic (inherited).
* The LLM only maps free text onto a closed set of values. Its output is
  validated against that set; anything else becomes None and the graph
  re-asks (zero-guessing, CLAUDE.md decision 8).
* A clicked option is accepted without calling the model.
* If the model is unreachable or returns garbage, the rule-based answer is
  used, so a flaky provider never blocks a session.
"""

from __future__ import annotations

import json
import logging

from chromaswarm.agents.consultant import HEX, PILLAR_QUESTIONS, RuleBasedConsultant, merge_color
from chromaswarm.agents.llm import JSONChat, LLMError
from chromaswarm.engines.design_spec import Philosophy
from chromaswarm.engines.palette import Mode
from chromaswarm.state_machine.pipeline_state import Domain, Pillars

log = logging.getLogger(__name__)

BASE_RULES = (
    "Bạn là bộ phân loại câu trả lời cho một trợ lý thiết kế web, người dùng là người Việt không chuyên. "
    "Chỉ trả về MỘT object JSON, không giải thích ngoài JSON. "
    "Không bao giờ đoán: nếu câu trả lời mơ hồ, chung chung (ví dụ 'đẹp là được'), "
    "mâu thuẫn (khớp từ hai lựa chọn trở lên) hoặc lạc đề, hãy trả null."
)

DOMAIN_HINTS = {
    Domain.ECOMMERCE: "bán hàng online, cửa hàng, shop",
    Domain.SAAS: "phần mềm, web app, dashboard, công cụ quản lý",
    Domain.BOOKING: "đặt lịch, đặt bàn, dịch vụ spa/nhà hàng/phòng khám/khách sạn",
    Domain.EDTECH: "khóa học, học trực tuyến",
    Domain.PORTFOLIO: "trang cá nhân, portfolio, hồ sơ năng lực",
}

MODE_HINTS = {
    Mode.LIGHT: "sáng, trắng, trong trẻo",
    Mode.WARM_PAPER: "sáng ấm, giấy kem, dịu mắt",
    Mode.DARK: "nền tối",
}


def _choices(pillar: str) -> dict[str, str]:
    return {o.value: f"{o.label}" + (f" ({o.hint})" if o.hint else "") for o in PILLAR_QUESTIONS[pillar][1]}


class LLMConsultant(RuleBasedConsultant):
    def __init__(self, chat: JSONChat):
        self.chat = chat
        self.name = f"llm:{chat.model}"
        self._domain_cache: dict[str, Domain | None] = {}

    # ------------------------------------------------------------ helpers
    def _ask(self, system: str, payload: dict) -> dict | None:
        try:
            return self.chat.complete_json(system, json.dumps(payload, ensure_ascii=False))
        except LLMError as e:
            log.warning("LLM call failed, falling back to rules: %s", e)
            return None

    # ------------------------------------------------------------ B1
    def classify_domain(self, prompt: str) -> Domain | None:
        # LangGraph re-runs a node on resume: cache so one prompt costs one call.
        if prompt in self._domain_cache:
            return self._domain_cache[prompt]
        allowed = {d.value: hint for d, hint in DOMAIN_HINTS.items()}
        system = (f"{BASE_RULES}\nXếp mô tả dự án vào đúng một loại: {json.dumps(allowed, ensure_ascii=False)}. "
                  'Định dạng: {"domain": "<mã loại>" | null}')
        data = self._ask(system, {"mo_ta_du_an": prompt})
        if data is None:
            result = super().classify_domain(prompt)
        else:
            value = data.get("domain")
            result = Domain(value) if value in allowed else None
        self._domain_cache[prompt] = result
        return result

    # ------------------------------------------------------------ B3
    def interpret(self, pillar: str, answer: str) -> str | None:
        answer = (answer or "").strip()
        if not answer:
            return None
        if pillar != "color" and answer in _choices(pillar):
            return answer  # a clicked option needs no model
        if pillar in ("theme", "layout", "margins"):
            return self._interpret_choice(pillar, answer)
        if pillar == "color":
            return self._interpret_color_llm(answer)
        if pillar == "scope":
            return self._interpret_scope(answer)
        return None

    def _interpret_choice(self, pillar: str, answer: str) -> str | None:
        allowed = _choices(pillar)
        question = PILLAR_QUESTIONS[pillar][0]
        system = (f"{BASE_RULES}\nCâu hỏi đã hỏi: {question}\n"
                  f"Các lựa chọn hợp lệ: {json.dumps(allowed, ensure_ascii=False)}\n"
                  'Định dạng: {"value": "<mã lựa chọn>" | null}')
        data = self._ask(system, {"cau_tra_loi": answer})
        if data is None:
            return super().interpret(pillar, answer)
        value = data.get("value")
        return value if value in allowed else None

    def _interpret_color_llm(self, answer: str) -> str | None:
        modes = {m.value for m in Mode}
        if answer in modes:
            return answer
        system = (f"{BASE_RULES}\nCâu hỏi đã hỏi: {PILLAR_QUESTIONS['color'][0]}\n"
                  f"mode phải là một trong {json.dumps({m.value: h for m, h in MODE_HINTS.items()}, ensure_ascii=False)} "
                  "hoặc null nếu người dùng chưa nói rõ tông sáng/tối. "
                  "hex là mã màu thương hiệu dạng #rrggbb nếu người dùng nêu mã hoặc tên màu cụ thể, ngược lại null. "
                  'Định dạng: {"mode": ... , "hex": ...}')
        data = self._ask(system, {"cau_tra_loi": answer})
        if data is None:
            return super().interpret("color", answer)
        mode = data.get("mode")
        if mode not in modes:
            return None  # tone is required; re-ask
        literal = HEX.search(answer)  # a code the user typed always wins over the model's
        hex_ = literal.group(0).lower() if literal else data.get("hex")
        if isinstance(hex_, str) and HEX.fullmatch(hex_.strip()) and len(hex_.strip()) == 7:
            return f"{mode} {hex_.strip().lower()}"
        return mode

    def _interpret_scope(self, answer: str) -> str | None:
        system = (f"{BASE_RULES}\nCâu hỏi đã hỏi: {PILLAR_QUESTIONS['scope'][0]}\n"
                  "Câu trả lời đủ rõ khi nêu được CẢ đối tượng khách hàng LẪN một hành động chính (CTA). "
                  'Định dạng: {"clear": true | false}')
        data = self._ask(system, {"cau_tra_loi": answer})
        if data is None:
            return super().interpret("scope", answer)
        # keep the user's own words: downstream extract_cta / base_font_for read them
        return answer if data.get("clear") is True else None

    # ------------------------------------------------------------ B7
    def interpret_feedback(self, feedback: str, pillars: Pillars) -> dict[str, str]:
        fb = (feedback or "").strip()
        if not fb:
            return {}
        options = {k: _choices(k) for k in ("theme", "layout", "margins")}
        system = (f"{BASE_RULES}\nNgười dùng vừa xem bản kế hoạch thiết kế và góp ý. "
                  "Chỉ ghi nhận thay đổi được nói RÕ RÀNG về phong cách (theme), bố cục (layout), "
                  "khoảng cách (margins), tông nền (mode) hoặc màu thương hiệu (hex #rrggbb). "
                  "Góp ý về nội dung chữ, hình ảnh, nút bấm... thì để null hết. "
                  f"Giá trị hợp lệ: {json.dumps(options, ensure_ascii=False)}; "
                  f"mode: {json.dumps({m.value: h for m, h in MODE_HINTS.items()}, ensure_ascii=False)}. "
                  'Định dạng: {"theme": .., "layout": .., "margins": .., "mode": .., "hex": ..} (null = không đổi)')
        data = self._ask(system, {"gia_tri_hien_tai": pillars.model_dump(exclude={"scope"}), "gop_y": fb})
        if data is None:
            return super().interpret_feedback(fb, pillars)
        changes = {k: data.get(k) for k in options if data.get(k) in options[k]}
        mode = data.get("mode") if data.get("mode") in {m.value for m in Mode} else None
        literal = HEX.search(fb)
        hex_ = literal.group(0).lower() if literal else data.get("hex")
        hex_ = hex_.strip().lower() if isinstance(hex_, str) and HEX.fullmatch(hex_.strip()) and len(hex_.strip()) == 7 else None
        if color := merge_color(pillars.color, mode, hex_):
            changes["color"] = color
        return {k: v for k, v in changes.items() if v != getattr(pillars, k)}

    # ------------------------------------------------------------ B5
    def write_philosophy(self, facts: dict) -> Philosophy | None:
        system = ("Bạn là giám đốc nghệ thuật viết mục 'Triết lý thiết kế' cho DESIGN.md, bằng tiếng Việt, giọng rõ ràng, "
                  "không sáo rỗng, không dùng từ 'tuyệt vời', 'đẳng cấp'. Chỉ dùng các dữ kiện được cung cấp; "
                  "KHÔNG được tự đặt ra con số, mã màu hay tên phông chữ nào khác. "
                  "statement: 1 câu (tối đa 40 từ) nói tinh thần thiết kế gắn với khách hàng và hành động chính. "
                  "principles: đúng 3 nguyên tắc, mỗi nguyên tắc 1 câu cụ thể có thể kiểm chứng trên giao diện. "
                  'Chỉ trả về JSON: {"statement": "...", "principles": ["...", "...", "..."]}')
        data = self._ask(system, facts)
        if data is None:
            return None
        try:
            return Philosophy.model_validate(data)
        except ValueError:
            log.warning("LLM philosophy has the wrong shape, using the default")
            return None
