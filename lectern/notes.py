"""프로젝트 메모 (D92): 프로젝트 폴더의 .lectern/notes.md 하나 (GET·POST /api/notes).

앱이 스스로 사용자 파일을 만들지 않는다는 원칙 1 의 예외다 — 사용자가 메모를 쓸 때만, 이 자리 하나에만 쓴다.
점으로 시작해 트리·검색에 나오지 않고, 폴더를 옮기면 메모도 따라가며, Claude Code 가 읽을 수 있다.
저장은 편집 모드와 같은 길이다 (editing.py — 그사이 바뀌었으면 409, 임시 파일에 쓴 뒤 바꿔 끼우기).
경로는 고정이라 요청이 고르지 못한다. .lectern 이 링크나 정션이면 프로젝트 밖일 수 있어 쓰지 않는다.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from . import editing, paths
from .editing import EditError
from .i18n import t

NOTES_DIR = '.lectern'
NOTES_FILE = 'notes.md'
_JUNCTION_TAG = 0xA0000003


def notes_path(root: Path) -> Path:
    return root / NOTES_DIR / NOTES_FILE


def _is_link(path: Path) -> bool:
    """심볼릭 링크 또는 정션인지 (scanner 의 판정과 같게 — 정션은 reparse tag 로 본다)"""
    try:
        st = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or getattr(st, 'st_reparse_tag', 0) == _JUNCTION_TAG


def _check(root: Path) -> Path:
    path = notes_path(root)
    if paths.is_protected(path):
        raise EditError(403, t('Lectern 프로그램 폴더 안에서는 메모를 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요'))
    if _is_link(path.parent) or _is_link(path):
        raise EditError(403, t('메모 폴더가 링크라 쓰지 않았습니다 — .lectern 을 보통 폴더로 바꾸세요'))
    return path


def read_notes(root: Path) -> dict[str, Any]:
    """{text, hash, exists}. 파일이 없으면 빈 글 — 만들지 않는다"""
    path = notes_path(root)
    if _is_link(path.parent) or _is_link(path) or not path.is_file():
        return {'text': '', 'hash': None, 'exists': False}
    return editing.read_source(path) | {'exists': True}


def save_notes(root: Path, text: str, expect: Any) -> dict[str, Any]:
    """메모 글을 쓴다. expect: 읽을 때의 hash (없던 파일이면 None). {hash, size}"""
    path = _check(root)
    if path.exists():
        if expect is None:   # 없는 줄 알았는데 그사이 생겼다
            raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
        return editing.save_source(path, text, expect)
    if expect is not None:   # 있던 파일이 그사이 지워졌다 — 다시 읽게 한다
        raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
    try:
        os.makedirs(path.parent, exist_ok=True)
    except OSError as exc:
        raise EditError(500, t('메모 폴더를 만들지 못했습니다: {error}', error=exc.strerror or str(exc))) from exc
    return editing.create_source(path, text)
