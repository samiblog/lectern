"""독립창의 여러 상황 (D95): 특수 문자 이름, 같은 문서를 두 창에서, 없어진 문서, 화면 종류, 보기만 하는 프로젝트, 영어, 실패 길"""
import json
import shutil
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop


base = Path(tempfile.mkdtemp(prefix='lec-solo2-'))
proj = base / 'proj'
(proj / 'sub & dir').mkdir(parents=True)
NAME = "a&b 'c' #1 +%20 한글"
MARK = '<i data-xss="1">'
TEXT = '# 첫째\n\n첫 문단입니다.\n\n## 둘째 장\n\n둘째 장 글입니다.\n\n## 셋째 장\n\n셋째 장 글입니다.\n'
doc = proj / '가.md'
doc.write_text(TEXT, encoding='utf-8')
(proj / '나.md').write_text('# 둘째 문서\n\n나 글입니다.\n', encoding='utf-8')
(proj / '심은.md').write_text('# 심은 링크\n\n<a data-lec-open="{깨진 값" data-lec-href="x" href="https://example.com/a">깨진 링크</a>\n\n<a data-lec-open=\'{"type":"doc","path":"나.md"}\' data-lec-href="y" href="https://example.com/b">심은 링크</a>\n', encoding='utf-8')
(proj / f'{NAME}.md').write_text(f'# {MARK} 이상한 이름\n\n글입니다.\n', encoding='utf-8')
(proj / 'sub & dir' / f'{NAME} 둘.md').write_text('# 깊은 곳\n\n글입니다.\n', encoding='utf-8')
(proj / '보고.html').write_text('<!doctype html><html><body><h1>보고</h1><p>html 글</p></body></html>', encoding='utf-8')
(proj / '표.csv').write_text('이름,값\n찾을글,2\n', encoding='utf-8')
(proj / 'app.py').write_text('print("코드글")\n\n\ndef run():\n    return 1\n', encoding='utf-8')
(proj / '발표.md').write_text('---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 둘째 장\n', encoding='utf-8')
other = base / 'other'
other.mkdir()
(other / 'o.md').write_text('# 다른 프로젝트\n\n글\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []


def read(path=doc):
    for _ in range(100):
        try:
            return path.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.02)
    return ''


