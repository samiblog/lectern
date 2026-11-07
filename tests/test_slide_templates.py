"""Lectern 슬라이드 템플릿 (D101)·pptx 로 전환 (D102): 서버 쪽"""
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from lectern import editing, i18n, pptxexport, slidetemplates

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'skills' / 'lectern-to-pptx' / 'scripts' / 'build_pptx.py'
DECK = '---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 둘째\n\n글\n'


@pytest.fixture()
def config(tmp_path, monkeypatch):
    folder = tmp_path / 'config'
    folder.mkdir()
    monkeypatch.setenv('LECTERN_CONFIG_DIR', str(folder))
    return folder


def make_style(config, name='회사'):
    """보관소에 pptx 스타일 하나를 만든다."""
    md = config.parent / f'{name}-원본.md'
    md.write_text(DECK, encoding='utf-8')
    (config / 'pptx-styles').mkdir(exist_ok=True)
    out = config / 'pptx-styles' / f'{name}.pptx'
    r = subprocess.run([sys.executable, str(BUILD), str(md), '--out', str(out), '--style', 'deck'], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stderr
    return out


@pytest.mark.parametrize('lang, name', [('ko', '기본'), ('en', 'Basic')])
def test_builtin_group_has_twelve_named_templates(lang, name):
    items = slidetemplates.parse_group((ROOT / 'web' / 'templates' / lang / f'{name}.md').read_text(encoding='utf-8'))
    assert [x['number'] for x in items] == list(range(1, 13))
    for x in items:
        assert x['name'] and x['text'].endswith('\n') and '<!-- template:' not in x['text'], x['name']


def test_split_keeps_rules_inside_code():
    text = '---\nmarp: true\n---\n\n## 첫째\n\n```\n---\n```\n\n---\n\n## 둘째\n'
    assert slidetemplates.split_slides(text) == ['## 첫째\n\n```\n---\n```', '## 둘째']


def test_template_names_come_from_the_comment_then_the_title():
    items = slidetemplates.parse_group('<!-- template: 내 이름 -->\n\n## 제목\n\n---\n\n## 다른 제목\n\n---\n\n글만\n')
    assert [x['name'] for x in items][:2] == ['내 이름', '다른 제목'] and items[2]['name']
    assert items[0]['text'] == '## 제목\n'


def test_groups_list_builtin_first_then_own(config, monkeypatch):
    monkeypatch.setattr(i18n, 'language', lambda: 'ko')
    (config / 'templates').mkdir()
    (config / 'templates' / '회사 보고.md').write_text('---\nmarp: true\n---\n\n## 내 틀\n\n---\n\n## 둘째\n', encoding='utf-8')
    groups = slidetemplates.list_groups()
    assert [g['name'] for g in groups] == ['기본', '회사 보고'] and [g['own'] for g in groups] == [False, True]
    assert groups[0]['templates'][0]['name'] == '표지'
    assert [x['number'] for x in groups[1]['templates']] == [1, 2], '번호는 묶음 안에서 매긴다'


def test_list_skips_what_it_cannot_read(config):
    folder = config / 'templates'
    folder.mkdir()
    (folder / '깨진.md').write_bytes(b'\xff\xfe\x00')
    (folder / '큰.md').write_text('x' * (slidetemplates.MAX_GROUP + 1), encoding='utf-8')
    (folder / '글.txt').write_text('아님', encoding='utf-8')
    assert not [g for g in slidetemplates.list_groups() if g['own']]


def test_save_adds_a_slide_to_my_group(config, monkeypatch):
    monkeypatch.setattr(i18n, 'language', lambda: 'ko')
    first = slidetemplates.save_template('결론 먼저', '## 제목\n\n글\n')
    second = slidetemplates.save_template('두번째', '## 제목\n')
    assert [p.name for p in (config / 'templates').iterdir()] == ['내 템플릿.md']
    assert (first['number'], second['number']) == (1, 2) and first['group'] == '내 템플릿'
    text = (config / 'templates' / '내 템플릿.md').read_text(encoding='utf-8')
    assert text.startswith('---\nmarp: true\n') and text.count('<!-- template:') == 2
    items = slidetemplates.parse_group(text)
    assert [x['name'] for x in items] == ['결론 먼저', '두번째'] and items[0]['text'] == '## 제목\n\n글\n'


def test_save_never_changes_what_is_there(config, monkeypatch):
    monkeypatch.setattr(i18n, 'language', lambda: 'ko')
    slidetemplates.save_template('같은 이름', '## 첫째\n')
    path = config / 'templates' / '내 템플릿.md'
    before = path.read_bytes()
    with pytest.raises(editing.EditError) as e:
        slidetemplates.save_template('같은 이름', '## 둘째\n')
    assert e.value.status == 409 and path.read_bytes() == before
    slidetemplates.save_template('다른 이름', '## 셋째\n')
    assert path.read_bytes().startswith(before), '있던 글은 그대로이고 뒤에 더한다'


@pytest.mark.parametrize('name', ['', '   ', '../밖', 'a/b', 'a\\b', 'a:b', 'a --> b', 'CON', 'x' * 61, None, 3])
def test_save_refuses_bad_names(config, name):
    with pytest.raises(editing.EditError):
        slidetemplates.save_template(name, '## 글\n')
    assert not (config / 'templates').exists() or not list((config / 'templates').iterdir())


def test_save_refuses_empty_or_huge_text(config):
    for text in ('', '\n\n', 'x' * (slidetemplates.MAX_SLIDE + 1), None):
        with pytest.raises(editing.EditError):
            slidetemplates.save_template('이름', text)
    assert not (config / 'templates').exists()


def test_style_list_reads_colors_and_skips_lock_files(config):
    make_style(config)
    (config / 'pptx-styles' / '~$회사.pptx').write_bytes(b'lock')
    (config / 'pptx-styles' / '메모.txt').write_text('x', encoding='utf-8')
    items = pptxexport.list_styles()
    assert [x['name'] for x in items] == ['회사']
    assert all(re.fullmatch(r'#[0-9A-Fa-f]{6}', c) for c in items[0]['colors']) and items[0]['colors']


@pytest.mark.parametrize('name', ['', None, 3, '..', '.', '../회사', 'a/b', 'a\\b', 'c:x', '없는스타일'])
def test_style_path_stays_in_the_library(config, name):
    make_style(config)
    assert pptxexport.style_path(name) is None


def test_doc_memory(tmp_path):
    md = tmp_path / 'a.md'
    md.write_text('---\nmarp: true\npptxStyle: 회사 보고\n---\n\n# 글\n', encoding='utf-8')
    assert pptxexport.doc_memory(md) == {'style': '회사 보고', 'group': '', 'original': False}
    md.write_text('---\nmarp: true\ntemplates: 회사 보고\n---\n\n# 글\n', encoding='utf-8')
    assert pptxexport.doc_memory(md)['group'] == '회사 보고'
    md.write_text('# 글\n\npptxStyle: 본문\n', encoding='utf-8')
    assert pptxexport.doc_memory(md)['style'] == ''
    (tmp_path / '.pptx-work').mkdir()
    (tmp_path / '.pptx-work' / 'source.pptx').write_bytes(b'x')
    (tmp_path / 'a-변환기록.json').write_text(json.dumps({'snapshot': '.pptx-work/source.pptx'}), encoding='utf-8')
    assert pptxexport.doc_memory(md)['original'] is True
    (tmp_path / '.pptx-work' / 'source.pptx').unlink()
    assert pptxexport.doc_memory(md)['original'] is False


def test_free_path_never_takes_an_existing_file(tmp_path):
    md = tmp_path / '보고.md'
    assert pptxexport.free_path(md).name == '보고.pptx'
    (tmp_path / '보고.pptx').write_bytes(b'x')
    (tmp_path / '보고 2.pptx').write_bytes(b'x')
    assert pptxexport.free_path(md).name == '보고 3.pptx'


def test_export_uses_the_chosen_style_and_keeps_existing_files(tmp_path, config):
    make_style(config)
    md = tmp_path / '보고.md'
    md.write_text('---\nmarp: true\n---\n\n## 글\n\n내용\n', encoding='utf-8')
    (tmp_path / '보고.pptx').write_bytes(b'old')
    r = pptxexport.export(md, '회사')
    assert r['path'] == '보고 2.pptx' and r['slides'] == 1 and r['base']
    assert (tmp_path / '보고.pptx').read_bytes() == b'old'
    assert zipfile.is_zipfile(tmp_path / '보고 2.pptx')


def test_export_refuses_a_style_outside_the_library(tmp_path, config):
    md = tmp_path / '보고.md'
    md.write_text(DECK, encoding='utf-8')
    with pytest.raises(pptxexport.ExportError) as e:
        pptxexport.export(md, '../밖')
    assert e.value.status == 404
    assert not (tmp_path / '보고.pptx').exists()


def test_export_reports_why_it_failed(tmp_path, config):
    md = tmp_path / '보통.md'
    md.write_text('# 그냥 문서\n', encoding='utf-8')
    with pytest.raises(pptxexport.ExportError) as e:
        pptxexport.export(md, '')
    assert e.value.status == 500 and e.value.message
    assert not (tmp_path / '보통.pptx').exists()


def build(md, config, *args):
    r = subprocess.run([sys.executable, str(BUILD), str(md), *args], capture_output=True, text=True, encoding='utf-8', env=os.environ | {'LECTERN_CONFIG_DIR': str(config)})
    assert r.returncode == 0, r.stderr
    return json.loads(next(line for line in r.stdout.split('\n') if line.startswith('{"pptx"')))


def test_style_order_named_then_default_then_lectern(tmp_path, config):
    """적용 차례: 문서의 스타일, 기본 스타일, Lectern 스타일 (이번에 말한 양식은 위의 시험)"""
    make_style(config, '문서용')
    make_style(config, '기본용')
    (config / 'config.json').write_text(json.dumps({'pptx_style': '기본용'}), encoding='utf-8')
    md = tmp_path / 'a.md'
    md.write_text('---\nmarp: true\npptxStyle: 문서용\n---\n\n## 글\n', encoding='utf-8')
    assert Path(build(md, config, '--out', tmp_path / '1.pptx')['base']).stem == '문서용'
    md.write_text('---\nmarp: true\n---\n\n## 글\n', encoding='utf-8')
    assert Path(build(md, config, '--out', tmp_path / '2.pptx')['base']).stem == '기본용'
    (config / 'config.json').write_text('{}', encoding='utf-8')
    r = build(md, config, '--out', tmp_path / '3.pptx')
    assert r['base'] is None and r['style']


def test_template_group_pairs_with_the_style_of_the_same_name(tmp_path, config):
    make_style(config, '회사')
    md = tmp_path / 'a.md'
    md.write_text('---\nmarp: true\ntemplates: 회사\n---\n\n## 글\n', encoding='utf-8')
    assert Path(build(md, config, '--out', tmp_path / '1.pptx')['base']).stem == '회사'


def test_style_content_does_not_leak_into_the_new_file(tmp_path, config):
    """양식의 장 제목·표지 그림이 파일 속성으로 새지 않는다."""
    style = make_style(config, '회사')
    with zipfile.ZipFile(style) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    parts['docProps/app.xml'] = '<Properties><TitlesOfParts><vt:lpstr>기밀 장 제목</vt:lpstr></TitlesOfParts></Properties>'.encode('utf-8')
    parts['docProps/core.xml'] = '<cp:coreProperties><dc:title>기밀 제목</dc:title><dc:creator>작성자</dc:creator></cp:coreProperties>'.encode('utf-8')
    parts['docProps/thumbnail.jpeg'] = b'jpeg'
    parts['_rels/.rels'] = parts['_rels/.rels'].replace(b'</Relationships>', b'<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail" Target="docProps/thumbnail.jpeg"/></Relationships>')
    with zipfile.ZipFile(style, 'w') as z:
        for n, b in parts.items():
            z.writestr(n, b)
    md = tmp_path / '보고.md'
    md.write_text('---\nmarp: true\ntitle: 내 보고\npptxStyle: 회사\n---\n\n## 글\n', encoding='utf-8')
    build(md, config, '--out', tmp_path / '1.pptx')
    with zipfile.ZipFile(tmp_path / '1.pptx') as z:
        everything = b''.join(z.read(n) for n in z.namelist() if n.endswith(('.xml', '.rels'))).decode('utf-8')
        assert 'docProps/thumbnail.jpeg' not in z.namelist() and 'metadata/thumbnail' not in everything
    assert '기밀' not in everything and '작성자' not in everything and '내 보고' in everything


def test_register_style_puts_the_pptx_in_the_library(tmp_path, config):
    style = make_style(config, '원본')
    deck = tmp_path / '회사 양식.pptx'
    deck.write_bytes(style.read_bytes())
    script = ROOT / 'skills' / 'pptx-to-lectern' / 'scripts' / 'register_style.py'
    env = os.environ | {'LECTERN_CONFIG_DIR': str(config), 'PYTHONIOENCODING': 'utf-8'}

    def run(*args):
        return subprocess.run([sys.executable, str(script), str(deck), str(tmp_path / 'o'), '--name', '회사 보고', '--no-powerpoint', *args], capture_output=True, text=True, encoding='utf-8', env=env)

    r = run()
    assert r.returncode == 0, r.stdout[-300:] + r.stderr[-300:]
    report = json.loads(r.stdout.strip().split('\n')[-1])
    assert Path(report['style']).read_bytes() == deck.read_bytes()
    assert Path(report['group']) == config / 'templates' / '회사 보고.md', '이름이 같아야 짝이다'
    assert Path(report['guide']).is_file() and report['previews'] == []
    assert [x['name'] for x in pptxexport.list_styles()] == ['원본', '회사 보고']
    again = run()
    assert again.returncode == 1 and '이미 있습니다' in again.stdout, '같은 이름은 묻기 전에 바꾸지 않는다'
    assert run('--force').returncode == 0


def test_preview_stays_in_the_library(config):
    make_style(config)
    (config / 'pptx-styles' / '회사-1.png').write_bytes(b'png')
    assert pptxexport.list_styles()[0]['previews'] == ['회사-1.png']
    assert pptxexport.preview_path('회사-1.png')
    for bad in ('../회사-1.png', '회사.pptx', '회사-3.png', 'a/b-1.png', 'c:x-1.png', '없는-1.png'):
        assert pptxexport.preview_path(bad) is None, bad


def test_missing_named_style_is_reported_and_falls_through(tmp_path, config):
    md = tmp_path / 'a.md'
    md.write_text('---\nmarp: true\npptxStyle: 없는것\n---\n\n## 글\n', encoding='utf-8')
    r = build(md, config, '--out', tmp_path / '1.pptx')
    assert r['base'] is None and any('없는것' in n for n in r['notes'])


def test_config_keeps_the_default_style_key():
    from lectern import config as cfg
    assert 'pptx_style' in cfg.CLIENT_KEYS and cfg.DEFAULTS['pptx_style'] == ''
