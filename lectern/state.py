"""앱 전역 상태: 열린 프로젝트들(탭), 프로젝트마다 변경 감시, 설정.

프로젝트(폴더) 하나가 화면의 탭 하나다 (D34). 서버가 열린 순서와 선택된 탭을 들고 있고, 화면은 /api/state 로 맞춘다.
프로젝트마다 실행 동안만 쓰는 무작위 id 를 붙여 주소(/doc/<id>/…, ?p=<id>)에 쓴다 — 폴더 경로가 주소에 드러나지 않고,
문서가 다른 탭 프로젝트의 주소를 짐작해 그 파일을 불러올 수 없게.
"""
from __future__ import annotations

import os
import secrets
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .changes import ChangeLog, Watcher
from .config import MAX_TABS, Config
from .scanner import DEFAULT_EXCLUDE_DIRS, DEFAULT_HTML_EXCLUDE_DIRS, scan, scan_others
from .search import TextCache
from .terminal import Terminals


class TooManyTabs(Exception):
    pass


class Project:
    """열린 프로젝트 폴더 하나 (탭 하나): 변경 기록, 감시, 스캔 캐시."""

    def __init__(self, pid: str, root: Path, config: Config):
        self.id = pid
        self.root = root
        self.config = config
        self.log = ChangeLog()
        self._watcher: Watcher | None = None
        # 스캔 결과. 변경 기록(seq)이 그대로면 다시 쓴다 — 문서가 수천 개여도 트리·개요·검색이 폴더를 매번 훑지 않게
        self._scans: dict[tuple, tuple[int, list]] = {}
        self.texts = TextCache()   # 전체 검색이 읽은 글 (수정 시각·크기가 그대로면 다시 쓴다)

    @property
    def name(self) -> str:
        return self.root.name or str(self.root)

    @property
    def exclude(self) -> frozenset[str]:
        extra = self.config.get('exclude_dirs') or []
        return DEFAULT_EXCLUDE_DIRS | frozenset(str(x).lower() for x in extra)

    @property
    def html_exclude(self) -> frozenset[str]:
        extra = self.config.get('html_exclude_dirs') or []
        return DEFAULT_HTML_EXCLUDE_DIRS | frozenset(str(x).lower() for x in extra)

    def scan(self, rel: str = '', with_info: bool = True, fresh: bool = False) -> list:
        """폴더의 트리 (설정의 제외 폴더를 반영). 마지막 스캔 뒤로 파일 변경이 없으면 그 결과를 그대로 쓴다.

        감시가 놓칠 수 있는 변경(숨김 속성 바꾸기 등)은 fresh=True(화면의 F5)로 새로 훑는다. 돌려준 목록은 고치지 않는다.
        """
        key = (rel, with_info, self.exclude, self.html_exclude)
        seq = self.log.seq
        hit = self._scans.get(key)
        if hit and hit[0] == seq and not fresh:
            return hit[1]
        nodes = scan(self.root, self.exclude, rel=rel, with_info=with_info, html_exclude=self.html_exclude)
        if len(self._scans) > 64:
            self._scans.clear()
        self._scans[key] = (seq, nodes)
        return nodes

    def scan_others(self, fresh: bool = False) -> tuple[list, int, bool]:
        """문서 외 파일의 트리 (scanner.scan_others). 그 뒤로 파일이 생기거나 지워지지 않았으면(others_seq) 마지막 결과를 쓴다 —
        문서 내용만 바뀔 때는 다시 훑지 않는다. 돌려준 목록은 고치지 않는다."""
        key = ('others', self.exclude, self.html_exclude)
        seq = self.log.others_seq
        hit = self._scans.get(key)
        if hit and hit[0] == seq and not fresh:
            return hit[1]
        result = scan_others(self.root, self.exclude, self.html_exclude)
        self._scans[key] = (seq, result)
        return result

    def start(self) -> None:
        self._watcher = Watcher(self.root, self.log, self.exclude)
        self._watcher.start()
        self.log.push(None, True)

    def stop(self) -> None:
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    @property
    def watch_backend(self) -> str:
        return self._watcher.backend if self._watcher else 'none'

    def info(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'root': str(self.root),
            'name': self.name,
            'seq': self.log.seq,
            'watch': self.watch_backend,
            'position': self.config.position(str(self.root)),   # 마지막 문서와 스크롤 위치
        }


