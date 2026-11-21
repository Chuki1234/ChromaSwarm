"use client";

import { useState } from "react";
import type { CompareResult, CompareSection, PipelineState } from "@/components/pipeline-console";

type Props = { state: PipelineState; notice: string | null; running: boolean };

const BACKEND_HTTP = (process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://localhost:8100").replace(/^ws/, "http");

const SECTION_STATUS = {
  todo: { label: "Chờ", cls: "text-fg-3" },
  written: { label: "Dev đã viết", cls: "text-fg-2" },
  checked: { label: "Design đã đo", cls: "text-accent" },
} as const;

/** B8–B10 progress: sections moving through Dev → Design, live preview, token repairs. */
export function BuildPanel({ state, notice, running }: Props) {
  const planned = state.sections_planned ?? [];
  const done = new Set(state.sections_done ?? []);
  const checked = new Set(state.sections_checked ?? []);
  const progress = planned.length ? Math.round((checked.size / planned.length) * 100) : 0;

  return (
    <div className="flex flex-col gap-6" data-swarm-section="build">
      {!notice ? null : state.build_error ? (
        <p role="alert" className="rounded-lg border border-danger/40 px-4 py-3 text-sm text-danger">
          {notice}
        </p>
      ) : (
        <p className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-fg-2" aria-live="polite">
          {running && <span className="mr-2 inline-block size-2 animate-pulse rounded-full bg-accent align-middle" />}
          {notice}
        </p>
      )}

      {planned.length > 0 && (
        <div className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium">Section</span>
            <span className="font-mono text-xs text-fg-3">
              {checked.size}/{planned.length} · {progress}%
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-accent transition-[width] duration-500" style={{ width: `${progress}%` }} />
          </div>
          <ol className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            {planned.map((id, i) => {
              const s = checked.has(id) ? "checked" : done.has(id) ? "written" : "todo";
              return (
                <li key={id} className="flex items-baseline justify-between gap-4 border-b border-line py-2">
                  <span className="font-mono text-xs text-fg-3">{String(i + 1).padStart(2, "0")}</span>
                  <span className="flex-1 truncate">{id}</span>
                  <span className={`text-xs ${SECTION_STATUS[s].cls}`}>{SECTION_STATUS[s].label}</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {Object.keys(state.section_reviews ?? {}).length > 0 && <Reviews state={state} />}

      {state.preview_url && (
        <div className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium">Trang đang dựng</span>
            <a href={state.preview_url} target="_blank" rel="noreferrer" data-swarm-id="open-preview" data-swarm-role="link"
              className="font-mono text-xs text-accent underline-offset-4 hover:underline">
              {state.preview_url} ↗
            </a>
          </div>
          <iframe title="Bản xem trước trang đang dựng" src={state.preview_url}
            className="aspect-[16/10] w-full rounded-xl border border-line bg-surface" />
          <p className="text-xs text-fg-3">Đàn con trỏ của phòng Design hiển thị trên cửa sổ Chromium mà hệ thống mở riêng.</p>
        </div>
      )}

      {state.qa_summary && <QaPanel state={state} />}

      {(state.factory_log?.length ?? 0) > 0 && (
        <List title="Nhà máy cursor (B9): section → tổ → component" items={state.factory_log!} />
      )}

      {state.clone_compare && <ComparePanel result={state.clone_compare} session={state.session_id} />}

      {state.clone_fidelity != null && (
        <div className="flex flex-col gap-2 rounded-xl border border-line p-4" data-swarm-section="fidelity">
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="text-sm font-medium">Độ giống trang mẫu</h3>
            <span className="font-mono text-sm">{Math.round(state.clone_fidelity)}/100</span>
          </div>
          {(state.clone_fidelity_notes?.length ?? 0) > 0 && (
            <ul className="flex flex-col gap-1 text-sm text-fg-2">
              {state.clone_fidelity_notes!.map((n) => <li key={n}>{n}</li>)}
            </ul>
          )}
        </div>
      )}

      {state.qa_passed && (
        <div className="flex flex-col gap-2 rounded-xl border border-line p-4" data-swarm-section="template">
          <h3 className="text-sm font-medium">Dùng trang này làm template</h3>
          <p className="text-sm text-fg-2">
            Chữ nằm trong <code className="font-mono text-xs">content/</code>, ảnh trong{" "}
            <code className="font-mono text-xs">public/images/</code>. Giải nén, sửa nội dung, chạy{" "}
            <code className="font-mono text-xs">npm install && npm run dev</code> — xem HUONG_DAN.md bên trong.
          </p>
          <a href={`${BACKEND_HTTP}/sessions/${encodeURIComponent(state.session_id)}/template.zip`} download
            data-swarm-id="download-template" data-swarm-role="link"
            className="self-start rounded-lg bg-accent px-4 py-3 text-sm font-medium text-accent-fg hover:bg-[var(--accent-hover)]">
            Tải template (.zip)
          </a>
        </div>
      )}
      {(state.qa_passed || state.escalated_to_user) && <Publish sessionId={state.session_id} />}

      {Object.keys(state.page_routes ?? {}).length > 1 && (
        <List title="Các trang đã dựng" items={Object.entries(state.page_routes).map(([slug, route]) => `${route}  ·  ${slug}`)} />
      )}
      {(state.motion_effects?.length ?? 0) > 0 && (
        <List title="Hiệu ứng B8.1 (Motion MCP)" items={state.motion_effects} />
      )}
      {(state.token_changes?.length ?? 0) > 0 && (
        <List title="Phòng Design đã sửa tokens.css" items={state.token_changes} />
      )}
      {(state.open_findings?.length ?? 0) > 0 && (
        <List title="Còn lại cho Master QA (B11)" items={state.open_findings} />
      )}
    </div>
  );
}

/** B11 verdict: the four Master QA tests, self-healing loops and what is left for the user. */
function QaPanel({ state }: { state: PipelineState }) {
  const tests = (state.qa_summary ?? "").split(" · ");
  const loops = state.heal_history?.length ?? 0;
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section="qa-report">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-sm font-medium">Master QA (B11)</h3>
        <span className={`font-mono text-xs ${state.qa_passed ? "text-accent" : "text-danger"}`}>
          {state.qa_passed ? "100% PASSED" : state.escalated_to_user ? "Cần bạn xem" : "Đang tự sửa"}
        </span>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {tests.map((t) => (
          <li key={t} className="flex items-center gap-2 text-sm">
            <span aria-hidden className={t.endsWith("PASS") ? "text-accent" : "text-danger"}>{t.endsWith("PASS") ? "✓" : "✗"}</span>
            <span className="text-fg-2">{t}</span>
          </li>
        ))}
      </ul>
      {state.design_score != null && (
        <div className="flex flex-col gap-2 border-t border-line pt-3">
          <div className="flex items-baseline justify-between gap-4">
            <h4 className="text-sm font-medium">Chấm thẩm mỹ</h4>
            <span className="font-mono text-sm">{state.design_score.toFixed(1)}/10</span>
          </div>
          {(state.design_critique?.length ?? 0) > 0 && (
            <ul className="flex flex-col gap-1 text-xs text-fg-2">
              {state.design_critique.slice(0, 6).map((c, i) => (
                <li key={i}>— {c}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {loops > 0 && (
        <p className="text-xs text-fg-3">
          {loops} vòng tự sửa · Dev đã vá {state.heal_rules?.length ?? 0} điểm CSS trong heal.css
        </p>
      )}
      {!state.qa_passed && (state.qa_failures?.length ?? 0) > 0 && (
        <ul className="flex flex-col gap-1 font-mono text-xs text-fg-2">
          {state.qa_failures.slice(0, 12).map((f, i) => (
            <li key={i}>— {f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** B11 Clone: the Master cursor's 1:1 acceptance — each section of the reference beside the rebuild. */
function ComparePanel({ result, session }: { result: CompareResult; session: string }) {
  const [open, setOpen] = useState<string | null>(result.sections.find((s) => s.score < 80)?.id ?? result.sections[0]?.id ?? null);
  const shot = (name: string | null) => (name ? `${BACKEND_HTTP}/sessions/${encodeURIComponent(session)}/compare/${name}` : null);
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section="compare">
      <div className="flex items-baseline justify-between gap-4">
        <h3 className="text-sm font-medium">Nghiệm thu 1:1 với link gốc</h3>
        <span className="font-mono text-sm">{Math.round(result.total)}%</span>
      </div>
      <p className="text-xs text-fg-2">
        Từng component của trang mẫu được ghép với component cùng loại trên bản dựng: 40% đủ component · 30% vị trí và kích thước ·
        20% kiểu chữ, bo góc, đổ bóng · 10% chiều cao. Chữ và ảnh không được so.
        {result.rounds > 0 && ` ${result.rounds} vòng tinh chỉnh tự động.`}
      </p>
      <ul className="flex flex-col divide-y divide-line">
        {result.sections.map((s) => (
          <CompareRow key={s.id} s={s} open={open === s.id} onToggle={() => setOpen(open === s.id ? null : s.id)}
            refSrc={shot(s.ref_image)} builtSrc={shot(s.built_image)} />
        ))}
      </ul>
    </div>
  );
}

function CompareRow({ s, open, onToggle, refSrc, builtSrc }: {
  s: CompareSection; open: boolean; onToggle: () => void; refSrc: string | null; builtSrc: string | null;
}) {
  const tone = s.score >= 90 ? "text-accent" : s.score >= 75 ? "text-fg" : "text-danger";
  return (
    <li className="flex flex-col gap-3 py-2">
      <button type="button" onClick={onToggle} aria-expanded={open} data-swarm-id={`compare-${s.id}`} data-swarm-role="button"
        className="flex min-h-11 items-center justify-between gap-4 rounded-lg px-2 text-left text-sm hover:bg-surface">
        <span className="truncate">{s.name || s.id}</span>
        <span className={`font-mono text-xs ${tone}`}>{Math.round(s.score)}%</span>
      </button>
      {open && (
        <div className="flex flex-col gap-3 px-2">
          <div className="grid grid-cols-2 gap-2">
            {[["Trang mẫu", refSrc], ["Bản dựng", builtSrc]].map(([label, src]) => (
              <figure key={label} className="flex flex-col gap-1">
                <figcaption className="text-xs text-fg-2">{label}</figcaption>
                {src ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={src} alt={`${label}: ${s.name || s.id}`} loading="lazy"
                    className="max-h-80 w-full rounded-lg border border-line object-cover object-top" />
                ) : <div className="grid h-24 place-items-center rounded-lg border border-line text-xs text-fg-3">Chưa có ảnh</div>}
              </figure>
            ))}
          </div>
          <p className="font-mono text-xs text-fg-3">
            component {Math.round(s.parts.components * 100)}% · vị trí {Math.round(s.parts.layout * 100)}% · kiểu {Math.round(s.parts.style * 100)}% ·
            cao {s.ref_height}→{s.built_height}px
          </p>
          {(s.diffs.length > 0 || s.effects_missing.length > 0) && (
            <ul className="flex flex-col gap-1 text-xs text-fg-2">
              {s.diffs.map((d, k) => <li key={`d${k}-${d}`}>— {d}</li>)}
              {s.effects_missing.map((e, k) => <li key={`e${k}-${e}`}>— thiếu hiệu ứng {e}</li>)}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">{title}</h3>
      <ul className="flex flex-col gap-1 font-mono text-xs text-fg-2">
        {items.map((t, i) => (
          <li key={i}>— {t}</li>
        ))}
      </ul>
    </div>
  );
}

type PublishResult = { target: string; url: string; state: string; detail: string };
const TARGETS = [
  { id: "vercel", label: "Đưa lên Vercel", hint: "Có link chạy thật ngay, cần VERCEL_TOKEN trong backend/.env" },
  { id: "github", label: "Đẩy code lên GitHub", hint: "Repository riêng tư, cần GITHUB_TOKEN trong backend/.env" },
] as const;

/** After handover: a live link (Vercel) or the code in a private repository (GitHub), with the user's own token. */
function Publish({ sessionId }: { sessionId: string }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, PublishResult>>({});
  const [error, setError] = useState("");
  const go = async (target: string) => {
    setBusy(target);
    setError("");
    try {
      const r = await fetch(`${BACKEND_HTTP}/sessions/${encodeURIComponent(sessionId)}/publish/${target}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      const data = await r.json();
      if (!r.ok) setError(data.detail ?? "Xuất bản không thành công.");
      else setResults((prev) => ({ ...prev, [target]: data }));
    } catch {
      setError("Không kết nối được tới backend.");
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line p-4" data-swarm-section="publish">
      <h3 className="text-sm font-medium">Xuất bản</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {TARGETS.map((t) => (
          <div key={t.id} className="flex flex-col gap-2">
            <button type="button" disabled={busy !== null} onClick={() => go(t.id)} data-swarm-id={`publish-${t.id}`} data-swarm-role="button"
              className="h-11 rounded-lg border border-line-strong px-4 text-sm font-medium transition-colors duration-200 hover:border-fg-3 active:scale-[0.98] disabled:opacity-50">
              {busy === t.id ? "Đang xuất bản…" : t.label}
            </button>
            <span className="text-xs text-fg-3">{t.hint}</span>
            {results[t.id] && (
              <p className="text-sm" role="status">
                <a href={results[t.id].url} target="_blank" rel="noreferrer" className="break-all text-accent underline underline-offset-2">{results[t.id].url}</a>
                {results[t.id].detail && <span className="block text-fg-2">{results[t.id].detail}</span>}
              </p>
            )}
          </div>
        ))}
      </div>
      <p className="text-sm text-danger" role="alert">{error}</p>
    </div>
  );
}

/** B9 eyes: each section as it was seen right after it was built (desktop + phone), with the verdict. */
function Reviews({ state }: { state: PipelineState }) {
  const reviews = state.sections_planned.filter((id) => state.section_reviews?.[id]).map((id) => [id, state.section_reviews![id]] as const);
  const shot = (file: string) => `${BACKEND_HTTP}/sessions/${encodeURIComponent(state.session_id)}/shots/${file}`;
  return (
    <div className="flex flex-col gap-3" data-swarm-section="section-reviews">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium">Mắt kiểm tra từng phần</span>
        <span className="font-mono text-xs text-fg-3">{reviews.filter(([, r]) => r.ok).length}/{reviews.length} đạt</span>
      </div>
      <ol className="flex flex-col gap-3">
        {reviews.map(([id, r]) => (
          <li key={id} className="flex flex-col gap-3 rounded-xl border border-line p-3">
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <span className="font-medium">{r.name}</span>
              <span className={`font-mono text-xs ${r.ok ? "text-accent" : "text-fg-2"}`}>
                {r.ok ? "Đạt" : "Còn góp ý"} · {r.score.toFixed(0)}/10
                {r.tries > 0 && ` · từ ${r.first_score.toFixed(0)}, sửa ${r.fixed}/${r.tries}`}
              </span>
            </div>
            <div className="grid grid-cols-[1fr_96px] items-start gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element -- screenshot served by the backend */}
              <img src={shot(r.files[0])} alt={`${r.name} trên máy tính`} className="w-full rounded-md border border-line" loading="lazy" />
              {/* eslint-disable-next-line @next/next/no-img-element -- screenshot served by the backend */}
              <img src={shot(r.files[1])} alt={`${r.name} trên điện thoại`} className="w-full rounded-md border border-line" loading="lazy" />
            </div>
            {r.issues.length > 0 && (
              <ul className="flex flex-col gap-1 text-xs leading-relaxed text-fg-2">
                {r.issues.map((i) => <li key={i}>{i}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
