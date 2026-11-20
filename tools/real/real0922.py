"""0.92.2 — 빌드본·설치본 실제 창(WebView2)에서: Tab 이 문서 밖으로 나가지 않는다(실제 셸 셋을 연 채 md·링크 없는 문서·html·코드·모두 펼치기), 칸의 Enter 는 저장하고 현재 줄만 다음 줄로, 읽는 화면의 Enter 는 한 줄 편집·Alt+Enter 는 제목 접기와 링크 열기, 특수 문자 236자(뺀 글자 없음), 검색 결과로 간 뒤 / (넣기 창), 찾기 막대의 바꾸기 단추, Enter 키(Ctrl+Enter 줄 선택·Shift+Enter 새 줄)와 특수 문자 창, F6 한 바퀴(실제 셸 셋),
문서 탭·프로젝트 탭 끌어 옮기기와 다시 실행한 뒤의 차례 (시험용 설정 폴더·개인 폴더 — 실제 설정과 ~/.claude 는 건드리지 않는다).
  python real092.py --exe <Lectern.exe>"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real0922-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '보고서'
proj.mkdir()
(proj / 'a.md').write_text('# 가 문서\n\n첫째 문단.\n\n둘째 문단에 사과가 있다.\n\n셋째 문단.\n\n## 접는 절\n\n절 안의 글.\n\n링크 줄: [나 문서](b.md) 로.\n', encoding='utf-8')
for n in ('b', 'c', 'd'):
    (proj / f'{n}.md').write_text(f'# {n} 문서\n\n{n} 의 글.\n', encoding='utf-8')
(proj / 'page.html').write_text('<title>쪽</title><p><a href="#a">하나</a> <input value="칸"> <button>단추</button></p>', encoding='utf-8')
(proj / 'tool.py').write_text('x = 1' + chr(10) + 'y = 2' + chr(10), encoding='utf-8')
second = base / '둘째'
second.mkdir()
(second / 'README.md').write_text('# 둘째\n\n둘째 프로젝트.\n', encoding='utf-8')

STORE = "import('/static/js/store.js')"


def saved():
    for _ in range(40):
        try:
            return json.loads((config / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            time.sleep(0.05)
    return {}


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', timeout=40000)
    page.wait_for_timeout(1500)
    return b, page


def drag(page, sel_from, sel_to, side='left', esc=False):
    a = page.locator(sel_from).bounding_box()
    t = page.locator(sel_to).bounding_box()
    x = t['x'] + 6 if side == 'left' else t['x'] + t['width'] - 6
    page.mouse.move(a['x'] + a['width'] / 2, a['y'] + a['height'] / 2)
    page.mouse.down()
    page.mouse.move(x, t['y'] + t['height'] / 2, steps=12)
    bar = R.wait(lambda: page.locator('.lec-tab-drop:not([hidden])').count() > 0, 1.5)   # 막대는 다음 화면 갱신(rAF)에 놓인다
    if esc:
        page.keyboard.press('Escape')
    page.mouse.up()
    page.wait_for_timeout(400)
    return bar


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.VERSION, version)
        focus = lambda: page.evaluate(f"""() => {STORE}.then(({{ S }}) => {{
          const el = document.activeElement;
          if (el?.closest('#lec-term')) return 't' + (S.tab.term?.n ?? '?');
          if (el?.closest('#lec-sidebar')) return 'side';
          if (el?.id === 'lec-content' || el?.closest('#lec-panes')) return 'doc';
          return el ? (el.id || el.tagName) : '';
        }})""")  # noqa: E731
        here = lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.pane?.here?.line || 0)")  # noqa: E731
        order = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((x) => x.dataset.path)")  # noqa: E731
        active = lambda: page.evaluate("() => document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path")  # noqa: E731

        print('[검색 결과로 간 뒤 /]')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        R.wait(lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path === 'a.md')"), 10)
        page.wait_for_timeout(500)
        page.keyboard.press('Control+Shift+F')
        page.keyboard.type('사과')
        R.wait(lambda: page.locator('#lec-search-results .sr-hit').count() > 0, 10)
        page.keyboard.press('Enter')
        R.check('Enter — 초점은 문서, 현재 줄은 찾은 줄', R.wait(lambda: focus() == 'doc' and here() == 5, 5), (focus(), here()))
        page.keyboard.press('/')
        R.check('/ — 그 줄 아래에 넣기 창 (검색 칸에 글자가 들어가지 않음)', R.wait(lambda: page.locator('#lec-put:not([hidden])').count() > 0, 5)
                and page.input_value('#lec-search-input') == '사과', page.input_value('#lec-search-input'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        print('[찾기 막대의 바꾸기]')
        R.check('검색으로 열린 찾기 막대에 바꾸기 단추', page.is_visible('#lec-find-rep'))
        page.click('#lec-find-rep')
        R.check('누르면 바꿀 글 줄과 그 칸에 초점', page.is_visible('#lec-replace') and page.evaluate("document.activeElement?.id") == 'lec-replace-input')
        page.keyboard.type('배')
        page.keyboard.press('Enter')
        R.check('Enter — 그 문서에서 바꾸고 저장', R.wait(lambda: '배가 있다' in (proj / 'a.md').read_text(encoding='utf-8'), 6))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        print('[Enter 키와 특수 문자]')
        lit = lambda: (page.text_content('#lec-st-lit') or '') if page.locator('#lec-st-lit:not([hidden])').count() else ''  # noqa: E731
        page.locator('#lec-view p', has_text='셋째').click()
        page.wait_for_timeout(300)
        page.keyboard.press('Control+Enter')
        R.check('Ctrl+Enter — 줄 선택(하이라이트)', R.wait(lambda: lit().startswith('하이라이트'), 4), lit())
        page.keyboard.press('Control+Enter')
        page.keyboard.press('Shift+Enter')
        R.check('Shift+Enter — 아래에 새 줄', R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 4))
        page.keyboard.type('새 줄 ')
        page.keyboard.press('Control+Shift+Semicolon')
        R.check('칸의 Ctrl+Shift+; — 특수 문자 창', R.wait(lambda: page.locator('#lec-chars:not([hidden])').count() == 1, 6))
        page.keyboard.type('화살표')
        page.keyboard.press('Enter')
        page.keyboard.press('Control+Enter')
        R.check('넣고 Ctrl+Enter — 저장하고 그 줄 선택', R.wait(lambda: '새 줄 →' in (proj / 'a.md').read_text(encoding='utf-8') and lit().startswith('하이라이트'), 8), ((proj / 'a.md').read_text(encoding='utf-8')[-40:], lit()))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        print('[Enter 는 편집, Alt+Enter 는 열기 (D166) · 특수 문자 정리]')
        page.locator('#lec-view h2', has_text='접는 절').click()
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        R.check('제목 줄의 Enter — 한 줄 편집 (접지 않는다)', R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 4)
                and not page.evaluate("() => !!document.querySelector('#lec-view h2.lec-folded')"))
        page.keyboard.press('Enter')
        R.check('칸의 Enter — 닫는다, 파일 그대로, 현재 줄은 다음 줄로 (D168)', R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 0, 4) and '## 접는 절\n' in (proj / 'a.md').read_text(encoding='utf-8')
                and R.wait(lambda: here() == (proj / 'a.md').read_text(encoding='utf-8').split(chr(10)).index('## 접는 절') + 3, 4), here())
        page.keyboard.press('ArrowUp')   # 제목 줄로 돌아가서
        page.wait_for_timeout(300)
        page.keyboard.press('Alt+Enter')
        R.check('제목 줄의 Alt+Enter — 절 접기', R.wait(lambda: page.evaluate("() => !!document.querySelector('#lec-view h2.lec-folded')"), 4))
        page.keyboard.press('Alt+Enter')
        page.wait_for_timeout(300)
        page.locator('#lec-view p', has_text='링크 줄').click()
        page.wait_for_timeout(300)
        page.keyboard.press('Alt+Enter')
        R.check('링크 줄의 Alt+Enter — 그 문서가 열린다', R.wait(lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path)") == 'b.md', 6), page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path)"))
        page.keyboard.press('Alt+ArrowLeft')
        R.wait(lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path)") == 'a.md', 6)
        page.wait_for_timeout(500)
        page.locator('#lec-view p', has_text='첫째').click()
        page.keyboard.press('Control+Shift+Semicolon')
        R.wait(lambda: page.locator('#lec-chars:not([hidden])').count() == 1, 6)
        shown = page.evaluate("() => [...document.querySelectorAll('#lec-chars .cp-grid button')].map((b) => b.textContent).join('')")
        R.check('특수 문자 — 236자, 뺀 글자(• ☐ ☑ − ✓ ⑳ ☀)가 없다', len(set(shown)) == 236 and not set('•☐☑☒−✓✗⑳☀✉') & set(shown), (len(set(shown)), set('•☐☑☒−✓✗⑳☀✉') & set(shown)))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        print('[칸의 Enter — 저장하고 현재 줄만 다음 줄로 (D168)]')
        here_line = lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)")  # noqa: E731
        page.locator('#lec-view p', has_text='첫째').click()
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 4)
        page.keyboard.press('End')
        page.keyboard.type(' 고침')
        page.keyboard.press('Enter')
        R.check('고치고 Enter — 저장하고 닫고 현재 줄은 다음 줄 (열지 않음)', R.wait(lambda: '첫째 문단. 고침' in (proj / 'a.md').read_text(encoding='utf-8')
                and page.locator('#lec-view .lec-line-edit').count() == 0 and here_line() == 5, 6), here_line())
        page.keyboard.press('Enter')
        R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 4)
        page.keyboard.press('Enter')
        R.check('Enter·Enter — 또 다음 줄로', R.wait(lambda: here_line() == 7 and page.locator('#lec-view .lec-line-edit').count() == 0, 6), here_line())
        page.keyboard.press('Control+End')
        page.wait_for_timeout(300)
        last = here_line()
        page.keyboard.press('Enter')
        R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 4)
        page.keyboard.press('Enter')
        page.wait_for_timeout(800)
        R.check('마지막 줄의 Enter — 현재 줄은 그대로', here_line() == last and page.locator('#lec-view .lec-line-edit').count() == 0, (last, here_line()))

        print('[F6 한 바퀴 — 실제 셸 셋]')
        page.click('.side-tabs button[data-tab="files"]')
        for n in ('b.md', 'c.md', 'd.md'):
            page.locator(f'#lec-tree .row.file[data-doc="{n}"]').click()
            R.wait(lambda: active() == n, 10)
        page.locator('#lec-view h1').click()
        page.keyboard.press('F6')
        R.check('닫힌 터미널 — 열면서 1번으로', R.wait(lambda: focus() == 't0', 20), focus())
        page.click('#lec-term-new')
        page.click('#lec-term-new')
        for n in range(3):
            R.wait(lambda: 'PS ' in page.evaluate(f"""() => [...document.querySelectorAll('#lec-term-body > .term-pane[data-n="{n}"] .xterm-rows > div')].map((r) => r.textContent).join('')"""), 30)
        page.wait_for_timeout(800)
        page.locator('#lec-view h1').click()
        hops = []
        for key in ['F6'] * 5 + ['Shift+F6'] * 5:
            page.keyboard.press(key)
            page.wait_for_timeout(350)
            hops.append(focus())
        R.check('문서 → 1 → 2 → 3 → 사이드바 → 문서, Shift+F6 은 거꾸로', hops == ['t0', 't1', 't2', 'side', 'doc', 'side', 't2', 't1', 't0', 'doc'], hops)

        print('[Tab — 문서 밖으로 나가지 않는다 (D167), 실제 셸 셋을 연 채]')
        WHERE = """() => { const a = document.activeElement; if (!a || a === document.body) return 'body';
          if (a.closest('#lec-term')) return 'term'; if (a.closest('#lec-sidebar')) return 'side';
          if (a.closest('#lec-toolbar, #lec-tabbar, #lec-status, #lec-doctabs')) return 'chrome';
          return a.closest('#lec-panes') ? (a.tagName === 'IFRAME' ? 'frame' : 'doc') : 'other'; }"""

        def tab_run(n, key='Tab'):
            got = []
            for _ in range(n):
                page.keyboard.press(key)
                page.wait_for_timeout(150)
                got.append(page.evaluate(WHERE))
            return got

        def open_path(kind, path, ready):
            page.evaluate("([k, p]) => import('/static/js/store.js').then((m) => m.emit('open', { type: k, path: p }))", [kind, path])
            R.wait(lambda: page.locator(ready).count() > 0, 10)
            page.wait_for_timeout(700)

        open_path('doc', 'a.md', '#lec-view h2')
        page.locator('#lec-view p', has_text='셋째').click()
        got = tab_run(6) + tab_run(4, 'Shift+Tab')
        R.check('md 문서 — Tab 여섯 번·Shift+Tab 네 번이 모두 문서 안', all(g == 'doc' for g in got), got)
        open_path('doc', 'b.md', '#lec-view h1')
        page.locator('#lec-view p').first.click()
        got = tab_run(5)
        R.check('링크 없는 문서 — 문서 안', all(g == 'doc' for g in got), got)
        open_path('doc', 'page.html', '#lec-view iframe')
        page.wait_for_timeout(800)
        page.frame_locator('#lec-view iframe').locator('p').first.click(position={'x': 2, 'y': 2})
        got = tab_run(7) + tab_run(3, 'Shift+Tab')
        R.check('html 문서 — iframe 안에서 돈다 (입력 칸·단추를 지나도)', all(g == 'frame' for g in got), got)
        open_path('code', 'tool.py', '#lec-view .cv-line')
        page.locator('#lec-view .cv-line').first.click()
        got = tab_run(6)
        R.check('코드 화면 — 머리줄 단추를 돌고 문서 안', all(g == 'doc' for g in got), got)
        open_path('doc', 'a.md', '#lec-view h2')
        page.click('#lec-doctab-spread')
        page.wait_for_timeout(800)
        page.locator('#lec-view p', has_text='셋째').click()
        got = tab_run(6)
        R.check('모두 펼치기(터미널 칸이 같은 격자) — 문서 안', all(g == 'doc' for g in got), got)
        page.click('#lec-doctab-spread')
        page.wait_for_timeout(500)
        page.locator('#lec-view p', has_text='셋째').click()
        page.keyboard.press('F6')
        R.check('떠나는 것은 F6 — 터미널로', R.wait(lambda: page.evaluate(WHERE) == 'term', 6), page.evaluate(WHERE))
        page.keyboard.press('Shift+F6')
        page.wait_for_timeout(400)

        print('[문서 탭 끌어 옮기기]')
        for n in ('a', 'b', 'c', 'd'):   # 앞의 Tab 단계가 같은 탭에서 바꿔 열었다 — 문서 탭 넷을 둔다
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))", f'{n}.md')
            page.wait_for_timeout(500)
        R.wait(lambda: {'a.md', 'b.md', 'c.md', 'd.md'} <= set(order()), 8)
        start = order()
        act = active()
        bar = drag(page, '#lec-doctab-list .doc-tab[data-path="c.md"]', '#lec-doctab-list .doc-tab:first-child')
        R.check('c 를 맨 앞으로 — 막대가 보였고 차례가 바뀜, 고른 탭 그대로', bar and order()[0] == 'c.md' and sorted(order()) == sorted(start) and active() == act, (bar, order(), act, active()))
        before = order()
        drag(page, '#lec-doctab-list .doc-tab[data-path="b.md"]', '#lec-doctab-list .doc-tab:last-child', 'right', esc=True)
        R.check('Esc — 그만두고 그대로', order() == before, order())
        moved = order()

        print('[프로젝트 탭 끌어 옮기기]')
        page.evaluate("(p) => import('/static/js/tabs.js').then((m) => m.openFolder(p))", str(second))
        R.wait(lambda: page.locator('#lec-tablist .lec-tab').count() == 2, 10)
        names = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-tablist .lec-tab .name')].map((x) => x.textContent)")  # noqa: E731
        bar = drag(page, '#lec-tablist .lec-tab:nth-child(2)', '#lec-tablist .lec-tab:first-child')
        R.check('둘째를 맨 앞으로', bar and R.wait(lambda: names() == ['둘째', '보고서'], 5), names())
        R.check('— 설정의 탭 목록도 그 차례', R.wait(lambda: [Path(x).name for x in saved().get('tabs', [])] == ['둘째', '보고서'], 5), saved().get('tabs'))
        page.click('#lec-tablist .lec-tab:nth-child(2)')
        page.wait_for_timeout(2500)   # 문서 탭 차례는 1.5초 뒤에 남긴다
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        time.sleep(2)

        print('[다시 실행]')
        proc, cdp = R.launch(proj, config)
        R.CONN.update(cdp=cdp)
        b, page = connect(p, cdp)
        names = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-tablist .lec-tab .name')].map((x) => x.textContent)")  # noqa: E731
        R.check('프로젝트 탭 차례가 남는다', R.wait(lambda: names() == ['둘째', '보고서'], 10), names())
        page.evaluate("() => import('/static/js/store.js').then(({ S }) => import('/static/js/tabs.js').then((m) => m.selectTab(S.tabs.find((x) => x.name === '보고서'))))")
        moved = [x for x in moved if x.endswith(('.md', '.html'))]   # 다음 실행에는 md·html 문서 탭만 되살린다 (코드 탭은 아님 — openDocs)
        R.check('문서 탭 차례가 남는다 (md·html 문서 탭)', R.wait(lambda: order() == moved, 10), (moved, order()))
        print('[되살린 탭 옆의 고른 탭을 닫을 때 — 빈 탭이 끼지 않는다]')
        deferred = page.evaluate("import('/static/js/store.js').then(({ S }) => S.tab.panes.filter((x) => x.deferred).length)")
        page.evaluate("""() => { window.__names = []; const list = document.querySelector('#lec-doctab-list');
          window.__mo = new MutationObserver(() => window.__names.push(...[...list.querySelectorAll('.doc-tab .name')].map((e) => e.textContent)));
          window.__mo.observe(list, { childList: true, subtree: true, characterData: true }); }""")
        for _ in range(2):
            page.hover('#lec-doctab-list .doc-tab.active')
            page.wait_for_timeout(200)
            page.click('#lec-doctab-list .doc-tab.active .tab-close')
            page.wait_for_timeout(900)
        seen = page.evaluate('window.__names')
        R.check('되살린 탭이 있고, 고른 탭을 두 번 닫는 동안 빈 탭이 한 번도 없다', deferred >= 1 and bool(seen) and '빈 탭' not in seen, (deferred, sorted(set(seen))))
        b.close()
except Exception:
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
