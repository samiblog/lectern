"""md 문서의 내 스타일 (D103)"""
import json

import pytest

from lectern import editing, mdstyles

MARKS = ['제{1}조', '{①}', '{1}.']


@pytest.fixture()
def config(tmp_path, monkeypatch):
    monkeypatch.setenv('LECTERN_CONFIG_DIR', str(tmp_path))
    return tmp_path


def test_save_makes_one_new_file_and_lists_it(config):
    style = mdstyles.save_style('회사 규정', 'prose', MARKS)
    assert style == {'name': '회사 규정', 'kind': 'prose', 'marks': MARKS}
    assert [p.name for p in (config / 'md-styles').iterdir()] == ['회사 규정.json']
    assert mdstyles.list_styles() == [style]


def test_save_never_overwrites(config):
    mdstyles.save_style('같은 이름', 'prose', MARKS)
    before = (config / 'md-styles' / '같은 이름.json').read_bytes()
    with pytest.raises(editing.EditError) as e:
        mdstyles.save_style('같은 이름', 'outline', ['□'])
    assert e.value.status == 409
    assert (config / 'md-styles' / '같은 이름.json').read_bytes() == before


@pytest.mark.parametrize('name', ['', '  ', '../밖', 'a/b', 'a\\b', 'a:b', '.숨김', '끝점.', 'CON', 'x' * 41, None, 3])
def test_save_refuses_bad_names(config, name):
    with pytest.raises(editing.EditError):
        mdstyles.save_style(name, 'prose', MARKS)
    assert not (config / 'md-styles').exists()


@pytest.mark.parametrize('kind, marks', [('이상함', MARKS), (None, MARKS), ('prose', []), ('prose', ['', '']), ('prose', 'x'), ('prose', [1]), ('prose', ['x'] * 7), ('prose', ['x' * 17])])
def test_save_refuses_bad_shapes(config, kind, marks):
    with pytest.raises(editing.EditError):
        mdstyles.save_style('이름', kind, marks)


def test_list_skips_what_it_cannot_read(config):
    folder = config / 'md-styles'
    folder.mkdir()
    (folder / '깨짐.json').write_text('{', encoding='utf-8')
    (folder / '틀림.json').write_text(json.dumps({'kind': 'x', 'marks': MARKS}), encoding='utf-8')
    (folder / '글.txt').write_text('아님', encoding='utf-8')
    (folder / '좋음.json').write_text(json.dumps({'kind': 'outline', 'marks': ['□']}), encoding='utf-8')
    assert [x['name'] for x in mdstyles.list_styles()] == ['좋음']


def test_list_is_empty_without_the_folder(config):
    assert mdstyles.list_styles() == []
