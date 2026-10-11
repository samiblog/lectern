"""사용자 설정 (%APPDATA%\\Lectern\\config.json).

뷰어가 디스크에 쓰는 파일은 이 설정 파일 하나뿐이다 (보기 전용 원칙).
"""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

from .paths import config_dir

MAX_RECENT = 10

DEFAULTS: dict[str, Any] = {
    'version': 1,
    'recent': [],            # 최근 연 프로젝트 폴더 (최신순)
    'last_folder': None,     # 실행 인자가 없을 때 열 폴더
    'theme': 'auto',         # auto | default | report | dark
    'show_titles': True,     # 트리에 파일명 대신 문서 제목 표시
    'sidebar_visible': True,
    'toc_visible': True,
    'math': True,            # $...$ 수식 렌더링
    'external_images': True, # 문서 속 http(s) 이미지 표시 (끄면 링크로만)
    'window': {'width': 1280, 'height': 860},
    'exclude_dirs': [],      # 기본 제외 폴더에 추가할 폴더 이름 (직접 편집)
    'editor': None,          # 코드 파일을 열 편집기 실행 파일 경로 (None이면 PATH의 code)
}

# 프런트엔드(POST /api/config)에서 바꿀 수 있는 키. 나머지는 config.json 직접 편집.
CLIENT_KEYS = frozenset({'theme', 'show_titles', 'sidebar_visible', 'toc_visible', 'math', 'external_images', 'recent'})


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / 'config.json')
        self._lock = threading.Lock()
        # 파일이 있는데 읽지 못하면 그 이유. 이때는 기본값으로 돌고 저장하지 않는다 (손으로 고친 내용을 덮어쓰지 않도록)
        self.load_error: str | None = None
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        data = copy.deepcopy(DEFAULTS)
        try:
            text = self.path.read_text(encoding='utf-8-sig')  # 메모장·PowerShell 5.1 이 붙이는 BOM 허용
        except FileNotFoundError:
            return data
        except (OSError, ValueError) as exc:
            self.load_error = self._error_message(f'파일을 읽을 수 없음 ({exc})')
            return data
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            hint = ' 경로 안의 \\ 는 \\\\ 로 씁니다.' if 'escape' in exc.msg else ''
            self.load_error = self._error_message(f'{exc.lineno}행 {exc.colno}열: {exc.msg}', hint)
            return data
        if not isinstance(loaded, dict):
            self.load_error = self._error_message('맨 바깥이 { } 객체가 아님')
            return data
        for key, value in loaded.items():
            if key in DEFAULTS:
                data[key] = value
        return data

    def _error_message(self, detail: str, hint: str = '') -> str:
        return (f'설정 파일을 읽지 못해 기본 설정으로 실행합니다 ({detail}).{hint} '
                f'파일을 고칠 때까지 설정은 저장하지 않습니다: {self.path}')

    def save(self) -> None:
        if self.load_error:
            return
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix('.tmp')
                tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(tmp, self.path)
            except OSError:
                pass  # 설정 저장 실패는 보기 기능에 영향을 주지 않는다

    def get(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def update_client(self, patch: dict[str, Any]) -> None:
        changed = False
        for key, value in patch.items():
            if key in CLIENT_KEYS:
                self.data[key] = value
                changed = True
        if changed:
            self.save()

    def set_window(self, width: int, height: int) -> None:
        self.data['window'] = {'width': int(width), 'height': int(height)}
        self.save()

    def add_recent(self, folder: str) -> None:
        norm = os.path.normcase(folder)
        recent = [p for p in self.data.get('recent') or [] if os.path.normcase(p) != norm]
        recent.insert(0, folder)
        self.data['recent'] = recent[:MAX_RECENT]
        self.data['last_folder'] = folder
        self.save()

    def public(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)
