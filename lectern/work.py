"""업무 관리 (D124): 폴더마다 맨 위의 WORK.md 하나와 공통 폴더 (GET /api/work 등).

WORK.md 가 있는 폴더를 열거나 '폴더 더하기'로 고르면 그 경로를 설정(work_folders)에 기억한다. 업무 현황은 기억한 폴더와
공통 폴더(work_home)의 WORK.md 를 모아 보인다 — 탭이 닫혀 있어도. 원칙 3(고른 폴더와 그 하위만)의 예외라 좁게 둔다:
  - 읽는 것은 그 폴더 맨 위의 WORK.md 한 파일뿐이다. 그 폴더의 다른 파일은 읽지 않는다.
  - 경로는 설정에서만 온다. 요청은 목록에 있는 폴더를 이름으로 고를 뿐, 새 경로를 읽게 하지 못한다.
  - Lectern 프로그램 폴더 안(D71 — 예제)·링크·정션·숨김 파일은 읽지도 기억하지도 않는다.
쓰기는 일정 더하기 하나다 (사용자가 넣을 곳을 고르고 누를 때 — 문서로 보내기 D113 과 같은 규칙). 편집 모드와 같은 저장
(editing.save_source — 그사이 바뀌었으면 409, 임시 파일에 쓴 뒤 바꿔 끼우기)으로 그 파일만 고친다.
연결이 끊긴 드라이브의 폴더는 응답이 늦을 수 있어 파일마다 따로 읽고, 늦으면 기다리지 않고 '응답 없음'으로 둔다.
"""
from __future__ import annotations

import os
import stat
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from . import editing, paths
from .config import Config
from .editing import EditError
from .i18n import t
from .scanner import has_hidden_attr

WORK_FILE = 'WORK.md'
READ_WAIT = 3.0   # 업무 현황 한 번에 기다리는 시간(초). 넘은 폴더는 '응답 없음' — 다음 번에 다시 본다
_JUNCTION_TAG = 0xA0000003

_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='work')
_lock = threading.Lock()
_running: dict[str, Future] = {}               # 읽는 중인 폴더 (늦는 드라이브를 거듭 기다리지 않게)
_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}   # 폴더 → ((수정 시각, 크기), 읽은 것)


def _norm(folder: str) -> str:
    return os.path.normcase(os.path.normpath(folder))


def card_path(folder: Path) -> Path:
    return folder / WORK_FILE


def usable(folder: Path) -> Path | None:
    """folder 맨 위의 WORK.md 를 읽어도 되면 그 경로. 없거나, 프로그램 폴더 안(D71)이거나, 링크·정션·숨김이면 None"""
    path = card_path(folder)
    if paths.is_protected(path):
        return None
    try:
        st = path.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_reparse_tag', 0) == _JUNCTION_TAG or has_hidden_attr(st):
        return None
    return path if stat.S_ISREG(st.st_mode) else None


def note_opened(config: Config, root: Path) -> None:
    """프로젝트로 연 폴더에 WORK.md 가 있으면 업무 폴더 목록에 더한다. 공통 폴더는 더하지 않는다 (공통 WORK.md 는 과제가 아니다)"""
    home = config.get('work_home')
    if isinstance(home, str) and _norm(home) == _norm(str(root)):
        return
    if usable(root) is not None:
        config.add_work_folder(str(root))


def _read_one(folder: str) -> dict[str, Any]:
    """폴더 하나의 WORK.md — {text, hash, mtime} 또는 {error: missing-folder | missing-card | unreadable, detail}"""
    base = Path(folder)
    try:
        if not base.is_dir():
            return {'error': 'missing-folder'}
        path = usable(base)
        if path is None:
            return {'error': 'missing-card'}
        st = editing.steady(path.stat)
        sig = (st.st_mtime_ns, st.st_size)
        key = _norm(folder)
        hit = _cache.get(key)
        if hit and hit[0] == sig:
            return hit[1]
        source = editing.read_source(path)
        data = {'text': source['text'], 'hash': source['hash'], 'mtime': st.st_mtime}
        _cache[key] = (sig, data)
        return data
    except EditError as exc:
        return {'error': 'unreadable', 'detail': exc.message}
    except OSError as exc:
        return {'error': 'unreadable', 'detail': exc.strerror or str(exc)}


def _submit(folder: str) -> Future:
    key = _norm(folder)
    with _lock:
        job = _running.get(key)
        if job is None or job.done():
            job = _pool.submit(_read_one, folder)
            _running[key] = job
        return job


