"use client";

import { useEffect, useRef, useState } from "react";
import type { PipelineState } from "@/components/pipeline-console";
import { loadDraft, saveDraft } from "@/components/clone-history";

export type Option = { value: string; label: string; hint: string };
export type Question = {
  step: string;
  kind: "text" | "choice" | "mode" | "clone_source" | "assets" | "recommend_url" | "clone_content" | "approval" | "info" | "handover";
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
      {q.kind === "clone_content" && <CloneContent q={q} busy={busy} onAnswer={onAnswer} />}
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

const TEXT_FIELDS: { key: string; label: string; rows?: number; placeholder: string }[] = [
  { key: "name", label: "Tên của bạn / thương hiệu", placeholder: "Ví dụ: Minh Anh Studio" },
  { key: "headline", label: "Câu tiêu đề lớn ở đầu trang", placeholder: "Ví dụ: Thiết kế phần mềm phức tạp, giao diện gọn gàng" },
  { key: "intro", label: "Một hai câu giới thiệu", rows: 2, placeholder: "Ví dụ: 6 năm thiết kế sản phẩm B2B…" },
  { key: "projects", label: "Tên các dự án / sản phẩm (mỗi dòng một tên)", rows: 3, placeholder: "Cổng đặt tour B2B\nQuản lý đội tàu" },
  { key: "email", label: "Email liên hệ", placeholder: "ban@email.com" },
];

/** Downscale a photo to at most 2000px on its long side (JPEG), so the answer stays small. */
function toDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, 2000 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * k);
      c.height = Math.round(img.height * k);
      c.getContext("2d")!.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      resolve(c.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("not an image")); };
    img.src = url;
  });
}

