"""FastAPI + WebSocket server driving the LangGraph pipeline.

Client -> server (JSON):
  {"type": "answer", "value": <str | object>}   # resumes the pending interrupt
Server -> client:
  {"type": "state", "state": {...}, "question": {...} | null, "notice": str | null,
   "missing": [...], "tools": [...], "clarity_score": float, "finished": bool}
  {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from chromaswarm.agents.chat import LLMChat, RuleChat
from chromaswarm.agents.consultant import RuleBasedConsultant
from chromaswarm.agents.llm import LLMConfig, OpenAICompatChat
from chromaswarm.agents.llm_consultant import LLMConsultant
from chromaswarm.build.runtime import LocalBuildRuntime
from chromaswarm.playwright_engine.style_dna_scraper import scrape_url
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import BuildMode, GateError, Step, tools_for

BUILD_STEPS = {Step.B8_DESIGN, Step.B9_DEVELOP, Step.B10_INTEGRATE, Step.B11_MASTER_QA}

log = logging.getLogger(__name__)

# backend/.env (optional) - real environment variables take precedence
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

WORKSPACES = Path(__file__).resolve().parents[2] / "workspaces"


def build_runtime(env: dict[str, str] | None = None) -> LocalBuildRuntime | None:
    """B8-B10 run by default; CHROMASWARM_BUILD=0 stops after B7, CHROMASWARM_HEADED=0 hides the browser."""
    env = dict(os.environ if env is None else env)
    if env.get("CHROMASWARM_BUILD", "1") == "0":
        return None
    return LocalBuildRuntime(WORKSPACES, headed=env.get("CHROMASWARM_HEADED", "1") != "0")


build = build_runtime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if build:
        await build.close_all()  # never leave `next dev` processes behind


app = FastAPI(title="ChromaSwarm Orchestrator", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def build_consultant(env: dict[str, str] | None = None):
    """LLM consultant when CHROMASWARM_LLM_MODEL is set, otherwise the rule-based baseline."""
    cfg = LLMConfig.from_env(env)
    if cfg is None:
        return RuleBasedConsultant()
    return LLMConsultant(OpenAICompatChat(cfg))


def build_chat(env: dict[str, str] | None = None):
    """Creative-mode chat agent: LLM when configured (text role), otherwise answers go straight through."""
    cfg = LLMConfig.from_env(env)
    if cfg is None:
        return RuleChat()
    return LLMChat(OpenAICompatChat(cfg.for_role("text")))


consultant = build_consultant()
chat_agent = build_chat()
log.warning("ChromaSwarm consultant: %s", getattr(consultant, "name", "rule-based"))
runner = PipelineRunner(Deps(consultant=consultant, scrape=scrape_url, build=build))


def to_message(snap: dict) -> dict:
    p = snap["pipeline"]
    return {
        "type": "state",
        "state": p.model_dump(mode="json"),
        "question": snap["question"],
        "notice": snap["notice"],
        "finished": snap["finished"],
        "missing": p.missing_for_exit(),
        "tools": sorted(tools_for(p.step)),
        "clarity_score": p.pillars.clarity_score,
        "running": snap["question"] is None and not snap["finished"],
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "consultant": getattr(consultant, "name", "rule-based"),
            "chat": getattr(chat_agent, "name", "rule-based"), "build": build is not None}


# Every open Studio tab of a session, and one lock per session so an answer from the Studio
# and a B12 choice clicked in the browser window can never resume the graph at the same time.
CLIENTS: dict[str, set[WebSocket]] = defaultdict(set)
LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def broadcast(session_id: str, message: dict) -> None:
    for client in list(CLIENTS[session_id]):
        with contextlib.suppress(Exception):
            await client.send_json(message)


async def resume(session_id: str, value) -> dict:
    """Resume the pipeline with an answer and stream build progress to every tab of the session."""
    async def progress(snap: dict) -> None:
        if snap["pipeline"].step in BUILD_STEPS:  # only long-running build work streams
            await broadcast(session_id, to_message(snap))

    async with LOCKS[session_id]:
        snap = await runner.answer(session_id, value, on_progress=progress)
    await broadcast(session_id, to_message(snap))
    return snap


CHATS: dict[str, list[dict]] = defaultdict(list)  # Creative-mode transcript per session (memory only)


def design_summary(p) -> str:
    if p.design_md and "## 2." in p.design_md:
        return p.design_md[: p.design_md.index("## 2.")]
    return ""


async def chat(session_id: str, ws: WebSocket, text: str) -> None:
    """Creative mode: one free message -> answer / ask / revise (see agents/chat.py)."""
    text = (text or "").strip()
    if not text:
        return
    snap = await runner.snapshot(session_id)
    p = snap["pipeline"]
    if p.mode is BuildMode.CLONE:
        await ws.send_json({"type": "error", "message": "Clone mode dùng biểu mẫu link + mô tả; chat dành cho Creative mode."})
        return
    history = CHATS[session_id]
    history.append({"role": "user", "text": text})
    await broadcast(session_id, {"type": "chat", "role": "user", "text": text})
    turn = await asyncio.to_thread(chat_agent.respond, p.step.value, snap["question"],
                                   p.pillars.model_dump(), design_summary(p), history, text)
    if turn.reply:
        history.append({"role": "assistant", "text": turn.reply})
        await broadcast(session_id, {"type": "chat", "role": "assistant", "text": turn.reply, "intent": turn.intent})
    del history[:-40]
    if turn.intent in ("answer", "revise"):
        await resume(session_id, turn.answer)


async def browser_choice(session_id: str, value: dict) -> None:
    """B12 button clicked inside the handed-over browser window."""
    snap = await runner.snapshot(session_id)
    question = snap["question"] or {}
    if question.get("kind") != "handover":
        return
    if value.get("action") == "refine":  # feedback is typed in the Studio, not in the page
        await broadcast(session_id, {**to_message(snap),
                                     "notice": "Bạn ghi điều muốn tinh chỉnh vào ô góp ý trong Studio rồi bấm “Tinh chỉnh”."})
        return
    try:
        await resume(session_id, value)
    except Exception as e:
        log.exception("browser choice failed")
        await broadcast(session_id, {"type": "error", "message": f"Lỗi hệ thống: {e}"})


if build:
    build.on_choice = browser_choice


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    CLIENTS[session_id].add(ws)
    try:
        await ws.send_json(to_message(await runner.start(session_id)))  # inside: the tab may close at once
        while True:
            msg = await ws.receive_json()
            if msg.get("type") not in ("answer", "chat"):
                await ws.send_json({"type": "error", "message": f"Unknown message type {msg.get('type')!r}"})
                continue
            try:
                if msg["type"] == "chat":
                    await chat(session_id, ws, str(msg.get("text") or ""))
                else:
                    await resume(session_id, msg.get("value"))
            except GateError as e:
                await ws.send_json({"type": "error", "message": str(e)})
            except Exception as e:  # keep the socket alive; surface the problem
                log.exception("pipeline error")
                await ws.send_json({"type": "error", "message": f"Lỗi hệ thống: {e}"})
    except WebSocketDisconnect:
        return
    finally:
        CLIENTS[session_id].discard(ws)
