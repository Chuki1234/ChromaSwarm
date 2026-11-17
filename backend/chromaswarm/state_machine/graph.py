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

import asyncio
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
    PILLAR_QUESTIONS,
    SURFACE_QUESTION,
    Option,
    Question,
    RuleBasedConsultant,
    extract_cta,
    interpret_surface,
    project_title,
    split_color,
    surface_in_text,
    surface_question,
)
from chromaswarm.agents.planner import CLONE_PAGE, Section, design_inputs, page_sections, render_plan_md, render_product_md
from urllib.parse import urlparse

from chromaswarm.clone.reader import analyse as analyse_reference
from chromaswarm.clone.reader import clone_limits, guess_domain, wants_exact_copy
from chromaswarm.build.runtime import SectionCheck
from chromaswarm.agents.brief import Brief, mode_from_background
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import copy_key
from chromaswarm.clone.fidelity import render_markdown as render_fidelity
from chromaswarm.qa.critic import render_markdown
from chromaswarm.qa.master import heal_css
from chromaswarm.engines.design_spec import (
    build_design_spec,
    philosophy_facts,
    philosophy_is_grounded,
    render_design_md,
    render_tokens_css,
)
from chromaswarm.engines.presets import SURFACES, Layout, Surface, Theme
from chromaswarm.engines.style_dna import StyleDNA
from chromaswarm.state_machine.pipeline_state import (
    Asset,
    BuildMode,
    CloneSource,
    Pillars,
    SitemapPage,
    Domain,
    PageStatus,
    PipelineState,
    Reference,
    Step,
    tools_for,
)

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
    clone_reader: Any = None  # async (url, owned) -> CloneAnalysis; None = real Playwright reader
    build: Any = None  # BuildRuntime for B8-B10; None stops after approval (B1-B7 only)
    brief_reader: Any = None  # (prompt) -> agents.brief.Brief | None; None = never read a brief
    copywriter: Any = None  # (state, base PageCopy) -> validated copy dict | None; None = rule-based copy


PILLAR_LABELS = {"theme": "Phong cách", "layout": "Bố cục", "color": "Màu sắc", "margins": "Khoảng cách",
                 "surface": "Chất liệu"}


def feedback_notice(changes: dict[str, str]) -> str:
    if not changes:
        return ("Đã ghi góp ý vào DESIGN.md (mục quy tắc) để đội Dev làm theo. "
                "Các lựa chọn phong cách, bố cục, màu và khoảng cách giữ nguyên.")
    labels = {o.value: o.label for q in [*PILLAR_QUESTIONS.values(), SURFACE_QUESTION] for o in q[1]}

    def show(pillar: str, value: str) -> str:
        if pillar == "color":
            mode, *seed = value.split()
            return labels.get(mode, mode) + (f", màu {seed[0]}" if seed else "")
        return labels.get(value, value)

    done = "; ".join(f"{PILLAR_LABELS[k]} → {show(k, v)}" for k, v in changes.items())
    return f"Đã cập nhật: {done}. Tài liệu đã được tạo lại, bạn xem và duyệt nhé."


MISSING_LABELS = {"theme": "phong cách", "layout": "bố cục", "color": "tông màu nền", "margins": "độ thoáng",
                  "scope": "khách hàng & nút chính"}


def scope_gap(draft: str | None) -> str:
    """The half of the B3 scope answer still missing, given what is already known."""
    if not draft:
        return MISSING_LABELS["scope"]
    if extract_cta(draft):
        return "ai là khách hàng chính (độ tuổi, nghề, dùng điện thoại hay máy tính)"
    return "nút QUAN TRỌNG NHẤT bạn muốn khách bấm (ví dụ: Mua ngay, Đặt lịch, Đăng ký)"


