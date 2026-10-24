"""Windows 의사 콘솔(ConPTY)을 ctypes 로 — 오른쪽 터미널(D38)의 셸을 띄운다.

kernel32 의 CreatePseudoConsole(Windows 10 1809 이상)을 직접 쓴다. pywinpty 는 자기가 들고 온 콘솔 호스트를 써서
한국어 Windows 에서 한글 출력이 cp949 바이트로 깨졌다 (점검에서 확인). Windows 기본 ConPTY 는 입출력 모두 UTF-8 이다.

- 셸은 작업 개체(Job Object, KILL_ON_JOB_CLOSE) 안에서 돈다: 닫거나 이 프로세스가 끝나면 셸에서 띄운 프로그램까지 함께 끝난다.
  일시 정지로 만들어 작업 개체에 넣은 뒤 깨운다 — 넣기 전에 자식을 띄우는 틈이 없게.
- 부모의 표준 입출력을 물려주지 않는다 (STARTF_USESTDHANDLES + 빈 핸들). 안 그러면 부모의 콘솔·파이프로 출력이 샌다.
- 셸을 띄우기 전에 이 프로세스의 'Ctrl+C 무시' 표시를 끈다 (SetConsoleCtrlHandler(NULL, FALSE)). 이 표시는 자식에게 물려지는데,
  Lectern 을 새 프로세스 그룹으로 띄운 프로그램(일부 실행기·자동화 도구)에서 켜진 채로 오면 셸과 거기서 띄운 프로그램이
  Ctrl+C 로 멈추지 않는다 (점검에서 확인 — ping 이 끝까지 돌았다).
- 셸에서 띄운 프로그램이 시작하다 멈췄는지(보안 프로그램이 프로세스 생성을 막음 — D58) stuck_children() 이 읽기만 해서 찾는다.
  그런 프로그램은 핸들에서 종료 권한이 깎여 있어 따로 끝낼 수 없고, 작업 개체째 끝내는 것(terminate — 다시 시작)은 된다.
- read() 는 막혀 기다린다 (읽는 스레드에서 부른다). close() 는 그 스레드가 읽는 동안 불러도 된다 — ClosePseudoConsole 은
  남은 출력을 내보낸 뒤 파이프를 닫고, 그러면 read() 가 b'' 를 돌려준다.
"""
from __future__ import annotations

import ctypes
import struct
import sys
import threading
from ctypes import wintypes as w

from .i18n import t

AVAILABLE = False
if sys.platform == 'win32':
    _k = ctypes.WinDLL('kernel32', use_last_error=True)
    AVAILABLE = hasattr(_k, 'CreatePseudoConsole')

EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_BASIC_ACCOUNTING = 1
JOB_PROCESS_ID_LIST = 3
JOB_EXTENDED_LIMIT = 9
WAIT_OBJECT_0 = 0
INFINITE = 0xFFFFFFFF
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
ERROR_MORE_DATA = 234
ERROR_PARTIAL_COPY = 299
LIST_MODULES_ALL = 3
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
SYSTEM_PROCESS_INFORMATION = 5


class COORD(ctypes.Structure):
    _fields_ = [('X', w.SHORT), ('Y', w.SHORT)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR), ('lpTitle', w.LPWSTR),
                ('dwX', w.DWORD), ('dwY', w.DWORD), ('dwXSize', w.DWORD), ('dwYSize', w.DWORD),
                ('dwXCountChars', w.DWORD), ('dwYCountChars', w.DWORD), ('dwFillAttribute', w.DWORD),
                ('dwFlags', w.DWORD), ('wShowWindow', w.WORD), ('cbReserved2', w.WORD), ('lpReserved2', ctypes.c_void_p),
                ('hStdInput', w.HANDLE), ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [('StartupInfo', STARTUPINFOW), ('lpAttributeList', ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE), ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ('ReadOps', 'WriteOps', 'OtherOps', 'ReadBytes', 'WriteBytes', 'OtherBytes')]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', w.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', w.DWORD), ('Affinity', ctypes.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION), ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [('TotalUserTime', ctypes.c_int64), ('TotalKernelTime', ctypes.c_int64),
                ('ThisPeriodTotalUserTime', ctypes.c_int64), ('ThisPeriodTotalKernelTime', ctypes.c_int64),
                ('TotalPageFaultCount', w.DWORD), ('TotalProcesses', w.DWORD), ('ActiveProcesses', w.DWORD),
                ('TotalTerminatedProcesses', w.DWORD)]


