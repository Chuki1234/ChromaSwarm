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
import json
import logging
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

from chromaswarm.clone.checkpoints import SupabaseCloneSaver
from chromaswarm.clone.history import CloneHistory, resumable
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from chromaswarm.agents.chat import LLMChat, RuleChat
from chromaswarm.agents.consultant import RuleBasedConsultant
from chromaswarm.agents.llm import LLMConfig, OpenAICompatChat
from chromaswarm.agents.llm_consultant import LLMConsultant
from chromaswarm.build.runtime import LocalBuildRuntime
from chromaswarm.agents.brief import build_brief_reader
from chromaswarm.developer.copywriter import build_copywriter
from chromaswarm.developer.photo_bot import build_photo_bot
from chromaswarm.design.reference_vision import build_screenshot_reader
from chromaswarm.developer.stylist import build_stylist
from chromaswarm.qa.section_eye import build_section_eye
from chromaswarm.developer import publish, uploads
from chromaswarm.developer.template import app_dir_for, template_zip
from chromaswarm.clone.preview import page_preview
from chromaswarm.playwright_engine.style_dna_scraper import scrape_url
from chromaswarm.state_machine.graph import SERDE, Deps, PipelineRunner, handover_options
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
    await runner.close()


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
def state_db(env: dict[str, str] | None = None) -> Path | None:
    """Where sessions are saved (SQLite) so they survive a restart; CHROMASWARM_STATE_DB="" keeps them in memory."""
    env = dict(os.environ if env is None else env)
    value = env.get("CHROMASWARM_STATE_DB")
    if value is None:
        return WORKSPACES / ".state" / "sessions.sqlite"
    return Path(value) if value.strip() else None


DEPS = Deps(consultant=consultant, scrape=scrape_url, build=build, copywriter=build_copywriter(), photo_bot=build_photo_bot(),
                              brief_reader=build_brief_reader(), screenshot_reader=build_screenshot_reader(),
                              stylist=build_stylist(), section_eye=build_section_eye(),
                              compose=os.environ.get("CHROMASWARM_COMPOSE") == "1")
# Clone threads' graph state lives in Supabase when it is set up (clone/checkpoints.py): a restart picks a
# Clone session up exactly where it stopped, Creative threads stay in memory. Without Supabase settings every
# session is saved to SQLite (state_db).
history = CloneHistory()
runner = (PipelineRunner(DEPS, checkpointer=SupabaseCloneSaver(serde=SERDE, store=history)) if history.enabled
          else PipelineRunner(DEPS, db_path=state_db()))


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


@app.get("/clone/preview")
async def clone_preview(url: str) -> dict:
    """First-screen screenshot + title of a reference page, shown under the link before it is read."""
    from chromaswarm.state_machine.pipeline_state import Reference
    try:
        target = Reference.model_validate({"url": url}).url
    except ValueError:
        raise HTTPException(status_code=422, detail="Link chưa hợp lệ.") from None
    try:
        return (await page_preview(str(target))).model_dump()
    except Exception as e:  # noqa: BLE001 — unreachable / blocked page: the form still works without a preview
        raise HTTPException(status_code=502, detail=f"Không mở được trang: {str(e)[:120]}") from None


