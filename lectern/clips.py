"""담기함 (D197): 프로젝트 폴더의 .lectern/clips/ 에 담기함마다 Markdown 파일 하나 (GET·POST /api/clips, POST /api/clips/delete).

프로젝트 메모(notes.py — D92)와 같은 규칙이다: 사용자가 담거나 고칠 때만 만들고 쓰며, 이 폴더 안에만 쓴다. 점으로 시작해 트리·검색·모아 보기에
나오지 않고(담은 표가 원본과 겹쳐 두 번 나오지 않게), 폴더를 옮기면 따라가며, Claude Code 가 읽을 수 있다.
저장은 편집 모드와 같은 길이다 (editing.py — 그사이 바뀌었으면 409). 요청이 고르는 것은 파일 이름 하나뿐이고, 이름은 폴더 글자를 받지 않는다.
.lectern·clips 나 그 파일이 링크·정션이면 프로젝트 밖일 수 있어 읽지도 쓰지도 않는다. 담기함을 지우는 것은 휴지통으로만 (D104 — trash.py).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import editing, paths, trash
from .editing import BAD_NAME_CHARS, RESERVED_NAMES, EditError
from .i18n import t
from .notes import NOTES_DIR, _is_link

CLIPS_DIR = 'clips'
MAX_BOXES = 200
MAX_STEM = 60


def clips_dir(root: Path) -> Path:
    return root / NOTES_DIR / CLIPS_DIR


def _linked(root: Path) -> bool:
    return _is_link(root / NOTES_DIR) or _is_link(clips_dir(root))


def good_name(name: Any) -> bool:
    """담기함의 파일 이름으로 쓸 수 있는지 — 폴더 글자·숨김·Windows 가 받지 않는 이름은 아니다"""
    if not isinstance(name, str) or not name.lower().endswith('.md') or len(name) > MAX_STEM + 24:
        return False
    stem = name[:-3]
    return bool(stem) and stem[0] != '.' and stem == stem.strip() and not stem.endswith('.') \
        and not any(c in BAD_NAME_CHARS for c in name) and stem.split('.')[0].strip().lower() not in RESERVED_NAMES


def _target(root: Path, name: Any) -> Path:
    """쓸 파일. 이름이 올바르지 않거나 쓸 수 없는 자리면 EditError"""
    if not good_name(name):
        raise EditError(400, t('파일 경로가 올바르지 않습니다'))
    path = clips_dir(root) / name
    if paths.is_protected(path):
        raise EditError(403, t('Lectern 프로그램 폴더 안에서는 담기함을 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요'))
    if _linked(root) or _is_link(path):
        raise EditError(403, t('담기함 폴더가 링크라 쓰지 않았습니다 — .lectern 과 clips 를 보통 폴더로 바꾸세요'))
    return path


def _stem(title: str) -> str:
    """제목에서 파일 이름 — 빈칸은 - 로 (터미널의 @경로 가 끊기지 않게)"""
    kept = ''.join(' ' if c in BAD_NAME_CHARS or c in '@#' else c for c in title)
    stem = '-'.join(kept.split())[:MAX_STEM].strip('.-')
    if not stem or stem.split('.')[0].lower() in RESERVED_NAMES:
        stem = '-'.join(t('담기함').split())
    return stem


def read_clips(root: Path) -> dict[str, Any]:
    """{boxes: [{file, text, hash, mtime} | {file, error}]} — 이름 차례. 없으면 빈 목록 (만들지 않는다)"""
    boxes: list[dict[str, Any]] = []
    if _linked(root):
        return {'boxes': boxes}
    try:
        names = sorted((e.name for e in os.scandir(clips_dir(root)) if e.is_file(follow_symlinks=False)), key=str.lower)
    except OSError:
        return {'boxes': boxes}
    for name in names:
        path = clips_dir(root) / name
        if not good_name(name) or _is_link(path) or len(boxes) >= MAX_BOXES:
            continue
        try:
            got = editing.read_source(path)
            boxes.append({'file': name, 'text': got['text'], 'hash': got['hash'], 'mtime': path.stat().st_mtime})
        except EditError as exc:   # 너무 크거나 UTF-8 이 아닌 것 — 다른 담기함은 보인다
            boxes.append({'file': name, 'error': exc.message})
        except OSError:
            continue   # 읽는 사이 지워짐
    return {'boxes': boxes}


def save_clips(root: Path, name: Any, text: str, expect: Any) -> dict[str, Any]:
    """담기함 하나를 쓴다. expect: 읽을 때의 hash (없던 파일이면 None). {file, hash, mtime}"""
    path = _target(root, name)
    if path.exists():
        if expect is None:
            raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
        saved = editing.save_source(path, text, expect)
    else:
        if expect is not None:   # 있던 파일이 그사이 지워졌다 — 다시 읽게 한다
            raise EditError(409, t('편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다'))
        saved = _create(path, text)
    return {'file': name, 'hash': saved['hash'], 'mtime': path.stat().st_mtime}


def _create(path: Path, text: str) -> dict[str, Any]:
    try:
        os.makedirs(path.parent, exist_ok=True)
    except OSError as exc:
        raise EditError(500, t('담기함 폴더를 만들지 못했습니다: {error}', error=exc.strerror or str(exc))) from exc
    return editing.create_source(path, text)


def create_clips(root: Path, title: str, text: str) -> dict[str, Any]:
    """새 담기함 — 이름은 제목에서, 같은 이름이 있으면 번호를 붙인다 (덮어쓰지 않는다). {file, hash, mtime}"""
    stem = _stem(title)
    for n in range(1, 1000):
        name = f'{stem}{f"-{n}" if n > 1 else ""}.md'
        path = _target(root, name)
        if path.exists():
            continue
        try:
            saved = _create(path, text)
        except EditError as exc:
            if exc.status == 409:
                continue
            raise
        return {'file': name, 'hash': saved['hash'], 'mtime': path.stat().st_mtime}
    raise EditError(409, t('같은 이름의 파일이 있습니다 — 다른 이름으로 만드세요'))


def delete_clips(root: Path, name: Any) -> None:
    """담기함 하나를 휴지통으로 — 되살릴 수 없게 지우는 길은 없다"""
    path = _target(root, name)
    if not path.is_file():
        raise EditError(404, t('파일이 없습니다 — 그사이 지워졌거나 이름이 바뀌었습니다'))
    try:
        trash.send(path)
    except trash.TrashError as exc:
        raise EditError(409, exc.message) from exc
