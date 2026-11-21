"""Section templates for the app pages of the sitemap (B2): cart & checkout, dashboards, settings &
billing, service menus, booking, the learning room, contact and a task workspace.

Each one is a working screen, not a picture of one: every control changes state (Master QA, test 1),
forms validate and show their error and success states, lists have an empty state, numbers use
tabular figures. Words live in the page's content file like every other section, and each fixed
Vietnamese string is registered with its English translation (`T`), so a page built in English
leaves no Vietnamese behind.
"""

from __future__ import annotations

import json
import re

from chromaswarm.developer.i18n import UI_EN

UI: dict[str, str] = {}


def T(vi: str, en: str) -> str:
    """A fixed UI string and its English form (developer/i18n.py replaces whole literals)."""
    UI[vi] = en
    UI_EN.setdefault(vi, en)
    return vi


_SCALED = re.compile(r"(\d+(?:[.,]\d+)?)\s*(k|nghìn|ngàn|tr|triệu)(?!\w)", re.I)


def _amount(price: str) -> int | None:
    """₫ amount of a price as Vietnamese shops write it: "120.000đ", "85k", "1,5tr", "2 triệu", "Từ 200.000₫"."""
    text = (price or "").strip()
    if m := _SCALED.search(text):
        unit = 1000 if m.group(2).lower() in ("k", "nghìn", "ngàn") else 1_000_000
        value = round(float(m.group(1).replace(",", ".")) * unit)
        return value if 1000 <= value <= 10**10 else None
    digits = re.sub(r"\D", "", text)
    return int(digits) if 3 <= len(digits) <= 10 else None


# ----------------------------------------------------------------- cart & checkout

for vi, en in [
    ("Giỏ hàng", "Cart"), ("Kiểm tra đơn trước khi đặt", "Review your order"), ("Tóm tắt đơn hàng", "Order summary"),
    ("Tạm tính", "Subtotal"), ("Phí giao hàng", "Shipping"), ("Tổng cộng", "Total"), ("Miễn phí", "Free"),
    ("Họ và tên", "Full name"), ("Số điện thoại", "Phone number"), ("Địa chỉ nhận hàng", "Delivery address"),
    ("Thanh toán", "Payment"), ("Đặt hàng", "Place order"), ("Đã đặt hàng", "Order placed"), ("Xoá", "Remove"),
    ("Giảm số lượng", "Decrease quantity"), ("Tăng số lượng", "Increase quantity"), ("Số lượng ${it.name}", "Quantity of ${it.name}"),
    ("Tiếp tục mua sắm", "Continue shopping"), ("Thanh toán khi nhận hàng", "Cash on delivery"),
    ("Chuyển khoản ngân hàng", "Bank transfer"), ("Ví điện tử", "E-wallet"), ("Cách thanh toán", "Payment method"),
    ("Bạn điền đủ họ tên, số điện thoại 10 số và địa chỉ nhé.", "Please fill in your name, a 10-digit phone number and address."),
    ("Giỏ hàng đang trống, bạn chọn thêm sản phẩm nhé.", "Your cart is empty — add a product first."),
    ("Cảm ơn bạn! Chúng tôi sẽ gọi xác nhận đơn trong 15 phút.", "Thank you! We will call to confirm within 15 minutes."),
    ("Miễn phí giao hàng cho đơn từ 500.000₫", "Free delivery on orders from 500,000₫"),
]:
    T(vi, en)


# The forms send through the order API (developer/order.py); its labels give the shared states.
ORDER_IMPORT = 'import { ORDER } from "@/content/order";\nconst ORDER_L = ORDER.labels;\n'
for vi, en in [("Địa chỉ và giờ mở cửa", "Address and opening hours"), ("Điện thoại", "Phone"),
               ("Email hoặc số điện thoại", "Email or phone"), ("Cảm ơn bạn! Chúng tôi đã nhận lời nhắn và sẽ trả lời sớm.", "Thank you! We got your message and will reply soon."),
               ("Bạn điền họ tên, email hoặc số điện thoại đúng định dạng và lời nhắn (ít nhất 10 ký tự) nhé.",
                "Please enter your name, a valid email or phone number and a message of at least 10 characters.")]:
    T(vi, en)


