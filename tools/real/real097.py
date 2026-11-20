"""0.97.0 — 실제 창(WebView2)에서 새 사용설명서 트리(D182)와 영어 화면 글(D183).
  python real097.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

VERSION = re.search(r"__version__ = '([^']+)'", (R.REPO / 'lectern' / '__init__.py').read_text(encoding='utf-8'))[1]
base = Path(tempfile.mkdtemp(prefix='lec-real097-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '연구'
proj.mkdir(parents=True)
(proj / '분석.md').write_bytes('# 시장 점검\n\n구리 재고가 줄었다.\n'.encode('utf-8'))
TREE = "() => [...document.querySelectorAll('#lec-help-toc li.doc a')].map((a) => a.textContent)"
CUR = "() => document.querySelector('#lec-help-toc li.doc.current a')?.textContent || ''"
OPEN = "() => !document.querySelector('#lec-help').hidden && document.querySelectorAll('#lec-help-toc li.doc a').length >= 50"
MER = "() => [document.querySelectorAll('#lec-help-view pre.mermaid').length, document.querySelectorAll('#lec-help-view pre.mermaid svg').length, document.querySelectorAll('#lec-help-view .diagram-error').length]"
HANGUL = """() => { const t = document.querySelector('#lec-help-view').innerText.replace(/한국어/g, '');
  const code = [...document.querySelectorAll('#lec-help-view code')].map((c) => c.textContent).join('\\n');
  return (t.match(/[가-힣]+/g) || []).filter((w) => !code.includes(w)); }"""


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


def help_window(b, page):
    page.locator('#lec-content').focus()
    page.keyboard.press('F1')
    win = R.new_window(b, None, 30, key='help=1')
    if win:
        R.wait(lambda: win.evaluate(OPEN), 30)
    return win


def click_doc(win, num):
    win.locator(f'#lec-help-toc li.doc a[data-doc^="{num}-"]').click()
    R.wait(lambda: win.evaluate(CUR).startswith(num + ' '), 10)
    n = win.evaluate(MER)[0]
    if n:
        R.wait(lambda: sum(win.evaluate(MER)[1:]) >= n, 20)


def help_titles():
    import win32gui
    out = []
    win32gui.EnumWindows(lambda h, _: out.append(win32gui.GetWindowText(h)) if win32gui.IsWindowVisible(h) else None, None)
    return [x for x in out if x.endswith(' - Lectern') and ('사용설명서' in x or 'User guide' in x)]


def close_window(win):
    win.locator('#lec-help-scroll').focus()
    try:
        win.keyboard.press('F1')
    except Exception:   # 키를 떼기 전에 창이 닫힌다
        pass


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 {VERSION}', version == VERSION or not version, version)

        print('[사용설명서 — 문서 트리 (D182)]')
        win = help_window(b, page)
        R.check('— 창 제목 사용설명서 - Lectern', R.wait(lambda: help_titles() == ['사용설명서 - Lectern'], 10), help_titles())
        R.check('F1 — 사용설명서 창에 문서 50개의 트리', win is not None and win.evaluate(OPEN))
        if win:
            win.on('pageerror', lambda e: errors.append('설명서 창: ' + str(e)[:300]))
            tree = win.evaluate(TREE)
            R.check('— 차례가 1 시작하기부터 10.4 용어까지', tree[0] == '1 시작하기' and tree[-1] == '10.4 용어' and '5.1 슬라이드 쓰기' in tree, (tree[:2], tree[-2:]))
            R.check('— 처음은 시작하기, 경로가 보인다', win.evaluate(CUR) == '1 시작하기' and win.locator('#lec-help-view .help-path').count() == 1)
            mer = win.evaluate(MER)
            R.check('— 시작하기의 흐름도를 그린다 (WebView2)', mer[0] >= 1 and mer[1] == mer[0] and mer[2] == 0, mer)
            click_doc(win, '4.1')
            mer = win.evaluate(MER)
            R.check('4.1 고치는 길 고르기 — 흐름도와 경로(4 쓰기 아래)', mer[1] == mer[0] >= 1 and '4 쓰기' in win.text_content('#lec-help-view .help-path'), (mer, win.text_content('#lec-help-view .help-path')))
            click_doc(win, '4')
            kids = win.evaluate("() => [...document.querySelectorAll('#lec-help-view table a[data-doc], #lec-help-view table a[href$=\".md\"]')].length")
            R.check('장 문서 4 쓰기 — 하위 문서 표 (여덟)', kids >= 8, kids)
            win.locator('#lec-help-view table a', has_text='4.2 한 줄 편집').first.click()
            R.check('— 표의 문서를 누르면 그 문서로', R.wait(lambda: win.evaluate(CUR) == '4.2 한 줄 편집', 10), win.evaluate(CUR))
            win.locator('#lec-help-view .help-foot a.next').click()
            R.check('— 아래의 다음 문서', R.wait(lambda: win.evaluate(CUR).startswith('4.3 '), 10), win.evaluate(CUR))
            win.fill('#lec-help-find', '닫은 탭')
            win.wait_for_timeout(400)
            found = win.evaluate(TREE)
            R.check('설명서에서 찾기 — 모든 문서의 본문으로 거른다', 0 < len(found) < 50 and any(x.startswith('2.3 ') for x in found), found)
            win.press('#lec-help-find', 'Enter')
            R.check('— Enter 는 첫 문서를 연다', R.wait(lambda: win.evaluate(CUR) == found[0], 10), (win.evaluate(CUR), found[0]))
            win.fill('#lec-help-find', '')
            win.wait_for_timeout(300)
            click_doc(win, '10.1')
            kbd = win.evaluate("document.querySelectorAll('#lec-help-view table kbd').length")
            R.check('10.1 단축키 — 앱이 단축키 표를 넣는다', kbd >= 40, kbd)
            click_doc(win, '2.3')
            win.locator('#lec-help-toc li.sec a', has_text='닫기').click()
            top = lambda: win.evaluate("() => { const h = [...document.querySelectorAll('#lec-help-view h2')].find((x) => x.textContent === '닫기'); return h.getBoundingClientRect().top - document.querySelector('#lec-help-scroll').getBoundingClientRect().top; }")  # noqa: E731
            R.check('트리의 절을 누르면 그 절로', R.wait(lambda: 0 <= top() < 60, 10), top())
            close_window(win)
            R.check('설명서 창의 F1 — 창이 닫힌다 (창 제목으로)', R.wait(lambda: not help_titles(), 10), help_titles())

        print('[영어 화면 (D182·D183)]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.wait_for_timeout(500)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
        page.wait_for_timeout(1200)
        names = page.evaluate('''() => ({ titles: document.querySelector('#lec-btn-titles').textContent.trim(),
          folder: document.querySelector('#lec-newdoc-dir').textContent.trim(),
          ai: document.querySelector('#lec-set-ai').textContent.trim(),
          deck: document.querySelector('#lec-theme option[value="deck"]')?.textContent })''')
        R.check('영어 화면 글 — Titles · Folder · AI tool · Presentation', names == {'titles': 'Titles', 'folder': 'Folder', 'ai': 'AI tool', 'deck': 'Presentation'}, names)
        win = help_window(b, page)
        R.check('F1 — 영어 사용설명서 창에 문서 50개', win is not None and win.evaluate(OPEN))
        if win:
            tree = win.evaluate(TREE)
            R.check('— 영어 차례', tree[0] == '1 Getting started' and tree[-1] == '10.4 Terms' and '6.2 One html file' in tree, (tree[:2], tree[-2:]))
            for num in ('1', '4.1', '10.1'):
                click_doc(win, num)
                left = win.evaluate(HANGUL)
                mer = win.evaluate(MER)
                R.check(f'— {win.evaluate(CUR)}: 한글이 남지 않고 흐름도를 그린다', not left and mer[1] == mer[0] and mer[2] == 0, (left[:5], mer))
            close_window(win)
            R.check('영어 설명서 창의 F1 — 창이 닫힌다', R.wait(lambda: not help_titles(), 10), help_titles())
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
