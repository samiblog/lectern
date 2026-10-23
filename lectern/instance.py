"""Lectern 창은 하나: 이미 떠 있으면 새로 띄우지 않고 폴더를 그 창에 탭으로 넘긴다 (D34).

탐색기 우클릭 'Lectern으로 열기'나 `run.bat 폴더` 로 또 실행하면, 두 번째 실행은 Windows 이름 있는 파이프로 첫 실행에
폴더를 넘기고 끝난다. 첫 실행은 그 폴더를 탭으로 열고(화면은 /api/changes 의 tabs_seq 로 알아챈다) 창을 앞으로 가져온다.

- 파이프 이름에 사용자 이름과 설정 폴더를 넣는다. 다른 사용자의 창이나, 설정 폴더가 다른 실행(점검용 LECTERN_CONFIG_DIR)과
  섞이지 않게. 파이프는 기본 보안으로 만들어져 다른 사용자는 쓰지 못한다.
- 주고받는 것은 JSON 한 덩이씩이다. pickle 을 쓰는 send()/recv() 는 쓰지 않는다 — 받은 바이트로 코드가 돌 수 없게.
- 디스크에는 아무것도 쓰지 않는다 (보기 전용 원칙). Windows 가 아니면 쓰지 않는다 (개발·테스트용 실행).
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import sys
import threading
from collections.abc import Callable
from multiprocessing.connection import Client, Connection, Listener
from pathlib import Path
from typing import Any

MAX_MESSAGE = 16384
WAIT = 5.0   # 상대가 답하기를 기다리는 시간 (초)


def pipe_name(config_dir: Path) -> str:
    try:
        user = getpass.getuser()
    except (OSError, KeyError):
        user = 'user'
    who = re.sub(r'[^A-Za-z0-9_.-]', '_', user)[:40]
    tag = hashlib.sha1(os.path.normcase(str(config_dir)).encode('utf-8')).hexdigest()[:10]
    return rf'\\.\pipe\Lectern-{who}-{tag}'


def _send(conn: Connection, data: dict[str, Any]) -> None:
    conn.send_bytes(json.dumps(data, ensure_ascii=False).encode('utf-8'))


def _receive(conn: Connection) -> dict[str, Any] | None:
    if not conn.poll(WAIT):
        return None
    data = json.loads(conn.recv_bytes(MAX_MESSAGE).decode('utf-8'))
    return data if isinstance(data, dict) else None


def _allow_foreground(pid: int) -> None:
    """받는 쪽 창이 앞으로 나올 수 있게 한다. Windows 는 사용자가 방금 실행한 프로그램(이쪽)만 다른 창을 앞으로 가져올 수 있다."""
    try:
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(pid)
    except (AttributeError, OSError):
        pass


def forward(name: str, folder: str | None) -> bool:
    """떠 있는 Lectern 창이 있으면 폴더를 넘기고 True (폴더가 None 이면 창만 앞으로). 없으면 False — 이 실행이 창을 띄운다."""
    if sys.platform != 'win32':
        return False
    try:
        conn = Client(name, family='AF_PIPE')
    except OSError:
        return False
    try:
        hello = _receive(conn)
        pid = hello.get('pid') if hello else None
        if isinstance(pid, int) and not isinstance(pid, bool):
            _allow_foreground(pid)
        _send(conn, {'folder': folder})
        _receive(conn)   # 받았다는 답 (오지 않아도 넘긴 것으로 본다 — 창을 하나 더 띄우지 않는다)
    except (OSError, EOFError, ValueError):
        pass
    finally:
        conn.close()
    return True


class Receiver:
    """첫 실행: 다음 실행들이 넘기는 폴더를 받는다. 창이 준비되면 start(handler) — 그 전에 온 것은 기다렸다가 넘긴다."""

    def __init__(self, listener: Listener):
        self._listener = listener
        self._handler: Callable[[str | None], None] | None = None
        self._ready = threading.Event()
        threading.Thread(target=self._loop, name='lectern-instance', daemon=True).start()

    def start(self, handler: Callable[[str | None], None]) -> None:
        """handler(폴더 또는 None) 를 받을 때마다 부른다 (받는 스레드에서)."""
        self._handler = handler
        self._ready.set()

    def _loop(self) -> None:
        while True:
            try:
                conn = self._listener.accept()
            except OSError:
                return   # 닫힘
            # 답하지 않는 상대가 다음 실행을 막지 않게 하나씩 따로
            threading.Thread(target=self._talk, args=(conn,), daemon=True).start()

    def _talk(self, conn: Connection) -> None:
        with conn:
            try:
                _send(conn, {'pid': os.getpid()})
                msg = _receive(conn)
                if msg is None or not self._ready.wait(60) or self._handler is None:
                    return
                folder = msg.get('folder')
                self._handler(folder if isinstance(folder, str) and folder.strip() else None)
                _send(conn, {'ok': True})
            except (OSError, EOFError, ValueError):
                pass


def listen(name: str) -> Receiver | None:
    """이 실행이 첫 창이 된다: 파이프를 열어 둔다. 열지 못하면(Windows 가 아님 등) None — 창은 그대로 띄운다."""
    if sys.platform != 'win32':
        return None
    try:
        return Receiver(Listener(name, family='AF_PIPE'))
    except OSError:
        return None
