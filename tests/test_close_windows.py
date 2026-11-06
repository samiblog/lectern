"""tools/close_windows.py 시험 — 점검이 띄운 창만 고르는가. 사용자 창을 닫지 않는 것이 먼저다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

from close_windows import Window, folder_of, is_test_code_title, is_test_folder, to_close  # noqa: E402

TEMP = r'C:\Users\me\AppData\Local\Temp'


def explorer(hwnd, path):
    return Window(hwnd, 'explorer', path)


def code(hwnd, title):
    return Window(hwnd, 'code', title)


def picked(windows, before=()):
    return {w.hwnd for w in to_close(windows, set(before), TEMP)}


def test_folder_of_reads_explorer_addresses():
    assert folder_of("file:///C:/Users/me/AppData/Local/Temp/lec-hostile-8gt9/proj%20&%20'x'") == r"C:\Users\me\AppData\Local\Temp\lec-hostile-8gt9\proj & 'x'"
    assert folder_of('file:///D:/%EC%9E%90%EB%A3%8C') == r'D:\자료'
    assert folder_of('') == ''
    assert folder_of('::{20D04FE0-3AEA-1069-A2D8-08002B30309D}') == ''


def test_only_test_folders_under_temp_count():
    for path in (TEMP + r'\lec-hostile-8gt9\proj', TEMP + r'\lectern-smoke-1', TEMP + r'\claude\x\scratchpad\lec-winsolo-2\proj', TEMP.upper() + r'\LEC-A'):
        assert is_test_folder(path, TEMP), path
    for path in (TEMP, TEMP + r'\내 자료', TEMP + r'\lecture', r'D:\lec-project', r'D:\Works\lectern', r'C:\Users\me\Documents\lec-메모'):
        assert not is_test_folder(path, TEMP), path


def test_explorer_on_a_test_folder_closes_even_from_an_earlier_run():
    assert picked([explorer(1, TEMP + r'\lec-a\proj')], before=[1]) == {1}


def test_user_explorer_windows_stay_even_when_new():
    windows = [explorer(1, r'D:\Works\lectern'), explorer(2, r'C:\Users\me\Documents'), explorer(3, TEMP + r'\내 자료')]
    assert picked(windows) == set()


def test_temp_folder_itself_closes_only_when_it_came_up_during_the_test():
    assert picked([explorer(1, TEMP)]) == {1}
    assert picked([explorer(1, TEMP)], before=[1]) == set()


def test_a_window_with_a_user_tab_stays():
    windows = [explorer(1, TEMP + r'\lec-a'), explorer(1, r'D:\자료')]
    assert picked(windows) == set()
    assert picked([explorer(2, TEMP + r'\lec-a'), explorer(2, TEMP + r'\lec-b')]) == {2}


def test_code_title():
    assert is_test_code_title('example.py - Visual Studio Code')
    assert not is_test_code_title('● example.py - Visual Studio Code')
    assert not is_test_code_title('example.py - lectern - Visual Studio Code')
    assert not is_test_code_title('Visual Studio Code')
    assert not is_test_code_title('example.py - Notepad')


def test_code_window_closes_only_when_new_clean_and_without_a_folder():
    title = 'example.py - Visual Studio Code'
    assert picked([code(1, title)]) == {1}
    assert picked([code(1, title)], before=[1]) == set(), '점검 전부터 있던 창'
    assert picked([code(1, '● ' + title)]) == set(), '저장 안 한 고침'
    assert picked([code(1, 'app.py - lectern - Visual Studio Code')]) == set(), '폴더를 연 창'
