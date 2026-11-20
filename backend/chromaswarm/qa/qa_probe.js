/*
 * ChromaSwarm Master QA probe (B11). Read-only DOM measurements for the four
 * tests of FRONTEND_STANDARDS.md chapter 5. Returns raw numbers and selectors;
 * Python decides pass/fail with the deterministic engines.
 */
(() => {
  if (window.__chromaQA) return;

  const pixel = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  function rgba(color) {
    pixel.clearRect(0, 0, 1, 1);
    pixel.fillStyle = "#000";
    pixel.fillStyle = color;
    pixel.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = pixel.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  }
  const rgb = c => `rgb(${c.map(Math.round).join(", ")})`;
  const px = v => parseFloat(v) || 0;

  function cssPath(el) {
    if (el.dataset?.swarmId) return `[data-swarm-id="${CSS.escape(el.dataset.swarmId)}"]`;
    if (el.id) return `#${CSS.escape(el.id)}`;
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
      if (n.dataset?.swarmSection) { parts.unshift(`[data-swarm-section="${CSS.escape(n.dataset.swarmSection)}"]`); break; }
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === n.tagName) i++;
      parts.unshift(`${n.tagName.toLowerCase()}:nth-of-type(${i})`);
    }
    return parts.join(" > ") || "body";
  }

  const visible = el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  };
  const sectionOf = el => el.closest("[data-swarm-section]")?.getAttribute("data-swarm-section") ?? null;
  const ownText = el => [...el.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join("").trim();
  const inFloating = el => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const p = getComputedStyle(n).position;
      if (p === "fixed" || p === "sticky" || n.getAttribute("role") === "dialog") return true;
    }
    return false;
  };
  const inHScroller = el => {
    for (let n = el.parentElement; n && n !== document.body; n = n.parentElement) {
      const o = getComputedStyle(n).overflowX;
      if ((o === "auto" || o === "scroll") && n.scrollWidth > n.clientWidth) return true;
    }
    return false;
  };
  const textBlocks = () => [...document.body.querySelectorAll("*")]
    .filter(el => !/^(SCRIPT|STYLE|NOSCRIPT|CHROMASWARM-OVERLAY)$/.test(el.tagName) && ownText(el) && visible(el));

  function overImage(el) {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage !== "none") return true;
      if (rgba(cs.backgroundColor)[3] >= 1) return false;
    }
    return false;
  }

  function effectiveBg(el) {
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = rgba(getComputedStyle(n).backgroundColor);
      if (c[3] > 0) layers.push(c);
      if (c[3] >= 1) break;
    }
    let out = [255, 255, 255];
    for (const [r, g, b, a] of layers.reverse()) out = [r * a + out[0] * (1 - a), g * a + out[1] * (1 - a), b * a + out[2] * (1 - a)];
    return out;
  }

  const HOVER_PROPS = ["background-color", "color", "border-top-color", "border-bottom-color", "transform", "filter",
    "box-shadow", "opacity", "text-decoration-line", "outline-style", "translate", "scale"];
  const FOCUS_PROPS = ["outline-style", "outline-width", "outline-color", "box-shadow", "border-top-color"];

  function props(el, list) {
    const cs = getComputedStyle(el);
    return list.map(p => cs.getPropertyValue(p)).join("|");
  }

  window.__chromaQA = {
    interactives() {
      const seen = new Set(), out = [];
      for (const el of document.querySelectorAll("button, a[href], input, select, textarea, [data-swarm-role]")) {
        if (seen.has(el) || !visible(el) || el.disabled) continue;
        seen.add(el);
        out.push({
          selector: cssPath(el), tag: el.tagName.toLowerCase(), role: el.dataset?.swarmRole ?? null,
          type: el.getAttribute("type"), href: el.getAttribute("href"), section: sectionOf(el),
          label: (el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || "").trim().slice(0, 40),
          inline_link: el.tagName === "A" && /^(P|LI|SPAN|LABEL)$/.test(el.parentElement?.tagName ?? ""),
        });
      }
      return out;
    },

    /** Style signature of an element and its children, with running transitions finished. */
    styleSig(selector) {
      const el = document.querySelector(selector);
      if (!el) return null;
      for (const a of el.getAnimations({ subtree: true })) { try { a.finish(); } catch {} }
      return [el, ...el.children].map(e => props(e, HOVER_PROPS)).join("§");
    },

    focusSig(selector) {
      const el = document.querySelector(selector);
      if (!el) return null;
      for (const a of el.getAnimations()) { try { a.finish(); } catch {} }
      return props(el, FOCUS_PROPS);
    },

    activeSelector() {
      const el = document.activeElement;
      return el && el !== document.body ? cssPath(el) : null;
    },

    /** Scrolls the element into view; returns its centre and what is actually on top there. */
    probe(selector) {
      const el = document.querySelector(selector);
      if (!el) return null;
      el.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" });
      const r = el.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      const top = document.elementFromPoint(x, y);
      return { x, y, w: r.width, h: r.height, covered: !!top && top !== el && !el.contains(top) && !top.contains(el),
               covered_by: top ? cssPath(top) : null };
    },

    /** Everything a click could legitimately change. */
    domSig() {
      const aria = [...document.querySelectorAll("[aria-expanded],[aria-selected],[aria-pressed],[aria-checked],[aria-invalid]")]
        .map(e => ["aria-expanded", "aria-selected", "aria-pressed", "aria-checked", "aria-invalid"].map(a => e.getAttribute(a)).join(","));
      const inputs = [...document.querySelectorAll("input, select, textarea")].map(e => e.type === "password" ? e.type : e.value);
      return [document.body.innerText.length, document.body.innerText.slice(0, 4000), aria.join(";"), inputs.join(";"),
        location.hash, document.querySelectorAll("[role=dialog]").length, document.body.querySelectorAll("*").length].join("¶");
    },

    overflow() {
      const de = document.documentElement, cw = de.clientWidth;
      let worst = null, worstW = 0;
      if (de.scrollWidth > cw) {
        for (const el of document.body.querySelectorAll("*")) {
          const r = el.getBoundingClientRect();
          if (r.right > cw + 1 && !inHScroller(el) && r.width > worstW) { worst = el; worstW = r.width; }
        }
      }
      return { scroll_w: de.scrollWidth, client_w: cw, offender: worst ? cssPath(worst) : null };
    },

    collisions(limit = 12) {
      const boxes = [...textBlocks(), ...document.querySelectorAll("button, input, select")]
        .filter(el => visible(el) && !inFloating(el) && !inHScroller(el))
        .map(el => ({ el, r: el.getBoundingClientRect() }));
      const out = [];
      for (let i = 0; i < boxes.length && out.length < limit; i++) {
        for (let j = i + 1; j < boxes.length && out.length < limit; j++) {
          const a = boxes[i], b = boxes[j];
          if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
          const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
          const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
          if (w > 2 && h > 2) out.push({ a: cssPath(a.el), b: cssPath(b.el), area: Math.round(w * h) });
        }
      }
      return out;
    },

    /** Mobile margins: text and controls must keep >= `min` px from both screen edges. */
    margins(min = 16) {
      const vw = document.documentElement.clientWidth, out = [];
      for (const el of [...textBlocks(), ...document.querySelectorAll("button, input, select, a")]) {
        if (!visible(el) || inHScroller(el) || inFloating(el)) continue;
        const r = el.getBoundingClientRect();
        if (r.width >= vw - 1) continue;  // intentional full-bleed block
        if (r.left < min - 0.5 || r.right > vw - min + 0.5)
          out.push({ selector: cssPath(el), section: sectionOf(el), left: Math.round(r.left), right: Math.round(vw - r.right) });
      }
      return out.slice(0, 20);
    },

    tapTargets(min = 48) {
      return this.interactives().filter(i => !i.inline_link).map(i => {
        const r = document.querySelector(i.selector).getBoundingClientRect();
        return { ...i, w: Math.round(r.width), h: Math.round(r.height) };
      }).filter(i => i.w < min || i.h < min);
    },

    /** Side-by-side targets (sharing a row) closer than `min` px. Stacked full-width rows
        such as accordions are a separate, conventional pattern and are not measured. */
    tapSpacing(min = 8) {
      const els = this.interactives().filter(i => !i.inline_link).map(i => document.querySelector(i.selector))
        .filter(el => el && !inHScroller(el));
      const out = [];
      for (let i = 0; i < els.length && out.length < 20; i++) {
        for (let j = i + 1; j < els.length && out.length < 20; j++) {
          const a = els[i], b = els[j];
          if (a.contains(b) || b.contains(a)) continue;
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          const rowOverlap = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
          if (rowOverlap <= Math.min(ra.height, rb.height) / 2) continue;  // not on the same row
          const gap = Math.max(rb.left - ra.right, ra.left - rb.right);
          if (gap >= -0.5 && gap < min - 0.5) out.push({ a: cssPath(a), b: cssPath(b), gap: Math.round(gap) });
        }
      }
      return out;
    },

    /** Chapter 6-7 measurements (Test 4). */
    components(longText = 200) {
      const controls = [], links = [], disabled = [], labels = [], asterisks = [], long = [];
      const weights = {};
      for (const el of document.querySelectorAll("input, select, textarea")) {
        if (!visible(el) || /^(hidden|submit|button|reset|image|range|color|file)$/.test(el.type)) continue;
        const cs = getComputedStyle(el);
        const native = /^(checkbox|radio)$/.test(el.type) && cs.appearance !== "none";
        const visibleLabel = [...(el.labels || [])].some(visible) || !!el.getAttribute("aria-labelledby");
        controls.push({
          selector: cssPath(el), type: el.type || el.tagName.toLowerCase(), native,
          border: rgb(rgba(cs.borderTopColor).slice(0, 3)), border_w: px(cs.borderTopWidth),
          bg: rgb(effectiveBg(el)), outside: rgb(effectiveBg(el.parentElement)),
          placeholder: el.getAttribute("placeholder") || "", visible_label: visibleLabel,
          aria_label: !!el.getAttribute("aria-label"),
        });
      }
      for (const el of document.querySelectorAll("a[href]")) {
        if (!visible(el) || !/^(P|LI|SPAN|LABEL|DD|TD)$/.test(el.parentElement?.tagName ?? "")) continue;
        links.push({ selector: cssPath(el), underline: getComputedStyle(el).textDecorationLine.includes("underline") });
      }
      for (const el of document.querySelectorAll("button, input, select, textarea, [aria-disabled=true]")) {
        if (!visible(el) || !(el.disabled || el.getAttribute("aria-disabled") === "true")) continue;
        disabled.push({ selector: cssPath(el), explained: !!el.getAttribute("aria-describedby") });
      }
      for (const el of document.querySelectorAll("a[href], button")) {
        if (!visible(el)) continue;
        labels.push({ selector: cssPath(el), text: (el.innerText || "").trim().replace(/\s+/g, " ").toLowerCase() });
      }
      for (const el of textBlocks()) {
        const cs = getComputedStyle(el);
        if (ownText(el) === "*") asterisks.push({ selector: cssPath(el), color: rgb(rgba(cs.color).slice(0, 3)) });
        const family = cs.fontFamily.split(",")[0].trim().replace(/^["']|["']$/g, "");
        (weights[family] ??= new Set()).add(px(cs.fontWeight) || 400);
        if (/^(P|LI|DD|BLOCKQUOTE)$/.test(el.tagName) && el.innerText.trim().length >= longText) {
          const fs = px(cs.fontSize);
          long.push({ selector: cssPath(el), chars: el.innerText.trim().length, font_size: fs,
                      line_height: +((px(cs.lineHeight) || fs * 1.2) / fs).toFixed(2), align: cs.textAlign });
        }
      }
      // Cards sharing a row whose images differ in height (the "ragged bento" defect).
      const ragged = [], byParent = new Map();
      for (const card of document.querySelectorAll("[data-swarm-role=card]")) {
        if (!visible(card) || inHScroller(card)) continue;
        if (!byParent.has(card.parentElement)) byParent.set(card.parentElement, []);
        byParent.get(card.parentElement).push(card);
      }
      for (const [parent, cards] of byParent) {
        const rows = new Map();
        for (const c of cards) {
          const top = Math.round(c.getBoundingClientRect().top / 4);
          const img = c.querySelector("img");
          if (img) (rows.get(top) ?? rows.set(top, []).get(top)).push(Math.round(img.getBoundingClientRect().height));
        }
        for (const hs of rows.values())
          if (hs.length > 1 && Math.max(...hs) - Math.min(...hs) > 8) { ragged.push({ selector: cssPath(parent), heights: hs }); break; }
      }
      // Share of the page painted with saturated background colour (accent discipline).
      const de = document.documentElement, pageArea = de.scrollWidth * de.scrollHeight;
      let accentArea = 0;
      for (const el of document.body.querySelectorAll("*")) {
        if (/^(IMG|SVG|VIDEO|CANVAS|PICTURE)$/i.test(el.tagName) || !visible(el)) continue;
        const [r, g, b, a] = rgba(getComputedStyle(el).backgroundColor);
        if (a < 0.9 || Math.max(r, g, b) - Math.min(r, g, b) <= 40) continue;
        const rect = el.getBoundingClientRect();
        accentArea += Math.min(rect.width, de.scrollWidth) * rect.height;
      }
      return { controls, links, disabled, labels, asterisks, long, ragged,
               accent_share: +(accentArea / pageArea).toFixed(3),
               weights: Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, [...v].sort()])) };
    },

    async scrollAudit() {
      const stops = [], step = innerHeight * 0.8;
      const sticky = [...document.querySelectorAll("body *")].filter(el => {
        const p = getComputedStyle(el).position;
        return (p === "sticky" || p === "fixed") && visible(el) && el.getBoundingClientRect().top <= 1;
      });
      scrollTo({ top: 0, behavior: "instant" });
      for (let y = 0; ; y += step) {
        scrollTo({ top: y, behavior: "smooth" });
        await new Promise(r => setTimeout(r, 120));
        for (const el of sticky) {
          const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
          stops.push({ selector: cssPath(el), y: Math.round(scrollY), top: Math.round(r.top), h: Math.round(r.height),
            bg_alpha: rgba(cs.backgroundColor)[3], blur: cs.backdropFilter !== "none" });
        }
        if (y >= document.documentElement.scrollHeight - innerHeight) break;
      }
      // The last smooth step may still be travelling: land on the very bottom before judging what is hidden,
      // so scroll-driven reveals near the end of the page have really been reached.
      scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" });
      await new Promise(r => setTimeout(r, 400));
      const stuck = [...document.body.querySelectorAll("*")].filter(el => {
        if (el.closest("[aria-hidden=true]")) return false;
        const r = el.getBoundingClientRect();
        return r.width > 8 && r.height > 8 && getComputedStyle(el).opacity === "0" && el.checkVisibility({ visibilityProperty: true });
      }).map(cssPath).slice(0, 10);
      const broken = [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(cssPath);
      scrollTo({ top: 0, behavior: "smooth" });
      await new Promise(r => setTimeout(r, 300));
      return { sticky: stops, stuck, broken_images: broken, viewport_h: innerHeight };
    },

    texts(limit = 500) {
      return textBlocks().slice(0, limit).map(el => {
        const cs = getComputedStyle(el), bg = effectiveBg(el), f = rgba(cs.color);
        const fg = [0, 1, 2].map(i => f[i] * f[3] + bg[i] * (1 - f[3]));
        return { selector: cssPath(el), section: sectionOf(el), fg: rgb(fg), bg: rgb(bg), over_image: overImage(el),
                 font_size: px(cs.fontSize), font_weight: px(cs.fontWeight) || 400 };
      });
    },

    fonts() {
      const first = el => el ? getComputedStyle(el).fontFamily.split(",")[0].trim().replace(/^["']|["']$/g, "") : null;
      return {
        heading: first(document.querySelector("h1, h2, h3")),
        body: first(document.querySelector("main p, p")),
      };
    },

    slop() {
      const all = [...document.body.querySelectorAll("*")].filter(visible);
      const colorRe = /(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^()]*\)|#[0-9a-f]{3,8}\b/gi;
      const gradients = [], centered = [], shadows = [], distorted = [];
      for (const el of all) {
        const cs = getComputedStyle(el);
        if (cs.backgroundImage.includes("gradient")) {
          const stops = (cs.backgroundImage.match(colorRe) || []).map(c => rgb(rgba(c).slice(0, 3)));
          gradients.push({ selector: cssPath(el), stops, clip_text: cs.backgroundClip === "text" || cs.webkitBackgroundClip === "text",
                           control: /^(BUTTON|A)$/.test(el.tagName) || !!el.closest("button") });
        }
        if (cs.textAlign === "center" && ownText(el)) {
          // Count the real line boxes of the text: a one-line link padded to a 48px tap target is not 3 lines.
          const range = document.createRange();
          range.selectNodeContents(el);
          const lines = new Set([...range.getClientRects()].filter(q => q.width > 1).map(q => Math.round(q.top / 4))).size;
          if (lines >= 3) centered.push({ selector: cssPath(el), lines });
        }
        if (cs.boxShadow !== "none") {
          for (const layer of cs.boxShadow.split(/,(?![^(]*\))/)) {
            const color = layer.match(colorRe)?.[0];
            const nums = layer.replace(colorRe, "").match(/-?\d+(\.\d+)?px/g) || [];
            const blur = px(nums[2] ?? "0");
            const alpha = color ? rgba(color)[3] : 1;
            if (blur >= 10 && alpha > 0.1) { shadows.push({ selector: cssPath(el), alpha: +alpha.toFixed(2), blur, floating: inFloating(el) }); break; }
          }
        }
        if (el.tagName === "IMG" && el.naturalWidth && cs.objectFit !== "cover" && cs.objectFit !== "contain") {
          const r = el.getBoundingClientRect();
          const drift = Math.abs(r.width / r.height - el.naturalWidth / el.naturalHeight) / (el.naturalWidth / el.naturalHeight);
          if (drift > 0.02) distorted.push({ selector: cssPath(el), drift: +drift.toFixed(3) });
        }
      }
      const headings = [...document.querySelectorAll("h1, h2, h3, h4")].filter(visible);
      const emoji = /^\s*(\p{Extended_Pictographic}|<svg)/u;
      const iconHeadings = headings.filter(h => emoji.test(h.textContent) || h.firstElementChild?.tagName === "svg").length;
      const ctas = [];
      for (const sec of document.querySelectorAll("[data-swarm-section]")) {
        const labels = new Set();
        for (const b of sec.querySelectorAll("button, a")) {
          if (!visible(b)) continue;
          const bg = rgba(getComputedStyle(b).backgroundColor);
          const [r, g, bl] = bg, sat = Math.max(r, g, bl) - Math.min(r, g, bl);
          if (bg[3] > 0.9 && sat > 40) labels.add(b.innerText.trim());
        }
        ctas.push({ section: sec.getAttribute("data-swarm-section"), filled: [...labels] });
      }
      // "centered title + 3 identical cards": a container with exactly 3 same-shaped children under a centered heading
      let tripleSections = 0;
      for (const sec of document.querySelectorAll("[data-swarm-section]")) {
        const h = sec.querySelector("h2, h3");
        if (!h || getComputedStyle(h).textAlign !== "center") continue;
        const trio = [...sec.querySelectorAll("*")].some(c => c.children.length === 3 &&
          new Set([...c.children].map(k => k.tagName + k.children.length + Math.round(k.getBoundingClientRect().width))).size === 1);
        if (trio) tripleSections++;
      }
      return { gradients, centered, shadows, distorted, icon_headings: iconHeadings, headings: headings.length, ctas,
               triple_card_sections: tripleSections, text: document.body.innerText.toLowerCase().slice(0, 20000) };
    },
  };
})();
