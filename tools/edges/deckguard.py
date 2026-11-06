"""슬라이드의 울타리 (D96): 문서가 CSS·HTML·칸 낱말로 앱을 건드리거나 바깥에 요청하거나 터미널에 글을 흘리지 못하는지"""
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-deckguard-'))
proj = base / 'proj'
proj.mkdir()
ESC = '\x1b'
PIXEL = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='
EVIL = 'https://example.com'
DECK = rf"""---
marp: true
title: 울타리
size: constructor
style: |
  section {{ background-color: rgb(1, 2, 3); }}
  h2 {{ color: rgb(9, 8, 7); }}
  section.lead h1 {{ color: rgb(11, 12, 13); font-family: "Noto Sans KR", sans-serif; }}
  section::after {{ content: "쪽 \2014"; }}
  section > h2:first-child {{ letter-spacing: 1px; }}
  .band {{ background: linear-gradient(90deg, rgb(1, 1, 1), rgb(2, 2, 2)); }}
  @media print {{ section {{ color: rgb(20, 21, 22); }} }}
  .pic {{ background-image: url("{PIXEL}"); }}
  :has(&) #lec-status {{ display: none; }}
  :not(&) {{ display: none; }}
  :is(&, #lec-status) {{ display: none; }}
  \{{ }} #lec-status {{ display: none; }}
  h3 {{ content: "a
  }} #lec-status {{ display: none; }}
  h4 {{ background: u\72l({EVIL}/esc.png); }}
  h5 {{ background: image\-set("{EVIL}/set.png" 1x); }}
  h6 {{ background: -webkit-image\-set("{EVIL}/webkit.png" 1x); }}
  p {{ --x: url({EVIL}/var.png); background-image: var(--x); }}
  li {{ background: var(--c, red) url({EVIL}/short.png); }}
  td {{ border-image: url({EVIL}/border.png) 1; }}
  th {{ cursor: url({EVIL}/cur.png), auto; }}
  section {{ position: fixed; inset: 0; z-index: 99999; }}
  blockquote {{ --p: fixed; position: var(--p); }}
  meta {{ display: block; background: url("{EVIL}/meta?a=1"); }}
  pre {{ background: url("{EVIL}/open.png
---

# 표지

<img src="x" style="background: u\72l({EVIL}/inline.png)">

---

<style scoped>
h2 {{ background: u\72l({EVIL}/scoped.png); }}
:has(&) #lec-toolbar {{ display: none; }}
</style>

## 위조 틀

<div class="lec-slide-wrap" data-issues='[{{"text":"가짜 점검","line":1}}]' data-lines="1-9999" data-slide="1"><section class="lec-slide" data-page="1">가짜 슬라이드</section></div>

<span class="lec-tag" data-tag="a" data-tag-line="1">가짜 꼬리표</span>

<div id="lec-st-check">가짜 상태</div>

<div id="lec-menu">가짜 메뉴</div>

---

<!-- class: lec-slide-wrap lead -->

# 칸 낱말

::: a lec-slide-wrap card
위조 낱말이다.
:::

---

<!-- layout: constructor -->

## 없는 배치

::: a
글
:::

---

<!-- layout: 없는배치{ESC}[201~{ESC}]0;x{ESC}\ -->

## 제어 문자

::: a
글
:::

---

## 칸의 지시어

::: a
<!-- 칸 안의 노트 -->
<!-- text: 본문 15 -->
칸의 글이다.

<style scoped>
section {{ border-top-color: rgb(4, 5, 6); }}
</style>
:::
"""
(proj / '발표.md').write_text(DECK, encoding='utf-8', newline='\n')
(proj / '많은칸.md').write_text('---\nmarp: true\n---\n\n' + '::: a\n' * 16000, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
requests = []


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.on('request', lambda r: requests.append(r.url))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="발표.md"]').click()
        page.wait_for_selector('#lec-view.lec-deck', timeout=20000)
        page.wait_for_timeout(1500)

        print('[CSS 가두기]')
        check('상태줄이 보인다', page.locator('#lec-status').is_visible())
        check('도구 줄이 보인다', page.locator('#lec-toolbar').is_visible())
        check('문서 칸이 보인다', page.locator('#lec-view').is_visible())
        css = page.evaluate("[...document.querySelectorAll('#lec-view style.lec-deck-style')].map((s) => s.textContent).join('\\n')")
        check('& 가 남지 않았다', '&' not in css, css[:300])
        check('밖으로 가는 주소가 없다', 'example.com' not in css, css[:400])
        check('고정 위치가 없다', 'position: fixed' not in css and 'position: var' not in css, css[:300])
        low = lambda n, sel, name: page.evaluate(f"getComputedStyle(document.querySelectorAll('#lec-view .lec-slide')[{n}].querySelector('{sel}'))['{name}']")
        check('바른 CSS 는 듣는다 (배경)', page.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-slide')).backgroundColor") == 'rgb(1, 2, 3)')
        check('바른 CSS 는 듣는다 (제목)', low(1, 'h2', 'color') == 'rgb(9, 8, 7)', low(1, 'h2', 'color'))
        check('데이터 그림은 남는다', PIXEL in css, css[:300])
        check('선택자가 든 규칙이 듣는다', low(2, 'h1', 'color') == 'rgb(11, 12, 13)', low(2, 'h1', 'color'))
        check('글꼴 지정이 남는다', 'Noto Sans KR' in low(2, 'h1', 'fontFamily'), low(2, 'h1', 'fontFamily'))
        check('자식 선택자가 듣는다', low(1, 'h2', 'letterSpacing') == '1px', low(1, 'h2', 'letterSpacing'))
        check('의사 요소의 글이 남는다', '쪽 —' in page.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-slide'), '::after').content"))
        check('그라데이션이 남는다', 'linear-gradient' in css, css[:300])
        check('인쇄 규칙이 남는다', '@media print' in css and 'rgb(20, 21, 22)' in css, css[:300])
        check('슬라이드는 제자리에', page.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-slide')).position") != 'fixed')
        check('문서의 z-index 가 틀 밖으로 나오지 않는다', page.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-slide-wrap')).isolation") == 'isolate')

        print('[위조]')
        check('진짜 슬라이드 수', page.locator('#lec-view .lec-slide').count() == 6, page.locator('#lec-view .lec-slide').count())
        check('진짜 틀 수', page.locator('#lec-view .lec-slide-wrap').count() == 6, page.locator('#lec-view .lec-slide-wrap').count())
        check('가짜 꼬리표가 없다', page.locator('#lec-view .lec-tag', has_text='가짜 꼬리표').count() == 0)
        check('문서의 앱 id 가 없다', page.locator('#lec-view #lec-st-check, #lec-view #lec-menu').count() == 0)
        check('앱의 점검 표시는 하나', page.locator('#lec-st-check').count() == 1)
        check('칸의 lec- 낱말을 버린다', page.locator('#lec-view .lec-cell.lec-slide-wrap').count() == 0)
        check('장의 lec- 낱말을 버린다', page.locator('#lec-view section.lec-slide-wrap').count() == 0)
        check('다른 낱말은 남는다', page.locator('#lec-view .lec-slide.lead').count() >= 1)
        issues = page.evaluate("[...document.querySelectorAll('#lec-view .lec-slide-wrap')].flatMap((w) => JSON.parse(w.dataset.issues || '[]')).map((i) => i.text)")
        check('가짜 점검이 없다', not any('가짜' in x for x in issues), issues)
        check('없는 배치를 알린다 (constructor)', any('constructor' in x for x in issues), issues)

        print('[터미널에 넣는 글]')
        got = page.evaluate(r"""import('/static/js/terminal.js').then(({ plainText }) => ({
            esc: plainText('a\x1b[201~b\x1b]0;x\x07c\x9b1m'), crlf: plainText('a\r\nb\rc\td'), nul: plainText('a\x00\x7fb'),
        }))""")
        check('ESC·종 문자를 뺀다', got['esc'] == 'a[201~b]0;xc1m', repr(got['esc']))
        check('줄바꿈과 탭은 남긴다', got['crlf'] == 'a\nb\nc\td', repr(got['crlf']))
        check('NUL·DEL 을 뺀다', got['nul'] == 'ab', repr(got['nul']))
        page.wait_for_selector('#lec-st-check:not([hidden])', timeout=5000)
        page.evaluate("navigator.clipboard.writeText = (x) => { window.__copied = x; return Promise.resolve(); }")
        page.locator('#lec-st-check').click()
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        check('점검 목록에 ESC 가 없다', ESC not in menu and '없는배치' in menu, repr(menu[:200]))
        page.locator('#lec-menu button', has_text='복사').first.click()
        page.wait_for_timeout(200)
        text = page.evaluate('window.__copied || ""')
        check('복사한 글에 제어 문자가 없다', text and not any(ord(c) < 32 and c not in '\n\t' or 127 <= ord(c) < 160 for c in text), repr(text[:200]))

        print('[칸 안의 노트·지시어·CSS]')
        last = page.locator('#lec-view .lec-slide').nth(5)
        note = page.locator('#lec-view .lec-slide-notes').last.text_content() or ''
        check('칸 안의 노트를 읽는다', '칸 안의 노트' in note, note)
        check('칸 안의 글에 주석이 없다', '칸 안의 노트' not in last.text_content())
        pts = last.locator('.lec-cell p').first.evaluate("(e) => Math.round(parseFloat(getComputedStyle(e).fontSize) * 7.5) / 10")
        check('칸 안의 지시어를 읽는다', pts == 15, pts)
        check('칸 안의 style 을 읽는다', last.evaluate('(e) => getComputedStyle(e).borderTopColor') == 'rgb(4, 5, 6)', last.evaluate('(e) => getComputedStyle(e).borderTopColor'))

        print('[많은 머리 줄]')
        started = time.time()
        page.locator('#lec-tree .row.file[data-doc="많은칸.md"]').click()
        page.wait_for_function("document.querySelector('#lec-view .lec-slide')?.textContent.includes('::: a')", timeout=15000)
        took = time.time() - started
        check('닫지 않은 칸이 많아도 멈추지 않는다', took < 5, f'{took:.1f}초')

        check('바깥 요청이 없다', not [u for u in requests if 'example.com' in u], [u for u in requests if 'example.com' in u][:4])
        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
