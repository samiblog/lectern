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


@pytest.mark.parametrize('lang', ['ko', 'en'])
def test_builtin_templates_have_the_same_numbers_in_both_languages(lang):
    files = sorted((ROOT / 'web' / 'templates' / lang).glob('*.md'))
    assert [f.name[:2] for f in files] == [f'{i:02d}' for i in range(1, 13)]
    for f in files:
        text = f.read_text(encoding='utf-8')
        assert text.endswith('\n') and text.strip() and '\n---\n' not in text, f.name


def test_list_gives_builtin_first_then_own(config, monkeypatch):
    monkeypatch.setattr(i18n, 'language', lambda: 'ko')
    (config / 'templates').mkdir()
    (config / 'templates' / '01-내-틀.md').write_text('## 내 틀\n', encoding='utf-8')
    items = slidetemplates.list_templates()
    assert [x['number'] for x in items] == list(range(1, 14))
    assert items[0]['name'] == '표지' and not items[0]['own']
    assert items[12]['name'] == '내 틀' and items[12]['own'] and items[12]['text'] == '## 내 틀\n'


def test_list_skips_what_it_cannot_read(config):
    folder = config / 'templates'
    folder.mkdir()
    (folder / '깨진.md').write_bytes(b'\xff\xfe\x00')
    (folder / '큰.md').write_text('x' * (slidetemplates.MAX_BYTES + 1), encoding='utf-8')
    (folder / '글.txt').write_text('아님', encoding='utf-8')
    assert not [x for x in slidetemplates.list_templates() if x['own']]


def test_save_makes_one_new_numbered_file(config):
    first = slidetemplates.save_template('결론 먼저', '## 제목\n\n글\n')
    second = slidetemplates.save_template('두번째', '## 제목\n')
    files = sorted(p.name for p in (config / 'templates').iterdir())
    assert files == ['01-결론 먼저.md', '02-두번째.md']
    assert first['own'] and second['number'] == first['number'] + 1
    assert (config / 'templates' / '01-결론 먼저.md').read_bytes() == '## 제목\n\n글\n'.encode('utf-8')


def test_save_never_overwrites(config):
    slidetemplates.save_template('같은 이름', '## 첫째\n')
    with pytest.raises(editing.EditError) as e:
        slidetemplates.save_template('같은 이름', '## 둘째\n')
    assert e.value.status == 409
    assert (config / 'templates' / '01-같은 이름.md').read_text(encoding='utf-8') == '## 첫째\n'


@pytest.mark.parametrize('name', ['', '   ', '../밖', 'a/b', 'a\\b', 'a:b', '.숨김', '끝점.', 'CON', 'x' * 61, None, 3])
def test_save_refuses_bad_names(config, name):
    with pytest.raises(editing.EditError):
        slidetemplates.save_template(name, '## 글\n')
    assert not (config / 'templates').exists() or not list((config / 'templates').iterdir())


def test_save_refuses_empty_or_huge_text(config):
    for text in ('', '\n\n', 'x' * (slidetemplates.MAX_BYTES + 1), None):
        with pytest.raises(editing.EditError):
            slidetemplates.save_template('이름', text)


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
    assert pptxexport.doc_memory(md) == {'style': '회사 보고', 'original': False}
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


def test_missing_named_style_is_reported_and_falls_through(tmp_path, config):
    md = tmp_path / 'a.md'
    md.write_text('---\nmarp: true\npptxStyle: 없는것\n---\n\n## 글\n', encoding='utf-8')
    r = build(md, config, '--out', tmp_path / '1.pptx')
    assert r['base'] is None and any('없는것' in n for n in r['notes'])


def test_config_keeps_the_default_style_key():
    from lectern import config as cfg
    assert 'pptx_style' in cfg.CLIENT_KEYS and cfg.DEFAULTS['pptx_style'] == ''
