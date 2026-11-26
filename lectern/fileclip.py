"""파일 복사·붙여 넣기 (D203): 사이드바 '폴더' 묶음에서만 — Windows 클립보드의 파일 목록(CF_HDROP)으로 탐색기와 주고받는다.

- 복사: 고른 파일·폴더의 전체 경로를 클립보드에 '복사'(Preferred DropEffect = 복사)로 놓는다. 탐색기에서 Ctrl+V 하면 붙는다.
- 붙여 넣기: 클립보드의 파일 목록을 고른 폴더에 복사한다. 실제 복사는 Windows(SHFileOperationW)가 한다 —
  이름이 겹치면 '이름 - 복사본' 으로 새 이름을 붙이고(덮어쓰지 않음), 오래 걸리면 Windows 의 진행 창(취소)이 뜨고, 탐색기의 Ctrl+Z 로 되돌린다.
- 탐색기에서 '잘라내기' 한 것도 복사만 한다 — 원본은 지우지 않는다 (Lectern 에 옮기기는 없다).
- 바로가기 폴더(심볼릭 링크·정션)는 복사하지 않는다 — 따라가면 끝없이 돌거나 밖의 것을 끌어올 수 있다.
- 폴더를 그 자신이나 그 안으로 붙이지 않는다. 대상 폴더의 검사(프로젝트 안·보기만 하는 폴더)는 부르는 쪽(server)이 한다.

SHFileOperationW 는 STA 에서 불러야 한다 (trash.py 와 같게 잠깐 쓰는 스레드에서).
클립보드에 놓을 때는 창이 하나 있어야 한다 — 주인이 없는 클립보드에는 SetClipboardData 가 실패할 수 있다 (메시지 전용 창을 잠깐 만든다).
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
import threading
import time
from pathlib import Path

from .i18n import t

CF_HDROP = 15
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040
DROPEFFECT_COPY = 1
DROPEFFECT_MOVE = 2
FO_COPY = 2
FOF_NOCONFIRMMKDIR = 0x0200
FOF_RENAMEONCOLLISION = 0x0008
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400
COINIT_APARTMENTTHREADED = 0x2
HWND_MESSAGE = -3
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class ClipError(Exception):
    """복사·붙여 넣기를 하지 못했다. message 는 화면에 그대로 보인다"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _win():
    from ctypes import wintypes as w
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    shell = ctypes.WinDLL('shell32')
    user.OpenClipboard.argtypes = [w.HWND]
    user.OpenClipboard.restype = w.BOOL
    user.GetClipboardData.argtypes = [w.UINT]
    user.GetClipboardData.restype = w.HANDLE
    user.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
    user.SetClipboardData.restype = w.HANDLE
    user.RegisterClipboardFormatW.argtypes = [w.LPCWSTR]
    user.RegisterClipboardFormatW.restype = w.UINT
    user.IsClipboardFormatAvailable.argtypes = [w.UINT]
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user.CreateWindowExW.restype = w.HWND
    user.DestroyWindow.argtypes = [w.HWND]
    kernel.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = w.HGLOBAL
    kernel.GlobalLock.argtypes = [w.HGLOBAL]
    kernel.GlobalLock.restype = w.LPVOID
    kernel.GlobalUnlock.argtypes = [w.HGLOBAL]
    kernel.GlobalSize.argtypes = [w.HGLOBAL]
    kernel.GlobalSize.restype = ctypes.c_size_t
    kernel.GlobalFree.argtypes = [w.HGLOBAL]
    shell.DragQueryFileW.argtypes = [w.HANDLE, w.UINT, w.LPWSTR, w.UINT]
    shell.DragQueryFileW.restype = w.UINT
    return user, kernel, shell


def _open(user, hwnd=None) -> None:
    """클립보드를 연다 — 다른 프로그램이 잠깐 잡고 있으면 조금 기다린다"""
    for _ in range(40):
        if user.OpenClipboard(hwnd):
            return
        time.sleep(0.025)
    raise ClipError(t('클립보드를 열지 못했습니다 — 다른 프로그램이 쓰고 있습니다. 잠시 뒤 다시 하세요'))


def _global(kernel, data: bytes):
    h = kernel.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    if not h:
        raise ClipError(t('클립보드에 놓지 못했습니다'))
    p = kernel.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    kernel.GlobalUnlock(h)
    return h


def put(paths: list[Path]) -> None:
    """파일·폴더의 전체 경로를 클립보드에 '복사' 로 놓는다 (탐색기의 Ctrl+C 와 같은 모양)"""
    if sys.platform != 'win32':
        raise ClipError(t('이 컴퓨터에서는 파일을 클립보드에 놓을 수 없습니다'))
    user, kernel, _ = _win()
    names = ''.join(f'{p}\0' for p in paths) + '\0'
    drop = struct.pack('<IiiII', 20, 0, 0, 0, 1) + names.encode('utf-16-le')   # DROPFILES: pFiles=20, pt, fNC, fWide=1
    effect = struct.pack('<I', DROPEFFECT_COPY)
    fmt = user.RegisterClipboardFormatW('Preferred DropEffect')
    hwnd = user.CreateWindowExW(0, 'STATIC', None, 0, 0, 0, 0, 0, HWND_MESSAGE, None, None, None)
    try:
        _open(user, hwnd)
        try:
            user.EmptyClipboard()
            for kind, data in ((CF_HDROP, drop), (fmt, effect)):
                h = _global(kernel, data)
                if not user.SetClipboardData(kind, h):
                    kernel.GlobalFree(h)
                    raise ClipError(t('클립보드에 놓지 못했습니다'))
        finally:
            user.CloseClipboard()
    finally:
        if hwnd:
            user.DestroyWindow(hwnd)