def prefill_from_brief(p, brief) -> list[str]:
    """Pillars the brief answers in the user's own words; returns what was filled (for the notice)."""
    labels = {o.value: o.label for q in PILLAR_QUESTIONS.values() for o in q[1]}
    filled: list[str] = []
    for pillar in ("theme", "layout", "margins"):
        value = getattr(brief, pillar)
        if value and not getattr(p.pillars, pillar):
            setattr(p.pillars, pillar, value)
            filled.append(f"{PILLAR_LABELS[pillar]} “{labels.get(value, value)}”")
    mode = brief.mode or (mode_from_background(brief.background) if brief.background else None)
    if mode and not p.pillars.color:
        p.pillars.color = f"{mode} {brief.accent}" if brief.accent else mode
        filled.append(f"Màu “{labels.get(mode, mode)}”")
    if not p.pillars.surface and (named := surface_in_text(p.raw_prompt or "")):
        p.pillars.surface = named  # "glassmorphism / backdrop-blur" in the brief
        filled.append(f"Chất liệu “{SURFACES[Surface(named)].label_vi}”")
    if (scope := brief.scope()) and not p.pillars.scope:
        p.pillars.scope = scope
        filled.append(f"Khách hàng & nút chính “{brief.primary_cta}”")
    return filled


def feedback_changes(agent, fb: str, pillars: Pillars) -> dict[str, str]:
    """Pillar changes from B7/B12 feedback, plus a material named explicitly ('đổi sang kính mờ')."""
    changes = agent.interpret_feedback(fb, pillars)
    if (surface := surface_in_text(fb)) and surface != (pillars.surface or "flat"):
        changes["surface"] = surface
    return changes


def _copy(state: GraphState) -> PipelineState:
    return state.pipeline.model_copy(deep=True)


