"""내 도해 스타일·내 색 조합 (D215) — 설정 폴더 diagram-styles 의 json 을 읽기만 하고, 정해진 열쇠·범위만 넘긴다 (lectern/mydiagrams.py)."""
import json
import os
import sys

import pytest

from lectern import config, mydiagrams


def write(folder, name, data):
    path = folder / name
    path.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


GOOD_STYLE = {'kind': 'style', 'number': 11, 'name': '우리 회사', 'tip': '남색 띠, 직각 선', 'base': 8, 'corner': 4, 'border': 1.5, 'line': 'step',
              'line_width': 1.4, 'dash': False, 'shadow': True, 'fill': 'light', 'spacing': 'wide', 'bold': True, 'title': 'band', 'zones': False, 'sketch': False}
GOOD_COLORS = {'kind': 'colors', 'number': 9, 'name': '회사 색', 'series': ['#17304F', '#c41', '#6b7280'], 'strong': '#17304f', 'accent': '#C2410C', 'zones': ['#17304f', '#2f5d8a']}


def test_empty_or_missing_folder(tmp_path):
    got = mydiagrams.load(tmp_path / '없음')
    assert got == {'styles': [], 'colors': [], 'problems': [], 'next': {'style': 11, 'colors': 9}}
    assert mydiagrams.load(tmp_path)['styles'] == []


def test_good_files(tmp_path):
    write(tmp_path, '우리 회사.json', GOOD_STYLE)
    write(tmp_path, '회사 색.json', GOOD_COLORS)
    got = mydiagrams.load(tmp_path)
    assert got['problems'] == []
    st = got['styles'][0]
    assert st == {'n': 11, 'name': '우리 회사', 'tip': '남색 띠, 직각 선', 'file': '우리 회사.json', 'base': 8, 'corner': 4, 'border': 1.5, 'line': 'step',
                  'line_width': 1.4, 'dash': False, 'shadow': True, 'fill': 'light', 'spacing': 'wide', 'bold': True, 'title': 'band', 'zones': False, 'sketch': False}
    co = got['colors'][0]
    assert co['n'] == 9 and co['series'] == ['#17304f', '#cc4411', '#6b7280'] and co['accent'] == '#c2410c' and co['zones'] == ['#17304f', '#2f5d8a']
    assert got['next'] == {'style': 12, 'colors': 10}


def test_bad_values_are_left_out_with_reasons(tmp_path):
    write(tmp_path, 'a.json', {'kind': 'style', 'number': 12, 'name': '가', 'corner': 99, 'line': 'zigzag', 'dash': 'yes', 'base': 11, 'css': '.x{}', 'border': True})
    got = mydiagrams.load(tmp_path)
    assert got['styles'] == [{'n': 12, 'name': '가', 'tip': '', 'file': 'a.json'}]   # 틀린 값은 모두 빠지고 스타일은 남는다
    whys = ' '.join(p['why'] for p in got['problems'])
    for key in ('corner', 'line', 'dash', 'base', 'css', 'border'):
        assert key in whys, key
    assert got['next']['style'] == 11   # 11 은 비었다


@pytest.mark.parametrize('data, word', [
    ({'kind': 'style', 'number': 10, 'name': '가'}, 'number'),          # 기본 번호와 겹친다
    ({'kind': 'style', 'number': 100, 'name': '가'}, 'number'),
    ({'kind': 'style', 'number': 11.0, 'name': '가'}, 'number'),
    ({'kind': 'style', 'number': True, 'name': '가'}, 'number'),
    ({'kind': 'colors', 'number': 8, 'name': '가', 'series': ['#000', '#fff']}, 'number'),
    ({'kind': 'thing', 'number': 11, 'name': '가'}, 'kind'),
    ({'kind': 'style', 'number': 11, 'name': ''}, 'name'),
    ({'kind': 'style', 'number': 11, 'name': '3D 상자'}, 'name'),       # 숫자로 시작하면 '스타일: 3D' 가 3 으로 읽힌다
    ({'kind': 'style', 'number': 11, 'name': '가 · 나'}, 'name'),        # 표시 줄을 나누는 글자
    ({'kind': 'style', 'number': 11, 'name': '가;나'}, 'name'),
    ({'kind': 'style', 'number': 11, 'name': 'x' * 25}, 'name'),
    ({'kind': 'colors', 'number': 9, 'name': '가', 'series': ['#000']}, 'series'),
    ({'kind': 'colors', 'number': 9, 'name': '가', 'series': ['#000', 'red']}, 'series'),
    ({'kind': 'colors', 'number': 9, 'name': '가', 'series': ['#000', 'url(http://x)']}, 'series'),
])
def test_rejected_files(tmp_path, data, word):
    write(tmp_path, 'a.json', data)
    got = mydiagrams.load(tmp_path)
    assert got['styles'] == [] and got['colors'] == []
    assert len(got['problems']) == 1 and got['problems'][0]['file'] == 'a.json' and word in got['problems'][0]['why'], got['problems']


