"""PDF로 저장 (D131) — 인쇄 창 없이 창의 WebView2 가 지금 화면을 PDF 로 만든다 (CDP Page.printToPDF).

- 쪽 크기·여백·머리·쪽 번호는 화면의 보고서 인쇄 양식(web/themes/print.css 의 @page)을 따른다 (preferCSSPageSize).
  브라우저 인쇄 창이 붙이는 날짜·창 제목·주소(127.0.0.1) 머리글이 없다 — 이 길을 둔 까닭이다. WebView2 의 PrintToPdfAsync 는
  머리글을 끌 수 있지만 CSS 의 쪽 크기를 읽지 않아 Letter 로 나온다 (2026-11-13 WebView2 157 에서 시험).
- 쓰는 곳은 사용자가 저장 대화상자에서 고른 경로 하나뿐이다 (원칙 1의 예외). 덮어쓸지는 Windows 대화상자가 묻는다.
  Lectern 프로그램 폴더 안(설치된 예제)에는 쓰지 않는다 (D71). 같은 폴더의 임시 파일에 쓴 뒤 바꿔 끼운다 —
  쓰다 멈추면 반쪽 PDF 가 남지 않게.
- 개발자 도구를 꺼 둔 보통 실행에서도 CDP 를 부를 수 있다 (AreDevToolsEnabled 와 상관없다).
- 미리보기 (D134): 'PDF·인쇄' 창이 옵션을 바꿀 때마다 같은 길로 PDF 를 만들어 메모리에 두고(디스크에 쓰지 않는다), 서버가
  /pdf-preview/<토큰>.pdf 로 내준다 — 창의 iframe 이 WebView2 의 PDF 보기로 띄운다. 저장은 미리 본 그 바이트를 그대로 쓴다.
  토큰은 추측할 수 없는 값이고 최근 몇 개만 둔다 (/api 가 아니라 토큰 헤더가 없다 — iframe 은 헤더를 보낼 수 없다).
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import tempfile
from pathlib import Path
from threading import Lock, Semaphore
from typing import Any

from .i18n import t
from .paths import is_protected
from .scanner import resolve_inside

# 태그 PDF(읽어 주기·복사 순서)와 제목으로 만든 책갈피. 모르는 값은 WebView2 가 무시한다
PDF_PARAMS = {'preferCSSPageSize': True, 'printBackground': True, 'displayHeaderFooter': False,
              'generateTaggedPDF': True, 'generateDocumentOutline': True}
TIMEOUT = 180   # 초 — 그림이 많은 긴 문서도 보통 몇 초
MAX_PREVIEWS = 4   # 메모리에 두는 미리보기 PDF 수 (창 여럿이 함께 미리 볼 때도 모자라지 않게)
_previews: dict[str, bytes] = {}
_previews_lock = Lock()


def keep_preview(data: bytes) -> str:
    """미리보기 PDF 를 메모리에 두고 토큰을 준다. 오래된 것부터 버린다"""
    token = secrets.token_urlsafe(24)
    with _previews_lock:
        _previews[token] = data
        while len(_previews) > MAX_PREVIEWS:
            _previews.pop(next(iter(_previews)))
    return token


def preview_bytes(token: Any) -> bytes | None:
    """토큰의 미리보기 PDF (없거나 버렸으면 None)"""
    if not isinstance(token, str) or not token:
        return None
    with _previews_lock:
        return _previews.get(token)


def page_count(data: bytes) -> int:
    """PDF 의 쪽 수 (쪽 객체를 센다 — Chromium 이 만든 PDF 는 객체 흐름에 쪽을 넣지 않는다)"""
    return len(re.findall(rb'/Type\s*/Page[^s]', data))


def documents_dir() -> str:
    """내 문서 폴더 (없으면 집 폴더)"""
    home = Path.home()
    docs = home / 'Documents'
    return str(docs if docs.is_dir() else home)


def start_place(root: Path | None, rel: str) -> tuple[str, str]:
    """저장 대화상자가 처음 보일 폴더와 파일 이름: 문서 옆에 '문서 이름.pdf'.
    문서가 보기만 하는 폴더(D71 — 설치된 예제)에 있으면 내 문서 폴더에서 시작한다"""
    doc = resolve_inside(root, rel) if root is not None and rel else None
    if doc is None:
        return documents_dir(), 'document.pdf'
    folder = str(doc.parent)
    if is_protected(doc.parent):
        folder = documents_dir()
    return folder, doc.with_suffix('.pdf').name


def target_of(chosen: Any) -> Path | None:
    """대화상자가 준 값(글자 하나·목록·None) → 쓸 경로. 확장자가 .pdf 가 아니면 붙인다"""
    if isinstance(chosen, (list, tuple)):
        chosen = chosen[0] if chosen else None
    if not chosen:
        return None
    path = Path(os.path.abspath(str(chosen)))
    return path if path.suffix.lower() == '.pdf' else path.with_name(path.name + '.pdf')


def refuse(path: Path) -> str | None:
    """쓰면 안 되는 곳이면 화면에 보일 까닭"""
    if is_protected(path):
        return t('Lectern 프로그램 폴더 안에는 저장하지 않습니다 — 다른 폴더를 고르세요')
    if path.is_dir():
        return t('같은 이름의 폴더가 있습니다 — 다른 이름을 고르세요')
    if not path.parent.is_dir():
        return t('저장할 폴더가 없습니다: {path}', path=str(path.parent))
    return None


def write_pdf(path: Path, data: bytes) -> str | None:
    """PDF 를 쓴다 — 같은 폴더의 임시 파일에 쓰고 바꿔 끼운다. 못 쓰면 화면에 보일 까닭"""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.lectern-', suffix='.pdf.tmp', dir=path.parent)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
        tmp = None
        return None
    except PermissionError:
        return t('{name} 을 쓰지 못했습니다 — PDF 보기 프로그램이 그 파일을 열고 있으면 닫고 다시 저장하세요', name=path.name)
    except OSError as e:
        return t('{name} 을 쓰지 못했습니다: {error}', name=path.name, error=e.strerror or str(e))
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def print_to_pdf(window: Any) -> bytes:
    """창(pywebview, WinForms + WebView2)의 지금 화면을 PDF 바이트로. UI 스레드에서 부르고 끝날 때까지 기다린다.
    js_api 의 스레드에서 부른다 (UI 스레드에서 부르면 기다리는 동안 그 일이 돌지 못한다)"""
    from System import Action, Func, Object  # type: ignore[import-not-found]  # pythonnet — 창 모드에만
    from System.Threading.Tasks import Task  # type: ignore[import-not-found]

    wv = window.native.browser.webview
    done = Semaphore(0)
    box: dict[str, Any] = {}

    def finished(task: Any) -> None:
        try:
            box['json'] = task.Result
        except Exception as e:   # noqa: BLE001 — WebView2 의 오류(AggregateException)를 그대로 알린다
            box['error'] = e
        done.release()

    params = json.dumps(PDF_PARAMS)
    wv.Invoke(Func[Object](lambda: wv.CoreWebView2.CallDevToolsProtocolMethodAsync('Page.printToPDF', params)
                           .ContinueWith(Action[Task](finished))))
    if not done.acquire(timeout=TIMEOUT):
        raise TimeoutError(t('PDF 를 만드는 데 {n}초가 넘게 걸려 멈췄습니다', n=TIMEOUT))
    if 'error' in box:
        raise RuntimeError(str(box['error']))
    return base64.b64decode(json.loads(str(box['json']))['data'])


def save(window: Any, chosen: Any, token: Any = None) -> dict[str, str]:
    """대화상자에서 고른 값으로 PDF 를 쓴다 — 미리 본 것(token)이 있으면 그 바이트 그대로, 없으면 지금 만든다.
    화면에는 {'path'}·{'error'}, 고르지 않았으면 {}"""
    path = target_of(chosen)
    if path is None:
        return {}
    why = refuse(path)
    if why:
        return {'error': why}
    try:
        data = preview_bytes(token) or print_to_pdf(window)
    except Exception as e:   # noqa: BLE001 — WebView2 가 없는 PC, 시간 초과 등
        return {'error': t('PDF 를 만들지 못했습니다: {error}', error=str(e)[:300])}
    why = write_pdf(path, data)
    return {'error': why} if why else {'path': str(path)}
