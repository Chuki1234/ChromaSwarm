// Master Cursor's DevTools reader. Read authored layout, never infer it from picture positions.
({ indices = [], built = false, measure_only = false }) => {
  const box = e => { const r = e.getBoundingClientRect(); return {x:r.x, y:r.y + scrollY, w:r.width, h:r.height}; };
  const props = ['display','position','top','right','bottom','left','width','height','min-width','max-width','min-height','max-height',
    'margin-top','margin-right','margin-bottom','margin-left','padding-top','padding-right','padding-bottom','padding-left',
    'box-sizing','gap','row-gap','column-gap','grid-template-columns','grid-template-rows','grid-column','grid-row',
    'flex-direction','flex-wrap','flex-grow','flex-shrink','flex-basis','align-items','justify-content','aspect-ratio',
    'overflow-x','overflow-y','transform','transform-origin','clip-path','mask-image','filter','perspective','z-index'];
  const css = e => { const s=getComputedStyle(e); return Object.fromEntries(props.map(k=>[k,s.getPropertyValue(k)])); };
  const path = (e,root) => { const out=[]; while(e!==root&&e.parentElement){out.unshift([...e.parentElement.children].indexOf(e));e=e.parentElement;}return out.join('.'); };
  const safeURL = (v, attr) => {
    if (v.startsWith('#')) return v;
    if (attr==='src' && /^data:image\/(png|jpeg|webp|gif|svg\+xml);/i.test(v)) return v;
    try { const u=new URL(v,location.href);return ['http:','https:','mailto:','tel:'].includes(u.protocol)?u.href:''; } catch {return '';}
  };
  const absCSS = (text, base) => text.replace(/url\(\s*(['"]?)([^)'"\s]+)\1\s*\)/g, (all,q,v)=>{
    if (v.startsWith('#')||v.startsWith('data:')) return all;
    try { const u=new URL(v,base);return ['http:','https:'].includes(u.protocol)?`url("${u.href}")`:'none'; } catch {return 'none';}
  });
  const output={};
  for(const index of indices){
    const root=document.querySelector(built?`[data-swarm-section="${index}"]`:`[data-cs-block="${index}"]`);
    if(!root)continue;
    const all=[root,...root.querySelectorAll('*')];
    if(all.length>4000)continue; // Explicitly fall back rather than silently truncating a section.
    const animations=document.getAnimations().filter(a=>a.effect?.target&&(root===a.effect.target||root.contains(a.effect.target)));
    const special=[];
    for(const e of all){
      const s=getComputedStyle(e), own=animations.filter(a=>a.effect.target===e);
      if(!e.hasAttribute('data-swarm-asset')&&!own.length&&!['CANVAS','VIDEO','svg'].includes(e.tagName)&&s.transform==='none'&&s.filter==='none'&&!/gradient\(/.test(s.backgroundImage))continue;
      const id=e.getAttribute('data-swarm-asset')||'a-'+(path(e,root).replaceAll('.','-')||'root');
      if(!built)e.setAttribute('data-swarm-asset',id);
      const parents=[];
      for(let p=e.parentElement;p&&root.contains(p);p=p.parentElement){parents.push({path:path(p,root),box:box(p),css:css(p)});if(p===root)break;}
      const model=e.getAttribute('data-model-url')||e.closest('model-viewer')?.getAttribute('src');
      special.push({id,tag:e.tagName.toLowerCase(),path:path(e,root),box:box(e),css:css(e),parents,
        renderer_state:e.querySelector('[data-three-asset]')?.getAttribute('data-state')||null,
        ...(model?{scene:{model_url:safeURL(model,'src')}}:{}),
        animations:own.map(a=>({type:a.constructor.name,keyframes:a.effect.getKeyframes().map(({computedOffset,easing,offset,...f})=>({...f,offset:computedOffset,easing})),
          timing:{...a.effect.getTiming(),iterations:a.effect.getTiming().iterations===Infinity?'infinite':a.effect.getTiming().iterations}}))});
    }
    if(built||measure_only){output[index]={box:box(root),css:css(root),assets:special};continue;}
    const clone=root.cloneNode(true), copies=[clone,...clone.querySelectorAll('*')];
    for(let i=0;i<copies.length;i++){
      const e=copies[i], original=all[i];
      if(['SCRIPT','IFRAME','OBJECT','EMBED','BASE','META','LINK','STYLE','FOREIGNOBJECT'].includes(e.tagName.toUpperCase())){e.remove();continue;}
      if(/^(animate|set)/i.test(e.localName)&&/^(on|href|src)/i.test(e.getAttribute('attributeName')||'')){e.remove();continue;}
      for(const a of [...e.attributes]){
        if(/^on/i.test(a.name)||['srcdoc','nonce','integrity','action','formaction','autofocus'].includes(a.name)||/^data-cs-/.test(a.name))e.removeAttribute(a.name);
        else if(['src','href','xlink:href','poster'].includes(a.name)){const v=safeURL(a.value,a.name);if(v)e.setAttribute(a.name,v);else e.removeAttribute(a.name);}
      }
      if(e.tagName==='IMG'){const src=safeURL(original.currentSrc||original.src,'src');if(src)e.setAttribute('src',src);else e.removeAttribute('src');e.removeAttribute('srcset');e.removeAttribute('sizes');e.setAttribute('loading','eager');}
      if(e.tagName==='CANVAS'){
        if(original.hasAttribute('data-model-url'))continue; // Three.js reuses this exact canvas; its CSS box stays intact.
        try{const image=document.createElement('img');image.src=original.toDataURL('image/png');image.setAttribute('style',e.getAttribute('style')||'');image.className=e.className;image.setAttribute('data-swarm-asset',e.getAttribute('data-swarm-asset'));image.setAttribute('data-cs-canvas-fallback','true');image.width=original.width;image.height=original.height;e.replaceWith(image);}catch{e.setAttribute('data-cs-unresolved','canvas');}
      }
    }
    const warnings=[];
    const rules=(list,base)=>[...list].map(r=>{
      if(r.selectorText){
        const selectors=r.selectorText.replace(/::[\w-]+(?:\([^)]*\))?/g,'').replace(/:(hover|active|focus|focus-visible|focus-within|visited)/g,'');
        let keep=/(:root|\bhtml\b|\bbody\b|^\*)/.test(selectors);
        try{keep=keep||root.matches(selectors)||!!root.querySelector(selectors);}catch{keep=true;}
        let text=r.cssText;
        const parts=r.selectorText.split(','), globals=parts.filter(s=>/^(html|body|:root|:host)$/.test(s.trim()));
        if(globals.length){
          // The page's inherited type/theme applies, but html/body height, display and positioning
          // belong to the document, not to every section root.
          const inherited=[...r.style].filter(k=>(k.startsWith('--')||/^(font|line-height|letter-spacing|color|text-rendering)/.test(k))&&r.style.getPropertyValue(k)!=='inherit');
          const declarations=inherited.map(k=>`${k}:${r.style.getPropertyValue(k)}`).join(';');
          const rest=parts.filter(s=>!globals.includes(s));
          text=(declarations?`:scope {${declarations}}`:'')+(rest.length?rest.join(',')+text.slice(text.indexOf('{')):'');
        }
        // @scope implicitly anchors descendant selectors. Explicit :scope retains rules for the root itself.
        try{if(!globals.length&&root.matches(r.selectorText))text=':scope, '+text;}catch{}
        return keep?absCSS(text,base):'';
      }
      if(r.cssRules && !r.name){const inner=rules(r.cssRules,base);return inner?`${r.cssText.slice(0,r.cssText.indexOf('{'))}{${inner}}`:'';}
      return absCSS(r.cssText,base);
    }).join('\n');
    let styles=''; const links=[];
    for(const sheet of document.styleSheets){try{styles+=rules(sheet.cssRules,sheet.href||location.href)+'\n';}catch{if(sheet.href){links.push(sheet.href);warnings.push('external stylesheet: '+sheet.href);}}}
    // Keep inherited theme variables and font; author media rules retain vw/%/calc at every viewport.
    const computed=getComputedStyle(root), inherited={};
    for(const k of computed)if(k.startsWith('--'))inherited[k]=computed.getPropertyValue(k);
    inherited['font-family']=computed.fontFamily;inherited['color']=computed.color;
    clone.setAttribute('style',(clone.getAttribute('style')||'')+';'+Object.entries(inherited).map(([k,v])=>`${k}:${v}`).join(';'));
    const selectorPath=e=>{const parts=[];while(e&&e!==document.body){parts.unshift(e.tagName.toLowerCase()+':nth-child('+([...e.parentElement.children].indexOf(e)+1)+')');e=e.parentElement;}return 'body > '+parts.join(' > ');};
    output[index]={selector:selectorPath(root),html:clone.outerHTML,css:styles,stylesheets:links,box:box(root),layout:css(root),assets:special,warnings};
  }
  return output;
}
