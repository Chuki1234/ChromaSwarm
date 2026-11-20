"""Pydantic state for the ChromaSwarm 12-step pipeline (B1 -> B12).

Gates are enforced here in code, not in prompts:
- every step has deterministic exit criteria (`missing_for_exit`);
- tools are granted per step (`ALLOWED_TOOLS`), so B1-B7 agents never see a
  code-writing tool;
- Clarity Score is computed from filled pillars, never self-reported by an LLM;
- B7 (plan approval) can only be passed by an explicit user action;
- the B11 self-healing loop is capped by `MAX_HEAL_ITERATIONS`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


class Step(StrEnum):
    B1_READ_PROMPT = "B1"
    B2_SITEMAP = "B2"
    B3_ELICITATION = "B3"
    B4_ASSETS = "B4"
    B5_DESIGN_MD = "B5"
    B6_PLAN = "B6"
    B7_APPROVAL = "B7"
    B8_DESIGN = "B8"
    B9_DEVELOP = "B9"
    B10_INTEGRATE = "B10"
    B11_MASTER_QA = "B11"
    B12_HANDOVER = "B12"


ORDER: list[Step] = list(Step)

MAX_HEAL_ITERATIONS = 3


class Domain(StrEnum):
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    BOOKING = "booking"
    EDTECH = "edtech"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class Framework(StrEnum):
    NEXTJS = "nextjs"
    REACT_VITE = "react-vite"
    ANGULAR = "angular"


class PageStatus(StrEnum):
    PENDING = "pending"
    BUILDING = "building"
    DONE = "done"


class SitemapPage(BaseModel):
    slug: str
    title: str
    purpose: str
    status: PageStatus = PageStatus.PENDING


class Pillars(BaseModel):
    """The 5 elicitation pillars of B3, in their mandatory order."""

    theme: str | None = None
    layout: str | None = None
    color: str | None = None
    margins: str | None = None
    scope: str | None = None
    # Optional material (presets.Surface), asked right after the theme. Not one of the 5 pillars:
    # it never counts toward the Clarity Score and defaults to the theme's own flat surfaces.
    surface: str | None = None

    ORDERED_FIELDS: ClassVar[tuple[str, ...]] = ("theme", "layout", "color", "margins", "scope")

    def missing(self) -> list[str]:
        return [f for f in self.ORDERED_FIELDS if not (getattr(self, f) or "").strip()]

    def next_question(self) -> str | None:
        """The pillar to ask about next. Enforces the Theme->...->Scope order."""
        missing = self.missing()
        return missing[0] if missing else None

    @property
    def clarity_score(self) -> float:
        return round((len(self.ORDERED_FIELDS) - len(self.missing())) / len(self.ORDERED_FIELDS), 2)


class Reference(BaseModel):
    """A visual reference. Only its Design DNA may be learned, never its DOM/text."""

    screenshot_path: str | None = None
    url: str | None = None  # plain str (not HttpUrl) so LangGraph checkpoints can serialize it
    url_recommended: bool = False  # set once the agent has asked for the URL

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        host = v.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
        if "." not in host and host != "localhost":  # a local dev server is a valid (own) reference
            raise ValueError(f"not a web URL: {v}")
        return v


class BuildMode(StrEnum):
    CREATIVE = "creative"  # build from the user's idea, chatting through B1-B7
    CLONE = "clone"  # rebuild the page at a link (structure; text and images too if the user owns it)


class CloneSource(BaseModel):
    """Clone mode input and what was read from the reference page."""

    url: str
    owned: bool = False  # user confirmed the site is theirs: its text and images may be copied
    analysed: bool = False
    title: str | None = None
    sections: list[dict] = Field(default_factory=list)  # planner.Section dumps, in the page's order
    pillars: dict[str, str] = Field(default_factory=dict)
    heading_font: str | None = None
    body_font: str | None = None
    fonts: list[dict] = Field(default_factory=list)  # kept reference fonts: load URL + Vietnamese fallback
    lang: str | None = None  # the reference page's language (<html lang> or measured); the rebuild keeps it
    media_share: float = 0.0  # share of the reference page that is pictures
    # Structure clone of a picture/text-led page: the user's own similar photos and words, by slot (B4).
    content_asked: bool = False
    user_images: list[str] = Field(default_factory=list)  # file names in workspaces/<session>/uploads, slot order
    user_texts: dict[str, str] = Field(default_factory=dict)  # name, headline, intro, email, projects
    content: dict | None = None  # owned sites only
    notes: list[str] = Field(default_factory=list)
    content_width: int | None = None  # narrow single-column reference: its column width (px, 8pt)
    described: bool = True  # False: only a link was given (the default form); the kind of site is guessed at B2
    # The description asked for an exact copy ("100%", "y hệt"): the B2 notice says what is and is not copied.
    exact_requested: bool = False
    # Owned clones: the user confirms ownership again at B3, shown the reference's own name. None = not asked.
    owner_confirmed: bool | None = None
    # Per section of the reference: its box and its smallest pieces (geometry + computed style only).
    boxes: dict[str, dict] = Field(default_factory=dict)
    components: dict[str, list[dict]] = Field(default_factory=dict)
    # B2 effect check (clone/motion_check.py): the page operated with Playwright, effects timed.
    motion_checked: bool = False
    motion_report: dict | None = None
    analysis: str | None = None  # B2 top-down analysis (clone/analysis.py, ANALYSIS.md): measurements only
    # CLONE_BRIEF.md (clone/brief_doc.py): the build team's preparation sheet — concept, sections and why,
    # spacing, type / colour / backgrounds, pictures, every control (hover, click, destination), effects, and
    # what may and may not be cloned. Inputs are measurements only.
    style: dict | None = None  # StyleDNA dump (colours, fonts, spacing scale, radii, separation)
    backgrounds: list[dict] = Field(default_factory=list)
    media: list[dict] = Field(default_factory=list)
    brief: str | None = None
    # Sketch step (clone/sketch.py): the page drawn from what was read, checked against a screenshot; gaps
    # measured again. False = the B2 sketch pass is pending (old sessions default to done).
    sketched: bool = True
    sketch: dict | None = None  # coverage (before / after re-measuring), gaps, screen pairs (artifacts/sketch/)
    sketch_built: dict | None = None  # B10: the rebuild's wireframe sketch vs the reference's, per section
    spec: dict | None = None  # CloneSpec dump (clone/spec.py): copy / replace / skip / todo per item, used by the build


class Asset(BaseModel):
    kind: str  # logo | product-image | copy | pricing | other
    path_or_text: str
    note: str = ""


class HealAttempt(BaseModel):
    iteration: int
    failures: list[str]


class PipelineState(BaseModel):
    session_id: str
    step: Step = Step.B1_READ_PROMPT

    # B1
    mode: BuildMode | None = None
    clone: CloneSource | None = None
    raw_prompt: str | None = None
    domain: Domain | None = None
    framework: Framework = Framework.NEXTJS

    # B2
    sitemap: list[SitemapPage] = Field(default_factory=list)
    selected_page: str | None = None

    # B3
    pillars: Pillars = Field(default_factory=Pillars)

    # B4
    assets: list[Asset] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    assets_confirmed: bool = False  # user said "that's all I have"

    # B5-B6
    tokens_css: str | None = None
    plan_feedback: list[str] = Field(default_factory=list)  # B7 change requests
    design_md: str | None = None
    product_md: str | None = None
    plan_md: str | None = None

    # B7
    plan_approved: bool = False

    # B8-B10
    design_system_installed: bool = False  # B8: tokens.css written into the workspace
    sections_planned: list[str] = Field(default_factory=list)
    sections_done: list[str] = Field(default_factory=list)  # B9 Developer: written
    sections_checked: list[str] = Field(default_factory=list)  # B9 Design: measured (and repaired)
    preview_url: str | None = None
    page_routes: dict[str, str] = Field(default_factory=dict)  # sitemap slug -> app route ("/" for the first page)
    motion_effects: list[str] = Field(default_factory=list)  # B8.1 effects applied via MCP
    token_changes: list[str] = Field(default_factory=list)  # Design fixes written to tokens.css
    open_findings: list[str] = Field(default_factory=list)  # left for the Developer / B11
    integrated: bool = False
    build_passes: list[str] = Field(default_factory=list)  # Clone designer passes done at B10: colour, content
    build_error: str | None = None  # a B8-B10 failure the user must see; stops the build loop

    # B11
    qa_passed: bool = False
    heal_history: list[HealAttempt] = Field(default_factory=list)
    escalated_to_user: bool = False
    qa_summary: str | None = None
    qa_failures: list[str] = Field(default_factory=list)  # human-readable, latest run
    heal_rules: list[str] = Field(default_factory=list)  # Developer CSS patches -> app/heal.css
    heal_contrast: list[dict] = Field(default_factory=list)  # colour pairs for the Design department
    # B3: a detailed first message read as a design brief (agents/brief.py, validated). It pre-fills
    # pillars, orders the landing sections and feeds the copywriter. None = no brief / not read yet.
    brief: dict | None = None
    brief_read: bool = False
    brief_applied: bool = False  # B3 pre-fill from the brief done (once)
    # B3: scope answered in several messages ("18-30 tuổi", then "điện thoại", then "Mua ngay")
    # is judged as one answer: earlier unclear parts are kept here until the whole is clear.
    scope_draft: str | None = None
    # B9: page copy written once by the LLM copywriter (developer/copywriter.py), validated; keyed by
    # what it was written from so a B7/B12 change rewrites it. None = rule-based sample copy.
    page_copy: dict | None = None
    page_copy_key: str | None = None
    design_score: float | None = None  # B11 design critic (vision model), 1-10; None = no critic
    design_critique: list[str] = Field(default_factory=list)  # "where: problem → fix"
    clone_fidelity: float | None = None  # Clone mode, B11: closeness to the reference, 0-100 (clone/fidelity.py)
    clone_fidelity_notes: list[str] = Field(default_factory=list)
    # Clone B11 1:1 acceptance (Master cursor, section by section against the reference link).
    clone_compare: dict | None = None  # {"total", "rounds", "sections": [SectionCompare dumps], "tuned"}
    compare_rounds: int = 0  # acceptance rounds that changed match.css (max 2, then hand over)
    factory_log: list[str] = Field(default_factory=list)  # B9 factory: what each section's crews tuned

    # B12
    handover_closed: bool = False  # user chose "finish": no further page in this session

    # ------------------------------------------------------------------ gates

    def missing_for_exit(self) -> list[str]:
        """Exit criteria of the current step. Empty list == may advance."""
        s = self.step
        if s is Step.B1_READ_PROMPT:
            out = [n for n, v in (("mode", self.mode), ("raw_prompt", self.raw_prompt), ("domain", self.domain)) if not v]
            if self.mode is BuildMode.CLONE and not (self.clone and self.clone.url):
                out.append("clone_url")
            return out
        if s is Step.B2_SITEMAP and self.mode is BuildMode.CLONE and not (self.clone and self.clone.analysed):
            return ["clone_analysis"]
        if s is Step.B2_SITEMAP:
            out = []
            if not self.sitemap:
                out.append("sitemap")
            if not self.selected_page or self.selected_page not in {p.slug for p in self.sitemap}:
                out.append("selected_page")
            return out
        if s is Step.B3_ELICITATION:
            return [f"pillar:{m}" for m in self.pillars.missing()]
        if s is Step.B4_ASSETS:
            out = [] if self.assets_confirmed else ["assets_confirmed"]
            for i, r in enumerate(self.references):
                if r.screenshot_path and not r.url and not r.url_recommended:
                    out.append(f"reference[{i}]:recommend_url")
            return out
        if s is Step.B5_DESIGN_MD:
            return [] if self.design_md else ["design_md"]
        if s is Step.B6_PLAN:
            return [n for n, v in (("product_md", self.product_md), ("plan_md", self.plan_md)) if not v]
        if s is Step.B7_APPROVAL:
            return [] if self.plan_approved else ["user_approval"]
        if s is Step.B8_DESIGN:
            out = [] if self.design_system_installed else ["design_system"]
            return out + ([] if self.sections_planned else ["sections_planned"])
        if s is Step.B9_DEVELOP:
            # Pipelined per section (decision 3): Dev writes N while Design measures N-1.
            planned = set(self.sections_planned)
            out = [f"write:{x}" for x in self.sections_planned if x not in self.sections_done]
            out += [f"check:{x}" for x in self.sections_planned if x not in self.sections_checked]
            return out if planned else ["sections_planned"]
        if s is Step.B10_INTEGRATE:
            return [] if self.integrated else ["integrated"]
        if s is Step.B11_MASTER_QA:
            return [] if (self.qa_passed or self.escalated_to_user) else ["qa_passed"]
        return []  # B12 is terminal for the page; loops are explicit actions

    def can_advance(self) -> bool:
        return not self.missing_for_exit()

    def advance(self) -> Step:
        if self.step is Step.B7_APPROVAL:
            raise GateError("B7 can only be passed by approve_plan(), never by advance().")
        if self.step is Step.B12_HANDOVER:
            raise GateError("B12 ends via upgrade_current_page() or build_next_page().")
        missing = self.missing_for_exit()
        if missing:
            raise GateError(f"Cannot leave {self.step}: missing {missing}")
        self.step = ORDER[ORDER.index(self.step) + 1]
        return self.step

    # ------------------------------------------------------- explicit actions

    def reset_clone_source(self) -> Step:
        """Clone mode: the link could not be read; ask for it again at B1."""
        if self.step is not Step.B2_SITEMAP or self.mode is not BuildMode.CLONE:
            raise GateError("reset_clone_source() only valid at B2 in Clone mode")
        self.clone = None
        self.step = Step.B1_READ_PROMPT
        return self.step

    def approve_plan(self) -> Step:
        """Only callable from a user action in the Studio / WebSocket."""
        if self.step is not Step.B7_APPROVAL:
            raise GateError(f"approve_plan() only valid at B7, current step is {self.step}")
        if not (self.design_md and self.product_md and self.plan_md):
            raise GateError("Cannot approve: DESIGN.md / PRODUCT.md / PLAN.md incomplete")
        self.plan_approved = True
        self.step = Step.B8_DESIGN
        return self.step

    def request_plan_changes(self) -> Step:
        """B7 -> B5: user wants changes, documents are regenerated."""
        if self.step is not Step.B7_APPROVAL:
            raise GateError("request_plan_changes() only valid at B7")
        self.plan_approved = False
        self.design_md = self.product_md = self.plan_md = self.tokens_css = None
        self.step = Step.B5_DESIGN_MD
        return self.step

    def record_qa_failure(self, failures: list[str]) -> Step:
        """B11 FAIL: loop back to B8 until MAX_HEAL_ITERATIONS, then escalate."""
        if self.step is not Step.B11_MASTER_QA:
            raise GateError("record_qa_failure() only valid at B11")
        self.heal_history.append(HealAttempt(iteration=len(self.heal_history) + 1, failures=failures))
        if len(self.heal_history) >= MAX_HEAL_ITERATIONS:
            self.escalated_to_user = True
            return self.step
        self.sections_done = []
        self.sections_checked = []
        self.integrated = False
        self.build_passes = []
        self.step = Step.B8_DESIGN
        return self.step

    def escalate_qa(self, failures: list[str]) -> Step:
        """B11 FAIL with nothing the departments can patch: hand over to the user now
        instead of re-running an identical build."""
        if self.step is not Step.B11_MASTER_QA:
            raise GateError("escalate_qa() only valid at B11")
        self.heal_history.append(HealAttempt(iteration=len(self.heal_history) + 1, failures=failures))
        self.escalated_to_user = True
        return self.step

    def refine_current_page(self) -> Step:
        """B12 'Tinh chỉnh trang này' with feedback: documents are regenerated (B5) and the
        changed plan must be approved again at B7 before anything is rebuilt."""
        if self.step is not Step.B12_HANDOVER:
            raise GateError("refine_current_page() only valid at B12")
        self.plan_approved = False
        self.design_md = self.product_md = self.plan_md = self.tokens_css = None
        self._reset_build()
        self.step = Step.B5_DESIGN_MD
        return self.step

    def upgrade_current_page(self) -> Step:
        if self.step is not Step.B12_HANDOVER:
            raise GateError("upgrade_current_page() only valid at B12")
        self._reset_build()
        self.step = Step.B8_DESIGN
        return self.step

    def build_next_page(self, slug: str) -> Step:
        """B12 -> B6: DESIGN.md is kept so every page shares one design system."""
        if self.step is not Step.B12_HANDOVER:
            raise GateError("build_next_page() only valid at B12")
        pages = {p.slug: p for p in self.sitemap}
        if slug not in pages:
            raise GateError(f"Unknown page {slug!r}")
        if self.selected_page in pages:
            pages[self.selected_page].status = PageStatus.DONE
        pages[slug].status = PageStatus.BUILDING
        self.selected_page = slug
        self.plan_md = None
        self.plan_approved = False
        self._reset_build()
        self.step = Step.B6_PLAN
        return self.step

    def _reset_build(self) -> None:
        self.build_error = None
        self.preview_url = None
        self.motion_effects = []
        self.design_system_installed = False
        self.sections_planned = []
        self.sections_checked = []
        self.token_changes = []
        self.open_findings = []
        self.sections_done = []
        self.integrated = False
        self.build_passes = []
        self.qa_passed = False
        self.heal_history = []
        self.escalated_to_user = False
        self.qa_summary = None
        self.qa_failures = []
        self.heal_rules = []
        self.heal_contrast = []
        self.design_score = None
        self.design_critique = []
        self.clone_fidelity = None
        self.clone_fidelity_notes = []
        self.clone_compare = None
        self.compare_rounds = 0
        self.factory_log = []


class GateError(RuntimeError):
    """Raised when an action would skip a hard gate."""


# ------------------------------------------------------------- tool gating

READ_ONLY_TOOLS = frozenset({"read_knowledge_base", "ask_user"})
DOC_TOOLS = frozenset({"write_design_md", "write_product_md", "write_plan_md"})
CODEGEN_TOOLS = frozenset({"write_workspace_file", "run_dev_server"})
BROWSER_TOOLS = frozenset({"swarm_cursor", "browser_measure", "write_tokens"})
QA_TOOLS = frozenset({"qa_hover", "qa_click", "qa_scroll", "qa_viewport", "qa_report"})
MCP_TOOLS = frozenset({"mcp_motion"})  # B8.1 Motion & 2D/3D MCP Specialist (Design department)

ALLOWED_TOOLS: dict[Step, frozenset[str]] = {
    Step.B1_READ_PROMPT: READ_ONLY_TOOLS,
    Step.B2_SITEMAP: READ_ONLY_TOOLS | {"scrape_style_dna"},  # Clone mode reads the reference page here
    Step.B3_ELICITATION: READ_ONLY_TOOLS,
    Step.B4_ASSETS: READ_ONLY_TOOLS | {"save_asset", "scrape_style_dna"},
    Step.B5_DESIGN_MD: READ_ONLY_TOOLS | {"scrape_style_dna", "write_design_md"},
    Step.B6_PLAN: READ_ONLY_TOOLS | DOC_TOOLS,
    Step.B7_APPROVAL: READ_ONLY_TOOLS,
    Step.B8_DESIGN: READ_ONLY_TOOLS | BROWSER_TOOLS,
    Step.B9_DEVELOP: READ_ONLY_TOOLS | CODEGEN_TOOLS | BROWSER_TOOLS | MCP_TOOLS,  # both departments, pipelined
    Step.B10_INTEGRATE: READ_ONLY_TOOLS | CODEGEN_TOOLS | BROWSER_TOOLS,
    Step.B11_MASTER_QA: READ_ONLY_TOOLS | QA_TOOLS,
    Step.B12_HANDOVER: READ_ONLY_TOOLS,
}


def tools_for(step: Step) -> frozenset[str]:
    return ALLOWED_TOOLS[step]
