"use client";

import type { PipelineState } from "@/components/pipeline-console";

type Props = { state: PipelineState; notice: string | null; running: boolean };

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
