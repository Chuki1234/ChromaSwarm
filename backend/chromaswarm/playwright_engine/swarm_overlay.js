/*
 * ChromaSwarm overlay — injected with page.addInitScript(), written from scratch.
 *
 * Draws the Design department's cursors (B8), the Master QA cursor + HUD (B11)
 * and hides everything for the handover (B12). It never changes the page: one
 * host element with a shadow root, position:fixed, pointer-events:none, so the
 * page's own styles and clicks are untouched.
 *
 * The overlay only *reads* the DOM (rects, computed styles) and returns raw
 * numbers. All judgement (8pt grid, contrast, type scale) happens in Python
 * with the deterministic engines.
 */
(() => {
  if (window.__chromaSwarm) return;

  const AGENTS = {
    layout: { label: "Layout", color: "#3B82F6" },
    color: { label: "Color OKLCH", color: "#F59E0B" },
    typography: { label: "Typography", color: "#8B5CF6" },
    motion: { label: "Motion MCP", color: "#10B981" },
    inspector: { label: "Motion Inspector", color: "#10B981" },
    master: { label: "Master QA", color: "#F5B400" },
  };
  const FAIL = "#EF4444";
  const cfg = { instant: false, speed: 1 };
  const cursors = {}; // agent -> {el, x, y}
  let annotations = []; // {el, node, kind}
  let host, root, layer, hud, masterOn = false, handedOver = false;

  const CSS = `
    :host { all: initial; }
    .layer { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;
      font: 500 11px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .cursor { position: absolute; left: 0; top: 0; will-change: transform; }
    .cursor svg { display: block; filter: drop-shadow(0 1px 2px rgb(0 0 0 / .35)); }
    .tag { position: absolute; left: 14px; top: 16px; padding: 2px 6px; border-radius: 4px;
      color: #fff; white-space: nowrap; }
    .note { position: absolute; left: 14px; top: 36px; padding: 4px 8px; border-radius: 4px;
      background: rgb(17 17 17 / .88); color: #fff; white-space: nowrap; max-width: 360px;
      overflow: hidden; text-overflow: ellipsis; }
    .tag.sm { left: 10px; top: 11px; padding: 1px 4px; font-size: 10px; }
    .master .tag { top: 40px; left: 34px; font-size: 13px; }
    .master .note { top: 64px; left: 34px; font-size: 12px; }
    .box { position: absolute; border: 1px solid; box-sizing: border-box; }
    .box .lbl { position: absolute; left: -1px; top: -18px; padding: 1px 4px; color: #fff;
      white-space: nowrap; border-radius: 2px; }
    .guide { position: absolute; border: 0 dashed; opacity: .7; }
    .pad { position: absolute; background: rgb(16 185 129 / .18); }
    .mar { position: absolute; background: rgb(245 158 11 / .18); }
    .swatch { position: absolute; display: flex; gap: 4px; align-items: center; padding: 3px 6px;
      border-radius: 4px; background: rgb(17 17 17 / .88); color: #fff; white-space: nowrap; }
    .swatch i { width: 12px; height: 12px; border-radius: 2px; border: 1px solid rgb(255 255 255 / .6); }
    .caret { position: absolute; width: 2px; animation: blink 1s steps(1) infinite; }
    @keyframes blink { 50% { opacity: 0; } }
    .pulse { position: absolute; width: 96px; height: 96px; margin: -48px 0 0 -48px; border-radius: 50%;
      border: 3px solid ${AGENTS.master.color}; animation: ring .7s ease-out forwards; }
    @keyframes ring { from { transform: scale(.2); opacity: 1; } to { transform: scale(1.4); opacity: 0; } }
    .hud { position: absolute; left: 50%; bottom: 24px; transform: translateX(-50%); padding: 8px 16px;
      border-radius: 999px; background: rgb(17 17 17 / .92); color: #fff; font-size: 12px; white-space: nowrap;
      border: 1px solid ${AGENTS.master.color}; }
  `;

  function ensure() {
    if (handedOver) return false;
    if (!document.documentElement) return false;
    if (!host) {
      host = document.createElement("chromaswarm-overlay");
      host.setAttribute("data-chromaswarm", "overlay");
      root = host.attachShadow({ mode: "open" });
      const style = document.createElement("style");
      style.textContent = CSS;
      layer = document.createElement("div");
      layer.className = "layer";
      root.append(style, layer);
    }
    // Appended after the page's own nodes and re-attached if a framework re-render drops it.
    const parent = document.body || document.documentElement;
    if (!host.isConnected) parent.appendChild(host);
    return true;
  }

  const sleep = ms => new Promise(r => setTimeout(r, cfg.instant ? 0 : ms / cfg.speed));
  // A hidden or covered window stops painting, so requestAnimationFrame never fires there: never wait
  // more than 50ms for a frame, or the whole build stalls while the Chromium window is out of sight.
  const frame = () => new Promise(r => { requestAnimationFrame(() => r()); setTimeout(r, 50); });

  function arrow(color, size) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24"><path d="M3 2 L3 19 L8 14.5 L11.5 22 L14.5 20.6 L11 13.3 L18 13.3 Z"
      fill="${color}" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }

  function cursor(agent) {
    const def = AGENTS[agent];
    if (!def) throw new Error(`unknown agent ${agent}`);
    if (cursors[agent]) return cursors[agent];
    const el = document.createElement("div");
    el.className = "cursor" + (agent === "master" ? " master" : "");
    const size = def.size || (agent === "master" ? 48 : 22);
    el.innerHTML = `${arrow(def.color, size)}
      <span class="tag${size < 18 ? " sm" : ""}" style="background:${def.color};${agent === "master" ? "color:#111" : ""}">${def.label}</span>`;
    layer.appendChild(el);
    const idx = Object.keys(cursors).length;
    const c = { el, x: innerWidth - 120 - idx * 40, y: 80 + idx * 40 };
    place(c);
    cursors[agent] = c;
    return c;
  }

  function place(c) {
    c.el.style.transform = `translate(${c.x}px, ${c.y}px)`;
  }

  async function glide(c, x, y) {
    c.pin = null;  // sent somewhere else: it stops following its previous element (callers pin it again)
    c.el.style.visibility = "";
    c.moving = true;
    try { await glideTo(c, x, y); } finally { c.moving = false; }
  }

  async function glideTo(c, x, y) {
    const x0 = c.x, y0 = c.y;
    const dist = Math.hypot(x - x0, y - y0);
    if (cfg.instant || dist < 1) { c.x = x; c.y = y; place(c); return; }
    // Cubic Bezier with a sideways bow, so paths look hand-moved rather than linear.
    const bow = Math.min(120, dist * 0.25) * (Math.random() < 0.5 ? -1 : 1);
    const nx = -(y - y0) / dist, ny = (x - x0) / dist;
    const c1 = [x0 + (x - x0) * 0.3 + nx * bow, y0 + (y - y0) * 0.3 + ny * bow];
    const c2 = [x0 + (x - x0) * 0.7 + nx * bow * 0.4, y0 + (y - y0) * 0.7 + ny * bow * 0.4];
    const duration = Math.min(1100, 260 + dist * 0.7) / cfg.speed;
    const t0 = performance.now();
    for (;;) {
      await frame();
      const t = Math.min(1, (performance.now() - t0) / duration);
      const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      const u = 1 - e;
      c.x = u * u * u * x0 + 3 * u * u * e * c1[0] + 3 * u * e * e * c2[0] + e * e * e * x;
      c.y = u * u * u * y0 + 3 * u * u * e * c1[1] + 3 * u * e * e * c2[1] + e * e * e * y;
      place(c);
      if (t >= 1) return;
    }
  }

  /** Wait until smooth scrolling has stopped (position stable for 3 frames, max 1.5s). */
  async function settle() {
    let last = -1, stable = 0;
    const t0 = performance.now();
    while (stable < 3 && performance.now() - t0 < 1500) {
      await frame();
      const y = scrollY + scrollX * 1e6;
      stable = y === last ? stable + 1 : 0;
      last = y;
    }
  }

  function find(selector) {
    const el = document.querySelector(selector);
    if (!el) return null;
    return el;
  }

  async function reach(agent, selector) {
    if (!ensure()) return null;
    const el = find(selector);
    if (!el) return null;
    const r0 = el.getBoundingClientRect();
    if (r0.top < 0 || r0.bottom > innerHeight) {
      el.scrollIntoView({ block: r0.height > innerHeight * 0.8 ? "start" : "center",
        behavior: cfg.instant ? "auto" : "smooth" });
      await settle();
    }
    const r = el.getBoundingClientRect();
    const c = cursor(agent);
    const tx = Math.max(4, Math.min(innerWidth - 40, r.left + Math.min(24, r.width / 2)));
    const ty = Math.max(4, Math.min(innerHeight - 40, r.top + Math.min(16, r.height / 2)));
    await glide(c, tx, ty);
    return el;
  }

  const px = v => parseFloat(v) || 0;
  const rectOf = el => { const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; };

  function annotate(el, kind, build) {
    const node = document.createElement("div");
    node.dataset.kind = kind;
    layer.appendChild(node);
    const a = { el, node, kind, build };
    annotations.push(a);
    build(node, el.getBoundingClientRect());
    return a;
  }

  // A worker that reached its component stays on it: the page scrolls under the overlay (fixed layer), so
  // the cursor follows the element, and hides while the element is off screen (never parked at an edge).
  function pinAt(c) {
    if (!c.pin || c.moving) return;
    if (!c.pin.isConnected) { c.pin = null; return; }
    const r = c.pin.getBoundingClientRect();
    const off = r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth;
    c.el.style.visibility = off ? "hidden" : "";
    if (off) return;
    c.x = r.left + Math.min(12, r.width / 2);
    c.y = r.top + Math.min(8, r.height / 2);
    place(c);
  }

  function relayout() {
    for (const c of Object.values(cursors)) pinAt(c);
    annotations = annotations.filter(a => a.node.isConnected);
    for (const a of annotations) {
      if (!a.el.isConnected) { a.node.remove(); continue; }
      a.node.replaceChildren();
      a.build(a.node, a.el.getBoundingClientRect());
    }
  }
  let pending = false;
  const schedule = () => { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; relayout(); }); };
  addEventListener("scroll", schedule, { passive: true, capture: true });
  addEventListener("resize", schedule);

  function boxEl(r, color, label, dashed) {
    const b = document.createElement("div");
    b.className = "box";
    Object.assign(b.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px`,
      borderColor: color, borderStyle: dashed ? "dashed" : "solid" });
    if (label) {
      const l = document.createElement("span");
      l.className = "lbl";
      l.style.background = color;
      l.textContent = label;
      b.appendChild(l);
    }
    return b;
  }

  function band(cls, left, top, width, height) {
    const d = document.createElement("div");
    d.className = cls;
    Object.assign(d.style, { left: `${left}px`, top: `${top}px`, width: `${Math.max(0, width)}px`, height: `${Math.max(0, height)}px` });
    return d;
  }

  function note(agent, text) {
    const c = cursors[agent];
    if (!c) return;
    let n = c.el.querySelector(".note");
    if (!text) { n?.remove(); return; }
    if (!n) { n = document.createElement("span"); n.className = "note"; c.el.appendChild(n); }
    n.textContent = text;
  }

  // Browsers serialise computed colours as lab()/oklch()/color-mix results; paint one
  // pixel and read it back so Python always receives plain sRGB.
  const pixel = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  function rgba(color) {
    pixel.clearRect(0, 0, 1, 1);
    pixel.fillStyle = "#000";
    pixel.fillStyle = color;
    pixel.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = pixel.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  }
  const css = ([r, g, b]) => `rgb(${r}, ${g}, ${b})`;

  /** Background behind an element: translucent layers composited down to the first opaque one. */
  function effectiveBg(el) {
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c[3] > 0) layers.push(c);
      if (c[3] >= 1) break;
    }
    let out = [255, 255, 255];
    for (const [r, g, b, a] of layers.reverse()) out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a)];
    return out.map(Math.round);
  }

  const measureCanvas = document.createElement("canvas").getContext("2d");

  const api = {
    version: 1,
    agents: AGENTS,

    configure(opts = {}) { Object.assign(cfg, opts); return { ...cfg }; },

    install() { return ensure(); },

    async moveTo(agent, selector) {
      const el = await reach(agent, selector);
      return el ? rectOf(el) : null;
    },

    /** Layout agent: bounding box, padding/margin bands, ruler guides to the viewport edges. */
    async measure(agent, selector) {
      const el = await reach(agent, selector);
      if (!el) return null;
      const cs = getComputedStyle(el);
      const padding = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(px);
      const margin = [cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft].map(px);
      const gap = px(cs.rowGap) || px(cs.columnGap) || 0;
      const color = AGENTS[agent].color;
      annotate(el, "measure", (node, r) => {
        node.append(
          band("mar", r.left, r.top - margin[0], r.width, margin[0]),
          band("mar", r.left, r.bottom, r.width, margin[2]),
          band("pad", r.left, r.top, r.width, padding[0]),
          band("pad", r.left, r.bottom - padding[2], r.width, padding[2]),
          band("pad", r.left, r.top + padding[0], padding[3], r.height - padding[0] - padding[2]),
          band("pad", r.right - padding[1], r.top + padding[0], padding[1], r.height - padding[0] - padding[2]),
          boxEl(r, color, `${Math.round(r.width)}×${Math.round(r.height)}`),
        );
        for (const [left, top, w, h, side] of [[0, r.top, innerWidth, 0, "borderTopWidth"], [0, r.bottom, innerWidth, 0, "borderTopWidth"],
          [r.left, 0, 0, innerHeight, "borderLeftWidth"], [r.right, 0, 0, innerHeight, "borderLeftWidth"]]) {
          const g = band("guide", left, top, w, h);
          g.style[side] = "1px";
          g.style.borderColor = color;
          node.appendChild(g);
        }
      });
      note(agent, `pad ${padding.join("/")} · gap ${gap}`);
      // Where content actually starts: leftmost text or image box (padding may live on an inner container).
      let contentLeft = null, n = 0;
      for (const d of el.querySelectorAll("*")) {
        if (n++ > 2000) break;
        const hasText = [...d.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
        if (!hasText && !/^(IMG|SVG|INPUT|BUTTON|SELECT|VIDEO|CANVAS)$/i.test(d.tagName)) continue;
        const r = d.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || r.right <= 0) continue;
        contentLeft = contentLeft === null ? r.left : Math.min(contentLeft, r.left);
      }
      return { rect: rectOf(el), padding, margin, gap, viewport_w: innerWidth, content_left: contentLeft };
    },

    /** Color agent: computed foreground + effective background of an element. */
    async color(agent, selector) {
      const el = await reach(agent, selector);
      if (!el) return null;
      const cs = getComputedStyle(el);
      const bgRgb = effectiveBg(el), f = rgba(cs.color);
      // Translucent text is composited over its background too.
      const fg = css([0, 1, 2].map(i => Math.round(f[i] * f[3] + bgRgb[i] * (1 - f[3])))), bg = css(bgRgb);
      annotate(el, "color", (node, r) => {
        const s = document.createElement("div");
        s.className = "swatch";
        Object.assign(s.style, { left: `${Math.max(4, r.right - 150)}px`, top: `${Math.max(4, r.top + 4)}px` });
        s.innerHTML = `<i style="background:${bg}"></i><i style="background:${fg}"></i><span></span>`;
        s.querySelector("span").textContent = "bg / text";
        node.appendChild(s);
      });
      return { fg, bg, font_size: px(cs.fontSize), font_weight: px(cs.fontWeight) || 400, rect: rectOf(el) };
    },

    /** Typography agent: font metrics and measured line length in ch. */
    async typography(agent, selector) {
      const el = await reach(agent, selector);
      if (!el) return null;
      const cs = getComputedStyle(el);
      measureCanvas.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const ch = measureCanvas.measureText("0").width || px(cs.fontSize) * 0.5;
      const contentW = el.getBoundingClientRect().width - px(cs.paddingLeft) - px(cs.paddingRight);
      const color = AGENTS[agent].color;
      annotate(el, "typography", (node, r) => {
        const caret = band("caret", r.left - 4, r.top, 2, Math.min(r.height, px(cs.lineHeight) || px(cs.fontSize) * 1.4));
        caret.style.background = color;
        node.append(caret, boxEl(r, color, `${cs.fontSize} / ${cs.lineHeight}`, true));
      });
      const line_ch = Math.round(contentW / ch);
      note(agent, `${cs.fontSize} · ${line_ch}ch`);
      return {
        font_family: cs.fontFamily, font_size: px(cs.fontSize), line_height: cs.lineHeight === "normal" ? null : px(cs.lineHeight),
        font_weight: px(cs.fontWeight) || 400, letter_spacing: cs.letterSpacing, line_ch, rect: rectOf(el),
      };
    },

    note(agent, text) { if (ensure()) { cursor(agent); note(agent, text); } },

    // ---------------------------------------------------------------- factory (Clone B9 / B11)
    /** A worker cursor born at its parent's position (section -> crew -> component). */
    spawn(id, label, color, from, size) {
      if (!ensure()) return false;
      if (cursors[id]) { cursors[id].el.remove(); delete cursors[id]; }
      AGENTS[id] = { label, color, size: size || 18 };
      const c = cursor(id);
      const p = from && cursors[from];
      if (p) { c.x = p.x; c.y = p.y; place(c); }
      return true;
    },

    async flyTo(id, selector) {
      const el = await reach(id, selector);
      if (el && cursors[id] && id !== "master") { cursors[id].pin = el; pinAt(cursors[id]); }  // section / crew cursors stay on it
      return el ? rectOf(el) : null;
    },

    /** Workers go to their components together, one viewport at a time; each marks its component with
     *  a box and a label (green-ish = matches the reference, red = still differs). */
    async crew(items) {
      if (!ensure()) return 0;
      const found = items.map(it => ({ it, el: find(it.sel) })).filter(x => x.el);
      found.sort((a, b) => (a.el.getBoundingClientRect().top - b.el.getBoundingClientRect().top));
      let i = 0, done = 0;
      while (i < found.length) {
        const first = found[i].el.getBoundingClientRect();
        if (first.top < 0 || first.top > innerHeight * 0.75) {
          scrollBy({ top: first.top - 96, behavior: cfg.instant ? "auto" : "smooth" });
          await settle();
        }
        const batch = [];
        while (i < found.length && found[i].el.getBoundingClientRect().top < innerHeight - 40 && batch.length < 14) batch.push(found[i++]);
        if (!batch.length) batch.push(found[i++]);
        await Promise.all(batch.map(async ({ it, el }) => {
          api.spawn(it.id, it.label, it.color, it.from, 14);
          const r = el.getBoundingClientRect(), c = cursors[it.id];
          if (r.bottom > 0 && r.top < innerHeight) {
            await glide(c, Math.max(4, Math.min(innerWidth - 30, r.left + Math.min(12, r.width / 2))), r.top + Math.min(8, r.height / 2));
          }
          c.pin = el;  // from now on the worker follows its component (scrolling, re-layout)
          pinAt(c);
          annotate(el, "comp", (node, rr) => node.appendChild(boxEl(rr, it.ok ? it.color : FAIL, it.note || it.label, !it.ok)));
          done++;
        }));
        await sleep(450);
      }
      return done;
    },

    /** Workers fly back into their parent and disappear (components -> crew -> section -> master). */
    async merge(ids, into) {
      const target = cursors[into];
      await Promise.all(ids.filter(id => cursors[id]).map(async id => {
        const c = cursors[id];
        c.pin = null;
        c.el.style.visibility = "";
        if (target) await glide(c, target.x, target.y);
        c.el.remove(); delete cursors[id]; delete AGENTS[id];
      }));
      return true;
    },

    /** Where a cursor is (tests / debugging): window position and whether it shows. */
    pos(id) { const c = cursors[id]; return c ? { x: Math.round(c.x), y: Math.round(c.y), visible: c.el.style.visibility !== "hidden" } : null; },

    retire(id) { if (cursors[id]) { cursors[id].el.remove(); delete cursors[id]; delete AGENTS[id]; } return true; },

    /** B11: the 2.2x Master cursor and its HUD pill. */
    master(on = true) {
      if (!ensure()) return;
      masterOn = on;
      for (const [name, c] of Object.entries(cursors)) if (name !== "master") c.el.style.display = on ? "none" : "";
      if (on) cursor("master"); else cursors.master?.el.remove(), delete cursors.master;
    },
    hud(text) {
      if (!ensure()) return;
      if (!text) { hud?.remove(); hud = null; return; }
      if (!hud) { hud = document.createElement("div"); hud.className = "hud"; layer.appendChild(hud); }
      hud.textContent = text;
    },
    pulse() {
      const c = cursors.master;
      if (!c) return;
      const p = document.createElement("div");
      p.className = "pulse";
      Object.assign(p.style, { left: `${c.x + 6}px`, top: `${c.y + 4}px` });
      layer.appendChild(p);
      setTimeout(() => p.remove(), 800);
    },
    flag(selector, text) {
      if (!ensure()) return false;
      const el = find(selector);
      if (!el) return false;
      const stack = annotations.filter(a => a.kind === "flag" && a.el === el).length;
      annotate(el, "flag", (node, r) => {
        const b = boxEl(r, FAIL, text || "FAIL");
        b.querySelector(".lbl").style.top = `${-18 - stack * 18}px`;  // several faults on one element
        node.appendChild(b);
      });
      return true;
    },

    clear(kind) {
      for (const a of annotations) if (!kind || a.kind === kind) a.node.remove();
      annotations = annotations.filter(a => a.node.isConnected);
      for (const name of Object.keys(cursors)) note(name, null);
    },

    /** B12: remove every trace of the AI overlay; the page is the user's again. */
    handover() {
      handedOver = true;
      host?.remove();
      return true;
    },

    /** A new build after B12 (next page / refinement): the swarm comes back. */
    resume() {
      handedOver = false;
      return ensure();
    },

    state() {
      return {
        installed: !!host?.isConnected, handed_over: handedOver, master: masterOn,
        cursors: Object.fromEntries(Object.entries(cursors).map(([k, c]) => [k, { x: Math.round(c.x), y: Math.round(c.y) }])),
        annotations: annotations.map(a => a.kind), hud: hud?.textContent ?? null,
      };
    },
  };

  Object.defineProperty(window, "__chromaSwarm", { value: api, configurable: false, writable: false });

  // Attach once the page has painted, and keep re-attaching if a re-render removes the host.
  const boot = () => {
    if (!ensure()) return;
    new MutationObserver(() => { if (!handedOver && host && !host.isConnected) ensure(); })
      .observe(document.documentElement, { childList: true, subtree: true });
  };
  if (document.readyState === "complete") boot(); else addEventListener("load", boot, { once: true });
})();
