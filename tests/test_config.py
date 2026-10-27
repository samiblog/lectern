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
    edited['editor'] = r'C:\Tools\Code\code.cmd'          # 실행 중에 사용자가 편집기로 고침
    path.write_text(json.dumps(edited, ensure_ascii=False, indent=4), encoding='utf-8')
    assert cfg.get('editor') == r'C:\Tools\Code\code.cmd'  # 바로 반영
    cfg.update_client({'math': False})
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['editor'] == r'C:\Tools\Code\code.cmd' and saved['theme'] == 'dark' and saved['math'] is False


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
    from lectern.config import MAX_DOC_TABS, MAX_POSITIONS, MAX_PROJECTS

    cfg = Config(tmp_path / 'config.json')
    for i in range(MAX_PROJECTS + 3):
        cfg.remember_position(rf'C:\p{i}', 'a.md', 10)
    for i in range(MAX_POSITIONS + 5):
        cfg.remember_position(r'C:\p0', f'd{i}.md', i)
    assert len(cfg.get('projects')) == MAX_PROJECTS
    pos = cfg.position(r'C:\P0')                              # 대소문자 무시 (Windows 경로)
    assert pos['doc'] == f'd{MAX_POSITIONS + 4}.md' and len(pos['scroll']) == MAX_POSITIONS
    assert cfg.position(r'C:\nowhere') == {'doc': None, 'scroll': {}, 'docs': []}
    docs = [f'd{i}.md' for i in range(MAX_DOC_TABS + 1)]
    cfg.remember_position(r'C:\p0', 'd1.md', 3, docs)   # 문서 탭은 20개까지 (D64·D67)
    assert MAX_DOC_TABS == 20 and cfg.position(r'C:\p0')['docs'] == docs[:MAX_DOC_TABS]


def test_old_and_broken_positions(tmp_path):
    path = tmp_path / 'config.json'
    # 창을 나누던 때(v0.6)의 기록: doc 이 선택된 창의 문서였다. panes·active 는 읽지 않고, 다시 쓰면 없어진다
    path.write_text(json.dumps({'projects': {
        os.path.normcase(r'C:\old'): {'doc': 'b.md', 'scroll': {'a.md': 3, 'b.md': 7},
                                     'panes': [{'doc': 'a.md', 'scroll': 3}, {'doc': 'b.md', 'scroll': 7}], 'active': 1},
        os.path.normcase(r'C:\bad'): {'doc': 5, 'scroll': {'y.md': 'z', 'w.md': 2}},
    }}), encoding='utf-8')
    cfg = Config(path)
    assert cfg.position(r'C:\old') == {'doc': 'b.md', 'scroll': {'a.md': 3, 'b.md': 7}, 'docs': ['b.md']}   # docs 가 없던 기록은 doc 하나
    assert cfg.position(r'C:\bad') == {'doc': None, 'scroll': {'w.md': 2}, 'docs': []}   # 손으로 망가뜨린 값은 버린다
    cfg.remember_position(r'C:\old', 'a.md', 30)
    assert cfg.get('projects')[os.path.normcase(r'C:\old')] == {'doc': 'a.md', 'scroll': {'b.md': 7, 'a.md': 30}, 'docs': ['a.md']}
    # 1e400 은 JSON 으로 맞지만 inf 로 읽힌다 — 내보내면 화면이 받는 JSON 이 깨지므로 버린다
    text = json.dumps({'projects': {os.path.normcase(r'C:\big'): {'doc': 'z.md', 'scroll': {'z.md': 1, 'w.md': 5}}}})
    path.write_text(text.replace('"z.md": 1,', '"z.md": 1e400,'), encoding='utf-8')
    big = Config(path).position(r'C:\big')
    assert big['scroll'] == {'w.md': 5}
    json.dumps(big, allow_nan=False)


def test_tabs_are_recorded(tmp_path):
    from lectern.config import MAX_TABS

    path = tmp_path / 'config.json'
    cfg = Config(path)
    cfg.set_tabs([r'C:\a', r'C:\b'], 1)
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['tabs'] == [r'C:\a', r'C:\b'] and saved['active_tab'] == 1
    cfg.set_tabs([rf'C:\p{i}' for i in range(MAX_TABS + 2)], 99)   # 상한을 넘는 것은 자르고, 없는 순번은 첫 탭
    assert len(cfg.get('tabs')) == MAX_TABS and cfg.get('active_tab') == 0
    path.write_text(json.dumps({'tabs': r'C:\a', 'active_tab': 'x'}), encoding='utf-8')   # 손으로 고친 틀린 형식
    cfg = Config(path)
    assert cfg.get('tabs') == [] and cfg.get('active_tab') == 0 and 'tabs' in cfg.load_error


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
    c.update_client({'doc_width': 1.5})                          # 문서 폭 (D68) — 화면에서 바꿀 수 있는 키
    c.update_client({'doc_width': 'wide'})
    assert c.get('doc_width') == 1.5

