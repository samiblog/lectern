"""내보내기 창의 Word (D146 — docxexport.py): 양식 보관소, 스킬로 만들어 메모리에 두기, 저장 대화상자에서 고른 곳에 쓰기."""
import io
import sys
import zipfile
from pathlib import Path

import pytest

from lectern import docxexport, pdfexport
from lectern.paths import samples_dir

DOC = '# 보고서\n\n본문 한 줄. <mark>칠한 글</mark>.\n\n표 1. 값\n\n| 가 | 나 |\n|---|---|\n| 1 | 2 |\n'


@pytest.fixture()
def config(tmp_path, monkeypatch):
    folder = tmp_path / 'config'
    monkeypatch.setenv('LECTERN_CONFIG_DIR', str(folder))
    return folder


def test_styles_folder_lists_word_templates_only(config):
    assert docxexport.list_styles() == []   # 폴더가 없어도 빈 목록 (만들지 않는다)
    assert not (config / 'docx-styles').exists()
    folder = config / 'docx-styles'
    folder.mkdir(parents=True)
    for name in ('회사.dotx', '기관 보고.docx', '~$회사.dotx', '.숨김.dotx', '메모.txt'):
        (folder / name).write_bytes(b'x')
    (folder / '폴더.dotx').mkdir()
    assert docxexport.list_styles() == [{'name': '기관 보고', 'file': '기관 보고.docx'}, {'name': '회사', 'file': '회사.dotx'}]
    assert docxexport.style_path('회사') == folder / '회사.dotx'
    assert docxexport.style_path('기관 보고.docx') == folder / '기관 보고.docx'
    for bad in ('../회사', '..\\회사.dotx', 'C:/x.dotx', '~$회사', '메모', '', None, 3):
        assert docxexport.style_path(bad) is None


def test_build_runs_the_skill(tmp_path, config):
    md = tmp_path / '보고서.md'
    md.write_text(DOC, encoding='utf-8')
    data, report = docxexport.build(md, '')
    assert data[:2] == b'PK' and report == {'figures': 0, 'notes': []}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        doc = z.read('word/document.xml').decode('utf-8')
    assert '칠한 글' in doc and 'SEQ 표' in doc
    assert [p.name for p in tmp_path.iterdir()] == ['보고서.md']   # 문서 옆에 아무것도 쓰지 않는다
    with pytest.raises(docxexport.ExportError) as e:
        docxexport.build(md, '없는 양식')
    assert e.value.status == 404


def test_build_reports_why_it_failed(tmp_path, config, monkeypatch):
    md = tmp_path / 'a.md'
    md.write_text('# a\n', encoding='utf-8')
    monkeypatch.setattr(docxexport, '_command', lambda: [sys.executable, '-c', 'import sys; sys.exit("망가진 문서")'])
    with pytest.raises(docxexport.ExportError) as e:
        docxexport.build(md, '')
    assert e.value.status == 500 and '망가진 문서' in e.value.message


def test_save_kept_writes_the_built_bytes(tmp_path):
    token = pdfexport.keep_preview(b'PK docx bytes', 'docx')
    r = pdfexport.save_kept(str(tmp_path / '보고서'), token, 'docx')
    assert r == {'path': str(tmp_path / '보고서.docx')} and (tmp_path / '보고서.docx').read_bytes() == b'PK docx bytes'
    assert pdfexport.save_kept(None, token, 'docx') == {}
    assert 'error' in pdfexport.save_kept(str(tmp_path / '다른'), 'nope', 'docx')
    assert pdfexport.preview_bytes(token, 'html') is None   # 형식이 다른 토큰으로는 꺼내지 못한다
    assert 'error' in pdfexport.save_kept(str(samples_dir().resolve() / '안.docx'), token, 'docx')   # 프로그램 폴더 안 (D71)
    assert pdfexport.save_kept(str(tmp_path / 'x'), token, 'pdf') == {}   # PDF 는 이 길이 아니다
    folder, name = pdfexport.start_place(None, '', pdfexport.KINDS['docx'])
    assert name == 'document.docx'


def test_server_routes(tmp_path, config):
    from lectern.config import Config
    from lectern.server import create_app
    from lectern.state import AppState

    proj = tmp_path / 'proj'
    proj.mkdir()
    (proj / '보고서.md').write_text(DOC, encoding='utf-8')
    (proj / '그림.png').write_bytes(b'x')
    state = AppState(Config(), mode='browser')
    project = state.open(proj)
    client = create_app(state).test_client()
    r = client.post('/api/export/docx', json={'p': project.id, 'path': '보고서.md', 'style': ''})
    assert r.status_code == 200
    got = r.get_json()
    assert got['size'] > 1000 and got['figures'] == 0 and got['notes'] == []
    f = client.get(f"/export-file/{got['token']}.docx")
    assert f.status_code == 200 and f.data[:2] == b'PK' and 'attachment' in f.headers['Content-Disposition']
    assert f.headers['X-Content-Type-Options'] == 'nosniff' and f.headers['Cache-Control'] == 'no-store'
    assert client.get('/export-file/nope.docx').status_code == 404
    assert not list(proj.glob('*.docx'))   # 디스크에는 저장 대화상자에서 고른 곳에만
    assert client.post('/api/export/docx', json={'p': project.id, 'path': '../밖.md'}).status_code == 404
    assert client.post('/api/export/docx', json={'p': project.id, 'path': '그림.png'}).status_code == 404
    r = client.post('/api/export/docx', json={'p': project.id, 'path': '보고서.md', 'style': '없는 양식'})
    assert r.status_code == 404 and r.get_json()['error']
    got = client.get('/api/docx-styles').get_json()
    assert got['styles'] == [] and got['dir'] == str(Path(config) / 'docx-styles')
    assert len(got['builtin']) == 18 and {'id', 'name', 'group', 'fields', 'slots'} <= set(got['builtin'][0])   # Lectern 양식 (D147)
    r = client.post('/api/export/docx', json={'p': project.id, 'path': '보고서.md', 'style': 'lectern:research-report'})
    assert r.status_code == 200, r.get_json()
    doc = zipfile.ZipFile(io.BytesIO(client.get(f"/export-file/{r.get_json()['token']}.docx").data)).read('word/document.xml').decode('utf-8')
    assert '{{' not in doc and '보고서' in doc
    assert client.post('/api/export/docx', json={'p': project.id, 'path': '보고서.md', 'style': 'lectern:없는것'}).status_code == 404
    state.close()
