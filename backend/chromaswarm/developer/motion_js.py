"""B8.1 for Creative pages: scroll motion with GSAP (ScrollTrigger) and a Three.js scene, the
JavaScript half of the Motion & 2D/3D specialist (the CSS half is mcp_motion/).

The page never depends on them: `components/Motion.tsx` loads GSAP and Three.js lazily after
the page is interactive, does nothing under `prefers-reduced-motion`, never starts where WebGL
is missing, and only animates what `content/motion.ts` lists for the page — written section by
section at B9 from PLAN.md's effects. Content always ends visible (`clearProps`), so Master QA's
"stuck at opacity 0" check holds.
"""

from __future__ import annotations

import json
import re

GSAP_VERSION = "3.15.1"
THREE_VERSION = "0.187.0"
JS_EFFECTS = ("reveal", "stagger", "parallax", "scene-3d")
SCENE_HEROES = {"hero-centered", "hero-editorial", "hero-text"}  # headline over open space: room for a scene
WANTS_3D = re.compile(r"\b(3d|three\.?js|webgl|không gian ba chiều|3 chiều)\b", re.I)


def wants_3d(text: str) -> bool:
    return bool(WANTS_3D.search(text or ""))


def js_effects(effect: str | None, structure: str) -> list[str]:
    """The PLAN.md effect of a section as JS effect ids."""
    text = (effect or "").lower()
    out = []
    if "3d" in text or "three" in text:
        if structure in SCENE_HEROES:
            out.append("scene-3d")
    if "parallax" in text:
        out.append("parallax")
    if any(w in text for w in ("stagger", "lần lượt", "cards")):
        out.append("stagger")
    elif any(w in text for w in ("reveal", "entrance", "xuất hiện")):
        out.append("reveal")
    return out


def motion_config(pages: dict[str, dict[str, list[str]]]) -> str:
    return ("// HIỆU ỨNG CHUYỂN ĐỘNG — mỗi trang: section -> hiệu ứng (reveal, stagger, parallax, scene-3d).\n"
            "// Xoá một dòng để tắt hiệu ứng của section đó. Người dùng bật \"giảm chuyển động\" sẽ không thấy hiệu ứng.\n"
            f"export const MOTION: Record<string, Record<string, string[]>> = {json.dumps(pages, indent=2, ensure_ascii=False)};\n")


def parse_config(text: str) -> dict[str, dict[str, list[str]]]:
    m = re.search(r"= (\{.*\});\s*$", text or "", re.S)
    try:
        return json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}


MOTION_TSX = r'''"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { MOTION } from "@/content/motion";

/** GSAP scroll motion and the Three.js scene, loaded lazily; nothing under prefers-reduced-motion. */
export function Motion() {
  const path = usePathname();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const page = document.querySelector("main")?.getAttribute("data-swarm-page") ?? "index";
    const effects = MOTION[page] ?? {};
    if (!Object.keys(effects).length) return;
    const cleanup: (() => void)[] = [];
    let cancelled = false;
    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      const ctx = gsap.context(() => {
        for (const [id, list] of Object.entries(effects)) {
          const sec = document.querySelector<HTMLElement>(`[data-swarm-section="${id}"]`);
          if (!sec) continue;
          if (list.includes("stagger") || list.includes("reveal")) {
            const items = sec.querySelectorAll(list.includes("stagger") ? ".card, .product, .plan, .kpi, article, li" : ".container > *");
            if (items.length) {
              gsap.from(items, { y: 24, autoAlpha: 0, duration: 0.6, ease: "power2.out", stagger: 0.08, clearProps: "all",
                scrollTrigger: { trigger: sec, start: "top 92%", once: true } });
            }
          }
          if (list.includes("parallax")) {
            sec.querySelectorAll("img").forEach((img) => {
              gsap.fromTo(img, { yPercent: -4 }, { yPercent: 4, ease: "none",
                scrollTrigger: { trigger: sec, start: "top bottom", end: "bottom top", scrub: true } });
            });
          }
        }
      });
      cleanup.push(() => ctx.revert());
      for (const [id, list] of Object.entries(effects)) {
        const sec = document.querySelector<HTMLElement>(`[data-swarm-section="${id}"]`);
        if (!sec || !list.includes("scene-3d")) continue;
        const { mountScene } = await import("@/components/Scene3D");
        if (cancelled) return;
        cleanup.push(mountScene(sec));
      }
    })();
    return () => { cancelled = true; cleanup.forEach((stop) => stop()); };
  }, [path]);
  return null;
}
'''