class AppState:
    def __init__(self, config: Config, mode: str = 'app'):
        self.config = config
        self.mode = mode                 # 'app' (pywebview 창) | 'browser' (개발용)
        self.token: str | None = None    # pywebview 세션 토큰. None 이면 검사 안 함
        self.projects: dict[str, Project] = {}   # 열린 순서 = 탭 순서
        self.active: str | None = None           # 선택된 탭 (다음 실행에 되살리고, 폴더 대화상자가 여기서 시작)
        # 탭 목록이 바뀔 때마다 늘어난다. 다른 실행이 넘긴 폴더로 탭이 생기면 화면이 /api/changes 로 알아챈다
        self.tabs_seq = 0
        self.notices: list[dict[str, Any]] = []   # 화면에 알릴 말 [{id, text}] — 화면이 처음 보는 id 만 한 번 보인다
        # 오른쪽 터미널 (D38): 탭마다 셸. 터미널 API 는 페이지에 실어 주는 실행마다 새 비밀값(X-Term)도 확인한다
        self.terminals = Terminals()
        self.term_secret = secrets.token_hex(16)
        self._lock = threading.RLock()

    def get(self, pid: Any) -> Project | None:
        return self.projects.get(pid) if isinstance(pid, str) else None

    @property
    def active_project(self) -> Project | None:
        return self.get(self.active)

    def _find(self, path: Path) -> Project | None:
        key = os.path.normcase(str(path))
        return next((p for p in self.projects.values() if os.path.normcase(str(p.root)) == key), None)

    def open(self, folder: str | os.PathLike, remember: bool = True) -> Project:
        """폴더를 탭으로 연다 (이미 열려 있으면 그 탭). 연 탭이 선택된 탭이 된다.

        remember: 최근 폴더와 열린 탭 목록을 설정에 기록한다 (시작할 때 되살리는 중에는 끈다).
        """
        path = Path(folder).expanduser().resolve()
        if not path.is_dir():
            raise NotADirectoryError(f'폴더가 아닙니다: {path}')
        with self._lock:
            project = self._find(path)
            if project is None:
                if len(self.projects) >= MAX_TABS:
                    raise TooManyTabs(f'탭은 {MAX_TABS}개까지 열 수 있습니다. 안 쓰는 탭을 닫고 다시 여세요')
                pid = secrets.token_hex(4)
                while pid in self.projects:
                    pid = secrets.token_hex(4)
                project = Project(pid, path, self.config)
                project.start()
                self.projects[pid] = project
            self.active = project.id
            self.tabs_seq += 1   # 이미 열린 탭을 고른 것도 — 다른 실행이 넘긴 폴더면 화면이 그 탭으로 가야 한다
        if remember:
            self.config.add_recent(str(path))
            self.remember_tabs()
        return project

    def restore(self, folders: list[str], active: Any = 0) -> None:
        """지난 실행의 탭들을 연다. 없어진 폴더는 건너뛴다. active: 선택돼 있던 탭의 순번."""
        opened: list[Project | None] = []
        for folder in folders[:MAX_TABS]:
            try:
                opened.append(self.open(folder, remember=False) if Path(folder).is_dir() else None)
            except (OSError, NotADirectoryError, TooManyTabs):
                opened.append(None)
        index = active if isinstance(active, int) and not isinstance(active, bool) else 0
        chosen = opened[index] if 0 <= index < len(opened) else None
        if chosen is None:
            chosen = next((p for p in opened if p), None)
        self.active = chosen.id if chosen else None

    def close_tab(self, pid: str) -> bool:
        """탭을 닫는다 (감시를 멈춘다). 선택된 탭이었으면 그 오른쪽(없으면 왼쪽) 탭이 선택된다."""
        with self._lock:
            project = self.projects.get(pid)
            if project is None:
                return False
            ids = list(self.projects)
            i = ids.index(pid)
            del self.projects[pid]
            if self.active == pid:
                rest = ids[:i] + ids[i + 1:]
                self.active = rest[min(i, len(rest) - 1)] if rest else None
            self.tabs_seq += 1
        project.stop()
        self.terminals.close_project(pid)   # 그 탭의 셸과 셸에서 띄운 프로그램도
        self.remember_tabs()
        return True

    def activate(self, pid: str) -> bool:
        if pid not in self.projects:
            return False
        if self.active != pid:
            self.active = pid
            self.remember_tabs()
        return True

    def notify(self, text: str) -> None:
        """화면에 알린다 (실행 인자나 다른 실행이 넘긴 폴더를 열지 못했을 때 등). 화면은 tabs_seq 가 바뀐 것을 보고 /api/state 를 다시 읽는다."""
        with self._lock:
            last = self.notices[-1]['id'] if self.notices else 0
            self.notices = (self.notices + [{'id': last + 1, 'text': text}])[-5:]
            self.tabs_seq += 1

    def remember_tabs(self) -> None:
        with self._lock:
            roots = [str(p.root) for p in self.projects.values()]
            ids = list(self.projects)
            active = ids.index(self.active) if self.active in ids else 0
        self.config.set_tabs(roots, active)

    def close(self) -> None:
        """앱을 끝낼 때: 모든 감시를 멈춘다 (열린 탭 목록은 다음 실행을 위해 그대로 둔다)."""
        with self._lock:
            projects = list(self.projects.values())
        for project in projects:
            project.stop()
        self.terminals.close_all()

    def info(self) -> dict[str, Any]:
        with self._lock:
            projects = list(self.projects.values())
            active = self.active
            tabs_seq = self.tabs_seq
            notices = list(self.notices)
        return {
            'projects': [p.info() for p in projects],
            'active': active,
            'tabs_seq': tabs_seq,
            'max_tabs': MAX_TABS,
            'mode': self.mode,
            'sep': os.sep,
            'version': __version__,
            'config_error': self.config.load_error,
            'notices': notices,
        }
