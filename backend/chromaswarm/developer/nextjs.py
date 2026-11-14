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

import json
import urllib.parse

from pydantic import BaseModel

from chromaswarm.agents.planner import Section
from chromaswarm.developer.content import PageCopy
from chromaswarm.engines.design_spec import DesignSpec

NEXT_VERSION = "16.4.5"
REACT_VERSION = "19.3.0"


class WorkspaceFile(BaseModel):
    path: str  # relative to the workspace app root
    content: str


def component_name(section_id: str) -> str:
    return "".join(p.capitalize() for p in section_id.replace("_", "-").split("-")) + "Section"


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# ----------------------------------------------------------------- scaffold

def scaffold(project: str, spec: DesignSpec, photos: list[str] | None = None) -> list[WorkspaceFile]:
    fonts = sorted({spec.typography.heading_font, spec.typography.body_font})
    families = "&".join("family=" + urllib.parse.quote_plus(f) + ":wght@400;500;600;700" for f in fonts)
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
import "./motion.css";
import "./heal.css";

export const metadata: Metadata = {{ title: {_js(project)} }};

export default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?{families}&display=swap" />
      </head>
      <body>{{children}}</body>
    </html>
  );
}}
'''),
        WorkspaceFile(path="app/base.css", content=BASE_CSS),
        heal_file([]),
        motion_file([]),
        WorkspaceFile(path="components/Art.tsx", content=art_component(spec, photos or [])),
    ]


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
    """Tonal image placeholders as data-URI SVG, so pages never show grey boxes
    and every <img> has naturalWidth > 0 for the B11 image check."""
    p = spec.palette
    a, s, e = p.get("accent").hex, p.get("bg-surface").hex, p.get("bg-elevated").hex
    t = p.get("text-secondary").hex
    variants = []
    for i, (c1, c2) in enumerate([(a, s), (s, a), (e, t)]):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1000" viewBox="0 0 800 1000">'
               f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>'
               f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs><rect width="800" height="1000" fill="url(#g)"/>'
               f'<circle cx="{560 - i * 120}" cy="{360 + i * 90}" r="{220 - i * 30}" fill="{c2}" opacity=".35"/>'
               f'<rect x="120" y="{620 - i * 40}" width="560" height="2" fill="{c1}" opacity=".5"/></svg>')
        variants.append("data:image/svg+xml;utf8," + urllib.parse.quote(svg))
    return f'''const ART = {_js(variants)};
// Clone mode on the user's own site: their real photos come first.
const PHOTOS: string[] = {_js(photos or [])};

type Props = {{ label: string; ratio?: string; tone?: number }};

