import asyncio

from chromaswarm.clone.components import measure_reference
from chromaswarm.clone.sketch import check_reading
from playwright.async_api import async_playwright


def test_full_page_sketch_keeps_aria_hidden_animated_columns(tmp_path):
    source = tmp_path / "animated.html"
    image = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="220" height="300"%3E%3Crect width="220" height="300" fill="white"/%3E%3Cpath d="M20 30h160M20 60h100M20 90h160M20 120h120" stroke="black"/%3E%3C/svg%3E'
    cards = f"<img src='{image}'><img src='{image}'>"
    source.write_text(f'''<html><head><style>
      html {{ scroll-behavior:smooth }} body {{margin:0;padding-top:64px;font:18px sans-serif}}
      header {{position:fixed;top:0;width:100%;height:64px;z-index:20}} section {{position:relative;box-sizing:border-box}}
      #hero {{height:900px;background:#123}} h1 {{color:white}}
      .visual {{position:absolute;left:850px;top:80px;display:flex;gap:20px;height:650px;overflow:hidden}}
      .track {{display:flex;flex-direction:column;gap:20px;width:220px;animation:scroll 30s linear infinite}}
      .reverse {{animation-direction:reverse}} img {{width:220px;height:300px;flex-shrink:0}}
      @keyframes scroll {{from {{transform:translateY(0)}} to {{transform:translateY(-50%)}}}}
      #middle {{height:2000px}} footer {{height:200px;background:#ddd}}
      </style></head><body><header>Navigation</header><section id="hero"><h1>Moving CV previews</h1>
      <div class="visual" aria-hidden="true"><div class="track">{cards}</div><div class="track reverse">{cards}</div></div>
      </section><section id="middle"><h2>Second section</h2><p style="position:absolute;top:1400px">A component deep inside a tall section</p></section>
      <footer><h2>Final section</h2><p>The footer must appear in the sketch.</p></footer></body></html>''', encoding="utf-8")
    boxes = {"header": {"top": 0, "left": 0, "width": 1440, "height": 64},
             "hero": {"top": 64, "left": 0, "width": 1440, "height": 900},
             "middle": {"top": 964, "left": 0, "width": 1440, "height": 2000},
             "footer": {"top": 2964, "left": 0, "width": 1440, "height": 200}}

    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(source.as_uri())
            measured = await measure_reference(page, [{**b, "key": sid} for sid, b in boxes.items()])
            await browser.close()
        images = [c for c in measured["comps"]["hero"] if c["kind"] == "image"]
        assert any(c["x"] < 1000 for c in images) and any(c["x"] > 1000 for c in images)
        assert all(c.get("motion", {}).get("axis") == "y" for c in images)
        assert any(c["y"] > 1300 for c in measured["comps"]["middle"])
        header_ids = {c["rid"] for c in measured["comps"]["header"]}
        assert header_ids
        assert not any(c["rid"] in header_ids for sid, pieces in measured["comps"].items()
                       if sid != "header" for c in pieces)
        return await check_reading(source.as_uri(), boxes, measured["comps"], tmp_path / "sketch")

    result = asyncio.run(go())
    assert result["height"] >= 3164 and len(result["pairs"]) >= 4
    assert result["animated_components"] >= 2
    svg = (tmp_path / "sketch/sketch.svg").read_text(encoding="utf-8")
    assert "animation y" in svg and "footer" in svg and "clipPath" in svg
    assert (tmp_path / "sketch" / result["full"]).read_bytes().startswith(b"\xff\xd8")


def test_full_page_sketch_assets_are_served_with_the_right_type(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from chromaswarm import main

    folder = tmp_path / "s-full/artifacts/sketch"
    folder.mkdir(parents=True)
    (folder / "ref-full.jpg").write_bytes(b"jpeg")
    (folder / "sketch.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    monkeypatch.setattr(main, "WORKSPACES", tmp_path)
    client = TestClient(main.app)
    assert client.get("/sessions/s-full/sketch/ref-full.jpg").status_code == 200
    assert client.get("/sessions/s-full/sketch/sketch.svg").headers["content-type"].startswith("image/svg+xml")
    assert client.get("/sessions/s-full/sketch/private.env").status_code == 404
