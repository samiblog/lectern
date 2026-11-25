"""담기함 (D197): .lectern/clips/ 에 담기함마다 파일 하나 — 담거나 고칠 때만 만들고, 그 폴더 안에만 쓴다"""
from __future__ import annotations

import os

import pytest

from lectern import clips, paths, trash
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


def test_reading_creates_nothing(tmp_path):
    assert clips.read_clips(tmp_path) == {'boxes': []}
    assert not (tmp_path / '.lectern').exists()


def test_create_names_the_file_after_the_title(tmp_path):
    a = clips.create_clips(tmp_path, '구리 가격: 전망?', '# 가\n')
    b = clips.create_clips(tmp_path, '구리 가격 전망', '# 나\n')
    assert (a['file'], b['file']) == ('구리-가격-전망.md', '구리-가격-전망-2.md')   # 빈칸과 못 쓰는 글자는 -, 겹치면 번호
    got = clips.read_clips(tmp_path)['boxes']
    assert [(x['file'], x['text'], x['hash']) for x in got] == [('구리-가격-전망-2.md', '# 나\n', b['hash']), ('구리-가격-전망.md', '# 가\n', a['hash'])]


@pytest.mark.parametrize('title', ['', '   ', '...', '???', 'con', 'NUL', '.숨김', 'a' * 300, '@#'])
def test_any_title_gets_a_usable_name(tmp_path, title):
    name = clips.create_clips(tmp_path, title, '# x\n')['file']
    assert clips.good_name(name) and (tmp_path / '.lectern' / 'clips' / name).is_file()


@pytest.mark.parametrize('name', [None, 3, '', '.md', 'a.txt', '../a.md', 'a/b.md', 'a\\b.md', 'C:a.md', '.hidden.md', 'con.md', 'a .md', ' a.md', 'a..md', 'a\n.md', '..md'])
def test_names_stay_inside_the_folder(tmp_path, name):
    with pytest.raises(EditError) as err:
        clips.save_clips(tmp_path, name, 'x\n', None)
    assert err.value.status == 400
    assert not (tmp_path / '.lectern').exists()


def test_save_keeps_what_someone_else_wrote(tmp_path):
    first = clips.create_clips(tmp_path, '가', '하나\n')
    path = tmp_path / '.lectern' / 'clips' / '가.md'
    again = clips.save_clips(tmp_path, '가.md', '둘\n', first['hash'])
    path.write_text('다른 곳에서 고침\n', encoding='utf-8')
    with pytest.raises(EditError) as err:
        clips.save_clips(tmp_path, '가.md', '셋\n', again['hash'])
    assert err.value.status == 409 and path.read_text(encoding='utf-8') == '다른 곳에서 고침\n'
    with pytest.raises(EditError) as err:   # 없는 줄 알았는데 있다
        clips.save_clips(tmp_path, '가.md', '넷\n', None)
    assert err.value.status == 409
    path.unlink()
    with pytest.raises(EditError) as err:   # 있던 것이 지워졌다 — 다시 읽게
        clips.save_clips(tmp_path, '가.md', '다섯\n', again['hash'])
    assert err.value.status == 409
    assert clips.save_clips(tmp_path, '가.md', '여섯\n', None)['file'] == '가.md'


def test_a_bad_file_does_not_hide_the_others(tmp_path):
    clips.create_clips(tmp_path, '가', '하나\n')
    folder = tmp_path / '.lectern' / 'clips'
    (folder / '깨짐.md').write_bytes(b'\xb0\xa1\xb3\xaa')
    (folder / 'x.txt').write_text('아님', encoding='utf-8')
    (folder / '하위').mkdir()
    got = {b['file']: 'error' in b for b in clips.read_clips(tmp_path)['boxes']}
    assert got == {'가.md': False, '깨짐.md': True}


def test_nothing_is_written_inside_the_program_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'is_protected', lambda p: True)
    for call in (lambda: clips.create_clips(tmp_path, '가', 'x'), lambda: clips.save_clips(tmp_path, '가.md', 'x', None), lambda: clips.delete_clips(tmp_path, '가.md')):
        with pytest.raises(EditError) as err:
            call()
        assert err.value.status == 403
    assert not (tmp_path / '.lectern').exists()


