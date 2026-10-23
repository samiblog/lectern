from __future__ import annotations

import json
import pickle
import sys
import threading
import time
import uuid
from multiprocessing.connection import Client
from pathlib import Path

import pytest

from lectern import instance

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows 이름 있는 파이프')


def fresh_name() -> str:
    return rf'\\.\pipe\Lectern-test-{uuid.uuid4().hex}'


def test_pipe_name_follows_user_and_config_dir(tmp_path):
    a, b = instance.pipe_name(tmp_path / 'a'), instance.pipe_name(tmp_path / 'b')
    assert a.startswith('\\\\.\\pipe\\Lectern-') and a != b and a == instance.pipe_name(Path(str(tmp_path / 'a').upper()))


def test_first_run_has_no_window_to_forward_to():
    assert instance.forward(fresh_name(), r'C:\proj') is False


def test_second_run_forwards_folder():
    name = fresh_name()
    receiver = instance.listen(name)
    got: list[str | None] = []
    receiver.start(got.append)
    assert instance.forward(name, r'C:\proj') is True
    assert instance.forward(name, None) is True        # 폴더 없이 실행: 창만 앞으로
    assert got == [r'C:\proj', None]


def test_waits_until_window_is_ready():
    name = fresh_name()
    receiver = instance.listen(name)
    got: list[str | None] = []
    sender = threading.Thread(target=instance.forward, args=(name, r'C:\early'))
    sender.start()
    time.sleep(0.3)                                    # 창을 띄우는 동안 온 폴더는 기다렸다가 넘긴다
    receiver.start(got.append)
    sender.join(10)
    assert got == [r'C:\early']


def test_bad_messages_are_ignored():
    name = fresh_name()
    receiver = instance.listen(name)
    got: list[str | None] = []
    receiver.start(got.append)
    payloads = [b'not json', json.dumps(['x']).encode(), pickle.dumps({'folder': r'C:\evil'}),   # pickle 은 풀지 않는다
                b'x' * (instance.MAX_MESSAGE + 1), json.dumps({'folder': 5}).encode()]
    for payload in payloads:
        conn = Client(name, family='AF_PIPE')
        assert isinstance(json.loads(conn.recv_bytes())['pid'], int)
        try:
            conn.send_bytes(payload)
            conn.poll(2)                               # 받는 쪽이 처리할 때까지
        except BrokenPipeError:
            pass                                       # 너무 긴 것은 받는 쪽이 다 읽지 않고 끊는다
        conn.close()
    assert instance.forward(name, r'C:\ok')
    assert got == [None, r'C:\ok']                     # 폴더가 글자가 아니면 창만 앞으로
