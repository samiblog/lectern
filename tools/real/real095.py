"""D176 — 실제 창(WebView2)에서 Lectern 슬라이드를 지금 창에서 연다. 새 창은 고를 때만.
  python real095.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
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

base = Path(tempfile.mkdtemp(prefix='lec-slides-here-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '발표'
proj.mkdir()
shutil.copy(R.REPO / 'samples/slides/기초/01-처음-보기.md', proj / '덱.md')
(proj / '보고서.md').write_text('# 보고서\n\n본문.\n', encoding='utf-8')
STORE = "import('/static/js/store.js')"
VIEW = "() => ({ path: document.querySelector('#lec-view')?.dataset.docPath || '', deck: !!document.querySelector('#lec-view .lec-slide, #lec-view.lec-deck, #lec-view .lec-deck'), tabs: document.querySelectorAll('#lec-doctab-list .doc-tab').length })"


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


def solo_pages():
    """지금 떠 있는 독립창·슬라이드 창 (CDP 에 다시 붙어 센다)"""
    b2 = R.CONN['pw'].chromium.connect_over_cdp(f"http://127.0.0.1:{R.CONN['cdp']}")
    return [pg for ctx in b2.contexts for pg in ctx.pages if 'solo=' in R.href(pg)]


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        view = lambda: page.evaluate(VIEW)  # noqa: E731
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        want = R.REPO.joinpath('lectern/__init__.py').read_text(encoding='utf-8').split("__version__ = '")[1].split("'")[0]
        R.check(f'판 — {version}', version == want, (version, want))

        print('[목록에서 누르면 지금 창에]')
        page.locator('#lec-tree .row.file[data-doc="덱.md"]').click()
        R.check('Lectern 슬라이드가 지금 창의 문서 칸에 열린다', R.wait(lambda: view()['path'] == '덱.md' and view()['deck'], 15), view())
        time.sleep(3)
        R.check('— 새 창(슬라이드 창)은 뜨지 않는다', not solo_pages(), [R.href(x) for x in solo_pages()])
        page.screenshot(path=str(R.HERE / 'real095.png'))

        print('[보고서로 갔다가 돌아오기 — 문서와 같은 길]')
        page.locator('#lec-tree .row.file[data-doc="보고서.md"]').click()
        R.check('md 문서를 누르면 그 자리에서 바뀐다', R.wait(lambda: view()['path'] == '보고서.md', 10), view())
        page.locator('#lec-tree .row.file[data-doc="덱.md"]').click()
        R.check('슬라이드를 다시 누르면 그 문서 탭으로 (문서와 같은 규칙 — 새 창 없이)', R.wait(lambda: view()['path'] == '덱.md' and view()['deck'], 10) and not solo_pages(), view())

        print('[검색 결과로 슬라이드의 그 줄에]')
        line = next(i for i, l in enumerate((proj / '덱.md').read_text(encoding='utf-8').split('\n'), 1) if l.startswith('## ') or l.startswith('# '))
        page.evaluate(f"() => {STORE}.then((m) => m.emit('open', {{ type: 'doc', path: '덱.md', deckLine: {line + 8} }}))")
        R.check('deckLine 으로 열어도 지금 창 (검색·담기·메모의 길)', R.wait(lambda: view()['path'] == '덱.md', 10) and not solo_pages(), view())

        print('[새 창은 고를 때만]')
        page.locator('#lec-tree .row.file[data-doc="덱.md"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
        page.locator('#lec-menu button', has_text='새 창에서 열기').click()
        win = R.new_window(b, None, 30)
        R.check("왼쪽 목록 우클릭 '새 창에서 열기' — 슬라이드 창이 뜬다", win is not None)
        if win:
            R.check('— 그 창은 슬라이드 창 (발표 스타일을 따로)', R.wait(lambda: win.evaluate("document.documentElement.classList.contains('lec-slide-window')"), 15))
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