def cart_checkout(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    # The cart is what the visitor picked on the other pages (developer/cart.py); the page's own items
    # are only suggestions to add when it is empty — never invented lines, never invented prices.
    items = [{"name": i.name, "note": i.note, "image": i.image, "price": p}
             for i in c.items if (p := _amount(i.price))][:4]
    inner = '''        <div className="section-head"><p className="eyebrow">Giỏ hàng</p><h1 className="t-h2">Kiểm tra đơn trước khi đặt</h1></div>
        <div className="split split-7-5 align-start cart-layout">
          <div className="stack">
            {ready && lines.length === 0 && sent !== "done" && (
              <div className="stack">
                <p className="t-body muted" role="status">Giỏ hàng đang trống. <a href="/" className="btn-link" data-swarm-id="cart-continue" data-swarm-role="link">Tiếp tục mua sắm</a></p>
                {ITEMS.length > 0 && <ul className="cart-lines">
                  {ITEMS.map((it, i) => (
                    <li key={it.name} className="cart-line" data-swarm-id={`cart-suggest-${i + 1}`}>
                      <Art label={it.name} src={it.image} ratio="1 / 1" tone={i} sizes="112px" />
                      <div className="stack cart-line-body">
                        <div className="product-meta"><h2 className="t-h4">{it.name}</h2><span className="t-body price">{money(it.price)}</span></div>
                        <p className="t-caption muted">{it.note}</p>
                        <div className="row"><button type="button" className="btn btn-ghost" data-swarm-id={`cart-suggest-add-${i + 1}`}
                          data-swarm-role="button" onClick={() => addToCart(it)}>Thêm vào giỏ</button></div>
                      </div>
                    </li>
                  ))}
                </ul>}
              </div>
            )}
            <ul className="cart-lines">
              {lines.map((it, i) => (
                <li key={it.name} className="cart-line" data-swarm-id={`cart-line-${i + 1}`}>
                  <Art label={it.name} src={it.image} ratio="1 / 1" tone={i} sizes="112px" />
                  <div className="stack cart-line-body">
                    <div className="product-meta"><h2 className="t-h4">{it.name}</h2><span className="t-body price">{money(it.price * it.qty)}</span></div>
                    <p className="t-caption muted">{it.note}</p>
                    <div className="row">
                      <div className="stepper" role="group" aria-label={`Số lượng ${it.name}`}>
                        <button type="button" className="icon-btn" aria-label="Giảm số lượng" data-swarm-id={`qty-minus-${i + 1}`}
                          data-swarm-role="button" onClick={() => setCartQty(it.name, it.qty - 1)}>−</button>
                        <span className="t-body t-num" aria-live="polite">{it.qty}</span>
                        <button type="button" className="icon-btn" aria-label="Tăng số lượng" data-swarm-id={`qty-plus-${i + 1}`}
                          data-swarm-role="button" onClick={() => setCartQty(it.name, it.qty + 1)}>+</button>
                      </div>
                      <button type="button" className="btn-link" data-swarm-id={`remove-line-${i + 1}`} data-swarm-role="button"
                        onClick={() => setCartQty(it.name, 0)}>Xoá</button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {lines.length > 0 && <p className="t-caption muted">Miễn phí giao hàng cho đơn từ 500.000₫</p>}
          </div>
          <form className="card checkout" noValidate onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <h2 className="t-h3">Tóm tắt đơn hàng</h2>
            <dl className="summary">
              <div><dt className="t-body muted">Tạm tính</dt><dd className="t-body t-num">{money(subtotal)}</dd></div>
              <div><dt className="t-body muted">Phí giao hàng</dt><dd className="t-body t-num">{shipping ? money(shipping) : "Miễn phí"}</dd></div>
              <div className="summary-total"><dt className="t-h4">Tổng cộng</dt><dd className="t-h4 t-num">{money(subtotal + shipping)}</dd></div>
            </dl>
            <label htmlFor="co-name" className="t-body">Họ và tên</label>
            <input id="co-name" className="input" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)}
              aria-invalid={tried && !name.trim()} data-swarm-id="checkout-name" data-swarm-role="input" />
            <label htmlFor="co-phone" className="t-body">Số điện thoại</label>
            <input id="co-phone" type="tel" inputMode="tel" className="input" autoComplete="tel" value={phone}
              onChange={(e) => setPhone(e.target.value)} aria-invalid={tried && !phoneOk} data-swarm-id="checkout-phone" data-swarm-role="input" />
            <label htmlFor="co-address" className="t-body">Địa chỉ nhận hàng</label>
            <input id="co-address" className="input" autoComplete="street-address" value={address}
              onChange={(e) => setAddress(e.target.value)} aria-invalid={tried && !address.trim()} data-swarm-id="checkout-address" data-swarm-role="input" />
            <div className="stack choice-group" role="radiogroup" aria-label="Cách thanh toán">
              <span className="t-body">Thanh toán</span>
              {PAY.map((label, i) => (
                <button key={label} type="button" role="radio" aria-checked={pay === i} className={pay === i ? "choice is-active" : "choice"}
                  data-swarm-id={`pay-${i + 1}`} data-swarm-role="tab" onClick={() => setPay(i)}>{label}</button>
              ))}
            </div>
            <p className="t-caption form-error" role="alert">{error}</p>
            {sent === "done" ? (
              <div className="stack" role="status">
                <p className="t-body"><strong>{ORDER_L.done}{code}</strong></p>
                <p className="t-body muted">{ORDER_L.done_hint}</p>
              </div>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={sent === "sending"} data-swarm-id="place-order"
                data-swarm-role="button">{sent === "sending" ? ORDER_L.sending : "Đặt hàng"}</button>
            )}
            {sent === "offline" && <Undelivered summary={summary} id="checkout" />}
          </form>
        </div>'''
    body = '''  const lines = useCart();
  const ready = useHydrated();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [pay, setPay] = useState(0);
  const [tried, setTried] = useState(false);
  const [sent, setSent] = useState<"idle" | "sending" | "done" | "offline">("idle");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const subtotal = cartTotal(lines);
  const shipping = subtotal === 0 || subtotal >= 500000 ? 0 : 30000;
  const phoneOk = /^0\\d{9}$/.test(phone.replace(/\\s/g, ""));
  const summary = [...lines.map((l) => `${l.name} × ${l.qty} (${money(l.price * l.qty)})`),
    `${ORDER_L.total}: ${money(subtotal + shipping)}`, `${ORDER_L.name}: ${name}`, `${ORDER_L.phone}: ${phone}`,
    `${ORDER_L.address}: ${address}`, `${ORDER_L.payment}: ${PAY[pay]}`].join("\\n");
  const submit = async () => {
    setTried(true);
    if (!lines.length) return setError("Giỏ hàng đang trống, bạn chọn thêm sản phẩm nhé.");
    if (!name.trim() || !phoneOk || address.trim().length < 6) return setError("Bạn điền đủ họ tên, số điện thoại 10 số và địa chỉ nhé.");
    setError("");
    setSent("sending");
    // sent to the app's own API (developer/order.py); not delivered → the shop's own channels
    const r = await sendOrder({ source: "checkout", lines: lines.map((l) => ({ name: l.name, qty: l.qty })), name, contact: phone,
      address, pay: PAY[pay], note: `${ORDER_L.total}: ${money(subtotal + shipping)}` });
    if (r.ok) { setCode(r.id); setSent("done"); clearCart(); return; } // sent: the cart starts over
    if (r.errors) { setError(Object.values(r.errors)[0]); setSent("idle"); return; }
    setSent("offline"); // not sent: the cart stays, its summary goes out on the shop's own channels
  };
'''
    prelude = (f"\nconst ITEMS = {_js(items)};\nconst PAY = {_js(['Thanh toán khi nhận hàng', 'Chuyển khoản ngân hàng', 'Ví điện tử'])};\n"
               + ORDER_IMPORT)
    return _component(s, _root(s, "s-cart", inner), client=True, prelude=prelude, body=body)


# ----------------------------------------------------------------- dashboards

for vi, en in [
    ("Tổng quan", "Overview"), ("Khoảng thời gian", "Time range"), ("7 ngày", "7 days"), ("30 ngày", "30 days"),
    ("90 ngày", "90 days"), ("Doanh thu", "Revenue"), ("Đơn hàng", "Orders"), ("Khách mới", "New customers"),
    ("Tỉ lệ chuyển đổi", "Conversion rate"), ("Người dùng hoạt động", "Active users"), ("Đăng ký mới", "New sign-ups"),
    ("Doanh thu định kỳ", "Recurring revenue"), ("Tỉ lệ rời bỏ", "Churn rate"), ("Bài đã học", "Lessons done"),
    ("Giờ học", "Hours studied"), ("Điểm trung bình", "Average score"), ("Chuỗi ngày học", "Day streak"),
    ("so với kỳ trước", "vs previous period"), ("Số liệu chính", "Key figures"), ("Tiến độ của bạn", "Your progress"),
    ("Theo tháng", "By month"), ("Rê chuột hoặc dùng phím Tab trên từng cột để xem số liệu", "Hover or tab to a bar to read it"),
    ("Biểu đồ cột theo tháng", "Monthly bar chart"), ("Tháng ${p.label}: ${p.value}", "Month ${p.label}: ${p.value}"),
    ("Tháng ${SERIES[active].label}: ${SERIES[active].value}", "Month ${SERIES[active].label}: ${SERIES[active].value}"),
    ("Xu hướng 12 tháng", "12-month trend"), ("Cao nhất", "Peak"), ("Trung bình", "Average"),
]:
    T(vi, en)

KPI_SETS = {
    "shop": [("Doanh thu", 128_400_000, 0.12, "money"), ("Đơn hàng", 1284, 0.08, "count"),
             ("Khách mới", 342, -0.03, "count"), ("Tỉ lệ chuyển đổi", 3.4, 0.4, "pct")],
    "saas": [("Doanh thu định kỳ", 86_500_000, 0.06, "money"), ("Người dùng hoạt động", 2_480, 0.11, "count"),
             ("Đăng ký mới", 196, 0.18, "count"), ("Tỉ lệ rời bỏ", 2.1, -0.2, "pct")],
    "learn": [("Bài đã học", 24, 0.25, "count"), ("Giờ học", 31, 0.1, "count"),
              ("Điểm trung bình", 8.4, 0.05, "score"), ("Chuỗi ngày học", 12, 0.5, "count")],
}


def kpi_row(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    kind = "learn" if s.id in ("progress", "student-kpis") else "shop" if c.shop else "saas"
    kpis = [{"label": label, "value": value, "delta": delta, "kind": k} for label, value, delta, k in KPI_SETS[kind]]
    title = "Tiến độ của bạn" if kind == "learn" else "Số liệu chính"
    inner = '''        <div className="row between align-end">
          <div className="section-head"><p className="eyebrow">Tổng quan</p><h1 className="t-h2">''' + title + '''</h1></div>
          <div className="tabs" role="tablist" aria-label="Khoảng thời gian">
            {RANGES.map((r, i) => (
              <button key={r} type="button" role="tab" aria-selected={range === i} className={range === i ? "tab is-active" : "tab"}
                data-swarm-id={`range-tab-${i + 1}`} data-swarm-role="tab" onClick={() => setRange(i)}>{r}</button>
            ))}
          </div>
        </div>
        <dl className="kpis">
          {KPIS.map((k, i) => {
            const delta = k.delta * (range === 2 ? 1.6 : range === 0 ? 0.5 : 1);
            return (
              <div key={k.label} className="kpi" data-swarm-id={`kpi-${i + 1}`}>
                <dt className="t-caption muted">{k.label}</dt>
                <dd className="t-h2 t-num">{show(k.kind, k.value * (k.kind === "pct" || k.kind === "score" ? 1 : FACTOR[range]))}</dd>
                <dd className={delta >= 0 ? "delta is-up" : "delta is-down"}>
                  <span aria-hidden="true">{delta >= 0 ? "↑" : "↓"}</span> <span className="t-num">{Math.abs(delta * 100).toFixed(1)}%</span> <span className="muted">so với kỳ trước</span>
                </dd>
              </div>
            );
          })}
        </dl>'''
    prelude = (f"\nconst KPIS = {_js(kpis)};\nconst RANGES = {_js(['7 ngày', '30 ngày', '90 ngày'])};\n"
               "const FACTOR = [0.24, 1, 2.85];\n"
               "const show = (kind: string, n: number) =>\n"
               '  kind === "money" ? Math.round(n).toLocaleString("vi-VN") + "₫" : kind === "pct" ? n.toFixed(1) + "%" :\n'
               '  kind === "score" ? n.toFixed(1) : Math.round(n).toLocaleString("vi-VN");\n')
    return _component(s, _root(s, "s-kpis", inner), client=True, prelude=prelude, body="  const [range, setRange] = useState(1);\n")


def chart_panel(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    values = [42, 48, 45, 53, 61, 58, 66, 72, 69, 78, 84, 91]
    series = [{"label": f"{n:02d}", "value": v} for n, v in enumerate(values, 1)]
    inner = '''        <div className="split split-7-5 align-start">
          <figure className="card chart-card">
            <div className="row between">
              <h2 className="t-h3">Xu hướng 12 tháng</h2>
              <p className="t-caption muted" aria-live="polite">{active === null ? "Rê chuột hoặc dùng phím Tab trên từng cột để xem số liệu" : `Tháng ${SERIES[active].label}: ${SERIES[active].value}`}</p>
            </div>
            <svg viewBox="0 0 600 248" className="chart" role="img" aria-label="Biểu đồ cột theo tháng">
              {SERIES.map((p, i) => {
                const h = Math.round((p.value / MAX) * 200);
                return (
                  <g key={p.label}>
                    <rect x={i * 50 + 8} y={216 - h} width={34} height={h} rx={4} tabIndex={0} aria-label={`Tháng ${p.label}: ${p.value}`}
                      className={active === i ? "bar is-active" : "bar"} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
                      onFocus={() => setActive(i)} onBlur={() => setActive(null)} />
                    <text x={i * 50 + 25} y={240} textAnchor="middle" className="chart-label">{p.label}</text>
                  </g>
                );
              })}
            </svg>
          </figure>
          <dl className="stack chart-facts">
            <div className="kpi"><dt className="t-caption muted">Cao nhất</dt><dd className="t-h2 t-num">{MAX}</dd></div>
            <div className="kpi"><dt className="t-caption muted">Trung bình</dt><dd className="t-h2 t-num">{AVG}</dd></div>
          </dl>
        </div>'''
    prelude = (f"\nconst SERIES = {_js(series)};\nconst MAX = Math.max(...SERIES.map((p) => p.value));\n"
               "const AVG = Math.round(SERIES.reduce((t, p) => t + p.value, 0) / SERIES.length);\n")
    return _component(s, _root(s, "s-chart", inner), client=True, prelude=prelude,
                      body="  const [active, setActive] = useState<number | null>(null);\n")


# ----------------------------------------------------------------- data table

for vi, en in [
    ("Gần đây", "Recent"), ("Mã", "ID"), ("Khách hàng", "Customer"), ("Hạng mục", "Item"), ("Ngày", "Date"),
    ("Trạng thái", "Status"), ("Giá trị", "Amount"), ("Chờ xác nhận", "Pending"), ("Đang xử lý", "In progress"),
    ("Hoàn tất", "Completed"), ("Đã huỷ", "Cancelled"), ("Tìm theo mã hoặc tên", "Search by ID or name"),
    ("Lọc theo trạng thái", "Filter by status"), ("Không có dòng nào khớp bộ lọc.", "No rows match the filter."),
    ("Xoá bộ lọc", "Clear filters"), ("Sắp xếp theo giá trị", "Sort by amount"), ("Danh sách", "List"),
    ("Hiển thị ${rows.length} / ${ROWS.length} dòng", "Showing ${rows.length} of ${ROWS.length} rows"),
    ("Lịch hẹn của bạn", "Your bookings"), ("Đơn gần đây", "Recent orders"), ("Bài nộp gần đây", "Recent submissions"),
    ("Tìm kiếm trong bảng", "Search the table"), ("Bảng dữ liệu", "Data table"),
]:
    T(vi, en)

PEOPLE = ["Minh Anh", "Quốc Bảo", "Thu Hà", "Gia Huy", "Ngọc Lan", "Đức Long", "Bảo Châu", "Hải Nam"]
PEOPLE_EN = ["Alex Morgan", "Sam Lee", "Jordan Diaz", "Taylor Kim", "Riley Chen", "Casey Park", "Jamie Fox", "Drew Patel"]
for _vi, _en in zip(PEOPLE, PEOPLE_EN):
    T(_vi, _en)


def data_table(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    statuses = ["Chờ xác nhận", "Đang xử lý", "Hoàn tất", "Đã huỷ"]
    names = [i.name for i in c.items] or ["Hạng mục"]
    rows = [{"id": f"#{1048 - n}", "who": PEOPLE[n % len(PEOPLE)], "item": names[n % len(names)],
             "date": f"{18 - n:02d}/11", "status": statuses[(n * 3) % 4], "amount": 280000 + (n * 173000) % 1_400_000}
            for n in range(8)]
    title = {"my-bookings": "Lịch hẹn của bạn", "submissions": "Bài nộp gần đây"}.get(s.id, "Đơn gần đây")
    inner = '''        <div className="row between align-end">
          <div className="section-head"><p className="eyebrow">Gần đây</p><h2 className="t-h2">''' + title + '''</h2></div>
          <label className="row t-body table-search"><span className="visually-hidden">Tìm kiếm trong bảng</span>
            <input className="input" type="search" placeholder="Tìm theo mã hoặc tên" value={q} onChange={(e) => setQ(e.target.value)}
              data-swarm-id="table-search" data-swarm-role="input" />
          </label>
        </div>
        <div className="tabs" role="tablist" aria-label="Lọc theo trạng thái">
          {["Tất cả", ...STATUSES].map((st, i) => (
            <button key={st} type="button" role="tab" aria-selected={status === st} className={status === st ? "tab is-active" : "tab"}
              data-swarm-id={`status-tab-${i + 1}`} data-swarm-role="tab" onClick={() => setStatus(st)}>{st}</button>
          ))}
        </div>
        <div className="table-wrap" role="region" aria-label="Bảng dữ liệu" tabIndex={0}>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Mã</th><th scope="col">Khách hàng</th><th scope="col">Hạng mục</th><th scope="col">Ngày</th><th scope="col">Trạng thái</th>
                <th scope="col" aria-sort={desc ? "descending" : "ascending"} className="num">
                  <button type="button" className="sort" data-swarm-id="sort-amount" data-swarm-role="button" aria-label="Sắp xếp theo giá trị"
                    onClick={() => setDesc(!desc)}>Giá trị <span aria-hidden="true">{desc ? "↓" : "↑"}</span></button>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="t-num">{r.id}</td><td>{r.who}</td><td>{r.item}</td><td className="t-num">{r.date}</td>
                  <td><span className={`pill pill-${STATUSES.indexOf(r.status)}`}>{r.status}</span></td>
                  <td className="num t-num">{r.amount.toLocaleString("vi-VN")}₫</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length === 0 ? (
          <p className="t-body muted" role="status"><span>Không có dòng nào khớp bộ lọc.</span>{" "}
            <button type="button" className="btn-link" data-swarm-id="table-reset" data-swarm-role="button" onClick={() => { setQ(""); setStatus("Tất cả"); }}>Xoá bộ lọc</button></p>
        ) : (
          <p className="t-caption muted" role="status">{`Hiển thị ${rows.length} / ${ROWS.length} dòng`}</p>
        )}'''
    body = '''  const [q, setQ] = useState("");
  const [status, setStatus] = useState("Tất cả");
  const [desc, setDesc] = useState(true);
  const needle = q.trim().toLowerCase();
  const rows = ROWS.filter((r) => (status === "Tất cả" || r.status === status) &&
    (!needle || r.id.toLowerCase().includes(needle) || r.who.toLowerCase().includes(needle) || r.item.toLowerCase().includes(needle)))
    .sort((a, b) => (desc ? b.amount - a.amount : a.amount - b.amount));
'''
    return _component(s, _root(s, "s-table", inner), client=True,
                      prelude=f"\nconst ROWS = {_js(rows)};\nconst STATUSES = {_js(statuses)};\n", body=body)


# ----------------------------------------------------------------- settings & billing

for vi, en in [
    ("Cài đặt", "Settings"), ("Hồ sơ", "Profile"), ("Thông báo", "Notifications"), ("Bảo mật", "Security"),
    ("Tên hiển thị", "Display name"), ("Email liên hệ", "Contact email"), ("Lưu thay đổi", "Save changes"),
    ("Đã lưu", "Saved"), ("Chưa có thay đổi để lưu", "No changes to save"), ("Đã lưu thay đổi.", "Changes saved."),
    ("Email khi có đơn mới", "Email on new orders"), ("Bản tin hằng tuần", "Weekly digest"),
    ("Đăng nhập hai bước", "Two-step sign-in"), ("Cảnh báo đăng nhập lạ", "Unusual sign-in alerts"),
    ("Mục cài đặt", "Settings sections"), ("Tên hiển thị cần ít nhất 2 ký tự.", "Display name needs at least 2 characters."),
    ("Gói cước", "Plans"), ("Chọn gói phù hợp với nhóm của bạn", "Choose the plan that fits your team"),
    ("Theo tháng", "Monthly"), ("Theo năm (giảm 20%)", "Yearly (save 20%)"), ("Chu kỳ thanh toán", "Billing cycle"),
    ("Gói hiện tại", "Current plan"), ("Chọn gói này", "Choose this plan"), ("Đã chọn — chúng tôi gửi hoá đơn qua email", "Selected — invoice sent by email"),
    ("Khởi đầu", "Starter"), ("Nhóm", "Team"), ("Doanh nghiệp", "Business"), ("/tháng", "/month"),
    ("1 người dùng · 3 dự án", "1 user · 3 projects"), ("10 người dùng · dự án không giới hạn", "10 users · unlimited projects"),
    ("Không giới hạn người dùng · hỗ trợ riêng", "Unlimited users · dedicated support"), ("Phổ biến", "Popular"),
]:
    T(vi, en)


def settings_form(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    toggles = [{"group": 1, "label": "Email khi có đơn mới", "on": True}, {"group": 1, "label": "Bản tin hằng tuần", "on": False},
               {"group": 2, "label": "Đăng nhập hai bước", "on": False}, {"group": 2, "label": "Cảnh báo đăng nhập lạ", "on": True}]
    inner = '''        <div className="section-head"><p className="eyebrow">Cài đặt</p><h1 className="t-h2">''' + "{" + _js(c.brand) + "}" + '''</h1></div>
        <div className="settings">
          <nav className="settings-nav" aria-label="Mục cài đặt">
            {GROUPS.map((g, i) => (
              <button key={g} type="button" aria-current={group === i ? "page" : undefined} className={group === i ? "filter is-active" : "filter"}
                data-swarm-id={`settings-tab-${i + 1}`} data-swarm-role="tab" onClick={() => setGroup(i)}>{g}</button>
            ))}
          </nav>
          <form className="card settings-panel" noValidate onSubmit={(e) => { e.preventDefault(); save(); }}>
            {group === 0 ? (
              <>
                <label htmlFor="st-name" className="t-body">Tên hiển thị</label>
                <input id="st-name" className="input" value={name} onChange={(e) => { setName(e.target.value); setStatus(""); }}
                  aria-invalid={status === "error"} data-swarm-id="settings-name" data-swarm-role="input" />
                <label htmlFor="st-email" className="t-body">Email liên hệ</label>
                <input id="st-email" type="email" className="input" value={email} onChange={(e) => { setEmail(e.target.value); setStatus(""); }}
                  data-swarm-id="settings-email" data-swarm-role="input" />
              </>
            ) : (
              <ul className="stack toggles">
                {flags.map((t, i) => t.group === group && (
                  <li key={t.label} className="row between toggle-row">
                    <span className="t-body" id={`toggle-${i}`}>{t.label}</span>
                    <button type="button" role="switch" aria-checked={t.on} aria-labelledby={`toggle-${i}`} className={t.on ? "switch is-on" : "switch"}
                      data-swarm-id={`toggle-${i + 1}`} data-swarm-role="button"
                      onClick={() => { setFlags(flags.map((f, n) => (n === i ? { ...f, on: !f.on } : f))); setStatus(""); }}>
                      <span className="switch-knob" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="t-caption form-error" role="status">{status === "error" ? "Tên hiển thị cần ít nhất 2 ký tự." : status === "same" ? "Chưa có thay đổi để lưu" : status === "ok" ? "Đã lưu thay đổi." : ""}</p>
            <button type="submit" className="btn btn-primary" data-swarm-id="settings-save" data-swarm-role="button">{status === "ok" ? "Đã lưu" : "Lưu thay đổi"}</button>
          </form>
        </div>'''
    body = f'''  const [group, setGroup] = useState(0);
  const [name, setName] = useState({_js(c.brand)});
  const [email, setEmail] = useState("hello@example.com");
  const [flags, setFlags] = useState(TOGGLES);
  const [status, setStatus] = useState<"" | "ok" | "same" | "error">("");
  const [saved, setSaved] = useState(JSON.stringify([{_js(c.brand)}, "hello@example.com", TOGGLES]));
  const save = () => {{
    if (name.trim().length < 2) return setStatus("error");
    const now = JSON.stringify([name, email, flags]);
    if (now === saved) return setStatus("same");
    setSaved(now);
    setStatus("ok");
  }};
'''
    prelude = f"\nconst GROUPS = {_js(['Hồ sơ', 'Thông báo', 'Bảo mật'])};\nconst TOGGLES = {_js(toggles)};\n"
    return _component(s, _root(s, "s-settings", inner), client=True, prelude=prelude, body=body)


def plan_cards(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    plans = [{"name": "Khởi đầu", "price": 0, "note": "1 người dùng · 3 dự án"},
             {"name": "Nhóm", "price": 290000, "note": "10 người dùng · dự án không giới hạn"},
             {"name": "Doanh nghiệp", "price": 890000, "note": "Không giới hạn người dùng · hỗ trợ riêng"}]
    inner = '''        <div className="row between align-end">
          <div className="section-head"><p className="eyebrow">Gói cước</p><h2 className="t-h2">Chọn gói phù hợp với nhóm của bạn</h2></div>
          <div className="tabs" role="tablist" aria-label="Chu kỳ thanh toán">
            {CYCLES.map((label, i) => (
              <button key={label} type="button" role="tab" aria-selected={yearly === (i === 1)} className={yearly === (i === 1) ? "tab is-active" : "tab"}
                data-swarm-id={`cycle-tab-${i + 1}`} data-swarm-role="tab" onClick={() => setYearly(i === 1)}>{label}</button>
            ))}
          </div>
        </div>
        <ol className="plans">
          {PLANS.map((p, i) => (
            <li key={p.name} className={i === 1 ? "plan is-featured" : "plan"}>
              <div className="row between"><h3 className="t-h3">{p.name}</h3>{i === 1 && <span className="pill pill-2">Phổ biến</span>}</div>
              <p className="t-h2 t-num">{(yearly ? Math.round(p.price * 0.8) : p.price).toLocaleString("vi-VN")}₫<span className="t-body muted">/tháng</span></p>
              <p className="t-body muted">{p.note}</p>
              <button type="button" className={i === 1 ? "btn btn-primary" : "btn btn-ghost"} data-swarm-id={`plan-${i + 1}`} data-swarm-role="button"
                onClick={() => setChosen(i)}>{chosen === i ? "Gói hiện tại" : "Chọn gói này"}</button>
              {chosen === i && i !== 0 && <p className="t-caption muted" role="status">Đã chọn — chúng tôi gửi hoá đơn qua email</p>}
            </li>
          ))}
        </ol>'''
    prelude = f"\nconst PLANS = {_js(plans)};\nconst CYCLES = {_js(['Theo tháng', 'Theo năm (giảm 20%)'])};\n"
    return _component(s, _root(s, "s-plans", inner), client=True, prelude=prelude,
                      body="  const [yearly, setYearly] = useState(false);\n  const [chosen, setChosen] = useState(0);\n")


# ----------------------------------------------------------------- services & booking

for vi, en in [
    ("Bảng giá dịch vụ", "Service menu"), ("Dịch vụ", "Services"), ("phút", "min"), ("Đặt lịch", "Book"),
    ("Thời lượng", "Duration"), ("Đặt lịch hẹn", "Book an appointment"), ("Chọn dịch vụ", "Choose a service"),
    ("Chọn ngày", "Choose a day"), ("Chọn giờ", "Choose a time"), ("Hết chỗ", "Full"),
    ("Xác nhận đặt lịch", "Confirm booking"), ("Đã đặt lịch", "Booked"),
    ("Bạn chọn ngày, giờ và điền họ tên, số điện thoại nhé.", "Please pick a day and time and enter your name and phone."),
    ("Đã giữ chỗ cho bạn. Tin nhắn xác nhận sẽ được gửi tới số điện thoại của bạn.", "Your slot is held. A confirmation text is on its way."),
    ("Lịch trống trong 7 ngày tới", "Open slots in the next 7 days"), ("Giờ còn trống", "Available times"),
    ("Đã chọn", "Selected"),
]:
    T(vi, en)

SERVICES = {
    "default": [("Tư vấn lần đầu", 30, 0), ("Gói cơ bản", 45, 350000), ("Gói chuyên sâu", 60, 590000),
                ("Gói cao cấp", 90, 890000), ("Chăm sóc định kỳ", 45, 420000)],
}
for vi, en in [("Tư vấn lần đầu", "First consultation"), ("Gói cơ bản", "Essential"), ("Gói chuyên sâu", "In-depth"),
               ("Gói cao cấp", "Premium"), ("Chăm sóc định kỳ", "Regular care")]:
    T(vi, en)


def _services(c) -> list[dict]:
    names = [i.name for i in c.items[:5]]
    base = SERVICES["default"]
    return [{"name": names[n] if n < len(names) and c.shop is False and names[n] else name, "minutes": m, "price": p}
            for n, (name, m, p) in enumerate(base)]


def price_list(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    inner = '''        <div className="section-head"><p className="eyebrow">Dịch vụ</p><h2 className="t-h2">Bảng giá dịch vụ</h2></div>
        <ul className="price-list">
          {SERVICES.map((sv, i) => (
            <li key={sv.name} className={picked === i ? "price-row is-active" : "price-row"}>
              <div className="stack price-name"><h3 className="t-h4">{sv.name}</h3><span className="t-caption muted t-num">{`${sv.minutes} phút`}</span></div>
              <span className="price-leader" aria-hidden="true" />
              <span className="t-body price">{sv.price ? `${sv.price.toLocaleString("vi-VN")}₫` : "Miễn phí"}</span>
              <button type="button" className="btn btn-ghost" data-swarm-id={`service-book-${i + 1}`} data-swarm-role="button"
                aria-pressed={picked === i} onClick={() => setPicked(i)}>{picked === i ? "Đã chọn" : "Đặt lịch"}</button>
            </li>
          ))}
        </ul>
        {picked !== null && <p className="t-body" role="status"><a href="#booking" className="link-arrow">{SERVICES[picked].name} <span aria-hidden="true">→</span></a></p>}'''
    return _component(s, _root(s, "s-prices", inner), client=True, prelude=f"\nconst SERVICES = {_js(_services(c))};\n",
                      body="  const [picked, setPicked] = useState<number | null>(null);\n")


def booking_flow(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    slots = ["09:00", "09:45", "10:30", "13:30", "14:15", "15:00", "16:30", "17:15"]
    inner = '''        <div className="split split-7-5 align-start">
          <div className="stack">
            <div className="section-head"><p className="eyebrow">Lịch trống trong 7 ngày tới</p><h2 className="t-h2">Đặt lịch hẹn</h2></div>
            <label htmlFor="bk-service" className="t-body">Chọn dịch vụ</label>
            <select id="bk-service" className="input" value={service} onChange={(e) => setService(Number(e.target.value))}
              data-swarm-id="booking-service" data-swarm-role="input">
              {SERVICES.map((sv, i) => <option key={sv.name} value={i}>{sv.name}</option>)}
            </select>
            <span className="t-body">Chọn ngày</span>
            <div className="chips" role="radiogroup" aria-label="Chọn ngày">
              {days.map((d, i) => (
                <button key={d.key} type="button" role="radio" aria-checked={day === i} className={day === i ? "chip is-active" : "chip"}
                  data-swarm-id={`booking-day-${i + 1}`} data-swarm-role="tab" onClick={() => { setDay(i); setTime(null); }}>
                  <span className="t-caption">{d.weekday}</span><span className="t-h4 t-num">{d.day}</span>
                </button>
              ))}
            </div>
            <span className="t-body">Giờ còn trống</span>
            <div className="chips" role="radiogroup" aria-label="Chọn giờ">
              {SLOTS.map((t, i) => {
                const full = day !== null && (i + day * 3) % 5 === 0;
                return (
                  <button key={t} type="button" role="radio" aria-checked={time === t} disabled={day === null || full}
                    className={time === t ? "chip is-active" : "chip"} data-swarm-id={`booking-time-${i + 1}`} data-swarm-role="tab"
                    onClick={() => setTime(t)}><span className="t-num">{t}</span>{full && <span className="t-caption muted">Hết chỗ</span>}</button>
                );
              })}
            </div>
          </div>
          <form className="card checkout" noValidate onSubmit={(e) => { e.preventDefault(); confirm(); }}>
            <h3 className="t-h3">{SERVICES[service].name}</h3>
            <p className="t-body muted t-num">{`${SERVICES[service].minutes} phút`}{day !== null ? ` · ${days[day].day}/${days[day].month}` : ""}{time ? ` · ${time}` : ""}</p>
            <label htmlFor="bk-name" className="t-body">Họ và tên</label>
            <input id="bk-name" className="input" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)}
              aria-invalid={tried && !name.trim()} data-swarm-id="booking-name" data-swarm-role="input" />
            <label htmlFor="bk-phone" className="t-body">Số điện thoại</label>
            <input id="bk-phone" type="tel" inputMode="tel" className="input" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
              aria-invalid={tried && !phoneOk} data-swarm-id="booking-phone" data-swarm-role="input" />
            <p className="t-caption form-error" role="alert">{error}</p>
            {sent === "done" ? (
              <div className="stack" role="status">
                <p className="t-body"><strong>{ORDER_L.done}{code}</strong></p>
                <p className="t-body muted">{ORDER_L.done_hint}</p>
              </div>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={sent === "sending"} data-swarm-id="booking-confirm"
                data-swarm-role="button">{sent === "sending" ? ORDER_L.sending : "Xác nhận đặt lịch"}</button>
            )}
            {sent === "offline" && <Undelivered summary={summary} id="booking" />}
          </form>
        </div>'''
    body = '''  const [service, setService] = useState(1);
  const [day, setDay] = useState<number | null>(null);
  const [time, setTime] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [tried, setTried] = useState(false);
  const [sent, setSent] = useState<"idle" | "sending" | "done" | "offline">("idle");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [days, setDays] = useState(DAYS);
  useEffect(() => {  // real dates, computed on the visitor's clock (never at build time)
    const now = new Date();
    setDays(Array.from({ length: 7 }, (_, i) => {
      const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i + 1);
      return { key: d.toISOString().slice(0, 10), weekday: WEEKDAYS[d.getDay()], day: d.getDate(), month: d.getMonth() + 1 };
    }));
  }, []);
  const phoneOk = /^0\\d{9}$/.test(phone.replace(/\\s/g, ""));
  const when = day !== null ? `${days[day].day}/${days[day].month}${time ? ` ${ORDER_L.at} ${time}` : ""}` : "";
  const summary = [SERVICES[service].name, when, `${ORDER_L.name}: ${name}`, `${ORDER_L.phone}: ${phone}`].filter(Boolean).join("\\n");
  const confirm = async () => {
    setTried(true);
    if (day === null || !time || !name.trim() || !phoneOk) return setError("Bạn chọn ngày, giờ và điền họ tên, số điện thoại nhé.");
    setError("");
    setSent("sending");
    const r = await sendOrder({ source: "booking", item: SERVICES[service].name, date: days[day].key, time, name, contact: phone });
    if (r.ok) { setCode(r.id); setSent("done"); return; }
    if (r.errors) { setError(Object.values(r.errors)[0]); setSent("idle"); return; }
    setSent("offline");
  };
'''
    weekdays = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
    days = [{"key": f"d{i}", "weekday": weekdays[(i + 1) % 7], "day": 20 + i, "month": 11} for i in range(7)]
    prelude = (f"\nconst SERVICES = {_js(_services(c))};\nconst SLOTS = {json.dumps(slots)};\n"
               f"const WEEKDAYS = {_js(weekdays)};\nconst DAYS = {_js(days)};\n" + ORDER_IMPORT)
    code = _component(s, _root(s, "s-booking", inner), client=True, prelude=prelude, body=body)
    return code.replace('import { useState } from "react";', 'import { useEffect, useState } from "react";', 1)


for vi, en in [("CN", "Sun"), ("T2", "Mon"), ("T3", "Tue"), ("T4", "Wed"), ("T5", "Thu"), ("T6", "Fri"), ("T7", "Sat")]:
    T(vi, en)


# ----------------------------------------------------------------- learning room

for vi, en in [
    ("Phòng học", "Learning room"), ("Danh sách bài học", "Lessons"), ("Đánh dấu đã học xong", "Mark as complete"),
    ("Đã học xong", "Completed"), ("Bài tiếp theo", "Next lesson"), ("Tiến độ khoá học", "Course progress"),
    ("Bài ${current + 1}", "Lesson ${current + 1}"), ("${sv.minutes} phút", "${sv.minutes} min"), ("${l.minutes} phút", "${l.minutes} min"), ("${SERVICES[service].minutes} phút", "${SERVICES[service].minutes} min"), ("Video bài học", "Lesson video"), ("Ghi chú bài học", "Lesson notes"),
    ("Làm quen và mục tiêu khoá học", "Welcome and course goals"), ("Nền tảng cần nắm", "Core foundations"),
    ("Thực hành có hướng dẫn", "Guided practice"), ("Bài tập tình huống", "Case exercise"), ("Tổng kết và bước tiếp theo", "Wrap-up and next steps"),
    ("Đã hoàn thành khoá học — chúc mừng bạn!", "Course complete — congratulations!"),
]:
    T(vi, en)


def lesson_player(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    lessons = [{"title": t, "minutes": m} for t, m in [("Làm quen và mục tiêu khoá học", 8), ("Nền tảng cần nắm", 14),
               ("Thực hành có hướng dẫn", 22), ("Bài tập tình huống", 18), ("Tổng kết và bước tiếp theo", 9)]]
    inner = '''        <div className="learn">
          <nav className="stack learn-list" aria-label="Danh sách bài học">
            <p className="eyebrow">Phòng học</p>
            <div className="progress" role="progressbar" aria-label="Tiến độ khoá học" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
              <span style={{ width: `${pct}%` }} />
            </div>
            <p className="t-caption muted t-num">{pct}%</p>
            <ol className="stack">
              {LESSONS.map((l, i) => (
                <li key={l.title}>
                  <button type="button" aria-current={current === i ? "step" : undefined} className={current === i ? "lesson is-active" : "lesson"}
                    data-swarm-id={`lesson-${i + 1}`} data-swarm-role="tab" onClick={() => setCurrent(i)}>
                    <span className={done.includes(i) ? "lesson-mark is-done" : "lesson-mark"} aria-hidden="true">{done.includes(i) ? "✓" : i + 1}</span>
                    <span className="stack lesson-text"><span className="t-body">{l.title}</span><span className="t-caption muted t-num">{`${l.minutes} phút`}</span></span>
                  </button>
                </li>
              ))}
            </ol>
          </nav>
          <article className="stack learn-main">
            <Art label="Video bài học" ratio="16 / 9" tone={current} sizes="(min-width: 1024px) 66vw, 100vw" />
            <p className="eyebrow">{`Bài ${current + 1}`}</p>
            <h1 className="t-h2">{LESSONS[current].title}</h1>
            <p className="t-lead">''' + "{" + _js(c.subhead) + "}" + '''</p>
            <div className="row">
              <button type="button" className="btn btn-primary" data-swarm-id="lesson-complete" data-swarm-role="button"
                onClick={() => setDone(done.includes(current) ? done.filter((x) => x !== current) : [...done, current])}>
                {done.includes(current) ? "Đã học xong" : "Đánh dấu đã học xong"}</button>
              <button type="button" className="btn btn-ghost" data-swarm-id="lesson-next" data-swarm-role="button"
                onClick={() => setCurrent((current + 1) % LESSONS.length)}>Bài tiếp theo</button>
            </div>
            {pct === 100 && <p className="t-body" role="status">Đã hoàn thành khoá học — chúc mừng bạn!</p>}
          </article>
        </div>'''
    body = '''  const [current, setCurrent] = useState(0);
  const [done, setDone] = useState<number[]>([]);
  const pct = Math.round((done.length / LESSONS.length) * 100);
'''
    return _component(s, _root(s, "s-learn", inner), client=True, prelude=f"\nconst LESSONS = {_js(lessons)};\n", body=body)


# ----------------------------------------------------------------- contact

for vi, en in [
    ("Liên hệ với chúng tôi", "Get in touch"), ("Gửi lời nhắn", "Send a message"), ("Nội dung", "Message"),
    ("Đã gửi", "Sent"), ("Địa chỉ", "Address"), ("Giờ làm việc", "Opening hours"),
    ("Thứ 2 – Thứ 7, 8:00 – 18:00", "Mon – Sat, 8:00 – 18:00"), ("Phản hồi trong vòng 1 ngày làm việc", "We reply within one working day"),
    ("Bạn điền họ tên, email đúng định dạng và lời nhắn (ít nhất 10 ký tự) nhé.",
     "Please enter your name, a valid email and a message of at least 10 characters."),
    ("Cảm ơn bạn! Chúng tôi đã nhận lời nhắn và sẽ trả lời qua email.", "Thank you! We got your message and will reply by email."),
    ("12 Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh", "12 Nguyen Hue, District 1, Ho Chi Minh City"),
]:
    T(vi, en)


def contact_form(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _root
    inner = '''        <div className="split split-5-7 align-start">
          <div className="stack">
            <p className="eyebrow">Liên hệ</p>
            <h1 className="t-h2">Liên hệ với chúng tôi</h1>
            <p className="t-lead">Phản hồi trong vòng 1 ngày làm việc</p>FACTS
          </div>
          <form className="card checkout" noValidate onSubmit={(e) => { e.preventDefault(); send(); }}>
            <h2 className="t-h3">Gửi lời nhắn</h2>
            <label htmlFor="ct-name" className="t-body">Họ và tên</label>
            <input id="ct-name" className="input" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)}
              aria-invalid={tried && !name.trim()} data-swarm-id="contact-name" data-swarm-role="input" />
            <label htmlFor="ct-email" className="t-body">Email hoặc số điện thoại</label>
            <input id="ct-email" className="input" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
              aria-invalid={tried && !emailOk} data-swarm-id="contact-email" data-swarm-role="input" />
            <label htmlFor="ct-message" className="t-body">Nội dung</label>
            <textarea id="ct-message" className="input" rows={5} value={message} onChange={(e) => setMessage(e.target.value)}
              aria-invalid={tried && message.trim().length < 10} data-swarm-id="contact-message" data-swarm-role="input" />
            <p className="t-caption form-error" role="alert">{error}</p>
            {sent === "done" ? (
              <p className="t-body" role="status"><strong>Cảm ơn bạn! Chúng tôi đã nhận lời nhắn và sẽ trả lời sớm.</strong></p>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={sent === "sending"} data-swarm-id="contact-send"
                data-swarm-role="button">{sent === "sending" ? ORDER_L.sending : "Gửi lời nhắn"}</button>
            )}
            {sent === "offline" && <Undelivered summary={summary} id="contact" title={ORDER_L.offline_message} />}
          </form>
        </div>'''
    body = '''  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [tried, setTried] = useState(false);
  const [sent, setSent] = useState<"idle" | "sending" | "done" | "offline">("idle");
  const [error, setError] = useState("");
  const emailOk = /^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(email) || /^(?:\\+?84|0)\\d{9,10}$/.test(email.replace(/[\\s.\\-()]/g, ""));
  const summary = [`${ORDER_L.name}: ${name}`, `${ORDER_L.contact}: ${email}`, message].join("\\n");
  const send = async () => {
    setTried(true);
    if (!name.trim() || !emailOk || message.trim().length < 10) return setError("Bạn điền họ tên, email hoặc số điện thoại đúng định dạng và lời nhắn (ít nhất 10 ký tự) nhé.");
    setError("");
    setSent("sending");
    const r = await sendOrder({ source: "contact", name, contact: email, note: message });
    if (r.ok) { setSent("done"); return; }
    if (r.errors) { setError(Object.values(r.errors)[0]); setSent("idle"); return; }
    setSent("offline");
  };
'''
    return _component(s, _root(s, "s-contact", inner.replace("FACTS", _contact_facts(c))), client=True,
                      prelude=ORDER_IMPORT, body=body)


def _spaced(phone: str) -> str:
    """0905111222 → 0905 111 222 (how a Vietnamese number is read)."""
    return re.sub(r"^(\d{4})(\d{3})(\d{3,4})$", r"\1 \2 \3", phone)


def _contact_facts(c) -> str:
    """The owner's own contact line (B4), phone and email: never an invented address."""
    from chromaswarm.developer.nextjs import _js
    ch = c.order.channels if c.order else None
    rows = []
    if c.contact:
        rows.append(f'<div><dt className="t-caption muted">Địa chỉ và giờ mở cửa</dt><dd className="t-body">{{{_js(c.contact)}}}</dd></div>')
    if ch and ch.phone:
        rows.append(f'<div><dt className="t-caption muted">Điện thoại</dt><dd className="t-body"><a href={{{_js("tel:" + ch.phone)}}}>'
                    f'{{{_js(_spaced(ch.phone))}}}</a></dd></div>')
    if ch and ch.email:
        rows.append(f'<div><dt className="t-caption muted">Email</dt><dd className="t-body"><a href={{{_js("mailto:" + ch.email)}}}>'
                    f'{{{_js(ch.email)}}}</a></dd></div>')
    if not rows:
        return ""
    return '\n            <dl className="contact-facts">\n              ' + "\n              ".join(rows) + "\n            </dl>"


# ----------------------------------------------------------------- workspace board

for vi, en in [
    ("Không gian làm việc", "Workspace"), ("Việc của nhóm", "Team tasks"), ("Cần làm", "To do"), ("Đang làm", "Doing"),
    ("Xong", "Done"), ("Thêm việc mới", "Add a task"), ("Thêm", "Add"), ("Chuyển sang cột tiếp theo", "Move to the next column"),
    ("Chuyển lại", "Move back"), ("Tên việc cần ít nhất 3 ký tự.", "A task name needs at least 3 characters."),
    ("Chưa có việc nào ở đây.", "Nothing here yet."), ("Chuyển “${t.title}” sang cột tiếp theo", "Move “${t.title}” to the next column"),
    ("Chuyển “${t.title}” về cột trước", "Move “${t.title}” back"),
    ("Viết nội dung trang giới thiệu", "Write the about page copy"), ("Chọn ảnh cho bộ sưu tập mới", "Pick photos for the new collection"),
    ("Kiểm tra giá trên điện thoại", "Check prices on mobile"), ("Gửi bản thử cho khách", "Send the draft to the client"),
    ("Cập nhật bảng giá", "Update the price list"), ("Lên lịch đăng bài tuần sau", "Schedule next week's posts"),
]:
    T(vi, en)


def task_board(s, c) -> str:
    from chromaswarm.developer.nextjs import _component, _js, _root
    tasks = [{"id": n, "title": t, "col": col} for n, (t, col) in enumerate([
        ("Viết nội dung trang giới thiệu", 0), ("Chọn ảnh cho bộ sưu tập mới", 0), ("Lên lịch đăng bài tuần sau", 0),
        ("Kiểm tra giá trên điện thoại", 1), ("Cập nhật bảng giá", 1), ("Gửi bản thử cho khách", 2)])]
    inner = '''        <div className="row between align-end">
          <div className="section-head"><p className="eyebrow">Không gian làm việc</p><h1 className="t-h2">Việc của nhóm</h1></div>
          <form className="row board-add" noValidate onSubmit={(e) => { e.preventDefault(); add(); }}>
            <label htmlFor="new-task" className="visually-hidden">Thêm việc mới</label>
            <input id="new-task" className="input" placeholder="Thêm việc mới" value={draft} onChange={(e) => { setDraft(e.target.value); setError(""); }}
              aria-invalid={!!error} aria-describedby="new-task-msg" data-swarm-id="task-input" data-swarm-role="input" />
            <button type="submit" className="btn btn-primary" data-swarm-id="task-add" data-swarm-role="button">Thêm</button>
            <p id="new-task-msg" className="t-caption form-error" role="alert">{error}</p>
          </form>
        </div>
        <div className="board">
          {COLUMNS.map((col, ci) => {
            const mine = tasks.filter((t) => t.col === ci);
            return (
              <section key={col} className="board-col" aria-labelledby={`col-${ci}`}>
                <h2 className="t-h4 row between" id={`col-${ci}`}><span>{col}</span><span className="t-caption muted t-num">{mine.length}</span></h2>
                {mine.length === 0 && <p className="t-caption muted">Chưa có việc nào ở đây.</p>}
                <ul className="stack">
                  {mine.map((t) => (
                    <li key={t.id} className="task">
                      <span className="t-body">{t.title}</span>
                      <div className="row task-actions">
                        {ci > 0 && <button type="button" className="icon-btn" aria-label={`Chuyển “${t.title}” về cột trước`}
                          data-swarm-id={`task-back-${t.id + 1}`} data-swarm-role="button" onClick={() => move(t.id, -1)}>←</button>}
                        {ci < COLUMNS.length - 1 && <button type="button" className="icon-btn" aria-label={`Chuyển “${t.title}” sang cột tiếp theo`}
                          data-swarm-id={`task-next-${t.id + 1}`} data-swarm-role="button" onClick={() => move(t.id, 1)}>→</button>}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>'''
    body = '''  const [tasks, setTasks] = useState(TASKS);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const move = (id: number, step: number) => setTasks(tasks.map((t) => (t.id === id ? { ...t, col: t.col + step } : t)));
  const add = () => {
    if (draft.trim().length < 3) return setError("Tên việc cần ít nhất 3 ký tự.");
    setTasks([...tasks, { id: tasks.length, title: draft.trim(), col: 0 }]);
    setDraft("");
  };
'''
    prelude = f"\nconst TASKS = {_js(tasks)};\nconst COLUMNS = {_js(['Cần làm', 'Đang làm', 'Xong'])};\n"
    return _component(s, _root(s, "s-board", inner), client=True, prelude=prelude, body=body)


RENDERERS = {
    "cart-checkout": cart_checkout, "kpi-row": kpi_row, "chart-panel": chart_panel, "data-table": data_table,
    "settings-form": settings_form, "plan-cards": plan_cards, "price-list": price_list, "booking-flow": booking_flow,
    "lesson-player": lesson_player, "contact-form": contact_form, "task-board": task_board,
}

APP_CSS = """
/* App pages (developer/app_pages.py): hairline borders, tabular numbers, 8pt steps. */
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.form-error:not(:empty) { color: var(--danger); }
.cart-lines { list-style: none; padding: 0; display: flex; flex-direction: column; }
.cart-line { display: grid; grid-template-columns: 112px 1fr; gap: 24px; padding-block: 24px; border-bottom: 1px solid var(--border-subtle); }
.cart-line:first-child { border-top: 1px solid var(--border-subtle); }
.cart-line-body { gap: 8px; }
.stepper { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); }
.stepper .t-num { min-width: 24px; text-align: center; }
.checkout { gap: 12px; }
@media (min-width: 1024px) { .checkout { position: sticky; top: 96px; } }
.summary { display: flex; flex-direction: column; gap: 8px; padding-bottom: 16px; border-bottom: 1px solid var(--border-subtle); }
.summary > div { display: flex; justify-content: space-between; gap: 16px; }
.summary-total { padding-top: 8px; border-top: 1px solid var(--border-subtle); }
.choice-group { gap: 8px; }
.choice, .chip, .lesson { min-height: 48px; padding: 12px 16px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
  background: var(--bg-elevated); text-align: left; cursor: pointer;
  transition: border-color var(--duration) var(--ease), background-color var(--duration) var(--ease); }
.choice:hover, .chip:hover:not(:disabled), .lesson:hover { border-color: var(--text-secondary); background: var(--bg-surface); }
.choice.is-active, .chip.is-active { border-color: var(--action-ink); box-shadow: inset 0 0 0 1px var(--action-ink); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; flex-direction: column; align-items: center; gap: 4px; min-width: 64px; }
.chip:disabled { opacity: 0.5; cursor: not-allowed; }
.kpis { display: grid; gap: 1px; grid-template-columns: repeat(2, 1fr); margin-top: 32px; background: var(--border-subtle);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); overflow: hidden; }
@media (min-width: 1024px) { .kpis { grid-template-columns: 1.4fr repeat(3, 1fr); } }  /* first figure leads */
.kpi { display: flex; flex-direction: column; gap: 8px; padding: var(--card-padding); background: var(--bg-primary); }
.delta { font-size: var(--text-caption); }
.delta.is-up { color: var(--success, var(--text-primary)); }
.delta.is-down { color: var(--danger); }
.chart-card { gap: 24px; margin: 0; }
.chart { width: 100%; height: auto; }
.bar { fill: color-mix(in srgb, var(--action) 35%, var(--bg-surface)); transition: fill var(--duration) var(--ease); outline: none; }
.bar:hover, .bar:focus-visible, .bar.is-active { fill: var(--action); }
.chart-label { font-size: var(--text-caption); fill: var(--text-secondary); font-variant-numeric: tabular-nums; }
.chart-facts { gap: 1px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); overflow: hidden; background: var(--border-subtle); }
.table-search { flex: 1; max-width: 360px; }
.table-wrap { margin-top: 24px; overflow-x: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
.table { width: 100%; border-collapse: collapse; font-size: var(--text-body); }
.table th, .table td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border-subtle); white-space: nowrap; }
.table th { font-size: var(--text-caption); font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.08em; }
.table tbody tr { transition: background-color var(--duration) var(--ease); }
.table tbody tr:hover { background: var(--bg-surface); }
.table tbody tr:last-child td { border-bottom: 0; }
.table .num { text-align: right; }
.sort { min-height: 48px; padding: 0; border: 0; background: none; font: inherit; color: inherit; text-transform: inherit;
  letter-spacing: inherit; cursor: pointer; transition: color var(--duration) var(--ease); }
.sort:hover { color: var(--text-primary); }
.pill { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: var(--text-caption); border: 1px solid var(--border-strong); }
.pill-2 { border-color: var(--action-ink); color: var(--action-ink); }
.pill-3 { color: var(--text-secondary); text-decoration: line-through; }
.settings { display: grid; gap: var(--grid-gap); margin-top: 32px; }
@media (min-width: 1024px) { .settings { grid-template-columns: 240px 1fr; align-items: start; } }
.settings-nav { display: flex; flex-wrap: wrap; gap: 8px; }
@media (min-width: 1024px) { .settings-nav { flex-direction: column; } .settings-nav .filter { text-align: left; } }
.settings-panel { gap: 12px; max-width: 640px; }
.toggles { list-style: none; padding: 0; }
.toggle-row { padding-block: 8px; border-bottom: 1px solid var(--border-subtle); }
.switch { position: relative; width: 56px; height: 32px; min-height: 48px; padding: 0; border: 0; background: none; cursor: pointer; }
.switch::before { content: ""; position: absolute; inset: 8px 0; border-radius: 999px; background: var(--border-strong);
  transition: background-color var(--duration) var(--ease); }
.switch:hover::before { filter: brightness(0.92); }
.switch.is-on::before { background: var(--action); }
.switch-knob { position: absolute; top: 12px; left: 4px; width: 24px; height: 24px; border-radius: 50%; background: var(--bg-elevated);
  transition: transform var(--duration) var(--ease); }
.switch.is-on .switch-knob { transform: translateX(24px); }
.plans { list-style: none; padding: 0; display: grid; gap: 1px; margin-top: 32px; background: var(--border-subtle);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); overflow: hidden; }
@media (min-width: 1024px) { .plans { grid-template-columns: 1fr 1.25fr 1fr; } }  /* the recommended plan leads */
.plan { display: flex; flex-direction: column; gap: 16px; padding: var(--card-padding); background: var(--bg-primary); }
.plan.is-featured { background: var(--bg-surface); }
.plan .btn { margin-top: auto; }
.price-list { list-style: none; padding: 0; margin-top: 32px; }
.price-row { display: grid; grid-template-columns: 1fr auto; gap: 8px 24px; align-items: center; padding-block: 24px;
  border-bottom: 1px solid var(--border-subtle); transition: background-color var(--duration) var(--ease); }
.price-row.is-active { background: var(--bg-surface); }
.price-leader { display: none; }
@media (min-width: 768px) {
  .price-row { grid-template-columns: minmax(0, 2fr) 1fr auto auto; }
  .price-leader { display: block; border-bottom: 1px dotted var(--border-strong); align-self: end; margin-bottom: 8px; }
}
.price-name { gap: 4px; }
.learn { display: grid; gap: var(--grid-gap); }
@media (min-width: 1024px) { .learn { grid-template-columns: 320px 1fr; align-items: start; } .learn-list { position: sticky; top: 96px; } }
.learn-list ol { list-style: none; padding: 0; gap: 8px; }
.lesson { display: flex; gap: 12px; align-items: flex-start; width: 100%; }
.lesson[aria-current] { border-color: var(--action-ink); }
.lesson-mark { display: grid; place-items: center; flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  border: 1px solid var(--border-strong); font-size: var(--text-caption); font-variant-numeric: tabular-nums; }
.lesson-mark.is-done { background: var(--action); border-color: var(--action); color: var(--action-fg); }
.lesson-text { gap: 2px; }
.progress { height: 8px; border-radius: 999px; background: var(--bg-surface); border: 1px solid var(--border-subtle); overflow: hidden; }
.progress span { display: block; height: 100%; background: var(--action); transition: width var(--duration) var(--ease); }
.learn-main { gap: 16px; }
.contact-facts { display: flex; flex-direction: column; gap: 16px; margin-top: 16px; padding-top: 24px; border-top: 1px solid var(--border-subtle); }
textarea.input { resize: vertical; }
.board-add { flex: 1; max-width: 480px; align-items: flex-start; }
.board-add .form-error { flex-basis: 100%; }
.board { display: grid; gap: var(--grid-gap); margin-top: 32px; }
@media (min-width: 1024px) { .board { grid-template-columns: repeat(3, 1fr); align-items: start; } }
.board-col { display: flex; flex-direction: column; gap: 16px; padding: 16px; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); }
.board-col ul { list-style: none; padding: 0; gap: 8px; }
.task { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 8px 8px 16px;
  background: var(--bg-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
  transition: border-color var(--duration) var(--ease); }
.task:hover { border-color: var(--border-strong); }
.task-actions { gap: 0; flex-wrap: nowrap; }
"""


# ----------------------------------------------------------------- product preview (software heroes)
# Real software sites show their product, not a stock photo (Linear, Stripe, Notion). Without a real
# screenshot uploaded, the hero shows the product's own interface, built from the design tokens:
# a quiet app window with the brand, navigation, figures and a short table. Decorative (one image
# role, nothing inside is focusable), so it never adds controls Master QA would have to click.

PRODUCT_PREVIEW_TSX = r'''type Row = { name: string; meta: string; status: string };
type Props = { brand: string; title: string; nav: string[]; figures: string[][]; rows: Row[]; label: string };

/** The product's interface as the hero visual (decorative): window, sidebar, figures, a table. */
export function ProductPreview({ brand, title, nav, figures, rows, label }: Props) {
  const bars = [38, 52, 46, 61, 58, 72, 69, 84, 78, 91, 88, 97];
  return (
    <div className="pp" role="img" aria-label={label}>
      <div className="pp-bar" aria-hidden="true"><span /><span /><span /><em>{brand}</em></div>
      <div className="pp-body" aria-hidden="true">
        <aside className="pp-side">
          <strong>{brand}</strong>
          {nav.map((n, i) => <span key={n} className={i === 0 ? "is-on" : undefined}>{n}</span>)}
        </aside>
        <div className="pp-main">
          <p className="pp-title">{title}</p>
          <div className="pp-figs">
            {figures.map(([v, k]) => <div key={k}><b>{v}</b><small>{k}</small></div>)}
          </div>
          <svg viewBox="0 0 240 48" className="pp-chart" preserveAspectRatio="none">
            {bars.map((h, i) => <rect key={i} x={i * 20 + 2} y={48 - h * 0.46} width={14} height={h * 0.46} rx={2} />)}
          </svg>
          <div className="pp-rows">
            {rows.map((r) => (
              <div key={r.name} className="pp-row"><span>{r.name}</span><small>{r.meta}</small><i>{r.status}</i></div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
'''

PREVIEW_CSS = """
/* Product preview (components/ProductPreview.tsx): the product's own interface, tokens only. */
.pp { width: 100%; border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); background: var(--bg-elevated);
  overflow: hidden; text-align: left; font-size: var(--text-caption); line-height: 1.4; }
.pp-bar { display: flex; align-items: center; gap: 6px; padding: 10px 14px; border-bottom: 1px solid var(--border-subtle); }
.pp-bar span { width: 10px; height: 10px; border-radius: 50%; background: var(--border-strong); opacity: 0.5; }
.pp-bar em { margin-left: 12px; font-style: normal; color: var(--text-secondary); }
.pp-body { display: grid; grid-template-columns: 1fr; min-height: 280px; }
@media (min-width: 768px) { .pp-body { grid-template-columns: 180px 1fr; } }
.pp-side { display: none; flex-direction: column; gap: 4px; padding: 16px 12px; border-right: 1px solid var(--border-subtle);
  background: var(--bg-surface); }
@media (min-width: 768px) { .pp-side { display: flex; } }
.pp-side strong { font-family: var(--font-heading); font-size: var(--text-body); margin-bottom: 12px; }
.pp-side span { padding: 6px 8px; border-radius: var(--radius-sm); color: var(--text-secondary); }
.pp-side span.is-on { background: var(--bg-elevated); color: var(--text-primary); box-shadow: inset 0 0 0 1px var(--border-subtle); }
.pp-main { display: flex; flex-direction: column; gap: 16px; padding: 20px 24px; min-width: 0; }
.pp-title { font-family: var(--font-heading); font-size: var(--text-body); font-weight: 600; }
.pp-figs { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--border-subtle);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; }
.pp-figs div { display: flex; flex-direction: column; gap: 2px; padding: 12px; background: var(--bg-elevated); min-width: 0; }
.pp-figs b { font-size: var(--text-h4); font-weight: 600; font-variant-numeric: tabular-nums; }
.pp-figs small, .pp-row small { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pp-chart { width: 100%; height: 56px; }
.pp-chart rect { fill: color-mix(in srgb, var(--action) 30%, var(--bg-surface)); }
.pp-chart rect:last-child { fill: var(--action); }
.pp-rows { display: flex; flex-direction: column; border-top: 1px solid var(--border-subtle); }
.pp-row { display: grid; grid-template-columns: 1.4fr 1fr auto; gap: 12px; align-items: center; padding: 10px 0;
  border-bottom: 1px solid var(--border-subtle); }
.pp-row span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pp-row i { font-style: normal; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border-strong); }
@media (max-width: 767px) { .pp-figs { grid-template-columns: 1fr 1fr; } .pp-figs div:nth-child(n+3) { display: none; }
  .pp-row { grid-template-columns: 1fr auto; } .pp-row small { display: none; } .pp-main { padding: 16px; } }
"""


# Sample records for the decorative app window: what a user of the default SaaS sample (a team work
# board) would see. The plans (Gói Cơ bản…) are what the product costs, never rows inside it.
PREVIEW_NAV = ["Tổng quan", "Việc", "Dự án", "Báo cáo", "Cài đặt"]
PREVIEW_FIGURES = [["18", "việc đang mở"], ["6", "đến hạn tuần này"], ["3", "đang chờ duyệt"]]
PREVIEW_ROWS = [("Trang bảng giá mới", "Nhóm web · hạn 22/11", "Đang làm"),
                ("Sửa lỗi đăng nhập", "Nhóm app · hạn 21/11", "Chờ duyệt"),
                ("Báo cáo tuần 47", "Vận hành · hạn 24/11", "Xong")]


def preview_props(c) -> dict:
    """What the preview shows: records the product manages (copywriter `preview`, else the samples)."""
    rows = getattr(c, "preview_rows", None) or PREVIEW_ROWS
    return {"brand": c.brand, "title": "Tổng quan hôm nay", "label": f"Giao diện {c.brand}",
            "nav": getattr(c, "preview_nav", None) or PREVIEW_NAV,
            "figures": [list(f) for f in (getattr(c, "preview_figures", None) or PREVIEW_FIGURES)],
            "rows": [{"name": n, "meta": m, "status": st} for n, m, st in rows]}
