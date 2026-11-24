"""모아 보기 (D196): 사이드바의 이름 목록이 아니라 문서 탭 하나의 화면 — 문서 속 표·그림·차트 등을 실제 모습으로 펼쳐 놓는다.
사람이 쓰는 차례로 — 조사 폴더의 표를 모아 보고, 내용으로 걸러 견주고, 출처 줄로 그 문서에 갔다가 Alt+← 로 돌아오고, 거른 것을 새 문서·AI 도구로 넘긴다.
종류마다(그림·다이어그램·차트·강조글·박스글·코드·수식은 실제 요소, 할 일·링크·출처는 한 줄), 문서 정보·파일 종류, html 문서(정화),
문서가 심은 단추, 밖에서 고쳤을 때, 범위 바꾸기, 닫기, 영어 화면"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-partsview-'))
proj = base / 'proj'
(proj / '2-조사').mkdir(parents=True)
(proj / 'data').mkdir()
(proj / '2-조사' / '그림.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100" viewBox="0 0 160 100"><rect width="160" height="100" fill="#2b5c8a"/><circle cx="80" cy="50" r="30" fill="#ffffff"/></svg>', encoding='utf-8')


def put(rel, text):
    (proj / rel).write_text(text, encoding='utf-8', newline='\n')


PRICE = '''---
status: 초안
author: 김연구
---

# 가격 동향

## 2.1 분기별 가격

표 1. 구리 분기별 가격

| 분기 | 가격 | 전기비 |
|---|---:|---:|
| 1Q | 9,210 | +3.1% |
| 2Q | 9,480 | +2.9% |

자료: LME

본문입니다. [수급 전망](수급-전망.md#3-공급) 과 [없는 문서](없음.md), [이 문서의 절](#22-알루미늄) 을 봅니다.

## 2.2 알루미늄

표 2. 알루미늄 분기별 가격

| 분기 | 가격 | 비고 |
|---|---:|---|
| 1Q | 2,310 | [공급 절](#21-분기별-가격) |
| 2Q | 2,405 | <button type="button" class="parts-send" data-act="ai">심은 단추</button> |

주: 평균 가격
자료: LME

> [!NOTE]
> 구리 가격은 2분기에 올랐습니다.

그림 1. 앱 아이콘

![앱 아이콘](그림.svg)

- [ ] 구리 재고 확인
- [x] 가격 표 넣기

```python
def price(q):
    return {'1Q': 9210}[q]
```

$$
E = mc^2
$$

<!-- box -->
**박스 1. 구리 시장의 구조**

구리는 칠레와 페루에서 많이 납니다.
<!-- /box -->
'''
put('2-조사/가격-동향.md', PRICE)
put('2-조사/수급-전망.md', '''---
status: 검토
---

# 수급 전망

## 3 공급

표 1. 광산별 생산량

| 광산 | 나라 | 생산량 |
|---|---|---:|
| 에스콘디다 | 칠레 | 1,050 |
| 그라스버그 | 인도네시아 | 780 |

자료: 각 사 보고서

그림 1. 공급 흐름

```mermaid
flowchart LR
  광산 --> 제련 --> 가공
```

그림 2. 분기별 가격 (차트)

```vega-lite
{"data": {"values": [{"q": "1Q", "v": 9210}, {"q": "2Q", "v": 9480}]}, "mark": "bar", "encoding": {"x": {"field": "q", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}}}
```

![앱 아이콘](그림.svg)

2분기 구리 가격은 9,480 입니다.[^1]

[^1]: LME 2026년 2분기 자료.
''')
put('개요.md', '# 개요\n\n표 1. 요약\n\n| 항목 | 값 |\n|---|---|\n| 니켈 | 하락 |\n\n- [ ] 요약 쓰기\n')
put('자료.html', '<html><body><h1>자료</h1><h2>html 의 절</h2><table onclick="window.__bad=1"><caption>표 1. html 의 표</caption><tr><th>a</th><th>b</th></tr>'
    '<tr><td>구리</td><td><img src="x" onerror="window.__bad=1">2</td></tr></table><script>window.__bad=1</script></body></html>')
put('data/가격.csv', '분기,가격\n1Q,9210\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

EMIT = "(d) => import('/static/js/store.js').then((m) => m.emit('parts', d))"
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
VIEW = "() => import('/static/js/store.js').then((m) => ({ type: m.S.view?.type, path: m.S.view?.path || '' }))"
TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
CHUNKS = """() => [...document.querySelectorAll('#lec-view .parts-list .pv-chunk')].map((e) => ({ doc: e.dataset.doc, kind: e.dataset.kind, n: +e.dataset.n,
  sec: e.querySelector('.pv-sec')?.textContent || '', name: e.querySelector('.pv-name').textContent, detail: e.querySelector('.pv-detail')?.textContent || '',
  lines: e.querySelector('.pv-lines')?.textContent || '', real: !!e.querySelector('.pv-body.md-body'),
  cap: e.querySelector('.pv-body .lec-caption')?.textContent.trim() || '', src: [...e.querySelectorAll('.pv-body .lec-source')].map((p) => p.textContent.trim()).join(' / '),
  rows: e.querySelector('.pv-body table')?.rows.length || 0 }))"""
INFO = "() => document.querySelector('#lec-view .parts-info')?.textContent || ''"
DONE = "() => { const g = [...document.querySelectorAll('#lec-view .pv-spread')]; return g.length > 0 && g.every((x) => x.classList.contains('pv-done')); }"
READ = "() => { const t = document.querySelector('#lec-view .parts-info')?.textContent || ''; return !!t && !t.includes('읽는 중'); }"
KINDS = "() => Object.fromEntries([...document.querySelectorAll('#lec-view .parts-kinds button[data-kind]')].map((b) => [b.dataset.kind, +b.querySelector('.n').textContent]))"
SEEN = """(word) => { const t = [...document.querySelectorAll('#lec-view .table-wrap')].find((w) => w.textContent.includes(word));
  const r = t?.getBoundingClientRect(); const c = document.querySelector('#lec-content').getBoundingClientRect(); return !!r && r.bottom > c.top + 20 && r.top < c.bottom - 20; }"""
PASTED = "() => window.__pasted || []"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
ROWS = "() => [...document.querySelectorAll('#lec-view .parts-list .pt-item')].map((e) => [e.dataset.doc, e.querySelector('.pt-name').textContent, e.querySelector('.pt-label')?.textContent || ''])"
TOP = "() => document.querySelector('#lec-content').scrollTop"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1360, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")

        def view():
            return page.evaluate(VIEW)

        def kind(k):
            page.click(f'#lec-view .parts-kinds button[data-kind="{k}"]')
            until(page, f"() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind === '{k}'")

        def chunks():
            return page.evaluate(CHUNKS)

        def gather(**d):
            page.evaluate(EMIT, {'path': '', **d})
            page.wait_for_selector('#lec-view.parts-view .parts-list', timeout=15000)
            until(page, READ, 15000)

        print('[열기 — 문서 탭 하나에, 실제 모습으로]')
        page.evaluate(OPEN, '2-조사/가격-동향.md')
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=20000)
        check("사이드바에 '모아 보기' 탭이 없다 — 파일·최근 변경·검색·담기", page.evaluate("() => [...document.querySelectorAll('.side-tabs button')].map((x) => x.dataset.tab)") == ['files', 'recent', 'search', 'basket'],
              page.evaluate("() => [...document.querySelectorAll('.side-tabs button')].map((x) => x.dataset.tab)"))
        gather(kind='table')
        expect(page, '보던 문서를 두고 새 문서 탭에 — 탭 이름은 모아 보기', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기*'], lambda: page.evaluate(TABS))
        check("화면 종류는 'parts', 범위는 프로젝트 전체", view() == {'type': 'parts', 'path': ''} and page.inner_text('#lec-view .parts-scope') == 'proj 전체', (view(), page.inner_text('#lec-view .parts-scope')))
        expect(page, '표 다섯을 문서별로 — 개수', lambda: page.evaluate(INFO) == '문서 4개, 표 5개', lambda: page.evaluate(INFO))
        until(page, DONE, 15000)
        got = chunks()
        check('덩어리마다 실제 표가 그려진다', len(got) == 5 and all(c['real'] and c['rows'] >= 2 for c in got), got)
        first = got[0]
        check('출처 줄: 절 › 이름 · 크기, 원문 줄', first['doc'] == '2-조사/가격-동향.md' and first['sec'] == '2.1 분기별 가격' and first['name'] == '표 1' and first['detail'] == '2행 3열' and first['lines'] == '10~15행', first)
        check("캡션과 '자료:' 줄이 표와 함께 온다", first['cap'] == '표 1. 구리 분기별 가격' and first['src'] == '자료: LME', first)
        check("주·자료 두 줄도 함께", '주: 평균 가격' in got[1]['src'] and '자료: LME' in got[1]['src'], got[1])
        check('문서 머리줄 넷 (트리 순서)', page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-list .pt-doc .label')].map((e) => e.textContent)") == ['가격-동향.md', '수급-전망.md', '개요.md', '자료.html'],
              page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-list .pt-doc .label')].map((e) => e.textContent)"))
        check('표에 [복사] 단추', page.locator('#lec-view .pv-chunk .table-wrap > .table-copy').count() == 5, page.locator('#lec-view .pv-chunk .table-copy').count())
        check('상태줄에 범위와 개수', page.inner_text('#lec-st-path') == '모아 보기 — proj (프로젝트 전체)' and '표 5개' in page.inner_text('#lec-st-info'), (page.inner_text('#lec-st-path'), page.inner_text('#lec-st-info')))

        print('[html 문서의 표 — 정화해서]')
        html = [c for c in got if c['doc'] == '자료.html'][0]
        check('html 문서의 표도 펼친다 (절 이름, 줄 번호는 없다)', html['real'] and html['sec'] == 'html 의 절' and html['lines'] == '', html)
        check('스크립트·이벤트 속성은 돌지 않고 남지 않는다', page.evaluate("() => !window.__bad && !document.querySelector('#lec-view .pv-chunk [onclick], #lec-view .pv-chunk [onerror], #lec-view .pv-chunk script')"))

        print('[목차 패널 — 모은 것의 차례]')
        toc = page.evaluate("() => [...document.querySelectorAll('#lec-toc a[data-i]')].map((a) => [a.closest('li').className.trim(), a.querySelector('.tp-name').textContent, a.querySelector('.tp-label')?.textContent || ''])")
        check('문서와 그 아래 구성 요소 (캡션이 이름표)', toc[:3] == [['lv0', '가격-동향.md', ''], ['part', '표 1', '표 1. 구리 분기별 가격'], ['part', '표 2', '표 2. 알루미늄 분기별 가격']] and len(toc) == 9, toc)
        check('목차 머리는 모아 보기', page.inner_text('#lec-toc .toc-head') == '모아 보기')
        page.locator('#lec-toc a[data-i]', has_text='html 의 표').click()
        expect(page, '차례를 누르면 그 덩어리로', "() => { const r = document.querySelector('#lec-view .pv-chunk[data-doc=\"자료.html\"]').getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight - 60; }")
        page.evaluate("() => { document.querySelector('#lec-content').scrollTop = 0; }")

        print('[내용으로 거르기]')
        page.keyboard.press('Control+f')
        expect(page, 'Ctrl+F 는 이 화면의 거르기 칸으로', "() => document.activeElement?.classList.contains('parts-filter')")
        page.keyboard.type('칠레')
        expect(page, "'칠레' — 칸에 그 글이 든 표만 (이름·캡션에는 없다)", lambda: [(c['doc'], c['n']) for c in chunks()] == [('2-조사/수급-전망.md', 1)], chunks)
        expect(page, '— 개수는 거른 결과', lambda: page.evaluate(INFO) == '거른 결과 1개 (모두 5개)', lambda: page.evaluate(INFO))
        expect(page, '— 맞은 낱말을 표시한다', "() => [...document.querySelectorAll('#lec-view .pv-chunk mark.pv-hit')].map((m) => m.textContent).join() === '칠레'")
        check('거르는 동안 초점은 거르기 칸에 남는다', page.evaluate("() => document.activeElement?.classList.contains('parts-filter')"))
        page.fill('#lec-view .parts-filter', 'LME 알루미늄')
        expect(page, '낱말 둘은 둘 다 든 것만 — 자료 줄과 캡션', lambda: [(c['doc'], c['n']) for c in chunks()] == [('2-조사/가격-동향.md', 2)], chunks)
        page.fill('#lec-view .parts-filter', '구리')
        expect(page, "'구리' — 캡션·칸에 든 표 둘 (html 문서의 것도)", lambda: [(c['doc'], c['n']) for c in chunks()] == [('2-조사/가격-동향.md', 1), ('자료.html', 1)], chunks)
        expect(page, '— 다시 걸러도 표시는 지금 낱말로만', "() => { const m = [...document.querySelectorAll('#lec-view .pv-chunk mark.pv-hit')].map((x) => x.textContent); return m.length >= 2 && m.every((x) => x === '구리'); }")
        check('목차도 거른 것만', page.locator('#lec-toc a[data-i]').count() == 4, page.locator('#lec-toc a[data-i]').count())

        print('[넘기기 — AI 도구에, 새 문서로]')
        page.click('#lec-view .parts-send[data-act="ai"]')
        expect(page, "'AI 에': 보이는 것의 위치를 한 줄로 — Enter 없이 (html 문서는 줄 없이)", lambda: page.evaluate(PASTED) == ["@2-조사/가격-동향.md 10~15행 ('표 1. 구리 분기별 가격'), @자료.html ('표 1. html 의 표') "],
               lambda: page.evaluate(PASTED))
        expect(page, '— 터미널에 넣었다고 알린다', lambda: '터미널에 넣었습니다' in page.evaluate(TOAST), lambda: page.evaluate(TOAST), ms=40000)   # 이 알림이 아래 알림을 덮지 않게 기다린다
        page.click('#lec-view .parts-send[data-act="doc"]')
        expect(page, "'새 문서로': 새 문서의 경로를 묻는 창부터", "() => !document.querySelector('#lec-insert').hidden && document.querySelector('#lec-insert-title').textContent.includes('새 문서로')",
               lambda: page.inner_text('#lec-insert-title'))
        check('— html 문서의 것은 원문이 없어 빠진다고 알린다', 'html 문서' in page.evaluate(TOAST), page.evaluate(TOAST))
        check('— 처음 값은 프로젝트 폴더의 새 문서', page.input_value('#lec-insert-input') == '새 문서.md', page.input_value('#lec-insert-input'))
        page.fill('#lec-insert-input', '2-조사/구리-표.md')
        page.keyboard.press('Enter')
        made = proj / '2-조사' / '구리-표.md'
        until(page, lambda: made.exists() and '자료: LME' in made.read_text(encoding='utf-8'), 8000)
        text = made.read_text(encoding='utf-8') if made.exists() else ''
        check('— 그 경로에 새 문서가 생기고 캡션·표·자료 줄이 들어간다', '표 1. 구리 분기별 가격' in text and '| 1Q | 9,210 | +3.1% |' in text and '자료: LME' in text and 'html 의 표' not in text, text[:300])
        expect(page, '— 새 문서는 새 문서 탭에서 열린다 (모아 보기 탭은 남는다)', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기', '구리-표.md*'], lambda: page.evaluate(TABS))
        page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); const d = await import('/static/js/doctabs.js'); const e = await import('/static/js/editor.js');
          const pane = S.tab.panes.find((x) => x.current?.path === '2-조사/구리-표.md'); if (pane?.editor) e.closeEditor(pane, { ask: false, sync: false }); if (pane) d.closeDocTab(pane);
          await d.selectDocTab(S.tab.panes.find((x) => x.current?.type === 'parts')); }""")
        made.unlink()
        page.wait_for_selector('#lec-view.parts-view .parts-list')
        expect(page, '— 닫고 모아 보기 탭으로', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기*'], lambda: page.evaluate(TABS))
        expect(page, '새 문서를 지우면 표 수가 돌아온다', lambda: page.evaluate(KINDS).get('table') == 5, lambda: page.evaluate(KINDS))
        check('거르기 칸의 글은 그대로', page.input_value('#lec-view .parts-filter') == '구리')
        page.focus('#lec-view .parts-filter')
        page.keyboard.press('Escape')
        expect(page, '거르기 칸의 Esc 는 지운다', lambda: page.input_value('#lec-view .parts-filter') == '' and len(chunks()) == 5, chunks)

        print('[출처 줄로 가고 Alt+← 로 돌아오기]')
        until(page, DONE, 15000)
        page.fill('#lec-view .parts-filter', '생산량')
        expect(page, '거른 뒤', lambda: len(chunks()) == 1, chunks)
        page.click('#lec-view .pv-chunk[data-doc="2-조사/수급-전망.md"] .pv-go')
        page.wait_for_selector('#lec-view h1:has-text("수급 전망")', timeout=15000)
        expect(page, '출처 줄을 누르면 이 탭에서 그 문서의 그 표로', lambda: view() == {'type': 'doc', 'path': '2-조사/수급-전망.md'} and page.evaluate(SEEN, '에스콘디다'), view)
        check('— 탭은 늘지 않는다', page.evaluate(TABS) == ['가격-동향.md', '수급-전망.md*'], page.evaluate(TABS))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        expect(page, 'Alt+← 로 모아 보기에 — 거르기와 종류가 그대로', lambda: page.input_value('#lec-view .parts-filter') == '생산량' and len(chunks()) == 1 and view() == {'type': 'parts', 'path': ''}, chunks)
        page.fill('#lec-view .parts-filter', '')
        expect(page, '다 보인다', lambda: len(chunks()) == 5, chunks)
        page.click('#lec-view .pv-chunk[data-doc="2-조사/가격-동향.md"][data-n="2"] .pv-go')
        expect(page, '다른 탭에 열려 있는 문서면 그 탭으로 가서 그 표로', lambda: page.evaluate(TABS) == ['가격-동향.md*', '모아 보기'] and page.evaluate(SEEN, '2,405'), lambda: page.evaluate(TABS))
        page.locator('#lec-doctab-list .doc-tab', has_text='모아 보기').click()
        page.wait_for_selector('#lec-view.parts-view .pv-chunk')
        page.click('#lec-view .pv-chunk[data-doc="개요.md"] .pv-go', modifiers=['Control'])
        expect(page, 'Ctrl+누르기는 보던 화면을 두고 뒤에서 새 문서 탭', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기*', '개요.md'], lambda: page.evaluate(TABS))
        page.locator('#lec-view .pv-chunk[data-doc="개요.md"]').focus()
        page.keyboard.press('Enter')
        expect(page, '덩어리에 초점을 두고 Enter 도 그 문서로', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기', '개요.md*'], lambda: page.evaluate(TABS))
        page.locator('#lec-doctab-list .doc-tab', has_text='개요.md').click(button='middle')
        page.locator('#lec-doctab-list .doc-tab', has_text='모아 보기').click()
        page.wait_for_selector('#lec-view.parts-view .pv-chunk')

        print('[표 안의 링크와 문서가 심은 단추]')
        until(page, DONE, 15000)
        before = len(page.evaluate(PASTED))
        planted = page.locator('#lec-view .pv-chunk[data-doc="2-조사/가격-동향.md"][data-n="2"] .pv-body button.parts-send')
        check('문서가 심은 단추가 표 안에 그대로 있다 (시험의 전제)', planted.count() == 1, planted.count())
        if planted.count():
            planted.click()
            page.wait_for_timeout(300)
        check("— 그 'parts-send' 단추는 앱의 단추로 읽지 않는다 — 터미널에 넣지 않는다", len(page.evaluate(PASTED)) == before, page.evaluate(PASTED))
        page.locator('#lec-view .pv-chunk[data-doc="2-조사/가격-동향.md"][data-n="2"] .pv-body a', has_text='공급 절').click()
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=15000)
        check('표 안의 #절 링크는 그 문서의 그 절로 (이 화면에는 그 절이 없다)', page.evaluate(TABS) == ['가격-동향.md*', '모아 보기'] and not page.evaluate(TOAST).startswith('문서에서 해당'), (page.evaluate(TABS), page.evaluate(TOAST)))
        page.locator('#lec-doctab-list .doc-tab', has_text='모아 보기').click()
        page.wait_for_selector('#lec-view.parts-view .pv-chunk')

        print('[우클릭 — 위치·원문·담기]')
        page.locator('#lec-view .pv-chunk[data-doc="2-조사/수급-전망.md"] .pv-body table td').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden]) .menu-row')
        menu = page.evaluate("() => ({ rows: [...document.querySelectorAll('#lec-menu button[data-i]')].map((x) => (x.querySelector('span') || x).textContent.trim()), ref: [...document.querySelectorAll('#lec-menu .menu-row')].find((r) => r.textContent.includes('위치 복사'))?.querySelector('button').title })")
        check('표 위에서 우클릭하면 그 덩어리의 메뉴', {'문서에서 보기', '원문 복사', '위치 복사', '담기'} <= set(menu['rows']) and any(r.startswith('보이는 것 모두 담기 (5개)') for r in menu['rows']), menu)
        check("— 위치는 '@경로 줄 (캡션)'", menu['ref'] == "@2-조사/수급-전망.md 9~14행 ('표 1. 광산별 생산량')", menu['ref'])
        page.keyboard.press('Escape')

        print('[그림·다이어그램·차트 — 격자에 실제로]')
        kind('figure')
        until(page, DONE, 15000)
        expect(page, '그림은 격자에, 같은 그림은 한 번만 (+1곳)', lambda: page.locator('#lec-view .pv-chunks.pv-grid .pv-chunk').count() == 1 and page.inner_text('#lec-view .pv-src .pt-more') == '+1곳',
               lambda: page.inner_text('#lec-view .parts-list')[:200])
        expect(page, '— 실제 그림이 불러와진다', "() => { const i = document.querySelector('#lec-view .pv-chunk .pv-body img'); return !!i && i.complete && i.naturalWidth > 0; }", ms=10000)
        check('— 캡션도 함께', chunks()[0]['cap'] == '그림 1. 앱 아이콘', chunks())
        kind('diagram')
        expect(page, '다이어그램은 그려서 (Mermaid)', "() => !!document.querySelector('#lec-view .pv-chunk[data-kind=\"diagram\"] .pv-body pre.mermaid svg')", ms=40000)
        kind('chart')
        expect(page, '차트도 그려서 (Vega-Lite)', "() => !!document.querySelector('#lec-view .pv-chunk[data-kind=\"chart\"] .pv-body pre.lec-chart svg')", ms=40000)
        page.fill('#lec-view .parts-filter', 'quantitative')
        expect(page, '차트의 설정 글은 거르기에 걸리지 않는다 (캡션·절로만)', lambda: page.evaluate(INFO).startswith('거른 결과 0개'), lambda: page.evaluate(INFO))
        page.fill('#lec-view .parts-filter', '분기별')
        expect(page, '— 캡션으로는 걸린다', lambda: len(chunks()) == 1, chunks)
        page.fill('#lec-view .parts-filter', '')

        print('[강조글·박스글·코드·수식]')
        kind('box')
        expect(page, '강조글은 그 상자 그대로', "() => !!document.querySelector('#lec-view .pv-chunk .pv-body blockquote') && document.querySelector('#lec-view .pv-chunk .pv-body').textContent.includes('2분기에 올랐습니다')")
        kind('textbox')
        expect(page, '박스글도 제목 띠와 함께', "() => !!document.querySelector('#lec-view .pv-chunk .pv-body aside.lec-textbox') && document.querySelector('#lec-view .pv-chunk .pv-body').textContent.includes('구리 시장의 구조')")
        kind('code')
        expect(page, '코드는 코드 상자로', "() => !!document.querySelector('#lec-view .pv-chunk .pv-body .code-block pre code')")
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.click('#lec-view .pv-chunk .pv-body .code-copy')
        expect(page, '— [복사] 가 그 코드를 복사한다', lambda: 'def price(q):' in page.evaluate('() => navigator.clipboard.readText()'), lambda: page.evaluate(TOAST))
        kind('math')
        expect(page, '수식도 그린 모습으로', "() => !!document.querySelector('#lec-view .pv-chunk .pv-body .math-block .katex')")

        print('[할 일·링크·출처 — 한 줄씩]')
        kind('task')
        expect(page, '할 일은 한 줄 목록 (안 한 것부터)', lambda: page.evaluate(ROWS) == [['2-조사/가격-동향.md', '구리 재고 확인', ''], ['개요.md', '요약 쓰기', '']] and page.locator('#lec-view .pv-chunk').count() == 0,
               lambda: page.evaluate(ROWS))
        check('종류 아래 단추: 안 한 것 2 · 한 것 1 · 모두 3', page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-sub button')].map((x) => x.textContent)") == ['안 한 것2', '한 것1', '모두3'],
              page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-sub button')].map((x) => x.textContent)"))
        page.click('#lec-view .parts-sub button[data-sub="done"]')
        expect(page, "'한 것'", lambda: page.evaluate(ROWS) == [['2-조사/가격-동향.md', '가격 표 넣기', '']], lambda: page.evaluate(ROWS))
        page.click('#lec-view .parts-sub button[data-sub="open"]')
        check("넘기는 단추는 한 줄 종류에도 — 'AI 에'", page.is_enabled('#lec-view .parts-send[data-act="ai"]'))
        kind('link')
        expect(page, '링크 — 깨진 것을 가른다', lambda: page.locator('#lec-view .pt-item .pt-bad').count() == 1 and len(page.evaluate(ROWS)) >= 2, lambda: page.evaluate(ROWS))
        kind('source')
        expect(page, '출처와 각주', lambda: any('각주' in r[2] for r in page.evaluate(ROWS)) and any(r[1].startswith('자료: LME') for r in page.evaluate(ROWS)), lambda: page.evaluate(ROWS))
        page.locator('#lec-view .pt-item', has_text='자료: 각 사 보고서').click()
        page.wait_for_selector('#lec-view h1:has-text("수급 전망")', timeout=15000)
        check('한 줄 행을 눌러도 이 탭에서 그 문서로', page.evaluate(TABS) == ['가격-동향.md', '수급-전망.md*'], page.evaluate(TABS))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pt-item', timeout=15000)

        print('[문서 정보·파일 종류]')
        page.click('#lec-view .parts-mode button[data-mode="meta"]')
        expect(page, '문서 정보: 맨 앞 설정의 키', lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-kinds button[data-mkey]')].map((x) => x.dataset.mkey)") == ['status', 'author'],
               lambda: page.inner_text('#lec-view .parts-kinds'))
        check('— 값마다 문서', page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-list .pt-val .label, #lec-view .parts-list .pt-mdoc .label')].map((e) => e.textContent)") in (
            ['검토', '수급-전망.md', '초안', '가격-동향.md'], ['초안', '가격-동향.md', '검토', '수급-전망.md']),
            page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-list .pt-val .label, #lec-view .parts-list .pt-mdoc .label')].map((e) => e.textContent)"))
        check("— 넘기는 단추는 '문서 속 요소'에서만, 목차는 비운다", page.locator('#lec-view .parts-send:visible').count() == 0 and page.locator('#lec-toc a').count() == 0)
        page.click('#lec-view .parts-mode button[data-mode="files"]')
        expect(page, '파일 종류: 문서·자료의 형식 단추', lambda: {'docs:md', 'docs:html', 'others:csv', 'others:svg'} <= set(page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-kinds button[data-ftype]')].map((x) => x.dataset.ftype)")),
               lambda: page.inner_text('#lec-view .parts-kinds'))
        page.click('#lec-view .parts-kinds button[data-ftype="docs:md"]')
        expect(page, '— 문서 행', lambda: page.locator('#lec-view .parts-list .ft-row').count() == 3, lambda: page.inner_text('#lec-view .parts-list'))
        page.click('#lec-view .parts-kinds button[data-ftype="others:svg"]')
        expect(page, '— 그림 파일은 작은 그림으로', "() => document.querySelector('#lec-view .parts-list .ft-thumb img')?.naturalWidth > 0", ms=8000)
        page.click('#lec-view .parts-mode button[data-mode="parts"]')
        kind('table')
        until(page, DONE, 15000)

        print('[밖에서 고쳤을 때 — 거르기를 두고 그 문서만 다시]')
        page.fill('#lec-view .parts-filter', '분기')
        expect(page, '거른 뒤 둘', lambda: len(chunks()) == 2, chunks)
        page.focus('#lec-view .parts-filter')
        time.sleep(0.3)
        put('2-조사/가격-동향.md', PRICE.replace('| 2Q | 9,480 | +2.9% |', '| 2Q | 9,480 | +2.9% |\n| 3Q | 9,700 | +2.3% |'))
        expect(page, 'Claude 가 행을 더하면 그 표가 바뀐다 (3행)', lambda: next((c for c in chunks() if c['n'] == 1), {}).get('detail') == '3행 3열' and next((c for c in chunks() if c['n'] == 1), {}).get('rows') == 4, chunks, ms=15000)
        check('— 거르기 칸의 글과 초점은 그대로', page.input_value('#lec-view .parts-filter') == '분기' and page.evaluate("() => document.activeElement?.classList.contains('parts-filter')"))
        put('2-조사/새-표.md', '# 새 표\n\n| 분기 | 값 |\n|---|---|\n| 4Q | 1 |\n')
        expect(page, '새 문서가 생기면 표 수가 는다', lambda: page.evaluate(KINDS).get('table') == 6, lambda: page.evaluate(KINDS), ms=15000)
        (proj / '2-조사' / '새-표.md').unlink()
        expect(page, '지우면 준다', lambda: page.evaluate(KINDS).get('table') == 5, lambda: page.evaluate(KINDS), ms=15000)
        page.fill('#lec-view .parts-filter', '')

        print('[범위 — 폴더 개요·우클릭, 전체]')
        page.locator('#lec-tree .row.dir[data-dir="2-조사"]').click(button='right')
        page.locator('#lec-menu button', has_text='이 폴더의 표·그림 등 모아 보기').click()
        expect(page, '폴더 우클릭: 열려 있는 모아 보기 탭에서 범위만 그 폴더로', lambda: view() == {'type': 'parts', 'path': '2-조사'} and page.inner_text('#lec-view .parts-scope') == '2-조사 폴더' and page.evaluate(TABS) == ['가격-동향.md', '모아 보기 · 2-조사*'],
               lambda: (view(), page.evaluate(TABS)))
        expect(page, '— 그 폴더의 표 셋', lambda: len(chunks()) == 3 and all(c['doc'].startswith('2-조사/') for c in chunks()), chunks)
        page.click('#lec-view .parts-all')
        expect(page, "'전체' 로 프로젝트 전체", lambda: view() == {'type': 'parts', 'path': ''} and len(chunks()) == 5, chunks)
        page.keyboard.press('Alt+ArrowLeft')
        expect(page, 'Alt+← 로 앞의 범위(그 폴더)로', lambda: view() == {'type': 'parts', 'path': '2-조사'} and len(chunks()) == 3, chunks)
        page.click('#lec-btn-overview')
        page.wait_for_selector('#lec-view.overview .ov-parts')
        page.click('#lec-view .ov-parts button[data-parts="figure"]')
        expect(page, '폴더 개요의 단추: 그 자리에서 모아 보기로 (문서를 보던 탭이 아니다), 그 종류로', lambda: view() == {'type': 'parts', 'path': ''} and page.evaluate("() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind") == 'figure',
               lambda: (view(), page.evaluate(TABS)))
        check('— 탭은 그대로 둘', len(page.evaluate(TABS)) == 2, page.evaluate(TABS))

        print('[탭 막대의 모아 보기 단추]')
        pressed = lambda: page.get_attribute('#lec-btn-parts', 'aria-pressed')  # noqa: E731
        check('모아 보기를 보는 동안 단추는 눌린 모양', pressed() == 'true', pressed())
        page.hover('#lec-btn-parts')
        expect(page, '마우스를 올리면 이름', "() => { const b = document.querySelector('#lec-tabtip'); return !!b && !b.hidden && b.querySelector('b').textContent === '모아 보기'; }")
        page.evaluate(EMIT, {'path': '2-조사'})
        expect(page, '범위를 폴더로', lambda: view() == {'type': 'parts', 'path': '2-조사'}, view)
        kind('table')
        page.fill('#lec-view .parts-filter', '알루미늄')
        expect(page, '거른 뒤 하나', lambda: len(chunks()) == 1, chunks)
        page.locator('#lec-doctab-list .doc-tab', has_text='가격-동향.md').click()
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")')
        check('문서를 보면 풀린다', pressed() == 'false', pressed())
        page.click('#lec-btn-parts')
        expect(page, '단추를 누르면 열려 있는 모아 보기 탭으로 — 범위와 거르기를 바꾸지 않는다', lambda: view() == {'type': 'parts', 'path': '2-조사'} and page.input_value('#lec-view .parts-filter') == '알루미늄'
               and len(chunks()) == 1 and len(page.evaluate(TABS)) == 2 and pressed() == 'true', lambda: (view(), page.evaluate(TABS)))
        page.fill('#lec-view .parts-filter', '')
        kind('figure')

        print('[명령 찾기·닫기]')
        page.keyboard.press('Control+w')
        expect(page, 'Ctrl+W 로 모아 보기 탭을 닫는다', lambda: page.evaluate(TABS) == ['가격-동향.md*'], lambda: page.evaluate(TABS))
        page.keyboard.press('Control+Shift+p')
        page.wait_for_selector('#lec-palette:not([hidden])')
        page.keyboard.type('모아 보기')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        expect(page, '명령 찾기의 모아 보기 — 마지막에 고른 종류(그림)로 다시', lambda: page.evaluate(TABS) == ['가격-동향.md', '모아 보기*'] and page.evaluate("() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind") == 'figure',
               lambda: page.evaluate(TABS))
        page.locator('#lec-doctab-list .doc-tab', has_text='가격-동향.md').click(button='middle')   # 가운데 버튼으로 닫기
        expect(page, '하나 남은 모아 보기 탭', lambda: page.evaluate(TABS) == ['모아 보기*'], lambda: page.evaluate(TABS))
        page.keyboard.press('Control+w')
        expect(page, '— 닫으면 폴더 개요로', lambda: view()['type'] == 'overview', view)
        page.click('#lec-btn-parts')
        expect(page, '열린 모아 보기가 없으면 단추가 프로젝트 전체를 연다 (폴더 개요 자리에)', lambda: view() == {'type': 'parts', 'path': ''} and len(page.evaluate(TABS)) == 1, lambda: (view(), page.evaluate(TABS)))

        print('[창 폭]')
        gather(kind='table')
        until(page, DONE, 15000)
        for width in (1040, 760):
            page.set_viewport_size({'width': width, 'height': 800})
            page.wait_for_timeout(400)
            wide = page.evaluate("""() => { const v = document.querySelector('#lec-content'); const edge = v.getBoundingClientRect().right;
              return [...v.querySelectorAll('*')].filter((e) => !e.closest('.table-wrap, pre, svg') && e.getBoundingClientRect().right > edge + 1)
                .map((e) => [e.tagName, String(e.className), Math.round(e.getBoundingClientRect().right - edge)]).slice(0, 6); }""")
            check(f'{width}px: 옆으로 넘치지 않는다 (표·코드는 제 상자 안에서 민다)', not wide, wide)
        page.set_viewport_size({'width': 1360, 'height': 900})

        print('[영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate(EMIT, {'path': '', 'kind': 'table'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        until(page, "() => { const t = document.querySelector('#lec-view .parts-info')?.textContent || ''; return !!t && !t.includes('Reading'); }", 15000)
        en = page.evaluate("() => ({ h: document.querySelector('#lec-view .parts-top h1').textContent, info: document.querySelector('#lec-view .parts-info').textContent, send: [...document.querySelectorAll('#lec-view .parts-send')].map((x) => x.textContent), ph: document.querySelector('#lec-view .parts-filter').placeholder, tab: document.querySelector('#lec-doctab-list .doc-tab.active .name').textContent })")
        check('영어 화면의 이름·개수·단추', en['h'] == 'Elements' and en['info'] == '4 documents, 5 tables' and en['send'][0] == 'To new document' and en['send'][1].startswith('To ') and 'content' in en['ph'] and en['tab'] == 'Elements', en)
        hangul = page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-head, #lec-view .parts-bar')].map((e) => e.innerText).join(' ').match(/[가-힣]+/g) || []")
        check('머리와 줄에 남은 한글 없음 (프로젝트 이름·문서 글 빼고)', not hangul, hangul)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
