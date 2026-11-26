"""0.93.0 — 빌드본·설치본 실제 창(WebView2)에서: 옛 설정(files_view: folder)이 '폴더' 묶음으로 옮겨짐, '폴더' 묶음에서 문서 열기,
Ctrl+Shift+E 한 바퀴, 문서 트리의 키, 밖에서 고친 곳을 F7 로 보며 F2 로 고치기(실제 파일 감시), 실제 키(SendInput)의 F7 — 캐럿 브라우징이 끼지 않음
(맨 앞 창이 점검 창일 때만), Alt+O·Ctrl+Alt+[, 명령 찾기로 'PDF·인쇄' 창, 독립창의 명령 찾기에는 메인 창의 것이 없음, 다시 실행해도 펼친 묶음.
시험용 설정 폴더·개인 폴더 — 실제 설정과 ~/.claude 는 건드리지 않는다.
  python real093.py --exe <Lectern.exe>"""
import ctypes
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from ctypes import wintypes
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real093-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'version': 2, 'files_view': 'folder', 'files_open': 'code', 'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '보고서'
(proj / 'research').mkdir(parents=True)
(proj / 'data').mkdir()
DOC = ('# 구리 시장\n\n요약 문단.\n\n## 가격\n\n가격 문단 하나.\n\n가격 문단 둘.\n\n## 수요\n\n수요 문단.\n\n## 재고\n\n재고 문단.\n')
(proj / 'research' / '구리.md').write_text(DOC, encoding='utf-8')
(proj / 'research' / '니켈.md').write_text('# 니켈\n\n니켈 문단.\n', encoding='utf-8')
(proj / 'README.md').write_text('# 읽어 보기\n\n본문.\n', encoding='utf-8')
(proj / 'data' / '가격.csv').write_text('월,가격\n1,9000\n', encoding='utf-8')
(proj / 'tool.py').write_text('x = 1\n', encoding='utf-8')
SRC = lambda: (proj / 'research' / '구리.md').read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731
STORE = "import('/static/js/store.js')"

user32 = ctypes.WinDLL('user32', use_last_error=True)
ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _U)]


def send_key(vk, up=False):
    i = INPUT(type=1, u=_U(ki=KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), 0x0002 if up else 0, 0, 0)))
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


