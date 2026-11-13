"""독립창 (D95): 창은 프로젝트에 속한다 — 고른 프로젝트의 창만 보이고, 프로젝트 탭을 닫으면 함께 닫힌다. 창 없이 가짜 창으로 시험한다"""
from __future__ import annotations

import time
from urllib.parse import parse_qs

import pytest

from lectern import terminal
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

    def restore(self):
        self.calls.append('restore')

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


def test_a_deck_opens_once_until_the_window_says_otherwise(setup):
    state, solos, first, _, made, *_ = setup
    a, b, c, d = 'a' * 16, 'b' * 16, 'c' * 16, 'd' * 16

    def deck(wid, path='a.md', **extra):
        return solos.open(query(first.id, wid, type='doc', path=path, deck='1', **extra))

    assert deck(a) and deck(b)
    assert list(made) == [a], '막 띄워 아직 알려 오지 않은 창도 같은 발표의 창이다'
    state.board.seen(a, first.id, '창', [])
    assert deck(b) and list(made) == [a], '문서를 불러오기 전의 빈 목록은 아직 모르는 것이다'
    state.board.seen(a, first.id, '창', ['다른.md'])
    assert deck(c) and list(made) == [a, c], '다른 문서로 갔으면 이 발표의 창은 없다'
    state.board.seen(c, first.id, '창', ['a.md', 'b.md'])
    assert deck(d, 'b.md', line='12') and list(made) == [a, c], '창이 알려 온 문서면 그 창으로'
    assert state.board.take(c) == [{'type': 'doc', 'path': 'b.md', 'line': 12}]


def test_a_rename_reaches_the_windows_of_that_project(setup):
    state, _, first, second, *_ = setup
    state.board.seen('a' * 16, first.id, '창')
    state.board.seen('b' * 16, second.id, '창')
    state.board.renamed(first.id, 'a.md', 'b.md')
    item = {'type': 'renamed', 'path': 'a.md', 'to': 'b.md', 'p': first.id}
    assert state.board.take('a' * 16) == [item] and state.board.take('') == [item]
    assert state.board.take('b' * 16) == [], '다른 프로젝트의 창에는 가지 않는다'


def test_moving_a_deck_tab_opens_a_new_window(setup):
    state, solos, first, _, made, *_ = setup
    assert solos.open(query(first.id, 'a' * 16, type='doc', path='a.md', deck='1'))
    state.board.seen('a' * 16, first.id, '창', ['a.md'])
    assert solos.open(query(first.id, 'b' * 16, type='doc', path='a.md', deck='1', fresh='1'))
    assert len(made) == 2


def test_front_restores_only_a_minimized_window(setup):
    _, solos, first, _, made, *_ = setup
    wid = 'a' * 16
    solos.open(query(first.id, wid))

    def brought(minimized):
        made[wid].calls.clear()
        solos._solos[wid].minimized = minimized
        solos.front(wid)
        for _ in range(100):
            if 'show' in made[wid].calls:
                break
            time.sleep(0.01)
        return made[wid].calls

    assert brought(True) == ['restore', 'show']
    assert brought(False) == ['show'], '최대화한 창이 줄어들지 않게 restore 는 최소화한 창에만'


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


def relay_app(tmp_path):
    (tmp_path / 'a.md').write_text('# 가', encoding='utf-8')
    state = AppState(Config(tmp_path / 'config.json'), mode='browser')
    state.open(tmp_path, remember=False)
    return state, create_app(state).test_client(), {'X-Term': state.term_secret}


@pytest.mark.skipif(not terminal.AVAILABLE, reason='Windows 의사 콘솔(ConPTY)이 있어야 한다')
def test_terminal_relay_is_guarded_like_the_terminal(tmp_path):
    state, c, secret = relay_app(tmp_path)
    told = []
    state.on_send = told.append
    try:
        body = {'p': 'p1', 'text': '@a.md 1행 ', 'stay': False}
        assert c.post('/api/term/relay', json=body).status_code == 403   # 비밀값 없이는 안 된다
        assert c.post('/api/term/relay', json=body, headers={'X-Term': 'x'}).status_code == 403
        other_site = {**secret, 'Origin': 'http://evil.example'}
        assert c.post('/api/term/relay', json=body, headers=other_site).status_code == 403
        assert 'inbox' not in c.get('/api/changes').get_json()
        assert c.post('/api/term/relay', json=body, headers=secret).get_json()['ok'] and told == ['']
        assert c.get('/api/changes').get_json()['inbox'] == [{'term': '@a.md 1행 ', 'p': 'p1', 'stay': False}]
        c.post('/api/term/relay', json={**body, 'stay': True}, headers=secret)
        assert told == ['']   # 머무는 길은 메인 창을 앞으로 가져오지 않는다
        c.get('/api/changes')
        assert c.post('/api/term/relay', json={**body, 'text': 'x' * 65537}, headers=secret).status_code == 413
        assert c.post('/api/term/relay', json={**body, 'text': 1}, headers=secret).status_code == 400
        c.post('/api/term/relay', json={**body, 'stay': True, 'n': 2}, headers=secret)   # 받을 터미널의 번호 (D137)
        assert c.get('/api/changes').get_json()['inbox'] == [{'term': '@a.md 1행 ', 'p': 'p1', 'stay': True, 'n': 2}]
        for bad in (5, -1, '2', True, 1.0):
            assert c.post('/api/term/relay', json={**body, 'n': bad}, headers=secret).status_code == 400
    finally:
        state.close()


def test_document_route_cannot_carry_terminal_text(tmp_path):
    """문서를 보내는 길로는 셸에 글자를 보낼 수 없다 — 받은 칸만 다시 적는다"""
    state, c, _ = relay_app(tmp_path)
    try:
        c.post('/api/window-send', json={'to': '', 'type': 'doc', 'path': 'a.md', 'term': 'rm -rf', 'note': {'body': 'x'}, 'stay': True})
        c.post('/api/window-note', json={'p': 'p1', 'note': {'body': '글', 'line': 3, 'term': 'rm -rf', 'end': True}})
        assert c.get('/api/changes').get_json()['inbox'] == [{'type': 'doc', 'path': 'a.md', 'top': 0}, {'note': {'body': '글', 'line': 3}, 'p': 'p1'}]
    finally:
        state.close()
