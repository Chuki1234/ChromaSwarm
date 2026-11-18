"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BuildPanel } from "@/components/build-panel";
import { CloneSource, QuestionCard, type Answer, type Question } from "@/components/question-card";

const BACKEND_WS = process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100";

// What each pipeline step means for the user, in their words (ids stay the backend's B1..B12).
const STEPS: { id: string; label: string; phase: string; subs?: string[] }[] = [
  { id: "B1", label: "Lắng nghe ý tưởng", phase: "Thấu hiểu" },
  { id: "B2", label: "Chọn trang làm trước", phase: "Thấu hiểu" },
  { id: "B3", label: "Phong cách & khách hàng", phase: "Thấu hiểu" },
  { id: "B4", label: "Ảnh, logo & trang mẫu", phase: "Thấu hiểu" },
  { id: "B5", label: "Màu, chữ & khoảng cách", phase: "Lên kế hoạch" },
  { id: "B6", label: "Bố cục từng phần", phase: "Lên kế hoạch" },
  { id: "B7", label: "Bạn duyệt kế hoạch", phase: "Lên kế hoạch" },
  { id: "B8", label: "Cài đặt giao diện", phase: "Dựng trang" },
  { id: "B9", label: "Dựng từng phần trang", phase: "Dựng trang" },
  { id: "B10", label: "Ghép trang hoàn chỉnh", phase: "Dựng trang" },
  { id: "B11", label: "Kiểm tra & chấm điểm", phase: "Hoàn thiện" },
  { id: "B12", label: "Bàn giao cho bạn", phase: "Hoàn thiện" },
];
type Step = (typeof STEPS)[number];

// Clone runs the same 12 steps, but the first four read the reference page instead of asking questions.
const CLONE_STEPS: Step[] = [
  { id: "B1", label: "Đọc URL & phân tích", phase: "Đọc trang mẫu" },
  { id: "B2", label: "Tách phần & kiểm tra hiệu ứng", phase: "Đọc trang mẫu",
    subs: ["Tách các phần và component của trang", "Kiểm tra hiệu ứng: Playwright cuộn, rê chuột, đo thời gian"] },
  { id: "B3", label: "Phong cách từ trang mẫu", phase: "Đọc trang mẫu" },
  { id: "B4", label: "Font, ngôn ngữ & ảnh", phase: "Đọc trang mẫu" },
  { id: "B5", label: "Hệ màu, chữ & khoảng cách", phase: "Thiết kế" },
  { id: "B6", label: "Chọn layout từng phần", phase: "Thiết kế" },
  { id: "B7", label: "Bạn duyệt kế hoạch", phase: "Thiết kế" },
  { id: "B8", label: "Chuẩn bị khung & token", phase: "Dựng trang" },
  { id: "B9", label: "Dựng wireframe", phase: "Dựng trang",
    subs: ["Cursor section → tổ chữ / nút / ảnh → cursor từng component", "Tinh chỉnh từng component theo trang mẫu, nhập về"] },
  { id: "B10", label: "Tô màu & điền nội dung", phase: "Dựng trang" },
  { id: "B11", label: "Kiểm tra & nghiệm thu 1:1", phase: "Hoàn thiện",
    subs: ["Master QA: 4 bài kiểm tra", "Master Cursor so 1:1 từng component với link gốc"] },
  { id: "B12", label: "Bàn giao template", phase: "Hoàn thiện" },
];

// One click from the empty screen: a complete prompt goes straight to the plan (agents/brief.py).
const EXAMPLES: { tag: string; text: string }[] = [
  { tag: "Bán hàng", text: "Landing page bán nến thơm handmade, phong cách sang trọng, nền kem, màu xanh rêu, khách văn phòng 25-35 tuổi, muốn họ bấm Đặt mua" },
  { tag: "Đặt lịch", text: "Trang đặt lịch spa, tông tối sang trọng, muốn khách bấm Đặt lịch ngay" },
  { tag: "SaaS", text: "Landing page cho phần mềm quản lý dự án, giao diện hiện đại, nền tối, nút Dùng thử miễn phí" },
  { tag: "Thời trang", text: "Web bán giày sneaker cho sinh viên, phong cách cá tính, nhiều sản phẩm" },
];

