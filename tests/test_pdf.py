"""PDF 보기 (D201): PDF 는 '문서' 트리에 — 보기만. 서버는 받아 주기만 하고 글은 읽지 않는다 (검색·형광펜·제목), 고치거나 지우지 않는다"""
from __future__ import annotations

import pytest

from lectern import editing
from lectern.config import Config
from lectern.docinfo import doc_info
from lectern.editing import EditError
from lectern.scanner import doc_kind, iter_files, scan, scan_others
from lectern.server import create_app
from lectern.state import AppState

PDF = b'%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n'


@pytest.fixture
def proj(tmp_path):
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / '보고서.pdf').write_bytes(PDF)
    (tmp_path / 'docs' / 'a.md').write_text('# 문서\n\n구리 가격\n', encoding='utf-8')
    (tmp_path / 'b.PDF').write_bytes(PDF)
    return tmp_path


@pytest.fixture
def client(proj):
    st = AppState(Config(), mode='browser')
    st.open(proj)
    c = create_app(st).test_client()
    yield c, c.get('/api/state').get_json()['projects'][0]['id']
    st.close()


def test_pdf_is_a_document(proj):
    assert doc_kind('x.pdf') == doc_kind('X.PDF') == 'pdf'
    files = {f['path']: f['kind'] for f in iter_files(scan(proj))}
    assert files == {'docs/보고서.pdf': 'pdf', 'docs/a.md': 'markdown', 'b.PDF': 'pdf'}
    others = [f['path'] for f in iter_files(scan_others(proj)[0])]
    assert not [p for p in others if p.lower().endswith('.pdf')]   # '자료' 목록에는 없다


def test_pdf_text_is_not_read(proj):
    assert doc_info(proj / 'docs' / '보고서.pdf') == {'title': None, 'summary': ''}   # 트리에는 파일 이름


def test_pdf_is_view_only(proj):
    assert not editing.can_edit('보고서.pdf') and editing.can_edit('a.md') and editing.can_edit('a.html')
    with pytest.raises(EditError) as err:
        editing.delete_doc(proj, 'docs/보고서.pdf', frozenset(), frozenset())
    assert err.value.status == 400 and (proj / 'docs' / '보고서.pdf').exists()


def test_pdf_served_to_the_viewer(client):
    c, pid = client
    r = c.get(f'/doc/{pid}/docs/보고서.pdf')
    assert r.status_code == 200 and r.data == PDF and r.mimetype == 'application/pdf'
    assert r.headers['Content-Security-Policy'] == 'sandbox' and r.headers['X-Content-Type-Options'] == 'nosniff'
    part = c.get(f'/doc/{pid}/docs/보고서.pdf', headers={'Range': 'bytes=0-7'})   # pdf.js 는 큰 파일을 나눠 받는다
    assert part.status_code == 206 and part.data == PDF[:8]
    assert c.get(f'/doc/{pid}/../x.pdf').status_code == 404
    assert c.post('/api/source', json={'p': pid, 'path': 'docs/보고서.pdf'}).status_code in (400, 403, 404, 405)


def test_search_and_marks_skip_pdf(client, proj):
    c, pid = client
    (proj / 'docs' / '구리.pdf').write_bytes(PDF.replace(b'Catalog', b'Catalog /T (\xb1\xb8\xb8\xae)'))
    got = c.get(f'/api/search?p={pid}&q=구리').get_json()
    paths = [r['path'] for r in got.get('results', [])]
    assert 'docs/a.md' in paths and not [p for p in paths if p.endswith('.pdf')]
    assert c.get(f'/api/marks?p={pid}').status_code == 200


def test_vendor_ships_pdfjs():
    from lectern.paths import web_dir
    v = web_dir() / 'vendor' / 'pdfjs'
    assert (v / 'pdf.min.mjs').is_file() and (v / 'pdf.worker.min.mjs').is_file()
    assert (v / 'cmaps' / 'UniKS-UCS2-H.bcmap').is_file() and (v / 'cmaps' / 'KSCms-UHC-H.bcmap').is_file()
    assert sorted(x.name for x in (v / 'wasm').iterdir()) == ['jbig2.wasm', 'openjpeg.wasm', 'qcms_bg.wasm']
    assert not list((v / 'standard_fonts').glob('Liberation*'))   # GPL 글꼴은 넣지 않는다 (D201)
    lic = web_dir() / 'vendor' / 'licenses'
    assert (lic / 'pdfjs-dist.txt').is_file() and len(list(lic.glob('pdfjs-dist.*.txt'))) == 7
