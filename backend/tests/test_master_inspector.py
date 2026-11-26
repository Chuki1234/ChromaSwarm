import asyncio

from playwright.async_api import async_playwright

from chromaswarm.clone.components import FREEZE_JS
from chromaswarm.clone.master_inspector import compare, inspect, capture_panels
from chromaswarm.mcp_motion.client import build_special_assets
from chromaswarm.mcp_motion.special import build_special


def test_devtools_layout_roundtrip_and_gap_regression(tmp_path):
    source = tmp_path / 'reference.html'
    source.write_text('''<html><head><style>
      body{margin:0} .hero{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));padding-top:110px;min-height:900px}
      .words{grid-column:span 3;padding:80px 64px}.visual{grid-column:span 2;overflow:hidden}
      .columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75vw}
      .track{display:flex;flex-direction:column;gap:1vw;animation:slide 30s linear infinite}
      .track:nth-child(2){animation-direction:reverse}.card{height:160px;background:green}
      @keyframes slide{from{transform:translateY(0)}to{transform:translateY(-50%)}}
      @media(max-width:700px){.hero{grid-template-columns:1fr}.words,.visual{grid-column:span 1}}
      </style></head><body><section data-cs-block="hero" class="hero"><div class="words">Heading</div>
      <div class="visual"><div class="columns"><div class="track"><div class="card"></div><div class="card"></div></div>
      <div class="track"><div class="card"></div><div class="card"></div></div></div></div>
      <script>window.untrusted = true</script><img style="position:absolute;width:1px;height:1px" onerror="alert(1)" src="javascript:alert(1)"></section></body></html>''', encoding='utf-8')

    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            ref = await browser.new_page(viewport={'width':1440,'height':900})
            await ref.goto(source.as_uri())
            await ref.evaluate(FREEZE_JS)
            captured = (await inspect(ref, ['hero']))['hero']
            assert captured['assets'] and all(a.get('box_model') for a in captured['assets'])
            assert '<script' not in captured['html'] and 'onerror' not in captured['html'] and 'javascript:' not in captured['html']
            assert '0.75vw' in captured['css'] and '@media' in captured['css']
            clone = await browser.new_page()
            html = captured['html'].replace('<section ', '<section data-swarm-section="hero" ', 1)
            for width in (1440, 2032, 375):
                await ref.set_viewport_size({'width':width,'height':900})
                await clone.set_viewport_size({'width':width,'height':900})
                await clone.set_content('<style>body{margin:0}@scope ([data-swarm-section="hero"]) {'+captured['css']+'}</style>'+html)
                await ref.evaluate(FREEZE_JS)
                await clone.evaluate(FREEZE_JS)
                expected = await inspect(ref, ['hero'], cdp=False)
                actual = await inspect(clone, ['hero'], built=True, cdp=False)
                report = compare(expected, actual)
                assert report['total'] > 20 and report['passed'] == report['total'], [c for c in report['checks'] if not c['pass']]
            await clone.add_style_tag(content='.track{gap:100px!important}')
            changed = compare(expected, await inspect(clone, ['hero'], built=True, cdp=False))
            assert any(not c['pass'] and c['property']=='row-gap' for c in changed['checks'])
            await browser.close()
    asyncio.run(go())


def test_threejs_special_asset_uses_real_mcp_and_requires_scene_data():
    scene = {'objects':[{'geometry':'box','size':[1,2,1],'color':'#00ae34'}],
             'tracks':[{'object':0,'property':'rotation','from':[0,0,0],'to':[0,6.283,0],'duration':5}]}
    effects = asyncio.run(build_special_assets('hero', [{'id':'a-canvas','scene':scene}]))
    assert len(effects)==1 and effects[0].kind=='3d-threejs'
    assert effects[0].dependencies['three']
    code = next(f['content'] for f in effects[0].files if f['path'].endswith('/ThreeAsset.tsx'))
    assert 'WebGLRenderer' in code and 'GLTFLoader' in code and 'ResizeObserver' in code
    assert 'setAnimationLoop(null)' in code and 'dispose()' in code and 'prefers-reduced-motion' in code
    assert 'error' in build_special('hero','a-canvas',{})
    assert 'error' in build_special('hero','a-canvas',{'model_url':'javascript:alert(1)'})