export type PipelineState = {
  step: string;
  mode: "creative" | "clone" | null;
  clone: {
    url: string; owned: boolean; title: string | null; notes: string[];
    motion_report?: MotionReport | null;
  } | null;
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
  clone_fidelity?: number | null;
  clone_fidelity_notes?: string[];
  clone_compare?: CompareResult | null;
  compare_rounds?: number;
  factory_log?: string[];
  design_critique: string[];
  heal_history: { iteration: number; failures: string[] }[];
  heal_rules: string[];
  escalated_to_user: boolean;
  page_routes: Record<string, string>;
  motion_effects: string[];
  handover_closed: boolean;
};

export type MotionReport = {
  has_motion: boolean; steps?: number; hovered?: number; libs?: string[]; unsupported?: string[]; error?: string;
  items: { effect: string; section: string; label: string; how: string; params: Record<string, number | string> }[];
};
export type CompareSection = {
  id: string; name: string; score: number; parts: Record<string, number>; matched: number;
  diffs: string[]; effects_missing: string[]; ref_height: number; built_height: number;
  ref_image: string | null; built_image: string | null;
};
export type CompareResult = { total: number; rounds: number; tuned: number; sections: CompareSection[] };

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
/** The conversation as the user reads it, oldest first. Questions stay in place once answered. */
type Item =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string; tone?: "error" }
  | { kind: "question"; sig: string; q: Question; note: string | null }
  | { kind: "motion"; report: MotionReport };

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

// Gate keys from the backend (pipeline_state.missing_for_exit) in the user's words.
const NEEDS: Record<string, string> = {
  mode: "Chọn Creative hoặc Clone", raw_prompt: "Mô tả trang web bạn muốn", domain: "Xác định lĩnh vực",
  clone_url: "Link trang mẫu", clone_analysis: "Đọc trang mẫu", sitemap: "Danh sách trang", selected_page: "Chọn trang làm trước",
  "pillar:theme": "Phong cách", "pillar:layout": "Bố cục", "pillar:color": "Tông màu", "pillar:margins": "Độ thoáng",
  "pillar:scope": "Khách hàng & nút chính", assets_confirmed: "Ảnh, logo (hoặc bỏ qua)", design_md: "Bộ nhận diện",
  product_md: "Mô tả sản phẩm", plan_md: "Kế hoạch bố cục", user_approval: "Bạn duyệt kế hoạch",
  design_system: "Cài đặt giao diện", sections_planned: "Danh sách phần trang", integrated: "Ghép trang", qa_passed: "Qua kiểm tra chất lượng",
};
// Clone asks only for the link; everything else is read from the reference page.
const CLONE_NEEDS: Record<string, string> = {
  raw_prompt: "Dán link trang mẫu", domain: "Nhận loại trang (tự động)", "pillar:scope": "Đối tượng (tự động)",
};
const needLabel = (k: string, clone = false) =>
  (clone ? CLONE_NEEDS[k] : undefined) ?? NEEDS[k] ?? (k.startsWith("write:") ? `Dựng phần “${k.slice(6)}”` : k.startsWith("check:") ? `Kiểm tra phần “${k.slice(6)}”` : k);

const MODE_KEY = "chromaswarm-mode"; // the mode to open with after "Đổi chế độ" starts a new session

function savedMode(): "creative" | "clone" {
  try {
    return localStorage.getItem(MODE_KEY) === "clone" ? "clone" : "creative";
  } catch {
    return "creative";
  }
}

const sigOf = (s: Snapshot) => (s.question ? `${s.state.step}|${s.question.key}|${s.question.text}` : "");

