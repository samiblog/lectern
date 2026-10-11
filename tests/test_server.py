from __future__ import annotations

from urllib.parse import quote

import pytest

from lectern import osutil
from lectern.config import Config
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


def test_index_injects_mode(client):
    html = client.get('/').get_data(as_text=True)
    assert '<meta name="lec-mode" content="browser">' in html
    assert '{{MODE}}' not in html


def test_state_without_folder():
    st = AppState(Config(), mode='browser')
    c = create_app(st).test_client()
    assert c.get('/api/state').get_json()['root'] is None
    assert c.get('/api/tree').status_code == 409


def test_state_and_tree(client, project):
    st = client.get('/api/state').get_json()
    assert st['root'] == str(project) and st['name'] == 'proj' and st['seq'] >= 1
    assert st['config_error'] is None
    tree = client.get('/api/tree').get_json()['tree']
    names = [n['name'] for n in tree]
    assert names == ['docs', 'CLAUDE.md', 'README.md']


def test_open_rejects_non_folder(client, project):
    r = client.post('/api/open', json={'path': str(project / 'README.md')})
    assert r.status_code == 400 and 'error' in r.get_json()
    assert client.post('/api/open', json={}).status_code == 400


def test_overview(client):
    root = client.get('/api/overview').get_json()
    assert root['total'] == 5 and [d['name'] for d in root['dirs']] == ['docs']
    readme = next(f for f in root['files'] if f['name'] == 'README.md')
    assert readme['title'] == '프로젝트' and readme['summary'] == '설명 문단입니다.'
    assert len(root['recent']) == 5
    docs = client.get('/api/overview?path=docs').get_json()
    assert docs['name'] == 'docs' and docs['dirs'][0]['count'] == 1
    sub = client.get('/api/overview?path=docs/sub').get_json()
    assert sub['files'][0]['summary'] == 'frontmatter 설명'
    assert client.get('/api/overview?path=.claude').status_code == 404
    assert client.get('/api/overview?path=../').status_code == 404


def test_overview_path_is_normalized(client):
    d = client.get('/api/overview?path=docs/../docs').get_json()
    assert d['path'] == 'docs' and d['files'][0]['path'].startswith('docs/') and d['dirs'][0]['path'] == 'docs/sub'
    assert client.get('/api/overview?path=docs/sub/../..').get_json()['path'] == ''


def test_doc_serves_markdown_and_assets(client):
    r = client.get('/doc/README.md')
    assert r.status_code == 200 and r.mimetype == 'text/markdown'
    assert r.get_data(as_text=True).startswith('# 프로젝트')
    assert r.headers['Cache-Control'] == 'no-cache'
    svg = client.get('/doc/docs/img.svg')
    assert svg.status_code == 200
    # 주소로 직접 열어도 앱 출처에서 스크립트가 돌지 않게
    assert svg.headers['Content-Security-Policy'] == 'sandbox' and svg.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get('/doc/' + quote('docs/10-a.md')).status_code == 200


@pytest.mark.parametrize('bad', ['.hidden.md', '.claude/notes.md', '../x.md', 'docs/../../x.md', 'nope.md', 'docs'])
def test_doc_blocks_hidden_outside_missing(client, bad):
    assert client.get(f'/doc/{bad}').status_code == 404


def test_token_required_when_set(state):
    state.token = 'secret'
    c = create_app(state).test_client()
    assert c.get('/api/state').status_code == 403
    assert c.get('/api/state', headers={'X-Token': 'secret'}).status_code == 200
    assert c.get('/doc/README.md').status_code == 200          # 문서·이미지는 토큰 없이
    assert c.get('/').status_code == 200


def test_rejects_foreign_host_header(state):
    c = create_app(state).test_client()
    assert c.get('/doc/README.md', headers={'Host': 'evil.example:8765'}).status_code == 403
    assert c.get('/doc/README.md', headers={'Host': '127.0.0.1:8765'}).status_code == 200
    assert c.get('/doc/README.md', headers={'Host': 'localhost'}).status_code == 200


def test_state_reports_config_error(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{ "theme": "dark", }', encoding='utf-8')
    c = create_app(AppState(Config(path), mode='browser')).test_client()
    assert '설정 파일을 읽지 못해' in c.get('/api/state').get_json()['config_error']


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
                                         'recent': ['C:\\elsewhere']})
    data = r.get_json()
    assert data['theme'] == 'report'
    assert data['editor'] is None and data['exclude_dirs'] == []
    assert data['recent'] == [str(project)]          # 최근 폴더는 폴더를 열 때 서버만 기록한다
    assert client.post('/api/config', json=['x']).status_code == 400


def test_open_records_recent(client, project):
    cfg = client.get('/api/config').get_json()
    assert cfg['recent'][0] == str(project) and cfg['last_folder'] == str(project)


def test_changes_endpoint(client, state):
    seq = client.get('/api/state').get_json()['seq']
    state.log.push('README.md')
    r = client.get(f'/api/changes?since={seq}').get_json()
    assert r['paths'] == ['README.md'] and r['seq'] == seq + 1 and r['root'] == str(state.root)


def test_open_returns_state_with_version(client, project):
    r = client.post('/api/open', json={'path': str(project / 'docs')}).get_json()
    assert r['name'] == 'docs' and r['version'] and r['root'] == str(project / 'docs')


def test_reveal(client, monkeypatch):
    calls = []
    monkeypatch.setattr(osutil, 'reveal', lambda p: calls.append(p.name))
    assert client.post('/api/reveal', json={'path': 'README.md'}).get_json() == {'action': 'reveal'}
    assert calls == ['README.md']
    assert client.post('/api/reveal', json={'path': '../x'}).status_code == 404
    assert client.post('/api/reveal', json={}).status_code == 400


def test_api_errors_are_json(client):
    r = client.get('/api/open')          # 잘못된 메서드
    assert r.status_code == 405 and 'error' in r.get_json()


def test_open_external(client, monkeypatch):
    calls = []
    monkeypatch.setattr(osutil, 'open_path', lambda p, line, editor: calls.append((p.name, line)) or 'editor')
    r = client.post('/api/open-external', json={'path': 'src/app.py', 'line': 3})
    assert r.get_json() == {'action': 'editor'} and calls == [('app.py', 3)]
    assert client.post('/api/open-external', json={'path': '../x'}).status_code == 404
    assert client.post('/api/open-external', json={'path': '.claude/notes.md'}).status_code == 404
