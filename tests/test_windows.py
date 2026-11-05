"""독립창 (D95): 창은 프로젝트에 속한다 — 고른 프로젝트의 창만 보이고, 프로젝트 탭을 닫으면 함께 닫힌다. 창 없이 가짜 창으로 시험한다"""
from __future__ import annotations

import time
from urllib.parse import parse_qs

import pytest

from lectern.config import Config
from lectern.state import AppState
from lectern.server import create_app
from lectern.windows import MAX_WINDOWS, SoloWindows, WindowBoard


class FakeWindow:
    def __init__(self, query):
        self.query = query
        self.calls = []

    def show(self):
        self.calls.append('show')

    def hide(self):
        self.calls.append('hide')

    def destroy(self):
        self.calls.append('destroy')


@pytest.fixture
def setup(tmp_path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    state = AppState(Config(tmp_path / 'config.json'))
    first = state.open(tmp_path / 'a', remember=False)
    second = state.open(tmp_path / 'b', remember=False)
    made, asked = {}, []

    def create(query, wid):
        made[wid] = FakeWindow(query)
        return made[wid]

    def confirm(files):
        asked.append(files)
        return confirm.answer

    confirm.answer = True
    main = FakeWindow('main')
    solos = SoloWindows(state, create, confirm, main)
    yield state, solos, first, second, made, asked, confirm, main
    state.close_all() if hasattr(state, 'close_all') else [p.stop() for p in state.projects.values()]


def query(pid, wid='0123456789abcdef', **extra):
    rest = ''.join(f'&{k}={v}' for k, v in extra.items())
    return f'?solo={pid}&w={wid}{rest}'


def test_opens_only_for_an_open_project(setup):
    _, solos, first, *_ = setup
    assert solos.open(query(first.id, type='doc', path='a.md', top='12'))
    assert not solos.open(query('none', 'aaaaaaaaaaaaaaaa'))
    assert not solos.open(query(first.id))   # 같은 창 id
    assert not solos.open(f'?solo={first.id}&w=../x')
    assert not solos.open('')


def test_address_is_rebuilt_from_known_fields(setup):
    _, solos, first, _, made, *_ = setup
    solos.open(query(first.id, type='doc', path='a b.md', top='5', evil='1'))
    fields = parse_qs(next(iter(made.values())).query.lstrip('?'))
    assert set(fields) == {'solo', 'w', 'type', 'path', 'top'} and fields['path'] == ['a b.md']


def test_window_count_is_limited(setup):
    _, solos, first, *_ = setup
    for i in range(MAX_WINDOWS):
        assert solos.open(query(first.id, f'{i:016x}'))
    assert not solos.open(query(first.id, 'f' * 16))


def test_failed_window_leaves_no_trace(setup):
    state, solos, first, *_ = setup
    solos._create = lambda *_: (_ for _ in ()).throw(RuntimeError('창'))
    assert not solos.open(query(first.id))
    assert solos._of() == []


def test_only_the_active_projects_windows_are_shown(setup):
    state, solos, first, second, made, _, _, main = setup
    solos.open(query(first.id, 'a' * 16))
    solos.open(query(second.id, 'b' * 16))
    state.activate(second.id)
    solos.apply()
    assert made['a' * 16].calls == ['hide'] and made['b' * 16].calls == []
    assert main.calls == []   # 숨기기만 했으면 메인 창은 그대로
    state.activate(first.id)
    solos.apply()
    assert made['a' * 16].calls == ['hide', 'show'] and made['b' * 16].calls == ['hide']
    assert main.calls == ['show']   # 보인 창이 앞으로 나오니 메인 창을 다시 앞으로


def test_apply_changes_nothing_twice(setup):
    state, solos, first, second, made, *_ = setup
    solos.open(query(first.id, 'a' * 16))
    state.activate(second.id)
    solos.apply()
    solos.apply()
    assert made['a' * 16].calls == ['hide']


def test_selecting_a_project_wakes_the_windows(setup):
    state, solos, first, second, *_ = setup
    woken = []
    state.on_active = lambda: woken.append(state.active)
    state.activate(first.id)
    state.activate(first.id)   # 그대로면 알리지 않는다
    state.activate(second.id)
    assert woken == [first.id, second.id]


def test_a_window_that_is_gone_does_not_stop_the_rest(setup):
    state, solos, first, second, made, *_ = setup
    solos.open(query(first.id, 'a' * 16))
    solos.open(query(first.id, 'b' * 16))
    made['a' * 16].hide = lambda: (_ for _ in ()).throw(RuntimeError('닫힘'))
    state.activate(second.id)
    solos.apply()
    assert made['b' * 16].calls == ['hide']


def wait_destroyed(window):
    for _ in range(100):
        if 'destroy' in window.calls:
            return True
        time.sleep(0.01)
    return False


def test_closing_a_project_closes_its_windows_only(setup):
    state, solos, first, second, made, *_ = setup
    state.on_closed = solos.project_closed
    solos.open(query(first.id, 'a' * 16))
    solos.open(query(second.id, 'b' * 16))
    state.close_tab(first.id)
    assert wait_destroyed(made['a' * 16])
    assert 'destroy' not in made['b' * 16].calls


def test_close_all(setup):
    _, solos, first, second, made, *_ = setup
    solos.open(query(first.id, 'a' * 16))
    solos.open(query(second.id, 'b' * 16))
    solos.close_all()
    assert all(wait_destroyed(w) for w in made.values())


def test_unsaved_edits_are_per_window(setup):
    state, solos, first, second, _, asked, confirm, _ = setup
    solos.open(query(first.id, 'a' * 16))
    state.set_unsaved('', ['main.md'])
    state.set_unsaved('a' * 16, ['solo.md'])
    assert state.unsaved == ['main.md', 'solo.md']
    confirm.answer = False
    assert solos.may_close(second.id) and asked == []   # 그 프로젝트의 창이 아니면 묻지 않는다
    assert not solos.may_close(first.id) and asked == [['solo.md']]
    confirm.answer = True
    assert solos.may_close(first.id)
    solos.forget('a' * 16)
    assert state.unsaved == ['main.md']


def test_board_passes_documents_between_windows():
    board = WindowBoard()
    board.seen('', '', '메인')
    board.seen('a', 'p', '가.md')
    assert board.others('') == [{'id': 'a', 'project': 'p', 'title': '가.md'}]
    assert [w['id'] for w in board.others('a')] == ['']
    assert board.send('a', {'path': 'x'}) and not board.send('none', {'path': 'x'})
    assert board.take('a') == [{'path': 'x'}] and board.take('a') == []
    board.forget('a')
    assert board.others('') == [] and not board.send('a', {'path': 'x'})


def test_main_window_always_receives():
    """메인 창은 최소화하면 확인이 멈춘다 — 돌아와서 가져가도록 받아 둔다"""
    board = WindowBoard()
    assert board.send('', {'path': 'x'})
    assert board.take('') == [{'path': 'x'}]


def test_window_api(tmp_path):
    (tmp_path / 'a.md').write_text('# 가', encoding='utf-8')
    state = AppState(Config(tmp_path / 'config.json'), mode='browser')
    state.open(tmp_path, remember=False)
    told = []
    state.on_send = told.append
    try:
        c = create_app(state).test_client()
        assert 'windows' not in c.get('/api/changes').get_json()   # 혼자면 답이 전과 같다
        c.get('/api/changes?w=aaaaaaaa&wp=p1&wt=%EA%B0%80.md')
        assert c.get('/api/changes').get_json()['windows'] == [{'id': 'aaaaaaaa', 'project': 'p1', 'title': '가.md'}]
        sent = {'to': 'aaaaaaaa', 'type': 'doc', 'path': 'a.md', 'top': 12}
        assert c.post('/api/window-send', json=sent).get_json()['ok'] and told == ['aaaaaaaa']
        assert c.get('/api/changes?w=aaaaaaaa').get_json()['inbox'] == [{'type': 'doc', 'path': 'a.md', 'top': 12}]
        assert 'inbox' not in c.get('/api/changes?w=aaaaaaaa').get_json()
        assert not c.post('/api/window-send', json={**sent, 'to': 'none'}).get_json()['ok'] and told == ['aaaaaaaa']
        assert c.post('/api/window-send', json={**sent, 'type': 'overview'}).status_code == 400
        assert c.post('/api/window-send', json={**sent, 'to': 1}).status_code == 400
        c.post('/api/window-gone', json={'w': 'aaaaaaaa'})
        assert 'windows' not in c.get('/api/changes').get_json()
    finally:
        state.close()


def test_closing_a_window_leaves_the_board(setup):
    state, solos, first, *_ = setup
    solos.open(query(first.id, 'a' * 16))
    state.board.seen('a' * 16, first.id, '가.md')
    solos.forget('a' * 16)
    assert state.board.others('') == []


def test_front_brings_the_receiving_window(setup):
    _, solos, first, _, made, *_ = setup
    calls = []
    solos.bring_main = lambda: calls.append('main')
    solos.open(query(first.id, 'a' * 16))
    solos.front('')
    solos.front('a' * 16)
    solos.front('none')
    for _ in range(100):
        if calls and made['a' * 16].calls:
            break
        time.sleep(0.01)
    assert calls == ['main'] and made['a' * 16].calls == ['show']