export function PipelineConsole() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<Status>("connecting");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [draft, setDraft] = useState("");
  // Local until something is sent: the user can switch Creative <-> Clone freely on the empty screen.
  const [mode, setMode] = useState<"creative" | "clone">("creative");
  const [panelOpen, setPanelOpen] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const lastSig = useRef("");
  const lastNote = useRef<string | null>(null);
  const motionShown = useRef(false); // the B2 effect-check report goes into the thread once
  const pendingPrompt = useRef<string | null>(null); // typed on the empty screen, sent once Chroma asks for it
  const pendingClone = useRef<Answer | null>(null); // Clone form filled on the empty screen, sent once Chroma asks for it
  const endRef = useRef<HTMLDivElement>(null);

  const send = (payload: object) => wsRef.current?.send(JSON.stringify(payload));

  useEffect(() => {
    const ws = new WebSocket(`${BACKEND_WS}/ws/session/${sessionId()}`);
    wsRef.current = ws;
    ws.onopen = () => {
      setStatus("open");
      setMode(savedMode()); // after "Đổi chế độ": open the new session in the chosen mode
    };
    ws.onclose = () => setStatus("closed");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        const s = msg as Snapshot;
        setSnap(s);
        setBusy(false);
        const sig = sigOf(s);
        // The prompt / Clone form filled on the empty screen answers this question: don't show it again.
        if ((pendingPrompt.current && s.question?.key === "raw_prompt") ||
            (pendingClone.current && s.question?.kind === "clone_source")) lastSig.current = sig;
        if (sig && sig !== lastSig.current) {
          lastSig.current = sig;
          lastNote.current = s.notice;
          // The mode choice lives on the empty screen, not in the thread.
          if (s.question!.kind !== "mode") setItems((it) => [...it, { kind: "question", sig, q: s.question!, note: s.notice }]);
        } else if (s.notice && s.notice !== lastNote.current) {
          lastNote.current = s.notice; // same question, new remark ("chưa hiểu rõ…", "đã ghi lại…")
          setItems((it) => [...it, { kind: "assistant", text: s.notice! }]);
        }
        const mr = s.state?.clone?.motion_report;
        if (mr && !motionShown.current) {
          motionShown.current = true;
          setItems((it) => [...it, { kind: "motion", report: mr }]);
        }
        if (pendingClone.current && s.question?.kind === "clone_source") {
          const a = pendingClone.current;
          pendingClone.current = null;
          setBusy(true);
          send({ type: "answer", value: a.value });
        }
        if (pendingPrompt.current && s.question?.key === "raw_prompt") {
          const text = pendingPrompt.current;
          pendingPrompt.current = null;
          setBusy(true);
          send({ type: "chat", text });
        }
      } else if (msg.type === "chat") {
        setItems((it) => [...it, { kind: msg.role === "user" ? "user" : "assistant", text: msg.text }]);
        // user echo: the reply is on its way. Chroma's reply: done — an answer to a question ("Bento là gì?")
        // comes with no new state, so waiting for one would leave the composer locked.
        setBusy(msg.role === "user");
      } else if (msg.type === "error") {
        setBusy(false);
        setItems((it) => [...it, { kind: "assistant", tone: "error", text: `${msg.message} Bạn gửi lại giúp mình nhé.` }]);
      }
    };
    return () => ws.close();
  }, []);

  useLayoutEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [items, busy, snap?.state.sections_checked?.length, snap?.state.qa_summary]);

  useEffect(() => {
    if (!panelOpen) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setPanelOpen(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [panelOpen]);

  const question = snap?.question ?? null;
  const step = snap?.state.step ?? "B1";
  const empty = items.length === 0 && (!question || question.kind === "mode");
  const cloneMode = snap?.state.mode === "clone";
  const cloneView = cloneMode || (empty && mode === "clone");  // the tracker follows the switch on the empty screen
  const steps = cloneView ? CLONE_STEPS : STEPS;
  const stepIdx = steps.findIndex((s) => s.id === step);
  // Clone fills its own form; every other question accepts plain chat (answers, questions, changes of mind).
  // At handover a Clone takes plain text too: it is feedback to refine the page.
  const cloneRefine = cloneMode && question?.kind === "handover";
  const chatOpen = status === "open" && (cloneRefine || (!cloneMode && question?.kind !== "clone_source"));

  const answer = (a: Answer) => {
    if (!question) return;
    setItems((it) => [...it, { kind: "user", text: a.label }]);
    setBusy(true);
    send({ type: "answer", value: a.value });
  };

  const submit = (text: string) => {
    const t = text.trim();
    if (!t || busy || status !== "open") return;
    setDraft("");
    if (question?.kind === "mode") {
      // Empty screen: pick Creative, then send the prompt as soon as Chroma asks for it.
      pendingPrompt.current = t;
      setBusy(true);
      send({ type: "answer", value: "creative" });
      return;
    }
    setBusy(true);
    if (cloneRefine) {
      setItems((it) => [...it, { kind: "user", text: `Tinh chỉnh: ${t}` }]);
      send({ type: "answer", value: { action: "refine", feedback: t } });
      return;
    }
    send({ type: "chat", text: t });
  };

  const submitClone = (a: Answer) => {
    // Clone is chosen only now, with the form already filled: until then the switch stays reversible.
    pendingClone.current = a;
    setItems((it) => [...it, { kind: "user", text: a.label }]);
    setBusy(true);
    send({ type: "answer", value: "clone" });
  };

  const chooseMode = (m: "creative" | "clone") => {
    setMode(m);
    try {
      localStorage.setItem(MODE_KEY, m);
    } catch {}
  };

  const changeMode = () => {
    const other = cloneMode ? "creative" : "clone";
    const label = other === "clone" ? "Clone (dựng lại từ một trang có sẵn)" : "Creative (dựng từ ý tưởng)";
    if (stepIdx > 0 && !window.confirm(`Chuyển sang ${label}? Phiên hiện tại sẽ dừng lại và bắt đầu phiên mới.`)) return;
    chooseMode(other);
    restart();
  };

  const restart = () => {
    try {
      localStorage.removeItem("chromaswarm-session");
    } catch {}
    location.reload();
  };

  const building = !!snap && !question && (snap.running || snap.finished) && stepIdx >= steps.findIndex((s) => s.id === "B8");
  const lastQuestionIdx = items.map((i) => i.kind).lastIndexOf("question");

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      <SidePanel open={panelOpen} onClose={() => setPanelOpen(false)} snap={snap} status={status} stepIdx={stepIdx} onRestart={restart}
        steps={steps} clone={cloneView} />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className={`flex h-14 shrink-0 items-center gap-3 border-b border-line px-4 ${empty ? "md:hidden" : ""}`}>
          <button type="button" onClick={() => setPanelOpen(true)} aria-label="Mở bảng tiến độ" data-swarm-id="open-panel"
            data-swarm-role="button" className="grid size-10 place-items-center rounded-lg hover:bg-surface md:hidden">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden><path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
          {empty ? (
            <span className="font-semibold">ChromaSwarm</span>
          ) : (
            <button type="button" onClick={changeMode} data-swarm-id="change-mode" data-swarm-role="button"
              className="flex h-10 items-center gap-2 rounded-lg px-2 text-sm text-fg-2 transition-colors duration-200 hover:bg-surface hover:text-fg">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="M10 3.5 5.5 8l4.5 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              Đổi sang {cloneMode ? "Creative" : "Clone"}
            </button>
          )}
          {!empty && (
            <span className="rounded-full border border-line px-3 py-1 text-xs text-fg-2">
              {cloneMode ? "Clone · từ trang có sẵn" : "Creative · từ ý tưởng"}
            </span>
          )}
          <span className="ml-auto truncate text-xs text-fg-2">Bước {stepIdx + 1} · {steps[stepIdx]?.label}</span>
        </header>

        {empty ? (
          <EmptyState mode={mode} setMode={chooseMode} status={status}>
            <div className="stack-cell">
              <div data-hidden={mode !== "creative"} aria-hidden={mode !== "creative"} className="flex flex-col gap-4">
                <Composer value={draft} onChange={setDraft} onSubmit={() => submit(draft)} disabled={status !== "open" || mode !== "creative"}
                  busy={busy} big placeholder="Ví dụ: Landing page bán gốm thủ công, phong cách ấm áp, khách 25–40 tuổi, muốn họ bấm Đặt hàng" />
                <p className="px-2 text-xs text-fg-3">Gợi ý — bấm để thử ngay:</p>
                <ul className="grid gap-3 sm:grid-cols-2" aria-label="Gợi ý">
                  {EXAMPLES.map((e) => (
                    <li key={e.text}>
                      <button type="button" tabIndex={mode === "creative" ? 0 : -1} disabled={busy || status !== "open"} onClick={() => submit(e.text)}
                        data-swarm-role="button"
                        className="group flex h-full w-full flex-col gap-2 rounded-2xl border border-line bg-elevated p-4 text-left shadow-card transition-[transform,box-shadow,border-color] duration-300 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-float disabled:opacity-50">
                        <span className="self-start rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">{e.tag}</span>
                        <span className="text-sm leading-relaxed text-fg-2 group-hover:text-fg">{e.text}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              {/* self-start: the card keeps its own height instead of stretching to the taller Creative panel */}
              <div data-hidden={mode !== "clone"} aria-hidden={mode !== "clone"}
                className="self-start rounded-3xl border border-line bg-elevated p-6 shadow-card">
                {/* inert while hidden: its fields must not take focus behind the Creative panel */}
                <fieldset disabled={mode !== "clone"} className="contents">
                  <CloneSource busy={busy || status !== "open"} onAnswer={submitClone} />
                </fieldset>
              </div>
            </div>
          </EmptyState>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto" data-swarm-section="conversation">
              <ol className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8" aria-label="Hội thoại với Chroma">
                {items.map((it, i) =>
                  it.kind === "user" ? (
                    <li key={i} className="msg-in max-w-[85%] self-end whitespace-pre-wrap rounded-3xl bg-surface px-5 py-3 leading-relaxed">
                      {it.text}
                    </li>
                  ) : it.kind === "assistant" ? (
                    <Assistant key={i}>
                      <p className={`whitespace-pre-wrap leading-relaxed ${it.tone === "error" ? "text-danger" : "text-fg"}`}
                        role={it.tone === "error" ? "alert" : undefined}>{it.text}</p>
                    </Assistant>
                  ) : it.kind === "motion" ? (
                    <Assistant key={i}><MotionCard report={it.report} /></Assistant>
                  ) : i === lastQuestionIdx && question && it.sig === sigOf(snap!) ? (
                    <Assistant key={i}>
                      {question.kind === "handover" && <BuildPanel state={snap!.state} notice={null} running={false} />}
                      <QuestionCard key={it.sig} question={question} notice={it.note} state={snap!.state}
                        busy={busy || status !== "open"} onAnswer={answer} chatMode={chatOpen} />
                    </Assistant>
                  ) : (
                    <Assistant key={i}>
                      {it.note && <p className="mb-2 text-sm text-fg-2">{it.note}</p>}
                      <p className="whitespace-pre-line leading-relaxed text-fg-2">{it.q.text}</p>
                    </Assistant>
                  ),
                )}
                {building && (
                  <Assistant>
                    <BuildPanel state={snap!.state} notice={snap!.notice} running={snap!.running} />
                  </Assistant>
                )}
                {busy && (
                  <Assistant>
                    <span className="typing" aria-label="Chroma đang trả lời"><i /><i /><i /></span>
                  </Assistant>
                )}
                {status === "closed" && (
                  <Assistant>
                    <p role="alert" className="text-danger">Mất kết nối tới backend (cổng 8100). Hãy chạy backend rồi tải lại trang.</p>
                  </Assistant>
                )}
              </ol>
              <div ref={endRef} />
            </div>
            <div className="shrink-0 px-4 pb-4 pt-2">
              <div className="mx-auto w-full max-w-3xl">
                <Composer value={draft} onChange={setDraft} onSubmit={() => submit(draft)} disabled={!chatOpen} busy={busy}
                  placeholder={cloneRefine ? "Ghi góp ý để tinh chỉnh trang này (vd: tông tối hơn, khoảng cách gọn hơn)…"
                    : cloneMode ? "Clone mode: điền form trong hội thoại ở trên" : "Trả lời Chroma, hỏi lại (vd: “Bento là gì?”) hoặc đổi ý…"} />
                <p className="mt-2 text-center text-xs text-fg-3">Chroma chỉ dựng sau khi bạn duyệt kế hoạch ở bước B7.</p>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

/** B2 effect check: what Playwright found by operating the reference page, and how each effect moves. */
function MotionCard({ report }: { report: MotionReport }) {
  const fmt = (p: Record<string, number | string>) =>
    Object.entries(p).map(([k, v]) => `${PARAM_LABEL[k] ?? k} ${v}${PARAM_UNIT[k] ?? ""}`).join(" · ");
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section="motion-report">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-sm font-medium">Kiểm tra hiệu ứng (Playwright)</h3>
        <span className={`font-mono text-xs ${report.has_motion ? "text-accent" : "text-fg-2"}`}>
          {report.has_motion ? `${report.items.length} hiệu ứng` : "Không có hiệu ứng"}
        </span>
      </div>
      <p className="text-sm text-fg-2">
        {report.error ? `Không chạy được: ${report.error}` :
          `Đã cuộn ${report.steps ?? 0} màn hình và rê chuột thật lên ${report.hovered ?? 0} phần tử trên trang mẫu.`}
      </p>
      {report.items.length > 0 && (
        <ul className="flex flex-col divide-y divide-line">
          {report.items.map((m, i) => (
            <li key={i} className="flex flex-col gap-1 py-2">
              <span className="flex items-baseline justify-between gap-4 text-sm">
                <span className="font-medium">{m.label}</span>
                <span className="font-mono text-xs text-fg-3">{m.section}</span>
              </span>
              <span className="text-sm text-fg-2">{m.how}</span>
              {Object.keys(m.params).length > 0 && <span className="font-mono text-xs text-fg-3">{fmt(m.params)}</span>}
            </li>
          ))}
        </ul>
      )}
      {(report.libs?.length ?? 0) > 0 && <p className="text-xs text-fg-2">Thư viện chuyển động: {report.libs!.join(", ")}</p>}
      {(report.unsupported?.length ?? 0) > 0 && (
        <p className="text-xs text-fg-2">Chưa dựng lại được bằng CSS: {report.unsupported!.join(", ")}</p>
      )}
    </div>
  );
}

const PARAM_LABEL: Record<string, string> = {
  duration_ms: "thời gian", easing: "easing", distance_px: "quãng", stagger_ms: "trễ thẻ", scale: "tỉ lệ",
  cycle_s: "một vòng", blur_px: "blur",
};
const PARAM_UNIT: Record<string, string> = { duration_ms: "ms", distance_px: "px", stagger_ms: "ms", cycle_s: "s", blur_px: "px", scale: "×" };

function Assistant({ children }: { children: React.ReactNode }) {
  return (
    <li className="msg-in flex gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border border-line text-accent" aria-hidden>
        <Logo size={16} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-3 pt-1">{children}</div>
    </li>
  );
}

function Composer({ value, onChange, onSubmit, disabled, busy, placeholder, big = false }: {
  value: string; onChange: (v: string) => void; onSubmit: () => void; disabled: boolean; busy: boolean;
  placeholder: string; big?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);
  const ready = !disabled && !busy && !!value.trim();
  return (
    <form className={`flex items-end gap-2 rounded-3xl border border-line bg-elevated shadow-card transition-[border-color,box-shadow] duration-200 focus-within:border-accent/50 focus-within:shadow-float ${big ? "p-3" : "p-2"}`}
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }} data-swarm-section="chat-bar">
      <label htmlFor={big ? "prompt-input" : "chat-input"} className="sr-only">Nhắn cho Chroma</label>
      <textarea id={big ? "prompt-input" : "chat-input"} ref={ref} rows={1} value={value} disabled={disabled} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); onSubmit(); }
        }}
        className={`max-h-[200px] flex-1 resize-none bg-transparent px-3 py-2 leading-relaxed outline-none placeholder:text-fg-3 disabled:cursor-not-allowed ${big ? "min-h-[88px] text-base" : "text-sm"}`}
        data-swarm-id="chat-input" data-swarm-role="input" />
      <button type="submit" disabled={!ready} aria-label="Gửi" data-swarm-id="chat-send" data-swarm-role="button"
        className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-accent-fg shadow-card transition-[background-color,opacity,transform] duration-200 hover:bg-accent-hover active:scale-95 disabled:bg-line-strong disabled:text-elevated disabled:shadow-none">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden><path d="M9 14V4m0 0L4.5 8.5M9 4l4.5 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
    </form>
  );
}

