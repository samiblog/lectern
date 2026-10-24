"""내 스타일 (D53): 설정 폴더의 styles\\*.css — 목록, 머리 주석, 인터넷 길 지우기, 서버."""
from __future__ import annotations

import pytest

from conftest import write

from lectern import styles
from lectern.styles import list_styles, parse_head, read_style, sanitize_css

BUILTINS = ['dark', 'default', 'report']


def test_parse_head_reads_name_dark_base():
    head = '/* lectern-style\n   name: 우리 회사 보고서\n   dark: yes\n   base: report\n*/\n:root { --md-bg: #000; }'
    assert parse_head(head, BUILTINS) == {'name': '우리 회사 보고서', 'dark': True, 'base': 'report', 'head': True}
    # 별표로 줄을 시작해도, @charset 이 앞에 있어도 된다. 없는 바탕 스타일은 밝기에 따라 default / dark
    assert parse_head('@charset "utf-8";\n/* Lectern-Style\n * name: A\n * base: nope\n */', BUILTINS)['base'] == 'default'
    assert parse_head('/* lectern-style\n dark: 예\n*/', BUILTINS)['base'] == 'dark'
    # 머리 주석이 없으면 이름은 비우고(파일 이름을 쓴다) 밝음
    assert parse_head('/* 그냥 주석 */ :root {}', BUILTINS) == {'name': '', 'dark': False, 'base': 'default', 'head': False}


def test_list_styles_only_plain_css_files(tmp_path):
    write(tmp_path / '회사.css', '/* lectern-style\nname: 회사 보고서\n*/')
    write(tmp_path / '2-밤.css', '/* lectern-style\ndark: yes\n*/')
    write(tmp_path / '10-a.css', ':root {}')
    write(tmp_path / '.숨김.css', ':root {}')
    write(tmp_path / 'sub' / 'x.css', ':root {}')
    write(tmp_path / 'notes.txt', 'x')
    found = list_styles(tmp_path)
    assert [s['id'] for s in found] == ['user:2-밤', 'user:10-a', 'user:회사']   # 자연 정렬
    first = found[0]
    assert first['name'] == '2-밤' and first['dark'] and first['base'] == 'dark' and first['file'] == '2-밤.css' and first['mtime'] > 0
    assert found[2]['name'] == '회사 보고서' and found[2]['base'] == 'default'
    assert list_styles(tmp_path / 'none') == []


@pytest.mark.parametrize('css', [
    '@import url("https://fonts.example/a.css");',
    "@import 'https://x/y.css' screen;",
    'body { background: url(https://tracker.example/p.png); }',
    'body { background: url( "//tracker.example/p.png" ); }',
    'body { background: \\75 rl(https://tracker.example/p.png); }',
    'body { background: u\\rl(https://tracker.example/p.png); }',
    'body { background-image: image-set("https://x/a.png" 1x); }',
    '@font-face { font-family: X; src: url(https://fonts.example/x.woff2); }',
])
def test_sanitize_removes_internet_requests(css):
    out = sanitize_css(css).lower()
    assert 'https://' not in out.replace('/* @import', '') or '@import' not in out
    assert 'url(https' not in out and 'url( "//' not in out and 'image-set(' not in out and '@import url' not in out


def test_sanitize_keeps_data_urls_and_plain_css():
    css = ':root { --md-bg: #fff; }\n.md-body h1 { background: url(data:image/png;base64,AAAA) no-repeat; content: "\\201C"; }'
    assert sanitize_css(css) == css


def test_read_style_refuses_odd_names_and_big_files(tmp_path):
    write(tmp_path / 'a.css', 'body { background: url(http://x/y.png) }')
    assert read_style('a.css', tmp_path) == 'body { background: none }'
    for bad in ('../a.css', 'sub/a.css', 'a.txt', '.a.css', 'nope.css', 'C:\\a.css'):
        assert read_style(bad, tmp_path) is None
    (tmp_path / 'big.css').write_bytes(b'a' * (styles.MAX_STYLE_BYTES + 1))
    assert read_style('big.css', tmp_path) is None
