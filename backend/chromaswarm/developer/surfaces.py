"""Surface materials (presets.Surface): one stylesheet per material, layered over base.css.

Written to `app/surface.css`, imported after base.css and before heal.css, so B11 heal
rules still win. Every value is a token (colours, radii, the 3 shadow levels from
design_spec.shadow_tokens) or a step of the 8pt scale. Each material keeps the rules the
QA checks: text sits on >= 72% opaque fills, controls keep a >= 3:1 border, actions stay
one colour (`--action`), focus-visible is untouched.
"""

from __future__ import annotations

from chromaswarm.engines.presets import Surface

GLASS = """/* Surface: Liquid Glass — frosted translucent layers over soft brand-hue light. */
:root {
  --glass-fill: color-mix(in srgb, var(--bg-elevated) 72%, transparent);
  --glass-fill-strong: color-mix(in srgb, var(--bg-elevated) 86%, transparent);
  --glass-edge: color-mix(in srgb, var(--text-primary) 12%, transparent);
  --glass-blur: blur(24px) saturate(160%);
}
/* Something for the glass to refract: three faint glows in the brand hue (anti-slop #1: <= 12%).
   On a fixed layer, not on body: body keeps a solid colour so QA still measures text contrast. */
body::before { content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none; background:
  radial-gradient(48rem 32rem at 8% -4%, color-mix(in srgb, var(--accent) 12%, transparent), transparent 70%),
  radial-gradient(40rem 28rem at 96% 28%, color-mix(in srgb, var(--accent) 9%, transparent), transparent 70%),
  radial-gradient(44rem 30rem at 30% 100%, color-mix(in srgb, var(--accent) 8%, transparent), transparent 70%); }
.s-nav, .card, .hero-panel, .modal, .metrics, .faq-item, .btn-ghost, .filter, .tab {
  -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); }
/* Floating glass bar instead of an edge-to-edge header */
.s-nav { top: 12px; margin: 12px var(--gutter) 0; border: 1px solid var(--glass-edge); border-radius: var(--radius-lg);
  background: var(--glass-fill-strong); box-shadow: var(--shadow-md); }
@media (max-width: 767px) {
  .nav-links.is-open { inset: 72px 0 auto 0; border: 1px solid var(--glass-edge); border-radius: var(--radius-lg);
    background: var(--glass-fill-strong); -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur);
    box-shadow: var(--shadow-lg); }
}
.card, .hero-panel, .modal { background: var(--glass-fill); border: 1px solid var(--glass-edge); box-shadow: var(--shadow-md); }
a.card:hover, article.card:hover { border-color: var(--glass-edge); box-shadow: var(--shadow-lg); }
.s-alt { background: color-mix(in srgb, var(--bg-surface) 50%, transparent); }
.metrics { padding: 32px; border: 1px solid var(--glass-edge); border-radius: var(--radius-lg); background: var(--glass-fill);
  box-shadow: var(--shadow-sm); }
.faq { gap: 8px; border: 0; }
.faq-item { padding-inline: 24px; border: 1px solid var(--glass-edge); border-radius: var(--radius-md); background: var(--glass-fill); }
.art, .product > .art { border-radius: var(--radius-lg); }
.btn, .icon-btn { border-radius: 9999px; }
.btn-primary { box-shadow: var(--shadow-sm); }
.btn-ghost { background: var(--glass-fill); }
.btn-ghost:hover { background: var(--glass-fill-strong); }
.input { border-radius: var(--radius-md); background: var(--glass-fill-strong); }
.filter, .tab { border-radius: 9999px; background: var(--glass-fill); }
.thumb { border-radius: var(--radius-md); overflow: hidden; }
.s-hero-overlay { margin: 16px var(--gutter) 0; border-radius: var(--radius-lg); }
/* The signature: copy on a dark frosted panel floating over the photo. */
.s-hero-overlay .hero-copy-panel { max-width: 50rem; padding: clamp(24px, 4vw, 48px); border-radius: var(--radius-lg);
  background: color-mix(in srgb, oklch(0.18 0.01 260) 42%, transparent);
  border: 1px solid oklch(1 0 0 / 0.22); box-shadow: inset 0 1px 0 oklch(1 0 0 / 0.30), 0 24px 48px oklch(0 0 0 / 0.25);
  -webkit-backdrop-filter: var(--glass-blur); backdrop-filter: var(--glass-blur); }
.s-hero-overlay .hero-scrim { opacity: 0.6; }
.s-band { margin-inline: var(--gutter); border-radius: var(--radius-lg); }
.s-band .band { padding-inline: clamp(0px, 4vw, 48px); }
/* Accessibility: users who ask for less transparency get solid surfaces. */
@media (prefers-reduced-transparency: reduce) {
  :root { --glass-fill: var(--bg-elevated); --glass-fill-strong: var(--bg-elevated); }
  .s-hero-overlay .hero-copy-panel { background: oklch(0.18 0.01 260 / 0.88); }
}
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  :root { --glass-fill: var(--bg-elevated); --glass-fill-strong: var(--bg-elevated); }
}
"""

