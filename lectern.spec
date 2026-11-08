# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정.  사용: pyinstaller --noconfirm lectern.spec
# 결과: dist\Lectern\Lectern.exe  (onedir — 폴더째 복사해서 배포. 설치 파일은 installer\lectern.iss)
import re
from pathlib import Path

# 스킬 실행기에 묶는다. 없으면 말없이 반쪽 실행기가 나오니 여기서 멈춘다 (D99)
import PIL  # noqa: F401
import win32com.client  # noqa: F401
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

ROOT = Path(SPECPATH)
VERSION = re.search(r"__version__ = '([^']+)'", (ROOT / 'lectern' / '__init__.py').read_text(encoding='utf-8')).group(1)
NUMS = tuple(int(n) for n in VERSION.split('.')) + (0,) * (4 - len(VERSION.split('.')))


def version_of(description, name):
    """탐색기 '속성 → 자세히' 와 설치·제거 목록에 보이는 버전 정보 (한국어, 유니코드)"""
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=NUMS, prodvers=NUMS),
        kids=[
            StringFileInfo([StringTable('041204B0', [
                StringStruct('ProductName', 'Lectern'),
                StringStruct('FileDescription', description),
                StringStruct('FileVersion', VERSION),
                StringStruct('ProductVersion', VERSION),
                StringStruct('InternalName', name),
                StringStruct('OriginalFilename', f'{name}.exe'),
            ])]),
            VarFileInfo([VarStruct('Translation', [0x0412, 1200])]),
        ],
    )


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('web', 'web'),           # web/ 전체 (vendor 라이브러리 포함) → _internal\web
           ('samples', 'samples'),   # 예제 프로젝트 (D57 — 시작 화면의 '예제 열기') → _internal\samples
           ('skills', 'skills'),     # Claude Code 스킬 (D98 — 설치는 사용자가 시킬 때 Claude 가) → _internal\skills
           ('LICENSE', '.'),         # Lectern 의 라이선스(MIT)와 함께 든 오픈소스의 고지 — 바이너리로 배포할 때 함께 준다
           ('THIRD-PARTY-NOTICES.md', '.')],
    hiddenimports=[
        # watchdog 는 OS별 감시 모듈을 실행 중에 고르므로 명시해 둔다
        'watchdog.observers.read_directory_changes',
        'watchdog.observers.winapi',
        'watchdog.observers.polling',
    ],
    excludes=['tkinter', 'pytest', 'playwright'],
    noarchive=False,
)
# 시험이 skills/ 에 남긴 바이트코드는 설치 파일에 넣지 않는다
a.datas = [d for d in a.datas if '__pycache__' not in d[0]]
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
    version=version_of('Lectern 통합 리서치 작업 환경', 'Lectern'),   # 작업 관리자·'연결 프로그램' 에 보이는 이름 — 짧게
)

# 스킬 실행기 (D99). 돌리는 스크립트는 설치된 스킬 폴더의 것이니 코드는 빼고, 쓰는 모듈만 남긴다
SKILL_SCRIPTS = sorted((ROOT / 'skills').glob('*/scripts/*.py'))
SKILL_MODULES = {p.stem for p in SKILL_SCRIPTS}
b = Analysis(
    ['skillrun.py'],
    pathex=sorted({str(p.parent) for p in SKILL_SCRIPTS}),
    hiddenimports=sorted(SKILL_MODULES),
    excludes=['tkinter', 'pytest', 'playwright', 'win32ui', 'pywin', 'defusedxml', 'PIL._avif', 'PIL.AvifImagePlugin'],
    noarchive=False,
)
b.pure = [m for m in b.pure if m[0] not in SKILL_MODULES]
skill_exe = EXE(
    PYZ(b.pure),
    b.scripts,
    [('X utf8_mode=1', None, 'OPTION')],   # 한국어 Windows 에서도 출력과 파일을 UTF-8 로
    exclude_binaries=True,
    name='lectern-skill',
    console=True,                    # Claude 가 출력을 읽는다
    upx=False,
    icon=str(ROOT / 'assets' / 'lectern.ico'),
    version=version_of('Lectern 스킬 실행기', 'lectern-skill'),
)
coll = COLLECT(exe, skill_exe, a.binaries, b.binaries, a.datas, b.datas, name='Lectern', upx=False)
