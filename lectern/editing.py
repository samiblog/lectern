"""편집 모드 (D54): 문서·코드 파일의 원문을 주고, 고친 것을 저장한다 (GET /api/source, POST /api/save).

보기 전용(원칙 1)의 예외 — 사용자가 편집 모드에서 저장할 때만 그 파일 하나에 쓴다. 이미 있는 문서(md·html)·코드 파일만.
새로 만드는 것은 새 Markdown 문서 하나뿐이다 (D63·D65 — create_source: 사용자의 '새로 만들기'·'새 문서로 보내기'에서 경로를 정할 때,
프로젝트 안의 이미 있는 폴더에, 같은 이름이 있으면 만들지 않는다). 이름 바꾸기·지우기·폴더 만들기는 없다. UTF-8 글 파일만 고친다 (D1 — 다른 인코딩을 고치면 글자가 깨진다).
- 원문의 줄바꿈(CRLF/LF)과 BOM 은 저장할 때 그 파일의 것을 되살린다 (편집기는 LF 로만 다룬다). 섞여 있으면 많은 쪽으로.
- 그사이 다른 곳(Claude Code 등)이 고쳤으면 덮어쓰지 않는다 — 원문을 줄 때의 내용(SHA-256)과 지금 파일의 내용을 맞춰 보고
  다르면 409. 수정 시각·크기만으로는 같은 순간에 같은 크기로 바뀐 것을 놓친다. 화면이 물어서 덮어쓰기로 하면 force.
- 같은 폴더의 임시 파일(.lectern-….tmp — 점으로 시작해 감시·목록에 나오지 않는다)에 다 쓴 뒤 바꿔 끼운다 — 쓰다 멈춰도 원래 파일이
  남게. Windows 는 ReplaceFileW 로 — 원래 파일의 속성(숨김 등)·만든 시각·권한(ACL)을 그대로 둔다. 바꿔 끼울 수 없으면(다른 프로그램이
  잠깐 열어 둠) 조금 기다려 다시 해 보고, 그래도 안 되면 그 자리에 쓴다. 원래 자리에 새 내용이 들어갔는지 확인하기 전에는 임시 파일을
  지우지 않는다 — 저장이 끝내 안 되면 그 임시 파일에 고친 내용이 남는다 (오류에 그 경로). 읽기 전용 파일은 고치지 않는다.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Any

from .i18n import t
from .scanner import doc_kind, is_code, resolve_inside

MAX_EDIT_BYTES = 2 * 1024 * 1024
BOM = b'\xef\xbb\xbf'
# Windows 가 파일 이름에 받지 않는 글자와 이름 (새 문서 — D63)
BAD_NAME_CHARS = frozenset('<>:"/\\|?*') | frozenset(chr(c) for c in range(32))
RESERVED_NAMES = frozenset({'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))})


class EditError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def can_edit(name: str) -> bool:
    """편집 모드로 고칠 수 있는 종류 — 문서(md·html)와 코드"""
    return bool(doc_kind(name)) or is_code(name)


def _check(path: Path) -> os.stat_result:
    if not path.exists():
        raise EditError(404, t('파일이 없습니다 — 그사이 지워졌거나 이름이 바뀌었습니다'))
    if not path.is_file() or not can_edit(path.name):
        raise EditError(400, t('문서와 코드 파일만 편집할 수 있습니다'))
    st = path.stat()
    if st.st_size > MAX_EDIT_BYTES:
        raise EditError(413, t('{n}MB 가 넘는 파일은 편집할 수 없습니다', n=MAX_EDIT_BYTES // (1024 * 1024)))
    return st


def _decode(data: bytes) -> str:
    body = data[len(BOM):] if data.startswith(BOM) else data
    if b'\x00' in body:
        raise EditError(400, t('글 파일이 아니라서 편집할 수 없습니다'))
    try:
        return body.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise EditError(400, t('UTF-8 이 아닌 파일은 편집할 수 없습니다 (Lectern 은 UTF-8 글만 고칩니다)')) from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_whole(path: Path) -> bytes:
    """다른 프로그램이 쓰는 중이면(읽은 길이가 크기와 다름) 잠깐 기다려 다시 읽는다"""
    for _ in range(5):
        size = path.stat().st_size
        data = path.read_bytes()
        if len(data) == size:
            return data
        time.sleep(0.05)
    return data


def _newline(data: bytes) -> bytes:
    """그 파일의 줄바꿈 — 섞여 있으면 많은 쪽 (Claude Code 가 LF 로 쓴 파일에 PowerShell 이 CRLF 줄을 더한 경우 등)"""
    crlf = data.count(b'\r\n')
    return b'\r\n' if crlf > data.count(b'\n') - crlf else b'\n'


def read_source(path: Path) -> dict[str, Any]:
    """편집할 원문: {text(LF), newline, bom, hash(원문 바이트의 SHA-256), size}"""
    _check(path)
    data = _read_whole(path)
    text = _decode(data)
    return {'text': text.replace('\r\n', '\n'), 'newline': _newline(data).decode(), 'bom': data.startswith(BOM),
            'hash': _digest(data), 'size': len(data)}


def _swap(tmp: Path, path: Path) -> None:
    """임시 파일(tmp)로 path 를 바꿔 끼운다. Windows 는 ReplaceFileW — 원래 파일의 속성·만든 시각·ACL 을 남긴다"""
    if sys.platform == 'win32':
        import ctypes

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        flags = 0x2 | 0x4   # REPLACEFILE_IGNORE_MERGE_ERRORS | REPLACEFILE_IGNORE_ACL_ERRORS
        if kernel32.ReplaceFileW(str(path), str(tmp), None, flags, None, None):
            return
        raise PermissionError(ctypes.get_last_error() or 5, 'ReplaceFileW', str(path))
    os.replace(tmp, path)


def _holds(path: Path, data: bytes) -> bool:
    """path 에 data 가 그대로 들어 있는지"""
    try:
        return path.read_bytes() == data
    except OSError:
        return False


def save_source(path: Path, text: str, expect: Any, force: bool = False) -> dict[str, Any]:
    """고친 글(text — 줄바꿈은 무엇이든)을 그 파일의 줄바꿈·BOM 으로 저장한다. expect: 원문을 줄 때의 hash. {hash, size}"""
    _check(path)
    current = _read_whole(path)
    if not force and _digest(current) != expect:
        raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
    _decode(current)   # 그사이 UTF-8 이 아닌 파일로 바뀌었으면 덮어쓰지 않는다
    if not os.access(path, os.W_OK):
        raise EditError(403, t('읽기 전용 파일이라 저장하지 않았습니다 — 파일 속성에서 읽기 전용을 끄면 저장할 수 있습니다'))
    body = text.replace('\r\n', '\n').replace('\r', '\n')
    newline = _newline(current)
    if newline == b'\r\n':
        body = body.replace('\n', '\r\n')
    # 짝 없는 대리 문자(깨진 붙여 넣기 등)는 ? 로 — UTF-8 로 쓸 수 없다
    data = (BOM if current.startswith(BOM) else b'') + body.encode('utf-8', errors='replace')
    if len(data) > MAX_EDIT_BYTES:
        raise EditError(413, t('{n}MB 가 넘는 파일은 편집할 수 없습니다', n=MAX_EDIT_BYTES // (1024 * 1024)))
    tmp = path.with_name(f'.lectern-{secrets.token_hex(4)}.tmp')   # 짧게 — 긴 경로가 Windows 의 길이 한도를 넘지 않게
    error: OSError | None = None
    try:
        with open(tmp, 'xb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(5):   # Lectern 이나 다른 프로그램이 잠깐 읽는 중이면 바꿔 끼울 수 없다 — 조금 기다려 다시
            try:
                _swap(tmp, path)
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        else:
            path.write_bytes(data)   # 그래도 안 되면 그 자리에 쓴다
    except OSError as exc:
        error = exc
    saved = _holds(path, data)
    if saved:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass   # 지우지 못한 임시 파일 (점으로 시작해 목록에 나오지 않는다) — 저장은 됐다
    elif tmp.exists():   # 저장하지 못했다 — 고친 내용은 임시 파일에 남겨 둔다
        reason = (error.strerror or str(error)) if error else '?'
        raise EditError(500, t('저장하지 못했습니다: {error}. 고친 내용은 {tmp} 에 남겨 두었습니다', error=reason, tmp=str(tmp)))
    else:
        raise EditError(500, t('저장하지 못했습니다: {error}', error=(error.strerror or str(error)) if error else '?'))
    return {'hash': _digest(data), 'size': len(data)}


def new_doc_path(root: Path, rel: str, exclude: frozenset[str]) -> Path:
    """새 Markdown 문서를 만들 자리 (D63). rel: 프로젝트 기준 경로 ('reports/요약.md'). 이미 있는 폴더에, .md 만,
    숨김·제외 폴더 안과 Windows 가 받지 않는 이름은 안 된다 — 트리에 보이고 다시 열 수 있는 문서만 만든다. 안 되면 EditError"""
    parts = rel.replace('\\', '/').strip('/').split('/')
    name = parts[-1]
    if any(p in ('', '.', '..') for p in parts):
        raise EditError(400, t('새 문서의 경로가 올바르지 않습니다'))
    stem = os.path.splitext(name)[0]
    if (doc_kind(name) != 'markdown' or not stem.strip() or name.startswith('.') or name[-1] in ' .'
            or any(c in BAD_NAME_CHARS for c in name) or stem.lower() in RESERVED_NAMES):
        raise EditError(400, t('새 문서는 .md 로 끝나는 이름이어야 합니다 — 점으로 시작하거나 : * ? " < > | 같은 글자가 든 이름은 쓸 수 없습니다'))
    folders = parts[:-1]
    excluded = next((f for f in folders if f.lower() in exclude), None)
    if excluded:
        raise EditError(400, t('제외 폴더({name}) 안에는 만들지 않습니다 — 트리에 보이지 않습니다', name=excluded))
    folder = resolve_inside(root, '/'.join(folders)) if folders else root
    # 정션·링크를 거쳐 다른 곳으로 가는 폴더도 막는다 (트리에 없는 폴더)
    if folder is None or not folder.is_dir() or os.path.normcase(folder) != os.path.normcase(os.path.join(root, *folders)):
        raise EditError(404, t('폴더가 없습니다 — 새 문서는 이미 있는 폴더에만 만듭니다'))
    return folder / name


def create_source(path: Path, text: str) -> dict[str, Any]:
    """새 문서(path — new_doc_path 가 정한 자리)를 만들어 text 를 쓴다 (LF, BOM 없음). 같은 이름이 있으면 409 — 덮어쓰지 않는다. {hash, size}"""
    body = text.replace('\r\n', '\n').replace('\r', '\n')
    data = body.encode('utf-8', errors='replace')
    if len(data) > MAX_EDIT_BYTES:
        raise EditError(413, t('{n}MB 가 넘는 파일은 편집할 수 없습니다', n=MAX_EDIT_BYTES // (1024 * 1024)))
    try:
        with open(path, 'xb') as fh:   # 있으면 실패 (대소문자만 다른 이름도 — Windows)
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except FileExistsError as exc:
        raise EditError(409, t('같은 이름의 파일이 있습니다 — 다른 이름으로 만드세요')) from exc
    except OSError as exc:
        raise EditError(500, t('새 문서를 만들지 못했습니다: {error}', error=exc.strerror or str(exc))) from exc
    return {'hash': _digest(data), 'size': len(data)}
