"""B9 Developer department, Next.js adapter (rule-based baseline).

PLAN.md sections -> one TSX component per section, written into a standalone
Next.js App Router workspace. Every value comes from tokens.css (decision 4:
the Design department edits that file, never the components), every
interactive element carries data-swarm-id / data-swarm-role, and interactions
are real (accordion, tabs, modal, filtering, validation), because B11 clicks
them. An LLM-backed developer can replace `render_section` with the same
signature.
"""

from __future__ import annotations

import contextvars
import json
import re
import urllib.parse

from pydantic import BaseModel

from chromaswarm.agents.planner import Section
from chromaswarm.clone.fonts import google_css_url
from chromaswarm.developer.i18n import localize_code, localize_value
from chromaswarm.developer.content import PageCopy
from chromaswarm.developer.surfaces import surface_css
from chromaswarm.developer.measured import measurable, render_measured
from chromaswarm.engines.design_spec import DesignSpec

NEXT_VERSION = "16.4.5"
REACT_VERSION = "19.3.0"


class WorkspaceFile(BaseModel):
    path: str  # relative to the workspace app root
    content: str


def component_name(section_id: str) -> str:
    return "".join(p.capitalize() for p in section_id.replace("_", "-").split("-")) + "Section"


def _js(value, name: str | None = None) -> str:
    """A value in generated code. While a section is rendered for a template (`render_section(...,
    content=...)`), copy goes to the page's content file instead and the code reads `C.<key>`."""
    if (col := _COLLECT.get()) is not None:
        return f"C.{col.add(value, name)}"
    return json.dumps(value, ensure_ascii=False)


def _norm(value):
    """Tuples and models as plain JSON-like values, so copy can be compared with what a template shows."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    return value


class _Collector:
    """Copy shown by one section, keyed by the PageCopy field it came from (headline, story, items...)."""

    def __init__(self, page: str, copy: PageCopy):
        self.page, self.entries = page, {}
        self.fields = {k: _norm(v) for k, v in copy}

    def _name_for(self, value) -> str:
        v = _norm(value)
        for field, fv in self.fields.items():
            if v == fv or (isinstance(v, list) and v and isinstance(fv, list) and fv[:len(v)] == v):
                return field
        return "text"

    def add(self, value, name: str | None) -> str:
        base, v = name or self._name_for(value), _norm(value)
        for key, existing in self.entries.items():  # the same text shown twice is one entry
            if existing == v and key.rstrip("0123456789") == base:
                return key
        key, n = base, 2
        while key in self.entries:
            key, n = f"{base}{n}", n + 1
        self.entries[key] = v
        return key


_COLLECT: contextvars.ContextVar[_Collector | None] = contextvars.ContextVar("chromaswarm_collect", default=None)


# Fixed words written straight into a template (section titles, eyebrows, link labels): plain text
# between an opening and closing tag whose attributes hold no expression.
_FIXED_TEXT = re.compile(r"(<(h1|h2|h3|h4|p|span|a|figcaption|label|strong)\b([^<>{}]*)>)([^<>{}]*[^\W\d_][^<>{}]*)(</\2>)")


def _lift_fixed_text(jsx: str, col: "_Collector") -> str:
    def sub(m: re.Match) -> str:
        tag, attrs, text = m.group(2), m.group(3), m.group(4)
        name = ("eyebrow" if "eyebrow" in attrs else "heading" if tag in ("h1", "h2", "h3", "h4")
                else "link" if tag == "a" else "label")
        return f"{m.group(1)}{{C.{col.add(text.strip(), name)}}}{m.group(5)}"
    return _FIXED_TEXT.sub(sub, jsx)


def content_module(page: str) -> str:
    return f"content/{page or 'home'}"


# ----------------------------------------------------------------- scaffold

def scaffold(project: str, spec: DesignSpec, photos: list[str] | None = None) -> list[WorkspaceFile]:
    links = "\n".join(f'        <link rel="stylesheet" href="{url}" />' for url in font_stylesheets(spec))
    return [
        WorkspaceFile(path="package.json", content=json.dumps({
            "name": "chromaswarm-workspace", "private": True,
            "scripts": {"dev": "next dev", "build": "next build", "start": "next start"},
            "dependencies": {"next": NEXT_VERSION, "react": REACT_VERSION, "react-dom": REACT_VERSION},
            "devDependencies": {"typescript": "^5", "@types/react": "^19", "@types/react-dom": "^19",
                                "@types/node": "^20"},
        }, indent=2) + "\n"),
        WorkspaceFile(path="tsconfig.json", content=json.dumps({
            "compilerOptions": {
                "target": "ES2020", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": False, "skipLibCheck": True,
                "strict": True, "noEmit": True, "esModuleInterop": True, "module": "esnext",
                "moduleResolution": "bundler", "resolveJsonModule": True, "isolatedModules": True, "jsx": "react-jsx",
                "incremental": True, "plugins": [{"name": "next"}], "paths": {"@/*": ["./*"]},
            },
            "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
            "exclude": ["node_modules"],
        }, indent=2) + "\n"),
        WorkspaceFile(path="next.config.ts", content=(
            'import type { NextConfig } from "next";\n\n'
            "// Each workspace is its own Turbopack root (it never resolves files from the Studio).\n"
            "const nextConfig: NextConfig = { turbopack: { root: __dirname }, devIndicators: false, agentRules: false };\n\n"
            "export default nextConfig;\n")),
        WorkspaceFile(path="app/layout.tsx", content=f'''import type {{ Metadata }} from "next";
import "./tokens.css";
import "./base.css";
import "./surface.css";
import "./motion.css";
import "./match.css";
import "./heal.css";
import "./wireframe.css";

export const metadata: Metadata = {{ title: {_js(project)} }};

export default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{
  return (
    <html lang="{spec.inputs.lang}">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
{links}
      </head>
      <body>{{children}}</body>
    </html>
  );
}}
'''),
        WorkspaceFile(path="app/base.css", content=BASE_CSS),
        WorkspaceFile(path="app/surface.css", content=surface_css(spec.inputs.surface)),
        heal_file([]),
        motion_file([]),
        match_file(""),
        wireframe_file(None),
        WorkspaceFile(path="components/Art.tsx", content=art_component(spec, photos or [])),
        images_file(photos or []),
        WorkspaceFile(path="HUONG_DAN.md", content=guide(project)),
    ]


def images_file(photos: list[str]) -> WorkspaceFile:
    return WorkspaceFile(path="content/images.ts", content=(
        "// ẢNH TRÊN TRANG — dùng lần lượt theo thứ tự trong danh sách (ảnh 1 cho chỗ ảnh đầu tiên, ...).\n"
        "// Dùng ảnh của bạn: chép file vào thư mục public/images/ rồi ghi đường dẫn, ví dụ \"/images/chan-dung.jpg\".\n"
        "// Để trống danh sách thì trang dùng nền màu thay ảnh.\n"
        f"export const PHOTOS: string[] = {_ts(list(photos), 0)};\n"))


def guide(project: str) -> str:
    return f"""# Hướng dẫn dùng template — {project}

Trang này do ChromaSwarm dựng. Bạn chỉ cần sửa chữ và ảnh, không phải đụng vào code giao diện.

## 1. Sửa chữ

Mở thư mục `content/`: mỗi trang một file — trang chính là `home.ts`, `landing.ts` hoặc `clone.ts` (bản dựng lại từ trang mẫu); trang thêm sau có file riêng, ví dụ `pdp.ts`.

- Mỗi khối trong file là một phần của trang, theo thứ tự từ trên xuống, có ghi tên phần ở dòng `//` phía trên.
- Chỉ sửa chữ nằm trong dấu ngoặc kép. Giữ nguyên dấu ngoặc, dấu phẩy và tên bên trái dấu hai chấm.
- Chỗ có dấu ngoặc vuông như `[Tên của bạn]` là chỗ bắt buộc phải thay.
- Danh sách (thẻ, câu hỏi, dòng kinh nghiệm...) thêm hoặc bớt được: chép nguyên một dòng `[..., ...],` rồi sửa.

## 2. Thay ảnh

1. Chép ảnh vào `public/images/` (nên dùng .jpg hoặc .webp, cạnh dài khoảng 1600px).
2. Mở `content/images.ts`, ghi đường dẫn theo thứ tự xuất hiện trên trang, ví dụ:
   `export const PHOTOS: string[] = ["/images/anh-chinh.jpg", "/images/du-an-1.jpg"];`

## 3. Chạy thử trên máy

Cần Node.js 20 trở lên.

```bash
npm install
npm run dev
```

Mở http://localhost:3000. Sửa file nào, trang tự cập nhật.

## 4. Đưa lên mạng

Cách nhanh nhất: đẩy thư mục này lên GitHub rồi nhập vào https://vercel.com (miễn phí), hoặc chạy `npx vercel`.

## Không nên sửa (trừ khi bạn biết code)

