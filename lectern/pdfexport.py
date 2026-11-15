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
- 내보내기 창의 'html 로 저장' (D144): 화면이 지은 html 한 파일도 같은 길이다 — 메모리에 두고(/api/export/keep) /export-preview/<토큰>.html
  로 미리 보이고, 저장 대화상자에서 고른 경로에 그 바이트를 그대로 쓴다 (native.save_export). 미리보기는 형식(kind)마다 따로 센다.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import tempfile
import time
from pathlib import Path
from threading import Event, Lock, Semaphore
from typing import Any

from .i18n import t
from .paths import is_protected
from .scanner import resolve_inside

# 태그 PDF(읽어 주기·복사 순서)와 제목으로 만든 책갈피. 모르는 값은 WebView2 가 무시한다
PDF_PARAMS = {'preferCSSPageSize': True, 'printBackground': True, 'displayHeaderFooter': False,
              'generateTaggedPDF': True, 'generateDocumentOutline': True}
TIMEOUT = 180   # 초 — 그림이 많은 긴 문서도 보통 몇 초
MAX_PREVIEWS = 4   # 형식마다 메모리에 두는 미리보기 수 (창 여럿이 함께 미리 볼 때도 모자라지 않게)
MAX_HTML = 300 * 1024 * 1024   # html 한 파일 — 그림이 파일 안에 들어간다 (html 로 전환과 같다, D129)
HTML_MARK = '<meta name="generator" content="Lectern'   # 화면이 짓는 파일의 머리. 다른 글을 받아 쓰지 않게
KINDS = {'pdf': '.pdf', 'html': '.html', 'docx': '.docx'}   # 메모리에 두는 미리보기의 형식 (docx 는 미리 보지 않고 저장만 — D146)
_previews: dict[str, tuple[str, bytes]] = {}
_previews_lock = Lock()


def keep_preview(data: bytes, kind: str = 'pdf') -> str:
    """미리보기(PDF·html)를 메모리에 두고 토큰을 준다. 형식마다 오래된 것부터 버린다"""
    token = secrets.token_urlsafe(24)
    with _previews_lock:
        _previews[token] = (kind, data)
        same = [k for k, (kd, _) in _previews.items() if kd == kind]
        for old in same[:max(0, len(same) - MAX_PREVIEWS)]:
            _previews.pop(old, None)
    return token


def preview_bytes(token: Any, kind: str = 'pdf') -> bytes | None:
    """토큰의 미리보기 (없거나 버렸거나 형식이 다르면 None)"""
    if not isinstance(token, str) or not token:
        return None
    with _previews_lock:
        got = _previews.get(token)
    return got[1] if got and got[0] == kind else None


def keep_html(text: Any) -> str:
    """'html 로 저장' 의 미리보기 (D144): 화면이 지은 html 한 파일을 메모리에 둔다. 화면이 지은 것이 아니거나 너무 크면 ValueError"""
    if not isinstance(text, str) or not text.startswith('<!doctype html>') or HTML_MARK not in text[:2000]:
        raise ValueError(t('내보낸 html 이 아닙니다 — 창을 닫고 다시 여세요'))
    data = text.encode('utf-8')
    if len(data) > MAX_HTML:
        raise ValueError(t('html 이 300MB 를 넘습니다 — 큰 그림을 줄인 뒤 다시 하세요'))
    return keep_preview(data, 'html')


def page_count(data: bytes) -> int:
    """PDF 의 쪽 수 (쪽 객체를 센다 — Chromium 이 만든 PDF 는 객체 흐름에 쪽을 넣지 않는다)"""
    return len(re.findall(rb'/Type\s*/Page[^s]', data))


def documents_dir() -> str:
    """내 문서 폴더 (없으면 집 폴더)"""
    home = Path.home()
    docs = home / 'Documents'
    return str(docs if docs.is_dir() else home)


