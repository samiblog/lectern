"""앱 전역 상태: 열린 프로젝트 폴더, 변경 감시, 설정."""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .changes import ChangeLog, Watcher
from .config import Config
from .scanner import DEFAULT_EXCLUDE_DIRS, DEFAULT_HTML_EXCLUDE_DIRS, scan


class AppState:
    def __init__(self, config: Config, mode: str = 'app'):
        self.config = config
        self.mode = mode                 # 'app' (pywebview 창) | 'browser' (개발용)
        self.token: str | None = None    # pywebview 세션 토큰. None 이면 검사 안 함
        self.root: Path | None = None
        self.log = ChangeLog()
        self._watcher: Watcher | None = None
        self._lock = threading.Lock()
        # 스캔 결과. 변경 기록(seq)이 그대로면 다시 쓴다 — 문서가 수천 개여도 트리·개요·검색이 폴더를 매번 훑지 않게
        self._scans: dict[tuple, tuple[int, list]] = {}

    @property
    def exclude(self) -> frozenset[str]:
        extra = self.config.get('exclude_dirs') or []
        return DEFAULT_EXCLUDE_DIRS | frozenset(str(x).lower() for x in extra)

    @property
    def html_exclude(self) -> frozenset[str]:
        extra = self.config.get('html_exclude_dirs') or []
        return DEFAULT_HTML_EXCLUDE_DIRS | frozenset(str(x).lower() for x in extra)

    def scan(self, rel: str = '', with_info: bool = True, fresh: bool = False) -> list:
        """열린 폴더의 트리 (설정의 제외 폴더를 반영). 마지막 스캔 뒤로 파일 변경이 없으면 그 결과를 그대로 쓴다.

        감시가 놓칠 수 있는 변경(숨김 속성 바꾸기 등)은 fresh=True(화면의 F5)로 새로 훑는다. 돌려준 목록은 고치지 않는다.
        """
        assert self.root is not None
        key = (str(self.root), rel, with_info, self.exclude, self.html_exclude)
        seq = self.log.seq
        hit = self._scans.get(key)
        if hit and hit[0] == seq and not fresh:
            return hit[1]
        nodes = scan(self.root, self.exclude, rel=rel, with_info=with_info, html_exclude=self.html_exclude)
        if len(self._scans) > 64:
            self._scans.clear()
        self._scans[key] = (seq, nodes)
        return nodes

    def open(self, folder: str | os.PathLike) -> Path:
        path = Path(folder).expanduser().resolve()
        if not path.is_dir():
            raise NotADirectoryError(f'폴더가 아닙니다: {path}')
        with self._lock:
            if self._watcher:
                self._watcher.stop()
            self.root = path
            self._watcher = Watcher(path, self.log, self.exclude)
            self._watcher.start()
            self.log.push(None, True)
        self.config.add_recent(str(path))
        return path

    def close(self) -> None:
        with self._lock:
            if self._watcher:
                self._watcher.stop()
                self._watcher = None

    @property
    def watch_backend(self) -> str:
        return self._watcher.backend if self._watcher else 'none'

    def info(self) -> dict[str, Any]:
        root = self.root
        return {
            'root': str(root) if root else None,
            'name': (root.name or str(root)) if root else '',
            'seq': self.log.seq,
            'mode': self.mode,
            'sep': os.sep,
            'watch': self.watch_backend,
            'version': __version__,
            'config_error': self.config.load_error,
            'position': self.config.position(str(root)) if root else None,   # 마지막 문서와 스크롤 위치
        }