def test_tree_shows_file_names_from_version_2(tmp_path):
    from lectern.config import CONFIG_VERSION

    path = tmp_path / 'config.json'
    assert Config(path).get('show_titles') is False and CONFIG_VERSION == 2      # 새로 깔면 파일 이름
    # 옛 판(1)의 파일은 기본값도 함께 적혀 있어 show_titles: true 가 사용자가 고른 것인지 알 수 없다 — 한 번 파일 이름으로
    path.write_text(json.dumps({'version': 1, 'show_titles': True, 'theme': 'nord'}), encoding='utf-8')
    cfg = Config(path)
    assert cfg.get('show_titles') is False and cfg.get('version') == 2 and cfg.get('theme') == 'nord' and cfg.load_error is None
    assert json.loads(path.read_text(encoding='utf-8'))['version'] == 1          # 파일은 다음에 저장할 때 바뀐다
    cfg.update_client({'show_titles': True})                                     # 그 뒤에 다시 켜면 그대로 남는다
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['version'] == 2 and saved['show_titles'] is True and Config(path).get('show_titles') is True


def test_others_layout_settings(tmp_path):
    path = tmp_path / 'config.json'
    cfg = Config(path)
    assert cfg.get('others_visible') is True and cfg.get('others_height') is None
    cfg.update_client({'others_visible': False, 'others_height': 240})
    cfg.update_client({'others_height': 'tall'})                                # 형식이 틀리면 버린다
    assert cfg.get('others_visible') is False and cfg.get('others_height') == 240
    cfg.update_client({'others_height': None})                                  # 두 번 누르면 기본 높이
    assert cfg.get('others_height') is None


def test_files_view_setting(tmp_path):
    cfg = Config(tmp_path / 'config.json')
    assert cfg.get('files_view') == 'kind'                                     # 종류별 (문서 트리 위, 파일 아래)
    cfg.update_client({'files_view': 'folder'})
    assert cfg.get('files_view') == 'folder'


def test_terminal_settings(tmp_path):
    path = tmp_path / 'config.json'
    cfg = Config(path)
    assert cfg.get('terminal_shell') is None and cfg.get('terminal_width') is None
    cfg.update_client({'terminal_width': 520, 'terminal_shell': r'C:\evil.exe'})   # 셸은 화면에서 바꿀 수 없다 (파일만)
    assert cfg.get('terminal_width') == 520 and cfg.get('terminal_shell') is None
    cfg.update_client({'terminal_width': None})
    assert cfg.get('terminal_width') is None
    path.write_text(json.dumps({'terminal_shell': r'C:\Program Files\PowerShell\7\pwsh.exe', 'terminal_width': 'wide'}), encoding='utf-8')
    cfg = Config(path)
    assert cfg.get('terminal_shell') == r'C:\Program Files\PowerShell\7\pwsh.exe' and cfg.get('terminal_width') is None


def test_terminal_position_settings(tmp_path):
    # 터미널 자리 (D52): auto | side | bottom, 아래에 둘 때의 높이
    cfg = Config(tmp_path / 'config.json')
    assert cfg.get('terminal_position') == 'auto' and cfg.get('terminal_height') is None
    cfg.update_client({'terminal_position': 'bottom', 'terminal_height': 300})
    assert cfg.get('terminal_position') == 'bottom' and cfg.get('terminal_height') == 300
    cfg.update_client({'terminal_position': 'top', 'terminal_height': 'tall'})        # 모르는 값은 받지 않는다
    assert cfg.get('terminal_position') == 'bottom' and cfg.get('terminal_height') == 300
    cfg.update_client({'terminal_height': None})
    assert cfg.get('terminal_height') is None


def test_toc_width_setting(tmp_path):
    # 목차 폭 (D47): 경계를 끌면 화면이 저장하고, 두 번 누르면 null(기본 폭). 손으로 틀린 값을 적으면 기본값
    path = tmp_path / 'config.json'
    cfg = Config(path)
    assert cfg.get('toc_width') is None
    cfg.update_client({'toc_width': 320})
    assert cfg.get('toc_width') == 320
    cfg.update_client({'toc_width': None})
    assert cfg.get('toc_width') is None
    path.write_text(json.dumps({'toc_width': 'wide'}), encoding='utf-8')
    cfg = Config(path)
    assert cfg.get('toc_width') is None and 'toc_width' in (cfg.load_error or '')


def test_terminal_follow_style_setting(tmp_path):
    cfg = Config(tmp_path / 'config.json')
    assert cfg.get('terminal_follow_style') is True                             # 터미널 색은 문서 스타일을 따른다
    cfg.update_client({'terminal_follow_style': False})                         # 설정 창에서 끄면 늘 어둡게
    cfg.update_client({'terminal_follow_style': 'no'})                          # 형식이 틀리면 버린다
    assert cfg.get('terminal_follow_style') is False


def test_toc_hidden_parts_setting(tmp_path):
    cfg = Config(tmp_path / 'config.json')
    assert cfg.get('toc_hidden_parts') == []                                    # 목차에 구성 요소를 모두 보인다
    cfg.update_client({'toc_hidden_parts': ['code', 'math']})                  # 목차 머리의 종류 버튼
    cfg.update_client({'toc_hidden_parts': 'code'})                            # 형식이 틀리면 버린다
    assert cfg.get('toc_hidden_parts') == ['code', 'math']


def test_side_sections_settings(tmp_path):
    cfg = Config(tmp_path / 'config.json')
    assert cfg.get('docs_visible') is True and cfg.get('code_visible') is True and cfg.get('code_height') is None
    cfg.update_client({'docs_visible': False, 'code_visible': False, 'code_height': 180})   # 사이드바 '문서'·'코드' 묶음
    cfg.update_client({'code_height': 'big'})                                              # 형식이 틀리면 버린다
    assert cfg.get('docs_visible') is False and cfg.get('code_visible') is False and cfg.get('code_height') == 180
