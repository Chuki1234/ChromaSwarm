"use client";

import { useEffect, useState } from "react";

const BACKEND_HTTP = (process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100").replace(/^ws/, "http");

type Saved = { id: string; url: string | null; title: string | null; step: string; status: string; fidelity: number | null; updated_at: string };

const STATUS: Record<string, string> = {
  reading: "Đang đọc trang mẫu", planning: "Đang lên kế hoạch", building: "Đang dựng",
  "handed-over": "Đã bàn giao", finished: "Đã kết thúc", error: "Gặp lỗi",
};

/** Clone mode: saved sessions (Supabase, via the backend) — open one to continue where it was. */
export function CloneHistory({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<Saved[] | null>(null);
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${BACKEND_HTTP}/clone/sessions`)
      .then((r) => r.json())
      .then((d) => { if (alive) { setEnabled(!!d.enabled); setRows(d.sessions ?? []); } })
      .catch(() => alive && setRows([]));
    return () => { alive = false; };
  }, []);

  if (!enabled || !rows || rows.length === 0) return null;
  return (
    <section className="flex flex-col gap-3" aria-label="Phiên Clone đã lưu" data-swarm-section="clone-history">
      <h2 className="text-sm font-medium">Phiên Clone đã lưu</h2>
      <ul className="flex flex-col divide-y divide-line rounded-xl border border-line">
        {rows.slice(0, 8).map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-4 px-4 py-3">
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm">{s.title || s.url || s.id}</span>
              <span className="truncate text-xs text-fg-3">
                {STATUS[s.status] ?? s.status} · {s.step}
                {s.fidelity != null && ` · giống ${Math.round(s.fidelity)}%`}
                {" · "}{new Date(s.updated_at).toLocaleString("vi-VN")}
              </span>
            </span>
            <button type="button" onClick={() => onOpen(s.id)} data-swarm-id={`open-session-${s.id}`} data-swarm-role="button"
              className="min-h-11 shrink-0 rounded-lg border border-line px-4 text-sm hover:bg-surface">
              Mở lại
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The saved conversation of a Clone session, as thread items (answers and Chroma's notices). */
export async function savedThread(id: string): Promise<{ role: "user" | "assistant"; text: string }[]> {
  try {
    const r = await fetch(`${BACKEND_HTTP}/clone/sessions/${encodeURIComponent(id)}/messages`);
    const d = await r.json();
    return (d.messages ?? []).filter((m: { kind: string }) => m.kind !== "question")
      .map((m: { role: "user" | "assistant"; text: string }) => ({ role: m.role, text: m.text }));
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------- local persistence (this browser)
// localStorage can be unavailable (private window, blocked storage): every access is guarded and the Studio
// works without it — Supabase (via the backend) stays the source the conversation can be rebuilt from.

const DRAFT_KEY = "chromaswarm-clone-draft";
const THREAD_KEY = (id: string) => `chromaswarm-clone-thread:${id}`;

/** The link typed in the Clone form but not sent yet. */
export function loadDraft(): { url: string; owned: boolean } {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) {
      const d = JSON.parse(raw);
      return { url: String(d.url ?? ""), owned: !!d.owned };
    }
  } catch {}
  return { url: "", owned: false };
}

export function saveDraft(url: string, owned: boolean) {
  try {
    if (url) localStorage.setItem(DRAFT_KEY, JSON.stringify({ url, owned }));
    else localStorage.removeItem(DRAFT_KEY);
  } catch {}
}

type Kept = { kind: "user" | "assistant"; text: string; tone?: "error" } | { kind: "motion"; report: unknown } | { kind: "analysis"; text: string };

/** A Clone session's conversation as shown (answers, notices, effect card, analysis) — not the live question. */
export function loadThread(id: string): Kept[] {
  try {
    const raw = localStorage.getItem(THREAD_KEY(id));
    return raw ? (JSON.parse(raw) as Kept[]) : [];
  } catch {
    return [];
  }
}

export function saveThread(id: string, items: { kind: string }[]) {
  try {
    const kept = items.filter((it) => ["user", "assistant", "motion", "analysis"].includes(it.kind)).slice(-200);
    localStorage.setItem(THREAD_KEY(id), JSON.stringify(kept));
  } catch {}
}