def tops_of(pid):
    tops = []

    def on_top(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            tops.append(hwnd)
        return True

    user32.EnumWindows(ENUM(on_top), 0)
    return tops


def line_of(text):
    return SRC().split('\n').index(text) + 1


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)   # '폴더' 묶음을 펼쳐 시작하면 문서 트리는 접혀 있다
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
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.VERSION, version)
        focus = lambda: page.evaluate("""() => { const a = document.activeElement; const sec = a?.closest('.side-sec');
          if (sec) return sec.id + ':' + (a.dataset.doc ?? a.dataset.dir ?? a.dataset.path ?? a.id ?? '');
          if (a?.closest('#lec-panes') || a?.id === 'lec-content') return 'doc'; return a?.id || a?.tagName || ''; }""")  # noqa: E731
        here = lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.pane?.here?.line || 0)")  # noqa: E731
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731

        print("[옛 설정의 '폴더' 보기 → '폴더' 묶음]")
        R.check("옛 설정 files_view: folder — '폴더' 묶음이 펼쳐진 채로 시작", R.wait(lambda: page.evaluate("document.querySelector('#lec-folder').classList.contains('grow')"), 10))
        R.check("거르기 칸 옆 '폴더' 버튼은 없다", page.locator('#lec-btn-view').count() == 0)
        R.check('폴더 구조 그대로 — 문서와 csv·py 가 한 트리에', R.wait(lambda: page.locator('#lec-folder-list .row[data-path="tool.py"]').count() == 1
                and page.locator('#lec-folder-list .row[data-path="README.md"]').count() == 1, 10))
        if page.get_attribute('#lec-folder-list .row[data-path="research"]', 'aria-expanded') != 'true':
            page.locator('#lec-folder-list .row[data-path="research"] [data-toggle]').click()
        page.locator('#lec-folder-list .row[data-path="research/구리.md"]').click(modifiers=['Alt'])
        R.check('문서는 한 번 눌러 연다', R.wait(lambda: page.evaluate(f"() => {STORE}.then(({{ S }}) => S.view?.path === 'research/구리.md')"), 10))
        page.wait_for_timeout(600)

        print('[Ctrl+Shift+E 한 바퀴·문서 트리의 키]')
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Control+Shift+E')
        R.check('Ctrl+Shift+E — 펼친 묶음(폴더)의 지금 보는 문서', R.wait(lambda: focus() == 'lec-folder:research/구리.md', 4), focus())
        seen = []
        for _ in range(5):
            page.keyboard.press('Control+Shift+E')
            page.wait_for_timeout(500)
            seen.append(focus().split(':')[0])
        R.check('다시 누르면 문서 → 자료 → 코드 → 작업 → 폴더 (D205)', seen == ['lec-docs', 'lec-others', 'lec-code', 'lec-work', 'lec-folder'], seen)
        page.click('#lec-docs-head')
        page.keyboard.press('Control+Shift+E')
        R.wait(lambda: focus().startswith('lec-docs:'), 4)
        page.keyboard.press('Home')
        rows = page.evaluate("() => [...document.querySelectorAll('#lec-tree .row')].map((r) => r.dataset.doc ?? r.dataset.dir)")
        page.keyboard.press('End')
        R.check('트리의 Home·End', R.wait(lambda: focus() == f'lec-docs:{rows[-1]}', 3), (focus(), rows))
        page.keyboard.press('F6')
        R.check('F6 — 문서로', R.wait(lambda: focus() == 'doc', 3), focus())

        print('[밖에서 고친 곳을 F7 로 보며 F2 로 고치기]')
        time.sleep(1.1)
        (proj / 'research' / '구리.md').write_text(DOC.replace('가격 문단 둘.', '가격 문단 둘 — 올랐다.').replace('수요 문단.', '수요 문단 — 늘었다.')
                                                 .replace('재고 문단.', '재고 문단 — 줄었다.'), encoding='utf-8')
        R.check('실제 파일 감시로 다시 그림', R.wait(lambda: page.locator('#lec-view p', has_text='줄었다').count() == 1, 15))
        page.wait_for_timeout(500)
        page.locator('#lec-view h1').first.click()
        page.keyboard.press('F7')
        R.check('F7 — 첫 바뀐 곳', R.wait(lambda: here() == line_of('가격 문단 둘 — 올랐다.'), 4), here())
        page.keyboard.press('F7')
        R.wait(lambda: here() == line_of('수요 문단 — 늘었다.'), 4)
        page.keyboard.press('F2')
        R.wait(lambda: page.locator('#lec-view .lec-line-edit').count() == 1, 5)
        page.keyboard.press('End')
        page.keyboard.type(' (확인)')
        page.keyboard.press('Enter')
        R.wait(lambda: '(확인)' in SRC(), 6)
        page.wait_for_timeout(800)
        page.keyboard.press('F7')
        R.check('F2 로 고친 뒤의 F7 — 남은 셋째로', R.wait(lambda: here() == line_of('재고 문단 — 줄었다.'), 4), here())
        page.keyboard.press('Shift+F7')
        R.check('Shift+F7 — 내가 고친 줄', R.wait(lambda: here() == line_of('수요 문단 — 늘었다. (확인)'), 4), here())

        print('[실제 키(SendInput)의 F7]')
        fg = user32.GetForegroundWindow()
        if fg in tops_of(proc.pid):
            page.evaluate("() => { window.__f7 = 0; window.addEventListener('keydown', (e) => { if (e.key === 'F7') window.__f7 += 1; }, true); }")
            before = here()
            wins = len(tops_of(proc.pid))
            send_key(0x76)
            send_key(0x76, up=True)
            time.sleep(1.2)
            R.check('실제 F7 — 앱이 받아 다음 바뀐 곳으로, 캐럿 브라우징 창이 뜨지 않음', page.evaluate('window.__f7') == 1 and here() != before and len(tops_of(proc.pid)) == wins,
                    (page.evaluate('window.__f7'), before, here(), wins, len(tops_of(proc.pid))))
        else:
            print('  (건너뜀 — 맨 앞 창이 점검 창이 아님: 실제 키를 보내지 않는다)')

        print('[Alt+O·Ctrl+Alt+[ · 명령 찾기]')
        page.locator('#lec-view p').first.click()
        was = page.get_attribute('#lec-btn-toc', 'aria-pressed')
        page.keyboard.press('Alt+o')
        R.check('Alt+O — 목차', R.wait(lambda: page.get_attribute('#lec-btn-toc', 'aria-pressed') != was, 3))
        page.keyboard.press('Alt+o')
        page.keyboard.press('Control+Alt+BracketLeft')
        folded = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view > .lec-fold')].map((h) => h.classList.contains('lec-folded'))")  # noqa: E731
        R.check('Ctrl+Alt+[ — 모두 접기', R.wait(lambda: folded() and all(folded()), 3), folded())
        page.keyboard.press('Control+Alt+BracketRight')
        R.check('Ctrl+Alt+] — 모두 펴기', R.wait(lambda: not any(folded()), 3), folded())
        page.keyboard.press('Control+Shift+P')
        R.check("Ctrl+Shift+P — '>' 가 든 명령 찾기", R.wait(lambda: page.input_value('#lec-palette-input') == '>', 3))
        page.keyboard.type('인쇄')
        page.keyboard.press('Enter')
        R.check("'인쇄·PDF' — 창 모드의 PDF·인쇄 창이 열린다", R.wait(lambda: page.locator('#lec-print:not([hidden])').count() == 1, 8))
        where = page.evaluate("() => { const a = document.activeElement; return (a?.id || a?.tagName) + ' / ' + (a?.closest('[id]')?.id || ''); }")
        page.keyboard.press('Escape')
        R.check('바로 누른 Esc — PDF·인쇄 창이 닫힌다 (초점: ' + where + ')', R.wait(lambda: page.locator('#lec-print:not([hidden])').count() == 0, 5),
                page.evaluate("() => { const a = document.activeElement; return (a?.id || a?.tagName) + ' / ' + (a?.closest('[id]')?.id || ''); }"))
        if page.locator('#lec-print:not([hidden])').count():
            page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.closePrint())")

        print('[독립창의 명령 찾기]')
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Control+Shift+N')
        solo = R.new_window(b, None, 30)
        R.check('Ctrl+Shift+N — 독립창', solo is not None)
        if solo:
            solo.wait_for_selector('#lec-view h1', timeout=30000)
            solo.wait_for_timeout(800)
            solo.locator('#lec-view p').first.click()
            solo.keyboard.press('Control+Shift+P')
            R.wait(lambda: solo.locator('#lec-palette-list li.cmd').count() > 0, 5)
            names = solo.evaluate("() => [...document.querySelectorAll('#lec-palette-list li.cmd .t')].map((x) => x.textContent)")
            R.check('독립창의 명령 찾기 — 메인 창의 것(설정·메모·터미널·폴더 열기)은 없고 문서의 것은 있다',
                    '설정' not in names and '메모 열기·닫기' not in names and '터미널 열기·닫기' not in names and '폴더 열기 — 새 프로젝트 탭으로' not in names and '모두 접기' in names, names[:8])
            solo.keyboard.press('Escape')
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        time.sleep(2)

        print('[다시 실행]')
        proc, cdp = R.launch(proj, config)
        R.CONN.update(cdp=cdp)
        b, page = connect(p, cdp)
        R.check("펼친 묶음이 남는다 (마지막에 고른 '문서')", R.wait(lambda: page.evaluate("document.querySelector('#lec-docs').classList.contains('grow')"), 10))
        saved = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        R.check("설정 파일 — 판 3 이상 (지금 4 — D206), files_view 없음", (saved.get('version') or 0) >= 3 and 'files_view' not in saved and saved.get('files_open') == 'docs', {k: saved.get(k) for k in ('version', 'files_view', 'files_open')})
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
