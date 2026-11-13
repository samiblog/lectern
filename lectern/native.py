"""pywebview js_api — 창에서만 가능한 네이티브 기능만 둔다 (폴더 대화상자, 창 제목, 독립창, 발표 모드의 전체 화면, PDF로 저장).

나머지 기능은 모두 HTTP API(server.py)에 있어서 브라우저 개발 모드에서도 동작한다.
밑줄(_)로 시작하는 속성은 pywebview가 JS에 노출하지 않는다.
"""
from __future__ import annotations

from typing import Any

from .i18n import t
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

    def pdf_preview(self) -> dict[str, Any]:
        """'PDF·인쇄' 창의 미리보기 (D134): 이 창의 지금 화면을 PDF 로 만들어 메모리에 둔다 — {'token', 'pages', 'size'} 또는 {'error'}.
        화면은 /pdf-preview/<token>.pdf 를 iframe 으로 띄운다. PDF 보기의 저장 단추는 감춘다 — 파일은 'PDF로 저장…' 길로만 쓴다"""
        from . import pdfexport

        if self._window is None:
            return {'error': t('창이 없습니다')}
        try:
            self._hide_pdf_save()
            data = pdfexport.print_to_pdf(self._window)
        except Exception as e:   # noqa: BLE001 — WebView2 가 없는 PC, 시간 초과 등
            return {'error': t('PDF 를 만들지 못했습니다: {error}', error=str(e)[:300])}
        return {'token': pdfexport.keep_preview(data), 'pages': pdfexport.page_count(data), 'size': len(data)}

    def _hide_pdf_save(self) -> None:
        """WebView2 PDF 보기의 저장·다른 이름으로 저장 단추를 감춘다 (원칙 1 — 파일은 저장 대화상자 길로만). 못 하면 그대로"""
        if getattr(self, '_pdf_toolbar_done', False):
            return
        self._pdf_toolbar_done = True
        try:
            from Microsoft.Web.WebView2.Core import CoreWebView2PdfToolbarItems  # type: ignore[import-not-found]
            from System import Action  # type: ignore[import-not-found]

            wv = self._window.native.browser.webview
            hide = CoreWebView2PdfToolbarItems.Save | CoreWebView2PdfToolbarItems.SaveAs
            wv.Invoke(Action(lambda: setattr(wv.CoreWebView2.Settings, 'HiddenPdfToolbarItems', hide)))
        except Exception:   # noqa: BLE001 — 옛 WebView2 SDK 면 이 설정이 없다
            pass

    def save_pdf(self, tab: str, path: str, token: str = '') -> dict[str, str]:
        """'PDF로 저장…' (D131 — pdfexport.py): 저장 대화상자에서 사용자가 고른 경로에 이 창의 지금 화면(보고서 인쇄 양식)을
        PDF 하나로 쓴다. token 이 있으면 미리 본 PDF 를 그대로 (D134). 대화상자는 문서 옆, '문서 이름.pdf' 로 연다.
        화면에는 {'path'}·{'error'}, 취소면 {}"""
        import webview

        from . import pdfexport

        if self._window is None:
            return {}
        project = self._state.get(tab)
        folder, name = pdfexport.start_place(project.root if project else None, str(path or ''))
        dialog = getattr(webview, 'FileDialog', None)
        kind = dialog.SAVE if dialog else webview.SAVE_DIALOG
        chosen = self._window.create_file_dialog(kind, directory=folder, save_filename=name, file_types=(t('PDF 파일 (*.pdf)'),))
        return pdfexport.save(self._window, chosen, token)

    def set_title(self, title: str) -> None:
        if self._window is not None:
            self._window.title = str(title)

    def set_fullscreen(self, on: bool) -> None:
        """창 전체 화면 켜기·끄기 — 발표 모드(present.js, D59)가 시작·끝날 때"""
        if self._window is not None and bool(on) != self._fullscreen:
            self._window.toggle_fullscreen()
            self._fullscreen = bool(on)
