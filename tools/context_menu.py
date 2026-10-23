"""탐색기 우클릭 메뉴 'Lectern으로 열기' 등록/제거 (Windows, 현재 사용자만 — 관리자 권한 불필요).

사용법
    python tools/context_menu.py                 # dist\\Lectern\\Lectern.exe 가 있으면 그것으로, 없으면 pythonw + app.py 로 등록
    python tools/context_menu.py --exe C:\\Tools\\Lectern\\Lectern.exe
    python tools/context_menu.py --remove

등록 위치: HKCU\\Software\\Classes\\Directory\\shell\\Lectern (폴더 우클릭)
          HKCU\\Software\\Classes\\Directory\\Background\\shell\\Lectern (폴더 안 빈 곳 우클릭)
Windows 11에서는 '더 많은 옵션 표시' 아래에 나타난다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lectern.i18n import system_language  # noqa: E402

# 메뉴 이름은 Windows 표시 언어를 따른다 (설치 파일과 같게, D46)
LABEL = 'Lectern으로 열기' if system_language() == 'ko' else 'Open with Lectern'
KEYS = {
    r'Software\Classes\Directory\shell\Lectern': '%1',
    r'Software\Classes\Directory\Background\shell\Lectern': '%V',
}


def default_command() -> tuple[str, str]:
    """(명령 앞부분, 아이콘 경로)"""
    exe = ROOT / 'dist' / 'Lectern' / 'Lectern.exe'
    if exe.exists():
        return f'"{exe}"', str(exe)
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    runner = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{runner}" "{ROOT / "app.py"}"', str(runner)


def register(prefix: str, icon: str) -> None:
    import winreg

    for key, arg in KEYS.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, '', 0, winreg.REG_SZ, LABEL)
            winreg.SetValueEx(k, 'Icon', 0, winreg.REG_SZ, icon)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r'\command') as k:
            winreg.SetValueEx(k, '', 0, winreg.REG_SZ, f'{prefix} "{arg}"')
    print(f'등록했습니다: {prefix} "<폴더>"')


def remove() -> None:
    import winreg

    for key in KEYS:
        for sub in (key + r'\command', key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except FileNotFoundError:
                pass
    print('우클릭 메뉴를 제거했습니다.')


def main() -> None:
    if sys.platform != 'win32':
        sys.exit('Windows에서만 사용할 수 있습니다.')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--exe', help='Lectern.exe 경로')
    parser.add_argument('--remove', action='store_true', help='등록 제거')
    args = parser.parse_args()
    if args.remove:
        remove()
        return
    if args.exe:
        exe = Path(args.exe).resolve()
        if not exe.exists():
            sys.exit(f'파일이 없습니다: {exe}')
        register(f'"{exe}"', str(exe))
    else:
        register(*default_command())


if __name__ == '__main__':
    main()
