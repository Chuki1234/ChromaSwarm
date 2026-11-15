"""LLM copywriter (B9): page copy written for this project instead of sample formulas.

The design critic's most repeated complaint on every generated page was the copy:
formula headlines ("…, làm đúng từ chi tiết nhỏ nhất"), generic product names, the
user's own typo as the brand. This module asks the text model (`CHROMASWARM_LLM_MODEL`)
once per page for the visible copy, then validates it in code:

- same shape as the rule-based copy (counts), every string within a length limit;
- no generic marketing phrases (FRONTEND_STANDARDS ch.3 / ch.7);
- no number that is not already in the facts given (decision 7: no invented prices,
  delivery times or guarantees). Prices and the facts strip always stay the rules'.

Anything invalid -> None and the rule-based copy is used. Clone mode on the user's own
site never calls it: their real text wins.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from chromaswarm.agents.llm import JSONChat, LLMConfig, LLMError, OpenAICompatChat
from chromaswarm.developer.content import PageCopy
from chromaswarm.engines.presets import THEMES, Theme
from chromaswarm.state_machine.pipeline_state import PipelineState

log = logging.getLogger(__name__)

LIMITS = {"brand": 28, "announcement": 90, "eyebrow": 40, "headline": 64, "subhead": 170, "closing": 90,
          "title": 56, "body": 220, "name": 44, "note": 96, "category": 24, "q": 70, "a": 200}

BANNED = ["nâng tầm", "tuyệt vời", "đẳng cấp", "hàng đầu", "số 1", "số một", "giải pháp toàn diện",
          "trải nghiệm vượt trội", "chất lượng cao nhất", "làm đúng từ chi tiết nhỏ nhất", "lorem", "ipsum",
          "john doe", "nguyễn văn a", "khám phá ngay thế giới", "mang đến cho bạn"]

SYSTEM = """Bạn là copywriter cấp cao viết chữ cho một trang web tiếng Việt.
Viết như một thương hiệu thật đang bán hàng: cụ thể, ngắn, có hình ảnh, giọng tự nhiên, không sáo rỗng.
Quy tắc bắt buộc:
- Tiếng Việt chuẩn chính tả (sửa lỗi gõ của người dùng, ví dụ "máy tình" -> "máy tính").
- KHÔNG dùng các cụm: """ + ", ".join(f'"{b}"' for b in BANNED) + """.
- KHÔNG tự đặt ra giá tiền, thời gian giao/đổi trả/bảo hành hay phần trăm. Các con số loại này chỉ được lấy từ "du_kien".
- headline: một ý sắc, tối đa 9 từ, không dùng dấu phẩy nối hai vế kiểu công thức, không lặp tên thương hiệu.
- eyebrow: nhãn ngắn phía trên headline (loại sản phẩm / tinh thần), không trùng headline.
- brand: tên hiển thị ngắn trên thanh menu, 1-4 từ, lấy từ lời người dùng (không bịa tên riêng mới);
  nếu "brief_nguoi_dung" có brand thì dùng ĐÚNG tên đó. Tên sản phẩm / danh mục trong brief giữ nguyên.
