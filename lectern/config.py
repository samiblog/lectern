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
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        data = copy.deepcopy(DEFAULTS)
        try:
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return data
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if key in DEFAULTS:
                    data[key] = value
        return data

    def save(self) -> None:
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
