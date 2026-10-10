"""문서 속 링크가 가리키는 파일을 OS에 넘겨 여는 기능.

주의: os.startfile 은 파일을 '실행'할 수 있다. .py/.js/.bat/.ps1 등은 Windows 기본 동작이
실행이므로 절대 startfile 로 열지 않는다. 안전한 문서·이미지 형식만 기본 앱으로 열고,
그 밖의 파일은 편집기(VS Code 등)로 열거나, 편집기가 없으면 탐색기에서 선택만 해 준다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 기본 앱으로 열어도 실행되지 않는 형식
SAFE_DEFAULT_APP_EXT = frozenset({
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg', '.ico',
    '.pdf', '.txt', '.log', '.csv', '.tsv',
    '.xlsx', '.xls', '.docx', '.doc', '.pptx', '.ppt', '.hwp', '.hwpx',
    '.mp4', '.mp3', '.wav',
})

# 편집기 실행 인자에 들어가면 cmd 해석 문제를 일으킬 수 있는 문자 (code.cmd 는 배치 파일)
_UNSAFE_CHARS = frozenset('&|<>^%!"')

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def find_editor(configured: str | None) -> str | None:
    if configured and Path(configured).exists():
        return configured
    return shutil.which('code')


def _launch(args: list[str]) -> None:
    subprocess.Popen(args, creationflags=_NO_WINDOW, close_fds=True)


def open_default(path: Path) -> None:
    if sys.platform == 'win32':
        os.startfile(str(path))  # noqa: S606 - SAFE_DEFAULT_APP_EXT 와 폴더에만 사용
    elif sys.platform == 'darwin':
        _launch(['open', str(path)])
    else:
        _launch(['xdg-open', str(path)])


def reveal(path: Path) -> None:
    """탐색기에서 파일을 선택한 상태로 보여 준다."""
    if sys.platform == 'win32':
        subprocess.Popen(f'explorer /select,"{path}"', creationflags=_NO_WINDOW)
    else:
        open_default(path.parent if path.is_file() else path)


def open_path(path: Path, line: int | None = None, editor: str | None = None) -> str:
    """경로를 적절한 방법으로 연다. 사용한 방법을 반환: folder | default | editor | reveal"""
    if path.is_dir():
        open_default(path)
        return 'folder'
    if path.suffix.lower() in SAFE_DEFAULT_APP_EXT:
        open_default(path)
        return 'default'
    exe = find_editor(editor)
    if exe and not (_UNSAFE_CHARS & set(str(path))):
        _launch([exe, '-g', f'{path}:{line or 1}'])  # VS Code / Cursor 형식
        return 'editor'
    reveal(path)
    return 'reveal'
