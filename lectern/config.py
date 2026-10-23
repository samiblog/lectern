"""사용자 설정 (%APPDATA%\\Lectern\\config.json).

뷰어가 디스크에 쓰는 파일은 이 설정 파일 하나뿐이다 (보기 전용 원칙).
사용자가 편집기로 고칠 수 있는 파일이므로(설정 창의 '설정 파일 열기'), 읽거나 저장하기 전에
파일이 밖에서 바뀌었는지 보고 다시 읽는다 — 손으로 고친 값을 앱이 들고 있던 옛 값으로 덮어쓰지 않도록 (D21).
"""
from __future__ import annotations

import copy
import json
import math
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .paths import config_dir

MAX_RECENT = 10
MAX_PROJECTS = 20     # 마지막 위치를 기억하는 프로젝트 수
MAX_POSITIONS = 100   # 프로젝트마다 스크롤 위치를 기억하는 문서 수
MAX_TABS = 10         # 한 번에 여는 프로젝트 탭 수 (최근 폴더 수와 같게)

CONFIG_VERSION = 2   # 설정 형식 판. 올리면 _upgrade 에 옛 판을 바꾸는 코드를 둔다

DEFAULTS: dict[str, Any] = {
    'version': CONFIG_VERSION,
    'recent': [],            # 최근 연 프로젝트 폴더 (최신순)
    'last_folder': None,     # 마지막으로 연 폴더 (tabs 가 없던 옛 설정이면 이 폴더를 연다)
    'tabs': [],              # 열어 둔 프로젝트 탭 (왼쪽부터). 다음 실행에 되살린다 (서버가 기록)
    'active_tab': 0,         # 선택돼 있던 탭의 순번
    'theme': 'auto',         # auto 또는 스타일 id (web/js/theme.js 의 THEMES). 고른 스타일이 다음 실행의 기본
    'font_scale': 1.0,       # 문서 글자 크기 배율 (툴바의 − 100% + 버튼, 0.8~2)
    'theme_groups': 'use',   # 스타일 목록을 묶는 방식: use(용도별) | mood(분위기별) | tone(밝기별) — 설정 창
    'show_titles': False,    # 트리에 파일 이름 대신 문서 제목 표시 (기본은 파일 이름, 마우스를 올리면 제목 — 트리의 '제목' 버튼)
    'sidebar_visible': True,
    'sidebar_width': None,   # 사이드바 폭(px, 200~480). None 이면 기본 폭
    'files_view': 'kind',    # 사이드바 파일 탭을 보는 방법: kind(종류별 — 문서 트리 위, 파일 목록 아래) | folder(폴더 구조 그대로 한 트리)
    'docs_visible': True,    # 종류별 보기의 '문서' 묶음을 펼쳐 둠 (머리줄을 눌러 접기)
    'others_visible': True,  # 종류별 보기의 '파일' 묶음을 펼쳐 둠
    'others_height': None,   # 종류별 보기의 '파일' 묶음 높이(px). None 이면 기본 (분리선을 끌어 바꾸고 두 번 누르면 기본)
    'code_visible': True,    # 종류별 보기의 '코드' 묶음을 펼쳐 둠
    'code_height': None,     # 종류별 보기의 '코드' 묶음 높이(px). None 이면 기본
    'toc_visible': True,
    'toc_hidden_parts': [],  # 목차에서 감춘 구성 요소 종류: table·figure·box·diagram·code·math (목차 머리의 종류 버튼)
    'math': True,            # $...$ 수식 렌더링
    'external_images': True, # 문서 속 http(s) 이미지 표시 (끄면 링크로만)
    'restore_last': True,    # 폴더를 열면 마지막에 보던 문서와 위치로
    'expand_first_level': True,  # 폴더를 열면 트리의 첫 단계 폴더를 펼쳐 둠
    'window': {'width': 1280, 'height': 860},
    'exclude_dirs': [],      # 기본 제외 폴더에 추가할 폴더 이름 (직접 편집)
    'html_exclude_dirs': [], # 이 이름의 폴더 안 html 은 문서로 보지 않음 (기본 src·public 등에 더함, 직접 편집)
    'editor': None,          # 코드 파일을 열 편집기 실행 파일 경로 (None이면 PATH의 code)
    'terminal_shell': None,  # 오른쪽 터미널의 셸 실행 파일 전체 경로 (None 이면 Windows PowerShell 5.1, 직접 편집 — 예: pwsh.exe)
    'terminal_width': None,  # 오른쪽 터미널 폭(px). None 이면 기본 (경계를 끌어 바꾸고 두 번 누르면 기본)
    'terminal_follow_style': True,  # 터미널 색을 문서 스타일에 맞춤 (끄면 늘 어둡게 — 설정 창)
    'projects': {},          # 프로젝트별 마지막 문서와 문서별 스크롤 위치 (서버가 기록)
}

