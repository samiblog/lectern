from __future__ import annotations

import json
import os

from lectern.config import Config


def test_missing_file_uses_defaults_and_saves(tmp_path):
    path = tmp_path / 'config.json'
    cfg = Config(path)
    assert cfg.load_error is None and cfg.get('theme') == 'auto'
    cfg.add_recent('C:\\work\\proj')
    assert json.loads(path.read_text(encoding='utf-8'))['last_folder'] == 'C:\\work\\proj'


def test_broken_file_is_never_overwritten(tmp_path):
    path = tmp_path / 'config.json'
    broken = '{\n  "editor": "C:\\Tools\\code.cmd",\n  "exclude_dirs": ["data"]\n}\n'   # 역슬래시를 하나만 쓴 흔한 실수
    path.write_text(broken, encoding='utf-8')
    cfg = Config(path)
    assert cfg.get('editor') is None                          # 기본 설정으로 실행
    assert '2행' in cfg.load_error and '\\\\' in cfg.load_error   # 위치와 고치는 법을 알려 줌
    cfg.add_recent('C:\\work\\proj')
    cfg.update_client({'theme': 'dark'})
    cfg.set_window(900, 700)
    assert path.read_text(encoding='utf-8') == broken         # 손으로 고친 내용이 그대로 남음


