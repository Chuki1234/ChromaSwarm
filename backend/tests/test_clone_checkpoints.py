"""The graph state of a Clone session survives a backend restart through Supabase (mirrored checkpoints)."""

import asyncio
import json

import httpx

from chromaswarm.clone.checkpoints import SupabaseCloneSaver
from chromaswarm.clone.history import CloneHistory
from chromaswarm.state_machine.graph import SERDE, Deps, PipelineRunner, build_graph
from chromaswarm.state_machine.pipeline_state import Step
from tests.test_clone import fake_reader


def fake_supabase(rows: dict):
    """A tiny PostgREST: clone_graph_checkpoints rows kept in `rows`, everything else accepted."""
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "clone_graph_checkpoints" in path:
            if request.method == "POST":
                body = json.loads(request.content)
                rows[body["thread_id"]] = body
                return httpx.Response(201)
            tid = request.url.params.get("thread_id", "").removeprefix("eq.")
            return httpx.Response(200, json=[rows[tid]] if tid in rows else [])
        return httpx.Response(201 if request.method == "POST" else 200, json=[])
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def backend(rows: dict, tmp_path):
    """One backend process: its own memory, the shared Supabase."""
    store = CloneHistory("https://p.supabase.co", "k", fake_supabase(rows))
    saver = SupabaseCloneSaver(serde=SERDE, store=store)
    deps = Deps(artifacts_root=tmp_path, clone_reader=fake_reader())
    runner = PipelineRunner(deps, checkpointer=saver)
    return runner, saver


def test_a_clone_session_continues_after_a_restart_exactly_where_it_waited(tmp_path):
    rows: dict = {}

    async def first_process():
        runner, saver = backend(rows, tmp_path)
        await runner.start("c-1")
        await runner.answer("c-1", "clone")
        snap = await runner.answer("c-1", {"url": "https://gom-moc.vn"})
        await saver.flush_all()
        return snap

    async def second_process():
        runner, saver = backend(rows, tmp_path)  # fresh memory: nothing but Supabase
        return await runner.snapshot("c-1"), saver

    before = asyncio.run(first_process())
    assert before["pipeline"].step is Step.B7_APPROVAL and "c-1" in rows
    after, saver = asyncio.run(second_process())
    assert after["pipeline"].step is Step.B7_APPROVAL
    assert after["question"]["kind"] == before["question"]["kind"] == "approval"  # the same pending question
    assert after["pipeline"].clone.url == "https://gom-moc.vn" and "c-1" in saver.clone_threads


def test_creative_threads_are_never_mirrored(tmp_path):
    rows: dict = {}

    async def run():
        runner, saver = backend(rows, tmp_path)
        await runner.start("cr-1")
        await runner.answer("cr-1", "creative")
        await saver.flush_all()
    asyncio.run(run())
    assert rows == {}
