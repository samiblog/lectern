"""오른쪽 터미널 (D38): 프로젝트 탭마다 셸(기본 Windows PowerShell 5.1) 하나를 그 프로젝트 폴더에서 띄운다.

화면(web/js/terminal.js, xterm.js)과는 HTTP 로 주고받는다: 키 입력은 POST /api/term/input, 출력은 긴 폴링 GET /api/term/read
(받은 곳 다음부터, 새 출력이 생기거나 READ_WAIT 초가 지나면 돌아온다). 출력은 셸마다 최근 MAX_KEEP 글자까지 들고 있어
화면을 다시 불러와도 이어 보인다.

- 사용자가 화면에서 열 때만 시작한다. 셸로 명령을 보내는 길은 사용자의 키 입력뿐이다 — 문서나 다른 기능에서 보내지 않는다.
- 셸은 작업 개체 안에서 돈다 (conpty.py): 탭을 닫거나 앱이 끝나면 셸에서 띄운 프로그램까지 함께 끝난다.
- 셸은 전체 경로로 띄운다 (D29 — 프로젝트 폴더의 같은 이름 프로그램이 대신 실행되지 않게). 설정 terminal_shell 로 바꾼다.
- 셸에서 띄운 프로그램이 시작하다 멈추면(보안 프로그램이 프로세스 생성을 막음 — D58) 몇 초 안에 알아채 read·info 의 stuck 으로
  알린다. 화면은 '다시 시작'을 권한다 — 멈춘 프로그램은 종료 권한이 깎여 있어 작업 개체째 끝내야 풀린다.
"""
from __future__ import annotations

import codecs
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from .conpty import AVAILABLE, PseudoConsole
from .i18n import N_, t

MAX_KEEP = 512 * 1024    # 셸마다 들고 있는 최근 출력 (글자)
MAX_READ = 256 * 1024    # 한 번에 돌려주는 출력 (글자)
READ_WAIT = 20.0         # 긴 폴링이 새 출력을 기다리는 시간 (초)
STUCK_AFTER = 10.0       # 셸에서 띄운 프로그램이 이만큼 지나도록 시작하지 못했으면 멈춘 것으로 본다 (초, D58)
STUCK_CHECK = 3.0        # 그것을 보는 간격 (초 — 셸에서 프로그램이 돌 때만)

# 앱이 실행 중에 바꾸는 환경 값(osutil 이 넣는 NoDefaultCurrentDirectoryInExePath 등)이 셸로 새지 않게, 처음 값을 쓴다
_START_ENV = dict(os.environ)


def default_shell() -> str:
    return os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')


def shell_command(configured: str | None) -> tuple[str, str]:
    """(실행 파일, 명령줄). 설정은 실제로 있는 실행 파일의 전체 경로일 때만 쓴다 (이름만이면 PATH·현재 폴더에서 찾게 된다)"""
    exe = configured if configured and Path(configured).is_absolute() and Path(configured).is_file() else default_shell()
    args = ' -NoLogo' if Path(exe).stem.lower() in ('powershell', 'pwsh') else ''
    return exe, f'"{exe}"{args}'


_LABELS = {'powershell': 'PowerShell', 'pwsh': 'PowerShell 7', 'cmd': N_('명령 프롬프트')}   # 쓰는 곳에서 t()


def shell_label(exe: str) -> str:
    """터미널 머리줄에 보일 셸 이름"""
    stem = Path(exe).stem
    return t(_LABELS.get(stem.lower(), stem))


