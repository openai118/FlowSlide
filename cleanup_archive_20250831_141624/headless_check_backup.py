import asyncio
from playwright.async_api import async_playwright

async def run():
    p = async_playwright()
    async with p as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        url = 'file:///f:/projects/FlowSlide/ai_config_api_logged.html'
        await page.goto(url)
        # call switchTab to reveal the tab
        await page.evaluate("() => { if(window.switchTab) switchTab('data-backup'); }")
        # wait up to 2s for the tab to measure non-zero height
        try:
            await page.wait_for_function("() => { const el=document.getElementById('data-backup'); if(!el) return false; return (el.offsetHeight||el.getBoundingClientRect().height||el.scrollHeight)>2; }", timeout=2000)
        except Exception:
            # continue and capture measurement even if timed out
            pass
        # measure
        rect = await page.evaluate("() => { const el = document.getElementById('data-backup'); if(!el) return null; const r = el.getBoundingClientRect(); return {w: r.width, h: r.height, oh: el.offsetHeight, sh: el.scrollHeight, style: el.getAttribute('style')}; }")
        print('rect:', rect)
    # collect ancestor chain diagnostics
    anc = await page.evaluate("() => { const el = document.getElementById('data-backup'); if(!el) return null; const out=[]; let cur=el; while(cur){ try{ const cs=getComputedStyle(cur); const r=cur.getBoundingClientRect(); out.push({tag: cur.tagName, id: cur.id||null, cls: cur.className||null, display: cs.display, position: cs.position, overflow: cs.overflow, transform: cs.transform, contain: cs.contain, width: r.width, height: r.height, offsetHeight: cur.offsetHeight, clientHeight: cur.clientHeight, scrollHeight: cur.scrollHeight}); }catch(e){ out.push({tag: cur.tagName, id: cur.id||null, error: String(e)}); } cur=cur.parentElement; } return out; }")
    print('ancestors:')
    import json
    print(json.dumps(anc, indent=2, ensure_ascii=False))
    await browser.close()

if __name__=='__main__':
    asyncio.get_event_loop().run_until_complete(run())
