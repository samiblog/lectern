from __future__ import annotations

import time

from lectern.changes import ChangeLog, Watcher
from lectern.scanner import DEFAULT_EXCLUDE_DIRS


def test_changelog_since():
    log = ChangeLog()
    assert log.since(0) == {'seq': 0, 'paths': [], 'structure': False, 'others': False, 'reset': False}
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
    w.handle('moved', str(tmp_path / 'tmp.txt'), str(tmp_path / 'final.md'), False)   # tmp.txt 가 문서 외 파일에서 빠짐
    w.handle('created', str(tmp_path / 'newdir'), '', True)
    r = log.since(0)
    assert r['paths'] == ['a.md', 'docs/b.md', 'final.md']
    assert r['structure'] is True and r['others'] is True
    assert r['seq'] == 5


def test_other_files_are_logged_apart_from_documents(tmp_path):
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS)
    w.handle('modified', str(tmp_path / 'data.csv'), '', False)              # 문서 외 파일의 내용 수정은 보지 않는다
    assert log.seq == 0
    w.handle('created', str(tmp_path / 'data.csv'), '', False)
    r = log.since(0)
    # 문서 외 파일만 바뀌면 문서 트리는 그대로 (structure 아님) — 화면은 문서 외 파일 목록만 다시 읽는다
    assert r == {'seq': 1, 'paths': [], 'structure': False, 'others': True, 'reset': False} and log.others_seq == 1
    w.handle('modified', str(tmp_path / 'a.md'), '', False)
    assert log.since(1)['others'] is False and log.others_seq == 1            # 문서 내용 수정은 문서 외 목록과 상관없다
    w.handle('created', str(tmp_path / 'newdir'), '', True)
    assert log.others_seq == 3                                                # 폴더가 생기면 둘 다


def test_excluded_folder_coming_or_going_updates_other_files(tmp_path):
    # 제외 폴더는 '자료' 목록에 접힌 채 나온다 (D49) — 그 폴더가 생기거나 지워지면 알리고, 안의 변경은 보지 않는다
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS)
    w.handle('created', str(tmp_path / 'node_modules' / 'lib' / 'a.js'), '', False)
    w.handle('created', str(tmp_path / 'node_modules' / 'lib'), '', True)
    w.handle('modified', str(tmp_path / 'dist'), '', True)
    w.handle('created', str(tmp_path / '.venv' / 'dist'), '', True)          # 숨김 폴더 안
    w.handle('created', str(tmp_path / 'build' / 'dist'), '', True)          # 제외 폴더 안
    assert log.seq == 0
    w.handle('created', str(tmp_path / 'dist'), '', True)
    w.handle('deleted', str(tmp_path / 'src' / 'Build'), '', False)          # 지운 폴더는 폴더인지 모를 때가 있다
    r = log.since(0)
    assert r['others'] is True and r['structure'] is False and r['paths'] == [] and log.others_seq == 2


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


def test_polling_backend_notices_other_files(tmp_path):
    (tmp_path / 'a.md').write_text('# a', encoding='utf-8')
    log = ChangeLog()
    w = Watcher(tmp_path, log, DEFAULT_EXCLUDE_DIRS, poll_interval=0.1)
    w.start(force_polling=True)
    try:
        time.sleep(0.25)
        (tmp_path / 'data.csv').write_text('x', encoding='utf-8')   # 문서 외 파일이 생김
        deadline = time.time() + 3
        while time.time() < deadline and not log.since(0)['others']:
            time.sleep(0.05)
        r = log.since(0)
        assert r['others'] is True and r['paths'] == [] and r['structure'] is False
        seq = log.seq
        (tmp_path / 'dist').mkdir()                                  # 빈 제외 폴더도 '자료' 목록에 나온다 (D49)
        while time.time() < deadline + 3 and log.seq == seq:
            time.sleep(0.05)
        assert log.since(seq)['others'] is True
    finally:
        w.stop()
