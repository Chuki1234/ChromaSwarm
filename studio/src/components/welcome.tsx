"use client";

import { useRef } from "react";
import { HeroScene } from "@/components/hero-scene";
import type { Answer, Question } from "@/components/question-card";

/** B1 landing: what Chroma does, the 3D scene, and the one decision of this screen (Creative / Clone). */
export function Welcome({ question, busy, onAnswer }: { question: Question; busy: boolean; onAnswer: (a: Answer) => void }) {
  const creative = question.options.find((o) => o.value === "creative");
  const clone = question.options.find((o) => o.value === "clone");

  return (
    <div className="flex flex-col gap-12" data-swarm-section="welcome">
      <div className="grid items-center gap-8 lg:grid-cols-[1fr_minmax(0,520px)]">
        <div className="flex flex-col gap-6">
          <p className="rise font-mono text-xs uppercase tracking-[0.12em] text-accent sm:tracking-[0.2em]" style={{ "--d": "0ms" } as React.CSSProperties}>
            12 bước · 4 phòng ban · 1 trang mỗi lần
          </p>
          <h2 className="rise max-w-[16ch] text-4xl font-semibold leading-[1.05] tracking-tight text-balance sm:text-5xl lg:text-6xl"
            style={{ "--d": "80ms" } as React.CSSProperties}>
            Kể ý tưởng. Chroma dựng trang web cho bạn.
          </h2>
          <p className="rise max-w-[54ch] text-lg leading-relaxed text-fg-2" style={{ "--d": "160ms" } as React.CSSProperties}>
            Chroma hỏi vài câu về phong cách, màu và khách hàng, lập kế hoạch để bạn duyệt, rồi đội Design, Developer
            và QA dựng từng section ngay trước mắt bạn.
          </p>
          <ul className="rise flex flex-wrap gap-x-6 gap-y-2 text-sm text-fg-2" style={{ "--d": "240ms" } as React.CSSProperties}>
            <li className="flex items-center gap-2"><Check />Màu OKLCH đạt chuẩn tương phản</li>
            <li className="flex items-center gap-2"><Check />Kiểm thử ở 4 kích thước màn hình</li>
            <li className="flex items-center gap-2"><Check />Chấm điểm thẩm mỹ tự động</li>
          </ul>
        </div>
        <div className="rise hidden sm:block" style={{ "--d": "120ms" } as React.CSSProperties}>
          <HeroScene />
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <h3 className="rise text-sm font-medium text-fg-2" style={{ "--d": "320ms" } as React.CSSProperties}>{question.text}</h3>
        <div className="grid gap-4 md:grid-cols-2">
          {creative && (
            <ModeCard primary busy={busy} delay={380} value={creative.value} label={creative.label} hint={creative.hint}
              meta="Phù hợp khi bạn mới có ý tưởng" icon={<SparkIcon />} onAnswer={onAnswer} />
          )}
          {clone && (
            <ModeCard busy={busy} delay={440} value={clone.value} label={clone.label} hint={clone.hint}
              meta="Phù hợp khi đã có trang mẫu muốn làm theo" icon={<LayersIcon />} onAnswer={onAnswer} />
          )}
        </div>
      </div>
    </div>
  );
}

function ModeCard({ value, label, hint, meta, icon, primary = false, busy, delay, onAnswer }: {
  value: string; label: string; hint: string; meta: string; icon: React.ReactNode; primary?: boolean; busy: boolean;
  delay: number; onAnswer: (a: Answer) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [title, ...rest] = label.split(":");
  const tilt = (e: React.PointerEvent) => {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--rx", `${((e.clientY - r.top) / r.height - 0.5) * -6}deg`);
    el.style.setProperty("--ry", `${((e.clientX - r.left) / r.width - 0.5) * 8}deg`);
    el.style.setProperty("--mx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--my", `${((e.clientY - r.top) / r.height) * 100}%`);
  };
  const reset = () => {
    ref.current?.style.setProperty("--rx", "0deg");
    ref.current?.style.setProperty("--ry", "0deg");
  };
  return (
    <button
      ref={ref}
      type="button"
      disabled={busy}
      onPointerMove={tilt}
      onPointerLeave={reset}
      onClick={() => onAnswer({ value, label })}
      data-swarm-id={`option-${value}`}
      data-swarm-role="button"
      className={`mode-card rise group ${primary ? "mode-card-primary" : ""}`}
      style={{ "--d": `${delay}ms` } as React.CSSProperties}
    >
      <span className="mode-icon">{icon}</span>
      <span className="flex flex-col gap-2 text-left">
        <span className="text-lg font-semibold tracking-tight text-fg">{title.trim()}</span>
        <span className="text-sm leading-relaxed text-fg-2">{(rest.join(":").trim() || hint)}</span>
        {rest.length > 0 && hint && <span className="text-sm leading-relaxed text-fg-2">{hint}</span>}
        <span className="font-mono text-xs text-fg-3">{meta}</span>
      </span>
      <span className="mode-go" aria-hidden>
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 10h11m-4-4 4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
    </button>
  );
}

function Check() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden className="text-accent">
      <path d="m3.5 8.5 3 3 6-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.5 2.5M15.2 15.2l2.5 2.5M6.3 17.7l2.5-2.5M15.2 8.8l2.5-2.5"
        stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="m3 13 9 5 9-5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}
