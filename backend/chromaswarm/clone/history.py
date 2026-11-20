"""Clone mode history in Supabase: sessions, the conversation, and what Chroma did at each step.

Clone-only on purpose (Creative mode keeps its own in-memory chat, owned by its own branch). The backend
writes with the service-role key from `backend/.env` (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) through the
PostgREST API; the tables have RLS on and no policy, so no browser key can read them. Without the two
settings the store is disabled and Chroma runs exactly as before.

Nothing here may break a build: every call logs and swallows its own failure.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from chromaswarm.state_machine.pipeline_state import BuildMode, PipelineState, Step

log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request would drown the build log

BUILD_STEPS = {Step.B8_DESIGN, Step.B9_DEVELOP, Step.B10_INTEGRATE, Step.B11_MASTER_QA}


def status_of(p: PipelineState) -> str:
    if p.build_error:
        return "error"
    if p.handover_closed:
        return "finished"
    if p.step is Step.B12_HANDOVER:
        return "handed-over"
    if p.step in BUILD_STEPS:
        return "building"
    if p.step in (Step.B1_READ_PROMPT, Step.B2_SITEMAP):
        return "reading"
    return "planning"


def answer_text(value: Any) -> str:
    """What the user did, in a line (never a whole upload: photos are counted, not stored)."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if value.get("url"):
            return str(value["url"])
        if isinstance(value.get("spec"), dict) and not value.get("approve"):
            return "Đổi kế hoạch Clone: " + ", ".join(f"{k.split(':', 1)[-1]} → {v}" for k, v in list(value["spec"].items())[:6])
        if value.get("approve"):
            return "Duyệt kế hoạch"
        if value.get("feedback"):
            return f"Góp ý: {value['feedback']}"
        if "images" in value or "texts" in value:
            n, t = len(value.get("images") or []), len(value.get("texts") or {})
            return f"Đưa {n} ảnh và {t} mục nội dung" if n or t else "Bỏ qua, dùng ảnh và chữ mẫu"
        if value.get("action"):
            return f"Chọn: {value['action']}" + (f" ({value.get('slug')})" if value.get("slug") else "")
    return str(value)[:300]


def safe_payload(value: Any) -> Any:
    """The answer as stored: uploads reduced to their slot names."""
    if isinstance(value, dict) and value.get("images"):
        return {**value, "images": [{"slot": i.get("slot")} for i in value["images"] if isinstance(i, dict)]}
    return value


