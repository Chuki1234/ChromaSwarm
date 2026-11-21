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
import contextlib
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
from chromaswarm.agents.planner import (CLONE_PAGE, Section, design_inputs, design_intent, page_sections, render_plan_md,
                                        render_product_md)
from urllib.parse import urlparse

from chromaswarm.clone.reader import analyse as analyse_reference
from chromaswarm.clone.content_slots import clean_texts, image_slots, needs_content, save_images
from chromaswarm.clone.content_slots import warning as content_warning
from chromaswarm.clone.reader import clone_limits, guess_domain, motion_summary, wants_exact_copy
from chromaswarm.developer.i18n import normalise
from chromaswarm.build.runtime import SectionCheck
from chromaswarm.agents.brief import Brief, mode_from_background
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.copywriter import copy_key
from chromaswarm.developer.industry import pack_for as industry_pack
from chromaswarm.developer.real_content import fields as real_fields, parse as parse_real
from chromaswarm.developer.photo_bot import photo_key
from chromaswarm.developer.uploads import own_files, shared_photos
from chromaswarm.developer.motion_js import js_effects
from chromaswarm.developer.stylist import validate_css
from chromaswarm.developer.variants import variants_for
from chromaswarm.design.reference_vision import to_dna as shot_dna
from chromaswarm.developer.uploads import resolve as resolve_upload
from chromaswarm.clone.fidelity import render_markdown as render_fidelity
from chromaswarm.clone.components import render_compare
from chromaswarm.clone.motion_check import inspect_motion
from chromaswarm.clone.analysis import build as top_down
from chromaswarm.clone.brief_doc import build_brief
from chromaswarm.clone.sketch import check_reading
from chromaswarm.clone.spec import CloneSpec, apply_overrides, build_spec
from chromaswarm.clone.motion_check import summary as motion_check_summary
from chromaswarm.qa.critic import render_markdown
from chromaswarm.qa.master import heal_css
from chromaswarm.engines.design_spec import (
    build_design_spec,
    philosophy_facts,
    philosophy_is_grounded,
    render_design_md,
    render_tokens_css,
)
from chromaswarm.engines.presets import SURFACES, Surface, Theme
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
    # async (url, boxes) -> MotionReport; None = real Playwright check, skipped when a fake reader is injected
    motion_check: Any = None
    sketch_check: Any = None  # async (url, boxes, components, out_dir) -> dict; None = real check with the real reader
    build: Any = None  # BuildRuntime for B8-B10; None stops after approval (B1-B7 only)
    brief_reader: Any = None  # (prompt) -> agents.brief.Brief | None; None = never read a brief
    copywriter: Any = None  # (state, base PageCopy) -> validated copy dict | None; None = rule-based copy
    photo_bot: Any = None  # (state) -> checked photos list[dict] | None; None = curated topic photos
    screenshot_reader: Any = None  # (path) -> validated design reading of a reference screenshot | None
    stylist: Any = None  # developer/stylist.Stylist: composition (B10) and critic-driven refine (B11); None = templates only
    section_eye: Any = None  # qa/section_eye.SectionEye: each section shot and judged right after it is built
    compose: bool = False  # B10 blind composition layer (off: it broke QA in every live run; the eyes fix by sight)


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


REFINE_TARGET = 8.0  # design score the critic-driven refine aims for
MAX_REFINES = 2
MIN_GAIN = 0.2  # a refine round is kept only when the score rises at least this much


EYE_MAX_FIXES = 3  # tries per section: the template's variants first, then a fix by sight


def section_outline(outline: str, section_id: str) -> str:
    """The part of the page outline for one section."""
    for block in outline.split("## ")[1:]:
        if block.startswith(f"{section_id} "):
            return "## " + block
    return outline[:1500]


def kept_css(p: PipelineState, with_pending: bool = False) -> str:
    """The art director's layer for this page: kept rounds (and the one being tried)."""
    return "\n".join(r["css"] for r in p.style_rounds
                     if r.get("kept") is True or (with_pending and r.get("kept") is None))


def read_notice(p: PipelineState, reading: dict) -> str:
    """What was learned from the reference screenshot; its accent becomes the brand colour when the
    user named none (they can change it at B7)."""
    parts = ["nền tối" if reading["is_dark"] else "nền sáng"]
    if reading.get("density"):
        parts.append({"airy": "bố cục thoáng", "balanced": "độ thoáng vừa", "dense": "bố cục gọn"}[reading["density"]])
    if reading.get("radius_px") is not None:
        parts.append(f"bo góc ~{reading['radius_px']:.0f}px")
    accent = reading.get("accent")
    if accent and p.pillars.theme:
        mode, _, user_supplied = split_color(p.pillars.color or "light", Theme(p.pillars.theme))
        if not user_supplied:
            p.pillars.color = f"{mode} {accent}"
            parts.append(f"màu nhấn {accent} (dùng làm màu thương hiệu, đổi được ở bước duyệt)")
    return "Đã đọc ảnh trang tham khảo: " + ", ".join(parts) + ". Chỉ học đặc trưng thiết kế, không chép giao diện."


