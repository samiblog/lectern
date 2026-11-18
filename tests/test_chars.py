"""특수 문자 창의 목록 (D165 — web/data/chars.json, charpick.js)"""
import json
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'web' / 'data' / 'chars.json').read_text(encoding='utf-8'))
MARKDOWN = set('*_[]<>|#~$`\\')   # 넣은 글이 서식·표·수식이 되지 않게 — 이런 글자는 넣지 않는다
# Lectern 의 구조를 흉내 내는 글자 (2026-11-18 사용자 결정 — 문서의 안정성이 먼저): 목록(•)·할 일(☐☑☒)처럼 보이지만 아니고(레벨·Word 목록·할 일 수에
# 들지 않는다), 빼기 기호(−)는 표의 숫자로 읽히지 않는다 (숫자 열 정렬·표를 차트로)
STRUCTURE = set('•☐☑☒−')


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
    assert not STRUCTURE & set(chars)
    assert all(ord(c) > 127 for c in chars)   # ASCII 는 자판으로 친다
    assert len(chars) >= 200


def test_recent_chars_is_a_client_setting(tmp_path):
    from lectern.config import CLIENT_KEYS, DEFAULTS, value_ok
    assert 'recent_chars' in CLIENT_KEYS and DEFAULTS['recent_chars'] == []
    assert value_ok('recent_chars', ['→', '·']) and not value_ok('recent_chars', '→')


@pytest.mark.skipif(not all((Path('C:/Windows/Fonts') / f).exists() for f in ('malgun.ttf', 'batang.ttc')), reason='Windows 의 한국어 글꼴이 없다')
def test_every_char_is_in_the_korean_document_fonts():
    # 2026-11-18 사용자 결정 — 문서의 안정성이 먼저: 맑은 고딕(화면·Word 제목·고딕 인쇄)과 바탕(명조 인쇄의 마지막 대체)에 모두 있는 글자만.
    # 없는 글자는 다른 글꼴로 대체돼 화면·PDF·Word 에서 모양이 달라지거나 컬러 이모지가 된다 (✓·✗·☐·⑯~⑳·⁵~⁹·☀·✉ 를 뺐다)
    pymupdf = pytest.importorskip('pymupdf')
    fonts = [pymupdf.Font(fontfile=f'C:/Windows/Fonts/{f}') for f in ('malgun.ttf', 'batang.ttc')]
    missing = [c for c, _, _ in all_chars() if not all(f.has_glyph(ord(c)) for f in fonts)]
    assert not missing, ''.join(missing)