def test_not_json_and_not_object(tmp_path):
    write(tmp_path, 'a.json', '{ 이건 아님')
    write(tmp_path, 'b.json', '[1, 2]')
    got = mydiagrams.load(tmp_path)
    assert [p['file'] for p in got['problems']] == ['a.json', 'b.json']
    assert got['styles'] == []


def test_duplicate_number_older_file_wins(tmp_path):
    """쓰던 번호를 새 파일이 빼앗지 않는다 — 이름 순으로 앞이어도 나중에 생긴 파일은 고칠 것으로 (시나리오가 찾은 것)"""
    write(tmp_path, '우리 회사.json', {'kind': 'style', 'number': 11, 'name': '우리 회사'})
    write(tmp_path, '실수.json', {'kind': 'style', 'number': 11, 'name': '실수'})
    write(tmp_path, '다.json', {'kind': 'colors', 'number': 11, 'name': '다', 'series': ['#000', '#fff']})   # 색은 번호가 따로
    os.utime(tmp_path / '우리 회사.json', (1_700_000_000, 1_700_000_000))
    os.utime(tmp_path / '실수.json', (1_700_000_100, 1_700_000_100))
    got = mydiagrams.load(tmp_path)
    assert [s['name'] for s in got['styles']] == ['우리 회사'] and [c['n'] for c in got['colors']] == [11]
    assert [p['file'] for p in got['problems']] == ['실수.json'] and '11' in got['problems'][0]['why']
    assert got['next'] == {'style': 12, 'colors': 9}


def test_duplicate_number_same_time_by_name(tmp_path):
    for name in ('나.json', '가.json'):
        write(tmp_path, name, {'kind': 'style', 'number': 11, 'name': name[0]})
        os.utime(tmp_path / name, (1_700_000_000, 1_700_000_000))
    got = mydiagrams.load(tmp_path)
    assert [s['name'] for s in got['styles']] == ['가'] and got['problems'][0]['file'] == '나.json'


def test_sorted_by_number_and_bom(tmp_path):
    (tmp_path / 'b.json').write_text(json.dumps({'kind': 'style', 'number': 20, 'name': '나'}), encoding='utf-8-sig')
    write(tmp_path, 'a.json', {'kind': 'style', 'number': 13, 'name': '가'})
    assert [s['n'] for s in mydiagrams.load(tmp_path)['styles']] == [13, 20]


def test_size_limit_and_other_files(tmp_path):
    write(tmp_path, 'big.json', json.dumps({'kind': 'style', 'number': 11, 'name': '가', 'tip': 'x' * (mydiagrams.MAX_BYTES + 10)}))
    write(tmp_path, 'note.txt', 'not a style')
    (tmp_path / 'sub.json').mkdir()
    write(tmp_path, '.hidden.json', {'kind': 'style', 'number': 12, 'name': '숨김'})
    got = mydiagrams.load(tmp_path)
    assert got['styles'] == [] and [p['file'] for p in got['problems']] == ['big.json']


def test_name_and_tip_are_tidied(tmp_path):
    write(tmp_path, 'a.json', {'kind': 'style', 'number': 11, 'name': '  우리   회사 ', 'tip': ' 줄\n바꿈   ' + 'y' * 200})
    st = mydiagrams.load(tmp_path)['styles'][0]
    assert st['name'] == '우리 회사' and st['tip'].startswith('줄 바꿈 ') and len(st['tip']) == mydiagrams.TIP_MAX


def test_too_many_files(tmp_path):
    for i in range(mydiagrams.MAX_FILES + 3):
        write(tmp_path, f'{i:03}.json', {'kind': 'style', 'number': 11 + i % 80, 'name': f'가{i}'})
    got = mydiagrams.load(tmp_path)
    assert len(got['styles']) == mydiagrams.MAX_FILES
    assert any(p['file'] == '' for p in got['problems'])


@pytest.mark.skipif(sys.platform != 'win32' and not hasattr(os, 'symlink'), reason='링크를 만들 수 없음')
def test_links_are_not_followed(tmp_path):
    outside = tmp_path / 'outside.json'
    write(tmp_path, 'outside.json', {'kind': 'style', 'number': 11, 'name': '밖'})
    folder = tmp_path / 'diagram-styles'
    folder.mkdir()
    try:
        os.symlink(outside, folder / 'link.json')
    except OSError:
        pytest.skip('링크를 만들 권한이 없음')
    assert mydiagrams.load(folder)['styles'] == []


def test_numbers_fit_config():
    assert mydiagrams.FIRST_STYLE == config.DIAGRAM_STYLES + 1 and mydiagrams.FIRST_COLORS == config.DIAGRAM_COLORS + 1
    assert mydiagrams.LAST_NUMBER == config.DIAGRAM_NUMBER_MAX and mydiagrams.BUILTIN_STYLES == config.DIAGRAM_STYLES


def test_styles_dir_is_in_config_folder():
    from lectern.paths import config_dir
    assert mydiagrams.styles_dir() == config_dir() / 'diagram-styles'