const TRUST = [
  { title: "Kiểm thử tự động", text: "4 bài QA trên 4 kích thước màn hình" },
  { title: "Chấm điểm thẩm mỹ", text: "So với chuẩn các trang mẫu hàng đầu" },
  { title: "Code thật, của bạn", text: "Next.js, chạy được và sửa tiếp được" },
];

function EmptyState({ mode, setMode, status, children }: {
  mode: "creative" | "clone"; setMode: (m: "creative" | "clone") => void; status: Status; children: React.ReactNode;
}) {
  return (
    // Anchored from the top (not centred): switching panels changes nothing above them.
    <div className="flex-1 overflow-y-auto px-4" data-swarm-section="welcome">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 pb-16 pt-[clamp(32px,10vh,112px)]">
        <div className="msg-in flex flex-col items-center gap-4 text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-elevated px-3 py-1 text-xs text-fg-2 shadow-card">
            <span className="size-1.5 rounded-full bg-accent" aria-hidden />
            Đội thiết kế AI · 12 bước · bạn duyệt trước khi dựng
          </span>
          <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
            Hôm nay bạn muốn làm <span className="text-accent">trang web</span> gì?
          </h1>
          <p className="max-w-[56ch] text-pretty text-lg leading-relaxed text-fg-2">
            Kể bằng lời thường. Chroma hiểu phong cách, màu và khách hàng của bạn, chỉ hỏi phần còn thiếu, rồi dựng trang thật để bạn xem ngay.
          </p>
        </div>

        <ModeSwitch mode={mode} setMode={setMode} />
        {children}

        <ul className="grid gap-4 border-t border-line pt-8 sm:grid-cols-3" aria-label="Cam kết">
          {TRUST.map((t) => (
            <li key={t.title} className="flex items-start gap-3">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent-soft text-accent" aria-hidden>
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none"><path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </span>
              <span className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">{t.title}</span>
                <span className="text-sm text-fg-2">{t.text}</span>
              </span>
            </li>
          ))}
        </ul>
        {status === "closed" && (
          <p role="alert" className="text-center text-sm text-danger">Không kết nối được tới backend (cổng 8100). Hãy chạy backend rồi tải lại trang.</p>
        )}
      </div>
    </div>
  );
}

