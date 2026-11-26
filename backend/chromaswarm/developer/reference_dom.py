"""Emit the measured native DOM/CSS. Preserve authored grid/flex/vw/media rules and animation geometry."""
from __future__ import annotations

import json
import re


def render(section, page: str = '') -> str:
    from chromaswarm.developer.nextjs import component_name
    ref = section.reference
    html = re.sub(r'^(<[\w:-]+)', lambda m: m[0] + f' data-swarm-section="{section.id}" data-cs-native="true"', ref['html'], count=1)
    js = lambda value: json.dumps(value, ensure_ascii=False)
    # Each filtered sheet retains its own source order. Scope it so another section's base utility
    # cannot override this section's responsive utility merely because its component mounts later.
    styles = f'@scope ([data-swarm-section="{section.id}"]) {{\n' + ref.get('css', '') + '\n}'
    links = ref.get('stylesheets', [])
    scenes = [a for a in ref.get('assets', []) if a.get('scene')]
    components = [(''.join(p.title() for p in f'{section.id}-{a["id"]}'.split('-'))+'Asset', a['id']) for a in scenes]
    imports = '\n'.join(f'import {{ {name} }} from "@/components/motion/{name}";' for name, _ in components)
    portals = ''.join(f'{{targets[{js(asset)}] && createPortal(<{name} />, targets[{js(asset)}])}}' for name, asset in components)
    animations = [{'id': a['id'], **animation} for a in ref.get('assets', [])
                  for animation in a.get('animations', []) if animation['type'] not in ('CSSAnimation', 'CSSTransition')]
    return f'''"use client";
import {{ useEffect, useRef, useState, type MouseEvent }} from "react";
import {{ createPortal }} from "react-dom";
{imports}

// Master Cursor evidence: native layout and responsive authored CSS; no grid/gap substitutions.
const html = {js(html)};
const css = {js(styles)};
const panels: Record<string,string> = {js(ref.get('panels', {}))};
const animations = {js(animations)} as Array<{{id:string; keyframes:Keyframe[]; timing:Omit<KeyframeAnimationOptions,"iterations"> & {{iterations?:number|string}}}}>;
export function {component_name(section.id)}() {{
  const root = useRef<HTMLDivElement>(null);
  const [targets, setTargets] = useState<Record<string, Element>>({{}});
  const click = (event: MouseEvent<HTMLDivElement>) => {{
    const button = (event.target as Element).closest('button, [role="button"]');
    if (!button) return;
    const controls = button.getAttribute("aria-controls");
    let panel = controls ? document.getElementById(controls) : button.querySelector<HTMLElement>('[style*="height"]');
    const cached = panels[controls || button.id];
    if (!panel && cached) {{
      const doc = new DOMParser().parseFromString(cached, "text/html");
      const next = doc.body.firstElementChild as HTMLElement | null;
      const container = button.closest('h1,h2,h3,h4')?.parentElement || button.parentElement;
      if(next && container) {{ container.appendChild(next); panel = next; if(next.id)button.setAttribute('aria-controls',next.id); }}
    }}
    if (panel) {{
      const wasOpen = button.hasAttribute("aria-expanded") ? button.getAttribute("aria-expanded") === "true" : getComputedStyle(panel).opacity !== "0";
      button.setAttribute("aria-expanded", String(!wasOpen));
      if(wasOpen)button.removeAttribute('data-open');else button.setAttribute('data-open','true');
      panel.setAttribute("aria-hidden", String(wasOpen));
      panel.style.height = wasOpen ? "0px" : "auto";
      panel.style.opacity = wasOpen ? "0" : "1";
      panel.style.overflow = wasOpen ? "hidden" : "visible";
      panel.hidden = wasOpen;
    }} else if (/dismiss|close|ẩn thông báo|đóng/i.test(button.getAttribute("aria-label") || "")) {{
      const section = button.closest<HTMLElement>('[data-swarm-section]');
      if (section) section.hidden = true;
    }}
  }};
  useEffect(() => {{
    const found: Record<string, Element> = {{}};
    for (const id of {js([a['id'] for a in scenes])}) {{
      const target = root.current?.querySelector(`[data-swarm-asset="${{id}}"]`);
      if (target) found[id] = target;
    }}
    if(Object.keys(found).length) setTargets(found);
    const active: Animation[] = [];
    for (const a of animations) {{
      const e = root.current?.querySelector(`[data-swarm-asset="${{a.id}}"]`);
      if(e)active.push(e.animate(a.keyframes, {{...a.timing, iterations:a.timing.iterations === "infinite" ? Infinity : Number(a.timing.iterations ?? 1)}}));
    }}
    return () => active.forEach(a=>a.cancel());
  }}, []);
  return <>
    {''.join(f'<link rel="stylesheet" href={{{js(link)}}} />' for link in links)}
    <style>{{css}}</style>
    <div ref={{root}} onClick={{click}} onMouseOver={{e=>(e.target as Element).closest('button')?.setAttribute('data-hover','true')}}
      onMouseOut={{e=>(e.target as Element).closest('button')?.removeAttribute('data-hover')}}
      style={{{{display:"contents"}}}} dangerouslySetInnerHTML={{{{__html:html}}}} />
    {portals}
  </>;
}}
'''