def test_lazy_disclosure_is_read_and_the_initial_state_is_restored():
    async def go():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.set_content('''<style>section{display:block}</style><section data-cs-block="faq">
              <h2><button aria-controls="answer" aria-expanded="false">Question</button></h2></section>
              <script>document.querySelector('button').onclick=function(){
                const open=this.getAttribute('aria-expanded')==='true';this.setAttribute('aria-expanded',String(!open));
                if(open)document.getElementById('answer').remove();
                else this.closest('section').insertAdjacentHTML('beforeend','<div id="answer">Actual source answer</div>');
              }</script>''')
            captured = await inspect(page, ['faq'])
            await capture_panels(page, captured)
            assert 'Actual source answer' in captured['faq']['panels']['answer']
            assert await page.locator('button').get_attribute('aria-expanded')=='false'
            assert await page.locator('#answer').count()==0
            await browser.close()
    asyncio.run(go())


def test_document_height_is_not_copied_to_each_section_root():
    async def go():
        async with async_playwright() as pw:
            browser=await pw.chromium.launch()
            ref=await browser.new_page(viewport={'width':1440,'height':900})
            await ref.set_content('<style>html{min-height:100vh;line-height:1.5}body{margin:0}header{height:32px}</style><header data-cs-block="header">Header</header>')
            captured=(await inspect(ref,['header']))['header']
            built=await browser.new_page(viewport={'width':1440,'height':900})
            html=captured['html'].replace('<header ','<header data-swarm-section="header" ',1)
            await built.set_content('<style>body{margin:0}@scope ([data-swarm-section="header"]){'+captured['css']+'}</style>'+html)
            actual=(await inspect(built,['header'],built=True))['header']
            assert actual['box']['h']==32
            assert await built.locator('header').evaluate('(e)=>getComputedStyle(e).lineHeight')=='24px'
            await browser.close()
    asyncio.run(go())


def test_marquee_section_uses_the_clipped_frame_not_the_moving_track_center():
    from chromaswarm.clone.motion_check import build_report
    boxes={'hero':{'top':0,'height':900},'bento':{'top':900,'height':900}}
    post={'marquee':[{'top':-500,'h':3000,'w':280,'axis':'y','cycle':30,'reverse':False,'clip':{'top':110,'h':790}},
                     {'top':300,'h':2000,'w':280,'axis':'y','cycle':30,'reverse':True,'clip':{'top':110,'h':790}}]}
    report=build_report(boxes,[],post,[],0)
    vertical=[i for i in report.items if i.effect=='marquee-vertical']
    assert len(vertical)==1 and vertical[0].section=='hero'
    assert '2 cột' in vertical[0].how and 'ngược chiều' in vertical[0].how


def test_clone_cannot_pass_when_special_assets_were_not_audited():
    from chromaswarm.clone.verdict import judge
    from chromaswarm.state_machine.pipeline_state import CloneSource, PipelineState
    state=PipelineState(session_id='unverified',qa_passed=True,
        clone=CloneSource(url='https://example.com',sections=[{'id':'hero','reference':{'assets':[{'id':'a-root'}]}}]))
    result=judge(state,{'passed':1,'total':1,'pct':100,'sections':[]})
    assert result.status=='failed' and 'special assets' in result.title


def test_devtools_snapshot_checkpoint_is_small_and_lossless():
    import json
    from chromaswarm.agents.planner import Section
    reference={'html':'<section>Original content</section>','css':'.grid{gap:.75vw}',
               'assets':[{'id':f'a-{i}','css':{'gap':'1vw','margin-top':'110px'},'computed':[{'name':'display','value':'grid'}]*50} for i in range(80)]}
    section=Section(id='hero',name='Hero',structure='hero-text',content='x',reference=reference)
    saved=section.model_dump()
    assert len(json.dumps(saved['reference'])) < len(json.dumps(reference)) / 5
    assert Section.model_validate(saved).reference==reference
