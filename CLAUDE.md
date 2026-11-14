# ChromaSwarm

12-step multi-agent system that helps non-experts build professional frontend
pages one page at a time. Full spec: `docs/00_HANDOFF_CLAUDE.md` and
`docs/01..04_*.md`. Runtime knowledge base for agents: `knowledge-base/`.

## Layout

- `backend/` — Python 3.11+ orchestrator (`uv`, FastAPI + WebSocket, Pydantic, LangGraph, Anthropic SDK, Playwright).
  - `chromaswarm/state_machine/pipeline_state.py` — B1→B12 state, exit criteria, per-step tool grants.
  - `chromaswarm/state_machine/graph.py` — LangGraph B1–B7, one `interrupt()` per node pass, single router on `pipeline.step`; `PipelineRunner` is the WebSocket-facing API.
  - `chromaswarm/agents/consultant.py` — `ConsultantAgent` interface + `RuleBasedConsultant` (no-LLM baseline).
  - `chromaswarm/agents/llm.py` + `llm_consultant.py` — provider-neutral LLM layer, configured for **OpenRouter** (one key, any model). Three roles in `backend/.env`: `CHROMASWARM_LLM_MODEL` (text: B1–B7 interpretation, B7 feedback, B5 prose; default `qwen/qwen3.8-flash`), `_MODEL_CODE` (B9, default `qwen/qwen3-coder-next`), `_MODEL_VISION` (Clone mode from images; must accept images). The public OpenRouter catalogue is read once so each model gets the right request (reasoning off where allowed, lowest effort where mandatory; JSON mode only where supported, retried without it otherwise). `LLMConsultant` output is validated against closed value sets, prose is rejected unless every number is in `philosophy_facts`, and provider errors fall back to rules. `uv run python -m chromaswarm.agents.llm` validates the model IDs and the live connection. Model unset or placeholder key = rule-based.
  - `chromaswarm/agents/planner.py` — section blueprints, PRODUCT.md / PLAN.md renderers.
  - **Two modes, chosen at B1** (`BuildMode`):
    - *Creative* — real chat (`agents/chat.py`, WS message `{"type":"chat"}`): each message becomes `answer` (passed to the graph like a button, all validation applies), `ask` (Chroma replies from the session's DESIGN.md + standards ch.1–3; the pending question stays) or `revise` (B3 only: change an earlier pillar). Code-level limits in `chat.guard`: never approves B7, choice answers must be offered values, free-text answers keep the user's own words. No LLM → messages go straight through as answers.
    - *Clone* — B1 asks link + description + "this site is mine" (`clone_source`). B2 runs `clone/reader.py` (Playwright): the page's top-level sections classified onto buildable structures (in its own order), Style DNA → pillars, fonts kept only if in `VIETNAMESE_FONTS`, and — **only when the user confirmed ownership** — per-section text and image URLs (otherwise the JS returns no content). B3/B4 fill themselves from the reference (scope = description); B7 approval still required. Sitemap page slug `clone`; `planner.page_sections()` returns the reference's sections for it. Owned copy is mapped by section kind in `content.owned_clone_copy`. Pages are opened with `open_settled` (wait for `load`, ≤8s for network idle, then scroll through once for lazy / scroll-revealed content). The reader expands tall wrapper blocks and two-column layouts (content + sidebar: the side column's h1 box becomes the hero), keeps navigation, attaches loose headings to the next block in the same column, merges runs of picture-only blocks into one `gallery` section, counts any visual media (img/svg/video/canvas), and recognises feature showcases, testimonials (incl. CSS-drawn quotes / role lines / round-avatar cards), text-card rows, logo strips, list rows (entry + meta: posts with dates, work history) and closing CTAs. Tall `<header>`s (<360px) count as the navbar; fixed-position boxes narrower than half the page (promo widgets, chat bubbles) are skipped. A hero with no visual becomes `hero-text` (email signup when the reference had an input). The page's total content span is measured; under 1100px it is kept as `CloneSource.content_width` → `--container-max` (+ 2 gutters) in DESIGN.md / tokens.css. Sample copy is per domain and allocated page-wide (`content.copy_for`), so sections never repeat each other.
  - `chromaswarm/engines/` — deterministic, no LLM: `color` (OKLCH, WCAG, APCA), `palette` (60-30-10), `typography`, `spacing` (8pt), `presets`, `style_dna` (analysis), `design_spec` (DESIGN.md + tokens.css).
  - `chromaswarm/playwright_engine/style_dna_scraper.py` — returns aggregate style stats only (no DOM/text).
  - `chromaswarm/playwright_engine/swarm_overlay.js` — injected overlay (shadow DOM, `pointer-events:none`, re-attaches after re-renders): 4 Design cursors + rulers/box-model bands, 2.2x Master cursor + HUD + red flags, `handover()` removes it. It only reads the DOM.
  - `chromaswarm/playwright_engine/swarm.py` — `SwarmOverlay` (Python driver, event sink for streaming) and `design_pass()`: per section Layout → Color → Typography; verdicts (8pt grid, mobile gutter ≥16px, WCAG/APCA, 45–72ch, type scale) computed in Python with the engines. Demo: `uv run python -m chromaswarm.playwright_engine.demo [url]` (fixture page with 3 seeded defects).
  - `chromaswarm/developer/` — B9 Developer (rule-based baseline): `nextjs.py` renders one TSX component per PLAN.md section structure (real interactions, `data-swarm-*` on every control, styling only via tokens) + workspace scaffold; `content.py` builds page copy from the user's answers/assets; `workspace.py` writes files tool-gated per step and runs `next dev` (port 3001+, own process group).
  - `chromaswarm/design/dept.py` — B8 Design repairs: contrast → shift the colour token's OKLCH lightness; off-grid spacing → snap the spacing token. Written to the workspace `app/tokens.css` (decision 4); the rest goes to `open_findings`.
  - `chromaswarm/build/runtime.py` — `LocalBuildRuntime` owns per-session workspace, dev server, Playwright page + overlay (not checkpointed). B8 installs tokens; each B9 graph tick = Dev writes section N ∥ Design checks N−1; B10 reloads, checks section order + console errors. `CHROMASWARM_BUILD=0` stops after B7, `CHROMASWARM_HEADED=0` hides the browser.
  - `chromaswarm/qa/` — B11 Master QA: `qa_probe.js` (read-only DOM measurements) + `master.py` (4 tests of standards ch.5: interaction sweep incl. hover/click/console/focus-visible, scroll & sticky, 1440/1024/768/375 overflow/collision/margins/tap targets, DESIGN.md fonts + contrast + automatable anti-slop rules). Each failure carries a `heal` CSS rule (Developer → `app/heal.css` on the next B9) or a colour reading (Design → `tokens.css`). Loop: FAIL → B8 (tokens kept) → B11, max 3; nothing patchable → escalate at once. Fixture with one seeded defect per rule: `qa/fixtures/qa_defects.html`.
  - `chromaswarm/mcp_motion/` — B8.1: a real MCP server (`server.py`, stdio, tools `list_effects` / `build_effect`) returning dependency-free CSS effects (reveal, scroll-driven parallax, stagger; reduced-motion safe, page-scoped); `client.py` is what the Motion agent uses. `CHROMASWARM_MOTION_MCP="<cmd>"` swaps in an external server with the same tool contract. Motion failures never stop a build.
  - B12 (`graph.b12`): overlay removed + in-page handover bar (exposed binding → `main.browser_choice`), Studio card: next sitemap page (→ B6, DESIGN.md + tokens kept, new route `/<slug>`, earlier pages' headers re-rendered with the new link), refine with feedback (→ B5, re-approval at B7), or finish. One lock per session serialises Studio and browser answers.
  - Generated artifacts go to `workspaces/<session>/artifacts/`, the target app to `workspaces/<session>/app/`.
- `studio/` — Next.js 16 control UI (chat, step tracker, B7 approval). Port 3000.
- `workspaces/<project>/` — generated target apps (port 3001+). Never generated inside `studio/`.
- `knowledge-base/` — `FRONTEND_STANDARDS.md` + templates for DESIGN/PRODUCT/PLAN.md.

## Commands

```bash
cd backend && uv run pytest -q   # offline; needs `uv run playwright install chromium` once
CHROMASWARM_E2E=1 uv run pytest -q tests/test_build.py   # + real npm/next dev/Chromium build (~35s)
cp backend/.env.example backend/.env   # then set the LLM key, or empty the model for rule-based
cd backend && uv run uvicorn chromaswarm.main:app --port 8100 --reload
cd studio && npm run dev
```

The backend uses port **8100** (8000 is taken by another local service).

## Decisions (do not re-litigate)

1. Orchestrator is Python, not TypeScript (doc 04 Part 4 is superseded).
2. Gates are enforced in code: B1–B7 agents get no code-writing tools (`ALLOWED_TOOLS`); Clarity Score = filled pillars / 5; B7 passes only via an explicit user `approve_plan`.
3. B8/B9 run pipelined per section (Dev writes section N while Design measures N−1), not truly simultaneously. B8 = Design installs tokens only; B9 grants both departments' tools because they work pipelined.
4. Design-department changes are written to the workspace token file, never only applied via CSSOM.
5. B11 self-healing loop is capped at `MAX_HEAL_ITERATIONS = 3`, then escalates to the user.
6. Swarm Rebuild is inspiration only; the overlay is written from scratch.
7. Every number in DESIGN.md comes from the engines; an LLM may only write the philosophy prose and pick presets.
8. Unclear answers are re-asked (`interpret()` returns None) — never filled in by the agent.
9. Deviations from FRONTEND_STANDARDS.md, chosen to keep APCA / 8pt checks passing: dark-mode text-secondary 78% and text-muted 68% (spec: 72% / 52%); dense section padding 48px (spec: 40–56px, off-grid); mobile type ratio = 1 + 0.6·(r−1). Fonts: Instrument Serif → Playfair Display (editorial-luxury), Outfit/DM Sans → Lexend/Be Vietnam Pro (warm-organic), because the originals have no Vietnamese subset; `VIETNAMESE_FONTS` + a test guard every preset font.
10. Studio UI itself follows `FRONTEND_STANDARDS.md` (OKLCH tokens in `globals.css`, 8pt spacing, no AI-slop patterns).
11. Anti-cloning (standards §2.4) applies to **Creative mode only**. **Clone mode** (§2.5) may rebuild the reference identically: structure clone by default (section order and layout identical, the user's own text/images); **Clone 100%** (text, brand, logo, images too) only when the user ticks “Đây là trang web của tôi”. Ownership is never inferred, and without the tick the reader returns no content at all. Clone pages still pass B7 approval, the chapter-2 checks and B11.

## Next.js note

`studio/` runs Next.js 16 — read `studio/node_modules/next/dist/docs/` before using unfamiliar APIs. Run `npx next typegen` before `tsc` (provides `LayoutProps`).

## Roadmap

Phase 0 scaffold ✅ · 1 LangGraph wiring + interrupts ✅ · 2 deterministic engines ✅ · 3 LLM-backed B1–B7 agents ✅ (B1–B4 interpretation, B5 philosophy prose, B7 feedback → pillar changes; rule-based fallback for each; verified live via OpenRouter with `qwen/qwen3.8-flash`) · 4 swarm overlay ✅ (not yet driven by the pipeline: B8 wiring comes with Phase 5) · 5 B8–B10 ✅ (rule-based codegen; LLM codegen pluggable via `render_section`) · 6 B11 Master QA ✅ · 7 B12 + B8.1 MCP ✅. Not yet done: LLM-backed codegen/copy (needs an API key), real product assets instead of tonal placeholders.