SCENE_TSX = r'''import * as THREE from "three";

/** The brand colour as sRGB, whatever colour space the token uses (oklch, hex…). */
function tokenColor(name: string): THREE.Color {
  const probe = document.createElement("canvas");
  probe.width = probe.height = 1;
  const ctx = probe.getContext("2d");
  if (!ctx) return new THREE.Color(0x888888);
  ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return new THREE.Color(r / 255, g / 255, b / 255);
}

/** A quiet wireframe form behind the hero headline, offset to one side (asymmetric focal anchor).
 *  Paused off-screen; returns a cleanup function. Does nothing where WebGL is unavailable. */
export function mountScene(host: HTMLElement): () => void {
  const canvas = document.createElement("canvas");
  if (!(canvas.getContext("webgl2") || canvas.getContext("webgl"))) return () => {};
  canvas.className = "scene-3d";
  canvas.setAttribute("aria-hidden", "true");
  host.classList.add("has-scene");
  host.prepend(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  camera.position.z = 7;
  const accent = tokenColor("--action");
  const form = new THREE.Mesh(new THREE.IcosahedronGeometry(1.7, 1),
    new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.35 }));
  const halo = new THREE.Mesh(new THREE.TorusGeometry(2.6, 0.01, 8, 160),
    new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.25 }));
  scene.add(form, halo);
  let visible = true;
  let frame = 0;
  let pointerX = 0;
  const size = () => {
    const { width, height } = host.getBoundingClientRect();
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(height, 1);
    camera.updateProjectionMatrix();
    const x = width >= 1024 ? 3.4 : 0;  // beside the copy on desktop, centred and fainter on mobile
    form.position.x = halo.position.x = x;
    (form.material as THREE.MeshBasicMaterial).opacity = width >= 1024 ? 0.35 : 0.18;
  };
  const tick = () => {
    frame = requestAnimationFrame(tick);
    if (!visible) return;
    form.rotation.x += 0.0015;
    form.rotation.y += 0.0025 + pointerX * 0.002;
    halo.rotation.x = 1.2 + pointerX * 0.1;
    renderer.render(scene, camera);
  };
  const onPointer = (e: PointerEvent) => { pointerX = e.clientX / window.innerWidth - 0.5; };
  const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
  const ro = new ResizeObserver(size);
  io.observe(host);
  ro.observe(host);
  window.addEventListener("pointermove", onPointer, { passive: true });
  size();
  tick();
  return () => {
    cancelAnimationFrame(frame);
    io.disconnect();
    ro.disconnect();
    window.removeEventListener("pointermove", onPointer);
    renderer.dispose();
    canvas.remove();
    host.classList.remove("has-scene");
  };
}
'''

SCENE_CSS = """
/* Three.js scene (components/Scene3D.tsx): behind the hero copy, never in the way of a click. */
.has-scene { position: relative; isolation: isolate; overflow: hidden; }
.has-scene > .container { position: relative; z-index: 1; }
.scene-3d { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none; }
/* Never behind the words: the scene fades out over the headline column and stays off phones. */
.scene-3d { -webkit-mask-image: linear-gradient(to right, transparent 0 58%, #000 88%); mask-image: linear-gradient(to right, transparent 0 58%, #000 88%); }
@media (max-width: 1023px) { .scene-3d { display: none; } }
"""
