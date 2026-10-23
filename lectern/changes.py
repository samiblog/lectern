"""파일 변경 감지.

Watcher 가 프로젝트 폴더를 감시해 ChangeLog 에 이벤트를 쌓고,
프런트엔드는 1초마다 GET /api/changes?since=<seq> 로 새 이벤트만 가져간다.
(푸시 대신 폴링을 쓰는 이유는 docs/DECISIONS.md 참고)

watchdog 가 없으면 2초 간격 스캔 비교(폴링)로 대신한다.
문서가 아닌 파일은 생기고 지워지고 옮겨질 때만 기록한다 (others — 사이드바 '문서 외 파일'). 내용 수정은 보지 않는다.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from pathlib import Path
from typing import Any

from .scanner import doc_kind, iter_files, scan, scan_others

try:  # watchdog 는 선택 의존성
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - 폴링 대체 경로
    Observer = None
    FileSystemEventHandler = object

_IGNORED_EVENTS = {'opened', 'closed', 'closed_no_write'}


MAX_TOUCHED = 5000   # 내용이 바뀐 문서 외 파일을 기억하는 수 (최근 변경 — 넘으면 오래된 것부터 잊는다)


def _other_paths(nodes: list[dict[str, Any]]) -> dict[str, float]:
    """scan_others 트리의 파일과 제외 폴더(안은 읽지 않은 접힌 노드, D49) 경로 → 수정 시각 (폴더는 0)"""
    out: dict[str, float] = {}
    for n in nodes:
        if n['type'] == 'file' or n.get('excluded'):
            out[n['path']] = n.get('mtime', 0)
        if n.get('children'):
            out.update(_other_paths(n['children']))
    return out


class ChangeLog:
    """단조 증가하는 순번(seq)이 붙은 변경 기록. 스레드 안전."""

    def __init__(self, maxlen: int = 5000):
        self._lock = threading.Lock()
        self._seq = 0
        self._others_seq = 0   # 문서 외 파일 목록이 마지막으로 바뀌었을 수 있는 순번 (구조 변경 포함)
        self._tree_seq = 0     # touch 가 아닌 마지막 순번 — 문서 트리 스캔을 다시 쓸지 (문서 외 파일의 내용 수정으로는 다시 훑지 않게)
        self._items: deque[tuple[int, str | None, bool, bool, bool]] = deque(maxlen=maxlen)
        # 내용이 바뀐 문서 외 파일 → 그 순번 (최근 변경, D50). 목록(others_seq)은 그대로 두고 수정 시각만 새로 보게
        self._touched: dict[str, int] = {}

    @property
    def seq(self) -> int:
        with self._lock:
            return self._seq

    @property
    def others_seq(self) -> int:
        with self._lock:
            return self._others_seq

    @property
    def tree_seq(self) -> int:
        with self._lock:
            return self._tree_seq

    def push(self, path: str | None, structure: bool = False, others: bool = False) -> None:
        """path: 바뀐 문서 상대경로 (폴더·문서 외 파일이면 None). structure: 문서 트리 구성이 바뀜.
        others: 문서 외 파일이 생기거나 지워지거나 옮겨짐 (문서 트리는 그대로)."""
        with self._lock:
            self._seq += 1
            self._tree_seq = self._seq
            if structure or others:
                self._others_seq = self._seq
            self._items.append((self._seq, path, structure, others, False))

    def touch(self, path: str) -> None:
        """문서 외 파일(path)의 내용이 바뀜 — 목록은 그대로이고 최근 변경만 다시 볼 일 (D50)"""
        with self._lock:
            self._seq += 1
            self._items.append((self._seq, None, False, False, True))
            self._touched.pop(path, None)
            self._touched[path] = self._seq
            if len(self._touched) > MAX_TOUCHED:
                del self._touched[next(iter(self._touched))]

    def touched_since(self, seq: int) -> list[str]:
        """seq 뒤로 내용이 바뀐 문서 외 파일"""
        with self._lock:
            return [p for p, s in self._touched.items() if s > seq]

    def since(self, seq: int) -> dict[str, Any]:
        with self._lock:
            cur = self._seq
            if seq >= cur:
                return {'seq': cur, 'paths': [], 'structure': False, 'others': False, 'touched': False, 'reset': seq > cur}
            oldest = self._items[0][0] if self._items else cur + 1
            reset = seq < oldest - 1  # 기록이 밀려나 놓친 이벤트가 있음
            paths: set[str] = set()
            structure = others = touched = False
            for s, path, struct, other, touch in self._items:
                if s <= seq:
                    continue
                if path:
                    paths.add(path)
                structure = structure or struct
                others = others or other
                touched = touched or touch
        return {'seq': cur, 'paths': sorted(paths), 'structure': structure or reset, 'others': others or reset,
                'touched': touched or reset, 'reset': reset}


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

    def _excluded_top(self, raw: str | bytes) -> bool:
        """제외 폴더 자체인지 (그 위는 숨김도 제외도 아님). 안의 변경은 보지 않는다"""
        try:
            parts = Path(os.fsdecode(raw)).relative_to(self.root).parts
        except ValueError:
            return False
        return bool(parts) and parts[-1].lower() in self.exclude and not any(
            p.startswith('.') or p.lower() in self.exclude for p in parts[:-1])

    def handle(self, event_type: str, src: str | bytes, dest: str | bytes, is_dir: bool) -> None:
        for raw in (src, dest):
            if not raw:
                continue
            rel = self._rel(raw)
            if rel is None:
                if event_type != 'modified' and self._excluded_top(raw):
                    self.log.push(None, others=True)   # 제외 폴더가 생기거나 지워짐 — '자료' 목록에 접힌 채 나온다 (D49)
                continue
            if is_dir:
                if event_type != 'modified':
                    self.log.push(None, True)
            elif doc_kind(rel):
                self.log.push(rel, event_type != 'modified')
            elif event_type != 'modified':
                self.log.push(None, others=True)   # 문서 외 파일이 생기거나 지워짐
            else:
                self.log.touch(rel)   # 문서 외 파일의 내용 수정 — 목록은 다시 읽지 않고 최근 변경만 (D50)

    # --- 폴링 대체 --------------------------------------------------------
    def _snapshot(self) -> tuple[dict[str, tuple[float, int]], dict[str, float]]:
        """(문서 → (수정 시각, 크기), 문서 외 파일과 제외 폴더 → 수정 시각)"""
        nodes = scan(self.root, self.exclude, with_info=False)
        others, _, _ = scan_others(self.root, self.exclude)
        return {n['path']: (n['mtime'], n['size']) for n in iter_files(nodes)}, _other_paths(others)

    def _poll_loop(self) -> None:
        prev, prev_others = self._snapshot()
        while not self._stop.wait(self.poll_interval):
            cur, cur_others = self._snapshot()
            for path in sorted((cur.keys() - prev.keys()) | (prev.keys() - cur.keys())):
                self.log.push(path, True)
            for path in sorted(k for k in cur.keys() & prev.keys() if cur[k] != prev[k]):
                self.log.push(path, False)
            if cur_others.keys() != prev_others.keys():
                self.log.push(None, others=True)
            for path in sorted(k for k in cur_others.keys() & prev_others.keys() if cur_others[k] != prev_others[k]):
                self.log.touch(path)
            prev, prev_others = cur, cur_others
