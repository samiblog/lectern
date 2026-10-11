"""Lectern 진입점.

    python app.py [폴더]              pywebview 창으로 실행 (기본)
    python app.py --browser [폴더]    개발용: 서버만 띄우고 일반 브라우저로 확인
    python app.py --debug [폴더]      창 + 개발자 도구

폴더를 주지 않으면 마지막으로 연 폴더를 연다.
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path
from typing import Any

from lectern import __version__
from lectern.config import DEFAULTS, Config
from lectern.server import create_app
from lectern.state import AppState


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='Lectern', description='Lectern — 프로젝트 문서를 한눈에 보는 로컬 뷰어 (현재 Markdown)')
    parser.add_argument('folder', nargs='?', help='열 프로젝트 폴더')
    parser.add_argument('--browser', action='store_true', help='창 없이 서버만 실행 (개발용)')
    parser.add_argument('--port', type=int, default=0, help='서버 포트 (기본: 자동, --browser 기본 8765)')
    parser.add_argument('--debug', action='store_true', help='개발자 도구 사용')
    parser.add_argument('--version', action='version', version=__version__)
    return parser.parse_args(argv)


class _QuietPolling(logging.Filter):
    """1초마다 오는 /api/changes 요청 로그는 숨긴다."""

    def filter(self, record: logging.LogRecord) -> bool:
        return '/api/changes' not in record.getMessage()


def setup_logging(quiet: bool) -> None:
    log = logging.getLogger('werkzeug')
    log.addFilter(_QuietPolling())
    if quiet:
        log.setLevel(logging.ERROR)


def open_initial_folder(state: AppState, folder: str | None) -> None:
    target = folder or state.config.get('last_folder')
    if target and Path(target).is_dir():
        try:
            state.open(target)
        except OSError as exc:
            print(f'폴더를 열 수 없습니다: {exc}', file=sys.stderr)


def make_http_server(state: AppState, port: int):
    """창 모드와 브라우저 모드가 함께 쓰는 서버. 127.0.0.1 에만 바인딩한다."""
    from werkzeug.serving import make_server

    return make_server('127.0.0.1', port, create_app(state), threaded=True)


def run_browser(state: AppState, port: int) -> None:
    server = make_http_server(state, port or 8765)
    # 출력을 파일·NUL로 돌리면 stdout 은 cp949 라 '—' 같은 글자에서 죽는다 (tools/ui_smoke.py 가 그렇게 띄운다)
    print(f'Lectern (브라우저 모드): http://127.0.0.1:{server.server_port}/  (종료: Ctrl+C)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


DEFAULT_WINDOW = (DEFAULTS['window']['width'], DEFAULTS['window']['height'])
MIN_WINDOW = (720, 480)


def window_size(saved: Any) -> tuple[int, int]:
    """설정의 창 크기. 손으로 고쳐 형식이 틀렸으면 기본값, 최소 크기보다 작으면 최소 크기."""
    try:
        width, height = int(saved['width']), int(saved['height'])
    except (TypeError, KeyError, ValueError):
        return DEFAULT_WINDOW
    return max(width, MIN_WINDOW[0]), max(height, MIN_WINDOW[1])


def run_window(state: AppState, port: int, debug: bool) -> None:
    import webview

    from lectern.native import NativeApi

    state.token = getattr(webview, 'token', None)
    server = make_http_server(state, port)
    threading.Thread(target=server.serve_forever, name='lectern-http', daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/'

    width, height = window_size(state.config.get('window'))
    api = NativeApi(state)
    window = webview.create_window(
        'Lectern', url, js_api=api,
        width=width, height=height,
        min_size=MIN_WINDOW,
        text_select=True,   # 본문 선택·복사
        zoomable=True,      # Ctrl+휠 확대
    )
    api._window = window

    # 최소화·최대화한 채로 닫으면 그때 크기를 저장하지 않는다 (다음 실행 때 아주 작거나 화면만 한 일반 창이 되지 않도록)
    shown = {'state': 'normal'}
    window.events.minimized += lambda: shown.update(state='minimized')
    window.events.maximized += lambda: shown.update(state='maximized')
    window.events.restored += lambda: shown.update(state='normal')

    def on_closing() -> None:
        if shown['state'] != 'normal':
            return
        try:
            state.config.set_window(window.width, window.height)
        except Exception:  # 창 크기 저장 실패는 무시
            pass

    window.events.closing += on_closing
    try:
        webview.start(debug=debug)
    finally:
        server.shutdown()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    setup_logging(quiet=not (args.browser or args.debug))
    config = Config()
    if config.load_error:
        print(config.load_error, file=sys.stderr)
    state = AppState(config, mode='browser' if args.browser else 'app')
    open_initial_folder(state, args.folder)
    try:
        if args.browser:
            run_browser(state, args.port)
        else:
            run_window(state, args.port, args.debug)
    finally:
        state.close()


if __name__ == '__main__':
    main()