@app.get("/sessions/{session_id}/template.zip")
def download_template(session_id: str) -> Response:
    """The built page as a ready-to-fill template (content/ for words, public/images/ for photos)."""
    app_dir = app_dir_for(build.root, session_id) if build else None
    if app_dir is None:
        raise HTTPException(status_code=404, detail="Chưa có trang nào được dựng cho phiên này.")
    return Response(template_zip(app_dir), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="chromaswarm-{session_id}.zip"'})


_SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_SAFE_SHOT = re.compile(r"^[a-z0-9-]{1,80}-(ref|clone)\.jpg$")


@app.get("/sessions/{session_id}/compare/{name}")
def compare_shot(session_id: str, name: str) -> Response:
    """Clone B11 1:1 acceptance: one section of the reference or of the rebuild (side by side in the Studio)."""
    if not _SAFE_SESSION.match(session_id) or not _SAFE_SHOT.match(name):
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    path = WORKSPACES / session_id / "artifacts" / "compare" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/sessions/{session_id}/publish/{target}")
async def publish_site(session_id: str, target: str, body: dict | None = None) -> dict:
    """After handover: the built app on Vercel (live link) or GitHub (private repository), with the
    user's own token from backend/.env. Only a user click in the Studio calls this."""
    app_dir = app_dir_for(build.root, session_id) if build else None
    if app_dir is None:
        raise HTTPException(status_code=404, detail="Chưa có trang nào được dựng cho phiên này.")
    snap = await runner.snapshot(session_id)
    p = snap["pipeline"]
    if not p or not (p.qa_passed or p.escalated_to_user):
        raise HTTPException(status_code=409, detail="Trang chưa qua Master QA — đợi dựng xong rồi xuất bản.")
    from chromaswarm.agents.consultant import project_title
    name = str((body or {}).get("name") or (p.brief or {}).get("brand") or project_title(p.raw_prompt or "", limit=40))
    fn = {"vercel": publish.vercel, "github": publish.github}.get(target)
    if fn is None:
        raise HTTPException(status_code=404, detail="Chỉ hỗ trợ xuất bản lên Vercel hoặc GitHub.")
    try:
        return (await fn(app_dir, name)).model_dump()
    except publish.PublishError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@app.get("/sessions/{session_id}/shots/{name}")
def section_shot(session_id: str, name: str) -> FileResponse:
    """B9 eyes: a section screenshot (desktop / mobile) shown in the Studio next to its verdict."""
    import re
    if not uploads.SAFE_SESSION.match(session_id) or not re.fullmatch(r"[a-z0-9-]{1,80}-v\d-(desktop|mobile)\.jpg", name):
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    path = WORKSPACES / session_id / "artifacts" / "shots" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    return FileResponse(path, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"})


@app.post("/sessions/{session_id}/uploads")
async def upload_asset(session_id: str, kind: str = Form(...), file: UploadFile = File(...)) -> dict:
    """B4: the user's logo, product photo or reference screenshot (raster images only, checked by content)."""
    data = await file.read(uploads.MAX_BYTES + 1)
    try:
        saved = uploads.save(WORKSPACES, session_id, kind, data)
    except uploads.UploadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return {**saved.model_dump(), "url": f"/sessions/{session_id}/uploads/{saved.name}"}


@app.get("/sessions/{session_id}/uploads/{name}")
def uploaded_file(session_id: str, name: str) -> FileResponse:
    path = uploads.resolve(WORKSPACES, session_id, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Không có file này.")
    return FileResponse(path, media_type=uploads.media_type(path),
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})


_SAFE_SKETCH = re.compile(r"^(ref|built|shot)-\d{2}\.jpg$")


@app.get("/sessions/{session_id}/sketch/{name}")
def sketch_shot(session_id: str, name: str) -> Response:
    """Clone sketch step: reference screenshot | sketch of what was read (B2), or reference sketch | rebuild
    sketch (B10), one screen per image."""
    if not uploads.SAFE_SESSION.match(session_id) or not _SAFE_SKETCH.match(name):
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    path = WORKSPACES / session_id / "artifacts" / "sketch" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Không có ảnh này.")
    return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health() -> dict:
    return {"ok": True, "consultant": getattr(consultant, "name", "rule-based"),
            "chat": getattr(chat_agent, "name", "rule-based"), "build": build is not None}


# Every open Studio tab of a session, and one lock per session so an answer from the Studio
# and a B12 choice clicked in the browser window can never resume the graph at the same time.
CLIENTS: dict[str, set[WebSocket]] = defaultdict(set)
RUNNING: set[str] = set()  # sessions whose graph is running in this process right now
LOCKS: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def broadcast(session_id: str, message: dict) -> None:
    for client in list(CLIENTS[session_id]):
        with contextlib.suppress(Exception):
            await client.send_json(message)


async def resume(session_id: str, value) -> dict:
    """Resume the pipeline with an answer and stream build progress to every tab of the session.
    Clone sessions are written to Supabase as they go (clone/history.py; no-op without its settings)."""
    async def progress(snap: dict) -> None:
        await history.record_snapshot(snap)  # every step's notice, also the passes that do not stream
        # Long-running build work streams; so does Clone's reading (B1-B6 run by themselves, one pass per step),
        # so the Studio shows what Chroma is doing at each step instead of a silent wait.
        p = snap["pipeline"]
        if p.step in BUILD_STEPS or p.mode is BuildMode.CLONE:
            await broadcast(session_id, to_message(snap))

    async with LOCKS[session_id]:
        await history.record_answer((await runner.snapshot(session_id))["pipeline"], value)
        RUNNING.add(session_id)
        try:
            snap = await runner.answer(session_id, value, on_progress=progress)
        finally:
            RUNNING.discard(session_id)
    await history.record_snapshot(snap)
    await broadcast(session_id, to_message(snap))
    return snap



async def restore_clone(session_id: str) -> None:
    """After a backend restart, a Clone session saved in Supabase continues where it was (a build that was
    running goes back to the plan approval: its dev server and browser are gone)."""
    if not history.enabled or not uploads.SAFE_SESSION.match(session_id):
        return
    snap = await runner.snapshot(session_id)  # loads the thread's graph state from Supabase when memory lacks it
    p_now = snap["pipeline"]
    if p_now is not None and not (p_now.step in BUILD_STEPS and snap["question"] is None and snap["finished"] is False
                                  and session_id not in RUNNING):
        return  # resumed exactly where it was (a question waits), or still running in this process
    saved = p_now.model_dump(mode="json") if p_now is not None else await history.state(session_id)
    if not saved:
        return
    try:
        p = resumable(saved)  # a build cut off by the restart goes back to the plan approval
        async with LOCKS[session_id]:
            await (await runner.graph()).ainvoke({"pipeline": p}, runner._config(session_id))
        await history.add_event(session_id, "restored", p.step.value, {"step": p.step.value})
    except Exception as e:  # noqa: BLE001 — a bad saved state must not lock the user out: start fresh
        log.warning("could not restore clone session %s: %s", session_id, e)


@app.get("/clone/sessions")
async def clone_sessions() -> dict:
    """Saved Clone sessions (newest first) for the Studio's history list."""
    return {"enabled": history.enabled, "sessions": await history.sessions()}


@app.get("/clone/sessions/{session_id}/messages")
async def clone_messages(session_id: str) -> dict:
    """The saved conversation of one Clone session (to redraw the Studio thread after a reload)."""
    if not uploads.SAFE_SESSION.match(session_id):
        raise HTTPException(status_code=404, detail="Không có phiên này.")
    return {"messages": await history.messages(session_id)}



class Transcripts(dict):
    """Creative-mode chat per session, saved next to the session's workspace (survives a restart)."""

    def __missing__(self, session_id: str) -> list[dict]:
        path = self.path(session_id)
        try:
            history = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else []
        except (OSError, ValueError):
            history = []
        self[session_id] = history
        return history

    @staticmethod
    def path(session_id: str) -> Path | None:
        return WORKSPACES / session_id / "chat.json" if uploads.SAFE_SESSION.match(session_id) and runner.db_path else None

    def save(self, session_id: str) -> None:
        if path := self.path(session_id):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self[session_id], ensure_ascii=False), encoding="utf-8")