@pytest.mark.parametrize('level', ['.lectern', '.lectern/clips'])
def test_a_linked_folder_is_refused(tmp_path, level):
    outside = tmp_path / 'outside'
    (outside / 'clips').mkdir(parents=True)
    (outside / 'clips' / '밖.md').write_text('밖\n', encoding='utf-8')
    (outside / '밖.md').write_text('밖\n', encoding='utf-8')
    root = tmp_path / 'root'
    link = root / level
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
        else:
            link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('링크를 만들 수 없음')
    assert clips.read_clips(root) == {'boxes': []}
    for call in (lambda: clips.create_clips(root, '가', 'x'), lambda: clips.save_clips(root, '밖.md', 'x', None), lambda: clips.delete_clips(root, '밖.md')):
        with pytest.raises(EditError) as err:
            call()
        assert err.value.status == 403
    assert (outside / '밖.md').read_text(encoding='utf-8') == '밖\n' and not (outside / '가.md').exists()


def test_delete_only_goes_to_the_recycle_bin(tmp_path, monkeypatch):
    clips.create_clips(tmp_path, '가', '하나\n')
    sent = []
    monkeypatch.setattr(trash, 'send', lambda p: sent.append(p))
    clips.delete_clips(tmp_path, '가.md')
    assert sent == [tmp_path / '.lectern' / 'clips' / '가.md']
    with pytest.raises(EditError) as err:
        clips.delete_clips(tmp_path, '없음.md')
    assert err.value.status == 404

    def refuse(path):
        raise trash.TrashError('휴지통 없음')
    monkeypatch.setattr(trash, 'send', refuse)
    with pytest.raises(EditError) as err:
        clips.delete_clips(tmp_path, '가.md')
    assert err.value.status == 409 and (tmp_path / '.lectern' / 'clips' / '가.md').exists()


def test_api(client, state, project, monkeypatch):
    pid = state.active
    assert client.get(f'/api/clips?p={pid}').get_json() == {'boxes': [], 'cur': ''}
    made = client.post('/api/clips', json={'p': pid, 'title': '구리', 'text': '# 구리\n'}).get_json()
    assert made['file'] == '구리.md' and (project / '.lectern' / 'clips' / '구리.md').read_text(encoding='utf-8') == '# 구리\n'
    saved = client.post('/api/clips', json={'p': pid, 'file': '구리.md', 'text': '# 구리 2\n', 'hash': made['hash']}).get_json()
    assert client.post('/api/clips', json={'p': pid, 'file': '구리.md', 'text': 'x', 'hash': made['hash']}).status_code == 409
    assert client.get(f'/api/clips?p={pid}').get_json()['boxes'][0]['hash'] == saved['hash']
    assert client.post('/api/clips', json={'p': pid, 'file': '../밖.md', 'text': 'x', 'hash': None}).status_code == 400
    assert client.post('/api/clips', json={'p': pid, 'file': '구리.md', 'text': 3}).status_code == 400
    assert client.post('/api/clips/delete', json={'p': pid, 'file': '..\\notes.md'}).status_code == 400
    monkeypatch.setattr(trash, 'send', lambda p: p.unlink())
    assert client.post('/api/clips/delete', json={'p': pid, 'file': '구리.md'}).get_json() == {'ok': True}
    assert client.get(f'/api/clips?p={pid}').get_json() == {'boxes': [], 'cur': ''}


def test_clips_do_not_show_in_the_tree(client, state):
    pid = state.active
    client.post('/api/clips', json={'p': pid, 'title': '구리', 'text': '# 찾을낱말\n'})
    assert '.lectern' not in client.get(f'/api/tree?p={pid}').get_data(as_text=True)


def test_current_box_is_remembered(client, state, project):
    """지금 담기함은 설정에 — 문서 위치를 적어도 남고, 이름이 아닌 것은 받지 않는다 (D199)"""
    pid = client.get('/api/state').get_json()['projects'][0]['id']
    cur = lambda: client.get(f'/api/clips?p={pid}').get_json()['cur']   # noqa: E731
    assert cur() == ''
    assert client.post('/api/clips/current', json={'p': pid, 'file': '질문.md'}).get_json() == {'ok': True}
    assert cur() == '질문.md' and not (project / '.lectern').exists()
    assert client.post('/api/position', json={'p': pid, 'path': 'README.md', 'scroll': 3}).status_code == 200
    assert cur() == '질문.md'
    assert client.post('/api/position', json={'p': pid, 'path': '', 'docs': []}).status_code == 200
    assert cur() == '질문.md'
    bad = ['../x.md', 'a/b.md', r'a\b.md', 'x.txt', '', None, 3, '.숨김.md']
    assert [client.post('/api/clips/current', json={'p': pid, 'file': f}).status_code for f in bad] == [400] * len(bad)
    assert client.post('/api/clips/current', json={'file': '질문.md'}).status_code == 404
    assert cur() == '질문.md' and client.get('/api/state').get_json()['projects'][0]['position']['doc'] is None
    state.config.data['projects'] = {k: {**v, 'clip': 7} for k, v in state.config.data['projects'].items()}
    assert state.config.clip_box(str(project)) in ('', '질문.md')
