"use client";

import { useState } from "react";
import type { PipelineState } from "@/components/pipeline-console";

export type Option = { value: string; label: string; hint: string };
export type Question = {
  step: string;
  kind: "text" | "choice" | "mode" | "clone_source" | "assets" | "recommend_url" | "approval" | "info" | "handover";
  key: string;
  text: string;
  options: Option[];
  recommended: string | null;
  allow_free_text: boolean;
  note: string | null;
};
export type Answer = { value: unknown; label: string };

type Props = {
  question: Question;
  notice: string | null;
  state: PipelineState;
  busy: boolean;
  onAnswer: (a: Answer) => void;
  chatMode?: boolean; // Creative mode: free text goes through the chat bar instead of per-card inputs
};

const input =
  "w-full rounded-xl border border-line-strong bg-elevated px-4 py-3 text-sm outline-none transition-colors duration-200 placeholder:text-fg-3 focus-visible:border-accent";
const primaryBtn =
  "h-12 rounded-lg bg-accent px-6 text-sm font-medium text-accent-fg transition-[filter,transform] duration-200 hover:brightness-110 active:scale-[0.98] disabled:opacity-50";
const secondaryBtn =
  "h-12 rounded-lg border border-line px-6 text-sm font-medium text-fg-2 transition-colors duration-200 hover:border-fg-3 hover:text-fg active:scale-[0.98] disabled:opacity-50";

const PLACEHOLDERS: Record<string, string> = {
  raw_prompt: "Ví dụ: Mình muốn làm web bán đồ nội thất tối giản",
  scope: "Ví dụ: Người 30–45 tuổi, xem trên điện thoại; muốn họ bấm “Đặt lịch xem showroom”",
};

export function QuestionCard({ question: q, notice, state, busy, onAnswer, chatMode = false }: Props) {
  return (
    <div className="flex flex-col gap-6" data-swarm-section="question">
      {(notice || q.note) && (
        <p className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-fg-2">{notice || q.note}</p>
      )}
      <p className="max-w-[72ch] whitespace-pre-line text-lg leading-relaxed">{q.text}</p>
      {(q.kind === "choice" || q.kind === "mode") && <Choice q={q} busy={busy} onAnswer={onAnswer} hideFreeText={chatMode} />}
      {q.kind === "text" && !chatMode && <FreeText busy={busy} onAnswer={onAnswer} placeholder={PLACEHOLDERS[q.key]} />}
      {q.kind === "clone_source" && <CloneSource busy={busy} onAnswer={onAnswer} />}
      {q.kind === "recommend_url" && <RecommendUrl busy={busy} onAnswer={onAnswer} />}
      {q.kind === "assets" && <Assets busy={busy} onAnswer={onAnswer} />}
      {q.kind === "approval" && <Approval state={state} busy={busy} onAnswer={onAnswer} />}
      {q.kind === "handover" && <Handover q={q} state={state} busy={busy} onAnswer={onAnswer} />}
    </div>
  );
}

function Choice({ q, busy, onAnswer, hideFreeText = false }: { q: Question; busy: boolean; onAnswer: Props["onAnswer"]; hideFreeText?: boolean }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {q.options.map((o) => (
          <button
            key={o.value}
            type="button"
            disabled={busy}
            data-swarm-id={`option-${o.value}`}
            data-swarm-role="button"
            onClick={() => onAnswer({ value: o.value, label: o.label })}
            className="group flex flex-col items-start gap-1 rounded-2xl border border-line bg-elevated p-4 text-left shadow-card transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-accent/60 hover:shadow-float focus-visible:border-accent active:scale-[0.98] disabled:opacity-50"
          >
            <span className="flex items-center gap-2 text-sm font-medium">
              {o.label}
              {q.recommended === o.value && (
                <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent">
                  Nên làm trước
                </span>
              )}
            </span>
            {o.hint && <span className="text-xs text-fg-3">{o.hint}</span>}
          </button>
        ))}
      </div>
      {q.allow_free_text && !hideFreeText && <FreeText busy={busy} onAnswer={onAnswer} placeholder="Hoặc mô tả bằng lời của bạn…" />}
    </div>
  );
}

function FreeText({ busy, onAnswer, placeholder }: { busy: boolean; onAnswer: Props["onAnswer"]; placeholder?: string }) {
  const [text, setText] = useState("");
  return (
    <form
      className="flex flex-col gap-3 sm:flex-row"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) onAnswer({ value: text.trim(), label: text.trim() });
      }}
    >
      <label htmlFor="free-text" className="sr-only">
        Câu trả lời
      </label>
      <input
        id="free-text"
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder ?? "Ví dụ: Mình muốn làm web bán đồ nội thất tối giản"}
        data-swarm-id="free-text-input"
        data-swarm-role="input"
        className={`${input} h-12 flex-1 py-0`}
      />
      <button type="submit" disabled={busy || !text.trim()} data-swarm-id="send-answer" data-swarm-role="button" className={primaryBtn}>
        Gửi
      </button>
    </form>
  );
}

