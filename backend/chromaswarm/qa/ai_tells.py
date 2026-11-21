"""Words and sentence shapes that make a page read as AI-written: one list for every checker.

Readers spot generated copy by a handful of tells, not by grammar: stock marketing phrases
("nâng tầm", "seamless"), formula sentences ("Sẵn sàng bắt đầu? … chỉ mất một phút",
"X, làm đúng từ chi tiết nhỏ nhất", "không chỉ … mà còn"), emoji in body text, and proof
nobody gave (a 4,9/5 rating, 99,9% uptime, "40+ dự án") on a page for a business that has
not shared those numbers.

Used by:
- developer/copywriter.validate: an LLM field with a tell goes back to the rule copy;
- qa/master test 4 (slop-6-copy): the rendered page text, whatever wrote it;
- tests/test_ai_tells.py: the rule-based sample copy of every domain, VI and EN, is clean.
"""

from __future__ import annotations

import re

# Stock phrases, matched as whole words, case-insensitive.
PHRASES_VI = [
    "nâng tầm", "đẳng cấp", "vượt trội", "đột phá", "bứt phá", "hàng đầu", "số 1", "số một",
    "giải pháp toàn diện", "liền mạch", "mọi lúc mọi nơi", "mọi lúc, mọi nơi", "dễ dàng hơn bao giờ hết",
    "đồng hành cùng bạn", "trên mọi hành trình", "kỷ nguyên mới", "cách mạng hóa", "cách mạng hoá",
    "khơi nguồn", "đánh thức", "chạm đến cảm xúc", "tiềm năng vô hạn", "chúng tôi tự hào",
    "hãy để chúng tôi", "mang đến cho bạn", "vượt mong đợi", "vượt xa mong đợi", "an tâm tuyệt đối",
    "chuẩn mực mới", "bảo mật tuyệt đối", "hoàn hảo tuyệt đối", "định nghĩa lại", "tuyệt vời", "chất lượng cao nhất", "trải nghiệm vượt trội",
    "trải nghiệm đẳng cấp", "làm đúng từ chi tiết nhỏ nhất", "khám phá ngay thế giới", "lorem", "ipsum",
    "john doe", "nguyễn văn a",
]
PHRASES_EN = [
    "elevate your", "unlock the power", "unlock your", "unleash", "seamless", "seamlessly", "empower",
    "revolutionize", "revolutionise", "game-changer", "game changer", "cutting-edge", "next level",
    "in today's fast-paced", "all-in-one solution", "world-class", "best-in-class", "state-of-the-art",
    "supercharge", "harness the power", "look no further", "say goodbye to", "delve", "tailored to your needs",
    "beyond expectations", "exceeded expectations", "done right down to the details", "lorem ipsum",
]

# Formula sentences: (rule, Vietnamese label, pattern).
PATTERNS = [
    ("ready-question", "câu mời kiểu “Sẵn sàng…?”",
     re.compile(r"(?:^|[.!?]\s*)(?:bạn đã )?sẵn sàng\b[^.?!]*\?|\bready to\b[^.?!]*\?", re.I)),
    ("effortless", "hứa hẹn “chỉ mất một phút / vài cú nhấp”",
     re.compile(r"\bchỉ (?:mất|với|trong|cần) (?:một|vài|\d+) (?:phút|giây|cú (?:nhấp|click|chạm)|bước)\b"
                r"|\bin (?:just )?(?:a few clicks|seconds|minutes)\b|\bit takes a minute\b", re.I)),
    ("not-only", "công thức “không chỉ… mà còn” / “hơn cả”",
     re.compile(r"\bkhông chỉ\b.{1,60}?\bmà còn\b|\bhơn cả (?:một|là)\b|\bnot just\b.{1,60}?\bit'?s\b"
                r"|\bmore than just\b", re.I)),
    ("brand-comma-formula", "tiêu đề công thức “Tên, làm …”",
     re.compile(r"^[^,.!?]{1,30}, (?:làm|được làm|done|made|built) (?:đúng|right|for)\b", re.I)),
]
# Proof nobody supplied: ratings, uptime, "40+ clients". Only checked on sample copy (the user's own
# numbers are theirs to state; the copywriter already rejects numbers not in the facts).
PROOF = re.compile(r"\d[.,]\d\s*/\s*5\b|\b99[.,]9+\s*%|\b\d+\+\s*(?:khách|dự án|người dùng|clients|customers|users|projects)"
                   r"|\bhàng (?:nghìn|ngàn|triệu) (?:khách|người)|\b(?:thousands|millions) of (?:happy )?(?:customers|users)", re.I)
# Pictographic emoji only: ✓ ★ → are honest UI glyphs (a done lesson, a rating), not decoration.
EMOJI = re.compile("[\U0001F000-\U0001FAFF]")


def _phrase(p: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(p) + r"(?!\w)", re.I)


_PHRASES = [(p, _phrase(p)) for p in PHRASES_VI + PHRASES_EN]


def find(text: str, *, proof: bool = False, emoji: bool = True) -> list[str]:
    """Every tell in `text`, as a short Vietnamese label naming what was found. Empty = clean."""
    text = " ".join((text or "").split())
    if not text:
        return []
    out = [f"cụm sáo “{p}”" for p, rx in _PHRASES if rx.search(text)]
    out += [f"{label}: “{m.group().strip()[:50]}”" for _, label, rx in PATTERNS if (m := rx.search(text))]
    if proof and (m := PROOF.search(text)):
        out.append(f"số liệu chứng minh không có nguồn: “{m.group()}”")
    if emoji and (m := EMOJI.search(text)):
        out.append(f"emoji trong nội dung: “{m.group()}”")
    return out


def copy_strings(copy) -> list[tuple[str, str]]:
    """(field, text) for every visible line of a PageCopy (duck-typed: no import of developer/)."""
    out: list[tuple[str, str]] = [(k, getattr(copy, k, "") or "") for k in
                                  ("eyebrow", "headline", "subhead", "closing", "announcement", "cta", "cta_secondary")]
    for pool in ("story", "faqs", "tabs", "quotes"):
        out += [(f"{pool}[{i}]", " ".join(x[:1] if pool == "quotes" else x)) for i, x in enumerate(getattr(copy, pool, []))]
    for pool in ("items", "cards"):
        out += [(f"{pool}[{i}]", f"{it.name}. {it.note}") for i, it in enumerate(getattr(copy, pool, []))]
    out += [(f"facts[{i}]", f"{v} {k}") for i, (v, k) in enumerate(getattr(copy, "facts", []))]
    return [(k, v) for k, v in out if v]


def copy_tells(copy, *, proof: bool = True) -> list[tuple[str, str]]:
    """(field, tell) for a PageCopy: what a checker or test reports."""
    return [(field, t) for field, text in copy_strings(copy) for t in find(text, proof=proof)]
