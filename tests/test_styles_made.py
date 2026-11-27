"""'내 스타일 만들기' (D211): 창이 고른 값으로 설정 폴더 styles 에 CSS 하나 — 새 파일, 또는 그 창이 만든 파일만 고쳐 쓴다."""
import os

import pytest

from lectern.editing import EditError
from lectern.styles import MAKER_MARK, list_styles, made_values, read_style, save_made

VALUES = {'--md-font': '"나눔고딕", "Malgun Gothic", sans-serif', '--md-size': 15, '--md-line': 1.8, '--md-link': '#1D4FBF',
          '--lec-list-top-weight': 700, '--lec-list-top-scale': 1.08}


def test_new_file_has_head_and_only_given_values(tmp_path):
    got = save_made('우리 보고서', 'report', False, VALUES, folder=tmp_path)
    assert got['file'] == '우리 보고서.css' and got['id'] == 'user:우리 보고서'
    text = (tmp_path / '우리 보고서.css').read_text(encoding='utf-8')
    assert text.startswith('/* lectern-style\n   name: 우리 보고서\n   dark: no\n   base: report\n   maker: lectern\n*/\n')
    assert MAKER_MARK in text and '--md-size: 15px;' in text and '--md-line: 1.8;' in text and '--md-link: #1d4fbf;' in text
    assert '--lec-list-top-weight: 700;' in text and '--lec-list-top-scale: 1.08;' in text and '--md-heading' not in text
    style = list_styles(tmp_path)[0]
    assert (style['name'], style['base'], style['maker']) == ('우리 보고서', 'report', True)


def test_values_load_back(tmp_path):
    save_made('밤', 'dark', True, VALUES, folder=tmp_path)
    got = made_values('밤.css', tmp_path)
    assert (got['name'], got['base'], got['dark'], got['copied']) == ('밤', 'dark', True, False)
    assert got['values'] == {**VALUES, '--md-link': '#1d4fbf', '--md-size': 15.0, '--lec-list-top-weight': 700.0}


def test_same_name_is_not_overwritten(tmp_path):
    save_made('a', 'default', False, {}, folder=tmp_path)
    with pytest.raises(EditError) as err:
        save_made('a', 'default', False, VALUES, folder=tmp_path)
    assert err.value.status == 409
    assert '--md-size' not in (tmp_path / 'a.css').read_text(encoding='utf-8')


def test_replace_only_its_own_file_and_only_when_unchanged(tmp_path):
    first = save_made('a', 'default', False, {'--md-size': 15}, folder=tmp_path)
    again = save_made('a 새 이름', 'default', False, {'--md-size': 17}, file='a.css', stamp=first['stamp'], folder=tmp_path)
    text = (tmp_path / 'a.css').read_text(encoding='utf-8')
    assert again['file'] == 'a.css' and '--md-size: 17px;' in text and '15px' not in text and 'name: a 새 이름' in text
    with pytest.raises(EditError) as err:   # 불러온 뒤 바뀌었으면 (옛 stamp)
        save_made('a', 'default', False, {'--md-size': 18}, file='a.css', stamp=first['stamp'], folder=tmp_path)
    assert err.value.status == 409 and '17px' in (tmp_path / 'a.css').read_text(encoding='utf-8')
    (tmp_path / 'hand.css').write_text('/* lectern-style\n   name: 손\n*/\n:root { --md-size: 14px; }\n', encoding='utf-8')
    with pytest.raises(EditError) as err:   # 손으로 쓴 파일은 고치지 않는다
        save_made('손', 'default', False, {'--md-size': 18}, file='hand.css', stamp='x', folder=tmp_path)
    assert err.value.status == 404 and '14px' in (tmp_path / 'hand.css').read_text(encoding='utf-8')
    assert not [p for p in os.listdir(tmp_path) if p.startswith('.')], '임시 파일이 남지 않는다'


def test_copy_keeps_the_hand_written_rules(tmp_path):
    hand = '/* lectern-style\n   name: 회사\n   base: office\n*/\n.md-body h1 { border-bottom: 3px solid red; }\n'
    (tmp_path / '회사.css').write_text(hand, encoding='utf-8')
    save_made('회사 2', 'office', False, {'--md-size': 15}, copy='회사.css', folder=tmp_path)
    text = (tmp_path / '회사 2.css').read_text(encoding='utf-8')
    assert '/* lectern-base: 회사.css */\n.md-body h1 { border-bottom: 3px solid red; }' in text
    assert text.index('border-bottom') < text.index(MAKER_MARK), '값은 옮긴 규칙 뒤에 (이긴다)'
    assert (tmp_path / '회사.css').read_text(encoding='utf-8') == hand, '원래 파일은 그대로'
    got = made_values('회사 2.css', tmp_path)
    assert got['copied'] and got['values'] == {'--md-size': 15.0}
    again = save_made('회사 2', 'office', False, {'--md-size': 16}, file='회사 2.css', stamp=got['stamp'], folder=tmp_path)
    text = (tmp_path / '회사 2.css').read_text(encoding='utf-8')
    assert again and 'border-bottom: 3px solid red' in text and '--md-size: 16px;' in text and text.count(MAKER_MARK) == 1


@pytest.mark.parametrize('values', [
    {'--md-font': 'x; } body { display: none'}, {'--md-font': 'url(http://a/b)'}, {'--md-font': 'a/*b'}, {'--md-font': 'a\\62'},
    {'--md-link': 'red'}, {'--md-link': '#12345'}, {'--md-size': 99}, {'--md-size': '15'}, {'--md-size': True}, {'--md-line': 9},
    {'--md-bg': '#ffffff'}, {'color': '#ffffff'},
])
def test_bad_values_are_refused(tmp_path, values):
    with pytest.raises(EditError) as err:
        save_made('x', 'default', False, values, folder=tmp_path)
    assert err.value.status == 400 and not list(tmp_path.iterdir())


@pytest.mark.parametrize('name', ['', '.x', 'a/b', 'a:b', 'con', 'x' * 41, None])
def test_bad_names_are_refused(tmp_path, name):
    with pytest.raises(EditError):
        save_made(name, 'default', False, {}, folder=tmp_path)


def test_base_must_be_a_builtin_style(tmp_path):
    with pytest.raises(EditError):
        save_made('x', 'user:a', False, {}, folder=tmp_path)


def test_served_css_is_the_saved_css(tmp_path):
    save_made('x', 'default', False, VALUES, folder=tmp_path)
    assert '"나눔고딕"' in read_style('x.css', tmp_path)


def test_window_fields_match_the_server():
    """화면의 칸(stylemaker.js FIELDS)과 서버가 받는 값(MAKER_VARS)이 같은 열하나이고 범위도 같다"""
    import re
    from pathlib import Path

    from lectern.styles import MAKER_VARS
    src = (Path(__file__).resolve().parent.parent / 'web/js/stylemaker.js').read_text(encoding='utf-8')
    fields = re.findall(r"\{ key: '(--[a-z-]+)', group: '\w+', label: [^,]+, kind: '(\w+)'(?:, min: ([\d.]+), max: ([\d.]+))?", src)
    assert [k for k, *_ in fields] == list(MAKER_VARS)
    for key, kind, lo, hi in fields:
        spec = MAKER_VARS[key]
        if kind in ('px', 'num'):
            assert (float(lo), float(hi)) == (spec[1], spec[2]), key
        if kind == 'percent':
            assert (float(lo) / 100, float(hi) / 100) == (spec[1], spec[2]), key