function RecommendUrl({ busy, onAnswer }: { busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [url, setUrl] = useState("");
  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <label htmlFor="ref-url" className="sr-only">
        Link trang tham khảo
      </label>
      <input id="ref-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" className={`${input} h-12 flex-1 py-0`} />
      <button type="button" disabled={busy || !url.trim()} onClick={() => onAnswer({ value: url.trim(), label: url.trim() })} className={primaryBtn}>
        Gửi link
      </button>
      <button type="button" disabled={busy} onClick={() => onAnswer({ value: "", label: "Không có link" })} className={secondaryBtn}>
        Không có link
      </button>
    </div>
  );
}

function Assets({ busy, onAnswer }: { busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [items, setItems] = useState("");
  const [shot, setShot] = useState("");
  const [url, setUrl] = useState("");
  const submit = () => {
    const assets = items
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => ({ kind: "other", path_or_text: l }));
    const references = shot.trim() || url.trim() ? [{ screenshot_path: shot.trim() || null, url: url.trim() || null }] : [];
    const parts = [assets.length ? `${assets.length} tài nguyên` : "chưa có tài nguyên", references.length ? "1 tham khảo" : ""];
    onAnswer({ value: { assets, references, done: true }, label: parts.filter(Boolean).join(", ") });
  };
  return (
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-2 text-sm">
        <span className="text-fg-2">Tài nguyên (mỗi dòng một mục: logo, ảnh, slogan, bảng giá…)</span>
        <textarea value={items} onChange={(e) => setItems(e.target.value)} rows={4} className={input} placeholder={"logo.svg\nSlogan: Nội thất gỗ sồi, làm thủ công tại Đà Lạt"} />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-fg-2">Ảnh chụp trang mẫu (tên file)</span>
          <input value={shot} onChange={(e) => setShot(e.target.value)} className={input} placeholder="reference.png" />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          <span className="text-fg-2">Link trang mẫu</span>
          <input value={url} onChange={(e) => setUrl(e.target.value)} className={input} placeholder="https://…" />
        </label>
      </div>
      <button type="button" disabled={busy} onClick={submit} data-swarm-id="assets-done" data-swarm-role="button" className={`${primaryBtn} self-start`}>
        Đã gửi đủ
      </button>
    </div>
  );
}

const DOCS = [
  { key: "design_md", label: "DESIGN.md" },
  { key: "product_md", label: "PRODUCT.md" },
  { key: "plan_md", label: "PLAN.md" },
] as const;

