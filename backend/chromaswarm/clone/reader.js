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

  // A header whose own box is empty (0px: its bar is position: fixed / sticky inside it) counts as that bar.
  const pinnedIn = c => {
    if (c.getBoundingClientRect().height >= 16 || !(c.tagName === "HEADER" || c.querySelector("nav"))) return null;
    // The bar that holds the navigation (a promo strip above it is a separate fixed box): the tallest such one.
    const bars = [...c.querySelectorAll("nav, header, div")].filter(d => {
      const pos = getComputedStyle(d).position, r = d.getBoundingClientRect();
      return (pos === "fixed" || pos === "sticky") && r.width >= vw * 0.9 && r.height >= 32 && r.height < 240 && visible(d);
    });
    // Every bar of it, top to bottom: the announcement strip above the navigation is a section of its own.
    // (A bar nested in another bar is that bar.)
    const outer = bars.filter(d => !bars.some(o => o !== d && o.contains(d)));
    const withNav = outer.filter(d => d.tagName === "NAV" || d.querySelector("nav") || d.querySelectorAll("a, button").length >= 2);
    if (!withNav.length && !outer.length) return null;
    return outer.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
  };
  // Descend through single full-width wrappers (#__next, main, div.page...) to the section list
  // (a 0px header holding a fixed bar counts as a child: the descent must not walk past it).
  let root = document.body;
  for (let i = 0; i < 8; i++) {
    const kids = [...root.children].flatMap(c => pinnedIn(c) || [c]).filter(visible).filter(k => !/^(SCRIPT|STYLE|NOSCRIPT)$/.test(k.tagName));
    if (kids.length === 1 && kids[0].getBoundingClientRect().width >= vw * 0.9) root = kids[0];
    else break;
  }
  // 16px keeps one-line headings / paragraphs; the grouping below attaches them to the next block.
  const kidsOf = el => [...el.children].flatMap(c => pinnedIn(c) || [c]).filter(visible).filter(c => c.getBoundingClientRect().height >= 16
    && !/^(SCRIPT|STYLE|NOSCRIPT|BR|HR)$/.test(c.tagName));
  // Fixed-position boxes narrower than half the page (promo widgets, chat bubbles) float over the page:
  // they are not sections. A fixed full-width header stays.
  const floating = el => getComputedStyle(el).position === "fixed" && el.getBoundingClientRect().width < vw * 0.5;
  let blocks = kidsOf(root).filter(el => !floating(el));
  // Wrappers hide the real sections: expand <main>, and any block taller than ~2 screens that
  // holds several blocks of its own (e.g. one 9000px div around the whole page), a few levels deep.
  // A row of tall side-by-side children is a column layout: the columns are containers, not sections.
  const columnsOf = el => {
    const kids = kidsOf(el);
    if (kids.length < 2) return null;
    const rs = kids.map(k => k.getBoundingClientRect());
    const sideBySide = rs.some((r, i) => rs.some((q, j) => j !== i && q.left >= r.right - 4 && q.top < r.bottom && r.top < q.bottom));
    // Page columns (content + sidebar): exactly two, spanning most of the width, one of them long.
    // A row of 3+ equal cards is a card grid, not columns.
    const span = Math.max(...rs.map(r => r.right)) - Math.min(...rs.map(r => r.left));
    const isColumns = kids.length === 2 && sideBySide && span >= vw * 0.7
      && rs.every(r => r.height >= 300) && rs.some(r => r.height >= 600);
    return isColumns ? kids : null;
  };
  const columnSet = new Set();
  for (let depth = 0; depth < 6; depth++) {
    let changed = false;
    blocks = blocks.flatMap(el => {
      const kids = kidsOf(el);
      const tall = el.getBoundingClientRect().height > innerHeight * 2;
      const cols = columnsOf(el);
      if (cols && !el.querySelector(":scope > h1, :scope > h2")) { changed = true; cols.forEach(c => columnSet.add(c)); return cols; }
      if (kids.length >= 2 && columnSet.has(el)) { changed = true; return kids; }  // a column holds sections
      if (kids.length >= 1 && (el.tagName === "MAIN" || tall)) { changed = true; return kids; }  // single wrappers too
      return [el];
    });
    if (!changed) break;
  }
  blocks = blocks.filter(el => !floating(el));
  // Lone headings / paragraphs / link strips belong to the section after them (their text is counted
  // there); a run of them with nothing after it becomes a text section of its own. Navigation is kept.
  const isNav = el => el.tagName === "HEADER" || el.tagName === "NAV" || !!el.querySelector("nav");
  const isLoose = el => {
    if (isNav(el) || el.tagName === "H1" || el.querySelector("h1")) return false;  // the hero is never loose
    if (/^(H2|H3|H4|P|A|UL|SPAN)$/.test(el.tagName)) return true;  // a bare text element
    return el.getBoundingClientRect().height < 120 && !el.querySelector("img, picture, video, canvas, svg, button, input");
  };
  const grouped = [];
  let pending = [];
  const sameColumn = (a, b) => Math.abs(a.getBoundingClientRect().left - b.getBoundingClientRect().left) < 200;
  blocks.forEach((el, i) => {
    if (i > 0 && i < blocks.length - 1 && isLoose(el)) { pending.push(el); return; }
    if (pending.length && !sameColumn(pending[0], el)) {  // text that ends another column stands alone
      grouped.push({ el: null, lead: pending }); pending = [];
    }
    grouped.push({ el, lead: pending }); pending = [];
  });
  if (pending.length) grouped.splice(grouped.length - 1, 0, { el: null, lead: pending });  // before the footer
  const leadText = lead => lead.map(text).join(" ").trim();

  // Clickable rows whose first line is a question (only counted: no text leaves the page).
  const questionRows = el => [...el.querySelectorAll("summary, button, [role=button], [aria-expanded]")].filter(b => {
    const first = (b.innerText || "").split("\n").map(t => t.trim()).find(Boolean) || "";
    return first.length >= 8 && /[?？]$/.test(first);
  }).length;

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

  // Testimonial cards: a long sentence followed by a short "Role, Company" line.
  const ROLE = /(engineer|designer|founder|ceo|cto|head of|director|manager|giám đốc|trưởng|nhà sáng lập|khách hàng)/i;
  function attributions(el) {
    let n = 0;
    for (const card of el.querySelectorAll("figure, article, li, a, div")) {
      const lines = (card.innerText || "").split("\n").map(t => t.trim()).filter(Boolean);
      // The quote and the role line are different lines (a post title like "… for Product Designers" is not a card).
      const quote = lines.findIndex(l => l.length >= 60);
      if (lines.length >= 2 && lines.length <= 5 && quote >= 0
          && lines.some((l, i) => i !== quote && l.length < 60 && ROLE.test(l))) n++;
      if (n >= 4) break;
    }
    return n >= 2 ? 2 : 0;
  }

  // Testimonial cards drawn with a small round avatar next to a long sentence (quote mark often a background image).
  function avatarCards(el) {
    const cards = new Set();
    for (const img of el.querySelectorAll("img")) {
      const r = img.getBoundingClientRect();
      if (!visible(img) || r.width > 96 || r.width < 24) continue;
      const round = [img, img.parentElement].some(n => /50%|9999|999px/.test(getComputedStyle(n).borderRadius)
        || px(getComputedStyle(n).borderRadius) >= r.width / 2 - 1);
      if (!round) continue;
      const card = img.closest("article, li, figure:not(:has(> img:only-child)), blockquote") || img.parentElement?.parentElement?.parentElement;
      if (card && card !== el && [...card.querySelectorAll("p, blockquote, div")].some(n => ownText(n).length >= 60)) cards.add(card);
    }
    return cards.size >= 2 ? 2 : 0;
  }

  // A vertical list of one-line rows (blog posts with dates, work history): ≥3 stacked siblings, each short
  // and wide, with text at both ends of the row.
  function listRows(el) {
    let best = [];
    for (const parent of [el, ...el.querySelectorAll("*")].slice(0, 400)) {
      const kids = [...parent.children].filter(visible);
      if (kids.length < 3) continue;
      const rows = kids.filter(k => {
        const r = k.getBoundingClientRect();
        const parts = (k.innerText || "").split("\n").filter(t => t.trim()).length;  // entry + meta, not a bare bullet
        return r.height >= 16 && r.height < 100 && r.width >= 320 && parts >= 2 && !k.querySelector("img, video, canvas, input")
          && Math.abs(r.left - kids[0].getBoundingClientRect().left) < 4;
      });
      if (rows.length >= 3 && rows.length >= kids.length * 0.6 && rows.length > best.length) best = rows;
    }
    return best;
  }

  const pageBg = getComputedStyle(document.body).backgroundColor;
  const out = [];
  grouped.forEach(({ el: blockEl, lead }, index) => {
    const el = blockEl || lead[0];
    const r = blockEl ? blockEl.getBoundingClientRect() : (() => {
      const rs = lead.map(l => l.getBoundingClientRect());
      return { top: Math.min(...rs.map(x => x.top)), left: Math.min(...rs.map(x => x.left)),
               width: Math.max(...rs.map(x => x.width)), height: rs.reduce((a, x) => a + x.height, 0) };
    })();
    const cs = getComputedStyle(el);
    const cols = columns(el);
    const imgs = [...el.querySelectorAll("img")].filter(visible);
    // Visual media of any kind: product shots are often <video>, <canvas>, inline <svg> or <picture>.
    const media = [...el.querySelectorAll("img, picture, video, canvas, svg")].filter(visible).filter(m => {
      const r = m.getBoundingClientRect();
      return r.width >= 120 && r.height >= 80 && !m.parentElement.closest("svg");
    });
    const bigImg = media.some(i => i.getBoundingClientRect().width >= vw * 0.35);
    const heading = el.querySelector("h1, h2, h3");
    const listEls = listRows(el);
    const features = {
      tag: blockEl ? el.tagName.toLowerCase() : "text", role: el.getAttribute("role"), index, height: Math.round(r.height),
      // A fixed bar sits at its window place whatever the scroll: its page top is that place.
      top: Math.round(r.top + (blockEl && getComputedStyle(blockEl).position === "fixed" ? 0 : scrollY)), left: Math.round(r.left), width: Math.round(r.width),
      h1: !!el.querySelector("h1") || lead.some(l => l.tagName === "H1" || l.querySelector("h1")),
      headings: (blockEl ? el.querySelectorAll("h1,h2,h3,h4").length : 0) + lead.filter(l => /^H[1-4]$/.test(l.tagName) || l.querySelector("h1,h2,h3,h4")).length,
      lead_text: leadText(lead).length,
      nav: !!el.querySelector("nav") || el.tagName === "NAV", links: el.querySelectorAll("a").length,
      buttons: el.querySelectorAll("button, a[class*=btn], a[class*=button], [role=button]").length,
      inputs: el.querySelectorAll("input:not([type=hidden]), textarea, select").length,
      password: !!el.querySelector("input[type=password]"),
      accordion: Math.max(el.querySelectorAll("details, [aria-expanded]").length, questionRows(el)),
      // Rows that ask something (their label ends with "?"): an FAQ, not a list of features that open.
      questions: questionRows(el),
      tablist: !!el.querySelector("[role=tablist]"), images: media.length, big_image: bigImg,
      bg_differs: cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== pageBg,
      bg_image: cs.backgroundImage !== "none" || (media[0] && media[0].getBoundingClientRect().width >= vw * 0.9),
      columns: cols.count, scroller: scroller(el), text_len: (blockEl ? text(el).length : 0) + leadText(lead).length,
      prices: (text(el).match(new RegExp(priceRe, "gi")) || []).length,
      numeric_items: cols.items.filter(i => /^\s*[\d.,%+<>~]+/.test(text(i))).length,
      card_widths: cols.items.map(i => Math.round(i.getBoundingClientRect().width)),
      // Testimonials: blockquotes, or text blocks (at any depth) whose own text opens with a quote mark.
      quotes: el.querySelectorAll("blockquote").length + [...el.querySelectorAll("p, div, span, h3, h4, figure, q")].filter(n => {
        const t = ownText(n);
        if (t.length <= 30) return false;
        const before = getComputedStyle(n, "::before").content || "";
        return /^[“"«]/.test(t) || /[“"«]/.test(before.replace(/^"|"$/g, "")) || n.tagName === "Q";
      }).length + attributions(el) + avatarCards(el),
      rows: listEls.length,
      row_items_with_img: cols.items.filter(i => [...i.querySelectorAll("img, picture, video, canvas, svg")].some(m => {
        const r = m.getBoundingClientRect(); return r.width >= 64 && r.height >= 64;
      })).length,
      logos: [...el.querySelectorAll("img, svg")].filter(visible).filter(m => {
        const r = m.getBoundingClientRect(); return r.height >= 24 && r.height <= 140 && r.width >= 48 && !m.parentElement.closest("svg");
      }).length,
      padding_y: Math.round(px(cs.paddingTop) + px(cs.paddingBottom)),
    };
    const block = { features };
    if (owned) {
      block.content = {
        heading: (lead.map(l => /^H[1-4]$/.test(l.tagName) ? text(l) : "").find(Boolean) || text(heading)).slice(0, 160),
        headings: [...el.querySelectorAll("h1, h2, h3")].filter(visible).map(text).filter(Boolean).slice(0, 8).map(t => t.slice(0, 160)),
        logo: (() => { const a = el.querySelector('a[href="/"], a[href="./"], a[href="#"], a'); return a ? text(a).slice(0, 60) : ""; })(),
        paragraphs: [...lead.filter(l => l.tagName === "P"), ...(blockEl ? el.querySelectorAll("p") : [])].filter(visible).map(text).filter(t => t.length > 20).slice(0, 4).map(t => t.slice(0, 400)),
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
        // List rows: the entry (longest line) and its meta (date, period: the last line).
        rows: listEls.slice(0, 10).map(r => {
          const lines = (r.innerText || "").split("\n").map(t => t.trim()).filter(Boolean);
          const title = lines.reduce((a, b) => (b.length > a.length ? b : a), "");
          return [title.slice(0, 120), lines.length > 1 ? lines[lines.length - 1].slice(0, 40) : ""];
        }),
        faqs: [...el.querySelectorAll("details")].slice(0, 8).map(d => [text(d.querySelector("summary")), text(d).replace(text(d.querySelector("summary")), "").trim().slice(0, 300)]),
        // Every visible run of words in reading order, with what it is (tag, size, weight, case, place, link)
        // so each template takes its own words by role: label, heading, paragraph, button, question, name…
        texts: (() => {
          const out = [], seen = new Set();
          const scope = blockEl ? [el] : lead;
          for (const root of scope) for (const n of root.querySelectorAll("h1,h2,h3,h4,h5,h6,p,span,a,button,li,label,blockquote,figcaption,small,strong,dt,dd,summary,div")) {
            if (out.length >= 220) break;
            const own = [...n.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent).join(" ").replace(/\s+/g, " ").trim();
            const leafy = !n.querySelector("h1,h2,h3,h4,h5,h6,p,a,button,li,blockquote") && text(n);
            const words = own.length >= 2 ? own : (leafy && n.tagName !== "DIV" ? text(n) : "");
            if (!words || !visible(n)) continue;
            const ctl = n.closest("a, button, [role=button], summary");
            const key = ctl && ctl !== n && seen.has(ctl) ? null : (ctl || n);
            if (key && seen.has(key)) continue;
            if (key) seen.add(key);
            const r = n.getBoundingClientRect(), s = getComputedStyle(n);
            const control = ctl ? (ctl.tagName === "A" ? "link" : "button") : null;
            let pinned = false;  // in a fixed bar: its page place is its window place
            for (let e = n; e && e !== document.body; e = e.parentElement) if (getComputedStyle(e).position === "fixed") { pinned = true; break; }
            out.push({ t: (ctl && ctl !== n ? text(ctl) : words).slice(0, 400), tag: n.tagName.toLowerCase(),
                       fs: Math.round(parseFloat(s.fontSize)), fw: Math.round(parseFloat(s.fontWeight)), tt: s.textTransform === "uppercase" ? "upper" : "",
                       x: Math.round(r.left), y: Math.round(r.top + (pinned ? 0 : scrollY)), w: Math.round(r.width), h: Math.round(r.height),
                       control, href: ctl && ctl.tagName === "A" ? ctl.getAttribute("href") : null,
                       quote: !!n.closest("blockquote, q") || /^[“"«]/.test(words) });
          }
          return out;
        })(),
        pics: [...el.querySelectorAll("img")].filter(visible).slice(0, 40).map(i => {
          const r = i.getBoundingClientRect();
          let pinned = false;
          for (let e = i; e && e !== document.body; e = e.parentElement) if (getComputedStyle(e).position === "fixed") { pinned = true; break; }
          return { src: i.currentSrc || i.src, alt: i.alt || "", x: Math.round(r.left), y: Math.round(r.top + (pinned ? 0 : scrollY)), w: Math.round(r.width), h: Math.round(r.height) };
        }).filter(p => /^https?:/.test(p.src)),
      };
    }
    out.push(block);
  });

  // Content width of the page: horizontal span of all blocks' content (text, media, controls) together, so a
  // two-column page counts both columns. Narrow single-column sites (~700-900px) keep that column in the rebuild.
  const extents = out.map((_, i) => grouped[i]).map(({ el: b, lead }) => {
    let l = Infinity, r = -Infinity;
    for (const root of [b, ...lead].filter(Boolean)) {
      for (const n of [root, ...root.querySelectorAll("h1, h2, h3, h4, p, li, img, a, button, input, figure")]) {
        if (n === root && b) continue;
        if (!visible(n)) continue;
        const q = n.getBoundingClientRect();
        // Carousels and marquees park items far off-screen: only what lies inside the viewport counts.
        if (q.width < 40 || q.right <= 0 || q.left >= vw) continue;
        l = Math.min(l, Math.max(0, q.left)); r = Math.max(r, Math.min(vw, q.right));
      }
    }
    return r > l ? [l, r] : null;
  }).filter(Boolean);
  const contentWidth = extents.length
    ? Math.round(Math.max(...extents.map(e => e[1])) - Math.min(...extents.map(e => e[0]))) : null;

  // How much of the page is pictures: area of visible media / area of the page (0-1). Pages where this is
  // high (portfolios, galleries) look very different without their own photos.
  function mediaShare() {
    const pageArea = vw * Math.max(document.documentElement.scrollHeight, innerHeight);
    let area = 0;
    for (const m of document.querySelectorAll("img, picture, video, canvas")) {
      const r = m.getBoundingClientRect();
      if (r.width >= 120 && r.height >= 80 && m.checkVisibility({ opacityProperty: true })) area += r.width * r.height;
    }
    return Math.round(Math.min(1, area / pageArea) * 100) / 100;
  }

  // Page language: the declared <html lang>; otherwise Vietnamese when a noticeable share of letters carry
  // Vietnamese diacritics. Only a ratio is computed, no text leaves the page.
  function pageLang() {
    const declared = (document.documentElement.getAttribute("lang") || "").trim();
    if (declared) return declared;
    const sample = (document.body.innerText || "").slice(0, 20000);
    const letters = (sample.match(/\p{L}/gu) || []).length;
    const viet = (sample.match(/[ăâđêôơưàảãạáằẳẵặắầẩẫậấèẻẽẹéềểễệếìỉĩịíòỏõọóồổỗộốờởỡợớùủũụúừửữựứỳỷỹỵý]/giu) || []).length;
    return letters && viet / letters > 0.03 ? "vi" : "en";
  }

  const first = sel => { const el = document.querySelector(sel); return el ? getComputedStyle(el).fontFamily.split(",")[0].replace(/["']/g, "").trim() : null; };
  return {
    url: location.href,
    title: document.querySelector('meta[property="og:site_name"]')?.content || document.title || location.hostname,
    description: owned ? (document.querySelector('meta[name="description"]')?.content || "") : "",
    heading_font: first("h1") || first("h2"), body_font: first("main p") || first("p") || first("body"),
    blocks: out, content_width: contentWidth, lang: pageLang(), media_share: mediaShare(),
  };
}
