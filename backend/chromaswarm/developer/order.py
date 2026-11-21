"""The page's main action, for real: an order / booking / contact form.

Before, "Đặt bánh" only swapped its own label to "Đã ghi nhận, chúng tôi sẽ liên hệ" — nothing was
asked, nothing was sent, and the visitor believed the order had gone through (user test 21/11).

Now every primary CTA (hero, closing band, quick view) calls `openOrder()`, which opens one dialog
mounted in the layout (`components/OrderDialog.tsx`). What it asks depends on the site:
- shop: item + quantity, pick-up or delivery (+ address), a pick-up date when the industry needs one
  (bakery: cakes are made to order);
- booking: service + date and time (+ party size for a café / restaurant);
- lead (software, courses, portfolio): what they want + phone or email.
Then name and phone, validated on the page (errors under each field, input kept) and again on the
server. The order goes to the app's own `POST /api/orders` (`app/api/orders/route.ts`): appended to
`data/orders.jsonl` when the disk is writable (local / own server) and forwarded to
`ORDER_WEBHOOK_URL` when set (Google Sheets, Make, Zapier…). If neither works — e.g. on Vercel without
a webhook — the visitor is told so plainly and offered the shop's own channels instead: Zalo (order
text copied first), a call, an SMS or an email with the order filled in. The channels come from the
contact line the owner typed at B4 (`channels()`).
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel

from chromaswarm.state_machine.pipeline_state import Domain

PHONE = re.compile(r"(?<!\d)((?:\+84|84|0)[\s.\-]?(?:\d[\s.\-]?){8,9}\d)(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ZALO = re.compile(r"zalo", re.I)


class Channels(BaseModel):
    phone: str = ""  # digits only, e.g. 0905111222
    zalo: str = ""
    email: str = ""


def channels(contact: str) -> Channels:
    """Phone / Zalo / email the owner typed in their contact line ("… · Zalo 0905 111 222")."""
    text = contact or ""
    out = Channels()
    if m := EMAIL.search(text):
        out.email = m.group(0)
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        if not 10 <= len(digits) <= 11:
            continue
        before = text[max(0, m.start() - 12):m.start()]
        if ZALO.search(before):
            out.zalo = out.zalo or digits
        out.phone = out.phone or digits
    if out.phone and not out.zalo and ZALO.search(text):  # "zalo/hotline 0905…": the one number is both
        out.zalo = out.phone
    return out


VI = dict(
    at="lúc", total="Tổng cộng", payment="Thanh toán", receive="Cách nhận hàng", close="Đóng", item="Chọn", qty="Số lượng", date="Ngày", time="Giờ", party="Số người",
    pickup="Nhận tại cửa hàng", ship="Giao tận nơi", address="Địa chỉ giao", name="Họ và tên",
    phone="Số điện thoại", contact="Số điện thoại hoặc email", note="Ghi chú (không bắt buộc)", submit="Gửi",
    sending="Đang gửi…", hint="Cửa hàng gọi lại hoặc nhắn tin để xác nhận trước khi làm.",
    err_item="Chọn một mục.", err_when="Chọn ngày.", err_past="Ngày này đã qua, chọn từ hôm nay trở đi.",
    err_time="Chọn giờ.", err_party="Nhập số người, từ 1 đến 50.", err_name="Nhập tên để cửa hàng gọi bạn.",
    err_phone="Số điện thoại gồm 10 số, ví dụ 0905 123 456.",
    err_contact="Nhập số điện thoại 10 số hoặc email, ví dụ ten@email.com.",
    err_address="Nhập địa chỉ đủ số nhà và tên đường.", err_message="Lời nhắn cần ít nhất 10 ký tự.", err_server="Có thông tin chưa đúng, bạn xem lại các ô được đánh dấu.",
    done="Đã gửi. Mã đơn của bạn: ", done_hint="Cửa hàng sẽ liên hệ số bạn vừa nhập để xác nhận.",
    offline="Đơn chưa gửi tự động được.", offline_message="Lời nhắn chưa gửi tự động được.", offline_hint="Bạn gửi nội dung đơn cho cửa hàng qua một trong các cách dưới đây:",
    offline_none="Bạn chép nội dung đơn và gửi cho cửa hàng qua kênh bạn đang dùng.",
    zalo="Nhắn Zalo cho cửa hàng", call="Gọi", sms="Nhắn tin", mail="Gửi email", copy="Chép nội dung đơn",
    copied="Đã chép nội dung đơn — dán vào tin nhắn.", order_for="Đơn đặt tại", again="Đặt thêm",
)
EN = dict(
    at="at", total="Total", payment="Payment", receive="How you get it", close="Close", item="Choose", qty="Quantity", date="Date", time="Time", party="Guests",
    pickup="Pick up in store", ship="Deliver to me", address="Delivery address", name="Full name",
    phone="Phone number", contact="Phone or email", note="Note (optional)", submit="Send",
    sending="Sending…", hint="We call or message you to confirm before we start.",
    err_item="Choose one.", err_when="Choose a date.", err_past="That date has passed; choose today or later.",
    err_time="Choose a time.", err_party="Enter the number of guests, 1 to 50.", err_name="Enter your name so we can reach you.",
    err_phone="Enter a phone number with 10 digits.", err_contact="Enter a phone number or an email like name@email.com.",
    err_address="Enter the full street address.", err_message="A message needs at least 10 characters.", err_server="Some details need fixing; check the marked fields.",
    done="Sent. Your order code: ", done_hint="We will contact you on the number you entered to confirm.",
    offline="The order could not be sent automatically.", offline_message="The message could not be sent automatically.", offline_hint="Send the order details to us in one of these ways:",
    offline_none="Copy the order details and send them to us on the channel you use.",
    zalo="Message us on Zalo", call="Call", sms="Text us", mail="Email us", copy="Copy order details",
    copied="Order details copied — paste them into your message.", order_for="Order at", again="Order more",
)


class OrderSpec(BaseModel):
    kind: str  # shop | booking | lead
    brand: str
    title: str  # the dialog's heading: the page's own CTA ("Đặt bánh")
    item_label: str
    items: list[tuple[str, str]] = []  # (name, price) from the page's list
    item_required: bool = True
    qty: bool = False
    when: str = ""  # label of the date field; "" = not asked
    time: bool = False
    party: bool = False
    delivery: bool = False
    channels: Channels = Channels()
    labels: dict = VI
    cart: str = ""  # route of the built cart page ("/cart"); "" = cards open this form instead (developer/cart.py)


def order_spec(domain: Domain | None, brand: str, cta: str, items: list, contact: str, pack: dict | None,
               lang: str = "vi") -> OrderSpec:
    d = domain or Domain.OTHER
    extra = (pack or {}).get("order") or {}
    rows = [(i.name, i.price) for i in items][:12]
    en = lang != "vi"
    if d in (Domain.ECOMMERCE, Domain.OTHER):
        base = dict(kind="shop", item_label="Product" if en else "Sản phẩm", qty=True, delivery=True)
    elif d is Domain.BOOKING:
        base = dict(kind="booking", item_label="Service" if en else "Dịch vụ", when="Date" if en else "Ngày hẹn", time=True)
    elif d is Domain.EDTECH:
        base = dict(kind="lead", item_label="Course" if en else "Khóa học")
    elif d is Domain.SAAS:
        base = dict(kind="lead", item_label="Plan" if en else "Gói", item_required=False)
    else:
        base = dict(kind="lead", item_label="Project" if en else "Dự án", item_required=False)
        rows = []  # a portfolio's list is past work, not something to order
    spec = {**base, **({} if en else extra)}
    return OrderSpec(brand=brand, title=cta, items=rows, channels=channels(contact), labels=EN if en else VI,
                     **{k: v for k, v in spec.items() if k in OrderSpec.model_fields})


def order_file(spec: OrderSpec):
    from chromaswarm.developer.nextjs import WorkspaceFile  # local: nextjs imports this module
    data = spec.model_dump()
    data["items"] = [list(x) for x in spec.items]
    return WorkspaceFile(path="content/order.ts", content=(
        "// Form đặt hàng / đặt lịch mở từ nút chính. Sửa chữ trong dấu ngoặc kép; đổi số điện thoại, Zalo, email\n"
        "// ở mục channels. Đơn gửi tới app/api/orders (xem HUONG_DAN.md, mục Nhận đơn).\n"
        f"export const ORDER = {json.dumps(data, ensure_ascii=False, indent=2)};\n"))


ORDER_DIALOG_TSX = r'''"use client";

import { useEffect, useRef, useState } from "react";
import { ORDER } from "@/content/order";

const EVENT = "chromaswarm:order";
const PHONE = /^(?:\+?84|0)\d{9,10}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Opens the order form from any button on any page, optionally with one item already chosen. */
export function openOrder(item?: string) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { item } }));
}

export type Sent = { ok: true; id: string } | { ok: false; errors?: Record<string, string> };

/** Sends any of the site's forms (order dialog, checkout, booking, contact) to the app's own API.
 * `{ ok: false }` without `errors` = could not be delivered: show <Reach /> so the visitor can still send it. */
export async function sendOrder(body: Record<string, unknown>): Promise<Sent> {
  try {
    const r = await fetch("/api/orders", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...body, page: location.pathname }),
    });
    const data = await r.json().catch(() => ({}));
    if (r.ok && data.ok) return { ok: true, id: String(data.id) };
    if (r.status === 400 && data.errors) return { ok: false, errors: data.errors };
  } catch {
    // network down: same as not delivered
  }
  return { ok: false };
}

const fmtPhone = (p: string) => p.replace(/^(\d{4})(\d{3})(\d{3,4})$/, "$1 $2 $3");

/** The shop's own channels (from the owner's contact line), with the text of the order ready to send. */
export function Reach({ summary, id = "order" }: { summary: string; id?: string }) {
  const L = ORDER.labels;
  const ch = ORDER.channels;
  const [copied, setCopied] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(summary); setCopied(true); } catch { setCopied(false); }
  }
  return (
    <div className="order-channels">
      {ch.zalo && (
        <button type="button" className="btn btn-primary" data-swarm-id={`${id}-zalo`} data-swarm-role="button"
          onClick={async () => { await copy(); window.open(`https://zalo.me/${ch.zalo}`, "_blank", "noopener"); }}>{L.zalo}</button>
      )}
      {ch.phone && <a className="btn btn-ghost" href={`tel:${ch.phone}`} data-swarm-id={`${id}-call`} data-swarm-role="link">{L.call} {fmtPhone(ch.phone)}</a>}
      {ch.phone && (
        <a className="btn btn-ghost" href={`sms:${ch.phone}?&body=${encodeURIComponent(summary)}`}
          data-swarm-id={`${id}-sms`} data-swarm-role="link">{L.sms}</a>
      )}
      {ch.email && (
        <a className="btn btn-ghost" data-swarm-id={`${id}-mail`} data-swarm-role="link"
          href={`mailto:${ch.email}?subject=${encodeURIComponent(`${L.order_for} ${ORDER.brand}`)}&body=${encodeURIComponent(summary)}`}>{L.mail}</a>
      )}
      <button type="button" className="btn-link" data-swarm-id={`${id}-copy`} data-swarm-role="button" onClick={copy}>{L.copy}</button>
      <p className="t-caption" role="status">{copied ? L.copied : ""}</p>
    </div>
  );
}

/** A form that could not be delivered: say so, show what was filled in, offer the shop's own channels. */
export function Undelivered({ summary, id, title }: { summary: string; id: string; title?: string }) {
  const L = ORDER.labels;
  const ch = ORDER.channels;
  return (
    <div className="stack" role="alert">
      <p className="t-body"><strong>{title ?? L.offline}</strong></p>
      <p className="t-body muted">{ch.zalo || ch.phone || ch.email ? L.offline_hint : L.offline_none}</p>
      <pre className="order-summary t-caption">{summary}</pre>
      <Reach summary={summary} id={id} />
    </div>
  );
}

type Field = "item" | "date" | "time" | "party" | "address" | "name" | "phone";
type Errors = Partial<Record<Field, string>>;

function today() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

export function OrderDialog() {
  const L = ORDER.labels;
  const [open, setOpen] = useState(false);
  const [item, setItem] = useState("");
  const [qty, setQty] = useState(1);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [party, setParty] = useState("2");
  const [delivery, setDelivery] = useState<"pickup" | "ship">("pickup");
  const [address, setAddress] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [state, setState] = useState<"form" | "sending" | "done" | "offline">("form");
  const [code, setCode] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const focusError = useRef(false);

  useEffect(() => {
    if (!focusError.current) return;
    focusError.current = false;
    panel.current?.querySelector<HTMLElement>("[aria-invalid='true']")?.focus();
  }, [errors]);

  // A field's error goes away as soon as the visitor changes that field
  function edit<T>(field: Field, set: (v: T) => void) {
    return (v: T) => { set(v); setErrors((e) => (e[field] ? { ...e, [field]: undefined } : e)); };
  }
  const fmtDate = (d: string) => (d && ORDER.labels.at === "lúc" ? d.split("-").reverse().join("/") : d);

  function close() {
    setOpen(false);
    opener.current?.focus();
  }

  useEffect(() => {
    const onOpen = (e: Event) => {
      const want = (e as CustomEvent<{ item?: string }>).detail?.item;
      opener.current = document.activeElement as HTMLElement | null;
      setItem(want && ORDER.items.some(([n]) => n === want) ? want : ORDER.item_required ? ORDER.items[0]?.[0] ?? "" : "");
      setErrors({});
      setState("form");
      setOpen(true);
    };
    window.addEventListener(EVENT, onOpen);
    return () => window.removeEventListener(EVENT, onOpen);
  }, []);

  useEffect(() => {
    // a link to #dat-hang (the menu's "Đặt trước", or "/#dat-hang" from another page) opens the form
    const fromHash = () => {
      if (window.location.hash !== "#dat-hang") return;
      history.replaceState(null, "", window.location.pathname + window.location.search);
      openOrder();
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);

  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector<HTMLElement>("select, input, textarea")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = overflow; };
  }, [open]);

  if (!open) return null;

  const price = ORDER.items.find(([n]) => n === item)?.[1];
  const summary = [
    `${L.order_for} ${ORDER.brand}`,
    item && `${item}${ORDER.qty ? ` × ${qty}` : ""}${price ? ` (${price})` : ""}`,
    ORDER.when && `${ORDER.when}: ${fmtDate(date)}${time ? ` ${L.at} ${time}` : ""}`,
    ORDER.party && `${L.party}: ${party}`,
    ORDER.delivery && (delivery === "ship" ? `${L.ship}: ${address}` : L.pickup),
    `${L.name}: ${name}`,
    `${ORDER.kind === "lead" ? L.contact : L.phone}: ${phone}`,
    note && `${L.note.replace(/\s*\(.*\)$/, "")}: ${note}`,
  ].filter(Boolean).join("\n");

  function check(): Errors {
    const e: Errors = {};
    const contact = phone.replace(/[\s.\-()]/g, "");
    if (ORDER.items.length && ORDER.item_required && !item) e.item = L.err_item;
    if (ORDER.when && !date) e.date = L.err_when;
    else if (ORDER.when && date < today()) e.date = L.err_past;
    if (ORDER.time && !time) e.time = L.err_time;
    const guests = Number(party);
    if (ORDER.party && !(Number.isInteger(guests) && guests >= 1 && guests <= 50)) e.party = L.err_party;
    if (ORDER.delivery && delivery === "ship" && address.trim().length < 6) e.address = L.err_address;
    if (!name.trim()) e.name = L.err_name;
    if (ORDER.kind === "lead" ? !(PHONE.test(contact) || EMAIL.test(phone.trim())) : !PHONE.test(contact)) {
      e.phone = ORDER.kind === "lead" ? L.err_contact : L.err_phone;
    }
    return e;
  }

  async function submit(ev: React.FormEvent) {
    ev.preventDefault();
    const e = check();
    setErrors(e);
    if (Object.keys(e).length) {
      focusError.current = true; // the effect below focuses the first field to fix once it is drawn
      return;
    }
    setState("sending");
    const sent = await sendOrder({ source: "order", item, qty: ORDER.qty ? qty : undefined, date, time,
      party: ORDER.party ? Number(party) : undefined, delivery: ORDER.delivery ? delivery : undefined, address, name,
      contact: phone, note });
    if (sent.ok) { setCode(sent.id); setState("done"); return; }
    if (sent.errors) { focusError.current = true; setErrors(sent.errors); setState("form"); return; }
    setState("offline");
  }

  const ch = ORDER.channels;
  const reach = <Reach summary={summary} />;
  const err = (f: Field) => errors[f] && <p id={`order-${f}-err`} className="t-caption field-error">{errors[f]}</p>;
  const invalid = (f: Field) => ({ "aria-invalid": !!errors[f], "aria-describedby": errors[f] ? `order-${f}-err` : undefined });

  return (
    <div className="modal-scrim order-scrim" role="presentation" onClick={close}>
      <div ref={panel} className="modal order" role="dialog" aria-modal="true" aria-labelledby="order-title"
        onClick={(e) => e.stopPropagation()}>
        <div className="order-head">
          <h2 id="order-title" className="t-h3">{ORDER.title}</h2>
          <button type="button" className="icon-btn order-close" aria-label={L.close} data-swarm-id="order-close" data-swarm-role="button"
            onClick={close}>×</button>
        </div>
        {state === "done" ? (
          <div className="stack" role="status">
            <p className="t-body"><strong>{L.done}{code}</strong></p>
            <p className="t-body muted">{L.done_hint}</p>
            <pre className="order-summary t-caption">{summary}</pre>
            {(ch.zalo || ch.phone) && reach}
            <button type="button" className="btn btn-ghost" data-swarm-id="order-again" data-swarm-role="button"
              onClick={() => setState("form")}>{L.again}</button>
          </div>
        ) : state === "offline" ? (
          <Undelivered summary={summary} id="order" />
        ) : (
          <form className="stack order-form" noValidate onSubmit={submit}>
            {ORDER.items.length > 0 && (
              <div className="order-row">
                <label className="field">
                  <span className="t-body">{ORDER.item_label}</span>
                  <select className="input" value={item} onChange={(e) => edit("item", setItem)(e.target.value)} {...invalid("item")}
                    data-swarm-id="order-item" data-swarm-role="input">
                    {!ORDER.item_required && <option value="">—</option>}
                    {ORDER.items.map(([n, p]) => <option key={n} value={n}>{p ? `${n} — ${p}` : n}</option>)}
                  </select>
                  {err("item")}
                </label>
                {ORDER.qty && (
                  <label className="field order-qty">
                    <span className="t-body">{L.qty}</span>
                    <input className="input" type="number" inputMode="numeric" min={1} max={50} value={qty}
                      onChange={(e) => setQty(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                      data-swarm-id="order-qty" data-swarm-role="input" />
                  </label>
                )}
              </div>
            )}
            {ORDER.when && (
              <div className="order-row">
                <label className="field">
                  <span className="t-body">{ORDER.when}</span>
                  <input className="input" type="date" min={today()} value={date} onChange={(e) => edit("date", setDate)(e.target.value)}
                    {...invalid("date")} data-swarm-id="order-date" data-swarm-role="input" />
                  {err("date")}
                </label>
                {ORDER.time && (
                  <label className="field">
                    <span className="t-body">{L.time}</span>
                    <input className="input" type="time" value={time} onChange={(e) => edit("time", setTime)(e.target.value)}
                      {...invalid("time")} data-swarm-id="order-time" data-swarm-role="input" />
                    {err("time")}
                  </label>
                )}
              </div>
            )}
            {ORDER.party && (
              <label className="field">
                <span className="t-body">{L.party}</span>
                <input className="input" type="number" inputMode="numeric" min={1} max={50} value={party}
                  onChange={(e) => edit("party", setParty)(e.target.value)} {...invalid("party")} data-swarm-id="order-party" data-swarm-role="input" />
                {err("party")}
              </label>
            )}
            {ORDER.delivery && (
              <fieldset className="field order-delivery">
                <legend className="t-body">{L.receive}</legend>
                <div className="row">
                  {(["pickup", "ship"] as const).map((v) => (
                    <label key={v} className="order-choice">
                      <input type="radio" name="delivery" value={v} checked={delivery === v} onChange={() => setDelivery(v)}
                        data-swarm-id={`order-${v}`} data-swarm-role="input" />
                      <span>{v === "pickup" ? L.pickup : L.ship}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            {ORDER.delivery && delivery === "ship" && (
              <label className="field">
                <span className="t-body">{L.address}</span>
                <input className="input" value={address} onChange={(e) => edit("address", setAddress)(e.target.value)} autoComplete="street-address"
                  {...invalid("address")} data-swarm-id="order-address" data-swarm-role="input" />
                {err("address")}
              </label>
            )}
            <div className="order-row">
              <label className="field">
                <span className="t-body">{L.name}</span>
                <input className="input" value={name} onChange={(e) => edit("name", setName)(e.target.value)} autoComplete="name"
                  {...invalid("name")} data-swarm-id="order-name" data-swarm-role="input" />
                {err("name")}
              </label>
              <label className="field">
                <span className="t-body">{ORDER.kind === "lead" ? L.contact : L.phone}</span>
                <input className="input" value={phone} onChange={(e) => edit("phone", setPhone)(e.target.value)}
                  type={ORDER.kind === "lead" ? "text" : "tel"} inputMode={ORDER.kind === "lead" ? "email" : "tel"}
                  autoComplete={ORDER.kind === "lead" ? "email" : "tel"}
                  {...invalid("phone")} data-swarm-id="order-phone" data-swarm-role="input" />
                {err("phone")}
              </label>
            </div>
            <label className="field">
              <span className="t-body">{L.note}</span>
              <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500}
                data-swarm-id="order-note" data-swarm-role="input" />
            </label>
            <p className="t-caption muted">{L.hint}</p>
            <button type="submit" className="btn btn-primary" disabled={state === "sending"}
              data-swarm-id="order-submit" data-swarm-role="button">{state === "sending" ? L.sending : L.submit}</button>
          </form>
        )}
      </div>
    </div>
  );
}
'''

ORDER_ROUTE_TS = r'''import { appendFile, mkdir } from "node:fs/promises";
import { NextResponse } from "next/server";
import { ORDER } from "@/content/order";

// Orders from the form opened by the page's main button (components/OrderDialog.tsx).
// Kept in data/orders.jsonl when the disk is writable (your own computer or server) and sent to
// ORDER_WEBHOOK_URL when it is set (Google Sheets, Make, Zapier…). See HUONG_DAN.md, "Nhận đơn".
const PHONE = /^(?:\+?84|0)\d{9,10}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const text = (v: unknown, max: number) => (typeof v === "string" ? v.trim().slice(0, max) : "");

export async function POST(req: Request) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false }, { status: 400 });
  }
  // Which form sent it: the main-button dialog, the cart page, the booking page or the contact page
  const source = ["checkout", "booking", "contact"].includes(String(body.source)) ? String(body.source) : "order";
  const lines = Array.isArray(body.lines)
    ? body.lines.slice(0, 20).map((l) => ({ name: text((l as Record<string, unknown>)?.name, 120),
        qty: Math.max(1, Math.min(50, Number((l as Record<string, unknown>)?.qty) || 1)) })).filter((l) => l.name)
    : [];
  const order = {
    source,
    item: text(body.item, 120), qty: Math.max(1, Math.min(50, Number(body.qty) || 1)), lines,
    date: text(body.date, 10), time: text(body.time, 5), party: Number(body.party) || undefined,
    delivery: body.delivery === "ship" ? "ship" : body.delivery === "pickup" ? "pickup" : undefined,
    address: text(body.address, 200), pay: text(body.pay, 60), name: text(body.name, 80), contact: text(body.contact, 80),
    note: text(body.note, 2000), page: text(body.page, 120),
  };
  const errors: Record<string, string> = {};
  const L = ORDER.labels;
  const contact = order.contact.replace(/[\s.\-()]/g, "");
  const phoneOk = PHONE.test(contact);
  const date = /^\d{4}-\d{2}-\d{2}$/;
  if (!order.name) errors.name = L.err_name;
  if (source === "order") {
    if (ORDER.items.length && ORDER.item_required && !ORDER.items.some(([n]) => n === order.item)) errors.item = L.err_item;
    if (order.item && !ORDER.items.some(([n]) => n === order.item)) errors.item = L.err_item;
    if (ORDER.when && !date.test(order.date)) errors.date = L.err_when;
    if (ORDER.time && !/^\d{2}:\d{2}$/.test(order.time)) errors.time = L.err_time;
    if (ORDER.kind === "lead" ? !(phoneOk || EMAIL.test(order.contact)) : !phoneOk) {
      errors.phone = ORDER.kind === "lead" ? L.err_contact : L.err_phone;
    }
    if (order.delivery === "ship" && order.address.length < 6) errors.address = L.err_address;
  } else if (source === "checkout") {
    if (!lines.length) errors.item = L.err_item;
    if (!phoneOk) errors.phone = L.err_phone;
    if (order.address.length < 6) errors.address = L.err_address;
  } else if (source === "booking") {
    if (!order.item) errors.item = L.err_item;
    if (!date.test(order.date)) errors.date = L.err_when;
    if (!/^\d{2}:\d{2}$/.test(order.time)) errors.time = L.err_time;
    if (!phoneOk) errors.phone = L.err_phone;
  } else {
    if (!(phoneOk || EMAIL.test(order.contact))) errors.phone = L.err_contact;
    if (order.note.length < 10) errors.note = L.err_message;
  }
  if (Object.keys(errors).length) return NextResponse.json({ ok: false, errors }, { status: 400 });

  const id = Date.now().toString(36).slice(-4).toUpperCase() + Math.random().toString(36).slice(2, 4).toUpperCase();
  const record = { id, at: new Date().toISOString(), ...order };
  let saved = false;
  try {
    await mkdir("data", { recursive: true });
    await appendFile("data/orders.jsonl", JSON.stringify(record) + "\n", "utf8");
    saved = true;
  } catch {
    saved = false; // read-only disk (serverless): the webhook or the shop's own channels take over
  }
  let forwarded = false;
  const hook = process.env.ORDER_WEBHOOK_URL;
  if (hook) {
    try {
      const r = await fetch(hook, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(record) });
      forwarded = r.ok;
    } catch {
      forwarded = false;
    }
  }
  if (!saved && !forwarded) return NextResponse.json({ ok: false }, { status: 503 });
  return NextResponse.json({ ok: true, id });
}
'''

ORDER_CSS = """
/* Order form (components/OrderDialog.tsx) */
.order { width: min(560px, 100%); max-height: calc(100dvh - 48px); overflow-y: auto; }
.order-close { font-size: var(--text-h3); line-height: 1; }
.order-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.order-form { gap: 16px; }
.order-row { display: grid; gap: 16px; }
@media (min-width: 560px) { .order-row { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); } }
.order-qty { max-width: 160px; }
.field { display: flex; flex-direction: column; gap: 8px; min-width: 0; border: 0; padding: 0; margin: 0; }
.field .input { width: 100%; }
.field-error { color: var(--danger); }
.order-delivery .row { gap: 16px; }
.order-choice { display: inline-flex; align-items: center; gap: 8px; min-height: 48px; cursor: pointer; }
.order-choice input { width: 20px; height: 20px; accent-color: var(--action, var(--text-primary)); }
.order-summary { white-space: pre-wrap; margin: 0; padding: 16px; border-radius: var(--radius-sm);
  background: var(--bg-surface); border: 1px solid var(--border-subtle); font-family: inherit; }