- `app/tokens.css`: màu, chữ, khoảng cách — mọi con số đã được kiểm tra độ tương phản và lưới 8pt.
- `components/`: giao diện từng phần, đọc chữ từ thư mục `content/`.
"""


def font_stylesheets(spec: DesignSpec) -> list[str]:
    """Stylesheets for the page fonts: one Google Fonts request for every Google family (incl. the
    Vietnamese fallbacks of kept reference fonts), plus one per Fontshare family."""
    sources = {f["family"]: f for f in spec.inputs.font_sources}
    google, others = [], []
    for family in dict.fromkeys([spec.typography.heading_font, spec.typography.body_font]):
        src = sources.get(family)
        if src and src.get("provider") == "fontshare":
            others.append(src["css_url"])
        else:
            google.append(family)
        if src and not src.get("vietnamese") and src.get("fallback"):
            google.append(src["fallback"])
    google = sorted(dict.fromkeys(google))
    return ([google_css_url(google)] if google else []) + others


def wireframe_file(spec: DesignSpec | None) -> WorkspaceFile:
    """Wireframe pass (Clone): every colour token at its own lightness with no hue, photos in greyscale,
    no shadows — layout and hierarchy first, the same contrast as the final page. `None` = colour applied."""
    head = "/* Wireframe pass: layout and hierarchy in greys. Emptied when the colour pass runs (B10). */\n"
    if spec is None:
        return WorkspaceFile(path="app/wireframe.css", content=head)
    greys = []
    for tk in spec.palette.tokens:
        m = re.match(r"oklch\(\s*([\d.]+%?)", tk.css)
        if m:
            greys.append(f"  --{tk.name}: oklch({m.group(1)} 0 0);")
    css = (":root {\n" + "\n".join(greys) + "\n}\n"
           "img { filter: grayscale(1) contrast(.85); }\n"
           "* { box-shadow: none !important; text-shadow: none !important; }\n")
    return WorkspaceFile(path="app/wireframe.css", content=head + css)


_HREF = re.compile(r"^(/|#|https?:|mailto:|tel:)")


def skeleton(value, salt: int = 0):
    """Content for the wireframe pass: each word becomes a grey bar of about its length (links keep
    their targets), so the layout is judged before any copy is in. Items of a list get a different
    number of invisible zero-width spaces, so bars that look alike stay distinct (React keys)."""
    if isinstance(value, str):
        if not value or _HREF.match(value):
            return value
        return " ".join("▬" * max(2, min(len(w) // 2 + 1, 6)) for w in value.split()) + "\u200b" * salt
    if isinstance(value, list):
        return [skeleton(v, i) for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: skeleton(v, salt) for k, v in value.items()}
    return value


def match_file(body: str) -> WorkspaceFile:
    """Clone: component tuning (factory cursors in B9, Master's 1:1 acceptance in B11) — the reference's
    measured font sizes, weights, tracking, radii, button padding, card shadows; desktop only. Loaded
    before heal.css so QA patches still win."""
    head = "/* Component tuning to the reference page (Clone). Desktop only; heal.css still wins. */\n"
    return WorkspaceFile(path="app/match.css", content=head + body + ("\n" if body else ""))


def heal_file(rules: list[str]) -> WorkspaceFile:
    """B11 self-healing patches from the Master QA, loaded last so they win the cascade."""
    head = "/* Self-healing patches written by the Developer department after Master QA (B11). */\n"
    return WorkspaceFile(path="app/heal.css", content=head + "\n".join(rules) + ("\n" if rules else ""))


def motion_file(blocks: list[str]) -> WorkspaceFile:
    """B8.1 motion CSS returned by the Motion MCP server, one block per section effect."""
    head = "/* B8.1 motion effects (Motion & 2D/3D MCP Specialist). Respects prefers-reduced-motion. */\n"
    return WorkspaceFile(path="app/motion.css", content=head + "\n".join(blocks) + ("\n" if blocks else ""))


def route_dir(route: str) -> str:
    """'/' -> 'app', '/pdp' -> 'app/pdp'."""
    return "app" if route in ("", "/") else "app/" + route.strip("/")


def page_file(sections: list[Section], page: str = "", route: str = "/") -> WorkspaceFile:
    """Page file with the sections written so far (grows section by section via HMR).
    Each sitemap page gets its own route and its own components folder."""
    folder = f"components/sections/{page}" if page else "components/sections"
    imports = "\n".join(f'import {{ {component_name(s.id)} }} from "@/{folder}/{component_name(s.id)}";'
                        for s in sections)
    body = "\n".join(f"      <{component_name(s.id)} />" for s in sections)
    return WorkspaceFile(path=f"{route_dir(route)}/page.tsx", content=f"""{imports}

export default function Page() {{
  return (
    <main data-swarm-page="{page or 'index'}">
{body or "      {null}"}
    </main>
  );
}}
""")


def art_component(spec: DesignSpec, photos: list[str] | None = None) -> str:
    """Photos first (the user's own in Clone mode, else topic-matched Unsplash stock), with
    quiet tonal placeholders as data-URI SVG for offline use or a failed load, so pages never
    show grey boxes and every <img> has naturalWidth > 0 for the B11 image check.
    Placeholders use only neutral surface tones: the accent belongs to actions (§2.1)."""
    p = spec.palette
    s, e, b = p.get("bg-surface").hex, p.get("bg-elevated").hex, p.get("border-subtle").hex
    variants = []
    for c1, c2 in [(s, e), (e, s), (b, s)]:
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1000" viewBox="0 0 800 1000">'
               f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c1}"/>'
               f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs><rect width="800" height="1000" fill="url(#g)"/></svg>')
        variants.append("data:image/svg+xml;utf8," + urllib.parse.quote(svg))
    return f'''"use client";

const ART = {_js(variants)};
// Real photography: listed in content/images.ts (the user's own, or topic-matched Unsplash stock).
import {{ PHOTOS }} from "@/content/images";
const WIDTHS = [480, 800, 1200, 1800];

type Props = {{ label: string; ratio?: string; tone?: number; sizes?: string }};

/** Photos when available, tonal placeholders otherwise or when a photo fails to load. */
export function Art({{ label, ratio = "4 / 5", tone = 0, sizes = "(min-width: 1024px) 50vw, 100vw" }}: Props) {{
  const fallback = ART[tone % ART.length];
  const photo = PHOTOS.length ? PHOTOS[tone % PHOTOS.length] : null;
  // Unsplash serves any width on request: let the browser pick one for the slot.
  const sized = photo && photo.startsWith("https://images.unsplash.com/");
  return (
    <img className="art" alt={{label}} style={{{{ aspectRatio: ratio }}}}
      src={{photo ? (sized ? `${{photo}}&w=1200` : photo) : fallback}}
      srcSet={{sized ? WIDTHS.map((w) => `${{photo}}&w=${{w}} ${{w}}w`).join(", ") : undefined}}
      sizes={{sized ? sizes : undefined}}
      onError={{(e) => {{ const img = e.currentTarget; if (img.src !== fallback) {{ img.srcset = ""; img.src = fallback; }} }}}} />
  );
}}
'''


# ----------------------------------------------------------------- sections

def _root(section: Section, cls: str, inner: str, tag: str = "section") -> str:
    mcp = ' data-swarm-mcp="2d-css"' if section.effect or section.motion else ""  # B8.1 target (FRONTEND_STANDARDS §4.4)
    if section.surface == "alt":
        cls += " s-alt"  # tinted band: plain / tinted alternation gives the page rhythm
    return (f'<{tag} data-swarm-section="{section.id}"{mcp} className="s {cls}">\n'
            f'      <div className="container">\n{inner}\n      </div>\n    </{tag}>')


def _component(section: Section, jsx: str, *, client: bool = False, prelude: str = "", body: str = "") -> str:
    head = '"use client";\n\n' if client else ""
    imports = 'import { useState } from "react";\n' if client else ""
    if "<Art" in jsx:
        imports += 'import { Art } from "@/components/Art";\n'
    if (col := _COLLECT.get()) is not None:
        jsx = _lift_fixed_text(jsx, col)
    if col is not None and col.entries:
        # Template: this section's words live in the page's content file (edit text there, not here).
        imports += (f'import {{ content }} from "@/{content_module(col.page)}";\n\n'
                    f"const C = content[{json.dumps(section.id)}];\n")
    return f"""{head}{imports}{prelude}
export function {component_name(section.id)}() {{
{body}  return (
    {jsx}
  );
}}
"""


def _nav(s: Section, c: PageCopy) -> str:
    jsx = f'''<header data-swarm-section="{s.id}" className="s-nav">
      <div className="container nav-row">
        <a href="/" className="nav-logo" data-swarm-id="nav-logo" data-swarm-role="link">{{BRAND}}</a>
        <nav className={{open ? "nav-links is-open" : "nav-links"}} aria-label="Điều hướng chính">
          {{LINKS.map(([label, href]) => <a key={{label}} href={{href}} className="nav-link">{{label}}</a>)}}
        </nav>
{{actions}}
        <button type="button" className="icon-btn nav-toggle" data-swarm-id="nav-menu-toggle" data-swarm-role="button"
          aria-expanded={{open}} aria-label={{open ? "Đóng menu" : "Mở menu"}} onClick={{() => setOpen(!open)}}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
            {{open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}}
          </svg>
        </button>
      </div>
    </header>'''
    body = "  const [open, setOpen] = useState(false);\n"
    if c.shop:
        body += SHOP_STATE
    jsx = jsx.replace("{actions}", SHOP_ACTIONS if c.shop else "")
    if c.shop:
        jsx = jsx.replace('className="s-nav"', 'className="s-nav s-nav-shop"', 1)
    head = 'import { useEffect } from "react";\n' if c.shop else ""
    return _component(s, jsx, client=True, prelude=f"{head}\nconst BRAND = {_js(c.brand)};\nconst LINKS = {_js(c.nav_links)};\n",
                      body=body)


# Store header: search field, account, cart with a live count (grid "Thêm vào giỏ" dispatches cart:add).
SHOP_STATE = """  const [search, setSearch] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [count, setCount] = useState(0);
  useEffect(() => {
    const add = () => setCount((n) => n + 1);
    window.addEventListener("cart:add", add);
    return () => window.removeEventListener("cart:add", add);
  }, []);
"""
SHOP_ACTIONS = """        <div className="nav-actions">
          {search && <input className="input nav-search" type="search" aria-label="Tìm sản phẩm" autoFocus
            data-swarm-id="nav-search-input" data-swarm-role="input" />}
          <button type="button" className="icon-btn" aria-label={search ? "Đóng tìm kiếm" : "Tìm kiếm"} aria-expanded={search}
            data-swarm-id="nav-search" data-swarm-role="button" onClick={() => setSearch(!search)}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></svg>
          </button>
          <a href="#" className="icon-btn" aria-label="Tài khoản" data-swarm-id="nav-account" data-swarm-role="link">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c1.2-3.5 4-5 7-5s5.8 1.5 7 5" /></svg>
          </a>
          <div className="cart-wrap">
            <button type="button" className="icon-btn" aria-label={`Giỏ hàng, ${count} sản phẩm`} aria-expanded={cartOpen}
              data-swarm-id="nav-cart" data-swarm-role="button" onClick={() => setCartOpen(!cartOpen)}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden><path d="M6 8h12l-1 12H7L6 8Z" /><path d="M9 8a3 3 0 0 1 6 0" /></svg>
              {count > 0 && <span className="cart-count">{count}</span>}
            </button>
            {cartOpen && (
              <div className="cart-pop" role="status">
                <p className="t-body">{count ? `Giỏ hàng có ${count} sản phẩm.` : "Giỏ hàng đang trống."}</p>
              </div>
            )}
          </div>
        </div>"""


def _hero_split(s: Section, c: PageCopy) -> str:
    inner = f'''        <div className="split split-7-5">
          <div className="stack">
            <h1 className="t-display">{{{_js(c.headline)}}}</h1>
            <p className="t-lead">{{{_js(c.subhead)}}}</p>
            <div className="row">
              <button type="button" className="btn btn-primary" data-swarm-id="cta-primary" data-swarm-role="button"
                onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
              <a href="#details" className="link-arrow" data-swarm-id="cta-secondary" data-swarm-role="link">{c.cta_secondary} <span aria-hidden>→</span></a>
            </div>
          </div>
          <Art label={{{_js(c.brand, "image_alt")}}} />
        </div>'''
    return _component(s, _root(s, "s-hero", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


def _hero_text(s: Section, c: PageCopy) -> str:
    """Text-only hero: headline, lead and either an email signup (when the reference had one) or a CTA."""
    if any(i.id == "hero-email" for i in s.interactive):
        action = f'''            <form className="stack hero-signup" noValidate onSubmit={{(e) => {{ e.preventDefault(); setState(/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) ? "ok" : "error"); }}}}>
              <label htmlFor="hero-email" className="t-body">{{{_js(c.cta)}}}</label>
              <div className="row">
                <input id="hero-email" type="email" className="input" value={{email}} onChange={{(e) => setEmail(e.target.value)}}
                  placeholder="ban@email.com" data-swarm-id="hero-email" data-swarm-role="input"
                  aria-invalid={{state === "error"}} aria-describedby="hero-email-msg" />
                <button type="submit" className="btn btn-primary" data-swarm-id="hero-signup" data-swarm-role="button">Đăng ký</button>
              </div>
              <p id="hero-email-msg" className="t-caption" role="status">
                {{state === "ok" ? "Đã đăng ký, cảm ơn bạn." : state === "error" ? "Email chưa đúng định dạng." : ""}}
              </p>
            </form>'''
        body = '  const [email, setEmail] = useState("");\n  const [state, setState] = useState<"idle" | "ok" | "error">("idle");\n'
    else:
        action = f'''            <div className="row">
              <button type="button" className="btn btn-primary" data-swarm-id="cta-primary" data-swarm-role="button"
                onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
            </div>'''
        body = "  const [sent, setSent] = useState(false);\n"
    inner = f'''        <div className="stack hero-text">
            <h1 className="t-h1">{{{_js(c.headline)}}}</h1>
            <p className="t-lead">{{{_js(c.subhead)}}}</p>
{action}
        </div>'''
    return _component(s, _root(s, "s-hero-text", inner), client=True, body=body)


def _metrics(s: Section, c: PageCopy) -> str:
    inner = f'''        <dl className="metrics">
          {{FACTS.map(([v, k]) => (
            <div key={{k}} className="metric"><dt className="t-h3">{{v}}</dt><dd className="t-body muted">{{k}}</dd></div>
          ))}}
        </dl>'''
    return _component(s, _root(s, "s-metrics", inner), prelude=f"\nconst FACTS = {_js(c.facts)};\n")


def _z_rows(s: Section, c: PageCopy) -> str:
    inner = '''        <div id="details" className="z-rows">
          {ROWS.map(([title, text], i) => (
            <div key={title} className={i % 2 ? "split split-5-7 is-flipped" : "split split-7-5"}>
              {/* the photo always takes the wide column; ratios alternate so rows do not repeat */}
              <Art label={title} ratio={i % 2 ? "4 / 5" : "3 / 2"} tone={i + 1} sizes="(min-width: 1024px) 58vw, 100vw" />
              <div className="stack"><h2 className="t-h2">{title}</h2><p className="t-lead">{text}</p></div>
            </div>
          ))}
        </div>'''
    return _component(s, _root(s, "s-z", inner), prelude=f"\nconst ROWS = {_js(c.story[:3])};\n")


def _bento(s: Section, c: PageCopy) -> str:
    items = [i.model_dump() for i in (c.cards or c.items)[:4]]
    inner = '''        <div className="section-head"><p className="eyebrow">Bộ sưu tập</p><h2 className="t-h2">Những mẫu được chọn nhiều nhất</h2></div>
        <div className="bento">
          {ITEMS.map((it, i) => (
            <article key={it.name} className={i === 0 || i === 3 ? "product bento-wide" : "product"} data-swarm-id={`collection-card-${i + 1}`} data-swarm-role="card">
              {/* one image height per row, whatever the column span: cards in a row never go ragged */}
              <Art label={it.name} ratio="auto" tone={i + 4} sizes={i === 0 || i === 3 ? "(min-width: 768px) 66vw, 100vw" : "(min-width: 768px) 33vw, 100vw"} />
              <div className="product-meta">
                <div><h3 className="t-h4">{it.name}</h3><p className="t-body muted">{it.note}</p></div>
                {it.price && <span className="t-body price">{it.price}</span>}
              </div>
              <button type="button" className="btn-link" data-swarm-id={`quick-view-trigger-${i + 1}`} data-swarm-role="modal-trigger"
                onClick={() => setActive(i)}>Xem nhanh {it.name.toLowerCase()}</button>
            </article>
          ))}
        </div>
        {active !== null && (
          <div className="modal-scrim" role="presentation" onClick={() => setActive(null)}>
            <div className="modal" role="dialog" aria-modal="true" aria-label={ITEMS[active].name} onClick={(e) => e.stopPropagation()}>
              <h3 className="t-h3">{ITEMS[active].name}</h3>
              <p className="t-body">{ITEMS[active].note}</p>
              <button type="button" className="btn btn-primary" data-swarm-id="quick-view-close" data-swarm-role="button"
                onClick={() => setActive(null)}>Đóng</button>
            </div>
          </div>
        )}'''
    return _component(s, _root(s, "s-bento", inner), client=True, prelude=f"\nconst ITEMS = {_js(items)};\n",
                      body="  const [active, setActive] = useState<number | null>(null);\n")


def _accordion(s: Section, c: PageCopy) -> str:
    inner = '''        <div className="split split-5-7 align-start">
          <div className="section-head"><p className="eyebrow">Hỏi đáp</p><h2 className="t-h2">Điều bạn nên biết trước khi bắt đầu</h2></div>
          <div className="faq">
            {FAQS.map(([q, a], i) => (
              <div key={q} className="faq-item">
                <button type="button" className="faq-q" data-swarm-id={`faq-item-${i + 1}`} data-swarm-role="button"
                  aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
                  <span>{q}</span><span aria-hidden>{open === i ? "−" : "+"}</span>
                </button>
                {open === i && <p className="t-body faq-a">{a}</p>}
              </div>
            ))}
          </div>
        </div>'''
    return _component(s, _root(s, "s-faq", inner), client=True, prelude=f"\nconst FAQS = {_js(c.faqs)};\n",
                      body="  const [open, setOpen] = useState<number | null>(0);\n")


def _band(s: Section, c: PageCopy) -> str:
    inner = f'''        <div className="band">
          <h2 className="t-h2">{{{_js(c.closing)}}}</h2>
          <button type="button" className="btn btn-inverse" data-swarm-id="cta-closing" data-swarm-role="button"
            onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận" : {_js(c.cta)}}}</button>
        </div>'''
    return _component(s, _root(s, "s-band", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


def _footer(s: Section, c: PageCopy) -> str:
    cols = ""
    if c.shop:
        cols = '''
          <nav className="footer-col" aria-label="Hỗ trợ"><p className="t-body">Hỗ trợ</p>
            {["Vận chuyển", "Đổi trả", "Câu hỏi thường gặp"].map((l) => <a key={l} href="#" className="footer-link">{l}</a>)}</nav>
          <nav className="footer-col" aria-label="Chính sách"><p className="t-body">Chính sách</p>
            {["Bảo mật", "Điều khoản", "Liên hệ"].map((l) => <a key={l} href="#" className="footer-link">{l}</a>)}</nav>'''
    inner = f'''        <div className={{{json.dumps("footer-grid footer-shop" if c.shop else "footer-grid")}}}>
          <div className="stack"><strong className="t-h4">{{{_js(c.brand)}}}</strong><p className="t-caption muted">{{{_js(c.footer_line)}}}</p></div>{cols}
          <form className="stack" noValidate onSubmit={{(e) => {{ e.preventDefault(); setState(/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) ? "ok" : "error"); }}}}>
            <label htmlFor="newsletter" className="t-body">Nhận tin mới qua email</label>
            {{/* §6.1: messages sit above the field, where autofill menus and the keyboard cannot cover them */}}
            <p id="newsletter-msg" className="t-caption" role="status">
              {{state === "ok" ? "Đã đăng ký, cảm ơn bạn." : state === "error" ? "Nhập email đầy đủ, ví dụ ten@email.com" : ""}}
            </p>
            <div className="row">
              <input id="newsletter" type="email" className="input" value={{email}} onChange={{(e) => setEmail(e.target.value)}}
                data-swarm-id="footer-newsletter-input" data-swarm-role="input"
                aria-invalid={{state === "error"}} aria-describedby="newsletter-msg" />
              <button type="submit" className="btn btn-primary" data-swarm-id="footer-newsletter-submit" data-swarm-role="button">Đăng ký nhận tin</button>
            </div>
          </form>
        </div>'''
    return _component(s, _root(s, "s-footer", inner, tag="footer"), client=True,
                      body='  const [email, setEmail] = useState("");\n  const [state, setState] = useState<"idle" | "ok" | "error">("idle");\n')


def _hero_overlay(s: Section, c: PageCopy) -> str:
    """Full-bleed photo, dark scrim, copy on the photo (MODERN_UI_REFERENCES: Chamberlain, Marou)."""
    mcp = ' data-swarm-mcp="2d-css"' if s.effect or s.motion else ""
    jsx = f'''<section data-swarm-section="{s.id}"{mcp} className="s-hero-overlay">
      <Art label={{{_js(c.brand, "image_alt")}}} ratio="auto" sizes="100vw" />
      <div className="hero-scrim" aria-hidden />
      <div className="container hero-overlay-copy"><div className="hero-copy-panel">
        <p className="eyebrow on-photo">{{{_js(c.eyebrow or c.brand)}}}</p>
        <h1 className="t-display on-photo">{{{_js(c.headline)}}}</h1>
        <p className="t-lead on-photo">{{{_js(c.subhead)}}}</p>
        <div className="row">
          <button type="button" className="btn btn-inverse" data-swarm-id="cta-primary" data-swarm-role="button"
            onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
          <a href="#details" className="link-arrow on-photo" data-swarm-id="cta-secondary" data-swarm-role="link">{c.cta_secondary} <span aria-hidden>→</span></a>
        </div>
      </div></div>
    </section>'''
    return _component(s, jsx, client=True, body="  const [sent, setSent] = useState(false);\n")


def _hero_editorial(s: Section, c: PageCopy) -> str:
    """Very large headline across the page, copy + actions in a row, wide photo below (Linear)."""
    inner = f'''        <div className="hero-editorial">
          <p className="eyebrow">{{{_js(c.eyebrow or c.brand)}}}</p>
          <h1 className="t-display t-display-wide">{{{_js(c.headline)}}}</h1>
          <div className="hero-editorial-row">
            <p className="t-lead">{{{_js(c.subhead)}}}</p>
            <div className="row">
              <button type="button" className="btn btn-primary" data-swarm-id="cta-primary" data-swarm-role="button"
                onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
              <a href="#details" className="link-arrow" data-swarm-id="cta-secondary" data-swarm-role="link">{c.cta_secondary} <span aria-hidden>→</span></a>
            </div>
          </div>
          <Art label={{{_js(c.brand, "image_alt")}}} ratio="21 / 9" sizes="100vw" />
        </div>'''
    return _component(s, _root(s, "s-hero-editorial", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


def _hero_centered(s: Section, c: PageCopy) -> str:
    """Centred short copy above one large product photo on a quiet panel (Apple product pages)."""
    inner = f'''        <div className="hero-centered">
          <p className="eyebrow">{{{_js(c.eyebrow or c.brand)}}}</p>
          <h1 className="t-display">{{{_js(c.headline)}}}</h1>
          <p className="t-lead">{{{_js(c.subhead)}}}</p>
          <div className="row center">
            <button type="button" className="btn btn-primary" data-swarm-id="cta-primary" data-swarm-role="button"
              onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
            <a href="#details" className="link-arrow" data-swarm-id="cta-secondary" data-swarm-role="link">{c.cta_secondary} <span aria-hidden>→</span></a>
          </div>
          <div className="hero-panel"><Art label={{{_js(c.brand, "image_alt")}}} ratio="16 / 9" sizes="(min-width: 1024px) 80vw, 100vw" /></div>
        </div>'''
    return _component(s, _root(s, "s-hero-centered", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


def _full_image(s: Section, c: PageCopy) -> str:
    # Headline first (readable above the fold), the wide product visual right under it.
    inner = f'''        <div className="hero-image">
          <div className="hero-image-copy stack">
            <h1 className="t-display">{{{_js(c.headline)}}}</h1>
            <p className="t-lead">{{{_js(c.subhead)}}}</p>
            <div className="row">
              <button type="button" className="btn btn-primary" data-swarm-id="cta-primary" data-swarm-role="button"
                onClick={{() => setSent(true)}}>{{sent ? "Đã ghi nhận, chúng tôi sẽ liên hệ" : {_js(c.cta)}}}</button>
            </div>
          </div>
          <Art label={{{_js(c.brand, "image_alt")}}} ratio="16 / 8" />
        </div>'''
    return _component(s, _root(s, "s-hero-image", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


SECTION_TITLES_VI = {"categories": "Danh mục", "related": "Sản phẩm liên quan", "collection": "Nổi bật"}


def _scroller(s: Section, c: PageCopy) -> str:
    rid = s.interactive[0].id if s.interactive else "card"
    inner = f'''        <div className="section-head"><p className="eyebrow">{SECTION_TITLES_VI.get(s.id, "Khám phá")}</p><h2 className="t-h2">Chọn theo nhu cầu của bạn</h2></div>
        <div className="scroller">
          {{CATS.map((name, i) => (
            <a key={{name}} href="#" className="product scroller-item" data-swarm-id={{`{rid}-${{i + 1}}`}} data-swarm-role="card">
              <Art label={{name}} ratio="4 / 5" tone={{i + 1}} sizes="(min-width: 1024px) 25vw, 70vw" /><span className="t-h4">{{name}}</span>
            </a>
          ))}}
        </div>'''
    return _component(s, _root(s, "s-scroller", inner), prelude=f"\nconst CATS = {_js(c.categories)};\n")


def _grid4(s: Section, c: PageCopy) -> str:
    items = [i.model_dump() for i in c.items]
    cats = sorted({i.category for i in c.items if i.category}, key=lambda x: c.categories.index(x) if x in c.categories else 99)
    tabs = ""
    if cats:  # category tabs filter the grid for real (§ interaction sweep)
        tabs = '''
        <div className="tabs" role="tablist" aria-label="Lọc theo danh mục">
          {["Tất cả", ...CATS].map((cat, i) => (
            <button key={cat} type="button" role="tab" aria-selected={active === cat} className={`tab${active === cat ? " is-active" : ""}`}
              data-swarm-id={`category-tab-${i + 1}`} data-swarm-role="tab" onClick={() => setActive(cat)}>{cat}</button>
          ))}
        </div>'''
    inner = '''        <div className="row between align-end"><div className="section-head"><p className="eyebrow">Bán chạy</p><h2 className="t-h2">Khách mua lại nhiều nhất tháng này</h2></div><span className="t-body muted" aria-live="polite">{cart ? `Giỏ hàng: ${cart}` : ""}</span></div>''' + tabs + '''
        <div className="grid-4">
          {ITEMS.filter((it) => active === "Tất cả" || it.category === active).map((it, i) => (
            <article key={it.name} className="product" data-swarm-id={`product-card-${i + 1}`} data-swarm-role="card">
              <div className="product-media">
                <Art label={it.name} ratio="4 / 5" tone={i + 2} sizes="(min-width: 1024px) 25vw, (min-width: 768px) 50vw, 100vw" />
                {it.tag && <span className="product-tag">{it.tag}</span>}
              </div>
              <div className="product-meta"><h3 className="t-h4">{it.name}</h3><span className="t-body price">{it.price}</span></div>
              {it.note && <p className="t-caption muted">{it.note}</p>}
              {/* §6.2: an action repeated on every card is secondary, never a row of primaries */}
              <button type="button" className="btn btn-ghost" data-swarm-id={`add-to-cart-${i + 1}`} data-swarm-role="button"
                onClick={() => { setCart(cart + 1); window.dispatchEvent(new CustomEvent("cart:add")); }}>Thêm vào giỏ</button>
            </article>
          ))}
        </div>'''
    return _component(s, _root(s, "s-grid", inner), client=True,
                      prelude=f"\nconst ITEMS = {_js(items)};\nconst CATS = {_js(cats)};\n",
                      body='  const [cart, setCart] = useState(0);\n  const [active, setActive] = useState("Tất cả");\n')


def _announcement(s: Section, c: PageCopy) -> str:
    text = c.announcement or (" · ".join(c.usp[:2]) if c.usp else f"{c.brand} — {c.cta}")
    # The wrapper stays when dismissed (section order and QA probes keep finding it); only the bar collapses.
    jsx = f'''<div data-swarm-section="{s.id}" role="region" aria-label="Thông báo">
      {{open && (
        <div className="s-announce">
          <p className="t-caption">{{{_js(text, "text")}}}</p>
          <button type="button" className="announce-close" aria-label="Đóng thông báo" data-swarm-id="announcement-close"
            data-swarm-role="button" onClick={{() => setOpen(false)}}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
        </div>
      )}}
    </div>'''
    return _component(s, jsx, client=True, body="  const [open, setOpen] = useState(true);\n")


def _usp(s: Section, c: PageCopy) -> str:
    points = c.usp or [f for _, f in c.facts][:4]
    inner = '''        <ul className="usp">
          {POINTS.map((p) => (
            <li key={p} className="usp-item">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden><path d="m4.5 10.5 3.5 3.5 7.5-8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <span className="t-body">{p}</span>
            </li>
          ))}
        </ul>'''
    return _component(s, _root(s, "s-usp", inner), prelude=f"\nconst POINTS = {_js(points)};\n")


def _picker(s: Section, c: PageCopy) -> str:
    """Pick one option (skin type, need...) -> three recommended products appear beside it."""
    options = c.quiz_options or [cat for cat in c.categories[:3]] or ["Lựa chọn 1", "Lựa chọn 2", "Lựa chọn 3"]
    items = [i.model_dump() for i in c.items]
    inner = '''        <div className="picker">
          <div className="stack">
            <div className="section-head"><p className="eyebrow">Gợi ý cho riêng bạn</p><h2 className="t-h2">Chọn nhu cầu của bạn, chúng tôi gợi ý bộ sản phẩm phù hợp</h2></div>
            <div className="picker-options" role="radiogroup" aria-label="Chọn nhu cầu">
              {OPTIONS.map((o, i) => (
                <button key={o} type="button" role="radio" aria-checked={pick === i} className={`tab${pick === i ? " is-active" : ""}`}
                  data-swarm-id={`quiz-option-${i + 1}`} data-swarm-role="tab" onClick={() => setPick(i)}>{o}</button>
              ))}
            </div>
          </div>
          <div className="picker-result" aria-live="polite">
            {[0, 1, 2].map((k) => {
              const it = ITEMS[(pick + k) % ITEMS.length];
              return (
                <article key={`${pick}-${k}`} className="product picker-card">
                  <Art label={it.name} ratio="1 / 1" tone={pick * 3 + k + 1} sizes="(min-width: 1024px) 16vw, 33vw" />
                  <h3 className="t-body picker-name">{it.name}</h3>
                  <span className="t-caption muted price">{it.price}</span>
                </article>
              );
            })}
          </div>
        </div>'''
    return _component(s, _root(s, "s-picker", inner), client=True,
                      prelude=f"\nconst OPTIONS = {_js(options)};\nconst ITEMS = {_js(items)};\n",
                      body="  const [pick, setPick] = useState(0);\n")


def _split_story(s: Section, c: PageCopy) -> str:
    title, text = c.story[0]
    inner = f'''        <div className="split split-5-7">
          <h2 className="t-h2">{{{_js(title, "title")}}}</h2>
          <p className="t-lead">{{{_js(text, "text")}}}</p>
        </div>'''
    return _component(s, _root(s, "s-story", inner))


def _auth(s: Section, c: PageCopy) -> str:
    inner = '''        <div className="split split-5-7">
          <form className="stack card" noValidate onSubmit={(e) => { e.preventDefault(); setError(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) ? "Email chưa đúng định dạng." : pw.length < 8 ? "Mật khẩu cần ít nhất 8 ký tự." : ""); }}>
            <h1 className="t-h2">Đăng nhập</h1>
            <p className="t-caption" role="alert">{error}</p>
            <label htmlFor="email" className="t-body">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} data-swarm-id="email-input" data-swarm-role="input" />
            <label htmlFor="password" className="t-body">Mật khẩu</label>
            <div className="row">
              <input id="password" type={show ? "text" : "password"} className="input" value={pw} onChange={(e) => setPw(e.target.value)} data-swarm-id="password-input" data-swarm-role="input" />
              <button type="button" className="btn btn-ghost" data-swarm-id="password-toggle" data-swarm-role="button" onClick={() => setShow(!show)}>{show ? "Ẩn" : "Hiện"}</button>
            </div>
            <button type="submit" className="btn btn-primary" data-swarm-id="submit-login" data-swarm-role="button">Đăng nhập</button>
          </form>
          <Art label="Ảnh thương hiệu" />
        </div>'''
    return _component(s, _root(s, "s-auth", inner), client=True,
                      body='  const [email, setEmail] = useState("");\n  const [pw, setPw] = useState("");\n'
                           '  const [show, setShow] = useState(false);\n  const [error, setError] = useState("");\n')


def _title_count(s: Section, c: PageCopy) -> str:
    inner = f'''        <div className="row between">
          <h1 className="t-h1">{{{_js(c.categories[0])}}} <span className="t-body muted">{len(c.items)} sản phẩm</span></h1>
          <label className="row t-body">Sắp xếp
            <select className="input" value={{sort}} onChange={{(e) => setSort(e.target.value)}} data-swarm-id="sort-select" data-swarm-role="input">
              <option value="new">Mới nhất</option><option value="asc">Giá tăng dần</option><option value="desc">Giá giảm dần</option>
            </select>
          </label>
        </div>'''
    return _component(s, _root(s, "s-title", inner), client=True, body='  const [sort, setSort] = useState("new");\n')


def _sidebar_grid(s: Section, c: PageCopy) -> str:
    items = [i.model_dump() | {"cat": c.categories[n % len(c.categories)]} for n, i in enumerate(c.items)]
    inner = '''        <div className="sidebar-grid">
          <button type="button" className="btn btn-ghost filter-toggle" data-swarm-id="filter-drawer-toggle" data-swarm-role="button"
            aria-expanded={drawer} onClick={() => setDrawer(!drawer)}>Bộ lọc</button>
          <aside className={drawer ? "filters is-open" : "filters"} aria-label="Bộ lọc">
            {["Tất cả", ...CATS].map((cat, i) => (
              <button key={cat} type="button" className={cat === filter ? "filter is-active" : "filter"} aria-pressed={cat === filter}
                data-swarm-id={`filter-tab-${i + 1}`} data-swarm-role="filter-tab" onClick={() => setFilter(cat)}>{cat}</button>
            ))}
          </aside>
          <div className="grid-3">
            {ITEMS.filter((it) => filter === "Tất cả" || it.cat === filter).map((it, i) => (
              <a key={it.name} href="#" className="product" data-swarm-id={`product-card-${i + 1}`} data-swarm-role="card">
                <Art label={it.name} ratio="4 / 5" tone={i} /><h3 className="t-h4">{it.name}</h3><p className="t-body muted">{it.price}</p>
              </a>
            ))}
          </div>
        </div>'''
    return _component(s, _root(s, "s-catalog", inner), client=True,
                      prelude=f"\nconst ITEMS = {_js(items)};\nconst CATS = {_js(c.categories)};\n",
                      body='  const [filter, setFilter] = useState("Tất cả");\n  const [drawer, setDrawer] = useState(false);\n')


def _load_more(s: Section, c: PageCopy) -> str:
    inner = '''        <div className="row center">
          <p className="t-body muted" aria-live="polite">Đang hiển thị {shown} sản phẩm</p>
          <button type="button" className="btn btn-ghost" data-swarm-id="load-more" data-swarm-role="button" onClick={() => setShown(shown + 8)}>Hiện thêm 8 sản phẩm</button>
        </div>'''
    return _component(s, _root(s, "s-more", inner), client=True, body="  const [shown, setShown] = useState(8);\n")


def _tabs(s: Section, c: PageCopy) -> str:
    rid = s.interactive[0].id if s.interactive else "tab"
    inner = f'''        <div role="tablist" className="tabs">
          {{TABS.map(([label], i) => (
            <button key={{label}} type="button" role="tab" aria-selected={{tab === i}} className={{tab === i ? "tab is-active" : "tab"}}
              data-swarm-id={{`{rid}-${{i + 1}}`}} data-swarm-role="tab" onClick={{() => setTab(i)}}>{{label}}</button>
          ))}}
        </div>
        <p role="tabpanel" className="t-body tab-panel">{{TABS[tab][1]}}</p>'''
    return _component(s, _root(s, "s-tabs", inner), client=True, prelude=f"\nconst TABS = {_js(c.tabs)};\n",
                      body="  const [tab, setTab] = useState(0);\n")


def _pdp_main(s: Section, c: PageCopy) -> str:
    item = c.items[0]
    inner = f'''        <div className="split split-7-5">
          <div className="stack">
            <Art label={{{_js(item.name, "image_alt")}}} tone={{img}} />
            <div className="row">
              {{[0, 1, 2].map((i) => (
                <button key={{i}} type="button" className={{img === i ? "thumb is-active" : "thumb"}} aria-label={{`Ảnh ${{i + 1}}`}}
                  data-swarm-id={{`gallery-thumb-${{i + 1}}`}} data-swarm-role="button" onClick={{() => setImg(i)}}><Art label="" ratio="1 / 1" tone={{i}} /></button>
              ))}}
            </div>
          </div>
          <div className="stack">
            <h1 className="t-h1">{{{_js(item.name)}}}</h1>
            <p className="t-h3">{{{_js(item.price)}}}</p>
            <div className="row" role="radiogroup" aria-label="Phân loại">
              {{["S", "M", "L"].map((v, i) => (
                <button key={{v}} type="button" role="radio" aria-checked={{variant === v}} className={{variant === v ? "filter is-active" : "filter"}}
                  data-swarm-id={{`variant-picker-${{i + 1}}`}} data-swarm-role="tab" onClick={{() => setVariant(v)}}>{{v}}</button>
              ))}}
            </div>
            {{/* §6.4: the button is never disabled; a missing choice is explained instead */}}
            <p id="variant-msg" className="t-caption" role="status">{{missing && !variant ? "Chọn phân loại trước khi thêm vào giỏ" : ""}}</p>
            <button type="button" className="btn btn-primary" data-swarm-id="add-to-cart" data-swarm-role="button"
              aria-describedby="variant-msg" onClick={{() => (variant ? setAdded(true) : setMissing(true))}}>{{added ? "Đã thêm vào giỏ" : "Thêm vào giỏ"}}</button>
          </div>
        </div>'''
    return _component(s, _root(s, "s-pdp", inner), client=True,
                      body='  const [img, setImg] = useState(0);\n  const [variant, setVariant] = useState("");\n'
                           '  const [added, setAdded] = useState(false);\n  const [missing, setMissing] = useState(false);\n')


def _showcase(s: Section, c: PageCopy) -> str:
    """Feature showcase: heading left, explanation right, a wide product visual underneath."""
    title, text = c.story[0]
    inner = f'''        <div className="split split-5-7">
          <h2 className="t-h2">{{{_js(title, "title")}}}</h2>
          <div className="stack">
            <p className="t-lead">{{{_js(text, "text")}}}</p>
            <a href="#" className="link-arrow" data-swarm-id="{s.id}-more" data-swarm-role="link">Tìm hiểu thêm <span aria-hidden>→</span></a>
          </div>
        </div>
        <div className="showcase-media"><Art label={{{_js(title, "image_alt")}}} ratio="16 / 7" tone={{1}} /></div>'''
    return _component(s, _root(s, "s-showcase", inner))


def _testimonials(s: Section, c: PageCopy) -> str:
    inner = '''        <h2 className="t-h2">Khách hàng nói gì</h2>
        <div className="quotes">
          {QUOTES.map(([quote, who], i) => (
            <figure key={i} className="card quote">
              <blockquote className="t-h4">“{quote}”</blockquote>
              <figcaption className="t-caption muted">{who}</figcaption>
            </figure>
          ))}
        </div>'''
    return _component(s, _root(s, "s-quotes", inner), prelude=f"\nconst QUOTES = {_js(c.quotes[:2] or [('Chưa có đánh giá', 'Thêm đánh giá thật ở bước bàn giao')])};\n")


def _text_cards(s: Section, c: PageCopy) -> str:
    """A row of text cards (changelog, feature list) when the reference shows no visuals."""
    inner = '''        <div className="text-cards">
          {ROWS.map(([title, text]) => (
            <article key={title} className="text-card">
              <h3 className="t-h4">{title}</h3>
              <p className="t-body muted">{text}</p>
            </article>
          ))}
        </div>'''
    return _component(s, _root(s, "s-text-cards", inner), prelude=f"\nconst ROWS = {_js(c.story[:3])};\n")


def _gallery(s: Section, c: PageCopy) -> str:
    """Image gallery: one compact grid with as many tiles as the reference showed (3 to 12)."""
    tiles = max(3, min(s.count or 6, 12))
    inner = f'''        <h2 className="t-h2">{{{_js(c.story[0][0] if c.story else "Thư viện hình ảnh")}}}</h2>
        <div className="gallery">
          {{Array.from({{ length: {tiles} }}, (_, i) => (
            <figure key={{i}} className="gallery-tile"><Art label={{`Hình ${{i + 1}}`}} ratio="4 / 3" tone={{i}} /></figure>
          ))}}
        </div>'''
    return _component(s, _root(s, "s-gallery", inner))


def _logo_strip(s: Section, c: PageCopy) -> str:
    """"As featured on" / client logos: a short caption over a row of marks (placeholders until real logos)."""
    marks = max(3, min(s.count or 4, 8))
    if "marquee" in s.motion:  # the reference slides its logos: a duplicated track that loops seamlessly
        inner = f'''        <p className="t-caption muted logo-caption">Được nhắc đến trên</p>
        <div className="marquee" aria-label="Đối tác và báo chí">
          <ul className="logo-strip marquee-track">
            {{Array.from({{ length: {marks * 2} }}, (_, i) => (
              <li key={{i}} className="logo-mark t-h4" aria-hidden={{i >= {marks} || undefined}}>Logo {{(i % {marks}) + 1}}</li>
            ))}}
          </ul>
        </div>'''
        return _component(s, _root(s, "s-logos", inner))
    inner = f'''        <p className="t-caption muted logo-caption">Được nhắc đến trên</p>
        <ul className="logo-strip" aria-label="Đối tác và báo chí">
          {{Array.from({{ length: {marks} }}, (_, i) => (
            <li key={{i}} className="logo-mark t-h4">Logo {{i + 1}}</li>
          ))}}
        </ul>'''
    return _component(s, _root(s, "s-logos", inner))


def _list_rows(s: Section, c: PageCopy) -> str:
    """A stacked list of one-line entries (posts + dates, work history + periods) with a show-all control."""
    rows = c.rows or [(t, "") for t, _ in c.story]
    title = SECTION_TITLES_VI.get(s.id, "Bài viết" if any(ch.isdigit() for _, m in rows for ch in m) else "Danh sách")
    # The reference shows a preview image when a row is hovered: decorative, hidden from assistive tech.
    preview = ('''
                <span className="row-preview" aria-hidden="true"><Art label="" ratio="4 / 3" tone={i} /></span>'''
               if "hover-image" in s.motion else "")
    inner = f'''        <h2 className="t-caption muted list-title">{title}</h2>
        <ul className="list-rows">
          {{(all ? ROWS : ROWS.slice(0, 5)).map(([entry, meta], i) => (
            <li key={{entry}}>
              <a href="#" className="list-row" data-swarm-id={{`list-row-${{i + 1}}`}} data-swarm-role="link">
                <span className="t-body">{{entry}}</span><span className="list-dots" aria-hidden />
                <span className="t-caption muted">{{meta}}</span>{preview}
              </a>
            </li>
          ))}}
        </ul>
        {{ROWS.length > 5 && (
          <button type="button" className="btn btn-ghost list-more" data-swarm-id="list-more" data-swarm-role="button"
            aria-expanded={{all}} onClick={{() => setAll(!all)}}>{{all ? "Thu gọn" : `Xem tất cả (${{ROWS.length}})`}}</button>
        )}}'''
    return _component(s, _root(s, "s-list", inner), client=True, prelude=f"\nconst ROWS = {_js(rows[:10])};\n",
                      body="  const [all, setAll] = useState(false);\n")


BY_ID = {"site-header": _nav, "site-footer": _footer, "auth": _auth, "product-main": _pdp_main}
BY_STRUCTURE = {
    "sticky-bar": _nav, "split-7-5": _hero_split, "inline-metrics": _metrics, "alternating-z": _z_rows,
    "bento": _bento, "accordion": _accordion, "full-bleed-band": _band, "footer-columns": _footer,
    "full-bleed-image": _full_image, "hero-overlay": _hero_overlay,
    "hero-editorial": _hero_editorial, "hero-centered": _hero_centered, "horizontal-scroller": _scroller, "grid-4": _grid4, "split-5-7": _split_story,
    "title-with-count": _title_count, "sidebar-grid-4": _sidebar_grid, "inline-controls": _load_more, "tabs": _tabs,
    "feature-showcase": _showcase, "testimonials": _testimonials, "text-cards": _text_cards,
    "announcement-bar": _announcement, "usp-strip": _usp, "picker-recommend": _picker,
    "gallery": _gallery, "logo-strip": _logo_strip, "hero-text": _hero_text, "list-rows": _list_rows,
}


def _measured_or(template):
    """Clone: the section from the reference's own layout; its template when that layout cannot be built."""
    def render(s: Section, c: PageCopy) -> str:
        built = render_measured(s, c, _js)
        if built is None:
            if template is None:
                raise ValueError(f"no Next.js template for structure {s.structure!r}")
            return template(s, c)
        jsx, css = built
        inner = f"{jsx}\n        <style>{{{json.dumps(css)}}}</style>"
        band = " s-band" if (s.layout_box or {}).get("band") else ""  # the reference painted it the other way round
        return _component(s, _root(s, "s-measured" + band, inner))
    return render


def render_section(section: Section, copy: PageCopy, page: str = "", content: dict | None = None) -> WorkspaceFile:
    """One section component. With `content` (a dict), the section's copy is moved out of the code:
    `content[section.id]` receives it and the component reads it from the page's content file."""
    if section.reference.get('html') and section.reference.get('css'):
        from chromaswarm.developer.reference_dom import render
        if content is not None:
            content[section.id] = {}  # Native reference copy stays beside its DOM in this component.
        folder = f"components/sections/{page}" if page else "components/sections"
        return WorkspaceFile(path=f"{folder}/{component_name(section.id)}.tsx", content=render(section, page))
    fn = BY_ID.get(section.id) or BY_STRUCTURE.get(section.structure)
    if measurable(section):
        fn = _measured_or(fn)
    if section.design:
        # Clone: the section understood and built as a real component, numbers from the reference's DESIGN.md
        # (developer/clone_templates.py); other kinds fall back to the measured / structure renderer above.
        from chromaswarm.developer import clone_templates
        fallback = fn
        fn = lambda s, c: clone_templates.render(s, c) or (fallback(s, c) if fallback else None)  # noqa: E731
    if fn is None:
        raise ValueError(f"no Next.js template for structure {section.structure!r}")
    folder = f"components/sections/{page}" if page else "components/sections"
    col = _Collector(page, copy) if content is not None else None
    token = _COLLECT.set(col)
    try:
        code = localize_code(fn(section, copy), copy.lang)  # fixed UI words in the page's language
    finally:
        _COLLECT.reset(token)
    if col is not None:
        content[section.id] = localize_value(col.entries, copy.lang)
    return WorkspaceFile(path=f"{folder}/{component_name(section.id)}.tsx", content=code)


CONTENT_HEAD = """// NỘI DUNG TRANG — sửa chữ của bạn ngay trong file này, rồi lưu lại.
// - Mỗi khối là một phần của trang, theo thứ tự từ trên xuống.
// - Chỉ sửa phần chữ trong dấu ngoặc kép; giữ nguyên dấu ngoặc, dấu phẩy và tên bên trái dấu hai chấm.
// - Chữ mẫu do Chroma điền sẵn: thay bằng nội dung thật của bạn.
// Ảnh: xem content/images.ts. Hướng dẫn đầy đủ: HUONG_DAN.md.
"""


_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _ts(value, indent: int = 2) -> str:
    """Readable TypeScript literal: short lists on one line, objects one key per line, bare keys."""
    pad, inner = " " * indent, " " * (indent + 2)
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = [f"{inner}{k if _IDENT.match(k) else json.dumps(k)}: {_ts(v, indent + 2)}," for k, v in value.items()]
        return "{\n" + "\n".join(rows) + f"\n{pad}}}"
    if isinstance(value, list):
        flat = "[" + ", ".join(_ts(v, indent + 2) for v in value) + "]"
        if len(flat) <= 90 and "\n" not in flat:
            return flat
        return "[\n" + "\n".join(f"{inner}{_ts(v, indent + 2)}," for v in value) + f"\n{pad}]"
    return json.dumps(value, ensure_ascii=False)


def content_file(page: str, sections: list[tuple[Section, dict]]) -> WorkspaceFile:
    """The page's content file: every section's words, in page order, labelled by section name."""
    blocks = []
    for section, entries in sections:
        if not entries:
            continue
        blocks.append(f"  // {section.name}\n  {json.dumps(section.id)}: {_ts(entries, 2)},")
    return WorkspaceFile(path=f"{content_module(page)}.ts",
                         content=CONTENT_HEAD + "\nexport const content = {\n" + "\n".join(blocks) + "\n};\n")


# ----------------------------------------------------------------- base.css

BASE_CSS = """/* Generated by ChromaSwarm. Every value is a token from tokens.css or a step of the 8pt scale. */
*, *::before, *::after { box-sizing: border-box; }
* { margin: 0; }
html { -webkit-text-size-adjust: 100%; }
body { background: var(--bg-primary); color: var(--text-primary); font-family: var(--font-body);
  font-size: var(--text-body); line-height: 1.55; -webkit-font-smoothing: antialiased; }
img { display: block; max-width: 100%; }
a { color: inherit; }
p a, li a { color: var(--action-ink); text-decoration: underline; text-underline-offset: 3px; }  /* §2.7: never colour alone */
strong, b { font-weight: 600; }  /* §2.2: two weights per family (400 / 600) */
button, input, select { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--action); outline-offset: 2px; }

.container { max-width: var(--container-max); margin-inline: auto; padding-inline: var(--gutter); }
.s { padding-block: var(--section-y); }
.stack { display: flex; flex-direction: column; gap: 16px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
.between { justify-content: space-between; }
.center { justify-content: center; }
.muted { color: var(--text-secondary); }

.t-display, .t-h1, .t-h2, .t-h3, .t-h4 { font-family: var(--font-heading); font-weight: 600; text-wrap: balance; }
.t-display { font-size: var(--text-display); line-height: 1.05; letter-spacing: -0.03em; max-width: 16ch; }
.t-h1 { font-size: var(--text-h1); line-height: 1.12; letter-spacing: -0.015em; }
.t-h2 { font-size: var(--text-h2); line-height: 1.15; letter-spacing: -0.01em; }
.t-h3 { font-size: var(--text-h3); line-height: 1.2; }
.t-h4 { font-size: var(--text-h4); line-height: 1.25; }
.t-lead { font-size: var(--text-lead); line-height: 1.5; max-width: 60ch; color: var(--text-secondary); }
.t-body { font-size: var(--text-body); max-width: 65ch; }
.t-caption { font-size: var(--text-caption); line-height: 1.4; max-width: 65ch; }

.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: 12px 24px;
  border: 1px solid transparent; border-radius: var(--radius-md); font-size: var(--text-body); font-weight: 600;
  cursor: pointer; text-decoration: none;
  transition: background-color var(--duration) var(--ease), border-color var(--duration) var(--ease), transform 160ms var(--ease); }
.btn:active { transform: scale(0.98); }
/* §6.2 three button weights: primary (filled) · secondary (outlined, >= 3:1) · tertiary (underlined link).
   All in --action: the brand accent (tech / bold presets) or near-black (luxury / warm presets, §2.1). */
.btn-primary { background: var(--action); color: var(--action-fg); }
.btn-primary:hover { background: var(--action-hover); }
.btn-ghost { background: transparent; border-color: var(--action-ink); color: var(--action-ink); }
.btn-ghost:hover { background: var(--bg-surface); }
.btn-inverse { background: var(--band-action); color: var(--band-action-fg); }
.btn-inverse:hover { filter: brightness(1.08); }
.s-hero-overlay .btn-inverse { background: oklch(0.985 0 0); color: oklch(0.2 0.01 60); }  /* light on photos */
.btn-link { display: inline-flex; align-items: center; align-self: flex-start; min-height: 48px; padding: 0; border: 0;
  background: none; color: var(--action-ink); font-weight: 600; text-decoration: underline; text-underline-offset: 3px;
  cursor: pointer; transition: opacity var(--duration) var(--ease); }
.btn-link:hover { opacity: 0.72; }
.product .btn-link { color: var(--text-primary); }  /* quiet tertiary action on product cards (critic: blue links look raw) */
.icon-btn { flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; padding: 0;
  border: 0; border-radius: var(--radius-sm); background: none; cursor: pointer;
  transition: background-color var(--duration) var(--ease); }
.icon-btn:hover { background: var(--bg-surface); }
.link-arrow { display: inline-flex; gap: 8px; align-items: center; min-height: 48px; font-weight: 600;
  color: var(--action-ink); text-decoration: underline; text-underline-offset: 3px; }
.link-arrow span { transition: transform var(--duration) var(--ease); }
.link-arrow:hover { text-decoration-thickness: 2px; }
.link-arrow:hover span { transform: translateX(4px); }
.input { min-height: 48px; padding: 12px 16px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-elevated); flex: 1; min-width: 0; }
.input:hover { border-color: var(--text-secondary); }
.input[aria-invalid="true"] { border-color: var(--danger); }

.card { display: flex; flex-direction: column; gap: 16px; padding: var(--card-padding); background: var(--bg-surface);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); text-decoration: none;
  transition: border-color var(--duration) var(--ease), transform var(--duration) var(--ease); }
a.card:hover, article.card:hover { border-color: var(--text-secondary); transform: translateY(-4px); }
.art { width: 100%; height: auto; object-fit: cover; border-radius: var(--radius-md); background: var(--bg-surface); }

/* Product cards (MODERN_UI_REFERENCES pattern 3): no box, no border; the photo carries the card. */
.product { display: flex; flex-direction: column; gap: 12px; color: inherit; text-decoration: none; }
.product > .art { transition: filter var(--duration) var(--ease); }
.product:hover > .art { filter: brightness(0.94); }
.product-meta { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
.grid-4 .product-meta { flex-direction: column; align-items: flex-start; gap: 4px; }  /* price under the name: */
.grid-4 .product-meta h3 { min-height: calc(2 * 1.25em); display: -webkit-box; -webkit-line-clamp: 2;   /* every card */
  -webkit-box-orient: vertical; overflow: hidden; }                                                          /* aligns */
.grid-4 .product > .btn { margin-top: auto; }  /* buttons share one baseline whatever the note length */
article.product { transition: transform var(--duration) var(--ease); }
article.product:hover { transform: translateY(-2px); }  /* one- and two-line names keep prices on one baseline */
.price { white-space: nowrap; font-variant-numeric: tabular-nums; }
.section-head { display: flex; flex-direction: column; gap: 8px; }
.eyebrow { font-size: var(--text-caption); font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--text-secondary); }
.align-start { align-items: start; }
.align-end { align-items: flex-end; }

.split { display: grid; gap: var(--grid-gap); align-items: center; }
@media (min-width: 1024px) {
  .split-7-5 { grid-template-columns: 7fr 5fr; }
  .split-5-7 { grid-template-columns: 5fr 7fr; }
  .split.is-flipped > :first-child { order: 2; }
}

.s-nav { position: sticky; top: 0; z-index: 10; background: color-mix(in srgb, var(--bg-primary) 85%, transparent);
  backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-subtle); }
.nav-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; column-gap: 24px; min-height: 64px; }
.nav-logo { font-family: var(--font-heading); font-size: var(--text-h4); text-decoration: none; min-height: 48px;
  display: inline-flex; align-items: center; }
.nav-links { display: none; gap: 32px; }
.nav-links.is-open { display: flex; flex-direction: column; position: absolute; inset: 64px 0 auto 0; padding: 24px var(--gutter);
  background: var(--bg-primary); border-bottom: 1px solid var(--border-subtle); }
.nav-logo { transition: color var(--duration) var(--ease); }
.nav-logo:hover { text-decoration: underline; text-underline-offset: 4px; }
.nav-link { text-decoration: none; min-height: 48px; display: inline-flex; align-items: center; white-space: nowrap; }
.nav-link:hover { text-decoration: underline; text-underline-offset: 4px; }
@media (min-width: 768px) {
  .nav-links, .nav-links.is-open { display: flex; flex-direction: row; position: static; padding: 0; border: 0; background: none; }
  .nav-toggle { display: none; }
}

.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--grid-gap);
  border-block: 1px solid var(--border-subtle); padding-block: 32px; }
.metric dd { margin-top: 8px; }
.s-metrics { padding-block: calc(var(--section-y) / 2); }  /* a facts strip is not a full chapter */
.z-rows { display: flex; flex-direction: column; gap: var(--section-y); }
.bento { display: grid; gap: 32px 24px; margin-top: 32px; }
.bento .art { height: clamp(240px, 26vw, 400px); }  /* same image height across a row, whatever the span */
@media (min-width: 768px) { .bento { grid-template-columns: repeat(3, 1fr); } .bento-wide { grid-column: span 2; }
  .bento > :nth-child(3):last-child { grid-column: 1 / -1; } }  /* 3 cards: the last one closes the row */
.modal-scrim { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 24px;
  background: color-mix(in srgb, var(--text-primary) 45%, transparent); }
.modal { display: flex; flex-direction: column; gap: 16px; width: min(480px, 100%); padding: 32px;
  background: var(--bg-elevated); border-radius: var(--radius-lg); }
.faq { display: flex; flex-direction: column; border-top: 1px solid var(--border-subtle); }
.faq-item { border-bottom: 1px solid var(--border-subtle); }
.faq-q { display: flex; justify-content: space-between; gap: 16px; width: 100%; min-height: 64px; padding-block: 16px;
  background: none; border: 0; text-align: left; font-size: var(--text-lead); cursor: pointer; }
.faq-q:hover > span:first-child { text-decoration: underline; text-underline-offset: 4px; }
.faq-a { padding-bottom: 24px; color: var(--text-secondary); }
.s-band { background: var(--text-primary); color: var(--bg-primary); }  /* neutral: the accent is for actions only */
.band { display: flex; flex-direction: column; align-items: flex-start; gap: 32px; }
.s-footer { border-top: 1px solid var(--border-subtle); }
.footer-grid { display: grid; gap: var(--grid-gap); }
@media (min-width: 768px) { .footer-grid { grid-template-columns: 1fr 1fr; } }
.s-alt { background: var(--bg-surface); }
/* Store header actions + footer columns. With icons the menu collapses below 1024px, not 768px. */
.nav-logo { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 767px) {  /* long brand names wrap onto two short lines instead of being cut ("LUMIÈRE BOT…") */
  .s-nav-shop .nav-logo { font-size: var(--text-body); line-height: 1.15; white-space: normal; overflow: visible; }
}
@media (min-width: 768px) and (max-width: 1023px) {
  .s-nav-shop .nav-links { display: none; }
  .s-nav-shop .nav-links.is-open { display: flex; flex-direction: column; position: absolute; inset: 64px 0 auto 0;
    padding: 24px var(--gutter); background: var(--bg-primary); border-bottom: 1px solid var(--border-subtle); }
  .s-nav-shop .nav-toggle { display: inline-flex; }
}
@media (max-width: 767px) {
  .s-nav-shop .nav-row { gap: 8px; }
  .s-nav-shop [data-swarm-id="nav-account"] { display: none; }  /* account lives in the menu on phones */
}
.nav-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.nav-actions .icon-btn { position: relative; color: inherit; }
.nav-search { width: min(240px, 40vw); min-height: 48px; padding: 8px 12px; }
.cart-wrap { position: relative; }
.cart-count { position: absolute; top: 6px; right: 4px; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 9999px;
  display: grid; place-items: center; background: var(--action); color: var(--action-fg); font-size: 11px; font-weight: 600; }
.cart-pop { position: absolute; right: 0; top: calc(100% + 8px); z-index: 20; width: 240px; padding: 16px;
  background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); box-shadow: var(--shadow-lg); }
@media (max-width: 767px) { .nav-search { position: absolute; left: var(--gutter); right: var(--gutter); top: 72px; width: auto; } }
.footer-col { display: flex; flex-direction: column; gap: 4px; }
.footer-col > p { font-weight: 600; margin-bottom: 4px; }
.footer-link { min-height: 48px; display: inline-flex; align-items: center; color: var(--text-secondary); text-decoration: none; }
.footer-link:hover { color: var(--text-primary); text-decoration: underline; text-underline-offset: 3px; }
@media (min-width: 1024px) { .footer-shop { grid-template-columns: 1.4fr 1fr 1fr 1.6fr; } }

/* Hero repertoire (planner.hero_structure) */
.s-hero-overlay { position: relative; display: flex; align-items: flex-end; min-height: min(88vh, 860px);
  overflow: hidden; isolation: isolate; background: oklch(0.2 0.01 60); }  /* dark until the photo paints */
.s-hero-overlay > .art { position: absolute; inset: 0; width: 100%; height: 100%; border-radius: 0; z-index: -2; }
.hero-scrim { position: absolute; inset: 0; z-index: -1;  /* §2.2 text on photos: scrim keeps the copy legible */
  background: linear-gradient(to top, oklch(0.16 0.01 60 / 0.82) 0%, oklch(0.16 0.01 60 / 0.45) 45%, oklch(0.16 0.01 60 / 0) 75%); }
.hero-overlay-copy { padding-block: 96px 64px; width: 100%; }
.hero-copy-panel { display: flex; flex-direction: column; gap: 24px; }
.on-photo { color: oklch(0.985 0 0); text-shadow: 0 1px 2px oklch(0 0 0 / 0.25); }
.hero-overlay-copy .t-lead { max-width: 52ch; }
.link-arrow.on-photo { color: oklch(0.985 0 0); }
.hero-editorial { display: flex; flex-direction: column; gap: 32px; }
.t-display-wide { max-width: 18ch; }
.hero-editorial-row { display: grid; gap: 24px; align-items: end; }
.hero-editorial > .art { border-radius: var(--radius-lg); margin-top: 16px; }
@media (min-width: 1024px) { .hero-editorial-row { grid-template-columns: 7fr 5fr; } .hero-editorial-row .row { justify-content: flex-end; } }
.hero-centered { display: flex; flex-direction: column; align-items: center; gap: 24px; text-align: center; }
.hero-centered .t-display { max-width: 24ch; }  /* centred headings stay <= 2 lines (§ anti-slop 3) */
.hero-centered .t-lead { max-width: 56ch; }
.hero-panel { width: 100%; margin-top: 24px; padding: clamp(16px, 4vw, 48px); background: var(--bg-surface);
  border-radius: var(--radius-lg); }
@media (max-width: 767px) { .hero-centered { align-items: flex-start; text-align: left; } .hero-centered .row { justify-content: flex-start; } }
.hero-image { display: flex; flex-direction: column; gap: var(--grid-gap); }
.hero-image-copy { align-items: flex-start; }
.showcase-media { margin-top: var(--grid-gap); }
.quotes { display: grid; gap: 24px; margin-top: 32px; }
@media (min-width: 768px) { .quotes { grid-template-columns: repeat(2, 1fr); } }
.quote blockquote { margin: 0; line-height: 1.35; }
.gallery { display: grid; gap: 16px; margin-top: 32px; grid-template-columns: repeat(2, 1fr); }
@media (min-width: 1024px) { .gallery { grid-template-columns: repeat(3, 1fr); } }
.gallery-tile { margin: 0; }
.hero-text { max-width: 72ch; }
.hero-signup .input { flex: 1; min-width: 200px; }
.logo-caption, .list-title { text-transform: uppercase; letter-spacing: 0.08em; }
.logo-strip { list-style: none; padding: 0; margin-top: 16px; display: grid; gap: 16px; grid-template-columns: repeat(2, 1fr); }
@media (min-width: 768px) { .logo-strip { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); } }
.logo-mark { display: grid; place-items: center; min-height: 64px; border-radius: var(--radius-md);
  background: var(--bg-surface); color: var(--text-secondary); }
.list-rows { list-style: none; padding: 0; margin-top: 16px; display: grid; }
.list-row { display: flex; align-items: baseline; gap: 16px; min-height: 48px; padding: 8px 0; text-decoration: none; }
.list-row:hover .t-body { color: var(--accent); }
.list-row:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.list-dots { flex: 1; border-bottom: 1px dotted var(--border-subtle); min-width: 16px; }
.list-more { margin-top: 24px; }
.marquee-track.logo-strip { grid-template-columns: none; gap: 16px; }
.marquee-track .logo-mark { min-width: 160px; }
.text-cards { display: grid; gap: var(--grid-gap); }
@media (min-width: 768px) { .text-cards { grid-template-columns: repeat(3, 1fr); } }
.text-card { display: flex; flex-direction: column; gap: 8px; padding-top: 24px; border-top: 1px solid var(--border-subtle); }
.scroller { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(240px, 1fr); gap: 24px; overflow-x: auto;
  margin-top: 32px; padding-bottom: 8px; scroll-snap-type: x mandatory; }
.scroller-item { scroll-snap-align: start; }
.grid-4, .grid-3 { display: grid; gap: 24px; margin-top: 32px; }
@media (min-width: 768px) { .grid-4 { grid-template-columns: repeat(2, 1fr); } .grid-3 { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1024px) { .grid-4 { grid-template-columns: repeat(4, 1fr); } .grid-3 { grid-template-columns: repeat(3, 1fr); } }
.sidebar-grid { display: grid; gap: var(--grid-gap); }
.filters { display: none; flex-direction: column; gap: 8px; }
.filters.is-open { display: flex; }
@media (min-width: 1024px) {
  .sidebar-grid { grid-template-columns: 240px 1fr; align-items: start; }
  .filters { display: flex; position: sticky; top: 96px; }
  .filter-toggle { display: none; }
}
.filter, .tab { min-height: 48px; padding: 12px 16px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: transparent; text-align: left; cursor: pointer; transition: background-color var(--duration) var(--ease); }
.filter:hover, .tab:hover { background: var(--bg-surface); }
.filter.is-active, .tab.is-active { background: var(--text-primary); color: var(--bg-primary); border-color: var(--text-primary); }
.filter.is-active:hover, .tab.is-active:hover { background: color-mix(in srgb, var(--text-primary) 85%, var(--bg-primary)); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tab-panel { margin-top: 24px; }
.thumb { width: 80px; padding: 0; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); background: none; cursor: pointer; }
.thumb:hover, .thumb.is-active { border-color: var(--text-primary); }

/* Brief sections: announcement bar, promise strip, picker */
.s-announce { position: relative; display: flex; align-items: center; justify-content: center; min-height: 40px;
  padding: 8px 48px; background: var(--text-primary); color: var(--bg-primary); text-align: center; }
.announce-close { position: absolute; right: 8px; top: 50%; translate: 0 -50%; display: grid; place-items: center;
  width: 48px; height: 40px; border: 0; background: none; color: inherit; cursor: pointer; opacity: 0.8;
  transition: opacity var(--duration) var(--ease); }
.announce-close:hover { opacity: 1; }
.s-usp { padding-block: 32px; border-block: 1px solid var(--border-subtle); }
.usp { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px 24px; padding: 0; list-style: none; }
.usp-item { display: flex; align-items: center; gap: 12px; }
.usp-item svg { flex-shrink: 0; color: var(--action-ink); }
.picker { display: grid; gap: var(--grid-gap); align-items: center; }
@media (min-width: 1024px) { .picker { grid-template-columns: 5fr 7fr; } }
.picker-options { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.picker-result { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.picker-name { font-weight: 600; }  /* h3 defaults to 700: stay within the two weights (§2.2) */
.picker-card { animation: picker-in 400ms var(--ease) both; }
.picker-card:nth-child(2) { animation-delay: 60ms; } .picker-card:nth-child(3) { animation-delay: 120ms; }
@keyframes picker-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.product-media { position: relative; }
.product-tag { position: absolute; top: 12px; left: 12px; padding: 4px 8px; border-radius: var(--radius-sm);
  background: var(--bg-elevated); color: var(--text-primary); font-size: var(--text-caption); font-weight: 600; }
.s-grid .tabs { margin-top: 24px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 1ms !important; animation-duration: 1ms !important; }
}
"""
