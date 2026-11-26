"""DevTools evidence for layout and special assets, shared by the reader and Master QA."""
from __future__ import annotations

from pathlib import Path

PROBE = Path(__file__).with_suffix('.js').read_text(encoding='utf-8')


async def capture_panels(page, captured: dict) -> None:
    """Read lazily mounted accordion content and restore the source's initial state.

    Only ARIA disclosure buttons are operated; no forms, navigation or popup controls.
    Initial layout remains untouched in `captured`; extra panels mount only after a user clicks.
    """
    controls = await page.evaluate('''() => [...document.querySelectorAll('[data-cs-block] button[aria-expanded]')]
      .filter(e=>!e.hasAttribute('aria-haspopup')).map((e,i)=>{
        e.setAttribute('data-cs-toggle',String(i));
        return {i,id:e.id,index:e.closest('[data-cs-block]').getAttribute('data-cs-block'),target:e.getAttribute('aria-controls'),
                open:e.getAttribute('aria-expanded')==='true',missing:!document.getElementById(e.getAttribute('aria-controls'))};
      })''')
    for control in [c for c in controls if c['missing'] and not c['open']][:8]:
        section = captured.get(control['index'])
        if not section:
            continue
        button = page.locator(f'[data-cs-toggle="{control["i"]}"]')
        try:
            await button.click(force=True, timeout=2000)
            await page.wait_for_function('''(i)=>{const e=document.querySelector(`[data-cs-toggle="${i}"]`);
              return !!document.getElementById(e?.getAttribute('aria-controls'));}''', arg=control['i'], timeout=2000)
            target = await button.get_attribute('aria-controls')
            opened = (await inspect(page, [control['index']], cdp=False))[control['index']]
            panel = await page.evaluate('''({html,id})=>new DOMParser().parseFromString(html,'text/html').getElementById(id)?.outerHTML''',
                                        {'html':opened['html'], 'id':target})
            if panel:
                section.setdefault('panels', {})[control['target'] or control['id']] = panel
        finally:
            for initial in controls:
                current = page.locator(f'[data-cs-toggle="{initial["i"]}"]')
                if await current.count() and (await current.get_attribute('aria-expanded') == 'true') != initial['open']:
                    await current.click(force=True, timeout=2000)
            await page.wait_for_timeout(100)


async def inspect(page, indices: list[str], *, built: bool = False, cdp: bool = True, capture: bool = True) -> dict:
    result = await page.evaluate(PROBE, {'indices': indices, 'built': built, 'measure_only': not capture})
    if not cdp:
        return result
    session = await page.context.new_cdp_session(page)
    try:
        await session.send('DOM.enable')
        await session.send('CSS.enable')
        document = await session.send('DOM.getDocument', {'depth': 0})
        for key, section in result.items():
            for asset in section['assets'][:64]:
                selector = (f'[data-swarm-section="{key}"]' if built else f'[data-cs-block="{key}"]')
                selector += f' [data-swarm-asset="{asset["id"]}"]' if asset['path'] else ''
                node = await session.send('DOM.querySelector', {'nodeId': document['root']['nodeId'], 'selector': selector})
                if not node.get('nodeId'):
                    continue
                try:
                    asset['box_model'] = (await session.send('DOM.getBoxModel', {'nodeId': node['nodeId']}))['model']
                    measured = (await session.send('CSS.getComputedStyleForNode', {'nodeId': node['nodeId']}))['computedStyle']
                    relevant = set(asset['css']) | {'font-size','font-weight','line-height','color','background-color',
                                                   'opacity','animation-name','animation-duration','animation-direction'}
                    asset['computed'] = [value for value in measured if value['name'] in relevant]
                except Exception as error:
                    asset['measurement_error'] = str(error)[:100]
        return result
    finally:
        await session.detach()


