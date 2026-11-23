"""Clone B11: Master QA's verdict — does the rebuild match the reference's DESIGN.md?

The verdict is the item-by-item check against the design extracted from the reference (clone/conformance.py):

* "Clone thành công": Master QA passed (accessibility: contrast, tap targets, focus, overflow…) and every item
  of the reference's DESIGN.md matches on the rebuild;
* "Gần đạt": QA passed and at least 90% of the items match — the differing ones are listed;
* "Chưa đạt": otherwise.

The other measurements (reading coverage, screenshot / sketch match, 1:1 components, fidelity) are shown as
indicators beside it; they help find where to look but do not decide.
"""

from __future__ import annotations

from pydantic import BaseModel


class Indicator(BaseModel):
    key: str
    label: str
    value: float | None
    detail: str = ""


class Verdict(BaseModel):
    status: str  # "success" | "close" | "failed"
    title: str
    qa_passed: bool
    qa_failures: list[str] = []
    passed: int = 0  # DESIGN.md items that match
    total: int = 0
    pct: float = 0.0
    sections: list[dict] = []  # per section: passed / total / failed items in words
    indicators: list[Indicator] = []
    next_steps: list[str] = []


def judge(p, conformance: dict | None, final_sketch: dict | None = None) -> Verdict:
    c = conformance or {"passed": 0, "total": 0, "pct": 0.0, "sections": []}
    measured = c["total"] > 0
    healed = c.get("healed")
    compare = p.clone_compare or {}
    fs = final_sketch or {}
    indicators = [
        Indicator(key="reading", label="Đọc được trang mẫu (sketch B2)", value=((p.clone.sketch or {}).get("coverage") if p.clone else None)),
        Indicator(key="pixel", label="Ảnh chụp trang cuối giống trang mẫu", value=fs.get("pixel_score")),
        Indicator(key="sketch", label="Sketch trang cuối khớp sketch trang mẫu", value=fs.get("score")),
        Indicator(key="components", label="Nghiệm thu 1:1 từng component", value=compare.get("total")),
        Indicator(key="fidelity", label="Độ giống toàn trang (cùng bộ đọc)", value=p.clone_fidelity),
    ]
    worst = sorted([s for s in c["sections"] if s["total"]], key=lambda s: s["passed"] / s["total"])[:3]
    if measured and p.qa_passed and c["passed"] == c["total"]:
        status, title = "success", f"Clone thành công — khớp {c['passed']}/{c['total']} mục DESIGN.md của trang mẫu"
    elif measured and p.qa_passed and c["pct"] >= 90:
        status, title = "close", f"Gần đạt — khớp {c['passed']}/{c['total']} mục ({c['pct']:g}%)"
    else:
        why = [] if p.qa_passed else ["Master QA chưa qua"]
        if not measured:
            why.append("chưa đối chiếu được với DESIGN.md")
        elif c["passed"] < c["total"]:
            why.append(f"khớp {c['passed']}/{c['total']} mục ({c['pct']:g}%)")
        status, title = "failed", "Chưa đạt — " + "; ".join(why)
    steps = []
    if not p.qa_passed:
        steps.append("Sửa các lỗi Master QA còn lại (tương phản, vùng bấm…), rồi chạy lại B11.")
    for s in worst:
        if s["failed"]:
            steps.append(f"{s['name']}: {s['passed']}/{s['total']} mục — " + "; ".join(s["failed"][:3]))
    if healed:
        title += f" · đã tự sửa {healed['properties']} thuộc tính ({healed['before']}→{c['passed']} mục)"
    return Verdict(status=status, title=title, qa_passed=bool(p.qa_passed), qa_failures=list(p.qa_failures[:6]),
                   passed=c["passed"], total=c["total"], pct=c["pct"], sections=c["sections"], indicators=indicators,
                   next_steps=steps)


def render(v: Verdict, url: str) -> str:
    mark = {"success": "✅", "close": "🟡", "failed": "❌"}[v.status]
    out = ["# CLONE_RESULT.md — Master QA đối chiếu bản dựng với DESIGN.md của trang mẫu", "",
           f"- Trang mẫu: {url}", f"- **{mark} {v.title}**",
           f"- Master QA (tương phản, vùng bấm, focus, tràn khung…): {'qua' if v.qa_passed else 'chưa qua'}"
           + ("" if v.qa_passed else " — " + "; ".join(v.qa_failures[:3])), "",
           "## Từng section", "", "| Section | Khớp | Mục lệch |", "|---|---|---|"]
    for s in v.sections:
        out.append(f"| {s['name']} · `{s['id']}` | {s['passed']}/{s['total']} | " + ("; ".join(s["failed"][:6]) or "—") + " |")
    out += ["", "## Chỉ số tham khảo (không quyết định kết quả)", ""]
    for i in v.indicators:
        out.append(f"- {i.label}: {'—' if i.value is None else f'{i.value:g}%'}")
    if v.next_steps:
        out += ["", "## Cần làm tiếp", *[f"- {s}" for s in v.next_steps]]
    out += ["", "Mỗi mục lấy từ DESIGN.md trích ngược của trang mẫu (khung section, đệm, vị trí, kích thước, kiểu chữ, màu, "
            "bo góc, hiệu ứng). Chữ và hình không được so: clone cấu trúc không chép chúng."]
    return "\n".join(out) + "\n"
