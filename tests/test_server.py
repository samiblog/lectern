from __future__ import annotations

from urllib.parse import quote

import pytest

from conftest import write

import app as lectern_app
from lectern import osutil, state as state_module
from lectern.config import Config
from lectern.scanner import iter_files
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
    """열린 프로젝트(탭)의 id"""
    return state.active


@pytest.fixture
def other(tmp_path):
    """두 번째 프로젝트 (탭 두 개)"""
    root = tmp_path / 'other'
    write(root / 'README.md', '# 다른 프로젝트\n')
    write(root / 'notes' / 'a.md', '# 메모\n')
    return root.resolve()


def test_index_injects_mode(client):
    html = client.get('/').get_data(as_text=True)
    assert '<meta name="lec-mode" content="browser">' in html
    assert '{{MODE}}' not in html


def test_state_without_folder():
    st = AppState(Config(), mode='browser')
    c = create_app(st).test_client()
    info = c.get('/api/state').get_json()
    assert info['projects'] == [] and info['active'] is None and info['max_tabs'] == 10
    assert c.get('/api/tree').status_code == 404
    assert c.get('/api/tree?p=nope').status_code == 404


def test_state_and_tree(client, project, pid):
    st = client.get('/api/state').get_json()
    assert st['active'] == pid and len(st['projects']) == 1
    p = st['projects'][0]
    assert p['id'] == pid and p['root'] == str(project) and p['name'] == 'proj' and p['seq'] >= 1
    assert st['config_error'] is None and st['notices'] == []
    tree = client.get(f'/api/tree?p={pid}').get_json()['tree']
    names = [n['name'] for n in tree]
    assert names == ['docs', 'CLAUDE.md', 'README.md']


def test_open_rejects_non_folder(client, project):
    r = client.post('/api/open', json={'path': str(project / 'README.md')})
    assert r.status_code == 400 and 'error' in r.get_json()
    assert client.post('/api/open', json={}).status_code == 400


def test_overview(client, pid):
    root = client.get(f'/api/overview?p={pid}').get_json()
    assert root['total'] == 5 and [d['name'] for d in root['dirs']] == ['docs']
    readme = next(f for f in root['files'] if f['name'] == 'README.md')
    assert readme['title'] == '프로젝트' and readme['summary'] == '설명 문단입니다.'
    assert len(root['recent']) == 5
    docs = client.get(f'/api/overview?p={pid}&path=docs').get_json()
    assert docs['name'] == 'docs' and docs['dirs'][0]['count'] == 1
    sub = client.get(f'/api/overview?p={pid}&path=docs/sub').get_json()
    assert sub['files'][0]['summary'] == 'frontmatter 설명'
    assert client.get(f'/api/overview?p={pid}&path=.claude').status_code == 404
    assert client.get(f'/api/overview?p={pid}&path=../').status_code == 404
    assert client.get('/api/overview?path=docs').status_code == 404   # 프로젝트 id 없이는


def test_overview_path_is_normalized(client, pid):
    d = client.get(f'/api/overview?p={pid}&path=docs/../docs').get_json()
    assert d['path'] == 'docs' and d['files'][0]['path'].startswith('docs/') and d['dirs'][0]['path'] == 'docs/sub'
    assert client.get(f'/api/overview?p={pid}&path=docs/sub/../..').get_json()['path'] == ''


def test_doc_serves_markdown_and_assets(client, pid):
    r = client.get(f'/doc/{pid}/README.md')
    assert r.status_code == 200 and r.mimetype == 'text/markdown'
    assert r.get_data(as_text=True).startswith('# 프로젝트')
    assert r.headers['Cache-Control'] == 'no-cache'
    svg = fetch(client, f'/doc/{pid}/docs/img.svg')
    assert svg.status_code == 200
    # 주소로 직접 열어도 앱 출처에서 스크립트가 돌지 않게
    assert svg.headers['Content-Security-Policy'] == 'sandbox' and svg.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get(f'/doc/{pid}/' + quote('docs/10-a.md')).status_code == 200


@pytest.mark.parametrize('bad', ['.hidden.md', '.claude/notes.md', '../x.md', 'docs/../../x.md', 'nope.md', 'docs', '%5C%5Cevil.example%5Cshare%5Cx.png'])
def test_doc_blocks_hidden_outside_missing(client, pid, bad):
    assert client.get(f'/doc/{pid}/{bad}').status_code == 404


