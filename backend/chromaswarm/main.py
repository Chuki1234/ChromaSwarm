"""FastAPI + WebSocket server driving the LangGraph pipeline.

Client -> server (JSON):
  {"type": "answer", "value": <str | object>}   # resumes the pending interrupt
Server -> client:
  {"type": "state", "state": {...}, "question": {...} | null, "notice": str | null,
   "missing": [...], "tools": [...], "clarity_score": float, "finished": bool}
  {"type": "error", "message": "..."}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from chromaswarm.playwright_engine.style_dna_scraper import scrape_url
from chromaswarm.state_machine.graph import Deps, PipelineRunner
from chromaswarm.state_machine.pipeline_state import GateError, tools_for

log = logging.getLogger(__name__)

app = FastAPI(title="ChromaSwarm Orchestrator", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

runner = PipelineRunner(Deps(scrape=scrape_url))


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
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    await ws.send_json(to_message(await runner.start(session_id)))
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "answer":
                await ws.send_json({"type": "error", "message": f"Unknown message type {msg.get('type')!r}"})
                continue
            try:
                snap = await runner.answer(session_id, msg.get("value"))
            except GateError as e:
                await ws.send_json({"type": "error", "message": str(e)})
                continue
            except Exception as e:  # keep the socket alive; surface the problem
                log.exception("pipeline error")
                await ws.send_json({"type": "error", "message": f"Lỗi hệ thống: {e}"})
                continue
            await ws.send_json(to_message(snap))
    except WebSocketDisconnect:
        return