CHATS = Transcripts()


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
    CHATS.save(session_id)
    if turn.intent in ("answer", "revise"):
        await resume(session_id, turn.answer)


async def browser_choice(session_id: str, value: dict) -> None:
    """B12 button clicked inside the handed-over browser window."""
    snap = await runner.snapshot(session_id)
    question = snap["question"] or {}
    if question.get("kind") != "handover":
        return
    if value.get("action") == "refine" and not str(value.get("feedback") or "").strip():
        await broadcast(session_id, {**to_message(snap),
                                     "notice": "Bạn ghi điều muốn tinh chỉnh vào ô góp ý rồi gửi."})
        return
    try:
        await resume(session_id, value)
    except Exception as e:
        log.exception("browser choice failed")
        await broadcast(session_id, {"type": "error", "message": f"Lỗi hệ thống: {e}"})


async def restore(session_id: str, snap: dict) -> None:
    """First connection after a backend restart: an interrupted build carries on, and a handed-over
    page gets its dev server and browser window back."""
    if await runner.interrupted(session_id):
        asyncio.get_running_loop().create_task(_continue(session_id))
        return
    p = snap["pipeline"]
    question = snap["question"] or {}
    if build and p and question.get("kind") == "handover" and p.preview_url and not build.has_session(session_id):
        asyncio.get_running_loop().create_task(_reopen(session_id))


async def _continue(session_id: str) -> None:
    async def progress(snap: dict) -> None:
        await broadcast(session_id, to_message(snap))
    try:
        async with LOCKS[session_id]:
            snap = await runner.continue_run(session_id, on_progress=progress)
        await broadcast(session_id, to_message(snap))
    except Exception as e:
        log.exception("resuming %s failed", session_id)
        await broadcast(session_id, {"type": "error", "message": f"Không tiếp tục được phiên sau khi khởi động lại: {e}"})


async def _reopen(session_id: str) -> None:
    async with LOCKS[session_id]:
        snap = await runner.snapshot(session_id)
        p = snap["pipeline"]
        if build.has_session(session_id) or not p or not p.preview_url:
            return
        try:
            url = await build.reopen(session_id, p.preview_url, handover_options(p))
        except Exception as e:  # noqa: BLE001 — the documents and code are still on disk
            log.warning("reopen %s failed: %s", session_id, e)
            await broadcast(session_id, {**to_message(snap), "notice": f"Chưa mở lại được trang đã dựng: {str(e)[:120]}"})
            return
    if url:
        note = "Đã mở lại trang đã dựng sau khi máy chủ khởi động lại" + (f" · địa chỉ mới {url}" if url != p.preview_url else "") + "."
        await broadcast(session_id, {**to_message(snap), "notice": note})


if build:
    build.on_choice = browser_choice


@app.websocket("/ws/session/{session_id}")
async def session_ws(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    CLIENTS[session_id].add(ws)
    try:
        await restore_clone(session_id)
        snap = await runner.start(session_id)  # inside: the tab may close at once
        for line in CHATS[session_id]:  # a reopened tab or a restarted backend: the conversation so far
            await ws.send_json({"type": "chat", "role": line["role"], "text": line["text"], "replay": True})
        await ws.send_json(to_message(snap))
        await restore(session_id, snap)
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
