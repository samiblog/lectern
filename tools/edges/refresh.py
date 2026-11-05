"""자동 새로고침과 고른 글 (D94): 글이 같으면 다시 그리지 않고, 끄는 동안은 놓을 때까지 미룬다. 꼭 그려야 하는 길은 그대로 그린다"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

TEXT = '# 새로고침\n\n첫 문단은 **굵게** 한 줄입니다.\n\n둘째 문단입니다.\n\n## 절\n\n셋째 문단입니다.\n'
base = Path(tempfile.mkdtemp(prefix='lec-refresh-'))
proj = base / 'proj'
proj.mkdir()
doc = proj / '가.md'
doc.write_text(TEXT, encoding='utf-8')
(proj / '나.md').write_text('# 나\n\n오류검색어\n', encoding='utf-8')
(proj / 'app.py').write_text('print("오류검색어")\n', encoding='utf-8')
(proj / '표.csv').write_text('a,b\n1,2\n', encoding='utf-8')
html_doc = proj / '보고.html'
html_doc.write_text('<!doctype html><html><body><h1>보고</h1><p>처음 글</p></body></html>', encoding='utf-8')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)

SPY = """() => {
  window.__swaps = 0;
  new MutationObserver((ms) => { for (const m of ms) if (m.target.id === 'lec-view' && m.removedNodes.length >= 3) window.__swaps += 1; })
    .observe(document.body, { subtree: true, childList: true });
}"""
WATCH = 2300   # 감시가 알리고 1초 주기가 돌 때까지


def read():
    for _ in range(100):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.02)   # 저장이 파일을 바꿔 끼우는 순간
    return ''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="가.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("새로고침")')
        page.wait_for_timeout(1500)
        page.evaluate(SPY)
        first = page.locator('#lec-view p', has_text='첫 문단')
        swaps = lambda: page.evaluate('window.__swaps')
        chosen = lambda: page.evaluate('getSelection().toString().trim()')
        clear = lambda: page.evaluate('getSelection().removeAllRanges()')

        def until(want, ms=6000):
            end = time.time() + ms / 1000
            while time.time() < end and read() != want:
                time.sleep(0.02)
            return read() == want

        def save(old, new):
            """한 줄 편집으로 저장. 파일에 닿을 때까지"""
            page.locator('#lec-view p', has_text=old).click()
            page.keyboard.press('F2')
            page.wait_for_selector('#lec-view .lec-line-edit')
            page.keyboard.press('End')
            page.keyboard.type(new)
            page.keyboard.press('Enter')

        def back_to(text):
            doc.write_text(text, encoding='utf-8')
            page.wait_for_timeout(WATCH)
            clear()

        # --- 저장한 뒤
        before = swaps()
        save('둘째 문단', '더')
        saved = until(TEXT.replace('둘째 문단입니다.', '둘째 문단입니다.더'))
        page.wait_for_selector('#lec-view p:has-text("입니다.더")')
        page.wait_for_timeout(WATCH)
        check('저장 한 번에 화면은 한 번만 그린다 (감시가 또 알려도)', saved and swaps() - before == 1, swaps() - before)
        lost = 0
        for i in range(5):
            text = read()
            save('둘째 문단', str(i))
            until(text.replace('입니다.더', f'입니다.더{i}', 1))
            page.wait_for_selector(f'#lec-view p:has-text("입니다.더{i}")')
            first.click(click_count=3)
            page.wait_for_timeout(1600)
            lost += not chosen().startswith('첫 문단')
            clear()
            back_to(TEXT.replace('둘째 문단입니다.', '둘째 문단입니다.더'))
        check('저장한 바로 뒤에 고른 글이 사라지지 않는다', lost == 0, f'{lost}/5')
        back_to(TEXT)

        # --- 글이 같을 때
        first.click(click_count=3)
        before = swaps()
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH)
        check('글은 그대로 파일만 다시 쓰이면 그리지 않고 고른 글이 남는다', swaps() == before and chosen().startswith('첫 문단'), [swaps() - before, chosen()])
        doc.write_bytes(TEXT.replace('\n', '\r\n').encode('utf-8'))
        page.wait_for_timeout(WATCH)
        check('줄바꿈 종류만 달라져도 그대로', swaps() == before and chosen().startswith('첫 문단'), swaps() - before)
        doc.write_bytes(b'\xef\xbb\xbf' + TEXT.encode('utf-8'))
        page.wait_for_timeout(WATCH)
        check('BOM 만 달라져도 그대로', swaps() == before, swaps() - before)
        doc.write_text(TEXT, encoding='utf-8')
        os.utime(doc, (1_577_934_000, 1_577_934_000))
        page.wait_for_timeout(WATCH)
        check('그리지 않아도 상태줄의 수정 시각은 고친다', swaps() == before and '2020' in page.text_content('#lec-st-info'), page.text_content('#lec-st-info'))
        clear()

        # --- 꼭 그려야 하는 길
        before = swaps()
        doc.write_text(TEXT.replace('셋째 문단', '바뀐 문단'), encoding='utf-8')
        page.wait_for_selector('#lec-view p:has-text("바뀐 문단")', timeout=5000)
        check('글이 바뀌면 그린다', swaps() - before == 1, swaps() - before)
        back_to(TEXT)
        page.wait_for_selector('#lec-view p:has-text("셋째 문단")', timeout=5000)
        before = swaps()
        page.keyboard.press('F5')
        page.wait_for_timeout(900)
        check('F5 는 글이 같아도 그린다', swaps() - before == 1, swaps() - before)
        before = swaps()
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('refresh-view'))")   # 스타일·설정이 부르는 길
        page.wait_for_timeout(700)
        check('스타일·설정의 다시 그리기는 글이 같아도 그린다', swaps() - before == 1, swaps() - before)

        # 그리는 중에 감시가 같은 글을 알려도 그리던 것이 버려지지 않는다
        page.evaluate("""() => { const real = window.fetch; window.__realFetch = real;
          window.fetch = (u, o) => (String(u).includes('/doc/') ? new Promise((r) => setTimeout(r, 500)).then(() => real(u, o)) : real(u, o)); }""")
        before = swaps()
        page.evaluate("""import('/static/js/store.js').then(({ emit, S }) => { emit('refresh-view', S.pane); setTimeout(() => emit('refresh-auto', S.pane), 100); })""")
        page.wait_for_timeout(1700)
        page.evaluate('window.fetch = window.__realFetch')
        check('그리는 중에 들어온 자동 새로고침이 그리던 것을 버리지 않는다', swaps() - before == 1, swaps() - before)

        # --- 끄는 동안
        box = first.bounding_box()
        y = box['y'] + box['height'] / 2

        def drag_start():
            page.mouse.move(box['x'] + 5, y)
            page.mouse.down()
            page.mouse.move(box['x'] + 120, y, steps=5)

        def drag_end():
            page.mouse.move(box['x'] + 160, y, steps=3)
            page.mouse.up()

        before = swaps()
        drag_start()
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH)
        drag_end()
        page.wait_for_timeout(500)
        check('끄는 동안 글이 같은 쓰기가 오면 고르는 시작점이 그대로', swaps() == before and chosen().startswith('첫 문단'), [swaps() - before, chosen()])
        clear()
        drag_start()
        doc.write_text(TEXT.replace('셋째 문단', '끄는 중 바뀜'), encoding='utf-8')
        page.wait_for_timeout(WATCH)
        held = [swaps() - before, page.locator('#lec-view p:has-text("끄는 중 바뀜")').count()]
        drag_end()
        page.wait_for_selector('#lec-view p:has-text("끄는 중 바뀜")', timeout=3000)
        check('끄는 동안 글이 바뀌면 놓을 때까지 미루고 놓으면 그린다', held == [0, 0] and swaps() - before == 1, held)
        back_to(TEXT)
        before = swaps()
        drag_start()
        doc.write_text(TEXT.replace('셋째 문단', '창을 떠남'), encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.evaluate("window.dispatchEvent(new Event('blur'))")
        page.wait_for_selector('#lec-view p:has-text("창을 떠남")', timeout=3000)
        page.mouse.up()
        check('끄다가 창을 떠나도 미룬 것을 그린다', swaps() - before == 1, swaps() - before)
        back_to(TEXT)
        before = swaps()
        first.click()
        doc.write_text(TEXT.replace('셋째 문단', '누른 뒤 바뀜'), encoding='utf-8')
        page.wait_for_selector('#lec-view p:has-text("누른 뒤 바뀜")', timeout=5000)
        check('눌렀다 놓은 뒤에는 미루지 않는다', swaps() - before == 1, swaps() - before)
        back_to(TEXT)

        # 놓는 것을 놓쳐도 자동 새로고침이 멈춘 채 남지 않는다
        before = swaps()
        drag_start()
        doc.write_text(TEXT.replace('셋째 문단', '놓침'), encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.evaluate("window.dispatchEvent(new MouseEvent('mousemove', { buttons: 0 }))")
        page.wait_for_selector('#lec-view p:has-text("놓침")', timeout=3000)
        page.mouse.up()
        check('놓는 것을 놓쳐도 다음 마우스 움직임에서 그린다', swaps() - before == 1, swaps() - before)
        back_to(TEXT)

        # --- html 문서: 틀 안을 눌러도 자동 새로고침이 멈추지 않는다 (틀은 mousedown 만 전달한다)
        page.locator('#lec-tree .row.file[data-doc="보고.html"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view iframe')
        frame = page.frame_locator('#lec-view iframe')
        frame.locator('h1').click()
        frame.locator('p').click()
        page.wait_for_timeout(300)
        html_doc.write_text(html_doc.read_text(encoding='utf-8').replace('처음 글', '틀을 누른 뒤 바뀜'), encoding='utf-8')
        frame.locator('p:has-text("틀을 누른 뒤 바뀜")').wait_for(timeout=5000)
        check('html 틀 안을 누른 뒤에도 자동 새로고침이 된다', True)
        html_doc.write_text(html_doc.read_text(encoding='utf-8').replace('틀을 누른 뒤 바뀜', '또 바뀜'), encoding='utf-8')
        frame.locator('p:has-text("또 바뀜")').wait_for(timeout=5000)
        check('html 문서는 전처럼 바뀔 때마다 그린다', True)
        page.locator('#lec-tree .row.file[data-doc="가.md"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("새로고침")')
        page.wait_for_timeout(1200)

        # --- 한 줄 편집 중
        before = swaps()
        first.click()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.keyboard.press('Escape')
        page.wait_for_timeout(600)
        check('한 줄 편집 중에 글이 같은 쓰기가 오면 끝낸 뒤에도 그리지 않는다', swaps() == before, swaps() - before)
        page.locator('#lec-view h1').click()
        first.click()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        doc.write_text(TEXT.replace('셋째 문단', '편집 중 바뀜'), encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.keyboard.press('Escape')
        page.wait_for_selector('#lec-view p:has-text("편집 중 바뀜")', timeout=3000)
        check('한 줄 편집 중에 글이 바뀌면 끝낸 뒤에 그린다', swaps() - before == 1, swaps() - before)
        back_to(TEXT)

        # --- 이동 중에 바뀜: 옛 글을 받아 그리는 동안 들어온 변경을 이동이 끝난 뒤에 그린다
        page.evaluate("""() => { const real = window.fetch; window.__realFetch = real;
          window.fetch = (u, o) => (String(u).includes('/doc/') ? real(u, o).then((r) => new Promise((done) => setTimeout(() => done(r), 2800))) : real(u, o)); }""")
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path: '가.md', hash: 'new' }))")
        page.wait_for_timeout(200)   # 옛 글을 받은 뒤에 바뀐다
        doc.write_text(TEXT.replace('셋째 문단', '이동 중 바뀜'), encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.evaluate('window.fetch = window.__realFetch')
        page.wait_for_selector('#lec-view p:has-text("이동 중 바뀜")', timeout=5000)
        check('이동 중에 바뀐 글을 놓치지 않는다', True)
        back_to(TEXT)

        # --- 그리는 중에 글이 되돌아감: 그리던 옛 글이 끝에 남지 않는다 ('같은 글'로 건너뛰면 그리던 것이 화면에 남는다)
        page.evaluate("""() => { const real = window.fetch; window.__realFetch = real; let n = 0;
          window.fetch = (u, o) => (String(u).includes('/doc/') && (n += 1) === 2 ? real(u, o).then((r) => new Promise((done) => setTimeout(() => done(r), 2600))) : real(u, o)); }""")
        doc.write_text(TEXT.replace('셋째 문단', '곧 되돌아감'), encoding='utf-8')   # 1번은 비교, 2번은 그리기 (2.6초 붙들림)
        page.wait_for_timeout(1400)
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH + 1000)
        page.evaluate('window.fetch = window.__realFetch')
        shown = page.text_content('#lec-view')
        check('그리는 중에 글이 되돌아가면 옛 글이 남지 않는다', '셋째 문단' in shown and '곧 되돌아감' not in shown, shown[:80])
        back_to(TEXT)

        # --- 파일이 없어짐
        doc.unlink()
        page.wait_for_selector('#lec-view .doc-missing', timeout=5000)
        check('보던 문서가 지워지면 없음 화면', True)
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH)
        page.locator('#lec-tree .row.file[data-doc="가.md"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("새로고침")', timeout=5000)

        # --- 하이라이트 버튼은 현재 위치의 장부터 (화면 맨 위의 장이 아니라)
        doc.write_text('# 첫 장\n\n첫 장 글입니다.\n\n## 둘째 장\n\n둘째 장 글입니다.\n\n## 셋째 장\n\n셋째 장 글입니다.\n', encoding='utf-8')
        page.wait_for_selector('#lec-view h2:has-text("셋째 장")', timeout=5000)
        page.wait_for_timeout(500)
        sharp = lambda: page.evaluate("""[...document.querySelectorAll('#lec-view > .lec-lit')].filter((el) => /장 글입니다/.test(el.textContent)).map((el) => el.textContent.trim())""")
        page.locator('#lec-view p', has_text='셋째 장').click()
        page.wait_for_timeout(200)
        page.click('#lec-btn-spot')
        page.wait_for_timeout(250)
        check('하이라이트 버튼은 작은 화살표가 있는 장을 고른다', sharp() == ['셋째 장 글입니다.'], sharp())
        page.click('#lec-btn-spot')
        page.locator('#lec-view p', has_text='둘째 장').click()
        page.wait_for_timeout(200)
        page.keyboard.press('Alt+h')
        page.wait_for_timeout(250)
        check('Alt+H 도 같다', sharp() == ['둘째 장 글입니다.'], sharp())
        page.keyboard.press('Escape')
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(WATCH)

        # --- 검색이 실패해도 처리되지 않은 오류가 없다 (목록을 기다리는 동안 먼저 실패하는 길)
        errors.clear()
        page.locator('[role=tab][data-tab="search"]').click()
        page.fill('#lec-search-input', '오류검색어')
        page.wait_for_timeout(900)
        page.route('**/api/search?*', lambda r: r.fulfill(status=500, content_type='application/json', body=json.dumps({'error': '주입한 실패'})))
        page.evaluate("""(ms) => { const real = window.fetch;
          window.fetch = (u, o) => (String(u).includes('/api/others?') ? new Promise((r) => setTimeout(r, ms)).then(() => real(u, o)) : real(u, o)); }""", 400)
        page.keyboard.press('F5')
        page.wait_for_timeout(1700)
        info = page.text_content('#lec-search-info')
        check('검색이 실패하면 화면에 알리고 처리되지 않은 오류가 없다', not errors and '주입한 실패' in info, [errors[:2], info])
        page.unroute_all()
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('멈춤')
finally:
    stop(server, base)
report()
