"""B4 uploads (developer/uploads.py) and saved sessions (PipelineRunner with SQLite)."""

import asyncio
import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from chromaswarm.developer import uploads
from chromaswarm.developer.content import build_copy
from chromaswarm.developer.nextjs import render_section
from chromaswarm.agents.planner import NAV
from chromaswarm.state_machine.graph import PipelineRunner
from chromaswarm.state_machine.graph import Deps
from chromaswarm.state_machine.pipeline_state import Asset, Domain, Pillars, PipelineState, Step


def png(w: int = 1200, h: int = 800) -> bytes:
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))  # noqa: E731
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def jpg(w: int = 1600, h: int = 900) -> bytes:
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8\xff\xe0" + struct.pack(">H", 4) + b"JF" + sof + b"\xff\xd9"


def test_images_are_recognised_by_content_and_sized(tmp_path):
    a = uploads.save(tmp_path, "s1", "product-image", png())
    b = uploads.save(tmp_path, "s1", "logo", jpg())
    assert (a.width, a.height, a.path) == (1200, 800, f"uploads/{a.name}") and a.name.endswith(".png")
    assert (b.width, b.height) == (1600, 900) and b.name.startswith("logo-") and b.name.endswith(".jpg")
    assert uploads.save(tmp_path, "s1", "product-image", png()).name == a.name  # same bytes, one file


@pytest.mark.parametrize("data, why", [
    (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "SVG"),
    (b"GIF8 not really", "PNG"),
    (b"", "rỗng"),
])
def test_anything_but_a_raster_image_is_refused(tmp_path, data, why):
    with pytest.raises(uploads.UploadError, match=why):
        uploads.save(tmp_path, "s1", "logo", data)


def test_refuses_big_files_bad_kinds_and_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_BYTES", 100)
    with pytest.raises(uploads.UploadError, match="MB"):
        uploads.save(tmp_path, "s1", "logo", png() + b"\0" * 200)
    with pytest.raises(uploads.UploadError):
        uploads.save(tmp_path, "s1", "script", png())
    with pytest.raises(uploads.UploadError):
        uploads.save(tmp_path, "../x", "logo", png())
    assert uploads.resolve(tmp_path, "s1", "../../etc/passwd") is None
    assert uploads.resolve(tmp_path, "s1", "uploads/logo-000000000000.png") is None  # well-formed, not there


def test_own_photos_and_logo_replace_stock_on_the_page(tmp_path):
    photo = uploads.save(tmp_path, "s1", "product-image", png())
    logo = uploads.save(tmp_path, "s1", "logo", png(300, 80))
    p = PipelineState(session_id="s1", raw_prompt="shop cà phê rang xay", domain=Domain.ECOMMERCE,
                      pillars=Pillars(theme="warm-organic", layout="visual-first", color="light", margins="balanced",
                                      scope="Dân văn phòng; muốn họ bấm Mua ngay"),
                      assets=[Asset(kind="product-image", path_or_text=photo.path), Asset(kind="logo", path_or_text=logo.path),
                              Asset(kind="product-image", path_or_text="ảnh-tự-gõ.jpg")])  # a typed name is not a file
    copy = build_copy(p)
    assert copy.images == [f"/images/{photo.name}"] and copy.logo == f"/images/{logo.name}"
    nav = render_section(NAV, copy).content
    assert f'const LOGO = "/images/{logo.name}"' in nav and 'alt={BRAND} className="nav-logo-img"' in nav
    assert "LOGO" not in render_section(NAV, copy.model_copy(update={"logo": ""})).content


def test_upload_api_stores_and_serves_the_file(tmp_path, monkeypatch):
    from chromaswarm import main
    monkeypatch.setattr(main, "WORKSPACES", tmp_path)
    client = TestClient(main.app)
    r = client.post("/sessions/s-up/uploads", data={"kind": "product-image"}, files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 200 and r.json()["width"] == 1200
    got = client.get(r.json()["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/png" and got.headers["x-content-type-options"] == "nosniff"
    bad = client.post("/sessions/s-up/uploads", data={"kind": "logo"}, files={"file": ("x.png", b"<svg/>", "image/png")})
    assert bad.status_code == 422 and "SVG" in bad.json()["detail"]
    assert client.get("/sessions/s-up/uploads/..%2F..%2Fsecret").status_code == 404


def test_a_session_survives_a_restart(tmp_path):
    db = tmp_path / "sessions.sqlite"

    async def first():
        r = PipelineRunner(db_path=db)
        await r.start("s-keep")
        await r.answer("s-keep", "creative")
        await r.close()

    async def after_restart():
        r = PipelineRunner(db_path=db)
        snap = await r.start("s-keep")
        stopped = await r.interrupted("s-keep")
        await r.close()
        return snap, stopped

    asyncio.run(first())
    snap, stopped = asyncio.run(after_restart())
    assert snap["pipeline"].mode.value == "creative" and snap["question"]["key"] == "raw_prompt"
    assert stopped is False  # waiting for the user, not cut off mid-run


def test_a_build_cut_off_by_a_restart_carries_on_from_b8(tmp_path):
    from test_build import HAPPY, FakeBuild

    db = tmp_path / "sessions.sqlite"

    class Crash(FakeBuild):
        async def write_section(self, session, written, copy, page="", route="/"):
            if written[-1].id == "faq":
                raise asyncio.CancelledError  # the process dies mid-build
            await super().write_section(session, written, copy, page, route)

    async def before():
        r = PipelineRunner(Deps(artifacts_root=tmp_path, build=Crash()), db_path=db)
        await r.start("s-crash")
        for a in ["creative", *HAPPY]:
            await r.answer("s-crash", a)
        try:
            await r.answer("s-crash", {"approve": True})
        except BaseException:  # noqa: BLE001 — LangGraph re-raises it as NodeCancelledError
            pass
        await r.close()

    async def after():
        build = FakeBuild()
        r = PipelineRunner(Deps(artifacts_root=tmp_path, build=build), db_path=db)
        await r.start("s-crash")
        assert await r.interrupted("s-crash") is True and await r.interrupted("s-crash") is False
        snap = await r.continue_run("s-crash")
        await r.close()
        return snap, build

    asyncio.run(before())
    snap, build = asyncio.run(after())
    p = snap["pipeline"]
    assert p.step is Step.B12_HANDOVER and p.plan_approved and p.qa_passed
    assert build.log[0] == "tokens" and "write:site-header" in build.log  # rebuilt from B8 on the new process