.order-channels { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.order-channels .btn { text-decoration: none; }
@media (max-width: 559px) {
  .order-scrim { place-items: end stretch; padding: 0; }
  .order { width: 100%; max-height: 92dvh; border-radius: var(--radius-lg) var(--radius-lg) 0 0; padding: 24px 16px; }
}
"""

GUIDE = """
## 4. Nhận đơn

Nút chính của trang (ví dụ "Đặt bánh") mở form đặt hàng. Khách điền xong bấm Gửi, đơn được gửi tới `app/api/orders/route.ts`:

- **Chạy trên máy của bạn hoặc máy chủ riêng:** đơn được lưu vào `data/orders.jsonl`, mỗi dòng một đơn. File này chứa số điện thoại của khách: đừng đưa nó lên mạng.
- **Đăng lên Vercel hoặc nơi không ghi được file:** tạo một webhook nhận đơn (Google Sheets qua Apps Script, Make hoặc Zapier), rồi đặt biến môi trường `ORDER_WEBHOOK_URL` bằng địa chỉ đó.
- **Chưa có cả hai:** khách thấy dòng "Đơn chưa gửi tự động được" và các nút Zalo, gọi điện, nhắn tin, email lấy từ `content/order.ts` (mục `channels`). Hãy điền số điện thoại hoặc Zalo của bạn ở đó.
"""
