"""독립창 (D95): 브라우저 모드의 새 창으로 화면 쪽을 본다. 창을 숨기고 보이는 것은 tests/test_windows.py 와 빌드한 창의 시험이 맡는다"""
import json
import shutil
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-solo-'))
proj = base / 'proj'
proj.mkdir()
LONG = '\n\n'.join(f'문단 {i} 입니다.' for i in range(120))
(proj / '가.md').write_text(f'# 첫째\n\n가 문서 본문입니다.\n\n{LONG}\n\n## 끝 절\n\n끝 절의 글입니다.\n', encoding='utf-8')
(proj / '나.md').write_text('# 둘째\n\n나 문서 본문입니다.\n\n[셋째로 가기](다.md)\n\n[끝 절로 가기](가.md#끝-절)\n\n코드는 `app.py` 에 있다.\n', encoding='utf-8')
(proj / '다.md').write_text('# 셋째\n\n다 문서 본문입니다.\n', encoding='utf-8')
(proj / '라.md').write_text('# 넷째\n\n라 문서 본문입니다.\n', encoding='utf-8')
(proj / 'app.py').write_text('print("코드")\n', encoding='utf-8')
other = base / 'other'
other.mkdir()
(other / 'o.md').write_text('# 다른 프로젝트\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)


def api(path):
    return json.load(urllib.request.urlopen(url + path.lstrip('/'), timeout=5))


def saved_docs():
    return api('/api/state')['projects'][0]['position'].get('docs')


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        dialogs = []

        def watch(pg):
            pg.on('pageerror', lambda e: errors.append(str(e)))

        def on_dialog(d):
            dialogs.append(d.message)
            d.accept() if accept[0] else d.dismiss()

        accept = [False]
        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        row = lambda pg, name: pg.locator(f'#lec-tree .row.file[data-doc="{name}"]')
        tabs = lambda pg: pg.evaluate("[...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((t) => t.textContent.trim())")
        menu = lambda pg, name: pg.locator('#lec-menu button', has_text=name)

        def has_tab(pg, title):
            return any(title in x for x in tabs(pg))

        row(page, '가.md').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        row(page, '나.md').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째")')
        row(page, '다.md').click()
        page.wait_for_selector('#lec-view h1:has-text("셋째")')
        page.wait_for_timeout(1900)   # 문서 탭 기록이 서버에 닿는다
        before_docs = saved_docs()
        active = api('/api/state')['active']

        # --- 문서 탭 우클릭: 옮기기
        page.locator('#lec-doctab-list .doc-tab', has_text='나').click(button='right')
        check('문서 탭 메뉴에 새 창으로 옮기기', menu(page, '새 창으로 옮기기').count() == 1)
        with page.expect_popup() as info:
            menu(page, '새 창으로 옮기기').click()
        solo = info.value
        watch(solo)
        solo.on('dialog', on_dialog)
        solo.wait_for_selector('#lec-view h1:has-text("둘째")', timeout=8000)
        page.wait_for_timeout(300)
        check('옮기면 독립창에 그 문서가 열린다', solo.locator('#lec-view p', has_text='나 문서').count() == 1)
        check('옮기면 메인 창의 탭은 사라진다', not has_tab(page, '나'), tabs(page))
        check('메인 창의 다른 탭은 그대로', page.locator('#lec-doctab-list .doc-tab').count() == 2, tabs(page))

        # --- 독립창의 화면
        hidden = lambda pg, sel: pg.locator(sel).count() == 0 or not pg.locator(sel).is_visible()
        check('프로젝트 탭 막대가 없다', hidden(solo, '#lec-tablist') and hidden(solo, '#lec-btn-open'))
        check('터미널·메모·설정·터미널 모음이 없다', all(hidden(solo, s) for s in ('#lec-btn-term', '#lec-btn-notes', '#lec-btn-settings', '#lec-btn-gather')))
        check('사이드바는 기본으로 감춰져 있다', hidden(solo, '#lec-sidebar'))
        check('문서 탭 하나여도 문서 탭 줄이 보인다', solo.locator('#lec-doctabs').is_visible() and solo.locator('#lec-doctab-new').is_visible())
        check('편집·목차 버튼은 있다', solo.locator('#lec-btn-edit').is_visible() and solo.locator('#lec-btn-toc').is_visible())
        solo.keyboard.press('Control+b')
        solo.wait_for_selector('#lec-tree .row.file')
        check('Ctrl+B 로 트리를 꺼낸다', solo.locator('#lec-sidebar').is_visible())

        # --- 독립창에서 문서 열기
        row(solo, '라.md').click()
        solo.wait_for_selector('#lec-view h1:has-text("넷째")')
        check('트리를 누르면 그 창의 새 문서 탭', solo.locator('#lec-doctab-list .doc-tab').count() == 2, tabs(solo))
        check('메인 창의 탭은 늘지 않는다', page.locator('#lec-doctab-list .doc-tab').count() == 2, tabs(page))
        solo.keyboard.press('Control+t')
        solo.wait_for_selector('#lec-palette:not([hidden])')
        solo.keyboard.type('가')
        solo.wait_for_timeout(250)
        solo.keyboard.press('Enter')
        solo.wait_for_selector('#lec-view h1:has-text("첫째")')
        check('Ctrl+T 로도 새 문서 탭', solo.locator('#lec-doctab-list .doc-tab').count() == 3, tabs(solo))

        # --- 메인 창의 것을 바꾸지 않는다
        solo.wait_for_timeout(1900)
        state = api('/api/state')
        check('독립창의 탭이 다음 실행의 문서 탭 기록을 바꾸지 않는다', saved_docs() == before_docs or '라.md' not in (saved_docs() or []), saved_docs())
        check('선택된 프로젝트가 그대로', state['active'] == active)
        solo.keyboard.press('Control+=')
        solo.wait_for_timeout(200)
        cfg = api('/api/config')
        check('글자 크기·사이드바는 설정에 남지 않는다', cfg.get('font_scale', 1) in (1, 1.0, None) and cfg.get('sidebar_visible') is not False, [cfg.get('font_scale'), cfg.get('sidebar_visible')])
        solo.keyboard.press('Control+0')

        # --- 메인 창에만 있는 키
        before_seen = solo.evaluate("document.querySelector('#lec-notes').hidden")
        solo.keyboard.press('Alt+m')
        solo.keyboard.press('Control+`')
        solo.keyboard.press('Control+,')
        solo.wait_for_timeout(300)
        check('메모·터미널·설정 키는 듣지 않는다', before_seen and hidden(solo, '#lec-notes') and hidden(solo, '#lec-term') and hidden(solo, '#lec-settings'))
        solo.keyboard.press('Escape')

        # --- 터미널·메모로 보내기
        calls = []
        solo.on('request', lambda r: calls.append(r.url) if '/api/term' in r.url else None)
        solo.evaluate("import('/static/js/store.js').then(({ emit }) => emit('term-paste', '@보낸위치 '))")
        solo.wait_for_timeout(250)
        told = solo.text_content('#lec-toast')
        check('터미널로 보내면 메인 창에 맡긴다', '메인 창' in told and len(calls) == 1 and calls[0].endswith('/api/term/relay') and hidden(solo, '#lec-term'), [told, calls])
        page.wait_for_selector('#lec-term .xterm', timeout=15000)
        rows = lambda: page.evaluate("document.querySelector('#lec-term .xterm-rows')?.textContent || ''").replace(' ', '')   # 넓은 글자 뒤에 빈 칸이 따라온다
        arrived = False
        for _ in range(120):
            if '@보낸위치' in rows():
                arrived = True
                break
            page.wait_for_timeout(100)
        check('메인 창의 터미널에 들어간다', arrived, rows()[-120:])
        page.wait_for_timeout(600)
        check('Enter 는 누르지 않는다 (명령이 돌지 않는다)', '인식되지' not in rows() and 'not recognized' not in rows() and rows().count('@보낸위치') == 1, rows()[-160:])
        page.keyboard.press('Control+`')
        page.wait_for_timeout(300)
        page.locator('#lec-view h1').first.click()
        solo.evaluate("import('/static/js/store.js').then(({ emit }) => emit('new-note', { body: '독립창의 글' }))")
        page.wait_for_selector('#lec-notes:not([hidden])', timeout=4000)
        check('새 메모로 보내면 메인 창의 메모에 들어간다', '메인 창' in solo.text_content('#lec-toast'), solo.text_content('#lec-toast'))
        for _ in range(60):
            if (proj / '.lectern' / 'notes.md').exists() and '독립창의 글' in (proj / '.lectern' / 'notes.md').read_text(encoding='utf-8'):
                break
            page.wait_for_timeout(100)
        check('메모가 파일에 남는다', '독립창의 글' in (proj / '.lectern' / 'notes.md').read_text(encoding='utf-8'))
        page.keyboard.press('Alt+m')
        page.wait_for_timeout(300)
        page.locator('#lec-view h1').first.click()

        # --- 자동 새로고침과 저장
        (proj / '라.md').write_text('# 넷째\n\n라 문서가 바뀜.\n', encoding='utf-8')
        solo.locator('#lec-doctab-list .doc-tab', has_text='라').click()
        solo.wait_for_selector('#lec-view p:has-text("라 문서가 바뀜")', timeout=5000)
        check('독립창도 자동 새로고침된다', True)
        solo.locator('#lec-view p', has_text='라 문서').click()
        solo.keyboard.press('F2')
        solo.wait_for_selector('#lec-view .lec-line-edit')
        solo.keyboard.press('End')
        solo.keyboard.type('더')
        solo.keyboard.press('Enter')
        solo.wait_for_selector('#lec-view p:has-text("바뀜.더")', timeout=5000)
        row(page, '라.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view p:has-text("바뀜.더")', timeout=5000)
        check('독립창에서 저장한 글이 메인 창에 보인다', True)

        # --- 저장하지 않은 편집
        posted = []
        solo.on('request', lambda r: posted.append(r.post_data or '') if '/api/editing' in r.url else None)
        solo.keyboard.press('Control+e')
        solo.wait_for_selector('.lec-editor')
        solo.wait_for_timeout(300)
        solo.keyboard.press('Control+End')
        solo.keyboard.type('저장 안 함')
        solo.wait_for_timeout(900)
        wid = solo.evaluate("new URLSearchParams(location.search).get('w')")
        check('저장하지 않은 편집을 창 id 로 서버에 알린다', any(wid in x and '.md' in x for x in posted), posted[:2])
        dialogs.clear()
        accept[0] = False
        solo.keyboard.press('Control+Shift+n')
        solo.wait_for_timeout(500)
        check('저장하지 않은 편집이 있으면 옮기기 전에 묻고 아니오면 그대로', len(dialogs) == 1 and len(ctx.pages) == 2, [dialogs, len(ctx.pages)])
        accept[0] = True
        solo.keyboard.press('Control+e')
        solo.wait_for_timeout(400)

        # --- Ctrl+Shift+N
        with page.expect_popup() as info:
            page.keyboard.press('Control+Shift+n')
        solo2 = info.value
        watch(solo2)
        solo2.wait_for_selector('#lec-view h1:has-text("넷째")', timeout=8000)
        check('Ctrl+Shift+N 으로 지금 문서를 옮긴다', not has_tab(page, '라'), tabs(page))
        solo2.close()

        # --- 스크롤 위치
        page.locator('#lec-doctab-list .doc-tab', has_text='가').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        page.evaluate("document.querySelector('#lec-content').scrollTop = 1500")
        page.wait_for_timeout(200)
        with page.expect_popup() as info:
            page.keyboard.press('Control+Shift+n')
        solo3 = info.value
        solo3.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        solo3.wait_for_timeout(500)
        top = solo3.evaluate("document.querySelector('#lec-content').scrollTop")
        check('보던 스크롤 위치로 열린다', abs(top - 1500) < 30, top)
        solo3.close()

        # --- 트리 우클릭: 복사가 아니라 그 문서만 새 창에
        row(page, '나.md').click(button='right')
        check('트리 메뉴에 새 창에서 열기', menu(page, '새 창에서 열기').count() == 1)
        count = page.locator('#lec-doctab-list .doc-tab').count()
        with page.expect_popup() as info:
            menu(page, '새 창에서 열기').click()
        solo4 = info.value
        solo4.wait_for_selector('#lec-view h1:has-text("둘째")', timeout=8000)
        check('트리에서 열면 메인 창은 그대로', page.locator('#lec-doctab-list .doc-tab').count() == count)

        solo4.locator('#lec-view p', has_text='나 문서').click(button='right')
        solo4.wait_for_selector('#lec-menu:not([hidden])')
        check('독립창의 메뉴에도 터미널 버튼이 있다', solo4.locator('#lec-menu [data-term]').count() > 0)
        solo4.keyboard.press('Escape')

        # --- 다시 불러와도 독립창
        solo4.reload()
        solo4.wait_for_selector('#lec-view h1:has-text("둘째")', timeout=8000)
        check('독립창을 다시 불러와도 독립창', hidden(solo4, '#lec-tablist'))
        solo4.close()

        # --- 코드, 폴더 개요
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: 'app.py', newTab: true }))")
        page.wait_for_selector('#lec-view :text("코드")', timeout=6000)
        page.wait_for_timeout(400)   # 칸의 화면이 정해진 뒤에
        with page.expect_popup() as info:
            page.keyboard.press('Control+Shift+n')
        solo5 = info.value
        solo5.wait_for_selector('#lec-view :text("코드")', timeout=8000)
        check('코드 화면도 옮긴다', True)
        solo5.close()
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'overview', path: '' }))")
        page.wait_for_timeout(500)
        pages = len(ctx.pages)
        page.keyboard.press('Control+Shift+n')
        page.wait_for_timeout(400)
        check('폴더 개요는 옮기지 않고 알린다', len(ctx.pages) == pages and '문서나 코드' in page.text_content('#lec-toast'), page.text_content('#lec-toast'))

        # --- 하나뿐인 탭
        for _ in range(8):
            if page.locator('#lec-doctab-list .doc-tab').count() < 2:
                break
            page.keyboard.press('Control+w')
            page.wait_for_timeout(120)
        row(page, '다.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("셋째")')
        with page.expect_popup() as info:
            page.keyboard.press('Control+Shift+n')
        solo6 = info.value
        solo6.wait_for_selector('#lec-view h1:has-text("셋째")', timeout=8000)
        page.wait_for_timeout(500)
        check('메인 창의 하나뿐인 탭을 옮기면 폴더 개요', page.evaluate("import('/static/js/store.js').then(({ S }) => S.view?.type)") == 'overview')
        solo6.keyboard.press('Control+Shift+n')
        solo6.wait_for_timeout(300)
        check('독립창의 하나뿐인 탭은 옮기지 않는다', '하나뿐' in solo6.text_content('#lec-toast'), solo6.text_content('#lec-toast'))

        # --- 창 사이로 보내기
        doc_tabs = lambda pg: pg.locator('#lec-doctab-list .doc-tab').count()
        solo.locator('#lec-doctab-list .doc-tab', has_text='라').click(button='right')
        check('독립창의 탭 메뉴에 메인 창으로 보내기', menu(solo, '메인 창으로 보내기').count() == 1)
        before = doc_tabs(solo)
        menu(solo, '메인 창으로 보내기').click()
        page.wait_for_selector('#lec-view h1:has-text("넷째")', timeout=4000)
        solo.wait_for_timeout(200)
        check('메인 창이 받고 독립창의 탭은 사라진다', doc_tabs(solo) == before - 1 and not has_tab(solo, '라'), tabs(solo))

        page.wait_for_timeout(1300)   # 다른 창들을 알게 된다
        page.locator('#lec-doctab-list .doc-tab', has_text='라').click(button='right')
        check('메인 창의 탭 메뉴에 떠 있는 독립창이 나온다', menu(page, '창으로 보내기').count() == 2, page.locator('#lec-menu').inner_text())
        check('메인 창에는 메인 창으로 보내기가 없다', menu(page, '메인 창으로 보내기').count() == 0)
        menu(page, '다.md 창으로 보내기').click()
        solo6.wait_for_selector('#lec-view h1:has-text("넷째")', timeout=4000)
        check('이미 떠 있는 독립창으로 보낸다 (새 창이 뜨지 않는다)', has_tab(solo6, '라') and len(ctx.pages) == 3, [tabs(solo6), len(ctx.pages)])

        solo6.wait_for_timeout(1300)
        solo6.locator('#lec-doctab-list .doc-tab', has_text='라').click(button='right')
        menu(solo6, '외').first.click()
        solo.wait_for_selector('#lec-view h1:has-text("넷째")', timeout=4000)
        check('독립창끼리도 보낸다', has_tab(solo, '라') and not has_tab(solo6, '라'), [tabs(solo), tabs(solo6)])

        solo.locator('#lec-doctab-list .doc-tab', has_text='가').click()
        solo.wait_for_selector('#lec-view h1:has-text("첫째")')
        solo.evaluate("document.querySelector('#lec-content').scrollTop = 1500")
        solo.wait_for_timeout(200)
        solo.locator('#lec-doctab-list .doc-tab', has_text='가').click(button='right')
        menu(solo, '메인 창으로 보내기').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=4000)
        page.wait_for_timeout(300)
        top = page.evaluate("document.querySelector('#lec-content').scrollTop")
        check('보내도 스크롤 위치가 이어진다', abs(top - 1500) < 30, top)

        solo6.locator('#lec-doctab-list .doc-tab').first.click(button='right')
        menu(solo6, '메인 창으로 보내기').click()
        page.wait_for_selector('#lec-view h1:has-text("셋째")', timeout=4000)
        solo6.wait_for_timeout(300) if not solo6.is_closed() else None
        check('마지막 문서를 보내면 그 독립창은 닫힌다', solo6.is_closed())

        gone = page.evaluate("""() => fetch('/api/window-send', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ to: 'deadbeefdeadbeef', type: 'doc', path: '가.md', top: 0 }) }).then((r) => r.json())""")
        check('닫힌 창으로는 보내지 못한다', gone['ok'] is False, gone)
        page.wait_for_timeout(1300)
        page.locator('#lec-doctab-list .doc-tab', has_text='가').click(button='right')
        check('닫힌 창은 보낼 곳에서 빠진다', menu(page, '창으로 보내기').count() == 1, page.locator('#lec-menu').inner_text())
        page.keyboard.press('Escape')

        # --- 본문 링크
        row(page, '나.md').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째")')
        page.wait_for_timeout(500)
        count = doc_tabs(page)
        page.locator('#lec-view a', has_text='셋째로 가기').click(button='right')
        check('링크 메뉴에 새 창에서 열기', menu(page, '새 창에서 열기').count() == 1)
        with page.expect_popup() as info:
            menu(page, '새 창에서 열기').click()
        link_win = info.value
        link_win.wait_for_selector('#lec-view h1:has-text("셋째")', timeout=8000)
        check('링크를 새 창에서 열어도 메인 창은 그대로', doc_tabs(page) == count and page.locator('#lec-view h1:has-text("둘째")').count() == 1)
        link_win.close()
        page.locator('#lec-view a', has_text='끝 절로 가기').click(button='right')
        with page.expect_popup() as info:
            menu(page, '새 창에서 열기').click()
        link_win = info.value
        link_win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        link_win.wait_for_timeout(500)
        check('절 링크는 그 절로 연다', link_win.evaluate("document.querySelector('#lec-content').scrollTop") > 1000)
        link_win.close()
        page.locator('#lec-view a.path-link, #lec-view code a', has_text='app.py').first.click(button='right')
        with page.expect_popup() as info:
            menu(page, '새 창에서 열기').click()
        link_win = info.value
        link_win.wait_for_selector('#lec-view :text("코드")', timeout=8000)
        check('경로 표기도 새 창에서 연다', True)
        link_win.close()

        # --- 닫기
        n = solo.locator('#lec-doctab-list .doc-tab').count()
        solo.keyboard.press('Control+w')
        solo.wait_for_timeout(250)
        check('Ctrl+W 는 그 창의 문서 탭을 닫는다', solo.is_closed() or solo.locator('#lec-doctab-list .doc-tab').count() == n - 1)
        try:
            for _ in range(n):
                solo.keyboard.press('Control+w')
                solo.wait_for_timeout(250)
        except Exception:
            pass   # 마지막 탭에서 창이 닫혔다
        check('마지막 문서 탭을 닫으면 창이 닫힌다', solo.is_closed())
        check('독립창을 닫아도 프로젝트는 그대로', len(api('/api/state')['projects']) == 1)
        row(page, '나.md').click(button='right')
        with page.expect_popup() as info:
            menu(page, '새 창에서 열기').click()
        solo8 = info.value
        solo8.wait_for_selector('#lec-view h1:has-text("둘째")', timeout=8000)
        try:
            solo8.keyboard.press('Control+Shift+w')
            solo8.wait_for_timeout(400)
        except Exception:
            pass   # 창이 닫혔다
        check('Ctrl+Shift+W 는 창만 닫고 프로젝트를 닫지 않는다', solo8.is_closed() and len(api('/api/state')['projects']) == 1)

        # --- 프로젝트 탭을 닫으면 그 창도
        page.evaluate("(p) => fetch('/api/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) })", str(other))
        page.wait_for_timeout(1600)
        check('다른 프로젝트가 탭으로 열린다', page.locator('#lec-tablist .lec-tab').count() == 2)
        page.locator('#lec-tablist .lec-tab').first.click()
        page.wait_for_timeout(600)
        row(page, '가.md').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        with page.expect_popup() as info:
            page.keyboard.press('Control+Shift+n')
        solo7 = info.value
        solo7.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        page.keyboard.press('Control+Shift+w')
        end = time.time() + 5
        while time.time() < end and not solo7.is_closed():
            page.wait_for_timeout(100)
        check('프로젝트 탭을 닫으면 그 독립창도 닫힌다', solo7.is_closed())
        check('스크립트 오류가 없다', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('멈춤')
finally:
    stop(server, base)
report()
