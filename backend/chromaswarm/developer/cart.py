"""The shop's cart, kept across pages (Level 2: a cart that holds what the visitor picked).

`components/Cart.tsx` is one small store in the visitor's browser (localStorage, falling back to
memory when storage is blocked). "Thêm vào giỏ" on product cards, the quick view and the product
page add to it; the header icon shows its count and lines; the /cart page reads and edits it and
empties it once the order is sent.

The store is only used once the site has a cart page: `ORDER.cart` (content/order.ts, rewritten on
every page build) holds its route. Until then the same buttons open the order form for that item,
so a visitor never fills a cart nobody can check out. Items without a readable price ("Liên hệ")
always go through the order form.
"""

CART_TSX = r'''"use client";

import { useSyncExternalStore } from "react";

/** One line of the cart. `price` is in ₫ for one unit. */
export type CartLine = { name: string; price: number; qty: number; image?: string; note?: string };

const KEY = "cart";
const EVENT = "cart:change";
const EMPTY: CartLine[] = [];
let lines: CartLine[] | null = null;

const valid = (l: unknown): l is CartLine => {
  const x = l as CartLine;
  return !!x && typeof x.name === "string" && Number.isFinite(x.price) && x.price >= 0
    && Number.isInteger(x.qty) && x.qty > 0 && x.qty <= 99;
};

function load(): CartLine[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter(valid).slice(0, 30) : [];
  } catch {
    return [];
  }
}

function read(): CartLine[] {
  if (lines === null) lines = load();
  return lines;
}

function write(next: CartLine[]) {
  lines = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // storage blocked (private window): the cart still works on this page
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(fn: () => void) {
  const other = (e: StorageEvent) => {
    if (e.key === KEY) { lines = load(); fn(); } // another tab changed the cart
  };
  window.addEventListener(EVENT, fn);
  window.addEventListener("storage", other);
  return () => { window.removeEventListener(EVENT, fn); window.removeEventListener("storage", other); };
}

/** The cart's lines, live on every page. Empty during the server render. */
export function useCart(): CartLine[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}

export function addToCart(item: { name: string; price: number; image?: string; note?: string }, qty = 1) {
  const now = read();
  const found = now.find((l) => l.name === item.name);
  write(found
    ? now.map((l) => (l === found ? { ...l, qty: Math.min(99, l.qty + qty) } : l))
    : [...now, { name: item.name, price: item.price, qty, image: item.image || undefined, note: item.note || undefined }]);
}

export function setCartQty(name: string, qty: number) {
  const now = read();
  write(qty <= 0 ? now.filter((l) => l.name !== name) : now.map((l) => (l.name === name ? { ...l, qty: Math.min(99, qty) } : l)));
}

export function clearCart() {
  write([]);
}

/** False during the server render and hydration, true after: the cart page waits for it before
 * saying the cart is empty, so a full cart never flashes "empty". */
export function useHydrated(): boolean {
  return useSyncExternalStore(() => () => {}, () => true, () => false);
}

export const cartCount = (l: CartLine[]) => l.reduce((n, x) => n + x.qty, 0);
export const cartTotal = (l: CartLine[]) => l.reduce((n, x) => n + x.price * x.qty, 0);
export const money = (n: number) => n.toLocaleString("vi-VN") + "₫";
'''

CART_CSS = """
.cart-pop-lines { list-style: none; padding: 0; margin: 0 0 12px; display: flex; flex-direction: column; gap: 8px; }
.cart-pop-lines li { display: flex; justify-content: space-between; gap: 12px; }
.cart-pop-total { display: flex; justify-content: space-between; gap: 12px; padding-top: 12px; margin-bottom: 12px; border-top: 1px solid var(--border-subtle); }
.cart-pop .btn { width: 100%; }
.added-note { min-height: 1.5em; }
"""