/** Clone, B4 (picture/text-led reference): the warning, then the user's own similar photos by slot and words. */
function CloneContent({ q, busy, onAnswer }: { q: Question; busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [images, setImages] = useState<Record<string, string[]>>({});
  const [texts, setTexts] = useState<Record<string, string>>({});
  const maxOf = (hint: string) => parseInt(hint, 10) || 1;
  const add = async (slot: string, files: FileList | null, max: number) => {
    if (!files) return;
    const urls = await Promise.all([...files].slice(0, max).map((f) => toDataUrl(f).catch(() => "")));
    setImages((m) => ({ ...m, [slot]: [...(m[slot] ?? []), ...urls.filter(Boolean)].slice(0, max) }));
  };
  const count = Object.values(images).reduce((n, l) => n + l.length, 0);
  const filled = Object.values(texts).filter((v) => v.trim()).length;
  const submit = () => {
    const list = q.options.flatMap((o) => (images[o.value] ?? []).map((data) => ({ slot: o.value, data })));
    onAnswer({ value: { images: list, texts }, label: `${count} ảnh, ${filled} mục nội dung của tôi` });
  };
  return (
    <div className="flex flex-col gap-6" data-swarm-section="clone-content">
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Ảnh của bạn, theo từng chỗ trên trang</h3>
        {q.options.map((o) => {
          const max = maxOf(o.hint ?? "1");
          const got = images[o.value] ?? [];
          return (
            <div key={o.value} className="flex flex-col gap-2 rounded-xl border border-line p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{o.label}</span>
                <span className="text-xs text-fg-3">{o.hint} · đã chọn {got.length}/{max}</span>
              </div>
              {got.length > 0 && (
                <ul className="flex flex-wrap gap-2" aria-label={`Ảnh đã chọn cho ${o.label}`}>
                  {got.map((src, i) => (
                    <li key={i} className="relative">
                      {/* eslint-disable-next-line @next/next/no-img-element -- a local preview of the chosen file */}
                      <img src={src} alt={`Ảnh ${i + 1}`} className="size-16 rounded-lg border border-line object-cover" />
                      <button type="button" aria-label={`Bỏ ảnh ${i + 1}`} disabled={busy}
                        onClick={() => setImages((m) => ({ ...m, [o.value]: got.filter((_, j) => j !== i) }))}
                        className="absolute -right-2 -top-2 grid size-6 place-items-center rounded-full border border-line bg-elevated text-xs">×</button>
                    </li>
                  ))}
                </ul>
              )}
              {got.length < max && (
                <label className="self-start">
                  <span className={`${secondaryBtn} inline-flex cursor-pointer items-center`}>Chọn ảnh</span>
                  <input type="file" accept="image/*" multiple className="sr-only" disabled={busy}
                    data-swarm-id={`clone-images-${o.value}`} data-swarm-role="input"
                    onChange={(e) => { add(o.value, e.target.files, max - got.length); e.target.value = ""; }} />
                </label>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-medium">Nội dung của bạn</h3>
        {TEXT_FIELDS.map((f) => (
          <label key={f.key} className="flex flex-col gap-2 text-sm">
            <span className="text-fg-2">{f.label}</span>
            {f.rows ? (
              <textarea rows={f.rows} value={texts[f.key] ?? ""} placeholder={f.placeholder} className={input}
                onChange={(e) => setTexts((t) => ({ ...t, [f.key]: e.target.value }))} data-swarm-id={`clone-text-${f.key}`} data-swarm-role="input" />
            ) : (
              <input value={texts[f.key] ?? ""} placeholder={f.placeholder} className={`${input} h-12 py-0`}
                onChange={(e) => setTexts((t) => ({ ...t, [f.key]: e.target.value }))} data-swarm-id={`clone-text-${f.key}`} data-swarm-role="input" />
            )}
          </label>
        ))}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button type="button" disabled={busy || (count === 0 && filled === 0)} onClick={submit}
          data-swarm-id="clone-content-submit" data-swarm-role="button" className={primaryBtn}>
          Dùng ảnh và nội dung này
        </button>
        <button type="button" disabled={busy} data-swarm-id="clone-content-skip" data-swarm-role="button" className={secondaryBtn}
          onClick={() => onAnswer({ value: { images: [], texts: {} }, label: "Bỏ qua, dùng ảnh và chữ mẫu" })}>
          Bỏ qua, dùng ảnh và chữ mẫu
        </button>
      </div>
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
  const ref = useRef<HTMLDivElement>(null);
  // The build ends here: bring the handover into view (it sits under the build report otherwise).
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, []);
  return (
    <div ref={ref} className="flex flex-col gap-6 rounded-xl border border-accent p-4" data-swarm-section="handover">
      <div className="flex flex-col gap-1">
        <h3 className="text-base font-medium">Đã bàn giao trang</h3>
        <p className="text-sm text-fg-2">
          Dựng trang tiếp theo trong sitemap (giữ nguyên DESIGN.md, có kế hoạch mới để bạn duyệt), hoặc ghi góp ý để
          tinh chỉnh trang này (Chroma cập nhật kế hoạch, bạn duyệt lại rồi Chroma dựng lại).
        </p>
      </div>
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

const BACKEND_HTTP = (process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100").replace(/^ws/, "http");

type Preview = { url: string; title: string; image: string };

const validLink = (v: string) => {
  try {
    const u = new URL(v.trim());
    return (u.protocol === "http:" || u.protocol === "https:") && u.hostname.includes(".") ? u.toString() : null;
  } catch {
    return null;
  }
};

/** Clone, B1: a first-screen screenshot of the link as soon as it is valid, so the user can check it is the
 *  right page before Chroma reads it. Debounced; a page that blocks screenshots simply shows no preview. */
function LinkPreview({ url }: { url: string }) {
  const link = validLink(url);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ link: string; preview?: Preview; error?: string } | null>(null);
  useEffect(() => {
    if (!link) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      setState({ link });
      fetch(`${BACKEND_HTTP}/clone/preview?url=${encodeURIComponent(link)}`, { signal: ctrl.signal })
        .then(async (r) => {
          const data = await r.json();
          if (ctrl.signal.aborted) return;
          setState(r.ok ? { link, preview: data } : { link, error: data.detail || "Không tải được bản xem trước." });
        })
        .catch(() => { if (!ctrl.signal.aborted) setState({ link, error: "Không kết nối được tới backend." }); });
    }, 600);
    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [link, attempt]);
  if (!link || !state || state.link !== link) return null;
  return (
    <figure className="flex flex-col gap-2" data-swarm-section="link-preview" aria-live="polite">
      <div className="relative aspect-[16/10] overflow-hidden rounded-xl border border-line bg-surface" aria-busy={!state.preview && !state.error}>
        {state.preview ? (
          // eslint-disable-next-line @next/next/no-img-element -- a data URL screenshot, not an asset to optimise
          <img src={state.preview.image} alt={`Bản xem trước của ${state.preview.title}`} className="size-full object-cover object-top" />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-4 p-4 text-center text-sm text-fg-3">
            <p>{state.error ? `Không xem trước được trang này (${state.error}). Bạn vẫn có thể đọc trang.` : "Đang tải bản xem trước…"}</p>
            {state.error && (
              <button type="button" onClick={() => setAttempt((n) => n + 1)}
                className="min-h-12 rounded-lg border border-line px-4 text-fg hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                Thử lại bản xem trước
              </button>
            )}
          </div>
        )}
      </div>
      {state.preview && (
        <figcaption className="flex min-w-0 items-baseline justify-between gap-4 text-xs">
          <span className="truncate font-medium text-fg">{state.preview.title}</span>
          <span className="shrink-0 font-mono text-fg-3">{new URL(state.preview.url).hostname}</span>
        </figcaption>
      )}
    </figure>
  );
}

/** Clone mode, B1: a URL is enough to read the complete reference page. */
export function CloneSource({ busy, onAnswer }: { busy: boolean; onAnswer: Props["onAnswer"] }) {
  const [url, setUrl] = useState("");
  // The link survives a refresh until it is sent (read after mount: localStorage does not exist on the server).
  useEffect(() => {
    const d = loadDraft();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser storage exists only after mount (SSR-safe)
    if (d.url) setUrl(d.url);
  }, []);
  useEffect(() => { saveDraft(url, true); }, [url]);
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onAnswer({ value: { url: url.trim(), owned: true }, label: url.trim() });
        saveDraft("", false);
      }}
    >
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-medium">Link trang muốn dựng lại</span>
        <input id="clone-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" required
          className={`${input} h-12 py-0`} data-swarm-id="clone-url" data-swarm-role="input" />
      </label>
      <LinkPreview url={url} />
      <p className="text-sm text-fg-2">
        Chroma đọc toàn bộ trang mẫu: bố cục, chữ, hình ảnh, font và hiệu ứng. Bạn xem sketch toàn trang và duyệt kế hoạch trước khi dựng.
      </p>
      <button type="submit" disabled={busy || !url.trim()} data-swarm-id="clone-submit"
        data-swarm-role="button" className={`${primaryBtn} self-start`}>
        Đọc trang mẫu
      </button>
    </form>
  );
}
