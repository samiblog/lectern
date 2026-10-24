from __future__ import annotations

import os
import sys
import threading
import time

import pytest

from lectern import terminal
from lectern.terminal import Session, Terminals, shell_command, shell_label

windows = pytest.mark.skipif(not terminal.AVAILABLE, reason='Windows 의사 콘솔(ConPTY)이 있어야 한다')


def test_shell_command_uses_full_path_only(tmp_path):
    default, cmd = shell_command(None)
    assert os.path.isabs(default) and default.lower().endswith('powershell.exe') and cmd == f'"{default}" -NoLogo'
    # 이름만·없는 파일·상대경로는 기본 셸 (PATH·현재 폴더에서 찾지 않게 — D29)
    for bad in ('cmd.exe', 'pwsh', str(tmp_path / 'none.exe'), 'tools\\sh.exe'):
        assert shell_command(bad)[0] == default
    exe = sys.executable
    assert shell_command(exe) == (exe, f'"{exe}"')


def test_shell_label():
    assert shell_label(r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe') == 'PowerShell'
    assert shell_label(r'C:\Program Files\PowerShell\7\pwsh.exe') == 'PowerShell 7'
    assert shell_label(r'C:\Windows\System32\cmd.exe') == '명령 프롬프트'
    assert shell_label(r'D:\tools\nu.exe') == 'nu'


def fake_session(text: str, start: int = 0) -> Session:
    """의사 콘솔 없이 출력 버퍼만 있는 셸 (read 의 순번 계산 확인용)"""
    s = Session.__new__(Session)
    s._buf, s._start, s._cond = text, start, threading.Condition()
    s.alive, s.exit_code = True, None
    s.stuck, s._stuck_ver = [], 0
    return s


def test_read_from_position_and_reset(monkeypatch):
    s = fake_session('abcdef', start=100)   # 앞 100글자는 MAX_KEEP 을 넘어 버렸다
    assert s.read(103, timeout=0) == {'data': 'def', 'next': 106, 'reset': False, 'alive': True, 'exit': None, 'stuck': []}
    r = s.read(0, timeout=0)   # 버린 앞부분부터 달라면 남은 맨 앞부터, reset 을 단다 (화면을 새로 불러온 경우)
    assert r['data'] == 'abcdef' and r['next'] == 106 and r['reset']
    t0 = time.monotonic()
    assert s.read(106, timeout=0.2)['data'] == '' and time.monotonic() - t0 >= 0.15   # 새 출력을 기다렸다가 빈손
    monkeypatch.setattr(terminal, 'MAX_READ', 4)
    r = s.read(100, timeout=0)
    assert r['data'] == 'abcd' and r['next'] == 104
    s.alive, s.exit_code = False, 3   # 셸이 끝나도 못 받은 출력이 남아 있으면 alive 는 아직 참
    assert s.read(100, timeout=5) == {'data': 'abcd', 'next': 104, 'reset': False, 'alive': True, 'exit': 3, 'stuck': []}
    assert s.read(104, timeout=5) == {'data': 'ef', 'next': 106, 'reset': False, 'alive': False, 'exit': 3, 'stuck': []}
    assert s.read(106, timeout=5) == {'data': '', 'next': 106, 'reset': False, 'alive': False, 'exit': 3, 'stuck': []}


def test_append_keeps_recent_output(monkeypatch):
    monkeypatch.setattr(terminal, 'MAX_KEEP', 5)
    s = fake_session('')
    s._append('12345')
    s._append('678')
    assert s._buf == '45678' and s._start == 3 and s.end == 8


def read_until(session: Session, want: str, timeout: float = 20) -> str:
    out, pos = '', 0
    deadline = time.monotonic() + timeout
    while want not in out and time.monotonic() < deadline:
        r = session.read(pos, timeout=1)
        out += r['data']
        pos = r['next']
        if not r['alive']:
            break
    return out


def wait_for(cond, timeout: float = 10) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.1)
    return False


@windows
def test_session_runs_in_project_folder_with_korean(tmp_path, monkeypatch):
    cwd = tmp_path / '한글 폴더'
    cwd.mkdir()
    monkeypatch.setenv('LECTERN_LEAK_TEST', 'leaked')   # 앱이 실행 중에 바꾼 환경 값은 셸로 새지 않는다 (_START_ENV)
    s = Session('p1', str(cwd), None, 100, 30)
    try:
        assert read_until(s, '>')
        s.write('Write-Output ("lec" + "term" + "한글"); (Get-Location).Path; "[" + $env:LECTERN_LEAK_TEST + "]"\r')
        out = read_until(s, '[]')
        assert 'lecterm한글' in out and str(cwd) in out and '[]' in out and '[leaked]' not in out
    finally:
        s.close()
    assert wait_for(lambda: not s.alive)


