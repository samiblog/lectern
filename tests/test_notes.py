"""프로젝트 메모 (D92): .lectern/notes.md 를 쓸 때만 만들고, 그 자리 하나에만 쓴다"""
from __future__ import annotations

import os

import pytest

from lectern import notes, paths
from lectern.config import Config
from lectern.editing import EditError
from lectern.server import create_app
from lectern.state import AppState


@pytest.fixture
def state(project):
    st = AppState(Config(), mode='browser')
    st.open(project)
    yield st
    st.close()


@pytest.fixture
def client(state):
    return create_app(state).test_client()


@pytest.fixture
def pid(state):
    return state.active


def test_reading_creates_nothing(tmp_path):
    assert notes.read_notes(tmp_path) == {'text': '', 'hash': None, 'exists': False}
    assert not (tmp_path / '.lectern').exists()


def test_first_save_creates_the_folder_and_file(tmp_path):
    saved = notes.save_notes(tmp_path, '메모\n', None)
    target = tmp_path / '.lectern' / 'notes.md'
    assert target.read_text(encoding='utf-8') == '메모\n'
    got = notes.read_notes(tmp_path)
    assert got['text'] == '메모\n' and got['exists'] and got['hash'] == saved['hash']


def test_save_keeps_what_someone_else_wrote(tmp_path):
    first = notes.save_notes(tmp_path, '가\n', None)
    (tmp_path / '.lectern' / 'notes.md').write_text('다른 곳에서 고침\n', encoding='utf-8')
    with pytest.raises(EditError) as err:
        notes.save_notes(tmp_path, '나\n', first['hash'])
    assert err.value.status == 409
    assert (tmp_path / '.lectern' / 'notes.md').read_text(encoding='utf-8') == '다른 곳에서 고침\n'


def test_a_file_that_appeared_meanwhile_is_not_overwritten(tmp_path):
    (tmp_path / '.lectern').mkdir()
    (tmp_path / '.lectern' / 'notes.md').write_text('있던 글\n', encoding='utf-8')
    with pytest.raises(EditError) as err:
        notes.save_notes(tmp_path, '새 글\n', None)
    assert err.value.status == 409


def test_a_file_deleted_meanwhile_asks_to_read_again(tmp_path):
    first = notes.save_notes(tmp_path, '가\n', None)
    (tmp_path / '.lectern' / 'notes.md').unlink()
    with pytest.raises(EditError) as err:
        notes.save_notes(tmp_path, '나\n', first['hash'])
    assert err.value.status == 409


def test_nothing_is_written_inside_the_program_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'is_protected', lambda p: True)
    with pytest.raises(EditError) as err:
        notes.save_notes(tmp_path, '가\n', None)
    assert err.value.status == 403
    assert not (tmp_path / '.lectern').exists()


def test_a_linked_folder_is_refused(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'root'
    root.mkdir()
    try:
        os.symlink(outside, root / '.lectern', target_is_directory=True)
    except OSError:
        pytest.skip('심볼릭 링크를 만들 권한이 없음')
    assert notes.read_notes(root)['exists'] is False
    with pytest.raises(EditError) as err:
        notes.save_notes(root, '가\n', None)
    assert err.value.status == 403
    assert not list(outside.iterdir())


def test_the_api_reads_and_saves(client, project, pid):
    assert client.get(f'/api/notes?p={pid}').get_json()['exists'] is False
    r = client.post('/api/notes', json={'p': pid, 'text': '메모\n', 'hash': None})
    assert r.status_code == 200
    got = client.get(f'/api/notes?p={pid}').get_json()
    assert got['text'] == '메모\n' and got['hash'] == r.get_json()['hash']
    stale = client.post('/api/notes', json={'p': pid, 'text': '다른 글\n', 'hash': 'x'})
    assert stale.status_code == 409 and (project / '.lectern' / 'notes.md').read_text(encoding='utf-8') == '메모\n'


def test_the_api_takes_no_path(client, project, pid):
    client.post('/api/notes', json={'p': pid, 'text': '메모\n', 'hash': None, 'path': '../밖.md'})
    assert (project / '.lectern' / 'notes.md').exists() and not (project.parent / '밖.md').exists()


def test_the_notes_stay_out_of_the_tree_and_search(client, project, pid):
    client.post('/api/notes', json={'p': pid, 'text': '숨은찾을말\n', 'hash': None})
    assert b'notes.md' not in client.get(f'/api/tree?p={pid}').data
    assert not client.get(f'/api/search?p={pid}&q=숨은찾을말').get_json()['results']
    assert client.get(f'/doc/{pid}/.lectern/notes.md').status_code == 404