def read() -> tuple[list[Path], bool]:
    """클립보드의 파일 목록과 '잘라내기' 였는지. 파일이 없으면 ([], False)"""
    if sys.platform != 'win32':
        return [], False
    user, kernel, shell = _win()
    if not user.IsClipboardFormatAvailable(CF_HDROP):
        return [], False
    fmt = user.RegisterClipboardFormatW('Preferred DropEffect')
    _open(user)
    try:
        h = user.GetClipboardData(CF_HDROP)
        out: list[Path] = []
        if h:
            n = shell.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
            for i in range(n):
                size = shell.DragQueryFileW(h, i, None, 0)
                buf = ctypes.create_unicode_buffer(size + 1)
                shell.DragQueryFileW(h, i, buf, size + 1)
                out.append(Path(buf.value))
        cut = False
        e = user.GetClipboardData(fmt) if user.IsClipboardFormatAvailable(fmt) else None
        if e:
            p = kernel.GlobalLock(e)
            if p and kernel.GlobalSize(e) >= 4:
                cut = bool(ctypes.c_uint32.from_address(p).value & DROPEFFECT_MOVE)
            kernel.GlobalUnlock(e)
        return out, cut
    finally:
        user.CloseClipboard()


def is_link(path: Path) -> bool:
    """심볼릭 링크·정션(재분석 지점)인지 — 따라가지 않는다"""
    try:
        st = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return path.is_symlink() or bool(getattr(st, 'st_file_attributes', 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def _copy(sources: list[Path], dest: Path) -> tuple[int, bool]:
    from ctypes import wintypes as w

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1
        _fields_ = [('hwnd', w.HWND), ('wFunc', w.UINT), ('pFrom', ctypes.c_wchar_p), ('pTo', ctypes.c_wchar_p), ('fFlags', w.WORD),
                    ('fAnyOperationsAborted', w.BOOL), ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', ctypes.c_wchar_p)]

    shell = ctypes.WinDLL('shell32')
    shell.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell.SHFileOperationW.restype = ctypes.c_int
    src = ctypes.create_unicode_buffer(''.join(f'{p}\0' for p in sources))   # 버퍼가 끝의 글자 없음을 하나 더한다
    dst = ctypes.create_unicode_buffer(f'{dest}\0')
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_COPY
    op.pFrom = ctypes.cast(src, ctypes.c_wchar_p)
    op.pTo = ctypes.cast(dst, ctypes.c_wchar_p)
    op.fFlags = FOF_RENAMEONCOLLISION | FOF_ALLOWUNDO | FOF_NOCONFIRMMKDIR | FOF_NOERRORUI
    code = shell.SHFileOperationW(ctypes.byref(op))
    return code, bool(op.fAnyOperationsAborted)


def _in_apartment(sources: list[Path], dest: Path, out: list) -> None:
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    try:
        out.append(_copy(sources, dest))
    except OSError as exc:
        out.append(exc)
    finally:
        ole.CoUninitialize()


def paste(dest: Path) -> dict:
    """클립보드의 파일·폴더를 dest(이미 있는 폴더)에 복사한다. {copied: 복사한 수, cut: 잘라내기였는지, skipped: [건너뛴 이름]}"""
    if sys.platform != 'win32':
        raise ClipError(t('이 컴퓨터에서는 붙여 넣을 수 없습니다'))
    sources, cut = read()
    if not sources:
        raise ClipError(t('클립보드에 파일이 없습니다 — 탐색기나 폴더 묶음에서 파일을 복사(Ctrl+C)한 뒤 붙여 넣으세요'))
    target = os.path.normcase(str(dest.resolve()))
    keep: list[Path] = []
    skipped: list[str] = []
    for src in sources:
        if not src.exists() or is_link(src):
            skipped.append(src.name)
            continue
        here = os.path.normcase(str(src.resolve()))
        if src.is_dir() and (target == here or target.startswith(here + os.sep)):
            raise ClipError(t('폴더를 그 폴더 안으로 붙여 넣을 수 없습니다: {name}', name=src.name))
        keep.append(src)
    if not keep:
        raise ClipError(t('붙여 넣을 수 있는 파일이 없습니다 — 바로가기 폴더와 없어진 파일은 붙여 넣지 않습니다'))
    out: list = []
    worker = threading.Thread(target=_in_apartment, args=(keep, dest, out), daemon=True)
    worker.start()
    worker.join()
    result = out[0] if out else OSError('no result')
    if isinstance(result, OSError):
        raise ClipError(t('붙여 넣지 못했습니다 ({error})', error=str(result)))
    code, aborted = result
    if aborted:
        raise ClipError(t('붙여 넣기를 그만두었습니다 — 그때까지 복사한 것은 남습니다'))
    if code:
        raise ClipError(t('붙여 넣지 못했습니다 (Windows 코드 {code}) — 파일이 열려 있거나 권한이 없을 수 있습니다', code=hex(code)))
    return {'copied': len(keep), 'cut': cut, 'skipped': skipped}
