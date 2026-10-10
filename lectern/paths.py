"""리소스 폴더와 설정 폴더 위치.

PyInstaller로 묶으면 web/ 폴더는 sys._MEIPASS(onedir에서는 _internal) 아래에 풀린다.
개발 중에는 저장소 루트의 web/ 를 그대로 쓴다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = 'Lectern'


def resource_dir() -> Path:
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def web_dir() -> Path:
    return resource_dir() / 'web'


def config_dir() -> Path:
    """설정 폴더. 테스트에서는 LECTERN_CONFIG_DIR 로 바꿀 수 있다."""
    override = os.environ.get('LECTERN_CONFIG_DIR')
    if override:
        return Path(override)
    appdata = os.environ.get('APPDATA')
    if appdata:
        return Path(appdata) / APP_NAME
    return Path.home() / '.config' / 'lectern'
