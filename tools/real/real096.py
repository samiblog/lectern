"""0.96.0 — 실제 창(WebView2)에서 작은 수정 여덟 가지 (D177~D180).
  python real096.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
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

base = Path(tempfile.mkdtemp(prefix='lec-real096-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'settings_section': 'ai'}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '연구'
for folder in ('보고', '자료', 'src'):
    (proj / folder).mkdir(parents=True)
LINES = ['구리 재고가 줄었다.', '니켈 값은 그대로다.', '리튬은 다시 올랐다.']
(proj / '보고' / '분석.md').write_bytes(('# 시장 점검\n\n' + '\n'.join(LINES) + '\n').encode('utf-8'))
(proj / '보고' / 'README.md').write_bytes('# 개요\n\n보고.\n'.encode('utf-8'))
(proj / '자료' / 'README.md').write_bytes('# 개요\n\n자료.\n'.encode('utf-8'))
(proj / 'src' / 'load.py').write_bytes(b'x = 1\n')
STORE = "import('/static/js/store.js')"
ROWS = "() => { const el = document.querySelector('#lec-view p'); const r = document.createRange(); r.selectNodeContents(el); return new Set([...r.getClientRects()].filter((x) => x.width > 1).map((x) => Math.round(x.top / 4))).size; }"
SPOT = """(t) => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.textContent.indexOf(t); if (i < 0) continue;
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + t.length); const b = r.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; } return null; }"""
OVERLAP = """() => { const bar = document.querySelector('#lec-toolbar'); const items = [...bar.querySelectorAll(':scope > *, :scope > * > button')].filter((e) => e.offsetParent && e.getBoundingClientRect().width > 0);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) { if (items[i].contains(items[j]) || items[j].contains(items[i])) continue;
    const a = items[i].getBoundingClientRect(), b = items[j].getBoundingClientRect(); if (a.right - 1 > b.left && b.right - 1 > a.left) return (items[i].id || items[i].className) + ' × ' + (items[j].id || items[j].className); }
  return bar.scrollWidth > bar.clientWidth ? 'overflow' : ''; }"""
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = m.S.tab.terms.find((x) => x.n === n); if (!term) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join('\\n'); })"""
TAB_ROWS = """() => [...document.querySelectorAll('#lec-doctab-list .doc-tab .name')].map((el) => { const tell = el.querySelector('.tell');
  return [[...el.childNodes].filter((n) => n !== tell).map((n) => n.textContent).join('').trim(), tell ? tell.textContent : '']; })"""
VALUE = "() => document.querySelector('.CodeMirror')?.CodeMirror.getValue() ?? null"


def titles():
    """보이는 맨 위 창의 제목들"""
    import win32gui
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(win32gui.GetWindowText(h)) if win32gui.IsWindowVisible(h) else None, None)
    return [x for x in out if 'Lectern' in x]


def guide_window():
    return any(x == '사용설명서 - Lectern' for x in titles())


