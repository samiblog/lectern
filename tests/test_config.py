from __future__ import annotations

import json

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