def test_doc_needs_open_project(client, pid):
    assert client.get('/doc/README.md').status_code == 404              # 프로젝트 id 없는 옛 주소
    assert client.get('/doc/deadbeef/README.md').status_code == 404     # 열려 있지 않은 프로젝트


def test_fixed_types_win_over_windows_registry(state, pid, monkeypatch):
    import mimetypes

    # 레지스트리에 .js·.css·.svg 가 text/plain 으로 잡힌 Windows PC 흉내 (read_windows_registry 가 하는 일과 같음)
    db = mimetypes.MimeTypes()
    for ext in ('.js', '.css', '.svg'):
        db.add_type('text/plain', ext)
    monkeypatch.setattr(mimetypes, '_db', db)   # 테스트가 끝나면 원래 db 로 돌아간다
    c = create_app(state).test_client()
    assert fetch(c, '/static/js/main.js').mimetype == 'text/javascript'
    assert fetch(c, '/static/css/app.css').mimetype == 'text/css'
    assert fetch(c, f'/doc/{pid}/docs/img.svg').mimetype == 'image/svg+xml'


def test_token_required_when_set(state, pid):
    state.token = 'secret'
    c = create_app(state).test_client()
    assert c.get('/api/state').status_code == 403
    assert c.get('/api/state', headers={'X-Token': 'secret'}).status_code == 200
    assert c.get(f'/doc/{pid}/README.md').status_code == 200   # 문서·이미지는 토큰 없이
    assert c.get('/').status_code == 200


def test_rejects_foreign_host_header(state, pid):
    c = create_app(state).test_client()
    assert c.get(f'/doc/{pid}/README.md', headers={'Host': 'evil.example:8765'}).status_code == 403
    assert c.get(f'/doc/{pid}/README.md', headers={'Host': '127.0.0.1:8765'}).status_code == 200
    assert c.get(f'/doc/{pid}/README.md', headers={'Host': 'localhost'}).status_code == 200


