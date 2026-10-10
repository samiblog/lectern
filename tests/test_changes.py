from __future__ import annotations

import time

from lectern.changes import ChangeLog, Watcher
from lectern.scanner import DEFAULT_EXCLUDE_DIRS


def test_changelog_since():
    log = ChangeLog()
    assert log.since(0) == {'seq': 0, 'paths': [], 'structure': False, 'reset': False}
    log.push('a.md')
    log.push('b.md', structure=True)
    log.push('a.md')
    r = log.since(0)
    assert r['seq'] == 3 and r['paths'] == ['a.md', 'b.md'] and r['structure'] is True
    r = log.since(2)
    assert r['paths'] == ['a.md'] and r['structure'] is False
    assert log.since(3)['paths'] == []


def test_changelog_reset_when_history_dropped():
    log = ChangeLog(maxlen=2)
    for name in ('a.md', 'b.md', 'c.md'):
        log.push(name)
    r = log.since(0)
    assert r['reset'] is True and r['structure'] is True
    assert log.since(99)['reset'] is True


def test_watcher_handle_filters(tmp_path):
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS)
    w.handle('modified', str(tmp_path / 'a.md'), '', False)
    w.handle('created', str(tmp_path / 'docs' / 'b.md'), '', False)
    w.handle('modified', str(tmp_path / 'c.txt'), '', False)                 # md 아님
    w.handle('modified', str(tmp_path / '.claude' / 'x.md'), '', False)     # 숨김
    w.handle('modified', str(tmp_path / 'node_modules' / 'r.md'), '', False)  # 제외
    w.handle('modified', '/elsewhere/z.md', '', False)                       # 프로젝트 밖
    w.handle('moved', str(tmp_path / 'tmp.txt'), str(tmp_path / 'final.md'), False)
    w.handle('created', str(tmp_path / 'newdir'), '', True)
    r = log.since(0)
    assert r['paths'] == ['a.md', 'docs/b.md', 'final.md']
    assert r['structure'] is True
    assert r['seq'] == 4


def test_polling_backend_detects_changes(tmp_path):
    (tmp_path / 'a.md').write_text('# a', encoding='utf-8')
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS, poll_interval=0.1)
    w.start(force_polling=True)
    try:
        assert w.backend == 'polling'
        time.sleep(0.25)
        (tmp_path / 'b.md').write_text('# b', encoding='utf-8')
        (tmp_path / 'a.md').write_text('# a 수정됨', encoding='utf-8')
        deadline = time.time() + 3
        while time.time() < deadline and len(log.since(0)['paths']) < 2:
            time.sleep(0.05)
        r = log.since(0)
        assert r['paths'] == ['a.md', 'b.md'] and r['structure'] is True
    finally:
        w.stop()


def test_watchdog_backend_detects_changes(tmp_path):
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS)
    w.start()
    try:
        if w.backend != 'watchdog':
            return  # watchdog 미설치 환경
        time.sleep(0.2)
        (tmp_path / 'new.md').write_text('# new', encoding='utf-8')
        deadline = time.time() + 3
        while time.time() < deadline and 'new.md' not in log.since(0)['paths']:
            time.sleep(0.05)
        assert 'new.md' in log.since(0)['paths']
    finally:
        w.stop()
