"""목차 단추 (D208) — 좁은 창(1080px 이하)과 목차가 빈 문서에서도 단추가 듣는다.
- 넓은 창: 누르면 목차를 감추고 다시 누르면 보인다 (설정 toc_visible).
- 좁은 창: 목차는 처음에 감춰 있고 단추도 꺼짐 표시. 누르면 문서 오른쪽 위에 겹쳐 보이고(문서 칸은 그대로), 다시 누르면 감춘다. 설정은 그대로.
  창을 넓히면 원래 자리에, 다시 좁히면 겹친 목차가 남는다. 목차 링크를 누르면 그 절로. 오른쪽 터미널을 연 동안에도.
- 목차가 빈 문서(제목 없는 md·책갈피 없는 PDF)에서 누르면 그렇다고 알린다.
- 오른쪽 터미널 + 넓게 잡은 사이드바·목차·터미널 (사용자의 설정 — 387·376·722px): 문서 칸은 320px 을 지키고 셋이 줄어 창 안에 다 든다,
  앱이 창보다 넓어지지 않는다 (전에는 문서 칸이 0 이 되고 목차가 그 자리를 차지했다). 아래 터미널에서도 목차 단추가 듣는다."""
import json
import shutil
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

HERE = Path(__file__).parent
base = Path(tempfile.mkdtemp(prefix='lec-tocnarrow-'))
proj = base / 'p'
proj.mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n## 첫 절\n\n' + '글\n\n' * 40 + '## 둘째 절\n\n끝 문단.\n', encoding='utf-8', newline='\n')
(proj / '메모.md').write_text('제목 없는 메모 한 줄.\n', encoding='utf-8', newline='\n')
shutil.copy(HERE / 'pdfs' / 'scan.pdf', proj / '스캔.pdf')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')

