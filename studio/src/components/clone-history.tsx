"use client";

import { useEffect, useState } from "react";

const BACKEND_HTTP = (process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100").replace(/^ws/, "http");

export type Saved = { id: string; url: string | null; title: string | null; step: string; status: string; fidelity: number | null; updated_at: string };

export const STATUS: Record<string, string> = {
  reading: "Đang đọc trang mẫu", planning: "Đang lên kế hoạch", building: "Đang dựng",
  "handed-over": "Đã bàn giao", finished: "Đã kết thúc", error: "Gặp lỗi",
};

/** Clone mode: saved sessions (Supabase, via the backend), newest first. `null` while loading; `[]` when the
 * store is off or empty. Shown in the history sidebar — open one to continue where it was. */
export function useCloneSessions(): Saved[] | null {
  const [rows, setRows] = useState<Saved[] | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(`${BACKEND_HTTP}/clone/sessions`)
      .then((r) => r.json())
      .then((d) => { if (alive) setRows(d.enabled ? d.sessions ?? [] : []); })
      .catch(() => alive && setRows([]));
    return () => { alive = false; };
  }, []);
  return rows;
}

/** The saved conversation of a Clone session, as thread items (answers and Chroma's notices). */
export async function savedThread(id: string): Promise<{ role: "user" | "assistant"; text: string; step: string | null }[]> {
  try {
    const r = await fetch(`${BACKEND_HTTP}/clone/sessions/${encodeURIComponent(id)}/messages`);
    const d = await r.json();
    return (d.messages ?? []).filter((m: { kind: string }) => m.kind !== "question")
      .map((m: { role: "user" | "assistant"; text: string; step: string | null }) => ({ role: m.role, text: m.text, step: m.step }));
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

type Kept = { kind: "user" | "assistant"; text: string; tone?: "error" } | { kind: "motion"; report: unknown }
  | { kind: "analysis" | "brief"; text: string } | { kind: "sketch"; stage: string; result: unknown };

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
    const kept = items.filter((it) => ["user", "assistant", "motion", "analysis", "brief", "sketch"].includes(it.kind)).slice(-200);
    localStorage.setItem(THREAD_KEY(id), JSON.stringify(kept));
  } catch {}
}
