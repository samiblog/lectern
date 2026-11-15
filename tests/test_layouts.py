"""지면 틀 (D145 — lectern/layouts.py, web/layouts): 목록, 내 틀, 거르기, 앱의 틀마다의 약속"""
import re
from pathlib import Path

import pytest

from lectern import layouts
from lectern.paths import web_dir

BUILTIN = sorted(p for p in (web_dir() / 'layouts').glob('*.html'))


def test_builtin_layouts_are_listed_in_group_order():
    got = layouts.list_layouts(Path('없는-폴더'))
    ids = [x['id'] for x in got]
    assert len(ids) == len(BUILTIN) >= 15 and '_base' not in ids
    ranks = [layouts.GROUP_ORDER.index(x['group']) for x in got]
    assert ranks == sorted(ranks), '묶음 차례대로'
    gov = next(x for x in got if x['id'] == 'gov-report')
    assert gov['name'] == '정부 보고서' and gov['pages'] == 'A4' and not gov['flow'] and 'dept' in gov['fields'] and gov['slots'] == ['요약']
    assert next(x for x in got if x['id'] == 'longform')['flow']


@pytest.mark.parametrize('path', BUILTIN, ids=lambda p: p.stem)
def test_every_builtin_layout_keeps_the_rules(path):
    text = path.read_text(encoding='utf-8')
    head = layouts.parse_head(text)
    for key in ('name', 'name_en', 'group', 'group_en', 'pages', 'description', 'description_en'):
        assert head.get(key), f'{path.name}: 머리 주석에 {key}'
    assert head['group'] in layouts.GROUP_ORDER
    comment = layouts.HEAD.match(text).group(0)
    assert comment.count('-->') == 1, f'{path.name}: 머리 주석 안에 --> 가 있으면 주석이 거기서 끝난다'
    css = '\n'.join(layouts.STYLE.findall(text))
    cls = f'.lay-{path.stem}'
    rules = [r for r in re.findall(r'^\s*(\.[^{]+)\{', css, re.M)]
    assert rules and all(r.strip().startswith(cls) for r in rules), f'{path.name}: 규칙은 {cls} 로 (다른 틀과 섞이지 않게)'
    assert not re.search(r'url\(\s*["\']?(?!data:)', css) and '@import' not in css, '인터넷에서 불러오지 않는다'
    assert '<script' not in text.lower() and not re.search(r'\son[a-z]+=', text)
    assert '{{body}}' in text, '본문 자리'
    for slot in head.get('slots', '').split(','):
        if slot.strip():
            assert f'slot:{slot.strip()}' in text, f'{path.name}: 머리의 자리 {slot} 를 뼈대가 쓴다'
    got = layouts.read_layout(path.stem)
    assert got and got['markup'].strip() and got['base'] and '{{body}}' in got['markup']


def test_user_layouts_folder(tmp_path):
    (tmp_path / '분기 보고.html').write_text('<!--lectern-layout\nname: 분기 보고\npages: continuous\nfields: title, dept\n-->\n<style>.lay-분기-보고 h1{color:red}</style><main>{{body}}</main>', encoding='utf-8')
    (tmp_path / '.숨김.html').write_text('<main>{{body}}</main>', encoding='utf-8')
    (tmp_path / 'x.txt').write_text('no', encoding='utf-8')
    (tmp_path / '큼.html').write_text('<main>{{body}}</main>' + ' ' * (layouts.MAX_BYTES + 1), encoding='utf-8')
    mine = [x for x in layouts.list_layouts(tmp_path) if x['user']]
    assert [x['id'] for x in mine] == ['user/분기 보고'] and mine[0]['flow'] and mine[0]['fields'] == ['title', 'dept']
    got = layouts.read_layout('user/분기 보고', tmp_path)
    assert got['css'] == '.lay-분기-보고 h1{color:red}' and got['markup'] == '<main>{{body}}</main>'
    for bad in ('user/../분기 보고', '../x', '_base', 'user/.숨김', 'user/없음', '', None):
        assert layouts.read_layout(bad, tmp_path) is None


def test_sanitize_removes_scripts_and_internet():
    dirty = ('<p onclick="x()">a</p><script>alert(1)</script><iframe src="y"></iframe><img src="https://x/a.png">'
             '<a href="javascript:alert(1)">b</a><div style="background:url(http://e/x)">c</div><link rel="stylesheet" href="https://e/c.css">'
             '<img src="data:image/png;base64,AA">')
    out = layouts.sanitize(dirty)
    assert 'onclick' not in out and '<script' not in out and 'alert(1)' not in out and '<iframe' not in out and '<link' not in out
    assert 'https://x' not in out and 'javascript:' not in out and 'http://e' not in out
    assert 'src="data:image/png;base64,AA"' in out and '>a</p>' in out and '>b</a>' in out
    css = layouts.read_layout('research-report')['css']
    assert '@page' in css and '{{css:title}}' in css   # 쪽 머리의 문서 제목 — 화면(layout.js)이 CSS 글자로 채운다


def test_layout_routes():
    from lectern.config import Config
    from lectern.server import create_app
    from lectern.state import AppState
    st = AppState(Config(), mode='browser')
    c = create_app(st).test_client()
    r = c.get('/api/layouts')
    assert r.status_code == 200 and len(r.json['layouts']) >= 15 and r.json['dir'].endswith('layouts') and r.json['guide'].endswith('.md')
    assert Path(r.json['guide']).is_file() and Path(r.json['builtin']).is_dir()
    r = c.get('/api/layouts/research-report')
    assert r.status_code == 200 and set(r.json) == {'id', 'css', 'markup', 'base'} and '{{toc}}' in r.json['markup']
    assert c.get('/api/layouts/..%2F..%2Fapp').status_code == 404 and c.get('/api/layouts/_base').status_code == 404
    st.close()


def test_guides_exist():
    for name in ('layouts.md', 'layouts.en.md'):
        text = (web_dir() / 'help' / name).read_text(encoding='utf-8')
        assert '{{body}}' in text and 'data-if' in text and '{{css:' in text