def until(cond, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.03)
    return False


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        watch = lambda pg: pg.on('pageerror', lambda e: errors.append(str(e)[:160]))
        watch(page)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        row = lambda pg, name: pg.locator(f'#lec-tree .row.file[data-doc="{name}"]')
        menu = lambda pg, name: pg.locator('#lec-menu button', has_text=name)
        tabs = lambda pg: pg.evaluate("[...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((t) => t.textContent.trim())")
        toast = lambda pg: pg.text_content('#lec-toast')

        def popup(pg, act):
            with pg.expect_popup() as info:
                act()
            win = info.value
            watch(win)
            return win

        def window_of(pg, locator):
            locator.click(button='right')
            return popup(pg, lambda: menu(pg, '새 창에서 열기').click())

        # --- 특수 문자가 든 이름
        odd = page.locator('#lec-tree .row.file', has_text='a&b').filter(has_not_text='둘')   # 폴더가 먼저 나온다
        win = window_of(page, odd.first)
        win.wait_for_selector('#lec-view h1:has-text("이상한 이름")', timeout=8000)
        check('특수 문자 이름의 문서가 독립창에 열린다', win.locator('#lec-doctab-list .doc-tab').first.inner_text().strip().startswith('a&b'), tabs(win))
        win.reload()
        win.wait_for_selector('#lec-view h1:has-text("이상한 이름")', timeout=8000)
        check('다시 불러와도 같은 문서', True)
        row(page, '나.md').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째 문서")')
        page.wait_for_timeout(2600)   # 독립창이 알리고 메인 창이 받기까지 (각자 1초 주기)
        page.locator('#lec-doctab-list .doc-tab', has_text='나').click(button='right')
        label = menu(page, '창으로 보내기').first.inner_text()
        check('창 이름의 특수 문자가 글자로 보인다', NAME in label and page.locator('#lec-menu [data-xss]').count() == 0, label)
        menu(page, '창으로 보내기').first.click()
        win.wait_for_selector('#lec-view h1:has-text("둘째 문서")', timeout=4000)
        check('특수 문자 이름의 창으로 보낸다', any('나' in x for x in tabs(win)), tabs(win))
        win.close()
        deep = page.locator('#lec-tree .row.file', has_text='둘.md')
        if deep.count() == 0:
            page.locator('#lec-tree .row.dir [data-toggle]', has=page.locator('text=sub')).first.click()
        deep = page.locator('#lec-tree .row.file', has_text='둘')
        win = window_of(page, deep.last)
        win.wait_for_selector('#lec-view h1:has-text("깊은 곳")', timeout=8000)
        check('특수 문자가 든 폴더 안의 문서', True)
        win.close()

        # --- 문서가 심은 속성은 믿지 않는다
        row(page, '심은.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("심은 링크")')
        page.wait_for_timeout(300)
        shown = []
        for text in ('깨진 링크', '심은 링크'):
            page.locator('#lec-view a', has_text=text).last.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=3000)
            shown.append(menu(page, '새 창에서 열기').count())
            page.keyboard.press('Escape')
        check('문서가 심은 data-lec-open 으로는 새 창 메뉴가 나오지 않고 메뉴도 죽지 않는다', shown == [0, 0], shown)

        # --- 같은 문서를 두 창에서
        row(page, '가.md').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        win = window_of(page, row(page, '가.md'))
        win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        win.wait_for_timeout(500)

        def line_edit(pg, needle, typed):
            pg.locator('#lec-view p', has_text=needle).click()
            pg.keyboard.press('F2')
            pg.wait_for_selector('#lec-view .lec-line-edit')
            pg.keyboard.press('End')
            pg.keyboard.type(typed)

        line_edit(win, '첫 문단', '가')
        win.keyboard.press('Enter')
        check('독립창의 저장이 파일에', until(lambda: '첫 문단입니다.가' in read()))
        page.wait_for_selector('#lec-view p:has-text("입니다.가")', timeout=5000)
        check('같은 문서를 보는 메인 창이 저절로 바뀐다', True)
        page.wait_for_timeout(1200)
        line_edit(page, '첫 문단', '메인')
        line_edit(win, '첫 문단', '독립')
        win.keyboard.press('Enter')
        until(lambda: '입니다.가독립' in read())
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('같은 줄을 두 창에서 고치면 나중 것은 덮어쓰지 않고 클립보드로', '입니다.가독립' in read() and '메인' not in read() and '클립보드' in toast(page), [read()[:40], toast(page)])
        doc.write_text(TEXT, encoding='utf-8')
        page.wait_for_timeout(2300)

        # --- 없어지는 문서
        page.evaluate("""(p) => fetch('/api/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) })""",
                      {'p': page.evaluate("import('/static/js/store.js').then(({ S }) => S.tab.id)"), 'path': '가.md', 'name': '새이름.md'})
        win.wait_for_selector('#lec-view .doc-missing', timeout=6000)
        check('다른 창이 이름을 바꾸면 독립창은 없음 화면', True)
        (proj / '새이름.md').rename(doc)
        win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=7000)
        check('이름이 돌아오면 다시 보인다', True)
        doc.unlink()
        win.wait_for_selector('#lec-view .doc-missing', timeout=6000)
        doc.write_text(TEXT, encoding='utf-8')
        win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=7000)
        check('지워졌다 돌아와도 된다', True)
        win.close()

        # --- 화면 종류
        emit_open = lambda pg, d: pg.evaluate("(d) => import('/static/js/store.js').then(({ emit }) => emit('open', d))", d)
        for kind, path, ready in (('code', 'app.py', '#lec-view :text("코드글")'), ('code', '표.csv', '#lec-view :text("찾을글")'),
                                  ('doc', '보고.html', '#lec-view iframe'), ('doc', '발표.md', '#lec-view.lec-deck')):
            emit_open(page, {'type': kind, 'path': path, 'newTab': True, 'force': True})
            page.wait_for_selector(ready, timeout=7000)
            page.wait_for_timeout(500)
            win = popup(page, lambda: page.keyboard.press('Control+Shift+n'))
            win.wait_for_selector(ready, timeout=8000)
            check(f'{path} 를 독립창으로 옮긴다', True)
            win.close()

        # --- 편집 상자가 열려 있어도 저장할 것이 없으면 묻지 않는다
        dialogs = []
        page.on('dialog', lambda d: (dialogs.append(d.message), d.dismiss()))
        row(page, '나.md').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째 문서")')
        page.wait_for_timeout(400)
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-editor')
        page.wait_for_timeout(300)
        win = popup(page, lambda: page.keyboard.press('Control+Shift+n'))
        win.wait_for_selector('#lec-view h1:has-text("둘째 문서")', timeout=8000)
        check('고치지 않은 편집 상자는 묻지 않고 옮긴다', not dialogs, dialogs)

        # --- 독립창의 도구
        win.wait_for_timeout(500)   # 칸의 화면이 정해진 뒤에
        win.keyboard.press('Control+f')
        win.wait_for_selector('#lec-findbar:not([hidden]) .fb')
        win.keyboard.type('글입니다')
        check('Ctrl+F', until(lambda: '/' in win.text_content('#lec-find-count')), win.text_content('#lec-find-count'))
        win.keyboard.press('Escape')
        win.keyboard.press('Control+g')
        win.wait_for_selector('#lec-palette:not([hidden])')
        check('Ctrl+G', win.input_value('#lec-palette-input') == ':')
        win.keyboard.press('Escape')
        win.keyboard.press('F5')
        win.wait_for_timeout(600)
        check('F5 는 문서를 지키고 알린다', win.locator('#lec-view h1:has-text("둘째 문서")').count() == 1)
        win.keyboard.press('Control+/')
        win.wait_for_selector('#lec-keys:not([hidden])', timeout=3000)
        check('단축키 표에 Ctrl+Shift+N', 'Ctrl' in win.text_content('#lec-keys') and '새 창으로' in win.text_content('#lec-keys'))
        win.keyboard.press('Escape')
        win.keyboard.press('F1')
        win.wait_for_selector('#lec-help-view h1, #lec-help-view h2', timeout=4000)
        check('사용설명서에 독립창', '독립창' in win.text_content('#lec-help-view'))
        win.keyboard.press('Escape')
        win.close()

        # --- 고른 글 (D94) 과 하이라이트 (독립창에서도)
        row(page, '가.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        win = window_of(page, row(page, '가.md'))
        win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        win.wait_for_timeout(600)
        win.locator('#lec-view p', has_text='첫 문단').click(click_count=3)
        doc.write_text(TEXT, encoding='utf-8')
        win.wait_for_timeout(2500)
        check('독립창도 글이 같으면 선택한 글이 남는다', win.evaluate('getSelection().toString()').startswith('첫 문단'))
        win.evaluate('getSelection().removeAllRanges()')
        sharp = lambda pg: pg.evaluate("[...document.querySelectorAll('#lec-view > .lec-lit')].filter((e) => /글입니다/.test(e.textContent)).map((e) => e.textContent.trim())")
        win.locator('#lec-view p', has_text='셋째 장').click()
        win.wait_for_timeout(150)
        win.click('#lec-btn-spot')
        win.wait_for_timeout(250)
        check('독립창의 하이라이트도 화살표의 장', sharp(win) == ['셋째 장 글입니다.'], sharp(win))
        win.click('#lec-btn-spot')
        win.close()
        emit_open(page, {'type': 'code', 'path': 'app.py'})
        page.wait_for_selector('#lec-view :text("코드글")', timeout=6000)
        page.wait_for_timeout(500)
        page.locator('#lec-view .cv-line', has_text='return').click()
        page.wait_for_timeout(150)
        page.click('#lec-btn-spot')
        page.wait_for_timeout(250)
        lit = page.evaluate("(() => { const s = document.querySelector('#lec-st-lit'); return s.hidden ? '' : s.textContent; })()")
        check('코드 화면의 하이라이트는 현재 줄', '5행' in lit, lit)
        page.keyboard.press('Escape')

        # --- 다른 프로젝트의 창은 보낼 곳에 나오지 않는다
        row(page, '가.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        keep = window_of(page, row(page, '나.md'))
        keep.wait_for_selector('#lec-view h1:has-text("둘째 문서")', timeout=8000)
        page.evaluate("(p) => fetch('/api/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) })", str(other))
        page.wait_for_timeout(1700)
        page.locator('#lec-tablist .lec-tab').nth(1).click()
        page.wait_for_selector('#lec-tree .row.file[data-doc="o.md"]', timeout=6000)
        row(page, 'o.md').click()
        page.wait_for_selector('#lec-view h1:has-text("다른 프로젝트")')
        page.wait_for_timeout(1400)
        page.locator('#lec-doctab-list .doc-tab', has_text='o').first.click(button='right')
        check('다른 프로젝트의 독립창은 보낼 곳에 없다', menu(page, '창으로 보내기').count() == 0, page.locator('#lec-menu').inner_text())
        page.keyboard.press('Escape')
        page.locator('#lec-tablist .lec-tab').first.click()
        page.wait_for_timeout(500)

        # --- 메인 창이 다른 프로젝트를 보면 받지 않는다
        page.locator('#lec-tablist .lec-tab').nth(1).click()
        page.wait_for_timeout(500)
        keep.evaluate("import('/static/js/store.js').then(({ emit }) => emit('term-paste', '@다른곳 '))")
        ok = False
        for _ in range(40):
            if '다른 프로젝트' in toast(page):
                ok = True
                break
            page.wait_for_timeout(100)
        check('메인 창이 다른 프로젝트를 보면 터미널 글을 받지 않는다', ok and page.locator('#lec-term .xterm').count() == 0, toast(page))
        page.locator('#lec-tablist .lec-tab').first.click()
        page.wait_for_timeout(500)

        # --- 보내기 실패
        keep.route('**/api/window-send', lambda r: r.fulfill(status=500, content_type='application/json', body='{"error":"주입"}'))
        keep.locator('#lec-doctab-list .doc-tab').first.click(button='right')
        menu(keep, '메인 창으로 보내기').click()
        keep.wait_for_timeout(1500)
        check('보내기가 실패하면 알리고 탭을 지킨다', not keep.is_closed() and '보내지 못했습니다' in toast(keep), toast(keep))
        keep.unroute_all()
        keep.close()

        # --- 메인 창을 다시 불러와도 독립창의 흔적이 없다
        row(page, '가.md').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        page.wait_for_timeout(1800)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', timeout=8000)
        page.wait_for_selector('#lec-view h1', timeout=8000)
        check('메인 창을 다시 불러오면 메인 창의 문서', page.locator('#lec-tablist .lec-tab').count() == 2 and len(ctx.pages) == 1, [page.locator('#lec-tablist .lec-tab').count(), len(ctx.pages)])
        check('스크립트 오류가 없다', not errors, errors[:3])
        ctx.close()

        # --- 보기만 하는 프로젝트
        s2, url2, _ = serve(ROOT / 'samples', base / 'c2')
        extra.append(s2)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = ctx.new_page()
        watch(page)
        page.goto(url2)
        page.wait_for_selector('#lec-tree .row.file')
        row(page, 'README.md').click()
        page.wait_for_selector('#lec-view h1')
        page.wait_for_timeout(500)
        win = window_of(page, row(page, 'README.md'))
        win.wait_for_selector('#lec-view h1', timeout=8000)
        win.wait_for_timeout(500)
        win.locator('#lec-view p').first.click()
        win.keyboard.press('F2')
        win.wait_for_timeout(300)
        check('보기만 하는 프로젝트의 독립창에서 F2 는 열리지 않고 알린다', win.locator('.lec-line-edit').count() == 0 and '보기만' in toast(win), toast(win))
        win.close()
        ctx.close()

        # --- 영어
        c3 = base / 'c3'
        c3.mkdir()
        (c3 / 'config.json').write_text(json.dumps({'language': 'en', 'theme': 'dracula'}), encoding='utf-8')
        s3, url3, _ = serve(proj, c3)
        extra.append(s3)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = ctx.new_page()
        watch(page)
        page.goto(url3)
        page.wait_for_selector('#lec-tree .row.file')
        row(page, '가.md').click()
        page.wait_for_selector('#lec-view h1:has-text("첫째")')
        row(page, '나.md').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째 문서")')
        page.locator('#lec-doctab-list .doc-tab').first.click(button='right')
        text = page.locator('#lec-menu').inner_text()
        check('영어 화면의 탭 메뉴', 'Move to new window' in text and '새 창' not in text, text)
        win = popup(page, lambda: menu(page, 'Move to new window').click())
        win.wait_for_selector('#lec-view h1:has-text("첫째")', timeout=8000)
        win.wait_for_timeout(500)
        same = page.evaluate("document.querySelector('#lec-theme-css').getAttribute('href')") == win.evaluate("document.querySelector('#lec-theme-css').getAttribute('href')")
        check('독립창이 메인 창의 스타일을 따른다', same)
        row_en = win.locator('#lec-doctab-list .doc-tab').first
        row_en.click(button='right')
        text = win.locator('#lec-menu').inner_text()
        check('영어 독립창의 메뉴', 'Send to main window' in text, text)
        win.close()
        check('스크립트 오류가 없다 (보기만·영어)', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('멈춤')
finally:
    for s in extra:
        s.terminate()
        try:
            s.wait(10)
        except Exception:
            s.kill()
    stop(server, base)
report()
