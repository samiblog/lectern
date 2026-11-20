"""실제 창(WebView2) 시험의 도우미 — 판마다 빌드본·설치본으로 돌리는 tools/real/*.py 가 함께 쓴다 (2026-11-20, 임시 폴더에 있던 것을 저장소로).

브라우저 점검(tools/edges)이 못 보는 것 — WebView2 창, 독립창·슬라이드 창·사용설명서 창, 창 제목, 실제 파일 감시 — 을 본다.
앱을 창으로 띄우고(WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS 의 원격 디버깅 포트) playwright 의 connect_over_cdp 로 붙는다.
설정 폴더(LECTERN_CONFIG_DIR)를 시험마다 새로 두므로 설치된 Lectern 창과 섞이지 않는다.

    python tools/real/<시험>.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)

시험 스크립트는 `import realwin as R` 로 쓴다: R.launch(proj, config) → (proc, cdp), R.app_page(browser), R.wait(fn, sec),
R.check(이름, 조건, 자세히), R.new_window(browser, None, sec, key='solo=') — 새로 뜬 창은 붙어 있던 연결에 보이지 않아 다시 붙어 찾는다
(R.CONN 에 pw·cdp 를 먼저 넣는다). 끝에 R.count·R.fails 로 결과를 알린다.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = (REPO / 'lectern' / '__init__.py').read_text(encoding='utf-8').split("__version__ = '")[1].split("'")[0]   # 저장소의 지금 판
HERE = REPO / 'ui-shots' / 'real'   # 시험이 남기는 화면 — ui-shots 는 커밋하지 않는다
HERE.mkdir(parents=True, exist_ok=True)

args = sys.argv[1:]
EXE = None
if '--exe' in args:
    i = args.index('--exe')
    EXE = str(Path(args[i + 1]).resolve())   # 상대 경로·/ 로 적어도 — 앱은 저장소 폴더에서 띄운다
    del args[i:i + 2]

fails: list[str] = []
count = 0
CONN: dict = {}   # pw(sync_playwright 의 것)·cdp(포트) — new_window 가 다시 붙을 때


def check(name, cond, detail=''):
    """한 점검의 결과를 찍는다 — 실패면 fails 에 이름을 남긴다"""
    global count
    count += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else f' — {detail}'}", flush=True)
    if not cond:
        fails.append(name)


def wait(fn, sec=20, step=0.2):
    """fn() 이 참이 될 때까지 (sec 초까지) — 마지막 값을 돌려준다"""
    end = time.monotonic() + sec
    got = fn()
    while not got and time.monotonic() < end:
        time.sleep(step)
        got = fn()
    return got


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def launch(proj, config):
    """앱을 창으로 띄운다 (EXE 가 있으면 그것을, 없으면 소스의 app.py) — (proc, 원격 디버깅 포트)"""
    cdp = free_port()
    env = os.environ | {'LECTERN_CONFIG_DIR': str(config), 'PYTHONIOENCODING': 'utf-8',
                        'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS': f'--remote-debugging-port={cdp}'}
    cmd = [EXE, str(proj)] if EXE else [sys.executable, str(REPO / 'app.py'), str(proj)]
    log = open(Path(config) / 'app.log', 'w', encoding='utf-8', errors='replace')   # noqa: SIM115 — 앱이 끝날 때까지 쓴다
    proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    return proc, cdp


def href(pg):
    """페이지의 주소 — 일찍 붙으면 playwright 의 url 이 about:blank 에 머무니 페이지에 묻는다"""
    try:
        return pg.evaluate('location.href')
    except Exception:   # noqa: BLE001
        return ''


def app_page(browser):
    """메인 창의 페이지 (독립창·사용설명서 창이 아닌 것)"""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            url = href(pg)
            if url.startswith('http://127.0.0.1') and 'solo=' not in url and '?w=' not in url:
                return pg
    return None


def new_window(browser, before=None, sec=30, key='solo='):
    """새로 뜬 독립창·슬라이드 창·사용설명서 창 (주소에 key) — 붙어 있던 CDP 연결에는 새 창이 나타나지 않아 다시 붙어 찾는다. before 는 쓰지 않는다"""
    end = time.monotonic() + sec
    while time.monotonic() < end:
        try:
            b2 = CONN['pw'].chromium.connect_over_cdp(f"http://127.0.0.1:{CONN['cdp']}")
        except Exception:   # noqa: BLE001
            time.sleep(1)
            continue
        for ctx in b2.contexts:
            for pg in ctx.pages:
                if key in href(pg) and id(pg) not in CONN.setdefault('seen', set()):
                    CONN['seen'].add(id(pg))
                    return pg
        time.sleep(1.5)
    return None


READY = """(p) => {
  const v = document.querySelector('#lec-view');
  if (!v || v.dataset.docPath !== p) return false;
  if (v.classList.contains('lec-deck')) return !!v.querySelector('.lec-slide');
  return !!v.querySelector('h1') && ![...v.querySelectorAll('pre.mermaid, pre.lec-chart')].some((x) => !x.querySelector('svg, canvas') && !x.classList.contains('diagram-error'));
}"""


def open_doc(page, path):
    """문서를 열고 다 그릴 때까지 (다이어그램·차트까지)"""
    page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
    ok = wait(lambda: page.evaluate(f'({READY})({json.dumps(path)})'), 40)
    page.wait_for_timeout(600)
    return ok
