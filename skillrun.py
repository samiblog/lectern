"""Lectern 스킬 실행기 — lectern-skill.exe (D99).

Python 이 없는 PC 에서 PowerPoint 스킬을 돌린다. Python 과 pywin32, Pillow 를 묶은 콘솔 프로그램이다.
사용자가 시킨 Claude 가 부른다. 앱은 부르지 않는다.

    lectern-skill.exe <스킬>/scripts/이름.py 인자…
    lectern-skill.exe --version

스크립트가 sys.executable 로 자식을 띄우므로 python 처럼 -I·-B 를 받아 넘긴다.
돌리는 것은 SKILL.md 가 있는 스킬의 scripts 폴더 안 파일뿐이다. -c·-m 은 받지 않는다.
"""
from __future__ import annotations

import runpy
import sys
import traceback
from pathlib import Path

USAGE = '쓰는 법: lectern-skill.exe <스킬>/scripts/이름.py 인자…'
PYTHON_FLAGS = {'-I', '-B', '-E', '-s', '-u'}


def skill_script(name: str) -> Path | None:
    """스킬의 스크립트면 그 경로를, 아니면 None 을 준다."""
    path = Path(name).resolve()
    if path.suffix == '.py' and path.is_file() and path.parent.name == 'scripts' and (path.parent.parent / 'SKILL.md').is_file():
        return path
    return None


def version() -> int:
    """판과 묶은 라이브러리를 알린다. 빠진 것이 있으면 1 을 준다."""
    from lectern import __version__
    try:
        import PIL
        import win32com.client  # noqa: F401
    except ImportError as e:
        print(f'실행기에 라이브러리가 빠졌습니다: {e}. Lectern 을 다시 설치하면 됩니다', file=sys.stderr)
        return 1
    print(f'lectern-skill {__version__} (Python {sys.version.split()[0]}, Pillow {PIL.__version__}, pywin32)')
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    while args and args[0] in PYTHON_FLAGS:
        args.pop(0)
    if args[:1] == ['--version']:
        return version()
    if not args:
        print(USAGE, file=sys.stderr)
        return 2
    path = skill_script(args[0])
    if path is None:
        print(f'스킬의 스크립트가 아니어서 돌리지 않습니다: {args[0]}\n{USAGE}', file=sys.stderr)
        return 2
    sys.argv = [str(path), *args[1:]]
    sys.path.insert(0, str(path.parent))
    try:
        runpy.run_path(str(path), run_name='__main__')
    except Exception:  # noqa: BLE001 — 그냥 두면 PyInstaller 가 마지막 줄을 자기 안내로 덮어 스크립트가 까닭을 못 읽는다
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