class Session:
    """셸 하나. 읽는 스레드가 출력을 모으고, 지켜보는 스레드가 셸이 끝나면 정리한다."""

    def __init__(self, project_id: str, cwd: str, shell: str | None, cols: int, rows: int):
        self.id = secrets.token_hex(6)
        self.project_id = project_id
        self.exe, cmdline = shell_command(shell)
        self.alive = True
        self.exit_code: int | None = None
        self._buf = ''
        self._start = 0          # _buf 맨 앞 글자의 순번 (앞부분은 MAX_KEEP 을 넘으면 버린다)
        self.stuck: list[dict[str, Any]] = []   # 시작하다 멈춘 프로그램 [{pid, name}] (D58)
        self._stuck_ver = 0      # stuck 이 바뀔 때마다 늘린다 — 기다리는 read 를 깨운다
        self._cond = threading.Condition()
        self._pc = PseudoConsole(cmdline, cwd, dict(_START_ENV), cols, rows)
        self._reader = threading.Thread(target=self._read_loop, name=f'lectern-term-read-{self.id}', daemon=True)
        self._reader.start()
        threading.Thread(target=self._watch, name=f'lectern-term-watch-{self.id}', daemon=True).start()
        threading.Thread(target=self._check_stuck, name=f'lectern-term-stuck-{self.id}', daemon=True).start()

    @property
    def end(self) -> int:
        return self._start + len(self._buf)

    def _append(self, text: str) -> None:
        if not text:
            return
        with self._cond:
            self._buf += text
            if len(self._buf) > MAX_KEEP:
                cut = len(self._buf) - MAX_KEEP
                self._buf = self._buf[cut:]
                self._start += cut
            self._cond.notify_all()

    def _read_loop(self) -> None:
        decoder = codecs.getincrementaldecoder('utf-8')('replace')   # 한 글자가 두 번에 나뉘어 와도 이어 붙인다
        while True:
            chunk = self._pc.read()
            if not chunk:
                break
            self._append(decoder.decode(chunk))
        self._append(decoder.decode(b'', final=True))
        self._pc.close_output()

    def _watch(self) -> None:
        self._pc.wait()
        self.exit_code = self._pc.exit_code
        self._pc.close()            # 남은 출력을 내보내고 의사 콘솔을 닫는다 → 읽는 스레드가 끝난다
        self._reader.join(timeout=5)
        with self._cond:
            self.alive = False
            self._cond.notify_all()

    def _check_stuck(self) -> None:
        """셸에서 띄운 프로그램 중 시작하다 멈춘 것을 STUCK_CHECK 초마다 찾는다 (D58). 바뀌면 기다리는 read 를 깨운다"""
        while True:
            with self._cond:
                if self._cond.wait_for(lambda: not self.alive, STUCK_CHECK):
                    return
            try:
                found = self._pc.stuck_children(STUCK_AFTER) if self._pc.active_processes() > 1 else []
            except OSError:
                found = []
            with self._cond:
                if found != self.stuck:
                    self.stuck = found
                    self._stuck_ver += 1
                    self._cond.notify_all()

    def read(self, since: int, timeout: float = READ_WAIT) -> dict[str, Any]:
        """since(받은 곳) 다음의 출력. 없으면 새 출력이 생기거나 셸이 끝나거나 멈춘 프로그램(stuck)이 바뀌거나 timeout 이
        지날 때까지 기다린다. since 가 버린 앞부분이면 남은 맨 앞부터 주고 reset 을 단다."""
        with self._cond:
            ver = self._stuck_ver
            self._cond.wait_for(lambda: self.end > since or not self.alive or self._stuck_ver != ver, timeout)
            reset = since < self._start
            begin = max(since, self._start) - self._start
            data = self._buf[begin:begin + MAX_READ]
            return {'data': data, 'next': self._start + begin + len(data), 'reset': reset,
                    'alive': self.alive or self.end > self._start + begin + len(data), 'exit': self.exit_code,
                    'stuck': self.stuck}

    def write(self, text: str) -> None:
        if self.alive:
            self._pc.write(text.encode('utf-8', 'replace'))   # 짝이 맞지 않는 대리 문자는 '?' 로

    def resize(self, cols: int, rows: int) -> None:
        if self.alive:
            self._pc.resize(cols, rows)

    def busy(self) -> bool:
        """셸에서 띄운 프로그램이 돌고 있는지 (탭을 닫기 전에 묻는다)"""
        return self.alive and self._pc.active_processes() > 1

    def close(self) -> None:
        """셸과 셸에서 띄운 프로그램을 끝낸다. 정리는 지켜보는 스레드가 한다"""
        self._pc.terminate()


class Terminals:
    """열린 셸들. 프로젝트(탭)마다 하나 — 이미 돌고 있으면 그것을 쓴다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}

    @property
    def available(self) -> bool:
        return AVAILABLE

    def open(self, project_id: str, cwd: str, shell: str | None, cols: int, rows: int) -> Session:
        with self._lock:
            for s in self._sessions.values():
                if s.project_id == project_id and s.alive:
                    return s
            for sid in [sid for sid, s in self._sessions.items() if s.project_id == project_id]:
                del self._sessions[sid]   # 끝난 셸
            session = Session(project_id, cwd, shell, cols, rows)
            self._sessions[session.id] = session
            return session

    def get(self, sid: Any) -> Session | None:
        return self._sessions.get(sid) if isinstance(sid, str) else None

    def close(self, sid: str) -> None:
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session:
            session.close()

    def close_project(self, project_id: str) -> None:
        with self._lock:
            ids = [sid for sid, s in self._sessions.items() if s.project_id == project_id]
        for sid in ids:
            self.close(sid)

    def close_all(self) -> None:
        with self._lock:
            ids = list(self._sessions)
        for sid in ids:
            self.close(sid)
