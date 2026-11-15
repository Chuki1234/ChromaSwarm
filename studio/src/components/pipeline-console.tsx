"use client";

import { useEffect, useRef, useState } from "react";
import { BuildPanel } from "@/components/build-panel";
import { QuestionCard, type Answer, type Question } from "@/components/question-card";
import { Welcome } from "@/components/welcome";

const BACKEND_WS = process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100";

const STEPS: { id: string; label: string; phase: string }[] = [
  { id: "B1", label: "Đọc prompt", phase: "Tư vấn" },
  { id: "B2", label: "Tư vấn sitemap", phase: "Tư vấn" },
  { id: "B3", label: "Hỏi 5 trụ cột", phase: "Tư vấn" },
  { id: "B4", label: "Assets & tham khảo", phase: "Tư vấn" },
  { id: "B5", label: "DESIGN.md", phase: "Kế hoạch" },
  { id: "B6", label: "PRODUCT.md + PLAN.md", phase: "Kế hoạch" },
  { id: "B7", label: "Duyệt kế hoạch", phase: "Kế hoạch" },
  { id: "B8", label: "Phòng Design", phase: "Triển khai" },
  { id: "B9", label: "Phòng Developer", phase: "Triển khai" },
  { id: "B10", label: "Hợp nhất", phase: "Triển khai" },
  { id: "B11", label: "Cursor Lớn Nhất", phase: "Kiểm định" },
  { id: "B12", label: "Bàn giao", phase: "Kiểm định" },
];

export type PipelineState = {
  step: string;
  mode: "creative" | "clone" | null;
  clone: { url: string; owned: boolean; title: string | null; notes: string[] } | null;
  session_id: string;
  design_md: string | null;
  product_md: string | null;
  plan_md: string | null;
  pillars: Record<string, string | null>;
  sections_planned: string[];
  sections_done: string[];
  sections_checked: string[];
  preview_url: string | null;
  token_changes: string[];
  open_findings: string[];
  build_error: string | null;
  qa_passed: boolean;
  qa_summary: string | null;
  qa_failures: string[];
  design_score: number | null;
  design_critique: string[];
  heal_history: { iteration: number; failures: string[] }[];
  heal_rules: string[];
  escalated_to_user: boolean;
  page_routes: Record<string, string>;
  motion_effects: string[];
  handover_closed: boolean;
};

type Snapshot = {
  state: PipelineState;
  question: Question | null;
  notice: string | null;
  finished: boolean;
  missing: string[];
  tools: string[];
  clarity_score: number;
  running: boolean;
};

type Status = "connecting" | "open" | "closed";
type Turn = { step: string; question: string; answer: string };
type ChatLine = { role: "user" | "assistant"; text: string };

function sessionId(): string {
  try {
    const saved = localStorage.getItem("chromaswarm-session");
    if (saved) return saved;
    const id = `s-${Date.now().toString(36)}`;
    localStorage.setItem("chromaswarm-session", id);
    return id;
  } catch {
    return `s-${Date.now().toString(36)}`;
  }
}

