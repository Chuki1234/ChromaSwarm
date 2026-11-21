"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BuildPanel } from "@/components/build-panel";
import { loadThread, savedThread, saveThread, STATUS, useCloneSessions, type Saved } from "@/components/clone-history";
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
    analysis?: string | null;
    brief?: string | null;
    spec?: CloneSpec | null;
    sketch?: SketchResult | null;
    sketch_built?: SketchResult | null;
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
  section_reviews?: Record<string, { name: string; files: string[]; ok: boolean; score: number; issues: string[]; fixed: number; tries: number; first_score: number }>;
  page_routes: Record<string, string>;
  motion_effects: string[];
  handover_closed: boolean;
};

/** clone/sketch.py: B2 reading coverage (reference | sketch) or B10 sketch match (reference sketch | rebuild sketch). */
export type SketchResult = {
  coverage?: number; coverage_before?: number; gaps?: number; remeasured?: number; score?: number;
  sections?: Record<string, number>; pairs?: string[]; error?: string;
  pixel_score?: number; shot_pairs?: string[];
  described?: { x: number; y: number; w: number; h: number; added: number; seen: { kind: string; count: number; note: string } | null }[];
};

/** clone/spec.py: what the rebuild copies / replaces / skips, item by item; the user changes it at B7. */
export type CloneSpec = {
  items: { id: string; kind: string; section: string | null; action: string; why: string; replace_with: string; data: Record<string, unknown> }[];
  goal: string | null;
  overrides: Record<string, string>;
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
  // live = a progress notice while Chroma works (no question waiting): shown inside that step's activity block.
  | { kind: "assistant"; text: string; tone?: "error"; step?: string; live?: boolean; at?: number }
  | { kind: "question"; sig: string; q: Question; note: string | null }
  | { kind: "motion"; report: MotionReport }
  | { kind: "analysis"; text: string }
  | { kind: "brief"; text: string }
  | { kind: "sketch"; stage: "read" | "built"; result: SketchResult };

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

const PROGRESS_KEY = "chromaswarm-progress"; // the steps panel stays as the user left it (wide screens)
const wide = () => typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;
function savedProgress(): boolean {
  try {
    return wide() && localStorage.getItem(PROGRESS_KEY) !== "closed";
  } catch {
    return wide();
  }
}

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
  const [panelOpen, setPanelOpen] = useState(false); // history drawer (phones)
  const [progressOpen, setProgressOpen] = useState(false); // steps panel: beside the thread on wide screens, a drawer below
  const sessions = useCloneSessions();
  const wsRef = useRef<WebSocket | null>(null);
  const lastSig = useRef("");
  const lastNote = useRef<string | null>(null);
  const motionShown = useRef(false); // the B2 effect-check report goes into the thread once
  const threadRestored = useRef(false); // Clone: the saved conversation is loaded once per page load
  const analysisShown = useRef(false); // and the top-down analysis
  const briefShown = useRef(false); // and the build team's preparation sheet (CLONE_BRIEF.md)
  const sketchShown = useRef({ read: false, built: false }); // and the sketches (B2 reading, B10 rebuild)
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
      setProgressOpen(savedProgress());
    };
    ws.onclose = () => setStatus("closed");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") {
        const s = msg as Snapshot;
        setSnap(s);
        if (!threadRestored.current) {
          // First state after (re)connecting: a Clone session opened again gets its saved conversation back.
          threadRestored.current = true;
          if (s.state?.mode === "clone" && s.state.step !== "B1") {
            const sid = s.state.session_id;
            const local = loadThread(sid) as Item[];  // this browser's copy first: instant, works without Supabase
            if (local.length) {
              setItems((it) => [...local, ...it]);
              motionShown.current = local.some((x) => x.kind === "motion");
              analysisShown.current = local.some((x) => x.kind === "analysis");
              briefShown.current = local.some((x) => x.kind === "brief");
              sketchShown.current = { read: local.some((x) => x.kind === "sketch" && x.stage === "read"),
                                      built: local.some((x) => x.kind === "sketch" && x.stage === "built") };
            } else {
              savedThread(sid).then((rows) => {
                const restored: Item[] = rows.length
                  ? rows.map((r) => (r.role === "user" ? { kind: "user", text: r.text } : { kind: "assistant", text: r.text, step: r.step ?? undefined, live: true }))
                  : s.state.clone?.url ? [{ kind: "user", text: s.state.clone.url }] : [];  // at least the link sent
                if (restored.length) setItems((it) => [...restored, ...it]);
              });
            }
          }
        }
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
          const live = s.running || !s.question;
          setItems((it) => [...it, { kind: "assistant", text: s.notice!, step: s.state.step, live, at: Date.now() }]);
        }
        const mr = s.state?.clone?.motion_report;
        if (mr && !motionShown.current) {
          motionShown.current = true;
          setItems((it) => [...it, { kind: "motion", report: mr }]);
        }
        const an = s.state?.clone?.analysis;
        if (an && !analysisShown.current) {
          analysisShown.current = true;
          setItems((it) => [...it, { kind: "analysis", text: an }]);
        }
        for (const stage of ["read", "built"] as const) {
          const sk = stage === "read" ? s.state?.clone?.sketch : s.state?.clone?.sketch_built;
          if (sk && !sk.error && !sketchShown.current[stage]) {
            sketchShown.current[stage] = true;
            setItems((it) => [...it, { kind: "sketch", stage, result: sk }]);
          }
        }
        const br = s.state?.clone?.brief;
        if (br && !briefShown.current) {
          briefShown.current = true;
          setItems((it) => [...it, { kind: "brief", text: br }]);
        } else if (br) {  // the spec changed at B7: the sheet in the thread shows the new version
          setItems((it) => it.map((x) => (x.kind === "brief" && x.text !== br ? { ...x, text: br } : x)));
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
    if (!panelOpen && !progressOpen) return;
    const close = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setPanelOpen(false);
      if (!wide()) setProgressOpen(false); // on a wide screen the panel is part of the layout, not an overlay
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [panelOpen, progressOpen]);

  const toggleProgress = () => {
    const next = !progressOpen;
    setProgressOpen(next);
    if (wide()) {
      try {
        localStorage.setItem(PROGRESS_KEY, next ? "open" : "closed");
      } catch {}
    }
  };

  // Keep a Clone session's conversation in this browser, so a refresh shows it again (clone-history.tsx).
  useEffect(() => {
    if (snap?.state.mode === "clone" && items.length) saveThread(snap.state.session_id, items);
  }, [items, snap?.state.mode, snap?.state.session_id]);

  const question = snap?.question ?? null;
  const step = snap?.state.step ?? "B1";
  // A Clone session past B1 (its link sent, Chroma reading or building) is never the empty screen, even before
  // its conversation is back after a refresh.
  const clonePastLink = snap?.state.mode === "clone" && snap.state.step !== "B1";
  const empty = items.length === 0 && (!question || question.kind === "mode") && !clonePastLink;
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

  // Clone history (Supabase): open a saved session in place of the current one.
  const openSession = (id: string) => {
    try {
      localStorage.setItem("chromaswarm-session", id);
    } catch {}
    location.reload();
  };

  const restart = () => {
    try {
      localStorage.removeItem("chromaswarm-session");
    } catch {}
    location.reload();
  };

  const building = !!snap && !question && (snap.running || snap.finished) && stepIdx >= steps.findIndex((s) => s.id === "B8");
  const lastQuestionIdx = items.map((i) => i.kind).lastIndexOf("question");

  // Chroma's progress notices, grouped per step into activity blocks (like a chatbot's "thinking" trace).
  type Block = { kind: "item"; it: Item; i: number } | { kind: "activity"; step: string; notes: { text: string; at?: number }[]; i: number };
  const blocks: Block[] = [];
  items.forEach((it, i) => {
    if (it.kind === "assistant" && it.live && !it.tone) {
      const last = blocks[blocks.length - 1];
      const note = { text: it.text, at: it.at };
      if (last?.kind === "activity" && last.step === (it.step ?? "")) last.notes.push(note);
      else blocks.push({ kind: "activity", step: it.step ?? "", notes: [note], i });
    } else blocks.push({ kind: "item", it, i });
  });
  const working = !!snap?.running && !question;
  const lastBlock = blocks[blocks.length - 1];
  const activeActivity = working && lastBlock?.kind === "activity" ? lastBlock.i : -1;
  const stepLabel = (id: string) => {
    const k = steps.findIndex((s) => s.id === id);
    return k < 0 ? null : { n: k + 1, label: steps[k].label };
  };

  const clone = snap?.state.clone;
  const firstUser = items.find((it) => it.kind === "user") as { text: string } | undefined;
  const current = {
    id: snap?.state.session_id ?? "",
    title: clone?.title || hostOf(clone?.url) || firstUser?.text || "Cuộc trò chuyện mới",
    sub: empty ? "Chưa bắt đầu" : `${cloneMode ? "Clone" : "Creative"} · Bước ${stepIdx + 1}/${steps.length}`,
  };

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      <HistorySidebar open={panelOpen} onClose={() => setPanelOpen(false)} status={status} onRestart={restart} onOpen={openSession}
        current={current} sessions={sessions} />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className={`flex h-14 shrink-0 items-center gap-2 border-b border-line px-2 sm:gap-3 sm:px-4 ${empty ? "md:hidden" : ""}`}>
          <button type="button" onClick={() => setPanelOpen(true)} aria-label="Mở lịch sử phiên" data-swarm-id="open-panel"
            data-swarm-role="button" className="grid size-10 place-items-center rounded-lg hover:bg-surface md:hidden">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden><path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
          {empty ? (
            <span className="font-semibold">ChromaSwarm</span>
          ) : (
            <button type="button" onClick={changeMode} data-swarm-id="change-mode" data-swarm-role="button"
              className="flex h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-2 text-sm text-fg-2 transition-colors duration-200 hover:bg-surface hover:text-fg">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="M10 3.5 5.5 8l4.5 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
              Đổi sang {cloneMode ? "Creative" : "Clone"}
            </button>
          )}
          {!empty && (
            <span className="hidden whitespace-nowrap rounded-full border border-line px-3 py-1 text-xs text-fg-2 sm:inline">
              {cloneMode ? "Clone · từ trang có sẵn" : "Creative · từ ý tưởng"}
            </span>
          )}
          {!empty && (
            <button type="button" onClick={toggleProgress} aria-pressed={progressOpen} aria-controls="progress-panel"
              data-swarm-id="toggle-progress" data-swarm-role="button"
              className={`ml-auto flex h-10 min-w-0 items-center gap-2 rounded-lg border px-3 text-sm transition-colors duration-200 ${progressOpen ? "border-line-strong bg-surface text-fg" : "border-line text-fg-2 hover:bg-surface hover:text-fg"}`}>
              {working ? <span className="dot-live size-2 shrink-0 rounded-full bg-accent" aria-hidden />
                : <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className="shrink-0"><path d="M3 4h10M3 8h7M3 12h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>}
              <span className="hidden truncate sm:inline">{steps[stepIdx]?.label}</span>
              <span className="font-mono text-xs tabular-nums text-fg-2">{stepIdx + 1}/{steps.length}</span>
              <span className="sr-only">Tiến trình</span>
            </button>
          )}
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
                {blocks.map((b) => {
                  if (b.kind === "activity") {
                    const sl = stepLabel(b.step);
                    // A step lasts until the next step's first update (a one-update step still gets its time).
                    const next = blocks.find((x) => x.kind === "activity" && x.i > b.i) as { notes: { at?: number }[] } | undefined;
                    return (
                      <ActivityBlock key={`a${b.i}`} active={b.i === activeActivity} notes={b.notes} until={next?.notes[0]?.at}
                        title={sl ? sl.label : "Hoạt động của Chroma"} stepNo={sl?.n ?? null} />
                    );
                  }
                  const { it, i } = b;
                  return it.kind === "user" ? (
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
                  ) : it.kind === "analysis" ? (
                    <Assistant key={i}>
                      <details className="rounded-xl border border-line p-4" data-swarm-section="analysis">
                        <summary className="cursor-pointer text-sm font-medium" data-swarm-id="toggle-analysis" data-swarm-role="button">
                          Phân tích trang mẫu: tổng quan, rồi từng phần từ trên xuống
                        </summary>
                        <pre className="mt-3 max-h-[480px] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-fg-2">{it.text}</pre>
                      </details>
                    </Assistant>
                  ) : it.kind === "sketch" ? (
                    <Assistant key={i}><SketchCard stage={it.stage} result={it.result} session={snap?.state.session_id ?? ""} /></Assistant>
                  ) : it.kind === "brief" ? (
                    <Assistant key={i}>
                      <details className="rounded-xl border border-line p-4" data-swarm-section="clone-brief">
                        <summary className="cursor-pointer text-sm font-medium" data-swarm-id="toggle-brief" data-swarm-role="button">
                          Tài liệu chuẩn bị cho đội thi công: concept, section, khoảng cách, hình, nút, hiệu ứng, clone được gì
                        </summary>
                        <pre className="mt-3 max-h-[560px] overflow-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-fg-2">{it.text}</pre>
                      </details>
                      {question?.kind === "approval" && snap?.state.clone?.spec && (
                        <SpecSections spec={snap.state.clone.spec} busy={busy || status !== "open"}
                          onChange={(id, name, build) => answer({ label: `${build ? "Dựng" : "Không dựng"}: ${name}`, value: { spec: { [id]: build ? "copy" : "skip" } } })} />
                      )}
                    </Assistant>
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
                  );
                })}
                {building && (
                  <Assistant>
                    <BuildPanel state={snap!.state} notice={snap!.notice} running={snap!.running} />
                  </Assistant>
                )}
                {(busy || (working && !building)) && activeActivity < 0 && (
                  // Waiting for Chroma: a live line naming what it is on (a chatbot's "thinking…"), not bare dots.
                  <ActivityBlock key={`wait-${step}`} active notes={[]} title={steps[stepIdx]?.label ?? "Suy nghĩ"} stepNo={null} />
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

      {progressOpen && !empty && (
        <ProgressPanel onClose={() => setProgressOpen(false)} snap={snap} stepIdx={stepIdx} steps={steps} clone={cloneView} working={working} />
      )}
    </div>
  );
}

const hostOf = (url?: string | null) => {
  if (!url) return null;
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
};

const fmtDur = (ms: number) => {
  const sec = Math.max(1, Math.round(ms / 1000));
  return sec < 60 ? `${sec} giây` : `${Math.floor(sec / 60)} phút${sec % 60 ? ` ${sec % 60} giây` : ""}`;
};

/** One step of Chroma's work, as a chatbot shows its reasoning: open with a live label while the step runs,
 * folded to one line ("Bước 2 · … · 4 cập nhật · 38 giây") once it is done; the user can open or fold it. */
function ActivityBlock({ title, stepNo, notes, active, until }: {
  title: string; stepNo: number | null; notes: { text: string; at?: number }[]; active: boolean; until?: number;
}) {
  const [manual, setManual] = useState<boolean | null>(null); // null = follow the step (open while it runs)
  const open = manual ?? active;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  const first = notes[0]?.at;
  const last = notes[notes.length - 1]?.at;
  const span = first ? (active ? now : until ?? last ?? first) - first : 0;
  const meta = notes.length ? [`${notes.length} cập nhật`, span >= 1000 ? fmtDur(span) : null].filter(Boolean).join(" · ") : "";
  const lower = title.charAt(0).toLowerCase() + title.slice(1);
  return (
    <li className="msg-in flex gap-3" data-swarm-section="activity">
      <span className="mt-1.5 grid size-8 shrink-0 place-items-center text-fg-3" aria-hidden>
        {active ? (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="spin text-accent"><circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.8" /><path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-accent"><path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
        )}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <button type="button" aria-expanded={notes.length ? open : undefined} disabled={!notes.length} onClick={() => setManual(!open)}
          data-swarm-role="button" aria-live={active ? "polite" : undefined}
          className="-mx-2 flex min-h-11 items-center gap-2 rounded-lg px-2 text-left text-sm transition-colors duration-200 enabled:hover:bg-surface disabled:cursor-default">
          <span className={`min-w-0 truncate ${active ? "shimmer font-medium" : "text-fg-2"}`}>
            {active ? `Đang ${lower}…` : stepNo ? `Bước ${stepNo} · ${title}` : title}
          </span>
          <span className="shrink-0 font-mono text-xs tabular-nums text-fg-3">{meta}</span>
          {notes.length > 0 && <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden className="chev ml-auto shrink-0 text-fg-3"><path d="m6 4 4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>}
        </button>
        {open && notes.length > 0 && (
          <ol className="ml-1 mt-1 flex flex-col gap-2 border-l border-line pb-1 pl-4" aria-label={`Chi tiết: ${title}`}>
            {notes.map((n, k) => (
              <li key={k} className={`whitespace-pre-wrap text-sm leading-relaxed ${active && k === notes.length - 1 ? "text-fg" : "text-fg-2"}`}>
                {n.text}
              </li>
            ))}
          </ol>
        )}
      </div>
    </li>
  );
}

const BACKEND_HTTP = BACKEND_WS.replace(/^ws/, "http");

/** Clone sketch step: screen by screen, the reference next to what Chroma read (B2), or the reference's sketch
 * next to the rebuild's (B10). A red frame = a reading gap ("đọc thiếu" / "đã đo lại"). */
function SketchCard({ stage, result, session }: { stage: "read" | "built"; result: SketchResult; session: string }) {
  const shot = (name: string) => `${BACKEND_HTTP}/sessions/${encodeURIComponent(session)}/sketch/${name}`;
  const pairs = [...(result.shot_pairs ?? []), ...(result.pairs ?? [])];
  const named = (result.described ?? []).filter((d) => d.seen);
  const low = Object.entries(result.sections ?? {}).sort((a, b) => a[1] - b[1]).slice(0, 3);
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section={`sketch-${stage}`}>
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-sm font-medium">{stage === "read" ? "Sketch: trang mẫu vẽ lại từ những gì Chroma đọc được" : "Sketch bản dựng so với trang mẫu"}</h3>
        <span className="font-mono text-xs text-accent">
          {stage === "read" ? `đọc được ${result.coverage}%` : `sketch ${result.score}%` + (result.pixel_score != null ? ` · ảnh ${result.pixel_score}%` : "")}
        </span>
      </div>
      <p className="text-sm text-fg-2">
        {stage === "read"
          ? (result.gaps ? `Lần đầu phủ ${result.coverage_before}% trang; ${result.gaps} chỗ đọc thiếu (khung đỏ) được đo lại khi dừng animation, thêm ${result.remeasured} phần.` : "Không thấy chỗ nào đọc thiếu.")
          : `Wireframe của bản dựng trước khi tô màu: ảnh chụp so với ảnh chụp trang mẫu (khung đỏ = thiếu), rồi sketch so với sketch.${low.length ? " Thấp nhất: " + low.map(([k, v]) => `${k} ${v}%`).join(", ") + "." : ""}`}
      </p>
      {named.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs text-fg-2">
          {named.map((d, k) => (
            <li key={k}>Mô hình thị giác ở ({d.x}, {d.y}) {d.w}×{d.h}: {d.seen!.count} × {d.seen!.kind}{d.seen!.note ? ` — ${d.seen!.note}` : ""}</li>
          ))}
        </ul>
      )}
      <ul className="flex snap-x gap-3 overflow-x-auto pb-2" aria-label="Từng màn hình">
        {pairs.map((name, k) => (
          <li key={name} className="shrink-0 snap-start">
            <a href={shot(name)} target="_blank" rel="noreferrer" className="block rounded-lg border border-line hover:border-line-strong">
              {/* eslint-disable-next-line @next/next/no-img-element -- backend-served screenshots, not app assets */}
              <img src={shot(name)} alt={`Màn hình ${k + 1}`} width={580} height={180} loading="lazy" className="h-[180px] w-auto rounded-lg" />
            </a>
            <span className="mt-1 block text-xs text-fg-3">Màn hình {k + 1}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** B7 (Clone): the CloneSpec's sections — untick one and it is not built (the plan and the brief follow). */
function SpecSections({ spec, busy, onChange }: {
  spec: CloneSpec; busy: boolean; onChange: (id: string, name: string, build: boolean) => void;
}) {
  const sections = spec.items.filter((i) => i.kind === "section");
  const counts = spec.items.reduce<Record<string, number>>((n, i) => {
    const a = spec.overrides[i.id] ?? i.action;
    n[a] = (n[a] ?? 0) + 1;
    return n;
  }, {});
  return (
    <fieldset className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section="clone-spec" disabled={busy}>
      <legend className="px-1 text-sm font-medium">Dựng những phần nào?</legend>
      <p className="text-xs text-fg-2">
        {counts.copy ?? 0} mục dựng giống · {counts.replace ?? 0} thay bằng của bạn · {counts.skip ?? 0} không dựng · {counts.todo ?? 0} chưa tự động.
        Bỏ chọn một phần để không dựng nó.
      </p>
      <ul className="grid gap-1 sm:grid-cols-2">
        {sections.map((s) => {
          const build = (spec.overrides[s.id] ?? s.action) !== "skip";
          const name = String(s.data.name ?? s.section);
          return (
            <li key={s.id}>
              <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-2 text-sm hover:bg-surface">
                <input type="checkbox" checked={build} onChange={(e) => onChange(s.id, name, e.target.checked)}
                  className="size-4 accent-[var(--accent)]" data-swarm-id={`spec-${s.section}`} data-swarm-role="input" />
                <span className={build ? "" : "text-fg-3 line-through"}>{name}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </fieldset>
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

type Current = { id: string; title: string; sub: string };

/** Left column, as in a chatbot: new session, then the conversations — this one first, then saved Clone sessions. */
function HistorySidebar({ open, onClose, status, onRestart, onOpen, current, sessions }: {
  open: boolean; onClose: () => void; status: Status; onRestart: () => void; onOpen: (id: string) => void;
  current: Current; sessions: Saved[] | null;
}) {
  const statusLabel = { open: "Đã kết nối", connecting: "Đang kết nối", closed: "Mất kết nối" }[status];
  const others = (sessions ?? []).filter((s) => s.id !== current.id).slice(0, 30);
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-fg/30 md:hidden" onClick={onClose} aria-hidden />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col gap-4 border-r border-line bg-bg p-3 transition-transform duration-300 md:static md:w-64 md:translate-x-0 md:bg-surface/60 ${open ? "translate-x-0" : "-translate-x-full"}`}
        aria-label="Lịch sử phiên" data-swarm-section="history">
        <div className="flex h-10 items-center justify-between gap-2 px-2">
          <span className="flex items-center gap-2 font-semibold text-accent"><Logo size={20} /><span className="text-fg">ChromaSwarm</span></span>
          <button type="button" onClick={onClose} aria-label="Đóng lịch sử phiên" className="grid size-10 place-items-center rounded-lg hover:bg-surface md:hidden">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
        </div>
        <button type="button" onClick={onRestart} data-swarm-id="restart-session" data-swarm-role="button"
          className="flex h-11 items-center gap-2 rounded-xl border border-line bg-elevated px-3 text-sm shadow-card transition-colors duration-200 hover:border-line-strong">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          Phiên mới
        </button>
        <nav aria-label="Các phiên" className="-mx-1 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-1">
          <p className="px-2 pb-1 pt-2 text-xs font-medium text-fg-3">Đang mở</p>
          <div aria-current="page" className="flex flex-col gap-0.5 rounded-lg bg-surface px-3 py-2">
            <span className="truncate text-sm font-medium">{current.title}</span>
            <span className="truncate text-xs text-fg-2">{current.sub}</span>
          </div>
          <p className="px-2 pb-1 pt-4 text-xs font-medium text-fg-3">Phiên Clone đã lưu</p>
          {sessions === null ? (
            <p className="px-3 py-2 text-xs text-fg-3">Đang tải…</p>
          ) : others.length === 0 ? (
            <p className="px-3 py-2 text-xs leading-relaxed text-fg-3">Các phiên Clone được lưu tự động và hiện ở đây để mở lại.</p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {others.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => onOpen(s.id)} data-swarm-id={`open-session-${s.id}`} data-swarm-role="button"
                    title={s.url ?? undefined}
                    className="flex w-full flex-col gap-0.5 rounded-lg px-3 py-2 text-left transition-colors duration-200 hover:bg-surface">
                    <span className="truncate text-sm">{s.title || hostOf(s.url) || s.id}</span>
                    <span className="truncate text-xs text-fg-3">
                      {STATUS[s.status] ?? s.status}{s.fidelity != null && ` · giống ${Math.round(s.fidelity)}%`} · {ago(s.updated_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>
        <p className="flex items-center gap-2 px-2 text-xs text-fg-2" role="status">
          <span className={`size-2 rounded-full ${status === "open" ? "dot-live bg-accent" : status === "closed" ? "bg-danger" : "bg-fg-3"}`} />
          {statusLabel}
        </p>
      </aside>
    </>
  );
}

const ago = (iso: string) => {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "vừa xong";
  if (min < 60) return `${min} phút trước`;
  if (min < 60 * 24) return `${Math.round(min / 60)} giờ trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
};

/** Right column: where the session is in the 12 steps (toggled from the header; a drawer on narrow screens). */
function ProgressPanel({ onClose, snap, stepIdx, steps, clone, working }: {
  onClose: () => void; snap: Snapshot | null; stepIdx: number; steps: Step[]; clone: boolean; working: boolean;
}) {
  const STEPS = steps;
  const phases = [...new Set(STEPS.map((s) => s.phase))];
  return (
    <>
      <div className="fixed inset-0 z-30 bg-fg/30 lg:hidden" onClick={onClose} aria-hidden />
      <aside id="progress-panel" className="fixed inset-y-0 right-0 z-40 flex w-80 max-w-[88vw] flex-col gap-6 overflow-y-auto border-l border-line bg-bg p-4 lg:static lg:z-auto lg:max-w-none lg:bg-surface/40"
        aria-label="Tiến trình" data-swarm-section="step-tracker">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-medium">Tiến trình</h2>
          <button type="button" onClick={onClose} aria-label="Đóng tiến trình" data-swarm-id="close-progress" data-swarm-role="button"
            className="grid size-10 place-items-center rounded-lg hover:bg-surface">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden><path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-xs text-fg-2"><span>{working ? "Chroma đang làm việc" : "Tiến độ dự án"}</span><span className="font-mono">{stepIdx + 1}/{STEPS.length}</span></div>
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
                        {s.subs && state === "current" && (
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
