"""html 로 전환 (D129): 서버 쪽 — 문서 옆에 새 파일 하나, 덮어쓰지 않기, 받지 않는 글, 이번에 만든 파일만 브라우저로. 스킬이 impress 주석을 노트로 넣지 않는지"""
import importlib
import sys
from pathlib import Path

import pytest

from lectern import htmlexport, osutil, paths

ROOT = Path(__file__).resolve().parent.parent
DECK = '---\nmarp: true\n---\n\n# 표지\n\n---\n\n<!-- impress: x=0 y=900 -->\n## 둘째\n\n<!-- 진짜 노트 -->\n'
HTML = '<!doctype html>\n<html lang="ko">\n<head>\n<meta name="generator" content="Lectern (impress.js 2.0.0)">\n</head>\n<body></body>\n</html>\n'


@pytest.fixture()
def deck(tmp_path):
    md = tmp_path / '보고서.md'
    md.write_text(DECK, encoding='utf-8')
    return md


def test_writes_next_to_the_deck_and_never_overwrites(deck):
    first = htmlexport.write(deck, HTML)
    assert first == deck.with_name('보고서.html') and first.read_text(encoding='utf-8') == HTML
    second = htmlexport.write(deck, HTML.replace('<body>', '<body class="x">'))
    assert second.name == '보고서 2.html' and first.read_text(encoding='utf-8') == HTML
    assert htmlexport.free_path(deck).name == '보고서 3.html'


def test_keeps_line_endings_and_utf8(deck):
    out = htmlexport.write(deck, HTML.replace('<body>', '<body>한글'))
    assert b'\r\n' not in out.read_bytes() and '한글' in out.read_text(encoding='utf-8')


@pytest.mark.parametrize('text', [None, 3, '', '<p>아무 글</p>', '<!doctype html><title>x</title>', HTML.replace('Lectern', 'Other')])
def test_takes_only_what_the_screen_built(deck, text):
    with pytest.raises(htmlexport.ExportError) as e:
        htmlexport.write(deck, text)
    assert e.value.status == 400
    assert not deck.with_name('보고서.html').exists()


@pytest.mark.parametrize('body', ['# 보통 문서\n', '---\nmarp: false\n---\n# x\n', '---\ntitle: marp: true\n---\n'])
def test_only_next_to_lectern_slides(tmp_path, body):
    md = tmp_path / '문서.md'
    md.write_text(body, encoding='utf-8')
    with pytest.raises(htmlexport.ExportError) as e:
        htmlexport.write(md, HTML)
    assert e.value.status == 400 and not (tmp_path / '문서.html').exists()


def test_reads_marp_with_bom_crlf_and_comment(tmp_path):
    md = tmp_path / 'a.md'
    md.write_bytes('﻿---\r\nmarp: true # 슬라이드\r\n---\r\n# x\r\n'.encode('utf-8'))
    assert htmlexport.is_deck(md)
    assert not htmlexport.is_deck(tmp_path / '없음.md')
    txt = tmp_path / 'b.txt'
    txt.write_text('---\nmarp: true\n---\n', encoding='utf-8')
    assert not htmlexport.is_deck(txt)


def test_refuses_the_program_folder(deck, monkeypatch):
    monkeypatch.setattr(paths, 'is_protected', lambda p: True)
    with pytest.raises(htmlexport.ExportError) as e:
        htmlexport.write(deck, HTML)
    assert e.value.status == 403


def test_refuses_huge(deck, monkeypatch):
    monkeypatch.setattr(htmlexport, 'MAX_BYTES', 100)
    with pytest.raises(htmlexport.ExportError) as e:
        htmlexport.write(deck, HTML + 'x' * 200)
    assert e.value.status == 413


def test_opens_only_files_made_now(deck, monkeypatch):
    opened = []
    monkeypatch.setattr(osutil, 'open_default', opened.append)
    out = htmlexport.write(deck, HTML)
    htmlexport.open_made(out)
    assert opened == [out]
    other = deck.with_name('남의 것.html')
    other.write_text(HTML, encoding='utf-8')
    with pytest.raises(htmlexport.ExportError) as e:
        htmlexport.open_made(other)
    assert e.value.status == 403 and opened == [out]
    out.unlink()
    with pytest.raises(htmlexport.ExportError):
        htmlexport.open_made(out)


def test_server_routes(tmp_path, deck, monkeypatch):
    from lectern.config import Config
    from lectern.server import create_app
    from lectern.state import AppState

    monkeypatch.setenv('LECTERN_CONFIG_DIR', str(tmp_path / 'config'))
    state = AppState(Config(), mode='browser')
    project = state.open(deck.parent)
    client = create_app(state).test_client()
    r = client.get(f'/api/html-export?p={project.id}&path=보고서.md')
    assert r.status_code == 200 and r.get_json()['out'] == '보고서.html'
    r = client.post('/api/html-export', json={'p': project.id, 'path': '보고서.md', 'html': HTML})
    assert r.status_code == 200 and r.get_json() == {'path': '보고서.html'}
    r = client.post('/api/html-export', json={'p': project.id, 'path': '../밖.md', 'html': HTML})
    assert r.status_code == 404
    r = client.post('/api/html-export', json={'p': project.id, 'path': '보고서.md', 'html': '<p>x</p>'})
    assert r.status_code == 400 and r.get_json()['error']
    r = client.post('/api/html-export/open', json={'p': project.id, 'path': '보고서.md'})
    assert r.status_code == 403
    state.close()


def test_pptx_skill_reads_impress_as_a_directive_not_a_note(deck):
    sys.path.insert(0, str(ROOT / 'skills' / 'lectern-to-pptx' / 'scripts'))
    try:
        lectern_md = importlib.import_module('lectern_md')
        slides = lectern_md.read_deck(deck)['slides']
    finally:
        sys.path.pop(0)
    assert 'impress' not in slides[1]['notes'] and '진짜 노트' in slides[1]['notes']
    assert slides[1]['eff'].get('impress') and not slides[0]['eff'].get('impress')
