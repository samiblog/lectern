"""Lectern 슬라이드를 pptx 로 전환한다 (D102) — 사용자가 'pptx 로 전환' 을 누를 때만.

pptx 스타일은 프로젝트가 아니라 Lectern 전체가 함께 쓴다 (설정 폴더의 pptx-styles). 이 폴더는 읽기만 한다.
전환은 스킬의 build_pptx.py 를 그대로 쓴다. 정해진 프로그램을 인자로만 부르고 셸을 거치지 않는다.
결과는 문서 옆의 새 pptx 파일 하나이고, 있는 파일은 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from .i18n import t
from .paths import config_dir, program_dir, skills_dir

TIMEOUT = 300
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)   # 콘솔 프로그램이라 창이 번쩍이지 않게
_COLOR = re.compile(r'<a:(dk2|lt2|accent1|accent2|accent3|accent4)>\s*<a:(?:srgbClr val|sysClr[^>]*lastClr)="([0-9A-Fa-f]{6})"')


class ExportError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def styles_dir() -> Path:
    """pptx 스타일 보관소 (설정 폴더의 pptx-styles)"""
    return config_dir() / 'pptx-styles'


def _colors(path: Path) -> list[str]:
    """스타일의 대표색 — 목록의 색 띠. 읽지 못하면 빈 목록."""
    try:
        with zipfile.ZipFile(path) as z:
            theme = next((n for n in sorted(z.namelist()) if re.fullmatch(r'ppt/theme/theme\d+\.xml', n)), None)
            text = z.read(theme).decode('utf-8', 'replace') if theme else ''
    except (OSError, zipfile.BadZipFile, KeyError):
        return []
    found = dict(_COLOR.findall(text))
    return [f'#{found[k]}' for k in ('dk2', 'accent1', 'accent2', 'accent3', 'accent4') if k in found]


def list_styles() -> list[dict[str, Any]]:
    folder = styles_dir()
    if not folder.is_dir():
        return []
    items = (p for p in sorted(folder.glob('*.pptx'), key=lambda p: p.name.lower()) if p.is_file() and not p.is_symlink() and not p.name.startswith('~$'))
    return [{'name': p.stem, 'colors': _colors(p), 'previews': [f'{p.stem}-{n}.png' for n in (1, 2) if (folder / f'{p.stem}-{n}.png').is_file()]} for p in items]


def preview_path(file: str) -> Path | None:
    """보관소의 미리보기 그림 (이름-1.png). 보관소 안의 파일만 준다."""
    if not re.fullmatch(r'[^/\\:]+-[12]\.png', file):
        return None
    path = styles_dir() / file
    return path if path.is_file() and not path.is_symlink() else None


def style_path(name: Any) -> Path | None:
    """이름의 스타일 파일. 보관소 안의 파일만 준다."""
    if not isinstance(name, str) or not name or any(c in name for c in '/\\:') or name in ('.', '..'):
        return None
    path = styles_dir() / f'{name}.pptx'
    return path if path.is_file() and not path.is_symlink() else None


def doc_memory(md: Path) -> dict[str, Any]:
    """문서가 기억하는 스타일: {style: 맨 앞 설정의 pptxStyle, group: 템플릿 묶음(같은 이름의 스타일이 짝), original: pptx 에서 옮겨 와 원본 사본이 있는가}"""
    head = md.read_text(encoding='utf-8', errors='replace')[:4000]
    front = re.match(r'﻿?---\n(.*?)\n---', head.replace('\r\n', '\n'), re.S)
    def key(name: str) -> str:
        m = re.search(rf'^{name}:\s*(.+?)\s*$', front[1], re.M) if front else None
        return m[1].strip('\'"') if m else ''

    record = md.with_name(f'{md.stem}-변환기록.json')   # i18n-ok (스킬이 쓰는 파일 이름)
    original = False
    if record.is_file():
        try:
            snapshot = json.loads(record.read_text(encoding='utf-8')).get('snapshot')
            original = bool(snapshot) and (md.parent / snapshot).is_file()
        except (OSError, ValueError):
            pass
    return {'style': key('pptxStyle'), 'group': key('templates'), 'original': original}


def free_path(md: Path) -> Path:
    """문서 옆의 새 pptx 경로. 있으면 번호를 붙인다."""
    for n in range(1, 1000):
        path = md.with_name(f"{md.stem}{f' {n}' if n > 1 else ''}.pptx")
        if not path.exists():
            return path
    raise ExportError(409, t('같은 이름의 pptx 가 너무 많습니다 — 정리한 뒤 다시 하세요'))


def _command() -> list[str]:
    script = skills_dir() / 'lectern-to-pptx' / 'scripts' / 'build_pptx.py'
    folder = program_dir()
    return [str(folder / 'lectern-skill.exe') if folder else sys.executable, str(script)]


def export(md: Path, style: Any) -> dict[str, Any]:
    """style 이 있으면 그 스타일로, 빈 글자면 문서가 기억한 것으로 전환한다. 결과는 build_pptx 의 보고에 path 를 더한 것."""
    args: list[str] = []
    if style:
        path = style_path(style)
        if path is None:
            raise ExportError(404, t("pptx 스타일 '{name}' 이 보관소에 없습니다 — 다른 스타일을 고르세요", name=style))
        args = ['--template', str(path)]
    out = free_path(md)
    try:
        r = subprocess.run([*_command(), str(md), '--out', str(out), *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=TIMEOUT, creationflags=_NO_WINDOW, cwd=str(md.parent))
    except subprocess.TimeoutExpired:
        raise ExportError(504, t('제한 시간 안에 끝내지 못했습니다 — 차트가 많으면 Claude 에게 전환을 맡기세요')) from None
    except OSError as exc:
        raise ExportError(500, t('전환 프로그램을 띄우지 못했습니다: {why}', why=exc.strerror or exc)) from None
    report = next((json.loads(line) for line in reversed(r.stdout.split('\n')) if line.startswith('{"pptx"')), None)
    if r.returncode or report is None or not out.is_file():
        why = (r.stderr or r.stdout).strip().split('\n')[-1][:300]
        raise ExportError(500, t('pptx 를 만들지 못했습니다: {why}', why=why))
    report['path'] = out.name
    return report
