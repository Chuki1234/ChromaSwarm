"""Template output: page words in content/<page>.ts, photos in content/images.ts, zip export."""

import io
import zipfile

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import CLONE_PLACEHOLDERS, build_copy
from chromaswarm.developer.nextjs import content_file, images_file, render_section, scaffold
from chromaswarm.developer.template import app_dir_for, template_zip
from chromaswarm.state_machine.pipeline_state import CloneSource, Domain, PipelineState


def state(**kw) -> PipelineState:
    return PipelineState(session_id="s", raw_prompt="Trang cá nhân của nhà thiết kế, muốn khách bấm Liên hệ",
                         domain=Domain.PORTFOLIO, **kw)


def sec(sid, structure, name="Phần"):
    return Section(id=sid, name=name, structure=structure, content="x")


def test_words_move_to_the_content_file_and_the_component_reads_them():
    copy = build_copy(state())
    words: dict = {}
    hero = render_section(sec("hero", "hero-text", "Hero"), copy, "", content=words).content
    quotes = render_section(sec("testimonials", "testimonials", "Lời khách hàng"), copy, "", content=words).content
    assert 'import { content } from "@/content/home";' in hero and 'const C = content["hero"];' in hero
    assert "{C.headline}" in hero and copy.headline not in hero  # no copy left in the code
    assert words["hero"]["headline"] == copy.headline and words["hero"]["subhead"] == copy.subhead
    # fixed template words (section titles) are editable too
    assert words["testimonials"]["heading"] == "Khách hàng nói gì" and "{C.heading}" in quotes
    f = content_file("", [(sec("hero", "hero-text", "Hero"), words["hero"]),
                          (sec("testimonials", "testimonials", "Lời khách hàng"), words["testimonials"])])
    assert f.path == "content/home.ts" and "// Hero" in f.content and "// Lời khách hàng" in f.content
    assert f.content.index('"hero"') < f.content.index('"testimonials"') and "headline:" in f.content


def test_without_a_content_dict_rendering_is_unchanged():
    copy = build_copy(state())
    code = render_section(sec("hero", "hero-text"), copy).content
    assert copy.headline in code and "@/content/" not in code


def test_subpages_get_their_own_content_file():
    words: dict = {}
    code = render_section(sec("hero", "hero-text"), build_copy(state()), "pdp", content=words).content
    assert '"@/content/pdp"' in code and content_file("pdp", [(sec("hero", "hero-text"), words["hero"])]).path == "content/pdp.ts"


def test_structure_clone_shows_placeholders_not_guessed_names():
    s = state(selected_page="clone", clone=CloneSource(url="https://x.vn", owned=False))
    copy = build_copy(s)
    assert copy.brand == CLONE_PLACEHOLDERS["brand"] and copy.headline.startswith("[")
    owned = state(selected_page="clone", clone=CloneSource(url="https://x.vn", owned=True,
                                                           content={"site_title": "Gốm Mộc", "sections": {}}))
    assert build_copy(owned).brand == "Gốm Mộc"


def test_images_file_and_guide_are_part_of_the_scaffold(tmp_path):
    from chromaswarm.engines.design_spec import build_design_spec
    from chromaswarm.agents.planner import design_inputs
    s = state()
    s.pillars.theme, s.pillars.layout, s.pillars.color, s.pillars.margins = "warm-organic", "catalog", "light", "balanced"
    files = {f.path: f.content for f in scaffold("Dự án", build_design_spec(design_inputs(s, "Dự án")), ["https://a/1.jpg"])}
    assert 'import { PHOTOS } from "@/content/images";' in files["components/Art.tsx"]
    assert '"https://a/1.jpg"' in files["content/images.ts"] and "public/images" in files["content/images.ts"]
    assert "npm run dev" in files["HUONG_DAN.md"] and "`content/`" in files["HUONG_DAN.md"]
    assert images_file([]).content.rstrip().endswith("PHOTOS: string[] = [];")