def test_bom_is_accepted(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('\ufeff{"theme": "dark"}', encoding='utf-8')   # 메모장·PowerShell 5.1 이 붙이는 BOM
    cfg = Config(path)
    assert cfg.load_error is None and cfg.get('theme') == 'dark'


def test_non_object_is_an_error(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('["theme"]', encoding='utf-8')
    cfg = Config(path)
    assert cfg.load_error and cfg.get('theme') == 'auto'


def test_outside_edits_are_kept(tmp_path):
    path = tmp_path / 'config.json'
    cfg = Config(path)
    cfg.update_client({'theme': 'dark'})
    edited = json.loads(path.read_text(encoding='utf-8'))
    edited['editor'] = 'C:\Tools\Code\code.cmd'          # 실행 중에 사용자가 편집기로 고침
    path.write_text(json.dumps(edited, ensure_ascii=False, indent=4), encoding='utf-8')
    assert cfg.get('editor') == 'C:\Tools\Code\code.cmd'  # 바로 반영
    cfg.update_client({'math': False})
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['editor'] == 'C:\Tools\Code\code.cmd' and saved['theme'] == 'dark' and saved['math'] is False


def test_saving_resumes_after_file_is_fixed(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{ "theme": "dark", }', encoding='utf-8')
    cfg = Config(path)
    assert cfg.load_error
    path.write_text('{ "theme": "dark" }', encoding='utf-8')   # 사용자가 고침
    cfg.update_client({'math': False})
    assert cfg.load_error is None and json.loads(path.read_text(encoding='utf-8')) | {} == cfg.public()
    assert cfg.get('theme') == 'dark'


def test_positions_are_bounded(tmp_path):
    from lectern.config import MAX_POSITIONS, MAX_PROJECTS

    cfg = Config(tmp_path / 'config.json')
    for i in range(MAX_PROJECTS + 3):
        cfg.remember_position(rf'C:\p{i}', [('a.md', 10)])
    for i in range(MAX_POSITIONS + 5):
        cfg.remember_position(r'C:\p0', [(f'd{i}.md', i)])
    assert len(cfg.get('projects')) == MAX_PROJECTS
    pos = cfg.position(r'C:\P0')                              # 대소문자 무시 (Windows 경로)
    assert pos['doc'] == f'd{MAX_POSITIONS + 4}.md' and len(pos['scroll']) == MAX_POSITIONS
    assert cfg.position(r'C:\nowhere') == {'doc': None, 'scroll': {}, 'panes': [], 'active': 0}


def test_positions_keep_panes(tmp_path):
    from lectern.config import MAX_PANES

    path = tmp_path / 'config.json'
    cfg = Config(path)
    cfg.remember_position(r'C:\p', [('a.md', 10), ('b.md', 20), ('a.md', 30), ('c.md', 1)], active=2)
    pos = cfg.position(r'C:\p')
    assert pos['panes'] == [{'doc': 'a.md', 'scroll': 10}, {'doc': 'b.md', 'scroll': 20}, {'doc': 'a.md', 'scroll': 30}][:MAX_PANES]
    assert pos['active'] == 2 and pos['doc'] == 'a.md' and pos['scroll'] == {'b.md': 20, 'a.md': 30}
    # 창을 나누기 전의 기록은 창 하나로, 손으로 망가뜨린 값은 버린다
    path.write_text(json.dumps({'projects': {
        os.path.normcase(r'C:\old'): {'doc': 'x.md', 'scroll': {'x.md': 7}},
        os.path.normcase(r'C:\bad'): {'doc': 'y.md', 'panes': [{'doc': 'y.md', 'scroll': 'z'}, 3, {}], 'active': 5},
    }}), encoding='utf-8')
    cfg = Config(path)
    assert cfg.position(r'C:\old')['panes'] == [{'doc': 'x.md', 'scroll': 7}]
    bad = cfg.position(r'C:\bad')
    assert bad['panes'] == [{'doc': 'y.md', 'scroll': 0}] and bad['active'] == 0
    # 1e400 은 JSON 으로 맞지만 inf 로 읽힌다 — 내보내면 화면이 받는 JSON 이 깨지므로 버린다
    text = json.dumps({'projects': {os.path.normcase(r'C:\big'): {'doc': 'z.md', 'scroll': {'z.md': 1, 'w.md': 5},
                                                                   'panes': [{'doc': 'z.md', 'scroll': 1}]}}})
    path.write_text(text.replace('"scroll": 1}', '"scroll": 1e400}').replace('"z.md": 1,', '"z.md": 1e400,'), encoding='utf-8')
    big = Config(path).position(r'C:\big')
    assert big['panes'] == [{'doc': 'z.md', 'scroll': 0}] and big['scroll'] == {'w.md': 5}
    json.dumps(big, allow_nan=False)


def test_wrong_value_types_fall_back_and_are_reported(tmp_path):
    # 손으로 고치는 파일이라 JSON 은 맞아도 값의 형식이 틀릴 수 있다 (점검에서 발견: 트리·폴더 열기·편집기 열기가 500)
    path = tmp_path / 'config.json'
    text = json.dumps({'theme': 'paper', 'exclude_dirs': 'node_modules', 'html_exclude_dirs': 1, 'editor': 5,
                       'math': 'no', 'recent': ['C:\a', 3], 'window': [800, 600]})
    path.write_text(text, encoding='utf-8')
    c = Config(path)
    assert c.get('theme') == 'paper'                       # 맞는 값은 그대로
    assert c.get('exclude_dirs') == [] and c.get('html_exclude_dirs') == [] and c.get('editor') is None
    assert c.get('math') is True and c.get('recent') == [] and c.get('window') == {'width': 1280, 'height': 860}
    assert 'exclude_dirs' in c.load_error and 'editor' in c.load_error
    c.update_client({'theme': 'nord'})
    assert path.read_text(encoding='utf-8') == text        # 고칠 때까지 저장하지 않는다 (손으로 쓴 값을 지우지 않게)
    c.update_client({'theme': 5, 'math': 'yes'})          # 화면에서 오는 값도 형식이 틀리면 버린다
    assert c.get('theme') == 'nord' and c.get('math') is True


def test_font_scale_accepts_whole_numbers(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'font_scale': 2}), encoding='utf-8')
    c = Config(path)
    assert c.get('font_scale') == 2 and c.load_error is None    # 정수로 적어도 된다
    c.update_client({'font_scale': 1.35})
    c.update_client({'font_scale': 'big'})                        # 형식이 틀리면 버린다
    assert c.get('font_scale') == 1.35
