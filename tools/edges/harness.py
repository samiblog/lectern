"""가장자리 점검의 공통 부분: 결과 세기, 브라우저 모드 서버 띄우고 끝내기, 기다리기, 실패했을 때 남기는 것.

묶음(tools/edges/*.py)은 이 파일을 맨 먼저 불러온다. 불러오면 playwright 의 페이지를 지켜본다 —
- 실패한 점검과 묶음을 멈춘 예외마다 그때의 화면을 ui-shots/edges/ 에 남긴다 (묶음마다 처음 몇 개만).
- 화면의 스크립트 오류와 콘솔 오류를 모아 두었다가 실패하면 끝에 보인다. 점검 서버가 남긴 오류도 그렇다.
- LECTERN_TEST_SLOW(기본 1)를 고정 시간 대기와 기다리는 한도에 곱한다 — 느린 PC·CI 러너에서 2 로 준다.

새 점검은 고정 시간(wait_for_timeout) 뒤에 한 번 읽지 말고 until 로 조건을 기다린다. PC 가 바쁘면 그 시간이 모자란다
(2026-11-11 되풀이 시험: 전체를 돌린 4번 중 2번, 다른 일을 함께 돌릴 때만 실패했다).
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = Path(sys.argv[0]).stem
SHOTS = ROOT / 'ui-shots' / 'edges'
SLOW = max(1.0, float(os.environ.get('LECTERN_TEST_SLOW') or 1))
MAX_SHOTS = 4
fails: list[str] = []
_count = 0
_pages: list = []          # 묶음이 연 페이지 (가장 나중 것이 지금 보는 화면)
_page_errors: list[str] = []
_shots = 0
_server_log: Path | None = None


def _snap(label: str) -> None:
    """지금 화면을 남긴다 — 실패의 까닭을 다시 돌리지 않고 보려고"""
    global _shots
    if _shots >= MAX_SHOTS:
        return
    for page in reversed(_pages):
        try:
            if page.is_closed():
                continue
            SHOTS.mkdir(parents=True, exist_ok=True)
            _shots += 1
            path = SHOTS / f'{SUITE}-{_shots}.png'
            page.screenshot(path=str(path), timeout=5000)
            print(f'       화면: {path}  ({label[:60]})', flush=True)
        except Exception as e:   # 화면을 못 남겨도 점검은 이어 간다
            print(f'       화면을 남기지 못함: {str(e)[:80]}', flush=True)
        return


def check(name, cond, detail=''):
    global _count
    _count += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else f' — {detail}'}", flush=True)
    if not cond:
        fails.append(name)
        _snap(name)


def until(page, fn, ms=6000, step=50):
    """fn() 이 참이 될 때까지 기다려 그 값을 돌려준다 (끝내 거짓이면 마지막 값). 고정 시간 대기 대신 쓴다.
    fn 이 글자면 페이지 안에서 돌리는 식이다"""
    get = (lambda: page.evaluate(fn)) if isinstance(fn, str) else fn
    end = time.monotonic() + ms * SLOW / 1000
    got = get()
    while not got and time.monotonic() < end:
        page.wait_for_timeout(step / SLOW)   # wait_for_timeout 에 SLOW 가 곱해지므로 여기서는 나눈다
        got = get()
    return got


def expect(page, name, fn, detail=None, ms=6000):
    """조건을 기다렸다가 판정하는 check — fn 은 until 과 같다. detail 은 실패했을 때 보일 값(함수면 그때 부른다)"""
    got = until(page, fn, ms)
    check(name, bool(got), '' if got else detail() if callable(detail) else detail if detail is not None else got)
    return got


def _watch_pages() -> None:
    """playwright 의 페이지를 지켜본다: 연 페이지를 적어 두고, 대기 시간에 SLOW 를 곱하고, 예외로 끝나면 화면을 남긴다"""
    try:
        from playwright.sync_api import Browser, BrowserContext, Page
        from playwright.sync_api._context_manager import PlaywrightContextManager
    except ImportError:
        return

    def note(page):
        _pages.append(page)
        page.on('pageerror', lambda e: _page_errors.append(f'스크립트 오류: {str(e)[:300]}'))
        page.on('console', lambda m: _page_errors.append(f'콘솔: {m.text[:300]}') if m.type == 'error' else None)
        if SLOW > 1:
            page.set_default_timeout(30000 * SLOW)
        return page

    for cls in (Browser, BrowserContext):
        def new_page(self, *args, _orig=cls.new_page, **kwargs):
            return note(_orig(self, *args, **kwargs))
        cls.new_page = new_page

    if SLOW > 1:
        sleep = Page.wait_for_timeout
        Page.wait_for_timeout = lambda self, timeout, _orig=sleep: _orig(self, timeout * SLOW)
        for name in ('wait_for_function', 'wait_for_selector'):
            def waiter(self, *args, _orig=getattr(Page, name), **kwargs):
                if kwargs.get('timeout'):
                    kwargs['timeout'] = kwargs['timeout'] * SLOW
                return _orig(self, *args, **kwargs)
            setattr(Page, name, waiter)

    leave = PlaywrightContextManager.__exit__

    def exit_(self, exc_type, exc, tb, _orig=leave):
        if exc_type is not None:   # 묶음이 예외로 멈춤 — 브라우저가 닫히기 전에
            _snap(f'{exc_type.__name__}: {exc}')
        return _orig(self, exc_type, exc, tb)
    PlaywrightContextManager.__exit__ = exit_


_watch_pages()


def serve(proj, config):
    """proj 를 여는 서버를 띄운다. 설정은 config 폴더에 (설치된 Lectern 과 섞이지 않게). (서버, 주소, 포트).
    서버가 뜨지 않으면 그 자리에서 멈춘다 — 뜨지 않은 서버로 점검을 이어 가면 까닭 모를 시간 초과만 남는다"""
    global _server_log
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    Path(config).mkdir(parents=True, exist_ok=True)
    _server_log = Path(config) / 'server.log'
    log = _server_log.open('w', encoding='utf-8', errors='replace')
    server = subprocess.Popen([sys.executable, str(ROOT / 'tools' / 'quiet_app.py'), '--browser', '--port', str(port), str(proj)], cwd=ROOT,
                              env=os.environ | {'LECTERN_CONFIG_DIR': str(config), 'PYTHONIOENCODING': 'utf-8'}, stdout=log, stderr=subprocess.STDOUT)
    log.close()
    url = f'http://127.0.0.1:{port}/'
    end = time.monotonic() + 30 * SLOW
    while time.monotonic() < end:
        try:
            urllib.request.urlopen(url + 'api/state', timeout=1)
            return server, url, port
        except Exception:
            if server.poll() is not None:
                break
            time.sleep(0.3)
    server.kill()
    print(f'점검 서버가 뜨지 않았습니다 (포트 {port}, 종료 코드 {server.poll()})', flush=True)
    _show_server_log()
    sys.exit(1)


def _show_server_log() -> None:
    """점검 서버가 남긴 글의 끝 — 서버 쪽 예외(500)의 까닭이 여기 있다"""
    try:
        text = _server_log.read_text(encoding='utf-8', errors='replace').strip() if _server_log else ''
    except OSError:
        text = ''
    lines = [s for s in text.splitlines() if 'Lectern (' not in s]
    if lines:
        print('--- 점검 서버가 남긴 글 (끝 30줄)', flush=True)
        print('\n'.join(lines[-30:]), flush=True)


def stop(server, base):
    server.terminate()
    try:
        server.wait(10)
    except subprocess.TimeoutExpired:
        server.kill()
    if fails:
        _show_server_log()   # 임시 폴더를 지우기 전에
    for _ in range(6):       # 서버가 놓지 않은 파일이 잠깐 남는다 — 못 지우면 임시 폴더에 쌓인다
        time.sleep(0.5)
        shutil.rmtree(base, ignore_errors=True)
        if not Path(base).exists():
            break


def report():
    print(f'\n{_count}개 중 실패 {len(fails)}개', fails)
    if fails and _page_errors:
        print('--- 화면의 오류 (끝 10개)')
        print('\n'.join(_page_errors[-10:]))
    sys.exit(1 if fails else 0)
