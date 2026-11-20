"""지면 틀 (D145) — 브라우저 개발 모드에서: 내보내기 창의 틀 목록(묶음·내 틀), 맨 앞 설정 layout 이 처음 값, 고른 틀로 지은 html
(틀의 class·채운 자리·data-if·data-each·이름 있는 박스글이 자리로·차례·{{css:}} 의 CSS 글자·스크립트 없음), 비어 있는 맨 앞 설정 알림과 견본
복사, 내 틀(설정 폴더 layouts)의 스크립트·인터넷 길은 지워짐, 기본 양식으로 돌아가기, 슬라이드에는 틀이 없음, 같은 Chromium 의
page.pdf 로 찍은 쪽 크기(책 152×225mm, 투고 원고 Letter)·표지 쪽.

창 모드의 PDF(숨은 창이 찍는 것 — native.layout_pdf)는 여기서 돌지 않는다 — 세션 밖의 실제 창 시험."""
import html
import re
import tempfile
import traceback
from pathlib import Path

import pymupdf
from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-layouts-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir(parents=True)
(config / 'layouts').mkdir(parents=True)
(config / 'layouts' / '우리 회사.html').write_text("""<!--lectern-layout
name: 우리 회사 보고
name_en: Our report
group: 업무·공공
pages: A4
fields: title, dept
description: 시험용 내 틀
-->
<style>.lay-우리-회사 h1 { color: rgb(1, 2, 3); } .lay-우리-회사 .x { background: url(https://evil.example/x.png); }</style>
<script>window.bad = 1</script>
<h1 onclick="alert(1)">{{title}}</h1><p class="x">{{dept}}</p><img src="https://evil.example/a.png">
<main class="md-body">{{body}}</main>
""", encoding='utf-8')
DOC = """---
title: 분기 점검
subtitle: 부제의 글
author: 김연구
dept: 시장분석팀
결재: [담당, 팀장, 본부장]
layout: one-page
date: 2026-11-15
---

# 분기 점검

<!-- box: 결론 -->
**결론**

분할 매수로 단가를 낮춘다.
<!-- /box -->

<!-- box: 요약 -->
요약 상자의 글이다.
<!-- /box -->

## 1. 첫 절

표 1. 값

| 항목 | 값 |
|---|---|
| 가 | 10 |

### 1.1 작은 절

본문의 글이다.

## 2. 둘째 절

끝 문단.
"""
(proj / '점검.md').write_text(DOC, encoding='utf-8')
(proj / '기본.md').write_text('# 틀 없는 문서\n\n본문.\n', encoding='utf-8')
(proj / '발표.md').write_text('---\nmarp: true\n---\n\n# 발표\n', encoding='utf-8')
server, url, port = serve(proj, config)

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_export(path):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            page.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.docPath === p", arg=path)
            page.wait_for_timeout(400)
            page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.openPrint('html'))")
            page.wait_for_selector('#lec-print:not([hidden])')
            until(page, lambda: page.locator('#lec-pp-layout option').count() > 1, 10000)

        def built():
            until(page, lambda: page.is_enabled('#lec-print-html'), 20000)
            src = page.get_attribute('#lec-print-frame', 'src')
            return page.evaluate('(u) => fetch(u).then((r) => r.text())', src)

        def choose(lid):
            first = page.get_attribute('#lec-print-frame', 'src')
            page.select_option('#lec-pp-layout', lid)
            until(page, lambda: page.get_attribute('#lec-print-frame', 'src') != first and page.is_enabled('#lec-print-html'), 20000)
            return built()

        print('[틀 목록]')
        open_export('점검.md')
        groups = page.evaluate("[...document.querySelectorAll('#lec-pp-layout optgroup')].map((g) => g.label)")
        check('묶음: 업무·공공 · 연구 · 금융·컨설팅 · 매체·출판 · 안내 · 내 틀', groups == ['업무·공공', '연구', '금융·컨설팅', '매체·출판', '안내', '내 틀'], groups)
        first = page.evaluate("document.querySelector('#lec-pp-layout option').textContent")
        check('맨 위는 기본 양식', first == '보고서 (기본 양식)', first)
        check('맨 앞 설정 layout: one-page 가 처음 값', page.input_value('#lec-pp-layout') == 'one-page', page.input_value('#lec-pp-layout'))

        print('[고른 틀로 지은 html]')
        text = built()
        body = text[text.index('<body>'):]
        check('틀의 class 와 머리', 'class="lec-layout lay-one-page lay-paged"' in body and '<meta name="lectern-layout" content="one-page">' in text)
        check('스크립트 없음', '<script' not in text.lower() and 'onclick' not in text)
        check('맨 앞 설정 값이 자리에 — 제목·날짜(점)·부서', '분기 점검</h1>' in body and '2026. 11. 15.' in body and '시장분석팀' in body)
        check('data-each: 결재 칸이 셋', len(re.findall(r'<td>(담당|팀장|본부장)</td>', body)) == 3, re.findall(r'<td>[^<]*</td>', body)[:6])
        check('이름 있는 박스글이 자리로 — 굵은 제목 줄은 빠지고 글만', '분할 매수로 단가를 낮춘다.' in body and body.index('분할 매수로') < body.index('<main') and '<strong>결론</strong>' not in body)
        check('틀이 모르는 박스글(요약)은 본문에 그대로', body.index('요약 상자의 글이다.') > body.index('<main'))
        check('틀이 제목을 쓰면 본문 맨 앞 # 제목은 빠진다', body.count('분기 점검</h1>') == 1)
        check('캡션에 class caption', re.search(r'<p[^>]*class="(?:[^"]* )?caption(?: [^"]*)?"[^>]*>표 1\. 값', body) is not None)
        check('맨 앞 설정 표는 없다', 'front-matter' not in body)
        info = page.inner_text('#lec-pp-layout-info')
        check('창에 틀의 설명·쪽·박스글 자리', '경영진 보고용 한 장' in info and '쪽: A4' in info and '<!-- box: 결론 -->' in info, info)

        text = choose('research-report')
        body = text[text.index('<body>'):]
        check('차례 — ## 와 ###', re.search(r'<nav class="lay-toc"><ol><li class="lv2"><a href="#[^"]+">1\. 첫 절</a></li><li class="lv3">', body) is not None, re.findall(r'<nav class="lay-toc">.{0,200}', body)[:1])
        check('요약 자리는 박스글(요약)', '요약 상자의 글이다.' in body and body.index('요약 상자의 글이다.') < body.index('<main'))
        check('비어 있는 data-if 는 빠진다 (보고서 번호 없음)', 'class="no"' not in body)
        check("CSS 안의 {{css:title}} 은 CSS 글자로", '@top-left { content: "분기 점검";' in text and '{{' not in text[:text.index('</style>')])
        info = page.inner_text('#lec-pp-layout-info')
        check('비어 있는 맨 앞 설정을 알린다', '비어 있는 것: org, number' in info, info)
        check('견본 복사 단추가 보인다', page.is_visible('#lec-pp-layout-sample'))
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.click('#lec-pp-layout-sample')
        clip = page.evaluate('navigator.clipboard.readText()').replace('\r\n', '\n')
        check('견본: 비어 있는 키만', clip == '---\norg: \nnumber: \n---', clip)

        print('[내 틀]')
        text = choose('user/우리 회사')
        body = text[text.index('<body>'):]
        check('내 틀의 class 는 파일 이름에서', 'lay-우리-회사' in body and 'rgb(1, 2, 3)' in text)
        check('내 틀의 스크립트·이벤트·인터넷 그림·인터넷 CSS 는 지워진다', '<script' not in text.lower() and 'onclick' not in text and 'evil.example' not in text, re.findall(r'.{30}evil.{30}', text)[:2])
        with page.expect_download() as dl:
            page.click('#lec-print-html')
        check("'html로 저장…' — 틀로 지은 파일 그대로", Path(dl.value.path()).read_text(encoding='utf-8') == text)

        print('[기본 양식과 슬라이드]')
        open_export('기본.md')
        check('맨 앞 설정이 없으면 기본 양식', page.input_value('#lec-pp-layout') == '')
        text = built()
        check('기본 양식은 지금 화면 스타일 그대로 (틀 없음)', 'lec-layout' not in text[text.index('<body>'):] and '<article class="md-body">' in text)
        page.keyboard.press('Escape')
        page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", '발표.md')
        page.wait_for_timeout(800)
        page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.openPrint('html'))")
        page.wait_for_timeout(500)
        check('슬라이드에서는 html 창이 열리지 않는다', page.is_hidden('#lec-print'))

        print('[쪽 — 같은 Chromium 의 PDF]')
        open_export('점검.md')
        pdfpage = ctx.new_page()
        for lid, want, pages_min in (('book', (431, 638), 1), ('manuscript', (612, 792), 2), ('white-paper', (595, 842), 2)):
            text = choose(lid)
            f = base / f'{lid}.html'
            f.write_text(text, encoding='utf-8')
            pdfpage.goto(f.as_uri())
            pdfpage.wait_for_timeout(300)
            out = base / f'{lid}.pdf'
            pdfpage.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
            d = pymupdf.open(out)
            size = (round(d[0].rect.width), round(d[0].rect.height))
            check(f'{lid}: 쪽 크기 {want}, {pages_min}쪽 이상', size == want and d.page_count >= pages_min, (size, d.page_count))
        d = pymupdf.open(base / 'white-paper.pdf')
        check('백서: 1쪽은 표지(본문 없음), 2쪽부터 본문', '분기 점검' in d[0].get_text() and '본문의 글이다' not in d[0].get_text())
        page.keyboard.press('Escape')
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
