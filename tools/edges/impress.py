"""html 로 전환 (D129): 창(배치·지도·알림), 만든 파일(impress 가 켜짐·장 자리·노트·그림·수식 글꼴·차트·바깥 요청 0·스크립트는 둘뿐),
발표자 콘솔, 스크립트 없이 연 모양(Lectern 의 html 보기), impress: 지시어의 점검, API 의 거절"""
import base64
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-impress-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir()
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
(proj / '그림.png').write_bytes(PNG)
(proj / '보통.md').write_text('# 보통\n\n글입니다.\n', encoding='utf-8')
CHART = '{"data": {"values": [{"a": "가", "b": 3}, {"a": "나", "b": 5}]}, "mark": "bar", "encoding": {"x": {"field": "a", "type": "nominal"}, "y": {"field": "b", "type": "quantitative"}}}'
(proj / '전환시험.md').write_text(f'''---
marp: true
title: 전환 시험 발표
impress: grid
---

<!-- _class: lead -->
# 표지

<!-- 첫 장의 노트입니다 -->

---

## Mermaid

```mermaid
graph LR
  A[시작] --> B[끝]
```

---

<!-- layout: two -->
## 칸과 차트

::: a
- 왼쪽 글
- ![그림](그림.png)
:::

::: b
```vega-lite
{CHART}
```
:::

---

## 수식과 링크

$$\\int_0^1 x^2 \\, dx$$

[다른 문서](보통.md) · [바깥](https://example.com/page)

<img src="그림.png" alt="심은 그림" onerror="window.EVIL = 1">

---

<!-- hidden: true -->
## 숨긴 장

---

<!-- impress: x=0 y=3000 rotate=90 scale=2 -->
## 자리를 적은 장

<!-- 이 장은 돌아 있습니다 -->

---

<!-- _class: lead -->
# 2부

---

## 마지막

끝
''', encoding='utf-8')
(proj / '점검.md').write_text('''---
marp: true
impress: spiral
---

# 첫 장

<!-- imprss: x=1 -->

---

<!-- impress: x=abc w=3 y=10 -->
## 둘째
''', encoding='utf-8')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1320, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        api = lambda method, path, data=None: page.evaluate('''async ([method, path, data]) => {
            const r = await fetch(path, method === 'GET' ? {} : { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
            return { status: r.status, body: await r.json().catch(() => null) };
        }''', [method, path, data])
        tab = page.evaluate("fetch('/api/state').then((r) => r.json()).then((s) => s.tabs?.[0]?.id ?? s.projects?.[0]?.id ?? '')")

        print('[지시어 — 노트로 새지 않고, 잘못 쓰면 점검이 알린다]')
        page.locator('#lec-tree .row.file[data-doc="점검.md"]').click()
        page.wait_for_selector('#lec-view .lec-slide-wrap', timeout=10000)
        issues = until(page, "[...document.querySelectorAll('#lec-view .lec-slide-wrap')].map((w) => w.dataset.issues || '').join(' ')", 6000)
        check('맨 앞 설정의 모르는 배치 방식', 'spiral' in issues and 'grid' in issues, issues[:300])
        check('지시어 이름의 오타 (imprss)', 'imprss' in issues, issues[:300])
        check('읽지 못한 낱말', 'x=abc w=3' in issues, issues[:300])
        check('잘못된 impress 주석도 노트가 아니다', not page.evaluate("[...document.querySelectorAll('#lec-view .lec-slide-notes')].some((n) => n.textContent.includes('impress:'))"))

        print('[창]')
        page.locator('#lec-tree .row.file[data-doc="전환시험.md"]').click()
        page.wait_for_selector('#lec-view .lec-slide-wrap', timeout=10000)
        expect(page, '다이어그램·차트가 그려진다', "document.querySelectorAll('#lec-view pre.mermaid svg').length === 1 && document.querySelectorAll('#lec-view .lec-chart svg').length >= 1", ms=20000)
        check('장의 impress 주석은 노트로 가지 않는다', not page.evaluate("[...document.querySelectorAll('#lec-view .lec-slide-notes')].some((n) => n.textContent.includes('impress'))"))
        check('그 장에 자리가 적힌다', page.evaluate("document.querySelector('#lec-view .lec-slide[data-impress]')?.dataset.impress") == 'x=0 y=3000 rotate=90 scale=2')
        check('상태줄에 html 로 전환', page.locator('#lec-st-html').is_visible())
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])', timeout=5000)
        check('창의 제목에 만들 파일 이름', '전환시험.html' in page.text_content('#lec-html-title'), page.text_content('#lec-html-title'))
        check('문서에 적은 배치 방식이 처음 값', page.is_checked('input[name="lec-html-mode"][value="grid"]'))
        check('지도에 숨기지 않은 장 7개', page.locator('#lec-html-map rect').count() == 7, page.locator('#lec-html-map rect').count())
        check('표지·간지와 자리를 적은 장이 다르게', page.locator('#lec-html-map rect.lead').count() == 2 and page.locator('#lec-html-map rect.placed').count() == 1)
        info = page.text_content('#lec-html-info')
        check('알림: 장 수·숨긴 장·자리를 적은 장', '7장' in info and '숨긴 장 1개' in info and '자리를 적은 장 1개' in info, info)
        grid_xy = page.evaluate("[...document.querySelectorAll('#lec-html-map rect')].map((r) => [+r.getAttribute('x'), +r.getAttribute('y')])")
        page.click('input[name="lec-html-mode"][value="line"]')
        line_xy = page.evaluate("[...document.querySelectorAll('#lec-html-map rect')].map((r) => [+r.getAttribute('x'), +r.getAttribute('y')])")
        check('가로 한 줄을 고르면 지도가 바뀐다', grid_xy != line_xy and len({y for _, y in line_xy[:4]}) == 1)
        page.click('input[name="lec-html-mode"][value="grid"]')
        page.click('#lec-html-go')
        expect(page, '만들면 끝난 화면', "!document.querySelector('#lec-html-done').hidden", ms=20000)
        out = proj / '전환시험.html'
        summary = page.text_content('#lec-html-summary')
        check('파일이 문서 옆에 생긴다', out.is_file(), list(proj.iterdir()))
        check('알림에 이름과 장 수', '전환시험.html' in summary and '7' in summary, summary)
        page.click('#lec-html-open')   # 점검 서버는 브라우저를 띄우지 않는다 (quiet_app) — 거절하지 않는지만
        page.wait_for_timeout(300)
        check('방금 만든 파일은 브라우저로 열기를 받는다', page.locator('#lec-html').is_hidden() and not page.locator('#lec-toast:not([hidden])').is_visible())

        print('[다시 만들면 새 이름 — 덮어쓰지 않는다]')
        first = out.read_bytes()
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        check('제목이 다음 이름', '전환시험 2.html' in page.text_content('#lec-html-title'), page.text_content('#lec-html-title'))
        page.uncheck('#lec-html-overview')
        page.click('#lec-html-go')
        expect(page, '두 번째도 만든다', "!document.querySelector('#lec-html-done').hidden", ms=20000)
        page.click('#lec-html-close')
        check('첫 파일은 그대로', out.read_bytes() == first)
        check('둘째 파일', (proj / '전환시험 2.html').is_file())

        print('[API 의 거절]')
        r = api('POST', '/api/html-export', {'p': tab, 'path': '보통.md', 'html': first.decode('utf-8')})
        check('Lectern 슬라이드가 아닌 md 옆에는 만들지 않는다', r['status'] == 400 and not (proj / '보통.html').exists(), r)
        r = api('POST', '/api/html-export', {'p': tab, 'path': '전환시험.md', 'html': '<!doctype html><p>아무 글</p>'})
        check('화면이 지은 html 이 아니면 받지 않는다', r['status'] == 400, r)
        r = api('POST', '/api/html-export', {'p': tab, 'path': '../밖.md', 'html': first.decode('utf-8')})
        check('프로젝트 밖은 404', r['status'] == 404, r)
        r = api('POST', '/api/html-export/open', {'p': tab, 'path': '보통.md'})
        check('만들지 않은 파일은 브라우저로 열지 않는다', r['status'] == 403, r)
        r = api('GET', f'/api/html-export?p={tab}&path=%EC%A0%84%ED%99%98%EC%8B%9C%ED%97%98.md')
        check('다음 이름은 3', r['status'] == 200 and r['body']['out'] == '전환시험 3.html', r)

        print('[만든 파일을 브라우저로 — 발표]')
        ctx = b.new_context(viewport={'width': 1600, 'height': 900})
        outside = []
        ctx.route('**/*', lambda route: (outside.append(route.request.url), route.abort()) if not route.request.url.startswith('file:') else route.continue_())
        show = ctx.new_page()
        errors = []
        show.on('pageerror', lambda e: errors.append(str(e)))
        show.goto(out.as_uri())
        expect(show, 'impress 가 켜진다', "document.body.classList.contains('impress-enabled')")
        steps = show.evaluate("[...document.querySelectorAll('.step')].map((s) => [s.id, +s.dataset.x, +s.dataset.y, +s.dataset.rotate, +s.dataset.scale])")
        check('숨긴 장을 뺀 7장과 전체 보기', [s[0] for s in steps] == ['lec-slide-1', 'lec-slide-2', 'lec-slide-3', 'lec-slide-4', 'lec-slide-6', 'lec-slide-7', 'lec-slide-8', 'lec-overview'], steps)
        check('격자 자리 — 4장에서 접고 간지에서 줄을 바꾼다', [s[1:3] for s in steps[:4]] == [[0, 0], [1472, 0], [2944, 0], [4416, 0]] and steps[5][1:3] == [0, 1872] and steps[6][1:3] == [1472, 1872], steps)
        check('적은 자리가 이긴다', steps[4][1:] == [0, 3000, 90, 2], steps[4])
        check('첫 장이 지금 장', show.evaluate("document.querySelector('.step.active')?.id") == 'lec-slide-1')
        show.keyboard.press('ArrowRight')
        expect(show, '→ 로 다음 장', "document.querySelector('.step.active')?.id === 'lec-slide-2'")
        check('제목의 id(mermaid)가 impress 를 깨지 않는다', not errors, errors)
        check('Mermaid 그림이 들어 있다', show.locator('#lec-slide-2 pre.mermaid svg').count() == 1)
        check('차트가 들어 있다', show.locator('#lec-slide-3 .lec-chart svg').count() >= 1)
        check('칸 배치가 그대로', show.locator('#lec-slide-3 .lec-slide.lec-grid .lec-cell').count() == 2)
        srcs = show.evaluate("[...document.querySelectorAll('img')].map((i) => i.getAttribute('src').slice(0, 15))")
        check('그림은 파일 안에 (data:)', srcs and all(s.startswith('data:image/png') for s in srcs), srcs)
        show.evaluate('document.fonts.ready')
        fonts = until(show, "[...document.fonts].filter((f) => f.family.includes('KaTeX') && f.status === 'loaded').length", 6000)
        check('수식 글꼴이 파일 안에서 불린다', fonts > 0, fonts)
        check('바깥 요청이 없다', not outside, outside[:5])
        check('스크립트는 impress.js 와 시작 줄 둘', show.evaluate("document.scripts.length") == 2)
        check('문서가 심은 이벤트가 돌지 않는다', show.evaluate('window.EVIL') is None and show.locator('[onerror]').count() == 0)
        links = show.evaluate("[...document.querySelectorAll('#lec-slide-4 a')].map((a) => [a.textContent, a.getAttribute('href'), a.getAttribute('target')])")
        check('바깥 링크는 새 창, 프로젝트 안 링크는 글로', ['바깥', 'https://example.com/page', '_blank'] in links and ['다른 문서', None, None] in links, links)
        check('노트는 숨기고 장 안에', show.locator('#lec-slide-1 .notes').count() == 1 and not show.locator('#lec-slide-1 .notes').is_visible())
        check('앱 표시가 남지 않는다', show.locator('[data-lines], .lec-tag, .lec-slide-play, .code-copy').count() == 0)
        check('파일 제목', show.title() == '전환 시험 발표', show.title())
        show.keyboard.press('End')
        expect(show, 'End 로 전체 보기', "document.body.classList.contains('impress-on-lec-overview')")
        show.keyboard.press('Home')
        expect(show, 'Home 으로 첫 장', "document.querySelector('.step.active')?.id === 'lec-slide-1'")
        with ctx.expect_page(timeout=8000) as info:
            show.keyboard.press('p')
        console = info.value
        expect(console, '발표자 콘솔(P)에 노트', "document.getElementById('notes')?.innerText.includes('첫 장의 노트')")
        show.keyboard.press('ArrowRight')
        expect(console, '넘기면 콘솔의 노트도', "!document.getElementById('notes')?.innerText.includes('첫 장의 노트')")
        crlf = base / 'CRLF 로 저장.html'   # 받은 사람이 편집기에서 CRLF 로 저장해도 — 브라우저는 스크립트 글을 LF 로 읽는다
        crlf.write_bytes(first.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        again = ctx.new_page()
        again.goto(crlf.as_uri())
        expect(again, 'CRLF 로 저장한 파일도 impress 가 켜진다', "document.body.classList.contains('impress-enabled')")
        ctx.close()

        print('[git 이 impress.js 를 CRLF 로 받아도 — 해시는 LF 로 맞춘 글로]')
        page.route('**/static/vendor/impress/impress.js', lambda route: route.fulfill(
            status=200, content_type='text/javascript', body=(Path(__file__).resolve().parents[2] / 'web/vendor/impress/impress.js').read_text(encoding='utf-8').replace('\n', '\r\n')))
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        page.click('#lec-html-go')
        expect(page, 'CRLF 사본으로도 만든다', "!document.querySelector('#lec-html-done').hidden", ms=20000)
        page.click('#lec-html-close')
        page.unroute('**/static/vendor/impress/impress.js')
        third = proj / '전환시험 3.html'
        check('셋째 파일에 CR 이 없다', third.is_file() and b'\r' not in third.read_bytes())
        ctx = b.new_context(viewport={'width': 1280, 'height': 720})
        cr = ctx.new_page()
        cr.goto(third.as_uri())
        expect(cr, 'CRLF 사본으로 만든 파일도 impress 가 켜진다', "document.body.classList.contains('impress-enabled')")
        ctx.close()

        print('[스크립트 없이 열면 — 장이 위에서 아래로]')
        flat = b.new_context(java_script_enabled=False, viewport={'width': 900, 'height': 800})
        fp = flat.new_page()
        fp.goto(out.as_uri())
        boxes = fp.evaluate("[...document.querySelectorAll('.lec-step')].map((s) => { const r = s.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.right)]; })")
        check('impress 가 꺼진 채', fp.evaluate("document.body.className") == 'impress-not-supported')
        check('장이 위에서 아래로', len(boxes) == 7 and all(boxes[i][0] < boxes[i + 1][0] for i in range(6)), boxes)
        check('창 폭에 맞춰 줄인다', all(right <= 900 for _, right in boxes), boxes)
        check('노트가 보인다', fp.locator('#lec-slide-1 .notes').is_visible())
        check('전체 보기 장은 없다', not fp.locator('#lec-overview').is_visible())
        flat.close()

        print('[Lectern 에서 열면 — 스크립트 없이 문서로]')
        page.wait_for_selector('#lec-tree .row.file[data-doc="전환시험.html"]', timeout=10000)
        page.locator('#lec-tree .row.file[data-doc="전환시험.html"]').click()
        frame = page.wait_for_selector('#lec-view iframe', timeout=10000).content_frame()
        frame.wait_for_selector('.lec-step')
        cls = frame.evaluate("document.body.className")
        check('Lectern 은 impress 를 돌리지 않는다', 'impress-not-supported' in cls.split() and 'impress-enabled' not in cls.split()
              and not frame.evaluate("document.querySelector('#impress > div')?.style.transform"), cls)   # window.impress 는 <div id="impress"> 라 보지 않는다
        check('Lectern 의 표시 스타일(frame.css)을 막지 않는다', frame.evaluate("[...document.styleSheets].some((s) => (s.href || '').endsWith('/static/css/frame.css') && s.cssRules.length > 0)"))
        width = page.evaluate("document.querySelector('#lec-view iframe').getBoundingClientRect().width")
        right = frame.evaluate("Math.max(...[...document.querySelectorAll('.lec-step')].map((s) => s.getBoundingClientRect().right))")
        check('장이 칸 폭 안에', right <= width + 1, (right, width))
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
