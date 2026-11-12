"""고른 줄의 한 글자 키와 화살표의 가장자리 (D128).

- 한 글자 키: 줄을 고른 뒤 수식 키 없이 1~6·0·P·H·L·-·N·T·Q·C·B — 같은 키를 다시 누르면 되돌아간다, 고른 채 남는다, 한글 입력 상태, 누르고 있는 키,
  고르지 않았으면 알리기만.
- 화살표: 끝을 지나친 ↓ 가 연 빈 새 줄의 ↑ 는 읽기로 돌아온다 (줄마다 칸이 열리지 않는다). 이어서 편집할 때 빠르게 누른 ↑·↓ 도 빠지지 않는다.

기다릴 때는 고정 시간이 아니라 조건을 본다 (until).
"""
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-pickkeys-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = '# 키 시험\n\n첫 문단입니다.\n\n둘째 문단입니다.\n\n셋째 문단입니다.\n'
doc = proj / '키.md'
doc.write_text(DOC, encoding='utf-8')
PARAS = '\n\n'.join(f'평문 {i:02d} 번째 문단입니다.' for i in range(1, 13)) + '\n'
plain = proj / '평문.md'
plain.write_text(PARAS, encoding='utf-8')
server, url, port = serve(proj, base / 'config')
errors = []


def read(path):
    for _ in range(40):
        try:
            return path.read_text(encoding='utf-8')
        except OSError:   # 바꿔 끼우는 순간
            time.sleep(0.05)
    return None