@windows
def test_busy_and_close_ends_child_programs(tmp_path):
    s = Session('p1', str(tmp_path), None, 80, 24)
    try:
        assert read_until(s, '>')
        assert not s.busy()
        s.write('ping -n 60 127.0.0.1\r')
        assert wait_for(s.busy), '셸에서 띄운 프로그램이 돌면 busy'
    finally:
        s.close()   # 작업 개체째 끝낸다 — ping 까지
    assert wait_for(lambda: not s.alive)
    assert not s.busy()


@windows
def test_ctrl_c_stops_child_program(tmp_path):
    import ctypes
    k = ctypes.WinDLL('kernel32')
    k.SetConsoleCtrlHandler(None, True)   # Lectern 을 띄운 쪽이 새 프로세스 그룹으로 띄운 것처럼 — 'Ctrl+C 무시'가 켜진 채
    try:
        s = Session('p1', str(tmp_path), None, 80, 24)
    finally:
        k.SetConsoleCtrlHandler(None, False)
    try:
        assert read_until(s, '>')
        s.write('ping -n 60 127.0.0.1\r')
        assert wait_for(s.busy)
        s.write('\x03')   # 고른 글이 없을 때의 Ctrl+C
        assert wait_for(lambda: not s.busy(), 10), 'Ctrl+C 로 셸에서 띄운 프로그램이 멈춘다'
        assert s.alive   # 셸은 그대로
    finally:
        s.close()


@windows
def test_stuck_child_is_reported(tmp_path, monkeypatch):
    """시작하다 멈춘 프로그램 (D58): 보안 프로그램이 프로세스 생성을 막으면 자식이 로더도 돌지 않은 일시 정지로 남는다.
    같은 모양(일시 정지로 만든 자식)을 셸에서 띄워, stuck 으로 알리고(긴 폴링을 깨움) 다시 시작(작업 개체째)으로 끝나는지"""
    monkeypatch.setattr(terminal, 'STUCK_AFTER', 0.5)
    monkeypatch.setattr(terminal, 'STUCK_CHECK', 0.2)
    cmd = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'cmd.exe')
    script = tmp_path / 'stuck.py'
    script.write_text(f'import subprocess, time\nsubprocess.Popen([{cmd!r}, "/c", "exit"], creationflags=4)\n'
                      'print("started", flush=True)\ntime.sleep(60)\n', encoding='utf-8')
    s = Session('p1', str(tmp_path), None, 80, 24)
    try:
        assert read_until(s, '>')
        assert s.stuck == [] and s.read(s.end, timeout=0.1)['stuck'] == []
        since = s.end
        s.write(f"& '{sys.executable}' '{script}'\r")
        assert read_until(s, 'started')
        got = s.read(s.end, timeout=10)   # 새 출력이 없어도 stuck 이 바뀌면 돌아온다
        assert wait_for(lambda: s.stuck, 10)
        names = [p['name'].lower() for p in s.stuck]
        assert names == ['cmd.exe'], s.stuck
        assert s.read(since, timeout=0.1)['stuck'] == s.stuck and 'stuck' in got
    finally:
        s.close()   # 다시 시작과 같은 길 — 작업 개체째 끝낸다 (멈춘 자식까지)
    assert wait_for(lambda: not s.alive)


@windows
def test_exit_code_and_end(tmp_path):
    s = Session('p1', str(tmp_path), None, 80, 24)
    assert read_until(s, '>')
    s.write('exit 3\r')
    assert wait_for(lambda: not s.alive)
    r = s.read(s.end, timeout=1)
    assert r['alive'] is False and r['exit'] == 3
    s.write('dir\r')   # 끝난 셸에 보내도 오류 없이 버린다
    s.resize(100, 40)


@windows
def test_terminals_one_shell_per_project(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir()
    b.mkdir()
    terms = Terminals()
    try:
        s1 = terms.open('pa', str(a), None, 80, 24)
        assert terms.open('pa', str(a), None, 80, 24) is s1   # 돌고 있으면 그 셸
        s2 = terms.open('pb', str(b), None, 80, 24)
        assert s2 is not s1 and terms.get(s1.id) is s1 and terms.get(None) is None and terms.get(123) is None
        terms.close_project('pa')
        assert terms.get(s1.id) is None and wait_for(lambda: not s1.alive)
        s3 = terms.open('pa', str(a), None, 80, 24)
        assert s3 is not s1 and s3.alive
    finally:
        terms.close_all()
    assert wait_for(lambda: not s2.alive and not s3.alive)
