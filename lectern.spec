# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 설정.  사용: pyinstaller --noconfirm lectern.spec
# 결과: dist\Lectern\Lectern.exe  (onedir — 폴더째 복사해서 배포)

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
    icon=None,                       # 아이콘을 넣으려면 'assets/app.ico'
)
coll = COLLECT(exe, a.binaries, a.datas, name='Lectern', upx=False)
