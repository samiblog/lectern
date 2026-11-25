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
        # 세션마다 함께 가는 글이라 짧게 — D148 에서 글 종류·개발자 글버릇·남의 글을 다듬을 때를 더해 6,000자 → 10,000자
        assert len(text) < 10000


def test_writing_style_kinds_habits_and_review():
    """글쓰기 스타일 2판 (D148): 글 종류마다 기준(개조식을 나쁜 글로 보지 않는다), 개발자 글버릇, 남의 글을 다듬을 때(표를 먼저, 인용·숫자 값은 그대로),
    한 쪽의 글자 수, 내 문체 노트의 세 칸. 다듬기 점검·내 문체 안내는 두 언어 모두 있고 같은 절을 가진다"""
    ko = (web_dir() / 'help' / 'research-writing.md').read_text(encoding='utf-8')
    for part in ('## 글 종류마다 기준이 다르다', '**개조식 보고서**', '## 개발자 글버릇을 쓰지 않는다', '## AI 글버릇을 쓰지 않는다',
                 '## 남의 글을 옮기거나 다듬을 때', '1,000자', '## 내 문체', '지킬 것', '따라 하지 않을 것'):
        assert part in ko, part
    en = (web_dir() / 'help' / 'research-writing.en.md').read_text(encoding='utf-8')
    for part in ('## Each kind of document has its own standard', '**Bullet-point report or brief**', '## Do not write like a developer',
                 '## Do not write like an AI', "## When you carry over or edit someone else's writing", '500 words', '## My style', 'Do not copy'):
        assert part in en, part
    heads = lambda s: [line for line in s.splitlines() if line.startswith('## ')]
    assert len(heads(ko)) == len(heads(en))
    for name in ('review', 'voice'):
        k = (web_dir() / 'help' / f'{name}.md').read_text(encoding='utf-8')
        e = (web_dir() / 'help' / f'{name}.en.md').read_text(encoding='utf-8')
        assert k.startswith('# ') and e.startswith('# ')
        assert len(heads(k)) == len(heads(e)) >= 4, name
    review = (web_dir() / 'help' / 'review.md').read_text(encoding='utf-8')
    for part in ('**틀림**', '**읽기 어려움**', '**취향**', '**확인 필요**', '이 단계에서는 파일을 고치지 않는다', '**인용**', '**숫자 값**'):
        assert part in review, part
    voice = (web_dir() / 'help' / 'voice.md').read_text(encoding='utf-8')
    for part in ('**지킬 것**', '**참고할 것**', '**따라 하지 않을 것**', '이 단계에서는 파일을 쓰지 않는다', '새로 짓는다'):
        assert part in voice, part


def test_writing_guide_summary_is_short_and_quality_first():
    """작성 안내 끝의 요약 (D132 — 이름은 D159: 개인 규칙이나 지시 파일에 넣는 것): 첫 줄이 글의 질, 열 줄을 넘지 않는다"""
    for name, head in (('writing.md', '## 요약 — 개인 규칙이나 지시 파일에 넣는 것'), ('writing.en.md', '## Summary — what goes into the personal rules or the instruction file')):
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
    assert value_ok('print_margin', 'custom') and value_ok('print_margin_mm', [10, 0, 80, 12.5])
    bad = [[10, 10, 10], [10, 10, 10, 81], [-1, 5, 5, 5], [1, 2, 3, '4'], [1, 2, 3, True], [1, 2, 3, None], '10', [float('inf')] * 4]
    assert not [v for v in bad if value_ok('print_margin_mm', v)]
    assert value_ok('print_header', False) and not value_ok('print_header', 'no')
    assert value_ok('print_page_numbers', True)


# ---- 내보내기 창의 'html 로 저장' (D144) ------------------------------------------------------------

HTML = '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="generator" content="Lectern">\n<title>t</title>\n</head>\n<body></body>\n</html>\n'


def test_keep_html_takes_only_what_the_screen_built():
    token = pdfexport.keep_html(HTML)
    assert pdfexport.preview_bytes(token, 'html') == HTML.encode('utf-8')
    assert pdfexport.preview_bytes(token) is None   # 형식이 다른 토큰으로는 꺼내지 못한다 (PDF 미리보기와 섞이지 않게)
    for bad in ('<html><script>x</script>', '<!doctype html><title>남의 글</title>', None, 3):
        with pytest.raises(ValueError):
            pdfexport.keep_html(bad)


def test_previews_are_counted_per_kind():
    pdf = pdfexport.keep_preview(b'%PDF-1.7 keep')
    for _ in range(pdfexport.MAX_PREVIEWS + 1):
        pdfexport.keep_html(HTML)
    assert pdfexport.preview_bytes(pdf) == b'%PDF-1.7 keep'   # html 을 많이 만들어도 PDF 미리보기는 남는다


def test_html_save_places_and_targets(tmp_path):
    (tmp_path / 'report').mkdir()
    (tmp_path / 'report' / '의견서.md').write_text('# 의견서\n', encoding='utf-8')
    folder, name = pdfexport.start_place(tmp_path, 'report/의견서.md', '.html')
    assert Path(folder) == tmp_path / 'report' and name == '의견서.html'
    assert pdfexport.target_of(str(tmp_path / 'a'), '.html').name == 'a.html'
    assert pdfexport.target_of(str(tmp_path / 'a.htm'), '.html').name == 'a.htm'
    assert pdfexport.target_of(str(tmp_path / 'a.pdf'), '.html').name == 'a.pdf.html'


def test_save_html_writes_the_previewed_bytes(tmp_path):
    token = pdfexport.keep_html(HTML)
    r = pdfexport.save_html(str(tmp_path / '보고서'), token)
    assert r == {'path': str(tmp_path / '보고서.html')} and (tmp_path / '보고서.html').read_bytes() == HTML.encode('utf-8')
    assert not [p for p in tmp_path.iterdir() if p.name.startswith('.lectern-')]   # 임시 파일이 남지 않는다
    assert pdfexport.save_html(None, token) == {}   # 대화상자 취소
    assert 'error' in pdfexport.save_html(str(tmp_path / '다른'), 'nope')
    assert 'error' in pdfexport.save_html(str(samples_dir().resolve() / '안.html'), token)   # 프로그램 폴더 안 (D71)


def test_export_routes():
    """/api/export/keep 은 토큰이 있어야 하고, /export-preview/<토큰>.html 은 토큰만으로 — sandbox CSP 로 스크립트를 막는다"""
    from lectern.config import Config
    from lectern.server import create_app
    from lectern.state import AppState
    st = AppState(Config(), mode='window')
    st.token = 'secret'
    c = create_app(st).test_client()
    assert c.post('/api/export/keep', json={'text': HTML}).status_code == 403
    r = c.post('/api/export/keep', json={'text': HTML}, headers={'X-Token': 'secret'})
    assert r.status_code == 200 and r.json['size'] == len(HTML.encode('utf-8'))
    assert c.post('/api/export/keep', json={'text': '<p>x</p>'}, headers={'X-Token': 'secret'}).status_code == 400
    page = c.get(f"/export-preview/{r.json['token']}.html")
    assert page.status_code == 200 and page.data == HTML.encode('utf-8') and page.content_type.startswith('text/html')
    csp = page.headers['Content-Security-Policy']
    assert csp.startswith('sandbox;') and "default-src 'none'" in csp and 'script' not in csp
    assert c.get('/export-preview/nope.html').status_code == 404
    st.close()
