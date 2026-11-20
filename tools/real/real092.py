"""0.92.0 — 빌드본·설치본 실제 창(WebView2)에서: 검색 결과로 간 뒤 / (넣기 창), 찾기 막대의 바꾸기 단추, Enter 키(Ctrl+Enter 줄 선택·Shift+Enter 새 줄)와 특수 문자 창, F6 한 바퀴(실제 셸 셋),
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

base = Path(tempfile.mkdtemp(prefix='lec-real092-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '보고서'
proj.mkdir()
(proj / 'a.md').write_text('# 가 문서\n\n첫째 문단.\n\n둘째 문단에 사과가 있다.\n\n셋째 문단.\n', encoding='utf-8')
for n in ('b', 'c', 'd'):
    (proj / f'{n}.md').write_text(f'# {n} 문서\n\n{n} 의 글.\n', encoding='utf-8')
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
    bar = page.locator('.lec-tab-drop:not([hidden])').count() > 0
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

        print('[문서 탭 끌어 옮기기]')
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
        R.check('문서 탭 차례가 남는다', R.wait(lambda: order() == moved, 10), (moved, order()))
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
