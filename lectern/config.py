"""사용자 설정 (%APPDATA%\\Lectern\\config.json).

뷰어가 디스크에 쓰는 파일은 이 설정 파일 하나뿐이다 (보기 전용 원칙).
사용자가 편집기로 고칠 수 있는 파일이므로(설정 창의 '설정 파일 열기'), 읽거나 저장하기 전에
파일이 밖에서 바뀌었는지 보고 다시 읽는다 — 손으로 고친 값을 앱이 들고 있던 옛 값으로 덮어쓰지 않도록 (D21).
"""
from __future__ import annotations

import copy
import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import config_dir

MAX_RECENT = 10
MAX_PROJECTS = 20     # 마지막 위치를 기억하는 프로젝트 수
MAX_POSITIONS = 100   # 프로젝트마다 스크롤 위치를 기억하는 문서 수

DEFAULTS: dict[str, Any] = {
    'version': 1,
    'recent': [],            # 최근 연 프로젝트 폴더 (최신순)
    'last_folder': None,     # 실행 인자가 없을 때 열 폴더
    'theme': 'auto',         # auto 또는 스타일 id (web/js/theme.js 의 THEMES). 고른 스타일이 다음 실행의 기본
    'show_titles': True,     # 트리에 파일명 대신 문서 제목 표시
    'sidebar_visible': True,
    'sidebar_width': None,   # 사이드바 폭(px, 200~480). None 이면 기본 폭
    'toc_visible': True,
    'math': True,            # $...$ 수식 렌더링
    'external_images': True, # 문서 속 http(s) 이미지 표시 (끄면 링크로만)
    'restore_last': True,    # 폴더를 열면 마지막에 보던 문서와 위치로
    'expand_first_level': True,  # 폴더를 열면 트리의 첫 단계 폴더를 펼쳐 둠
    'window': {'width': 1280, 'height': 860},
    'exclude_dirs': [],      # 기본 제외 폴더에 추가할 폴더 이름 (직접 편집)
    'html_exclude_dirs': [], # 이 이름의 폴더 안 html 은 문서로 보지 않음 (기본 src·public 등에 더함, 직접 편집)
    'editor': None,          # 코드 파일을 열 편집기 실행 파일 경로 (None이면 PATH의 code)
    'projects': {},          # 프로젝트별 마지막 문서와 문서별 스크롤 위치 (서버가 기록)
}

# 프런트엔드(POST /api/config)에서 바꿀 수 있는 키. 나머지는 config.json 직접 편집.
# recent·last_folder·projects 는 서버가 기록한다 (add_recent, remember_position).
CLIENT_KEYS = frozenset({'theme', 'show_titles', 'sidebar_visible', 'sidebar_width', 'toc_visible', 'math',
                         'external_images', 'restore_last', 'expand_first_level'})

# null 도 되는 키 (나머지는 기본값과 같은 형식이어야 한다)
NULLABLE = frozenset({'last_folder', 'editor', 'sidebar_width'})
_EXAMPLE = {bool: 'true 또는 false', int: '숫자', float: '숫자', str: '"글자"', list: '["이름", ...] 목록', dict: '{ } 객체'}


def value_ok(key: str, value: Any) -> bool:
    """설정 값의 형식이 맞는지. 손으로 고치는 파일이라 JSON 은 맞아도 형식이 틀릴 수 있다 (예: "exclude_dirs": "data")."""
    if value is None:
        return key in NULLABLE
    default = DEFAULTS[key]
    if key == 'sidebar_width':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if key in ('last_folder', 'editor'):
        return isinstance(value, str)
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    return isinstance(value, type(default))


