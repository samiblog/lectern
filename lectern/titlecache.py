"""문서 제목을 기억해 둔다 (D140) — 프로젝트를 열 때 문서마다 파일을 열지 않게.

트리는 문서의 제목을 보여 주려고 문서마다 앞부분을 읽는다 (docinfo.doc_info). 한 번 읽은 파일은 빠르지만 처음 읽는 파일은
보안 프로그램의 검사로 하나에 0.01~0.1초가 걸려, 문서가 수백 개인 프로젝트는 여는 데 수 초~수십 초가 걸렸다 (2026-11-15 측정).
그래서 제목을 설정 폴더의 `cache\\titles-<프로젝트>.json` 에 적어 두고, 파일의 수정 시각과 크기가 같으면 파일을 열지 않는다.

- 적는 것은 제목과 'Lectern 슬라이드인지'뿐이다. 본문과 요약은 적지 않는다 (요약은 폴더 개요가 그때 읽는다).
- 프로젝트 폴더에는 아무것도 쓰지 않는다. 설정 폴더(%APPDATA%\\Lectern)에만, 프로젝트마다 파일 하나.
- 기억은 없어져도 된다 — 읽지 못하거나 쓰지 못하면 조용히 넘어가고 파일을 읽는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

VERSION = 1
MAX_FILES = 60          # 설정 폴더에 두는 기억 파일 수 — 넘으면 오래 안 쓴 것부터 지운다
MAX_DOCS = 50_000       # 한 프로젝트에서 기억하는 문서 수
Info = tuple[str | None, bool]   # (제목, Lectern 슬라이드인지)


def cache_path(config_dir: Path, root: Path) -> Path:
    key = hashlib.sha1(os.path.normcase(str(root)).encode('utf-8')).hexdigest()[:16]
    return Path(config_dir) / 'cache' / f'titles-{key}.json'


class TitleCache:
    """프로젝트 하나의 제목 기억. 경로는 프로젝트 기준 '/' 구분 상대경로"""

    def __init__(self, root: Path, config_dir: Path | None):
        self.root = root
        self.file = cache_path(config_dir, root) if config_dir else None
        self._docs: dict[str, tuple[int, int, str | None, bool]] = {}
        self._dirty = False
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if not self.file:
            return
        try:
            data = json.loads(self.file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict) or data.get('version') != VERSION or data.get('root') != str(self.root):
            return   # 다른 판이거나 (해시가 겹친) 다른 프로젝트
        docs = data.get('docs')
        if not isinstance(docs, dict):
            return
        for rel, row in docs.items():
            if (isinstance(rel, str) and isinstance(row, list) and len(row) == 4 and isinstance(row[0], int) and isinstance(row[1], int)
                    and (row[2] is None or isinstance(row[2], str)) and isinstance(row[3], bool)):
                self._docs[rel] = (row[0], row[1], row[2], row[3])

    def get(self, rel: str, st: Any) -> Info | None:
        """기억한 제목 — 수정 시각과 크기가 같을 때만. 없으면 None"""
        row = self._docs.get(rel)
        if row and row[0] == st.st_mtime_ns and row[1] == st.st_size:
            return row[2], row[3]
        return None

    def put(self, rel: str, st: Any, info: Info) -> None:
        row = (st.st_mtime_ns, st.st_size, info[0], bool(info[1]))
        with self._lock:
            if self._docs.get(rel) != row:
                self._docs[rel] = row
                self._dirty = True

    def keep(self, rels: set[str]) -> None:
        """프로젝트 전체를 훑은 뒤: 없어진 문서의 기억을 버린다"""
        with self._lock:
            gone = [r for r in self._docs if r not in rels]
            for r in gone:
                del self._docs[r]
            if gone:
                self._dirty = True

    def save(self) -> bool:
        """바뀌었으면 적는다. 적었으면 True — 쓰지 못해도 조용히 넘어간다 (기억일 뿐이다)"""
        with self._lock:
            if not self.file or not self._dirty:
                return False
            docs = dict(list(self._docs.items())[:MAX_DOCS])
            self._dirty = False
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.file.with_suffix('.tmp')
            tmp.write_text(json.dumps({'version': VERSION, 'root': str(self.root), 'docs': docs}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            os.replace(tmp, self.file)
            _prune(self.file.parent)
            return True
        except OSError:
            return False


def _prune(folder: Path) -> None:
    """기억 파일이 너무 많으면 오래 안 쓴 것부터 지운다 (설정 폴더의 우리 파일만)"""
    try:
        files = sorted(folder.glob('titles-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[MAX_FILES:]:
            old.unlink(missing_ok=True)
    except OSError:
        pass
