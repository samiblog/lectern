"""v0.48.0 의 빈틈: 줄 번호와 다른 기능이 만나는 곳, 코드 화면의 되돌리기, 체크 칸의 다시 하기"""
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop



PARA = '긴 문단입니다. ' * 40
DOC = '# 번호 문서\n\n첫 문단\n\n- [ ] 할 일\n\n> [!NOTE]\n> 박스글\n\n```mermaid\ngraph TD; A-->B\n```\n\n$$x^2$$\n\n![그림](없는그림.png)\n\n' + ''.join(f'## 절 {i}\n\n' + (PARA + '\n\n') * 5 for i in range(1, 5))
base = Path(tempfile.mkdtemp(prefix='lec-48-'))
proj = base / 'proj'
(proj / 'code').mkdir(parents=True)
doc = proj / 'a.md'
doc.write_text(DOC, encoding='utf-8')
(proj / 'b.md').write_text('# 둘째\n\n둘째 글\n', encoding='utf-8')
big = proj / 'big.md'
big.write_text('# 큰 문서\n\n' + '\n\n'.join(f'문단 {i}' for i in range(1, 6001)) + '\n', encoding='utf-8')
(proj / 'deck.md').write_text('---\nmarp: true\n---\n\n# 표지\n\n글\n', encoding='utf-8')
code = proj / 'code' / 'x.py'
code.write_text('a = 1\nb = 2\nc = 3\n', encoding='utf-8')
server, url, port = serve(proj, base / 'config')


def src(path, n):
    for _ in range(40):
        try:
            return path.read_text(encoding='utf-8').split('\n')[n - 1]
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간 (ReplaceFileW)
            time.sleep(0.02)
    return path.read_text(encoding='utf-8').split('\n')[n - 1]