if AVAILABLE:
    _k.CreatePseudoConsole.argtypes = [COORD, w.HANDLE, w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    _k.CreatePseudoConsole.restype = ctypes.c_long
    _k.ResizePseudoConsole.argtypes = [w.HANDLE, COORD]
    _k.ResizePseudoConsole.restype = ctypes.c_long
    _k.ClosePseudoConsole.argtypes = [w.HANDLE]
    _k.ClosePseudoConsole.restype = None
    _k.CreatePipe.argtypes = [ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE), ctypes.c_void_p, w.DWORD]
    _k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    _k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_void_p, ctypes.c_void_p]
    _k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    _k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD, ctypes.c_void_p,
                                  w.LPCWSTR, ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION)]
    _k.ResumeThread.argtypes = [w.HANDLE]
    _k.ResumeThread.restype = w.DWORD
    _k.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    _k.WriteFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    _k.CloseHandle.argtypes = [w.HANDLE]
    _k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    _k.WaitForSingleObject.restype = w.DWORD
    _k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    _k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    _k.CreateJobObjectW.restype = w.HANDLE
    _k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    _k.QueryInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    _k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    _k.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    _k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    _k.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, w.BOOL]
    # 시작하다 멈춘 프로그램 찾기 (stuck_children — 읽기만)
    _k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    _k.OpenProcess.restype = w.HANDLE
    _k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    _k.GetSystemTimeAsFileTime.argtypes = [ctypes.POINTER(w.FILETIME)]
    _k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    _psapi = ctypes.WinDLL('psapi', use_last_error=True)
    _psapi.EnumProcessModulesEx.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), w.DWORD]
    _nt = ctypes.WinDLL('ntdll')
    _nt.NtQuerySystemInformation.argtypes = [ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    _nt.NtQuerySystemInformation.restype = ctypes.c_long


def _check(ok: object, what: str) -> None:
    if not ok:
        err = ctypes.get_last_error()
        raise OSError(err, t('{what} 실패: {error}', what=what, error=ctypes.FormatError(err).strip()))


def _env_block(env: dict[str, str]) -> ctypes.Array:
    """CreateProcessW 의 환경 블록 (UTF-16, 이름 순, 마지막에 빈 줄)"""
    items = sorted(env.items(), key=lambda kv: kv[0].upper())
    return ctypes.create_unicode_buffer('\0'.join(f'{k}={v}' for k, v in items) + '\0\0')


def _size(cols: int, rows: int) -> COORD:
    return COORD(max(2, min(int(cols), 1000)), max(1, min(int(rows), 500)))


def _filetime(ft: w.FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def _process_state(pid: int) -> tuple[int, str, bool] | None:
    """(만든 시각 — FILETIME 정수, 실행 파일 이름, 로더가 돌았는지). 열 수 없으면 None.
    로더가 한 번도 돌지 않은 프로세스(PEB 의 모듈 목록이 아직 없음)는 EnumProcessModulesEx 가 ERROR_PARTIAL_COPY 로 실패한다"""
    h = _k.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not _k.GetProcessTimes(h, *(ctypes.byref(x) for x in times)):
            return None
        name = ctypes.create_unicode_buffer(520)
        size = w.DWORD(520)
        exe = name.value.rsplit('\\', 1)[-1] if _k.QueryFullProcessImageNameW(h, 0, name, ctypes.byref(size)) else ''
        mods = (ctypes.c_void_p * 1)()
        need = w.DWORD()
        ok = _psapi.EnumProcessModulesEx(h, mods, ctypes.sizeof(mods), ctypes.byref(need), LIST_MODULES_ALL)
        ran = bool(ok) or ctypes.get_last_error() != ERROR_PARTIAL_COPY   # 다른 까닭의 실패는 멈춘 것으로 보지 않는다
        return _filetime(times[0]), exe, ran
    finally:
        _k.CloseHandle(h)


def _all_suspended(pids: set[int]) -> set[int]:
    """pids 중 스레드가 모두 일시 정지(대기 이유 Suspended)인 것 — 시스템의 프로세스·스레드 목록에서 (NtQuerySystemInformation)"""
    size = 1 << 19
    while True:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_ulong()
        status = _nt.NtQuerySystemInformation(SYSTEM_PROCESS_INFORMATION, buf, size, ctypes.byref(got)) & 0xFFFFFFFF
        if status == STATUS_INFO_LENGTH_MISMATCH and size < (1 << 26):
            size = max(size * 2, got.value + 65536)
            continue
        if status:
            return set()
        break
    raw, off, found = buf.raw, 0, set()
    # SYSTEM_PROCESS_INFORMATION(x64): 0 다음 항목까지, 4 스레드 수, 80 프로세스 id, 0x100 부터 SYSTEM_THREAD_INFORMATION(0x50 씩 —
    # 68 상태, 72 대기 이유). 상태 5 = Waiting, 대기 이유 5 = Suspended
    while True:
        nxt, nthreads = struct.unpack_from('<II', raw, off)
        pid = struct.unpack_from('<Q', raw, off + 80)[0]
        if pid in pids and nthreads:
            states = [struct.unpack_from('<II', raw, off + 0x100 + i * 0x50 + 68) for i in range(nthreads)]
            if all(s == (5, 5) for s in states):
                found.add(pid)
        if not nxt:
            return found
        off += nxt


class PseudoConsole:
    """의사 콘솔 위의 프로세스 하나 (셸). cmdline 의 첫 낱말은 실행 파일의 전체 경로여야 한다."""

    def __init__(self, cmdline: str, cwd: str, env: dict[str, str], cols: int = 80, rows: int = 24):
        if not AVAILABLE:
            raise OSError(t('이 Windows 에는 의사 콘솔(ConPTY)이 없습니다 (Windows 10 1809 이상 필요)'))
        self._lock = threading.Lock()
        self._closed = False
        self._hpc = w.HANDLE()
        self._job = None
        self._loaded: set[int] = set()   # 로더가 돈 것을 본 프로세스 (stuck_children 이 다시 열어 보지 않게)
        self._proc = PROCESS_INFORMATION()
        in_read, self._in, self._out, out_write = w.HANDLE(), w.HANDLE(), w.HANDLE(), w.HANDLE()
        _check(_k.CreatePipe(ctypes.byref(in_read), ctypes.byref(self._in), None, 0), 'CreatePipe')
        _check(_k.CreatePipe(ctypes.byref(self._out), ctypes.byref(out_write), None, 0), 'CreatePipe')
        try:
            hr = _k.CreatePseudoConsole(_size(cols, rows), in_read, out_write, 0, ctypes.byref(self._hpc))
            if hr != 0:
                raise OSError(hr, t('CreatePseudoConsole 실패 (0x{code})', code=f'{hr & 0xFFFFFFFF:08X}'))
        finally:
            _k.CloseHandle(in_read)      # 의사 콘솔이 들고 있다
            _k.CloseHandle(out_write)
        try:
            self._job = _k.CreateJobObjectW(None, None)
            _check(self._job, 'CreateJobObject')
            limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            _check(_k.SetInformationJobObject(self._job, JOB_EXTENDED_LIMIT, ctypes.byref(limits), ctypes.sizeof(limits)),
                   'SetInformationJobObject')
            self._spawn(cmdline, cwd, env)
        except BaseException:
            self.close()
            raise

    def _spawn(self, cmdline: str, cwd: str, env: dict[str, str]) -> None:
        size = ctypes.c_size_t()
        _k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attrs = ctypes.create_string_buffer(size.value)
        _check(_k.InitializeProcThreadAttributeList(attrs, 1, 0, ctypes.byref(size)), 'InitializeProcThreadAttributeList')
        try:
            _check(_k.UpdateProcThreadAttribute(attrs, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE, self._hpc,
                                                ctypes.sizeof(w.HANDLE), None, None), 'UpdateProcThreadAttribute')
            si = STARTUPINFOEXW()
            si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
            si.StartupInfo.dwFlags = STARTF_USESTDHANDLES   # 빈 표준 핸들 — 부모의 콘솔·파이프를 물려받지 않게
            si.lpAttributeList = ctypes.cast(attrs, ctypes.c_void_p)
            flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT | CREATE_SUSPENDED
            _k.SetConsoleCtrlHandler(None, False)   # 'Ctrl+C 무시'를 물려주지 않게 (모듈 설명)
            _check(_k.CreateProcessW(None, ctypes.create_unicode_buffer(cmdline), None, None, False, flags,
                                     _env_block(env), cwd, ctypes.byref(si), ctypes.byref(self._proc)), 'CreateProcess')
        finally:
            _k.DeleteProcThreadAttributeList(attrs)
        if not _k.AssignProcessToJobObject(self._job, self._proc.hProcess):
            _k.TerminateProcess(self._proc.hProcess, 1)   # 작업 개체 밖에서 돌면 탭을 닫아도 자식이 남는다
            _check(False, 'AssignProcessToJobObject')
        _k.ResumeThread(self._proc.hThread)

    @property
    def pid(self) -> int:
        return int(self._proc.dwProcessId)

    def read(self, size: int = 65536) -> bytes:
        """출력을 막혀 기다려 읽는다. 끝나면(의사 콘솔이 닫힘) b''"""
        buf = ctypes.create_string_buffer(size)
        n = w.DWORD()
        if not _k.ReadFile(self._out, buf, size, ctypes.byref(n), None) or not n.value:
            return b''
        return buf.raw[:n.value]

    def write(self, data: bytes) -> None:
        with self._lock:
            if self._closed:
                return
            view = memoryview(data)
            while view:
                n = w.DWORD()
                if not _k.WriteFile(self._in, bytes(view[:65536]), min(len(view), 65536), ctypes.byref(n), None):
                    return   # 셸이 끝나는 중
                view = view[n.value:]

    def resize(self, cols: int, rows: int) -> None:
        with self._lock:
            if not self._closed:
                _k.ResizePseudoConsole(self._hpc, _size(cols, rows))

    def wait(self, timeout: float | None = None) -> bool:
        """셸이 끝날 때까지 기다린다. 끝났으면 True"""
        ms = INFINITE if timeout is None else int(timeout * 1000)
        return _k.WaitForSingleObject(self._proc.hProcess, ms) == WAIT_OBJECT_0

    @property
    def exit_code(self) -> int | None:
        code = w.DWORD()
        if not self._proc.hProcess or not _k.GetExitCodeProcess(self._proc.hProcess, ctypes.byref(code)) or code.value == 259:
            return None   # 259 = STILL_ACTIVE
        return int(code.value)

    def active_processes(self) -> int:
        """작업 개체 안에서 돌고 있는 프로세스 수 (셸 + 셸에서 띄운 프로그램)"""
        info = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not self._job or not _k.QueryInformationJobObject(self._job, JOB_BASIC_ACCOUNTING, ctypes.byref(info),
                                                             ctypes.sizeof(info), None):
            return 0
        return int(info.ActiveProcesses)

    def job_pids(self) -> list[int]:
        """작업 개체 안의 프로세스 id 들 (셸 포함)"""
        n = 64
        while True:
            # JOBOBJECT_BASIC_PROCESS_ID_LIST: DWORD 두 개(맡은 수·목록의 수) 다음에 ULONG_PTR 목록 — 앞의 두 DWORD 가 size_t 한 칸
            buf = (ctypes.c_size_t * (1 + n))()
            with self._lock:
                if self._closed or not self._job:
                    return []
                ok = _k.QueryInformationJobObject(self._job, JOB_PROCESS_ID_LIST, buf, ctypes.sizeof(buf), None)
            if ok:
                count = buf[0] >> 32
                return [int(pid) for pid in buf[1:1 + count]]
            if ctypes.get_last_error() != ERROR_MORE_DATA or n >= 4096:
                return []
            n *= 4

    def stuck_children(self, min_age: float) -> list[dict[str, object]]:
        """시작하다 멈춘 프로그램 [{pid, name}] (D58): 만들어진 지 min_age 초가 넘도록 로더가 한 번도 돌지 않았고(모듈 0개)
        스레드가 모두 일시 정지인 것. 보안 프로그램(DRM)의 커널 드라이버가 프로세스 생성을 막으면 이렇게 남고, 그것을 띄운
        프로그램(git 을 띄운 Claude Code 등)은 CreateProcess 안에서 끝없이 기다린다. 읽기만 한다 — 끝내는 것은 다시 시작(작업 개체째)"""
        pids = self.job_pids()
        self._loaded &= set(pids)
        now = w.FILETIME()
        _k.GetSystemTimeAsFileTime(ctypes.byref(now))
        candidates: dict[int, str] = {}
        for pid in pids:
            if pid in self._loaded or pid == self.pid:
                continue
            state = _process_state(pid)
            if state is None:
                continue
            created, exe, ran = state
            if ran:
                self._loaded.add(pid)
            elif (_filetime(now) - created) / 1e7 >= min_age:
                candidates[pid] = exe
        if not candidates:
            return []
        stuck = _all_suspended(set(candidates))
        return [{'pid': pid, 'name': candidates[pid]} for pid in sorted(stuck)]

    def terminate(self) -> None:
        """셸과 셸에서 띄운 프로그램을 끝낸다 (wait() 가 돌아온다). 정리는 그 뒤 close() 로 — 기다리는 핸들을 닫지 않게"""
        with self._lock:
            if not self._closed and self._job:
                _k.TerminateJobObject(self._job, 1)

    def close(self) -> None:
        """셸과 셸에서 띄운 프로그램을 끝내고 의사 콘솔을 닫는다. 여러 번 불러도 된다. 읽는 핸들은 close_output() 이 닫는다.
        다른 스레드가 wait() 로 기다리는 중에는 부르지 않는다 (terminate() 를 쓴다)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self._job:
            _k.TerminateJobObject(self._job, 1)
        if self._hpc:
            _k.ClosePseudoConsole(self._hpc)   # 남은 출력을 내보내고 파이프를 닫는다 → read() 가 b''
            self._hpc = w.HANDLE()
        for handle in (self._in, self._proc.hThread, self._proc.hProcess, self._job):
            if handle:
                _k.CloseHandle(handle)
        self._in = w.HANDLE()
        self._proc.hThread = self._proc.hProcess = None
        self._job = None

    def close_output(self) -> None:
        """읽는 스레드가 b'' 를 받은 뒤 부른다"""
        if self._out:
            _k.CloseHandle(self._out)
            self._out = w.HANDLE()