class CloneHistory:
    def __init__(self, url: str | None = None, key: str | None = None, client: httpx.AsyncClient | None = None):
        # None = read backend/.env (via the environment); an explicit "" switches the store off.
        self.url = (os.environ.get("SUPABASE_URL", "") if url is None else url).rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") if key is None else key
        self.enabled = bool(self.url and self.key)
        self._client = client
        self._last_notice: dict[str, str] = {}
        self._last_step: dict[str, str] = {}
        self._last_question: dict[str, str] = {}

    # ---------------------------------------------------------------- transport
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    def _headers(self, prefer: str = "return=minimal") -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                "Prefer": prefer}

    async def _post(self, table: str, rows: Any, prefer: str = "return=minimal", query: str = "") -> bool:
        if not self.enabled:
            return False
        try:
            r = await self._http().post(f"{self.url}/rest/v1/{table}{query}", json=rows, headers=self._headers(prefer))
            if r.status_code >= 300:
                log.warning("supabase %s: %s %s", table, r.status_code, r.text[:200])
                return False
            return True
        except Exception as e:  # noqa: BLE001 — history never breaks a build
            log.warning("supabase %s failed: %s", table, e)
            return False

    async def _get(self, table: str, query: str) -> list[dict]:
        if not self.enabled:
            return []
        try:
            r = await self._http().get(f"{self.url}/rest/v1/{table}?{query}", headers=self._headers())
            if r.status_code >= 300:
                log.warning("supabase %s: %s %s", table, r.status_code, r.text[:200])
                return []
            return r.json()
        except Exception as e:  # noqa: BLE001
            log.warning("supabase %s failed: %s", table, e)
            return []

    # ---------------------------------------------------------------- writes
    async def save_session(self, p: PipelineState) -> bool:
        if p.mode is not BuildMode.CLONE:
            return False
        c = p.clone
        row = {"id": p.session_id, "url": c.url if c else None, "title": c.title if c else None,
               "domain": p.domain.value if p.domain else None, "step": p.step.value, "status": status_of(p),
               "fidelity": (p.clone_compare or {}).get("total"), "state": p.model_dump(mode="json"),
               "updated_at": _now()}
        return await self._post("clone_sessions", row, "resolution=merge-duplicates,return=minimal", "?on_conflict=id")

    async def add_message(self, session_id: str, role: str, kind: str, text: str, step: str | None = None,
                          payload: Any = None) -> bool:
        if not text:
            return False
        return await self._post("clone_messages", {"session_id": session_id, "role": role, "kind": kind,
                                                   "step": step, "text": text[:8000], "payload": payload})

    async def add_event(self, session_id: str, type_: str, step: str | None = None, data: Any = None) -> bool:
        return await self._post("clone_events", {"session_id": session_id, "type": type_, "step": step, "data": data})

    async def record_answer(self, before: PipelineState | None, value: Any) -> None:
        """The user's answer, before the graph runs (so the conversation reads in order)."""
        if before is None or before.mode is not BuildMode.CLONE:
            return
        await self.save_session(before)
        await self.add_message(before.session_id, "user", "answer", answer_text(value), before.step.value,
                               safe_payload(value))

    async def record_snapshot(self, snap: dict) -> None:
        """What Chroma said and did: new notice, new question, step changes, results worth keeping."""
        p: PipelineState | None = snap.get("pipeline")
        if p is None or p.mode is not BuildMode.CLONE:
            return
        sid = p.session_id
        await self.save_session(p)
        if self._last_step.get(sid) != p.step.value:
            self._last_step[sid] = p.step.value
            await self.add_event(sid, "step", p.step.value, {"status": status_of(p)})
            if p.step is Step.B3_ELICITATION and p.clone and p.clone.motion_report:
                await self.add_event(sid, "motion", "B2", p.clone.motion_report)
            if p.step is Step.B12_HANDOVER:
                await self.add_event(sid, "handover", "B12", {"qa": p.qa_summary, "compare": p.clone_compare,
                                                              "fidelity": p.clone_fidelity})
        notice = snap.get("notice")
        if notice and self._last_notice.get(sid) != notice:
            self._last_notice[sid] = notice
            await self.add_message(sid, "assistant", "notice", notice, p.step.value)
            await self.add_event(sid, "notice", p.step.value, {"text": notice})
        question = snap.get("question") or {}
        qkey = f"{question.get('step')}:{question.get('kind')}:{question.get('text', '')[:80]}"
        if question and self._last_question.get(sid) != qkey:
            self._last_question[sid] = qkey
            await self.add_message(sid, "assistant", "question", question.get("text") or "", p.step.value,
                                   {"kind": question.get("kind"), "key": question.get("key")})

    # ---------------------------------------------------------------- reads
    async def sessions(self, limit: int = 30) -> list[dict]:
        return await self._get("clone_sessions", f"select=id,url,title,domain,step,status,fidelity,updated_at"
                                                 f"&order=updated_at.desc&limit={int(limit)}")

    async def state(self, session_id: str) -> dict | None:
        rows = await self._get("clone_sessions", f"select=state&id=eq.{_q(session_id)}")
        return rows[0]["state"] if rows else None

    async def messages(self, session_id: str) -> list[dict]:
        return await self._get("clone_messages", f"select=role,kind,step,text,created_at&session_id=eq.{_q(session_id)}"
                                                 f"&order=id.asc&limit=500")


def _now() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _q(value: str) -> str:
    from urllib.parse import quote
    return quote(value, safe="")


def resumable(state: dict) -> PipelineState:
    """A saved Clone session as the graph should pick it up after a restart: a build that was running
    (its dev server and browser are gone) goes back to the plan approval, so nothing rebuilds by itself."""
    p = PipelineState.model_validate(state)
    if p.step in BUILD_STEPS:
        p.preview_url = None
        p.sections_done, p.sections_checked = [], []
        p.integrated, p.qa_passed, p.build_error = False, False, None
        p.build_passes = []
        p.plan_approved = False
        p.step = Step.B7_APPROVAL
    return p
