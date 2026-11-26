"""레벨 키와 단축키 정리 (D152): 여러 줄을 골라도 하위를 두 번 옮기지 않음, 제목은 >> 가 그 줄만·Alt+Shift 가 하위 절까지(알림),
Tab 은 제목을 바꾸지 않고 알림, 번호 다시 매김 알림, 하위 항목의 종류 바꾸기, 하위가 있는 항목을 제목으로, Ctrl+Alt+숫자 되돌리기,
vi 의 p·P(표의 행·번호 목록)와 Y, 슬라이드 제목 줄의 Alt+↓, 바꾸기 창의 강조글, 전체 편집의 Ctrl+D·Ctrl+Shift+D·K, '전체 편집으로 열기',
vi 의 i, 칸 안의 앱 키(F1), 코드 화면의 Ctrl+Shift+/, '자료' 목록 폴더의 업무 카드, 번호를 단 제목의 알림."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-keystidy-'))
proj = base / 'proj'
proj.mkdir(parents=True)
LEVEL = ('# 레벨\n\n## 첫째 장\n\n### 첫째 절\n\n#### 첫째 항\n\n## 둘째 장\n\n- 가\n- 나\n  - 나1\n  - 나2\n- 다\n\n1. 하나\n2. 둘\n3. 셋\n4. 넷\n\n'
         '- 부모\n  - 자식1\n  - 자식2\n\n10. 열\n    - 열의 하위\n11. 열하나\n')
TABLE = '# 표\n\n| 이름 | 값 |\n|---|---|\n| 가 | 1 |\n| 나 | 2 |\n\n1. 하나\n2. 둘\n\n강조글 아래 문단.\n\n> [!NOTE]\n> 참고 글이다.\n'
DECK = '---\nmarp: true\n---\n\n# 첫 장\n\n첫 장 글\n\n---\n\n# 둘째 장\n\n둘째 장 글\n'
NUMBERED = '# 보고서\n\n## 1. 서론\n\n### 1.1 배경\n\n## 2. 본론\n\n## 3. 결론\n'
files = {'레벨.md': LEVEL, '표.md': TABLE, '장.md': DECK, '번호.md': NUMBERED}
for name, text in files.items():
    (proj / name).write_text(text, encoding='utf-8')
(proj / 'code.py').write_text('print(1)\nprint(2)\n', encoding='utf-8')
(proj / '자료만').mkdir()
(proj / '자료만' / 'data.csv').write_text('a,b\n1,2\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)
errors = []


def read(name):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


lines = lambda name: read(name).split('\n')

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''
        clear_toast = lambda: page.evaluate("() => { const t = document.querySelector('#lec-toast'); t.textContent = ''; t.hidden = true; }")
        vi = lambda on: page.evaluate("(on) => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: on }))", on)

        def open_doc(name, alt=False):
            page.keyboard.press('Escape')
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click(modifiers=['Alt'] if alt else [])
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_timeout(600)

        def reset(name):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            if read(name) != files[name]:
                (proj / name).write_text(files[name], encoding='utf-8')
            until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == files[name].rstrip('\n') or
                  page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == files[name], 8000)
            page.wait_for_timeout(300)

        def go(n):
            page.locator('#lec-view h1').first.click()
            page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", n)
            page.wait_for_timeout(200)

        def twice(key):
            page.keyboard.press(key)
            page.wait_for_timeout(250)
            page.keyboard.press(key)

        print('[레벨 — 여러 줄]')
        open_doc('레벨.md')
        go(12)
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Tab')
        expect(page, '나·나1·나2 를 골라 Tab — 하위가 두 번 들어가지 않음', lambda: lines('레벨.md')[11:14] == ['  - 나', '    - 나1', '    - 나2'], lambda: lines('레벨.md')[10:15])

        print('[레벨 — 제목]')
        reset('레벨.md')
        vi(True)
        go(3)
        page.keyboard.press('>')
        page.keyboard.press('>')
        expect(page, 'vi 의 >> 는 그 줄만', lambda: lines('레벨.md')[2] == '### 첫째 장' and lines('레벨.md')[4] == '### 첫째 절', lambda: lines('레벨.md')[2:7])
        vi(False)
        reset('레벨.md')
        go(3)
        clear_toast()
        twice('Alt+Shift+ArrowRight')
        expect(page, 'Alt+Shift+→ 는 하위 절까지', lambda: lines('레벨.md')[2:7] == ['### 첫째 장', '', '#### 첫째 절', '', '##### 첫째 항'], lambda: lines('레벨.md')[2:7])
        expect(page, '— 함께 옮긴 하위 절 제목을 알린다', lambda: '하위 절 제목 2개도 함께 옮겼습니다' in toast(), toast)
        reset('레벨.md')
        go(3)
        page.keyboard.press('Control+Enter')
        clear_toast()
        page.keyboard.press('Tab')
        expect(page, '하이라이트한 제목의 Tab — 바꾸지 않고 키를 알린다', lambda: '제목 수준은 숫자 키' in toast() and read('레벨.md') == LEVEL, toast)
        page.keyboard.press('Escape')

        print('[레벨 — 번호]')
        reset('레벨.md')
        go(19)
        clear_toast()
        twice('Alt+Shift+ArrowRight')
        expect(page, '셋째를 안으로 — 넷째가 3', lambda: lines('레벨.md')[18:20] == ['   1. 셋', '3. 넷'], lambda: lines('레벨.md')[16:21])
        expect(page, '— 번호를 다시 매긴 뒤 항목을 알린다', lambda: '뒤 항목 1개의 번호를 다시 매겼습니다' in toast(), toast)

        print('[줄 종류]')
        reset('레벨.md')
        go(23)
        twice('n')
        expect(page, '하위 항목을 번호로 — 들여쓰기 그대로', lambda: lines('레벨.md')[22] == '  1. 자식1' and lines('레벨.md')[21] == '- 부모', lambda: lines('레벨.md')[20:25])
        reset('레벨.md')
        go(26)
        twice('2')
        expect(page, '하위가 있는 10. 항목을 제목으로 — 하위가 코드 블록이 되지 않음', lambda: '## 열\n\n- 열의 하위\n10. 열하나' in read('레벨.md'), lambda: read('레벨.md')[-60:])
        reset('레벨.md')
        go(9)
        page.keyboard.press('Control+Enter')
        page.keyboard.press('Control+Alt+2')
        expect(page, 'Ctrl+Alt+2 를 제목 2 에서 — 문단으로', lambda: lines('레벨.md')[8] == '둘째 장',lambda: lines('레벨.md')[8])
        page.keyboard.press('Control+Alt+2')
        expect(page, '한 번 더 — 제목 2', lambda: lines('레벨.md')[8] == '## 둘째 장',lambda: lines('레벨.md')[8])
        page.keyboard.press('Escape')

        print('[vi 의 p · P · Y]')
        open_doc('표.md')
        vi(True)
        go(5)
        page.keyboard.press('y')
        page.keyboard.press('y')
        page.keyboard.press('p')
        expect(page, '표의 행을 yyp — 표 안에', lambda: lines('표.md')[4:7] == ['| 가 | 1 |', '| 가 | 1 |', '| 나 | 2 |'], lambda: lines('표.md')[2:9])
        reset('표.md')
        go(8)
        page.keyboard.press('Shift+Y')
        page.keyboard.press('p')
        expect(page, '번호 목록을 Yp — 번호를 다시 매김', lambda: lines('표.md')[7:10] == ['1. 하나', '2. 하나', '3. 둘'], lambda: lines('표.md')[6:11])
        reset('표.md')
        vi(False)

        print('[고른 줄 바꾸기 창의 강조글]')
        go(14)
        page.keyboard.press('Control+Enter')
        page.locator('#lec-view .callout, #lec-view blockquote').last.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='바꾸기').first.click()
        page.wait_for_selector('#lec-put:not([hidden])')
        page.keyboard.type('팁')
        page.wait_for_timeout(200)
        page.keyboard.press('Enter')
        expect(page, '강조글을 팁으로 — 한 겹 더 감싸지 않음', lambda: '> [!TIP]\n> 참고 글이다.' in read('표.md') and '> >' not in read('표.md'), lambda: read('표.md')[-60:])
        page.keyboard.press('Escape')

        print('[슬라이드 제목 줄의 Alt+↓]')
        open_doc('장.md', alt=True)
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        page.wait_for_timeout(800)
        page.locator('#lec-view h1', has_text='첫 장').first.click()
        page.keyboard.press('Control+Enter')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, '고른 슬라이드 제목 한 줄의 Alt+↓ — 장째 옮김', lambda: read('장.md').index('# 둘째 장') < read('장.md').index('# 첫 장') and '첫 장 글' in read('장.md'), lambda: read('장.md'))
        page.keyboard.press('Escape')

        print('[전체 편집의 Ctrl+D · Ctrl+Shift+D · K]')
        open_doc('번호.md')
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=10000)
        cm = lambda: page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.getValue()")
        page.evaluate("() => { const c = document.querySelector('.CodeMirror').CodeMirror; c.focus(); c.setCursor({ line: 2, ch: 0 }); }")
        page.keyboard.press('Control+d')
        page.wait_for_timeout(200)
        check('Ctrl+D 는 줄을 지우지 않음', cm() == NUMBERED, cm()[:60])
        page.keyboard.press('Control+Shift+d')
        page.wait_for_timeout(200)
        check('Ctrl+Shift+D 줄 복제', cm().split('\n')[2:4] == ['## 1. 서론', '## 1. 서론'], cm().split('\n')[:5])
        page.keyboard.press('Control+Shift+k')
        page.wait_for_timeout(200)
        check('Ctrl+Shift+K 줄 지우기', cm() == NUMBERED, cm()[:60])
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)

        print('[번호를 단 제목]')
        reset('번호.md')
        go(5)
        clear_toast()
        twice('Alt+Shift+ArrowLeft')
        expect(page, '### 1.1 배경을 밖으로 — 2. 배경, 뒤 번호도', lambda: '## 2. 배경' in read('번호.md') and '## 3. 본론' in read('번호.md'), lambda: read('번호.md'))
        expect(page, '— 제목 번호를 다시 매긴 것을 알린다', lambda: '제목 번호' in toast() and '다시 매겼습니다' in toast(), toast)

        print('[메뉴 이름 · vi 의 i · 칸 안의 F1]')
        open_doc('표.md')
        reset('표.md')
        page.locator('#lec-view p', has_text='강조글 아래 문단').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.querySelector('span')?.textContent.trim() || b.textContent.trim())")
        check("보통 줄 메뉴는 '전체 편집으로 열기'", '전체 편집으로 열기' in items and '여기서 편집' not in items, items)
        page.keyboard.press('Escape')
        vi(True)
        page.locator('#lec-view p', has_text='강조글 아래 문단').dblclick()
        page.wait_for_timeout(400)
        page.keyboard.press('i')
        expect(page, 'vi 키면 낱말을 고른 채 i 는 칸 열기', lambda: page.locator('#lec-view .lec-line-edit').count() == 1 and '*' not in read('표.md').split('\n')[10], lambda: read('표.md').split('\n')[10])
        page.keyboard.press('End')
        page.keyboard.type(' 더함')
        page.keyboard.press('F1')
        expect(page, '칸 안의 F1 — 저장하고 사용설명서', lambda: '강조글 아래 문단. 더함' in read('표.md') and page.locator('#lec-help:not([hidden]), #lec-manual:not([hidden])').count() >= 1,
               lambda: (read('표.md').split('\n')[10], page.evaluate("() => [...document.querySelectorAll('[id^=lec-]')].filter((e) => !e.hidden && /help|manual/.test(e.id)).map((e) => e.id)")))
        page.keyboard.press('F1')
        vi(False)

        print('[코드 화면의 Ctrl+Shift+/]')
        page.click('#lec-code-head')
        page.locator('#lec-code-list .row[data-path="code.py"]').click()
        page.wait_for_selector('#lec-view .cv-line', timeout=8000)
        page.locator('#lec-view .cv-line').first.click()
        page.keyboard.press('Control+Shift+Slash')
        page.wait_for_timeout(400)
        check('Ctrl+Shift+/ 는 단축키 표를 열지 않음', page.locator('#lec-keys').is_hidden())

        print("['폴더' 묶음 폴더의 업무 카드 — '자료' 목록은 자료만 만든다 (D203)]")
        page.click('#lec-others-head')
        page.locator('#lec-others-list .row', has_text='자료만').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("'자료' 목록의 폴더에는 업무 카드·새 문서·새 폴더가 없다", not any('업무 카드' in x or '새 문서' in x or '새 폴더' in x for x in items), items)
        page.keyboard.press('Escape')
        page.click('#lec-folder-head')
        page.locator('#lec-folder-list .row', has_text='자료만').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("문서가 없는 폴더에도 '폴더' 묶음에서 '이 폴더에 업무 카드 만들기…'", any('이 폴더에 업무 카드 만들기' in x for x in items), items)
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
