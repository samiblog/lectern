"""PDF로 저장 (D131 — pdfexport.py)과 보고서 인쇄 양식(print.css)·글쓰기 스타일(D132)의 파일들.
WebView2 로 PDF 를 만드는 부분은 창이 있어야 해서 여기서는 경로·쓰기만 본다 (창 시험은 docs/TESTING.md 의 수동 점검)."""
import os
import re
import sys
from pathlib import Path

import pytest

from lectern import pdfexport
from lectern.config import value_ok
from lectern.paths import samples_dir, web_dir

ROOT = Path(__file__).resolve().parents[1]


def test_start_place_is_next_to_the_document(tmp_path):
    (tmp_path / 'report').mkdir()
    (tmp_path / 'report' / '의견서.md').write_text('# 의견서\n', encoding='utf-8')
    folder, name = pdfexport.start_place(tmp_path, 'report/의견서.md')
    assert Path(folder) == tmp_path / 'report' and name == '의견서.pdf'


def test_start_place_falls_back_to_documents(tmp_path):
    docs = pdfexport.documents_dir()
    assert pdfexport.start_place(None, 'x.md') == (docs, 'document.pdf')
    assert pdfexport.start_place(tmp_path, '../밖.md') == (docs, 'document.pdf')   # 프로젝트 밖은 resolve_inside 가 막는다
    # 보기만 하는 예제 폴더(D71)의 문서면 내 문서 폴더에서 연다 — 이름은 문서 이름 그대로
    folder, name = pdfexport.start_place(samples_dir().resolve(), 'research/구리-시장-동향.md')
    assert folder == docs and name == '구리-시장-동향.pdf'


def test_target_of_adds_the_extension(tmp_path):
    assert pdfexport.target_of(None) is None
    assert pdfexport.target_of(()) is None
    assert pdfexport.target_of(str(tmp_path / 'a.pdf')) == tmp_path / 'a.pdf'
    assert pdfexport.target_of([str(tmp_path / 'b')]) == tmp_path / 'b.pdf'
    assert pdfexport.target_of(str(tmp_path / 'c.PDF')) == tmp_path / 'c.PDF'
    assert pdfexport.target_of(str(tmp_path / '보고서.2026')) == tmp_path / '보고서.2026.pdf'


def test_refuse(tmp_path):
    assert pdfexport.refuse(tmp_path / 'ok.pdf') is None
    (tmp_path / 'dir.pdf').mkdir()
    assert pdfexport.refuse(tmp_path / 'dir.pdf')
    assert pdfexport.refuse(tmp_path / 'no' / 'x.pdf')
    assert pdfexport.refuse(samples_dir().resolve() / 'research' / 'x.pdf')   # 프로그램 폴더 안(D71)


def test_write_pdf_replaces_and_leaves_no_temp(tmp_path):
    target = tmp_path / '보고서.pdf'
    assert pdfexport.write_pdf(target, b'%PDF-1 one') is None
    assert pdfexport.write_pdf(target, b'%PDF-1 two') is None
    assert target.read_bytes() == b'%PDF-1 two'
    assert [p.name for p in tmp_path.iterdir()] == ['보고서.pdf']


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 의 나눠 쓰기 잠금')
def test_write_pdf_keeps_a_locked_file(tmp_path):
    """PDF 보기 프로그램이 파일을 잠그고 있으면 옛 파일을 그대로 두고 까닭과 할 일을 알린다"""
    import ctypes
    target = tmp_path / 'x.pdf'
    target.write_bytes(b'old')
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = ctypes.c_void_p
    handle = k32.CreateFileW(str(target), 0x80000000, 0, None, 3, 0x80, None)   # 나눠 쓰기 없음
    try:
        why = pdfexport.write_pdf(target, b'new')
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))
    assert why and 'x.pdf' in why
    assert target.read_bytes() == b'old'
    assert [p.name for p in tmp_path.iterdir()] == ['x.pdf']


def test_save_without_a_choice_does_nothing():
    assert pdfexport.save(None, None) == {}
    assert pdfexport.save(None, [str(samples_dir().resolve() / 'x.pdf')])['error']   # 만들기 전에 거절 — 창을 부르지 않는다


def test_ai_tool_setting():
    """쓰는 AI 도구 (D138): 네 값만, 기본은 Claude Code, 화면에서 바꾼다"""
    from lectern.config import CLIENT_KEYS, DEFAULTS
    assert DEFAULTS['ai_tool'] == 'claude' and 'ai_tool' in CLIENT_KEYS
    assert all(value_ok('ai_tool', v) for v in ('claude', 'codex', 'antigravity', 'opencode', 'any'))
    assert not value_ok('ai_tool', 'gemini') and not value_ok('ai_tool', None) and not value_ok('ai_tool', 1)


def test_print_font_setting():
    assert value_ok('print_font', 'serif') and value_ok('print_font', 'sans')
    assert not value_ok('print_font', 'mono') and not value_ok('print_font', None)


