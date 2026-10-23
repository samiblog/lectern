"""pywebview js_api — 창에서만 가능한 네이티브 기능만 둔다.

나머지 기능은 모두 HTTP API(server.py)에 있어서 브라우저 개발 모드에서도 동작한다.
밑줄(_)로 시작하는 속성은 pywebview가 JS에 노출하지 않는다.
"""
from __future__ import annotations

from typing import Any

from .state import AppState


class NativeApi:
    def __init__(self, state: AppState):
        self._state = state
        self._window: Any = None

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
