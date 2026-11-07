"""저장이 파일을 바꿔 끼우는 동안의 읽기 — Windows 의 ReplaceFileW 는 원래 이름을 잠깐 비운다"""
import sys
import threading
import time

import pytest

from lectern import editing
from lectern.docinfo import read_text


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
                misses.append('없음')
            try:
                editing.steady(read_text, path)
                editing._read_whole(path)
            except Exception as exc:   # 다른 오류로 스레드가 조용히 끝나지 않게 모두 적는다
                misses.append(repr(exc))
            time.sleep(0.002)   # 사람이 쓰는 빠르기보다 훨씬 잦게

    worker = threading.Thread(target=watch)
    worker.start()
    try:
        for i in range(150):
            tmp = tmp_path / f'.lectern-{i}.tmp'
            tmp.write_text(f'{i}\n', encoding='utf-8')
            for _ in range(40):   # 저장(editing.save_source)처럼 — 읽는 쪽이 잡고 있으면 바꿔 끼우기가 잠깐 거부된다
                try:
                    editing._swap(tmp, path)
                    break
                except PermissionError:
                    time.sleep(0.01)
    finally:
        stop.set()
        worker.join()
    assert not misses, misses[:3]