def raw(rel):
    for _ in range(40):
        try:
            return (proj / rel).read_bytes()
        except OSError:
            time.sleep(0.05)
    return None


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
    page.wait_for_timeout(1500)
    return b, page


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731
        term_text = lambda n: page.evaluate(TEXT, n)  # noqa: E731
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        want = R.REPO.joinpath('lectern/__init__.py').read_text(encoding='utf-8').split("__version__ = '")[1].split("'")[0]
        R.check(f'판 — {version}', version == want, (version, want))
        width = page.evaluate('innerWidth')
        R.check(f'툴바 단추가 겹치거나 넘치지 않는다 (창 폭 {width}px)', page.evaluate(OVERLAP) == '', page.evaluate(OVERLAP))

        print('[이어 쓴 줄의 한 줄 편집]')
        page.locator('#lec-tree .row.dir[data-dir="보고"]').click()
        page.locator('#lec-tree .row.file[data-doc="보고/분석.md"]').click()
        page.wait_for_selector('#lec-view h1', timeout=15000)
        page.wait_for_timeout(400)
        at = page.evaluate(SPOT, LINES[1])
        page.mouse.click(at['x'], at['y'])
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        R.check('가운데 줄을 열어도 문단은 세 줄', page.evaluate(ROWS) == 3, page.evaluate(ROWS))
        page.keyboard.press('End')
        page.keyboard.type(' (확인)')
        page.keyboard.press('Enter')
        R.check('저장 — 그 줄만', R.wait(lambda: raw('보고/분석.md') == ('# 시장 점검\n\n' + '\n'.join([LINES[0], LINES[1] + ' (확인)', LINES[2]]) + '\n').encode('utf-8'), 8), raw('보고/분석.md'))
        page.keyboard.press('Escape')

        print("['자료'의 만들기 — CSV]")
        page.click('#lec-others-head')
        page.click('#lec-others-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.select_option('#lec-newdoc-folder', '자료')   # '자료' 목록에는 자료 파일이 든 폴더만 — 위치에서 고른다
        page.keyboard.type('측정값')
        page.fill('#lec-newdoc-header', '날짜, 값')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.evaluate("() => { const cm = document.querySelector('.CodeMirror').CodeMirror; cm.setCursor(cm.lineCount() - 1, 0); }")
        page.keyboard.type('2026-11-19,42')
        page.keyboard.press('Control+s')
        R.check('자료/측정값.csv — BOM·머리행·CRLF', R.wait(lambda: raw('자료/측정값.csv') == b'\xef\xbb\xbf' + '날짜,값\r\n2026-11-19,42'.encode('utf-8'), 8), raw('자료/측정값.csv'))
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print("['코드'의 만들기]")
        page.click('#lec-code-head')
        page.locator('#lec-code-list .row', has_text='src').first.click()
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        R.check('처음 이름은 새 파일.py', page.input_value('#lec-newdoc-title') == '새 파일.py', page.input_value('#lec-newdoc-title'))
        page.fill('#lec-newdoc-title', '정리')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.keyboard.type('print(1)')
        page.keyboard.press('Control+s')
        R.check('src/정리.py — 편집 모드에서 저장', R.wait(lambda: raw('src/정리.py') == b'print(1)', 8), raw('src/정리.py'))
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print('[같은 이름의 탭]')
        page.click('#lec-docs-head')
        page.locator('#lec-tree .row.file[data-doc="보고/README.md"]').click(modifiers=['Control'])
        page.locator('#lec-tree .row.dir[data-dir="자료"]').click()
        page.locator('#lec-tree .row.file[data-doc="자료/README.md"]').click(modifiers=['Control'])
        tabs = lambda: sorted(r for r in page.evaluate(TAB_ROWS) if r[0] in ('README.md', '개요'))  # noqa: E731
        R.check('README.md · 보고 / README.md · 자료', R.wait(lambda: tabs() == [['README.md', '보고'], ['README.md', '자료']], 8), tabs())

        print('[터미널 — 설정 ▣ 와 화면 다시 붙기]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=20000)
        R.wait(lambda: 'PS ' in term_text(0), 30)
        page.locator('#lec-term .term-pane[data-n="0"] .term-box').click()
        page.keyboard.type('function prompt { "P" + "S> " }; $mark = 7; "pi" + "d=$PID"')
        page.keyboard.press('Enter')
        R.wait(lambda: any(line.startswith('pid=') for line in term_text(0).split('\n')), 15)
        pid = next((line[4:].strip() for line in term_text(0).split('\n') if line.startswith('pid=')), '')
        R.check('1번 셸 — PID', pid.isdigit(), term_text(0)[-200:])
        page.click('#lec-term-new')
        R.wait(lambda: 'PS ' in term_text(1), 30)
        page.locator('#lec-term .term-pane[data-n="1"] .term-box').click()
        R.wait(lambda: page.evaluate(f"() => {STORE}.then((m) => m.S.tab.term?.n === 1)"), 5)
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        page.click('#lec-aiguide-term')
        R.check('설정 창 ▣ — 2번을 썼으면 2번 터미널로', R.wait(lambda: '2번 터미널에 넣었습니다' in toast(), 8), toast())
        page.keyboard.press('Escape')
        page.locator('#lec-term .term-pane[data-n="0"] .term-pane-head').click(button='right')   # 둘이면 쌓은 칸 — 칸 머리줄
        page.locator('#lec-menu').get_by_text('1번 터미널 화면 다시 붙기').click()
        R.check('화면 다시 붙기 — 지난 출력이 다시 보인다', R.wait(lambda: f'pid={pid}' in term_text(0), 10), term_text(0)[-200:])
        page.locator('#lec-term .term-pane[data-n="0"] .term-box').click()
        page.keyboard.type('"pi" + "d=$PID mark=$mark 한글" + "-1"')
        page.keyboard.press('Enter')
        R.check('— 같은 셸 (PID·변수), 한글 입력', R.wait(lambda: f'pid={pid} mark=7 한글-1' in term_text(0), 10), term_text(0)[-200:])
        page.screenshot(path=str(R.HERE / 'real096.png'))

        print('[F1 — 사용설명서는 따로 창이 기본 (D181)]')
        page.locator('#lec-content').focus()
        page.keyboard.press('F1')
        win = R.new_window(b, None, 30, key='help=1')
        R.check('F1 — 곧바로 사용설명서 창 (실제 독립창)', win is not None)
        if win:
            R.check('— 그 창이 설명서를 연다', R.wait(lambda: win.evaluate("!!document.querySelector('#lec-help') && !document.querySelector('#lec-help').hidden && document.querySelectorAll('#lec-help-toc a').length > 10"), 20))
            R.check('— 메인 창은 덮지 않는다', not page.evaluate("!document.querySelector('#lec-help').hidden"))
            R.check('— 창 제목 사용설명서 - Lectern', R.wait(lambda: guide_window(), 10), titles())
            page.locator('#lec-content').focus()
            page.keyboard.press('F1')
            time.sleep(3)
            R.check('메인 창에서 F1 을 또 — 새 창 없이 떠 있는 창 하나', sum(x == '사용설명서 - Lectern' for x in titles()) == 1, titles())

        print('[Shift+F1 — 예제 가이드 창]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Shift+F1')
        guide = R.new_window(b, None, 40, key='guide=1')
        R.check('Shift+F1 — 예제 가이드 창', guide is not None)
        if guide:
            R.check('— 예제의 README 를 연다', R.wait(lambda: guide.evaluate("document.querySelector('#lec-view')?.dataset.docPath || ''") == 'README.md', 30))
            R.check('— 메인 창은 보던 프로젝트 그대로', page.evaluate(f"() => {STORE}.then((m) => m.S.tab?.name)") == '연구')
            guide.locator('#lec-view p').first.click()
            guide.keyboard.press('Control+e')
            R.check('— 보기만: Ctrl+E 는 편집을 열지 않고 알린다', R.wait(lambda: '보기만' in (guide.text_content('#lec-toast') or ''), 6) and guide.locator('.CodeMirror').count() == 0,
                    guide.text_content('#lec-toast'))
            page.evaluate(f"() => {STORE}.then((m) => import('/static/js/tabs.js').then((x) => x.selectTab(m.S.tabs.find((tb) => tb.name !== '연구'))))")
            time.sleep(2)
            page.evaluate(f"() => {STORE}.then((m) => import('/static/js/tabs.js').then((x) => x.selectTab(m.S.tabs.find((tb) => tb.name === '연구'))))")
            time.sleep(2)
            R.check('메인 창에서 프로젝트를 바꿔도 두 창은 남는다', guide_window() and any(x.endswith('samples - Lectern') for x in titles()), titles())
        if win:
            win.locator('#lec-help-scroll').focus()
            try:
                win.keyboard.press('F1')
            except Exception:   # 키를 떼기 전에 창이 닫힌다
                pass
            R.check('설명서 창의 F1 — 창이 닫힌다', R.wait(lambda: not guide_window(), 10), titles())
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
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