def test_state_reports_config_error(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{ "theme": "dark", }', encoding='utf-8')
    c = create_app(AppState(Config(path), mode='browser')).test_client()
    assert '설정 파일을 읽지 못해' in c.get('/api/state').get_json()['config_error']


def fetch(client, url: str, **kw):
    """파일을 그대로 보내는 응답(send_file)은 닫아 둔다 (닫지 않으면 ResourceWarning)"""
    r = client.get(url, **kw)
    r.close()
    return r


def csp_of(client) -> dict[str, str]:
    header = client.get('/').headers['Content-Security-Policy']
    return dict(d.strip().split(' ', 1) for d in header.split(';'))


def test_index_csp_follows_external_images(client):
    assert client.get('/').headers['Referrer-Policy'] == 'no-referrer'
    csp = csp_of(client)
    assert 'script-src' not in csp and 'default-src' not in csp   # D14: 스크립트는 CSP로 막지 않는다
    assert 'https:' in csp['img-src'] and csp['connect-src'] == "'self'"
    client.post('/api/config', json={'external_images': False})
    assert 'http' not in csp_of(client)['img-src']


def test_external_images_default_on_and_client_can_toggle(client):
    assert client.get('/api/config').get_json()['external_images'] is True
    assert client.post('/api/config', json={'external_images': False}).get_json()['external_images'] is False


def test_config_only_client_keys(client, project):
    r = client.post('/api/config', json={'theme': 'report', 'editor': 'evil.exe', 'exclude_dirs': ['x'],
                                         'recent': ['C:\\elsewhere'], 'tabs': ['C:\\elsewhere']})
    data = r.get_json()
    assert data['theme'] == 'report'
    assert data['editor'] is None and data['exclude_dirs'] == []
    assert data['recent'] == [str(project)]          # 최근 폴더·탭은 폴더를 열 때 서버만 기록한다
    assert data['tabs'] == [str(project)]
    assert client.post('/api/config', json=['x']).status_code == 400


def test_open_records_recent_and_tabs(client, project):
    cfg = client.get('/api/config').get_json()
    assert cfg['recent'][0] == str(project) and cfg['last_folder'] == str(project)
    assert cfg['tabs'] == [str(project)] and cfg['active_tab'] == 0


def test_tabs_open_activate_close(client, state, project, other, pid):
    r = client.post('/api/open', json={'path': str(other)}).get_json()
    second = r['opened']
    assert second != pid and r['active'] == second
    assert [p['root'] for p in r['projects']] == [str(project), str(other)]
    assert client.get('/api/config').get_json()['tabs'] == [str(project), str(other)]
    # 이미 열린 폴더는 새 탭을 만들지 않고 그 탭을 고른다 (같은 폴더를 다른 표기로 열어도)
    again = client.post('/api/open', json={'path': str(project / 'docs' / '..')}).get_json()
    assert again['opened'] == pid and again['active'] == pid and len(again['projects']) == 2
    assert client.get('/api/config').get_json()['active_tab'] == 0
    assert client.post('/api/activate', json={'p': second}).get_json() == {'ok': True}
    assert state.active == second and client.get('/api/config').get_json()['active_tab'] == 1
    assert client.post('/api/activate', json={'p': 'nope'}).status_code == 404
    # 선택된 탭을 닫으면 그 오른쪽, 없으면 왼쪽 탭이 선택된다. 닫힌 탭의 문서·트리는 더 열리지 않는다
    seq = state.tabs_seq
    closed = client.post('/api/close', json={'p': second}).get_json()
    assert [p['id'] for p in closed['projects']] == [pid] and closed['active'] == pid and closed['tabs_seq'] == seq + 1
    assert client.get(f'/doc/{second}/README.md').status_code == 404
    assert client.get(f'/api/tree?p={second}').status_code == 404
    assert client.get('/api/config').get_json()['tabs'] == [str(project)]
    assert client.post('/api/close', json={'p': second}).status_code == 200   # 이미 닫힌 탭은 그대로
    assert client.post('/api/close', json={}).status_code == 400
    client.post('/api/close', json={'p': pid})
    assert client.get('/api/state').get_json()['active'] is None


def test_too_many_tabs(client, tmp_path, monkeypatch):
    monkeypatch.setattr(state_module, 'MAX_TABS', 2)
    write(tmp_path / 'b' / 'x.md')
    write(tmp_path / 'c' / 'x.md')
    assert client.post('/api/open', json={'path': str(tmp_path / 'b')}).status_code == 200
    r = client.post('/api/open', json={'path': str(tmp_path / 'c')})
    assert r.status_code == 400 and '2개까지' in r.get_json()['error']


def test_projects_stay_apart(client, state, pid, other):
    second = client.post('/api/open', json={'path': str(other)}).get_json()['opened']
    assert client.get(f'/doc/{second}/README.md').get_data(as_text=True).startswith('# 다른 프로젝트')
    assert client.get(f'/doc/{pid}/README.md').get_data(as_text=True).startswith('# 프로젝트')
    assert client.get(f'/doc/{pid}/notes/a.md').status_code == 404
    # 한 프로젝트의 문서가 상대경로로 다른 탭 프로젝트의 파일을 부르지 못한다
    assert client.get(f'/doc/{pid}/../{second}/README.md').status_code == 404
    assert client.get(f'/doc/{pid}/%2E%2E/{second}/README.md').status_code == 404
    tree = client.get(f'/api/tree?p={second}').get_json()
    assert tree['root'] == str(other) and [n['name'] for n in tree['tree']] == ['notes', 'README.md']
    assert client.post('/api/exists', json={'p': second, 'paths': ['README.md', 'docs/10-a.md']}).get_json()['found'] == {'README.md': 'README.md'}


def test_changes_endpoint(client, state, pid, other):
    seq = client.get('/api/state').get_json()['projects'][0]['seq']
    state.get(pid).log.push('README.md')
    second = state.open(other)
    r = client.get(f'/api/changes?since={pid}:{seq},{second.id}:0,nope:1,{pid}x:2,bad').get_json()
    assert set(r['projects']) == {pid, second.id} and r['tabs_seq'] == state.tabs_seq
    assert r['projects'][pid]['paths'] == ['README.md'] and r['projects'][pid]['seq'] == seq + 1
    assert r['projects'][second.id]['structure'] is True   # 처음 열 때 트리를 그리라는 기록
    assert client.get('/api/changes').get_json() == {'tabs_seq': state.tabs_seq, 'projects': {}}


def test_reveal(client, monkeypatch, pid, project):
    calls = []
    monkeypatch.setattr(osutil, 'reveal', lambda p: calls.append(p))
    assert client.post('/api/reveal', json={'p': pid, 'path': 'README.md'}).get_json() == {'action': 'reveal'}
    assert client.post('/api/reveal', json={'p': pid, 'path': ''}).status_code == 200   # 탭 우클릭: 프로젝트 폴더
    assert [c.name for c in calls] == ['README.md', 'proj'] and calls[1] == project
    assert client.post('/api/reveal', json={'p': pid, 'path': '../x'}).status_code == 404
    assert client.post('/api/reveal', json={'p': pid}).status_code == 400
    assert client.post('/api/reveal', json={'path': 'README.md'}).status_code == 404


def test_api_errors_are_json(client):
    r = client.get('/api/open')          # 잘못된 메서드
    assert r.status_code == 405 and 'error' in r.get_json()


def test_open_external(client, monkeypatch, pid):
    calls = []
    monkeypatch.setattr(osutil, 'open_path', lambda p, line, editor: calls.append((p.name, line)) or 'editor')
    r = client.post('/api/open-external', json={'p': pid, 'path': 'src/app.py', 'line': 3})
    assert r.get_json() == {'action': 'editor'} and calls == [('app.py', 3)]
    assert client.post('/api/open-external', json={'p': pid, 'path': '../x'}).status_code == 404
    assert client.post('/api/open-external', json={'p': pid, 'path': '.claude/notes.md'}).status_code == 404


def test_search_endpoint(client, pid):
    r = client.get(f'/api/search?p={pid}&q=' + quote('설명 문단')).get_json()
    assert [x['path'] for x in r['results']] == ['README.md'] and r['results'][0]['hits'][0]['line'] == 3
    assert client.get(f'/api/search?p={pid}&q=' + quote('숨김')).get_json()['results'] == []   # 숨김 문서는 찾지 않는다
    assert client.get(f'/api/search?p={pid}&q=' + 'x' * 201).status_code == 400


def test_position_is_remembered(client, project, pid):
    post = lambda body: client.post('/api/position', json={'p': pid} | body)   # noqa: E731
    assert post({'path': 'docs/10-a.md', 'scroll': 420}).get_json() == {'ok': True}
    pos = client.get('/api/state').get_json()['projects'][0]['position']
    assert pos == {'doc': 'docs/10-a.md', 'scroll': {'docs/10-a.md': 420}}
    assert post({'path': '../x.md', 'scroll': 1}).status_code == 404
    bad = [{'path': 'docs', 'scroll': 1}, {'path': 'README.md', 'scroll': -1}, {'path': 'README.md', 'scroll': '1'},
           {'panes': [{'path': 'README.md', 'scroll': 5}], 'active': 0}]   # 창을 나누던 때(v0.6)의 형식
    assert [post(b).status_code for b in bad] == [400] * len(bad)
    assert client.post('/api/position', json={'path': 'README.md', 'scroll': 1}).status_code == 404   # 프로젝트 id 없이는
    client.post('/api/config', json={'restore_last': False})
    post({'path': 'README.md', 'scroll': 5})
    assert client.get('/api/state').get_json()['projects'][0]['position']['doc'] == 'docs/10-a.md'   # 꺼 두면 기록하지 않음


def test_open_config(client, state, monkeypatch):
    calls = []
    monkeypatch.setattr(osutil, 'open_path', lambda p, line, editor: calls.append(p) or 'editor')
    r = client.post('/api/open-config', json={}).get_json()
    assert r['action'] == 'editor' and calls == [state.config.path] and state.config.path.exists()


@pytest.mark.parametrize('route', ['/api/open-config', '/api/open', '/api/close', '/api/activate', '/api/config',
                                   '/api/position', '/api/open-external', '/api/reveal', '/api/exists'])
def test_post_requires_json(client, monkeypatch, pid, route):
    # 브라우저 모드(토큰 없음)에서 다른 사이트의 폼이 사전 확인(preflight) 없이 POST 하지 못하게 — JSON 본문만 받는다
    calls = []
    monkeypatch.setattr(osutil, 'open_path', lambda *a: calls.append(a) or 'editor')
    monkeypatch.setattr(osutil, 'reveal', lambda *a: calls.append(a))
    r = client.post(route, data={'p': pid, 'path': 'README.md'})
    assert r.status_code == 415 and 'error' in r.get_json()
    assert client.post(route, data=f'{{"p": "{pid}", "path": "README.md"}}', content_type='text/plain').status_code == 415
    assert calls == [] and client.get('/api/state').get_json()['active'] == pid


def test_html_doc_policy(client, project, pid):
    write(project / 'docs' / 'r.html', '<title>보고서</title><p>본문</p>')
    r = fetch(client, f'/doc/{pid}/docs/r.html')
    csp = r.headers['Content-Security-Policy']
    assert r.headers['Content-Type'] == 'text/html; charset=utf-8'
    # 같은 출처(앱이 목차·찾기·링크를 다룸)지만 스크립트·연결·폼은 막고, 인터넷 그림은 설정을 따른다
    assert csp.startswith('sandbox allow-same-origin allow-modals;') and "default-src 'none'" in csp and 'https:' in csp
    assert 'allow-scripts' not in csp and 'script-src' not in csp
    assert r.headers['Referrer-Policy'] == 'no-referrer'   # 문서 속 인터넷 그림이 앱 주소를 보내지 않게
    client.post('/api/config', json={'external_images': False})
    assert 'https:' not in fetch(client, f'/doc/{pid}/docs/r.html').headers['Content-Security-Policy']
    assert fetch(client, f'/doc/{pid}/docs/img.svg').headers['Content-Security-Policy'] == 'sandbox'
    assert csp_of(client)['frame-src'] == "'self'"
    tree = client.get(f'/api/tree?p={pid}').get_json()['tree']
    docs = next(n for n in tree if n['name'] == 'docs')
    assert {'path': 'docs/r.html', 'kind': 'html', 'title': '보고서'}.items() <= next(
        c for c in docs['children'] if c['name'] == 'r.html').items()


def test_exists_for_path_links(client, pid):
    r = client.post('/api/exists', json={'p': pid, 'paths': ['src/app.py', '../src/app.py', 'docs/10-a.md', 'nope.py',
                                                             '.hidden.md', '../../x.py', 'docs'], 'base': 'docs'}).get_json()
    # 프로젝트 기준, 그다음 문서 폴더 기준. 숨김·밖·폴더는 없는 것으로
    assert r['found'] == {'src/app.py': 'src/app.py', '../src/app.py': 'src/app.py', 'docs/10-a.md': 'docs/10-a.md'}
    assert client.post('/api/exists', json={'p': pid, 'paths': 'x'}).status_code == 400


def test_tree_scan_is_reused_until_something_changes(client, state, project, pid):
    state.close()   # 감시를 멈춰 변경 기록(seq)을 이 테스트가 정한다 (프로젝트를 만들며 쓴 파일의 늦은 알림이 끼어들지 않게)
    proj = state.get(pid)
    first = proj.scan()
    assert proj.scan() is first                        # 변경 기록이 그대로면 다시 훑지 않는다
    write(project / 'docs' / 'new.md', '# 새 문서\n')
    assert proj.scan() is first                        # 감시가 알리기 전에는 그대로
    proj.log.push('docs/new.md', True)
    second = proj.scan()
    assert second is not first and 'docs/new.md' in {n['path'] for n in iter_files(second)}
    assert proj.scan(fresh=True) is not second         # F5 는 늘 새로
    paths = {n['path'] for n in iter_files(client.get(f'/api/tree?p={pid}&fresh=1').get_json()['tree'])}
    assert 'docs/new.md' in paths


def test_startup_restores_tabs(project, other, tmp_path):
    cfg = Config()
    cfg.set_tabs([str(project), str(tmp_path / 'gone'), str(other)], 2)
    st = AppState(cfg, mode='browser')
    try:
        lectern_app.open_initial(st, None)
        # 없어진 폴더는 건너뛰고, 선택돼 있던 탭(순번 2 = other)을 고른다
        assert [p.root for p in st.projects.values()] == [project, other] and st.active_project.root == other
        assert cfg.get('recent') == []                    # 되살리기는 최근 폴더 순서를 바꾸지 않는다
        lectern_app.open_folder(st, str(project))         # 이미 열린 폴더를 인자로 주면 그 탭을 고른다
        assert len(st.projects) == 2 and st.active_project.root == project
        lectern_app.open_folder(st, str(tmp_path / 'gone'))
        info = st.info()
        assert len(info['projects']) == 2 and '열 수 없습니다' in info['notices'][-1]['text']   # 창에 알린다
    finally:
        st.close()


def test_startup_reads_old_last_folder(project):
    cfg = Config()
    cfg.add_recent(str(project))       # 탭이 생기기 전(v0.6 이하)의 설정: last_folder 만 있음
    st = AppState(cfg, mode='browser')
    try:
        lectern_app.open_initial(st, None)
        assert st.active_project.root == project
    finally:
        st.close()
