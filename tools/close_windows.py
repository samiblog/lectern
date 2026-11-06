"""점검이 띄운 탐색기·VS Code 창을 닫는다.

점검 서버는 바깥 프로그램을 부르지 않는다 (tools/quiet_app.py). 그래도 실제 앱을 띄우는 점검이 남긴 창은
여기서 닫는다. ui_smoke·ui_edges 는 끝날 때 저절로 부른다. 따로 돌리는 점검은 이렇게 쓴다.

    python tools/close_windows.py --mark     :: 점검 전에. 지금 떠 있는 창을 적어 둔다
    python tools/close_windows.py            :: 점검 뒤에. 점검이 띄운 창을 닫는다

사용자의 창은 닫지 않는다.
- 탐색기: 임시 폴더 안의 점검 폴더(lec-·lectern-)만. 임시 폴더 자체는 점검 중에 새로 뜬 것만
  (폴더를 고른 채 열면 상위 폴더 창이 뜬다). 다른 탭이 함께 있는 창은 그대로 둔다.
- VS Code: 점검 중에 새로 뜬 창 중 폴더 없이 파일 하나만 열고 저장 안 한 고침이 없는 것만.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote, urlparse

MARK = Path(tempfile.gettempdir()) / 'lectern-test-windows.json'
PREFIXES = ('lec-', 'lectern-')
CODE_TITLE = ' - Visual Studio Code'
WM_CLOSE = 0x0010
GW_OWNER = 4


@dataclass(frozen=True)
class Window:
    hwnd: int
    kind: str       # 'explorer' 또는 'code'
    where: str      # 탐색기는 폴더, VS Code 는 창 제목


def folder_of(url: str) -> str:
    """탐색기의 file:///C:/… 주소를 경로로. 파일 폴더가 아니면 빈 글자."""
    if not url.lower().startswith('file:'):
        return ''
    path = unquote(urlparse(url).path).lstrip('/')
    return str(PureWindowsPath(path))


def is_test_folder(path: str, temp: str) -> bool:
    try:
        parts = PureWindowsPath(path).relative_to(PureWindowsPath(temp)).parts
    except ValueError:
        return False
    return any(part.lower().startswith(PREFIXES) for part in parts)


def is_test_code_title(title: str) -> bool:
    """폴더 없이 파일 하나만 연 창의 제목은 '파일 - Visual Studio Code' 이고, 고치다 만 글이 있으면 ● 가 붙는다."""
    return title.endswith(CODE_TITLE) and '●' not in title and ' - ' not in title[:-len(CODE_TITLE)]


def to_close(windows: list[Window], before: set[int], temp: str) -> list[Window]:
    """닫을 창을 고른다. before 는 점검 전에 떠 있던 창이다."""
    tabs: dict[int, list[Window]] = {}
    for w in windows:
        tabs.setdefault(w.hwnd, []).append(w)
    picked = []
    for hwnd, group in tabs.items():
        w = group[0]
        new = hwnd not in before
        if w.kind == 'code':
            if new and is_test_code_title(w.where):
                picked.append(w)
        elif all(is_test_folder(t.where, temp) or (new and PureWindowsPath(t.where) == PureWindowsPath(temp)) for t in group):
            picked.append(w)
    return picked


def open_windows() -> list[Window]:
    """떠 있는 탐색기·VS Code 창. Windows 가 아니거나 pywin32 가 없으면 있는 만큼만."""
    if sys.platform != 'win32':
        return []
    import ctypes
    from ctypes import wintypes
    found = []
    try:
        import win32com.client as wc
        for w in wc.Dispatch('Shell.Application').Windows():
            try:
                if str(w.FullName).lower().endswith('explorer.exe') and (folder := folder_of(str(w.LocationURL))):
                    found.append(Window(int(w.HWND), 'explorer', folder))
            except Exception:  # noqa: BLE001 — 닫히는 중인 창은 읽지 못한다
                continue
    except ImportError:
        pass
    user32 = ctypes.WinDLL('user32')

    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(400)
            user32.GetWindowTextW(hwnd, buf, 400)
            if buf.value.endswith(CODE_TITLE):
                found.append(Window(int(hwnd), 'code', buf.value))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    return found


def close(window: Window) -> None:
    """창을 닫는다. 폴더를 지운 뒤라 '위치를 사용할 수 없습니다' 가 떠 있으면 그 알림부터 닫는다."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32')
    alerts = []

    def visit(hwnd, _):
        name = ctypes.create_unicode_buffer(32)
        user32.GetClassNameW(hwnd, name, 32)
        if name.value == '#32770' and user32.GetWindow(hwnd, GW_OWNER) == window.hwnd:
            alerts.append(hwnd)
        return True

    if window.kind == 'explorer':
        user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(visit), 0)
    for hwnd in alerts:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    if alerts:
        time.sleep(.8)
    user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)


def snapshot() -> set[int]:
    return {w.hwnd for w in open_windows()}


def close_new(before: set[int]) -> list[Window]:
    """점검이 띄운 창을 닫고 그 목록을 준다. 창 정리 때문에 점검이 실패하지는 않는다."""
    try:
        picked = to_close(open_windows(), before, tempfile.gettempdir())
        for w in picked:
            close(w)
    except OSError as exc:
        print(f'남은 창을 닫지 못했습니다: {exc}', file=sys.stderr)
        return []
    if picked:
        print(f'점검이 띄운 창 {len(picked)}개를 닫았습니다: ' + ', '.join(Path(w.where).name for w in picked))
    return picked


def main(argv: list[str]) -> int:
    if '--mark' in argv:
        MARK.write_text(json.dumps(sorted(snapshot())), encoding='utf-8')
        return 0
    before = set(json.loads(MARK.read_text(encoding='utf-8'))) if MARK.exists() else snapshot()
    close_new(before)
    MARK.unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
