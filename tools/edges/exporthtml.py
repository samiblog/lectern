"""내보내기 창의 'html 로 저장' (D144) — 브라우저 개발 모드에서: 메뉴, 창(형식·PDF 막힘·단추), 지은 파일(스크립트 없음, 앱 표시 없음,
접은 절·박스글 폄, 그림·차트·수식이 파일 안에, 같은 파일 안 링크만 남김, 인쇄하면 보고서 양식), 미리보기와 내려받은 바이트가 같음,
문서가 바뀌면 미리보기도 다시, 슬라이드에는 없음, 인터넷 그림을 끈 설정, 결과 파일을 열 때 바깥 요청이 없음.

창 모드의 저장 대화상자(native.save_export)는 여기서 돌지 않는다 — 쓰는 길은 tests/test_pdfexport.py 가 본다."""
import base64
import html
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-exporthtml-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
(proj / 'docs' / '점.png').write_bytes(PNG)
(proj / 'docs' / '다른.md').write_text('# 다른 문서\n', encoding='utf-8')
DOC = """---
date: 2026-10-01
owner: 시험
---

# 내보낼 보고서

[목차]

## 1. 접을 절

접어 둔 절의 글이다.

## 2. 여러 가지

표 1. 값

| 항목 | 값 |
|---|---|
| 가 | 10 |

[표 1](#표-1) 을 본다. 각주도 있다[^1]. [다른 문서](다른.md) 와 [바깥](https://example.com/x).

<!-- box -->
**박스 1. 접은 상자**

상자 안의 글이다.
<!-- /box -->

- [ ] 할 일 하나

![점](점.png)

![바깥 그림](https://example.com/a.png)

수식 $e = mc^2$ 이다.

```mermaid
flowchart LR
  A --> B
```

```vega-lite
{"data": {"values": [{"a": "x", "b": 1}, {"a": "y", "b": 2}]}, "mark": "bar", "encoding": {"x": {"field": "a", "type": "nominal"}, "y": {"field": "b", "type": "quantitative"}}}
```

```python
print("코드")
```

[^1]: 각주의 글.
"""
doc = proj / 'docs' / '보고서.md'
doc.write_text(DOC, encoding='utf-8')
(proj / 'docs' / '발표.md').write_text('---\nmarp: true\n---\n\n# 발표\n', encoding='utf-8')
server, url, port = serve(proj, config)
LABELS = "[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(path):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            page.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.docPath === p", arg=path)
            page.wait_for_timeout(300)

        def menu():
            page.keyboard.press('Escape')
            page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
            page.wait_for_selector('#lec-menu:not([hidden])')
            return page.evaluate(LABELS)

        def preview():
            src = page.get_attribute('#lec-print-frame', 'src') or ''
            return src, (page.evaluate('(u) => fetch(u).then((r) => r.text())', src) if src.startswith('/export-preview/') else '')

        print('[메뉴와 창]')
        open_doc('docs/보고서.md')
        until(page, lambda: page.locator('#lec-view pre.mermaid svg').count() == 1 and page.locator('#lec-view .lec-chart svg, #lec-view .lec-chart canvas').count() >= 1, 15000)
        page.locator('#lec-view h2', has_text='접을 절').click()
        page.keyboard.press('Control+Shift+BracketLeft')
        page.locator('#lec-view .lec-textbox-fold').click()
        check('절과 박스글을 접어 둔다', until(page, lambda: page.locator('#lec-view .lec-folded').count() == 1 and page.locator('#lec-view .lec-textbox-folded').count() == 1))
        labels = menu()
        check("문서 여백의 우클릭에 'html로 저장…'", 'html로 저장…' in labels, labels)
        page.locator('#lec-menu button', has_text='html로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('창 제목은 내보내기', page.inner_text('#lec-print-title') == '내보내기 — 보고서.md', page.inner_text('#lec-print-title'))
        check('html 형식이 골라져 있고 PDF 는 막혀 있다 (브라우저 개발 모드)',
              page.is_checked('#lec-print input[name="pp_format"][value="html"]') and page.is_disabled('#lec-print input[name="pp_format"][value="pdf"]'))
        check('PDF 옵션과 단추는 감추고 html 단추만', page.is_hidden('#lec-print-layout') and page.is_hidden('#lec-print-save') and page.is_hidden('#lec-print-paper')
              and page.is_visible('#lec-print-html'))
        check('미리보기가 뜬다', until(page, lambda: preview()[0].startswith('/export-preview/'), 20000), page.get_attribute('#lec-print-frame', 'src'))
        check('크기를 알린다', re.fullmatch(r'html 한 파일 · \d+KB', page.inner_text('#lec-print-info')) is not None, page.inner_text('#lec-print-info'))
        src, text = preview()
        body = text[text.index('<body>'):] if '<body>' in text else ''

        print('[지은 파일]')
        check('머리: doctype·generator·제목·출처 이름', text.startswith('<!doctype html>') and '<meta name="generator" content="Lectern">' in text
              and '<title>내보낼 보고서</title>' in text and '<meta name="lectern-source" content="보고서.md">' in text, text[:400])
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', text)
        policy = html.unescape(csp[1]) if csp else ''
        check('스크립트를 허용하지 않는 CSP', "default-src 'none'" in policy and 'script' not in policy, policy)
        check('스크립트·단추·앱 속성이 없다', '<script' not in text.lower() and '<button' not in body and 'data-lines' not in body and 'contenteditable' not in body)
        check('맨 앞 설정 표는 빠진다', 'front-matter' not in body and '시험</td>' not in body)
        check('접어 둔 절과 박스글도 펴서 담는다', '접어 둔 절의 글이다' in body and '상자 안의 글이다' in body and 'lec-fold' not in body and 'lec-textbox-folded' not in body)
        check('프로젝트의 그림은 파일 안에', re.search(r'<img[^>]+src="data:image/png;base64,', body) is not None)
        check('인터넷 그림은 주소로 — referrer 없이, CSP 가 받는다', 'https://example.com/a.png' in body and 'referrerpolicy="no-referrer"' in body and 'img-src data: https: http:' in policy)
        check('Mermaid·차트는 SVG 로', body.count('<svg') >= 2, body.count('<svg'))
        check('수식은 KaTeX — 글꼴이 파일 안에', 'class="katex"' in body and 'url(data:font/woff2' in text and 'fonts/KaTeX' not in text)
        check('같은 파일 안 링크(목차·상호 참조·각주)는 남는다', 'href="#표-1"' in body or 'href="#%ED%91%9C-1"' in body, re.findall(r'href="#[^"]+"', body)[:6])
        check('각주 링크', 'href="#fn1"' in body)
        check('프로젝트 안 문서 링크는 글로', '다른.md' not in re.findall(r'href="([^"]+)"', body).__str__() and '다른 문서' in body)
        ext = re.search(r'<a [^>]*href="https://example.com/x"[^>]*>', body)
        check('바깥 링크는 새 창, referrer 없이', ext and 'target="_blank"' in ext[0] and 'rel="noopener noreferrer"' in ext[0], ext and ext[0])
        check('체크 칸은 누를 수 없게', re.search(r'<input[^>]*disabled', body) is not None)
        check('인쇄하면 보고서 양식 — print.css 와 쪽 머리(제목·날짜)', '<style media="print">' in text and '@page' in text and '"내보낼 보고서"' in text and '2026-10-01' in text)

        print('[미리보기와 저장]')
        frame = page.frame_locator('#lec-print-frame')
        check('미리보기에 문서가 보인다', until(page, lambda: frame.locator('article.md-body h1').count() == 1) and frame.locator('article.md-body h1').inner_text() == '내보낼 보고서')
        with page.expect_download() as dl:
            page.click('#lec-print-html')
        got = Path(dl.value.path()).read_bytes()
        check("'html로 저장…' — 문서 이름.html, 미리 본 바이트 그대로", dl.value.suggested_filename == '보고서.html' and got == text.encode('utf-8'), dl.value.suggested_filename)
        check('저장하면 창이 닫힌다', until(page, lambda: page.is_hidden('#lec-print')))

        print('[결과 파일 열기]')
        out = base / 'out.html'
        out.write_bytes(got)
        view = ctx.new_page()
        asked = []
        view.on('request', lambda r: asked.append(r.url) if not r.url.startswith(('file:', 'data:')) else None)
        view.route(re.compile(r'^https?://'), lambda r: r.abort())   # 시험의 인터넷 그림 주소는 없는 곳이다 — 기다리지 않게
        view.goto(out.as_uri(), wait_until='domcontentloaded')
        view.wait_for_timeout(800)
        check('브라우저로 열면 바깥 요청은 인터넷 그림뿐', set(asked) <= {'https://example.com/a.png'}, asked)
        check('결과 파일에 제목·표·차트가 보인다', view.locator('article.md-body h1').inner_text() == '내보낼 보고서' and view.locator('article.md-body table').count() >= 1
              and view.locator('article.md-body svg').count() >= 2)
        view.close()

        print('[문서가 바뀌면 미리보기도]')
        page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='html로 저장…').click()
        until(page, lambda: preview()[0].startswith('/export-preview/'), 20000)
        first = preview()[0]
        doc.write_text(DOC.replace('상자 안의 글이다.', '고친 상자 글이다.'), encoding='utf-8')
        check('Claude 가 문서를 고치면 미리보기를 다시 짓는다', until(page, lambda: preview()[0] not in ('', first) and '고친 상자 글이다' in preview()[1], 20000))
        page.click('#lec-print-close')
        check('닫기', page.is_hidden('#lec-print'))

        print('[슬라이드와 설정]')
        open_doc('docs/발표.md')
        page.wait_for_timeout(600)
        page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate(LABELS)
        check("Lectern 슬라이드에는 'html로 저장…' 이 없다 (슬라이드는 'html 로 전환')", 'html로 저장…' not in labels, labels)
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ external_images: false }))")
        open_doc('docs/보고서.md')
        page.wait_for_timeout(800)
        page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='html로 저장…').click()
        until(page, lambda: preview()[0].startswith('/export-preview/'), 20000)
        _, off = preview()
        csp2 = html.unescape(re.search(r'Content-Security-Policy" content="([^"]+)"', off)[1])
        # 불러오지 못한 인터넷 그림은 화면이 링크로 바꿔 둔다 (D19) — 그림으로는 담지 않는다
        check('인터넷 그림을 끈 설정이면 인터넷 그림을 담지 않는다', not re.search(r'<img[^>]+src="https?:', off) and 'img-src data:;' in csp2, csp2)
        page.keyboard.press('Escape')
        check('Esc 로 닫는다', until(page, lambda: page.is_hidden('#lec-print')))
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
