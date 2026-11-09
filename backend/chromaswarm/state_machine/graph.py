"""LangGraph wiring of B1-B7 with human-in-the-loop interrupts.

Every node does exactly one thing, then a single router sends the run to the
node for `pipeline.step`. Nodes that need the user call `interrupt(question)`;
the run pauses, the WebSocket forwards the question, and the user's answer
resumes it via `Command(resume=answer)`. Gate checks live in PipelineState, so
a node can never move past a step whose exit criteria are unmet.

Nodes re-execute from the top when resumed (LangGraph semantics), so each node
works on a copy of the state and performs at most one interrupt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from chromaswarm.agents.consultant import (
    ConsultantAgent,
    Option,
    Question,
    RuleBasedConsultant,
    project_title,
    split_color,
)
from chromaswarm.agents.planner import design_inputs, render_plan_md, render_product_md
from chromaswarm.engines.design_spec import build_design_spec, render_design_md, render_tokens_css
from chromaswarm.engines.presets import Theme
from chromaswarm.engines.style_dna import StyleDNA
from chromaswarm.state_machine.pipeline_state import Asset, Domain, PageStatus, PipelineState, Reference, Step

log = logging.getLogger(__name__)


class GraphState(BaseModel):
    pipeline: PipelineState
    notice: str | None = None  # assistant-side message for the UI (e.g. "answer was unclear")


class Deps(BaseModel):
    """Injected services. Swappable for tests and for the Phase 3 Claude agents."""

    model_config = {"arbitrary_types_allowed": True}
    consultant: Any = RuleBasedConsultant()
    artifacts_root: Path = Path(__file__).resolve().parents[3] / "workspaces"
    scrape: Any = None  # async (url) -> StyleDNA; None disables URL scraping


def _copy(state: GraphState) -> PipelineState:
    return state.pipeline.model_copy(deep=True)


_STATE_TYPES = ("PipelineState", "Step", "Domain", "Framework", "PageStatus", "Pillars", "SitemapPage",
                "Reference", "Asset", "HealAttempt")
SERDE = JsonPlusSerializer(allowed_msgpack_modules=[
    ("chromaswarm.state_machine.pipeline_state", name) for name in _STATE_TYPES
] + [("chromaswarm.state_machine.graph", "GraphState")])


def build_graph(deps: Deps | None = None, checkpointer=None):
    deps = deps or Deps()
    agent: ConsultantAgent = deps.consultant

    def write_artifact(p: PipelineState, name: str, content: str) -> None:
        folder = deps.artifacts_root / p.session_id / "artifacts"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(content, encoding="utf-8")

    # ---------------------------------------------------------------- B1
    def b1(state: GraphState) -> dict:
        p = _copy(state)
        if not p.raw_prompt:
            answer = interrupt(Question(step="B1", kind="text", key="raw_prompt",
                                        text="Bạn muốn xây dựng trang web gì? Cứ mô tả bằng lời bình thường.").model_dump())
            p.raw_prompt = str(answer).strip() or None
            return {"pipeline": p, "notice": None}
        if not p.domain:
            p.domain = agent.classify_domain(p.raw_prompt)
            if not p.domain:
                answer = interrupt(Question(
                    step="B1", kind="choice", key="domain", allow_free_text=False,
                    text="Mình chưa chắc đây là loại sản phẩm nào. Trang web của bạn gần nhất với:",
                    options=[Option(value=d.value, label=label) for d, label in (
                        (Domain.ECOMMERCE, "Bán hàng online"), (Domain.SAAS, "Phần mềm / Web app"),
                        (Domain.BOOKING, "Đặt lịch / Dịch vụ"), (Domain.EDTECH, "Khóa học"),
                        (Domain.PORTFOLIO, "Trang cá nhân / Portfolio"))],
                ).model_dump())
                try:
                    p.domain = Domain(answer)
                except ValueError:
                    return {"pipeline": p, "notice": "Vui lòng chọn một trong các loại trên."}
        p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B2
    def b2(state: GraphState) -> dict:
        p = _copy(state)
        pages, first = agent.sitemap_for(p.domain)
        p.sitemap = pages
        listing = "\n".join(f"{n}. {pg.title} — {pg.purpose}" for n, pg in enumerate(pages, 1))
        answer = interrupt(Question(
            step="B2", kind="choice", key="selected_page", allow_free_text=False, recommended=first,
            text=("Để trang web này dùng được như một sản phẩm thật, hệ thống nên gồm các trang sau:\n"
                  f"{listing}\n\nChúng ta xây từng trang một để đạt độ hoàn thiện cao nhất. Bạn muốn bắt đầu từ trang nào?"),
            options=[Option(value=pg.slug, label=pg.title, hint=pg.purpose) for pg in pages],
        ).model_dump())
        if answer not in {pg.slug for pg in pages}:
            return {"pipeline": p, "notice": "Vui lòng chọn một trang trong danh sách."}
        p.selected_page = answer
        next(pg for pg in p.sitemap if pg.slug == answer).status = PageStatus.BUILDING
        p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B3
    def b3(state: GraphState) -> dict:
        p = _copy(state)
        pillar = p.pillars.next_question()
        q = agent.pillar_question(pillar)
        q.note = state.notice
        answer = interrupt(q.model_dump())
        value = agent.interpret(pillar, str(answer))
        if value is None:
            return {"pipeline": p, "notice": "Mình chưa hiểu rõ câu trả lời — bạn chọn một phương án hoặc mô tả cụ thể hơn nhé."}
        setattr(p.pillars, pillar, value)
        if p.can_advance():
            p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B4
    def b4(state: GraphState) -> dict:
        p = _copy(state)
        pending = next((i for i, r in enumerate(p.references)
                        if r.screenshot_path and not r.url and not r.url_recommended), None)
        if pending is not None:
            answer = interrupt(Question(
                step="B4", kind="recommend_url", key=f"reference_url:{pending}",
                text=("Bạn có thể gửi kèm đường dẫn (URL) của trang web trong ảnh này không? Khi có cả Ảnh + Link, "
                      "đội Design dùng Playwright đọc chính xác phông chữ, thông số lề và hiệu ứng để chắt lọc vào "
                      "thiết kế riêng cho bạn. Hệ thống chỉ học đặc trưng thiết kế, không sao chép giao diện gốc."),
            ).model_dump())
            p.references[pending].url_recommended = True
            if answer:
                try:
                    p.references[pending] = p.references[pending].model_copy(
                        update={"url": Reference.model_validate({"url": str(answer)}).url})
                except ValueError:
                    return {"pipeline": p, "notice": "Link chưa hợp lệ — bạn kiểm tra lại giúp mình nhé."}
            if p.can_advance():
                p.advance()
            return {"pipeline": p, "notice": None}

        answer = interrupt(Question(
            step="B4", kind="assets", key="assets",
            text=("Bạn gửi giúp mình các tài nguyên đang có: logo, ảnh sản phẩm thật, slogan/thông điệp chính, "
                  "bảng giá hoặc danh sách sản phẩm. Nếu có trang web bạn thích, gửi ảnh chụp kèm link. "
                  "Chưa có ảnh cũng không sao — bấm “Đã gửi đủ”."),
        ).model_dump())
        data = answer if isinstance(answer, dict) else {}
        for a in data.get("assets", []):
            p.assets.append(Asset.model_validate(a))
        for r in data.get("references", []):
            try:
                p.references.append(Reference.model_validate(r))
            except ValueError:
                continue
        if data.get("done"):
            p.assets_confirmed = True
        if p.can_advance():
            p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B5
    async def b5(state: GraphState) -> dict:
        p = _copy(state)
        dna: StyleDNA | None = None
        url = next((str(r.url) for r in p.references if r.url), None)
        if url and deps.scrape:
            try:
                dna = await deps.scrape(url)
            except Exception as e:  # network / timeout: continue from B3 answers alone
                log.warning("style DNA scrape failed for %s: %s", url, e)
        project = project_title(p.raw_prompt or "")
        spec = build_design_spec(design_inputs(p, project, dna))
        p.design_md = render_design_md(spec)
        p.tokens_css = render_tokens_css(spec)
        write_artifact(p, "DESIGN.md", p.design_md)
        write_artifact(p, "tokens.css", p.tokens_css)
        p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B6
    def b6(state: GraphState) -> dict:
        p = _copy(state)
        project = project_title(p.raw_prompt or "")
        spec = build_design_spec(design_inputs(p, project))
        theme = Theme(p.pillars.theme)
        _, seed, user_supplied = split_color(p.pillars.color or "light", theme)
        seed_note = None if user_supplied else (
            f"Bạn chưa có màu thương hiệu, hệ thống đề xuất màu gốc {seed} theo phong cách đã chọn. "
            "Bạn có thể đổi ở bước duyệt.")
        p.product_md = render_product_md(p, project, seed_note)
        p.plan_md = render_plan_md(p, spec)
        write_artifact(p, "PRODUCT.md", p.product_md)
        write_artifact(p, "PLAN.md", p.plan_md)
        p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B7
    def b7(state: GraphState) -> dict:
        p = _copy(state)
        answer = interrupt(Question(
            step="B7", kind="approval", key="approval", allow_free_text=True,
            text="Đây là bộ 3 tài liệu cho trang này. Bạn duyệt để bắt đầu dựng, hoặc ghi rõ điều muốn đổi.",
        ).model_dump())
        data = answer if isinstance(answer, dict) else {"approve": False, "feedback": str(answer)}
        if data.get("approve") is True:
            p.approve_plan()
        else:
            if fb := (data.get("feedback") or "").strip():
                p.plan_feedback.append(fb)
            p.request_plan_changes()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B8+
    def build_pending(state: GraphState) -> dict:
        return {"notice": "Kế hoạch đã duyệt. Phòng Design & Developer (B8–B12) sẽ được nối ở Phase 4–7."}

    nodes = {"b1": b1, "b2": b2, "b3": b3, "b4": b4, "b5": b5, "b6": b6, "b7": b7, "build_pending": build_pending}
    step_node = {Step.B1_READ_PROMPT: "b1", Step.B2_SITEMAP: "b2", Step.B3_ELICITATION: "b3",
                 Step.B4_ASSETS: "b4", Step.B5_DESIGN_MD: "b5", Step.B6_PLAN: "b6", Step.B7_APPROVAL: "b7"}

    def route(state: GraphState) -> str:
        return step_node.get(state.pipeline.step, "build_pending")

    g = StateGraph(GraphState)
    for name, fn in nodes.items():
        g.add_node(name, fn)
    g.add_conditional_edges(START, route, list(nodes))
    for name in step_node.values():
        g.add_conditional_edges(name, route, list(nodes))
    g.add_edge("build_pending", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver(serde=SERDE))


class PipelineRunner:
    """Session-facing API used by the WebSocket server."""

    def __init__(self, deps: Deps | None = None):
        self.graph = build_graph(deps)

    @staticmethod
    def _config(session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}, "recursion_limit": 200}

    async def snapshot(self, session_id: str) -> dict:
        snap = await self.graph.aget_state(self._config(session_id))
        values = snap.values or {}
        pipeline = values.get("pipeline") if isinstance(values, dict) else None
        if isinstance(pipeline, dict):
            pipeline = PipelineState.model_validate(pipeline)
        question = snap.interrupts[0].value if snap.interrupts else None
        return {"pipeline": pipeline, "question": question,
                "notice": values.get("notice") if isinstance(values, dict) else None,
                "finished": not snap.next and pipeline is not None}

    async def start(self, session_id: str) -> dict:
        snap = await self.graph.aget_state(self._config(session_id))
        if not snap.values:
            await self.graph.ainvoke({"pipeline": PipelineState(session_id=session_id)}, self._config(session_id))
        return await self.snapshot(session_id)

    async def answer(self, session_id: str, value: Any) -> dict:
        # LangGraph cannot resume with None; nodes treat "" as "skipped".
        await self.graph.ainvoke(Command(resume="" if value is None else value), self._config(session_id))
        return await self.snapshot(session_id)
