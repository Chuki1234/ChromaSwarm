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
        if "." not in v.split("//", 1)[1].split("/", 1)[0]:
            raise ValueError(f"not a web URL: {v}")
        return v


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
    sections_done: list[str] = Field(default_factory=list)
    integrated: bool = False

    # B11
    qa_passed: bool = False
    heal_history: list[HealAttempt] = Field(default_factory=list)
    escalated_to_user: bool = False

    # ------------------------------------------------------------------ gates

    def missing_for_exit(self) -> list[str]:
        """Exit criteria of the current step. Empty list == may advance."""
        s = self.step
        if s is Step.B1_READ_PROMPT:
            return [n for n, v in (("raw_prompt", self.raw_prompt), ("domain", self.domain)) if not v]
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
        # B8 and B9 run pipelined per section (Phase 5); in this linear view
        # both steps only require that at least one section has been built.
        if s in (Step.B8_DESIGN, Step.B9_DEVELOP):
            return [] if self.sections_done else ["sections"]
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
        self.integrated = False
        self.step = Step.B8_DESIGN
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
        self.sections_done = []
        self.integrated = False
        self.qa_passed = False
        self.heal_history = []
        self.escalated_to_user = False


class GateError(RuntimeError):
    """Raised when an action would skip a hard gate."""


# ------------------------------------------------------------- tool gating

READ_ONLY_TOOLS = frozenset({"read_knowledge_base", "ask_user"})
DOC_TOOLS = frozenset({"write_design_md", "write_product_md", "write_plan_md"})
CODEGEN_TOOLS = frozenset({"write_workspace_file", "run_dev_server"})
BROWSER_TOOLS = frozenset({"swarm_cursor", "browser_measure", "write_tokens"})
QA_TOOLS = frozenset({"qa_hover", "qa_click", "qa_scroll", "qa_viewport", "qa_report"})

ALLOWED_TOOLS: dict[Step, frozenset[str]] = {
    Step.B1_READ_PROMPT: READ_ONLY_TOOLS,
    Step.B2_SITEMAP: READ_ONLY_TOOLS,
    Step.B3_ELICITATION: READ_ONLY_TOOLS,
    Step.B4_ASSETS: READ_ONLY_TOOLS | {"save_asset", "scrape_style_dna"},
    Step.B5_DESIGN_MD: READ_ONLY_TOOLS | {"scrape_style_dna", "write_design_md"},
    Step.B6_PLAN: READ_ONLY_TOOLS | DOC_TOOLS,
    Step.B7_APPROVAL: READ_ONLY_TOOLS,
    Step.B8_DESIGN: READ_ONLY_TOOLS | BROWSER_TOOLS,
    Step.B9_DEVELOP: READ_ONLY_TOOLS | CODEGEN_TOOLS,
    Step.B10_INTEGRATE: READ_ONLY_TOOLS | CODEGEN_TOOLS | BROWSER_TOOLS,
    Step.B11_MASTER_QA: READ_ONLY_TOOLS | QA_TOOLS,
    Step.B12_HANDOVER: READ_ONLY_TOOLS,
}


def tools_for(step: Step) -> frozenset[str]:
    return ALLOWED_TOOLS[step]
