"""0.113.1 사람 시나리오 둘 — 같은 차트를 다른 자리에서 (D216): 문서의 기본 줄·내 색 조합·모아 보기·슬라이드·영어 화면·좁은 창·동료의 PC.

1. 보고서에 Claude 가 문서의 기본 줄 '<!-- 도해: 색 2 보고서 남색 -->' 을 넣어 두었다 — 계열이 하나인 막대(Vega-Lite)·선(ECharts)이 남색,
   막대 색을 적은 Plotly 차트는 원문 색 그대로.
2. 모아 보기의 '차트' — 보고서의 차트가 문서에서와 같은 색 (문서의 기본 줄을 따른다), 발표의 차트도 그 문서의 줄(내 색 조합 9)대로.
3. 발표(Lectern 슬라이드)는 '<!-- 도해: 색 9 회사 색 -->' — 설정 폴더의 내 색 조합. 막대는 회사 색의 첫 색, 열지도(ECharts)의 진한 끝도 그 색.
4. 슬라이드의 막대 '색 조합…' — 아홉 칸(내 것 포함)이 모두 다르고 지금은 9. 4 선명한 구분을 고르면 그 블록에 '// 색: 4 선명한 구분'.
5. 영어 화면 — 원문이 색을 정한 Plotly 차트의 'Color set…' 창에 영어 알림.
6. 좁은 창(900×640) — 알림이 있어도 창이 화면 안에, 마지막 칸까지 닿는다.
7. 동료의 PC(내 색 조합 파일이 없다) — 9 를 모르니 설정의 기본(1)으로, 표시 줄의 이름은 남는다.
8. 보고서 원문은 그대로, 발표는 표시 줄 하나. 화면 스크립트 오류 없음."""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
REPORT = f"""# 3분기 항만 보고

<!-- 도해: 색 2 보고서 남색 -->

## 1. 물동량

{FENCE}vega-lite
{{ "title": "월별 물동량", "width": "container", "height": 200,
  "data": {{"values": [{{"월": "7월", "값": 51}}, {{"월": "8월", "값": 48}}, {{"월": "9월", "값": 53}}]}},
  "mark": "bar", "encoding": {{"x": {{"field": "월", "type": "ordinal", "title": null}}, "y": {{"field": "값", "type": "quantitative"}}}} }}
{FENCE}

{FENCE}echarts
{{ "title": {{"text": "운임 지수"}}, "xAxis": {{"type": "category", "data": ["1주", "2주", "3주"]}}, "yAxis": {{"type": "value", "scale": true}},
  "series": [{{"type": "line", "data": [1010, 1045, 1032]}}] }}
{FENCE}

{FENCE}mermaid
flowchart LR
  A[입항] --> B[하역]:::key --> C[반출]
{FENCE}

{FENCE}plotly
{{ "data": [{{"type": "bar", "x": ["광양", "포항"], "y": [120, 95], "marker": {{"color": "#2f5d8a"}}}}],
  "layout": {{"title": {{"text": "항만별 처리량"}}, "height": 260}} }}
{FENCE}
"""
DECK = f"""---
marp: true
---

# 3분기 항만

<!-- 도해: 색 9 회사 색 -->

---

## 물동량

{FENCE}vega-lite
{{ "width": "container", "height": 200,
  "data": {{"values": [{{"월": "7월", "값": 51}}, {{"월": "8월", "값": 48}}, {{"월": "9월", "값": 53}}]}},
  "mark": "bar", "encoding": {{"x": {{"field": "월", "type": "ordinal", "title": null}}, "y": {{"field": "값", "type": "quantitative"}}}} }}
{FENCE}

---

## 흐름

{FENCE}mermaid
flowchart LR
  A[입항] --> B[하역]:::key
{FENCE}

---

## 지연

{FENCE}echarts
{{ "xAxis": {{"type": "category", "data": ["7월", "8월", "9월"]}}, "yAxis": {{"type": "category", "data": ["광양", "포항"]}},
  "visualMap": {{"min": 0, "max": 8, "show": false}},
  "series": [{{"type": "heatmap", "data": [[0, 0, 5], [1, 0, 7], [2, 0, 6], [0, 1, 3], [1, 1, 4], [2, 1, 8]]}}] }}
{FENCE}
"""
MINE = {'kind': 'colors', 'number': 9, 'name': '회사 색', 'tip': '회사 로고의 초록과 금색', 'series': ['#0b3d2e', '#5fa37f', '#c9a227', '#7a7a7a'], 'strong': '#0b3d2e', 'accent': '#c9a227'}
CH = '#lec-view pre.lec-chart'
COLORS_OF = """(n) => { const svg = n?.querySelector('svg'); if (!svg) return [];
  const out = new Set(); for (const el of svg.querySelectorAll('path, rect, circle, line, polygon, polyline')) for (const a of ['fill', 'stroke']) {
    const v = (el.style.getPropertyValue(a) || el.getAttribute(a) || '').toLowerCase().replace(/\\s+/g, ''); if (v && v !== 'none' && !v.startsWith('url(')) out.add(v); }
  return [...out]; }"""
