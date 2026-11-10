"""업무 관리 (D124): WORK.md 가 있는 폴더를 기억하고, 그 파일 하나만 읽고, 고른 파일에만 쓴다"""
from __future__ import annotations

import os
import time

import pytest

from conftest import write
from lectern import paths, work
from lectern.config import Config
from lectern.editing import EditError
from lectern.server import create_app
from lectern.state import AppState

CARD = '---\nstatus: 진행\npriority: 상\ndue: 2026-12-15\n---\n\n# 시장분석\n\n## 일정\n\n- 2026-11-12 14:00 팀장 보고\n'


@pytest.fixture
def state():
    st = AppState(Config(), mode='browser')
    yield st
    st.close()


@pytest.fixture
def client(state):
    return create_app(state).test_client()


def folder(tmp_path, name, card=CARD):
    root = tmp_path / name
    write(root / 'README.md', '# 다른 문서\n')
    if card is not None:
        write(root / 'WORK.md', card)
    return root.resolve()


def test_opening_a_folder_with_work_md_remembers_it(state, tmp_path):
    a = folder(tmp_path, 'a')
    b = folder(tmp_path, 'b', card=None)
    state.open(a)
    state.open(b)
    assert state.config.get('work_folders') == [str(a)]
    state.open(a)   # 다시 열어도 한 번만
    assert state.config.get('work_folders') == [str(a)]


def test_the_program_folder_is_never_remembered(state, tmp_path, monkeypatch):
    a = folder(tmp_path, 'a')
    monkeypatch.setattr(paths, 'is_protected', lambda p: True)
    state.open(a)
    assert state.config.get('work_folders') == []


