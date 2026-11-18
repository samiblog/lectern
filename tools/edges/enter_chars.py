"""Enter 키 통일과 특수 문자 (D164·D165): 읽는 화면의 Ctrl+Enter 는 줄 선택(하이라이트 켜고 끄기 — 현재 줄·고른 줄), Shift+Enter 는 아래에 새 줄,
Ctrl+Shift+Enter 는 위에. 칸의 Shift+Enter 는 이어 쓰기, Ctrl+Enter 는 저장하고 그 줄 선택(빈 새 줄이면 넣지 않고 닫기만), vi 의 o.
특수 문자 창: 칸의 Ctrl+Shift+; (거르기·초성·←↑↓→·Enter·Esc·최근), 읽는 화면의 Ctrl+Shift+; 와 넣기 창의 '특수 문자'(현재 줄 끝에 — 새 줄을 남기지 않음),
칸의 우클릭 메뉴, 편집 모드의 Ctrl+Shift+;"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-enterchars-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = '# 문서\n\n첫째 문단.\n\n둘째 문단.\n\n셋째 문단.\n'
doc = proj / 'a.md'
doc.write_text(DOC, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)


def src():
    for _ in range(40):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1300, 'height': 800}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.wait_for_timeout(600)
        lit = lambda: (page.text_content('#lec-st-lit') or '') if page.locator('#lec-st-lit:not([hidden])').count() else ''  # noqa: E731
        cells = lambda: page.locator('#lec-view .lec-line-edit').count()  # noqa: E731
        chars_open = lambda: page.locator('#lec-chars:not([hidden])').count() > 0  # noqa: E731

        def reset(text=DOC):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            doc.write_text(text, encoding='utf-8')
            until(page, lambda: page.locator('#lec-view p').count() == text.count('문단'), 6000)
            page.wait_for_timeout(400)

        def at(text):
            page.locator('#lec-view p', has_text=text).first.click()
            page.wait_for_timeout(200)

        print('[읽는 화면 — Ctrl+Enter 줄 선택, Shift+Enter 새 줄]')
        at('둘째')
        page.keyboard.press('Control+Enter')
        expect(page, 'Ctrl+Enter — 현재 줄의 하이라이트 (줄 선택)', lambda: lit().startswith('하이라이트') and '1줄' in lit(), lit)
        page.keyboard.press('Control+Enter')
        expect(page, '한 번 더 — 끈다', lambda: lit() == '', lit)
        at('첫째')
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Control+Enter')
        expect(page, '고른 줄의 Ctrl+Enter — 그 줄들의 하이라이트', lambda: lit().startswith('하이라이트 3~7행'), lit)
        page.keyboard.press('Shift+Enter')
        page.wait_for_timeout(300)
        check('여러 줄을 고른 채 Shift+Enter — 새 줄을 열지 않는다', cells() == 0 and src() == DOC, (cells(), src()))
        reset()
        at('둘째')
        page.keyboard.press('Shift+Enter')
        expect(page, 'Shift+Enter — 아래에 새 줄 (칸)', lambda: cells() == 1)
        page.keyboard.type('새 아래 줄')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄 아래에 들어간다', lambda: '둘째 문단.\n\n새 아래 줄\n\n셋째' in src(), src)
        at('둘째')
        page.keyboard.press('Control+Shift+Enter')
        expect(page, 'Ctrl+Shift+Enter — 위에 새 줄', lambda: cells() == 1)
        page.keyboard.type('새 위 줄')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄 위에 들어간다', lambda: '새 위 줄\n\n둘째 문단.' in src(), src)

        print('[칸 — Shift+Enter 이어 쓰기, Ctrl+Enter 저장하고 그 줄 선택]')
        reset()
        at('셋째')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('End')
        page.keyboard.type(' 더')
        page.keyboard.press('Shift+Enter')
        page.wait_for_timeout(500)
        page.keyboard.type('이어 쓴 줄')
        page.keyboard.press('Control+Enter')
        expect(page, '칸의 Ctrl+Enter — 저장하고 닫는다', lambda: cells() == 0 and '셋째 문단. 더\n\n이어 쓴 줄\n' in src(), src)
        expect(page, '— 그 줄을 선택(하이라이트)', lambda: lit().startswith('하이라이트') and '1줄' in lit(), lit)
        here = page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)")
        check('— 그 줄은 방금 쓴 줄', here == src().split('\n').index('이어 쓴 줄') + 1, here)
        page.keyboard.press('Control+Enter')
        expect(page, '— 읽는 화면의 Ctrl+Enter 로 끈다', lambda: lit() == '', lit)
        page.keyboard.press('Shift+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit')
        before = src()
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(500)
        check('빈 새 줄의 Ctrl+Enter — 넣지 않고 닫기만 (선택할 줄이 없다)', cells() == 0 and src() == before and lit() == '', (cells(), lit()))

        print('[vi 의 o]')
        page.evaluate("() => import('/static/js/api.js').then(({ saveConfig }) => saveConfig({ vi_keys: true }))")
        page.wait_for_timeout(300)
        reset()
        at('첫째')
        page.keyboard.press('o')
        expect(page, 'o — 아래에 새 줄 (Shift+Enter 와 같다)', lambda: cells() == 1)
        page.keyboard.type('오 줄')
        page.keyboard.press('Enter')
        expect(page, '— 첫째 아래에', lambda: '첫째 문단.\n\n오 줄\n' in src(), src)
        page.evaluate("() => import('/static/js/api.js').then(({ saveConfig }) => saveConfig({ vi_keys: false }))")
        page.wait_for_timeout(300)

        print('[특수 문자 — 칸의 Ctrl+Shift+;]')
        reset()
        at('첫째')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('End')
        page.keyboard.press('Control+Shift+Semicolon')
        expect(page, '특수 문자 창이 뜬다 — 거르기 칸에 초점', lambda: chars_open() and page.evaluate("document.activeElement?.id") == 'lec-chars-find')
        groups = page.evaluate("() => [...document.querySelectorAll('#lec-chars .cp-name')].map((x) => x.textContent)")
        check('묶음 — 문장 부호·화살표·도형·수학·단위·번호·첨자·그리스 문자·기타 (처음엔 최근 없음)', groups[:3] == ['문장 부호', '화살표', '도형'] and len(groups) == 9, groups)
        check('아래 줄에 고른 문자의 이름', '가운뎃점' in page.text_content('#lec-chars-name'), page.text_content('#lec-chars-name'))
        page.keyboard.press('ArrowRight')
        check('→ — 옆 칸', '줄표' in page.text_content('#lec-chars-name'), page.text_content('#lec-chars-name'))
        page.keyboard.press('ArrowDown')
        name_down = page.text_content('#lec-chars-name')
        check('↓ — 아랫줄의 가까운 칸', name_down and '줄표' not in name_down and '가운뎃점' not in name_down, name_down)
        page.keyboard.type('화살표')
        page.wait_for_timeout(150)
        shown = page.evaluate("() => [...document.querySelectorAll('#lec-chars .cp-grid button')].map((b) => b.textContent)")
        check('거르기 — 이름에 화살표가 든 것만', shown[:4] == ['→', '←', '↑', '↓'] and all('화살표' in page.get_attribute(f'#lec-chars .cp-grid button[data-i="{i}"]', 'title') for i in range(len(shown))), shown)
        page.keyboard.press('Enter')
        expect(page, 'Enter — 커서 자리에 넣고 창을 닫는다, 칸은 그대로', lambda: not chars_open() and cells() == 1
               and page.evaluate("document.querySelector('#lec-view .lec-line-edit')?.textContent") == '첫째 문단.→', lambda: page.evaluate("document.querySelector('#lec-view .lec-line-edit')?.textContent"))
        page.keyboard.type('다음')
        page.keyboard.press('Enter')
        expect(page, '— 저장하면 원문에 그대로 (서식이 되지 않는 글자)', lambda: '첫째 문단.→다음\n' in src(), src)
        cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('최근 넣은 문자를 설정에 (recent_chars)', cfg.get('recent_chars', [])[:1] == ['→'], cfg.get('recent_chars'))
        at('둘째')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('Control+Shift+Semicolon')
        page.wait_for_selector('#lec-chars:not([hidden])')
        first_group = page.evaluate("() => document.querySelector('#lec-chars .cp-name')?.textContent")
        check('다음에 열면 맨 위에 최근', first_group == '최근' and page.evaluate("() => document.querySelector('#lec-chars .cp-group.recent button')?.textContent") == '→', first_group)
        page.keyboard.type('ㅅㅆ')
        page.wait_for_timeout(150)
        shown = page.evaluate("() => [...document.querySelectorAll('#lec-chars .cp-grid button')].map((b) => b.textContent)")
        check('초성으로 거르기 — ㅅㅆ 섭씨', shown == ['℃'], shown)
        page.fill('#lec-chars-find', 'zzzz')
        check('맞는 것이 없으면 알림', 'zzzz' and page.locator('#lec-chars .cp-none').count() == 1)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        check('Esc — 넣지 않고 닫는다, 칸과 커서는 그대로', not chars_open() and cells() == 1 and page.evaluate("document.activeElement?.classList.contains('lec-line-edit')"))
        page.locator('#lec-view .lec-line-edit').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='특수 문자…').click()
        expect(page, '칸의 우클릭 메뉴 — 특수 문자…', chars_open)
        page.fill('#lec-chars-find', '섭씨')
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')
        expect(page, '— 넣고 저장', lambda: '℃' in src(), src)

        print('[읽는 화면의 Ctrl+Shift+; · 넣기 창의 특수 문자]')
        reset()
        at('셋째')
        page.keyboard.press('Control+Shift+Semicolon')
        expect(page, '읽는 화면 — 현재 줄의 칸을 열고 특수 문자 창', lambda: chars_open() and cells() == 1)
        page.fill('#lec-chars-find', '참고표')
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄 끝에', lambda: '셋째 문단.※\n' in src(), src)
        reset()
        at('둘째')
        page.keyboard.press('/')
        page.wait_for_selector('#lec-put:not([hidden])')
        page.keyboard.type('특수')
        page.keyboard.press('Enter')
        expect(page, '넣기 창의 특수 문자 — 특수 문자 창이 뜬다', chars_open)
        page.fill('#lec-chars-find', '원 숫자 1')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        check('— 아래 새 줄이 아니라 현재 줄 끝의 칸에', cells() == 1 and page.evaluate("document.querySelector('#lec-view .lec-line-edit')?.textContent") == '둘째 문단.①',
              page.evaluate("document.querySelector('#lec-view .lec-line-edit')?.textContent"))
        page.keyboard.press('Enter')
        expect(page, '— 저장하면 빈 줄 없이 그 줄만 바뀐다', lambda: src() == DOC.replace('둘째 문단.', '둘째 문단.①'), src)

        print('[편집 모드의 Ctrl+Shift+;]')
        reset()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-editor .CodeMirror')
        page.wait_for_timeout(300)
        page.evaluate("() => { const cm = document.querySelector('.lec-editor .CodeMirror').CodeMirror; cm.focus(); cm.setCursor({ line: 2, ch: 2 }); }")
        page.keyboard.press('Control+Shift+Semicolon')
        expect(page, '편집 모드 — 특수 문자 창', chars_open)
        page.fill('#lec-chars-find', '가운뎃점')
        page.keyboard.press('Enter')
        got = page.evaluate("() => document.querySelector('.lec-editor .CodeMirror').CodeMirror.getLine(2)")
        check('— 커서 자리에 넣고 편집기로 돌아온다', got == '첫째· 문단.' and page.evaluate("!!document.activeElement?.closest('.lec-editor')"), got)
        page.keyboard.press('Control+s')
        expect(page, '— 저장', lambda: '첫째· 문단.' in src(), src)
        page.keyboard.press('Control+e')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
