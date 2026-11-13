"""보고서 인쇄 양식과 PDF (D131) — 브라우저 개발 모드에서: 메뉴, 인쇄 화면의 모양, 쪽 머리, 글꼴 설정, 어두운 스타일, 슬라이드 쪽 크기,
화면 설정(글자 크기·문서 폭·줄 번호)이 종이에 새지 않음, 쪽 나누기(긴 표·긴 코드·큰 그림·캡션 — 0.74.1 실제 시나리오에서 찾은 것),
'PDF·인쇄' 창(D134 — 창 API 를 가짜로 끼워: 옵션을 바꾸면 미리보기를 다시, 설정에 남기, 미리 본 토큰으로 저장, 슬라이드는 옵션을 막음, Esc).

창 모드의 'PDF로 저장…'(WebView2 + 저장 대화상자)은 여기서 돌지 않는다 — docs/TESTING.md 의 수동 점검. 대신 같은 Chromium 의
printToPDF(page.pdf, preferCSSPageSize)로 쪽 크기·쪽 수를 본다.
"""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-printpdf-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
LONG = '\n\n'.join(f'## {i}. 절\n\n' + '본문 문단이다. ' * 80 for i in range(1, 9))
(proj / 'docs' / '보고서.md').write_text(f"""---
date: 2026-10-01
author: 시험
---

# 보고서 "제목" \\ 끝

> 작성: 시험

첫 문단의 `인라인 코드`. [본문 링크](https://example.com/body)

| 항목 | 값 (t) |
|---|---|
| 가 | 10 |
| 나 | 20 |

표 1. 긴 표

| 번호 | 항목 | 값 (t) |
|---|---|---:|
{''.join(f'| {i} | 항목 {i} | {i * 3} |' + chr(10) for i in range(1, 21))}
| 구분 | 1월 | 2월 | 3월 | 4월 | 5월 | 6월 | 7월 | 8월 | 9월 | 10월 | 11월 | 12월 | 합계 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 품목 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 78 |

```python
{chr(10).join(f'v{i} = {i}' for i in range(1, 41))}
long_line = "{'x' * 300}"
```

![큰 그림](tall.svg)

그림 1. 아주 긴 그림

{LONG}

## 출처

- [기관 보고서](https://example.org/report)
""", encoding='utf-8')
(proj / 'docs' / '발표.md').write_text("""---
marp: true
---

# 첫 장

---

## 둘째 장

- 하나

---

<!-- hidden: true -->

## 숨긴 장
""", encoding='utf-8')
(proj / 'docs' / 'tall.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="2400"><rect width="400" height="2400" fill="#ccd"/></svg>', encoding='utf-8')
(proj / 'docs' / '쪽.html').write_text('<!doctype html><title>쪽</title><h1>html 문서</h1><p>본문</p>', encoding='utf-8')

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"


def media_boxes(pdf: bytes):
    return [tuple(round(float(x)) for x in m.split()[2:4]) for m in re.findall(rb'/MediaBox\s*\[([^\]]+)\]', pdf and pdf or b'')] if pdf else []


