# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정.  사용: pyinstaller --noconfirm lectern.spec
# 결과: dist\Lectern\Lectern.exe  (onedir — 폴더째 복사해서 배포. 설치 파일은 installer\lectern.iss)
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH)
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT / 'lectern' / '__init__.py').read_text(encoding='utf-8')).group(1)
NUMS = tuple(int(n) for n in VERSION.split('.')) + (0,) * (4 - len(VERSION.split('.')))

# 탐색기 '속성 → 자세히' 와 설치·제거 목록에 보이는 버전 정보 (한국어, 유니코드)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMS, prodvers=NUMS),
    kids=[
        StringFileInfo([StringTable('041204B0', [
            StringStruct('ProductName', 'Lectern'),
            StringStruct('FileDescription', 'Lectern 문서 뷰어'),
            StringStruct('FileVersion', VERSION),
            StringStruct('ProductVersion', VERSION),
            StringStruct('InternalName', 'Lectern'),
            StringStruct('OriginalFilename', 'Lectern.exe'),
        ])]),
        VarFileInfo([VarStruct('Translation', [0x0412, 1200])]),
    ],
)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web')],          # web/ 전체 (vendor 라이브러리 포함) → _internal\web
    hiddenimports=[
        # watchdog 는 OS별 감시 모듈을 실행 중에 고르므로 명시해 둔다
        'watchdog.observers.read_directory_changes',
        'watchdog.observers.winapi',
        'watchdog.observers.polling',
    ],
    excludes=['tkinter', 'pytest', 'playwright'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Lectern',
    console=False,                   # 창 앱 (콘솔 없음)
    upx=False,                       # 백신 오탐을 줄이기 위해 압축하지 않음
    icon=str(ROOT / 'assets' / 'lectern.ico'),   # 바꾸려면 assets/lectern.svg 를 고치고 tools/make_icon.py
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, name='Lectern', upx=False)
