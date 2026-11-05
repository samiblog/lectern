"""HTML 문서(iframe) 안의 F6·뒤로 기록, 엑셀 화면의 Ctrl+Shift+→"""
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402



base = Path(tempfile.mkdtemp(prefix='lec-last-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
filler = ''.join(f'<h2 id="s{i}">절 {i}</h2>' + '<p>긴 문단입니다. 긴 문단입니다.</p>' * 30 for i in range(1, 6))
(proj / 'page.html').write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>쪽</title></head><body><h1>HTML 쪽</h1><p><a href="#s4">절 4 로</a></p>{filler}</body></html>', encoding='utf-8')
(proj / 'a.md').write_text('# 문서\n\n글\n', encoding='utf-8')
rows = ('<row r="1"><c r="A1" t="inlineStr"><is><t>품목</t></is></c><c r="B1"><v>1</v></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>구리</t></is></c><c r="B2"><v>2</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>니켈</t></is></c><c r="B3"><v>3</v></c></row>')
make_xlsx(proj / 'data' / '가격.xlsx', [('1분기', rows, None)])

server, url, port = serve(proj, base / 'config')

IN_TERM = "!!document.activeElement?.closest('#lec-term')"
ROWS = "[...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')].map((r) => r.textContent).join('')"
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')

        def wait(js, ms=5000):
            try:
                page.wait_for_function(js, timeout=ms)
                return True
            except Exception:
                return False

        top = lambda: page.evaluate("document.querySelector('#lec-content').scrollTop")
        settle = lambda ms=250: page.wait_for_timeout(ms)
        print('[HTML 문서]')
        page.locator('#lec-tree .row.file[data-doc="page.html"]').click(modifiers=['Alt'])
        wait("!!document.querySelector('iframe.lec-html')", 8000)
        settle(800)
        frame = page.frame_locator('iframe.lec-html')
        frame.locator('h1').click()
        page.evaluate("document.querySelector('#lec-content').scrollTop = 300")
        settle()
        t0 = top()
        page.locator('#lec-toc a[data-i]', has_text='절 4').click()
        settle()
        t1 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('목차로 뛴 뒤 Alt+← 로 읽던 자리', t1 > t0 + 500 and abs(top() - t0) <= 2, (t0, t1, top()))
        page.evaluate("document.querySelector('#lec-content').scrollTop = 0")
        settle()
        frame.locator('a', has_text='절 4 로').click()
        settle()
        t2 = top()
        frame.locator('h2', has_text='절 4').click()   # 초점을 iframe 안에 — 뛴 곳을 눌러 스크롤이 움직이지 않게
        settle(150)
        t3 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        still = page.evaluate("import('/static/js/store.js').then((m) => [m.S.view.type, m.S.view.path])")
        check('iframe 안의 링크로 뛴 뒤 iframe 안에서 Alt+← (문서는 그대로)', t2 > 500 and abs(t3 - t2) <= 2 and abs(top()) <= 2 and still == ['doc', 'page.html'], (t2, t3, top(), still))
        page.keyboard.press('Alt+ArrowRight')
        settle()
        check('Alt+→ 로 다시 뛴 곳', abs(top() - t2) <= 2, (t2, top()))
        frame.locator('h1').click()
        page.keyboard.press('F6')
        check('iframe 안에서 F6 은 터미널로', wait(IN_TERM, 15000), page.evaluate("document.activeElement.tagName"))
        wait(f"{ROWS}.includes('PS ')", 20000)
        page.keyboard.press('F6')
        settle(500)
        check('돌아오면 문서 칸으로', page.evaluate("document.activeElement?.id === 'lec-content'"), page.evaluate("document.activeElement.id || document.activeElement.tagName"))
        print('[엑셀 화면]')
        page.evaluate("import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/가격.xlsx' }))")
        wait("!!document.querySelector('#lec-view tr.cv-line')", 8000)
        settle(400)
        page.locator('#lec-view tr.cv-line', has_text='구리').click()
        page.keyboard.press('Control+Shift+ArrowRight')
        got = wait(f"{ROWS}.includes(\"@data/가격.xlsx '1분기' 시트 2행\")", 6000)
        check("Ctrl+Shift+→ 는 '시트'가 든 위치를 넣고 터미널로", got and wait(IN_TERM, 3000), page.evaluate(ROWS)[-80:])
        page.keyboard.press('Escape')
        page.keyboard.press('F6')
        wait("document.activeElement?.id === 'lec-content'", 3000)
        page.locator('#lec-view tr.cv-line', has_text='니켈').click(modifiers=['Shift'])
        settle(200)
        page.keyboard.press('F2')
        told = wait("document.querySelector('#lec-toast').textContent.includes('엑셀 보기는 보기만')", 3000)
        check('엑셀 화면의 F2 는 열지 않고 까닭을 알림', told and page.locator('#lec-view .lec-line-edit').count() == 0)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    stop(server, base)
report()