def until(path, n, want, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        if src(path, n) == want:
            return True
        time.sleep(0.05)
    return False


GUTTER = '#lec-content > .lec-gutter span'
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR').new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=300: page.wait_for_timeout(ms)
        nums = lambda: page.evaluate(f"[...document.querySelectorAll('{GUTTER}')].map((s) => s.textContent)")
        opened = lambda path, title: (page.locator(f'#lec-tree .row.file[data-doc="{path}"]').click(), page.wait_for_selector(f'#lec-view h1:has-text("{title}")'), settle())
        top = lambda: page.evaluate("document.querySelector('#lec-content').scrollTop")

        print('[줄 번호와 다른 블록]')
        opened('a.md', '번호 문서')
        page.keyboard.press('Alt+l')
        page.wait_for_selector(GUTTER)
        settle(600)
        got = nums()
        want_lines = {'1', '3', '5', '7', '10', '14', '16', '18'}
        check('제목·문단·할 일·박스글·다이어그램·수식·그림에 번호', want_lines <= set(got), got[:12])
        check('번호가 늘어나는 차례', [int(x) for x in got] == sorted(int(x) for x in got), got[:12])
        ys = page.evaluate(f"[...document.querySelectorAll('{GUTTER}')].map((s) => s.getBoundingClientRect().top)")
        check('번호끼리 겹치지 않음', all(b - a >= 9 for a, b in zip(ys, ys[1:])), min((b - a for a, b in zip(ys, ys[1:])), default=None))
        print('[켜고 끌 때 읽던 자리]')
        page.evaluate("document.querySelector('#lec-content').scrollTop = 2500")
        settle()
        anchor = "(() => { const t = document.querySelector('#lec-content').getBoundingClientRect().top; return [...document.querySelector('#lec-view').children].find((e) => e.getBoundingClientRect().bottom > t).dataset.lines; })()"
        a0 = page.evaluate(anchor)
        page.keyboard.press('Alt+l')
        settle()
        a1 = page.evaluate(anchor)
        page.keyboard.press('Alt+l')
        settle()
        a2 = page.evaluate(anchor)
        lines_of = [int(x.split('-')[0]) for x in (a0, a1, a2)]
        check('끄고 켜도 같은 곳을 봄 (폭이 바뀌어 글이 다시 흐르니 이웃 문단까지)', max(lines_of) - min(lines_of) <= 2, (a0, a1, a2))
        print('[하이라이트·한 줄 편집과 함께]')
        page.evaluate("document.querySelector('#lec-content').scrollTop = 0")
        settle()
        page.locator('#lec-view p', has_text='첫 문단').click()
        page.keyboard.press('Shift+Enter')
        settle()
        hit = page.evaluate(f"""(() => {{ const g = document.querySelector('{GUTTER}').getBoundingClientRect(); const e = document.elementFromPoint(g.left + 2, g.top + 3);
          return e?.closest('.lec-gutter') ? 'gutter' : e?.tagName; }})()""")
        z = page.evaluate("[getComputedStyle(document.querySelector('.lec-gutter')).zIndex, getComputedStyle(document.querySelector('.lec-here')).zIndex]")
        check('번호는 누르기를 막지 않고 하이라이트·삼각형 아래', hit != 'gutter' and int(z[0]) < int(z[1]), (hit, z))
        page.keyboard.press('Escape')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        settle()
        during = nums()
        page.keyboard.type('X')
        page.keyboard.press('Enter')
        until(doc, 3, '첫 문단X')
        page.wait_for_selector('#lec-view p:has-text("첫 문단X")')
        settle(400)
        check('한 줄 편집 중에도 번호가 그대로, 저장 뒤에도', during[:3] == ['1', '3', '5'] and nums()[:3] == ['1', '3', '5'], (during[:4], nums()[:4]))
        print('[체크 칸·코드 화면의 되돌리기와 다시 하기]')
        page.keyboard.press('Control+z')
        z1 = until(doc, 3, '첫 문단')
        settle(500)
        page.keyboard.press('Control+y')
        y1 = until(doc, 3, '첫 문단X')
        settle(500)
        page.locator('#lec-view .task-list-item-checkbox').click()
        c1 = until(doc, 5, '- [x] 할 일')
        settle(500)
        page.keyboard.press('Control+z')
        c2 = until(doc, 5, '- [ ] 할 일')
        settle(500)
        page.keyboard.press('Control+y')
        c3 = until(doc, 5, '- [x] 할 일')
        settle(500)
        page.keyboard.press('Control+z')
        until(doc, 5, '- [ ] 할 일')
        settle(500)
        page.keyboard.press('Control+z')
        until(doc, 3, '첫 문단')
        settle(500)
        check('문서: 한 줄 편집·체크 칸을 오감', all((z1, y1, c1, c2, c3)) and src(doc, 3) == '첫 문단' and src(doc, 5) == '- [ ] 할 일', (z1, y1, c1, c2, c3))
        page.keyboard.press('Control+p')
        page.keyboard.type('x.py')
        page.locator('#lec-palette-list li.code', has_text='code/x.py').click()
        page.wait_for_selector('#lec-view.code-view .cv-line[data-line="2"]')
        settle()
        page.locator('#lec-view .cv-line[data-line="2"]').click()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('End')
        page.keyboard.type('2')
        page.keyboard.press('Enter')
        v1 = until(code, 2, 'b = 22')
        settle(900)
        page.keyboard.press('Control+z')
        v2 = until(code, 2, 'b = 2')
        settle(900)
        page.keyboard.press('Control+y')
        v3 = until(code, 2, 'b = 22')
        settle(900)
        page.keyboard.press('Control+z')
        until(code, 2, 'b = 2')
        check('코드 화면에서도 오감', v1 and v2 and v3, (v1, v2, v3, src(code, 2)))
        before = doc.read_text(encoding='utf-8')
        page.locator('#lec-tree .row.file[data-doc="b.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째")')
        settle()
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+y')
        settle(400)
        check('기록이 없는 문서의 Ctrl+Y 는 아무것도 안 함', doc.read_text(encoding='utf-8') == before and page.evaluate("document.activeElement.tagName") != 'INPUT')
        print('[편집 칸·찾기 칸의 키]')
        opened('a.md', '번호 문서')
        page.locator('#lec-view p', has_text='첫 문단').click()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('Alt+l')
        settle()
        in_cell = len(nums()) > 0
        page.keyboard.press('Escape')
        page.keyboard.press('Control+f')
        page.keyboard.type('l')
        page.keyboard.press('Alt+l')
        settle()
        in_find = len(nums()) > 0
        page.keyboard.press('Escape')
        check('글을 치는 칸에서 Alt+L 은 줄 번호를 바꾸지 않음', in_cell and in_find, (in_cell, in_find))
        print('[모두 펼치기]')
        page.locator('#lec-tree .row.file[data-doc="b.md"]').click(modifiers=['Control'])
        page.wait_for_function("document.querySelectorAll('#lec-doctab-list .doc-tab').length === 2")
        settle(500)
        page.click('#lec-doctab-spread')
        page.wait_for_function("document.documentElement.classList.contains('spread-on')")
        settle(700)
        panes = page.evaluate("[...document.querySelectorAll('#lec-panes .sp-cell')].map((c) => c.querySelectorAll('.lec-gutter span').length)")
        check('칸마다 번호', len(panes) == 2 and all(n > 0 for n in panes), panes)
        page.click('#lec-doctab-spread')
        page.wait_for_function("!document.documentElement.classList.contains('spread-on')")
        settle(300)
        print('[슬라이드·폴더 개요·큰 문서]')
        opened('deck.md', '표지')
        d = [page.locator('#lec-content > .lec-gutter').count(), page.evaluate("document.querySelector('#lec-btn-lines').disabled")]
        check('슬라이드는 쓰지 않음', d == [0, True], d)
        page.locator('#lec-status button', has_text='문서로 보기').click()
        page.wait_for_function("!document.querySelector('#lec-view').classList.contains('lec-deck')")
        settle(400)
        check('문서로 보면 번호', len(nums()) > 0, nums())
        t0 = time.time()
        page.locator('#lec-tree .row.file[data-doc="big.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("큰 문서")')
        page.wait_for_function(f"document.querySelectorAll('{GUTTER}').length === 6001", timeout=15000)
        drawn = time.time() - t0
        lag = page.evaluate("""() => new Promise((done) => { const sc = document.querySelector('#lec-content'); let n = 0; const t = performance.now();
          const step = () => { sc.scrollTop += 400; if (++n < 30) requestAnimationFrame(step); else done(performance.now() - t); }; requestAnimationFrame(step); })""")
        check('6천 문단 문서에서 3초 안에 그리고 스크롤이 끌리지 않음', drawn < 3 and lag < 1500, (round(drawn, 2), round(lag)))
        print(f'    6천 문단: 그리기 {drawn:.2f}초, 스크롤 30번 {lag:.0f}ms')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    stop(server, base)
report()