def board(config: Config) -> dict[str, Any]:
    """업무 현황의 재료: {home: {path, name, text, hash, mtime} | {path, name, error} | None, folders: [같은 모양…], alerts}.
    WORK.md 의 글을 그대로 준다 — 읽어 계산하는 것(상태·기한·일정)은 화면이 한다 (오늘 날짜가 화면의 것이다)"""
    home = config.get('work_home')
    home = home if isinstance(home, str) and home else None
    folders = [f for f in config.get('work_folders') or [] if isinstance(f, str) and f]
    if home:
        folders = [f for f in folders if _norm(f) != _norm(home)]
    wanted = ([home] if home else []) + folders
    jobs = [(folder, _submit(folder)) for folder in wanted]
    deadline = time.monotonic() + READ_WAIT
    read: dict[str, dict[str, Any]] = {}
    for folder, job in jobs:
        try:
            data = job.result(timeout=max(0.01, deadline - time.monotonic()))
        except FutureTimeout:
            data = {'error': 'slow'}
        read[folder] = {'path': folder, 'name': Path(folder).name or folder} | data
    return {'home': read[home] if home else None, 'folders': [read[f] for f in folders], 'alerts': config.get('work_alerts') is not False}


def _known(config: Config, folder: str) -> bool:
    key = _norm(folder)
    home = config.get('work_home')
    listed = [f for f in config.get('work_folders') or [] if isinstance(f, str)]
    return (isinstance(home, str) and bool(home) and _norm(home) == key) or any(_norm(f) == key for f in listed)


def _target(config: Config, folder: Any) -> Path:
    """목록이나 공통 폴더에 있는 폴더의 WORK.md. 요청이 목록에 없는 경로를 고르면 403"""
    if not isinstance(folder, str) or not folder or not _known(config, folder):
        raise EditError(403, t('업무 폴더 목록에 없는 폴더입니다 — 업무 현황을 다시 열어 고르세요'))
    path = usable(Path(folder))
    if path is None:
        raise EditError(404, t('WORK.md 가 없습니다 — 그사이 지워졌거나 폴더가 옮겨졌습니다'))
    return path


def read_card(config: Config, folder: Any) -> dict[str, Any]:
    """일정 더하기가 고칠 원문: editing.read_source 와 같다 {text(LF), newline, bom, hash, size}"""
    return editing.read_source(_target(config, folder))


def save_card(config: Config, folder: Any, text: str, expect: Any) -> dict[str, Any]:
    """WORK.md 에 고친 글을 쓴다 — 읽은 뒤로 바뀌었으면 409. {hash, size}"""
    path = _target(config, folder)
    result = editing.save_source(path, text, expect)
    _cache.pop(_norm(folder), None)
    return result


def _folder_arg(folder: Any) -> Path:
    if not isinstance(folder, str) or not folder.strip():
        raise EditError(400, t('폴더를 고르세요'))
    path = Path(folder.strip().strip('"')).expanduser()
    if not path.is_absolute():
        raise EditError(400, t('폴더의 전체 경로가 필요합니다'))
    path = path.resolve()
    if not path.is_dir():
        raise EditError(404, t('폴더가 아닙니다: {path}', path=path))
    if paths.is_protected(path):
        raise EditError(403, t('Lectern 프로그램 폴더 안은 업무 관리에 쓰지 않습니다 — 예제는 다른 곳에 복사해 쓰세요'))
    return path


def add_folder(config: Config, folder: Any) -> str:
    """'폴더 더하기' — 고른 폴더를 업무 폴더 목록에 더한다. WORK.md 가 없으면 EditError(404, code no-card 는 서버가 붙인다)"""
    path = _folder_arg(folder)
    if usable(path) is None:
        raise EditError(404, t('그 폴더에 WORK.md 가 없습니다'))
    config.add_work_folder(str(path))
    return str(path)


def remove_folder(config: Config, folder: Any) -> None:
    """목록에서 뺀다 — 파일과 폴더는 그대로. 목록에 없는 글이면 아무 일도 없다"""
    if isinstance(folder, str) and folder:
        config.remove_work_folder(folder)
        _cache.pop(_norm(folder), None)


def set_home(config: Config, folder: Any) -> str | None:
    """공통 폴더를 정한다 (None·빈 글이면 비운다). 고른 폴더가 목록에 있으면 목록에서 빠진다"""
    if folder is None or (isinstance(folder, str) and not folder.strip()):
        config.set_work_home(None)
        return None
    path = _folder_arg(folder)
    config.set_work_home(str(path))
    return str(path)