def menu(page, keep=False):
    """문서 여백을 우클릭한 메뉴의 항목들 (스크롤돼 있어도 보이는 곳에서). keep 이면 메뉴를 닫지 않는다"""
    page.keyboard.press('Escape')
    box = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const r = v.getBoundingClientRect();
      const left = Math.min(...[...v.children].map((c) => c.getBoundingClientRect().left));
      const c = document.querySelector('#lec-content').getBoundingClientRect();
      return { x: Math.max(r.left + 4, left - 14), y: c.top + Math.min(200, c.height / 3) }; }""")
    page.mouse.click(box['x'], box['y'], button='right')
    page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
    items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
    if not keep:
        page.keyboard.press('Escape')
    return items


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate(OPEN, 'docs/보고서.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)

        print('[메뉴 — 브라우저 개발 모드에는 PDF로 저장이 없다]')
        items = menu(page)
        check("인쇄 창 하나 ('인쇄 / PDF로 저장…')", '인쇄 / PDF로 저장…' in items and 'PDF로 저장…' not in items, items)
        check('루트에 인쇄 글꼴 (기본 명조)', page.evaluate('() => document.documentElement.dataset.printFont') == 'serif')

        print('[인쇄 화면 — 보고서 양식]')
        page.evaluate("() => dispatchEvent(new Event('beforeprint'))")   # 인쇄 직전 (printdoc.js 가 쪽 머리를 적는다)
        css = page.evaluate("() => document.querySelector('#lec-print-page')?.textContent || ''")
        check('쪽 머리에 문서 제목 — 따옴표·역슬래시는 CSS 글자로', '"보고서 \\"제목\\" \\\\ 끝"' in css, css[:200])
        check('쪽 머리 날짜는 맨 앞 설정의 date', '"2026-10-01"' in css, css[:300])
        check('첫 쪽은 머리 없음을 뒤에 다시', css.index('@page :first') > css.index('@top-left { content: "'), css)
        page.emulate_media(media='print')
        look = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const cs = (el) => getComputedStyle(el);
          const a = v.querySelector('a.ext'); const src = [...v.querySelectorAll('a.ext')].pop();
          return { toolbar: cs(document.querySelector('#lec-toolbar')).display, font: cs(v).fontFamily, size: cs(v).fontSize,
            front: cs(v.querySelector('.front-matter')).display, h1: cs(v.querySelector('h1')).textAlign,
            link: getComputedStyle(a, '::after').content, source: getComputedStyle(src, '::after').content,
            th: cs(v.querySelector('thead th')).backgroundColor, html: cs(document.documentElement).backgroundColor }; }""")
        check('툴바는 빠진다', look['toolbar'] == 'none', look)
        check('본문은 명조 (함초롬바탕부터)', look['font'].startswith('"HCR Batang"'), look['font'])
        check('본문 10.5pt', look['size'] == '14px', look['size'])
        check('맨 앞 설정은 싣지 않는다', look['front'] == 'none', look['front'])
        check('제목은 가운데', look['h1'] == 'center', look['h1'])
        check('본문 링크 뒤에 주소가 붙지 않는다', look['link'] in ('none', 'normal'), look['link'])
        check("'출처' 절의 링크는 주소와 함께", 'example.org' in look['source'] or 'attr' in look['source'], look['source'])
        check('표 머리행은 옅은 회색', look['th'] == 'rgb(236, 236, 236)', look['th'])
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        boxes = media_boxes(pdf)
        check('A4 쪽 (595 x 842)', boxes and all(bx == (595, 842) for bx in boxes), boxes[:3])
        check('여러 쪽', len(boxes) >= 3, len(boxes))
        page.emulate_media(media='screen')

        print('[쪽 나누기 — 긴 표·긴 코드·큰 그림·캡션·넓은 표]')
        page.emulate_media(media='print')
        brk = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const cs = (el) => getComputedStyle(el);
          const tables = [...v.querySelectorAll('table')]; const long = tables.find((t) => t.rows.length > 13); const wide = tables.find((t) => t.rows[0].cells.length > 12);
          const pres = [...v.querySelectorAll('pre:not(.mermaid):not(.lec-chart)')]; const cap = long.closest('.table-wrap').previousElementSibling;
          const img = v.querySelector('img[alt="큰 그림"]');
          return { longTable: cs(long).breakInside, shortTable: cs(tables[0] === long ? tables[tables.length - 1] : tables[0]).breakInside, thead: cs(long.tHead).display,
            caption: cap.textContent.trim().slice(0, 6) + ' ' + cs(cap).breakAfter, wideSize: cs(wide).fontSize, cell: cs(wide.rows[0].cells[10]).wordBreak,
            preLong: pres[0].classList.contains('lec-print-long') + ' ' + cs(pres[0]).breakInside + ' ' + cs(pres[0]).whiteSpace,
            imgMax: cs(img).maxHeight }; }""")
        check('12행이 넘는 표는 쪽을 나눠 싣고 머리행을 되풀이', brk['longTable'] == 'auto' and brk['thead'] == 'table-header-group', brk)
        check('짧은 표는 한 덩어리', brk['shortTable'] == 'avoid', brk['shortTable'])
        check("캡션 '표 1.' 은 표와 붙는다", brk['caption'] == '표 1. 긴 avoid', brk['caption'])
        check('열이 13개 넘는 표는 7pt, 칸 안에서 낱말을 쪼개지 않음', brk['wideSize'] == '9.33333px' and brk['cell'] == 'keep-all', brk)
        check('40줄 코드는 쪽을 나눠 싣고 긴 줄은 접는다', brk['preLong'] == 'true auto pre-wrap', brk['preLong'])
        check('그림은 한 쪽 높이(225mm) 안으로', brk['imgMax'].startswith('850'), brk['imgMax'])
        page.emulate_media(media='screen')

        print('[화면 설정이 종이에 새지 않는다 — 글자 크기·문서 폭·줄 번호]')
        page.emulate_media(media='print')
        plain = page.evaluate("() => { const c = document.querySelector('#lec-view p code, #lec-view code'); return [getComputedStyle(document.querySelector('#lec-view')).paddingLeft, c ? getComputedStyle(c).fontSize : '']; }")
        page.emulate_media(media='screen')
        for _ in range(4):
            page.click('#lec-text-bigger')
        while page.is_enabled('#lec-width-wider'):
            page.click('#lec-width-wider')
        page.click('#lec-view h1')
        page.keyboard.press('Alt+l')
        until(page, "() => document.documentElement.classList.contains('line-numbers')")
        page.emulate_media(media='print')
        leaked = page.evaluate("() => { const c = document.querySelector('#lec-view p code, #lec-view code'); return [getComputedStyle(document.querySelector('#lec-view')).paddingLeft, c ? getComputedStyle(c).fontSize : '']; }")
        page.emulate_media(media='screen')
        check('줄 번호를 켜도 본문 왼쪽 여백 0, 글자를 키워도 같은 크기', plain == leaked and leaked[0] == '0px', (plain, leaked))
        page.keyboard.press('Alt+l')
        page.click('#lec-text-reset')
        page.click('#lec-width-reset')
        page.emulate_media(media='print')   # 'screen' 을 흉내 낸 채면 page.pdf 도 화면 모양으로 만든다
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        page.emulate_media(media='screen')
        check('PDF 도 A4', media_boxes(pdf)[:1] == [(595, 842)], media_boxes(pdf)[:1])

        print('[설정 창 — 인쇄·PDF 글꼴]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        check('명조가 골라져 있다', page.is_checked('#lec-settings input[name="print_font"][value="serif"]'))
        page.click('#lec-settings input[name="print_font"][value="sans"]')
        expect(page, '고딕을 고르면 루트에 sans', "() => document.documentElement.dataset.printFont === 'sans'")
        page.keyboard.press('Escape')
        page.emulate_media(media='print')
        font = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view')).fontFamily")
        check('본문이 고딕 (맑은 고딕)', font.startswith('"Malgun Gothic"'), font)
        page.emulate_media(media='screen')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        expect(page, '다시 열어도 고딕', "() => document.documentElement.dataset.printFont === 'sans'")

        print('[어두운 화면 스타일 — 종이는 흰 바탕]')
        page.evaluate(OPEN, 'docs/보고서.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then(async (s) => { s.S.config.theme = 'dark'; await (await import('/static/js/theme.js')).applyTheme(); })")
        until(page, "() => document.documentElement.dataset.ui === 'dark'")
        page.emulate_media(media='print')
        look = page.evaluate("() => ({ html: getComputedStyle(document.documentElement).backgroundColor, scheme: getComputedStyle(document.documentElement).colorScheme, fg: getComputedStyle(document.querySelector('#lec-view > p')).color })")
        check('바탕은 흰색, 색 체계는 밝게', look['html'] == 'rgb(255, 255, 255)' and look['scheme'] == 'light', look)
        check('글자는 검게', look['fg'] in ('rgb(17, 17, 17)', 'rgb(0, 0, 0)'), look['fg'])
        page.emulate_media(media='screen')

        print('[Lectern 슬라이드 — 쪽 크기는 슬라이드]')
        page.evaluate(OPEN, 'docs/발표.md')
        page.wait_for_selector('#lec-view .lec-slide', timeout=20000)
        page.wait_for_timeout(500)
        page.evaluate("() => dispatchEvent(new Event('beforeprint'))")
        css = page.evaluate("() => document.querySelector('#lec-print-page')?.textContent || ''")
        check('기본 쪽 크기를 슬라이드 크기로', 'size: 1280px 720px' in css and 'margin: 0' in css, css)
        page.emulate_media(media='print')   # 'screen' 을 흉내 낸 채면 page.pdf 도 화면 모양으로 만든다
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
        page.emulate_media(media='screen')
        boxes = media_boxes(pdf)
        check('숨기지 않은 두 장이 두 쪽, 960x540', boxes == [(960, 540), (960, 540)], boxes)

        print('[html 문서 — 인쇄 창 하나, md 문서 스타일 없음]')
        page.evaluate(OPEN, 'docs/쪽.html')
        page.wait_for_selector('#lec-view > iframe.lec-html:not(.lec-loading)', timeout=20000)
        page.wait_for_timeout(500)
        page.evaluate("() => { const v = document.querySelector('#lec-view'); v.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: v.getBoundingClientRect().left + 3, clientY: 300 })); }")
        page.wait_for_timeout(300)
        items = page.evaluate("() => document.querySelector('#lec-menu').hidden ? [] : [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("'인쇄 / PDF로 저장…' 만 있고 'md 문서 스타일…' 은 없다 (칸에 앞 md 문서의 경로가 남아 있어도)",
              '인쇄 / PDF로 저장…' in items and 'md 문서 스타일…' not in items, items)
        page.keyboard.press('Escape')

        print('[글쓰기 스타일 — 설정 창의 요청 글]')
        style = page.evaluate("() => import('/static/js/store.js').then((m) => m.S.writingStyle)")
        check('스타일 파일의 경로', style.endswith('research-writing.md'), style)
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        check('글쓰기 스타일 칸과 두 버튼', page.is_visible('#lec-wstyle-prompt') and page.is_visible('#lec-wstyle-term'))
        page.keyboard.press('Escape')

        print("[PDF·인쇄 창 — 가짜 창 API 로]")
        page.evaluate(OPEN, 'docs/보고서.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)
        page.evaluate("""() => { window.__calls = []; window.pywebview = { api: {
          pdf_preview: async () => { const css = document.querySelector('#lec-print-page')?.textContent || ''; window.__calls.push(['preview', css]);
            await new Promise((r) => setTimeout(r, 120)); return { token: 'fake' + window.__calls.length, pages: 3, size: 4096 }; },
          save_pdf: async (tab, path, token) => { window.__calls.push(['save', path, token]); return { path: 'C:/x/보고서.pdf' }; } } }; }""")
        calls = lambda: page.evaluate('() => window.__calls')
        items = menu(page, keep=True)
        check("창 모드면 'PDF로 저장…'·'인쇄…'", 'PDF로 저장…' in items and '인쇄…' in items, items)
        page.click('#lec-menu button:has-text("PDF로 저장…")')
        expect(page, '창이 뜨고 미리보기 정보', "() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-info').textContent === '3쪽 · 4KB'",
               lambda: page.evaluate("() => document.querySelector('#lec-print-info').textContent"))
        first = calls()
        check('처음 미리보기는 보통 여백과 머리 제목으로', len(first) == 1 and 'margin: 25mm 22mm 22mm 22mm' in first[0][1] and '보고서' in first[0][1], first[-1:])
        check('iframe 은 미리보기 주소', page.evaluate("() => document.querySelector('#lec-print-frame').getAttribute('src')") == '/pdf-preview/fake1.pdf#view=Fit')
        page.click('#lec-print input[name=pp_margin][value=narrow]')
        until(page, lambda: len(calls()) >= 2 and page.evaluate("() => document.querySelector('#lec-print-wait').hidden"))
        check('여백을 바꾸면 다시 만든다 (15mm)', 'margin: 15mm 15mm 15mm 15mm' in calls()[-1][1], calls()[-1][1][:80])
        page.click('#lec-pp-header')
        until(page, lambda: len(calls()) >= 3 and page.evaluate("() => document.querySelector('#lec-print-wait').hidden"))
        css = calls()[-1][1]
        check('쪽 머리를 끄면 머리 글자가 없다', '@top-left { content: none; font-family' in css and '@top-right { content: none; font-family' in css, css[:200])
        page.click('#lec-pp-pages')
        until(page, lambda: len(calls()) >= 4 and page.evaluate("() => document.querySelector('#lec-print-wait').hidden"))
        check('쪽 번호를 끄면 바닥도 없다', '@bottom-center { content: none;' in calls()[-1][1], calls()[-1][1][:240])
        cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('옵션은 설정에 남는다', cfg.get('print_margin') == 'narrow' and cfg.get('print_header') is False and cfg.get('print_page_numbers') is False,
              {k: v for k, v in cfg.items() if k.startswith('print')})
        page.click('#lec-print-save')
        expect(page, '저장은 미리 본 토큰으로, 저장하면 창이 닫힌다', "() => document.querySelector('#lec-print').hidden")
        last = calls()[-1]
        check('save_pdf(탭, 문서, 마지막 미리보기 토큰)', last[0] == 'save' and last[1] == 'docs/보고서.md' and last[2] == f'fake{len(calls()) - 1}', last)
        items = menu(page, keep=True)
        page.click('#lec-menu button:has-text("인쇄…")')
        expect(page, "'인쇄…' 로 열면 인쇄가 기본 단추", "() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-paper').classList.contains('primary')")
        check('다시 열면 고른 옵션 그대로', page.evaluate("() => [document.querySelector('#lec-print input[name=pp_margin]:checked').value, document.querySelector('#lec-pp-header').checked]") == ['narrow', False])
        for sel in ('#lec-print input[name=pp_margin][value=normal]', '#lec-pp-header', '#lec-pp-pages'):
            n = len(calls())
            page.click(sel)
            until(page, lambda: len(calls()) > n and page.evaluate("() => document.querySelector('#lec-print-wait').hidden"))
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 닫는다', "() => document.querySelector('#lec-print').hidden")
        page.evaluate(OPEN, 'docs/발표.md')
        page.wait_for_selector('#lec-view .lec-slide', timeout=20000)
        page.wait_for_timeout(400)
        menu(page, keep=True)
        page.click('#lec-menu button:has-text("PDF로 저장…")')
        expect(page, '슬라이드: 옵션은 막고 까닭을 알린다', "() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-layout').disabled && document.querySelector('#lec-print-note').textContent.includes('슬라이드')")
        until(page, lambda: page.evaluate("() => document.querySelector('#lec-print-wait').hidden"))
        check('슬라이드 미리보기는 슬라이드 크기 쪽으로', 'size: 1280px 720px' in calls()[-1][1], calls()[-1][1][:120])
        page.click('#lec-print-close')
        expect(page, '닫기 단추', "() => document.querySelector('#lec-print').hidden")

        print('[탭 막대의 [인쇄] 버튼 (D135)]')
        order = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn')].map((b) => b.id)")
        check('순서: 편집·목차·인쇄·메모·터미널', order == ['lec-btn-edit', 'lec-btn-toc', 'lec-btn-print', 'lec-btn-notes', 'lec-btn-term'], order)
        page.evaluate(OPEN, 'docs/보고서.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)
        page.click('#lec-btn-print')
        expect(page, 'md 문서면 PDF·인쇄 창, 인쇄가 기본 단추', "() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-paper').classList.contains('primary')")
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 닫힘', "() => document.querySelector('#lec-print').hidden")
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'overview', path: '' }))")
        page.wait_for_selector('#lec-view.overview', timeout=10000)
        page.click('#lec-btn-print')
        expect(page, '폴더 개요면 알림만', "() => document.querySelector('#lec-print').hidden && document.querySelector('#lec-toast').textContent.includes('문서를 볼 때 인쇄')")
        page.evaluate('() => { delete window.pywebview; }')
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