_STATE_TYPES = ("PipelineState", "Step", "Domain", "Framework", "PageStatus", "Pillars", "SitemapPage",
                "Reference", "Asset", "HealAttempt", "BuildMode", "CloneSource")
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
        if not p.mode:
            answer = interrupt(Question(
                step="B1", kind="mode", key="mode", allow_free_text=False,
                text="Bạn muốn Chroma làm theo cách nào?",
                options=[Option(value=BuildMode.CREATIVE.value, label="Creative: dựng từ ý tưởng của bạn",
                                hint="Trò chuyện với Chroma; Chroma hỏi 5 trụ cột rồi thiết kế riêng cho bạn"),
                         Option(value=BuildMode.CLONE.value, label="Clone: dựng lại từ một trang web",
                                hint="Gửi link và mô tả; dựng lại cấu trúc trang, cả chữ và ảnh nếu là trang của bạn")],
            ).model_dump())
            try:
                p.mode = BuildMode(answer)
            except ValueError:
                return {"pipeline": p, "notice": "Vui lòng chọn Creative hoặc Clone."}
            return {"pipeline": p, "notice": None}
        if p.mode is BuildMode.CLONE and not p.clone:
            answer = interrupt(Question(
                step="B1", kind="clone_source", key="clone_source",
                text="Gửi link trang bạn muốn dựng lại.",
            ).model_dump())
            data = answer if isinstance(answer, dict) else {}
            prompt = str(data.get("prompt") or "").strip()
            try:
                url = Reference.model_validate({"url": str(data.get("url") or "")}).url
            except ValueError:
                url = None
            if not url:
                return {"pipeline": p, "notice": "Clone cần một link hợp lệ (ví dụ https://tenmien.vn)."}
            owned = bool(data.get("owned"))
            p.clone = CloneSource(url=url, owned=owned, described=bool(prompt),
                                  exact_requested=not owned and wants_exact_copy(prompt))
            # The link is enough: without a description the kind of site is read from the reference at B2.
            p.raw_prompt = prompt or f"Dựng lại trang {urlparse(url).hostname or url}"
            if not prompt:
                p.domain = Domain.OTHER
            return {"pipeline": p, "notice": None}
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
    async def b2(state: GraphState) -> dict:
        p = _copy(state)
        if p.mode is BuildMode.CLONE:
            return await b2_clone(p)
        return b2_creative(p)

    async def b2_clone(p: PipelineState) -> dict:
        """Read the reference page: structure, style and (owned) content."""
        reader = deps.clone_reader or analyse_reference
        try:
            a = await reader(p.clone.url, p.clone.owned)
        except Exception as e:
            log.warning("clone analysis failed for %s: %s", p.clone.url, e)
            p.reset_clone_source()
            return {"pipeline": p, "notice": f"Không mở được trang {p.clone.url if p.clone else ''}: {str(e)[:120]}. Bạn kiểm tra link rồi gửi lại nhé."}
        p.clone = p.clone.model_copy(update={
            "analysed": True, "title": a.title, "sections": [sec.model_dump() for sec in a.sections],
            "pillars": a.pillars, "heading_font": a.heading_font, "body_font": a.body_font,
            "content": a.content, "notes": a.notes,
            "content_width": a.content_width, "fonts": a.fonts})
        if not p.clone.described:
            p.domain = guess_domain(a)  # sample copy and suggested pages follow the kind of site read
        pages, _ = agent.sitemap_for(p.domain)
        clone_page = SitemapPage(slug=CLONE_PAGE, title=f"Bản dựng lại · {a.title}"[:80],
                                 purpose=f"Dựng lại từ {p.clone.url}", status=PageStatus.BUILDING)
        p.sitemap = [clone_page] + pages
        p.selected_page = CLONE_PAGE
        p.advance()
        kind = "cấu trúc, chữ và ảnh (trang của bạn)" if p.clone.owned else "cấu trúc và phong cách (chữ, ảnh là của bạn)"
        names = ", ".join(sec.name for sec in a.sections)
        notice = f"Đã đọc {len(a.sections)} section từ trang mẫu: {names}. Sẽ dựng lại {kind}."
        if p.clone.exact_requested and not p.clone.owned:
            # "Giống 100%": said once, never asked — most people clone someone else's page.
            notice += (" Bố cục, phong cách và nhịp trang được dựng giống trang mẫu; chữ, ảnh và tên thương hiệu "
                       "của trang mẫu thuộc về chủ trang nên không được chép — bạn dán nội dung của mình vào template.")
        if limits := clone_limits(a):
            notice += " Sẽ không giống trang mẫu ở: " + "; ".join(limits) + "."
        return {"pipeline": p, "notice": notice}

    def b2_creative(p: PipelineState) -> dict:
        if not p.brief_read and deps.brief_reader:
            # Read the prompt once for every answer it already gives; returned before any interrupt so the
            # (LLM) reading is persisted and never repeated.
            p.brief_read = True
            brief = deps.brief_reader(p.raw_prompt or "")
            p.brief = brief.model_dump() if brief else None
            return {"pipeline": p, "notice": None}
        pages, first = agent.sitemap_for(p.domain)
        p.sitemap = pages
        asked = (p.brief or {}).get("page")
        if asked in {pg.slug for pg in pages}:  # "làm landing page": no need to ask which page
            p.selected_page = asked
            next(pg for pg in p.sitemap if pg.slug == asked).status = PageStatus.BUILDING
            p.advance()
            title = next(pg.title for pg in pages if pg.slug == asked)
            return {"pipeline": p, "notice": f"Bắt đầu với {title} như bạn yêu cầu."}
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
        if p.mode is BuildMode.CLONE and p.clone and p.clone.analysed and p.clone.owned and p.clone.owner_confirmed is None:
            # Owned clones copy someone's name, words and photos: confirm against the page's own name.
            answer = interrupt(Question(
                step="B3", kind="choice", key="clone_owner_confirm", allow_free_text=False,
                text=(f"Trang mẫu tên là “{p.clone.title}”. Chroma sẽ chép tên, chữ và ảnh của trang này. "
                      "Chỉ xác nhận nếu bạn là chủ trang hoặc được chủ trang cho phép."),
                options=[Option(value="confirm", label="Tôi là chủ trang / được phép",
                                hint="Chép cả chữ, ảnh và thương hiệu"),
                         Option(value="structure", label="Chỉ dựng cấu trúc",
                                hint="Bỏ chữ và ảnh đã đọc; dùng nội dung của bạn")],
            ).model_dump())
            if answer not in ("confirm", "structure"):
                return {"pipeline": p, "notice": "Vui lòng chọn một trong hai cách."}
            if answer == "confirm":
                p.clone = p.clone.model_copy(update={"owner_confirmed": True})
                return {"pipeline": p, "notice": None}
            p.clone = p.clone.model_copy(update={"owner_confirmed": False, "owned": False, "content": None})
            return {"pipeline": p, "notice": "Đã bỏ chữ và ảnh của trang mẫu; chỉ dựng lại cấu trúc và phong cách."}
        if p.mode is BuildMode.CLONE and p.clone and p.clone.analysed:
            # Measured on the reference page, not guessed; the user reviews them at B7.
            for key, value in p.clone.pillars.items():
                if not getattr(p.pillars, key):
                    setattr(p.pillars, key, value)
            if not p.pillars.scope and p.raw_prompt and len(p.raw_prompt) >= 12:
                p.pillars.scope = p.raw_prompt
            if p.can_advance():
                p.advance()
                return {"pipeline": p, "notice": "Đã lấy 4 trụ cột từ trang mẫu và đối tượng từ mô tả của bạn."}
        if p.mode is not BuildMode.CLONE and p.brief and not p.brief_applied:
            p.brief_applied = True
            brief = Brief.model_validate(p.brief)
            taken = prefill_from_brief(p, brief) + brief.summary()
            if not p.pillars.scope and (brief.audience or brief.primary_cta):
                # half of the scope answer is in the prompt: keep it, ask only the other half
                p.scope_draft = brief.audience or f"Hành động quan trọng nhất: {brief.primary_cta}"
            missing = [scope_gap(p.scope_draft) if m == "scope" else MISSING_LABELS[m] for m in p.pillars.missing()]
            if p.can_advance():
                p.advance()
            if not taken:
                return {"pipeline": p, "notice": state.notice}
            text = "Mình đã lấy từ mô tả của bạn: " + "; ".join(taken) + "."
            text += (f" Chỉ còn thiếu: {', '.join(missing)} — mình hỏi tiếp." if missing
                     else " Đã đủ thông tin, không cần hỏi thêm. Bạn vẫn đổi được mọi thứ ở bước duyệt kế hoạch.")
            return {"pipeline": p, "notice": text}
        if p.pillars.theme and not p.pillars.surface and not (p.brief or {}).get("theme"):
            # Material, right after the theme; skipped when the first message already named one.
            if named := surface_in_text(p.raw_prompt or ""):
                p.pillars.surface = named  # returned (not followed by an interrupt) so the value is persisted
                return {"pipeline": p, "notice": state.notice}
            else:
                sq = surface_question()
                sq.note = state.notice
                answer = interrupt(sq.model_dump())
                value = None if isinstance(answer, dict) else interpret_surface(str(answer))
                if value is None:
                    return {"pipeline": p, "notice": "Mình chưa hiểu rõ — bạn chọn một chất liệu trong danh sách nhé."}
                p.pillars.surface = value
                return {"pipeline": p, "notice": None}
        pillar = p.pillars.next_question()
        q = agent.pillar_question(pillar)
        if pillar == "scope" and p.scope_draft:  # half of it is known: ask only the other half
            q.text = (f"Mình đã có: “{p.scope_draft}”. Bạn cho mình biết thêm {scope_gap(p.scope_draft)} nhé?")
        q.note = state.notice
        answer = interrupt(q.model_dump())
        if isinstance(answer, dict) and answer.get("revise") in Pillars.ORDERED_FIELDS:
            # Creative chat: change a pillar answered earlier; the pending question stays.
            target = answer["revise"]
            value = agent.interpret(target, str(answer.get("text") or ""))
            if value is None:
                return {"pipeline": p, "notice": "Mình chưa hiểu rõ điều bạn muốn đổi, bạn nói cụ thể hơn nhé."}
            setattr(p.pillars, target, value)
            if p.can_advance():
                p.advance()
            return {"pipeline": p, "notice": f"Đã đổi {PILLAR_LABELS.get(target, 'đối tượng & CTA')}."}
        if pillar == "scope":
            # Audience and main action often come in separate messages: judge them together.
            new = str(answer).strip()
            combined = p.scope_draft if p.scope_draft and new in p.scope_draft.split("; ") else \
                "; ".join(x for x in (p.scope_draft, new) if x)  # a repeated message is not added twice
            value = agent.interpret("scope", combined)
            if value is None:
                p.scope_draft = combined
                return {"pipeline": p, "notice": f"Mình đã ghi lại: “{combined}”. Chỉ còn thiếu {scope_gap(combined)}."}
            p.scope_draft = None
        else:
            value = agent.interpret(pillar, str(answer))
            if pillar == "color" and value and len(value.split()) == 1 and (p.brief or {}).get("accent"):
                value = f"{value} {p.brief['accent']}"  # tone from this answer + the colour named in the prompt
        if value is None:
            return {"pipeline": p, "notice": "Mình chưa hiểu rõ câu trả lời — bạn chọn một phương án hoặc mô tả cụ thể hơn nhé."}
        setattr(p.pillars, pillar, value)
        if p.can_advance():
            p.advance()
        return {"pipeline": p, "notice": None}

    # ---------------------------------------------------------------- B4
    def b4(state: GraphState) -> dict:
        p = _copy(state)
        if p.mode is BuildMode.CLONE and p.clone:
            # The reference itself is the resource; B5 reads its Style DNA from the URL.
            if not any(r.url == p.clone.url for r in p.references):
                p.references.append(Reference.model_validate({"url": p.clone.url}))
            p.assets_confirmed = True
            p.advance()
            return {"pipeline": p, "notice": None}
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

        if (p.brief or {}).get("assets_said") and not p.assets_confirmed:
            p.assets_confirmed = True  # "dùng ảnh Unsplash": no need to ask for assets
            p.advance()
            return {"pipeline": p, "notice": (state.notice + " " if state.notice else "") +
                    "Bạn đã nói về nguồn ảnh nên mình bỏ qua bước gửi tài nguyên."}
        answer = interrupt(Question(
            step="B4", kind="assets", key="assets", note=state.notice,
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
        inputs = design_inputs(p, project, dna)
        spec = build_design_spec(inputs)
        # Optional LLM prose; the engine default stays unless every number it cites is grounded.
        facts = philosophy_facts(spec)
        phil = await asyncio.to_thread(agent.write_philosophy, facts)
        if phil is not None and philosophy_is_grounded(phil, facts):
            spec = build_design_spec(inputs.model_copy(update={"philosophy": phil}))
        elif phil is not None:
            log.warning("LLM philosophy cited numbers outside the engine facts; using the default")
        p.design_md = render_design_md(spec)
        p.tokens_css = render_tokens_css(spec)
        write_artifact(p, "DESIGN.md", p.design_md)
        write_artifact(p, "tokens.css", p.tokens_css)
        p.advance()
        return {"pipeline": p}  # keep a B7 notice ("đã đổi ...") visible through B5/B6

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
        return {"pipeline": p}

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
            return {"pipeline": p, "notice": None}
        fb = (data.get("feedback") or "").strip()
        if not fb:
            return {"pipeline": p, "notice": "Bạn ghi rõ điều muốn đổi giúp mình nhé (ví dụ: đổi sang tông tối)."}
        changes = feedback_changes(agent, fb, p.pillars)
        for pillar, value in changes.items():
            setattr(p.pillars, pillar, value)
        p.plan_feedback.append(fb)
        p.request_plan_changes()
        return {"pipeline": p, "notice": feedback_notice(changes)}

    # ---------------------------------------------------------------- B8-B10
    def build_context(p: PipelineState) -> tuple[str, Any, list[Section]]:
        project = project_title(p.raw_prompt or "")
        spec = build_design_spec(design_inputs(p, project))
        return project, spec, page_sections(p)

    async def b8(state: GraphState) -> dict:
        """Design installs the design system into the workspace (tokens only, no code)."""
        p = _copy(state)
        _, _, sections = build_context(p)
        try:
            other_pages = any(slug != p.selected_page for slug in p.page_routes)
            await deps.build.install_design_system(p.session_id, p.tokens_css or "",
                                                   keep_existing=bool(p.heal_history) or other_pages)
        except Exception as e:
            log.exception("B8 failed")
            p.build_error = f"B8: {e}"
            return {"pipeline": p, "notice": f"Lỗi khi cài hệ thiết kế: {e}"}
        p.design_system_installed = True
        p.sections_planned = [s.id for s in sections]
        if p.selected_page and p.selected_page not in p.page_routes:  # first page is "/", later ones "/<slug>"
            p.page_routes[p.selected_page] = "/" if not p.page_routes else f"/{p.selected_page}"
        p.advance()
        return {"pipeline": p, "notice": f"B8 · Phòng Design đã cài tokens.css. Bắt đầu dựng {len(sections)} section."}

    async def b9(state: GraphState) -> dict:
        """One pipelined tick: Developer writes section N while Design measures N-1."""
        p = _copy(state)
        project, spec, sections = build_context(p)
        by_id = {s.id: s for s in sections}
        try:
            slug = p.selected_page or ""
            route = p.page_routes.get(slug, "/")
            if deps.copywriter and not (p.mode is BuildMode.CLONE and p.clone and p.clone.owned):
                key = copy_key(p)
                if p.page_copy_key != key:  # once per page (and again after a B7/B12 change)
                    base = build_copy(p.model_copy(update={"page_copy": None}))
                    p.page_copy = await asyncio.to_thread(deps.copywriter, p, base)
                    p.page_copy_key = key
            if not p.preview_url:
                photos = build_copy(p).images
                p.preview_url = await (deps.build.start_app(p.session_id, project, spec, route, photos) if photos
                                       else deps.build.start_app(p.session_id, project, spec, route))
            if not p.sections_done and (p.heal_rules or p.heal_contrast):  # first tick of a heal loop
                healed = await deps.build.heal(p.session_id, p.heal_rules, p.heal_contrast)
                p.token_changes += [f"{c.token}: {c.old} → {c.new} (B11: {c.reason})" for c in healed]
                p.heal_contrast = []
            to_write = next((s for s in sections if s.id not in p.sections_done), None)
            to_check = next((x for x in p.sections_done if x not in p.sections_checked), None)
            jobs = []
            if to_write:
                written = [by_id[x] for x in p.sections_done] + [to_write]
                copy = build_copy(p)
                jobs.append(deps.build.write_section(p.session_id, written, copy, slug, route))
                others = [x for x in p.page_routes if x != slug]
                if to_write.id == "site-header" and others and hasattr(deps.build, "refresh_shared"):
                    jobs.append(deps.build.refresh_shared(p.session_id, to_write, copy, others))
            if to_check:
                jobs.append(deps.build.check_section(p.session_id, to_check, spec))
            results = await asyncio.gather(*jobs)
            motion, motion_error = [], None
            if to_check and by_id[to_check].effect and "mcp_motion" in tools_for(p.step):  # B8.1, optional
                try:
                    motion = await deps.build.motion(p.session_id, by_id[to_check], spec, slug)
                except Exception as e:  # an optional effect must never stop the build
                    log.warning("B8.1 motion failed for %s: %s", to_check, e)
                    motion_error = str(e)
        except Exception as e:
            log.exception("B9 failed")
            p.build_error = f"B9: {e}"
            return {"pipeline": p, "notice": f"Lỗi khi dựng trang: {e}"}
        parts = []
        if to_write:
            p.sections_done.append(to_write.id)
            parts.append(f"Dev viết “{to_write.name}”")
        if to_check:
            check = next(r for r in results if isinstance(r, SectionCheck))
            p.sections_checked.append(to_check)
            p.token_changes += [f"{c.token}: {c.old} → {c.new} ({c.reason})" for c in check.changes]
            p.open_findings += [f"{f.section}: {f.detail}" for f in check.open]
            fixed = f", sửa {len(check.changes)} token" if check.changes else ""
            parts.append(f"Design đo “{by_id[to_check].name}”{fixed}")
            for fx in motion:
                p.motion_effects.append(f"{fx.section_id}: {fx.effect} ({fx.kind}, qua MCP)")
                parts.append(f"Motion thêm {fx.effect} qua MCP")
            if motion_error:
                p.motion_effects.append(f"{to_check}: bỏ qua hiệu ứng ({motion_error[:80]})")
        if p.can_advance():
            p.advance()
        done = f"{len(p.sections_checked)}/{len(p.sections_planned)}"
        return {"pipeline": p, "notice": f"B9 · {' · '.join(parts)} ({done})"}

    async def b10(state: GraphState) -> dict:
        p = _copy(state)
        try:
            report = await deps.build.integrate(p.session_id, p.sections_planned)
        except Exception as e:
            log.exception("B10 failed")
            p.build_error = f"B10: {e}"
            return {"pipeline": p, "notice": f"Lỗi khi ghép trang: {e}"}
        if not report.ok:
            problems = report.missing + report.console_errors[:3]
            p.build_error = "B10: " + "; ".join(problems)
            return {"pipeline": p, "notice": f"Ghép trang chưa đạt: {'; '.join(problems)}"}
        p.open_findings = [f"{f.section}: {f.detail}" for f in report.open]
        p.integrated = True
        p.advance()
        left = f" Còn {len(report.open)} điểm chuyển cho B11." if report.open else " Không còn lỗi thiết kế."
        return {"pipeline": p, "notice": f"B10 · Đã ghép {len(p.sections_planned)} section trên {p.preview_url}.{left}"}

    # ---------------------------------------------------------------- B11
    async def b11(state: GraphState) -> dict:
        """Master QA. PASS -> B12. FAIL -> patches for Dev/Design and back to B8 (max 3 loops),
        or straight to the user when nothing left is patchable."""
        p = _copy(state)
        _, spec, _ = build_context(p)
        try:
            report = await deps.build.master_qa(p.session_id, spec)
        except Exception as e:
            log.exception("B11 failed")
            p.build_error = f"B11: {e}"
            return {"pipeline": p, "notice": f"Lỗi khi chạy Master QA: {e}"}
        p.qa_summary = report.summary()
        p.qa_failures = [f"[Bài {f.test}] {f.detail}" + (f" ({f.viewport}px)" if f.viewport else "") for f in report.failures]
        if report.passed:
            p.qa_passed = True
            notice = "B11 · Master Cursor: 100% PASSED — cả 4 bài kiểm tra đều đạt."
            # Design critic (vision model): QA proves the page is not wrong, this grades how good it looks.
            if critic := getattr(deps.build, "critique", None):
                context = f"{p.raw_prompt or ''} · trang {p.selected_page or ''} · phong cách {p.pillars.theme}"
                if c := await critic(p.session_id, context):
                    p.design_score = c.overall
                    p.design_critique = [f"{i.where}: {i.problem} → {i.fix}" for i in c.issues]
                    write_artifact(p, "CRITIQUE.md", render_markdown(c))
                    notice += f" Chấm thẩm mỹ: {c.overall:.1f}/10."
            # Clone mode: how close the rebuild is to the reference (same reader on both pages).
            measure = getattr(deps.build, "fidelity", None)
            if p.mode == BuildMode.CLONE and p.clone and measure:
                if f := await measure(p.session_id, p.clone.url):
                    p.clone_fidelity = f.total
                    p.clone_fidelity_notes = f.notes
                    write_artifact(p, "FIDELITY.md", render_fidelity(f, p.clone.url))
                    notice += f" Độ giống trang mẫu: {f.total:.0f}/100."
            p.advance()
            return {"pipeline": p, "notice": notice}
        new_rules = [r for r in heal_css(report.failures) if r not in p.heal_rules]
        contrast = [f.reading.model_dump() for f in report.failures if f.reading]
        if not new_rules and not contrast:
            p.escalate_qa(p.qa_failures)
            p.advance()
            return {"pipeline": p, "notice": f"B11 · Còn {len(report.failures)} lỗi hệ thống không tự sửa được, "
                                              "chuyển cho bạn xem xét ở bước bàn giao."}
        iteration = len(p.heal_history) + 1
        p.record_qa_failure(p.qa_failures)
        if p.escalated_to_user:  # MAX_HEAL_ITERATIONS reached
            p.advance()
            return {"pipeline": p, "notice": f"B11 · Đã tự sửa {iteration} vòng, còn {len(report.failures)} lỗi. "
                                              "Chuyển cho bạn quyết định."}
        p.heal_rules += new_rules
        p.heal_contrast = contrast
        return {"pipeline": p, "notice": f"B11 · {len(report.failures)} lỗi, vòng tự sửa {iteration}: "
                                          f"Dev vá {len(new_rules)} điểm CSS, Design sửa {len(contrast)} cặp màu. Dựng lại…"}

    # ---------------------------------------------------------------- B12
    async def b12(state: GraphState) -> dict:
        """Handover: overlay removed, the window belongs to the user. Next: refine this page
        (back to B5, re-approval at B7) or build another sitemap page (B6, DESIGN.md kept)."""
        p = _copy(state)
        pending = [pg for pg in p.sitemap if pg.slug not in p.page_routes]
        verdict = ("Master QA đạt 100% cả 4 bài." if p.qa_passed
                   else f"Master QA còn {len(p.qa_failures)} lỗi hệ thống chưa tự sửa được, bạn xem danh sách bên dưới.")
        options = [{"label": f"Dựng trang tiếp theo: {pending[0].title}", "value": {"action": "next", "page": pending[0].slug},
                    "primary": True}] if pending else []
        options.append({"label": "Tinh chỉnh trang này (ghi góp ý trong Studio)", "value": {"action": "refine"}})
        await deps.build.handover(p.session_id, options)
        answer = interrupt(Question(
            step="B12", kind="handover", key="handover", allow_free_text=True,
            recommended=pending[0].slug if pending else None,
            text=(f"Trang đã sẵn sàng tại {p.preview_url}. {verdict}\n"
                  "Cửa sổ trình duyệt giờ là của bạn: bấm thử mọi thứ. Sau đó chọn bước tiếp theo."),
            options=[Option(value=pg.slug, label=pg.title, hint=pg.purpose) for pg in pending],
        ).model_dump())
        data = answer if isinstance(answer, dict) else {"action": "refine", "feedback": str(answer)}
        action = data.get("action")
        if action == "next":
            if data.get("page") not in {pg.slug for pg in pending}:
                return {"pipeline": p, "notice": "Vui lòng chọn một trang chưa dựng trong danh sách."}
            title = next(pg.title for pg in pending if pg.slug == data["page"])
            p.build_next_page(data["page"])
            return {"pipeline": p, "notice": f"Bắt đầu trang “{title}”: giữ nguyên DESIGN.md, lập PLAN.md mới để bạn duyệt."}
        if action == "finish":
            p.handover_closed = True
            return {"pipeline": p, "notice": "Đã kết thúc. Mã nguồn nằm trong workspaces/<phiên>/app, chạy bằng `npm run dev`."}
        fb = (data.get("feedback") or "").strip()
        if not fb:
            return {"pipeline": p, "notice": "Bạn ghi rõ điều muốn tinh chỉnh trong Studio giúp mình nhé (ví dụ: đổi sang tông tối)."}
        changes = feedback_changes(agent, fb, p.pillars)
        for pillar, value in changes.items():
            setattr(p.pillars, pillar, value)
        p.plan_feedback.append(fb)
        p.refine_current_page()
        return {"pipeline": p, "notice": feedback_notice(changes)}

    def build_pending(state: GraphState) -> dict:
        p = state.pipeline
        if p.build_error:
            return {"notice": f"Dừng dựng trang: {p.build_error}"}
        if p.step is Step.B8_DESIGN:  # no build runtime configured
            return {"notice": "Kế hoạch đã duyệt. Bộ dựng trang (B8–B10) chưa được bật trên máy chủ này."}
        return {"notice": state.notice or "Đã kết thúc phiên."}

    nodes = {"b1": b1, "b2": b2, "b3": b3, "b4": b4, "b5": b5, "b6": b6, "b7": b7,
             "b8": b8, "b9": b9, "b10": b10, "b11": b11, "b12": b12, "build_pending": build_pending}
    step_node = {Step.B1_READ_PROMPT: "b1", Step.B2_SITEMAP: "b2", Step.B3_ELICITATION: "b3",
                 Step.B4_ASSETS: "b4", Step.B5_DESIGN_MD: "b5", Step.B6_PLAN: "b6", Step.B7_APPROVAL: "b7",
                 Step.B8_DESIGN: "b8", Step.B9_DEVELOP: "b9", Step.B10_INTEGRATE: "b10", Step.B11_MASTER_QA: "b11",
                 Step.B12_HANDOVER: "b12"}
    build_steps = {Step.B8_DESIGN, Step.B9_DEVELOP, Step.B10_INTEGRATE, Step.B11_MASTER_QA, Step.B12_HANDOVER}

    def route(state: GraphState) -> str:
        p = state.pipeline
        if p.step in build_steps and (deps.build is None or p.build_error):
            return "build_pending"
        if p.step is Step.B12_HANDOVER and p.handover_closed:
            return "build_pending"
        return step_node.get(p.step, "build_pending")

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

    async def answer(self, session_id: str, value: Any, on_progress: Any = None) -> dict:
        """Resume with the user's answer. `on_progress(snapshot)` is awaited after every node,
        so long B8-B10 runs stream section-by-section progress to the Studio."""
        # LangGraph cannot resume with None; nodes treat "" as "skipped".
        async for _ in self.graph.astream(Command(resume="" if value is None else value),
                                          self._config(session_id), stream_mode="updates"):
            if on_progress:
                snap = await self.snapshot(session_id)
                if snap["question"] is None and not snap["finished"]:
                    await on_progress(snap)
        return await self.snapshot(session_id)
