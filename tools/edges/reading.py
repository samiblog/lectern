"""문서에는 적었지만 ui_smoke 에 점검이 없는 동작을 본다. 프로젝트·설정은 임시 폴더"""
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop



LONG = '아주 긴 설명입니다. ' * 40
PARA = '긴 문단입니다. ' * 40
EDGE = f"""# 가장자리 점검

짧은 줄
둘째 줄
셋째 줄

| 품목 | 설명 |
|---|---|
| 구리 | {LONG.strip()} |
| 니켈 | 짧음 |

- [ ] 보통 할 일
  - [ ] 안쪽 할 일
- [X] 큰 X 할 일

1. [ ] 번호 할 일

> - [ ] 인용 할 일

> [!NOTE]
> - [ ] 박스 할 일

수식 $x^2$ 뒤의 글입니다.

[링크](#절-b) 뒤의 글입니다.

`인라인 코드` 뒤의 글입니다.

---

## 절 A

""" + (PARA + '\n\n') * 8 + '## 절 B\n\n' + (PARA + '\n\n') * 8
MOVE = '# 이동\n\n' + ''.join(f'## 장 {i}\n\n' + (PARA + '\n\n') * 6 for i in range(1, 6))
DECK = '---\nmarp: true\n---\n\n# 표지\n\n- [ ] 슬라이드 할 일\n\n---\n\n# 둘째\n\n글\n'
CODE = '\n'.join(f'def func_{i}():\n    return {i}\n\n' + '# 설명\n' * 20 for i in range(1, 16)) + '\n'

base = Path(tempfile.mkdtemp(prefix='lec-gaps-'))
proj = base / 'proj'
(proj / 'code').mkdir(parents=True)
edge = proj / 'edge.md'
edge.write_text(EDGE, encoding='utf-8')
(proj / 'move.md').write_text(MOVE, encoding='utf-8')
(proj / 'other.md').write_text('# 다른 문서\n\n글\n', encoding='utf-8')
deck = proj / 'deck.md'
deck.write_text(DECK, encoding='utf-8')
(proj / 'code' / 'long.py').write_text(CODE, encoding='utf-8')

server, url, port = serve(proj, base / 'config')

POINT = """(needle) => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.nodeValue.indexOf(needle); if (i >= 0) { n.parentElement.scrollIntoView({ block: 'nearest' });
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getBoundingClientRect(); return [b.left + 1, b.top + b.height / 2]; } } return null; }"""
CARET = """(() => { const sp = document.activeElement; const c = getSelection().getRangeAt(0).cloneRange(); c.collapse(true);
  if (c.startContainer === sp) { c.setStart(sp.firstChild, c.startOffset ? sp.firstChild.length : 0); c.collapse(true); }
  const all = document.createRange(); all.selectNodeContents(sp);
  const tops = [...new Set([...all.getClientRects()].filter((r) => r.height).map((r) => Math.round(r.top)))];
  return [tops.indexOf(Math.round(c.getClientRects()[0].top)), tops.length]; })()"""
EDITING = "[...document.querySelectorAll('#lec-view .lec-line-edit')].map((s) => s.parentElement.tagName + ':' + s.textContent.slice(0, 16))"
IN_TERM = "!!document.activeElement?.closest('#lec-term')"
IN_DOC = "document.activeElement?.id === 'lec-content'"


def src(path, n):
    for _ in range(40):
        try:
            return path.read_text(encoding='utf-8').split('\n')[n - 1]
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간 (ReplaceFileW)
            time.sleep(0.02)
    return path.read_text(encoding='utf-8').split('\n')[n - 1]