ST = """() => import('/static/js/store.js').then(({ S }) => { const toc = document.querySelector('#lec-toc'); const r = toc.getBoundingClientRect();
  return { cfg: S.config.toc_visible, shown: getComputedStyle(toc).display !== 'none' && r.width > 0, btn: document.querySelector('#lec-btn-toc').classList.contains('on'),
    over: getComputedStyle(toc).position === 'absolute', w: Math.round(r.width), panes: Math.round(document.querySelector('#lec-panes').getBoundingClientRect().width) }; })"""
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 850})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-toc a', timeout=10000)

        def st():
            return page.evaluate(ST)

        print('[넓은 창]')
        check('목차가 보이고 단추는 켜짐', until(page, lambda: st()['shown'] and st()['btn']), st())
        page.click('#lec-btn-toc')
        check('누르면 감춘다 (설정 toc_visible 꺼짐)', until(page, lambda: not st()['shown'] and not st()['btn'] and st()['cfg'] is False), st())
        page.click('#lec-btn-toc')
        check('다시 누르면 보인다', until(page, lambda: st()['shown'] and st()['cfg'] is True), st())

        print('[좁은 창 — 1000px]')
        page.set_viewport_size({'width': 1000, 'height': 800})
        check('목차는 감춰 있고 단추도 꺼짐 표시 (설정은 그대로)', until(page, lambda: not st()['shown'] and not st()['btn'] and st()['cfg'] is True), st())
        panes = st()['panes']
        page.click('#lec-btn-toc')
        check('누르면 문서 위에 겹쳐 보인다 — 문서 칸 폭은 그대로', until(page, lambda: st()['shown'] and st()['over'] and st()['btn']) and abs(st()['panes'] - panes) <= 1, (st(), panes))
        page.locator('#lec-toc a', has_text='둘째 절').click()
        expect(page, '목차 링크를 누르면 그 절로', "() => { const h = [...document.querySelectorAll('#lec-view h2')].find((e) => e.textContent.includes('둘째 절')); const r = h.getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; }")
        page.click('#lec-btn-toc')
        check('다시 누르면 감춘다 — 설정은 그대로', until(page, lambda: not st()['shown'] and not st()['btn'] and st()['cfg'] is True), st())
        page.click('#lec-btn-toc')
        page.set_viewport_size({'width': 1300, 'height': 850})
        check('넓히면 원래 자리 (겹치지 않음)', until(page, lambda: st()['shown'] and not st()['over']), st())
        page.set_viewport_size({'width': 1000, 'height': 800})
        check('다시 좁히면 겹친 목차가 남는다', until(page, lambda: st()['shown'] and st()['over'] and st()['btn']), st())
        page.click('#lec-btn-toc')

        print('[좁은 창 — 오른쪽 터미널을 연 동안]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ terminal_position: 'side' }))")
        page.click('#lec-btn-term')
        until(page, "() => document.documentElement.classList.contains('term-on')", ms=8000)
        page.wait_for_timeout(400)
        page.click('#lec-btn-toc')
        check('터미널을 연 채로도 누르면 목차가 보인다', until(page, lambda: st()['shown'] and st()['btn']), st())
        page.click('#lec-btn-toc')
        check('다시 누르면 감춘다', until(page, lambda: not st()['shown']), st())
        page.click('#lec-btn-term')
        page.wait_for_timeout(500)

        print('[목차가 빈 문서]')
        page.set_viewport_size({'width': 1300, 'height': 850})
        page.click('#lec-tree .row[data-doc="메모.md"]')
        page.wait_for_timeout(600)
        page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        page.click('#lec-btn-toc')
        if st()['cfg'] is False:
            page.click('#lec-btn-toc')
        check('제목 없는 md 에서 목차를 켜면 알린다', until(page, lambda: '목차로 보일 것이 없습니다' in page.evaluate(TOAST)), page.evaluate(TOAST))
        page.click('#lec-others-head')
        page.click('#lec-others-list .row[data-path="스캔.pdf"]')
        page.wait_for_selector('#lec-view.pdf-view', timeout=15000)
        page.wait_for_timeout(800)
        page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        page.click('#lec-btn-toc')
        if st()['cfg'] is False:
            page.click('#lec-btn-toc')
        check('책갈피 없는 PDF 에서도', until(page, lambda: '목차로 보일 것이 없습니다' in page.evaluate(TOAST)), page.evaluate(TOAST))
        print('[오른쪽 터미널 — 넓게 잡은 폭 (사용자 설정)]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ terminal_position: 'side', sidebar_width: 387, toc_width: 376, terminal_width: 722, toc_visible: true }))")
        LAY = """() => { const r = (s) => document.querySelector(s).getBoundingClientRect(); const toc = r('#lec-toc'), term = r('#lec-term'), panes = r('#lec-panes');
          const wide = [...document.querySelectorAll('body *')].filter((e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.right > innerWidth + 1 && getComputedStyle(e).visibility !== 'hidden'; }).slice(0, 4).map((e) => (e.id || e.className || e.tagName) + ':' + Math.round(e.getBoundingClientRect().right));
          return { wide, body: document.body.scrollWidth, w: innerWidth, panes: Math.round(panes.width), toc: [Math.round(toc.left), Math.round(toc.right)], term: [Math.round(term.left), Math.round(term.right), Math.round(term.width)] }; }"""
        for w in (1400, 1150, 1000):
            page.set_viewport_size({'width': w, 'height': 800})
            page.reload()
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            if page.locator('#lec-docs.closed').count():
                page.click('#lec-docs-head')
            page.click('#lec-tree .row[data-doc="보고서.md"]')
            page.wait_for_selector('#lec-toc a', state='attached', timeout=10000)
            page.click('#lec-btn-term')
            until(page, "() => document.documentElement.classList.contains('term-on')", ms=8000)
            page.wait_for_timeout(400)
            if not st()['shown']:
                page.click('#lec-btn-toc')
            until(page, lambda: st()['shown'])
            lay = until(page, lambda: (x := page.evaluate(LAY)) and x['body'] == w and x, ms=4000) or page.evaluate(LAY)   # 터미널이 줄어든 폭에 글자 칸을 다시 맞출 때까지
            check(f'{w}px — 문서 320px 이상·목차·터미널(280px 이상)이 모두 창 안, 앱이 창보다 넓지 않다',
                  lay and lay['body'] == w and lay['panes'] >= 318 and lay['toc'][1] <= lay['term'][0] + 1 and lay['term'][1] <= w and lay['term'][2] >= 279, lay)
            page.click('#lec-btn-toc')
            check(f'{w}px — 다시 누르면 목차를 감춘다', until(page, lambda: not st()['shown']), st())
            page.click('#lec-btn-term')
            page.wait_for_timeout(400)
        print('[목차를 꺼 둔 채 오른쪽 터미널을 열고 목차 단추 (실제 창 시험이 찾음)]')
        page.set_viewport_size({'width': 1300, 'height': 850})
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ toc_visible: false }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if page.locator('#lec-docs.closed').count():
            page.click('#lec-docs-head')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-toc a', state='attached', timeout=10000)
        check('목차를 꺼 두었다', not st()['shown'] and st()['cfg'] is False, st())
        page.click('#lec-btn-term')
        until(page, "() => document.documentElement.classList.contains('term-on')", ms=8000)
        page.wait_for_timeout(400)
        page.click('#lec-btn-toc')
        check('터미널을 연 채로 누르면 목차가 켜지며 보인다', until(page, lambda: st()['shown'] and st()['btn'] and st()['cfg'] is True), st())
        page.click('#lec-btn-toc')
        check('— 다시 누르면 감춘다', until(page, lambda: not st()['shown']), st())
        page.click('#lec-btn-term')
        page.wait_for_timeout(400)
        print('[아래 터미널 — 좁은 창]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ terminal_position: 'bottom' }))")
        page.set_viewport_size({'width': 1000, 'height': 800})
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if page.locator('#lec-docs.closed').count():
            page.click('#lec-docs-head')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-toc a', state='attached', timeout=10000)
        page.click('#lec-btn-term')
        until(page, "() => document.documentElement.classList.contains('term-on')", ms=8000)
        page.wait_for_timeout(400)
        page.click('#lec-btn-toc')
        lay = until(page, lambda: st()['shown'] and page.evaluate(LAY))
        check('아래 터미널을 연 좁은 창에서도 목차가 보이고 창 안에', lay and lay['toc'][1] <= 1000 and lay['body'] == 1000, lay)
        page.click('#lec-btn-toc')
        check('— 다시 누르면 감춘다', until(page, lambda: not st()['shown']), st())
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
