"""문서 삭제 (D104): 사용자가 고른 파일 하나를 Windows 휴지통으로 보낸다.

되살릴 수 없게 지우는 길은 만들지 않는다. 휴지통이 없는 드라이브(네트워크·이동식)는 지우지 않고 까닭을 알린다.
고정 드라이브라도 휴지통을 끈 PC 면 Windows 가 직접 묻는다 (FOF_WANTNUKEWARNING).

SHFileOperationW 는 STA 에서 불러야 한다. waitress 스레드는 COM 을 열지 않았으므로 잠깐 쓰는 스레드에서 부른다.
"""
from __future__ import annotations

import ctypes
import sys
import threading
from pathlib import Path

from .i18n import t

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400
FOF_WANTNUKEWARNING = 0x4000
DRIVE_FIXED = 3
COINIT_APARTMENTTHREADED = 0x2


class TrashError(Exception):
    """휴지통으로 보내지 못했다. message 는 화면에 그대로 보인다"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _recycle(path: Path) -> tuple[int, bool]:
    """SHFileOperationW 를 부른다. (돌려준 값, 사용자가 그만두었는지)"""
    from ctypes import wintypes as w

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _pack_ = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 1   # shellapi.h: 32비트는 1바이트로 붙여 놓는다
        _fields_ = [('hwnd', w.HWND), ('wFunc', w.UINT), ('pFrom', ctypes.c_wchar_p), ('pTo', ctypes.c_wchar_p), ('fFlags', w.WORD),
                    ('fAnyOperationsAborted', w.BOOL), ('hNameMappings', ctypes.c_void_p), ('lpszProgressTitle', ctypes.c_wchar_p)]

    shell = ctypes.WinDLL('shell32')
    shell.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell.SHFileOperationW.restype = ctypes.c_int
    names = ctypes.create_unicode_buffer(f'{path}\0')   # 목록은 글자 없음 두 개로 끝난다 (버퍼가 하나를 더한다)
    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = ctypes.cast(names, ctypes.c_wchar_p)
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI | FOF_WANTNUKEWARNING
    code = shell.SHFileOperationW(ctypes.byref(op))
    return code, bool(op.fAnyOperationsAborted)


def _in_apartment(path: Path, out: list) -> None:
    ole = ctypes.WinDLL('ole32')
    ole.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    try:
        out.append(_recycle(path))
    except OSError as exc:
        out.append(exc)
    finally:
        ole.CoUninitialize()


def send(path: Path) -> None:
    """파일 하나를 휴지통으로 보낸다. 안 되면 TrashError — 그때 파일은 그대로다"""
    if sys.platform != 'win32':
        raise TrashError(t('이 컴퓨터에서는 휴지통으로 보낼 수 없습니다 — 파일은 그대로입니다'))
    kernel = ctypes.WinDLL('kernel32')
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    if kernel.GetDriveTypeW(path.anchor) != DRIVE_FIXED:
        raise TrashError(t('이 드라이브에는 휴지통이 없어 지우지 않았습니다 — 탐색기에서 지우세요'))
    out: list = []
    worker = threading.Thread(target=_in_apartment, args=(path, out), daemon=True)
    worker.start()
    worker.join()
    result = out[0] if out else OSError('no result')
    if isinstance(result, OSError):
        raise TrashError(t('휴지통으로 보내지 못했습니다: {error}', error=str(result)))
    code, aborted = result
    if aborted:
        raise TrashError(t('지우기를 그만두었습니다 — 파일은 그대로입니다'))
    if code or path.exists():
        raise TrashError(t('휴지통으로 보내지 못했습니다 — 다른 프로그램이 이 파일을 쓰고 있으면 그 프로그램에서 닫은 뒤 다시 하세요'))
