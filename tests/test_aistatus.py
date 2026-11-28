"""AI 도구에 건네는 것의 지금 상태 (D159 — aistatus.py, /api/ai-status) 와 설정의 판 번호 (/api/changes 의 config)"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import write

from lectern import aistatus
from lectern.config import Config
from lectern.paths import skills_dir, web_dir
from lectern.server import create_app
from lectern.state import AppState

ROOT = Path(__file__).resolve().parent.parent
STYLE = web_dir() / 'help' / 'research-writing.md'
STYLES = aistatus.lectern_styles(web_dir() / 'help')   # 글쓰기 스타일 넷 (D161)


def copy_tree(src: Path, dst: Path) -> None:
    for f in src.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts:
            (dst / f.relative_to(src)).parent.mkdir(parents=True, exist_ok=True)
            (dst / f.relative_to(src)).write_bytes(f.read_bytes())


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / 'home'
    h.mkdir()
    return h


def test_empty_home_reports_nothing_installed(home, tmp_path):
    proj = tmp_path / 'proj'
    proj.mkdir()
    st = aistatus.status(home, 'claude', skills_dir(), STYLES, proj)
    assert st['tool'] == 'claude'
    assert st['skills']['items'] == {n: 'missing' for n in aistatus.LECTERN_SKILLS}
    assert st['rules'] == {'path': str(home / '.claude' / 'rules' / 'lectern.md'), 'exists': False, 'lectern': False, 'summary': 0}
    assert st['summary_now'] == aistatus.SUMMARY_NOW
    c = st['claude']
    assert c['voice'] is None and c['voice_path'].endswith('내-문체.md')
    assert c['styles']['research']['state'] == 'missing' and c['styles']['research']['name'] == '리서치 글쓰기'
    assert [c['styles'][k]['name'] for k in ('brief', 'academic', 'plain')] == ['업무 보고', '학술 글', '쉬운 설명']
    assert c['settings']['user'] == {'path': str(home / '.claude' / 'settings.json'), 'value': None, 'ok': True}
    p = st['project']
    assert p['root'] == str(proj) and p['name'] == 'proj'
    assert p['rules'] == [{'path': str(proj / 'CLAUDE.md'), 'exists': False, 'lectern': False, 'summary': 0}]
    assert p['skills']['dir'] == str(proj / '.claude' / 'skills')
    assert p['settings']['local']['value'] is None and p['settings']['shared']['value'] is None


def test_installed_things_are_seen(home, tmp_path):
    proj = tmp_path / 'proj'
    write(proj / 'CLAUDE.md', '# 지침\n\n## 문서 (Lectern 으로 읽음)\n')
    write(proj / '.claude' / 'settings.local.json', json.dumps({'outputStyle': '리서치 글쓰기', 'permissions': {'allow': ['Bash(rm:*)']}}))
    write(home / '.claude' / 'settings.json', json.dumps({'outputStyle': 'Explanatory', 'env': {'SECRET_TOKEN': 'x'}}))
    write(home / '.claude' / 'rules' / 'lectern.md', '## 문서 (Lectern 으로 읽음)\n')
    write(home / '.claude' / 'rules' / '내-문체.md', '# 내 문체\n')
    write(home / '.claude' / 'output-styles' / 'research-writing.md', STYLE.read_text(encoding='utf-8'))
    write(home / '.claude' / 'output-styles' / 'terse.md', '---\nname: 짧게\ndescription: 짧은 답\n---\n본문\n')
    sk = home / '.claude' / 'skills'
    copy_tree(skills_dir() / 'pptx-to-lectern', sk / 'pptx-to-lectern')
    copy_tree(skills_dir() / 'lectern-to-pptx', sk / 'lectern-to-pptx')
    (sk / 'lectern-to-pptx' / 'SKILL.md').write_text('옛 판\n', encoding='utf-8')
    (sk / 'pptx-to-lectern' / '내가-더한.txt').write_text('더한 파일은 보지 않는다', encoding='utf-8')
    st = aistatus.status(home, 'claude', skills_dir(), STYLES, proj)
    assert st['skills']['items'] == {'pptx-to-lectern': 'same', 'lectern-to-pptx': 'differs', 'lectern-to-docx': 'missing'}
    assert st['rules']['exists'] and st['rules']['lectern']
    c = st['claude']
    assert c['voice'] == str(home / '.claude' / 'rules' / '내-문체.md')
    assert c['styles']['research']['state'] == 'same' and not c['styles']['research']['voice'] and c['styles']['brief']['state'] == 'missing'
    assert c['other_styles'] == [{'file': 'terse.md', 'path': str(home / '.claude' / 'output-styles' / 'terse.md'), 'name': '짧게', 'description': '짧은 답'}]
    assert c['settings']['user']['value'] == 'Explanatory'
    assert st['project']['settings']['local']['value'] == '리서치 글쓰기'
    assert st['project']['rules'][0] == {'path': str(proj / 'CLAUDE.md'), 'exists': True, 'lectern': True, 'summary': 0}
    # 설정 파일의 다른 값(권한·환경 변수)은 어디에도 나오지 않는다
    text = json.dumps(st, ensure_ascii=False)
    assert 'SECRET_TOKEN' not in text and 'permissions' not in text and 'Bash(rm' not in text


def test_summary_version_mark(home, tmp_path):
    """요약의 판 (0.113.2): 작성 안내의 요약 맨 위 줄 — 예전 요약(표시 없음)은 0, 설정 창이 새 요약으로 바꾸라고 알린다"""
    for name in ('writing.md', 'writing.en.md'):
        text = (web_dir() / 'help' / name).read_text(encoding='utf-8')
        summary = text.rsplit('```markdown', 1)[1]
        assert f'<!-- lectern-summary: {aistatus.SUMMARY_NOW} -->' in summary.splitlines()[2], name   # 요약 제목 바로 아래
    proj = tmp_path / 'proj'
    write(proj / 'CLAUDE.md', '# 지침\n\n## 문서 (Lectern 으로 읽음)\n<!--lectern-summary: 2-->\n- 형식보다 글\n')
    write(home / '.claude' / 'rules' / 'lectern.md', '## 문서 (Lectern 으로 읽음)\n- 예전 요약\n')
    st = aistatus.status(home, 'claude', skills_dir(), STYLES, proj)
    assert st['rules']['lectern'] and st['rules']['summary'] == 0
    assert st['project']['rules'][0]['summary'] == 2


def test_old_voice_section_in_style_still_counts_as_same(home):
    body = STYLE.read_text(encoding='utf-8')
    write(home / '.claude' / 'output-styles' / 'research-writing.md', body.rstrip('\n') + '\n\n## 내 문체\n\n- 지킬 것: 합니다체\n')
    st = aistatus.status(home, 'claude', skills_dir(), STYLES)['claude']['styles']['research']
    assert st == {'path': str(home / '.claude' / 'output-styles' / 'research-writing.md'), 'name': '리서치 글쓰기', 'state': 'same', 'voice': True}
    write(home / '.claude' / 'output-styles' / 'research-writing.md', body.replace('동료이자 편집자', '편집자'))
    assert aistatus.status(home, 'claude', skills_dir(), STYLES)['claude']['styles']['research']['state'] == 'differs'


def test_broken_settings_file_is_not_read(home, tmp_path):
    write(home / '.claude' / 'settings.json', '{ "outputStyle": "x", }')
    st = aistatus.status(home, 'claude', skills_dir(), STYLES)
    assert st['claude']['settings']['user'] == {'path': str(home / '.claude' / 'settings.json'), 'value': None, 'ok': False}
    write(home / '.claude' / 'settings.json', '["outputStyle"]')
    assert aistatus.status(home, 'claude', skills_dir(), STYLES)['claude']['settings']['user']['value'] is None


def test_other_tools(home, tmp_path):
    proj = tmp_path / 'proj'
    write(proj / 'AGENTS.md', '# 지침\n')
    write(home / '.codex' / 'AGENTS.md', '# 내 지침\n\n## 문서 (Lectern 으로 읽음)\n')
    write(home / '.codex' / 'AGENTS.override.md', '# 덮어쓰기\n')
    st = aistatus.status(home, 'codex', skills_dir(), STYLES, proj)
    assert 'claude' not in st
    assert st['skills']['dir'] == str(home / '.agents' / 'skills')
    assert st['rules'] == {'path': str(home / '.codex' / 'AGENTS.md'), 'exists': True, 'lectern': True, 'summary': 0, 'override': str(home / '.codex' / 'AGENTS.override.md')}
    assert st['project']['rules'] == [{'path': str(proj / 'AGENTS.md'), 'exists': True, 'lectern': False, 'summary': 0}]
    assert st['project']['skills']['dir'] == str(proj / '.agents' / 'skills')
    many = aistatus.status(home, 'any', skills_dir(), STYLES, proj)
    assert [Path(r['path']).name for r in many['project']['rules']] == ['CLAUDE.md', 'AGENTS.md']


def test_tool_table_matches_the_screen():
    """서버의 자리와 화면(aitool.js)의 자리가 같다"""
    js = (ROOT / 'web' / 'js' / 'aitool.js').read_text(encoding='utf-8')
    for tool, info in aistatus.TOOLS.items():
        line = next(x for x in js.splitlines() if re.match(rf'\s*{tool}: \{{', x))
        field = lambda name: re.search(rf"\b{name}: '([^']*)'", line).group(1)  # noqa: E731
        assert field('skills') == '~/' + '/'.join(info['skills']), tool
        assert field('projectSkills') == '/'.join(info['project_skills']), tool
        assert field('rules') == '~/' + '/'.join(info['rules']), tool
        assert field('file') == info['file'][0], tool


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('LECTERN_HOME', str(home))
    proj = tmp_path / 'proj'
    write(proj / 'README.md', '# 읽어 보기\n')
    st = AppState(Config(), mode='browser')
    st.open(proj)
    yield create_app(st).test_client(), st, home, proj
    st.close()


def test_api_ai_status(app_client):
    client, st, home, proj = app_client
    write(home / '.claude' / 'rules' / 'lectern.md', 'Lectern\n')
    r = client.get(f'/api/ai-status?p={st.active}').get_json()
    assert r['home'] == str(home) and r['rules']['exists'] and r['project']['root'] == str(proj)
    assert client.get('/api/ai-status').get_json()['project'] is None
    assert client.get('/api/ai-status?p=없는탭').get_json()['project'] is None


def test_config_revision_follows_changes(app_client):
    client, st, home, proj = app_client
    rev = client.get('/api/config').get_json()['_rev']
    assert client.get(f'/api/changes?since={st.active}:0').get_json()['config'] == rev
    client.post('/api/config', json={'font_scale': 1.2})
    assert client.get('/api/changes').get_json()['config'] == rev + 1
    client.post('/api/config', json={'font_scale': 1.2})   # 같은 값은 판을 올리지 않는다
    client.post('/api/config', json={'nope': 1})            # 바꿀 수 없는 열쇠도
    assert client.get('/api/changes').get_json()['config'] == rev + 1
    client.post('/api/position', json={'p': st.active, 'path': 'README.md', 'scroll': 10})   # 위치 기록은 판을 올리지 않는다
    assert client.get('/api/changes').get_json()['config'] == rev + 1
    assert client.get('/api/config').get_json()['_rev'] == rev + 1
    # 밖에서 고친 설정 파일도 (설정 창의 '설정 파일 열기')
    path = st.config.path
    data = json.loads(path.read_text(encoding='utf-8'))
    data['doc_width'] = 1.5
    import os
    import time
    path.write_text(json.dumps(data), encoding='utf-8')
    os.utime(path, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    assert client.get('/api/changes').get_json()['config'] == rev + 2
    assert client.get('/api/config').get_json()['doc_width'] == 1.5
    assert '_rev' not in json.loads(path.read_text(encoding='utf-8'))


def test_home_dir(monkeypatch, tmp_path):
    monkeypatch.delenv('LECTERN_HOME', raising=False)
    assert aistatus.home_dir() == Path.home()
    monkeypatch.setenv('LECTERN_HOME', str(tmp_path))
    assert aistatus.home_dir() == tmp_path


def test_scope_settings_are_checked(app_client):
    client, st, home, proj = app_client
    client.post('/api/config', json={'ai_scope_guide': 'folder', 'ai_scope_skills': 'everywhere', 'ai_style_where': 'off'})
    c = client.get('/api/config').get_json()
    assert c['ai_scope_guide'] == 'folder' and c['ai_scope_skills'] == 'all' and c['ai_style_where'] == 'off'
