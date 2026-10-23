from __future__ import annotations

import os
from pathlib import Path

import pytest

from lectern import osutil


@pytest.fixture
def calls(monkeypatch):
    log = []
    monkeypatch.setattr(osutil, 'open_default', lambda p: log.append(('default', p.name)))
    monkeypatch.setattr(osutil, 'reveal', lambda p: log.append(('reveal', p.name)))
    monkeypatch.setattr(osutil, '_launch', lambda args: log.append(('launch', args)))
    return log


def test_safe_types_use_default_app(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: None)
    f = tmp_path / 'chart.png'
    f.write_bytes(b'')
    assert osutil.open_path(f) == 'default' and calls == [('default', 'chart.png')]


def test_code_files_never_go_to_default_app(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: None)
    for name in ('run.py', 'job.bat', 'x.ps1', 'a.js', 'notes.md'):
        f = tmp_path / name
        f.write_text('', encoding='utf-8')
        assert osutil.open_path(f) == 'reveal'
    assert all(kind == 'reveal' for kind, _ in calls)


def test_editor_gets_line(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: '/usr/bin/code')
    f = tmp_path / 'app.py'
    f.write_text('', encoding='utf-8')
    assert osutil.open_path(f, line=42) == 'editor'
    assert calls == [('launch', ['/usr/bin/code', '-g', f'{f}:42'])]


def test_unsafe_characters_fall_back_to_reveal(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: '/usr/bin/code')
    f = tmp_path / 'a&calc.py'
    f.write_text('', encoding='utf-8')
    assert osutil.open_path(f) == 'reveal'


def test_folder_opens(tmp_path, calls):
    assert osutil.open_path(tmp_path) == 'folder'


def test_editor_is_not_taken_from_current_folder(tmp_path, monkeypatch):
    # run.bat . 처럼 열린 프로젝트가 현재 폴더일 때, 그 안의 code.cmd 가 편집기로 잡혀 실행되면 안 된다 (Windows 는 현재 폴더를 먼저 찾는다)
    (tmp_path / 'code.cmd').write_text('@echo planted\r\n', encoding='utf-8')
    (tmp_path / 'code').write_text('#!/bin/sh\necho planted\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('NoDefaultCurrentDirectoryInExePath', raising=False)
    found = osutil.find_editor(None)
    assert found is None or (os.path.isabs(found) and Path(found).parent != tmp_path)
    assert osutil.find_editor('code.cmd') != 'code.cmd'   # 상대경로 설정도 쓰지 않는다
    configured = tmp_path / 'my-editor.exe'
    configured.write_bytes(b'')
    assert osutil.find_editor(str(configured)) == str(configured)


def test_how_to_open():
    assert [osutil.how_to_open(n) for n in ('표.CSV', 'a.pdf', 'app.py', 'setup.exe', 'a.zip', 'macro.xlsm', 'Makefile')] == \
        ['default', 'default', 'editor', 'reveal', 'reveal', 'reveal', 'editor']


def test_unreadable_types_are_only_revealed(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: '/usr/bin/code')
    for name in ('setup.exe', 'a.zip', 'macro.xlsm'):
        f = tmp_path / name
        f.write_bytes(b'')
        # 실행 파일·압축·매크로 문서는 기본 앱으로도 편집기로도 열지 않는다 ('편집기로 열기'를 보내도)
        assert osutil.open_path(f) == 'reveal' and osutil.open_path(f, prefer_editor=True) == 'reveal'
    assert all(kind == 'reveal' for kind, _ in calls)


def test_prefer_editor_for_default_app_types(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(osutil, 'find_editor', lambda _: '/usr/bin/code')
    f = tmp_path / 'data.csv'
    f.write_text('a,b', encoding='utf-8')
    assert osutil.open_path(f) == 'default' and osutil.open_path(f, prefer_editor=True) == 'editor'
    assert calls == [('default', 'data.csv'), ('launch', ['/usr/bin/code', '-g', f'{f}:1'])]