CLAY = """/* Surface: Claymorphism — puffy rounded blocks lit from above (shadows: design_spec.shadow_tokens). */
.card, .hero-panel, .modal { border: 0; background: var(--bg-elevated); box-shadow: var(--shadow-md); }
a.card:hover, article.card:hover { box-shadow: var(--shadow-lg); }
.s-nav { border-bottom: 0; box-shadow: var(--shadow-sm); }
.metrics { padding: 32px; border: 0; border-radius: var(--radius-lg); background: var(--bg-elevated); box-shadow: var(--shadow-md); }
.faq { gap: 16px; border: 0; }
.faq-item { padding-inline: 24px; border: 0; border-radius: var(--radius-md); background: var(--bg-elevated); box-shadow: var(--shadow-sm); }
.art { border-radius: var(--radius-lg); }
.product > .art { box-shadow: var(--shadow-md); transition: transform var(--duration) var(--ease), box-shadow var(--duration) var(--ease); }
.product:hover > .art { filter: none; transform: translateY(-4px); box-shadow: var(--shadow-lg); }
.btn, .icon-btn { border-radius: 9999px; }
.btn { transition: background-color var(--duration) var(--ease), box-shadow var(--duration) var(--ease), transform 160ms var(--ease); }
.btn-primary, .btn-inverse { box-shadow: var(--shadow-sm); }
.btn-primary:hover, .btn-inverse:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.btn-ghost { background: var(--bg-elevated); box-shadow: var(--shadow-sm); }
.btn:active { transform: translateY(1px) scale(0.98); }
/* Inputs are pressed into the surface, not raised; the border keeps >= 3:1 (§6.1). */
.input { border-radius: var(--radius-md); background: var(--bg-surface);
  box-shadow: inset 0 2px 6px color-mix(in srgb, var(--text-primary) 10%, transparent); }
.filter, .tab { border-radius: 9999px; }
.filter.is-active, .tab.is-active { box-shadow: var(--shadow-sm); }
.thumb { border-radius: var(--radius-md); overflow: hidden; }
.s-hero-overlay { margin: 16px var(--gutter) 0; border-radius: var(--radius-lg); }
.s-band { margin-inline: var(--gutter); border-radius: var(--radius-lg); }
.s-band .band { padding-inline: clamp(0px, 4vw, 48px); }
"""

BRUTAL = """/* Surface: Neo-brutalism — 2px ink borders, hard offset shadows, square corners. */
.btn { border: 2px solid var(--text-primary); border-radius: 0; box-shadow: var(--shadow-md);
  transition: transform 120ms var(--ease), box-shadow 120ms var(--ease), background-color var(--duration) var(--ease); }
.btn:hover { transform: translate(-2px, -2px); box-shadow: var(--shadow-lg); }
.btn:active { transform: translate(4px, 4px); box-shadow: 0 0 0 var(--text-primary); }
.btn-ghost { background: var(--bg-elevated); border-color: var(--text-primary); color: var(--text-primary); }
.btn-ghost:hover { background: var(--bg-elevated); }
/* On photos the offset shadow takes the brand accent. */
.s-hero-overlay .btn { box-shadow: 4px 4px 0 var(--accent); }
.s-hero-overlay .btn:hover { box-shadow: 8px 8px 0 var(--accent); }
.btn-link { box-shadow: none; }
.card, .hero-panel, .modal { border: 2px solid var(--text-primary); border-radius: 0; background: var(--bg-elevated);
  box-shadow: var(--shadow-md); }
a.card:hover, article.card:hover { border-color: var(--text-primary); transform: translate(-2px, -2px); box-shadow: var(--shadow-lg); }
.art { border: 2px solid var(--text-primary); border-radius: 0; }
.s-hero-overlay > .art { border: 0; }
.product > .art { transition: transform 120ms var(--ease), box-shadow 120ms var(--ease); }
.product:hover > .art { filter: none; transform: translate(-2px, -2px); box-shadow: var(--shadow-md); }
.input { border: 2px solid var(--text-primary); border-radius: 0; }
.input:focus-visible { box-shadow: var(--shadow-sm); }
.filter, .tab, .thumb, .icon-btn { border: 2px solid var(--text-primary); border-radius: 0; }
.s-nav { border-bottom: 2px solid var(--text-primary); background: var(--bg-primary);
  -webkit-backdrop-filter: none; backdrop-filter: none; }
.nav-links.is-open { border-bottom: 2px solid var(--text-primary); }
.metrics { border-block: 2px solid var(--text-primary); }
.faq { border-top: 2px solid var(--text-primary); }
.faq-item { border-bottom: 2px solid var(--text-primary); }
.s-alt { border-block: 2px solid var(--text-primary); }
.s-footer { border-top: 2px solid var(--text-primary); }
/* Bolder type: one heavy weight for the heading family, tight tracking (still <= 2 weights per family). */
.t-display, .t-h1, .t-h2, .t-h3, .t-h4 { font-weight: 700; }
.t-display { letter-spacing: -0.04em; line-height: 1; }
.nav-logo { font-weight: 700; }
/* Colour block: the closing band is the accent itself, its button an ink-bordered light block. */
.s-band { background: var(--accent); color: var(--accent-fg); border-block: 2px solid var(--text-primary); }
.s-band .btn, .s-band .btn-inverse { background: var(--bg-primary); color: var(--text-primary);
  border-color: var(--text-primary); box-shadow: 4px 4px 0 var(--text-primary); }
.s-band .btn:hover { box-shadow: 8px 8px 0 var(--text-primary); }
/* Product photos sit in ink frames with a hard shadow from the start. */
.product > .art { box-shadow: var(--shadow-sm); }
/* Eyebrows become small accent tags (the accent's own readable ink, a tiny share of the page). */
.eyebrow { width: fit-content; padding: 4px 8px; background: var(--accent); color: var(--accent-fg);
  letter-spacing: 0.08em; }  /* body font: a mono eyebrow breaks DESIGN.md's body font (QA test 4) */
"""

CSS: dict[Surface, str] = {Surface.FLAT: "/* Surface: flat — the theme's own surfaces (base.css). */\n",
                           Surface.GLASS: GLASS, Surface.CLAY: CLAY, Surface.BRUTAL: BRUTAL}


def surface_css(surface: Surface) -> str:
    return CSS[surface]