def test_print_style_is_loaded_last_for_print_only():
    html = (web_dir() / 'index.html').read_text(encoding='utf-8')
    links = re.findall(r'<link[^>]+href="([^"]+\.css)"[^>]*>', html)
    assert links[-1] == '/static/themes/print.css', links
    assert re.search(r'href="/static/themes/print\.css" media="print"', html)
    css = (web_dir() / 'themes' / 'print.css').read_text(encoding='utf-8')
    assert re.search(r'@page\s*\{\s*size:\s*A4;\s*margin:\s*25mm 22mm 22mm 22mm;', css)
    assert '@page :first' in css and 'counter(page)' in css
    assert 'color-scheme: light' in css   # 어두운 스타일의 쪽 여백 (D131)
    assert '.md-body:not(.lec-deck)' in css   # 슬라이드에는 닿지 않는다


def test_writing_style_files():
    """글쓰기 스타일 (D132): 출력 스타일의 머리는 name·description 만 — keep-coding-instructions 를 적지 않아 개발자 지시가 빠진다"""
    for name, title in (('research-writing.md', '리서치 글쓰기'), ('research-writing.en.md', 'Research writing')):
        text = (web_dir() / 'help' / name).read_text(encoding='utf-8')
        head = text.split('---', 2)[1]
        assert f'name: {title}' in head and 'description:' in head
        assert 'keep-coding-instructions' not in head
        assert len(text) < 6000   # 세션마다 함께 가는 글이라 짧게


def test_writing_guide_summary_is_short_and_quality_first():
    """작성 안내의 '지시 파일에 넣을 요약' (D132 — 이름은 D138: CLAUDE.md·AGENTS.md): 첫 줄이 글의 질, 열 줄을 넘지 않는다"""
    for name, head in (('writing.md', '## 지시 파일에 넣을 요약'), ('writing.en.md', '## Summary for the instruction file')):
        text = (web_dir() / 'help' / name).read_text(encoding='utf-8')
        block = text.split(head, 1)[1].split('```markdown', 1)[1].split('```', 1)[0]
        bullets = [s for s in block.splitlines() if s.startswith('- ')]
        assert 5 <= len(bullets) <= 10, len(bullets)
        assert ('글' in bullets[0] and '형식' in bullets[0]) or ('Writing' in bullets[0])


def test_build_ships_the_writing_style():
    """설치 파일: web/ 통째로 들어가므로 따로 적을 것은 없다 — web 이 spec 의 datas 에 있는지만"""
    spec = (ROOT / 'lectern.spec').read_text(encoding='utf-8')
    assert re.search(r"\('web',\s*'web'\)", spec), 'web 폴더가 설치 파일에 들어가야 한다'
    assert os.path.isfile(web_dir() / 'help' / 'research-writing.md')


def test_preview_store_keeps_the_last_few():
    """미리보기 PDF (D134): 메모리에만, 추측할 수 없는 토큰으로, 최근 몇 개만"""
    first = pdfexport.keep_preview(b'%PDF-1.7 1 0 obj << /Type /Page >> 2 0 obj << /Type /Pages >>')
    assert pdfexport.preview_bytes(first).startswith(b'%PDF') and len(first) >= 30
    assert pdfexport.page_count(pdfexport.preview_bytes(first)) == 1
    others = [pdfexport.keep_preview(b'%PDF-x') for _ in range(pdfexport.MAX_PREVIEWS)]
    assert pdfexport.preview_bytes(first) is None and pdfexport.preview_bytes(others[-1]) == b'%PDF-x'
    assert pdfexport.preview_bytes('') is None and pdfexport.preview_bytes(None) is None


def test_preview_route_needs_only_the_token():
    """/pdf-preview/<토큰>.pdf — iframe 은 X-Token 머리를 보낼 수 없어 /api 밖이다. 토큰이 비밀, 모르는 토큰은 404"""
    from lectern.config import Config
    from lectern.server import create_app
    from lectern.state import AppState
    st = AppState(Config(), mode='window')
    st.token = 'secret'   # 창 모드 — /api 는 X-Token 이 있어야 한다
    c = create_app(st).test_client()
    token = pdfexport.keep_preview(b'%PDF-1.7 preview')
    r = c.get(f'/pdf-preview/{token}.pdf')
    assert r.status_code == 200 and r.data == b'%PDF-1.7 preview' and r.content_type == 'application/pdf'
    assert r.headers['Cache-Control'] == 'no-store' and r.headers['X-Content-Type-Options'] == 'nosniff'
    assert c.get('/pdf-preview/nope.pdf').status_code == 404
    assert c.get('/api/state').status_code == 403   # /api 는 여전히 토큰을
    st.close()


def test_print_options_settings():
    assert value_ok('print_margin', 'narrow') and not value_ok('print_margin', '10mm')
    assert value_ok('print_header', False) and not value_ok('print_header', 'no')
    assert value_ok('print_page_numbers', True)
