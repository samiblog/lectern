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
    """작성 안내의 'CLAUDE.md 에 넣을 요약' (D132): 첫 줄이 글의 질, 열 줄을 넘지 않는다"""
    for name, head in (('writing.md', '## CLAUDE.md 에 넣을 요약'), ('writing.en.md', '## Summary for CLAUDE.md')):
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