# 프런트엔드(POST /api/config)에서 바꿀 수 있는 키. 나머지는 config.json 직접 편집.
# recent·last_folder·tabs·active_tab·projects 는 서버가 기록한다 (add_recent, set_tabs, remember_position).
CLIENT_KEYS = frozenset({'theme', 'theme_groups', 'font_scale', 'show_titles', 'sidebar_visible', 'sidebar_width', 'toc_visible', 'math',
                         'external_images', 'restore_last', 'expand_first_level', 'files_view', 'docs_visible', 'others_visible', 'others_height', 'code_visible', 'code_height',
                         'terminal_width',
                         'terminal_follow_style', 'toc_hidden_parts'})

# null 도 되는 키 (나머지는 기본값과 같은 형식이어야 한다)
NULLABLE = frozenset({'last_folder', 'editor', 'sidebar_width', 'others_height', 'code_height', 'terminal_shell', 'terminal_width'})
_EXAMPLE = {bool: 'true 또는 false', int: '숫자', float: '숫자', str: '"글자"', list: '["이름", ...] 목록', dict: '{ } 객체'}


def is_number(value: Any) -> bool:
    """유한한 숫자. JSON 의 1e400 은 inf 로 읽히는데, 그대로 내보내면 화면이 받는 JSON 이 깨진다 (Infinity)"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def value_ok(key: str, value: Any) -> bool:
    """설정 값의 형식이 맞는지. 손으로 고치는 파일이라 JSON 은 맞아도 형식이 틀릴 수 있다 (예: "exclude_dirs": "data")."""
    if value is None:
        return key in NULLABLE
    default = DEFAULTS[key]
    if key in ('sidebar_width', 'others_height', 'code_height', 'terminal_width'):
        return is_number(value)
    if key in ('last_folder', 'editor', 'terminal_shell'):
        return isinstance(value, str)
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):   # 1 처럼 정수로 적어도 된다
        return is_number(value)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    return isinstance(value, type(default))


def _upgrade(data: dict[str, Any]) -> None:
    """옛 판(version)의 설정을 지금 판으로 바꾼다. 파일에는 다음에 설정을 저장할 때 쓰인다 (그 전까지는 읽을 때마다 같은 값으로 바꾼다)."""
    if data['version'] < 2:
        # v0.7.1: 트리는 파일 이름이 기본이 됐다 (사용자 요청 — 마우스를 올리면 제목). 앱은 저장할 때 기본값도 함께 적으므로
        # 옛 파일의 show_titles: true 는 사용자가 고른 것인지 알 수 없다. 한 번 파일 이름으로 돌린다
        data['show_titles'] = False
    data['version'] = max(data['version'], CONFIG_VERSION)


def _expected(key: str) -> str:
    default = DEFAULTS[key]
    kind = (str if key in ('last_folder', 'editor', 'terminal_shell')
            else int if key in ('sidebar_width', 'others_height', 'code_height', 'terminal_width') else type(default))
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
        _upgrade(data)
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

    def set_tabs(self, roots: list[str], active: int = 0) -> None:
        """열어 둔 탭(왼쪽부터 폴더 경로)과 선택된 탭의 순번. 다음 실행에 이대로 되살린다."""
        roots = roots[:MAX_TABS]
        active = active if 0 <= active < len(roots) else 0

        def change(data: dict[str, Any]) -> bool:
            if data.get('tabs') == roots and data.get('active_tab') == active:
                return False
            data['tabs'] = roots
            data['active_tab'] = active
            return True
        self._update(change)

    def remember_position(self, root: str, doc: str, scroll: int) -> None:
        """프로젝트의 마지막 문서와 스크롤 위치. 문서별 스크롤 위치도 남긴다 (뒤로 가기·다시 열 때).
        최근 것이 뒤에 오도록 다시 넣고 오래된 것부터 버린다."""
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
        """{doc, scroll:{문서: 위치}}. 사용자가 고친 값도 있으므로 형식이 틀린 것은 버린다.
        창을 나누던 때(v0.6)의 기록에 남은 panes·active 는 읽지 않는다 — doc 이 그때 선택된 창의 문서다."""
        projects = self.get('projects')
        entry = projects.get(os.path.normcase(root)) if isinstance(projects, dict) else None
        if not isinstance(entry, dict):
            return {'doc': None, 'scroll': {}}
        doc = entry.get('doc') if isinstance(entry.get('doc'), str) else None
        scrolls = entry.get('scroll') if isinstance(entry.get('scroll'), dict) else {}
        return {'doc': doc, 'scroll': {k: v for k, v in scrolls.items() if is_number(v)}}

    def public(self) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            return copy.deepcopy(self.data)