COLORS = f"(i) => ({COLORS_OF})([...document.querySelectorAll('{CH}')][i])"
PART = f"(sel) => ({COLORS_OF})(document.querySelector(sel))"
MARKS = f"() => [...document.querySelectorAll('{CH}')].map((n) => n.dataset.diagramColors || '-')"
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg'); if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect, circle, polygon, line, image')) {
    if (el.tagName === 'image') { const h = el.getAttribute('href') || el.getAttribute('xlink:href') || ''; out.add('img' + h.length + h.slice(-24)); continue; }
    for (const a of ['fill', 'stroke']) { const v = (el.style.getPropertyValue(a) || el.getAttribute(a) || '').toLowerCase().replace(/\\s+/g, ''); if (v && v !== 'none' && !v.startsWith('url(')) out.add(a[0] + v); }
  }
  return [...out].sort().join(' '); })"""
NOTE = "() => { const n = document.querySelector('#lec-dpick-same'); return n && !n.hidden ? n.textContent : ''; }"
EMIT = "(d) => import('/static/js/store.js').then((m) => m.emit('parts', d))"


def rgb(h):
    return f'rgb({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)})'


def has(colors, h):
    return h.lower() in colors or rgb(h) in colors


base = Path(tempfile.mkdtemp(prefix='lec-scen1131b-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '보고서.md'
rep.write_text(REPORT, encoding='utf-8', newline='\n')
deck = proj / '발표.md'
deck.write_text(DECK, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False, 'language': 'ko'}), encoding='utf-8')
mine_dir = config / 'diagram-styles'
mine_dir.mkdir()
(mine_dir / '회사 색.json').write_text(json.dumps(MINE, ensure_ascii=False), encoding='utf-8')
text = lambda f: f.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def drawn(n):
            return until(page, lambda: page.locator(f'{CH}.chart-ok').count() == n, ms=60000)

        def colors(i):
            return page.evaluate(COLORS, i)

        def marks():
            return page.evaluate(MARKS)

        def open_doc(name, n, title):
            page.click(f'#lec-tree .row[data-doc="{name}"]')
            until(page, lambda: page.locator('#lec-view h1', has_text=title).count() > 0, ms=20000)
            drawn(n)
            page.wait_for_timeout(150)

        def picker(i, item='색 조합…'):
            node = page.locator(CH).nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 30, 'y': 30})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(150)
            return page.evaluate(LOOKS), page.evaluate(NOTE)

        print('[1. 보고서 — 문서의 기본 줄 2]')
        open_doc('보고서.md', 3, '3분기 항만 보고')
        check('세 차트 모두 문서의 줄 2', marks() == ['2', '2', '2'], marks())
        check('계열이 하나인 Vega-Lite 막대가 남색 (#17304f)', has(colors(0), '#17304f') and not has(colors(0), '#4c78a8'), colors(0))
        check('계열이 하나인 ECharts 선도 남색', has(colors(1), '#17304f'), colors(1))
        check('막대 색을 적은 Plotly 는 원문 색 (#2f5d8a)', has(colors(2), '#2f5d8a'), colors(2))

        print('[2. 모아 보기의 차트 — 문서에서와 같은 색]')
        page.evaluate(EMIT, {'path': '', 'kind': 'chart'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        until(page, lambda: page.locator('#lec-view .pv-chunk pre.lec-chart.chart-ok').count() == 5, ms=60000)
        page.wait_for_timeout(300)
        pv_bar = page.evaluate(PART, '#lec-view .pv-chunk[data-doc="보고서.md"] pre.lec-chart[data-chart="vega-lite"]')
        check('보고서의 막대는 모아 보기에서도 남색 (문서의 기본 줄)', has(pv_bar, '#17304f'), pv_bar)
        pv_line = page.evaluate(PART, '#lec-view .pv-chunk[data-doc="보고서.md"] pre.lec-chart[data-chart="echarts"]')
        check('보고서의 선도', has(pv_line, '#17304f'), pv_line)
        pv_deck = page.evaluate(PART, '#lec-view .pv-chunk[data-doc="발표.md"] pre.lec-chart[data-chart="vega-lite"]')
        check('발표의 막대는 그 문서의 줄(내 색 조합 9)대로 (#0b3d2e)', has(pv_deck, '#0b3d2e'), pv_deck)
        page.evaluate(EMIT, {'path': '', 'kind': 'diagram'})
        until(page, lambda: page.locator('#lec-view .pv-chunk pre.mermaid.mermaid-ok').count() == 2, ms=60000)
        keys = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#lec-view .pv-chunk')].map((c) => {
          const r = c.querySelector('pre.mermaid g.node.key rect, pre.mermaid g.node.key path'); return [c.dataset.doc, r ? getComputedStyle(r).fill : '']; }))""")
        check('모아 보기의 흐름도도 그 문서의 줄대로 — 발표의 핵심 상자는 회사 색 (#0b3d2e)', keys.get('발표.md') == 'rgb(11, 61, 46)', keys)
        check('보고서의 핵심 상자는 남색', keys.get('보고서.md') == 'rgb(23, 48, 79)', keys)

        print('[3. 발표 — 내 색 조합 9]')
        open_doc('발표.md', 2, '3분기 항만')
        check('두 차트 모두 9', marks() == ['9', '9'], marks())
        check('슬라이드의 막대가 회사 색의 첫 색 (#0b3d2e)', has(colors(0), '#0b3d2e'), colors(0))
        check('열지도의 진한 끝도 회사 색 (#0b3d2e)', has(colors(1), '#0b3d2e'), colors(1))

        print('[4. 슬라이드의 막대 — 고르기 창]')
        looks, note = picker(0)
        check('아홉 칸(내 것 포함)이 모두 다르다', len(looks) == 9 and len(set(looks)) == 9, len(set(looks)))
        check("지금은 9, 그 칸에 '내 것'", page.locator('#lec-dpick .dpick-card.on').get_attribute('data-n') == '9'
              and page.locator('#lec-dpick .dpick-card[data-n="9"] .dpick-name em').count() == 1)
        check('알림 없음', not note, note)
        page.locator('#lec-dpick .dpick-card[data-n="4"]').click()
        until(page, lambda: '// 색: 4 선명한 구분\n' in text(deck), ms=8000)
        check("그 블록에 '// 색: 4 선명한 구분' (문서의 줄은 그대로)", '```vega-lite\n// 색: 4 선명한 구분\n{ "width"' in text(deck) and '<!-- 도해: 색 9 회사 색 -->' in text(deck), text(deck)[:260])
        until(page, lambda: marks() == ['4', '9'], ms=15000)
        drawn(2)
        check('막대가 선명한 구분의 첫 색 (#4e79a7)', has(colors(0), '#4e79a7'), colors(0))

        print('[5. 영어 화면 — 원문이 색을 정한 차트의 알림]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if not page.locator('#lec-view h1', has_text='3분기 항만 보고').count():
            page.click('#lec-tree .row[data-doc="보고서.md"]')
        until(page, lambda: page.locator('#lec-view h1', has_text='3분기 항만 보고').count() > 0, ms=20000)
        drawn(3)
        looks, note = picker(2, 'Color set…')
        check('Plotly 막대(원문 색): 칸이 같다', len(set(looks)) == 1, looks[0][:60])
        check("영어 알림 'the source sets its own colors'", note.startswith('All tiles look the same — the source sets its own colors'), note)
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if not page.locator('#lec-view h1', has_text='3분기 항만 보고').count():
            page.click('#lec-tree .row[data-doc="보고서.md"]')
        until(page, lambda: page.locator('#lec-view h1', has_text='3분기 항만 보고').count() > 0, ms=20000)
        drawn(3)

        print('[6. 좁은 창 — 알림이 있어도]')
        page.set_viewport_size({'width': 900, 'height': 640})
        page.wait_for_timeout(400)
        looks, note = picker(2)
        box = page.evaluate("() => { const r = document.querySelector('#lec-dpick .dialog-box').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, innerWidth, innerHeight]; }")
        check('알림이 보이고 창이 화면 안에', bool(note) and box[0] >= 0 and box[1] >= 0 and box[2] <= box[4] and box[3] <= box[5], (note[:30], box))
        last = page.locator('#lec-dpick .dpick-card').last
        last.scroll_into_view_if_needed()
        ok = page.evaluate("() => { const g = document.querySelector('#lec-dpick-grid').getBoundingClientRect(); const cs = document.querySelectorAll('#lec-dpick .dpick-card'); const c = cs[cs.length - 1].getBoundingClientRect(); return c.bottom <= g.bottom + 1 && c.top >= g.top - 1; }")
        check('마지막 칸까지 창 안에서 스크롤로 닿는다', ok)
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.wait_for_timeout(300)

        print('[7. 동료의 PC — 내 색 조합 파일이 없다]')
        (mine_dir / '회사 색.json').unlink()
        open_doc('발표.md', 2, '3분기 항만')
        until(page, lambda: marks() == ['4', '1'], ms=15000)
        drawn(2)
        check('9 를 모르니 열지도는 설정의 기본(1) — 회사 색이 아니다', marks() == ['4', '1'] and not has(colors(1), '#0b3d2e'), (marks(), colors(1)))
        check("문서의 줄 '색 9 회사 색' 은 원문에 그대로", '<!-- 도해: 색 9 회사 색 -->' in text(deck))

        print('[8. 원문]')
        check('보고서 원문은 그대로', text(rep) == REPORT)
        check('발표는 표시 줄 하나만 더해졌다', text(deck) == DECK.replace('{ "width"', '// 색: 4 선명한 구분\n{ "width"', 1), text(deck)[:300])
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