/** Real photos when the user supplied them, otherwise tonal placeholders in the page's own palette. */
export function Art({{ label, ratio = "4 / 5", tone = 0 }}: Props) {{
  const src = PHOTOS.length ? PHOTOS[tone % PHOTOS.length] : ART[tone % ART.length];
  return <img className="art" src={{src}} alt={{label}} style={{{{ aspectRatio: ratio }}}} />;
}}
'''


# ----------------------------------------------------------------- sections

def _root(section: Section, cls: str, inner: str, tag: str = "section") -> str:
    mcp = ' data-swarm-mcp="2d-css"' if section.effect else ""  # B8.1 target (FRONTEND_STANDARDS §4.4)
    return (f'<{tag} data-swarm-section="{section.id}"{mcp} className="s {cls}">\n'
            f'      <div className="container">\n{inner}\n      </div>\n    </{tag}>')


def _component(section: Section, jsx: str, *, client: bool = False, prelude: str = "", body: str = "") -> str:
    head = '"use client";\n\n' if client else ""
    imports = 'import { useState } from "react";\n' if client else ""
    if "<Art" in jsx:
        imports += 'import { Art } from "@/components/Art";\n'
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
        <button type="button" className="btn btn-ghost nav-toggle" data-swarm-id="nav-menu-toggle" data-swarm-role="button"
          aria-expanded={{open}} aria-label="Mở menu" onClick={{() => setOpen(!open)}}>{{open ? "Đóng" : "Menu"}}</button>
      </div>
    </header>'''
    return _component(s, jsx, client=True, prelude=f"\nconst BRAND = {_js(c.brand)};\nconst LINKS = {_js(c.nav_links)};\n",
                      body="  const [open, setOpen] = useState(false);\n")


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
          <Art label={{{_js(c.brand)}}} />
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
            <div key={title} className={i % 2 ? "split split-5-7 is-flipped" : "split split-5-7"}>
              <Art label={title} ratio="3 / 2" tone={i + 1} />
              <div className="stack"><h2 className="t-h2">{title}</h2><p className="t-body">{text}</p></div>
            </div>
          ))}
        </div>'''
    return _component(s, _root(s, "s-z", inner), prelude=f"\nconst ROWS = {_js(c.story)};\n")


def _bento(s: Section, c: PageCopy) -> str:
    items = [i.model_dump() for i in (c.cards or c.items)[:4]]
    inner = '''        <h2 className="t-h2">Nổi bật</h2>
        <div className="bento">
          {ITEMS.map((it, i) => (
            <article key={it.name} className={i === 0 || i === 3 ? "card bento-wide" : "card"} data-swarm-id={`collection-card-${i + 1}`} data-swarm-role="card">
              <Art label={it.name} ratio={ITEMS.length === 3 && i === 2 ? "21 / 9" : i === 0 || i === 3 ? "16 / 9" : "1 / 1"} tone={i} />
              <div className="row between">
                <div><h3 className="t-h4">{it.name}</h3><p className="t-body muted">{it.note}</p></div>
                {it.price && <span className="t-body">{it.price}</span>}
              </div>
              <button type="button" className="btn btn-ghost" data-swarm-id={`quick-view-trigger-${i + 1}`} data-swarm-role="modal-trigger"
                onClick={() => setActive(i)}>Xem nhanh</button>
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
    inner = '''        <div className="split split-5-7">
          <h2 className="t-h2">Câu hỏi thường gặp</h2>
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
    inner = f'''        <div className="footer-grid">
          <div className="stack"><strong className="t-h4">{{{_js(c.brand)}}}</strong><p className="t-caption muted">{{{_js(c.footer_line)}}}</p></div>
          <form className="stack" noValidate onSubmit={{(e) => {{ e.preventDefault(); setState(/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) ? "ok" : "error"); }}}}>
            <label htmlFor="newsletter" className="t-body">Nhận tin mới qua email</label>
            <div className="row">
              <input id="newsletter" type="email" className="input" value={{email}} onChange={{(e) => setEmail(e.target.value)}}
                placeholder="ban@email.com" data-swarm-id="footer-newsletter-input" data-swarm-role="input"
                aria-invalid={{state === "error"}} aria-describedby="newsletter-msg" />
              <button type="submit" className="btn btn-primary" data-swarm-id="footer-newsletter-submit" data-swarm-role="button">Đăng ký</button>
            </div>
            <p id="newsletter-msg" className="t-caption" role="status">
              {{state === "ok" ? "Đã đăng ký, cảm ơn bạn." : state === "error" ? "Email chưa đúng định dạng." : ""}}
            </p>
          </form>
        </div>'''
    return _component(s, _root(s, "s-footer", inner, tag="footer"), client=True,
                      body='  const [email, setEmail] = useState("");\n  const [state, setState] = useState<"idle" | "ok" | "error">("idle");\n')


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
          <Art label={{{_js(c.brand)}}} ratio="16 / 8" />
        </div>'''
    return _component(s, _root(s, "s-hero-image", inner), client=True, body="  const [sent, setSent] = useState(false);\n")


SECTION_TITLES_VI = {"categories": "Danh mục", "related": "Sản phẩm liên quan", "collection": "Nổi bật"}


def _scroller(s: Section, c: PageCopy) -> str:
    rid = s.interactive[0].id if s.interactive else "card"
    inner = f'''        <h2 className="t-h2">{SECTION_TITLES_VI.get(s.id, "Khám phá")}</h2>
        <div className="scroller">
          {{CATS.map((name, i) => (
            <a key={{name}} href="#" className="card scroller-item" data-swarm-id={{`{rid}-${{i + 1}}`}} data-swarm-role="card">
              <Art label={{name}} ratio="1 / 1" tone={{i}} /><span className="t-h4">{{name}}</span>
            </a>
          ))}}
        </div>'''
    return _component(s, _root(s, "s-scroller", inner), prelude=f"\nconst CATS = {_js(c.categories)};\n")


def _grid4(s: Section, c: PageCopy) -> str:
    items = [i.model_dump() for i in c.items]
    inner = '''        <div className="row between"><h2 className="t-h2">Bán chạy</h2><span className="t-body muted" aria-live="polite">{cart ? `Giỏ hàng: ${cart}` : ""}</span></div>
        <div className="grid-4">
          {ITEMS.map((it, i) => (
            <article key={it.name} className="card" data-swarm-id={`product-card-${i + 1}`} data-swarm-role="card">
              <Art label={it.name} ratio="4 / 5" tone={i} />
              <h3 className="t-h4">{it.name}</h3>
              <p className="t-body muted">{it.price || it.note}</p>
              <button type="button" className="btn btn-primary" data-swarm-id={`add-to-cart-${i + 1}`} data-swarm-role="button"
                onClick={() => setCart(cart + 1)}>Thêm vào giỏ</button>
            </article>
          ))}
        </div>'''
    return _component(s, _root(s, "s-grid", inner), client=True, prelude=f"\nconst ITEMS = {_js(items)};\n",
                      body="  const [cart, setCart] = useState(0);\n")


def _split_story(s: Section, c: PageCopy) -> str:
    title, text = c.story[0]
    inner = f'''        <div className="split split-5-7">
          <h2 className="t-h2">{{{_js(title)}}}</h2>
          <p className="t-lead">{{{_js(text)}}}</p>
        </div>'''
    return _component(s, _root(s, "s-story", inner))


def _auth(s: Section, c: PageCopy) -> str:
    inner = '''        <div className="split split-5-7">
          <form className="stack card" noValidate onSubmit={(e) => { e.preventDefault(); setError(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) ? "Email chưa đúng định dạng." : pw.length < 8 ? "Mật khẩu cần ít nhất 8 ký tự." : ""); }}>
            <h1 className="t-h2">Đăng nhập</h1>
            <label htmlFor="email" className="t-body">Email</label>
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} data-swarm-id="email-input" data-swarm-role="input" />
            <label htmlFor="password" className="t-body">Mật khẩu</label>
            <div className="row">
              <input id="password" type={show ? "text" : "password"} className="input" value={pw} onChange={(e) => setPw(e.target.value)} data-swarm-id="password-input" data-swarm-role="input" />
              <button type="button" className="btn btn-ghost" data-swarm-id="password-toggle" data-swarm-role="button" onClick={() => setShow(!show)}>{show ? "Ẩn" : "Hiện"}</button>
            </div>
            <p className="t-caption" role="alert">{error}</p>
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
              <a key={it.name} href="#" className="card" data-swarm-id={`product-card-${i + 1}`} data-swarm-role="card">
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
          <button type="button" className="btn btn-ghost" data-swarm-id="load-more" data-swarm-role="button" onClick={() => setShown(shown + 8)}>Xem thêm</button>
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
            <Art label={{{_js(item.name)}}} tone={{img}} />
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
            <button type="button" className="btn btn-primary" disabled={{!variant}} data-swarm-id="add-to-cart" data-swarm-role="button"
              onClick={{() => setAdded(true)}}>{{added ? "Đã thêm vào giỏ" : variant ? "Thêm vào giỏ" : "Chọn phân loại"}}</button>
          </div>
        </div>'''
    return _component(s, _root(s, "s-pdp", inner), client=True,
                      body='  const [img, setImg] = useState(0);\n  const [variant, setVariant] = useState("");\n'
                           '  const [added, setAdded] = useState(false);\n')


def _showcase(s: Section, c: PageCopy) -> str:
    """Feature showcase: heading left, explanation right, a wide product visual underneath."""
    title, text = c.story[0]
    inner = f'''        <div className="split split-5-7">
          <h2 className="t-h2">{{{_js(title)}}}</h2>
          <div className="stack">
            <p className="t-lead">{{{_js(text)}}}</p>
            <a href="#" className="link-arrow" data-swarm-id="{s.id}-more" data-swarm-role="link">Tìm hiểu thêm <span aria-hidden>→</span></a>
          </div>
        </div>
        <div className="showcase-media"><Art label={{{_js(title)}}} ratio="16 / 7" tone={{1}} /></div>'''
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
          {ROWS.map(([title, text], i) => (
            <article key={title} className="text-card">
              <span className="t-caption muted">{String(i + 1).padStart(2, "0")}</span>
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
    inner = f'''        <h2 className="t-caption muted list-title">{title}</h2>
        <ul className="list-rows">
          {{(all ? ROWS : ROWS.slice(0, 5)).map(([entry, meta], i) => (
            <li key={{entry}}>
              <a href="#" className="list-row" data-swarm-id={{`list-row-${{i + 1}}`}} data-swarm-role="link">
                <span className="t-body">{{entry}}</span><span className="list-dots" aria-hidden />
                <span className="t-caption muted">{{meta}}</span>
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
    "full-bleed-image": _full_image, "horizontal-scroller": _scroller, "grid-4": _grid4, "split-5-7": _split_story,
    "title-with-count": _title_count, "sidebar-grid-4": _sidebar_grid, "inline-controls": _load_more, "tabs": _tabs,
    "feature-showcase": _showcase, "testimonials": _testimonials, "text-cards": _text_cards,
    "gallery": _gallery, "logo-strip": _logo_strip, "hero-text": _hero_text, "list-rows": _list_rows,
}


def render_section(section: Section, copy: PageCopy, page: str = "") -> WorkspaceFile:
    fn = BY_ID.get(section.id) or BY_STRUCTURE.get(section.structure)
    if fn is None:
        raise ValueError(f"no Next.js template for structure {section.structure!r}")
    folder = f"components/sections/{page}" if page else "components/sections"
    return WorkspaceFile(path=f"{folder}/{component_name(section.id)}.tsx", content=fn(section, copy))


# ----------------------------------------------------------------- base.css

BASE_CSS = """/* Generated by ChromaSwarm. Every value is a token from tokens.css or a step of the 8pt scale. */
*, *::before, *::after { box-sizing: border-box; }
* { margin: 0; }
html { -webkit-text-size-adjust: 100%; }
body { background: var(--bg-primary); color: var(--text-primary); font-family: var(--font-body);
  font-size: var(--text-body); line-height: 1.55; -webkit-font-smoothing: antialiased; }
img { display: block; max-width: 100%; }
a { color: inherit; }
button, input, select { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

.container { max-width: var(--container-max); margin-inline: auto; padding-inline: var(--gutter); }
.s { padding-block: var(--section-y); }
.stack { display: flex; flex-direction: column; gap: 16px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
.between { justify-content: space-between; }
.center { justify-content: center; }
.muted { color: var(--text-secondary); }

.t-display, .t-h1, .t-h2, .t-h3, .t-h4 { font-family: var(--font-heading); font-weight: 500; text-wrap: balance; }
.t-display { font-size: var(--text-display); line-height: 1.1; letter-spacing: -0.02em; max-width: 16ch; }
.t-h1 { font-size: var(--text-h1); line-height: 1.12; letter-spacing: -0.015em; }
.t-h2 { font-size: var(--text-h2); line-height: 1.15; letter-spacing: -0.01em; }
.t-h3 { font-size: var(--text-h3); line-height: 1.2; }
.t-h4 { font-size: var(--text-h4); line-height: 1.25; }
.t-lead { font-size: var(--text-lead); line-height: 1.5; max-width: 60ch; color: var(--text-secondary); }
.t-body { font-size: var(--text-body); max-width: 65ch; }
.t-caption { font-size: var(--text-caption); line-height: 1.4; max-width: 65ch; }

.btn { display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: 12px 24px;
  border: 1px solid transparent; border-radius: var(--radius-md); font-size: var(--text-body); font-weight: 500;
  cursor: pointer; text-decoration: none;
  transition: background-color var(--duration) var(--ease), border-color var(--duration) var(--ease), transform 160ms var(--ease); }
.btn:active { transform: scale(0.98); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); color: var(--accent-fg); }
.btn-primary:hover:not(:disabled) { background: var(--accent-hover); }
.btn-ghost { background: transparent; border-color: var(--border-subtle); color: var(--text-primary); }
.btn-ghost:hover { border-color: var(--text-secondary); background: var(--bg-surface); }
.btn-inverse { background: var(--accent-fg); color: var(--accent); }
.btn-inverse:hover { background: var(--bg-elevated); }
.link-arrow { display: inline-flex; gap: 8px; align-items: center; min-height: 48px; text-decoration: none; font-weight: 500; }
.link-arrow span { transition: transform var(--duration) var(--ease); }
.link-arrow:hover { color: var(--accent); }
.link-arrow:hover span { transform: translateX(4px); }
.input { min-height: 48px; padding: 12px 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  background: var(--bg-elevated); flex: 1; min-width: 0; }
.input:hover { border-color: var(--text-secondary); }
.input[aria-invalid="true"] { border-color: var(--danger); }

.card { display: flex; flex-direction: column; gap: 16px; padding: var(--card-padding); background: var(--bg-surface);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); text-decoration: none;
  transition: border-color var(--duration) var(--ease), transform var(--duration) var(--ease); }
a.card:hover, article.card:hover { border-color: var(--text-secondary); transform: translateY(-4px); }
.art { width: 100%; height: auto; object-fit: cover; border-radius: var(--radius-md); }

.split { display: grid; gap: var(--grid-gap); align-items: center; }
@media (min-width: 1024px) {
  .split-7-5 { grid-template-columns: 7fr 5fr; }
  .split-5-7 { grid-template-columns: 5fr 7fr; }
  .split.is-flipped > :first-child { order: 2; }
}

.s-nav { position: sticky; top: 0; z-index: 10; background: color-mix(in oklch, var(--bg-primary) 85%, transparent);
  backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-subtle); }
.nav-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; column-gap: 24px; min-height: 64px; }
.nav-logo { font-family: var(--font-heading); font-size: var(--text-h4); text-decoration: none; min-height: 48px;
  display: inline-flex; align-items: center; }
.nav-links { display: none; gap: 32px; }
.nav-links.is-open { display: flex; flex-direction: column; position: absolute; inset: 64px 0 auto 0; padding: 24px var(--gutter);
  background: var(--bg-primary); border-bottom: 1px solid var(--border-subtle); }
.nav-logo { transition: color var(--duration) var(--ease); }
.nav-logo:hover { color: var(--accent); }
.nav-link { text-decoration: none; min-height: 48px; display: inline-flex; align-items: center; white-space: nowrap; }
.nav-link:hover { color: var(--accent); }
@media (min-width: 768px) {
  .nav-links, .nav-links.is-open { display: flex; flex-direction: row; position: static; padding: 0; border: 0; background: none; }
  .nav-toggle { display: none; }
}

.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: var(--grid-gap);
  border-block: 1px solid var(--border-subtle); padding-block: 32px; }
.metric dd { margin-top: 8px; }
.z-rows { display: flex; flex-direction: column; gap: var(--section-y); }
.bento { display: grid; gap: 24px; margin-top: 32px; }
@media (min-width: 768px) { .bento { grid-template-columns: repeat(3, 1fr); } .bento-wide { grid-column: span 2; }
  .bento > :nth-child(3):last-child { grid-column: 1 / -1; } }  /* 3 cards: the last one closes the row (21:9 art) */
.modal-scrim { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 24px;
  background: color-mix(in oklch, var(--text-primary) 45%, transparent); }
.modal { display: flex; flex-direction: column; gap: 16px; width: min(480px, 100%); padding: 32px;
  background: var(--bg-elevated); border-radius: var(--radius-lg); }
.faq { display: flex; flex-direction: column; border-top: 1px solid var(--border-subtle); }
.faq-item { border-bottom: 1px solid var(--border-subtle); }
.faq-q { display: flex; justify-content: space-between; gap: 16px; width: 100%; min-height: 64px; padding-block: 16px;
  background: none; border: 0; text-align: left; font-size: var(--text-lead); cursor: pointer; }
.faq-q:hover { color: var(--accent); }
.faq-a { padding-bottom: 24px; color: var(--text-secondary); }
.s-band { background: var(--accent); color: var(--accent-fg); }
.band { display: flex; flex-direction: column; align-items: flex-start; gap: 32px; }
.s-footer { border-top: 1px solid var(--border-subtle); }
.footer-grid { display: grid; gap: var(--grid-gap); }
@media (min-width: 768px) { .footer-grid { grid-template-columns: 1fr 1fr; } }
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
.filter, .tab { min-height: 48px; padding: 12px 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  background: transparent; text-align: left; cursor: pointer; transition: background-color var(--duration) var(--ease); }
.filter:hover, .tab:hover { background: var(--bg-surface); }
.filter.is-active, .tab.is-active { background: var(--text-primary); color: var(--bg-primary); border-color: var(--text-primary); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tab-panel { margin-top: 24px; }
.thumb { width: 80px; padding: 0; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: none; cursor: pointer; }
.thumb:hover, .thumb.is-active { border-color: var(--text-primary); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition-duration: 1ms !important; animation-duration: 1ms !important; }
}
"""