- announcement: một dòng ưu đãi / cam kết ngắn cho thanh thông báo trên cùng (dựa trên brief, không bịa số).
- Ghi chú sản phẩm KHÔNG nhắc giá (giá đã hiển thị riêng).
- "items" là SẢN PHẨM bán thật (tên + đặc điểm), không phải chính sách hay dịch vụ.
- Giữ đúng SỐ LƯỢNG phần tử như "hinh_dang" (ví dụ story có 3 phần tử thì trả đúng 3).
- Giới hạn ký tự: headline 64, subhead 170, tiêu đề story 56, nội dung story 220, tên sản phẩm 44, ghi chú 96, câu hỏi 70, trả lời 200.
Trả về JSON đúng dạng:
{"brand": "", "eyebrow": "", "headline": "", "subhead": "", "closing": "", "announcement": "",
 "story": [["tiêu đề", "nội dung"], ...], "items": [["tên", "ghi chú ngắn"], ...],
 "cards": [["tên", "ghi chú ngắn"], ...], "categories": ["", ...], "faqs": [["câu hỏi", "trả lời"], ...]}"""

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Commercial claims: a number with a money / time / percent unit. Specs ("3 cổng USB") are fine.
_CLAIM = re.compile(r"(\d+(?:[.,]\d+)*)\s*(?:₫|đ\b|vnđ|%|k\b|nghìn|ngàn|triệu|giờ|h\b|ngày|tuần|tháng|năm)", re.I)


def copy_key(state: PipelineState) -> str:
    """What the copy is written from: a change to any of it rewrites the copy."""
    src = [state.raw_prompt, state.pillars.scope, state.pillars.theme, state.domain, state.selected_page,
           [a.path_or_text for a in state.assets if a.kind in ("copy", "pricing", "other")], state.plan_feedback]
    return hashlib.sha1(json.dumps(src, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def facts_for(state: PipelineState, base: PageCopy) -> dict:
    theme = THEMES[Theme(state.pillars.theme)].label_vi if state.pillars.theme else ""
    return {
        "mo_ta_du_an": state.raw_prompt, "khach_hang_va_hanh_dong": state.pillars.scope, "linh_vuc": str(state.domain),
        "trang": state.selected_page, "phong_cach": theme, "nut_chinh": base.cta,
        "tai_nguyen_nguoi_dung": [a.path_or_text for a in state.assets if a.kind in ("copy", "pricing", "other")][:6],
        "gop_y_nguoi_dung": state.plan_feedback[-3:],
        "brief_nguoi_dung": {k: v for k, v in (state.brief or {}).items()
                             if k in ("brand", "audience", "usp", "categories", "products", "quiz_options") and v},
        "du_kien": {"so_lieu": [f"{v} {k}" for v, k in base.facts], "gia": [i.price for i in base.items if i.price]},
        # Shops show products in the bento too: those cards are the items, never written separately
        # (the design critic caught a "Bộ sưu tập" filled with service policies).
        "hinh_dang": {"story": len(base.story), "items": len(base.items),
                      "cards": 0 if _cards_are_items(base) else len(base.cards),
                      "categories": len(base.categories), "faqs": len(base.faqs)},
        "ban_mau_hien_tai": {"headline": base.headline, "items": [i.name for i in base.items],
                             "faqs": [q for q, _ in base.faqs]},
    }


def _cards_are_items(base: PageCopy) -> bool:
    return [c.name for c in base.cards] == [i.name for i in base.items[:len(base.cards)]]


def _text(v, limit: int) -> str:
    if not isinstance(v, str) or not v.strip():
        raise ValueError("empty")
    v = " ".join(v.split())
    if len(v) > limit:
        raise ValueError(f"too long ({len(v)} > {limit}): {v[:40]}")
    return v


def _pairs(v, n: int, a: str, b: str) -> list[list[str]]:
    if not isinstance(v, list) or len(v) < n:
        raise ValueError(f"expected {n} pairs, got {len(v) if isinstance(v, list) else 0}")
    v = v[:n]
    if not all(isinstance(x, (list, tuple)) and len(x) == 2 for x in v):
        raise ValueError("pair shape")
    return [[_text(x[0], LIMITS[a]), _text(x[1], LIMITS[b])] for x in v]


_PRICE_IN_NOTE = re.compile(r"(?:giá\s*[:\-]?\s*)?\d[\d.,]*\s*(?:₫|đ\b|vnđ)\s*[-–:|·]?\s*", re.I)


def validate(raw: dict, base: PageCopy, facts: dict) -> dict:
    """Shape, length, banned phrases and number grounding. Raises ValueError when anything is off."""
    if (facts.get("brief_nguoi_dung") or {}).get("products"):  # the user's product names stay as written
        names = facts["brief_nguoi_dung"]["products"]
        if isinstance(raw.get("items"), list):
            raw["items"] = [[names[i], x[1]] if i < len(names) and isinstance(x, (list, tuple)) and len(x) == 2 else x
                            for i, x in enumerate(raw["items"])]
    for pool in ("items", "cards"):  # the price is shown on its own; never twice in the note
        if isinstance(raw.get(pool), list):
            raw[pool] = [[x[0], _PRICE_IN_NOTE.sub("", x[1]).strip(" -–:|·") or x[1]]
                         if isinstance(x, (list, tuple)) and len(x) == 2 and isinstance(x[1], str) else x
                         for x in raw[pool]]
    out: dict = {k: _text(raw.get(k), LIMITS[k]) for k in ("brand", "eyebrow", "headline", "subhead", "closing")}
    out["announcement"] = _text(raw["announcement"], LIMITS["announcement"]) if raw.get("announcement") else ""
    if brand := (facts.get("brief_nguoi_dung") or {}).get("brand"):
        out["brand"] = brand  # the user's own brand name, never a rewrite
    out["story"] = _pairs(raw.get("story"), len(base.story), "title", "body")
    out["items"] = _pairs(raw.get("items"), len(base.items), "name", "note")
    if _cards_are_items(base):
        out["cards"] = out["items"][:len(base.cards)]
    else:
        out["cards"] = _pairs(raw.get("cards"), len(base.cards), "name", "note") if base.cards else []
    out["faqs"] = _pairs(raw.get("faqs"), len(base.faqs), "q", "a")
    cats = raw.get("categories")
    if not isinstance(cats, list) or len(cats) < len(base.categories):
        raise ValueError("categories shape")
    out["categories"] = [_text(c, LIMITS["category"]) for c in cats[:len(base.categories)]]
    if out["headline"].lower() == out["eyebrow"].lower():
        raise ValueError("eyebrow repeats the headline")
    # Per field, not all-or-nothing: one invented claim ("cháy 60 giờ") or generic phrase only sends
    # THAT field back to the rule copy; the rest of the written page is kept.
    allowed = set(_NUMBER.findall(json.dumps(facts, ensure_ascii=False)))

    def ok(text: str) -> bool:
        low = text.lower()
        return not any(b in low for b in BANNED) and all(n in allowed for n in _CLAIM.findall(low))

    fallback = {"brand": base.brand, "eyebrow": "", "headline": base.headline, "subhead": base.subhead,
                "closing": base.closing, "announcement": ""}
    replaced = [k for k in fallback if out.get(k) and not ok(out[k])]
    for k in replaced:
        out[k] = fallback[k]
    base_pairs = {"story": [list(x) for x in base.story], "faqs": [list(x) for x in base.faqs],
                  "items": [[i.name, i.note] for i in base.items], "cards": [[c.name, c.note] for c in base.cards]}
    for pool, pairs in base_pairs.items():
        for i, pair in enumerate(out.get(pool) or []):
            if not ok(" ".join(pair)):
                out[pool][i] = pairs[i] if i < len(pairs) else pair
                replaced.append(f"{pool}[{i}]")
    out["categories"] = [c if ok(c) else base.categories[i] for i, c in enumerate(out["categories"])]
    if replaced:
        log.info("copywriter: kept the rule copy for %s (invented claim or generic phrase)", ", ".join(replaced))
    if len(replaced) > 6:  # most of the page would be sample copy again: ask once more
        raise ValueError(f"too many ungrounded fields: {replaced[:4]}")
    return out


class Copywriter:
    def __init__(self, chat: JSONChat):
        self.chat = chat

    def __call__(self, state: PipelineState, base: PageCopy) -> dict | None:
        facts = facts_for(state, base)
        user = json.dumps(facts, ensure_ascii=False)
        for attempt in (1, 2):  # one retry with the validation error spelled out
            try:
                raw = self.chat.complete_json(SYSTEM, user, max_tokens=3000)
                return validate(raw, base, facts)
            except (LLMError, ValueError, TypeError, KeyError, IndexError) as e:
                log.warning("copywriter attempt %d rejected: %s", attempt, e)
                user = json.dumps({**facts, "loi_lan_truoc": str(e)[:200]}, ensure_ascii=False)
        return None


def build_copywriter(env: dict[str, str] | None = None) -> Copywriter | None:
    cfg = LLMConfig.from_env(env)
    return Copywriter(OpenAICompatChat(cfg.for_role("text"))) if cfg else None