def _expected(key: str) -> str:
    default = DEFAULTS[key]
    kind = str if key in ('last_folder', 'editor') else int if key == 'sidebar_width' else type(default)
    return _EXAMPLE.get(kind, '맞는 형식')


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / 'config.json')
        self._lock = threading.RLock()
        self._disk: tuple[int, int] | None = None   # 마지막으로 읽거나 쓴 파일의 (수정 시각, 크기)
        # 파일이 있는데 읽지 못하면 그 이유. 이때는 기본값으로 돌고, 파일이 고쳐질 때까지 저장하지 않는다
        self.load_error: str | None = None
        data, self.load_error = self._read()
        self.data = data or copy.deepcopy(DEFAULTS)

    def _signature(self) -> tuple[int, int] | None:
        try:
            st = self.path.stat()
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size

    def _read(self) -> tuple[dict[str, Any] | None, str | None]:
        """(설정, 오류). 파일이 없으면 기본값. 읽지 못하면 (None, 이유)."""
        self._disk = self._signature()
        data = copy.deepcopy(DEFAULTS)
        try:
            text = self.path.read_text(encoding='utf-8-sig')  # 메모장·PowerShell 5.1 이 붙이는 BOM 허용
        except FileNotFoundError:
            return data, None
        except (OSError, ValueError) as exc:
            return None, self._error_message(f'파일을 읽을 수 없음 ({exc})')
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            hint = ' 경로 안의 \\ 는 \\\\ 로 씁니다.' if 'escape' in exc.msg else ''
            return None, self._error_message(f'{exc.lineno}행 {exc.colno}열: {exc.msg}', hint)
        if not isinstance(loaded, dict):
            return None, self._error_message('맨 바깥이 { } 객체가 아님')
        wrong = []
        for key, value in loaded.items():
            if key not in DEFAULTS:
                continue
            if value_ok(key, value):
                data[key] = value
            else:
                wrong.append(f'{key} 는 {_expected(key)}')
        if wrong:
            # 맞는 값은 쓰고 틀린 값만 기본값으로. 파일을 고칠 때까지 저장하지 않는다 (손으로 쓴 값을 덮어쓰지 않게, D21)
            return data, (f'설정 파일의 값 형식이 틀려 그 값은 기본값으로 실행합니다 ({"; ".join(wrong)}). '
                          f'파일을 고칠 때까지 설정은 저장하지 않습니다: {self.path}')
        return data, None

    def _error_message(self, detail: str, hint: str = '') -> str:
        return (f'설정 파일을 읽지 못해 기본 설정으로 실행합니다 ({detail}).{hint} '
                f'파일을 고칠 때까지 설정은 저장하지 않습니다: {self.path}')

    def _refresh(self) -> None:
        """파일이 밖에서 바뀌었으면 다시 읽는다. 고친 파일이 깨졌으면 들고 있던 값으로 돌고 저장을 멈춘다."""
        if self._signature() == self._disk:
            return
        data, error = self._read()
        self.load_error = error
        if data is not None:
            self.data = data

    def save(self) -> None:
        with self._lock:
            if self.load_error:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix('.tmp')
                tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(tmp, self.path)
                self._disk = self._signature()
            except OSError:
                pass  # 설정 저장 실패는 보기 기능에 영향을 주지 않는다

    def _update(self, change: Callable[[dict[str, Any]], bool | None]) -> None:
        """밖에서 고친 값을 먼저 읽어 들이고, 바꾼 뒤 저장한다. change 가 False 를 돌려주면 저장하지 않는다."""
        with self._lock:
            self._refresh()
            if change(self.data) is not False:
                self.save()

    def get(self, key: str) -> Any:
        with self._lock:
            self._refresh()
            return self.data.get(key, DEFAULTS.get(key))

    def update_client(self, patch: dict[str, Any]) -> None:
        def change(data: dict[str, Any]) -> bool:
            keys = [k for k in patch if k in CLIENT_KEYS and value_ok(k, patch[k])]
            for key in keys:
                data[key] = patch[key]
            return bool(keys)
        self._update(change)

    def set_window(self, width: int, height: int) -> None:
        self._update(lambda data: data.update(window={'width': int(width), 'height': int(height)}))

    def add_recent(self, folder: str) -> None:
        def change(data: dict[str, Any]) -> None:
            norm = os.path.normcase(folder)
            recent = [p for p in data.get('recent') or [] if os.path.normcase(p) != norm]
            data['recent'] = ([folder] + recent)[:MAX_RECENT]
            data['last_folder'] = folder
        self._update(change)

    def remember_position(self, root: str, doc: str, scroll: int) -> None:
        """프로젝트의 마지막 문서와 그 문서의 스크롤 위치. 최근 것이 뒤에 오도록 다시 넣고 오래된 것부터 버린다."""
        def change(data: dict[str, Any]) -> None:
            projects = data.get('projects') if isinstance(data.get('projects'), dict) else {}
            key = os.path.normcase(root)
            entry = projects.pop(key, None)
            scrolls = entry.get('scroll') if isinstance(entry, dict) and isinstance(entry.get('scroll'), dict) else {}
            scrolls.pop(doc, None)
            scrolls[doc] = max(0, int(scroll))
            projects[key] = {'doc': doc, 'scroll': dict(list(scrolls.items())[-MAX_POSITIONS:])}
            data['projects'] = dict(list(projects.items())[-MAX_PROJECTS:])
        self._update(change)

    def position(self, root: str) -> dict[str, Any]:
        projects = self.get('projects')
        entry = projects.get(os.path.normcase(root)) if isinstance(projects, dict) else None
        if not isinstance(entry, dict):
            return {'doc': None, 'scroll': {}}
        return {'doc': entry.get('doc'), 'scroll': entry.get('scroll') if isinstance(entry.get('scroll'), dict) else {}}

    def public(self) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            return copy.deepcopy(self.data)
