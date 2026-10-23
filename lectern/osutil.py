"""문서 속 링크와 사이드바 '문서 외 파일'이 가리키는 파일을 OS에 넘겨 여는 기능.

주의: os.startfile 은 파일을 '실행'할 수 있다. .py/.js/.bat/.ps1 등은 Windows 기본 동작이
실행이므로 절대 startfile 로 열지 않는다. 안전한 문서·이미지 형식만 기본 앱으로 열고,
실행 파일·압축·데이터처럼 편집기로 읽을 수 없는 형식은 탐색기에서 선택만 하고,
그 밖의 파일은 편집기(VS Code 등)로 연다 (편집기가 없으면 탐색기에서 선택).
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
    '.mp4', '.mp3', '.wav', '.m4a', '.mov', '.tif', '.tiff',
})

# 편집기로 열어도 읽을 수 없는 형식 (실행·설치 파일, 압축, 데이터베이스, 매크로가 든 오피스 문서 등).
# 기본 앱으로도 편집기로도 열지 않고 탐색기에서 선택만 한다 — 실행은 사용자가 탐색기에서 직접
REVEAL_ONLY_EXT = frozenset({
    '.exe', '.msi', '.msix', '.appx', '.dll', '.sys', '.com', '.scr', '.cpl', '.ocx', '.lnk', '.url',
    '.jar', '.apk', '.class', '.pyc', '.pyd', '.so', '.dylib', '.o', '.obj', '.lib', '.bin', '.dat',
    '.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.cab', '.iso', '.img', '.vhd', '.vhdx',
    '.db', '.sqlite', '.sqlite3', '.mdb', '.accdb', '.parquet', '.pkl', '.npy', '.h5',
    '.docm', '.dotm', '.xlsm', '.xltm', '.xlsb', '.pptm',
    '.ttf', '.otf', '.woff', '.woff2', '.psd', '.ai',
})

# 편집기 실행 인자에 들어가면 cmd 해석 문제를 일으킬 수 있는 문자 (code.cmd 는 배치 파일)
_UNSAFE_CHARS = frozenset('&|<>^%!"')

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def find_editor(configured: str | None) -> str | None:
    """설정한 편집기(절대경로) 또는 PATH 의 code. 현재 폴더에서는 찾지 않는다.

    Windows 는 실행 파일을 PATH 보다 현재 폴더에서 먼저 찾는다. `run.bat .`·탐색기 우클릭으로 띄우면 현재 폴더가
    열린 프로젝트라서, 내려받은 프로젝트에 든 code.cmd 가 링크 한 번에 실행될 수 있다 (점검에서 발견).
    """
    if configured and Path(configured).is_absolute() and Path(configured).is_file():
        return configured
    os.environ['NoDefaultCurrentDirectoryInExePath'] = '1'   # shutil.which 가 현재 폴더를 보지 않게 (Windows)
    found = shutil.which('code')
    return found if found and os.path.isabs(found) else None


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
        # 'explorer' 만 쓰면 현재 폴더(열린 프로젝트)의 explorer.exe 가 먼저 잡힐 수 있어 Windows 폴더의 것을 쓴다
        explorer = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'explorer.exe')
        subprocess.Popen(f'"{explorer}" /select,"{path}"', creationflags=_NO_WINDOW)
    else:
        open_default(path.parent if path.is_file() else path)


def how_to_open(name: str) -> str:
    """파일을 열 방법: default(기본 앱) | editor(편집기 — 없으면 탐색기) | reveal(탐색기에서 선택만). 화면이 메뉴에 보인다"""
    ext = os.path.splitext(name)[1].lower()
    if ext in SAFE_DEFAULT_APP_EXT:
        return 'default'
    return 'reveal' if ext in REVEAL_ONLY_EXT else 'editor'


def open_path(path: Path, line: int | None = None, editor: str | None = None, prefer_editor: bool = False) -> str:
    """경로를 적절한 방법으로 연다. 사용한 방법을 반환: folder | default | editor | reveal

    prefer_editor: 기본 앱으로 여는 형식(csv·txt 등)도 편집기로 ('편집기로 열기'). 읽을 수 없는 형식은 그래도 탐색기에서 선택만.
    """
    if path.is_dir():
        open_default(path)
        return 'folder'
    how = how_to_open(path.name)
    if how == 'default' and not prefer_editor:
        open_default(path)
        return 'default'
    exe = find_editor(editor) if how != 'reveal' else None
    if exe and not (_UNSAFE_CHARS & set(str(path))):
        _launch([exe, '-g', f'{path}:{line or 1}'])  # VS Code / Cursor 형식
        return 'editor'
    reveal(path)
    return 'reveal'