/** Segmented control with a sliding thumb: the selection moves, the layout never does. */
function ModeSwitch({ mode, setMode }: { mode: "creative" | "clone"; setMode: (m: "creative" | "clone") => void }) {
  const opts = [
    { value: "creative" as const, label: "Creative", hint: "từ ý tưởng" },
    { value: "clone" as const, label: "Clone", hint: "từ trang có sẵn" },
  ];
  return (
    <div className="relative mx-auto grid w-full max-w-sm grid-cols-2 rounded-full border border-line bg-surface p-1 text-sm" role="radiogroup" aria-label="Chế độ">
      <span className="seg-thumb absolute inset-y-1 left-1 w-[calc(50%-4px)] rounded-full bg-elevated shadow-card" aria-hidden
        style={{ transform: mode === "clone" ? "translateX(100%)" : "translateX(0)" }} />
      {opts.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={mode === o.value} onClick={() => setMode(o.value)}
          data-swarm-id={`option-${o.value}`} data-swarm-role="button"
          className={`relative z-10 flex h-10 items-center justify-center gap-1.5 rounded-full transition-colors duration-200 ${mode === o.value ? "font-medium text-fg" : "text-fg-2 hover:text-fg"}`}>
          {o.label}<span className="hidden text-fg-3 sm:inline">· {o.hint}</span>
        </button>
      ))}
    </div>
  );
}

