from __future__ import annotations

import http.client
import threading

import pytest

from app import DEFAULT_WINDOW, MIN_WINDOW, HttpServer, window_size


@pytest.mark.parametrize('saved, expected', [
    ({'width': 1500, 'height': 900}, (1500, 900)),
    ({'width': '1500', 'height': 900}, (1500, 900)),
    ({'width': 160, 'height': 28}, MIN_WINDOW),              # 최소화한 채 저장된 크기
    (None, DEFAULT_WINDOW),                                  # 손으로 고친 설정이 이상한 경우
    ({'width': 'wide'}, DEFAULT_WINDOW),
    ([1280, 860], DEFAULT_WINDOW),
])
def test_window_size(saved, expected):
    assert window_size(saved) == expected


def _hello(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '2')])
    return [b'ok']


def test_http_server_keeps_connections_and_stays_local():
    """응답마다 연결을 닫지 않는다 (D82 — 닫힌 연결이 쌓이면 시작 파일을 받지 못하는 일이 있었다), 127.0.0.1 에만"""
    server = HttpServer(_hello, 0)
    loop = threading.Thread(target=server.serve_forever, daemon=True)
    loop.start()
    try:
        assert server._server.socket.getsockname()[0] == '127.0.0.1'
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        conn.request('GET', '/')
        res = conn.getresponse()
        assert res.read() == b'ok' and res.getheader('Connection') != 'close' and res.getheader('Server') == 'Lectern'
        sock = conn.sock
        conn.request('GET', '/')
        assert conn.getresponse().read() == b'ok' and conn.sock is sock   # 연결을 열어 둔 채로 끝낸다
    finally:
        server.shutdown()
    loop.join(5)
    assert not loop.is_alive()   # 연결이 열려 있어도 끝난다 — 창을 닫을 때 (터미널의 긴 폴링)
    conn.close()
    with pytest.raises(OSError):
        http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2).connect()
