"""파일 변경 감지.

Watcher 가 프로젝트 폴더를 감시해 ChangeLog 에 이벤트를 쌓고,
프런트엔드는 1초마다 GET /api/changes?since=<seq> 로 새 이벤트만 가져간다.
(푸시 대신 폴링을 쓰는 이유는 docs/DECISIONS.md 참고)

watchdog 가 없으면 2초 간격 스캔 비교(폴링)로 대신한다.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from pathlib import Path
from typing import Any

from .scanner import doc_kind, iter_files, scan

try:  # watchdog 는 선택 의존성
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - 폴링 대체 경로
    Observer = None
    FileSystemEventHandler = object

_IGNORED_EVENTS = {'opened', 'closed', 'closed_no_write'}


class ChangeLog:
    """단조 증가하는 순번(seq)이 붙은 변경 기록. 스레드 안전."""

    def __init__(self, maxlen: int = 5000):
        self._lock = threading.Lock()
        self._seq = 0
        self._items: deque[tuple[int, str | None, bool]] = deque(maxlen=maxlen)

    @property
    def seq(self) -> int:
        with self._lock:
            return self._seq

    def push(self, path: str | None, structure: bool = False) -> None:
        """path: 바뀐 md 파일 상대경로 (폴더 변경이면 None). structure: 트리 구성이 바뀜."""
        with self._lock:
            self._seq += 1
            self._items.append((self._seq, path, structure))

    def since(self, seq: int) -> dict[str, Any]:
        with self._lock:
            cur = self._seq
            if seq >= cur:
                return {'seq': cur, 'paths': [], 'structure': False, 'reset': seq > cur}
            oldest = self._items[0][0] if self._items else cur + 1
            reset = seq < oldest - 1  # 기록이 밀려나 놓친 이벤트가 있음
            paths: set[str] = set()
            structure = False
            for s, path, struct in self._items:
                if s <= seq:
                    continue
                if path:
                    paths.add(path)
                structure = structure or struct
        return {'seq': cur, 'paths': sorted(paths), 'structure': structure or reset, 'reset': reset}


class _Handler(FileSystemEventHandler):
    def __init__(self, watcher: 'Watcher'):
        super().__init__()
        self.watcher = watcher

    def on_any_event(self, event: Any) -> None:
        if event.event_type in _IGNORED_EVENTS:
            return
        self.watcher.handle(event.event_type, event.src_path,
                            getattr(event, 'dest_path', '') or '', event.is_directory)


class Watcher:
    def __init__(self, root: Path, log: ChangeLog, exclude: frozenset[str], poll_interval: float = 2.0):
        self.root = root
        self.log = log
        self.exclude = frozenset(x.lower() for x in exclude)
        self.poll_interval = poll_interval
        self._observer: Any = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.backend = 'none'

    def start(self, force_polling: bool = False) -> None:
        if Observer is not None and not force_polling:
            try:
                observer = Observer()
                observer.schedule(_Handler(self), str(self.root), recursive=True)
                observer.daemon = True
                observer.start()
                self._observer = observer
                self.backend = 'watchdog'
                return
            except OSError:
                self._observer = None
        self._thread = threading.Thread(target=self._poll_loop, name='lectern-poll', daemon=True)
        self._thread.start()
        self.backend = 'polling'

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except RuntimeError:
                pass
            self._observer = None

    # --- watchdog 이벤트 처리 ---------------------------------------------
    def _rel(self, raw: str | bytes) -> str | None:
        try:
            rel = Path(os.fsdecode(raw)).relative_to(self.root)
        except ValueError:
            return None
        parts = rel.parts
        if not parts:
            return None
        if any(p.startswith('.') or p.lower() in self.exclude for p in parts):
            return None
        return rel.as_posix()

    def handle(self, event_type: str, src: str | bytes, dest: str | bytes, is_dir: bool) -> None:
        for raw in (src, dest):
            if not raw:
                continue
            rel = self._rel(raw)
            if rel is None:
                continue
            if is_dir:
                if event_type != 'modified':
                    self.log.push(None, True)
            elif doc_kind(rel):
                self.log.push(rel, event_type != 'modified')

    # --- 폴링 대체 --------------------------------------------------------
    def _snapshot(self) -> dict[str, tuple[float, int]]:
        nodes = scan(self.root, self.exclude, with_info=False)
        return {n['path']: (n['mtime'], n['size']) for n in iter_files(nodes)}

    def _poll_loop(self) -> None:
        prev = self._snapshot()
        while not self._stop.wait(self.poll_interval):
            cur = self._snapshot()
            for path in sorted((cur.keys() - prev.keys()) | (prev.keys() - cur.keys())):
                self.log.push(path, True)
            for path in sorted(k for k in cur.keys() & prev.keys() if cur[k] != prev[k]):
                self.log.push(path, False)
            prev = cur