function SidePanel({ open, onClose, snap, status, stepIdx, onRestart, steps, clone }: {
  open: boolean; onClose: () => void; snap: Snapshot | null; status: Status; stepIdx: number; onRestart: () => void;
  steps: Step[]; clone: boolean;
}) {
  const STEPS = steps;
  const phases = [...new Set(STEPS.map((s) => s.phase))];
  const statusLabel = { open: "Đã kết nối", connecting: "Đang kết nối", closed: "Mất kết nối" }[status];
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-fg/30 md:hidden" onClick={onClose} aria-hidden />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col gap-6 overflow-y-auto border-r border-line bg-bg p-4 transition-transform duration-300 md:static md:translate-x-0 md:bg-surface/60 ${open ? "translate-x-0" : "-translate-x-full"}`}
        aria-label="Tiến độ" data-swarm-section="step-tracker">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 font-semibold text-accent"><Logo size={20} /><span className="text-fg">ChromaSwarm</span></span>
          <button type="button" onClick={onClose} aria-label="Đóng bảng tiến độ" className="grid size-9 place-items-center rounded-lg hover:bg-surface md:hidden">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
        </div>
        <button type="button" onClick={onRestart} data-swarm-id="restart-session" data-swarm-role="button"
          className="flex h-11 items-center gap-2 rounded-xl border border-line px-3 text-sm transition-colors duration-200 hover:bg-surface">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          Phiên mới
        </button>
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs text-fg-2"><span>Tiến độ dự án</span><span className="font-mono">{stepIdx + 1}/{STEPS.length}</span></div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface" role="progressbar" aria-label="Tiến độ 12 bước"
            aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={stepIdx + 1}>
            <div className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out" style={{ width: `${((stepIdx + 1) / STEPS.length) * 100}%` }} />
          </div>
        </div>
        <nav aria-label="Các bước" className="flex flex-col gap-3">
          {phases.map((phase) => (
            <div key={phase} className="flex flex-col">
              <p className="px-2 pb-1 text-xs font-medium text-fg-3">{phase}</p>
              <ol className="flex flex-col">
                {STEPS.filter((s) => s.phase === phase).map((s) => {
                  const i = STEPS.indexOf(s);
                  const state = i < stepIdx ? "done" : i === stepIdx ? "current" : "todo";
                  return (
                    <li key={s.id} aria-current={state === "current" ? "step" : undefined}
                      className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${state === "current" ? "bg-surface font-medium text-fg" : state === "done" ? "text-fg-2" : "text-fg-3"}`}>
                      <span className="grid size-4 shrink-0 place-items-center" aria-hidden>
                        {state === "done" ? (
                          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="text-accent"><path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                        ) : state === "current" ? <span className="dot-live size-2 rounded-full bg-accent" /> : <span className="size-1.5 rounded-full bg-line" />}
                      </span>
                      <span className="w-5 text-right font-mono text-[11px] tabular-nums">{i + 1}</span>
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate">{s.label}</span>
                        {s.subs && state !== "todo" && (
                          <span className="flex flex-col gap-0.5 pt-1">
                            {s.subs.map((sub) => (
                              <span key={sub} className="text-xs font-normal leading-snug text-fg-2">· {sub}</span>
                            ))}
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </nav>
        {snap && snap.missing.length > 0 && (
          <div className="flex flex-col gap-2 rounded-xl border border-line p-3">
            <p className="text-xs font-medium">Việc tiếp theo</p>
            <ul className="flex flex-col gap-1 text-xs text-fg-2">
              {snap.missing.slice(0, 5).map((m) => (
                <li key={m} className="flex items-start gap-2"><span className="mt-1.5 size-1 shrink-0 rounded-full bg-fg-3" aria-hidden />{needLabel(m, clone)}</li>
              ))}
            </ul>
            <p className="text-xs text-fg-3">Đã rõ {Math.round(snap.clarity_score * 100)}% yêu cầu thiết kế</p>
          </div>
        )}
        <p className="mt-auto flex items-center gap-2 text-xs text-fg-2" role="status">
          <span className={`size-2 rounded-full ${status === "open" ? "dot-live bg-accent" : status === "closed" ? "bg-danger" : "bg-fg-3"}`} />
          {statusLabel}
        </p>
      </aside>
    </>
  );
}

function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="m12 2 9 5v10l-9 5-9-5V7l9-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m3 7 9 5 9-5M12 12v10" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}