export function PipelineConsole() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<Status>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState<Turn[]>([]);
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`${BACKEND_WS}/ws/session/${sessionId()}`);
    wsRef.current = ws;
    ws.onopen = () => setStatus("open");
    ws.onclose = () => setStatus("closed");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      setBusy(false);
      if (msg.type === "state") {
        setSnap(msg);
        setError(null);
      } else if (msg.type === "chat") {
        setChat((c) => [...c, { role: msg.role, text: msg.text }]);
        if (msg.role === "user") setBusy(true); // the reply / next question is on its way
      } else if (msg.type === "error") {
        setError(msg.message);
      }
    };
    return () => ws.close();
  }, []);

  const answer = (a: Answer) => {
    if (!snap?.question) return;
    setHistory((h) => [...h, { step: snap.state.step, question: snap.question!.text.split("\n")[0], answer: a.label }]);
    setBusy(true);
    wsRef.current?.send(JSON.stringify({ type: "answer", value: a.value }));
  };

  const sendChat = () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setBusy(true);
    wsRef.current?.send(JSON.stringify({ type: "chat", text }));
  };

  const restart = () => {
    try {
      localStorage.removeItem("chromaswarm-session");
    } catch {}
    location.reload();
  };

  const current = snap?.state.step ?? "B1";
  // Creative mode (and the mode choice itself) talks through the chat bar; Clone uses its form.
  const chatEnabled = !!snap && snap.state.mode !== "clone" && !!snap.question && snap.question.kind !== "clone_source";
  const currentIdx = STEPS.findIndex((s) => s.id === current);
  // B1 before anything was said: the landing view (what Chroma does + the Creative / Clone choice).
  const welcome = current === "B1" && snap?.question?.kind === "mode" && history.length === 0 && chat.length === 0;
  const phases = [...new Set(STEPS.map((s) => s.phase))];
  const statusLabel = { open: "Đã kết nối", connecting: "Đang kết nối", closed: "Mất kết nối" }[status];

  return (
    <main className="mx-auto grid w-full max-w-[1360px] flex-1 gap-8 px-4 py-12 md:grid-cols-[240px_1fr] md:px-8 lg:grid-cols-[240px_1fr_280px]">
      <div className="backdrop" aria-hidden />
      <aside className="flex flex-col gap-6">
        <div className="flex items-center justify-between gap-3">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Logo />ChromaSwarm
          </h1>
          <span className="flex items-center gap-2 whitespace-nowrap text-xs text-fg-2" role="status">
            <span className={`h-2 w-2 rounded-full ${status === "open" ? "dot-live bg-accent" : status === "closed" ? "bg-danger" : "bg-fg-3"}`} />
            {statusLabel}
          </span>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs text-fg-2">
            <span>Tiến độ</span>
            <span className="font-mono">{currentIdx + 1}/{STEPS.length}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface" role="progressbar" aria-label="Tiến độ 12 bước"
            aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={currentIdx + 1}>
            <div className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out"
              style={{ width: `${((currentIdx + 1) / STEPS.length) * 100}%` }} />
          </div>
        </div>
        <nav aria-label="Các bước" className="hidden flex-col gap-4 md:flex" data-swarm-section="step-tracker">
          {phases.map((phase) => (
            <div key={phase} className="flex flex-col gap-1">
              <p className="px-3 font-mono text-[11px] uppercase tracking-[0.16em] text-fg-3">{phase}</p>
              <ol className="flex flex-col">
                {STEPS.filter((s) => s.phase === phase).map((s) => {
                  const i = STEPS.indexOf(s);
                  const state = i < currentIdx ? "done" : i === currentIdx ? "current" : "todo";
                  return (
                    <li key={s.id} aria-current={state === "current" ? "step" : undefined}
                      className={`flex items-center gap-3 rounded-lg px-3 py-1.5 text-sm transition-colors duration-300 ${
                        state === "current" ? "bg-surface font-medium text-fg" : state === "done" ? "text-fg-2" : "text-fg-3"}`}>
                      <span className="grid h-5 w-5 shrink-0 place-items-center" aria-hidden>
                        {state === "done" ? (
                          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-accent"><path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                        ) : state === "current" ? (
                          <span className="dot-live h-2 w-2 rounded-full bg-accent" />
                        ) : (
                          <span className="h-1.5 w-1.5 rounded-full bg-line" />
                        )}
                      </span>
                      <span className="w-8 font-mono text-xs">{s.id}</span>
                      <span>{s.label}</span>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </nav>
        <button
          type="button"
          onClick={restart}
          data-swarm-id="restart-session"
          data-swarm-role="button"
          className="mt-4 self-start text-xs text-fg-3 underline-offset-4 transition-colors duration-200 hover:text-fg hover:underline"
        >
          Bắt đầu phiên mới
        </button>
      </aside>

      <section className={`flex min-w-0 flex-col gap-8 ${welcome ? "lg:col-span-2" : ""}`} data-swarm-section="conversation">
        {welcome && snap?.question ? (
          <Welcome question={snap.question} busy={busy || status !== "open"} onAnswer={answer} />
        ) : (
        <>
        <header className="flex flex-col gap-2">
          <p className="font-mono text-xs uppercase tracking-widest text-fg-3">
            {STEPS[currentIdx]?.phase} · {current}
          </p>
          <h2 className="text-3xl font-semibold tracking-tight">{STEPS[currentIdx]?.label}</h2>
        </header>

        {history.length > 0 && (
          <ol className="flex flex-col gap-4 border-b border-line pb-8">
            {history.map((t, i) => (
              <li key={i} className="grid grid-cols-[40px_1fr] gap-x-4 gap-y-1 text-sm">
                <span className="font-mono text-xs text-fg-3">{t.step}</span>
                <span className="text-fg-2">{t.question}</span>
                <span />
                <span className="font-medium">→ {t.answer}</span>
              </li>
            ))}
          </ol>
        )}

        {chat.length > 0 && (
          <ol className="flex flex-col gap-3" aria-label="Trò chuyện với Chroma" data-swarm-section="chat-log">
            {chat.map((m, i) => (
              <li key={i} className={`max-w-[72ch] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                m.role === "user" ? "self-end bg-surface text-fg" : "self-start border border-line text-fg-2"}`}>
                {m.role === "assistant" && <span className="mb-1 block font-mono text-[11px] uppercase tracking-wider text-fg-3">Chroma</span>}
                {m.text}
              </li>
            ))}
          </ol>
        )}

        {error && (  /* next to the question, where the user is looking */
          <p role="alert" className="rounded-lg border border-danger/40 px-4 py-3 text-sm text-danger">
            {error} Bạn gửi lại câu trả lời giúp mình nhé.
          </p>
        )}

        {snap?.question?.kind === "handover" && <BuildPanel state={snap.state} notice={null} running={false} />}

        {snap?.question ? (
          <QuestionCard
            key={`${snap.state.step}-${snap.question.key}-${history.length}`}
            question={snap.question}
            notice={snap.notice}
            state={snap.state}
            busy={busy || status !== "open"}
            onAnswer={answer}
            chatMode={chatEnabled}
          />
        ) : snap && (snap.running || snap.finished) && currentIdx >= STEPS.findIndex((s) => s.id === "B8") ? (
          <BuildPanel state={snap.state} notice={snap.notice} running={snap.running} />
        ) : !snap ? (
          <LoadingSkeleton closed={status === "closed"} />
        ) : (
          <p className="flex items-center gap-2 text-sm text-fg-2"><span className="dot-live h-2 w-2 rounded-full bg-accent" />Đang xử lý…</p>
        )}
        {chatEnabled && (
          <form
            className="sticky bottom-4 flex gap-3 rounded-xl border border-line bg-bg p-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendChat();
            }}
            data-swarm-section="chat-bar"
          >
            <label htmlFor="chat-input" className="sr-only">Nhắn cho Chroma</label>
            <input id="chat-input" value={draft} onChange={(e) => setDraft(e.target.value)} autoComplete="off"
              placeholder="Trả lời, hỏi lại (vd: “Bento là gì?”) hoặc đổi ý (vd: “cho mình đổi lại màu”)…"
              className="h-12 flex-1 rounded-lg bg-transparent px-3 text-sm outline-none placeholder:text-fg-3"
              data-swarm-id="chat-input" data-swarm-role="input" />
            <button type="submit" disabled={busy || status !== "open" || !draft.trim()} data-swarm-id="chat-send"
              data-swarm-role="button"
              className="h-12 rounded-lg bg-accent px-6 text-sm font-medium text-accent-fg transition-[filter,transform] duration-200 hover:brightness-110 active:scale-[0.98] disabled:opacity-50">
              Gửi
            </button>
          </form>
        )}
        </>
        )}
      </section>

      <aside className={`flex-col gap-4 md:col-start-2 lg:col-start-auto ${welcome ? "hidden" : "flex"}`} data-swarm-section="gates">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-1">
          <Stat label="Clarity Score (B3)" value={`${Math.round((snap?.clarity_score ?? 0) * 100)}%`} />
          <Stat label="Tool được cấp" value={String(snap?.tools.length ?? "–")} />
        </div>
        <Panel title="Điều kiện để qua bước">
          {snap?.missing.length ? (
            <ul className="flex flex-col gap-2 font-mono text-xs text-fg-2">
              {snap.missing.map((m) => (
                <li key={m}>— {m}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-fg-2">Đã đủ.</p>
          )}
        </Panel>
        <Panel title="Tool agent được dùng">
          <ul className="flex flex-wrap gap-2">
            {snap?.tools.map((t) => (
              <li key={t} className="rounded-md border border-line px-2 py-1 font-mono text-xs text-fg-2">
                {t}
              </li>
            ))}
          </ul>
        </Panel>
      </aside>
    </main>
  );
}

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden className="text-accent">
      <path d="m12 2 9 5v10l-9 5-9-5V7l9-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m3 7 9 5 9-5M12 12v10" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function LoadingSkeleton({ closed }: { closed: boolean }) {
  if (closed)
    return (
      <p role="alert" className="rounded-lg border border-danger/40 px-4 py-3 text-sm text-danger">
        Không kết nối được tới backend (cổng 8100). Hãy chạy backend rồi tải lại trang.
      </p>
    );
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Đang tải">
      <div className="h-4 w-40 animate-pulse rounded bg-surface" />
      <div className="h-12 w-3/4 animate-pulse rounded-lg bg-surface" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-32 animate-pulse rounded-2xl bg-surface" />
        <div className="h-32 animate-pulse rounded-2xl bg-surface" />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-line bg-surface p-4">
      <span className="text-xs text-fg-3">{label}</span>
      <span className="font-mono text-2xl">{value}</span>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
      <h3 className="text-sm font-medium">{title}</h3>
      {children}
    </div>
  );
}