def test_the_board_reads_closed_folders_too(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    project = state.open(a)
    state.close_tab(project.id)
    got = client.get('/api/work').get_json()
    assert got['home'] is None and got['alerts'] is True
    (card,) = got['folders']
    assert card['path'] == str(a) and card['name'] == 'a' and card['text'] == CARD and card['hash']


def test_the_board_reads_only_work_md(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    state.config.add_work_folder(str(a))
    got = client.get('/api/work').get_json()
    assert '다른 문서' not in str(got)


def test_missing_folders_and_cards_say_so(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    b = folder(tmp_path, 'b')
    state.config.add_work_folder(str(a))
    state.config.add_work_folder(str(b))
    (b / 'WORK.md').unlink()
    for p in a.iterdir():
        p.unlink()
    a.rmdir()
    got = {f['name']: f for f in client.get('/api/work').get_json()['folders']}
    assert got['a']['error'] == 'missing-folder' and got['b']['error'] == 'missing-card'


def test_a_hidden_or_linked_card_is_not_read(tmp_path):
    a = folder(tmp_path, 'a')
    target = tmp_path / 'elsewhere.md'
    write(target, '# 밖\n')
    (a / 'WORK.md').unlink()
    try:
        os.symlink(target, a / 'WORK.md')
    except OSError:
        pytest.skip('이 PC 에서는 심볼릭 링크를 만들 수 없다')
    assert work.usable(a) is None


def test_a_slow_drive_does_not_hold_the_board(state, tmp_path, monkeypatch):
    a = folder(tmp_path, 'a')
    b = folder(tmp_path, 'b')
    state.config.add_work_folder(str(a))
    state.config.add_work_folder(str(b))
    real = work._read_one

    def slow(path):
        if path == str(a):
            time.sleep(1.0)
        return real(path)

    monkeypatch.setattr(work, '_read_one', slow)
    monkeypatch.setattr(work, 'READ_WAIT', 0.3)
    started = time.monotonic()
    got = {f['name']: f for f in work.board(state.config)['folders']}
    assert time.monotonic() - started < 0.9
    assert got['a']['error'] == 'slow' and got['b']['text'] == CARD


def test_home_is_not_a_task_and_leaves_the_list(state, client, tmp_path):
    home = folder(tmp_path, 'home', card='# 공통 업무\n\n## 일정\n')
    state.open(home)
    assert state.config.get('work_folders') == [str(home)]
    assert client.post('/api/work/home', json={'path': str(home)}).get_json() == {'home': str(home)}
    assert state.config.get('work_folders') == []
    got = client.get('/api/work').get_json()
    assert got['home']['path'] == str(home) and got['home']['text'].startswith('# 공통 업무') and got['folders'] == []
    state.open(home)   # 공통 폴더를 다시 열어도 목록에 들어가지 않는다
    assert state.config.get('work_folders') == []
    assert client.post('/api/work/home', json={'path': None}).get_json() == {'home': None}


def test_adding_a_folder(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    b = folder(tmp_path, 'b', card=None)
    got = client.post('/api/work/folders', json={'add': str(a)}).get_json()
    assert got['path'] == str(a) and got['folders'] == [str(a)]
    resp = client.post('/api/work/folders', json={'add': str(b)})
    assert resp.status_code == 404 and resp.get_json()['code'] == 'no-card'
    assert client.post('/api/work/folders', json={'add': 'relative/path'}).status_code == 400
    assert client.post('/api/work/folders', json={'remove': str(a)}).get_json()['folders'] == []
    assert (a / 'WORK.md').exists()   # 빼도 파일은 그대로


def test_the_program_folder_cannot_be_added(state, client, tmp_path, monkeypatch):
    a = folder(tmp_path, 'a')
    monkeypatch.setattr(paths, 'is_protected', lambda p: True)
    assert client.post('/api/work/folders', json={'add': str(a)}).status_code == 403
    assert client.post('/api/work/home', json={'path': str(a)}).status_code == 403


def test_writing_only_to_listed_cards(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    stranger = folder(tmp_path, 'stranger')
    state.config.add_work_folder(str(a))
    src = client.get('/api/work/card', query_string={'folder': str(a)}).get_json()
    assert src['text'] == CARD
    new = CARD + '- 2026-11-14 10:00 팀 회의\n'
    saved = client.post('/api/work/card', json={'folder': str(a), 'text': new, 'hash': src['hash']}).get_json()
    assert saved['hash'] and (a / 'WORK.md').read_text(encoding='utf-8') == new
    # 목록에 없는 폴더는 읽지도 쓰지도 않는다
    assert client.get('/api/work/card', query_string={'folder': str(stranger)}).status_code == 403
    resp = client.post('/api/work/card', json={'folder': str(stranger), 'text': 'x', 'hash': None})
    assert resp.status_code == 403 and (stranger / 'WORK.md').read_text(encoding='utf-8') == CARD


def test_writing_keeps_what_someone_else_wrote(state, client, tmp_path):
    a = folder(tmp_path, 'a')
    state.config.add_work_folder(str(a))
    src = client.get('/api/work/card', query_string={'folder': str(a)}).get_json()
    (a / 'WORK.md').write_text(CARD + '- 다른 곳에서 더함\n', encoding='utf-8')
    resp = client.post('/api/work/card', json={'folder': str(a), 'text': CARD + '- 내 일정\n', 'hash': src['hash']})
    assert resp.status_code == 409
    assert '다른 곳에서 더함' in (a / 'WORK.md').read_text(encoding='utf-8')


def test_making_a_card_remembers_the_folder(state, client, tmp_path):
    a = folder(tmp_path, 'a', card=None)
    project = state.open(a)
    assert state.config.get('work_folders') == []
    resp = client.post('/api/save', json={'p': project.id, 'path': 'WORK.md', 'text': CARD, 'create': True})
    assert resp.status_code == 200 and state.config.get('work_folders') == [str(a)]
    again = client.post('/api/save', json={'p': project.id, 'path': 'WORK.md', 'text': 'x', 'create': True})
    assert again.status_code == 409 and (a / 'WORK.md').read_text(encoding='utf-8') == CARD   # 덮어쓰지 않는다


def test_a_card_written_by_someone_else_in_an_open_tab_is_found(state, client, tmp_path):
    a = folder(tmp_path, 'a', card=None)
    state.open(a)
    write(a / 'WORK.md', CARD)   # 터미널의 Claude 가 만든 경우
    assert [f['path'] for f in client.get('/api/work').get_json()['folders']] == [str(a)]


def test_the_list_has_a_limit(tmp_path, monkeypatch):
    from lectern import config as config_module
    monkeypatch.setattr(config_module, 'MAX_WORK_FOLDERS', 2)
    cfg = Config()
    assert cfg.add_work_folder(str(tmp_path / 'a')) and cfg.add_work_folder(str(tmp_path / 'b'))
    assert not cfg.add_work_folder(str(tmp_path / 'c'))
    assert len(cfg.get('work_folders')) == 2


def test_bad_values_in_the_file_fall_back(tmp_path):
    cfg = Config()
    cfg.path.write_text('{"work_folders": "C:/x", "work_home": 3}', encoding='utf-8')
    cfg = Config()
    assert cfg.get('work_folders') == [] and cfg.get('work_home') is None
