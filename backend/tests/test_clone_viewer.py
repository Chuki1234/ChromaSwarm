"""Clone: the finished page's permanent link — sent once per finished build, reachable later."""

import asyncio
from types import SimpleNamespace

from chromaswarm.clone import viewer as v
from chromaswarm.state_machine.pipeline_state import BuildMode, PipelineState, Step


def _app(root, sid, installed=True):
    app = root / sid / "app"
    app.mkdir(parents=True)
    (app / "package.json").write_text("{}")
    if installed:
        (app / "node_modules").mkdir()
    return app


def test_page_link_points_at_the_backend(monkeypatch):
    monkeypatch.setenv("CHROMASWARM_PUBLIC_URL", "http://example.test:8100/")
    assert v.page_link("s-abc") == "http://example.test:8100/sessions/s-abc/page"


def test_app_dir_needs_a_runnable_app_and_a_safe_id(tmp_path):
    _app(tmp_path, "s-ok")
    _app(tmp_path, "s-bare", installed=False)
    assert v.app_dir(tmp_path, "s-ok") == tmp_path / "s-ok" / "app"
    assert v.app_dir(tmp_path, "s-bare") is None
    assert v.app_dir(tmp_path, "../etc") is None
    assert v.app_dir(tmp_path, "s-missing") is None


def test_viewer_uses_the_builds_own_server_while_it_runs(tmp_path):
    live = SimpleNamespace(server=SimpleNamespace(url="http://localhost:3001", proc=SimpleNamespace(returncode=None)))
    runtime = SimpleNamespace(_sessions={"s-live": live})
    viewer = v.PageViewer(tmp_path, runtime)
    assert asyncio.run(viewer.url("s-live")) == "http://localhost:3001"
    assert asyncio.run(viewer.url("s-gone")) is None  # no app on disk: nothing to show


def test_announce_sends_the_link_once_per_finished_build(tmp_path, monkeypatch):
    from chromaswarm import main
    _app(tmp_path, "s-done")
    monkeypatch.setattr(main, "WORKSPACES", tmp_path)
    sent, saved = [], []

    async def broadcast(sid, msg):
        sent.append(msg)

    async def add_message(sid, role, kind, text, step=None, payload=None):
        saved.append((kind, text, payload))
        return True

    monkeypatch.setattr(main, "broadcast", broadcast)
    monkeypatch.setattr(main.history, "add_message", add_message)
    main.LINKS_SENT.pop("s-done", None)
    p = PipelineState(session_id="s-done", mode=BuildMode.CLONE, step=Step.B12_HANDOVER, preview_url="http://localhost:3001",
                      clone_verdict={"status": "failed", "title": "Chưa đạt — khớp 90/180 mục"})
    snap = {"pipeline": p, "question": {"kind": "handover"}, "finished": False}
    asyncio.run(main.announce_page("s-done", snap))
    asyncio.run(main.announce_page("s-done", snap))  # same build: not sent twice
    assert len(sent) == 1 and sent[0]["type"] == "page_link" and sent[0]["url"].endswith("/sessions/s-done/page")
    assert "Chưa đạt" in sent[0]["text"] and saved[0][0] == "page_link" and saved[0][2]["url"] == sent[0]["url"]
    # Still building (a question before the handover): nothing yet.
    main.LINKS_SENT.pop("s-done", None)
    sent.clear()
    asyncio.run(main.announce_page("s-done", {"pipeline": p, "question": {"kind": "approval"}, "finished": False}))
    assert sent == []
