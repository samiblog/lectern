"""설정 원문 보기 (D160 — rawfiles.py, /api/raw/list·/api/raw): 원문 줄은 파일 그대로 번호와 함께, 설명 줄은 번호 없이.
읽는 자리는 목록의 것뿐 — 스킬 폴더 밖·숨김은 막는다"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import write

from lectern import aistatus, rawfiles
from lectern.config import DEFAULTS, Config
from lectern.paths import skills_dir, web_dir
from lectern.server import create_app
from lectern.state import AppState

STYLE = web_dir() / 'help' / 'research-writing.md'
STYLES = aistatus.lectern_styles(web_dir() / 'help')


def lines_of(got):
    """파일 줄만 — 설명 줄을 빼면 원문과 같아야 한다"""
    return [r['text'] for r in got['rows'] if 'n' in r]


def notes_before(got, text):
    """그 원문 줄 바로 앞의 설명 줄들"""
    out, buf = [], []
    for r in got['rows']:
        if 'note' in r:
            buf.append(r['note'])
        else:
            if r['text'] == text:
                return buf
            buf = []
    return out


def test_every_setting_has_a_meaning():
    assert set(rawfiles.CONFIG_DOCS) == set(DEFAULTS)


@pytest.fixture
def env(tmp_path):
    home = tmp_path / 'home'
    proj = tmp_path / 'proj'
    write(proj / 'README.md', '# 읽어 보기\n')
    cfg = tmp_path / 'config.json'
    data = dict(DEFAULTS)
    data['font_scale'] = 'big'          # 형식이 틀린 값
    data['mystery'] = 1                 # Lectern 이 쓰지 않는 열쇠
    del data['csv_stats']               # 파일에 없는 설정
    cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    write(home / '.claude' / 'settings.json', json.dumps({'outputStyle': 'Explanatory', 'permissions': {'allow': ['Bash(ls:*)'], 'deny': []},
                                                          'env': {'TOKEN': 'secret'}, 'somethingNew': True}, indent=2))
    write(home / '.claude' / 'output-styles' / 'terse.md', '---\nname: 짧게\ndescription: 짧은 답\nkeep-coding-instructions: true\n---\n본문\n')
    shutil.copytree(skills_dir() / 'lectern-to-docx', home / '.claude' / 'skills' / 'lectern-to-docx', ignore=shutil.ignore_patterns('__pycache__'))
    write(proj / '.claude' / 'settings.local.json', json.dumps({'outputStyle': '리서치 글쓰기'}))
    groups = rawfiles.catalog(home, 'claude', cfg, skills_dir(), STYLES, proj, 'proj')
    return groups, home, proj, cfg


def test_catalog(env):
    groups, home, proj, cfg = env
    names = [g['group'] for g in groups]
    assert names == ['Lectern', 'Claude Code — 개인 폴더', '이 폴더 — proj', 'Lectern 에 든 것']
    ids = {it['id']: it for g in groups for it in g['items']}
    assert ids['config']['path'] == str(cfg) and ids['config']['exists']
    assert ids['rules']['path'] == str(home / '.claude' / 'rules' / 'lectern.md') and not ids['rules']['exists']
    assert ids['voice']['path'].endswith('내-문체.md')
    assert ids['style:terse.md']['exists'] and ids['skill:lectern-to-docx']['exists'] and not ids['skill:pptx-to-lectern']['exists']
    assert ids['csettings-local']['exists'] and not ids['csettings-shared']['exists']
    assert ids['lstyle:research']['path'] == str(STYLE) and ids['lskill:lectern-to-pptx']['exists']
    assert [i for i in ids if i.startswith('lstyle:')] == ['lstyle:research', 'lstyle:brief', 'lstyle:academic', 'lstyle:plain']
    assert not any(i.startswith('pskill:') for i in ids)   # 이 폴더에 없는 스킬은 목록에 넣지 않는다


def test_config_rows_keep_the_file_and_explain_each_key(env):
    groups, home, proj, cfg = env
    got = rawfiles.read(groups, 'config')
    assert lines_of(got) == cfg.read_text(encoding='utf-8').split('\n')
    assert [r['n'] for r in got['rows'] if 'n' in r] == list(range(1, len(lines_of(got)) + 1))
    assert got['rows'][0]['note'].startswith('Lectern 의 설정 — 모든 폴더와 창에 듣는다')
    lang = notes_before(got, '  "language": "auto",')
    assert lang == ["화면 언어 — auto(Windows 표시 언어)·ko·en. 바꾸면 화면을 다시 불러온다 · 기본 \"auto\" · 바꾸는 곳: 설정 창 '일반'"]
    assert notes_before(got, '  "editor": null,') == ["코드 파일을 열 편집기의 전체 경로 — null 이면 VS Code(code) · 기본 null · 바꾸는 곳: 이 파일에서만 — 설정 창 '고급'의 '설정 파일 열기'"]
    assert '바꾸는 곳: Lectern 이 기록 — 고칠 일 없음' in notes_before(got, '  "projects": {},')[0]
    assert notes_before(got, '  "font_scale": "big",')[-1] == '형식이 틀려 기본값으로 돌고 있습니다'
    assert notes_before(got, '  "mystery": 1') == ['Lectern 이 쓰지 않는 열쇠입니다']
    assert got['rows'][-1] == {'note': '파일에 없는 설정은 기본값으로 돈다: csv_stats'}


def test_broken_config_is_still_shown(tmp_path):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{ "language": "ko", }', encoding='utf-8')
    groups = rawfiles.catalog(tmp_path, 'claude', cfg, skills_dir(), STYLES, None)
    got = rawfiles.read(groups, 'config')
    assert lines_of(got) == ['{ "language": "ko", }']
    assert any('JSON 으로 읽지 못하는 파일입니다' in r.get('note', '') for r in got['rows'])


def test_claude_settings_raw_with_meanings(env):
    groups, *_ = env
    got = rawfiles.read(groups, 'csettings')
    assert '"TOKEN": "secret"' in '\n'.join(lines_of(got))   # 원문 그대로 (사용자 요청 — 머리가 조심하라고 알린다)
    assert '비밀 값이 있을 수 있으니' in got['rows'][0]['note']
    assert notes_before(got, '  "outputStyle": "Explanatory",')[0].startswith('출력 스타일 — ')
    assert notes_before(got, '    "allow": [') == ['묻지 않고 해도 되는 일']
    assert notes_before(got, '    "deny": []') == ['하면 안 되는 일']
    assert notes_before(got, '  "somethingNew": true') == ['Claude Code 의 설정 — 뜻은 Claude Code 설명서의 settings 장']
    local = rawfiles.read(groups, 'csettings-local')
    assert '/output-style 로 고른 값이 여기에' in local['rows'][0]['note']


def test_style_and_skill_heads(env):
    groups, *_ = env
    got = rawfiles.read(groups, 'style:terse.md')
    assert notes_before(got, 'keep-coding-instructions: true') == ['true 면 Claude Code 의 개발 지침을 남긴다 — 없거나 false 면 뺀다']
    assert notes_before(got, 'name: 짧게')[0] == '스타일 이름 — /output-style 목록과 설정 값 outputStyle 에 쓰인다'
    lst = rawfiles.read(groups, 'lstyle:research')
    assert lst['rows'][0]['note'].startswith('Lectern 에 든 글쓰기 스타일') and lines_of(lst) == STYLE.read_text(encoding='utf-8').split('\n')
    sk = rawfiles.read(groups, 'skill:lectern-to-docx')
    assert sk['sub'] == 'SKILL.md' and sk['rows'][0]['note'].startswith('스킬 — ')
    rels = [f['rel'] for f in sk['files']]
    assert 'SKILL.md' in rels and any(r.startswith('scripts/') for r in rels) and not any('__pycache__' in r for r in rels)
    script = next(r for r in rels if r.endswith('.py'))
    py = rawfiles.read(groups, 'skill:lectern-to-docx', script)
    assert py['sub'] == script and all('n' in r for r in py['rows'])   # 프로그램에는 설명 줄을 달지 않는다
    docx = next((r for r in rels if r.endswith('.docx')), None)
    if docx:
        assert rawfiles.read(groups, 'skill:lectern-to-docx', docx)['reason'] == 'binary'
    missing = rawfiles.read(groups, 'skill:pptx-to-lectern')
    assert missing['rows'] == [] and missing['reason'] == 'missing'


def test_only_listed_places(env):
    groups, home, proj, cfg = env
    assert rawfiles.read(groups, 'nope') is None
    assert rawfiles.read(groups, 'style:../settings.json') is None
    assert rawfiles.read(groups, 'skill:lectern-to-docx', '../../settings.json') is None
    assert rawfiles.read(groups, 'skill:lectern-to-docx', 'C:/Windows/win.ini') is None
    write(home / '.claude' / 'skills' / 'lectern-to-docx' / '.hidden.md', '숨김\n')
    assert rawfiles.read(groups, 'skill:lectern-to-docx', '.hidden.md') is None


def test_big_file(tmp_path, monkeypatch):
    cfg = tmp_path / 'config.json'
    cfg.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(rawfiles, 'MAX_TEXT', 1)
    groups = rawfiles.catalog(tmp_path, 'claude', cfg, skills_dir(), STYLES, None)
    assert rawfiles.read(groups, 'config')['reason'] == 'big'


def test_other_tool(tmp_path):
    write(tmp_path / '.codex' / 'AGENTS.md', '# 내 지침\n')
    groups = rawfiles.catalog(tmp_path, 'codex', tmp_path / 'c.json', skills_dir(), STYLES, None)
    ids = [it['id'] for g in groups for it in g['items']]
    assert 'csettings' not in ids and 'voice' not in ids and groups[1]['group'] == 'Codex — 개인 폴더'
    got = rawfiles.read(groups, 'rules', cli='Codex')
    assert got['path'] == str(tmp_path / '.codex' / 'AGENTS.md') and 'Codex 가 모든 프로젝트에서 읽는 개인 지시 파일' in got['rows'][0]['note']


def test_api(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    write(home / '.claude' / 'rules' / 'lectern.md', 'Lectern 요약\n')
    monkeypatch.setenv('LECTERN_HOME', str(home))
    proj = tmp_path / 'proj'
    write(proj / 'README.md', '# 읽어 보기\n')
    st = AppState(Config(), mode='browser')
    st.open(proj)
    try:
        client = create_app(st).test_client()
        groups = client.get(f'/api/raw/list?p={st.active}').get_json()['groups']
        assert [g['group'] for g in groups][2] == '이 폴더 — proj'
        got = client.get('/api/raw?id=rules').get_json()
        assert got['path'] == str(home / '.claude' / 'rules' / 'lectern.md') and got['rows'][-1] == {'n': 2, 'text': ''}
        assert client.get('/api/raw?id=config').get_json()['rows'][0]['note'].startswith('Lectern 의 설정')
        assert client.get('/api/raw?id=nope').status_code == 404
        assert client.get('/api/raw?id=lskill:lectern-to-docx&f=../../lectern/config.py').status_code == 404
    finally:
        st.close()
