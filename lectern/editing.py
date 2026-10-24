"""편집 모드 (D54): 문서·코드 파일의 원문을 주고, 고친 것을 저장한다 (GET /api/source, POST /api/save).

보기 전용(원칙 1)의 예외 — 사용자가 편집 모드에서 저장할 때만 그 파일 하나에 쓴다. 이미 있는 문서(md·html)·코드 파일만
(새로 만들기·이름 바꾸기·지우기는 없다). UTF-8 글 파일만 고친다 (D1 — 다른 인코딩을 고치면 글자가 깨진다).
- 원문의 줄바꿈(CRLF/LF)과 BOM 은 저장할 때 그 파일의 것을 되살린다 (편집기는 LF 로만 다룬다).
- 그사이 다른 곳(Claude Code 등)이 고쳤으면 덮어쓰지 않는다 — 원문을 줄 때의 수정 시각·크기와 맞춰 보고 다르면 409.
  화면이 물어서 덮어쓰기로 하면 force.
- 같은 폴더의 임시 파일(점으로 시작 — 감시·목록에 나오지 않는다)에 다 쓴 뒤 바꿔 끼운다 — 쓰다 멈춰도 원래 파일이 남게.
  바꿔 끼울 수 없으면(다른 프로그램이 지우지 못하게 열어 둠) 그 자리에 쓴다.
수정 시각(ns)은 JS 의 수로는 정밀도를 잃으므로 글자로 주고받는다.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

from .i18n import t
from .scanner import doc_kind, is_code

MAX_EDIT_BYTES = 2 * 1024 * 1024
BOM = b'\xef\xbb\xbf'


class EditError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def can_edit(name: str) -> bool:
    """편집 모드로 고칠 수 있는 종류 — 문서(md·html)와 코드"""
    return bool(doc_kind(name)) or is_code(name)


def _check(path: Path) -> os.stat_result:
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


def read_source(path: Path) -> dict[str, Any]:
    """편집할 원문: {text(LF), newline, bom, mtime_ns(글자), size}"""
    st = _check(path)
    data = path.read_bytes()
    text = _decode(data)
    return {'text': text.replace('\r\n', '\n'), 'newline': '\r\n' if '\r\n' in text else '\n', 'bom': data.startswith(BOM),
            'mtime_ns': str(st.st_mtime_ns), 'size': st.st_size}


def save_source(path: Path, text: str, mtime_ns: str, size: Any, force: bool = False) -> dict[str, Any]:
    """고친 글(text — 줄바꿈은 무엇이든)을 그 파일의 줄바꿈·BOM 으로 저장한다. {mtime_ns, size}"""
    st = _check(path)
    if not force and (str(st.st_mtime_ns) != str(mtime_ns) or st.st_size != size):
        raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
    current = path.read_bytes()
    _decode(current)   # 그사이 UTF-8 이 아닌 파일로 바뀌었으면 덮어쓰지 않는다
    body = text.replace('\r\n', '\n').replace('\r', '\n')
    if b'\r\n' in current:
        body = body.replace('\n', '\r\n')
    data = (BOM if current.startswith(BOM) else b'') + body.encode('utf-8')
    if len(data) > MAX_EDIT_BYTES:
        raise EditError(413, t('{n}MB 가 넘는 파일은 편집할 수 없습니다', n=MAX_EDIT_BYTES // (1024 * 1024)))
    tmp = path.with_name(f'.{path.name}.lectern-{secrets.token_hex(4)}.tmp')
    try:
        with open(tmp, 'xb') as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.replace(tmp, path)
        except PermissionError:   # 다른 프로그램이 지우지 못하게 열어 둠 — 그 자리에 쓴다
            path.write_bytes(data)
    except OSError as exc:
        raise EditError(500, t('저장하지 못했습니다: {error}', error=exc.strerror or str(exc))) from exc
    finally:
        tmp.unlink(missing_ok=True)
    st = path.stat()
    return {'mtime_ns': str(st.st_mtime_ns), 'size': st.st_size}