def until_line(path, n, want, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        if src(path, n) == want:
            return True
        time.sleep(0.05)
    return False


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors: list[str] = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')

        def wait(js, ms=5000):
            try:
                page.wait_for_function(js, timeout=ms)
                return True
            except Exception:
                return False

        def open_doc(path, title):
            page.click('.side-tabs button[data-tab="files"]')
            page.locator(f'#lec-tree .row.file[data-doc="{path}"]').click(modifiers=['Alt'])
            page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            page.wait_for_timeout(250)

        editing = lambda: page.evaluate(EDITING)
        edit_open = lambda: wait("!!document.querySelector('#lec-view .lec-line-edit')")
        point = lambda needle: page.evaluate(POINT, needle)
        top = lambda: page.evaluate("document.querySelector('#lec-content').scrollTop")
        near = lambda a, b: abs(a - b) <= 2
        toast_has = lambda s: wait(f"document.querySelector('#lec-toast').textContent.includes('{s}')", 3000)
        clear_toast = lambda: page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        settle = lambda ms=250: page.wait_for_timeout(ms)
        lit = lambda: page.evaluate("document.querySelector('#lec-st-lit').hidden ? null : document.querySelector('#lec-st-lit').textContent")

        def set_top(y):
            page.evaluate(f"document.querySelector('#lec-content').scrollTop = {y}")
            settle(200)

        def undo():
            page.locator('#lec-view h1').first.click()
            page.keyboard.press('Control+z')

        print('[두 번 누르기]')
        open_doc('edge.md', '가장자리 점검')
        page.mouse.dblclick(*point('둘째'))
        edit_open()
        first = editing()
        page.keyboard.type('X')
        page.keyboard.press('Enter')
        check('한 화면 줄에 이어진 짧은 줄은 누른 원문 줄로', first == ['P:둘째 줄'] and until_line(edge, 4, 'X둘째 줄'), (first, src(edge, 4)))
        page.wait_for_selector('#lec-view p:has-text("X둘째")')
        undo()
        until_line(edge, 4, '둘째 줄')
        settle(1300)
        page.mouse.dblclick(*point('설명입니다'))
        edit_open()
        page.keyboard.type('Y')
        page.keyboard.press('Enter')
        check('표의 칸을 두 번 누르면 그 칸의 누른 자리', until_line(edge, 9, f'| 구리 | 아주 긴 Y{LONG.strip()[5:]} |'), src(edge, 9)[:30])
        page.wait_for_selector('#lec-view td:has-text("Y설명")')
        undo()
        until_line(edge, 9, f'| 구리 | {LONG.strip()} |')
        settle(1300)
        at = point('수식')
        math = page.evaluate("(() => { const r = document.querySelector('#lec-view .katex').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
        page.mouse.dblclick(*math)
        settle(450)
        check('수식 위는 열지 않음', editing() == [], editing())
        page.mouse.dblclick(*point('뒤의 글'))
        edit_open()
        check('수식이 든 줄의 글은 열림 (표시 잠금 없이 원문 글자로)', editing() == ['P:수식 $x^2$ 뒤의 글입니다'], editing())
        page.keyboard.press('Escape')
        box = page.locator('#lec-view').bounding_box()
        page.mouse.dblclick(box['x'] + 3, 300)
        settle(450)
        check('본문 왼쪽 여백은 열지 않음', editing() == [], editing())
        page.locator('#lec-view hr').first.dblclick()
        settle(450)
        check('구분선은 열지 않고 알리지도 않음', editing() == [], editing())
        before_task = src(edge, 12)
        page.locator('#lec-view .task-list-item-checkbox').first.dblclick()
        settle(700)
        check('체크 칸을 두 번 눌러도 한 번만 바뀜', src(edge, 12) == '- [x] 보통 할 일' and editing() == [], (before_task, src(edge, 12), editing()))
        page.locator('#lec-view .task-list-item-checkbox').first.click()
        until_line(edge, 12, '- [ ] 보통 할 일')
        settle(1300)

        print('[표 칸의 꺾인 글]')
        spots = page.evaluate("""(() => { const td = [...document.querySelectorAll('#lec-view td')].find((c) => c.textContent.startsWith('아주 긴')); td.scrollIntoView({ block: 'nearest' });
          const r = document.createRange(); r.selectNodeContents(td); const rs = [...r.getClientRects()].filter((x) => x.height);
          const ys = [...new Set(rs.map((x) => Math.round((x.top + x.bottom) / 2)))]; return { x: rs[0].left + 30, ys }; })()""")
        check('칸이 여러 줄로 꺾임', len(spots['ys']) >= 3, spots)
        page.mouse.dblclick(spots['x'], spots['ys'][1])
        edit_open()
        a = page.evaluate(CARET)
        page.keyboard.press('ArrowUp')
        b = page.evaluate(CARET)
        page.keyboard.press('ArrowUp')
        moved = wait("document.activeElement.classList.contains('lec-line-edit') && document.activeElement.textContent === '설명'")
        check('칸 안에서 위로, 맨 윗줄에서 위 행의 같은 칸', a[0] == 1 and b[0] == 0 and moved, (a, b, editing()))
        page.keyboard.press('Escape')
        settle()
        spots = page.evaluate("""(() => { const td = [...document.querySelectorAll('#lec-view td')].find((c) => c.textContent.startsWith('아주 긴')); td.scrollIntoView({ block: 'nearest' });
          const r = document.createRange(); r.selectNodeContents(td); const rs = [...r.getClientRects()].filter((x) => x.height);
          return { x: rs[0].left + 30, ys: [...new Set(rs.map((x) => Math.round((x.top + x.bottom) / 2)))] }; })()""")
        page.mouse.dblclick(spots['x'], spots['ys'][-1])
        edit_open()
        page.keyboard.press('ArrowDown')
        check('맨 아랫줄에서 아래 행의 같은 칸', wait("document.activeElement.classList.contains('lec-line-edit') && document.activeElement.textContent === '짧음'"), editing())
        page.keyboard.press('Escape')
        settle()

        print('[할 일 표시의 모양]')
        boxes = page.locator('#lec-view .task-list-item-checkbox')
        for i, (n, on, off) in enumerate(((12, '- [x] 보통 할 일', '- [ ] 보통 할 일'), (13, '  - [x] 안쪽 할 일', '  - [ ] 안쪽 할 일'), (14, '- [ ] 큰 X 할 일', '- [x] 큰 X 할 일'),
                                          (16, '1. [x] 번호 할 일', '1. [ ] 번호 할 일'), (18, '> - [x] 인용 할 일', '> - [ ] 인용 할 일'), (21, '> - [x] 박스 할 일', '> - [ ] 박스 할 일'))):
            boxes.nth(i).click()
            one = until_line(edge, n, on)
            settle(450)
            boxes.nth(i).click()
            two = until_line(edge, n, off)
            settle(450)
            check(f'{n}행: {off}', one and two, src(edge, n))
        page.keyboard.press('Control+z')
        check('Ctrl+Z 가 체크 칸 저장을 차례로 되돌림', until_line(edge, 21, '> - [x] 박스 할 일'), src(edge, 21))
        settle(450)
        page.keyboard.press('Control+z')
        until_line(edge, 21, '> - [ ] 박스 할 일')
        settle(1300)
        edge.write_text(edge.read_text(encoding='utf-8').replace('- [x] 큰 X 할 일', '- [X] 큰 X 할 일'), encoding='utf-8')
        settle(1500)

        print('[흐린 곳의 체크 칸]')
        page.locator('#lec-view h1').click(modifiers=['Shift'])
        settle(150)
        hl = lit()
        page.locator('#lec-view .task-list-item-checkbox').first.click()
        settle(500)
        check('줄 하이라이트 밖의 칸은 저장하지 않고 하이라이트만 끔', hl == '하이라이트 1행 · 1줄' and src(edge, 12) == '- [ ] 보통 할 일' and lit() is None, (hl, src(edge, 12), lit()))
        page.locator('#lec-view li', has_text='큰 X').locator('input').click(modifiers=['Shift'])
        settle(200)
        hl = lit()
        page.locator('#lec-view li', has_text='큰 X').locator('input').click()
        ok = until_line(edge, 14, '- [ ] 큰 X 할 일')
        check('하이라이트 안의 칸은 바뀜', hl == '하이라이트 14행 · 1줄' and ok, (hl, src(edge, 14)))
        settle(500)
        page.keyboard.press('Control+z')
        until_line(edge, 14, '- [X] 큰 X 할 일')
        page.keyboard.press('Escape')
        settle(1300)
        page.click('#lec-btn-spot')
        settle(150)
        page.click('#lec-spot-next')
        settle(200)
        page.evaluate("document.querySelector('#lec-view .task-list-item-checkbox').scrollIntoView({ block: 'center' })")
        settle(200)
        chapter_on = page.evaluate("document.querySelector('#lec-btn-spot').classList.contains('on')")
        page.locator('#lec-view .task-list-item-checkbox').first.click()
        settle(500)
        check('장 하이라이트의 흐린 곳 칸은 그 장으로만 옮김', chapter_on and src(edge, 12) == '- [ ] 보통 할 일', (chapter_on, src(edge, 12)))
        page.click('#lec-btn-spot')
        settle(200)

        print('[슬라이드]')
        open_doc('deck.md', '표지')
        slide_box = page.evaluate("[...document.querySelectorAll('#lec-view .task-list-item-checkbox')].map((b) => b.disabled)")
        check('슬라이드의 칸도 누를 수 있음', slide_box == [False], slide_box)
        page.locator('#lec-status button', has_text='문서로 보기').click()
        wait("!document.querySelector('#lec-view').classList.contains('lec-deck')")
        settle(300)
        page.locator('#lec-view .task-list-item-checkbox').first.click()
        check('문서로 보면 칸을 누를 수 있음', until_line(deck, 7, '- [x] 슬라이드 할 일'), src(deck, 7))
        settle(500)

        print('[뒤로 기록의 나머지 길]')
        open_doc('edge.md', '가장자리 점검')
        set_top(0)
        link_at = point('링크')   # 링크가 보이게 스크롤한다 — 그 자리가 돌아올 곳
        settle(200)
        t0 = top()
        page.mouse.click(*link_at)
        settle()
        t1 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('절 링크', t1 > t0 + 500 and near(top(), t0), (t0, t1, top()))
        set_top(2500)
        page.click('.side-tabs button[data-tab="parts"]')
        wait("!!document.querySelector('#lec-parts-list .pt-item')", 15000)
        page.click('#lec-parts-kinds button[data-kind="table"]')
        settle(300)
        page.locator('#lec-parts-list .pt-item[data-doc="edge.md"]').first.click(modifiers=['Alt'])
        settle()
        t1 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('모아 보기 결과', t1 < 1500 and near(top(), 2500), (t1, top()))
        set_top(2500)
        page.keyboard.press('Control+Shift+f')
        page.keyboard.type('뒤의 글')
        wait("!!document.querySelector('#lec-search-results .sr-hit[data-doc=\"edge.md\"]')")
        page.locator('#lec-search-results .sr-hit[data-doc="edge.md"]').first.click(modifiers=['Alt'])
        settle(400)
        t1 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('검색 결과', t1 < 1500 and near(top(), 2500), (t1, top()))
        page.locator('#lec-content').focus()
        page.keyboard.press('Escape')
        open_doc('edge.md', '가장자리 점검')
        set_top(0)
        toc = lambda name: page.locator('#lec-toc a[data-i]', has_text=name).first.click()
        toc('절 B')
        settle()
        toc('절 B')
        settle()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('이미 보는 절을 또 눌러도 뒤로 한 번이면 뛰기 전 자리', near(top(), 0), top())
        page.keyboard.press('Control+p')
        page.keyboard.type('long.py')
        page.locator('#lec-palette-list li.code', has_text='code/long.py').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view.code-view .cv-line[data-line="9"]')
        settle()
        page.evaluate("document.querySelector('#lec-content').scrollTop = 300")
        settle(200)
        c0 = top()
        page.locator('#lec-toc a[data-i]', has_text='func_12').click()
        settle()
        c1 = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('코드 화면의 목차', c1 > c0 + 500 and near(top(), c0), (c0, c1, top()))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view h1:has-text("가장자리 점검")')
        check('코드 화면에서 앞 문서로', True)

        open_doc('move.md', '이동')
        set_top(800)
        toc('장 4')
        settle()
        j1 = top()
        row = page.locator('#lec-tree .row.file[data-doc="move.md"]')
        row.focus()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-rename:not([hidden])')
        page.fill('#lec-rename-input', 'moved.md')
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-tree .row.file[data-doc="moved.md"]', timeout=8000)
        settle(500)
        page.locator('#lec-content').focus()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('이름을 바꿔도 뛰기 전 자리로', near(top(), 800) and page.inner_text('#lec-st-path') == 'moved.md', (j1, top(), page.inner_text('#lec-st-path')))

        toc('장 4')
        settle()
        page.locator('#lec-tree .row.file[data-doc="other.md"]').dblclick()
        wait("document.querySelectorAll('#lec-doctab-list .doc-tab').length === 2")
        settle(500)
        page.keyboard.press('Alt+1')
        settle(500)
        page.locator('#lec-content').focus()
        at_jump = top()
        page.keyboard.press('Alt+ArrowLeft')
        settle()
        check('두 번 누르기로 새 탭을 만들어도 앞 탭의 기록이 남음', at_jump > 1500 and near(top(), 800), (at_jump, top()))
        page.keyboard.press('Alt+2')
        settle(300)
        page.keyboard.press('Control+F4')
        wait("document.querySelectorAll('#lec-doctab-list .doc-tab').length === 1")
        settle(400)

        toc('장 3')
        settle()
        jump_h = page.evaluate("import('/static/js/store.js').then((m) => [m.S.pane.hIndex, m.S.pane.history.at(m.S.pane.hIndex - 1).line])")
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-editor .CodeMirror')
        settle(300)
        n0 = page.evaluate("import('/static/js/store.js').then((m) => m.S.pane.history.length)")
        toc('장 5')
        settle(300)
        n1 = page.evaluate("import('/static/js/store.js').then((m) => m.S.pane.history.length)")
        page.click('#lec-btn-back')
        settle(400)
        cm_line = page.evaluate("document.querySelector('.lec-pane.active .lec-editor .CodeMirror').CodeMirror.getCursor().line + 1")
        page.keyboard.press('Control+e')
        wait("!document.querySelector('.lec-editor')")
        check('편집 중에는 뛰기를 남기지 않고, 뒤로 버튼은 편집기가 그 줄로', n0 == n1 and jump_h[1] and cm_line == jump_h[1], (n0, n1, jump_h, cm_line))

        print('[F6 의 나머지 상황]')
        open_doc('edge.md', '가장자리 점검')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+p')
        page.wait_for_selector('#lec-palette:not([hidden])')
        page.keyboard.press('F6')
        settle(300)
        check('문서 열기 창이 열려 있으면 아무것도 안 함', page.evaluate("document.activeElement.closest('#lec-palette') !== null") and page.evaluate("document.querySelector('#lec-term').hidden"))
        page.keyboard.press('Escape')
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help:not([hidden])')
        page.keyboard.press('F6')
        settle(300)
        check('사용설명서가 덮고 있으면 아무것도 안 함', page.evaluate("document.querySelector('#lec-term').hidden"))
        page.keyboard.press('F1')
        settle(200)
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+f')
        page.keyboard.type('뒤의')
        settle(300)
        page.keyboard.press('F6')
        check('찾기 칸에서 F6 은 터미널로', wait(IN_TERM, 15000))
        rows = "[...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')].map((r) => r.textContent).join('')"
        wait(f"{rows}.includes('PS ')", 20000)
        page.keyboard.press('F6')
        check('돌아오면 문서로', wait(IN_DOC, 3000))
        page.keyboard.press('Escape')
        page.click('#lec-term-new')
        wait("document.querySelectorAll('#lec-term-tabs .term-tab').length === 2", 8000)
        wait(IN_TERM, 8000)
        settle(800)
        page.keyboard.press('F6')
        wait(IN_DOC, 3000)
        page.keyboard.press('F6')
        wait(IN_TERM, 3000)
        two = page.evaluate("import('/static/js/store.js').then((m) => m.S.tab.term.n)")
        check('터미널이 여럿이면 고른(마지막에 쓰던) 터미널로', two == 1, two)
        page.locator('#lec-term-tabs .term-tab[data-n="1"] [data-close]').click()
        wait("document.querySelectorAll('#lec-term-tabs .term-tab').length === 1", 8000)
        settle(500)
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+p')
        page.keyboard.type('long.py')
        page.locator('#lec-palette-list li.code', has_text='code/long.py').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view.code-view .cv-line[data-line="5"]')
        settle(300)
        page.locator('#lec-view .cv-line[data-line="5"]').click()
        page.keyboard.press('Shift+ArrowRight')
        check('코드 화면의 Shift+→', wait(f"{rows}.includes('@code/long.py 5행')", 6000) and wait(IN_TERM, 3000))
        page.keyboard.press('Escape')
        settle(300)
        open_doc('edge.md', '가장자리 점검')
        page.locator('#lec-view p', has_text='짧은 줄').click()
        page.keyboard.press('F2')
        edit_open()
        page.keyboard.press('Home')
        text0 = page.evaluate("document.activeElement.textContent")
        page.keyboard.press('Control+Shift+ArrowRight')
        settle(300)
        sel = page.evaluate("getSelection().toString()")
        kept = page.evaluate("document.activeElement.classList.contains('lec-line-edit')")
        check('한 줄 편집 칸의 Ctrl+Shift+→ 는 낱말 고르기', kept and sel.strip() and sel in text0, (kept, sel, text0))
        page.keyboard.press('Escape')
        page.click('#lec-doctab-spread')
        wait("document.documentElement.classList.contains('spread-on')")
        settle(400)
        page.locator('#lec-content').focus()
        page.keyboard.press('F6')
        a = wait(IN_TERM, 4000)
        page.keyboard.press('F6')
        b = wait(IN_DOC, 3000)
        check('모두 펼치기에서도 F6', a and b, (a, b))
        page.click('#lec-doctab-spread')
        wait("!document.documentElement.classList.contains('spread-on')")
        settle(300)
        if not page.evaluate("document.querySelector('#lec-term').hidden"):
            page.keyboard.press('Control+Backquote')
        settle(300)

        print('[장 하이라이트와 한 줄 편집]')
        page.locator('#lec-content').focus()
        set_top(0)
        page.click('#lec-btn-spot')
        settle(200)
        page.locator('#lec-view p', has_text='짧은 줄').click()
        page.keyboard.press('F2')
        edit_open()
        shade = "(() => { const b = document.querySelector('#lec-view').parentElement.querySelector(':scope > .lec-spot'); return !!b && !b.hidden && b.classList.contains('editing'); })()"
        lifted = wait(shade, 2000)
        page.keyboard.press('ArrowDown')
        settle(300)
        down = editing()
        chapter_kept = page.evaluate("document.querySelector('#lec-btn-spot').classList.contains('on')") and lit() is not None
        page.keyboard.press('Escape')
        settle(300)
        off = page.evaluate("document.querySelector('#lec-btn-spot').classList.contains('on')")
        status = lit()
        check('장 하이라이트 중 F2 는 회색을 걷고, 끝내면 장 하이라이트 그대로', lifted and off, (lifted, down, chapter_kept, off, status))
        page.click('#lec-btn-spot')
        settle(200)

        print('[보기만 하는 프로젝트]')
        page.click('#lec-btn-recent')
        page.locator('#lec-menu button', has_text='예제 열기').click()
        wait("document.querySelectorAll('#lec-tablist .lec-tab').length === 2", 8000)
        page.wait_for_selector('#lec-view h1:has-text("Lectern 예제")')
        settle(300)
        page.locator('#lec-view h1').click()
        clear_toast()
        page.keyboard.press('F2')
        told = toast_has('보기만 합니다')
        check('F2 는 열지 않고 까닭을 알림', told and editing() == [], (told, editing()))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    stop(server, base)
report()
