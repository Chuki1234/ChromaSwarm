# ChromaSwarm

12-step multi-agent system that helps non-experts build professional frontend
pages one page at a time. Full spec: `docs/00_HANDOFF_CLAUDE.md` and
`docs/01..04_*.md`. Runtime knowledge base for agents: `knowledge-base/`.

## Layout

- `backend/` — Python 3.11+ orchestrator (`uv`, FastAPI + WebSocket, Pydantic, LangGraph, Anthropic SDK, Playwright).
  - `chromaswarm/state_machine/pipeline_state.py` — B1→B12 state, exit criteria, per-step tool grants.
  - `chromaswarm/state_machine/graph.py` — LangGraph B1–B7, one `interrupt()` per node pass, single router on `pipeline.step`; `PipelineRunner` is the WebSocket-facing API.
  - `chromaswarm/agents/consultant.py` — `ConsultantAgent` interface + `RuleBasedConsultant` (no-LLM baseline; Claude agent plugs in at Phase 3).
  - `chromaswarm/agents/planner.py` — section blueprints, PRODUCT.md / PLAN.md renderers.
  - `chromaswarm/engines/` — deterministic, no LLM: `color` (OKLCH, WCAG, APCA), `palette` (60-30-10), `typography`, `spacing` (8pt), `presets`, `style_dna` (analysis), `design_spec` (DESIGN.md + tokens.css).
  - `chromaswarm/playwright_engine/style_dna_scraper.py` — returns aggregate style stats only (no DOM/text).
  - Generated artifacts go to `workspaces/<session>/artifacts/`.
- `studio/` — Next.js 16 control UI (chat, step tracker, B7 approval). Port 3000.
- `workspaces/<project>/` — generated target apps (port 3001+). Never generated inside `studio/`.
- `knowledge-base/` — `FRONTEND_STANDARDS.md` + templates for DESIGN/PRODUCT/PLAN.md.

## Commands

```bash
cd backend && uv run pytest -q   # needs `uv run playwright install chromium` once
cd backend && uv run uvicorn chromaswarm.main:app --port 8100 --reload
cd studio && npm run dev
```

The backend uses port **8100** (8000 is taken by another local service).

## Decisions (do not re-litigate)

1. Orchestrator is Python, not TypeScript (doc 04 Part 4 is superseded).
2. Gates are enforced in code: B1–B7 agents get no code-writing tools (`ALLOWED_TOOLS`); Clarity Score = filled pillars / 5; B7 passes only via an explicit user `approve_plan`.
3. B8/B9 run pipelined per section (Dev writes section N while Design measures N−1), not truly simultaneously.
4. Design-department changes are written to the workspace token file, never only applied via CSSOM.
5. B11 self-healing loop is capped at `MAX_HEAL_ITERATIONS = 3`, then escalates to the user.
6. Swarm Rebuild is inspiration only; the overlay is written from scratch.
7. Every number in DESIGN.md comes from the engines; an LLM may only write the philosophy prose and pick presets.
8. Unclear answers are re-asked (`interpret()` returns None) — never filled in by the agent.
9. Deviations from FRONTEND_STANDARDS.md, chosen to keep APCA / 8pt checks passing: dark-mode text-secondary 78% and text-muted 68% (spec: 72% / 52%); dense section padding 48px (spec: 40–56px, off-grid); mobile type ratio = 1 + 0.6·(r−1).
10. Studio UI itself follows `FRONTEND_STANDARDS.md` (OKLCH tokens in `globals.css`, 8pt spacing, no AI-slop patterns).

## Next.js note

`studio/` runs Next.js 16 — read `studio/node_modules/next/dist/docs/` before using unfamiliar APIs. Run `npx next typegen` before `tsc` (provides `LayoutProps`).

## Roadmap

Phase 0 scaffold ✅ · 1 LangGraph wiring + interrupts ✅ · 2 deterministic engines ✅ · 3 Claude-backed B1–B7 agents · 4 swarm overlay · 5 B8–B10 · 6 B11 Master QA · 7 B12 + B8.1 MCP.
