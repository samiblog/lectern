"""'폴더' 묶음의 모든 것과 복사·붙여 넣기 (D203): 숨김·링크·빈 폴더는 그 묶음에만, 숨긴 파일은 보기만, 붙여 넣기는 덮어쓰지 않는다"""
from __future__ import annotations

import subprocess
import sys

import pytest

from lectern import fileclip
from lectern.config import Config
from lectern.scanner import iter_files, list_all, resolve_inside, scan, scan_hidden, scan_others
from lectern.server import create_app
from lectern.state import AppState

windows = pytest.mark.skipif(sys.platform != 'win32', reason='Windows 의 숨김 속성·정션·클립보드')


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / 'p'
    (root / '보고').mkdir(parents=True)
    (root / '빈').mkdir()
    (root / '숨김만').mkdir()
    (root / '.git').mkdir()
    (root / 'node_modules').mkdir()
    (root / 'a.md').write_text('# 문서\n', encoding='utf-8')
    (root / '보고' / 'b.py').write_text('x = 1\n', encoding='utf-8')
    (root / '.env').write_text('KEY=1\n', encoding='utf-8')
    (root / '.git' / 'HEAD').write_text('ref\n', encoding='utf-8')
    (root / '숨김만' / '.keep').write_text('', encoding='utf-8')
    (root / 'node_modules' / '.cache').write_text('c', encoding='utf-8')
    return root.resolve()


@pytest.fixture
def client(proj):
    st = AppState(Config(), mode='browser')
    st.open(proj)
    c = create_app(st).test_client()
    yield c, c.get('/api/state').get_json()['projects'][0]['id']
    st.close()


def test_hidden_items_only_in_the_folders_group(proj):
    nodes, truncated = scan_hidden(proj)
    got = {n['path']: n for n in nodes}
    assert not truncated
    assert got['.env']['hidden'] and got['.env']['type'] == 'file'
    assert got['.git']['hidden'] and got['.git']['children'] is None   # 펼칠 때 읽는다
    assert got['숨김만/.keep']['hidden']
    assert got['빈'].get('empty') and got['빈']['children'] == []
    assert 'node_modules/.cache' not in got   # 제외 폴더의 안은 펼칠 때
    # 문서 트리·코드·자료 목록에는 그대로 없다
    plain = [f['path'] for f in iter_files(scan(proj))] + [f['path'] for f in iter_files(scan_others(proj)[0])]
    assert not [p for p in plain if p.startswith('.') or '/.' in p]


def test_list_all_reads_one_level_of_everything(proj):
    nodes, _ = list_all(proj, '.git')
    assert [(n['path'], n['hidden']) for n in nodes] == [('.git/HEAD', True)]   # 숨긴 폴더 안은 모두 숨김
    nodes, _ = list_all(proj, 'node_modules')
    assert [(n['path'], n['hidden']) for n in nodes] == [('node_modules/.cache', True)]


def test_resolve_inside_hidden_only_when_asked(proj):
    assert resolve_inside(proj, '.env') is None
    assert resolve_inside(proj, '.env', hidden_ok=True) == proj / '.env'
    assert resolve_inside(proj, '../x', hidden_ok=True) is None   # 밖은 그대로 막는다
    assert resolve_inside(proj, '\\\\server\\share', hidden_ok=True) is None


def test_hidden_file_needs_the_token(client):
    c, pid = client
    assert c.get(f'/doc/{pid}/.env').status_code == 404
    r = c.get(f'/doc/{pid}/.env?hidden=1')   # 브라우저 모드는 토큰이 없어 1
    assert r.status_code == 200 and r.data.rstrip() == b'KEY=1'
    assert c.get(f'/doc/{pid}/.env?hidden=2').status_code == 404


def test_hidden_file_is_never_saved(client, proj):
    c, pid = client
    r = c.post('/api/save', json={'p': pid, 'path': '.env', 'text': 'X', 'hash': ''})
    assert r.status_code in (403, 404)
    assert (proj / '.env').read_text(encoding='utf-8') == 'KEY=1\n'


def test_api_hidden_and_dir_all(client):
    c, pid = client
    nodes = c.get(f'/api/others/hidden?p={pid}').get_json()['nodes']
    assert {'.env', '.git', '숨김만/.keep', '빈'} <= {n['path'] for n in nodes}
    assert c.get(f'/api/others/dir?p={pid}&path=.git').status_code == 404   # all 없이는 숨긴 폴더를 읽지 않는다
    got = c.get(f'/api/others/dir?p={pid}&path=.git&all=1').get_json()
    assert [n['path'] for n in got['nodes']] == ['.git/HEAD']
    assert c.get(f'/api/others/dir?p={pid}&path=../x&all=1').status_code == 404


@windows
def test_junction_is_shown_not_followed(proj, tmp_path):
    out = tmp_path / '밖'
    out.mkdir()
    (out / '비밀.txt').write_text('s', encoding='utf-8')
    subprocess.run(['cmd', '/c', 'mklink', '/J', str(proj / '링크'), str(out)], check=True, capture_output=True)
    got = {n['path']: n for n in scan_hidden(proj)[0]}
    assert got['링크']['link'] and got['링크']['type'] == 'file'
    assert not any(p.startswith('링크/') for p in got)
    assert resolve_inside(proj, '링크/비밀.txt', hidden_ok=True) is None   # 링크를 따라 밖으로 나가지 않는다


@windows
def test_copy_and_paste_with_the_windows_clipboard(client, proj, tmp_path):
    c, pid = client
    assert c.post('/api/files/copy', json={'p': pid, 'paths': ['a.md', '.env', '보고']}).get_json() == {'count': 3}
    names, cut = fileclip.read()
    assert sorted(p.name for p in names) == ['.env', 'a.md', '보고'] and not cut
    r = c.post('/api/files/paste', json={'p': pid, 'dir': '빈'}).get_json()
    assert r == {'copied': 3, 'cut': False, 'skipped': []}
    assert (proj / '빈' / 'a.md').exists() and (proj / '빈' / '.env').exists() and (proj / '빈' / '보고' / 'b.py').exists()
    r = c.post('/api/files/paste', json={'p': pid, 'dir': ''}).get_json()
    assert r['copied'] == 3
    assert (proj / 'a - 복사본.md').exists() or (proj / 'a - Copy.md').exists()   # 겹치면 새 이름 — 덮어쓰지 않는다
    assert (proj / 'a.md').read_text(encoding='utf-8') == '# 문서\n'


@windows
def test_paste_refuses_folder_into_itself_and_missing(client, proj):
    c, pid = client
    fileclip.put([proj / '보고'])
    r = c.post('/api/files/paste', json={'p': pid, 'dir': '보고'})
    assert r.status_code == 400 and '그 폴더 안으로' in r.get_json()['error']
    assert c.post('/api/files/paste', json={'p': pid, 'dir': '없는 폴더'}).status_code == 404
    assert c.post('/api/files/paste', json={'p': pid, 'dir': '../밖'}).status_code == 404
