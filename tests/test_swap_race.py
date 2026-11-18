"""저장이 파일을 바꿔 끼우는 동안의 읽기 — Windows 의 ReplaceFileW 는 원래 이름을 잠깐 비운다"""
import sys
import threading
import time
import warnings

import pytest

from lectern import editing
from lectern.docinfo import read_text


def test_present_waits_only_for_missing(tmp_path):
    there = tmp_path / '있음.md'
    there.write_text('글\n', encoding='utf-8')
    assert editing.present(there)
    assert not editing.present(tmp_path / '없음.md')


def test_present_file_waits_only_for_missing(tmp_path):
    there = tmp_path / '있음.md'
    there.write_text('글\n', encoding='utf-8')
    assert editing.present_file(there)
    start = time.perf_counter()
    assert not editing.present_file(tmp_path)   # 폴더는 기다리지 않는다
    assert time.perf_counter() - start < 0.05
    assert not editing.present_file(tmp_path / '없음.md')
    gone = tmp_path / '.lectern-gap.tmp'
    there.replace(gone)   # 바꿔 끼우는 순간처럼 원래 이름이 잠깐 빈다
    timer = threading.Timer(0.04, lambda: gone.replace(there))
    timer.start()
    try:
        assert editing.present_file(there)
    finally:
        timer.join()


def test_swap_puts_new_text_when_original_is_gone(tmp_path):
    """바꿔 끼우다 멈춰 원래 파일이 없어진 경우 — 새 글을 바로 그 자리에 놓는다"""
    path = tmp_path / '문서.md'
    tmp = tmp_path / '.lectern-1.tmp'
    tmp.write_text('새 글\n', encoding='utf-8')
    editing._swap(tmp, path)
    assert path.read_text(encoding='utf-8') == '새 글\n' and not tmp.exists()


def _race(folder):
    """바꿔 끼우기 150번 동안 다른 스레드가 쉬지 않고 읽는다 — 읽기가 빈 순간들 [(몇 번째 바꿔 끼우기, 무엇)]"""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / '문서.md'
    path.write_text('처음\n', encoding='utf-8')
    stop = threading.Event()
    misses = []
    at = [0]   # 지금 몇 번째 바꿔 끼우기인지 — 실패했을 때 어느 순간인지 보이게

    def watch():
        while not stop.is_set():
            if not editing.present(path):
                misses.append((at[0], '없음'))
            try:
                editing.steady(read_text, path)
                editing._read_whole(path)
            except Exception as exc:   # 다른 오류로 스레드가 조용히 끝나지 않게 모두 적는다
                misses.append((at[0], repr(exc)))
            time.sleep(0.002)   # 사람이 쓰는 빠르기보다 훨씬 잦게

    worker = threading.Thread(target=watch)
    worker.start()
    try:
        for i in range(150):
            at[0] = i
            tmp = folder / f'.lectern-{i}.tmp'
            tmp.write_text(f'{i}\n', encoding='utf-8')
            for _ in range(40):   # 저장(editing.save_source)처럼 — 읽는 쪽이 잡고 있으면 바꿔 끼우기가 잠깐 거부된다
                try:
                    editing._swap(tmp, path)
                    break
                except PermissionError:
                    time.sleep(0.01)
            time.sleep(0.005)   # 저장은 잇달아도 사람의 키 사이만큼은 떨어져 있다
    finally:
        stop.set()
        worker.join()
    return misses


@pytest.mark.skipif(sys.platform != 'win32', reason='ReplaceFileW 는 Windows 만')
def test_reads_never_miss_during_swaps(tmp_path):
    """전체 pytest 12번 가운데 2번, 다른 무거운 작업과 함께 돌 때만 실패했다 (2026-11-19 — 이 시험만으로는 35번 모두 통과).
    한 번 실패하면 다시 돌려, 다시도 실패해야 실패로 친다 — 처음 실패는 경고로 남겨 원인(몇 번째 바꿔 끼우기에서 무엇이 비었나)을 본다"""
    first = _race(tmp_path / '1')
    if not first:
        return
    again = _race(tmp_path / '2')
    assert not again, f'두 번 모두 읽기가 비었다 — 처음 {first[:3]}, 다시 {again[:3]}'
    warnings.warn(f'흔들림: 바꿔 끼우는 사이 읽기가 한 번 비었다가 다시 돌리니 괜찮았다 — {len(first)}번, 처음 셋 {first[:3]}')
