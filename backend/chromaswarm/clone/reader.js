/*
 * Clone mode reader. Splits a live page into its top-level sections and measures
 * each one (layout features only). With `owned` = true it also returns the
 * section's text, link labels and image URLs; otherwise no content leaves the page.
 */
(owned) => {
  const px = v => parseFloat(v) || 0;
  const vw = document.documentElement.clientWidth;
  const visible = el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  };
  const text = el => (el?.innerText || "").replace(/\s+/g, " ").trim();
  const ownText = el => [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(" ").trim();

  // Descend through single full-width wrappers (#__next, main, div.page...) to the section list.
  let root = document.body;
  for (let i = 0; i < 8; i++) {
    const kids = [...root.children].filter(visible).filter(k => !/^(SCRIPT|STYLE|NOSCRIPT)$/.test(k.tagName));
    if (kids.length === 1 && kids[0].getBoundingClientRect().width >= vw * 0.9) root = kids[0];
    else break;
  }
  let blocks = [...root.children].filter(visible).filter(el => el.getBoundingClientRect().height >= 40);
  // A <main> among the blocks holds the page's real sections: expand it in place.
  blocks = blocks.flatMap(el => el.tagName === "MAIN" && el.children.length > 1
    ? [...el.children].filter(visible).filter(c => c.getBoundingClientRect().height >= 40) : [el]);

  const priceRe = /(\d[\d.,]*\s?(₫|đ|vnd|vnđ|\$|€|usd))|((\$|€)\s?\d)/i;

  function columns(el) {
    // Widest row of side-by-side siblings: kids whose vertical centre falls inside an anchor kid's
    // span (works when one column is vertically centred against a taller image).
    let best = 1, bestEls = [];
    for (const parent of [el, ...el.querySelectorAll("*")].slice(0, 400)) {
      const kids = [...parent.children].filter(visible).filter(k => {
        const r = k.getBoundingClientRect();
        return r.width >= 60 && r.height >= 30;
      });
      if (kids.length < 2) continue;
      for (const anchor of kids) {
        const a = anchor.getBoundingClientRect();
        const row = kids.filter(k => {
          const r = k.getBoundingClientRect(), mid = r.top + r.height / 2;
          return mid >= a.top && mid <= a.bottom;
        });
        if (row.length > best) { best = row.length; bestEls = row; }
      }
    }
    return { count: best, items: bestEls };
  }

  function scroller(el) {
    return [el, ...el.querySelectorAll("*")].slice(0, 400).some(n => {
      const o = getComputedStyle(n).overflowX;
      return (o === "auto" || o === "scroll") && n.scrollWidth > n.clientWidth + 40;
    });
  }

  const pageBg = getComputedStyle(document.body).backgroundColor;
  const out = [];
  blocks.forEach((el, index) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const cols = columns(el);
    const imgs = [...el.querySelectorAll("img")].filter(visible);
    const bigImg = imgs.some(i => i.getBoundingClientRect().width >= vw * 0.35);
    const heading = el.querySelector("h1, h2, h3");
    const features = {
      tag: el.tagName.toLowerCase(), role: el.getAttribute("role"), index, height: Math.round(r.height),
      top: Math.round(r.top + scrollY), h1: !!el.querySelector("h1"), headings: el.querySelectorAll("h1,h2,h3,h4").length,
      nav: !!el.querySelector("nav") || el.tagName === "NAV", links: el.querySelectorAll("a").length,
      buttons: el.querySelectorAll("button, a[class*=btn], a[class*=button], [role=button]").length,
      inputs: el.querySelectorAll("input:not([type=hidden]), textarea, select").length,
      password: !!el.querySelector("input[type=password]"),
      accordion: el.querySelectorAll("details, [aria-expanded]").length,
      tablist: !!el.querySelector("[role=tablist]"), images: imgs.length, big_image: bigImg,
      bg_differs: cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== pageBg,
      bg_image: cs.backgroundImage !== "none" || (imgs[0] && imgs[0].getBoundingClientRect().width >= vw * 0.9),
      columns: cols.count, scroller: scroller(el), text_len: text(el).length,
      prices: (text(el).match(new RegExp(priceRe, "gi")) || []).length,
      numeric_items: cols.items.filter(i => /^\s*[\d.,%+<>~]+/.test(text(i))).length,
      card_widths: cols.items.map(i => Math.round(i.getBoundingClientRect().width)),
      row_items_with_img: cols.items.filter(i => i.querySelector("img")).length,
      padding_y: Math.round(px(cs.paddingTop) + px(cs.paddingBottom)),
    };
    const block = { features };
    if (owned) {
      block.content = {
        heading: text(heading).slice(0, 160),
        headings: [...el.querySelectorAll("h1, h2, h3")].filter(visible).map(text).filter(Boolean).slice(0, 8).map(t => t.slice(0, 160)),
        logo: (() => { const a = el.querySelector('a[href="/"], a[href="./"], a[href="#"], a'); return a ? text(a).slice(0, 60) : ""; })(),
        paragraphs: [...el.querySelectorAll("p")].filter(visible).map(text).filter(t => t.length > 20).slice(0, 4).map(t => t.slice(0, 400)),
        buttons: [...el.querySelectorAll("button, a")].filter(visible).map(b => text(b)).filter(t => t && t.length <= 40).slice(0, 8),
        nav: [...el.querySelectorAll("nav a")].filter(visible).slice(0, 8).map(a => [text(a), a.getAttribute("href") || "#"]).filter(([t]) => t && t.length <= 30),
        images: imgs.slice(0, 8).map(i => i.currentSrc || i.src).filter(u => /^https?:/.test(u)),
        // Every card of the grid, not just its first row: all visible siblings of the row's items.
        items: (cols.items.length >= 2 ? [...cols.items[0].parentElement.children].filter(visible) : cols.items).slice(0, 8).map(i => {
          const lines = (i.innerText || "").split("\n").map(t => t.trim()).filter(Boolean);
          return {
          title: text(i.querySelector("h2,h3,h4,dt,strong,b")) || (lines[0] || "").slice(0, 60),
          note: text(i.querySelector("p,dd")).slice(0, 140) || (lines[1] || "").slice(0, 140),
          price: (text(i).match(priceRe) || [""])[0],
          image: (i.querySelector("img")?.currentSrc || i.querySelector("img")?.src || ""),
        }; }),
        faqs: [...el.querySelectorAll("details")].slice(0, 8).map(d => [text(d.querySelector("summary")), text(d).replace(text(d.querySelector("summary")), "").trim().slice(0, 300)]),
      };
    }
    out.push(block);
  });

  const first = sel => { const el = document.querySelector(sel); return el ? getComputedStyle(el).fontFamily.split(",")[0].replace(/["']/g, "").trim() : null; };
  return {
    url: location.href,
    title: document.querySelector('meta[property="og:site_name"]')?.content || document.title || location.hostname,
    description: owned ? (document.querySelector('meta[name="description"]')?.content || "") : "",
    heading_font: first("h1") || first("h2"), body_font: first("main p") || first("p") || first("body"),
    blocks: out,
  };
}
