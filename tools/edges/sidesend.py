"""사이드바 목록의 행에서 터미널로 보내기 (D195): '파일' 탭의 문서·코드·자료·폴더 목록에서 행을 고른 채 Shift+→ 를 누르면
우클릭 메뉴 '@경로 복사' 옆의 ▣ 터미널을 누른 것과 같다 — '@경로 ' 를 최근에 쓴 터미널에 (Enter 없이), 초점도 터미널로.
Ctrl+Shift+→ 는 초점을 그 행에 둔다, Shift+1~5 는 그 번호의 터미널로, Shift+← 는 '@경로' 복사, 형광펜·할 일 줄은 '@경로 N행'.
→ · ← 의 펼치기·접기와 글자로 찾기는 그대로 — 문서 칸의 Shift+→ ('@경로 a행')도 그대로"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-sidesend-'))
proj = base / 'proj'
(proj / 'sub' / '깊은 곳').mkdir(parents=True)
(proj / 'code').mkdir()
(proj / 'data').mkdir()
(proj / '가.md').write_text('# 가 문서\n\n머리 문단.\n\n- [ ] 구리 재고 확인\n- [x] 끝낸 일\n\n<mark>칠한 글</mark> 이 있습니다.\n', encoding='utf-8', newline='\n')
(proj / 'sub' / '나.md').write_text('# 나 문서\n\n본문.\n', encoding='utf-8', newline='\n')
(proj / 'sub' / '깊은 곳' / '다 문서.md').write_text('# 다 문서\n\n본문.\n', encoding='utf-8', newline='\n')
(proj / 'code' / 'x.py').write_text('x = 1\n', encoding='utf-8')
(proj / 'data' / '표.csv').write_text('a,b\n1,2\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

SENT = "() => window.__sent || []"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
FOCUS = """() => { const a = document.activeElement;
  if (a?.closest('#lec-term')) return 'term';
  const sec = a?.closest('.side-sec');
  if (sec) return sec.id + ':' + (a.dataset.itemDoc ? a.dataset.itemDoc + '#' + a.dataset.line : a.dataset.doc ?? a.dataset.dir ?? a.dataset.path ?? a.id ?? '');
  if (a?.closest('#lec-panes')) return 'doc';
  return a?.id || a?.tagName || ''; }"""
OPEN = "(dir) => !!document.querySelector(`#lec-tree .row[data-dir=\"${dir}\"] .caret`)?.classList.contains('open')"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1360, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("""() => import('/static/js/store.js').then((m) => { window.__sent = [];
          const note = (ev) => (d) => window.__sent.push({ ev, text: typeof d === 'string' ? d : d.text, n: typeof d === 'string' ? null : d.n ?? null, back: typeof d === 'object' && !!d.back });
          m.on('term-paste', note('paste')); m.on('term-paste-stay', note('stay')); })""")

        def sent():
            return page.evaluate(SENT)

        def last():
            got = sent()
            return got[-1] if got else None

        def focus(sel):
            page.locator(sel).first.focus()

        def clip():
            return page.evaluate('() => navigator.clipboard.readText()')

        def fold(dir_, want):
            """문서 트리의 폴더를 펼치거나 접어 둔다 (처음 상태에 기대지 않게)"""
            if page.evaluate(OPEN, dir_) != want:
                page.locator(f'#lec-tree .row.dir[data-dir="{dir_}"] [data-toggle]').click()
                until(page, lambda: page.evaluate(OPEN, dir_) == want)

        print('[문서 목록 — 문서 행]')
        fold('sub', True)
        fold('sub/깊은 곳', False)
        page.wait_for_selector('#lec-tree .row.file[data-doc="sub/나.md"]')
        focus('#lec-tree .row.file[data-doc="sub/나.md"]')
        page.keyboard.press('Shift+ArrowRight')
        expect(page, "Shift+→: '@경로 ' 를 터미널에 — 우클릭의 ▣ 터미널과 같은 글", lambda: last() == {'ev': 'paste', 'text': '@sub/나.md ', 'n': None, 'back': True}, last)
        expect(page, "— 1번 터미널을 열어 넣고 알린다 (Enter 없이)", lambda: '1번 터미널에 넣었습니다' in page.evaluate(TOAST), lambda: page.evaluate(TOAST), ms=40000)
        expect(page, '— 초점은 터미널로', lambda: page.evaluate(FOCUS) == 'term', lambda: page.evaluate(FOCUS))
        check('— 문서는 열리지 않는다 (보내기만)', page.evaluate("() => import('/static/js/store.js').then((m) => m.S.view?.type)") == 'overview')
        # 메뉴의 ▣ 와 같은 글인지
        page.locator('#lec-tree .row.file[data-doc="sub/나.md"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden]) .menu-term')
        n0 = len(sent())
        page.locator('#lec-menu .menu-row', has_text='@sub/나.md 복사').locator('.menu-term').click()
        expect(page, "우클릭 '@경로 복사' 의 ▣ 터미널도 같은 글", lambda: len(sent()) == n0 + 1 and last()['text'] == '@sub/나.md ', last)

        print('[초점을 목록에 두고 이어 넣기]')
        focus('#lec-tree .row.file[data-doc="sub/나.md"]')
        n0 = len(sent())
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, 'Ctrl+Shift+→: 같은 글을 넣고', lambda: len(sent()) == n0 + 1 and last() == {'ev': 'stay', 'text': '@sub/나.md ', 'n': None, 'back': True}, last)
        expect(page, '— 넣은 뒤에도 초점은 그 행에', lambda: '터미널에 넣었습니다' in page.evaluate(TOAST) and page.evaluate(FOCUS) == 'lec-docs:sub/나.md', lambda: (page.evaluate(TOAST), page.evaluate(FOCUS)), ms=15000)
        page.keyboard.press('ArrowUp')
        expect(page, '— ↑ 로 옮겨', lambda: page.evaluate(FOCUS) == 'lec-docs:sub/깊은 곳', lambda: page.evaluate(FOCUS))
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '— 다음 것도 이어서 (폴더는 @폴더)', lambda: last() == {'ev': 'stay', 'text': '@sub/깊은 곳 ', 'n': None, 'back': True}, last)
        expect(page, '— 초점은 여전히 목록에', lambda: page.evaluate(FOCUS) == 'lec-docs:sub/깊은 곳', lambda: page.evaluate(FOCUS), ms=15000)

        print('[폴더 행 — 펼치기·접기는 Shift 없는 화살표]')
        check('닫힌 폴더', not page.evaluate(OPEN, 'sub/깊은 곳'))
        n0 = len(sent())
        page.keyboard.press('ArrowRight')
        expect(page, '→ 는 그대로 펼친다 (보내지 않는다)', lambda: page.evaluate(OPEN, 'sub/깊은 곳') and len(sent()) == n0, sent)
        page.keyboard.press('Shift+ArrowLeft')
        expect(page, "Shift+← 는 '@경로' 를 복사한다 — 접지 않는다", lambda: clip() == '@sub/깊은 곳' and page.evaluate(OPEN, 'sub/깊은 곳') and '복사했습니다' in page.evaluate(TOAST), lambda: (clip(), page.evaluate(TOAST)))
        page.keyboard.press('ArrowLeft')
        expect(page, '← 는 그대로 접는다', lambda: not page.evaluate(OPEN, 'sub/깊은 곳'))
        focus('#lec-tree .row.dir[data-dir="sub/깊은 곳"]')
        page.keyboard.press('Shift+ArrowRight')
        expect(page, 'Shift+→ 는 닫힌 폴더를 펼치지 않고 보낸다', lambda: len(sent()) == n0 + 1 and last()['text'] == '@sub/깊은 곳 ' and not page.evaluate(OPEN, 'sub/깊은 곳'), last)

        print('[번호를 정해 보내기]')
        focus('#lec-tree .row.file[data-doc="가.md"]')
        page.keyboard.press('Shift+Digit2')
        expect(page, 'Shift+2: 2번 터미널로 (없으면 알린다)', lambda: last() == {'ev': 'paste', 'text': '@가.md ', 'n': 1, 'back': True} and '2번 터미널이 없습니다' in page.evaluate(TOAST), lambda: (last(), page.evaluate(TOAST)))
        focus('#lec-tree .row.file[data-doc="가.md"]')
        page.keyboard.press('Control+Shift+Digit1')
        expect(page, 'Ctrl+Shift+1: 1번 터미널로, 초점은 목록에', lambda: last() == {'ev': 'stay', 'text': '@가.md ', 'n': 0, 'back': True}, last)
        expect(page, '— 넣은 뒤 초점', lambda: page.evaluate(FOCUS) == 'lec-docs:가.md', lambda: page.evaluate(FOCUS), ms=15000)
        n0 = len(sent())
        page.keyboard.press('s')
        expect(page, '글자로 찾기는 그대로 (s → sub)', lambda: page.evaluate(FOCUS) == 'lec-docs:sub' and len(sent()) == n0, lambda: page.evaluate(FOCUS))

        print('[형광펜·할 일 줄]')
        page.click('#lec-docs .kind-head[data-kind="tasks"]')
        page.wait_for_selector('#lec-tree .row.item[data-item-doc="가.md"]')
        focus('#lec-tree .row.item[data-item-doc="가.md"]')
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, "할 일 줄: '@경로 N행 '", lambda: last() == {'ev': 'stay', 'text': '@가.md 5행 ', 'n': None, 'back': True}, last)
        page.keyboard.press('Shift+ArrowLeft')
        expect(page, '— Shift+← 는 그 위치를 복사', lambda: clip() == '@가.md 5행', clip)
        page.click('#lec-docs .kind-head[data-kind="marks"]')
        page.wait_for_selector('#lec-tree .row.item.marks[data-item-doc="가.md"]')
        focus('#lec-tree .row.item.marks[data-item-doc="가.md"]')
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, "형광펜 줄도 '@경로 N행 '", lambda: last()['text'] == '@가.md 8행 ', last)
        page.click('#lec-docs .kind-head[data-kind="all"]')

        print('[코드·자료·폴더 목록]')
        page.click('#lec-code-head')
        page.locator('#lec-code-list .row[data-path="code"] [data-toggle]').click()
        page.locator('#lec-code-list .row[data-path="code/x.py"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view.code-view .cv-line')
        focus('#lec-code-list .row[data-path="code/x.py"]')
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '코드 목록의 파일', lambda: last() == {'ev': 'stay', 'text': '@code/x.py ', 'n': None, 'back': True}, last)
        expect(page, '— 초점은 그 행에', lambda: page.evaluate(FOCUS) == 'lec-code:code/x.py', lambda: page.evaluate(FOCUS), ms=15000)
        page.keyboard.press('ArrowUp')
        n0 = len(sent())
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '코드 목록의 폴더', lambda: len(sent()) == n0 + 1 and last()['text'] == '@code ', last)
        page.click('#lec-others-head')
        page.locator('#lec-others-list .row[data-path="data"] [data-toggle]').click()
        page.wait_for_selector('#lec-others-list .row[data-path="data/표.csv"]')
        focus('#lec-others-list .row[data-path="data/표.csv"]')
        page.keyboard.press('Shift+ArrowLeft')
        expect(page, '자료 목록: Shift+← 복사', lambda: clip() == '@data/표.csv', clip)
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '자료 목록의 파일', lambda: last()['text'] == '@data/표.csv ', last)
        page.click('#lec-folder-head')
        page.wait_for_selector('#lec-folder-list .row[data-path="sub"]')
        focus('#lec-folder-list .row[data-path="sub"]')
        opened = "() => !!document.querySelector('#lec-folder-list .row[data-path=\"sub\"] .caret')?.classList.contains('open')"
        was = page.evaluate(opened)
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '폴더 목록의 폴더 — 보내기만, 펼친 것은 그대로', lambda: last()['text'] == '@sub ' and page.evaluate(opened) == was, last)
        page.click('#lec-docs-head')

        print('[문서 칸의 Shift+→ 는 그대로]')
        page.locator('#lec-tree .row.file[data-doc="가.md"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view h1:has-text("가 문서")')
        page.locator('#lec-view p', has_text='머리 문단').click()
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, "문서 칸에서는 현재 줄의 '@경로 a행 '", lambda: last() == {'ev': 'stay', 'text': '@가.md 3행 ', 'n': None, 'back': False}, last)

        print('[단축키 표]')
        page.keyboard.press('Escape')
        keys = page.evaluate("() => import('/static/js/help.js').then((m) => JSON.stringify(m.SHORTCUTS || null))")
        check("단축키 표에 '목록에서 고른 것을 터미널로'", keys is not None and '사이드바 목록' in (keys or '') and 'Shift+→' in (keys or ''), (keys or '')[:120])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
