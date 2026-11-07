"""독립창 (D95): 프로젝트의 문서를 별도 창에서 본다.

창은 프로젝트에 속한다 — 메인 창에서 다른 프로젝트를 고르면 숨고, 돌아오면 그대로 다시 보인다. 같은 서버·같은 화면(web/)을 쓰고
주소의 ?solo=<프로젝트 id>&w=<창 id> 만 다르다 (web/js/solo.js). 닫으면 끝이고 다음 실행에 되살리지 않는다.
메인 창을 닫으면 모두 닫고, 프로젝트 탭을 닫으면 그 프로젝트의 창을 닫는다.

창끼리는 바로 말할 수 없어 문서는 서버를 거쳐 보낸다 (WindowBoard — 받는 창은 1초마다 도는 /api/changes 로 가져간다).
pywebview 에 닿는 것은 부르는 쪽(app.py)이 준 create 뿐이라 창 없이 시험할 수 있다.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import parse_qs, urlencode

if TYPE_CHECKING:
    from .state import AppState

MAX_WINDOWS = 8
WINDOW_ID = re.compile(r'[0-9a-f]{8,32}')
START_KEYS = ('type', 'path', 'top', 'hash', 'line', 'deck')   # 주소에 실어 보내는 첫 화면 (solo.js)
MAIN = ''   # 메인 창의 창 id


class WindowBoard:
    """창들이 서로 알고 문서를 보내는 곳. 메인 창은 늘 있는 것으로 본다 — 최소화하면 확인이 멈추지만 돌아오면 가져간다"""

    def __init__(self) -> None:
        self._seen: dict[str, dict[str, str]] = {}
        self._decks: dict[str, list[str]] = {}   # 창이 지금 연 발표들 — 한 번이라도 알려 온 창만 (불러오기 전의 빈 목록은 모르는 것)
        self._inbox: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def seen(self, wid: str, project: str, title: str, decks: list[str] | None = None) -> None:
        with self._lock:
            self._seen[wid] = {'id': wid, 'project': project, 'title': title[:80]}
            if decks or wid in self._decks:
                self._decks[wid] = decks or []

    def told(self, wid: str) -> bool:
        """이 창이 연 발표를 알려 왔는지 — 그 뒤로는 처음 연 문서가 아니라 알려 온 목록을 믿는다"""
        with self._lock:
            return wid in self._decks

    def holder(self, project: str, path: str) -> str | None:
        """이 발표를 지금 연 창 (D96 — 창이 알려 온 것. 처음 연 문서가 아니라 지금 문서라야 그 창이 보여 줄 수 있다)"""
        with self._lock:
            return next((k for k, decks in self._decks.items() if path in decks and self._seen.get(k, {}).get('project') == project), None)

    def others(self, wid: str) -> list[dict[str, str]]:
        with self._lock:
            return [w for k, w in self._seen.items() if k != wid]

    def send(self, to: str, item: dict[str, Any]) -> bool:
        """to 의 창으로 문서를 보낸다. 그 창이 없으면 False"""
        with self._lock:
            if to != MAIN and to not in self._seen:
                return False
            self._inbox.setdefault(to, []).append(item)
            return True

    def renamed(self, project: str, path: str, to: str) -> None:
        """파일 이름이 바뀌었다 — 그 파일을 연 다른 창이 '없는 파일'이 되지 않게 모든 창에 알린다 (바꾼 창에는 할 일이 없다)"""
        item = {'type': 'renamed', 'path': path, 'to': to, 'p': project}
        with self._lock:
            for wid in {MAIN, *(k for k, w in self._seen.items() if w['project'] == project)}:
                self._inbox.setdefault(wid, []).append(item)

    def deleted(self, project: str, path: str) -> None:
        """문서를 휴지통으로 보냈다 — 그 문서를 연 다른 창이 칸을 닫게 모든 창에 알린다 (보낸 창은 이미 닫았으니 받아도 할 일이 없다)"""
        item = {'type': 'deleted', 'path': path, 'p': project}
        with self._lock:
            for wid in {MAIN, *(k for k, w in self._seen.items() if w['project'] == project)}:
                self._inbox.setdefault(wid, []).append(item)

    def take(self, wid: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._inbox.pop(wid, [])

    def forget(self, wid: str) -> None:
        with self._lock:
            self._seen.pop(wid, None)
            self._decks.pop(wid, None)
            self._inbox.pop(wid, None)


@dataclass
class Solo:
    id: str
    project: str
    window: Any = None
    visible: bool = True
    deck: str = ''   # 슬라이드 창이면 그 Lectern 슬라이드의 경로 (D96)
    minimized: bool = False


class SoloWindows:
    def __init__(self, state: AppState, create: Callable[[str, str], Any], confirm: Callable[[list[str]], bool], main: Any = None):
        """create(주소의 뒤쪽, 창 id): 창을 만들어 돌려준다. confirm(파일들): 저장하지 않은 편집을 버려도 되는지 묻는다"""
        self._state = state
        self._create = create
        self._confirm = confirm
        self._main = main
        self.bring_main: Callable[[], None] | None = None   # 메인 창을 앞으로 (최소화돼 있으면 되돌린다 — app.py)
        self._solos: dict[str, Solo] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self.quitting = False   # 메인 창이 닫히는 중 — 이미 물었다

    def start(self) -> None:
        """프로젝트를 고를 때 창을 숨기고 보이는 스레드. 창 호출은 창이 뜰 때까지 기다릴 수 있어 요청을 붙들지 않게 따로 돈다"""
        threading.Thread(target=self._run, name='lectern-windows', daemon=True).start()

    def _run(self) -> None:
        while True:
            self._wake.wait()
            self._wake.clear()
            self.apply()

    def wake(self) -> None:
        self._wake.set()

    def open(self, query: str) -> bool:
        """독립창을 띄운다. query 는 화면이 만든 주소의 뒤쪽 — 아는 값만 다시 만들어 쓴다"""
        fields = parse_qs(str(query).lstrip('?'))
        pid = fields.get('solo', [''])[0]
        wid = fields.get('w', [''])[0]
        if self._state.get(pid) is None or not WINDOW_ID.fullmatch(wid):
            return False
        deck = fields.get('path', [''])[0] if fields.get('deck', [''])[0] == '1' else ''
        board = self._state.board
        held = board.holder(pid, deck) if deck and 'fresh' not in fields else None
        with self._lock:
            same = self._solos.get(held) if held else None
            if same is None and deck and 'fresh' not in fields:   # 막 띄워 아직 알려 오지 않은 창
                same = next((s for s in self._solos.values() if s.deck == deck and s.project == pid and not board.told(s.id)), None)
            if same is None:
                if len(self._solos) >= MAX_WINDOWS or wid in self._solos:
                    return False
                solo = self._solos[wid] = Solo(wid, pid, deck=deck)
        if same is not None:   # 이 발표의 슬라이드 창이 이미 있다 — 그 문서를 보이고 창을 앞으로
            jump = {k: fields[k][0] for k in ('hash', 'line') if k in fields}
            board.send(same.id, {'type': 'doc', 'path': deck, **({'line': int(jump['line'])} if jump.get('line', '').isdigit() else {}), **({'hash': jump['hash']} if 'hash' in jump else {})})
            self.front(same.id)
            return True
        start = {k: fields[k][0] for k in START_KEYS if k in fields}
        try:
            solo.window = self._create('?' + urlencode({'solo': pid, 'w': wid, **start}), wid)
        except Exception:
            self.forget(wid)
            return False
        events = getattr(solo.window, 'events', None)
        if events:   # 창이 스스로 알려 주지 않는다 (app.py 의 메인 창과 같다)
            events.minimized += lambda: setattr(solo, 'minimized', True)
            events.maximized += lambda: setattr(solo, 'minimized', False)
            events.restored += lambda: setattr(solo, 'minimized', False)
        return True

    def forget(self, wid: str) -> None:
        """창이 닫혔다"""
        with self._lock:
            self._solos.pop(wid, None)
        self._state.set_unsaved(wid, [])
        self._state.board.forget(wid)

    def front(self, wid: str) -> None:
        """문서를 받는 창을 앞으로 — 요청을 붙들지 않게 따로"""
        with self._lock:
            solo = self._solos.get(wid)
        window = solo.window if solo else None

        def bring() -> None:
            if solo.minimized:   # 보이기만으로는 돌아오지 않는다. 최대화한 창에 restore 를 부르면 줄어든다
                window.restore()
            window.show()

        show = self.bring_main if wid == MAIN else (bring if window else None)
        if show:
            threading.Thread(target=show, name='lectern-windows-front', daemon=True).start()

    def _of(self, pid: str | None = None) -> list[Solo]:
        with self._lock:
            return [s for s in self._solos.values() if pid is None or s.project == pid]

    def apply(self) -> None:
        """선택된 프로젝트의 창만 보이게 한다. 보이는 창은 앞으로 나오므로 고른 쪽인 메인 창을 다시 앞으로"""
        active = self._state.active
        shown = False
        for solo in self._of():
            want = solo.project == active
            if want == solo.visible or solo.window is None:
                continue
            try:
                (solo.window.show if want else solo.window.hide)()
            except Exception:
                continue   # 그사이 닫힘
            solo.visible = want
            shown = shown or want
        if shown and self._main is not None:
            self._main.show()

    def may_close(self, pid: str) -> bool:
        """프로젝트 탭을 닫아도 되는지 — 그 프로젝트의 독립창에 저장하지 않은 편집이 있으면 묻는다"""
        files = [p for solo in self._of(pid) for p in self._state.unsaved_by.get(solo.id, [])]
        return not files or self._confirm(files)

    def project_closed(self, pid: str) -> None:
        """프로젝트 탭이 닫혔다 — 그 창들도. 묻는 것은 may_close 에서 끝났다"""
        self._destroy(self._of(pid))

    def close_all(self) -> None:
        self._destroy(self._of())

    def _destroy(self, solos: list[Solo]) -> None:
        for solo in solos:
            self._state.set_unsaved(solo.id, [])

        def run() -> None:
            for solo in solos:
                try:
                    solo.window.destroy()
                except Exception:
                    pass   # 그사이 닫힘

        threading.Thread(target=run, name='lectern-windows-close', daemon=True).start()