def handover_options(p: PipelineState) -> list[dict]:
    """B12 buttons shown in the handed-over browser window."""
    pending = [pg for pg in p.sitemap if pg.slug not in p.page_routes]
    options = [{"label": f"Dựng trang tiếp theo: {pending[0].title}", "value": {"action": "next", "page": pending[0].slug},
                "primary": True, "sent": f"Đang lập kế hoạch cho “{pending[0].title}” — duyệt trong Studio."}] if pending else []
    options.append({"label": "Tinh chỉnh trang này", "value": {"action": "refine"}, "feedback": True,
                    "placeholder": "Ví dụ: tông tối hơn, khoảng cách gọn hơn, đổi màu nhấn sang xanh lá",
                    "submit": "Gửi góp ý", "sent": "Đã nhận góp ý — duyệt lại kế hoạch trong Studio."})
    return options


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
        """Read the reference page: structure, style and (owned) content; then, as a pass of its own,
        operate it with Playwright to find and time its effects."""
        if p.clone and p.clone.analysed and not p.clone.motion_checked:
            return await b2_motion(p)
        if p.clone and p.clone.analysed and not p.clone.sketched:
            return await b2_sketch(p)
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
            "content_width": a.content_width, "fonts": a.fonts, "lang": a.lang, "media_share": a.media_share,
            "boxes": a.boxes, "components": a.components,
            "style": a.dna.model_dump(mode="json") if a.dna else None, "backgrounds": a.backgrounds, "media": a.media})
        if not p.clone.described:
            p.domain = guess_domain(a)  # sample copy and suggested pages follow the kind of site read
        pages, _ = agent.sitemap_for(p.domain)
        clone_page = SitemapPage(slug=CLONE_PAGE, title=f"Bản dựng lại · {a.title}"[:80],
                                 purpose=f"Dựng lại từ {p.clone.url}", status=PageStatus.BUILDING)
        p.sitemap = [clone_page] + pages
        p.selected_page = CLONE_PAGE
        check = deps.motion_check or (inspect_motion if deps.clone_reader is None else None)
        if check:
            p.clone.motion_checked = False  # next pass: the effect check (b2_motion), then B3
        else:
            p.clone.motion_checked = True
            analyse_top_down(p)
            p.advance()
        kind = "cấu trúc, chữ và ảnh (trang của bạn)" if p.clone.owned else "cấu trúc và phong cách (chữ, ảnh là của bạn)"
        names = ", ".join(sec.name for sec in a.sections)
        notice = f"Đã đọc {len(a.sections)} section từ trang mẫu: {names}. Sẽ dựng lại {kind}."
        if p.clone.exact_requested and not p.clone.owned:
            # "Giống 100%": said once, never asked — most people clone someone else's page.
            notice += (" Bố cục, phong cách và nhịp trang được dựng giống trang mẫu; chữ, ảnh và tên thương hiệu "
                       "của trang mẫu thuộc về chủ trang nên không được chép — bạn dán nội dung của mình vào template.")
        if a.lang:
            lang = normalise(a.lang)
            notice += (f" Ngôn ngữ trang mẫu: {a.lang} — bản dựng giữ nguyên ngôn ngữ này."
                       if lang == "en" and a.lang.lower().startswith("en") or lang == "vi" else
                       f" Ngôn ngữ trang mẫu: {a.lang} — chưa có bộ chữ mẫu cho ngôn ngữ này, bản dựng dùng tiếng Anh.")
        if effects := motion_summary(a):
            notice += f" Hiệu ứng đọc được và sẽ dựng lại: {effects}."
        if limits := clone_limits(a):
            notice += " Sẽ không giống trang mẫu ở: " + "; ".join(limits) + "."
        if check:
            notice += " Tiếp theo: kiểm tra hiệu ứng — Playwright cuộn và rê chuột trên trang mẫu."
        return {"pipeline": p, "notice": notice}

    async def b2_motion(p: PipelineState) -> dict:
        """B2 · effect check: does the reference move, where and how (timed), per section."""
        check = deps.motion_check or inspect_motion
        try:
            report = await check(p.clone.url, p.clone.boxes)
        except Exception as e:  # never blocks the clone: the page is rebuilt without effects
            log.warning("motion check failed for %s: %s", p.clone.url, e)
            p.clone.motion_checked = True
            p.clone.motion_report = {"has_motion": False, "items": [], "error": str(e)[:160]}
            p.advance()
            return {"pipeline": p, "notice": f"Kiểm tra hiệu ứng không chạy được ({str(e)[:100]}); dựng lại không kèm hiệu ứng."}
        sections = []
        for raw in p.clone.sections:
            sec = dict(raw)
            found = report.per_section.get(sec["id"], [])
            sec["motion"] = list(dict.fromkeys([*sec.get("motion", []), *found]))
            sec["motion_params"] = report.params.get(sec["id"], {})
            sections.append(sec)
        p.clone.sections = sections
        p.clone.motion_checked = True
        p.clone.motion_report = report.model_dump()
        if sketch_check():
            p.clone.sketched = False  # next pass: the sketch (draw what was read, check it, measure the gaps)
            return {"pipeline": p, "notice": motion_check_summary(report) + " Tiếp theo: vẽ sketch từ những gì đã đọc và đối chiếu với trang thật."}
        analyse_top_down(p)
        p.advance()
        return {"pipeline": p, "notice": motion_check_summary(report)}

    def sketch_check():
        if deps.sketch_check:
            return deps.sketch_check
        if deps.clone_reader is not None:
            return None

        async def real(url, boxes, comps, out):  # the vision model names what the reader could not measure
            from chromaswarm.qa.critic import vision_chat
            return await check_reading(url, boxes, comps, out, vision=vision_chat())
        return real

    async def b2_sketch(p: PipelineState) -> dict:
        """B2 · sketch: the page drawn from what was read, against a screenshot of it; gaps measured again."""
        check = sketch_check()
        notice = ""
        try:
            out = deps.artifacts_root / p.session_id / "artifacts" / "sketch"
            res = await check(p.clone.url, p.clone.boxes, p.clone.components, out)
            p.clone.components = res.pop("components")
            sections = []
            for raw in p.clone.sections:  # measured sections are rebuilt from the completed reading
                sec = dict(raw)
                if sec.get("layout") and sec["id"] in p.clone.components:
                    sec["layout"] = p.clone.components[sec["id"]]
                sections.append(sec)
            p.clone.sections = sections
            p.clone.sketch = res
            named = [d["seen"]["note"] or d["seen"]["kind"] for d in res.get("described", []) if d.get("seen")]
            notice = (f"Sketch: Chroma đọc được {res['coverage']:g}% trang"
                      + (f" (trước khi đo lại {res['coverage_before']:g}%; thêm {res['remeasured']} phần ở {res['gaps']} chỗ đọc thiếu)"
                         if res.get("gaps") else "")
                      + (f"; mô hình thị giác nhận ra: {'; '.join(named[:4])}" if named else "")
                      + ". Xem sketch cạnh ảnh chụp trang thật ở dưới.")
        except Exception as e:  # never blocks the clone
            log.warning("sketch failed for %s: %s", p.clone.url, e)
            p.clone.sketch = {"error": str(e)[:160]}
            notice = f"Sketch không chạy được ({str(e)[:100]}); dựng theo phần đã đọc."
        p.clone.sketched = True
        analyse_top_down(p)
        p.advance()
        return {"pipeline": p, "notice": notice}

    def analyse_top_down(p: PipelineState) -> None:
        """The preparation step's write-up: overview, then the page top-down (clone/analysis.py)."""
        try:
            p.clone.analysis = top_down(p.clone, p.domain.value if p.domain else "other", p.clone.sections)
            write_artifact(p, "ANALYSIS.md", p.clone.analysis)
        except Exception as e:  # a report never blocks the clone
            log.warning("analysis failed: %s", e)
        try:  # what the rebuild copies / replaces / skips (clone/spec.py) — the build steps read it
            spec = build_spec(p.clone)
            p.clone.spec = spec.model_dump()
            apply_spec(p, spec)
        except Exception as e:
            log.warning("clone spec failed: %s", e)
        write_brief(p)

    def apply_spec(p: PipelineState, spec: CloneSpec) -> None:
        """What the build reads per section: effects to build (an intro on load becomes `reveal`), where each
        control leads, the painted background layers."""
        sections = []
        for raw in p.clone.sections:
            sec = dict(raw)
            for effect, params in spec.effects(sec["id"]).items():
                if effect not in sec.get("motion", []):
                    sec["motion"] = [*sec.get("motion", []), effect]
                sec["motion_params"] = {**(sec.get("motion_params") or {}), effect: params}
            sec["links"] = spec.controls(sec["id"])
            sec["paint"] = spec.layers(sec["id"])
            sections.append(sec)
        p.clone.sections = sections

    def write_brief(p: PipelineState) -> None:
        try:  # the build team's preparation sheet: concept, sections, spacing, pictures, controls, effects, clone or not
            p.clone.brief = build_brief(p.clone, p.domain.value if p.domain else "other")
            write_artifact(p, "CLONE_BRIEF.md", p.clone.brief)
        except Exception as e:
            log.warning("clone brief failed: %s", e)

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
                return {"pipeline": p, "notice": ("Đã lấy 4 trụ cột từ trang mẫu và đối tượng từ mô tả của bạn." if p.clone.described
                                                 else "Đã lấy phong cách, bố cục, màu và độ thoáng từ trang mẫu.")}
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
            sections = [Section.model_validate(s) for s in p.clone.sections]
            if (not p.clone.owned and not p.clone.content_asked
                    and needs_content(sections, p.clone.media_share, p.domain is Domain.PORTFOLIO)):
                # A picture/text-led page: say how much of its look is its own photos and words, and ask
                # for similar ones by slot. The answer may be empty: the template keeps samples.
                answer = interrupt(Question(
                    step="B4", kind="clone_content", key="clone_content",
                    text=content_warning(sections, p.clone.media_share),
                    options=[Option(value=sl.id, label=sl.label, hint=f"{sl.count} ảnh · {sl.hint}")
                             for sl in image_slots(sections)],
                ).model_dump())
                data = answer if isinstance(answer, dict) else {}
                names = save_images(list(data.get("images") or []), deps.artifacts_root / p.session_id / "uploads")
                texts = clean_texts(data.get("texts") or {})
                p.clone = p.clone.model_copy(update={"content_asked": True, "user_images": names, "user_texts": texts})
                total = sum(sl.count for sl in image_slots(sections))
                notice = (f"Đã nhận {len(names)}/{total} ảnh và {len(texts)} mục nội dung của bạn."
                          if names or texts else "Bỏ qua — bản dựng dùng ảnh và chữ mẫu, bạn thay sau trong content/.")
                p.assets_confirmed = True
                p.advance()
                return {"pipeline": p, "notice": notice}
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
            text=("Bạn gửi giúp mình nội dung thật và tài nguyên đang có: logo, ảnh sản phẩm thật, và những gì "
                  "khách cần biết (bán gì, giá, điểm khác biệt, số liệu, lời khách). Mục nào điền, trang dùng đúng "
                  "lời của bạn; mục nào bỏ trống, mình dùng chữ mẫu và ghi rõ trong PRODUCT.md để bạn thay sau. "
                  "Chưa có gì cũng không sao — bấm “Đã gửi đủ”."),
            # Real-content form for this kind of site (developer/real_content.py): value = field key
            options=[Option(value=f.key, label=f.label, hint=f.placeholder) for f in real_fields(p.domain, industry_pack(p))],
        ).model_dump())
        data = answer if isinstance(answer, dict) else {}
        real = parse_real(data.get("content"))
        notice = None
        if real.given():
            p.real_content = real.model_dump()
            notice = f"Đã nhận {', '.join(real.given())} của bạn" + \
                (f"; còn dùng chữ mẫu cho {', '.join(real.missing())}." if real.missing() else ".")
        for a in data.get("assets", []):
            p.assets.append(Asset.model_validate(a))
        have = {a.path_or_text for a in p.assets}
        for it in real.items:  # a photo attached to one line of the list is copied into the app like any upload
            if it.image and it.image not in have:
                p.assets.append(Asset(kind="product-image", path_or_text=it.image, note=it.name))
                have.add(it.image)
        for r in data.get("references", []):
            try:
                p.references.append(Reference.model_validate(r))
            except ValueError:
                continue
        if data.get("done"):
            p.assets_confirmed = True
        if p.can_advance():
            p.advance()
        return {"pipeline": p, "notice": notice}

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
        notice = state.notice
        shot = next((r.screenshot_path for r in p.references if r.screenshot_path), None)
        if dna is None and shot and deps.screenshot_reader and p.mode is not BuildMode.CLONE:
            path = resolve_upload(deps.artifacts_root, p.session_id, shot)
            if path and p.reference_reading_key != shot:  # read once per screenshot (B7 changes come back here)
                p.reference_reading = await asyncio.to_thread(deps.screenshot_reader, path)
                p.reference_reading_key = shot
                if p.reference_reading:
                    notice = read_notice(p, p.reference_reading)
            if path and p.reference_reading:
                dna = shot_dna(p.reference_reading)
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
        if notice != state.notice:
            return {"pipeline": p, "notice": notice}
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
        changed: list[str] = []
        if isinstance(data.get("spec"), dict) and p.mode is BuildMode.CLONE and p.clone and p.clone.spec:
            # The user's decisions on the CloneSpec (e.g. skip a section): the plan and the brief follow.
            spec = CloneSpec.model_validate(p.clone.spec)
            changed = apply_overrides(spec, data["spec"])
            if changed:
                p.clone.spec = spec.model_dump()
                apply_spec(p, spec)
                write_brief(p)
                project = project_title(p.raw_prompt or "")
                p.plan_md = render_plan_md(p, build_design_spec(design_inputs(p, project)))
                write_artifact(p, "PLAN.md", p.plan_md)
        if data.get("approve") is True:
            p.approve_plan()
            return {"pipeline": p, "notice": None}
        if changed and not (data.get("feedback") or "").strip():
            return {"pipeline": p, "notice": "Đã cập nhật kế hoạch: " + "; ".join(changed) + "."}
        fb = (data.get("feedback") or "").strip()
        if not fb:
            return {"pipeline": p, "notice": "Bạn ghi rõ điều muốn đổi giúp mình nhé (ví dụ: đổi sang tông tối)."}
        changes = feedback_changes(agent, fb, p.pillars)
        for pillar, value in changes.items():
            setattr(p.pillars, pillar, value)
        p.plan_feedback.append(fb)
        p.request_plan_changes()
        return {"pipeline": p, "notice": feedback_notice(changes)}

    # ---------------------------------------------------------------- art director
    def styling(p: PipelineState) -> bool:
        return bool(deps.stylist and p.mode is not BuildMode.CLONE and hasattr(deps.build, "write_style_layer"))

    async def look_at(p: PipelineState, sec: Section) -> str:
        """Shoot the section just measured at 1440 and 375, have it judged, fix what CSS can fix by sight
        (kept only if the verdict improves and the phone does not overflow), then move on."""
        if not (deps.section_eye and p.mode is not BuildMode.CLONE and hasattr(deps.build, "section_shots")):
            return ""
        folder = deps.artifacts_root / p.session_id / "artifacts" / "shots"
        page = p.selected_page or ""
        shots = await deps.build.section_shots(p.session_id, sec.id, folder, "v0")
        verdict = shots and await asyncio.to_thread(deps.section_eye.look, sec.name, sec.content, p.raw_prompt or "",
                                                    shots["images"])
        if not shots or not verdict:
            return ""
        first, tries, fixed, picked = verdict, 0, 0, None
        options = [v for v in variants_for(sec.structure)]  # hand-written, QA-safe compositions first
        while not verdict.ok and verdict.fixable and tries < EYE_MAX_FIXES and hasattr(deps.build, "write_style_layer"):
            if options:
                variant = options.pop(0)
                css, _ = validate_css(variant.for_section(sec.id), [sec.id])
                label, notes = variant.label, [f"{sec.id} → biến thể “{variant.label}”"]
            elif styling(p):  # no variant left: the art director fixes the notes by sight
                outline = section_outline(await deps.build.outline(p.session_id), sec.id)
                patch = await asyncio.to_thread(deps.stylist.fix_section, sec.id, [i.line() for i in verdict.fixable],
                                                outline, shots["images"])
                if not patch:
                    break
                css, label, notes = patch.css, None, patch.notes
            else:
                break
            tries += 1
            # A variant replaces the section's earlier variant; a fix adds to what is kept.
            if label:
                for r in p.style_rounds:
                    if r["kind"] == "section" and r.get("section") == sec.id and r.get("variant") and r.get("kept"):
                        r.update(kept=False, why="replaced")
            p.style_rounds.append({"kind": "section", "section": sec.id, "css": css, "notes": notes, "kept": None,
                                   "variant": label})
            await deps.build.write_style_layer(p.session_id, page, kept_css(p, with_pending=True), step=Step.B9_DEVELOP)
            again = await deps.build.section_shots(p.session_id, sec.id, folder, f"v{tries}")
            seen = again and not again["overflow"] and await asyncio.to_thread(
                deps.section_eye.look, sec.name, sec.content, p.raw_prompt or "", again["images"])
            if seen and seen.better_than(verdict):
                p.style_rounds[-1]["kept"] = True
                verdict, shots, fixed = seen, again, fixed + 1
                picked = label or picked
            else:
                p.style_rounds[-1].update(kept=False, why="eye")
                if label:  # the variant this one replaced comes back
                    for r in reversed(p.style_rounds[:-1]):
                        if r["kind"] == "section" and r.get("section") == sec.id and r.get("why") == "replaced":
                            r.update(kept=True, why=None)
                            break
                await deps.build.write_style_layer(p.session_id, page, kept_css(p), step=Step.B9_DEVELOP)
        p.section_reviews[sec.id] = {"name": sec.name, "files": shots["files"], "ok": verdict.ok, "score": verdict.score,
                                     "issues": [i.line() for i in verdict.issues], "fixed": fixed, "tries": tries,
                                     "first_score": first.score, "variant": picked}
        state_word = "đạt" if verdict.ok else f"còn {len(verdict.issues)} góp ý"
        fix_word = (f", chọn bố cục “{picked}”" if picked else "") + (f", thử {tries} lần" if tries else "")
        return f"Mắt xem “{sec.name}” ở 1440 & 375: {state_word} ({verdict.score:.0f}/10{fix_word})"

    async def style_context(p: PipelineState) -> str:
        sections = page_sections(p)
        outline = await deps.build.outline(p.session_id) if hasattr(deps.build, "outline") else ""
        intent = "\n".join(design_intent(p, sections))
        listing = "\n".join(f"- {s.id} · {s.structure} · {s.content[:120]}" for s in sections)
        return (f"Brief: {p.raw_prompt or ''}\nTheme: {p.pillars.theme} · layout {p.pillars.layout} · "
                f"density {p.pillars.margins} · surface {p.pillars.surface or 'flat'}\n\n{intent}\n\n"
                f"Sections (id · template · purpose):\n{listing}\n\nDOM outline (tags and classes):\n{outline[:7000]}")

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
        first = "wireframe (khung xám, chưa màu và chữ) cho" if p.mode is BuildMode.CLONE and not p.heal_history else "dựng"
        return {"pipeline": p, "notice": f"B8 · Phòng Design đã cài tokens.css. Bắt đầu {first} {len(sections)} section."}

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
            own_photos = bool(shared_photos(p))  # photos attached to single items leave the rest to the bot
            if deps.photo_bot and p.mode is not BuildMode.CLONE and not own_photos and not p.preview_url:
                key = photo_key(p)
                if p.page_photos_key != key:  # once per project brief: the bot searches and looks at photos
                    p.page_photos = await asyncio.to_thread(deps.photo_bot, p)
                    p.page_photos_key = key
            if not p.preview_url:
                generated = [x["url"] for x in p.page_photos or [] if str(x.get("url", "")).startswith("uploads/")]
                files = [f for x in own_files(p, "product-image") + own_files(p, "logo") + generated
                         if (f := resolve_upload(deps.artifacts_root, p.session_id, x))]
                if files and hasattr(deps.build, "import_uploads"):
                    await deps.build.import_uploads(p.session_id, files)
                if p.mode is BuildMode.CLONE and not p.heal_history and hasattr(deps.build, "begin_wireframe"):
                    deps.build.begin_wireframe(p.session_id)  # designer passes: wireframe -> colour -> content
                photos = build_copy(p).images
                p.preview_url = await (deps.build.start_app(p.session_id, project, spec, route, photos) if photos
                                       else deps.build.start_app(p.session_id, project, spec, route))
            if not p.sections_done and (p.heal_rules or p.heal_contrast):  # first tick of a heal loop
                healed = await deps.build.heal(p.session_id, p.heal_rules, p.heal_contrast)
                p.token_changes += [f"{c.token}: {c.old} → {c.new} (B11: {c.reason})" for c in healed]
                p.heal_contrast = []
            if p.mode is BuildMode.CLONE and p.clone and p.clone.components and hasattr(deps.build, "set_reference"):
                # The factory cursors tune each section's components to the reference's (B2 reading).
                built = {s.id for s in sections}  # sections the CloneSpec skips are not compared
                deps.build.set_reference(p.session_id, {k: v for k, v in p.clone.components.items() if k in built}, p.clone.boxes,
                                         {s.id: s.name for s in sections}, slug)
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
            motion, motion_error, js = [], None, []
            if to_check and (by_id[to_check].effect or by_id[to_check].motion) and "mcp_motion" in tools_for(p.step):
                try:
                    sec = by_id[to_check]
                    if p.mode is not BuildMode.CLONE and hasattr(deps.build, "motion_js"):  # GSAP / Three.js
                        js = await deps.build.motion_js(p.session_id, slug, sec.id, js_effects(sec.effect, sec.structure))
                    if not js:
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
            wire = getattr(deps.build, "wireframe_active", None)
            parts.append(f"{'Wireframe' if wire and wire(p.session_id) else 'Dev viết'} “{to_write.name}”")
        if to_check:
            check = next(r for r in results if isinstance(r, SectionCheck))
            p.sections_checked.append(to_check)
            p.token_changes += [f"{c.token}: {c.old} → {c.new} ({c.reason})" for c in check.changes]
            p.open_findings += [f"{f.section}: {f.detail}" for f in check.open]
            fixed = f", sửa {len(check.changes)} token" if check.changes else ""
            parts.append(f"Design đo “{by_id[to_check].name}”{fixed}")
            if check.match_before is not None:
                line = (f"{by_id[to_check].name}: {check.components} component · {', '.join(check.crews)} · "
                        f"khớp {check.match_before:.0f}% → {check.match_after:.0f}%"
                        + (f" (chỉnh {check.tuned} thuộc tính)" if check.tuned else ""))
                p.factory_log = [x for x in p.factory_log if not x.startswith(by_id[to_check].name + ":")] + [line]
                parts.append(f"Nhà máy cursor: {len(check.crews)} tổ, {check.components} component, khớp "
                             f"{check.match_before:.0f}→{check.match_after:.0f}%")
            for fx in motion:
                line = f"{fx.section_id}: {fx.effect} ({fx.kind}, qua MCP)"
                if line not in p.motion_effects:  # a heal loop rebuilds the sections: list each effect once
                    p.motion_effects.append(line)
                parts.append(f"Motion thêm {fx.effect} qua MCP")
            if js and (line := f"{to_check}: {', '.join(js)} (GSAP / Three.js)") not in p.motion_effects:
                p.motion_effects.append(line)
                parts.append(f"Motion thêm {', '.join(js)} (GSAP / Three.js)")
            if motion_error:
                p.motion_effects.append(f"{to_check}: bỏ qua hiệu ứng ({motion_error[:80]})")
            try:
                if seen := await look_at(p, by_id[to_check]):
                    parts.append(seen)
            except Exception as e:  # noqa: BLE001 — looking never stops a build
                log.warning("section eye failed for %s: %s", to_check, e)
        if p.can_advance():
            p.advance()
            if hasattr(deps.build, "release_checks"):
                await deps.build.release_checks(p.session_id)  # every section looked at: close the hidden tabs
        done = f"{len(p.sections_checked)}/{len(p.sections_planned)}"
        return {"pipeline": p, "notice": f"B9 · {' · '.join(parts)} ({done})"}

    async def b10(state: GraphState) -> dict:
        p = _copy(state)
        active = getattr(deps.build, "wireframe_active", None)
        if active and active(p.session_id):
            # Designer passes, one per graph pass so the Studio sees each: colour first, then the content.
            try:
                if "colour" not in p.build_passes:
                    sketch_note = ""
                    if p.mode is BuildMode.CLONE and p.clone and p.clone.components and hasattr(deps.build, "sketch_check"):
                        # The wireframe, sketched like the reference was at B2: does the layout match before colour?
                        with contextlib.suppress(Exception):
                            built = {s.id for s in build_context(p)[2]}
                            res = await deps.build.sketch_check(
                                p.session_id, {k: v for k, v in p.clone.boxes.items() if k in built},
                                {k: v for k, v in p.clone.components.items() if k in built},
                                deps.artifacts_root / p.session_id / "artifacts" / "sketch")
                            if res:
                                p.clone.sketch_built = res
                                low = sorted(res["sections"].items(), key=lambda kv: kv[1])[:3]
                                sketch_note = (f" Sketch bản dựng khớp {res['score']:g}% sketch trang mẫu"
                                               + (f", ảnh chụp giống {res['pixel_score']:g}%" if res.get("pixel_score") is not None else "")
                                               + (" (thấp nhất: " + ", ".join(f"{k} {v:g}%" for k, v in low) + ")" if low else "") + ".")
                    await deps.build.colour(p.session_id)
                    p.build_passes.append("colour")
                    return {"pipeline": p, "notice": "B10 · Tô màu: hệ màu của DESIGN.md thay cho khung xám của wireframe." + sketch_note}
                await deps.build.fill_content(p.session_id)
                p.build_passes.append("content")
                return {"pipeline": p, "notice": "B10 · Điền nội dung: chữ và ảnh vào từng phần, rồi ghép trang."}
            except Exception as e:
                log.exception("B10 pass failed")
                p.build_error = f"B10: {e}"
                return {"pipeline": p, "notice": f"Lỗi khi tô màu / điền nội dung: {e}"}
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
        composed = ""
        if deps.compose and styling(p) and not p.style_rounds:  # once per build: the art director composes this page
            patch = await asyncio.to_thread(deps.stylist.compose, await style_context(p), p.sections_planned)
            # No patch: an empty layer, so a rebuilt page never keeps a composition made for an earlier plan.
            await deps.build.write_style_layer(p.session_id, p.selected_page or "", patch.css if patch else "")
            if patch:
                p.style_rounds.append({"kind": "compose", "css": patch.css, "notes": patch.notes, "kept": None})
                composed = f" Art director bố cục lại {len(patch.notes) or 'vài'} điểm cho riêng trang này."
        p.advance()
        left = f" Còn {len(report.open)} điểm chuyển cho B11." if report.open else " Không còn lỗi thiết kế."
        return {"pipeline": p, "notice": f"B10 · Đã ghép {len(p.sections_planned)} section trên {p.preview_url}.{left}{composed}"}

    # ---------------------------------------------------------------- B11
    async def b11(state: GraphState) -> dict:
        """Master QA. PASS -> B12. FAIL -> patches for Dev/Design and back to B8 (max 3 loops),
        or straight to the user when nothing left is patchable. Clone: after QA passes, the 1:1
        acceptance against the reference (its own pass)."""
        p = _copy(state)
        _, spec, sections = build_context(p)
        if p.qa_passed and p.mode == BuildMode.CLONE and p.clone and getattr(deps.build, "compare", None):
            return await b11_accept(p, spec, sections)
        try:
            report = await deps.build.master_qa(p.session_id, spec, creative=p.mode is not BuildMode.CLONE)
        except Exception as e:
            log.exception("B11 failed")
            p.build_error = f"B11: {e}"
            return {"pipeline": p, "notice": f"Lỗi khi chạy Master QA: {e}"}
        unproven = [r for r in p.style_rounds if r["kind"] == "section" and r.get("kept") is True and not r.get("qa")]
        if unproven and not report.passed:
            # Fixes made by sight in B9 broke a QA rule: all of them go, QA runs again on the plain templates.
            for r in unproven:
                r.update(kept=False, why="qa")
            await deps.build.write_style_layer(p.session_id, p.selected_page or "", kept_css(p), step=Step.B11_MASTER_QA)
            return {"pipeline": p, "notice": f"B11 · {len(unproven)} chỉnh sửa theo mắt ở B9 làm hỏng kiểm tra nên đã bỏ; "
                                              "kiểm tra lại trang…"}
        if report.passed:
            for r in unproven:
                r["qa"] = True
        pending = p.style_rounds[-1] if p.style_rounds and p.style_rounds[-1].get("kept") is None else None
        if pending and not report.passed:
            # The art director's layer broke a QA rule: it is dropped, never healed around.
            pending.update(kept=False, why="qa", failures=[f.detail for f in report.failures][:5])
            await deps.build.write_style_layer(p.session_id, p.selected_page or "", kept_css(p), step=Step.B11_MASTER_QA)
            if pending["kind"] == "refine":  # the page before this round passed QA and was graded
                p.design_score, p.design_critique = pending["before"], pending["critique"]
                p.qa_summary, p.qa_failures, p.qa_passed = pending["qa_summary"], [], True
                write_artifact(p, "CRITIQUE.md", pending["critique_md"])
                p.advance()
                return {"pipeline": p, "notice": f"B11 · Bản chỉnh theo nhận xét làm hỏng {len(report.failures)} bài kiểm tra "
                                                  f"nên đã bỏ; giữ bản trước (thẩm mỹ {p.design_score:.1f}/10)."}
            return {"pipeline": p, "notice": "B11 · Lớp bố cục của art director làm hỏng kiểm tra nên đã bỏ; kiểm tra lại trang…"}
        p.qa_summary = report.summary()
        p.qa_failures = [f"[Bài {f.test}] {f.detail}" + (f" ({f.viewport}px)" if f.viewport else "") for f in report.failures]
        if report.passed:
            p.qa_passed = True
            notice = "B11 · Master Cursor: 100% PASSED — cả 4 bài kiểm tra đều đạt."
            if pending and pending["kind"] == "compose":
                pending["kept"] = True
            accept = getattr(deps.build, "compare", None)
            if p.mode == BuildMode.CLONE and p.clone and accept:
                # Next pass: the 1:1 acceptance against the reference link (b11_accept).
                return {"pipeline": p, "notice": notice + " Tiếp theo: Master Cursor nghiệm thu 1:1 với link gốc."}
            # Design critic (vision model): QA proves the page is not wrong, this grades how good it looks.
            if critic := getattr(deps.build, "critique", None):
                context = f"{p.raw_prompt or ''} · trang {p.selected_page or ''} · phong cách {p.pillars.theme}"
                if c := await critic(p.session_id, context):
                    p.design_score = c.overall
                    p.design_critique = [f"{i.where}: {i.problem} → {i.fix}" for i in c.issues]
                    critique_md = render_markdown(c)
                    write_artifact(p, "CRITIQUE.md", critique_md)
                    notice += f" Chấm thẩm mỹ: {c.overall:.1f}/10."
                    if pending and pending["kind"] == "refine":
                        pending["after"] = c.overall
                        if c.overall < pending["before"] + MIN_GAIN:  # not better: back to the graded page before it
                            pending["kept"] = False
                            pending["why"] = "score"
                            await deps.build.write_style_layer(p.session_id, p.selected_page or "", kept_css(p),
                                                               step=Step.B11_MASTER_QA)
                            p.design_score, p.design_critique = pending["before"], pending["critique"]
                            write_artifact(p, "CRITIQUE.md", pending["critique_md"])
                            notice += f" Không tốt hơn bản trước nên giữ bản trước ({p.design_score:.1f}/10)."
                        else:
                            pending["kept"] = True
                            notice += f" Tăng từ {pending['before']:.1f} nhờ chỉnh theo nhận xét."
                    rounds = sum(1 for r in p.style_rounds if r["kind"] == "refine")
                    if (styling(p) and p.design_score < REFINE_TARGET and rounds < MAX_REFINES
                            and not (pending and pending.get("kept") is False)):
                        patch = await asyncio.to_thread(deps.stylist.refine, p.design_critique, await style_context(p),
                                                        p.sections_planned)
                        if patch:
                            p.style_rounds.append({"kind": "refine", "css": patch.css, "notes": patch.notes, "kept": None,
                                                   "before": p.design_score, "critique": p.design_critique,
                                                   "critique_md": critique_md, "qa_summary": p.qa_summary})
                            await deps.build.write_style_layer(p.session_id, p.selected_page or "",
                                                               kept_css(p, with_pending=True), step=Step.B11_MASTER_QA)
                            p.qa_passed = False
                            return {"pipeline": p, "notice": notice + f" Dưới {REFINE_TARGET:.0f}: art director sửa "
                                                             f"{len(patch.notes) or 'các'} điểm theo nhận xét (vòng {rounds + 1}), "
                                                             "rồi kiểm tra và chấm lại."}
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
        clone_accept = p.mode == BuildMode.CLONE and p.clone and getattr(deps.build, "compare", None)
        if not new_rules and not contrast:
            p.escalate_qa(p.qa_failures)
            if clone_accept:  # still compare with the reference, so the user sees how close it is
                p.compare_rounds = 2
                return await b11_accept(p, spec, sections)
            p.advance()
            return {"pipeline": p, "notice": f"B11 · Còn {len(report.failures)} lỗi hệ thống không tự sửa được, "
                                              "chuyển cho bạn xem xét ở bước bàn giao."}
        iteration = len(p.heal_history) + 1
        p.record_qa_failure(p.qa_failures)
        if p.escalated_to_user:  # MAX_HEAL_ITERATIONS reached
            if clone_accept:
                p.compare_rounds = 2
                return await b11_accept(p, spec, sections)
            p.advance()
            return {"pipeline": p, "notice": f"B11 · Đã tự sửa {iteration} vòng, còn {len(report.failures)} lỗi. "
                                              "Chuyển cho bạn quyết định."}
        p.heal_rules += new_rules
        p.heal_contrast = contrast
        return {"pipeline": p, "notice": f"B11 · {len(report.failures)} lỗi, vòng tự sửa {iteration}: "
                                          f"Dev vá {len(new_rules)} điểm CSS, Design sửa {len(contrast)} cặp màu. Dựng lại…"}

    async def b11_accept(p: PipelineState, spec, sections: list[Section]) -> dict:
        """Master cursor compares every section with the reference link, component by component.
        Differences it can measure are tuned into match.css and checked again (QA re-runs, max 2 rounds)."""
        try:
            shots = deps.artifacts_root / p.session_id / "artifacts" / "compare"
            result = await deps.build.compare(p.session_id, p.clone.url, sections, p.clone.boxes,
                                              p.selected_page or "", shots)
        except Exception as e:
            log.exception("1:1 acceptance failed")
            result = None
            notice_err = f" (nghiệm thu 1:1 lỗi: {str(e)[:100]})"
        else:
            notice_err = ""
        notice = "B11 · Nghiệm thu 1:1"
        if result:
            rounds = p.compare_rounds + (1 if result.get("tuned") else 0)
            p.clone_compare = {**result, "rounds": rounds}
            if result.get("tuned") and p.compare_rounds < 2:
                p.compare_rounds += 1
                p.qa_passed = False  # the page changed: Master QA checks it again before the next comparison
                return {"pipeline": p, "notice": (f"B11 · Nghiệm thu 1:1 vòng {p.compare_rounds}: giống {result['total']:.0f}% — "
                                                  f"chỉnh {result['tuned']} thuộc tính cho khớp trang mẫu, kiểm tra lại…")}
            notice += f": giống {result['total']:.0f}% theo từng component"
            low = [s for s in result["sections"] if s["score"] < 80]
            if low:
                notice += " · cần xem: " + ", ".join(f"{s['name'] or s['id']} {s['score']:.0f}%" for s in low[:4])
        notice += notice_err
        if critic := getattr(deps.build, "critique", None):
            context = f"{p.raw_prompt or ''} · trang {p.selected_page or ''} · phong cách {p.pillars.theme}"
            if c := await critic(p.session_id, context):
                p.design_score = c.overall
                p.design_critique = [f"{i.where}: {i.problem} → {i.fix}" for i in c.issues]
                write_artifact(p, "CRITIQUE.md", render_markdown(c))
        if measure := getattr(deps.build, "fidelity", None):
            if f := await measure(p.session_id, p.clone.url):
                p.clone_fidelity = f.total
                p.clone_fidelity_notes = f.notes
                write_artifact(p, "FIDELITY.md", render_fidelity(f, p.clone.url))
                notice += f" · độ giống toàn trang {f.total:.0f}/100"
        if p.clone_compare:
            write_artifact(p, "COMPARE.md", render_compare(p.clone_compare, p.clone.url))
        p.advance()
        return {"pipeline": p, "notice": notice + "."}

    # ---------------------------------------------------------------- B12
    async def b12(state: GraphState) -> dict:
        """Handover: overlay removed, the window belongs to the user. Next: refine this page
        (back to B5, re-approval at B7) or build another sitemap page (B6, DESIGN.md kept)."""
        p = _copy(state)
        pending = [pg for pg in p.sitemap if pg.slug not in p.page_routes]
        verdict = ("Master QA đạt 100% cả 4 bài." if p.qa_passed
                   else f"Master QA còn {len(p.qa_failures)} lỗi hệ thống chưa tự sửa được, bạn xem danh sách bên dưới.")
        await deps.build.handover(p.session_id, handover_options(p))
        answer = interrupt(Question(
            step="B12", kind="handover", key="handover", allow_free_text=True,
            recommended=pending[0].slug if pending else None,
            text=(f"Đã bàn giao trang · {p.preview_url}. {verdict}\n"
                  "Cửa sổ trình duyệt giờ là của bạn: bấm thử mọi thứ, rồi chọn một trong hai cách đi tiếp — "
                  "dựng trang tiếp theo trong sitemap (giữ nguyên DESIGN.md), hoặc ghi góp ý để tinh chỉnh trang này "
                  "(Chroma cập nhật kế hoạch để bạn duyệt lại rồi dựng lại)."),
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
    """Session-facing API used by the WebSocket server.

    With `db_path`, every checkpoint is written to SQLite, so a session survives a backend restart
    (the Studio keeps its session id): the graph is compiled on first use, inside the running loop.
    Without it, sessions live in memory (tests, one-off scripts)."""

    def __init__(self, deps: Deps | None = None, db_path: Path | None = None, checkpointer=None):
        self.deps = deps
        self.db_path = None if checkpointer is not None else db_path
        # `checkpointer`: a ready saver (Clone sessions mirrored to Supabase, clone/checkpoints.py)
        self._graph = None if self.db_path else build_graph(deps, checkpointer=checkpointer)
        self._conn = None
        self._lock = asyncio.Lock()
        self._recovered: set[str] = set()

    async def graph(self):
        if self._graph is None:
            async with self._lock:
                if self._graph is None:
                    import aiosqlite
                    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    self._conn = await aiosqlite.connect(str(self.db_path))
                    saver = AsyncSqliteSaver(self._conn, serde=SERDE)
                    await saver.setup()
                    self._graph = build_graph(self.deps, checkpointer=saver)
        return self._graph

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @staticmethod
    def _config(session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}, "recursion_limit": 200}

    async def snapshot(self, session_id: str) -> dict:
        snap = await (await self.graph()).aget_state(self._config(session_id))
        values = snap.values or {}
        pipeline = values.get("pipeline") if isinstance(values, dict) else None
        if isinstance(pipeline, dict):
            pipeline = PipelineState.model_validate(pipeline)
        question = snap.interrupts[0].value if snap.interrupts else None
        return {"pipeline": pipeline, "question": question,
                "notice": values.get("notice") if isinstance(values, dict) else None,
                "finished": not snap.next and pipeline is not None}

    async def start(self, session_id: str) -> dict:
        graph = await self.graph()
        snap = await graph.aget_state(self._config(session_id))
        if not snap.values:
            self._recovered.add(session_id)  # new in this process: nothing to recover
            await graph.ainvoke({"pipeline": PipelineState(session_id=session_id)}, self._config(session_id))
        return await self.snapshot(session_id)

    async def interrupted(self, session_id: str) -> bool:
        """True once per process for a saved session whose run stopped between two steps (the backend
        was restarted mid-build): it has no question for the user and is not finished."""
        if session_id in self._recovered:
            return False
        self._recovered.add(session_id)
        snap = await self.snapshot(session_id)
        return snap["pipeline"] is not None and snap["question"] is None and not snap["finished"]

    async def continue_run(self, session_id: str, on_progress: Any = None) -> dict:
        """Carry on an interrupted run. A build is restarted from B8 (the dev server and browser died
        with the old process); the documents, approval and earlier pages are kept."""
        graph = await self.graph()
        snap = await self.snapshot(session_id)
        p: PipelineState = snap["pipeline"]
        if p.step in (Step.B8_DESIGN, Step.B9_DEVELOP, Step.B10_INTEGRATE, Step.B11_MASTER_QA):
            p = p.model_copy(deep=True)
            p._reset_build()
            p.step = Step.B8_DESIGN
            await graph.aupdate_state(self._config(session_id), {
                "pipeline": p, "notice": "Máy chủ vừa khởi động lại: dựng lại trang từ bước B8, kế hoạch đã duyệt giữ nguyên."})
        return await self._run(session_id, None, on_progress)

    async def answer(self, session_id: str, value: Any, on_progress: Any = None) -> dict:
        """Resume with the user's answer. `on_progress(snapshot)` is awaited after every node,
        so long B8-B10 runs stream section-by-section progress to the Studio."""
        # LangGraph cannot resume with None; nodes treat "" as "skipped".
        return await self._run(session_id, Command(resume="" if value is None else value), on_progress)

    async def _run(self, session_id: str, command: Any, on_progress: Any) -> dict:
        graph = await self.graph()
        async for _ in graph.astream(command, self._config(session_id), stream_mode="updates"):
            if on_progress:
                snap = await self.snapshot(session_id)
                if snap["question"] is None and not snap["finished"]:
                    await on_progress(snap)
        return await self.snapshot(session_id)