function Approval({ state, busy, onAnswer }: { state: PipelineState; busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [tab, setTab] = useState<(typeof DOCS)[number]["key"]>("design_md");
  const [feedback, setFeedback] = useState("");
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" className="flex gap-1 border-b border-line">
        {DOCS.map((d) => (
          <button
            key={d.key}
            role="tab"
            aria-selected={tab === d.key}
            onClick={() => setTab(d.key)}
            data-swarm-id={`doc-tab-${d.key}`}
            data-swarm-role="tab"
            className={`-mb-px border-b-2 px-4 py-2 font-mono text-xs transition-colors duration-200 ${
              tab === d.key ? "border-accent text-fg" : "border-transparent text-fg-3 hover:text-fg"
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>
      <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-surface p-6 font-mono text-xs leading-relaxed text-fg-2">
        {state[tab]}
      </pre>
      <label className="flex flex-col gap-2 text-sm">
        <span className="text-fg-2">Muốn đổi gì? (để trống nếu duyệt luôn)</span>
        <textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} rows={2} className={input} placeholder="Ví dụ: đổi màu chủ đạo sang xanh rêu, bớt chữ ở hero" />
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          disabled={busy}
          data-swarm-id="approve-plan"
          data-swarm-role="button"
          onClick={() => onAnswer({ value: { approve: true }, label: "Duyệt kế hoạch" })}
          className={primaryBtn}
        >
          Duyệt & bắt đầu dựng
        </button>
        <button
          type="button"
          disabled={busy || !feedback.trim()}
          data-swarm-id="request-changes"
          data-swarm-role="button"
          onClick={() => onAnswer({ value: { approve: false, feedback: feedback.trim() }, label: `Yêu cầu sửa: ${feedback.trim()}` })}
          className={secondaryBtn}
        >
          Yêu cầu chỉnh sửa
        </button>
      </div>
    </div>
  );
}

/** B12: the page is the user's now. Build the next sitemap page, refine this one, or finish. */
function Handover({ q, state, busy, onAnswer }: { q: Question; state: PipelineState; busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [feedback, setFeedback] = useState("");
  return (
    <div className="flex flex-col gap-6">
      {state.preview_url && (
        <a href={state.preview_url} target="_blank" rel="noreferrer" data-swarm-id="open-handover" data-swarm-role="link"
          className={`${primaryBtn} inline-flex items-center self-start`}>
          Mở trang để dùng thử ↗
        </a>
      )}
      {q.options.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Dựng trang tiếp theo (giữ nguyên DESIGN.md)</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {q.options.map((o) => (
              <button key={o.value} type="button" disabled={busy} data-swarm-id={`next-page-${o.value}`} data-swarm-role="button"
                onClick={() => onAnswer({ value: { action: "next", page: o.value }, label: `Dựng trang: ${o.label}` })}
                className="flex flex-col items-start gap-1 rounded-xl border border-line p-4 text-left transition-colors duration-200 hover:border-accent focus-visible:border-accent active:scale-[0.98] disabled:opacity-50">
                <span className="flex items-center gap-2 text-sm font-medium">
                  {o.label}
                  {q.recommended === o.value && (
                    <span className="rounded-sm bg-accent px-1.5 py-0.5 font-mono text-[11px] uppercase tracking-wider text-accent-fg">Nên làm tiếp</span>
                  )}
                </span>
                {o.hint && <span className="text-xs text-fg-3">{o.hint}</span>}
              </button>
            ))}
          </div>
        </div>
      )}
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-medium">Hoặc tinh chỉnh trang này</span>
        <textarea value={feedback} onChange={(e) => setFeedback(e.target.value)} rows={2} className={input}
          placeholder="Ví dụ: đổi sang tông tối, khoảng cách gọn hơn" data-swarm-id="refine-feedback" data-swarm-role="input" />
      </label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button type="button" disabled={busy || !feedback.trim()} data-swarm-id="refine-page" data-swarm-role="button"
          onClick={() => onAnswer({ value: { action: "refine", feedback: feedback.trim() }, label: `Tinh chỉnh: ${feedback.trim()}` })}
          className={secondaryBtn}>
          Tinh chỉnh (duyệt lại kế hoạch)
        </button>
        <button type="button" disabled={busy} data-swarm-id="finish-session" data-swarm-role="button"
          onClick={() => onAnswer({ value: { action: "finish" }, label: "Kết thúc" })} className={secondaryBtn}>
          Kết thúc
        </button>
      </div>
    </div>
  );
}

/** Clone mode, B1: link + a short description. Copying the page's own words and photos is an opt-in
 *  behind a small link (moving one's own site), never a question asked of everyone. */
export function CloneSource({ busy, onAnswer }: { busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [url, setUrl] = useState("");
  const [prompt, setPrompt] = useState("");
  const [owned, setOwned] = useState(false);
  const [showOwned, setShowOwned] = useState(false);
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onAnswer({ value: { url: url.trim(), prompt: prompt.trim(), owned }, label: `${url.trim()}${owned ? " (trang của tôi)" : ""}` });
      }}
    >
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-medium">Link trang muốn dựng lại</span>
        <input id="clone-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" required
          className={`${input} h-12 py-0`} data-swarm-id="clone-url" data-swarm-role="input" />
      </label>
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-medium">Mô tả trang web của bạn</span>
        <textarea id="clone-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} required className={input}
          placeholder="Ví dụ: Shop gốm thủ công Bát Tràng, khách 25–40 tuổi, muốn họ bấm “Nhắn tin đặt hàng”"
          data-swarm-id="clone-prompt" data-swarm-role="input" />
      </label>
      <p className="text-sm text-fg-2">
        Chroma dựng lại bố cục và phong cách của trang mẫu thành một template; bạn dán chữ và ảnh của mình vào.
      </p>
      {/* Rare case (moving one's own site to Next.js): kept out of the way, never asked of everyone. */}
      {!showOwned ? (
        <button type="button" onClick={() => setShowOwned(true)} data-swarm-id="clone-own-site" data-swarm-role="button"
          className="self-start text-sm text-fg-2 underline underline-offset-4 hover:text-fg">
          Chuyển trang của chính bạn sang Next.js?
        </button>
      ) : (
        <label className="flex items-start gap-3 rounded-lg border border-line p-4 text-sm">
          <input id="clone-owned" type="checkbox" checked={owned} onChange={(e) => setOwned(e.target.checked)}
            className="mt-1 size-4 accent-[var(--color-accent)]" data-swarm-id="clone-owned" data-swarm-role="input" />
          <span className="flex flex-col gap-1">
            <span className="font-medium">Đây là trang web của tôi — chép cả chữ và ảnh</span>
            <span className="text-fg-2">Chỉ dành cho trang bạn sở hữu hoặc được chủ trang cho phép. Chroma xác nhận lại tên trang sau khi đọc.</span>
          </span>
        </label>
      )}
      <button type="submit" disabled={busy || !url.trim() || prompt.trim().length < 12} data-swarm-id="clone-submit"
        data-swarm-role="button" className={`${primaryBtn} self-start`}>
        Đọc trang mẫu
      </button>
    </form>
  );
}