def compare(reference: dict, built: dict, tolerance: float = 1.5) -> dict:
    """Same viewport and frozen animation phase. Report each box/gap/property separately."""
    checks = []
    for sid, section in reference.items():
        actual = built.get(sid, {})
        for prop in ('x', 'y', 'w', 'h'):
            want, got = section['box'][prop], actual.get('box', {}).get(prop)
            checks.append({'section': sid, 'asset': 'section', 'property': prop, 'reference': want, 'built': got,
                           'delta': round(got-want, 3) if got is not None else None,
                           'pass': got is not None and abs(got-want)<=tolerance})
        by_id = {a['id']: a for a in actual.get('assets', [])}
        for asset in section.get('assets', []):
            other = by_id.get(asset['id'])
            if other is None:
                checks.append({'section': sid, 'asset': asset['id'], 'property': 'present', 'pass': False})
                continue
            if asset.get('tag') == 'canvas':
                checks.append({'section': sid, 'asset': asset['id'], 'property': 'scene-reconstructed',
                               'reference': 'source geometry/model + animation',
                               'built': other.get('renderer_state') if asset.get('scene') else 'snapshot / unresolved canvas',
                               'pass': bool(asset.get('scene')) and other.get('renderer_state') == 'ready'})
            # Relative to section, so a mismatch above does not obscure the asset's local layout.
            for prop in ('x', 'y', 'w', 'h'):
                origin = 'x' if prop == 'x' else 'y' if prop == 'y' else None
                want = asset['box'][prop] - (section['box'][origin] if origin else 0)
                got = other['box'][prop] - (actual['box'][origin] if origin else 0)
                checks.append({'section': sid, 'asset': asset['id'], 'property': prop, 'reference': want,
                               'built': got, 'delta': round(got-want, 3), 'pass': abs(got-want) <= tolerance})
            for prop in ('row-gap', 'column-gap', 'display', 'grid-template-columns', 'margin-top', 'margin-left'):
                want, got = asset['css'].get(prop), other['css'].get(prop)
                checks.append({'section': sid, 'asset': asset['id'], 'property': prop,
                               'reference': want, 'built': got, 'pass': want == got})
            for i, parent in enumerate(asset.get('parents', [])):
                other_parent = next((p for p in other.get('parents', []) if p['path'] == parent['path']), None)
                for prop in ('row-gap', 'column-gap', 'padding-top', 'padding-left', 'grid-template-columns', 'align-items', 'justify-content'):
                    want, got = parent['css'].get(prop), (other_parent or {}).get('css', {}).get(prop)
                    checks.append({'section': sid, 'asset': asset['id'], 'property': f'parent[{i}].{prop}',
                                   'reference': want, 'built': got, 'pass': want == got})
    passed = sum(c['pass'] for c in checks)
    return {'passed': passed, 'total': len(checks), 'checks': checks,
            'pct': round(100*passed/len(checks), 1) if checks else None}


async def audit(reference_page, built_page, sections: list) -> dict:
    """Master Cursor reads F12-style evidence in both pages at the same viewport and animation phase."""
    from chromaswarm.clone.components import FREEZE_JS
    selectors = {s.id: s.reference['selector'] for s in sections if s.reference.get('selector')}
    if not selectors:
        return {'passed': 0, 'total': 0, 'checks': [], 'pct': None}
    await reference_page.mouse.move(0, 0)
    await built_page.mouse.move(0, 0)
    await reference_page.evaluate('''(selectors) => {for(const [id,selector] of Object.entries(selectors)) {
      const e=document.querySelector(selector); if(e)e.setAttribute('data-cs-block',id);
    }}''', selectors)
    await reference_page.evaluate(FREEZE_JS)
    await built_page.evaluate(FREEZE_JS)
    reference = await inspect(reference_page, list(selectors), capture=False)
    built = await inspect(built_page, list(selectors), built=True)
    return {**compare(reference, built), 'viewport': built_page.viewport_size, 'reference': reference, 'built': built}
