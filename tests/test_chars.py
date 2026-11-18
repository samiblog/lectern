"""특수 문자 창의 목록 (D165 — web/data/chars.json, charpick.js)"""
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'web' / 'data' / 'chars.json').read_text(encoding='utf-8'))
MARKDOWN = set('*_[]<>|#~$`\\')   # 넣은 글이 서식·표·수식이 되지 않게 — 이런 글자는 넣지 않는다


def all_chars():
    return [c for g in DATA['groups'] for c in g['chars']]


def test_groups_have_names_in_both_languages():
    ids = [g['id'] for g in DATA['groups']]
    assert len(ids) == len(set(ids)) and len(ids) >= 8
    for g in DATA['groups']:
        assert g['ko'].strip() and g['en'].strip() and g['chars']


def test_each_char_is_one_printable_character_with_names():
    for c, ko, en in all_chars():
        assert len(c) == 1, c
        assert unicodedata.category(c)[0] in 'PSNL', (c, unicodedata.category(c))   # 문장 부호·기호·숫자·글자 (빈칸·제어 문자 없음)
        assert ko.strip() and en.strip(), c
        assert en != ko and any('a' <= x.lower() <= 'z' for x in en), (c, en)   # 영어 이름은 영어로 (원 자음 ㉠ 처럼 그 글자는 들어가도 된다)


def test_no_duplicates_and_no_markdown_marks():
    chars = [c for c, _, _ in all_chars()]
    assert len(chars) == len(set(chars))
    assert not MARKDOWN & set(chars)
    assert all(ord(c) > 127 for c in chars)   # ASCII 는 자판으로 친다
    assert len(chars) >= 200


def test_recent_chars_is_a_client_setting(tmp_path):
    from lectern.config import CLIENT_KEYS, DEFAULTS, value_ok
    assert 'recent_chars' in CLIENT_KEYS and DEFAULTS['recent_chars'] == []
    assert value_ok('recent_chars', ['→', '·']) and not value_ok('recent_chars', '→')