def start_place(root: Path | None, rel: str, ext: str = '.pdf') -> tuple[str, str]:
    """저장 대화상자가 처음 보일 폴더와 파일 이름: 문서 옆에 '문서 이름.pdf'(html 이면 .html).
    문서가 보기만 하는 폴더(D71 — 설치된 예제)에 있으면 내 문서 폴더에서 시작한다"""
    doc = resolve_inside(root, rel) if root is not None and rel else None
    if doc is None:
        return documents_dir(), f'document{ext}'
    folder = str(doc.parent)
    if is_protected(doc.parent):
        folder = documents_dir()
    return folder, doc.with_suffix(ext).name


def target_of(chosen: Any, ext: str = '.pdf') -> Path | None:
    """대화상자가 준 값(글자 하나·목록·None) → 쓸 경로. 확장자가 ext 가 아니면 붙인다 (html 은 .htm 도 받는다)"""
    if isinstance(chosen, (list, tuple)):
        chosen = chosen[0] if chosen else None
    if not chosen:
        return None
    path = Path(os.path.abspath(str(chosen)))
    ok = (ext,) if ext != '.html' else ('.html', '.htm')
    return path if path.suffix.lower() in ok else path.with_name(path.name + ext)


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
    return write_file(path, data, '.pdf')


def write_file(path: Path, data: bytes, ext: str) -> str | None:
    """내보낸 파일(PDF·html)을 쓴다 — 같은 폴더의 임시 파일에 쓰고 바꿔 끼운다 (쓰다 멈춰도 반쪽 파일이 남지 않게). 못 쓰면 화면에 보일 까닭"""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.lectern-', suffix=f'{ext}.tmp', dir=path.parent)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
        tmp = None
        return None
    except PermissionError:
        if ext == '.pdf':
            return t('{name} 을 쓰지 못했습니다 — PDF 보기 프로그램이 그 파일을 열고 있으면 닫고 다시 저장하세요', name=path.name)
        return t('{name} 을 쓰지 못했습니다 — 다른 프로그램이 그 파일을 열고 있으면 닫고 다시 저장하세요', name=path.name)
    except OSError as e:
        return t('{name} 을 쓰지 못했습니다: {error}', name=path.name, error=e.strerror or str(e))
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def print_hidden(url: str) -> bytes:
    """주소의 html 을 숨은 창에 열어 PDF 바이트로 (지면 틀 — D145). 다 읽고 글꼴이 준비되면 찍고 창을 닫는다.
    js_api 의 스레드에서 부른다 (창을 만들고 기다리는 동안 UI 스레드가 돌아야 한다)"""
    import webview

    hidden = webview.create_window('Lectern', url, hidden=True, width=1000, height=1400)
    loaded = Event()
    hidden.events.loaded += lambda: loaded.set()
    try:
        if not loaded.wait(60):
            raise TimeoutError(t('PDF 를 만드는 데 {n}초가 넘게 걸려 멈췄습니다', n=60))
        for _ in range(50):   # 글꼴 (5초까지)
            try:
                if hidden.evaluate_js('document.fonts.status') == 'loaded':
                    break
            except Exception:   # noqa: BLE001 — 아직 읽는 중
                pass
            time.sleep(0.1)
        return print_to_pdf(hidden)
    finally:
        try:
            hidden.destroy()
        except Exception:   # noqa: BLE001 — 이미 닫혔다
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


def save_kept(chosen: Any, token: Any, kind: str) -> dict[str, str]:
    """'html 로 저장'(D144)·'Word로 저장'(D146): 대화상자에서 고른 값으로 메모리에 둔 파일을 그 바이트 그대로 쓴다.
    화면에는 {'path'}·{'error'}, 고르지 않았으면 {}"""
    ext = KINDS.get(kind)
    if kind == 'pdf' or ext is None:
        return {}
    path = target_of(chosen, ext)
    if path is None:
        return {}
    why = refuse(path)
    if why:
        return {'error': why}
    data = preview_bytes(token, kind)
    if data is None:
        return {'error': t('미리 본 html 이 없습니다 — 창을 닫고 다시 여세요') if kind == 'html' else t('만든 Word 파일이 없습니다 — 창을 닫고 다시 여세요')}
    why = write_file(path, data, ext)
    return {'error': why} if why else {'path': str(path)}


def save_html(chosen: Any, token: Any) -> dict[str, str]:
    """'html 로 저장' (D144) — save_kept 의 html"""
    return save_kept(chosen, token, 'html')