def test_zip_has_the_app_without_packages_or_build_output(tmp_path):
    app = tmp_path / "sess-1" / "app"
    for rel in ("package.json", "content/home.ts", "app/page.tsx", "node_modules/x/index.js", ".next/cache/a", "HUONG_DAN.md"):
        (app / rel).parent.mkdir(parents=True, exist_ok=True)
        (app / rel).write_text("x")
    assert app_dir_for(tmp_path, "sess-1") == app.resolve()
    assert app_dir_for(tmp_path, "../etc") is None and app_dir_for(tmp_path, "missing") is None
    names = zipfile.ZipFile(io.BytesIO(template_zip(app))).namelist()
    assert "trang-web/content/home.ts" in names and "trang-web/HUONG_DAN.md" in names
    assert "trang-web/public/images/.gitkeep" in names
    assert not any("node_modules" in n or ".next" in n for n in names)


def test_design_md_has_no_unformatted_placeholders():
    import re
    from chromaswarm.agents.planner import design_inputs
    from chromaswarm.engines.design_spec import build_design_spec, render_design_md
    s = state(selected_page="clone", clone=CloneSource(url="https://x.vn", content_width=640))
    s.pillars.theme, s.pillars.layout, s.pillars.color, s.pillars.margins = "warm-organic", "catalog", "light", "balanced"
    md = render_design_md(build_design_spec(design_inputs(s, "X")))
    assert not re.search(r"\{[a-z_.]+\}", md) and "gutter 16px" in md


UNACCENTED_VI = __import__("re").compile(r"\b(Xem|nhanh|Menu chinh)\b")
VI_LETTERS = __import__("re").compile(r"[ăâđêôơưàảãạáằẳẵặắầẩẫậấèẻẽẹéềểễệếìỉĩịíòỏõọóồổỗộốờởỡợớùủũụúừửữựứỳỷỹỵý]", __import__("re").I)


def test_an_english_reference_is_rebuilt_in_english(tmp_path):
    from chromaswarm.agents.planner import design_inputs
    from chromaswarm.developer.i18n import normalise
    from chromaswarm.engines.design_spec import build_design_spec
    assert normalise("en-US") == "en" and normalise("vi") == "vi" and normalise("de") == "en" and normalise(None) == "vi"
    s = state(selected_page="clone", clone=CloneSource(url="https://x.com", lang="en-US"))
    copy = build_copy(s)
    assert copy.lang == "en" and copy.brand == "[Your name]" and copy.nav[0] == "Work"
    words: dict = {}
    code = ""
    for sid, kind in [("site-header", "sticky-bar"), ("hero", "hero-text"), ("testimonials", "testimonials"),
                      ("list-rows", "list-rows"), ("bento", "bento"), ("faq", "accordion"), ("site-footer", "footer-columns")]:
        code += render_section(sec(sid, kind), copy, "", content=words).content
    # No Vietnamese left anywhere on the page: code, lifted labels or sample copy.
    assert not VI_LETTERS.search(code), VI_LETTERS.search(code)
    assert not VI_LETTERS.search(str(words)), [w for w in str(words).split('"') if VI_LETTERS.search(w)][:5]
    assert words["testimonials"]["heading"] == "What clients say"
    s.pillars.theme, s.pillars.layout, s.pillars.color, s.pillars.margins = "warm-organic", "catalog", "light", "balanced"
    files = {f.path: f.content for f in scaffold("X", build_design_spec(design_inputs(s, "X")))}
    assert '<html lang="en">' in files["app/layout.tsx"]


def test_vietnamese_pages_are_unchanged():
    copy = build_copy(state())
    assert copy.lang == "vi" and copy.nav[0] == "Dự án"


def test_no_template_leaves_vietnamese_on_an_english_page():
    from chromaswarm.developer.nextjs import BY_ID, BY_STRUCTURE
    from chromaswarm.state_machine.pipeline_state import Domain
    for dom in Domain:
        s = PipelineState(session_id="s", raw_prompt="x", domain=dom, selected_page="clone",
                          clone=CloneSource(url="https://x.com", lang="en"))
        copy = build_copy(s)
        for sid, kind in [(k, k) for k in BY_STRUCTURE] + [(i, "split-7-5") for i in BY_ID]:
            words: dict = {}
            code = render_section(sec(sid, kind), copy, "", content=words).content
            lines = [ln for ln in (code + "\n" + str(words)).splitlines()
                     if (VI_LETTERS.search(ln) or UNACCENTED_VI.search(ln)) and not ln.strip().startswith("//")]
            assert not lines, (dom, sid, lines[:3])
