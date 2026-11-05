"""pywebview js_api — 창에서만 가능한 네이티브 기능만 둔다 (폴더 대화상자, 창 제목, 독립창, 발표 모드의 전체 화면).

나머지 기능은 모두 HTTP API(server.py)에 있어서 브라우저 개발 모드에서도 동작한다.
밑줄(_)로 시작하는 속성은 pywebview가 JS에 노출하지 않는다.
"""
from __future__ import annotations

from typing import Any

from .state import AppState


class NativeApi:
    def __init__(self, state: AppState, windows: Any = None):
        self._state = state
        self._windows = windows   # 독립창 (D95 — windows.py)
        self._window: Any = None
        self._fullscreen = False

    def open_window(self, query: str) -> bool:
        """독립창을 띄운다 (D95). query: 화면이 만든 주소의 뒤쪽. 띄우지 못하면 False"""
        return bool(self._windows and self._windows.open(query))

    def close_window(self) -> None:
        """이 창을 닫는다 — 독립창의 마지막 문서 탭을 닫을 때"""
        if self._window is not None:
            self._window.destroy()

    def choose_folder(self) -> str | None:
        """폴더 선택 대화상자. 취소하면 None. 폴더를 실제로 여는 것은 JS가 POST /api/open 으로 한다."""
        import webview

        if self._window is None:
            return None
        dialog = getattr(webview, 'FileDialog', None)
        kind = dialog.FOLDER if dialog else webview.FOLDER_DIALOG
        project = self._state.active_project   # 선택된 탭의 폴더에서 시작
        start = str(project.root) if project else ''
        result = self._window.create_file_dialog(kind, directory=start)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    def set_title(self, title: str) -> None:
        if self._window is not None:
            self._window.title = str(title)

    def set_fullscreen(self, on: bool) -> None:
        """창 전체 화면 켜기·끄기 — 발표 모드(present.js, D59)가 시작·끝날 때"""
        if self._window is not None and bool(on) != self._fullscreen:
            self._window.toggle_fullscreen()
            self._fullscreen = bool(on)
