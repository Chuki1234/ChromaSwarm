"use client";

import { useEffect, useRef } from "react";

/**
 * 3D illustration of what ChromaSwarm does: a web page assembled layer by layer
 * (nav, hero, cards, story, footer) while the agent cursors work on it.
 * Pure CSS 3D (no WebGL): the scene tilts toward the pointer; with
 * prefers-reduced-motion it stays still. Decorative only (aria-hidden).
 */
const LAYERS = [
  { id: "nav", label: "Header" },
  { id: "hero", label: "Hero" },
  { id: "cards", label: "Bento" },
  { id: "story", label: "Story" },
  { id: "footer", label: "Footer" },
] as const;

const CURSORS = [
  { name: "Layout", cls: "c-layout" },
  { name: "Color", cls: "c-color" },
  { name: "Type", cls: "c-type" },
  { name: "Master QA", cls: "c-master" },
];

export function HeroScene() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - (r.left + r.width / 2)) / r.width; // -0.5 .. 0.5 around the scene
      const y = (e.clientY - (r.top + r.height / 2)) / r.height;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        el.style.setProperty("--tilt-x", `${Math.max(-1, Math.min(1, y)) * -8}deg`);
        el.style.setProperty("--tilt-y", `${Math.max(-1, Math.min(1, x)) * 10}deg`);
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div ref={ref} className="scene" aria-hidden>
      <div className="scene-glow" />
      <div className="scene-stage">
        {LAYERS.map((l, i) => (
          <div key={l.id} className={`sheet sheet-${l.id}`} style={{ "--i": i } as React.CSSProperties}>
            <span className="sheet-tag">{l.label}</span>
            <Skeleton id={l.id} />
          </div>
        ))}
        {CURSORS.map((c) => (
          <div key={c.name} className={`swarm-cursor ${c.cls}`}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M2 2l13 5.5-5.6 1.9L7.5 15z" fill="currentColor" stroke="var(--bg-primary)" strokeWidth="1.2" strokeLinejoin="round" />
            </svg>
            <span>{c.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Skeleton({ id }: { id: (typeof LAYERS)[number]["id"] }) {
  switch (id) {
    case "nav":
      return (
        <div className="sk-row">
          <i className="sk w-16" />
          <span className="sk-gap" />
          <i className="sk w-8" /><i className="sk w-8" /><i className="sk w-8" />
        </div>
      );
    case "hero":
      return (
        <div className="sk-hero">
          <div className="sk-col">
            <i className="sk sk-title w-40" />
            <i className="sk sk-title w-28" />
            <i className="sk w-32" />
            <i className="sk sk-btn" />
          </div>
          <i className="sk-photo" />
        </div>
      );
    case "cards":
      return (
        <div className="sk-cards">
          <i className="sk-photo" /><i className="sk-photo" /><i className="sk-photo" />
        </div>
      );
    case "story":
      return (
        <div className="sk-hero">
          <i className="sk-photo" />
          <div className="sk-col">
            <i className="sk sk-title w-28" />
            <i className="sk w-36" />
            <i className="sk w-32" />
          </div>
        </div>
      );
    default:
      return (
        <div className="sk-row">
          <i className="sk w-20" />
          <span className="sk-gap" />
          <i className="sk w-24" />
        </div>
      );
  }
}
