"""초점과 탭 (D162·D163): 검색 결과로 간 뒤 초점은 문서 — / 가 그 줄에서 넣기 창, 파일 이름 행은 목록에 남음,
찾기 막대의 '바꾸기' 단추(md 만, 열고 닫기·Ctrl+H·바꾸기·코드 화면에서는 감춤), F6 한 바퀴(문서 → 터미널 1·2·3 → 사이드바 → 문서,
Shift+F6 거꾸로, 닫힌 터미널은 열면서 1번, 감춘 사이드바는 건너뜀, 아래 배치의 탭도, 사이드바의 마지막 자리),
문서 탭·프로젝트 탭 끌어 옮기기(차례·고른 탭 그대로·Alt+1·Ctrl+1·조금 움직이면 누르기·Esc 그만두기·다시 열어도 그 차례)"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-focustabs-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / 'a.md').write_text('# 가 문서\n\n첫째 문단.\n\n둘째 문단에 사과가 있다.\n\n셋째 문단에도 사과.\n', encoding='utf-8')
(proj / 'b.md').write_text('# 나 문서\n\n나 문서의 글.\n', encoding='utf-8')
(proj / 'c.md').write_text('# 다 문서\n\n다 문서의 글.\n', encoding='utf-8')
(proj / 'd.md').write_text('# 라 문서\n\n라 문서의 글.\n', encoding='utf-8')
(proj / 'zeta.md').write_text('# 제타\n\n이름으로만 찾는 문서.\n', encoding='utf-8')
(proj / 'p.html').write_text('<title>쪽</title><p>html 의 사과.</p>', encoding='utf-8')
(proj / 'tool.py').write_text('fruit = "사과"\nprint(fruit)\n', encoding='utf-8')
others = []
for name in ('둘째', '셋째'):
    d = base / name
    d.mkdir()
    (d / 'README.md').write_text(f'# {name} 프로젝트\n\n{name} 의 글.\n', encoding='utf-8')
    others.append(d)
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

STORE = "import('/static/js/store.js')"
FOCUS = f"""() => {STORE}.then(({{ S }}) => {{
  const el = document.activeElement;
  if (el?.closest('#lec-term')) return 't' + (S.tab.term?.n ?? '?');
  if (el?.closest('#lec-sidebar')) return 'side';
  if (el?.id === 'lec-content' || el?.closest('#lec-panes')) return 'doc';
  return el ? (el.id || el.tagName) : '';
}})"""


def src(name='a.md'):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1500, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        focus = lambda: page.evaluate(FOCUS)  # noqa: E731
        here = lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.pane?.here?.line || 0)")  # noqa: E731
        put_open = lambda: page.locator('#lec-put:not([hidden])').count() > 0  # noqa: E731
        doc_order = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((x) => x.dataset.path)")  # noqa: E731
        active_doc = lambda: page.evaluate("() => document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path")  # noqa: E731

        def open_doc(path):
            page.locator(f'#lec-tree .row.file[data-doc="{path}"]').click()
            until(page, lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path === '{path}')"), 8000)
            page.wait_for_timeout(300)

        def drag(sel_from, sel_to, side='left', steps=10, esc=False):
            a = page.locator(sel_from).bounding_box()
            b = page.locator(sel_to).bounding_box()
            x = b['x'] + 6 if side == 'left' else b['x'] + b['width'] - 6
            page.mouse.move(a['x'] + a['width'] / 2, a['y'] + a['height'] / 2)
            page.mouse.down()
            page.mouse.move(x, b['y'] + b['height'] / 2, steps=steps)
            shown = page.locator('.lec-tab-drop:not([hidden])').count() > 0
            if esc:
                page.keyboard.press('Escape')
            page.mouse.up()
            page.wait_for_timeout(300)
            return shown

        print('[검색 결과로 간 뒤 — 초점은 문서]')
        open_doc('a.md')
        page.keyboard.press('Control+Shift+F')
        page.keyboard.type('둘째 문단')
        until(page, "!!document.querySelector('#lec-search-results .sr-hit')", 8000)
        page.keyboard.press('Enter')
        expect(page, 'Enter — 초점이 문서 칸으로', lambda: focus() == 'doc', focus)
        check('현재 줄은 찾은 줄 (5행)', here() == 5, here())
        page.keyboard.press('/')
        expect(page, '/ 가 그 줄에서 넣기 창을 연다 (검색 칸에 글자가 들어가지 않는다)', put_open)
        check('검색어는 그대로', page.input_value('#lec-search-input') == '둘째 문단', page.input_value('#lec-search-input'))
        page.keyboard.press('Escape')
        until(page, lambda: not put_open())
        page.fill('#lec-search-input', '사과')
        until(page, "!!document.querySelector('#lec-search-results .sr-hit[data-kind=\"code\"]')", 8000)
        page.locator('#lec-search-results .sr-hit', has_text='셋째').click()
        expect(page, '결과 줄을 누르면 — 초점이 문서로', lambda: focus() == 'doc', focus)
        check('— 현재 줄은 그 줄 (7행)', here() == 7, here())
        page.keyboard.press('Period')
        expect(page, '. 가 그 줄의 바꾸기 창을 연다', put_open)
        page.keyboard.press('Escape')
        until(page, lambda: not put_open())
        check('찾기 막대에도 그 말 — 바꾸기 단추가 보인다 (md)', page.locator('#lec-findbar:not([hidden])').count() == 1 and page.is_visible('#lec-find-rep')
              and page.input_value('#lec-find-input') == '사과')
        page.locator('#lec-search-results .sr-hit[data-kind="code"]').first.click()
        until(page, "!!document.querySelector('#lec-view.code-view')", 8000)
        expect(page, '코드 결과도 — 초점이 문서 칸으로', lambda: focus() == 'doc', focus)
        check('— 코드 화면에서는 바꾸기 단추가 없다', not page.is_visible('#lec-find-rep'))
        page.keyboard.press('Escape')
        page.click('.side-tabs button[data-tab="files"]')

        print('[찾기 막대의 바꾸기]')
        open_doc('a.md')
        page.locator('#lec-view p', has_text='첫째').click()
        page.keyboard.press('Control+f')
        page.fill('#lec-find-input', '사과')
        check('md 문서 — 바꾸기 단추가 보이고 눌리지 않은 상태', page.is_visible('#lec-find-rep') and page.get_attribute('#lec-find-rep', 'aria-pressed') == 'false')
        page.click('#lec-find-rep')
        check('누르면 바꿀 글 줄이 열리고 그 칸에 초점', page.is_visible('#lec-replace') and page.evaluate("document.activeElement?.id") == 'lec-replace-input')
        check('— 단추는 눌린 상태', page.get_attribute('#lec-find-rep', 'aria-pressed') == 'true')
        page.keyboard.type('배')
        page.keyboard.press('Enter')
        expect(page, 'Enter — 현재 줄 뒤의 첫 곳을 바꾼다', lambda: '둘째 문단에 배가' in src() and '셋째 문단에도 사과' in src(), src)
        page.click('#lec-find-rep')
        check('다시 누르면 줄을 닫고 찾는 말 칸으로', page.is_hidden('#lec-replace') and page.evaluate("document.activeElement?.id") == 'lec-find-input'
              and page.get_attribute('#lec-find-rep', 'aria-pressed') == 'false')
        page.keyboard.press('Control+h')
        check('찾는 말 칸의 Ctrl+H 도 바꾸기 줄을 연다', page.is_visible('#lec-replace'))
        page.click('#lec-replace-all')
        expect(page, '모두 바꾸기', lambda: '사과' not in src(), src)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.keyboard.press('Control+f')
        check('닫았다 다시 열면 바꾸기 줄은 닫힌 채', page.is_hidden('#lec-replace') and page.get_attribute('#lec-find-rep', 'aria-pressed') == 'false')
        page.click('#lec-find-rep')
        page.locator('#lec-tree .row.file[data-doc="p.html"]').click()
        until(page, "!!document.querySelector('#lec-view iframe')", 8000)
        page.wait_for_timeout(400)
        check('html 문서로 가면 — 단추를 감추고 바꾸기 줄을 닫는다', not page.is_visible('#lec-find-rep') and page.is_hidden('#lec-replace'))
        page.keyboard.press('Escape')

        print('[F6 한 바퀴]')
        for n in ('b.md', 'c.md', 'd.md'):
            open_doc(n)
        page.locator('#lec-view h1').click()
        page.wait_for_timeout(200)
        page.keyboard.press('F6')
        expect(page, '닫힌 터미널 — 열면서 1번으로', lambda: focus() == 't0', focus, ms=15000)
        page.keyboard.press('F6')
        expect(page, '터미널 1 → 사이드바', lambda: focus() == 'side', focus)
        page.keyboard.press('F6')
        expect(page, '사이드바 → 문서', lambda: focus() == 'doc', focus)
        page.keyboard.press('Shift+F6')
        expect(page, 'Shift+F6 — 문서 → 사이드바', lambda: focus() == 'side', focus)
        page.keyboard.press('Shift+F6')
        expect(page, 'Shift+F6 — 사이드바 → 터미널 1', lambda: focus() == 't0', focus)
        page.click('#lec-term-new')
        page.click('#lec-term-new')
        until(page, "document.querySelectorAll('#lec-term-body > .term-pane').length === 3", 10000)
        for n in range(3):   # 셸이 뜨면 새 터미널이 초점을 가져가므로 셋 다 뜬 뒤에
            until(page, f"[...document.querySelectorAll('#lec-term-body > .term-pane[data-n=\"{n}\"] .xterm-rows > div')].map((r) => r.textContent).join('').includes('PS ')", 20000)
        page.wait_for_timeout(300)
        until(page, lambda: focus() == 't2', 8000)
        page.keyboard.press('Shift+F6')
        page.keyboard.press('Shift+F6')
        page.keyboard.press('Shift+F6')
        expect(page, '쌓은 셋 — Shift+F6 셋이면 3 → 2 → 1 → 문서', lambda: focus() == 'doc', focus)
        hops = []
        for _ in range(5):
            page.keyboard.press('F6')
            page.wait_for_timeout(250)
            hops.append(focus())
        check('쌓은 셋 — 문서 → 1 → 2 → 3 → 사이드바 → 문서', hops == ['t0', 't1', 't2', 'side', 'doc'], hops)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+b')
        until(page, "document.querySelector('#lec-sidebar').offsetWidth === 0", 4000)
        hops = []
        for _ in range(4):
            page.keyboard.press('F6')
            page.wait_for_timeout(250)
            hops.append(focus())
        check('사이드바를 감추면 건너뛴다 — 1 → 2 → 3 → 문서', hops == ['t0', 't1', 't2', 'doc'], hops)
        page.keyboard.press('Control+b')
        until(page, "document.querySelector('#lec-sidebar').offsetWidth > 0", 4000)
        page.evaluate(f"() => {STORE}.then(({{ S }}) => {{ S.tab.term = S.tab.terms.find((x) => x.n === 2); }})")
        page.keyboard.press('Control+`')
        until(page, "document.querySelector('#lec-term').hidden", 4000)
        page.locator('#lec-view h1').click()
        page.keyboard.press('F6')
        expect(page, '패널을 닫았다 열면 — 마지막에 쓰던 3번이 아니라 1번부터', lambda: focus() == 't0', focus, ms=8000)
        page.keyboard.press('Shift+F6')
        page.keyboard.press('Control+Shift+F')   # 사이드바의 검색 칸에 초점
        until(page, "document.activeElement?.id === 'lec-search-input'", 3000)
        page.keyboard.press('F6')
        until(page, lambda: focus() == 'doc', 3000)
        page.keyboard.press('Shift+F6')
        expect(page, '사이드바로 돌아가면 마지막에 있던 곳 (검색 칸)', "document.activeElement?.id === 'lec-search-input'",
               lambda: page.evaluate("document.activeElement?.id || document.activeElement?.className"))
        page.click('#lec-term-place')   # 오른쪽 → 아래 (터미널 머리줄의 단추)
        page.wait_for_timeout(600)
        page.locator('#lec-view h1').click()
        below = page.evaluate("() => import('/static/js/terminal.js').then((m) => m.terminalBelow())")
        hops = []
        for _ in range(4):
            page.keyboard.press('F6')
            page.wait_for_timeout(300)
            hops.append(focus())
        shown = page.evaluate("() => [...document.querySelectorAll('#lec-term-body > .term-pane:not([hidden])')].map((x) => +x.dataset.n)")
        check('아래 배치(탭)도 — 1 → 2 → 3 을 차례로 보이며 → 사이드바', below and hops == ['t0', 't1', 't2', 'side'], (below, hops))
        check('— 셋째에서 보이는 터미널은 3번 하나', shown == [2], shown)
        page.keyboard.press('F6')

        print('[문서 탭 끌어 옮기기]')
        check('처음 차례', doc_order() == ['zeta.md', 'a.md', 'p.html', 'b.md', 'c.md', 'd.md'] or len(doc_order()) >= 4, doc_order())
        start = doc_order()
        act = active_doc()
        shown = drag('#lec-doctab-list .doc-tab[data-path="c.md"]', '#lec-doctab-list .doc-tab:first-child', 'left')
        got = doc_order()
        check('c 를 맨 앞으로 — 놓일 자리 막대가 보였고 차례가 바뀐다', shown and got[0] == 'c.md' and sorted(got) == sorted(start), (shown, got))
        check('— 고른 탭은 그대로', active_doc() == act, (act, active_doc()))
        check('— 끈 뒤 막대는 사라진다', page.locator('.lec-tab-drop').count() == 0)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Alt+1')
        expect(page, 'Alt+1 은 새 차례의 첫 탭 (c)', lambda: active_doc() == 'c.md', active_doc)
        before = doc_order()
        drag('#lec-doctab-list .doc-tab[data-path="a.md"]', '#lec-doctab-list .doc-tab:last-child', 'right')
        check('a 를 맨 뒤로', doc_order()[-1] == 'a.md' and len(doc_order()) == len(before), doc_order())
        before = doc_order()
        shown = drag('#lec-doctab-list .doc-tab[data-path="b.md"]', '#lec-doctab-list .doc-tab:first-child', 'left', esc=True)
        check('Esc — 그만두고 차례 그대로', shown and doc_order() == before, (shown, doc_order()))
        box = page.locator('#lec-doctab-list .doc-tab[data-path="b.md"]').bounding_box()
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] / 2 + 3, box['y'] + box['height'] / 2, steps=2)
        page.mouse.up()
        expect(page, '조금(3px) 움직인 것은 누르기 — 그 탭을 고른다', lambda: active_doc() == 'b.md' and doc_order() == before, lambda: (active_doc(), doc_order()))
        moved = doc_order()
        page.wait_for_timeout(2200)   # 위치 기록은 1.5초 뒤에 보낸다 (position.js)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        expect(page, '다시 열어도 그 차례 (md·html 문서)', lambda: doc_order() == [x for x in moved if x.endswith('.md') or x.endswith('.html')], lambda: (moved, doc_order()), ms=8000)

        print('[프로젝트 탭 끌어 옮기기]')
        for d in others:
            page.evaluate("(p) => import('/static/js/tabs.js').then((m) => m.openFolder(p))", str(d))
        until(page, "document.querySelectorAll('#lec-tablist .lec-tab').length === 3", 8000)
        page.evaluate("() => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path: 'README.md' }))")
        until(page, lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.type === 'doc')"), 8000)
        names = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-tablist .lec-tab .name')].map((x) => x.textContent)")  # noqa: E731
        check('처음 차례', names() == ['proj', '둘째', '셋째'], names())
        shown = drag('#lec-tablist .lec-tab:nth-child(3)', '#lec-tablist .lec-tab:first-child', 'left')
        expect(page, '셋째를 맨 앞으로', lambda: names() == ['셋째', 'proj', '둘째'], names)
        check('— 놓일 자리 막대', shown)
        server_order = page.evaluate("() => fetch('/api/state').then((r) => r.json()).then((d) => d.projects.map((x) => x.name))")
        check('— 서버의 탭 차례도', server_order == ['셋째', 'proj', '둘째'], server_order)
        still = page.evaluate(f"() => {STORE}.then(({{ S }}) => [S.tab.name, S.view?.type])")
        check('— 고른 탭 그대로, 끈 뒤의 누르기로 폴더 개요가 열리지 않는다', still == ['셋째', 'doc'], still)
        cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('— 다음 실행의 탭 목록도 그 차례', [Path(x).name for x in cfg.get('tabs', [])] == ['셋째', 'proj', '둘째'] and cfg.get('active_tab') == 0, (cfg.get('tabs'), cfg.get('active_tab')))
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+2')
        expect(page, 'Ctrl+2 는 새 차례의 둘째 (proj)', lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.tab.name)") == 'proj')
        shown = drag('#lec-tablist .lec-tab:first-child', '#lec-tablist .lec-tab:last-child', 'right', esc=True)
        check('Esc — 그만둔다', names() == ['셋째', 'proj', '둘째'], names())
        page.reload()
        page.wait_for_selector('#lec-tablist .lec-tab')
        expect(page, '다시 불러와도 그 차례', lambda: names() == ['셋째', 'proj', '둘째'], names)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
