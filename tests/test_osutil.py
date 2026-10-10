from __future__ import annotations

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
