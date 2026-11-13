"""보고서 인쇄 양식과 PDF (D131) — 브라우저 개발 모드에서: 메뉴, 인쇄 화면의 모양, 쪽 머리, 글꼴 설정, 어두운 스타일, 슬라이드 쪽 크기.

창 모드의 'PDF로 저장…'(WebView2 + 저장 대화상자)은 여기서 돌지 않는다 — docs/TESTING.md 의 수동 점검. 대신 같은 Chromium 의
printToPDF(page.pdf, preferCSSPageSize)로 쪽 크기·쪽 수를 본다.
"""
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

첫 문단. [본문 링크](https://example.com/body)

| 항목 | 값 (t) |
|---|---|
| 가 | 10 |
| 나 | 20 |

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
(proj / 'docs' / '쪽.html').write_text('<!doctype html><title>쪽</title><h1>html 문서</h1><p>본문</p>', encoding='utf-8')

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"


def media_boxes(pdf: bytes):
    return [tuple(round(float(x)) for x in m.split()[2:4]) for m in re.findall(rb'/MediaBox\s*\[([^\]]+)\]', pdf and pdf or b'')] if pdf else []


def menu(page):
    page.keyboard.press('Escape')
    box = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const r = v.getBoundingClientRect();
      const left = Math.min(...[...v.children].map((c) => c.getBoundingClientRect().left));
      return { x: Math.max(r.left + 4, left - 14), y: r.top + 200 }; }""")
    page.mouse.click(box['x'], box['y'], button='right')
    page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
    items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
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
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
