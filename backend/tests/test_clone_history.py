"""Clone history in Supabase: what is written, what is never written, and how a session comes back."""

import asyncio
import json

import httpx

from chromaswarm.clone.history import CloneHistory, answer_text, resumable, safe_payload
from chromaswarm.state_machine.pipeline_state import BuildMode, CloneSource, PipelineState, Step


def fake_supabase():
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "service-key" and request.headers["Authorization"] == "Bearer service-key"
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path + ("?" + request.url.query.decode() if request.url.query else ""), body))
        if request.method == "GET" and "clone_messages" in request.url.path:
            return httpx.Response(200, json=[{"role": "user", "kind": "answer", "step": "B1", "text": "https://x.dev"}])
        if request.method == "GET":
            return httpx.Response(200, json=[{"state": PipelineState(session_id="s-1", mode=BuildMode.CLONE,
                                                                     step=Step.B9_DEVELOP, plan_approved=True,
                                                                     preview_url="http://localhost:3001").model_dump(mode="json")}])
        return httpx.Response(201)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CloneHistory("https://proj.supabase.co", "service-key", client), calls


def test_clone_sessions_messages_and_events_are_written_creative_ones_never():
    store, calls = fake_supabase()
    clone = PipelineState(session_id="s-1", mode=BuildMode.CLONE, step=Step.B2_SITEMAP,
                          clone=CloneSource(url="https://x.dev"))
    creative = PipelineState(session_id="s-2", mode=BuildMode.CREATIVE, step=Step.B2_SITEMAP)

    async def run():
        await store.record_answer(clone, {"url": "https://x.dev"})
        await store.record_snapshot({"pipeline": clone, "notice": "Đã đọc 5 section", "question": None})
        await store.record_snapshot({"pipeline": clone, "notice": "Đã đọc 5 section", "question": None})  # no repeat
        await store.record_answer(creative, "hello")
        await store.record_snapshot({"pipeline": creative, "notice": "x", "question": None})
    asyncio.run(run())
    tables = [path.split("/rest/v1/")[1].split("?")[0] for _, path, _ in calls]
    assert "clone_sessions" in tables and tables.count("clone_messages") == 2 and "clone_events" in tables
    assert all(b is None or b.get("id", b.get("session_id")) == "s-1" for _, _, b in calls)  # nothing from Creative
    session_row = next(b for _, p, b in calls if "clone_sessions" in p)
    assert session_row["url"] == "https://x.dev" and session_row["state"]["session_id"] == "s-1"
    assert any("on_conflict=id" in p for _, p, _ in calls)


def test_uploads_are_counted_not_stored():
    value = {"images": [{"slot": "hero", "data": "data:image/png;base64,AAAA"}], "texts": {"name": "A"}}
    assert answer_text(value) == "Đưa 1 ảnh và 1 mục nội dung"
    assert safe_payload(value)["images"] == [{"slot": "hero"}]


def test_a_build_that_was_running_comes_back_at_the_plan_approval():
    store, _ = fake_supabase()
    saved = asyncio.run(store.state("s-1"))
    p = resumable(saved)
    assert p.step is Step.B7_APPROVAL and not p.plan_approved and p.preview_url is None
    assert asyncio.run(store.messages("s-1"))[0]["text"] == "https://x.dev"


def test_without_settings_the_store_does_nothing():
    store = CloneHistory("", "")
    assert not store.enabled
    assert asyncio.run(store.sessions()) == [] and asyncio.run(store.add_event("s", "x")) is False