HERE = "import('/static/js/store.js').then(({ S }) => S.pane?.here?.line ?? null)"
CELL = "document.querySelector('#lec-view .lec-line-edit')?.textContent ?? null"
PICKED = "!document.querySelector('#lec-st-lit')?.hidden && (document.querySelector('#lec-st-lit')?.textContent || '')"

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1300, 'height': 900}).new_page()
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(name, selector):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_selector(selector, timeout=8000)

        def reset(text=DOC):
            if read(doc) != text:
                doc.write_text(text, encoding='utf-8')
            until(page, lambda: page.locator('#lec-view p', has_text='첫 문단입니다').count() == 1 and page.locator('#lec-view h1').count() == 1)

        def pick(text):
            page.keyboard.press('Escape')
            page.locator('#lec-view :is(p, li, h1, h2, h3, blockquote p)', has_text=text).first.click()
            page.keyboard.press('Insert')
            return until(page, PICKED)

        def becomes(name, want, ms=6000):
            got = until(page, lambda: read(doc) == want and read(doc), ms)
            check(name, got == want, repr(read(doc)))

        print('[한 글자 키]')
        open_doc('키.md', '#lec-view h1:has-text("키 시험")')
        page.locator('#lec-view p', has_text='첫 문단').click()
        page.keyboard.press('Escape')
        page.keyboard.press('l')
        expect(page, '고르지 않고 누르면 고르라고 알리기만', lambda: '줄을 먼저 고르세요' in (page.text_content('#lec-toast') or ''), lambda: page.text_content('#lec-toast'))
        check('파일은 그대로', read(doc) == DOC, read(doc))

        steps = [
            ('l', 'L: 목록', DOC.replace('첫 문단', '- 첫 문단')),
            ('l', 'L 다시: 문단으로', DOC),
            ('t', 'T: 할 일', DOC.replace('첫 문단', '- [ ] 첫 문단')),
            ('t', 'T 다시: 목록으로', DOC.replace('첫 문단', '- 첫 문단')),
            ('p', 'P: 문단', DOC),
            ('2', '2: 제목 2', DOC.replace('첫 문단', '## 첫 문단')),
            ('h', 'H: 제목 2 → 3', DOC.replace('첫 문단', '### 첫 문단')),
            ('h', 'H: 제목 3 → 1', DOC.replace('첫 문단', '# 첫 문단')),
            ('h', 'H: 제목 1 → 문단', DOC),
            ('4', '4: 제목 4', DOC.replace('첫 문단', '#### 첫 문단')),
            ('4', '4 다시: 문단으로', DOC),
            ('n', 'N: 번호 목록', DOC.replace('첫 문단', '1. 첫 문단')),
            ('-', '-: 목록', DOC.replace('첫 문단', '- 첫 문단')),
            ('q', 'Q: 인용', DOC.replace('첫 문단', '> 첫 문단')),
            ('0', '0: 문단', DOC),
            ('b', 'B: 통째로 굵게', DOC.replace('첫 문단입니다.', '**첫 문단입니다.**')),
            ('b', 'B 다시: 굵게를 풂', DOC),
        ]
        check('Insert 로 현재 줄을 고름', pick('첫 문단'), page.evaluate(PICKED))
        for key, name, want in steps:
            page.keyboard.press(key)
            becomes(name, want)
            check(f'{name} — 고른 채 남음', until(page, PICKED), page.evaluate(PICKED))

        print('[강조글]')
        page.keyboard.press('c')
        becomes('C: 강조글(참고)', DOC.replace('첫 문단입니다.', '> [!NOTE]\n> 첫 문단입니다.'))
        picked = until(page, PICKED)
        check('강조글 전체를 고른 채', picked and '3' in picked and '4' in picked, picked)
        page.keyboard.press('c')
        becomes('C 다시: 참고 → 팁', DOC.replace('첫 문단입니다.', '> [!TIP]\n> 첫 문단입니다.'))
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        becomes('Ctrl+Z 두 번으로 처음으로', DOC)

        print('[여러 줄·한글·누르고 있기·기존 키]')
        reset()
        pick('첫 문단')
        page.keyboard.press('Shift+ArrowDown')
        until(page, lambda: '5' in (page.evaluate(PICKED) or ''))
        page.keyboard.press('l')
        becomes('두 문단을 고르고 L: 목록 하나', DOC.replace('첫 문단입니다.\n\n둘째', '- 첫 문단입니다.\n- 둘째'))
        reset()
        pick('둘째 문단')
        page.evaluate("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: 'ㅅ', code: 'KeyT', bubbles: true, cancelable: true }))")
        becomes('한글 입력 상태(ㅅ, 자판 T): 할 일', DOC.replace('둘째 문단', '- [ ] 둘째 문단'))
        page.keyboard.press('t')
        becomes('다시 T: 목록', DOC.replace('둘째 문단', '- 둘째 문단'))
        page.keyboard.press('p')
        becomes('P: 문단', DOC)
        page.evaluate("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', { key: 'l', code: 'KeyL', repeat: true, bubbles: true, cancelable: true }))")
        page.wait_for_timeout(400)
        check('누르고 있는 키(자동 반복)는 듣지 않는다', read(doc) == DOC, read(doc))
        page.keyboard.press('Control+Alt+3')
        becomes('Ctrl+Alt+3 도 그대로', DOC.replace('둘째 문단', '### 둘째 문단'))
        page.keyboard.press('Control+z')
        becomes('되돌림', DOC)
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.keyboard.press('2')
        page.wait_for_timeout(400)
        check('고른 줄을 풀면 숫자를 눌러도 그대로', read(doc) == DOC, read(doc))

        print('[고른 줄 바꾸기 창의 키]')
        pick('셋째 문단')
        page.locator('#lec-view p', has_text='셋째 문단').click(button='right')
        page.locator('#lec-menu button, #lec-menu li', has_text='고른 줄 바꾸기').first.click()
        page.wait_for_selector('#lec-put:not([hidden])')
        hints = page.evaluate("Object.fromEntries([...document.querySelectorAll('#lec-put li[role=option]')].map((li) => [li.querySelector('.t')?.textContent, li.querySelector('kbd')?.textContent || '']))")
        check('창의 항목 옆에 한 글자 키', hints.get('목록') == 'L' and hints.get('할 일') == 'T' and hints.get('제목 2') == '2' and hints.get('강조글 — 참고') == 'C', hints)
        page.keyboard.press('Escape')

        print('[화살표 — 끝을 지나친 ↓ 와 다시 ↑]')
        open_doc('평문.md', '#lec-view p')
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Escape')
        page.evaluate("""() => { window.__up = []; window.addEventListener('keydown', (e) => {
          if (e.key === 'ArrowUp') window.__up.push(!!document.querySelector('#lec-view .lec-line-edit')); }, true); }""")
        for _ in range(15):
            page.keyboard.press('ArrowDown')
            page.wait_for_timeout(60)
        check('끝을 지나친 ↓: 문서 끝에 빈 새 줄', until(page, f'({CELL}) === ""'), page.evaluate(CELL))
        page.keyboard.press('ArrowUp')
        expect(page, '빈 새 줄의 ↑: 칸을 걷고 읽기로, 마지막 줄에', lambda: page.evaluate(CELL) is None and page.evaluate(HERE) == 23, lambda: (page.evaluate(CELL), page.evaluate(HERE)))
        for _ in range(11):
            page.keyboard.press('ArrowUp')
            page.wait_for_timeout(60)
        expect(page, '다시 ↑ 로 맨 위까지 — 줄마다 칸이 열리지 않는다', lambda: page.evaluate(HERE) == 1 and page.evaluate(CELL) is None, lambda: (page.evaluate(HERE), page.evaluate(CELL)))
        ups = page.evaluate('window.__up')
        check('↑ 를 누를 때 칸이 열려 있던 것은 첫 번째(빈 새 줄)뿐', ups[:1] == [True] and not any(ups[1:]), ups)
        check('파일은 그대로', read(plain) == PARAS)

        print('[화살표 — 이어서 편집할 때 빠르게]')
        page.locator('#lec-view p', has_text='평문 12').click()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        for _ in range(11):   # 쉬지 않고 — 저장하고 다음 칸을 여는 사이에 누른 키도
            page.keyboard.press('ArrowUp')
        got = until(page, lambda: (page.evaluate(CELL) or '').startswith('평문 01') and page.evaluate(HERE) == 1, 8000)
        check('↑ 열한 번: 맨 위 줄의 칸에 (빠진 키 없이, 되돌아가지 않고)', got, (page.evaluate(CELL), page.evaluate(HERE)))
        for _ in range(5):
            page.keyboard.press('ArrowDown')
        got = until(page, lambda: (page.evaluate(CELL) or '').startswith('평문 06') and page.evaluate(HERE) == 11, 8000)
        check('↓ 다섯 번: 여섯째 줄의 칸에', got, (page.evaluate(CELL), page.evaluate(HERE)))
        page.keyboard.press('Escape')
        check('편집은 아무것도 바꾸지 않음', read(plain) == PARAS)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
