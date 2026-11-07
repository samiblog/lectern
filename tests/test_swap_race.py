"""저장이 파일을 바꿔 끼우는 동안의 읽기 — Windows 의 ReplaceFileW 는 원래 이름을 잠깐 비운다"""
import sys
import threading

import pytest

from lectern import editing


def test_present_waits_only_for_missing(tmp_path):
    there = tmp_path / '있음.md'
    there.write_text('글\n', encoding='utf-8')
    assert editing.present(there)
    assert not editing.present(tmp_path / '없음.md')


@pytest.mark.skipif(sys.platform != 'win32', reason='ReplaceFileW 는 Windows 만')
def test_reads_never_miss_during_swaps(tmp_path):
    path = tmp_path / '문서.md'
    path.write_text('처음\n', encoding='utf-8')
    stop = threading.Event()
    misses = []

    def watch():
        while not stop.is_set():
            if not editing.present(path):
                misses.append(1)

    worker = threading.Thread(target=watch)
    worker.start()
    try:
        for i in range(150):
            tmp = tmp_path / f'.lectern-{i}.tmp'
            tmp.write_text(f'{i}\n', encoding='utf-8')
            editing._swap(tmp, path)
    finally:
        stop.set()
        worker.join()
    assert not misses
