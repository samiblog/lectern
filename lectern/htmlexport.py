"""Lectern 슬라이드를 impress.js 발표 html 로 전환한다 (D129) — 사용자가 'html 로 전환' 을 누를 때만.

html 은 화면(web/js/impressexport.js)이 슬라이드 창에서 그린 장을 모아 짓는다. 서버는 문서 옆에 새 파일 하나를 쓰기만 한다.
있는 파일은 덮어쓰지 않고 `보고서 2.html` 처럼 새 이름을 쓴다 (pptx 로 전환과 같다 — D102).

브라우저로 열기는 이번 실행에 여기서 만든 파일만 한다. .html 은 기본 앱으로 여는 형식이 아니다 (원칙 5 — 문서 속 링크의 html 은
편집기로). 이 파일은 앱이 쓴 내용이고, 파일의 CSP 가 앱이 넣은 두 스크립트(impress.js 와 시작 줄)만 돌게 한다.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

from . import osutil, paths
from .i18n import t

MAX_BYTES = 300 * 1024 * 1024   # 사진이 많은 발표도 — 그림은 파일 안에 들어간다
MARK = '<meta name="generator" content="Lectern'   # 화면이 짓는 파일의 머리. 다른 글을 받아 쓰지 않게
_made: set[str] = set()
_lock = threading.Lock()


class ExportError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_deck(md: Path) -> bool:
    """맨 앞 설정에 marp: true 가 있는 md — Lectern 슬라이드"""
    if md.suffix.lower() != '.md':
        return False
    try:
        with md.open(encoding='utf-8', errors='replace') as f:
            head = f.read(4000)
    except OSError:
        return False
    front = re.match(r'﻿?---\n(.*?)\n---', head.replace('\r\n', '\n'), re.S)
    return bool(front and re.search(r'^marp:\s*true\s*(#.*)?$', front[1], re.M))


def free_path(md: Path) -> Path:
    """문서 옆의 새 html 경로. 있으면 번호를 붙인다."""
    for n in range(1, 1000):
        path = md.with_name(f"{md.stem}{f' {n}' if n > 1 else ''}.html")
        if not path.exists():
            return path
    raise ExportError(409, t('같은 이름의 html 이 너무 많습니다 — 정리한 뒤 다시 하세요'))


def write(md: Path, text: Any) -> Path:
    """md 옆에 새 html 을 쓴다. 덮어쓰지 않는다 — 그사이 같은 이름이 생기면 다음 번호로. 안 되면 ExportError"""
    if not isinstance(text, str) or not text.startswith('<!doctype html>') or MARK not in text[:2000]:
        raise ExportError(400, t('전환한 html 이 아닙니다 — 슬라이드 창에서 다시 전환하세요'))
    if not is_deck(md):
        raise ExportError(400, t('Lectern 슬라이드가 아닙니다 — 맨 앞 설정에 marp: true 가 있어야 합니다'))
    if paths.is_protected(md):
        raise ExportError(403, t('Lectern 프로그램 폴더 안에는 만들지 않습니다 — 그 폴더를 다른 곳에 복사해 여세요'))
    data = text.encode('utf-8')
    if len(data) > MAX_BYTES:
        raise ExportError(413, t('html 이 300MB 를 넘습니다 — 큰 그림을 줄인 뒤 다시 하세요'))
    try:
        for n in range(1, 1000):
            path = md.with_name(f"{md.stem}{f' {n}' if n > 1 else ''}.html")
            try:
                with open(path, 'xb') as f:   # 있으면 실패한다 — 덮어쓰지 않는다
                    f.write(data)
            except FileExistsError:
                continue
            with _lock:
                _made.add(_key(path))
            return path
    except OSError as exc:
        raise ExportError(500, t('html 을 저장하지 못했습니다: {error}', error=exc.strerror or str(exc))) from exc
    raise ExportError(409, t('같은 이름의 html 이 너무 많습니다 — 정리한 뒤 다시 하세요'))


def made(path: Path) -> bool:
    with _lock:
        return _key(path) in _made


def open_made(path: Path) -> None:
    """이번 실행에 만든 html 을 기본 브라우저로 연다. 다른 html 은 열지 않는다"""
    if not made(path) or not path.is_file():
        raise ExportError(403, t('Lectern 이 이번에 만든 html 만 브라우저로 엽니다 — 탐색기에서 여세요'))
    osutil.open_default(path)
